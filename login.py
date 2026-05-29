import base64
import hmac
import json
from pathlib import Path

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore

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


SESSION_AUTH_KEY = "admin_authenticated"
SESSION_USER_KEY = "admin_username"
ADMIN_COLLECTION = "administrador"
LOGIN_VIDEO_PATH = Path("fondologin.mp4")
SECRET_JSON_PATHS = (
    Path(".streamlit/secrets.toml"),
    Path(".streamlit/secret.toml"),
    Path(".streamlit/firebase-service-account.json"),
)


def is_authenticated():
    return bool(st.session_state.get(SESSION_AUTH_KEY, False))


def logout():
    st.session_state[SESSION_AUTH_KEY] = False
    st.session_state[SESSION_USER_KEY] = ""


def _clean_service_account(service_account):
    if not service_account or not isinstance(service_account, dict):
        return service_account
    if "private_key" in service_account and isinstance(service_account["private_key"], str):
        key = service_account["private_key"].strip().strip('"').strip("'").strip()
        key = key.replace("\\n", "\n")
        if "-----BEGIN" in key:
            key = "-----BEGIN" + key.split("-----BEGIN")[-1]
        if "-----END PRIVATE KEY-----" in key:
            key = key.split("-----END PRIVATE KEY-----")[0] + "-----END PRIVATE KEY-----"
        service_account["private_key"] = key.strip()
    return service_account


def _load_service_account_file(path):
    raw_content = path.read_text(encoding="utf-8-sig").strip()
    if raw_content.startswith("{"):
        service_account, _ = json.JSONDecoder().raw_decode(raw_content)
        return _clean_service_account(service_account)
    parsed = tomllib.loads(raw_content)
    for key in ["firebase", "firebase_service_account", "google_service_account"]:
        if key in parsed:
            return _clean_service_account(dict(parsed[key]))
    if "type" in parsed and "project_id" in parsed:
        return _clean_service_account(parsed)
    return None


def _firebase_service_account_from_sources():
    try:
        for key in ["firebase", "firebase_service_account", "google_service_account"]:
            if key in st.secrets:
                return _clean_service_account(dict(st.secrets[key]))
        root = dict(st.secrets)
        if "type" in root and "project_id" in root and "private_key" in root:
            return _clean_service_account(root)
    except Exception:
        pass

    for json_path in SECRET_JSON_PATHS:
        if json_path.exists():
            loaded = _load_service_account_file(json_path)
            if loaded:
                return loaded
    return None


def _get_auth_firestore_client():
    service_account = _firebase_service_account_from_sources()
    if not service_account:
        return None

    project_id = service_account.get("project_id")
    if not project_id:
        return None

    if firebase_admin._apps:
        current_app = firebase_admin.get_app()
        if current_app.project_id != project_id:
            firebase_admin.delete_app(current_app)
        else:
            return firestore.client()

    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def _get_admin_credentials_from_secrets():
    try:
        auth = st.secrets.get("admin_auth", {})
        username = str(auth.get("username", "")).strip()
        password = str(auth.get("password", "")).strip()
        if username and password:
            return username, password
    except Exception:
        pass
    return None, None


def _is_admin_identifier_match(doc_id, data, username):
    user_lower = username.lower()
    id_candidates = []

    for key in [
        "usuario", "user", "username", "correo", "email", "mail",
        "login", "admin", "nombre_usuario", "id", "id_admin",
    ]:
        value = data.get(key)
        if value:
            id_candidates.append(str(value).strip())

    id_candidates.append(str(doc_id).strip())

    for key, value in data.items():
        key_norm = str(key).lower().replace("ñ", "n")
        if any(token in key_norm for token in ["user", "correo", "email", "mail", "login"]):
            if value:
                id_candidates.append(str(value).strip())

    return any(
        hmac.compare_digest(user_lower, candidate.lower())
        for candidate in id_candidates
        if candidate
    )


def _is_admin_password_match(data, password):
    pass_candidates = []
    for key in ["password", "contrasena", "contraseña", "clave", "pass"]:
        value = data.get(key)
        if value is not None:
            pass_candidates.append(str(value))

    for key, value in data.items():
        key_norm = str(key).lower().replace("ñ", "n")
        if any(token in key_norm for token in ["pass", "contra", "clave"]) and value is not None:
            pass_candidates.append(str(value))

    return any(hmac.compare_digest(password, stored) for stored in pass_candidates)


def _check_credentials(input_user, input_pass):
    username = str(input_user or "").strip()
    password = str(input_pass or "")
    if not username or not password:
        return False

    try:
        db = _get_auth_firestore_client()
        if db is not None:
            docs = db.collection(ADMIN_COLLECTION).stream()
            for admin_doc in docs:
                data = admin_doc.to_dict() or {}
                if not bool(data.get("activo", True)):
                    continue
                if not _is_admin_identifier_match(admin_doc.id, data, username):
                    continue
                if _is_admin_password_match(data, password):
                    return True
    except Exception:
        pass

    admin_user, admin_pass = _get_admin_credentials_from_secrets()
    if admin_user and admin_pass:
        return (
            hmac.compare_digest(username.lower(), admin_user.lower())
            and hmac.compare_digest(password, admin_pass)
        )

    return hmac.compare_digest(username, "admin") and hmac.compare_digest(password, "admin123")


def render_login():
    login_video_b64 = ""
    if LOGIN_VIDEO_PATH.exists():
        login_video_b64 = base64.b64encode(LOGIN_VIDEO_PATH.read_bytes()).decode("utf-8")

    st.markdown(
        f"""
        <style>
        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {{
            background: transparent !important;
        }}
        [data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .main .block-container {{
            position: relative;
            z-index: 20;
        }}
        .login-video-wrap {{
            position: fixed;
            inset: 0;
            z-index: -20;
            overflow: hidden;
            pointer-events: none;
        }}
        .login-video-wrap video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            filter: saturate(0.95) contrast(0.95);
        }}
        .login-video-overlay {{
            position: fixed;
            inset: 0;
            z-index: -10;
            background: rgba(0, 0, 0, 0.34);
            pointer-events: none;
        }}
        .login-head {{
            max-width: 460px;
            margin: 3.2rem auto 1rem;
            padding: 1.05rem 1.1rem;
            border: 1px solid #d4d4d8;
            border-radius: 14px;
            background: #ffffff;
            box-shadow: 0 12px 28px rgba(15,23,42,0.10);
        }}
        [data-testid="stForm"] {{
            background: #ffffff !important;
            opacity: 1 !important;
            border: 1px solid #d4d4d8 !important;
            box-shadow: 0 14px 30px rgba(15,23,42,0.20) !important;
        }}
        [data-testid="stForm"] * {{
            opacity: 1 !important;
        }}
        </style>
        <div class="login-video-wrap">
            <video autoplay muted loop playsinline>
                <source src="data:video/mp4;base64,{login_video_b64}" type="video/mp4">
            </video>
        </div>
        <div class="login-video-overlay"></div>
        <div class="login-head">
            <div style="font-family:'Space Mono',monospace;font-size:1.05rem;color:#0b0b0b;letter-spacing:0.03em;">
                Login Administrador
            </div>
            <div style="font-size:0.81rem;color:#3f3f46;margin-top:0.2rem;">
                Ingresa usuario o correo y tu clave.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1.25, 2.5, 1.25])
    with center:
        with st.form("admin_login_form", clear_on_submit=False):
            username = st.text_input("Usuario o correo", placeholder="admin@gmail.com")
            password = st.text_input("Contrasena", type="password", placeholder="********")
            submit = st.form_submit_button("Iniciar sesion", use_container_width=True)

        if submit:
            if _check_credentials(username, password):
                st.session_state[SESSION_AUTH_KEY] = True
                st.session_state[SESSION_USER_KEY] = username.strip()
                st.success("Acceso correcto.")
                st.rerun()
            else:
                st.error("Usuario/correo o contrasena incorrectos.")

        st.caption(
            "Coleccion `administrador`: acepta identificador por `usuario`, `correo` o id del documento."
        )
        st.caption(
            "Clave aceptada en campos: `password`, `contrasena`, `contraseña`, `clave`, `pass`."
        )
