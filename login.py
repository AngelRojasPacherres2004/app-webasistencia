import hmac
import base64
from pathlib import Path

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore


SESSION_AUTH_KEY = "admin_authenticated"
SESSION_USER_KEY = "admin_username"
ADMIN_COLLECTION = "administrador"
LOGIN_VIDEO_PATH = Path("fondologin.mp4")


def is_authenticated():
    return bool(st.session_state.get(SESSION_AUTH_KEY, False))


def logout():
    st.session_state[SESSION_AUTH_KEY] = False
    st.session_state[SESSION_USER_KEY] = ""


def _firebase_service_account_from_secrets():
    try:
        for key in ["firebase", "firebase_service_account", "google_service_account"]:
            if key in st.secrets:
                return dict(st.secrets[key])

        # Soporta secrets en formato JSON raíz
        root = dict(st.secrets)
        if "type" in root and "project_id" in root and "private_key" in root:
            return root
    except Exception:
        return None
    return None


def _get_auth_firestore_client():
    service_account = _firebase_service_account_from_secrets()
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


def _check_credentials(input_user, input_pass):
    username = str(input_user or "").strip()
    password = str(input_pass or "")
    if not username or not password:
        return False

    # 1) Intenta autenticar con Firebase (coleccion: administrador)
    try:
        db = _get_auth_firestore_client()
        if db is not None:
            docs = (
                db.collection(ADMIN_COLLECTION)
                .where("usuario", "==", username)
                .limit(1)
                .stream()
            )
            admin_doc = next(docs, None)
            if admin_doc:
                data = admin_doc.to_dict() or {}
                stored_password = str(data.get("password") or data.get("contrasena") or "")
                is_active = bool(data.get("activo", True))
                if is_active and stored_password:
                    return hmac.compare_digest(password, stored_password)
    except Exception:
        pass

    # 2) Fallback a secrets
    admin_user, admin_pass = _get_admin_credentials_from_secrets()
    if admin_user and admin_pass:
        return (
            hmac.compare_digest(username, admin_user)
            and hmac.compare_digest(password, admin_pass)
        )

    # 3) Fallback temporal local
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
            background: linear-gradient(180deg, #ffffff, #f8fafc);
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
                Ingresa tus credenciales para acceder al panel.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1.25, 2.5, 1.25])
    with center:
        with st.form("admin_login_form", clear_on_submit=False):
            username = st.text_input("Usuario", placeholder="admin")
            password = st.text_input("Contrasena", type="password", placeholder="********")
            submit = st.form_submit_button("Iniciar sesion", use_container_width=True)

        if submit:
            if _check_credentials(username, password):
                st.session_state[SESSION_AUTH_KEY] = True
                st.session_state[SESSION_USER_KEY] = username.strip()
                st.success("Acceso correcto.")
                st.rerun()
            else:
                st.error("Usuario o contrasena incorrectos.")

        st.caption(
            "Login con Firebase coleccion `administrador` (campos: `usuario`, `password`/`contrasena`, `activo`)."
        )
        st.caption(
            "Si no existe ese usuario en Firebase, usa fallback de `secrets` ([admin_auth]) o temporal: admin/admin123."
        )
