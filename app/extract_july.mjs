import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
const input = await FileBlob.load("C:/Users/lilia/Downloads/Automatização/MEDIÇÕES AWL - 2026 - Automatização.xlsx");
const wb = await SpreadsheetFile.importXlsx(input);
const sh = wb.worksheets.getItem("2ª quinz.julho");
const values = sh.getUsedRange().values;
await fs.writeFile("../runtime_july_manual.json", JSON.stringify(values));
console.log(JSON.stringify({rows:values.length,cols:values[0]?.length||0,header:values[5],sample:values.slice(6,12)}));
