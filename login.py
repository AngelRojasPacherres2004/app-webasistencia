import base64
import hmac
import re
from pathlib import Path

import streamlit as st

from supabase_backend import list_admin_rows, verify_password

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


def _validate_login_input(username, password):
    user = str(username or "").strip()
    pwd = str(password or "")
    if not user or not pwd:
        return "Debes completar correo y contrasena."
    return None


def _check_credentials(input_user, input_pass):
    username = str(input_user or "").strip().lower()
    password = str(input_pass or "")
    if not username or not password:
        return False

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
        /* Reset de fondos de Streamlit para ver el video */
        [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main .block-container {{
            background: transparent !important;
        }}
        
        /* Contenedor del Video de fondo */
        .login-video-wrap {{
            position: fixed;
            inset: 0;
            z-index: -2;
            overflow: hidden;
        }}
        
        .login-video-wrap video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        /* Capa de filtro (Ligero filtro oscuro de antes) */
        .login-overlay {{
            content: "";
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.34) !important;
            z-index: -1;
        }}

        .main .block-container {{
            position: relative;
            z-index: 10;
            padding-top: 10vh !important;
        }}

        /* Tarjeta de Login (Glassmorphism) */
        [data-testid="stForm"] {{
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 28px !important;
            padding: 3rem 2.5rem !important;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5) !important;
        }}

        .login-logo {{
            text-align: center;
            margin-bottom: 2rem;
        }}

        .login-logo h1 {{
            font-family: 'Space Mono', monospace !important;
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            color: #ffffff !important;
            letter-spacing: -0.05em !important;
            margin: 0 !important;
            border: none !important;
            padding: 0 !important;
        }}

        .login-logo p {{
            font-family: 'DM Sans', sans-serif !important;
            font-size: 0.9rem !important;
            color: #94a3b8 !important;
            margin-top: 0.5rem !important;
        }}

        /* Inputs con estilo moderno */
        [data-testid="stTextInput"] label {{
            color: #cbd5e1 !important;
            font-family: 'Space Mono', monospace !important;
            font-size: 0.75rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.1em !important;
            margin-bottom: 0.5rem !important;
        }}

        [data-testid="stTextInput"] input {{
            background: rgba(255, 255, 255, 0.85) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: #000000 !important;
            border-radius: 12px !important;
            padding: 0.75rem 1rem !important;
        }}

        /* Botón de entrada */
        .stButton button {{
            background: transparent !important;
            color: #ffffff !important;
            font-family: 'Space Mono', monospace !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            padding: 0.75rem !important;
            margin-top: 1.5rem !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
            transition: all 0.3s ease !important;
        }}

        .stButton button:hover {{
            background: rgba(255, 255, 255, 0.15) !important;
            transform: translateY(-2px) !important;
            border-color: rgba(255, 255, 255, 0.4) !important;
        }}
        </style>

        <div class="login-video-wrap">
            <video autoplay muted loop playsinline>
                <source src="data:video/mp4;base64,{login_video_b64}" type="video/mp4">
            </video>
        </div>
        <div class="login-overlay"></div>
        """,
        unsafe_allow_html=True,
    )

    _, center, _ = st.columns([1, 1.5, 1])
    with center:
        with st.form("admin_login_form", clear_on_submit=False):
            st.markdown(
                """
                <div class="login-logo">
                    <h1>⬡ ADMIN</h1>
                    <p>Gestión de Asistencia y Personal</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            username = st.text_input("Usuario / Correo", placeholder="admin@empresa.com")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Entrar al Panel", use_container_width=True)

        if submit:
            try:
                input_error = _validate_login_input(username, password)
                if input_error:
                    st.error(input_error)
                    return

                if _check_credentials(username, password):
                    st.session_state[SESSION_AUTH_KEY] = True
                    st.session_state[SESSION_USER_KEY] = username.strip()
                    st.success("Acceso correcto.")
                    st.rerun()
                    return

                st.error("Correo o contrasena incorrectos.")
            except Exception as exc:
                st.error(f"Error al iniciar sesion: {exc}")
