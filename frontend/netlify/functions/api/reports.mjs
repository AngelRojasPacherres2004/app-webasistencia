import ExcelJS from "exceljs";
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import { formatTime } from "./lib.mjs";

const BLUE = "1E3A5F";
const LIGHT_BLUE = "DBEAFE";

const fitColumns = (sheet, maximum = 38) => {
  sheet.columns.forEach((column) => {
    let width = 10;
    column.eachCell?.({ includeEmpty: true }, (cell) => {
      width = Math.max(width, String(cell.value ?? "").length + 2);
    });
    column.width = Math.min(width, maximum);
  });
};

const workbookBuffer = async (workbook) => Buffer.from(await workbook.xlsx.writeBuffer());

export async function attendanceExcel(rows, metadata) {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = "Gestión de Asistencia";
  const sheet = workbook.addWorksheet("Resumen", { views: [{ state: "frozen", ySplit: 10 }] });
  sheet.mergeCells("A1:M1");
  const title = sheet.getCell("A1");
  title.value = "Reporte de Asistencias";
  title.font = { color: { argb: "FFFFFFFF" }, bold: true, size: 16 };
  title.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${BLUE}` } };
  title.alignment = { horizontal: "center", vertical: "middle" };
  sheet.getRow(1).height = 28;
  const info = [
    ["Periodo", metadata.label || "-"],
    ["Rango", `${metadata.start || "-"} - ${metadata.end || "-"}`],
    ["Tienda", metadata.store_label || "Todas las tiendas"],
    ["Persona", metadata.worker_label || "Todas"],
    ["Búsqueda", metadata.search || "-"],
    ["Generado", new Intl.DateTimeFormat("es-PE", { dateStyle: "short", timeStyle: "short", timeZone: "America/Lima" }).format(new Date())],
  ];
  info.forEach(([label, value], index) => {
    sheet.getCell(index + 3, 1).value = label;
    sheet.getCell(index + 3, 1).font = { bold: true };
    sheet.getCell(index + 3, 2).value = value;
  });
  const headers = [
    "#", "Trabajador", "DNI", "Sede", "Fecha", "Entrada", "Ini. receso",
    "Fin receso", "Salida", "Horas", "Cálculo horas", "Tardanza", "Justificado",
  ];
  const header = sheet.getRow(10);
  header.values = headers;
  header.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: `FF${BLUE}` } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${LIGHT_BLUE}` } };
    cell.alignment = { horizontal: "center" };
    cell.border = { bottom: { style: "thin", color: { argb: "FF93C5FD" } } };
  });
  rows.forEach((row, index) => {
    const start = minutes(row.hora_inicio);
    const end = minutes(row.hora_final);
    const hasBreak = Boolean(formatTime(row.inicio_receso) && formatTime(row.final_receso));
    const total = start === null || end === null ? null : Math.max(Math.floor(end / 60) * 60 - start - (hasBreak ? 60 : 0), 0);
    const hours = total === null ? "" : `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
    const calculation = total === null ? "" : `${String(Math.floor(end / 60)).padStart(2, "0")}:00 - ${formatTime(row.hora_inicio)}${hasBreak ? " - 1:00 receso" : ""} = ${hours}`;
    sheet.addRow([
      index + 1, row.nombre_trabajador || "-", row.dni || "-", row.nombre_tienda || "-",
      row.fecha || "-", formatTime(row.hora_inicio), formatTime(row.inicio_receso),
      formatTime(row.final_receso), formatTime(row.hora_final), hours, calculation,
      row.late ? "Sí" : "No", row.justificado ? "Sí" : "No",
    ]);
  });
  sheet.autoFilter = rows.length ? `A10:M${sheet.rowCount}` : undefined;
  fitColumns(sheet);
  return workbookBuffer(workbook);
}

export async function marksExcel(rows) {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Marcas", { views: [{ state: "frozen", ySplit: 1 }] });
  sheet.addRow(["#", "Trabajador", "DNI", "Tienda", "Fecha", "Hora", "Tipo", "Ubicación"]);
  sheet.getRow(1).eachCell((cell) => {
    cell.font = { bold: true, color: { argb: "FFFFFFFF" } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${BLUE}` } };
    cell.alignment = { horizontal: "center" };
  });
  rows.forEach((row, index) => sheet.addRow([
    index + 1, row.nombre_trabajador || "-", row.id_trabajador || "-",
    row.nombre_tienda || "-", row.fecha_local || "-", row.hora_local || "-",
    row.tipo || "-", typeof row.ubicacion === "object" ? JSON.stringify(row.ubicacion) : row.ubicacion || "-",
  ]));
  fitColumns(sheet);
  sheet.autoFilter = rows.length ? `A1:H${sheet.rowCount}` : undefined;
  return workbookBuffer(workbook);
}

const minutes = (value) => {
  const text = formatTime(value);
  if (!text) return null;
  const [hour, minute] = text.split(":").map(Number);
  return Number.isFinite(hour) && Number.isFinite(minute) ? hour * 60 + minute : null;
};

const safeText = (value) => String(value ?? "").replace(/[^\x20-\x7EÀ-ÿ]/g, " ");

function drawText(page, font, text, x, y, size = 8, color = rgb(0.08, 0.12, 0.18), maxWidth = 160) {
  let output = safeText(text);
  while (output.length > 1 && font.widthOfTextAtSize(output, size) > maxWidth) output = `${output.slice(0, -2)}…`;
  page.drawText(output, { x, y, size, font, color });
}

export async function workersPdf(workers, storeLabel, query) {
  const pdf = await PDFDocument.create();
  const regular = await pdf.embedFont(StandardFonts.Helvetica);
  const bold = await pdf.embedFont(StandardFonts.HelveticaBold);
  const pageSize = [841.89, 595.28];
  const columns = [35, 58, 210, 275, 345, 445, 615, 725];
  let page;
  let y;
  const header = () => {
    page = pdf.addPage(pageSize);
    drawText(page, bold, "Directorio de trabajadores", 35, 555, 17, rgb(0.08, 0.18, 0.32), 500);
    drawText(page, regular, `Tienda: ${storeLabel || "Todas"} · Búsqueda: ${query || "-"} · Registros: ${workers.length}`, 35, 535, 8, undefined, 760);
    page.drawRectangle({ x: 32, y: 500, width: 778, height: 23, color: rgb(0.12, 0.23, 0.37) });
    ["#", "Nombre", "DNI", "Cargo", "Tienda", "Correo", "Teléfono", "Estado"].forEach((label, index) =>
      drawText(page, bold, label, columns[index], 508, 7, rgb(1, 1, 1), index === 1 ? 145 : 95));
    y = 485;
  };
  header();
  workers.forEach((worker, index) => {
    if (y < 40) header();
    if (index % 2) page.drawRectangle({ x: 32, y: y - 6, width: 778, height: 22, color: rgb(0.97, 0.98, 0.99) });
    const values = [
      index + 1, worker.nombre_trabajador || "-", worker.dni || "-", worker.area || "-",
      worker.nombre_sede || "-", worker.correo || "-", worker.telefono || "-",
      worker.estado ? "Activo" : "Inactivo",
    ];
    values.forEach((value, column) => drawText(page, regular, value, columns[column], y, 7, undefined, column === 1 ? 145 : column === 5 ? 160 : 90));
    y -= 22;
  });
  return Buffer.from(await pdf.save());
}

export async function attendancePdf(rows, workers, metadata) {
  const pdf = await PDFDocument.create();
  const regular = await pdf.embedFont(StandardFonts.Helvetica);
  const bold = await pdf.embedFont(StandardFonts.HelveticaBold);
  const pageSize = [841.89, 595.28];
  const start = new Date(`${metadata.start}T12:00:00`);
  const end = new Date(`${metadata.end}T12:00:00`);
  const index = new Map(rows.map((row) => [`${row.dni}-${row.fecha}`, row]));
  let week = new Date(start);
  week.setDate(week.getDate() - ((week.getDay() + 6) % 7));
  let weekNumber = 1;
  while (week <= end) {
    const days = Array.from({ length: 6 }, (_, offset) => {
      const day = new Date(week); day.setDate(day.getDate() + offset); return day;
    }).filter((day) => day >= start && day <= end);
    if (!days.length) { week.setDate(week.getDate() + 7); continue; }
    const chunks = [];
    for (let offset = 0; offset < workers.length || offset === 0; offset += 16) chunks.push(workers.slice(offset, offset + 16));
    chunks.forEach((chunk, pageIndex) => {
      const page = pdf.addPage(pageSize);
      drawText(page, bold, "Reporte de Asistencias", 28, 558, 16, rgb(0.08, 0.18, 0.32), 500);
      drawText(page, regular, `${metadata.label} · ${metadata.start} - ${metadata.end} · ${metadata.store_label || "Todas las tiendas"}`, 28, 540, 8, undefined, 780);
      drawText(page, bold, `Semana ${weekNumber}${pageIndex ? " (continuación)" : ""}`, 28, 514, 9, rgb(0.12, 0.25, 0.55), 160);
      const nameWidth = 185;
      const dayWidth = (780 - nameWidth) / days.length;
      page.drawRectangle({ x: 28, y: 480, width: 780, height: 25, color: rgb(0.12, 0.23, 0.37) });
      drawText(page, bold, "Trabajador", 34, 489, 7, rgb(1, 1, 1), nameWidth - 12);
      days.forEach((day, dayIndex) => {
        const label = new Intl.DateTimeFormat("es-PE", { weekday: "short", day: "2-digit", month: "2-digit" }).format(day);
        drawText(page, bold, label, 28 + nameWidth + dayIndex * dayWidth + 5, 489, 7, rgb(1, 1, 1), dayWidth - 8);
      });
      let y = 460;
      chunk.forEach((worker, rowIndex) => {
        if (rowIndex % 2) page.drawRectangle({ x: 28, y: y - 7, width: 780, height: 25, color: rgb(0.97, 0.98, 0.99) });
        drawText(page, bold, worker.nombre_trabajador || "-", 34, y, 7, undefined, nameWidth - 12);
        days.forEach((day, dayIndex) => {
          const key = `${worker.dni}-${day.toISOString().slice(0, 10)}`;
          const row = index.get(key);
          const x = 28 + nameWidth + dayIndex * dayWidth;
          const color = !row ? rgb(0.86, 0.15, 0.15) : row.justificado ? rgb(0.12, 0.3, 0.7) : row.late ? rgb(0.58, 0.28, 0.03) : rgb(0.08, 0.4, 0.2);
          const value = !row ? "FALTA" : [row.hora_inicio, row.inicio_receso, row.final_receso, row.hora_final].filter(Boolean).join(" / ") || "-";
          drawText(page, row ? regular : bold, value, x + 5, y, 6.5, color, dayWidth - 8);
        });
        y -= 25;
      });
    });
    week.setDate(week.getDate() + 7);
    weekNumber += 1;
  }
  return Buffer.from(await pdf.save());
}
