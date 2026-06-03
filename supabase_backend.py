from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import bcrypt
from psycopg2 import sql

from config.db import get_connection


TABLE_KEY_FIELDS = {
    "tienda": "id_tienda",
    "trabajador": "dni",
    "qr": "id",
    "asistencia": "id_asistencia",
    "administrador": "correo",
    "horario_trabajador": "id_horario",
}


def get_supabase_client():
    return get_connection()


def server_timestamp():
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/Lima")).isoformat()


def table_key_field(table_name):
    return TABLE_KEY_FIELDS.get(table_name, "id")


def _normalize_select(select):
    if not select or select == "*":
        return sql.SQL("*")

    if isinstance(select, (list, tuple)):
        columns = list(select)
    else:
        columns = [item.strip() for item in str(select).split(",") if item.strip()]

    if not columns:
        return sql.SQL("*")

    return sql.SQL(", ").join(sql.Identifier(column) for column in columns)


def _normalize_order_by(order_by):
    if not order_by:
        return sql.SQL("")

    if (
        isinstance(order_by, tuple)
        and len(order_by) == 2
        and not isinstance(order_by[0], (list, tuple))
    ):
        ordering = (order_by,)
    else:
        ordering = order_by if isinstance(order_by, (list, tuple)) else (order_by,)
    clauses = []
    for item in ordering:
        if isinstance(item, tuple):
            field, descending = item
        else:
            field, descending = item, False
        clause = sql.SQL("{} {}").format(
            sql.Identifier(str(field)),
            sql.SQL("DESC") if descending else sql.SQL("ASC"),
        )
        clauses.append(clause)

    return sql.SQL(" ORDER BY ") + sql.SQL(", ").join(clauses)


def _build_where(filters, params):
    if not filters:
        return sql.SQL("")

    clauses = []
    for field, operator, value in filters:
        field_sql = sql.Identifier(str(field))
        if operator == "eq":
            clauses.append(sql.SQL("{} = %s").format(field_sql))
            params.append(value)
        elif operator == "ilike":
            clauses.append(sql.SQL("{} ILIKE %s").format(field_sql))
            params.append(value)
        elif operator == "in":
            clauses.append(sql.SQL("{} = ANY(%s)").format(field_sql))
            params.append(list(value))
        else:
            raise ValueError(f"Operador no soportado: {operator}")

    return sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)


def _fetch_all(query, params=None):
    params = params or []
    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall() or []


def _fetch_one(query, params=None):
    params = params or []
    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()


def _execute(query, params=None, fetch=False):
    params = params or []
    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone() if fetch else None
        connection.commit()
        return result


def fetch_rows(table_name, select="*", filters=None, order_by=None, limit=None):
    params = []
    query = sql.SQL("SELECT {select} FROM {table}").format(
        select=_normalize_select(select),
        table=sql.Identifier(table_name),
    )
    query += _build_where(filters, params)
    query += _normalize_order_by(order_by)
    if limit is not None:
        query += sql.SQL(" LIMIT %s")
        params.append(int(limit))
    return _fetch_all(query, params)


def document_exists(table_name, doc_id, key_field=None):
    # Si el ID está vacío o es nulo, no puede existir en la base de datos
    if not doc_id or not str(doc_id).strip():
        return False

    key_field = key_field or table_key_field(table_name)
    try:
        rows = fetch_rows(
            table_name,
            select=key_field,
            filters=[(key_field, "eq", doc_id)],
            limit=1,
        )
        return bool(rows)
    except Exception:
        # Si hay un error de representación (ej: se envía texto a un UUID), asumimos que no existe
        return False


def insert_document(table_name, data):
    payload = dict(data or {})
    if not payload:
        raise ValueError("No hay datos para insertar.")

    columns = list(payload.keys())
    values = list(payload.values())
    query = sql.SQL("INSERT INTO {table} ({columns}) VALUES ({values})").format(
        table=sql.Identifier(table_name),
        columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    _execute(query, values)


def upsert_document(table_name, doc_id, data, key_field=None):
    payload = dict(data or {})
    key_field = key_field or table_key_field(table_name)
    payload[key_field] = doc_id

    columns = list(payload.keys())
    values = list(payload.values())
    update_columns = [column for column in columns if column != key_field]

    if update_columns:
        conflict_action = sql.SQL("DO UPDATE SET {updates}").format(
            updates=sql.SQL(", ").join(
                sql.SQL("{column} = EXCLUDED.{column}").format(
                    column=sql.Identifier(column)
                )
                for column in update_columns
            )
        )
    else:
        conflict_action = sql.SQL("DO NOTHING")

    query = sql.SQL(
        "INSERT INTO {table} ({columns}) VALUES ({values}) "
        "ON CONFLICT ({key_field}) {conflict_action}"
    ).format(
        table=sql.Identifier(table_name),
        columns=sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        values=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        key_field=sql.Identifier(key_field),
        conflict_action=conflict_action,
    )
    _execute(query, values)


def update_document(table_name, doc_id, data, key_field=None):
    payload = dict(data or {})
    key_field = key_field or table_key_field(table_name)
    if key_field in payload:
        payload.pop(key_field)

    if not payload:
        return

    assignments = sql.SQL(", ").join(
        sql.SQL("{column} = %s").format(column=sql.Identifier(column))
        for column in payload.keys()
    )
    query = sql.SQL("UPDATE {table} SET {assignments} WHERE {key_field} = %s").format(
        table=sql.Identifier(table_name),
        assignments=assignments,
        key_field=sql.Identifier(key_field),
    )
    _execute(query, list(payload.values()) + [doc_id])


def delete_rows(table_name, filters):
    params = []
    query = sql.SQL("DELETE FROM {table}").format(table=sql.Identifier(table_name))
    query += _build_where(filters, params)
    _execute(query, params)


def delete_document(table_name, doc_id, key_field=None):
    key_field = key_field or table_key_field(table_name)
    query = sql.SQL("DELETE FROM {table} WHERE {key_field} = %s").format(
        table=sql.Identifier(table_name),
        key_field=sql.Identifier(key_field),
    )
    _execute(query, [doc_id])


def hash_password(password):
    return str(password or "")


def verify_password(stored_password, candidate_password):
    stored = str(stored_password or "")
    candidate = str(candidate_password or "")
    if not stored or not candidate:
        return False
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(candidate.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    return stored == candidate


def create_store_with_qr(store_table, qr_table, document_id, store_data):
    qr_token = uuid4().hex
    store_payload = dict(store_data or {})
    store_payload["id_tienda"] = document_id

    with closing(get_connection()) as connection:
        with connection.cursor() as cursor:
            store_columns = list(store_payload.keys())
            store_values = list(store_payload.values())
            store_query = sql.SQL(
                "INSERT INTO {table} ({columns}) VALUES ({values}) "
                "ON CONFLICT (id_tienda) DO UPDATE SET {updates}"
            ).format(
                table=sql.Identifier(store_table),
                columns=sql.SQL(", ").join(sql.Identifier(column) for column in store_columns),
                values=sql.SQL(", ").join(sql.Placeholder() for _ in store_columns),
                updates=sql.SQL(", ").join(
                    sql.SQL("{column} = EXCLUDED.{column}").format(
                        column=sql.Identifier(column)
                    )
                    for column in store_columns
                    if column != "id_tienda"
                ),
            )
            cursor.execute(store_query, store_values)

            cursor.execute(
                sql.SQL("DELETE FROM {table} WHERE id_tienda = %s").format(
                    table=sql.Identifier(qr_table)
                ),
                [document_id],
            )
            cursor.execute(
                sql.SQL(
                    "INSERT INTO {table} (id_tienda, token, fecha_creada) VALUES (%s, %s, %s)"
                ).format(table=sql.Identifier(qr_table)),
                [document_id, qr_token, server_timestamp()],
            )
        connection.commit()

    return qr_token


def list_table_rows(table_name, select="*", filters=None, order_by=None, limit=None):
    return fetch_rows(
        table_name,
        select=select,
        filters=filters,
        order_by=order_by,
        limit=limit,
    )


def list_admin_rows():
    return fetch_rows("administrador", order_by=("correo", False))


def get_admin_login_diagnostics():
    diagnostics = {
        "connected": False,
        "table": "administrador",
        "row_count": 0,
        "sample_emails": [],
        "error": "",
    }

    try:
        rows = list_admin_rows()
        diagnostics["connected"] = True
        diagnostics["row_count"] = len(rows)
        diagnostics["sample_emails"] = [
            str(row.get("correo", "")).strip()
            for row in rows[:5]
            if str(row.get("correo", "")).strip()
        ]
    except Exception as exc:
        diagnostics["error"] = str(exc)

    return diagnostics
