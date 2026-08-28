import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const source = "C:/Users/lilia/Downloads/FECHAMENTOS PRELOG/MEDIÇÕES AWL - 2026.xlsx";
const input = await FileBlob.load(source);
const wb = await SpreadsheetFile.importXlsx(input);
const sheets = wb.worksheets.items;
const summary = [];
for (const sh of sheets) {
  const used = sh.getUsedRange();
  const vals = used?.values ?? [];
  summary.push({name: sh.name, rows: vals.length, cols: vals[0]?.length ?? 0, sample: vals.slice(0, 10)});
  if (/julho|junho/i.test(sh.name)) {
    await fs.writeFile(`reference_${sh.name.replace(/[^a-z0-9]+/gi,"_")}.json`, JSON.stringify(vals));
  }
}
await fs.writeFile("reference_sheets.json", JSON.stringify(summary));
console.log(JSON.stringify(summary.map(x=>({name:x.name,rows:x.rows,cols:x.cols})), null, 2));
