from calendar import monthrange
from datetime import date, datetime, time

import streamlit as st


def _parse_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _weekday_name(day_value):
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
        parsed_date = _parse_date(row.get("fecha"))
        if parsed_date and parsed_date.year == month_start.year and parsed_date.month == month_start.month:
            monthly_attendance[parsed_date] = row

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


def _worker_card(worker):
    return f"""
    <div class="salary-worker-card">
        <div class="salary-worker-name">{worker.get('nombre_trabajador', '-')}</div>
        <div class="salary-worker-meta">DNI {worker.get('dni', '-')} · {worker.get('nombre_sede', '-')}</div>
    </div>
    """


def render_salarios(api):
    api.section_header("Salarios", "Estimacion mensual con descuentos por faltas y tardanzas")

    tiendas = api.get_tiendas()
    trabajadores = api.get_trabajadores()

    st.markdown(
        """
        <style>
        .salary-hero {
            border: 1px solid #cfe3f7;
            border-left: 5px solid #2563eb;
            border-radius: 14px;
            padding: 1.15rem 1.25rem;
            background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
            box-shadow: 0 10px 24px rgba(120, 189, 242, 0.12);
            margin-bottom: 1rem;
        }
        .salary-hero__title {
            font-family: 'Space Mono', monospace;
            font-size: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #0f172a;
            margin: 0;
        }
        .salary-hero__sub {
            margin-top: 0.35rem;
            color: #5f7182;
            font-size: 0.82rem;
        }
        .salary-worker-card {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            background: #fff;
            padding: 0.9rem 1rem;
            margin-bottom: 0.5rem;
        }
        .salary-worker-name {
            font-weight: 700;
            color: #0f172a;
            font-size: 0.92rem;
        }
        .salary-worker-meta {
            color: #64748b;
            font-size: 0.74rem;
            margin-top: 0.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="salary-hero">
            <div class="salary-hero__title">Salario esperado</div>
            <div class="salary-hero__sub">
                Selecciona una tienda, un trabajador y un mes para ver el total estimado con faltas y tardanzas.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not tiendas:
        st.warning("Primero registra al menos una tienda.")
        return
    if not trabajadores:
        st.warning("Todavia no hay trabajadores registrados.")
        return

    store_options = {"Todas": None}
    store_options.update({f"{store['nombre_tienda']} · {store['id_tienda']}": store for store in tiendas})

    col_filter_1, col_filter_2 = st.columns([1.35, 1])
    selected_store_label = col_filter_1.selectbox(
        "Filtrar por tienda",
        options=list(store_options.keys()),
        index=0,
        key="salario_store_filter",
    )
    search_query = col_filter_2.text_input(
        "Buscar trabajador",
        placeholder="Nombre, DNI o cargo",
        key="salario_worker_search",
    )

    filtered_workers = trabajadores
    if selected_store_label != "Todas":
        selected_store = store_options[selected_store_label]
        filtered_workers = [
            worker for worker in filtered_workers
            if str(worker.get("id_sede", "")).strip() == str(selected_store["id_tienda"]).strip()
        ]

    if search_query:
        query = search_query.lower()
        filtered_workers = [
            worker for worker in filtered_workers
            if query in worker.get("nombre_trabajador", "").lower()
            or query in worker.get("dni", "").lower()
            or query in (worker.get("area", "") or "").lower()
        ]

    if not filtered_workers:
        st.info("No se encontraron trabajadores con ese filtro.")
        return

    worker_options = {f"{worker['nombre_trabajador']} · {worker['dni']}": worker for worker in filtered_workers}
    selected_worker_label = st.selectbox(
        "Trabajador",
        options=list(worker_options.keys()),
        index=None,
        placeholder="Selecciona un trabajador",
        key="salary_worker_select",
    )

    selected_worker = worker_options.get(selected_worker_label) if selected_worker_label else None
    if not selected_worker:
        st.caption("Selecciona un trabajador para ver su salario esperado.")
        return

    attendance_rows = api.get_asistencias_trabajador(selected_worker["id_trabajador"])
    attendance_months = sorted({
        _parse_date(row.get("fecha")).replace(day=1)
        for row in attendance_rows
        if _parse_date(row.get("fecha"))
    })
    if not attendance_months:
        attendance_months = [date.today().replace(day=1)]

    col_worker, col_month = st.columns([1.6, 1])
    col_worker.markdown(_worker_card(selected_worker), unsafe_allow_html=True)

    month_key = f"salary_month_{selected_worker['dni']}"
    if month_key not in st.session_state or st.session_state[month_key] not in attendance_months:
        st.session_state[month_key] = attendance_months[-1]

    selected_month = col_month.selectbox(
        "Mes",
        options=attendance_months,
        format_func=lambda value: value.strftime("%B %Y"),
        key=month_key,
    )

    summary = _build_salary_summary(api, selected_worker, selected_month)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Sueldo base", f"S/ {summary['base_salary']:,.2f}")
    metric_cols[1].metric("Faltas", summary["absences"])
    metric_cols[2].metric("Tardanzas", summary["tardies"])
    metric_cols[3].metric("Total estimado", f"S/ {summary['net_salary']:,.2f}")

    st.caption(
        f"Mes evaluado: `{selected_month.strftime('%B %Y')}` · "
        f"{summary['expected_days']} dias programados · "
        f"dia base `S/ {summary['daily_rate']:,.2f}` · "
        f"hora referencial `S/ {summary['hour_rate']:,.2f}`"
    )

    detail_cols = st.columns(3)
    detail_cols[0].metric("Descuento por faltas", f"S/ {summary['absence_deduction']:,.2f}")
    detail_cols[1].metric("Descuento por tardanzas", f"S/ {summary['tardy_deduction']:,.2f}")
    detail_cols[2].metric("Descuentos totales", f"S/ {summary['total_deductions']:,.2f}")

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="font-family:'Space Mono',monospace;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;margin-bottom:0.5rem;">
                Formula de calculo
            </div>
            <div style="line-height:1.7;color:#0f172a;">
                Sueldo base - faltas - tardanzas = total estimado<br>
                <code>S/ {summary['base_salary']:,.2f}</code> - <code>S/ {summary['absence_deduction']:,.2f}</code> - <code>S/ {summary['tardy_deduction']:,.2f}</code> = <code>S/ {summary['net_salary']:,.2f}</code>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Ver detalle de calculo", expanded=False):
        st.dataframe(summary["breakdown"], use_container_width=True, hide_index=True)
