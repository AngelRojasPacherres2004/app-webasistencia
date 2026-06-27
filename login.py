import hashlib
import hmac
import json
from pathlib import Path
from urllib.parse import quote, unquote

import streamlit as st
import streamlit.components.v1 as components

from supabase_backend import get_admin_by_email, verify_password

SESSION_AUTH_KEY = "admin_authenticated"
SESSION_USER_KEY = "admin_username"
SESSION_TOKEN_KEY = "admin_auth_token"
LOGIN_VIDEO_PATH = Path("fondologin.mp4")
AUTH_QUERY_PARAM = "auth"


def is_authenticated():
    return bool(st.session_state.get(SESSION_AUTH_KEY, False))


def _get_auth_secret():
    try:
        secret = str(st.secrets.get("auth_secret", "")).strip()
        if secret:
            return secret
    except Exception:
        pass

    try:
        from config.db import load_env

        load_env()
        fallback = str(st.secrets.get("database_url", "")).strip()
    except Exception:
        fallback = ""

    if fallback:
        return hashlib.sha256(fallback.encode("utf-8")).hexdigest()

    return "web_appasistencia_auth_secret"


def _sign_payload(payload: str) -> str:
    secret = _get_auth_secret().encode("utf-8")
    digest = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest


def _build_auth_token(username: str) -> str:
    payload = json.dumps({"u": str(username or "").strip().lower()}, separators=(",", ":"))
    signature = _sign_payload(payload)
    return f"{quote(payload)}.{signature}"


def _verify_auth_token(token: str):
    raw_token = str(token or "").strip()
    if not raw_token or "." not in raw_token:
        return None

    encoded_payload, signature = raw_token.rsplit(".", 1)
    try:
        payload = unquote(encoded_payload)
        expected_signature = _sign_payload(payload)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        data = json.loads(payload)
        username = str(data.get("u", "")).strip().lower()
        return username or None
    except Exception:
        return None


def _apply_authenticated_state(username: str, token: str | None = None):
    st.session_state[SESSION_AUTH_KEY] = True
    st.session_state[SESSION_USER_KEY] = str(username or "").strip()
    if token:
        st.session_state[SESSION_TOKEN_KEY] = token
    st.query_params[AUTH_QUERY_PARAM] = token or _build_auth_token(username)


def logout():
    st.session_state[SESSION_AUTH_KEY] = False
    st.session_state[SESSION_USER_KEY] = ""
    st.session_state.pop(SESSION_TOKEN_KEY, None)
    try:
        if AUTH_QUERY_PARAM in st.query_params:
            del st.query_params[AUTH_QUERY_PARAM]
    except Exception:
        pass


def hydrate_auth_from_query_params():
    token = ""
    try:
        token = st.query_params.get(AUTH_QUERY_PARAM, "")
        if isinstance(token, list):
            token = token[0] if token else ""
    except Exception:
        token = ""

    if st.session_state.get(SESSION_AUTH_KEY):
        return True

    username = _verify_auth_token(token)
    if not username:
        return False

    admin_row = get_admin_by_email(username)
    if not admin_row:
        return False

    _apply_authenticated_state(username, token=str(token))
    return True


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

    admin_row = get_admin_by_email(username)
    if admin_row:
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


def _render_login_content():
    # Paint a lightweight layer before the streamed video becomes ready. It
    # immediately covers Streamlit's stale dashboard during logout.
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] > .main {
            position: relative !important;
            z-index: 1100 !important;
        }

        [data-testid="stHeader"] {
            z-index: 1200 !important;
        }

        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }

        [data-testid="stElementContainer"] {
            opacity: 1 !important;
            transition: none !important;
        }

        .login-transition-cover {
            position: fixed;
            inset: 0;
            z-index: 1099;
            background:
                radial-gradient(circle at 18% 25%, rgba(148, 163, 184, 0.20), transparent 30%),
                radial-gradient(circle at 82% 70%, rgba(203, 213, 225, 0.28), transparent 34%),
                #e9ece8;
            pointer-events: none;
        }

        [data-testid="stVideo"] {
            position: fixed !important;
            inset: 0 !important;
            z-index: 1100 !important;
            width: 100vw !important;
            height: 100vh !important;
            object-fit: cover !important;
            object-position: center center !important;
            display: block !important;
            pointer-events: none !important;
        }

        [data-testid="stVideo"]::-webkit-media-controls,
        [data-testid="stVideo"]::-webkit-media-controls-enclosure,
        [data-testid="stVideo"]::-webkit-media-controls-overlay-enclosure,
        [data-testid="stVideo"]::-webkit-media-controls-panel,
        [data-testid="stVideo"]::-webkit-media-controls-overlay-play-button,
        [data-testid="stVideo"]::-webkit-media-controls-start-playback-button,
        [data-testid="stVideo"]::-webkit-media-controls-timeline,
        [data-testid="stVideo"]::-webkit-media-controls-current-time-display,
        [data-testid="stVideo"]::-webkit-media-controls-time-remaining-display,
        [data-testid="stVideo"]::-webkit-media-controls-mute-button,
        [data-testid="stVideo"]::-webkit-media-controls-fullscreen-button {
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
        }

        [data-testid="stVideo"] video {
            width: 100vw !important;
            height: 100vh !important;
            object-fit: cover !important;
        }

        .login-overlay {
            position: fixed;
            inset: 0;
            z-index: 1101;
            background: rgba(0, 0, 0, 0.34);
            pointer-events: none;
        }

        [data-testid="stForm"] {
            position: relative !important;
            z-index: 1102 !important;
        }

        [data-testid="stHorizontalBlock"]:has([data-testid="stForm"]) {
            position: relative !important;
            z-index: 1102 !important;
        }
        </style>
        <div class="login-transition-cover"></div>
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
                unsafe_allow_html=True,
            )
            username = st.text_input("Usuario / Correo", placeholder="admin@empresa.com")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Entrar al Panel", use_container_width=True)

        if submit:
            try:
                input_error = _validate_login_input(username, password)
                if input_error:
                    st.error(input_error)
                elif _check_credentials(username, password):
                    auth_token = _build_auth_token(username)
                    _apply_authenticated_state(username, auth_token)
                    return True
                else:
                    st.error("Correo o contrasena incorrectos.")
            except Exception as exc:
                st.error(f"Error al iniciar sesion: {exc}")

    if LOGIN_VIDEO_PATH.exists():
        components.html(
            """
            <script>
            (() => {
                const parentDocument = window.parent.document;

                const configureLoginVideo = () => {
                    const video = parentDocument.querySelector('[data-testid="stVideo"]');
                    if (!video) return false;

                    video.controls = false;
                    video.removeAttribute("controls");
                    video.setAttribute("playsinline", "");
                    video.setAttribute(
                        "controlslist",
                        "nodownload nofullscreen noremoteplayback"
                    );
                    video.disablePictureInPicture = true;
                    video.muted = true;
                    video.loop = true;
                    video.autoplay = true;
                    video.play().catch(() => {});
                    return true;
                };

                if (parentDocument.documentElement.dataset.loginSubmitHandler !== "true") {
                    parentDocument.documentElement.dataset.loginSubmitHandler = "true";
                    parentDocument.addEventListener("click", (event) => {
                        const button = event.target.closest?.(
                            '[data-testid="stForm"] button[type="submit"]'
                        );
                        if (!button) return;

                        button.style.cursor = "wait";
                        const label = button.querySelector("p");
                        if (label) label.textContent = "Ingresando…";
                    }, true);
                }

                const configureLogin = () => {
                    configureLoginVideo();
                };

                const observer = new MutationObserver(configureLogin);
                observer.observe(parentDocument.documentElement, {
                    childList: true,
                    subtree: true,
                });
                window.addEventListener("unload", () => observer.disconnect());
                configureLogin();
            })();
            </script>
            """,
            height=0,
            width=0,
        )
        st.video(
            str(LOGIN_VIDEO_PATH),
            format="video/mp4",
            autoplay=True,
            muted=True,
            loop=True,
        )

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"], [data-testid="stHeader"], .main .block-container {{
            background: transparent !important;
        }}

        [data-testid="stAppViewContainer"] > .main {{
            position: relative !important;
            z-index: 1100 !important;
        }}

        [data-testid="stHeader"] {{
            z-index: 1200 !important;
        }}

        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {{
            display: none !important;
        }}

        [data-testid="stVideo"] {{
            position: fixed;
            inset: 0;
            z-index: 1100;
            overflow: hidden;
            background: transparent;
            object-fit: cover !important;
            object-position: center center !important;
            display: block !important;
            pointer-events: none;
        }}

        [data-testid="stVideo"]::-webkit-media-controls,
        [data-testid="stVideo"]::-webkit-media-controls-enclosure,
        [data-testid="stVideo"]::-webkit-media-controls-overlay-enclosure,
        [data-testid="stVideo"]::-webkit-media-controls-panel,
        [data-testid="stVideo"]::-webkit-media-controls-overlay-play-button,
        [data-testid="stVideo"]::-webkit-media-controls-start-playback-button {{
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
        }}

        [data-testid="stVideo"] video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            background: transparent;
        }}

        .login-overlay {{
            content: "";
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.34) !important;
            z-index: 1101;
            pointer-events: none;
        }}

        .main .block-container {{
            position: relative;
            z-index: 10;
            padding-top: 10vh !important;
        }}

        [data-testid="stForm"] {{
            position: relative !important;
            z-index: 1102 !important;
            background: rgba(255, 255, 255, 0.05) !important;
            backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 28px !important;
            padding: 3rem 2.5rem !important;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5) !important;
        }}

        [data-testid="stHorizontalBlock"]:has([data-testid="stForm"]) {{
            position: relative !important;
            z-index: 1102 !important;
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

        [data-testid="stTextInput"] label p {{
            color: #ffffff !important;
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
        """,
        unsafe_allow_html=True,
    )

    return False


def render_login():
    """Render the login and return its placeholder for a clean transition."""
    login_placeholder = st.empty()
    with login_placeholder.container():
        authenticated = _render_login_content()

    return authenticated, login_placeholder
