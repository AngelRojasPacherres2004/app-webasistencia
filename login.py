import base64
import hmac
from pathlib import Path

import streamlit as st

from supabase_backend import get_admin_login_diagnostics, list_admin_rows, verify_password

SESSION_AUTH_KEY = "admin_authenticated"
SESSION_USER_KEY = "admin_username"
LOGIN_VIDEO_PATH = Path("fondologin.mp4")


def is_authenticated():
    return bool(st.session_state.get(SESSION_AUTH_KEY, False))


def logout():
    st.session_state[SESSION_AUTH_KEY] = False
    st.session_state[SESSION_USER_KEY] = ""


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
    username = str(input_user or "").strip().lower()
    password = str(input_pass or "")
    if not username or not password:
        return False

    try:
        for admin_row in list_admin_rows():
            correo = str((admin_row or {}).get("correo", "")).strip().lower()
            if not correo:
                continue
            if not hmac.compare_digest(correo, username):
                continue
            stored_password = (
                admin_row.get("contrasena")
                or admin_row.get("password")
                or admin_row.get("contraseña")
                or admin_row.get("clave")
                or ""
            )
            if verify_password(stored_password, password):
                return True
    except Exception:
        return False

    admin_user, admin_pass = _get_admin_credentials_from_secrets()
    if admin_user and admin_pass:
        return (
            hmac.compare_digest(username, admin_user.lower())
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
                Ingresa tu correo y contraseña.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1.25, 2.5, 1.25])
    with center:
        with st.form("admin_login_form", clear_on_submit=False):
            username = st.text_input("Correo", placeholder="admin@empresa.com")
            password = st.text_input("Contraseña", type="password", placeholder="********")
            submit = st.form_submit_button("Iniciar sesión", use_container_width=True)

        if submit:
            if _check_credentials(username, password):
                st.session_state[SESSION_AUTH_KEY] = True
                st.session_state[SESSION_USER_KEY] = username.strip()
                st.success("Acceso correcto.")
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos.")
                with st.expander("Diagnóstico de PostgreSQL", expanded=True):
                    diag = get_admin_login_diagnostics()
                    st.write({
                        "conectado": diag["connected"],
                        "tabla": diag["table"],
                        "filas_leidas": diag["row_count"],
                        "correos_vistos": diag["sample_emails"],
                    })
                    if diag["error"]:
                        st.error(diag["error"])
