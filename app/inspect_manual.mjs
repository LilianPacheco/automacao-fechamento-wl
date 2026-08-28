import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
const input = await FileBlob.load("C:/Users/lilia/Downloads/Automatização/MEDIÇÕES AWL - 2026 - Automatização.xlsx");
const workbook = await SpreadsheetFile.importXlsx(input);
console.log((await workbook.inspect({kind:"workbook,sheet,table",maxChars:12000,tableMaxRows:8,tableMaxCols:14})).ndjson);
for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  console.log(`SHEET ${sheet.name}`);
  console.log((await workbook.inspect({kind:"region",sheetId:sheet.name,range:used.address,maxChars:12000})).ndjson);
}
