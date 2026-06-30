from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


HEADER_FILL = PatternFill("solid", fgColor="1E3A5F")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def _finish_workbook(workbook: Workbook, sheet) -> bytes:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(
            max_length + 4, 42
        )
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def attendance_excel(rows: list[dict], metadata: dict) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Asistencias"
    headers = [
        "#",
        "Trabajador",
        "DNI",
        "Tienda",
        "Fecha",
        "Entrada",
        "Inicio receso",
        "Fin receso",
        "Salida",
        "Tardanza",
        "Justificado",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    for index, row in enumerate(rows, 1):
        sheet.append(
            [
                index,
                row.get("nombre_trabajador") or "-",
                row.get("dni") or "-",
                row.get("nombre_tienda") or "-",
                row.get("fecha") or "-",
                row.get("hora_inicio") or "-",
                row.get("inicio_receso") or "-",
                row.get("final_receso") or "-",
                row.get("hora_final") or "-",
                "Sí" if row.get("late") else "No",
                "Sí" if row.get("justificado") else "No",
            ]
        )
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.oddFooter.center.text = (
        f"Periodo: {metadata.get('label', '')} · "
        f"Generado: {datetime.now():%d/%m/%Y %H:%M}"
    )
    return _finish_workbook(workbook, sheet)


def marks_excel(rows: list[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Marcas"
    headers = [
        "#",
        "Trabajador",
        "DNI",
        "Tienda",
        "Fecha",
        "Hora",
        "Tipo",
        "Ubicación",
    ]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    for index, row in enumerate(rows, 1):
        location = row.get("ubicacion")
        if isinstance(location, (dict, list)):
            location = json.dumps(location, ensure_ascii=False)
        sheet.append(
            [
                index,
                row.get("nombre_trabajador") or "-",
                row.get("id_trabajador") or "-",
                row.get("nombre_tienda") or "-",
                row.get("fecha_local") or "-",
                row.get("hora_local") or "-",
                row.get("tipo") or "-",
                location or "-",
            ]
        )
    return _finish_workbook(workbook, sheet)


def attendance_pdf(rows: list[dict], workers: list[dict], metadata: dict) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Reporte de asistencias", styles["Title"]),
        Paragraph(
            (
                f"{metadata.get('label', '')} · "
                f"{metadata.get('start', '')} a {metadata.get('end', '')} · "
                f"{len(workers)} trabajadores · {len(rows)} registros"
            ),
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
    ]
    table_rows = [
        [
            "#",
            "Trabajador",
            "DNI",
            "Tienda",
            "Fecha",
            "Entrada",
            "Receso",
            "Salida",
            "Estado",
        ]
    ]
    for index, row in enumerate(rows, 1):
        state = (
            "Justificado"
            if row.get("justificado")
            else "Tardanza"
            if row.get("late")
            else "Puntual"
        )
        table_rows.append(
            [
                index,
                str(row.get("nombre_trabajador") or "-")[:32],
                row.get("dni") or "-",
                str(row.get("nombre_tienda") or "-")[:24],
                row.get("fecha") or "-",
                row.get("hora_inicio") or "-",
                (
                    f"{row.get('inicio_receso') or '-'} / "
                    f"{row.get('final_receso') or '-'}"
                ),
                row.get("hora_final") or "-",
                state,
            ]
        )
    table = Table(
        table_rows,
        repeatRows=1,
        colWidths=[9 * mm, 45 * mm, 23 * mm, 38 * mm, 23 * mm, 18 * mm, 30 * mm, 18 * mm, 25 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    document.build(story)
    return buffer.getvalue()


def workers_pdf(workers: list[dict], store_label: str, query: str) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Directorio de trabajadores", styles["Title"]),
        Paragraph(
            f"Tienda: {store_label or 'Todas'} · Búsqueda: {query or '—'} · Registros: {len(workers)}",
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
    ]
    rows = [["#", "Nombre", "DNI", "Cargo", "Tienda", "Correo", "Teléfono", "Estado"]]
    for index, worker in enumerate(workers, 1):
        rows.append(
            [
                index,
                worker.get("nombre_trabajador") or "-",
                worker.get("dni") or "-",
                worker.get("area") or "-",
                worker.get("nombre_sede") or "-",
                worker.get("correo") or "-",
                worker.get("telefono") or "-",
                "Activo" if worker.get("estado") else "Inactivo",
            ]
        )
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    document.build(story)
    return buffer.getvalue()
