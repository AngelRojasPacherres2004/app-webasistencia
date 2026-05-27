from datetime import date, timedelta

import streamlit as st

# ── Constantes (deben coincidir con admin.py) ──────────────────────────────────
ATTENDANCE_COLLECTION = "asistencia"
WORKER_COLLECTION     = "trabajador"
STORE_COLLECTION      = "tienda"

WEEK_DAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


# ── CSS (mismo tema que admin.py) ──────────────────────────────────────────────
SHARED_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg:      #f5f6fa;
    --surface: #ffffff;
    --border:  #dde1ea;
    --accent:  #2563eb;
    --text:    #111827;
    --muted:   #6b7280;
    --mono:    'Space Mono', monospace;
    --sans:    'DM Sans', sans-serif;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
}
[data-testid="stHeader"]  { background: transparent !important; }
[data-testid="stToolbar"] { display: none; }
.main .block-container    { padding: 2rem 2.5rem 4rem !important; max-width: 1300px; }

/* Métricas */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-top: 3px solid var(--accent) !important;
    border-radius: 6px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
}
[data-testid="stMetricLabel"] {
    font-family: var(--mono) !important;
    font-size: 0.62rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--muted) !important;
}
[data-testid="stMetricValue"] {
    font-family: var(--mono) !important;
    font-size: 1.8rem !important;
    color: var(--text) !important;
}

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input {
    background: #fff !important;
    border: 1px solid var(--border) !important;
    border-radius: 5px !important;
    color: var(--text) !important;
    font-family: var(--sans) !important;
    font-size: 0.875rem !important;
}
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stDateInput"] label,
[data-testid="stTimeInput"] label {
    font-family: var(--mono) !important;
    font-size: 0.62rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: var(--muted) !important;
}

/* Botón */
[data-testid="stFormSubmitButton"] button,
.stButton button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 5px !important;
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    padding: 0.6rem 1.4rem !important;
    box-shadow: 0 2px 6px rgba(37,99,235,0.2) !important;
    transition: background 0.15s, transform 0.1s !important;
}
[data-testid="stFormSubmitButton"] button:hover,
.stButton button:hover {
    background: #1d4ed8 !important;
    transform: translateY(-1px) !important;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}

/* Form */
[data-testid="stForm"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    padding: 1.5rem !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04) !important;
}

/* Alerts */
[data-testid="stAlert"] {
    border-radius: 5px !important;
    font-family: var(--sans) !important;
    font-size: 0.85rem !important;
}

.stCaption, [data-testid="stCaptionContainer"] {
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    color: var(--muted) !important;
}

hr { border-color: var(--border) !important; }

::-webkit-scrollbar { width:6px; height:6px; }
::-webkit-scrollbar-track  { background: var(--bg); }
::-webkit-scrollbar-thumb  { background: var(--border); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:#b0b7c3; }
</style>
"""


# ── Helpers de fecha ───────────────────────────────────────────────────────────
def _parse_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _first_present(data, *keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return ""


def _path_value_after(path_parts, collection_names):
    normalized_names = {name.lower() for name in collection_names}
    for index, part in enumerate(path_parts[:-1]):
        if part.lower() in normalized_names:
            return path_parts[index + 1]
    return ""


def _normalize_schedule_date(value, fallback=""):
    parsed = _parse_date(value)
    if parsed:
        return parsed.isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _week_start(d):
    return d - timedelta(days=d.weekday())


def _week_label(start):
    end = start + timedelta(days=6)
    return f"{start.strftime('%d/%m/%Y')}  →  {end.strftime('%d/%m/%Y')}"


# ── Obtención de datos desde Firebase ─────────────────────────────────────────
def _get_db():
    """Importa y devuelve el cliente Firestore ya inicializado en admin.py."""
    try:
        from admin import get_firestore_client
        return get_firestore_client()
    except Exception:
        # fallback: inicializar aquí si se usa como módulo independiente
        import json, tomllib
        from pathlib import Path
        import firebase_admin
        from firebase_admin import credentials, firestore

        SECRET_PATHS = (
            Path(".streamlit/secrets.toml"),
            Path(".streamlit/secret.toml"),
            Path(".streamlit/firebase-service-account.json"),
        )

        def _extract_json_prefix(raw):
            if not raw.startswith("{"):
                return None
            lines = raw.splitlines()
            prefix_lines = []
            for line in lines:
                if line.lstrip().startswith("["):
                    break
                prefix_lines.append(line)
            prefix = "\n".join(prefix_lines).strip()
            if prefix.startswith("{"):
                return prefix
            return None

        def _load_sa():
            try:
                if "firebase_service_account" in st.secrets:
                    return dict(st.secrets["firebase_service_account"])
            except Exception:
                pass
            for p in SECRET_PATHS:
                if p.exists():
                    raw = p.read_text("utf-8").strip()
                    json_prefix = _extract_json_prefix(raw)
                    if json_prefix:
                        try:
                            parsed = json.loads(json_prefix)
                            if not isinstance(parsed, dict):
                                raise ValueError("El archivo no contiene un objeto JSON válido")
                            if "firebase_service_account" in parsed:
                                return dict(parsed["firebase_service_account"])
                            if "type" in parsed and "project_id" in parsed:
                                return parsed
                        except json.JSONDecodeError:
                            pass
                    try:
                        parsed = tomllib.loads(raw)
                        if "firebase_service_account" in parsed:
                            return dict(parsed["firebase_service_account"])
                        if "type" in parsed and "project_id" in parsed:
                            return dict(parsed)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(f"Credenciales inválidas en {p}: {exc}") from exc
                    except tomllib.TOMLDecodeError as exc:
                        raise RuntimeError(f"Credenciales inválidas en {p}: {exc}") from exc
            st.error("No se encontraron credenciales de Firebase.")
            st.stop()

        sa = _load_sa()
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(sa))
        return firestore.client()


@st.cache_data(ttl=30, show_spinner=False)
def _get_asistencias_full():
    """Trae TODOS los campos de asistencia desde Firestore."""
    db = _get_db()
    docs = db.collection(ATTENDANCE_COLLECTION).stream()
    rows = []
    for doc in docs:
        d = doc.to_dict()
        entrada = d.get("entrada") if isinstance(d.get("entrada"), dict) else {}
        salida = d.get("salida") if isinstance(d.get("salida"), dict) else {}
        rows.append({
            "doc_id":            doc.id,
            "fecha":             d.get("fecha", ""),
            "id_trabajador":     d.get("id_trabajador", ""),
            "nombre_trabajador": d.get("nombre_trabajador", ""),
            "dni":               d.get("dni", ""),
            "nombre_tienda":     d.get("nombre_tienda", ""),
            "nombre_sede":       d.get("nombre_sede", ""),
            "id_tienda":         d.get("id_tienda", ""),
            "id_sede":           d.get("id_sede", ""),
            "hora_inicio":       d.get("hora_inicio") or entrada.get("hora") or "",
            "inicio_receso":     d.get("inicio_receso", ""),
            "final_receso":      d.get("final_receso", ""),
            # el campo puede llamarse hora_final o hora_finalhas según el doc
            "hora_final":        d.get("hora_final") or d.get("hora_finalhas") or salida.get("hora") or "",
            "ultima_marca":      d.get("ultima_marca", ""),
            "entrada":           entrada,
            "salida":            salida,
        })
    return rows


@st.cache_data(ttl=30, show_spinner=False)
def _get_dias_schedule():
    db = _get_db()
    rows = []
    seen_paths = set()

    for doc in db.collection_group("dias").stream():
        path = doc.reference.path
        if path in seen_paths:
            continue
        seen_paths.add(path)

        data = doc.to_dict() or {}
        entrada = data.get("entrada") if isinstance(data.get("entrada"), dict) else {}
        salida = data.get("salida") if isinstance(data.get("salida"), dict) else {}

        path_parts = path.split("/")
        raw_fecha = _first_present(
            data,
            "fecha",
            "date",
            "dia",
            "fecha_dia",
        ) or doc.id

        id_trabajador = _first_present(
            data,
            "id_trabajador",
            "trabajador_id",
            "idTrabajador",
            "worker_id",
        ) or _path_value_after(path_parts, ("trabajadores", "trabajador"))

        rows.append({
            "doc_id": doc.id,
            "fecha": raw_fecha,
            "fecha_dt": _parse_date(raw_fecha),
            "id_trabajador": str(id_trabajador).strip(),
            "id_sede": _first_present(data, "id_sede", "sede_id", "idSede"),
            "entrada_hora": _first_present(entrada, "hora", "entrada") or data.get("hora_entrada") or "",
            "salida_hora": _first_present(salida, "hora", "salida") or data.get("hora_salida") or "",
            "entrada": entrada,
            "salida": salida,
        })

    return rows


@st.cache_data(ttl=30, show_spinner=False)
def _get_trabajadores():
    db = _get_db()
    docs = db.collection(WORKER_COLLECTION).stream()
    workers = []
    for doc in docs:
        d = doc.to_dict()
        workers.append({
            "doc_id":            doc.id,
            "id_trabajador":     d.get("id_trabajador", doc.id),
            "nombre_trabajador": d.get("nombre_trabajador", ""),
            "dni":               d.get("dni", ""),
            "nombre_sede":       d.get("nombre_sede", ""),
            "id_sede":           d.get("id_sede", ""),
        })
    return sorted(workers, key=lambda x: x["nombre_trabajador"])


@st.cache_data(ttl=30, show_spinner=False)
def _get_tiendas():
    db = _get_db()
    docs = db.collection(STORE_COLLECTION).stream()
    tiendas = []
    for doc in docs:
        d = doc.to_dict()
        tiendas.append({
            "doc_id":       doc.id,
            "id_tienda":    d.get("id_tienda", doc.id),
            "nombre_tienda":d.get("nombre_tienda", ""),
            "id_sede":      d.get("id_sede", ""),
            "nombre_sede":  d.get("nombre_sede", ""),
        })
    return sorted(tiendas, key=lambda x: x["nombre_tienda"])


def _save_asistencia(data: dict):
    from firebase_admin import firestore as _fs
    db = _get_db()
    db.collection(ATTENDANCE_COLLECTION).document(data["doc_id"]).set(data)
    st.cache_data.clear()


# ── Enriquecimiento de filas ───────────────────────────────────────────────────
def _enrich(rows, workers, schedule_rows=None):
    by_id  = {str(w["id_trabajador"]): w for w in workers}
    by_dni = {str(w["dni"]): w for w in workers}
    schedule_index = {}

    for sched in (schedule_rows or []):
        worker_id = str(sched.get("id_trabajador") or "").strip()
        sched_date = _normalize_schedule_date(sched.get("fecha")) or (sched.get("fecha_dt").isoformat() if sched.get("fecha_dt") else "")
        if worker_id and sched_date:
            schedule_index[(worker_id, sched_date)] = sched

    result = []
    for row in rows:
        item = dict(row)
        worker = (
            by_id.get(str(item.get("id_trabajador", "")))
            or by_dni.get(str(item.get("dni", "")))
        )
        if worker:
            if not item["nombre_trabajador"]:
                item["nombre_trabajador"] = worker["nombre_trabajador"]
            if not item["dni"]:
                item["dni"] = worker["dni"]
            if not item["nombre_sede"]:
                item["nombre_sede"] = worker["nombre_sede"]

        if not item["nombre_trabajador"]:
            item["nombre_trabajador"] = item.get("id_trabajador") or item.get("dni") or "Sin nombre"

        entrada = item.get("entrada") if isinstance(item.get("entrada"), dict) else {}
        salida = item.get("salida") if isinstance(item.get("salida"), dict) else {}

        item["hora_inicio"] = item.get("hora_inicio") or entrada.get("hora") or ""
        item["hora_final"] = item.get("hora_final") or salida.get("hora") or ""

        match_key = (
            str(item.get("id_trabajador") or "").strip(),
            _normalize_schedule_date(item.get("fecha")) or (item.get("fecha_dt").isoformat() if item.get("fecha_dt") else ""),
        )
        schedule = schedule_index.get(match_key)
        if schedule:
            item["entrada_programada"] = schedule.get("entrada_hora") or ""
            item["salida_programada"] = schedule.get("salida_hora") or ""
        else:
            item["entrada_programada"] = item.get("hora_inicio") or entrada.get("hora") or ""
            item["salida_programada"] = item.get("hora_final") or salida.get("hora") or ""

        # rango horario para mostrar en la tarjeta
        ini = item.get("hora_inicio") or ""
        fin = item.get("hora_final")  or ""
        item["rango_horario"] = f"{ini} – {fin}" if (ini or fin) else (item.get("ultima_marca") or "")

        item["fecha_dt"] = _parse_date(item.get("fecha"))
        result.append(item)
    return result


# ── Componentes UI ─────────────────────────────────────────────────────────────
def _section_header(title, subtitle=None):
    sub_html = (
        f'<div style="font-size:0.82rem;color:#6b7280;font-family:DM Sans,sans-serif;'
        f'margin-top:0.2rem;">{subtitle}</div>'
        if subtitle else ""
    )
    st.markdown(f"""
    <div style="margin:0.5rem 0 1.25rem;padding-left:0.75rem;border-left:3px solid #2563eb;">
        <div style="font-family:'Space Mono',monospace;font-size:0.75rem;
                    text-transform:uppercase;letter-spacing:0.1em;color:#2563eb;">
            {title}
        </div>
        {sub_html}
    </div>""", unsafe_allow_html=True)


def _week_selector(current_start):
    prev_col, picker_col, next_col = st.columns([1, 2, 1])

    if prev_col.button("← Semana anterior", use_container_width=True):
        st.session_state["aw_date"] = current_start - timedelta(days=7)
        st.rerun()

    picked = picker_col.date_input(
        "Semana",
        value=current_start,
        key="aw_picker",
        help="Selecciona cualquier día de la semana que quieres ver.",
        label_visibility="collapsed",
    )

    if next_col.button("Semana siguiente →", use_container_width=True):
        st.session_state["aw_date"] = current_start + timedelta(days=7)
        st.rerun()

    if picked != current_start:
        st.session_state["aw_date"] = picked
        current_start = _week_start(picked)

    st.caption(f"Semana: `{_week_label(current_start)}`")
    return current_start


def _attendance_card(row):
    marca = row.get("ultima_marca", "")
    # color según última marca
    color_map = {
        "hora_inicio":   "#2563eb",
        "inicio_receso": "#f59e0b",
        "final_receso":  "#8b5cf6",
        "hora_final":    "#16a34a",
        "hora_finalhas": "#16a34a",
    }
    color = color_map.get(marca, "#94a3b8")

    return f"""
    <div style="border-left:3px solid {color};background:#f8faff;
                border-radius:6px;padding:0.55rem 0.65rem;margin-bottom:0.45rem;
                box-shadow:0 1px 3px rgba(0,0,0,0.06);">
        <div style="font-size:0.8rem;font-weight:600;color:#111827;line-height:1.2;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
             title="{row.get('nombre_trabajador','')}">
            {row.get('nombre_trabajador', 'Sin nombre')}
        </div>
        <div style="font-family:'Space Mono',monospace;font-size:0.65rem;
                    color:#6b7280;margin-top:0.2rem;">
            {row.get('rango_horario', '')}
        </div>
        <div style="font-size:0.65rem;color:#6b7280;margin-top:0.1rem;">
            {row.get('nombre_tienda') or row.get('nombre_sede') or ''}
        </div>
    </div>"""


def _week_grid(rows, week_start):
    days = [week_start + timedelta(days=i) for i in range(7)]
    cols = st.columns(7)

    for idx, day in enumerate(days):
        day_rows = sorted(
            [r for r in rows if r.get("fecha_dt") == day],
            key=lambda r: r.get("nombre_trabajador", ""),
        )
        is_today = day == date.today()
        header_bg  = "#2563eb" if is_today else "#f0f4ff"
        header_txt = "#ffffff"  if is_today else "#2563eb"
        day_bg     = "#eef4ff"  if is_today else "#ffffff"

        with cols[idx]:
            st.markdown(f"""
            <div style="background:{day_bg};border:1px solid #dde1ea;border-radius:8px;
                        min-height:200px;overflow:hidden;">
                <div style="background:{header_bg};padding:0.5rem 0.65rem;">
                    <div style="font-family:'Space Mono',monospace;font-size:0.62rem;
                                color:{header_txt};text-transform:uppercase;letter-spacing:0.06em;">
                        {WEEK_DAYS[idx]}
                    </div>
                    <div style="font-family:'Space Mono',monospace;font-weight:700;
                                font-size:1rem;color:{header_txt};">
                        {day.strftime('%d/%m')}
                    </div>
                </div>
                <div style="padding:0.5rem 0.5rem 0.35rem;">
            """, unsafe_allow_html=True)

            if not day_rows:
                st.markdown(
                    '<div style="font-size:0.72rem;color:#94a3b8;padding:0.25rem 0.15rem;">Sin registros</div>',
                    unsafe_allow_html=True,
                )
            for row in day_rows:
                st.markdown(_attendance_card(row), unsafe_allow_html=True)

            st.markdown("</div></div>", unsafe_allow_html=True)


# ── Vista principal ────────────────────────────────────────────────────────────
def render_asistencias(api=None):
    st.markdown(SHARED_CSS, unsafe_allow_html=True)

    # Encabezado de página
    st.markdown("""
    <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.25rem;">
        <div style="font-size:1.4rem;color:#2563eb;">⬡</div>
        <div>
            <div style="font-family:'Space Mono',monospace;font-size:1.25rem;
                        letter-spacing:0.03em;color:#111827;line-height:1.1;">
                Asistencias
            </div>
            <div style="font-size:0.78rem;color:#6b7280;font-family:'DM Sans',sans-serif;
                        margin-top:0.15rem;">
                Vista semanal · Firebase Firestore
            </div>
        </div>
    </div>
    <hr style="margin:0.75rem 0 1.5rem;border-color:#dde1ea;">
    """, unsafe_allow_html=True)

    # Carga de datos
    with st.spinner("Cargando datos…"):
        try:
            asistencias  = _get_asistencias_full()
            trabajadores = _get_trabajadores()
            tiendas      = _get_tiendas()
            dias         = _get_dias_schedule()
        except Exception as exc:
            st.error(f"Error al conectar con Firebase: {exc}")
            st.stop()

    rows = _enrich(asistencias, trabajadores, dias)

    # ── Métricas globales ──────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total registros",  len(rows))
    m2.metric("Trabajadores",     len({r["id_trabajador"] for r in rows if r["id_trabajador"]}))
    m3.metric("Tiendas",          len({r["nombre_tienda"] for r in rows if r["nombre_tienda"]}))
    valid_dates = [r["fecha_dt"] for r in rows if r.get("fecha_dt")]
    m4.metric("Rango de fechas",
              f"{min(valid_dates).strftime('%d/%m')} – {max(valid_dates).strftime('%d/%m')}"
              if valid_dates else "—")

    st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)

    # ── Selector de semana ─────────────────────────────────────────────────────
    _section_header("Vista semanal", "Lunes a domingo con trabajador y horario")

    if "aw_date" not in st.session_state:
        st.session_state["aw_date"] = max(valid_dates) if valid_dates else date.today()

    week_start = _week_start(st.session_state["aw_date"])
    week_start = _week_selector(week_start)
    week_end   = week_start + timedelta(days=6)

    week_rows = [r for r in rows if r.get("fecha_dt") and week_start <= r["fecha_dt"] <= week_end]

    st.markdown('<div style="height:0.75rem"></div>', unsafe_allow_html=True)
    _week_grid(rows, week_start)

    # ── Tabla de la semana ─────────────────────────────────────────────────────
    st.markdown('<div style="height:1.25rem"></div>', unsafe_allow_html=True)
    _section_header("Detalle de la semana")
    st.caption(f"{len(week_rows)} registros · semana `{_week_label(week_start)}`")

    if week_rows:
        table = sorted(week_rows, key=lambda r: (r["fecha_dt"], r.get("nombre_trabajador", "")))
        st.dataframe(
            [{
                "Fecha":            r["fecha_dt"].strftime("%d/%m/%Y"),
                "Día":              WEEK_DAYS[r["fecha_dt"].weekday()],
                "Trabajador":       r.get("nombre_trabajador", ""),
                "DNI":              r.get("dni", ""),
                "Tienda":           r.get("nombre_tienda", ""),
                "Sede":             r.get("nombre_sede", ""),
                "Entrada prevista": r.get("entrada_programada", ""),
                "Entrada":          r.get("hora_inicio", ""),
                "Ini. receso":      r.get("inicio_receso", ""),
                "Fin receso":       r.get("final_receso", ""),
                "Salida prevista":  r.get("salida_programada", ""),
                "Salida":           r.get("hora_final", ""),
                "Última marca":     r.get("ultima_marca", ""),
            } for r in table],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No hay asistencias registradas en esta semana.")

    # ── Formulario nueva asistencia ────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    _section_header("Nueva asistencia", "Registra o corrige una marca manualmente")

    if not tiendas or not trabajadores:
        st.warning("Necesitas al menos una tienda y un trabajador registrados.")
        return

    tienda_opts = {f"{t['nombre_tienda']}  ·  {t['id_tienda']}": t for t in tiendas}
    worker_opts = {f"{w['nombre_trabajador']}  ·  {w['dni']}": w   for w in trabajadores}

    with st.form("new_attendance_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        tienda_lbl = c1.selectbox("Tienda *",     options=list(tienda_opts.keys()), index=None, placeholder="Selecciona una tienda")
        worker_lbl = c2.selectbox("Trabajador *", options=list(worker_opts.keys()), index=None, placeholder="Selecciona un trabajador")
        fecha      = c1.date_input("Fecha *")

        st.markdown(
            '<div style="margin:0.75rem 0 0.25rem;font-family:Space Mono,monospace;'
            'font-size:0.62rem;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;">'
            'Marcas horarias</div>',
            unsafe_allow_html=True,
        )
        t1, t2, t3, t4 = st.columns(4)
        hora_inicio   = t1.time_input("Entrada")
        inicio_receso = t2.time_input("Ini. receso")
        final_receso  = t3.time_input("Fin receso")
        hora_final    = t4.time_input("Salida")

        ultima_marca = st.selectbox(
            "Última marca *",
            options=["hora_inicio", "inicio_receso", "final_receso", "hora_final"],
        )
        submitted = st.form_submit_button("Registrar asistencia", use_container_width=True)

    if not submitted:
        return

    missing = [k for k, v in {
        "Tienda": tienda_lbl, "Trabajador": worker_lbl,
    }.items() if not v]
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    tienda    = tienda_opts[tienda_lbl]
    trabajador = worker_opts[worker_lbl]

    def _fmt(t):
        return t.strftime("%H:%M") if t else ""

    # doc_id único
    from uuid import uuid4
    raw_id = f"{trabajador['id_trabajador']}_{fecha.isoformat()}_{tienda['id_tienda']}"
    safe   = "".join(c if c.isalnum() else "_" for c in raw_id.lower()).strip("_") or uuid4().hex

    _save_asistencia({
        "doc_id":            safe,
        "nombre_tienda":     tienda["nombre_tienda"],
        "id_tienda":         tienda["id_tienda"],
        "id_trabajador":     trabajador["id_trabajador"],
        "nombre_trabajador": trabajador["nombre_trabajador"],
        "fecha":             fecha.isoformat(),
        "hora_inicio":       _fmt(hora_inicio),
        "inicio_receso":     _fmt(inicio_receso),
        "final_receso":      _fmt(final_receso),
        "hora_final":        _fmt(hora_final),
        "ultima_marca":      ultima_marca,
        "id_sede":           tienda["id_sede"],
        "nombre_sede":       tienda["nombre_sede"],
        "dni":               trabajador["dni"],
    })
    st.success(f"✓  Asistencia registrada → `{ATTENDANCE_COLLECTION}/{safe}`")


# ── Punto de entrada (standalone) ─────────────────────────────────────────────
if __name__ == "__main__":
    st.set_page_config(
        page_title="Asistencias",
        page_icon="⬡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    render_asistencias()