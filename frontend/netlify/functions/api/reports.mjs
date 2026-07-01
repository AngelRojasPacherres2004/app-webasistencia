import ExcelJS from "exceljs";
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import { formatTime } from "./lib.mjs";

const BLUE = "1E3A5F";
const LIGHT_BLUE = "DBEAFE";
const MM = 2.83465;
const fitColumns = (sheet, maximum = 42, padding = 4) => {
  sheet.columns.forEach((column) => {
    let width = 0;
    column.eachCell?.({ includeEmpty: true }, (cell) => {
      width = Math.max(width, String(cell.value ?? "").length + padding);
    });
    column.width = Math.min(width, maximum);
  });
};
const workbookBuffer = async (workbook) => Buffer.from(await workbook.xlsx.writeBuffer());
const reportDate = (value) => {
  const [year, month, day] = String(value || "").slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : "-";
};
const generatedAt = () => {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(new Date()).reduce((result, part) => ({ ...result, [part.type]: part.value }), {});
  return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`;
};
const minutes = (value) => {
  const [hour, minute] = formatTime(value).split(":").map(Number);
  return Number.isFinite(hour) && Number.isFinite(minute) ? hour * 60 + minute : null;
};

export async function attendanceExcel(rows, metadata) {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet("Resumen");
  const title = sheet.getCell("A1");
  title.value = "Reporte de Asistencias";
  title.font = { color: { argb: "FFFFFFFF" }, bold: true };
  title.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${BLUE}` } };
  title.alignment = { horizontal: "center" };
  [
    ["Periodo", metadata.label || "-"],
    ["Rango", `${reportDate(metadata.start)} - ${reportDate(metadata.end)}`],
    ["Tienda", metadata.store_label || "Todas las tiendas"],
    ["Persona", metadata.worker_label || "Todas"],
    ["Búsqueda", metadata.search || "-"],
    ["Generado", generatedAt()],
  ].forEach(([label, value], index) => {
    sheet.getCell(index + 3, 1).value = label;
    sheet.getCell(index + 3, 1).font = { bold: true };
    sheet.getCell(index + 3, 2).value = value;
  });
  const header = sheet.getRow(10);
  header.values = [
    "#", "Trabajador", "DNI", "Sede", "Fecha", "Entrada", "Ini. receso",
    "Fin receso", "Salida", "Horas", "Cálculo horas", "Tardanza", "Justificado",
  ];
  header.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: `FF${BLUE}` } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${LIGHT_BLUE}` } };
    cell.alignment = { horizontal: "center" };
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
  if (rows.length) {
    sheet.views = [{ state: "frozen", ySplit: 10, topLeftCell: "A11" }];
    sheet.autoFilter = `A10:M${sheet.rowCount}`;
  }
  fitColumns(sheet, 40, 4);
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

const safeText = (value) => String(value ?? "").replaceAll("—", "-").replaceAll("…", "...").replace(/[^\x20-\x7E\u00A0-\u00FF]/g, " ");
function drawText(page, font, text, x, y, size = 8, color = rgb(0.08, 0.12, 0.18), maxWidth = 160, centered = false) {
  let output = safeText(text);
  while (output.length > 1 && font.widthOfTextAtSize(output, size) > maxWidth) output = `${output.slice(0, -4)}...`;
  const offset = centered ? Math.max((maxWidth - font.widthOfTextAtSize(output, size)) / 2, 3) : 0;
  page.drawText(output, { x: x + offset, y, size, font, color });
}
const pdfColor = (hex) => {
  const value = hex.replace("#", "");
  return rgb(Number.parseInt(value.slice(0, 2), 16) / 255, Number.parseInt(value.slice(2, 4), 16) / 255, Number.parseInt(value.slice(4, 6), 16) / 255);
};
const cell = (page, x, y, width, height, fill, border = "#64748B") =>
  page.drawRectangle({ x, y: y - height, width, height, color: pdfColor(fill), borderColor: pdfColor(border), borderWidth: 0.35 });
const isoDate = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const dateLabel = (date) => `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`;

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
      worker.nombre_sede || "-", worker.correo || "-", worker.telefono || "-", worker.estado ? "Activo" : "Inactivo",
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
  const margin = 10 * MM;
  const pageWidth = pageSize[0] - (margin * 2);
  const colors = {
    black: "#0F172A", dark: "#1E293B", muted: "#64748B", light: "#F1F5F9",
    header: "#1E3A5F", alternate: "#F8FAFC", accent: "#2563EB",
    onFill: "#DCFCE7", onText: "#166534", lateFill: "#FEF3C7", lateText: "#92400E",
    justifiedFill: "#DBEAFE", justifiedText: "#1D4ED8", absent: "#DC2626",
  };
  const start = new Date(`${metadata.start}T12:00:00`);
  const end = new Date(`${metadata.end}T12:00:00`);
  const sortedWorkers = [...workers].sort((a, b) => {
    const first = String(a.nombre_trabajador || "");
    const second = String(b.nombre_trabajador || "");
    return first < second ? -1 : first > second ? 1 : 0;
  });
  const attendance = new Map(rows.map((row) => [`${String(row.dni || "").trim()}-${row.fecha}`, row]));
  const lateCount = rows.filter((row) => row.late).length;
  const generated = generatedAt();
  const weeks = [];
  const cursor = new Date(start);
  cursor.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  while (cursor <= end) {
    const days = Array.from({ length: 6 }, (_, offset) => {
      const day = new Date(cursor);
      day.setDate(cursor.getDate() + offset);
      return day;
    }).filter((day) => day >= start && day <= end);
    if (days.length) weeks.push(days);
    cursor.setDate(cursor.getDate() + 7);
  }

  let page = pdf.addPage(pageSize);
  let y = 558;
  drawText(page, bold, "Reporte de Asistencias", margin, y, 16, pdfColor(colors.black), 500);
  y -= 20;
  drawText(page, regular, `Periodo: ${metadata.label || "-"} · Rango: ${reportDate(metadata.start)} - ${reportDate(metadata.end)} · Generado: ${generated}`, margin, y, 8, pdfColor(colors.dark), pageWidth);
  y -= 12;
  page.drawLine({ start: { x: margin, y }, end: { x: margin + pageWidth, y }, thickness: 1.2, color: pdfColor(colors.accent) });
  y -= 10;

  const metaWidths = [22, 68, 28, 22, 24, 22].map((value) => value * MM);
  [
    ["Tienda", metadata.store_label || "Todas las tiendas", "Trabajadores", sortedWorkers.length, "Registros", rows.length],
    ["Búsqueda", metadata.search || "-", "A tiempo", rows.length - lateCount, "Tardanzas", lateCount],
  ].forEach((values, rowIndex) => {
    let x = (pageSize[0] - metaWidths.reduce((total, width) => total + width, 0)) / 2;
    values.forEach((value, columnIndex) => {
      const width = metaWidths[columnIndex];
      cell(page, x, y, width, 19, rowIndex ? colors.light : "#FFFFFF");
      drawText(page, columnIndex % 2 === 0 ? bold : regular, value, x + 4, y - 13, 7.5, pdfColor(columnIndex % 2 === 0 ? colors.black : colors.dark), width - 8);
      x += width;
    });
    y -= 19;
  });
  y -= 9;

  const legend = [
    ["Leyenda de colores:", colors.light, colors.black, 34], ["Puntual", colors.onFill, colors.onText, 32],
    ["Tardanza", colors.lateFill, colors.lateText, 34], ["Justificado", colors.justifiedFill, colors.justifiedText, 34],
    ["Falta", colors.absent, "#FFFFFF", 28], ["Sin marca", colors.light, colors.muted, 30],
  ];
  const legendWidth = legend.reduce((total, item) => total + (item[3] * MM), 0);
  let legendX = (pageSize[0] - legendWidth) / 2;
  legend.forEach(([label, fill, textColor, widthMm], index) => {
    const width = widthMm * MM;
    cell(page, legendX, y, width, 21, fill);
    drawText(page, index === 0 ? bold : regular, label, legendX, y - 14, 7, pdfColor(textColor), width, true);
    legendX += width;
  });
  y -= 33;

  const dayNames = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
  const rowLines = (worker, days) => days.map((day) => {
    const row = attendance.get(`${String(worker.dni || "").trim()}-${isoDate(day)}`);
    if (!row) return 1;
    const count = [row.hora_inicio, row.inicio_receso, row.final_receso, row.hora_final]
      .map(formatTime).filter(Boolean).length;
    return Math.max(count + (row.justificado && row.fuera_horario ? 1 : 0), 1);
  });
  const workerRowHeight = (worker, days) => Math.max(18, Math.max(...rowLines(worker, days)) * 6.2 + 5);
  const drawWeek = (days, weekNumber, offset, chunk, continued) => {
    drawText(page, bold, `Semana ${weekNumber} · ${dateLabel(days[0])} - ${dateLabel(days.at(-1))}${continued ? " (continuación)" : ""}`, margin, y, 8, pdfColor("#1E40AF"), pageWidth);
    y -= 12;
    const tableWidth = 246 * MM;
    const tableX = (pageSize[0] - tableWidth) / 2;
    const numberWidth = 8 * MM;
    const workerWidth = 42 * MM;
    const dayWidth = (tableWidth - numberWidth - workerWidth) / days.length;
    const headerHeight = 28;
    let x = tableX;
    [[numberWidth, "N°"], [workerWidth, "Trabajador"]].forEach(([width, label], index) => {
      cell(page, x, y, width, headerHeight, colors.header);
      drawText(page, bold, label, x + (index ? 4 : 0), y - 17, 7.5, rgb(1, 1, 1), width - (index ? 8 : 0), !index);
      x += width;
    });
    days.forEach((day) => {
      cell(page, x, y, dayWidth, headerHeight, colors.header);
      drawText(page, bold, dayNames[day.getDay() - 1], x, y - 12, 7, rgb(1, 1, 1), dayWidth, true);
      drawText(page, bold, dateLabel(day), x, y - 22, 7, rgb(1, 1, 1), dayWidth, true);
      x += dayWidth;
    });
    y -= headerHeight;

    chunk.forEach((worker, chunkIndex) => {
      const rowHeight = workerRowHeight(worker, days);
      const alternate = (offset + chunkIndex) % 2 ? colors.alternate : "#FFFFFF";
      const centerBaseline = y - (rowHeight / 2) - 2.5;
      let cellX = tableX;
      cell(page, cellX, y, numberWidth, rowHeight, alternate);
      drawText(page, regular, offset + chunkIndex + 1, cellX, centerBaseline, 7, pdfColor(colors.muted), numberWidth, true);
      cellX += numberWidth;
      cell(page, cellX, y, workerWidth, rowHeight, alternate);
      drawText(page, bold, worker.nombre_trabajador || "-", cellX + 4, centerBaseline, 7, pdfColor(colors.black), workerWidth - 8);
      cellX += workerWidth;
      days.forEach((day) => {
        const row = attendance.get(`${String(worker.dni || "").trim()}-${isoDate(day)}`);
        let lines = ["FALTA"];
        let fill = colors.absent;
        let textColor = "#FFFFFF";
        if (row) {
          lines = [row.hora_inicio, row.inicio_receso, row.final_receso, row.hora_final].map(formatTime).filter(Boolean);
          fill = colors.light;
          textColor = colors.muted;
          if (lines.length) {
            if (row.justificado && row.fuera_horario) {
              lines = ["JUSTIFICADO", ...lines];
              fill = colors.justifiedFill;
              textColor = colors.justifiedText;
            } else if (row.late) {
              fill = colors.lateFill;
              textColor = colors.lateText;
            } else {
              fill = colors.onFill;
              textColor = colors.onText;
            }
          } else lines = ["-"];
        }
        cell(page, cellX, y, dayWidth, rowHeight, fill);
        const lineHeight = 6.2;
        const firstY = y - ((rowHeight - (lines.length * lineHeight)) / 2) - 5.3;
        lines.forEach((line, lineIndex) =>
          drawText(page, bold, line, cellX, firstY - (lineIndex * lineHeight), 6, pdfColor(textColor), dayWidth, true));
        cellX += dayWidth;
      });
      y -= rowHeight;
    });
    y -= 14;
  };

  weeks.forEach((days, weekIndex) => {
    let offset = 0;
    let continued = false;
    while (offset < sortedWorkers.length || (!sortedWorkers.length && offset === 0)) {
      if (y < 110) {
        page = pdf.addPage(pageSize);
        y = 558;
        continued = offset > 0;
      }
      const chunk = [];
      let usedHeight = 0;
      for (const worker of sortedWorkers.slice(offset)) {
        const height = workerRowHeight(worker, days);
        if (chunk.length && usedHeight + height > y - 90) break;
        chunk.push(worker);
        usedHeight += height;
      }
      drawWeek(days, weekIndex + 1, offset, chunk, continued);
      if (!sortedWorkers.length) break;
      offset += chunk.length;
      continued = offset > 0;
    }
  });

  if (y < 45) {
    page = pdf.addPage(pageSize);
    y = 558;
  }
  page.drawLine({ start: { x: margin, y: y - 2 }, end: { x: margin + pageWidth, y: y - 2 }, thickness: 0.4, color: pdfColor(colors.muted) });
  const footer = safeText(`Generado el ${generated} | ${sortedWorkers.length} trabajadores | ${rows.length} registros | ${rows.length - lateCount} a tiempo | ${lateCount} tardanzas`);
  page.drawText(footer, {
    x: margin + pageWidth - regular.widthOfTextAtSize(footer, 6.5),
    y: y - 13,
    size: 6.5,
    font: regular,
    color: pdfColor(colors.muted),
  });
  return Buffer.from(await pdf.save());
}
