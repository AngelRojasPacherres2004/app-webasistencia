from pathlib import Path
from uuid import uuid4
from datetime import date
import json
import tomllib

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore
from cloudinary_uploader import upload_worker_file


st.set_page_config(
    page_title="Admin · Asistencia",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Tema visual ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg:        #f5f6fa;
    --surface:   #ffffff;
    --border:    #dde1ea;
    --accent:    #2563eb;
    --accent2:   #0ea86e;
    --danger:    #dc2626;
    --text:      #111827;
    --muted:     #6b7280;
    --mono:      'Space Mono', monospace;
    --sans:      'DM Sans', sans-serif;
}

/* Base */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border); }

/* Main container */
.main .block-container {
    padding: 2.5rem 3rem 4rem !important;
    max-width: 1200px;
}

/* Títulos */
h1 {
    font-family: var(--mono) !important;
    font-size: 1.5rem !important;
    letter-spacing: 0.03em !important;
    color: var(--text) !important;
    border-bottom: 1px solid var(--border);
    padding-bottom: 1rem;
    margin-bottom: 0.25rem !important;
}
h2, h3 {
    font-family: var(--mono) !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: var(--muted) !important;
    margin-top: 1.5rem !important;
}
p, [data-testid="stText"], small, label {
    font-family: var(--sans) !important;
    color: var(--text) !important;
}
.stCaption, [data-testid="stCaptionContainer"] {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    color: var(--muted) !important;
}

/* Métricas */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-top: 3px solid var(--accent) !important;
    border-radius: 6px !important;
    padding: 1.25rem 1.5rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
[data-testid="stMetricLabel"] {
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--muted) !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    font-size: 2.2rem !important;
    color: var(--text) !important;
}

/* Tabs */
[data-testid="stTabs"] button {
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--muted) !important;
    border: none !important;
    background: transparent !important;
    padding: 0.6rem 1rem !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
}
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid var(--border) !important;
    gap: 0.25rem !important;
}
[data-testid="stTabsContent"] {
    padding-top: 1.5rem !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stTimeInput"] input,
[data-testid="stDateInput"] input {
    background: #fff !important;
    border: 1px solid var(--border) !important;
    border-radius: 5px !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
    font-size: 0.875rem !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stTimeInput"] label,
[data-testid="stDateInput"] label,
[data-testid="stMultiSelect"] label {
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: var(--muted) !important;
    margin-bottom: 0.25rem !important;
}

/* Botón principal */
[data-testid="stFormSubmitButton"] button,
.stButton button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 5px !important;
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    padding: 0.65rem 1.5rem !important;
    transition: background 0.15s, box-shadow 0.15s, transform 0.1s !important;
    box-shadow: 0 2px 6px rgba(37,99,235,0.25) !important;
}
[data-testid="stFormSubmitButton"] button:hover,
.stButton button:hover {
    background: #1d4ed8 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.3) !important;
}
[data-testid="stFormSubmitButton"] button:active,
.stButton button:active {
    transform: translateY(0) !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: 5px !important;
    font-family: var(--sans) !important;
    font-size: 0.85rem !important;
}

/* Multiselect chips */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: rgba(37,99,235,0.1) !important;
    border: 1px solid rgba(37,99,235,0.25) !important;
    border-radius: 3px !important;
    color: var(--accent) !important;
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
}

/* Form container */
[data-testid="stForm"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 1.5rem !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.05) !important;
}

/* Divider */
hr { border-color: var(--border) !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #b0b7c3; }
</style>
""", unsafe_allow_html=True)


# ── Constantes ─────────────────────────────────────────────────────────────────
WORKER_COLLECTION = "trabajador"
STORE_COLLECTION = "tienda"
ATTENDANCE_COLLECTION = "asistencia"
QR_ACTIVE_COLLECTION = "qr_activos"
MONTH_NAMES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)
WEEK_DAYS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado")
SCHEDULE_FIELDS = ("hora_inicio", "inicio_receso", "final_receso", "hora_final")
HIDDEN_FIELDS = ("password", "contrasena", "contraseña")
SECRET_JSON_PATHS = (
    Path(".streamlit/secrets.toml"),
    Path(".streamlit/secret.toml"),
    Path(".streamlit/secrets.toml"),
    Path(".streamlit/firebase-service-account.json"),
)


def clean_service_account(service_account):
    """Limpia y valida el diccionario de la cuenta de servicio."""
    if not service_account or not isinstance(service_account, dict):
        return service_account
    
    # Asegura que la llave privada no tenga espacios extra y procese bien los saltos de línea
    if "private_key" in service_account and isinstance(service_account["private_key"], str):
        service_account["private_key"] = service_account["private_key"].replace("\\n", "\n").strip()
    
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


@st.cache_resource(show_spinner=False)
def get_firestore_client():
    service_account = load_service_account()
    project_id = service_account.get("project_id")

    if firebase_admin._apps:
        current_app = firebase_admin.get_app()
        if current_app.project_id != project_id:
            firebase_admin.delete_app(current_app)
        else:
            return firestore.client()

    if firebase_admin._apps:
        return firestore.client()

    cred = credentials.Certificate(service_account)
    firebase_admin.initialize_app(cred)
    return firestore.client()


def load_service_account():
    try:
        for key in ["firebase_service_account", "google_service_account"]:
            if key in st.secrets:
                return clean_service_account(dict(st.secrets[key]))
    except Exception:
        pass

    for json_path in SECRET_JSON_PATHS:
        if json_path.exists():
            return load_service_account_file(json_path)

    st.error(
        "No encontré credenciales de Firebase. Coloca el JSON en "
        "`.streamlit/secrets.toml` o `.streamlit/firebase-service-account.json`."
    )
    st.stop()


def load_service_account_file(path):
    raw_content = path.read_text(encoding="utf-8-sig").strip()
    if raw_content.startswith("{"):
        service_account, _ = json.JSONDecoder().raw_decode(raw_content)
        return clean_service_account(service_account)
    parsed = tomllib.loads(raw_content)
    for key in ["firebase_service_account", "google_service_account"]:
        if key in parsed:
            return clean_service_account(dict(parsed[key]))
    if "type" in parsed and "project_id" in parsed:
        return clean_service_account(parsed)
    st.error(f"No pude leer credenciales válidas desde `{path}`.")
    st.stop()


def required_missing(fields):
    return [label for label, value in fields.items() if not str(value or "").strip()]


def document_exists(collection_name, document_id):
    db = get_firestore_client()
    return db.collection(collection_name).document(document_id).get().exists


def create_document(collection_name, document_id, data):
    db = get_firestore_client()
    db.collection(collection_name).document(document_id).set(data)
    st.cache_data.clear()


def create_store_with_qr(document_id, store_data):
    db = get_firestore_client()
    qr_token = uuid4().hex
    qr_data = {
        "id_tienda": store_data["id_tienda"],
        "nombre_tienda": store_data["nombre_tienda"],
        "id_sede": store_data["id_sede"],
        "nombre_sede": store_data["nombre_sede"],
        "direccion": store_data["direccion"],
        "token": qr_token,
        "activo": True,
        "fecha_creada": firestore.SERVER_TIMESTAMP,
    }

    batch = db.batch()
    batch.set(db.collection(STORE_COLLECTION).document(document_id), store_data)
    batch.set(db.collection(QR_ACTIVE_COLLECTION).document(document_id), qr_data)
    batch.commit()
    st.cache_data.clear()
    return qr_token


# ── Queries cacheadas ──────────────────────────────────────────────────────────
@st.cache_data(ttl=10, show_spinner=False)
def get_tiendas():
    db = get_firestore_client()
    docs = db.collection(STORE_COLLECTION).stream()
    tiendas = []
    for doc in docs:
        data = doc.to_dict()
        tiendas.append({
            "doc_id": doc.id,
            "id_tienda": data.get("id_tienda", doc.id),
            "correo": data.get("correo", ""),
            "tiene_contrasena": bool(data.get("password") or data.get("contrasena")),
            "nombre_tienda": data.get("nombre_tienda", ""),
            "id_sede": data.get("id_sede", ""),
            "nombre_sede": data.get("nombre_sede", ""),
            "direccion": data.get("direccion", ""),
        })
    return sorted(tiendas, key=lambda x: x["nombre_tienda"])


@st.cache_data(ttl=10, show_spinner=False)
def get_trabajadores():
    db = get_firestore_client()
    docs = db.collection(WORKER_COLLECTION).stream()
    trabajadores = []
    for doc in docs:
        data = doc.to_dict()
        trabajadores.append({
            "doc_id": doc.id,
            "id_trabajador": data.get("id_trabajador", doc.id),
            "correo": data.get("correo", ""),
            "tiene_contrasena": bool(data.get("password") or data.get("contrasena")),
            "area": data.get("area", ""),
            "dni": data.get("dni", ""),
            "id_sede": data.get("id_sede", ""),
            "nombre_sede": data.get("nombre_sede", ""),
            "nombre_trabajador": data.get("nombre_trabajador", ""),
            "cuenta_bancaria": data.get("cuenta_bancaria", ""),
            "dias_horario": ", ".join((data.get("horario") or {}).keys()),
        })
    return sorted(trabajadores, key=lambda x: x["nombre_trabajador"])


@st.cache_data(ttl=10, show_spinner=False)
def get_asistencias():
    db = get_firestore_client()
    docs = db.collection(ATTENDANCE_COLLECTION).limit(30).stream()
    asistencias = []
    for doc in docs:
        data = doc.to_dict()
        asistencias.append({
            "doc_id": doc.id,
            "fecha": data.get("fecha", ""),
            "nombre_tienda": data.get("nombre_tienda", ""),
            "id_trabajador": data.get("id_trabajador", ""),
            "dni": data.get("dni", ""),
            "ultima_marca": data.get("ultima_marca", ""),
        })
    return asistencias


@st.cache_data(ttl=10, show_spinner=False)
def get_asistencias_trabajador(id_trabajador):
    db = get_firestore_client()
    docs = (
        db.collection(ATTENDANCE_COLLECTION)
        .where("id_trabajador", "==", id_trabajador)
        .stream()
    )
    asistencias = []
    for doc in docs:
        data = doc.to_dict()
        parsed_date = parse_iso_date(data.get("fecha"))
        asistencias.append({
            "doc_id": doc.id,
            "fecha": data.get("fecha", ""),
            "fecha_orden": parsed_date.isoformat() if parsed_date else "",
            "nombre_tienda": data.get("nombre_tienda", ""),
            "id_tienda": data.get("id_tienda", ""),
            "hora_inicio": data.get("hora_inicio", ""),
            "inicio_receso": data.get("inicio_receso", ""),
            "final_receso": data.get("final_receso", ""),
            "hora_final": data.get("hora_final") or data.get("hora_finalhas", ""),
            "ultima_marca": data.get("ultima_marca", ""),
            "id_sede": data.get("id_sede", ""),
            "nombre_sede": data.get("nombre_sede", ""),
            "dni": data.get("dni", ""),
        })
    return sorted(asistencias, key=lambda x: x["fecha_orden"], reverse=True)


# ── Componentes UI ─────────────────────────────────────────────────────────────
def section_header(title, subtitle=None):
    """Encabezado de sección con línea decorativa."""
    st.markdown(f"""
    <div style="margin: 0.5rem 0 1.5rem; padding-left: 0.75rem;
                border-left: 3px solid #2563eb;">
        <div style="font-family:'Space Mono',monospace; font-size:0.78rem;
                    text-transform:uppercase; letter-spacing:0.1em; color:#2563eb;
                    margin-bottom:0.2rem;">{title}</div>
        {'<div style="font-size:0.82rem; color:#6b7280; font-family:DM Sans,sans-serif;">'+subtitle+'</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def badge(text, color="#5865f2"):
    return f'<span style="background:rgba(88,101,242,0.15);color:{color};border:1px solid rgba(88,101,242,0.3);border-radius:3px;padding:2px 8px;font-family:Space Mono,monospace;font-size:0.65rem;letter-spacing:0.06em;">{text}</span>'


def build_schedule_inputs(selected_days):
    if not selected_days:
        return {}

    st.markdown("""
    <div style="font-family:'Space Mono',monospace; font-size:0.68rem;
                text-transform:uppercase; letter-spacing:0.08em; color:#6b7280;
                margin: 1.25rem 0 0.75rem; padding: 0.5rem 0;
                border-top: 1px solid #dde1ea; border-bottom: 1px solid #dde1ea;">
        ⬡ &nbsp;Horario por día
    </div>
    """, unsafe_allow_html=True)

    schedule = {}
    header = st.columns([1.2, 1, 1, 1, 1])
    for col, label in zip(header, ["Día", "Entrada", "Ini. receso", "Fin receso", "Salida"]):
        col.markdown(f'<span style="font-family:Space Mono,monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.07em;color:#6b7280;">{label}</span>', unsafe_allow_html=True)

    for day in selected_days:
        cols = st.columns([1.2, 1, 1, 1, 1])
        cols[0].markdown(f'<span style="font-family:Space Mono,monospace;font-size:0.78rem;color:#111827;">{day.capitalize()}</span>', unsafe_allow_html=True)
        schedule[day] = {
            "hora_inicio":    format_time(cols[1].time_input("Hora inicio",    key=f"{day}_hora_inicio",    label_visibility="collapsed")),
            "inicio_receso":  format_time(cols[2].time_input("Inicio receso",  key=f"{day}_inicio_receso",  label_visibility="collapsed")),
            "final_receso":   format_time(cols[3].time_input("Final receso",   key=f"{day}_final_receso",   label_visibility="collapsed")),
            "hora_final":     format_time(cols[4].time_input("Hora final",     key=f"{day}_hora_final",     label_visibility="collapsed")),
        }
    return schedule


# ── Formularios ────────────────────────────────────────────────────────────────
def tienda_form():
    section_header("Nueva tienda / sede", "Registra un punto de venta en el sistema")

    with st.form("create_store_form", clear_on_submit=True):
        col_1, col_2 = st.columns(2)
        id_tienda      = col_1.text_input("ID tienda *",            placeholder="tienda_001")
        nombre_tienda  = col_1.text_input("Nombre tienda *",        placeholder="Tienda Centro")
        id_sede        = col_1.text_input("ID sede *",              placeholder="sede_001")
        correo         = col_2.text_input("Correo *",               placeholder="tienda@empresa.com")
        password       = col_2.text_input("Contraseña del correo *", type="password")
        nombre_sede    = col_2.text_input("Nombre sede *",          placeholder="Sede Lima Norte")
        direccion      = col_2.text_input("Dirección *",            placeholder="Av. Principal 123")

        submitted = st.form_submit_button("⬡  Registrar tienda", use_container_width=True)

    if not submitted:
        return

    missing = required_missing({
        "ID tienda": id_tienda, "Correo": correo, "Contraseña": password,
        "Nombre tienda": nombre_tienda, "ID sede": id_sede,
        "Nombre sede": nombre_sede, "Dirección": direccion,
    })
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    doc_id = normalize_doc_id(id_tienda)
    if document_exists(STORE_COLLECTION, doc_id):
        st.error(f"Ya existe una tienda con el ID `{doc_id}`.")
        return

    store_data = {
        "id_tienda": id_tienda.strip(),
        "correo": normalize_email(correo),
        "password": password, "contrasena": password,
        "nombre_tienda": nombre_tienda.strip(),
        "id_sede": id_sede.strip(),
        "nombre_sede": nombre_sede.strip(),
        "direccion": direccion.strip(),
    }
    qr_token = create_store_with_qr(doc_id, store_data)
    st.success(f"✓  Tienda registrada → `{STORE_COLLECTION}/{doc_id}`")
    st.caption(f"QR activo creado: `{QR_ACTIVE_COLLECTION}/{doc_id}` - token `{qr_token}`")


def trabajador_form():
    section_header("Nuevo trabajador", "Crea el perfil de un colaborador con su horario")
    tiendas = get_tiendas()

    if not tiendas:
        st.warning("Primero registra al menos una tienda para asignar la sede.")
        return

    tienda_options = {
        f"{t['nombre_tienda']}  ·  {t['nombre_sede']}": t for t in tiendas
    }

    selected_days = st.multiselect(
        "Días laborables *",
        options=list(WEEK_DAYS),
        default=list(WEEK_DAYS),
        format_func=str.capitalize,
    )
    if not selected_days:
        st.warning("Selecciona al menos un día para el horario.")

    with st.form("create_worker_form", clear_on_submit=True):
        col_1, col_2 = st.columns(2)
        id_trabajador     = col_1.text_input("ID trabajador *",       placeholder="trab_001")
        nombre_trabajador = col_1.text_input("Nombre completo *",     placeholder="Juan Pérez")
        dni               = col_1.text_input("DNI *",                 placeholder="12345678")
        area              = col_1.text_input("Área *",                placeholder="Ventas")
        correo            = col_2.text_input("Correo *",              placeholder="juan@empresa.com")
        password          = col_2.text_input("Contraseña del correo *", type="password")
        cuenta_bancaria   = col_2.text_input("Cuenta bancaria *",     placeholder="0011-0123-...")
        foto_dni          = col_2.file_uploader(
            "Foto DNI *",
            type=["jpg", "jpeg", "png", "pdf"],
        )
        tienda_label      = st.selectbox(
            "Tienda / sede asignada *",
            options=list(tienda_options.keys()),
            index=None, placeholder="Selecciona una tienda",
        )
        horario = build_schedule_inputs(selected_days)
        submitted = st.form_submit_button("⬡  Registrar trabajador", use_container_width=True)

    if not submitted:
        return

    missing = required_missing({
        "ID trabajador": id_trabajador, "Correo": correo, "Contraseña": password,
        "Área": area, "DNI": dni, "Foto DNI": foto_dni,
        "Tienda / sede": tienda_label, "Nombre": nombre_trabajador,
        "Cuenta bancaria": cuenta_bancaria,
    })
    if not selected_days:
        missing.append("Días laborables")

    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    doc_id = normalize_doc_id(id_trabajador)
    if document_exists(WORKER_COLLECTION, doc_id):
        st.error(f"Ya existe un trabajador con el ID `{doc_id}`.")
        return

    tienda = tienda_options[tienda_label]
    try:
        uploaded_dni = upload_worker_file(foto_dni, doc_id)
    except Exception as exc:
        st.error(f"No se pudo subir el archivo a Cloudinary: {exc}")
        return

    create_document(WORKER_COLLECTION, doc_id, {
        "id_trabajador": id_trabajador.strip(),
        "correo": normalize_email(correo),
        "password": password, "contrasena": password,
        "area": area.strip(), "dni": dni.strip(),
        "foto_dni": uploaded_dni["secure_url"],
        "foto_dni_public_id": uploaded_dni["public_id"],
        "foto_dni_asset_id": uploaded_dni["asset_id"],
        "foto_dni_resource_type": uploaded_dni["resource_type"],
        "foto_dni_nombre_archivo": uploaded_dni["name"],
        "id_sede": tienda["id_sede"], "nombre_sede": tienda["nombre_sede"],
        "nombre_trabajador": nombre_trabajador.strip(),
        "cuenta_bancaria": cuenta_bancaria.strip(),
        "fecha_creada": firestore.SERVER_TIMESTAMP,
        "horario": horario,
    })
    st.success(f"✓  Trabajador registrado → `{WORKER_COLLECTION}/{doc_id}`")


def asistencia_form():
    section_header("Nueva asistencia", "Registra o corrige una marca de asistencia manualmente")
    tiendas     = get_tiendas()
    trabajadores = get_trabajadores()

    if not tiendas or not trabajadores:
        st.warning("Necesitas al menos una tienda y un trabajador registrados.")
        return

    tienda_options = {f"{t['nombre_tienda']}  ·  {t['id_tienda']}": t for t in tiendas}
    worker_options = {f"{w['nombre_trabajador']}  ·  {w['dni']}": w for w in trabajadores}

    with st.form("create_attendance_form", clear_on_submit=True):
        col_1, col_2 = st.columns(2)
        tienda_label  = col_1.selectbox("Tienda *",     options=list(tienda_options.keys()), index=None, placeholder="Selecciona una tienda")
        worker_label  = col_2.selectbox("Trabajador *", options=list(worker_options.keys()), index=None, placeholder="Selecciona un trabajador")
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
        "Tienda": tienda_label, "Trabajador": worker_label,
        "Fecha": fecha, "Entrada": hora_inicio,
        "Ini. receso": inicio_receso, "Fin receso": final_receso,
        "Salida": hora_final, "Última marca": ultima_marca,
    })
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    tienda    = tienda_options[tienda_label]
    trabajador = worker_options[worker_label]
    doc_id = normalize_doc_id(
        f"{trabajador['id_trabajador']}_{fecha.isoformat()}_{tienda['id_tienda']}"
    )
    create_document(ATTENDANCE_COLLECTION, doc_id, {
        "nombre_tienda":  tienda["nombre_tienda"],
        "id_tienda":      tienda["id_tienda"],
        "id_trabajador":  trabajador["id_trabajador"],
        "fecha":          fecha.isoformat(),
        "hora_inicio":    format_time(hora_inicio),
        "inicio_receso":  format_time(inicio_receso),
        "final_receso":   format_time(final_receso),
        "hora_finalhas":  format_time(hora_final),
        "ultima_marca":   ultima_marca,
        "id_sede":        tienda["id_sede"],
        "nombre_sede":    tienda["nombre_sede"],
        "dni":            trabajador["dni"],
    })
    st.success(f"✓  Asistencia registrada → `{ATTENDANCE_COLLECTION}/{doc_id}`")


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
        st.caption(f"colección Firebase: `{STORE_COLLECTION}`")
        if tiendas:
            st.dataframe(tiendas, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay tiendas registradas.")

    with tab_w:
        st.caption(f"colección Firebase: `{WORKER_COLLECTION}`")
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
        st.caption(f"colección Firebase: `{ATTENDANCE_COLLECTION}`  ·  últimos 30 registros")
        if asistencias:
            st.dataframe(asistencias, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay asistencias registradas.")


# ── Página principal ───────────────────────────────────────────────────────────
def admin_page():
    # Encabezado
    st.markdown("""
    <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.25rem;">
        <div style="font-size:1.4rem; color:#2563eb;">⬡</div>
        <div>
            <div style="font-family:'Space Mono',monospace; font-size:1.35rem;
                        letter-spacing:0.04em; color:#111827; line-height:1;">
                Panel de Administración
            </div>
            <div style="font-size:0.78rem; color:#6b7280; font-family:'DM Sans',sans-serif;
                        margin-top:0.2rem;">
                Sistema de Asistencia · Firebase Firestore
            </div>
        </div>
    </div>
    <hr style="margin: 0.75rem 0 1.5rem; border-color:#dde1ea;">
    """, unsafe_allow_html=True)

    try:
        get_firestore_client()
    except Exception as exc:
        st.error(f"No se pudo conectar con Firebase: {exc}")
        st.stop()

    tab_overview, tab_store, tab_worker, tab_attendance = st.tabs([
        "⬡  Resumen",
        "⊕  Tienda / Sede",
        "⊕  Trabajador",
        "⊕  Asistencia",
    ])

    with tab_overview:
        overview()
    with tab_store:
        tienda_form()
    with tab_worker:
        trabajador_form()
    with tab_attendance:
        asistencia_form()


def main():
    admin_page()


if __name__ == "__main__":
    main()
