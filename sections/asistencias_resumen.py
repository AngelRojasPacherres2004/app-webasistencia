from calendar import monthrange
from datetime import date, datetime, timedelta
import re

import streamlit as st
import streamlit.components.v1 as components


# ================================================================
#  CONSTANTES
# ================================================================

MONTH_NAMES = (
    "Enero","Febrero","Marzo","Abril","Mayo","Junio",
    "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
)

DAY_NAME_MAP = {
    0:"lunes", 1:"martes", 2:"miercoles", 3:"jueves",
    4:"viernes", 5:"sabado", 6:"domingo",
}


# ================================================================
#  HELPERS GENERALES
# ================================================================

def _parse_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _week_start(current_date):
    return current_date - timedelta(days=current_date.weekday())


def _week_label(start_date):
    end_date = start_date + timedelta(days=6)
    return f"{start_date.strftime('%d/%m/%Y')} -> {end_date.strftime('%d/%m/%Y')}"


def _month_label(d):
    return f"{MONTH_NAMES[d.month - 1]} {d.year}"


def _safe_text(value):
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _sanitize_filename(text):
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", _safe_text(text).lower()).strip("_")
    return safe or "reporte"


def _parse_time_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if "T" in text: text = text.split("T", 1)[-1]
        if " " in text: text = text.split(" ", 1)[-1]
        return text[:5]
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    return str(value)[:5]


# ================================================================
#  LOGICA DE HORARIO Y TARDANZAS
# ================================================================

def _build_schedule_map(horarios):
    schedule_map = {}
    for row in horarios:
        dni      = str(row.get("dni_trabajador", "")).strip()
        day_name = str(row.get("dia_semana", "")).strip()
        entrada  = row.get("horario_entrada")
        if isinstance(entrada, str):
            try:
                entrada = datetime.strptime(entrada[:5], "%H:%M").time()
            except ValueError:
                entrada = None
        schedule_map.setdefault(dni, {})[day_name] = entrada
    return schedule_map


def _apply_late_flag(rows, schedule_map):
    for row in rows:
        parsed = _parse_date(row.get("fecha"))
        if not parsed:
            row["late"] = False
            continue
        dni       = str(row.get("dni", "")).strip()
        scheduled = schedule_map.get(dni, {}).get(DAY_NAME_MAP.get(parsed.weekday(), ""))
        actual    = _parse_time_value(row.get("hora_inicio"))
        if scheduled and actual:
            try:
                row["late"] = datetime.strptime(actual[:5], "%H:%M").time() > scheduled
            except ValueError:
                row["late"] = False
        else:
            row["late"] = False


# ================================================================
#  FILTROS
# ================================================================

def _filter_context(asistencias, trabajadores, selected_store_label, store_options, search_query):
    filtered_workers     = list(trabajadores)
    filtered_asistencias = list(asistencias)

    if selected_store_label != "Todas":
        store = store_options[selected_store_label]
        filtered_workers = [
            w for w in filtered_workers
            if str(w.get("id_sede", "")).strip() == str(store["id_tienda"]).strip()
        ]
        worker_ids = {w.get("dni", "") for w in filtered_workers}
        filtered_asistencias = [
            r for r in filtered_asistencias
            if str(r.get("dni", "")).strip() in worker_ids
        ]

    if search_query:
        q = search_query.lower()
        filtered_workers = [
            w for w in filtered_workers
            if q in f"{w.get('nombre_trabajador','')} {w.get('dni','')} {w.get('nombre_sede','')}".lower()
        ]
        worker_ids = {w.get("dni", "") for w in filtered_workers}
        filtered_asistencias = [
            r for r in filtered_asistencias
            if str(r.get("dni", "")).strip() in worker_ids
        ]

    return filtered_workers, filtered_asistencias


def _period_bounds(period_type, reference_date):
    reference_date = reference_date or date.today()
    if period_type == "Mes":
        start = date(reference_date.year, reference_date.month, 1)
        end   = date(reference_date.year, reference_date.month,
                     monthrange(reference_date.year, reference_date.month)[1])
        return start, end, _month_label(start)

    if reference_date.day <= 15:
        start = date(reference_date.year, reference_date.month, 1)
        end   = date(reference_date.year, reference_date.month, 15)
        label = f"{_month_label(start)} - Quincena 1"
    else:
        start = date(reference_date.year, reference_date.month, 16)
        end   = date(reference_date.year, reference_date.month,
                     monthrange(reference_date.year, reference_date.month)[1])
        label = f"{_month_label(start)} - Quincena 2"
    return start, end, label


def _collect_period_rows(asistencias, workers, start_date, end_date, schedule_map):
    workers_by_dni = {str(w.get("dni", "")).strip(): w for w in workers}
    rows = []
    for row in asistencias:
        parsed = _parse_date(row.get("fecha"))
        if not parsed or not (start_date <= parsed <= end_date):
            continue
        dni    = str(row.get("dni", "")).strip()
        worker = workers_by_dni.get(dni)
        if not worker:
            continue
        row_copy = dict(row)
        row_copy["nombre_trabajador"] = worker.get("nombre_trabajador", row_copy.get("nombre_trabajador", ""))
        row_copy["nombre_sede"]       = worker.get("nombre_sede",       row_copy.get("nombre_sede", ""))
        row_copy["cargo"]             = worker.get("area") or worker.get("cargo", "")
        rows.append(row_copy)

    _apply_late_flag(rows, schedule_map)
    return sorted(rows, key=lambda r: (r.get("fecha", ""), r.get("nombre_trabajador", "")))


# ================================================================
#  PDF CON REPORTLAB
# ================================================================
def _build_attendance_pdf(period_label, selected_store_label, search_query,
                           workers, rows, start_date, end_date, tiendas=None):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable, KeepTogether,
    )
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from io import BytesIO
    from datetime import timedelta

    # ── Paleta ────────────────────────────────────────────────────
    C_BLACK      = colors.HexColor("#0f172a")
    C_DARK       = colors.HexColor("#1e293b")
    C_MID        = colors.HexColor("#64748b")
    C_LIGHT      = colors.HexColor("#f1f5f9")
    C_WHITE      = colors.white
    C_HEADER_BG  = colors.HexColor("#1e3a5f")   # azul oscuro — header tabla
    C_WEEK_BG    = colors.HexColor("#dbeafe")    # azul claro — cabecera semana
    C_WEEK_TEXT  = colors.HexColor("#1e40af")    # azul semana texto
    C_ROW_ALT    = colors.HexColor("#f8fafc")    # fila alternada
    C_ACCENT     = colors.HexColor("#2563eb")
    C_GREEN_TEXT = colors.HexColor("#166534")
    C_RED_TEXT   = colors.HexColor("#991b1b")
    C_RED_BG     = colors.HexColor("#fff0f0")
    C_SAT_BG     = colors.HexColor("#fefce8")    # amarillo suave — sábado
    C_ABSENT_BG  = colors.HexColor("#f1f5f9")    # gris — falta

    # ── Estilos ───────────────────────────────────────────────────
    def sty(name, font="Helvetica", size=8, color=None, bold=False,
            align=None, leading=10, italic=False):
        fn = "Helvetica-BoldOblique" if bold and italic else \
             "Helvetica-Bold" if bold else \
             "Helvetica-Oblique" if italic else font
        kw = dict(fontName=fn, fontSize=size,
                  textColor=color or C_BLACK, leading=leading)
        if align:
            kw["alignment"] = align
        return ParagraphStyle(name, **kw)

    sty_title    = sty("title",  bold=True,  size=16, leading=20)
    sty_subtitle = sty("sub",    size=8,     color=C_DARK, leading=11)
    sty_footer   = sty("foot",   size=6.5,   color=C_MID, align=TA_RIGHT, leading=9)
    sty_ml       = sty("ml",     bold=True,  size=7.5)
    sty_mv       = sty("mv",     size=7.5,   color=C_DARK)
    sty_th       = sty("th",     bold=True,  size=7.5, color=C_WHITE, align=TA_CENTER)
    sty_th_l     = sty("thl",    bold=True,  size=7.5, color=C_WHITE)
    sty_week_hd  = sty("wk",     bold=True,  size=8,   color=C_WEEK_TEXT)
    sty_cell     = sty("cell",   size=7,     color=C_BLACK)
    sty_cell_c   = sty("cellc",  size=7,     color=C_BLACK, align=TA_CENTER)
    sty_bold     = sty("bold",   bold=True,  size=7,   color=C_BLACK)
    sty_late     = sty("late",   bold=True,  size=6.5, color=C_RED_TEXT, align=TA_CENTER)
    sty_ok       = sty("ok",     bold=True,  size=6.5, color=C_GREEN_TEXT, align=TA_CENTER)
    sty_absent   = sty("abs",    italic=True,size=6.5, color=C_MID, align=TA_CENTER)
    sty_num      = sty("num",    size=7,     color=C_MID, align=TA_CENTER)

    # ── Helpers ───────────────────────────────────────────────────
    def fmt_time(val):
        if not val or str(val).strip() in ("", "None", "--"):
            return ""
        s = str(val).strip()
        if "T" in s: s = s.split("T")[-1]
        if " " in s: s = s.split(" ")[-1]
        return s[:5]

    def cell_marcaciones(row_data):
        """Devuelve un Paragraph con hasta 4 marcaciones apiladas."""
        if row_data is None:
            return Paragraph("Falta", sty_absent)
        e  = fmt_time(row_data.get("hora_inicio"))
        r1 = fmt_time(row_data.get("inicio_receso"))
        r2 = fmt_time(row_data.get("final_receso"))
        s  = fmt_time(row_data.get("hora_final"))
        is_late = bool(row_data.get("late"))

        parts = []
        if e:
            color = "#991b1b" if is_late else "#166534"
            parts.append(f'<font color="{color}"><b>{e}</b></font>')
        if r1:
            parts.append(f'<font color="#92400e">{r1}</font>')
        if r2:
            parts.append(f'<font color="#5b21b6">{r2}</font>')
        if s:
            parts.append(f'<font color="#1d4ed8">{s}</font>')
        if not parts:
            return Paragraph("—", sty_absent)
        return Paragraph("<br/>".join(parts), sty_cell_c)

    # ── Organizar datos ───────────────────────────────────────────
    # índice: dni → fecha → row
    from collections import defaultdict
    att_index = defaultdict(dict)
    for row in rows:
        try:
            d = date.fromisoformat(str(row.get("fecha", ""))[:10])
        except ValueError:
            continue
        dni = str(row.get("dni", "")).strip()
        att_index[dni][d] = row

    # semanas dentro del periodo (lunes a sábado)
    def get_weeks(start, end):
        weeks = []
        cursor = start - timedelta(days=start.weekday())  # lunes de la semana
        week_num = 1
        while cursor <= end:
            days = []
            for i in range(6):  # lunes=0 ... sábado=5
                d = cursor + timedelta(days=i)
                if start <= d <= end:
                    days.append(d)
            if days:
                weeks.append((week_num, days))
                week_num += 1
            cursor += timedelta(days=7)
        return weeks

    weeks = get_weeks(start_date, end_date)

    # ── Stats generales ───────────────────────────────────────────
    generated_at  = datetime.now().strftime("%d/%m/%Y %H:%M")
    store_label   = selected_store_label if selected_store_label != "Todas" else "Todas las tiendas"
    tardanzas     = sum(1 for r in rows if r.get("late"))
    puntual_count = len(rows) - tardanzas

    # ── Documento ─────────────────────────────────────────────────
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=10*mm, rightMargin=10*mm,
        topMargin=12*mm,  bottomMargin=12*mm,
    )
    story = []

    # ── TÍTULO ────────────────────────────────────────────────────
    story.append(Paragraph("Reporte de Asistencias", sty_title))
    story.append(Paragraph(
        f"Periodo: <b>{period_label}</b>  ·  "
        f"Rango: {start_date.strftime('%d/%m/%Y')} — {end_date.strftime('%d/%m/%Y')}  ·  "
        f"Generado: {generated_at}", sty_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.2, color=C_ACCENT, spaceAfter=2*mm))

    # ── METADATOS ─────────────────────────────────────────────────
    meta = [
        [Paragraph("<b>Tienda</b>",       sty_ml), Paragraph(store_label,        sty_mv),
         Paragraph("<b>Trabajadores</b>", sty_ml), Paragraph(str(len(workers)),  sty_mv),
         Paragraph("<b>Registros</b>",    sty_ml), Paragraph(str(len(rows)),     sty_mv)],
        [Paragraph("<b>Busqueda</b>",     sty_ml), Paragraph(search_query or "—", sty_mv),
         Paragraph("<b>A tiempo</b>",     sty_ml), Paragraph(str(puntual_count), sty_mv),
         Paragraph("<b>Tardanzas</b>",    sty_ml), Paragraph(str(tardanzas),     sty_mv)],
    ]
    meta_t = Table(meta, colWidths=[22*mm, 68*mm, 28*mm, 22*mm, 24*mm, 22*mm])
    meta_t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [C_WHITE, C_LIGHT]),
        ("BOX",            (0,0), (-1,-1), 0.5, C_MID),
        ("INNERGRID",      (0,0), (-1,-1), 0.25, C_MID),
        ("TOPPADDING",     (0,0), (-1,-1), 2),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 2),
        ("LEFTPADDING",    (0,0), (-1,-1), 4),
        ("RIGHTPADDING",   (0,0), (-1,-1), 4),
        ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 3*mm))

    # ── LEYENDA ───────────────────────────────────────────────────
    leyenda_data = [[
        Paragraph("<b>Leyenda de marcaciones:</b>", sty_ml),
        Paragraph('<font color="#166534"><b>Entrada (puntual)</b></font>', sty_cell),
        Paragraph('<font color="#991b1b"><b>Entrada (tardanza)</b></font>', sty_cell),
        Paragraph('<font color="#92400e">Inicio receso</font>', sty_cell),
        Paragraph('<font color="#5b21b6">Fin receso</font>', sty_cell),
        Paragraph('<font color="#1d4ed8">Salida</font>', sty_cell),
    ]]
    ley_t = Table(leyenda_data, colWidths=[38*mm, 38*mm, 38*mm, 32*mm, 28*mm, 26*mm])
    ley_t.setStyle(TableStyle([
        ("BOX",           (0,0), (-1,-1), 0.4, C_MID),
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("BACKGROUND",    (0,0), (-1,-1), C_LIGHT),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(ley_t)
    story.append(Spacer(1, 4*mm))

    # ── TABLAS POR SEMANA ─────────────────────────────────────────
    DAY_NAMES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]

    for week_num, week_days in weeks:
        # encabezado de semana
        week_start_str = week_days[0].strftime("%d/%m")
        week_end_str   = week_days[-1].strftime("%d/%m")
        story.append(Paragraph(
            f"Semana {week_num}  ·  {week_start_str} — {week_end_str}",
            sty_week_hd,
        ))

        # fechas del header (solo los días presentes en la semana)
        day_headers = [
            f"{DAY_NAMES[d.weekday()]}\n{d.strftime('%d/%m')}"
            for d in week_days
        ]

        # anchos: N° + Trabajador + días
        n_days    = len(week_days)
        day_w     = (246 - 8 - 42) / n_days  # distribuir espacio disponible
        col_ws    = [8*mm, 42*mm] + [day_w*mm] * n_days

        # header row
        header_row = [
            Paragraph("N°",         sty_th),
            Paragraph("Trabajador", sty_th_l),
        ] + [Paragraph(h.replace("\n", "<br/>"), sty_th) for h in day_headers]

        # filas de trabajadores
        table_rows = [header_row]
        style_cmds = [
            ("BACKGROUND",    (0,0), (-1,0),  C_HEADER_BG),
            ("BOX",           (0,0), (-1,-1), 0.5, C_MID),
            ("INNERGRID",     (0,0), (-1,-1), 0.25, C_MID),
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("LEFTPADDING",   (0,0), (-1,-1), 3),
            ("RIGHTPADDING",  (0,0), (-1,-1), 3),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_ROW_ALT]),
        ]

        for row_idx, worker in enumerate(workers, 1):
            dni    = str(worker.get("dni", "")).strip()
            nombre = _safe_text(worker.get("nombre_trabajador", ""))
            worker_att = att_index.get(dni, {})

            cells = [
                Paragraph(str(row_idx), sty_num),
                Paragraph(nombre,       sty_bold),
            ]

            for col_idx, day in enumerate(week_days, 2):
                row_data = worker_att.get(day)
                cells.append(cell_marcaciones(row_data))

                # colorear celda según estado
                if row_data is None:
                    style_cmds.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), C_ABSENT_BG))
                elif row_data.get("late"):
                    style_cmds.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), C_RED_BG))
                elif day.weekday() == 5:  # sábado
                    style_cmds.append(("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), C_SAT_BG))

            table_rows.append(cells)

        week_table = Table(table_rows, colWidths=col_ws, repeatRows=1)
        week_table.setStyle(TableStyle(style_cmds))

        story.append(KeepTogether([week_table]))
        story.append(Spacer(1, 5*mm))

    # ── PIE ───────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.4, color=C_MID))
    story.append(Paragraph(
        f"Generado el {generated_at}  |  {len(workers)} trabajadores  |  "
        f"{len(rows)} registros  |  {puntual_count} a tiempo  |  {tardanzas} tardanzas",
        sty_footer,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()

# ================================================================
#  HTML TABLA SEMANAL
# ================================================================

def _cell_html(attendance_row):
    if not attendance_row:
        return '<span class="m-empty">-</span>'
    entrada = attendance_row.get("hora_inicio") or "-"
    salida  = attendance_row.get("hora_final")  or "-"
    is_late = bool(attendance_row.get("late"))
    color   = "#dc2626" if is_late else "#1d4ed8"
    return (
        '<div style="display:flex;flex-direction:column;gap:.12rem;line-height:1.15;">'
        f'<span style="font-family:Space Mono,monospace;font-size:.78rem;color:{color};font-weight:700;">{entrada}</span>'
        f'<span style="font-family:Space Mono,monospace;font-size:.78rem;color:#166534;font-weight:700;">{salida}</span>'
        "</div>"
    )


def _render_weekly_matrix(workers, attendance_map, days):
    rows_html = []
    for worker in workers:
        dni   = worker.get("dni", "")
        w_att = attendance_map.get(dni, {})
        cells = "".join(f"<td>{_cell_html(w_att.get(d))}</td>" for d in days)
        rows_html.append(f"""
        <tr>
          <td class="worker-td">
            <div class="worker-name">{worker.get('nombre_trabajador','-')}</div>
            <div class="worker-meta">DNI {dni} · {worker.get('nombre_sede','-')}</div>
          </td>
          {cells}
        </tr>""")

    header_cells = "".join(
        f"<th>{d.strftime('%A')}<br>"
        f"<span style='font-weight:400;font-size:.6rem;'>{d.strftime('%d/%m')}</span></th>"
        for d in days
    )
    return f"""
    <html><head><style>
      body{{margin:0;font-family:'DM Sans',sans-serif;}}
      .wrap{{overflow-x:auto;border:1px solid #e2e8f0;border-radius:12px;
             background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.04);}}
      .at-table{{width:100%;border-collapse:collapse;font-size:.85rem;}}
      .at-table thead th{{text-align:left;padding:.85rem .9rem;background:#f8fafc;
        color:#64748b;font-family:'Space Mono',monospace;font-size:.68rem;
        text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid #e2e8f0;
        white-space:nowrap;}}
      .at-table tbody tr{{border-bottom:1px solid #f1f5f9;}}
      .at-table tbody tr:hover{{background:#fafbff;}}
      .at-table td{{padding:1rem .9rem;vertical-align:middle;color:#1e293b;}}
      .at-table td.worker-td{{min-width:180px;}}
      .worker-name{{font-weight:700;color:#0f172a;font-size:.85rem;}}
      .worker-meta{{font-size:.69rem;color:#64748b;margin-top:.15rem;}}
      .m-empty{{color:#94a3b8;font-family:'Space Mono',monospace;font-size:.78rem;}}
    </style></head>
    <body><div class="wrap">
      <table class="at-table">
        <thead><tr><th>Trabajador</th>{header_cells}</tr></thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div></body></html>"""


# ================================================================
#  VISTA PRINCIPAL
# ================================================================

def render_resumen(api=None):
    if api is None:
        st.error("Falta el contexto de la app.")
        return

    st.markdown("""
    <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.25rem;">
        <div style="font-size:1.4rem;color:#2563eb;">⬡</div>
        <div>
            <div style="font-family:'Space Mono',monospace;font-size:1.25rem;
                        letter-spacing:0.03em;color:#000000;line-height:1.1;">
                Asistencias
            </div>
            <div style="font-size:0.78rem;color:#000000;font-family:'DM Sans',sans-serif;
                        margin-top:0.15rem;">
                Vista semanal por trabajador · PostgreSQL
            </div>
        </div>
    </div>
    <hr style="margin:0.75rem 0 1.5rem;border-color:#dde1ea;">
    """, unsafe_allow_html=True)

    with st.spinner("Cargando asistencias..."):
        asistencias  = api.get_asistencias()
        trabajadores = api.get_trabajadores()
        tiendas      = api.get_tiendas()
        horarios     = api.get_horarios_trabajador()

    store_options = {"Todas": None}
    store_options.update({
        f"{s['nombre_tienda']} · {s['id_tienda']}": s for s in tiendas
    })

    if "resumen_week" not in st.session_state:
        all_dates = [_parse_date(r.get("fecha")) for r in asistencias if _parse_date(r.get("fecha"))]
        st.session_state["resumen_week"] = max(all_dates) if all_dates else date.today()

    current_start = _week_start(st.session_state["resumen_week"])
    week_end      = current_start + timedelta(days=6)
    week_days     = [current_start + timedelta(days=i) for i in range(7)]

    # Filtros
    sc1, sc2, sc3, sc4 = st.columns([2.4, 1.3, 0.9, 1.1])
    search_query = sc1.text_input(
        "Buscar", placeholder="Nombre, DNI o sede...",
        key="resumen_search", label_visibility="collapsed",
    )
    selected_store_label = sc2.selectbox(
        "Tienda", options=list(store_options.keys()),
        index=0, key="resumen_store_filter", label_visibility="collapsed",
    )
    if sc3.button("Anterior", use_container_width=True, key="resumen_prev_button"):
        st.session_state["resumen_week"] = current_start - timedelta(days=7)
        st.rerun()
    picked = sc4.date_input("Semana", value=current_start,
                            key="resumen_picker", label_visibility="collapsed")
    if picked != current_start:
        st.session_state["resumen_week"] = picked
        current_start = _week_start(picked)
        week_end  = current_start + timedelta(days=6)
        week_days = [current_start + timedelta(days=i) for i in range(7)]

    schedule_map = _build_schedule_map(horarios)
    _apply_late_flag(asistencias, schedule_map)

    filtered_workers, filtered_asistencias = _filter_context(
        asistencias, trabajadores, selected_store_label, store_options, search_query,
    )

    valid_dates = [_parse_date(r.get("fecha")) for r in filtered_asistencias
                   if _parse_date(r.get("fecha"))]

    # Metricas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tiendas",      len(tiendas))
    m2.metric("Trabajadores", len(filtered_workers))
    m3.metric("Registros",    len(filtered_asistencias))
    m4.metric("Rango de fechas",
              f"{min(valid_dates).strftime('%d/%m')} - {max(valid_dates).strftime('%d/%m')}"
              if valid_dates else "-")

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    st.caption(f"Semana: `{_week_label(current_start)}` · `{len(filtered_asistencias):,}` registros")

    attendance_map = {}
    for row in filtered_asistencias:
        parsed = _parse_date(row.get("fecha"))
        if not parsed or not (current_start <= parsed <= week_end):
            continue
        attendance_map.setdefault(str(row.get("dni","")).strip(), {})[parsed] = row

    total_present  = sum(1 for w in filtered_workers for d in week_days
                         if attendance_map.get(w.get("dni",""), {}).get(d))
    total_possible = len(filtered_workers) * 7

    c1, c2 = st.columns(2)
    c1.metric("Marcas en la semana", total_present)
    c2.metric("Faltas en la semana", max(total_possible - total_present, 0))

    if not filtered_workers:
        st.info("No hay trabajadores o asistencias para este rango.")
        return

    # Exportar PDF
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    ex1, ex2, ex3 = st.columns([1.1, 1.1, 1.3])

    export_period = ex1.selectbox(
        "Periodo PDF", ["Mes", "Quincena"],
        index=0, key="resumen_export_period",
    )
    export_reference = ex2.date_input(
        "Referencia PDF",
        value=st.session_state.get("resumen_week", date.today()),
        key="resumen_export_reference",
    )
    ex3.caption("Respeta el filtro de tienda y busqueda activa.")

    export_start, export_end, period_label = _period_bounds(export_period, export_reference)
    export_rows = _collect_period_rows(
        filtered_asistencias, filtered_workers,
        export_start, export_end, schedule_map,
    )

    if export_rows:
        pdf_bytes = _build_attendance_pdf(
            period_label         = period_label,
            selected_store_label = selected_store_label,
            search_query         = search_query,
            workers              = filtered_workers,
            rows                 = export_rows,
            start_date           = export_start,
            end_date             = export_end,
            tiendas              = tiendas,
        )
        pdf_name = (
            f"asistencias_{_sanitize_filename(period_label)}_"
            f"{_sanitize_filename(selected_store_label)}.pdf"
        )
        ex3.download_button(
            "Exportar PDF",
            data=pdf_bytes,
            file_name=pdf_name,
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        ex3.info("Sin registros para el periodo seleccionado.")

    # Tabla semanal
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    table_html = _render_weekly_matrix(filtered_workers, attendance_map, week_days)
    components.html(table_html,
                    height=max(320, 92 + len(filtered_workers) * 88),
                    scrolling=True)