import os
import resend
from html import escape
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# ================================================================
#  HELPERS
# ================================================================

def _build_message_html(body: str) -> str:
    safe_body = escape(str(body or "").strip()).replace("\n", "<br/>")
    return f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#0f172a;">
        <p>{safe_body}</p>
    </div>
    """


def _get_absent_workers_today(api) -> list[dict]:
    """Devuelve trabajadores que no han marcado asistencia hoy."""
    today_str = date.today().isoformat()

    trabajadores = api.get_trabajadores()
    asistencias  = api.get_asistencias()

    # DNIs que ya marcaron hoy
    marked_today = {
        str(a.get("dni", "")).strip()
        for a in asistencias
        if str(a.get("fecha", ""))[:10] == today_str
    }

    absent = []
    for w in trabajadores:
        dni = str(w.get("dni", "")).strip()
        if not w.get("estado", True):
            continue
        day_name_map = {
            0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves",
            4: "viernes", 5: "sabado", 6: "domingo",
        }
        today_day = day_name_map[date.today().weekday()]
        dias = [d.lower() for d in (w.get("dias_horario") or [])]
        if today_day not in dias:
            continue
        if dni not in marked_today:
            absent.append(w)

    return absent

def _build_absent_message(absent_workers: list[dict], store_label: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/Lima"))
    today_str = now.strftime("%d/%m/%Y")
    hour_str  = now.strftime("%H:%M")

    tienda_txt = store_label.split(" · ")[0] if " · " in store_label else store_label
    if tienda_txt == "Todas":
        tienda_txt = "todas las tiendas"

    lines = [
        f"Trabajadores sin asistencia hoy {today_str} a las {hour_str} — {tienda_txt}:",
        "",
    ]
    for i, w in enumerate(absent_workers, 1):
        nombre = w.get("nombre_trabajador", "-")
        sede   = w.get("nombre_sede", "-")
        cargo  = w.get("area") or w.get("cargo", "-")
        lines.append(f"{i}. {nombre} — {sede} — {cargo}")

    if not absent_workers:
        lines.append("¡Todos han marcado asistencia hoy!")

    return "\n".join(lines)
# ================================================================
#  VISTA PRINCIPAL
# ================================================================

def render_correo(api=None):
    st.markdown(
        """
        <div style="margin-bottom:24px;">
            <h2 class="page-title">Correo</h2>
            <p class="page-subtitle">Enviar un mensaje desde Resend a cualquier destinatario</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_key        = os.getenv("RESEND_API_KEY", "").strip()
    sender_default = os.getenv("RESEND_FROM", "").strip()

    if not api_key:
        st.error("Falta `RESEND_API_KEY` en tu archivo `.env`.")
        return
    if not sender_default:
        st.error("Falta `RESEND_FROM` en tu archivo `.env`.")
        return

    resend.api_key = api_key
    st.info(f"Remitente configurado: `{sender_default}`")

    # ── Sección: ausentes de hoy ──────────────────────────────────
    if api is not None:
        st.markdown("### Ausentes hoy")

        tiendas = api.get_tiendas()
        store_options = {"Todas": None}
        store_options.update({
            f"{t['nombre_tienda']} ": t for t in tiendas
        })

        selected_store_label = st.selectbox(
            "Filtrar por tienda",
            options=list(store_options.keys()),
            index=0,
            key="correo_store_filter",
        )

        absent_workers = _get_absent_workers_today(api)

        # Filtrar por tienda si se seleccionó una
        if selected_store_label != "Todas":
            store = store_options[selected_store_label]
            absent_workers = [
                w for w in absent_workers
                if str(w.get("id_sede", "")).strip() == str(store["id_tienda"]).strip()
            ]

        if absent_workers:
            st.warning(f"{len(absent_workers)} trabajador(es) sin asistencia hoy.")
            rows = [
                {
                    "Nombre":  w.get("nombre_trabajador", "-"),
                    "DNI":     w.get("dni", "-"),
                    "Sede":    w.get("nombre_sede", "-"),
                    "Cargo":   w.get("area") or w.get("cargo", "-"),
                }
                for w in absent_workers
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.success("Todos los trabajadores han marcado asistencia hoy.")

        absent_message_text = _build_absent_message(absent_workers, selected_store_label)

        if st.button("Usar lista de ausentes como mensaje", use_container_width=True):
            st.session_state["correo_prefill_message"] = absent_message_text
            st.session_state["correo_prefill_subject"] = (
                f"Ausentes {date.today().strftime('%d/%m/%Y')} — "
                f"{selected_store_label if selected_store_label != 'Todas' else 'Todas las tiendas'}"
            )
            st.rerun()

        st.markdown("---")

    if "correo_prefill_message" in st.session_state:
        st.session_state["correo_subject_val"] = st.session_state.pop("correo_prefill_subject", "")
        st.session_state["correo_message_val"] = st.session_state.pop("correo_prefill_message", "")

    with st.form("resend_email_form", clear_on_submit=False):
        col_left, col_right = st.columns(2)
        sender = col_left.text_input(
            "Remitente",
            value=sender_default,
            help="Debe ser un remitente autorizado en Resend.",
        )
        recipient = col_right.text_input(
            "Destinatario",
            placeholder="cliente@gmail.com",
        )
        subject = st.text_input(
            "Asunto",
            placeholder="Aviso de asistencia",
            key="correo_subject_val",
        )
        message = st.text_area(
            "Mensaje",
            placeholder="Escribe aqui el contenido del correo...",
            height=180,
            key="correo_message_val",
        )
        submitted = st.form_submit_button("Enviar correo", use_container_width=True)

    if not submitted:
        return

    if not str(sender or "").strip():
        st.error("Debes indicar un remitente.")
        return
    if not str(recipient or "").strip():
        st.error("Debes indicar un destinatario.")
        return
    if not str(subject or "").strip():
        st.error("Debes indicar un asunto.")
        return
    if not str(message or "").strip():
        st.error("Debes escribir un mensaje.")
        return

    try:
        response = resend.Emails.send({
            "from":    sender.strip(),
            "to":      [recipient.strip()],
            "subject": subject.strip(),
            "html":    _build_message_html(message),
            "text":    message.strip(),
        })

        message_id = ""
        if isinstance(response, dict):
            message_id = str(response.get("id", "")).strip()
        else:
            message_id = str(getattr(response, "id", "") or "").strip()

        if message_id:
            st.success(f"Correo enviado correctamente. ID: `{message_id}`")
        else:
            st.success("Correo enviado correctamente.")

    except Exception as exc:
        st.error(f"No se pudo enviar el correo: {exc}")