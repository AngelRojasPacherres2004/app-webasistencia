from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from psycopg2 import sql

from config.db import get_pooled_connection


LIMA_TZ = ZoneInfo("America/Lima")


def replace_worker_schedule(dni: str, schedules: list[dict]) -> None:
    with get_pooled_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM horario_trabajador WHERE dni_trabajador = %s",
                [dni],
            )
            for item in schedules:
                cursor.execute(
                    """
                    INSERT INTO horario_trabajador
                        (dni_trabajador, dia_semana, horario_entrada,
                         horario_inicio_receso, horario_fin_receso, horario_salida)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        dni,
                        item["dia_semana"],
                        item.get("horario_entrada") or "00:00",
                        item.get("horario_inicio_receso") or "00:00",
                        item.get("horario_fin_receso") or "00:00",
                        item.get("horario_salida") or "00:00",
                    ],
                )
        connection.commit()


def list_email_configs() -> list[dict]:
    with get_pooled_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM public.alerta_puntualidad_config
                ORDER BY tipo_reporte, hora_envio
                """
            )
            return cursor.fetchall() or []


def save_email_config(payload: dict, config_id: str | None = None) -> str:
    config_id = config_id or str(uuid.uuid4())
    store_id = payload.get("id_tienda") or None
    report_type = "TIENDA" if store_id else "GENERAL"
    send_time = str(payload.get("hora_envio") or "").strip()
    if len(send_time) == 5:
        send_time += ":00"
    values = [
        store_id,
        str(payload.get("correo_destino") or "").strip(),
        int(payload.get("minutos_tolerancia") or 0),
        report_type,
        str(payload.get("nombre_reporte") or "Reporte mañana"),
        send_time,
        int(payload.get("ventana_minutos") or 5),
    ]
    with get_pooled_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.alerta_puntualidad_config
                    (id_config, id_tienda, correo_destino, minutos_tolerancia,
                     activo, tipo_reporte, nombre_reporte, hora_envio,
                     ventana_minutos)
                VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s)
                ON CONFLICT (id_config) DO UPDATE SET
                    id_tienda = EXCLUDED.id_tienda,
                    correo_destino = EXCLUDED.correo_destino,
                    minutos_tolerancia = EXCLUDED.minutos_tolerancia,
                    tipo_reporte = EXCLUDED.tipo_reporte,
                    nombre_reporte = EXCLUDED.nombre_reporte,
                    hora_envio = EXCLUDED.hora_envio,
                    ventana_minutos = EXCLUDED.ventana_minutos
                """,
                [config_id] + values,
            )
        connection.commit()
    return config_id


def delete_email_config(config_id: str) -> None:
    with get_pooled_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM public.alerta_puntualidad_config WHERE id_config = %s",
                [config_id],
            )
        connection.commit()


def list_marks(
    start: date,
    end: date,
    store_id: str = "",
    worker_dni: str = "",
) -> list[dict]:
    start_time = datetime.combine(start, datetime.min.time(), tzinfo=LIMA_TZ)
    end_time = datetime.combine(
        end + timedelta(days=1), datetime.min.time(), tzinfo=LIMA_TZ
    )
    query = """
        SELECT
            am.id,
            am.id_tienda,
            t.nombre AS nombre_tienda,
            t.direccion AS direccion_tienda,
            am.id_trabajador,
            tr.nombre AS nombre_trabajador,
            am.hora_marca,
            (am.hora_marca AT TIME ZONE 'America/Lima') AS hora_marca_local,
            DATE(am.hora_marca AT TIME ZONE 'America/Lima') AS fecha_local,
            am.ubicacion,
            am.tipo
        FROM public.asistencia_multiple am
        LEFT JOIN public.tienda t ON t.id_tienda::text = am.id_tienda::text
        LEFT JOIN public.trabajador tr ON tr.dni = am.id_trabajador
        WHERE am.hora_marca >= %s AND am.hora_marca < %s
    """
    params: list = [start_time, end_time]
    if store_id:
        query += " AND am.id_tienda::text = %s"
        params.append(store_id)
    if worker_dni:
        query += " AND am.id_trabajador = %s"
        params.append(worker_dni)
    query += " ORDER BY am.hora_marca DESC"
    with get_pooled_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall() or []
    result = []
    for row in rows:
        item = dict(row)
        local = item.get("hora_marca_local") or item.get("hora_marca")
        item["fecha_local"] = (
            local.strftime("%Y-%m-%d")
            if isinstance(local, datetime)
            else str(item.get("fecha_local") or "")[:10]
        )
        item["hora_local"] = (
            local.strftime("%H:%M:%S")
            if isinstance(local, datetime)
            else str(local or "")[11:19]
        )
        for key in ("hora_marca", "hora_marca_local"):
            if isinstance(item.get(key), datetime):
                item[key] = item[key].isoformat()
        result.append(item)
    return result
