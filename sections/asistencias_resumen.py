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
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.enums import TA_RIGHT
    from io import BytesIO

    C_BLACK      = colors.HexColor("#0f172a")
    C_DARK       = colors.HexColor("#1e293b")
    C_MID        = colors.HexColor("#64748b")
    C_LIGHT      = colors.HexColor("#f1f5f9")
    C_WHITE      = colors.white
    C_HEADER_BG  = colors.HexColor("#1e3a5f")
    C_ROW_ALT    = colors.HexColor("#f8fafc")
    C_ACCENT     = colors.HexColor("#2563eb")
    C_GREEN_TEXT = colors.HexColor("#166534")
    C_RED_TEXT   = colors.HexColor("#991b1b")
    C_RED_BG     = colors.HexColor("#fff0f0")

    def sty(name, font="Helvetica", size=8, color=None, bold=False, align=None, leading=10):
        kw = dict(fontName="Helvetica-Bold" if bold else font,
                  fontSize=size, textColor=color or C_BLACK, leading=leading)
        if align:
            kw["alignment"] = align
        return ParagraphStyle(name, **kw)

    sty_title    = sty("title",  bold=True,  size=18, leading=22)
    sty_subtitle = sty("sub",    size=9,     color=C_DARK, leading=12)
    sty_footer   = sty("foot",   size=7,     color=C_MID,  align=TA_RIGHT, leading=9)
    sty_ml       = sty("ml",     bold=True,  size=8)
    sty_mv       = sty("mv",     size=8,     color=C_DARK)
    sty_sec      = sty("sec",    bold=True,  size=10, color=C_ACCENT, leading=14)
    sty_th       = sty("th",     bold=True,  size=8,  color=C_WHITE)
    sty_cell     = sty("cell",   size=7.5)
    sty_bold     = sty("bold",   bold=True,  size=7.5)
    sty_late     = sty("late",   bold=True,  size=7.5, color=C_RED_TEXT)
    sty_ok       = sty("ok",     bold=True,  size=7.5, color=C_GREEN_TEXT)

    generated_at  = datetime.now().strftime("%d/%m/%Y %H:%M")
    store_label   = selected_store_label if selected_store_label != "Todas" else "Todas las tiendas"
    tardanzas     = sum(1 for r in rows if r.get("late"))
    puntual_count = len(rows) - tardanzas

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm,  bottomMargin=15*mm)
    story = []

    # TITULO
    story.append(Paragraph("Reporte de Asistencias", sty_title))
    story.append(Paragraph(
        f"Periodo: <b>{period_label}</b>  ·  Generado: {generated_at}", sty_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceAfter=3*mm))

    # METADATOS
    meta = [
        [Paragraph("<b>Tienda</b>", sty_ml), Paragraph(store_label, sty_mv),
         Paragraph("<b>Periodo</b>", sty_ml), Paragraph(period_label, sty_mv)],
        [Paragraph("<b>Rango</b>", sty_ml),
         Paragraph(f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}", sty_mv),
         Paragraph("<b>Busqueda</b>", sty_ml), Paragraph(search_query or "-", sty_mv)],
        [Paragraph("<b>Trabajadores</b>", sty_ml), Paragraph(str(len(workers)), sty_mv),
         Paragraph("<b>Registros</b>", sty_ml), Paragraph(str(len(rows)), sty_mv)],
        [Paragraph("<b>A tiempo</b>", sty_ml), Paragraph(str(puntual_count), sty_mv),
         Paragraph("<b>Tardanzas</b>", sty_ml), Paragraph(str(tardanzas), sty_mv)],
    ]
    meta_t = Table(meta, colWidths=[32*mm, 88*mm, 32*mm, 68*mm])
    meta_t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [C_WHITE, C_LIGHT]),
        ("BOX",           (0,0), (-1,-1), 0.5, C_MID),
        ("INNERGRID",     (0,0), (-1,-1), 0.25, C_MID),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 5),
        ("RIGHTPADDING",  (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(meta_t)

    # RESUMEN POR TIENDA
    if tiendas and len(tiendas) > 1:
        story.append(Paragraph("Resumen por tienda", sty_sec))
        tstats = {}
        for r in rows:
            sede = _safe_text(r.get("nombre_sede", "Sin tienda"))
            tstats.setdefault(sede, {"total": 0, "tarde": 0, "workers": set()})
            tstats[sede]["total"] += 1
            tstats[sede]["workers"].add(r.get("dni", ""))
            if r.get("late"):
                tstats[sede]["tarde"] += 1

        thead = [Paragraph(h, sty_th) for h in
                 ["Tienda","Trabajadores","Registros","A tiempo","Tardanzas","% Puntualidad"]]
        trows = [thead]
        for nombre, s in sorted(tstats.items()):
            pct = round((s["total"] - s["tarde"]) / s["total"] * 100) if s["total"] else 0
            trows.append([
                Paragraph(nombre, sty_cell),
                Paragraph(str(len(s["workers"])), sty_cell),
                Paragraph(str(s["total"]), sty_cell),
                Paragraph(str(s["total"] - s["tarde"]), sty_ok),
                Paragraph(str(s["tarde"]), sty_late if s["tarde"] else sty_cell),
                Paragraph(f"{pct}%", sty_bold),
            ])
        st2 = Table(trows, colWidths=[70*mm, 28*mm, 26*mm, 26*mm, 26*mm, 34*mm])
        st2.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  C_HEADER_BG),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_ROW_ALT]),
            ("BOX",           (0,0), (-1,-1), 0.5, C_MID),
            ("INNERGRID",     (0,0), (-1,-1), 0.25, C_MID),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
            ("RIGHTPADDING",  (0,0), (-1,-1), 4),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(st2)

    # TABLA PRINCIPAL
    story.append(Paragraph("Detalle de asistencias", sty_sec))
    col_widths = [20*mm, 46*mm, 20*mm, 26*mm, 38*mm,
                  18*mm, 20*mm, 20*mm, 18*mm, 20*mm]
    headers = [Paragraph(h, sty_th) for h in
               ["Fecha","Trabajador","DNI","Cargo","Tienda",
                "Entrada","Ini.Receso","Fin Receso","Salida","Estado"]]
    table_rows = [headers]
    for row in rows:
        is_late = bool(row.get("late"))
        fecha_d = _parse_date(row.get("fecha"))
        fecha_s = fecha_d.strftime("%d/%m/%Y") if fecha_d else _safe_text(row.get("fecha",""))
        table_rows.append([
            Paragraph(fecha_s,                                     sty_cell),
            Paragraph(_safe_text(row.get("nombre_trabajador","")), sty_bold),
            Paragraph(_safe_text(row.get("dni","")),               sty_cell),
            Paragraph(_safe_text(row.get("cargo","")),             sty_cell),
            Paragraph(_safe_text(row.get("nombre_sede","")),       sty_cell),
            Paragraph(_safe_text(row.get("hora_inicio","--")),     sty_late if is_late else sty_cell),
            Paragraph(_safe_text(row.get("inicio_receso","--")),   sty_cell),
            Paragraph(_safe_text(row.get("final_receso","--")),    sty_cell),
            Paragraph(_safe_text(row.get("hora_final","--")),      sty_cell),
            Paragraph("TARDANZA" if is_late else "A TIEMPO",       sty_late if is_late else sty_ok),
        ])

    ts = TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  C_HEADER_BG),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_WHITE, C_ROW_ALT]),
        ("BOX",           (0,0), (-1,-1), 0.5, C_MID),
        ("INNERGRID",     (0,0), (-1,-1), 0.25, C_MID),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ("RIGHTPADDING",  (0,0), (-1,-1), 4),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ])
    for idx, row in enumerate(rows, 1):
        if row.get("late"):
            ts.add("BACKGROUND", (0, idx), (-1, idx), C_RED_BG)

    main_t = Table(table_rows, colWidths=col_widths, repeatRows=1)
    main_t.setStyle(ts)
    story.append(main_t)

    # PIE
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_MID))
    story.append(Paragraph(
        f"Generado el {generated_at}  |  {len(rows)} registros  |  "
        f"{puntual_count} a tiempo  |  {tardanzas} tardanzas",
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