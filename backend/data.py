from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from math import ceil
from zoneinfo import ZoneInfo

from supabase_backend import fetch_row_sets, fetch_rows


LIMA_TZ = ZoneInfo("America/Lima")
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
WEEK_DAYS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado")
WEEKDAY_NAMES = WEEK_DAYS + ("domingo",)


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {
        "1",
        "true",
        "t",
        "yes",
        "y",
        "si",
        "sí",
    }


def parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def format_time(value) -> str:
    if value in (None, "", False):
        return ""
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(LIMA_TZ)
        return value.strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    text = str(value).strip()
    if "T" in text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo:
                parsed = parsed.astimezone(LIMA_TZ)
            return parsed.strftime("%H:%M")
        except ValueError:
            text = text.split("T")[-1]
    if " " in text:
        text = text.split(" ")[-1]
    return text[:5]


def time_minutes(value) -> int | None:
    text = format_time(value)
    if not text:
        return None
    try:
        parsed = datetime.strptime(text[:5], "%H:%M")
        return parsed.hour * 60 + parsed.minute
    except ValueError:
        return None


def serialize_store(row: dict) -> dict:
    return {
        "id_tienda": str(row.get("id_tienda") or ""),
        "correo": row.get("correo") or "",
        "tiene_contrasena": bool(row.get("contrasena")),
        "nombre_tienda": row.get("nombre") or "",
        "direccion": row.get("direccion") or "",
        "telefono": row.get("telefono") or "",
        "fecha_apertura": str(row.get("fecha_apertura") or "")[:10],
        "estado": as_bool(row.get("estado", True)),
    }


def serialize_worker(row: dict, stores: dict, schedules: dict) -> dict:
    dni = str(row.get("dni") or "")
    store = stores.get(str(row.get("id_tienda") or ""), {})
    schedule = schedules.get(dni, {})
    return {
        "dni": dni,
        "id_trabajador": dni,
        "id_sede": str(row.get("id_tienda") or ""),
        "nombre_sede": store.get("nombre_tienda", ""),
        "nombre_trabajador": row.get("nombre") or "",
        "correo": row.get("correo") or "",
        "tiene_contrasena": bool(row.get("contrasena")),
        "area": row.get("cargo") or "",
        "sueldo": float(row.get("sueldo") or 0),
        "csi": row.get("csi") or "",
        "telefono": row.get("telefono") or "",
        "foto_dni": row.get("foto_dni") or "",
        "dias_horario": list(schedule.keys()),
        "horario": schedule,
        "estado": as_bool(row.get("estado", True)),
    }


def serialize_schedule(row: dict, workers: dict, stores: dict) -> dict:
    dni = str(row.get("dni_trabajador") or "")
    worker = workers.get(dni, {})
    store = stores.get(str(worker.get("id_sede") or ""), {})
    return {
        "dni_trabajador": dni,
        "nombre_trabajador": worker.get("nombre_trabajador", ""),
        "id_tienda": worker.get("id_sede", ""),
        "nombre_tienda": store.get("nombre_tienda", ""),
        "dia_semana": row.get("dia_semana") or "",
        "horario_entrada": format_time(row.get("horario_entrada")),
        "horario_inicio_receso": format_time(row.get("horario_inicio_receso")),
        "horario_fin_receso": format_time(row.get("horario_fin_receso")),
        "horario_salida": format_time(row.get("horario_salida")),
    }


def serialize_attendance(row: dict) -> dict:
    fecha = str(row.get("fecha") or "")[:10]
    return {
        "id_asistencia": str(
            row.get("id_asistencia") or row.get("doc_id") or ""
        ),
        "fecha": fecha,
        "id_tienda": str(row.get("id_tienda") or ""),
        "nombre_tienda": row.get("nombre_tienda") or "",
        "dni": str(row.get("dni_trabajador") or row.get("dni") or ""),
        "nombre_trabajador": row.get("nombre_trabajador") or "",
        "cargo": row.get("cargo") or "",
        "hora_inicio": format_time(row.get("horario_entrada")),
        "inicio_receso": format_time(row.get("horario_inicio_receso")),
        "final_receso": format_time(row.get("horario_fin_receso")),
        "hora_final": format_time(row.get("horario_salida")),
        "justificado": as_bool(row.get("justificado")),
    }


def load_dashboard(include_attendances: bool = True) -> dict:
    requests = {
            "stores": {
                "table_name": "tienda",
                "order_by": ("nombre", False),
            },
            "workers": {
                "table_name": "trabajador",
                "order_by": ("nombre", False),
            },
            "schedules": {
                "table_name": "horario_trabajador",
                "order_by": (
                    ("dni_trabajador", False),
                    ("dia_semana", False),
                ),
            },
        }
    if include_attendances:
        requests["attendances"] = {
                "table_name": "v_asistencia_resumen",
                "order_by": (("fecha", True), ("id_asistencia", True)),
        }
    rows = fetch_row_sets(requests)
    stores = [serialize_store(row) for row in rows["stores"]]
    stores_by_id = {row["id_tienda"]: row for row in stores}
    schedule_map: dict[str, dict] = {}
    for row in rows["schedules"]:
        dni = str(row.get("dni_trabajador") or "")
        schedule_map.setdefault(dni, {})[str(row.get("dia_semana") or "")] = {
            "horario_entrada": format_time(row.get("horario_entrada")),
            "horario_inicio_receso": format_time(
                row.get("horario_inicio_receso")
            ),
            "horario_fin_receso": format_time(row.get("horario_fin_receso")),
            "horario_salida": format_time(row.get("horario_salida")),
        }
    workers = [
        serialize_worker(row, stores_by_id, schedule_map) for row in rows["workers"]
    ]
    workers_by_dni = {row["dni"]: row for row in workers}
    schedules = [
        serialize_schedule(row, workers_by_dni, stores_by_id)
        for row in rows["schedules"]
    ]
    attendances = [
        serialize_attendance(row) for row in rows.get("attendances", [])
    ]
    for attendance in attendances:
        worker = workers_by_dni.get(attendance["dni"], {})
        if worker:
            attendance["nombre_trabajador"] = worker.get(
                "nombre_trabajador", attendance["nombre_trabajador"]
            )
            attendance["id_tienda"] = worker.get(
                "id_sede", attendance["id_tienda"]
            )
            attendance["nombre_tienda"] = worker.get(
                "nombre_sede", attendance["nombre_tienda"]
            )
    return {
        "stores": stores,
        "workers": workers,
        "schedules": schedules,
        "attendances": attendances,
    }


def build_schedule_map(schedules: list[dict]) -> dict:
    result: dict[str, dict] = {}
    for row in schedules:
        result.setdefault(str(row.get("dni_trabajador") or ""), {})[
            str(row.get("dia_semana") or "")
        ] = row
    return result


def attendance_period(
    dashboard: dict,
    start: date,
    end: date,
    store_id: str = "",
    worker_dni: str = "",
    query: str = "",
) -> dict:
    query = str(query or "").strip().lower()
    workers = dashboard["workers"]
    if store_id:
        workers = [
            item
            for item in workers
            if str(item.get("id_sede")) == str(store_id)
        ]
    if worker_dni:
        workers = [
            item
            for item in workers
            if str(item.get("dni")) == str(worker_dni)
        ]
    if query:
        workers = [
            item
            for item in workers
            if query
            in (
                f"{item.get('nombre_trabajador', '')} "
                f"{item.get('dni', '')} {item.get('nombre_sede', '')}"
            ).lower()
        ]

    worker_map = {str(item["dni"]): item for item in workers}
    schedules = build_schedule_map(dashboard["schedules"])
    rows = []
    for raw in dashboard["attendances"]:
        current = parse_date(raw.get("fecha"))
        dni = str(raw.get("dni") or "")
        if not current or not start <= current <= end or dni not in worker_map:
            continue
        day_name = WEEKDAY_NAMES[current.weekday()]
        schedule = schedules.get(dni, {}).get(day_name)
        if not schedule and not as_bool(raw.get("justificado")):
            continue
        row = dict(raw)
        worker = worker_map[dni]
        row["nombre_trabajador"] = worker["nombre_trabajador"]
        row["nombre_tienda"] = worker["nombre_sede"]
        row["cargo"] = worker["area"]
        expected = time_minutes(schedule.get("horario_entrada")) if schedule else None
        actual = time_minutes(row.get("hora_inicio"))
        row["late"] = (
            expected is not None and actual is not None and actual > expected
        )
        row["fuera_horario"] = schedule is None
        row["justificable"] = (
            schedule is None
            and not row["justificado"]
            and bool(row.get("hora_inicio") or row.get("hora_final"))
        )
        rows.append(row)

    rows.sort(key=lambda item: (item["fecha"], item["nombre_trabajador"]))
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "workers": workers,
        "rows": rows,
        "metrics": {
            "workers": len(workers),
            "records": len(rows),
            "on_time": sum(1 for row in rows if not row["late"]),
            "late": sum(1 for row in rows if row["late"]),
            "pending_justifications": sum(
                1 for row in rows if row["justificable"]
            ),
        },
    }


def month_bounds(reference: date) -> tuple[date, date, str]:
    start = reference.replace(day=1)
    end = reference.replace(day=monthrange(reference.year, reference.month)[1])
    return start, end, f"{MONTH_NAMES[start.month - 1]} {start.year}"


def fortnight_bounds(reference: date) -> tuple[date, date, str]:
    start = reference.replace(day=1 if reference.day <= 15 else 16)
    end = reference.replace(
        day=15
        if reference.day <= 15
        else monthrange(reference.year, reference.month)[1]
    )
    suffix = "Quincena 1" if reference.day <= 15 else "Quincena 2"
    return start, end, f"{MONTH_NAMES[start.month - 1]} {start.year} · {suffix}"


def week_bounds(reference: date) -> tuple[date, date, str]:
    start = reference - timedelta(days=reference.weekday())
    end = start + timedelta(days=6)
    label = (
        f"Semana {start.strftime('%d/%m/%Y')} "
        f"— {end.strftime('%d/%m/%Y')}"
    )
    return start, end, label


def scheduled_day_hours(schedule: dict) -> float:
    entry = time_minutes(schedule.get("horario_entrada"))
    exit_time = time_minutes(schedule.get("horario_salida"))
    if entry is None or exit_time is None or exit_time <= entry:
        return 8.0
    total = exit_time - entry
    break_start = time_minutes(schedule.get("horario_inicio_receso"))
    break_end = time_minutes(schedule.get("horario_fin_receso"))
    if (
        break_start is not None
        and break_end is not None
        and break_end > break_start
    ):
        total -= break_end - break_start
    return max(total / 60, 1.0)


def real_hours(attendance: dict) -> float | None:
    entry = time_minutes(attendance.get("hora_inicio"))
    exit_time = time_minutes(attendance.get("hora_final"))
    if entry is None or exit_time is None or exit_time <= entry:
        return None
    total = exit_time - entry
    break_start = time_minutes(attendance.get("inicio_receso"))
    break_end = time_minutes(attendance.get("final_receso"))
    if (
        break_start is not None
        and break_end is not None
        and break_end > break_start
    ):
        total -= break_end - break_start
    return max(total / 60, 0)


def rounded_extra_hours(attendance: dict) -> float:
    entry = time_minutes(attendance.get("hora_inicio"))
    exit_time = time_minutes(attendance.get("hora_final"))
    if entry is None or exit_time is None:
        return 0
    hours = max((exit_time // 60) - int(ceil(entry / 60)), 0)
    if attendance.get("inicio_receso") and attendance.get("final_receso"):
        hours = max(hours - 1, 0)
    return float(hours)


def salary_summary(
    dashboard: dict,
    worker_dni: str,
    month_start: date,
    reference_days: int = 26,
    hours_per_day: float = 8,
    tolerance_minutes: int = 0,
    penalty_mode: str = "hour",
    fixed_penalty: float = 0,
) -> dict:
    worker = next(
        (
            item
            for item in dashboard["workers"]
            if str(item.get("dni")) == str(worker_dni)
        ),
        None,
    )
    if not worker:
        raise ValueError("Trabajador no encontrado.")
    schedule_map = build_schedule_map(dashboard["schedules"]).get(
        str(worker_dni), {}
    )
    attendance_map = {}
    for row in dashboard["attendances"]:
        current = parse_date(row.get("fecha"))
        if (
            str(row.get("dni")) == str(worker_dni)
            and current
            and current.year == month_start.year
            and current.month == month_start.month
        ):
            attendance_map[current] = row

    scheduled_days = worker.get("dias_horario") or list(schedule_map)
    base_salary = float(worker.get("sueldo") or 0)
    reference_days = max(int(reference_days or 26), 1)
    hours_per_day = max(float(hours_per_day or 8), 1)
    daily_rate = base_salary / reference_days
    hour_rate = daily_rate / hours_per_day
    penalty_amount = hour_rate if penalty_mode == "hour" else float(
        fixed_penalty or 0
    )

    breakdown = []
    absences = tardies = extra_days = scheduled_month_days = 0
    absence_deduction = tardy_deduction = extra_earnings = 0.0
    scheduled_earnings = 0.0
    for day_number in range(
        1, monthrange(month_start.year, month_start.month)[1] + 1
    ):
        current = date(month_start.year, month_start.month, day_number)
        day_name = WEEKDAY_NAMES[current.weekday()]
        schedule = schedule_map.get(day_name, {})
        has_schedule = day_name in scheduled_days and bool(schedule)
        attendance = attendance_map.get(current)
        if has_schedule:
            scheduled_month_days += 1
        if not attendance:
            if has_schedule:
                absences += 1
                absence_deduction += daily_rate
                breakdown.append(
                    {
                        "fecha": current.isoformat(),
                        "tipo": "Falta",
                        "entrada_programada": schedule.get(
                            "horario_entrada", "-"
                        ),
                        "salida_programada": schedule.get(
                            "horario_salida", "-"
                        ),
                        "entrada_real": "-",
                        "salida_real": "-",
                        "horas_reales": 0,
                        "pago": 0,
                        "descuento": round(daily_rate, 2),
                        "bonificacion": 0,
                    }
                )
            continue

        if has_schedule:
            scheduled_hours = scheduled_day_hours(schedule)
            day_pay = scheduled_hours * hour_rate
            scheduled_earnings += day_pay
            expected = time_minutes(schedule.get("horario_entrada"))
            actual = time_minutes(attendance.get("hora_inicio"))
            late = (
                expected is not None
                and actual is not None
                and actual > expected + int(tolerance_minutes or 0)
            )
            discount = penalty_amount if late else 0
            if late:
                tardies += 1
                tardy_deduction += discount
            breakdown.append(
                {
                    "fecha": current.isoformat(),
                    "tipo": "Tardanza" if late else "Asistencia",
                    "entrada_programada": schedule.get(
                        "horario_entrada", "-"
                    ),
                    "salida_programada": schedule.get(
                        "horario_salida", "-"
                    ),
                    "entrada_real": attendance.get("hora_inicio") or "-",
                    "salida_real": attendance.get("hora_final") or "-",
                    "horas_reales": round(real_hours(attendance) or 0, 2),
                    "pago": round(day_pay, 2),
                    "descuento": round(discount, 2),
                    "bonificacion": 0,
                }
            )
        elif as_bool(attendance.get("justificado")):
            extra_hours = rounded_extra_hours(attendance)
            bonus = extra_hours * hour_rate
            if extra_hours:
                extra_days += 1
                extra_earnings += bonus
            breakdown.append(
                {
                    "fecha": current.isoformat(),
                    "tipo": "Extra" if extra_hours else "Asistencia",
                    "entrada_programada": "-",
                    "salida_programada": "-",
                    "entrada_real": attendance.get("hora_inicio") or "-",
                    "salida_real": attendance.get("hora_final") or "-",
                    "horas_reales": round(real_hours(attendance) or 0, 2),
                    "pago": round(bonus, 2),
                    "descuento": 0,
                    "bonificacion": round(bonus, 2),
                }
            )

    net_salary = max(
        scheduled_earnings - tardy_deduction + extra_earnings, 0
    )
    return {
        "worker": worker,
        "month": month_start.isoformat(),
        "base_salary": base_salary,
        "reference_days": reference_days,
        "hours_per_day": hours_per_day,
        "scheduled_month_days": scheduled_month_days,
        "present_days": scheduled_month_days - absences + extra_days,
        "absences": absences,
        "tardies": tardies,
        "scheduled_earnings": round(scheduled_earnings, 2),
        "daily_rate": round(daily_rate, 2),
        "hour_rate": round(hour_rate, 2),
        "absence_deduction": round(absence_deduction, 2),
        "tardy_deduction": round(tardy_deduction, 2),
        "extra_days": extra_days,
        "extra_earnings": round(extra_earnings, 2),
        "net_salary": round(net_salary, 2),
        "penalty_amount": round(penalty_amount, 2),
        "breakdown": breakdown,
    }


def load_worker_attendances(dni: str) -> list[dict]:
    return [
        serialize_attendance(row)
        for row in fetch_rows(
            "asistencia",
            filters=[("dni_trabajador", "eq", dni)],
            order_by=(("fecha", True), ("id_asistencia", True)),
        )
    ]
