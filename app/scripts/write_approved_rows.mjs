import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const configPath = process.argv[2];
if (!configPath) throw new Error("Informe o arquivo JSON de configuração.");
const config = JSON.parse(await fs.readFile(configPath, "utf8"));
if (!config.input_path || !config.output_path || !config.sheet_name) {
  throw new Error("Configuração incompleta: entrada, saída e aba são obrigatórias.");
}
if (!Array.isArray(config.rows) || config.rows.length === 0) {
  throw new Error("Não há linhas aprovadas para importar.");
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(config.input_path));
const sheet = workbook.worksheets.getItem(config.sheet_name);
const headerRow = Number(config.header_row || 6);
const header = sheet.getRange(`A${headerRow}:M${headerRow}`).values[0]
  .map((value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase());
for (const expected of ["TIPO", "OBRA", "QUANT", "PECA", "DIMENS", "VOL UNIT", "TIPO DE CARGA"]) {
  if (!header.some((value) => value.includes(expected))) {
    throw new Error(`Cabeçalho obrigatório não encontrado: ${expected}. Nenhuma escrita foi exportada.`);
  }
}

function splitPiece(value) {
  const compact = String(value || "").trim().replace(/\s+/g, "");
  const match = /^([A-Za-zÀ-ÿ]+)-?(.*)$/.exec(compact);
  if (!match) return [compact, ""];
  return [match[1].replace(/-$/, ""), match[2].replace(/^-/, "")];
}

function isFree(values, formulas = []) {
  // H may contain the workbook's DIG.VOLUME placeholder and I/K/L/M may
  // already contain formulas. A:G and J are the actual source fields.
  const sourceIndexes = [0, 1, 2, 3, 4, 5, 6, 9];
  return sourceIndexes.every((index) => values[index] === null || values[index] === "")
    && !formulas.some((formula) => /\bSUM\s*\(/i.test(String(formula || "")));
}

const scanStart = headerRow + 1;
const scanEnd = Number(config.scan_end_row || 1500);
const scan = sheet.getRange(`A${scanStart}:M${scanEnd}`).values;
const scanFormulas = sheet.getRange(`A${scanStart}:M${scanEnd}`).formulas;
let totalRow = 0;
for (let index = 0; index < scan.length; index += 1) {
  const formulas = scanFormulas[index] || [];
  if (formulas.some((formula) => /\bSUM\s*\(/i.test(String(formula || "")))) {
    totalRow = scanStart + index;
    break;
  }
}
if (!totalRow) throw new Error("A linha de total não foi localizada. Nenhuma escrita foi exportada.");

const freeRows = [];
for (let row = scanStart; row < totalRow && freeRows.length < config.rows.length; row += 1) {
  const index = row - scanStart;
  if (isFree(scan[index], scanFormulas[index] || [])) freeRows.push(row);
}
if (freeRows.length < config.rows.length) {
  throw new Error("A aba não possui linhas preparadas suficientes antes do total. Nenhuma escrita foi exportada.");
}

const imported = [];
for (let index = 0; index < config.rows.length; index += 1) {
  const input = config.rows[index];
  if (input.status && input.status !== "APROVADO") {
    throw new Error("Foi recebida uma linha que não está aprovada. Nenhuma escrita foi exportada.");
  }
  const targetRow = freeRows[index];
  const target = sheet.getRange(`A${targetRow}:M${targetRow}`);
  const before = target.values[0];
  if (!isFree(before, target.formulas[0])) {
    throw new Error(`A linha ${targetRow} deixou de estar livre. Nenhuma escrita foi exportada.`);
  }
  const [piecePrefix, pieceNumber] = splitPiece(input.piece);
  sheet.getRange(`A${targetRow}:H${targetRow}`).values = [[
    input.type_name,
    new Date(`${input.message_date}T12:00:00`),
    input.work,
    Number(input.quantity),
    piecePrefix,
    pieceNumber,
    input.dimensions,
    input.unit_volume === null ? null : Number(input.unit_volume),
  ]];
  sheet.getRange(`J${targetRow}`).values = [[input.cargo_type]];
  sheet.getRange(`B${targetRow}`).format.numberFormat = "dd/mm/yyyy";
  sheet.getRange(`H${targetRow}:I${targetRow}`).format.numberFormat = "0.000";

  sheet.getRange(`I${targetRow}`).formulas = [[`=H${targetRow}*D${targetRow}`]];
  sheet.getRange(`K${targetRow}`).formulas = [[`=VLOOKUP(A${targetRow},'TABELA'!$A$2:$C$200,3,0)`]];
  sheet.getRange(`L${targetRow}`).formulas = [[`=VLOOKUP(A${targetRow},'TABELA'!$A$2:$C$200,2,0)`]];
  sheet.getRange(`M${targetRow}`).formulas = [[
    `=IF($K${targetRow}="PÇ",$L${targetRow}*$D${targetRow},IF($K${targetRow}="m³",$I${targetRow}*$L${targetRow},$D${targetRow}*$L${targetRow}))`,
  ]];
  imported.push({ target_row: targetRow, piece: input.piece });
}

const firstRow = freeRows[0];
const lastRow = freeRows[freeRows.length - 1];
const check = await workbook.inspect({
  kind: "table",
  sheetId: config.sheet_name,
  range: `A${firstRow}:M${lastRow}`,
  include: "values,formulas",
  tableMaxRows: config.rows.length,
  tableMaxCols: 13,
  maxChars: 12000,
});
const errors = await workbook.inspect({
  kind: "match",
  sheetId: config.sheet_name,
  range: `A${firstRow}:M${lastRow}`,
  searchTerm: "#REF!|#DIV/0!|#NAME\\?|#N/A|#VALOR!|#N/D",
  options: { useRegex: true, maxResults: 100 },
  summary: "safe import formula error scan",
});
if (errors.ndjson.includes('"matchCount":') && !errors.ndjson.includes('"matchCount":0')) {
  throw new Error(`Foram encontrados erros de fórmula na cópia: ${errors.ndjson}`);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(config.output_path);
if (config.preview_path) {
  const preview = await workbook.render({
    sheetName: config.sheet_name,
    range: `A1:M${Math.min(lastRow + 1, firstRow + 12)}`,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(config.preview_path, new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({ ok: true, imported, check: check.ndjson, errors: errors.ndjson }));
