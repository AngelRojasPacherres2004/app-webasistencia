from calendar import monthrange
from datetime import date, datetime, time

import streamlit as st


def _badge_estado(estado: bool) -> str:
    if estado:
        return '<span class="badge badge--active">ACTIVO</span>'
    return '<span class="badge badge--inactive">INACTIVO</span>'


def _badge_cargo(cargo: str) -> str:
    if not cargo:
        return '<span class="badge badge--gray">-</span>'
    return f'<span class="badge badge--blue">{cargo.upper()}</span>'


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
    existing_password = worker.get("contrasena", "") if worker else ""
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
        password = col_2.text_input(
            "Contrasena",
            type="password",
            placeholder="Dejar vacio para mantener",
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

    missing = api.required_missing({"DNI": dni, "Nombre": nombre, "Tienda": tienda_label})
    if worker is None and not foto_dni:
        missing.append("Foto DNI")
    if not selected_days:
        missing.append("Dias laborables")

    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return None

    doc_id = str(dni).strip()
    tienda = tienda_options[tienda_label]
    photo_url = existing_photo
    if foto_dni:
        try:
            uploaded_dni = api.upload_worker_file(foto_dni, doc_id)
            photo_url = uploaded_dni["secure_url"]
        except Exception as exc:
            st.error(f"No se pudo subir el archivo a Cloudinary: {exc}")
            return None
    elif not photo_url and worker is None:
        st.error("Debes subir la foto del DNI.")
        return None

    password_value = password.strip() if password else ""
    stored_password = worker.get("contrasena", "") if worker else ""

    worker_data = {
        "dni": doc_id,
        "id_tienda": tienda["id_tienda"],
        "correo": api.normalize_email(correo),
        "contrasena": api.hash_password(password_value) if password_value else stored_password,
        "nombre": nombre.strip(),
        "cargo": cargo.strip(),
        "sueldo": float(sueldo) if sueldo is not None else None,
        "telefono": telefono.strip(),
        "csi": csi.strip(),
        "foto_dni": photo_url,
        "estado": bool(estado),
    }

    api.create_document(api.WORKER_COLLECTION, doc_id, worker_data)
    api.save_worker_schedule(worker_data, selected_days, horario)
    st.session_state["worker_success_message"] = f"Trabajador guardado -> `{api.WORKER_COLLECTION}/{doc_id}`"
    st.cache_data.clear()
    st.session_state[f"worker_{form_kind}_seed"] = form_seed + 1
    st.session_state["worker_form_mode"] = "list"
    st.rerun()


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

    if not trabajadores:
        st.info("No se encontraron trabajadores.")
        return

    st.markdown(
        """
        <div style='margin-bottom:12px;'>
            <span class='section-header__title'>Lista de trabajadores</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_h = st.columns([2.5, 1.2, 1.2, 1.2, 1, 0.6, 0.6])
    headers = ["TRABAJADOR", "DNI", "CARGO", "TIENDA", "ESTADO", "", ""]
    for col, header in zip(col_h, headers):
        col.markdown(f"<span class='table-header'>{header}</span>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    for worker in trabajadores:
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([2.5, 1.2, 1.2, 1.2, 1, 0.6, 0.6])

            with col1:
                alias = worker.get("nombre_sede", "") or ""
                st.markdown(
                    f"""
                    <div>
                        <span class="row-main">{worker.get('nombre_trabajador', '-')}</span>
                        {f'<br><span class="row-sub">{alias}</span>' if alias else ''}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col2:
                st.caption(worker.get("dni", "-"))

            with col3:
                st.markdown(_badge_cargo(worker.get("area", "")), unsafe_allow_html=True)

            with col4:
                st.caption(worker.get("nombre_sede", "-"))

            with col5:
                st.markdown(_badge_estado(worker.get("estado", True)), unsafe_allow_html=True)

            with col6:
                estado_actual = worker.get("estado", True)
                emoji = "🟢" if estado_actual else "🔴"
                nuevo_estado = not estado_actual
                if st.button(emoji, key=f"toggle_w_{worker['dni']}", help="Cambiar estado", use_container_width=True):
                    try:
                        api.update_document(
                            api.WORKER_COLLECTION,
                            worker["dni"],
                            {"estado": bool(nuevo_estado)},
                            key_field="dni",
                        )
                        st.cache_data.clear()
                        st.session_state["worker_success_message"] = "Estado actualizado."
                    except Exception as exc:
                        st.session_state["worker_success_message"] = f"Error: {exc}"
                    st.rerun()

            with col7:
                if st.button("🖍", key=f"edit_w_{worker['dni']}", help="Editar", use_container_width=True):
                    st.session_state["worker_form_mode"] = "editar"
                    st.session_state["worker_id_editar"] = worker["dni"]
                    st.rerun()

        if (
            st.session_state["worker_form_mode"] == "editar"
            and st.session_state["worker_id_editar"] == worker["dni"]
        ):
            _render_worker_form(api, worker=worker)

            if st.button("Cancelar edicion", key=f"cancel_edit_w_{worker['dni']}"):
                st.session_state["worker_form_mode"] = None
                st.session_state["worker_id_editar"] = None
                st.rerun()

            st.markdown(
                """
                <div style="margin:16px 0 8px;">
                    <span class="section-header__title" style="font-size:14px;">Horario registrado</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            horarios_w = [
                row for row in horarios
                if str(row.get("dni_trabajador", "")).strip() == str(worker.get("dni", "")).strip()
            ]
            if horarios_w:
                cols_h = st.columns([1.2, 1, 1, 1, 1])
                for col, label in zip(cols_h, ["Dia", "Entrada", "Ini. receso", "Fin receso", "Salida"]):
                    col.markdown(f"<span class='table-header'>{label}</span>", unsafe_allow_html=True)
                for row in horarios_w:
                    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 1])
                    c1.caption(row.get("dia_semana", "-").capitalize())
                    c2.caption(row.get("horario_entrada", "-"))
                    c3.caption(row.get("horario_inicio_receso", "-"))
                    c4.caption(row.get("horario_fin_receso", "-"))
                    c5.caption(row.get("horario_salida", "-"))
            else:
                st.info("Este trabajador aun no tiene horarios registrados.")
            return

    return
    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='margin-bottom:12px;'>
            <span class='section-header__title'>Resumen salarial</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    salary_worker_options = {f"{worker['nombre_trabajador']} - {worker['dni']}": worker for worker in trabajadores}
    if not salary_worker_options:
        st.info("No hay trabajadores disponibles para calcular el salario.")
        return

    salary_cols = st.columns([2.4, 1.2])
    selected_salary_label = salary_cols[0].selectbox(
        "Trabajador seleccionado",
        options=list(salary_worker_options.keys()),
        index=None,
        placeholder="Selecciona un trabajador",
        key="salary_worker_select",
    )

    selected_salary_worker = salary_worker_options.get(selected_salary_label) if selected_salary_label else None
    if not selected_salary_worker:
        st.caption("Selecciona un trabajador para ver el calculo mensual.")
        return

    attendance_rows = api.get_asistencias_trabajador(selected_salary_worker["id_trabajador"])
    attendance_months = sorted({
        date.fromisoformat(str(item.get("fecha", ""))[:10]).replace(day=1)
        for item in attendance_rows
        if str(item.get("fecha", "")).strip()
    })
    if not attendance_months:
        attendance_months = [date.today().replace(day=1)]

    month_key = f"salary_month_{selected_salary_worker['dni']}"
    if month_key not in st.session_state or st.session_state[month_key] not in attendance_months:
        st.session_state[month_key] = attendance_months[-1]

    selected_month = salary_cols[1].selectbox(
        "Mes",
        options=attendance_months,
        format_func=lambda value: value.strftime("%B %Y"),
        key=month_key,
    )

    salary_summary = _build_salary_summary(api, selected_salary_worker, selected_month)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Sueldo base", f"S/ {salary_summary['base_salary']:,.2f}")
    metric_cols[1].metric("Faltas", salary_summary["absences"])
    metric_cols[2].metric("Tardanzas", salary_summary["tardies"])
    metric_cols[3].metric("Total estimado", f"S/ {salary_summary['net_salary']:,.2f}")

    st.caption(
        f"Mes evaluado: `{selected_month.strftime('%B %Y')}` · "
        f"{salary_summary['expected_days']} dias programados · "
        f"dia base `S/ {salary_summary['daily_rate']:,.2f}` · "
        f"hora referencial `S/ {salary_summary['hour_rate']:,.2f}`"
    )

    detail_cols = st.columns(3)
    detail_cols[0].metric("Descuento por faltas", f"S/ {salary_summary['absence_deduction']:,.2f}")
    detail_cols[1].metric("Descuento por tardanzas", f"S/ {salary_summary['tardy_deduction']:,.2f}")
    detail_cols[2].metric("Descuentos totales", f"S/ {salary_summary['total_deductions']:,.2f}")

    with st.expander("Ver calculo detallado", expanded=False):
        st.markdown(
            f"""
            <div style="font-size:0.9rem;line-height:1.6;">
                <strong>Formula:</strong><br>
                Sueldo base - faltas - tardanzas<br>
                = <code>S/ {salary_summary['base_salary']:,.2f}</code>
                - <code>S/ {salary_summary['absence_deduction']:,.2f}</code>
                - <code>S/ {salary_summary['tardy_deduction']:,.2f}</code>
                = <code>S/ {salary_summary['net_salary']:,.2f}</code>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if salary_summary["breakdown"]:
            st.dataframe(salary_summary["breakdown"], use_container_width=True, hide_index=True)
