from pathlib import Path
from uuid import uuid4
from datetime import date
from types import SimpleNamespace
import json
import base64
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

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore
from cloudinary_uploader import upload_worker_file
from login import is_authenticated, render_login, logout
from sections.asistencias import render_asistencias
from sections.overview import render_overview
from sections.tiendas import render_tiendas
from sections.trabajadores import render_trabajadores


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

# ── Tema visual ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
    --primary:   #ffffff;
    --secondary: #eaf4ff;
    --tertiary:  #2563eb;
    --bg:        var(--primary);
    --surface:   var(--primary);
    --surface-2: var(--secondary);
    --border:    #cfe3f7;
    --accent:    #78bdf2;
    --accent2:   #d8efff;
    --danger:    var(--tertiary);
    --text:      #1f2a37;
    --muted:     #5f7182;
    --mono:      'Space Mono', monospace;
    --sans:      'DM Sans', sans-serif;
}

/* Base */
html, body, .stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"], .main {
    background: linear-gradient(180deg, var(--primary) 0%, var(--secondary) 100%) !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
}
[data-testid="stAppViewContainer"] > .main { background: transparent !important; }
[data-testid="stHeader"] { background: rgba(255,255,255,0.88) !important; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stSidebar"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
    left: 0 !important;
    right: auto !important;
    width: 20rem !important;
    min-width: 20rem !important;
    max-width: 20rem !important;
    background: var(--primary) !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: 8px 0 30px rgba(120,189,242,0.12) !important;
    z-index: 20 !important;
}
[data-testid="stSidebar"][aria-hidden="true"],
[data-testid="stSidebar"][aria-expanded="false"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
    left: 0 !important;
    width: 20rem !important;
    min-width: 20rem !important;
    max-width: 20rem !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 1.25rem;
    width: 100% !important;
}
[data-testid="stSidebar"] > div {
    width: 100% !important;
}
[data-testid="stSidebar"] [role="radiogroup"] {
    gap: 0.45rem;
}
[data-testid="stSidebar"] [data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebar"] button,
[data-testid="stSidebar"] [role="button"],
[data-testid="stSidebar"] [aria-label*="sidebar"],
[data-testid="stSidebar"] [aria-label*="colaps"],
[data-testid="stSidebar"] [aria-label*="expand"],
[data-testid="stSidebar"] [data-testid*="sidebar"] {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}
[data-testid="stSidebar"] label {
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--primary);
    padding: 0.72rem 0.8rem;
    transition: background 0.15s ease, border-color 0.15s ease, transform 0.12s ease;
}
[data-testid="stSidebar"] label:hover {
    background: var(--secondary);
    border-color: var(--accent);
    transform: translateX(2px);
}
[data-testid="stSidebar"] label:has(input:checked) {
    background: var(--secondary);
    border-color: var(--accent);
    box-shadow: inset 4px 0 0 var(--tertiary);
}

/* Main container */
.main .block-container {
    padding: 2rem 2.2rem 4rem !important;
    max-width: 1180px;
    animation: fadeSlide 0.45s ease-out !important;
}

@keyframes fadeSlide {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

.hero-banner {
    position: relative;
    border: 1px solid var(--border);
    border-left: 5px solid var(--tertiary);
    background: var(--primary);
    border-radius: 8px;
    padding: 1.2rem 1.35rem;
    margin-bottom: 1rem;
    box-shadow: 0 14px 32px rgba(120,189,242,0.16);
    overflow: hidden;
}
.hero-banner::before {
    content: "";
    position: absolute;
    width: 35%;
    height: 100%;
    right: 0;
    top: 0;
    background: linear-gradient(90deg, rgba(234,244,255,0), var(--secondary));
}
.hero-banner::after {
    content: "";
    position: absolute;
    width: 100%;
    height: 3px;
    left: 0;
    bottom: 0;
    background: linear-gradient(90deg, var(--accent), var(--tertiary));
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
    background: var(--primary) !important;
    border: 1px solid var(--border) !important;
    border-top: 4px solid var(--accent) !important;
    border-radius: 8px !important;
    padding: 1.25rem 1.5rem !important;
    box-shadow: 0 10px 24px rgba(120,189,242,0.14) !important;
    transition: transform 0.16s ease, box-shadow 0.16s ease !important;
    position: relative !important;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 12px 28px rgba(120,189,242,0.20) !important;
}
[data-testid="stMetric"]::after {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), var(--tertiary));
    opacity: 0.65;
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
    font-size: 2.45rem !important;
    color: var(--text) !important;
}

/* Tabs */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid var(--border) !important;
    gap: 0.4rem !important;
    padding: 0.3rem 0 !important;
}
[data-testid="stTabs"] button {
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: var(--text) !important;
    border: 1px solid transparent !important;
    background: var(--secondary) !important;
    border-radius: 8px !important;
    padding: 0.58rem 1.05rem !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #ffffff !important;
    background: var(--tertiary) !important;
    border-color: var(--tertiary) !important;
    box-shadow: 0 10px 20px rgba(37,99,235,0.20) !important;
}
[data-testid="stTabsContent"] {
    padding-top: 1.5rem !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stTimeInput"] input,
[data-testid="stDateInput"] input {
    background: #ffffff !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
    font-size: 0.875rem !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 4px rgba(120,189,242,0.22) !important;
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

/* Sliders */
[data-testid="stSlider"] {
    padding: 0.25rem 0 !important;
}
[data-testid="stSlider"] input[type="range"] {
    opacity: 1 !important;
    visibility: visible !important;
    display: block !important;
}
[data-testid="stSlider"] [role="slider"] {
    opacity: 1 !important;
    visibility: visible !important;
    background: var(--tertiary) !important;
    border: 2px solid #ffffff !important;
    box-shadow: 0 0 0 4px rgba(37,99,235,0.18) !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] {
    background: #dbeafe !important;
    border-radius: 999px !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] > div {
    background: var(--tertiary) !important;
    border-radius: 999px !important;
}

/* Botón principal */
[data-testid="stFormSubmitButton"] button,
.stButton button {
    background: var(--tertiary) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    padding: 0.72rem 1.5rem !important;
    transition: background 0.15s, box-shadow 0.15s, transform 0.1s !important;
    box-shadow: 0 10px 20px rgba(37,99,235,0.18) !important;
    position: relative !important;
    overflow: hidden !important;
}
[data-testid="stFormSubmitButton"] button *,
.stButton button * {
    color: #ffffff !important;
    fill: #ffffff !important;
}
[data-testid="stFormSubmitButton"] button:hover,
.stButton button:hover {
    background: #1d4ed8 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 14px 26px rgba(37,99,235,0.24) !important;
}
[data-testid="stFormSubmitButton"] button:active,
.stButton button:active {
    transform: translateY(0) !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
    box-shadow: 0 6px 16px rgba(120,189,242,0.12) !important;
    background: #ffffff !important;
}
[data-testid="stDataFrame"] * {
    color: var(--text) !important;
}
[data-testid="stDataFrame"] [role="gridcell"],
[data-testid="stDataFrame"] [role="columnheader"] {
    background: #ffffff !important;
    border-color: #e5e7eb !important;
}
[data-testid="stTable"] * {
    color: var(--text) !important;
    background: #ffffff !important;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: 5px !important;
    font-family: var(--sans) !important;
    font-size: 0.85rem !important;
    border-left: 3px solid var(--danger) !important;
}

/* Multiselect chips */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: var(--secondary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--accent) !important;
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
}

/* Form container */
[data-testid="stForm"] {
    background: var(--primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 1.5rem !important;
    box-shadow: 0 14px 30px rgba(120,189,242,0.14) !important;
    backdrop-filter: blur(2px) !important;
}

/* Elegant micro accents */
.stCaption code {
    background: var(--secondary) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 999px !important;
    padding: 0.08rem 0.45rem !important;
}

[data-testid="stAlert"] {
    box-shadow: 0 8px 18px rgba(120,189,242,0.12) !important;
}

/* Divider */
hr { border-color: var(--border) !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #b0b7c3; }
</style>
""".replace("__BG_IMAGE__", background_image_b64), unsafe_allow_html=True)


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
    Path(".streamlit/firebase-service-account.json"),
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


def build_attendance_row(doc, data):
    path_parts = doc.reference.path.split("/")
    fecha = (
        first_present(data, "fecha", "date", "dia", "fecha_dia")
        or path_value_after(path_parts, ("dias", "dia"))
        or doc.id
    )
    parsed_date = parse_iso_date(fecha)
    id_trabajador = first_present(
        data,
        "id_trabajador",
        "trabajador_id",
        "idTrabajador",
        "worker_id",
    ) or path_value_after(path_parts, ("trabajadores", "trabajador"))
    id_tienda = first_present(
        data,
        "id_tienda",
        "tienda_id",
        "idTienda",
        "store_id",
    ) or path_value_after(path_parts, ("tiendas", "tienda"))
    id_sede = first_present(
        data,
        "id_sede",
        "sede_id",
        "idSede",
    ) or path_value_after(path_parts, ("asistencias", "sedes", "sede"))

    entrada = data.get("entrada") if isinstance(data.get("entrada"), dict) else {}
    salida = data.get("salida") if isinstance(data.get("salida"), dict) else {}
    horario = data.get("horario") if isinstance(data.get("horario"), dict) else {}

    return {
        "doc_id": doc.id,
        "ruta": doc.reference.path,
        "fecha": fecha,
        "fecha_orden": parsed_date.isoformat() if parsed_date else "",
        "nombre_tienda": (
            first_present(data, "nombre_tienda", "tienda", "store_name")
            or entrada.get("nombre_tienda")
            or salida.get("nombre_tienda")
            or id_tienda
        ),
        "id_tienda": id_tienda or entrada.get("id_tienda") or salida.get("id_tienda"),
        "id_trabajador": id_trabajador,
        "nombre_trabajador": first_present(
            data,
            "nombre_trabajador",
            "trabajador",
            "nombre",
            "worker_name",
        ),
        "dni": first_present(data, "dni", "documento"),
        "hora_inicio": (
            first_present(data, "hora_inicio", "horaEntrada")
            or entrada.get("hora")
            or horario.get("hora_inicio")
        ),
        "inicio_receso": first_present(data, "inicio_receso", "inicioReceso"),
        "final_receso": first_present(data, "final_receso", "finalReceso"),
        "hora_final": (
            first_present(data, "hora_final", "hora_finalhas", "horaSalida")
            or salida.get("hora")
            or horario.get("hora_final")
        ),
        "ultima_marca": (
            first_present(data, "ultima_marca", "ultimaMarca", "estado")
            or salida.get("estado")
            or map_value(data, "refrigerio_fin", "estado")
            or map_value(data, "refrigerio_inicio", "estado")
            or entrada.get("estado")
        ),
        "id_sede": id_sede,
        "nombre_sede": (
            first_present(data, "nombre_sede", "sede")
            or entrada.get("nombre_sede")
            or salida.get("nombre_sede")
            or id_sede
        ),
        "horario_programado": (
            f"{horario.get('hora_inicio', '')} - {horario.get('hora_final', '')}"
            if horario else ""
        ),
    }


def stream_attendance_sources(db):
    seen_paths = set()

    for doc in db.collection(ATTENDANCE_COLLECTION).limit(250).stream():
        seen_paths.add(doc.reference.path)
        yield doc

    for collection_name in ("dias", "asistencias", "asistencia"):
        try:
            docs = db.collection_group(collection_name).stream()
            for doc in docs:
                if doc.reference.path in seen_paths:
                    continue
                seen_paths.add(doc.reference.path)
                yield doc
        except Exception:
            continue


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
        for key in ["firebase", "firebase_service_account", "google_service_account"]:
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
    for key in ["firebase", "firebase_service_account", "google_service_account"]:
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
    asistencias = []

    for doc in stream_attendance_sources(db):
        asistencias.append(build_attendance_row(doc, doc.to_dict() or {}))

    unique_rows = {item["ruta"]: item for item in asistencias}
    return sorted(
        unique_rows.values(),
        key=lambda item: item["fecha_orden"] or item["fecha"],
        reverse=True,
    )


@st.cache_data(ttl=10, show_spinner=False)
def get_asistencias_trabajador(id_trabajador):
    db = get_firestore_client()
    asistencias = []

    docs = (
        db.collection(ATTENDANCE_COLLECTION)
        .where("id_trabajador", "==", id_trabajador)
        .stream()
    )
    for doc in docs:
        asistencias.append(build_attendance_row(doc, doc.to_dict() or {}))

    for doc in stream_attendance_sources(db):
        row = build_attendance_row(doc, doc.to_dict() or {})
        if str(row["id_trabajador"]) == str(id_trabajador):
            asistencias.append(row)

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


def build_schedule_inputs(selected_days):
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
        document_exists=document_exists,
        firestore=firestore,
        format_time=format_time,
        get_asistencias=get_asistencias,
        get_tiendas=get_tiendas,
        get_trabajadores=get_trabajadores,
        normalize_doc_id=normalize_doc_id,
        normalize_email=normalize_email,
        required_missing=required_missing,
        section_header=section_header,
        upload_worker_file=upload_worker_file,
        worker_attendance_dialog=worker_attendance_dialog,
    )


# ── Página principal ───────────────────────────────────────────────────────────
def admin_page():
    pages = {
        "Resumen": render_overview,
        "Tiendas": render_tiendas,
        "Trabajadores": render_trabajadores,
        "Asistencias": render_asistencias,
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
                        Sistema de Asistencia · Firebase Firestore
                    </div>
                </div>
            </div>
            <div style="font-family:'Space Mono',monospace;font-size:0.64rem;letter-spacing:0.08em;
                        text-transform:uppercase;padding:0.38rem 0.7rem;border-radius:8px;
                        color:#ffffff;background:#e53935;">
                {current_page}
            </div>
        </div>
    </div>
    <hr style="margin: 0.85rem 0 1.5rem; border-color:#cfe3f7;">
    """.replace("{current_page}", current_page), unsafe_allow_html=True)

    try:
        get_firestore_client()
    except Exception as exc:
        st.error(f"No se pudo conectar con Firebase: {exc}")
        st.stop()

    pages[current_page](build_section_context())


def main():
    if not is_authenticated():
        render_login()
        return
    admin_page()


if __name__ == "__main__":
    main()
