from calendar import monthrange
from datetime import date, datetime, time
from math import ceil

import streamlit as st

MONTH_NAMES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


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


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "si", "sí"}


def _minutes_to_rounded_hours(minutes):
    if minutes is None or minutes <= 0:
        return 0
    return int(ceil(minutes / 60))


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


def _attendance_work_minutes(attendance):
    entry = _time_to_minutes(attendance.get("hora_inicio"))
    exit_time = _time_to_minutes(attendance.get("hora_final"))
    if entry is None or exit_time is None:
        return None

    total_minutes = exit_time - entry
    if total_minutes <= 0:
        return None

    break_start = _time_to_minutes(attendance.get("inicio_receso"))
    break_end = _time_to_minutes(attendance.get("final_receso"))
    if break_start is not None and break_end is not None and break_end > break_start:
        total_minutes -= break_end - break_start

    return max(total_minutes, 0)


def _hours_from_minutes(minutes):
    if minutes is None:
        return 0.0
    return max(minutes / 60.0, 0.0)


def _round_up_hour(minutes):
    if minutes is None:
        return None
    return int((minutes + 59) // 60)


def _round_down_hour(minutes):
    if minutes is None:
        return None
    return int(minutes // 60)


def _attendance_real_hours(attendance):
    entry = _time_to_minutes(attendance.get("hora_inicio"))
    exit_time = _time_to_minutes(attendance.get("hora_final"))
    if entry is None or exit_time is None:
        return None

    total_minutes = max(exit_time - entry, 0)
    break_start = _time_to_minutes(attendance.get("inicio_receso"))
    break_end = _time_to_minutes(attendance.get("final_receso"))
    if break_start is not None and break_end is not None and break_end > break_start:
        total_minutes -= break_end - break_start

    return max(total_minutes / 60.0, 0.0)


def _attendance_rounded_hours(attendance):
    entry_minutes = _time_to_minutes(attendance.get("hora_inicio"))
    exit_minutes = _time_to_minutes(attendance.get("hora_final"))
    if entry_minutes is None or exit_minutes is None:
        return 0.0

    rounded_entry = _round_up_hour(entry_minutes)
    rounded_exit = _round_down_hour(exit_minutes)
    hours = max(rounded_exit - rounded_entry, 0)

    break_start = attendance.get("inicio_receso")
    break_end = attendance.get("final_receso")
    if break_start not in (None, "", "-") and break_end not in (None, "", "-"):
        hours = max(hours - 1, 0)

    return float(hours)


def _month_days(month_start):
    total_days = monthrange(month_start.year, month_start.month)[1]
    return [date(month_start.year, month_start.month, day) for day in range(1, total_days + 1)]


def _month_label(month_value):
    return f"{MONTH_NAMES[month_value.month - 1]} {month_value.year}"


def _build_salary_summary(api, worker, month_start, reference_days=26, hours_per_day=8, tolerance_minutes=0, penalty_mode="1 hora de trabajo", fixed_penalty_amount=0.0):
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

    base_salary = float(worker.get("sueldo") or 0)
    reference_days = max(int(reference_days or 26), 1)
    daily_rate = base_salary / reference_days if reference_days else 0.0

    scheduled_day_hours_list = [
        _scheduled_day_hours(schedule_rows.get(day_name, {}))
        for day_name in scheduled_days
        if schedule_rows.get(day_name, {})
    ]
    average_day_hours = (
        sum(scheduled_day_hours_list) / len(scheduled_day_hours_list)
        if scheduled_day_hours_list
        else 8.0
    )
    hours_per_day = max(float(hours_per_day or 8), 1.0)
    hour_rate = (base_salary / reference_days / hours_per_day) if base_salary else 0.0
    penalty_amount = hour_rate if penalty_mode == "1 hora de trabajo" else float(fixed_penalty_amount or 0.0)

    breakdown = []
    absences = 0
    tardies = 0
    absence_deduction = 0.0
    tardy_deduction = 0.0
    extra_days = 0
    extra_earnings = 0.0
    scheduled_earnings = 0.0
    scheduled_month_days = 0

    for current_day in _month_days(month_start):
        day_name = _weekday_name(current_day)
        attendance = monthly_attendance.get(current_day)
        schedule_row = schedule_rows.get(day_name, {})
        has_schedule = day_name in scheduled_days and bool(schedule_row)
        scheduled_entry = _time_to_minutes(schedule_row.get("horario_entrada"))
        tolerance_limit = (
            scheduled_entry + int(tolerance_minutes or 0)
            if scheduled_entry is not None
            else None
        )

        if has_schedule:
            scheduled_month_days += 1

        if not attendance:
            if has_schedule:
                absences += 1
                deduction = daily_rate
                absence_deduction += deduction
                breakdown.append({
                    "Fecha": current_day.isoformat(),
                    "Tipo": "Falta",
                    "Entrada programada": schedule_row.get("horario_entrada", "-"),
                    "Salida programada": schedule_row.get("horario_salida", "-"),
                    "Entrada real": "-",
                    "Salida real": "-",
                    "Receso": f"{schedule_row.get('horario_inicio_receso', '-')} - {schedule_row.get('horario_fin_receso', '-')}",
                    "Horas reales": 0.0,
                    "Horas programadas": round(_scheduled_day_hours(schedule_row), 2),
                    "Pago del dia": 0.0,
                    "Horas redondeadas": "-",
                    "Descuento": round(deduction, 2),
                    "Bonificacion": 0.0,
                })
            continue

        actual_entry = _time_to_minutes(attendance.get("hora_inicio"))
        if has_schedule and scheduled_entry is not None and actual_entry is not None:
            is_late = actual_entry > tolerance_limit
            scheduled_hours = _scheduled_day_hours(schedule_row)
            real_hours = _attendance_real_hours(attendance)
            day_pay = scheduled_hours * hour_rate if scheduled_hours else 0.0
            scheduled_earnings += day_pay
            deduction = 0.0
            if is_late:
                tardies += 1
                deduction = penalty_amount
                tardy_deduction += deduction

            breakdown.append({
                "Fecha": current_day.isoformat(),
                "Tipo": "Tardanza" if is_late else "Asistencia",
                "Entrada programada": schedule_row.get("horario_entrada", "-"),
                "Salida programada": schedule_row.get("horario_salida", "-"),
                "Entrada real": attendance.get("hora_inicio", "-"),
                "Salida real": attendance.get("hora_final", "-"),
                "Receso": f"{schedule_row.get('horario_inicio_receso', '-')} - {schedule_row.get('horario_fin_receso', '-')}",
                "Horas reales": round(real_hours if real_hours is not None else 0.0, 2),
                "Horas programadas": round(scheduled_hours, 2),
                "Pago del dia": round(day_pay, 2),
                "Horas redondeadas": "-",
                "Descuento": round(deduction, 2),
                "Bonificacion": 0.0,
            })
            continue

        if has_schedule:
            scheduled_hours = _scheduled_day_hours(schedule_row)
            breakdown.append({
                "Fecha": current_day.isoformat(),
                "Tipo": "Asistencia",
                "Entrada programada": schedule_row.get("horario_entrada", "-"),
                "Salida programada": schedule_row.get("horario_salida", "-"),
                "Entrada real": attendance.get("hora_inicio", "-"),
                "Salida real": attendance.get("hora_final", "-"),
                "Receso": f"{schedule_row.get('horario_inicio_receso', '-')} - {schedule_row.get('horario_fin_receso', '-')}",
                "Horas reales": 0.0,
                "Horas programadas": round(scheduled_hours, 2),
                "Pago del dia": 0.0,
                "Horas redondeadas": "-",
                "Descuento": 0.0,
                "Bonificacion": 0.0,
            })
            continue

        if not _as_bool(attendance.get("justificado")):
            continue

        real_hours = _attendance_real_hours(attendance)
        rounded_hours = _attendance_rounded_hours(attendance)
        bonus = rounded_hours * hour_rate if rounded_hours else 0.0
        if rounded_hours:
            extra_days += 1
            extra_earnings += bonus

        breakdown.append({
            "Fecha": current_day.isoformat(),
            "Tipo": "Extra" if rounded_hours else "Asistencia",
            "Entrada programada": "-",
            "Salida programada": "-",
            "Entrada real": attendance.get("hora_inicio", "-"),
            "Salida real": attendance.get("hora_final", "-"),
            "Receso": f"{attendance.get('inicio_receso', '-')} - {attendance.get('final_receso', '-')}",
            "Horas reales": round(real_hours if real_hours is not None else 0.0, 2),
            "Horas programadas": "-",
            "Pago del dia": round(bonus, 2),
            "Horas redondeadas": rounded_hours if rounded_hours else "-",
            "Descuento": 0.0,
            "Bonificacion": round(bonus, 2),
        })

    attended_scheduled_days = scheduled_month_days - absences
    net_salary = max(scheduled_earnings - tardy_deduction + extra_earnings, 0.0)

    return {
        "month_start": month_start,
        "base_salary": base_salary,
        "reference_days": reference_days,
        "hours_per_day": hours_per_day,
        "scheduled_days": scheduled_days,
        "scheduled_month_days": scheduled_month_days,
        "present_days": attended_scheduled_days + extra_days,
        "attended_scheduled_days": attended_scheduled_days,
        "absences": absences,
        "tardies": tardies,
        "scheduled_earnings": scheduled_earnings,
        "daily_rate": daily_rate,
        "hour_rate": hour_rate,
        "average_day_hours": average_day_hours,
        "absence_deduction": absence_deduction,
        "tardy_deduction": tardy_deduction,
        "extra_days": extra_days,
        "extra_earnings": extra_earnings,
        "net_salary": net_salary,
        "breakdown": breakdown,
        "tolerance_minutes": int(tolerance_minutes or 0),
        "penalty_mode": penalty_mode,
        "penalty_amount": penalty_amount,
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
        div[data-testid="stMetric"] {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            background: #ffffff;
            padding: 0.85rem 0.95rem;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetric"] label {
            font-size: 0.68rem !important;
            white-space: normal !important;
            line-height: 1.2 !important;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: 1.15rem !important;
            line-height: 1.15 !important;
            white-space: nowrap !important;
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
        format_func=_month_label,
        key=month_key,
    )

    control_cols = st.columns([0.85, 0.9, 1.1, 1.0])
    reference_days = control_cols[0].number_input(
        "Dias para calculo",
        min_value=1,
        max_value=31,
        step=1,
        value=26,
        key=f"salary_reference_days_{selected_worker['dni']}",
    )
    hours_per_day = control_cols[1].number_input(
        "Horas por dia",
        min_value=1.0,
        max_value=24.0,
        step=0.5,
        value=8.0,
        format="%.1f",
        key=f"salary_hours_per_day_{selected_worker['dni']}",
    )
    tolerance_minutes = control_cols[2].selectbox(
        "Tolerancia",
        options=[0, 5, 10, 15, 20, 30],
        index=2,
        format_func=lambda value: f"{value} min",
        key=f"salary_tolerance_{selected_worker['dni']}",
    )
    penalty_mode = control_cols[3].selectbox(
        "Penalizacion",
        options=["1 hora de trabajo", "Monto fijo"],
        index=0,
        key=f"salary_penalty_mode_{selected_worker['dni']}",
    )
    fixed_penalty_amount = 0.0
    if penalty_mode == "Monto fijo":
        fixed_penalty_amount = st.number_input(
            "Monto por tardanza",
            min_value=0.0,
            step=5.0,
            format="%.2f",
            value=0.0,
            key=f"salary_penalty_amount_{selected_worker['dni']}",
        )
    else:
        st.caption("Se descuenta 1 hora segun el valor calculado.")

    summary = _build_salary_summary(
        api,
        selected_worker,
        selected_month,
        reference_days=reference_days,
        hours_per_day=hours_per_day,
        tolerance_minutes=tolerance_minutes,
        penalty_mode=penalty_mode,
        fixed_penalty_amount=fixed_penalty_amount,
    )

    metric_row_1 = st.columns(3)
    metric_row_1[0].metric("Sueldo base", f"S/ {summary['base_salary']:,.2f}")
    metric_row_1[1].metric("Sueldo por dia", f"S/ {summary['daily_rate']:,.2f}")
    metric_row_1[2].metric("Sueldo por hora", f"S/ {summary['hour_rate']:,.2f}")

    st.caption(
        f"Mes evaluado: `{_month_label(selected_month)}` · "
        f"{summary['reference_days']} dias de referencia · "
        f"{summary['hours_per_day']} horas por dia · "
        f"{summary['scheduled_month_days']} dias programados · "
        f"{summary['average_day_hours']:,.2f} horas por dia · "
        f"tolerancia `{summary['tolerance_minutes']} min` · "
        f"penalizacion `{summary['penalty_mode']}`"
    )

    detail_cols = st.columns(4)
    detail_cols[0].metric("Total estimado actual", f"S/ {summary['net_salary']:,.2f}")
    detail_cols[1].metric("Dias programados", summary["scheduled_month_days"])
    detail_cols[2].metric("Dias de falta", summary["absences"])
    detail_cols[3].metric("Dias extra", summary["extra_days"])

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="font-family:'Space Mono',monospace;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;margin-bottom:0.5rem;">
                Formula de calculo
            </div>
            <div style="line-height:1.7;color:#0f172a;">
                Total estimado actual = suma de pagos por dia segun horas programadas - tardanzas + extras<br>
                <code>S/ {summary['scheduled_earnings']:,.2f}</code> - <code>S/ {summary['tardy_deduction']:,.2f}</code> + <code>S/ {summary['extra_earnings']:,.2f}</code> = <code>S/ {summary['net_salary']:,.2f}</code>
            </div>
            <div style="margin-top:0.35rem;color:#64748b;font-size:0.75rem;">
                Sueldo por hora = sueldo base / dias de calculo / horas por dia
                <br>
                Pago del dia = horas programadas del turno x sueldo por hora; si no hay horario, horas redondeadas de la asistencia x sueldo por hora
            </div>
            """,
            unsafe_allow_html=True,
        )

    if summary.get("scheduled_days"):
        scheduled_days_text = ", ".join(day.capitalize() for day in summary["scheduled_days"])
        st.caption(f"Dias de horario considerados: {scheduled_days_text}")

    with st.expander("Ver detalle de calculo", expanded=False):
        st.dataframe(summary["breakdown"], use_container_width=True, hide_index=True)
