from calendar import monthrange
from datetime import date, datetime, time
import re
import textwrap

import streamlit as st


def _badge_estado(estado: bool) -> str:
    if estado:
        return '<span class="badge badge--active">ACTIVO</span>'
    return '<span class="badge badge--inactive">INACTIVO</span>'


def _badge_cargo(cargo: str) -> str:
    if not cargo:
        return '<span class="badge badge--gray">-</span>'
    return f'<span class="badge badge--blue">{cargo.upper()}</span>'


def _validate_password(password):
    text = str(password or "").strip()
    if not text:
        return None
    if len(text) < 3:
        return "La contrasena debe tener al menos 3 caracteres."
    if not re.fullmatch(r"[A-Za-z0-9!@#$%^&*()_+\-=\[\]{};:'\",.<>/?\\|`~]+", text):
        return "La contrasena solo puede incluir letras, numeros y signos sin espacios."
    return None


def _worker_label(worker):
    return f"{worker.get('nombre_trabajador', '')} - {worker.get('dni', '')}"


def _weekday_name(day_value: date) -> str:
    return (
        "lunes",
        "martes",
        "miercoles",
        "jueves",
        "viernes",
        "sabado",
        "domingo",
    )[day_value.weekday()]


def _parse_time_value(value):
    if not value:
        return None
    if isinstance(value, time):
        return value
    try:
        return datetime.strptime(str(value)[:5], "%H:%M").time()
    except ValueError:
        return None


def _time_to_minutes(value):
    parsed = _parse_time_value(value)
    if not parsed:
        return None
    return parsed.hour * 60 + parsed.minute


def _scheduled_day_hours(schedule_row):
    entry = _time_to_minutes(schedule_row.get("horario_entrada"))
    exit_time = _time_to_minutes(schedule_row.get("horario_salida"))
    if entry is None or exit_time is None:
        return 8.0

    total_minutes = exit_time - entry
    if total_minutes <= 0:
        return 8.0

    break_start = _time_to_minutes(schedule_row.get("horario_inicio_receso"))
    break_end = _time_to_minutes(schedule_row.get("horario_fin_receso"))
    if break_start is not None and break_end is not None and break_end > break_start:
        total_minutes -= break_end - break_start

    return max(total_minutes / 60, 1.0)


def _month_days(month_start):
    total_days = monthrange(month_start.year, month_start.month)[1]
    return [date(month_start.year, month_start.month, day) for day in range(1, total_days + 1)]


def _build_salary_summary(api, worker, month_start):
    attendance_rows = api.get_asistencias_trabajador(worker["id_trabajador"])
    schedule_rows = {
        row.get("dia_semana", ""): row
        for row in api.get_horarios_trabajador()
        if str(row.get("dni_trabajador", "")).strip() == str(worker.get("dni", "")).strip()
    }

    monthly_attendance = {}
    for row in attendance_rows:
        try:
            current_date = date.fromisoformat(str(row.get("fecha", ""))[:10])
        except ValueError:
            continue
        if current_date.year == month_start.year and current_date.month == month_start.month:
            monthly_attendance[current_date] = row

    scheduled_days = worker.get("dias_horario", []) or list(schedule_rows.keys())
    scheduled_days = [day for day in scheduled_days if day]

    expected_days = [
        current_day
        for current_day in _month_days(month_start)
        if _weekday_name(current_day) in scheduled_days
    ]

    base_salary = float(worker.get("sueldo") or 0)
    daily_rate = base_salary / len(expected_days) if expected_days else 0.0

    breakdown = []
    absences = 0
    tardies = 0
    absence_deduction = 0.0
    tardy_deduction = 0.0
    expected_day_hours = []

    for current_day in expected_days:
        day_name = _weekday_name(current_day)
        attendance = monthly_attendance.get(current_day)
        schedule_row = schedule_rows.get(day_name, {})
        scheduled_entry = _time_to_minutes(schedule_row.get("horario_entrada"))
        scheduled_hours = _scheduled_day_hours(schedule_row)
        expected_day_hours.append(scheduled_hours)

        if not attendance:
            absences += 1
            deduction = daily_rate
            absence_deduction += deduction
            breakdown.append({
                "Fecha": current_day.isoformat(),
                "Tipo": "Falta",
                "Entrada programada": schedule_row.get("horario_entrada", "-"),
                "Entrada real": "-",
                "Descuento": round(deduction, 2),
            })
            continue

        actual_entry = _time_to_minutes(attendance.get("hora_inicio"))
        is_late = (
            scheduled_entry is not None
            and actual_entry is not None
            and actual_entry > scheduled_entry
        )
        deduction = 0.0
        if is_late:
            tardies += 1
            deduction = daily_rate / scheduled_hours if scheduled_hours else 0.0
            tardy_deduction += deduction

        breakdown.append({
            "Fecha": current_day.isoformat(),
            "Tipo": "Tardanza" if is_late else "Asistencia",
            "Entrada programada": schedule_row.get("horario_entrada", "-"),
            "Entrada real": attendance.get("hora_inicio", "-"),
            "Descuento": round(deduction, 2),
        })

    total_deductions = absence_deduction + tardy_deduction
    net_salary = max(base_salary - total_deductions, 0.0)
    average_day_hours = sum(expected_day_hours) / len(expected_day_hours) if expected_day_hours else 8.0

    return {
        "month_start": month_start,
        "base_salary": base_salary,
        "expected_days": len(expected_days),
        "present_days": len(expected_days) - absences,
        "absences": absences,
        "tardies": tardies,
        "daily_rate": daily_rate,
        "hour_rate": daily_rate / average_day_hours if daily_rate else 0.0,
        "average_day_hours": average_day_hours,
        "absence_deduction": absence_deduction,
        "tardy_deduction": tardy_deduction,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
        "breakdown": breakdown,
    }


def _build_initial_schedule(horarios, dni):
    schedule = {}
    for row in horarios:
        if str(row.get("dni_trabajador", "")).strip() != str(dni).strip():
            continue
        schedule[row.get("dia_semana", "")] = {
            "horario_entrada": row.get("horario_entrada", ""),
            "horario_inicio_receso": row.get("horario_inicio_receso", ""),
            "horario_fin_receso": row.get("horario_fin_receso", ""),
            "horario_salida": row.get("horario_salida", ""),
        }
    return schedule


def _selected_days_from_worker(worker):
    if not worker:
        return []
    days = worker.get("dias_horario", [])
    if isinstance(days, list):
        return [day for day in days if day]
    if isinstance(days, str):
        return [part.strip() for part in days.split(",") if part.strip()]
    return []


def _schedule_rows_view(horarios):
    return [
        {
            "DNI": row.get("dni_trabajador", ""),
            "Trabajador": row.get("nombre_trabajador", ""),
            "Tienda": row.get("nombre_tienda", ""),
            "Dia": row.get("dia_semana", ""),
            "Entrada": row.get("horario_entrada", ""),
            "Ini. receso": row.get("horario_inicio_receso", ""),
            "Fin receso": row.get("horario_fin_receso", ""),
            "Salida": row.get("horario_salida", ""),
        }
        for row in horarios
    ]


def _safe_text(value):
    text = str(value or "")
    return text.replace("\r", " ").replace("\n", " ").strip()


def _sanitize_filename(text):
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", _safe_text(text).lower()).strip("_")
    return safe or "reporte"


def _wrap_pdf_text(value, max_width):
    text = _safe_text(value)
    if not text:
        return [""]
    return textwrap.wrap(text, width=max_width, break_long_words=False, break_on_hyphens=False) or [text]


def _pdf_escape_text(value):
    return _safe_text(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def _build_workers_pdf(workers, tienda_label, search_query):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from io import BytesIO
    from datetime import datetime

    # ── Paleta ────────────────────────────────────────────────────
    C_BLACK      = colors.HexColor("#0f172a")
    C_DARK       = colors.HexColor("#1e293b")
    C_MID        = colors.HexColor("#64748b")
    C_LIGHT      = colors.HexColor("#f1f5f9")
    C_WHITE      = colors.white
    C_HEADER_BG  = colors.HexColor("#1e3a5f")  # azul oscuro — header tabla
    C_ROW_ALT    = colors.HexColor("#f8fafc")  # fila alternada
    C_ACCENT     = colors.HexColor("#2563eb")
    C_GREEN_BG   = colors.HexColor("#dcfce7")
    C_GREEN_TEXT = colors.HexColor("#166534")
    C_RED_BG     = colors.HexColor("#fee2e2")
    C_RED_TEXT   = colors.HexColor("#991b1b")

    # ── Estilos ───────────────────────────────────────────────────
    sty_title = ParagraphStyle("title",
        fontName="Helvetica-Bold", fontSize=18,
        textColor=C_BLACK, spaceAfter=2*mm)

    sty_subtitle = ParagraphStyle("subtitle",
        fontName="Helvetica", fontSize=9,
        textColor=C_DARK, spaceAfter=1*mm)

    sty_meta_lbl = ParagraphStyle("meta_lbl",
        fontName="Helvetica-Bold", fontSize=8, textColor=C_BLACK)

    sty_meta_val = ParagraphStyle("meta_val",
        fontName="Helvetica", fontSize=8, textColor=C_DARK)

    sty_footer = ParagraphStyle("footer",
        fontName="Helvetica", fontSize=7,
        textColor=C_MID, alignment=TA_RIGHT)

    sty_th = ParagraphStyle("th",
        fontName="Helvetica-Bold", fontSize=8,
        textColor=C_WHITE, leading=10)

    sty_cell = ParagraphStyle("cell",
        fontName="Helvetica", fontSize=8,
        textColor=C_BLACK, leading=10)

    sty_cell_bold = ParagraphStyle("cell_bold",
        fontName="Helvetica-Bold", fontSize=8,
        textColor=C_BLACK, leading=10)

    sty_active = ParagraphStyle("active",
        fontName="Helvetica-Bold", fontSize=7.5,
        textColor=C_GREEN_TEXT, leading=10)

    sty_inactive = ParagraphStyle("inactive",
        fontName="Helvetica-Bold", fontSize=7.5,
        textColor=C_RED_TEXT, leading=10)

    # ── Stats ─────────────────────────────────────────────────────
    activos   = sum(1 for w in workers if w.get("estado", True))
    inactivos = len(workers) - activos
    tienda_text   = tienda_label if tienda_label != "Todas" else "Todas las tiendas"
    generated_at  = datetime.now().strftime("%d/%m/%Y %H:%M")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm,  bottomMargin=15*mm,
    )

    story = []

    # ── TÍTULO ────────────────────────────────────────────────────
    story.append(Paragraph("Reporte de Trabajadores", sty_title))
    story.append(Paragraph(f"Generado: {generated_at}", sty_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_ACCENT, spaceAfter=3*mm))

    # ── METADATOS ─────────────────────────────────────────────────
    meta = [
        [Paragraph("<b>Tienda</b>", sty_meta_lbl),
         Paragraph(tienda_text, sty_meta_val),
         Paragraph("<b>Búsqueda activa</b>", sty_meta_lbl),
         Paragraph(search_query or "—", sty_meta_val)],

        [Paragraph("<b>Total trabajadores</b>", sty_meta_lbl),
         Paragraph(str(len(workers)), sty_meta_val),
         Paragraph("<b>Activos / Inactivos</b>", sty_meta_lbl),
         Paragraph(f"{activos} activos  ·  {inactivos} inactivos", sty_meta_val)],
    ]
    meta_table = Table(meta, colWidths=[38*mm, 80*mm, 42*mm, 60*mm])
    meta_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_WHITE, C_LIGHT]),
        ("BOX",            (0, 0), (-1, -1), 0.5, C_MID),
        ("INNERGRID",      (0, 0), (-1, -1), 0.25, C_MID),
        ("TOPPADDING",     (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
        ("LEFTPADDING",    (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4*mm))

    # ── TABLA PRINCIPAL ───────────────────────────────────────────
    headers = [
        Paragraph("N°",           sty_th),
        Paragraph("Trabajador",   sty_th),
        Paragraph("DNI",          sty_th),
        Paragraph("Correo",       sty_th),
        Paragraph("Cargo",        sty_th),
        Paragraph("Tienda",       sty_th),
        Paragraph("Teléfono",     sty_th),
        Paragraph("Sueldo",       sty_th),
        Paragraph("Estado",       sty_th),
    ]
    col_widths = [10*mm, 55*mm, 22*mm, 55*mm, 28*mm, 45*mm, 28*mm, 20*mm, 22*mm]

    table_rows = [headers]
    for i, worker in enumerate(workers, 1):
        estado   = bool(worker.get("estado", True))
        sueldo   = worker.get("sueldo")
        sueldo_s = f"S/ {float(sueldo):,.2f}" if sueldo else "—"

        table_rows.append([
            Paragraph(str(i), sty_cell),
            Paragraph(_safe_text(worker.get("nombre_trabajador", "")), sty_cell_bold),
            Paragraph(_safe_text(worker.get("dni", "")),               sty_cell),
            Paragraph(_safe_text(worker.get("correo", "")),            sty_cell),
            Paragraph(_safe_text(worker.get("area") or worker.get("cargo", "")), sty_cell),
            Paragraph(_safe_text(worker.get("nombre_sede", "")),       sty_cell),
            Paragraph(_safe_text(worker.get("telefono", "")),          sty_cell),
            Paragraph(sueldo_s,                                         sty_cell),
            Paragraph("ACTIVO" if estado else "INACTIVO",
                      sty_active if estado else sty_inactive),
        ])

    main_table = Table(table_rows, colWidths=col_widths, repeatRows=1)

    # Estilo base
    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_HEADER_BG),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_MID),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, C_MID),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])

    # Colorear fila según estado
    for idx, worker in enumerate(workers, 1):
        if not worker.get("estado", True):
            ts.add("BACKGROUND", (0, idx), (-1, idx), C_RED_BG)
        elif idx % 2 == 0:
            ts.add("BACKGROUND", (0, idx), (-1, idx), C_ROW_ALT)

    main_table.setStyle(ts)
    story.append(main_table)

    # ── PIE ───────────────────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_MID))
    story.append(Paragraph(
        f"Generado el {generated_at}  ·  {len(workers)} trabajadores  ·  {activos} activos  ·  {inactivos} inactivos",
        sty_footer,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()

def _render_worker_form(api, worker=None):
    tiendas = api.get_tiendas()
    if not tiendas:
        st.warning("Primero registra al menos una tienda.")
        return

    form_kind = "edit" if worker else "create"
    form_seed = int(st.session_state.get(f"worker_{form_kind}_seed", 0))

    titulo = "Editar trabajador" if worker else "Nuevo trabajador"
    st.markdown(
        f"""
        <div class="form-card {'form-card--edit' if worker else 'form-card--create'}">
            <p class="form-card__title">{titulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_days = st.multiselect(
        "Dias laborables *",
        options=list(api.WEEK_DAYS),
        default=_selected_days_from_worker(worker) if worker else list(api.WEEK_DAYS),
        format_func=str.capitalize,
        key=f"worker_{form_kind}_days_{form_seed}",
    )
    if not selected_days:
        st.warning("Selecciona al menos un dia para el horario.")

    initial_schedule = _build_initial_schedule(api.get_horarios_trabajador(), worker.get("dni")) if worker else None
    existing_photo = worker.get("foto_dni", "") if worker else ""
    estado_actual = bool(worker.get("estado", True)) if worker else True

    tienda_options = {f"{t['nombre_tienda']} - {t['id_tienda']}": t for t in tiendas}
    selected_store_key = None
    if worker:
        for label, store in tienda_options.items():
            if store["id_tienda"] == worker.get("id_sede", ""):
                selected_store_key = label
                break

    button_text = "Guardar cambios" if worker else "Registrar trabajador"

    with st.form(f"worker_form_{form_kind}_{form_seed}", clear_on_submit=False):
        col_1, col_2 = st.columns(2)
        dni = col_1.text_input(
            "DNI *",
            value=worker.get("dni", "") if worker else "",
            placeholder="12345678",
            key=f"{form_kind}_dni_{form_seed}",
        )
        nombre = col_1.text_input(
            "Nombre completo *",
            value=worker.get("nombre_trabajador", "") if worker else "",
            placeholder="Juan Perez",
            key=f"{form_kind}_nombre_{form_seed}",
        )
        cargo = col_1.text_input(
            "Cargo",
            value=worker.get("area", "") if worker else "",
            placeholder="Ventas",
            key=f"{form_kind}_cargo_{form_seed}",
        )
        sueldo = col_1.number_input(
            "Sueldo",
            min_value=0.0,
            step=50.0,
            format="%.2f",
            value=float(worker.get("sueldo") or 0) if worker else 0.0,
            key=f"{form_kind}_sueldo_{form_seed}",
        )

        correo = col_2.text_input(
            "Correo",
            value=worker.get("correo", "") if worker else "",
            placeholder="juan@empresa.com",
            key=f"{form_kind}_correo_{form_seed}",
        )
        password_label = "Contrasena *" if not worker else "Contrasena"
        password_placeholder = "Ingresa una contrasena" if not worker else "Dejar vacio para mantener la actual"
        password = col_2.text_input(
            password_label,
            value="",
            type="password",
            placeholder=password_placeholder,
            key=f"{form_kind}_password_{form_seed}",
        )
        telefono = col_2.text_input(
            "Telefono",
            value=worker.get("telefono", "") if worker else "",
            placeholder="+51 999 999 999",
            key=f"{form_kind}_telefono_{form_seed}",
        )
        csi = col_2.text_input(
            "CSI / codigo interno",
            value=worker.get("csi", "") if worker else "",
            placeholder="CSI-001",
            key=f"{form_kind}_csi_{form_seed}",
        )
        estado = col_2.selectbox(
            "Estado",
            options=[True, False],
            index=0 if estado_actual else 1,
            format_func=lambda value: "Activo" if value else "Inactivo",
            key=f"{form_kind}_estado_{form_seed}",
        )
        foto_dni = col_2.file_uploader(
            "Foto DNI" + (" *" if worker is None else ""),
            type=["jpg", "jpeg", "png", "pdf"],
            key=f"{form_kind}_foto_{form_seed}",
        )

        tienda_label = st.selectbox(
            "Tienda asignada *",
            options=list(tienda_options.keys()),
            index=list(tienda_options.keys()).index(selected_store_key) if selected_store_key in tienda_options else None,
            placeholder="Selecciona una tienda",
            key=f"{form_kind}_tienda_{form_seed}",
        )

        horario = api.build_schedule_inputs(
            selected_days,
            key_prefix=f"{form_kind}_{form_seed}",
            initial_schedule=initial_schedule,
        )
        submitted = st.form_submit_button(button_text, use_container_width=True)

    if not submitted:
        return None

    try:
        missing = api.required_missing({"DNI": dni, "Nombre": nombre, "Tienda": tienda_label})
        if worker is None and not foto_dni:
            missing.append("Foto DNI")
        if worker is None and not password:
            missing.append("Contrasena")
        if not selected_days:
            missing.append("Dias laborables")

        if missing:
            st.error("Campos requeridos: " + ", ".join(missing))
            return None

        password_error = _validate_password(password)
        if password_error:
            st.error(password_error)
            return None

        doc_id = str(dni).strip()
        tienda = tienda_options[tienda_label]
        photo_url = existing_photo
        if foto_dni:
            uploaded_dni = api.upload_worker_file(foto_dni, doc_id)
            photo_url = uploaded_dni["secure_url"]
        elif not photo_url and worker is None:
            st.error("Debes subir la foto del DNI.")
            return None

        worker_data = {
            "dni": doc_id,
            "id_tienda": tienda["id_tienda"],
            "correo": api.normalize_email(correo),
            "nombre": nombre.strip(),
            "cargo": cargo.strip(),
            "sueldo": float(sueldo) if sueldo is not None else None,
            "telefono": telefono.strip(),
            "csi": csi.strip(),
            "foto_dni": photo_url,
            "estado": bool(estado),
        }
        if str(password or "").strip():
            worker_data["contrasena"] = str(password).strip()

        api.create_document(api.WORKER_COLLECTION, doc_id, worker_data)
        api.save_worker_schedule(worker_data, selected_days, horario)
        st.session_state["worker_success_message"] = f"Trabajador guardado -> `{api.WORKER_COLLECTION}/{doc_id}`"
        api.invalidate_collection_cache(api.WORKER_COLLECTION)
        st.session_state[f"worker_{form_kind}_seed"] = form_seed + 1
        st.session_state["worker_form_mode"] = "list"
        st.rerun()
    except Exception as exc:
        st.error(f"No se pudo guardar el trabajador: {exc}")


def render_trabajadores(api):
    st.markdown(
        """
        <div style="margin-bottom:24px;">
            <h2 class="page-title">Trabajadores</h2>
            <p class="page-subtitle">Gestion de personal, horarios y accesos</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for key in ["worker_form_mode", "worker_success_message", "worker_id_editar"]:
        if key not in st.session_state:
            st.session_state[key] = None

    msg = st.session_state.pop("worker_success_message", None)
    if msg:
        st.success(msg)

    tiendas = api.get_tiendas()
    trabajadores = api.get_trabajadores()
    horarios = api.get_horarios_trabajador()

    if not tiendas:
        st.warning("Primero registra al menos una tienda.")
        return

    col_busq, col_store, col_btn = st.columns([2.6, 1.4, 1])
    with col_busq:
        busqueda = st.text_input(
            "Buscar por nombre, DNI o cargo",
            placeholder="Escribe para filtrar...",
            label_visibility="collapsed",
        )
    store_options = {"Todas": None}
    store_options.update({f"{t['nombre_tienda']} - {t['id_tienda']}": t for t in tiendas})
    with col_store:
        tienda_filtro = st.selectbox(
            "Filtrar por tienda",
            options=list(store_options.keys()),
            index=0,
            key="worker_store_filter",
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("Nuevo trabajador", use_container_width=True, key="worker_new_button"):
            st.session_state["worker_form_mode"] = "crear"
            st.session_state["worker_id_editar"] = None
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if st.session_state["worker_form_mode"] == "crear":
        _render_worker_form(api, worker=None)
        if st.button("Cancelar", key="btn_cancel_crear_worker"):
            st.session_state["worker_form_mode"] = None
            st.rerun()
        st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:20px 0'>", unsafe_allow_html=True)

    if tienda_filtro != "Todas":
        selected_store = store_options[tienda_filtro]
        trabajadores = [
            worker for worker in trabajadores
            if str(worker.get("id_sede", "")).strip() == str(selected_store["id_tienda"]).strip()
        ]

    if busqueda:
        query = busqueda.lower()
        trabajadores = [
            worker for worker in trabajadores
            if query in worker.get("nombre_trabajador", "").lower()
            or query in worker.get("dni", "").lower()
            or query in (worker.get("area", "") or "").lower()
        ]

    filtered_workers = list(trabajadores)

    if not filtered_workers:
        st.info("No se encontraron trabajadores.")
        return

    export_col_1, export_col_2 = st.columns([1.05, 1.35])
    export_col_1.caption("Exporta en PDF la lista filtrada de trabajadores.")
    pdf_bytes = _build_workers_pdf(filtered_workers, tienda_filtro, busqueda)
    pdf_name = f"trabajadores_{_sanitize_filename(tienda_filtro)}.pdf"
    export_col_2.download_button(
        "Exportar PDF",
        data=pdf_bytes,
        file_name=pdf_name,
        mime="application/pdf",
        use_container_width=True,
    )

    # Envolvemos toda la lista y encabezados en un único contenedor unificado (Panel responsivo)
    with st.container(border=True):
        st.markdown("<div style='margin-bottom:15px;'><span class='section-header__title'>Lista de trabajadores</span></div>", unsafe_allow_html=True)
        
        # Cabecera de la tabla dentro del contenedor para mantener alineación responsiva
        headers = ["TRABAJADOR", "CORREO", "CARGO", "ESTADO", "", ""]
        col_h = st.columns([2.6, 1.7, 1.2, 1, 0.6, 0.6])
        for col, header in zip(col_h, headers):
            col.markdown(f"<span class='table-header'>{header}</span>", unsafe_allow_html=True)
            
        st.markdown("<hr style='margin:0.8rem 0; border-color:#e2e8f0; opacity:0.8;'>", unsafe_allow_html=True)

        for i, worker in enumerate(filtered_workers):
            if i > 0:
                st.markdown("<hr style='margin:0.5rem 0; border-color:#f1f5f9; opacity:0.6;'>", unsafe_allow_html=True)
            
            col1, col2, col3, col4, col5, col6 = st.columns([2.6, 1.7, 1.2, 1, 0.6, 0.6])

            with col1:
                nombre = worker.get("nombre_trabajador", "-")
                st.markdown(
                    f"""
                    <div>
                        <div class="row-main">{nombre}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col2:
                st.caption(str(worker.get("correo", "-")))
            
            with col3:
                st.markdown(_badge_cargo(worker.get("area", worker.get("cargo", ""))), unsafe_allow_html=True)

            with col4:
                st.markdown(_badge_estado(worker.get("estado", True)), unsafe_allow_html=True)

            with col5:
                estado_actual = bool(worker.get("estado", True))
                emoji = "🟢" if estado_actual else "🔴"
                nuevo_estado = not estado_actual
                if st.button(emoji, key=f"toggle_worker_{worker['dni']}", help="Cambiar estado", use_container_width=True):
                    try:
                        api.update_document(
                            api.WORKER_COLLECTION,
                            worker["dni"],
                            {"estado": bool(nuevo_estado)},
                            key_field="dni",
                        )
                        api.invalidate_collection_cache(api.WORKER_COLLECTION)
                        st.session_state["worker_success_message"] = "✅ Estado actualizado."
                    except Exception as exc:
                        st.session_state["worker_success_message"] = f"Error: {exc}"
                    st.rerun()

            with col6:
                if st.button("🖍", key=f"edit_worker_{worker['dni']}", help="Editar", use_container_width=True):
                    st.session_state["worker_form_mode"] = "editar"
                    st.session_state["worker_id_editar"] = worker["dni"]
                    st.rerun()

    # Formulario de edición fuera del panel de lista
    if st.session_state.get("worker_form_mode") == "editar" and st.session_state.get("worker_id_editar"):
        worker_to_edit = next((w for w in trabajadores if w["dni"] == st.session_state["worker_id_editar"]), None)
        if worker_to_edit:
            st.markdown("---")
            _render_worker_form(api, worker=worker_to_edit)
            if st.button("✖ Cancelar edición", key="btn_cancel_edit_worker"):
                st.session_state["worker_form_mode"] = "list"
                st.session_state["worker_id_editar"] = None
                st.rerun()
