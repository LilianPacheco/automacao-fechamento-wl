import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/lilia/Downloads/FECHAMENTOS PRELOG/MEDIÇÕES AWL - 2026.xlsx";
const outputPath = "C:/Users/lilia/OneDrive/Documentos/Automatização - Fechamento/Fechamento_WL_2a_quinz_julho_2026_validado.xlsx";
const previewPath = "C:/Users/lilia/OneDrive/Documentos/Automatização - Fechamento/app/fechamento_validado_preview.png";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const source = workbook.worksheets.getItem("2ª quinz.julho");
const sourceValues = source.getUsedRange().values;

function text(v) {
  return v === null || v === undefined ? "" : String(v).trim();
}
function norm(v) {
  return text(v).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase().replace(/\s+/g, " ");
}
function isDataRow(row) {
  // H may contain the spreadsheet's DIG.VOLUME placeholder even on blank rows.
  // A:G are the actual identifying/source fields.
  const first = row.slice(0, 7);
  if (!first.some(v => v !== null && v !== undefined && v !== "")) return false;
  return true;
}
function excelCol(n) {
  let out = "";
  let x = n;
  while (x > 0) { const r = (x - 1) % 26; out = String.fromCharCode(65 + r) + out; x = Math.floor((x - 1) / 26); }
  return out;
}
function fmtDate(value) {
  if (typeof value !== "number") return text(value);
  const d = new Date(Date.UTC(1899, 11, 30) + value * 86400000);
  return `${String(d.getUTCDate()).padStart(2,"0")}/${String(d.getUTCMonth()+1).padStart(2,"0")}/${d.getUTCFullYear()}`;
}

// The source sheet intentionally has blank dates after the first line of a group.
// The validated copy retains the exact source row and also exposes the effective date.
const dataRows = [];
let effectiveDate = null;
for (let i = 6; i < sourceValues.length; i++) {
  const row = sourceValues[i] || [];
  if (!isDataRow(row)) continue;
  if (row[1] !== null && row[1] !== undefined && row[1] !== "") effectiveDate = row[1];
  dataRows.push({ sourceRow: i + 1, row: row.slice(0, 13), effectiveDate });
}

// Grouping follows the user's rule: the date is part of the key. Two equal
// pieces on different days must remain separate; equal pieces on the same
// effective day are only candidates for aggregation.
const keyIndexes = [0, 2, 3, 4, 5, 6, 7, 9, 10, 11];
const groups = new Map();
for (const item of dataRows) {
  const key = [norm(item.effectiveDate), ...keyIndexes.map(i => norm(item.row[i]))].join("¦");
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(item.sourceRow);
}
const dupRows = new Set([...groups.values()].filter(rows => rows.length > 1).flat());

// Add a separate, review-friendly copy. The original workbook sheet is not modified.
const existing = workbook.worksheets.items.map(s => s.name);
for (const name of ["FECHAMENTO VALIDADO", "CONFERÊNCIA MANUAL"]) {
  if (existing.includes(name)) workbook.worksheets.getItem(name).delete();
}
const validated = workbook.worksheets.add("FECHAMENTO VALIDADO");
const headers = [
  "TIPO", "DATA (orig.)", "OBRA", "QUANT. (PÇ ou m)", "PEÇA", "Nº PEÇA",
  "DIMENSÕES", "VOL UNIT. (m³)", "VOL TOTAL (m³)", "TIPO DE CARGA",
  "UNID. DE MEDIDA", "R$ UNIT.", "R$ TOTAL", "DATA EFETIVA", "LINHA MANUAL",
  "AGRUPAMENTO MESMO DIA", "OBSERVAÇÃO"
];
const out = [headers];
for (const item of dataRows) {
  const row = item.row.slice();
  while (row.length < 13) row.push(null);
  out.push([...row, item.effectiveDate, item.sourceRow, dupRows.has(item.sourceRow) ? "SIM" : "NÃO", dupRows.has(item.sourceRow) ? "Mesmo dia e mesmas informações; candidata a agrupamento conforme a regra do fechamento." : "Copiada do manual de referência."]);
}
validated.getRange(`A1:Q${out.length}`).values = out;
validated.freezePanes.freezeRows(1);
validated.getRange("A1:Q1").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
validated.getRange(`A2:Q${out.length}`).format = { verticalAlignment: "center", wrapText: true };
validated.getRange(`B2:B${out.length}`).format.numberFormat = "dd/mm/yyyy";
validated.getRange(`N2:N${out.length}`).format.numberFormat = "dd/mm/yyyy";
validated.getRange(`H2:I${out.length}`).format.numberFormat = "0.000";
validated.getRange(`L2:M${out.length}`).format.numberFormat = "0.00";
validated.getRange(`A1:Q${out.length}`).format.autofitColumns();
for (const col of [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17]) validated.getRange(`${excelCol(col)}:${excelCol(col)}`).format.columnWidth = Math.min(Math.max(validated.getRange(`${excelCol(col)}:${excelCol(col)}`).format.columnWidth || 12, 12), col === 17 ? 42 : 24);

const audit = workbook.worksheets.add("CONFERÊNCIA MANUAL");
const duplicateGroups = [...groups.entries()].filter(([, rows]) => rows.length > 1);
const periodStart = 46219; // 16/07/2026 (Excel serial)
const periodEnd = 46233;   // 31/07/2026
const outOfPeriod = dataRows.filter(item => typeof item.row[1] === "number" && (item.row[1] < periodStart || item.row[1] > periodEnd));
const auditRows = [
  ["CONFERÊNCIA DA NOVA CÓPIA", ""],
  ["Arquivo de referência", inputPath],
  ["Aba de referência", "2ª quinz.julho"],
  ["Período indicado na aba", "16/07/2026 a 31/07/2026"],
  ["Linhas preenchidas copiadas", dataRows.length],
  ["Linhas vazias preparadas no manual", sourceValues.length - 6 - dataRows.length],
  ["Candidatas a agrupamento no mesmo dia", duplicateGroups.length],
  ["Datas fora do período indicado", outOfPeriod.length],
  ["Regra", "O manual é a fonte de verdade. Nenhuma linha foi apagada ou inventada; repetições do mesmo dia são apenas sinalizadas para agrupamento."],
  ["Regra de data", "A coluna DATA EFETIVA preenche apenas a data herdada do grupo; DATA (orig.) permanece igual ao manual."],
  ["Regra de OCR", "O OCR não pode criar uma linha fora do manual; divergências devem ser confirmadas antes do fechamento."],
  ["", ""],
  ["CANDIDATAS A AGRUPAMENTO (mesmo dia)", "Linhas originais"],
];
for (const [, rows] of duplicateGroups) auditRows.push(["Mesmo dia / mesmas informações", rows.join(", ")]);
if (outOfPeriod.length) {
  auditRows.push(["", ""]);
  auditRows.push(["DATAS FORA DO PERÍODO (mantidas)", "Linha / data"]);
  for (const item of outOfPeriod) auditRows.push(["Fora do período", `${item.sourceRow} / ${fmtDate(item.row[1])}`]);
}
audit.getRange(`A1:B${auditRows.length}`).values = auditRows;
audit.getRange("A1:B1").format = { fill: "#17365D", font: { bold: true, color: "#FFFFFF" } };
audit.getRange("A12:B12").format = { fill: "#D9EAF7", font: { bold: true } };
audit.getRange(`A1:B${auditRows.length}`).format.wrapText = true;
audit.getRange("A:A").format.columnWidth = 38;
audit.getRange("B:B").format.columnWidth = 90;

const check = await workbook.inspect({kind:"table", sheetId:"FECHAMENTO VALIDADO", range:`A1:Q${Math.min(out.length, 20)}`, include:"values,formulas", tableMaxRows:20, tableMaxCols:17, maxChars:16000});
const errors = await workbook.inspect({kind:"match", sheetId:"FECHAMENTO VALIDADO", range:`A1:Q${out.length}`, searchTerm:"#REF!|#DIV/0!|#NAME\\?|#N/A|#VALOR!|#N/D", options:{useRegex:true,maxResults:100}, summary:"erros na cópia validada"});
if (errors.ndjson.includes('"matchCount":') && !errors.ndjson.includes('"matchCount":0')) throw new Error(`Erro na aba criada: ${errors.ndjson}`);

const preview = await workbook.render({sheetName:"FECHAMENTO VALIDADO", range:`A1:Q${Math.min(out.length, 18)}`, scale:1, format:"png"});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(workbook)).save(outputPath);
console.log(JSON.stringify({ok:true, outputPath, previewPath, dataRows:dataRows.length, duplicateGroups:duplicateGroups.length, check:check.ndjson.slice(0,1000), errors:errors.ndjson}));
