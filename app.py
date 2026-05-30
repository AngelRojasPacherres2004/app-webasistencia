from pathlib import Path
from uuid import uuid4
from datetime import date, datetime, time, timezone
from types import SimpleNamespace
import base64
from zoneinfo import ZoneInfo
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        import toml as _toml
        class _TomlFallback:
            @staticmethod
            def loads(content):
                return _toml.loads(content)
        tomllib = _TomlFallback()

import streamlit as st
from cloudinary_uploader import upload_worker_file
from login import is_authenticated, render_login, logout
from sections.asistencias_resumen import render_resumen
from sections.tiendas import render_tiendas
from sections.trabajadores import render_trabajadores
from supabase_backend import (
    create_store_with_qr as backend_create_store_with_qr,
    document_exists as backend_document_exists,
    delete_document,
    fetch_rows,
    hash_password,
    server_timestamp,
    update_document,
    upsert_document,
)
from config.db import get_connection


st.set_page_config(
    page_title="Admin · Asistencia",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKGROUND_IMAGE_PATH = Path("fondo.png")
background_image_b64 = ""
if BACKGROUND_IMAGE_PATH.exists():
    background_image_b64 = base64.b64encode(BACKGROUND_IMAGE_PATH.read_bytes()).decode("utf-8")

# ?? Tema visual ????????????????????????????????????????????????????????????????

def apply_global_css():
    css_path = Path("styles/global.css")
    if not css_path.exists():
        return
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


apply_global_css()



# ── Constantes ─────────────────────────────────────────────────────────────────
WORKER_COLLECTION = "trabajador"
STORE_COLLECTION = "tienda"
ATTENDANCE_COLLECTION = "asistencia"
QR_ACTIVE_COLLECTION = "qr"
MONTH_NAMES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)
WEEK_DAYS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado")
WEEKDAY_NAMES = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
SCHEDULE_FIELDS = ("hora_inicio", "inicio_receso", "final_receso", "hora_final")
HIDDEN_FIELDS = ("password", "contrasena", "contraseña")
SECRET_JSON_PATHS = (
    Path(".streamlit/secrets.toml"),
    Path(".streamlit/secret.toml"),
)


def clean_service_account(service_account):
    """Limpia y valida el diccionario de la cuenta de servicio."""
    if not service_account or not isinstance(service_account, dict):
        return service_account
    
    # Asegura que la llave privada no tenga espacios extra y procese bien los saltos de línea
    if "private_key" in service_account and isinstance(service_account["private_key"], str):
        key = service_account["private_key"]
        # Limpiar comillas accidentales y espacios (común al pegar desde JSON a Streamlit Secrets)
        key = key.strip().strip('"').strip("'").strip()
        # Convertir representaciones literales de \n en saltos de línea reales
        key = key.replace("\\n", "\n")
        # Forzar el inicio en el marcador de apertura
        if "-----BEGIN" in key:
            key = "-----BEGIN" + key.split("-----BEGIN")[-1]
        # Forzar el fin en el marcador de cierre (esto elimina el carácter 61 "=" inválido si hay basura después)
        if "-----END PRIVATE KEY-----" in key:
            key = key.split("-----END PRIVATE KEY-----")[0] + "-----END PRIVATE KEY-----"
        service_account["private_key"] = key.strip()
    
    return service_account


# ── Helpers ────────────────────────────────────────────────────────────────────
def normalize_doc_id(value):
    normalized = str(value or "").strip().lower()
    safe_value = "".join(
        character if character.isalnum() else "_" for character in normalized
    ).strip("_")
    return safe_value or uuid4().hex


def normalize_email(email):
    return str(email or "").strip().lower()


def format_time(value):
    if not value:
        return ""
    if isinstance(value, str):
        text = value.strip()
        if "T" in text:
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%H:%M")
            except ValueError:
                pass
        return text[:5] if len(text) >= 5 and text[2] == ":" else text
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    return value.strftime("%H:%M")


def parse_iso_date(value):
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def add_months(month_value, delta):
    month_index = month_value.month - 1 + delta
    year = month_value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def format_month(month_value):
    return f"{MONTH_NAMES[month_value.month - 1]} {month_value.year}"


def first_present(data, *keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def map_value(data, map_key, value_key):
    value = data.get(map_key)
    if isinstance(value, dict):
        return value.get(value_key) or ""
    return ""


def path_value_after(path_parts, collection_names):
    normalized_names = {name.lower() for name in collection_names}
    for index, part in enumerate(path_parts[:-1]):
        if part.lower() in normalized_names:
            return path_parts[index + 1]
    return ""


def build_attendance_row(doc, data=None):
    if isinstance(doc, dict) and data is None:
        data = doc
    data = data or {}
    fecha = str(data.get("fecha") or "")
    parsed_date = parse_iso_date(fecha)
    return {
        "doc_id": str(data.get("id_asistencia") or data.get("doc_id") or "").strip(),
        "ruta": str(data.get("id_asistencia") or data.get("doc_id") or "").strip(),
        "fecha": fecha,
        "fecha_orden": parsed_date.isoformat() if parsed_date else "",
        "nombre_tienda": data.get("nombre_tienda", ""),
        "id_tienda": data.get("id_tienda", ""),
        "id_trabajador": data.get("dni_trabajador", ""),
        "nombre_trabajador": data.get("nombre_trabajador", ""),
        "dni": data.get("dni_trabajador", ""),
        "hora_inicio": format_time(data.get("horario_entrada")),
        "inicio_receso": format_time(data.get("horario_inicio_receso")),
        "final_receso": format_time(data.get("horario_fin_receso")),
        "hora_final": format_time(data.get("horario_salida")),
        "ultima_marca": (
            "hora_final"
            if data.get("horario_salida")
            else "final_receso" if data.get("horario_fin_receso")
            else "inicio_receso" if data.get("horario_inicio_receso")
            else "hora_inicio" if data.get("horario_entrada")
            else ""
        ),
        "id_sede": data.get("id_tienda", ""),
        "nombre_sede": data.get("nombre_tienda", ""),
        "horario_programado": "",
    }


@st.cache_resource(show_spinner=False)
def get_database_client():
    return get_connection()


def load_service_account():
    return {}


def load_service_account_file(path):
    return {}


def required_missing(fields):
    return [label for label, value in fields.items() if not str(value or "").strip()]


def document_exists(collection_name, document_id):
    return backend_document_exists(collection_name, document_id)


def create_document(collection_name, document_id, data):
    upsert_document(collection_name, document_id, data)
    st.cache_data.clear()


def create_store_with_qr(document_id, store_data):
    qr_token = backend_create_store_with_qr(
        STORE_COLLECTION,
        QR_ACTIVE_COLLECTION,
        document_id,
        store_data,
    )
    st.cache_data.clear()
    return qr_token


# ── Queries cacheadas ──────────────────────────────────────────────────────────
@st.cache_data(ttl=10, show_spinner=False)
def get_tiendas():
    docs = fetch_rows(STORE_COLLECTION, order_by=("nombre", False))
    tiendas = []
    for data in docs:
        tiendas.append({
            "doc_id": data.get("id_tienda", ""),
            "id_tienda": data.get("id_tienda", ""),
            "correo": data.get("correo", ""),
            "tiene_contrasena": bool(data.get("contrasena")),
            "nombre_tienda": data.get("nombre", ""),
            "id_sede": data.get("id_tienda", ""),
            "nombre_sede": data.get("nombre", ""),
            "direccion": data.get("direccion", ""),
            "telefono": data.get("telefono", ""),
            "fecha_apertura": data.get("fecha_apertura", ""),
            "estado": data.get("estado", True),
        })
    return sorted(tiendas, key=lambda x: x["nombre_tienda"])


@st.cache_data(ttl=10, show_spinner=False)
def get_trabajadores():
    docs = fetch_rows(WORKER_COLLECTION, order_by=("nombre", False))
    tiendas = {row["id_tienda"]: row for row in get_tiendas()}
    horarios = fetch_rows("horario_trabajador", order_by=(("dni_trabajador", False), ("dia_semana", False)))
    schedule_map = {}
    for row in horarios:
        schedule_map.setdefault(row.get("dni_trabajador", ""), {})[row.get("dia_semana", "")] = row
    trabajadores = []
    for data in docs:
        tienda = tiendas.get(data.get("id_tienda", ""), {})
        horario = schedule_map.get(data.get("dni", ""), {})
        trabajadores.append({
            "doc_id": data.get("dni", ""),
            "id_trabajador": data.get("dni", ""),
            "correo": data.get("correo", ""),
            "tiene_contrasena": bool(data.get("contrasena")),
            "area": data.get("cargo", ""),
            "sueldo": data.get("sueldo", ""),
            "dni": data.get("dni", ""),
            "id_sede": data.get("id_tienda", ""),
            "nombre_sede": tienda.get("nombre_tienda", ""),
            "nombre_trabajador": data.get("nombre", ""),
            "cuenta_bancaria": "",
            "csi": data.get("csi", ""),
            "telefono": data.get("telefono", ""),
            "foto_dni": data.get("foto_dni", ""),
            "dias_horario": list(horario.keys()),
            "dias_horario_texto": ", ".join(horario.keys()),
            "horario": horario,
            "estado": bool(data.get("estado", True)),
        })
    return sorted(trabajadores, key=lambda x: x["nombre_trabajador"])


@st.cache_data(ttl=10, show_spinner=False)
def get_horarios_trabajador():
    horarios = fetch_rows("horario_trabajador", order_by=(("dni_trabajador", False), ("dia_semana", False)))
    trabajadores = {row["dni"]: row for row in get_trabajadores()}
    tiendas = {row["id_tienda"]: row for row in get_tiendas()}
    rows = []
    for item in horarios:
        worker = trabajadores.get(item.get("dni_trabajador", ""), {})
        tienda = tiendas.get(worker.get("id_sede", ""), {})
        rows.append({
            "dni_trabajador": item.get("dni_trabajador", ""),
            "nombre_trabajador": worker.get("nombre_trabajador", ""),
            "id_tienda": worker.get("id_sede", ""),
            "nombre_tienda": tienda.get("nombre_tienda", ""),
            "dia_semana": item.get("dia_semana", ""),
            "horario_entrada": format_time(item.get("horario_entrada")),
            "horario_inicio_receso": format_time(item.get("horario_inicio_receso")),
            "horario_fin_receso": format_time(item.get("horario_fin_receso")),
            "horario_salida": format_time(item.get("horario_salida")),
        })
    return rows


@st.cache_data(ttl=10, show_spinner=False)
def get_asistencias():
    docs = fetch_rows(ATTENDANCE_COLLECTION, order_by=(("fecha", True), ("id_asistencia", True)))
    trabajadores = {row["dni"]: row for row in get_trabajadores()}
    tiendas = {row["id_tienda"]: row for row in get_tiendas()}
    asistencias = []
    for data in docs:
        row = build_attendance_row(data, data)
        worker = trabajadores.get(row.get("dni", ""), {})
        if worker:
            row["nombre_trabajador"] = worker.get("nombre_trabajador", "")
            row["id_tienda"] = worker.get("id_sede", "")
            row["nombre_sede"] = worker.get("nombre_sede", "")
            tienda = tiendas.get(worker.get("id_sede", ""), {})
            row["nombre_tienda"] = tienda.get("nombre_tienda", row.get("nombre_sede", ""))
        asistencias.append(row)

    unique_rows = {item["ruta"]: item for item in asistencias}
    return sorted(
        unique_rows.values(),
        key=lambda item: item["fecha_orden"] or item["fecha"],
        reverse=True,
    )


@st.cache_data(ttl=10, show_spinner=False)
def get_asistencias_trabajador(id_trabajador):
    docs = fetch_rows(
        ATTENDANCE_COLLECTION,
        filters=[("dni_trabajador", "eq", id_trabajador)],
        order_by=(("fecha", True), ("id_asistencia", True)),
    )
    asistencias = [build_attendance_row(data, data) for data in docs]

    unique_rows = {item["ruta"]: item for item in asistencias}
    return sorted(unique_rows.values(), key=lambda x: x["fecha_orden"], reverse=True)


# ── Componentes UI ─────────────────────────────────────────────────────────────
def section_header(title, subtitle=None):
    """Encabezado de sección con línea decorativa."""
    st.markdown(f"""
    <div style="margin: 0.5rem 0 1.5rem; padding-left: 0.75rem;
                border-left: 3px solid var(--tertiary);">
        <div style="font-family:'Space Mono',monospace; font-size:0.78rem;
                    text-transform:uppercase; letter-spacing:0.1em; color:var(--text);
                    margin-bottom:0.2rem;">{title}</div>
        {'<div style="font-size:0.82rem; color:var(--muted); font-family:DM Sans,sans-serif;">'+subtitle+'</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def badge(text, color="var(--text)"):
    return f'<span style="background:var(--secondary);color:{color};border:1px solid var(--border);border-radius:6px;padding:2px 8px;font-family:Space Mono,monospace;font-size:0.65rem;letter-spacing:0.06em;">{text}</span>'


def _parse_time_value(value):
    if not value:
        return None
    if isinstance(value, time):
        return value
    text = str(value).strip()
    if not text:
        return None
    if " " in text:
        text = text.split(" ", 1)[1]
    if "T" in text:
        text = text.split("T", 1)[-1]
    try:
        return time.fromisoformat(text[:8])
    except ValueError:
        return None


def _time_select_options(step_minutes=15):
    options = ["Sin registro"]
    current_minutes = 0
    while current_minutes < 24 * 60:
        hour_value = current_minutes // 60
        minute_value = current_minutes % 60
        options.append(f"{hour_value:02d}:{minute_value:02d}")
        current_minutes += step_minutes
    return options


def _time_select_index(current_value, options):
    if not current_value:
        return 0
    normalized = format_time(current_value)[:5]
    try:
        return options.index(normalized)
    except ValueError:
        return 0


def build_schedule_inputs(selected_days, key_prefix="schedule", initial_schedule=None):
    if not selected_days:
        return {}

    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.68rem;
                text-transform:uppercase; letter-spacing:0.08em; color:var(--muted);
                margin: 1.25rem 0 0.75rem; padding: 0.5rem 0;
                border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);">
        ⬡ &nbsp;Horario por día
    </div>
    """, unsafe_allow_html=True)

    schedule = {}
    header = st.columns([1.2, 1, 1, 1, 1])
    for col, label in zip(header, ["Día", "Entrada", "Ini. receso", "Fin receso", "Salida"]):
        col.markdown(f'<span style="font-family:Space Mono,monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.07em;color:var(--muted);">{label}</span>', unsafe_allow_html=True)

    for day in selected_days:
        cols = st.columns([1.2, 1, 1, 1, 1])
        cols[0].markdown(f'<span style="font-family:Space Mono,monospace;font-size:0.78rem;color:var(--text);">{day.capitalize()}</span>', unsafe_allow_html=True)
        day_initial = (initial_schedule or {}).get(day, {})

        time_options = _time_select_options()
        inicio_receso_selection = cols[2].selectbox(
            "Inicio receso",
            options=time_options,
            index=_time_select_index(
                day_initial.get("horario_inicio_receso") or day_initial.get("inicio_receso"),
                time_options,
            ),
            key=f"{key_prefix}_{day}_inicio_receso",
            label_visibility="collapsed",
        )
        inicio_receso_value = None if inicio_receso_selection == "Sin registro" else inicio_receso_selection

        fin_receso_selection = cols[3].selectbox(
            "Fin receso",
            options=time_options,
            index=_time_select_index(
                day_initial.get("horario_fin_receso") or day_initial.get("final_receso"),
                time_options,
            ),
            key=f"{key_prefix}_{day}_fin_receso",
            label_visibility="collapsed",
        )
        fin_receso_value = None if fin_receso_selection == "Sin registro" else fin_receso_selection

        schedule[day] = {
            "hora_inicio":    format_time(cols[1].time_input("Hora inicio",    value=_parse_time_value(day_initial.get("horario_entrada") or day_initial.get("hora_inicio")),    key=f"{key_prefix}_{day}_hora_inicio",    label_visibility="collapsed")),
            "inicio_receso":  inicio_receso_value,
            "final_receso":   fin_receso_value,
            "hora_final":     format_time(cols[4].time_input("Hora final",     value=_parse_time_value(day_initial.get("horario_salida") or day_initial.get("hora_final")),     key=f"{key_prefix}_{day}_hora_final",     label_visibility="collapsed")),
        }
    return schedule


def _combine_local_datetime(fecha_value, hora_value):
    if not fecha_value or not hora_value:
        return None
    local_zone = ZoneInfo("America/Lima")
    if isinstance(fecha_value, str):
        fecha_obj = date.fromisoformat(fecha_value[:10])
    else:
        fecha_obj = fecha_value
    if isinstance(hora_value, str):
        hora_obj = time.fromisoformat(hora_value[:8])
    else:
        hora_obj = hora_value
    combined = datetime.combine(fecha_obj, hora_obj)
    return combined.replace(tzinfo=local_zone).isoformat()


def save_worker_with_schedule(worker_data, selected_days, schedule):
    if isinstance(worker_data, str):
        worker_data = {"dni": worker_data}
    dni = worker_data["dni"]
    upsert_document(WORKER_COLLECTION, dni, worker_data, key_field="dni")
    from supabase_backend import delete_rows, insert_document

    delete_rows("horario_trabajador", [("dni_trabajador", "eq", dni)])
    for day in selected_days:
        day_schedule = schedule.get(day, {})
        insert_document("horario_trabajador", {
            "dni_trabajador": dni,
            "dia_semana": day,
            "horario_entrada": day_schedule.get("hora_inicio") or None,
            "horario_inicio_receso": day_schedule.get("inicio_receso") or None,
            "horario_fin_receso": day_schedule.get("final_receso") or None,
            "horario_salida": day_schedule.get("hora_final") or None,
        })


def save_attendance_record(attendance_data):
    from supabase_backend import insert_document
    insert_document(ATTENDANCE_COLLECTION, attendance_data)


# ── Formularios ────────────────────────────────────────────────────────────────
def tienda_form():
    section_header("Nueva tienda", "Registra una tienda en el sistema")

    with st.form("create_store_form", clear_on_submit=True):
        col_1, col_2 = st.columns(2)
        nombre_tienda = col_1.text_input("Nombre tienda *", placeholder="Tienda Centro")
        correo = col_1.text_input("Correo *", placeholder="tienda@empresa.com")
        telefono = col_1.text_input("Teléfono", placeholder="+51 999 999 999")
        direccion = col_2.text_input("Dirección", placeholder="Av. Principal 123")
        fecha_apertura = col_2.date_input("Fecha apertura", value=None)
        password = col_2.text_input("Contraseña *", type="password")

        submitted = st.form_submit_button("⬡  Registrar tienda", use_container_width=True)

    if not submitted:
        return

    missing = required_missing({
        "Nombre tienda": nombre_tienda, "Correo": correo, "Contraseña": password,
    })
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    doc_id = str(uuid4())

    store_data = {
        "correo": normalize_email(correo),
        "contrasena": hash_password(password),
        "nombre": nombre_tienda.strip(),
        "telefono": telefono.strip(),
        "direccion": direccion.strip(),
        "fecha_apertura": fecha_apertura.isoformat() if fecha_apertura else None,
        "estado": True,
    }
    qr_token = create_store_with_qr(doc_id, store_data)
    st.success(f"✓  Tienda registrada → `{STORE_COLLECTION}/{doc_id}`")
    st.caption(f"QR activo creado en `{QR_ACTIVE_COLLECTION}` - token `{qr_token}`")


def trabajador_form():
    section_header("Nuevo trabajador", "Crea el perfil y horario de un colaborador")
    tiendas = get_tiendas()

    success_message = st.session_state.pop("worker_success_message", None)
    if success_message:
        st.success(success_message)

    if not tiendas:
        st.warning("Primero registra al menos una tienda.")
        return

    tienda_options = {
        f"{t['nombre_tienda']}  ·  {t['id_tienda']}": t for t in tiendas
    }

    form_seed = int(st.session_state.get("worker_form_seed", 0))
    selected_days = st.multiselect(
        "Días laborables *",
        options=list(WEEK_DAYS),
        default=list(WEEK_DAYS),
        format_func=str.capitalize,
        key=f"worker_days_{form_seed}",
    )
    if not selected_days:
        st.warning("Selecciona al menos un día para el horario.")

    with st.form(f"create_worker_form_{form_seed}", clear_on_submit=False):
        col_1, col_2 = st.columns(2)
        dni = col_1.text_input("DNI *", placeholder="12345678", key=f"worker_dni_{form_seed}")
        nombre = col_1.text_input("Nombre completo *", placeholder="Juan Pérez", key=f"worker_nombre_{form_seed}")
        cargo = col_1.text_input("Cargo", placeholder="Ventas", key=f"worker_cargo_{form_seed}")
        sueldo = col_1.number_input("Sueldo", min_value=0.0, step=50.0, format="%.2f", key=f"worker_sueldo_{form_seed}")
        correo = col_2.text_input("Correo", placeholder="juan@empresa.com", key=f"worker_correo_{form_seed}")
        password = col_2.text_input("Contraseña", type="password", key=f"worker_password_{form_seed}")
        telefono = col_2.text_input("Teléfono", placeholder="+51 999 999 999", key=f"worker_telefono_{form_seed}")
        csi = col_2.text_input("CSI / código interno", placeholder="CSI-001", key=f"worker_csi_{form_seed}")
        foto_dni = col_2.file_uploader(
            "Foto DNI *",
            type=["jpg", "jpeg", "png", "pdf"],
            key=f"worker_foto_{form_seed}",
        )
        tienda_label      = st.selectbox(
            "Tienda / sede asignada *",
            options=list(tienda_options.keys()),
            index=None,
            placeholder="Selecciona una tienda",
            key=f"worker_tienda_{form_seed}",
        )
        horario = build_schedule_inputs(selected_days, key_prefix=f"worker_{form_seed}")
        submitted = st.form_submit_button("⬡  Registrar trabajador", use_container_width=True)

    if not submitted:
        return

    missing = required_missing({
        "DNI": dni, "Nombre": nombre, "Foto DNI": foto_dni,
        "Tienda": tienda_label,
    })
    if not selected_days:
        missing.append("Días laborables")

    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    doc_id = str(dni).strip()
    if document_exists(WORKER_COLLECTION, doc_id):
        st.error(f"Ya existe un trabajador con el ID `{doc_id}`.")
        return

    tienda = tienda_options[tienda_label]
    try:
        uploaded_dni = upload_worker_file(foto_dni, doc_id)
    except Exception as exc:
        st.error(f"No se pudo subir el archivo a Cloudinary: {exc}")
        return

    worker_data = {
        "dni": doc_id,
        "id_tienda": tienda["id_tienda"],
        "correo": normalize_email(correo),
        "contrasena": hash_password(password),
        "nombre": nombre.strip(),
        "cargo": cargo.strip(),
        "sueldo": float(sueldo) if sueldo is not None else None,
        "telefono": telefono.strip(),
        "csi": csi.strip(),
        "foto_dni": uploaded_dni["secure_url"],
        "estado": True,
    }
    create_document(WORKER_COLLECTION, doc_id, worker_data)
    from supabase_backend import delete_rows, insert_document
    delete_rows("horario_trabajador", [("dni_trabajador", "eq", doc_id)])
    for day in selected_days:
        schedule_item = horario.get(day, {})
        insert_document("horario_trabajador", {
            "dni_trabajador": doc_id,
            "dia_semana": day,
            "horario_entrada": schedule_item.get("hora_inicio") or None,
            "horario_inicio_receso": schedule_item.get("inicio_receso") or None,
            "horario_fin_receso": schedule_item.get("final_receso") or None,
            "horario_salida": schedule_item.get("hora_final") or None,
        })
    st.session_state["worker_success_message"] = f"✓  Trabajador registrado → `{WORKER_COLLECTION}/{doc_id}`"
    st.session_state["worker_form_seed"] = form_seed + 1
    st.rerun()


def asistencia_form():
    section_header("Nueva asistencia", "Registra o corrige una marca manualmente")
    trabajadores = get_trabajadores()

    if not trabajadores:
        st.warning("Necesitas al menos un trabajador registrado.")
        return

    worker_options = {f"{w['nombre_trabajador']}  ·  {w['dni']}": w for w in trabajadores}

    with st.form("create_attendance_form", clear_on_submit=True):
        col_1, col_2 = st.columns(2)
        worker_label  = col_1.selectbox("Trabajador *", options=list(worker_options.keys()), index=None, placeholder="Selecciona un trabajador")
        fecha         = col_1.date_input("Fecha *")

        st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
        st.markdown('<span style="font-family:Space Mono,monospace;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;">⬡ &nbsp;Marcas horarias</span>', unsafe_allow_html=True)

        t1, t2, t3, t4 = st.columns(4)
        hora_inicio   = t1.time_input("Entrada *")
        inicio_receso = t2.time_input("Ini. receso *")
        final_receso  = t3.time_input("Fin receso *")
        hora_final    = t4.time_input("Salida *")

        ultima_marca = st.selectbox(
            "Última marca registrada *",
            options=["hora_inicio", "inicio_receso", "final_receso", "hora_final"],
        )
        submitted = st.form_submit_button("⬡  Registrar asistencia", use_container_width=True)

    if not submitted:
        return

    missing = required_missing({
        "Trabajador": worker_label,
        "Fecha": fecha,
        "Entrada": hora_inicio,
        "Ini. receso": inicio_receso,
        "Fin receso": final_receso,
        "Salida": hora_final,
    })
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    trabajador = worker_options[worker_label]
    create_document(ATTENDANCE_COLLECTION, str(uuid4()), {
        "dni_trabajador": trabajador["dni"],
        "fecha": fecha.isoformat(),
        "horario_entrada": _combine_local_datetime(fecha, hora_inicio),
        "horario_inicio_receso": _combine_local_datetime(fecha, inicio_receso),
        "horario_fin_receso": _combine_local_datetime(fecha, final_receso),
        "horario_salida": _combine_local_datetime(fecha, hora_final),
    })
    st.success(f"✓  Asistencia registrada → `{ATTENDANCE_COLLECTION}`")


# ── Vista general ──────────────────────────────────────────────────────────────
@st.dialog("Asistencias del trabajador", width="large")
def worker_attendance_dialog(trabajador):
    asistencias = get_asistencias_trabajador(trabajador["id_trabajador"])
    st.caption(
        f"{trabajador['nombre_trabajador']} · DNI {trabajador['dni']} · "
        f"{trabajador['nombre_sede']}"
    )

    if not asistencias:
        st.info("Este trabajador todavia no tiene asistencias registradas.")
        return

    attendance_dates = [
        parsed_date for item in asistencias
        if (parsed_date := parse_iso_date(item["fecha"]))
    ]
    if not attendance_dates:
        st.warning("Hay asistencias, pero ninguna tiene una fecha valida.")
        return

    month_key = f"attendance_month_{trabajador['doc_id']}"
    available_months = sorted({date(d.year, d.month, 1) for d in attendance_dates})
    if month_key not in st.session_state:
        st.session_state[month_key] = available_months[-1]

    current_month = st.session_state[month_key]
    min_month, max_month = available_months[0], available_months[-1]
    can_go_back = current_month > min_month
    can_go_next = current_month < max_month

    prev_col, title_col, next_col = st.columns([1, 2, 1])
    if prev_col.button("←", disabled=not can_go_back, use_container_width=True):
        st.session_state[month_key] = add_months(current_month, -1)
        st.rerun(scope="fragment")
    title_col.markdown(
        f"<div style='text-align:center;font-family:Space Mono,monospace;"
        f"font-size:0.9rem;padding-top:0.45rem;'>{format_month(current_month)}</div>",
        unsafe_allow_html=True,
    )
    if next_col.button("→", disabled=not can_go_next, use_container_width=True):
        st.session_state[month_key] = add_months(current_month, 1)
        st.rerun(scope="fragment")

    monthly_rows = []
    for item in asistencias:
        parsed_date = parse_iso_date(item["fecha"])
        if not parsed_date:
            continue
        if parsed_date.year == current_month.year and parsed_date.month == current_month.month:
            monthly_rows.append({
                "fecha": item["fecha"],
                "tienda": item["nombre_tienda"],
                "entrada": item["hora_inicio"],
                "ini_receso": item["inicio_receso"],
                "fin_receso": item["final_receso"],
                "salida": item["hora_final"],
                "ultima_marca": item["ultima_marca"],
            })

    st.metric("Asistencias del mes", len(monthly_rows))
    if monthly_rows:
        st.dataframe(monthly_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No hay asistencias en este mes.")


def overview():
    tiendas      = get_tiendas()
    trabajadores = get_trabajadores()
    asistencias  = get_asistencias()

    m1, m2, m3 = st.columns(3)
    m1.metric("Tiendas",              len(tiendas))
    m2.metric("Trabajadores",         len(trabajadores))
    m3.metric("Asistencias recientes", len(asistencias))

    st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)

    tab_t, tab_w, tab_a = st.tabs(["Tiendas", "Trabajadores", "Asistencias"])

    with tab_t:
        st.caption(f"tabla PostgreSQL: `{STORE_COLLECTION}`")
        if tiendas:
            st.dataframe(tiendas, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay tiendas registradas.")

    with tab_w:
        st.caption(f"tabla PostgreSQL: `{WORKER_COLLECTION}`")
        if trabajadores:
            st.dataframe(trabajadores, use_container_width=True, hide_index=True)
            worker_options = {
                f"{t['nombre_trabajador']}  ·  {t['dni']}": t for t in trabajadores
            }
            selected_worker_label = st.selectbox(
                "Ver asistencias de trabajador",
                options=list(worker_options.keys()),
                index=None,
                placeholder="Selecciona un trabajador",
            )
            if st.button(
                "Ver asistencias",
                disabled=not selected_worker_label,
                use_container_width=True,
            ):
                worker_attendance_dialog(worker_options[selected_worker_label])
        else:
            st.info("Todavía no hay trabajadores registrados.")

    with tab_a:
        st.caption(f"tabla PostgreSQL: `{ATTENDANCE_COLLECTION}`  ·  últimos 30 registros")
        if asistencias:
            st.dataframe(asistencias, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay asistencias registradas.")


def build_section_context():
    return SimpleNamespace(
        ATTENDANCE_COLLECTION=ATTENDANCE_COLLECTION,
        QR_ACTIVE_COLLECTION=QR_ACTIVE_COLLECTION,
        STORE_COLLECTION=STORE_COLLECTION,
        WEEK_DAYS=WEEK_DAYS,
        WORKER_COLLECTION=WORKER_COLLECTION,
        build_schedule_inputs=build_schedule_inputs,
        create_document=create_document,
        create_store_with_qr=create_store_with_qr,
        delete_document=delete_document,
        document_exists=document_exists,
        format_time=format_time,
        get_asistencias=get_asistencias,
        get_horarios_trabajador=get_horarios_trabajador,
        get_tiendas=get_tiendas,
        get_trabajadores=get_trabajadores,
        normalize_doc_id=normalize_doc_id,
        normalize_email=normalize_email,
        hash_password=hash_password,
        server_timestamp=server_timestamp,
        required_missing=required_missing,
        section_header=section_header,
        upload_worker_file=upload_worker_file,
        save_worker_schedule=save_worker_with_schedule,
        save_attendance_record=save_attendance_record,
        update_document=update_document,
        worker_attendance_dialog=worker_attendance_dialog,
    )


# ── Página principal ───────────────────────────────────────────────────────────
def admin_page():
    pages = {
        "Asistencias": render_resumen,
        "Tiendas": render_tiendas,
        "Trabajadores": render_trabajadores,
    }

    with st.sidebar:
        st.markdown("""
        <div style="padding:0.35rem 0 1rem;">
            <div style="font-family:'Space Mono',monospace;font-size:1.05rem;color:#1f2a37;">
                Admin Asistencia
            </div>
            <div style="font-size:0.78rem;color:#5f7182;margin-top:0.2rem;">
                Panel de RRHH
            </div>
        </div>
        """, unsafe_allow_html=True)
        current_page = st.radio(
            "Sección",
            options=list(pages.keys()),
            label_visibility="collapsed",
        )
        st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
        if st.button("Cerrar sesión", use_container_width=True):
            logout()
            st.rerun()

    st.markdown("""
    <div class="hero-banner">
        <div style="display:flex; align-items:center; justify-content:space-between; gap:1rem;">
            <div style="display:flex; align-items:center; gap:0.8rem;">
                <div style="font-size:1.45rem; color:#78bdf2; line-height:1;">⬡</div>
                <div>
                    <div style="font-family:'Space Mono',monospace; font-size:1.35rem;
                                letter-spacing:0.04em; color:#1f2a37; line-height:1;">
                        Panel de Administración
                    </div>
                    <div style="font-size:0.79rem; color:#5f7182; font-family:'DM Sans',sans-serif;
                                margin-top:0.24rem;">
                        Sistema de Asistencia · PostgreSQL
                    </div>
                </div>
            </div>
            <div style="font-family:'Space Mono',monospace;font-size:0.64rem;letter-spacing:0.08em;
                        text-transform:uppercase;padding:0.38rem 0.7rem;border-radius:8px;
                        color:#ffffff;background:var(--tertiary);">
                {current_page}
            </div>
        </div>
    </div>
    <hr style="margin: 0.85rem 0 1.5rem; border-color:#cfe3f7;">
    """.replace("{current_page}", current_page), unsafe_allow_html=True)

    try:
        connection = get_connection()
        connection.close()
    except Exception as exc:
        st.error(f"No se pudo conectar con PostgreSQL: {exc}")
        st.stop()

    pages[current_page](build_section_context())


def main():
    if not is_authenticated():
        render_login()
        return
    admin_page()


if __name__ == "__main__":
    main()
