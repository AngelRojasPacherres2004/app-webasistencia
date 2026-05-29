from collections import defaultdict
from datetime import date, timedelta

import streamlit as st

WEEK_DAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")

MARCACIONES = [
    ("Entrada",     "entrada",           "hora_entrada"),
    ("Rec. inicio", "refrigerio_inicio", "hora_refrigerio_inicio"),
    ("Rec. fin",    "refrigerio_fin",    "hora_refrigerio_fin"),
    ("Salida",      "salida",            "hora_salida"),
]

OVERVIEW_CSS = """
<style>
[data-testid="stAppViewContainer"] {
    background: #f8fafc !important;
}
[data-testid="stMetric"] {
    background: #fff !important;
    border: 1px solid #e2e8f0 !important;
    border-top: 3px solid #2563eb !important;
    border-radius: 12px !important;
    padding: 1.1rem 1.3rem !important;
    box-shadow: 0 2px 12px rgba(15,23,42,.06) !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'Space Mono',monospace !important;
    font-size: .62rem !important;
    text-transform: uppercase !important;
    letter-spacing: .1em !important;
    color: #64748b !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Space Mono',monospace !important;
    font-size: 1.9rem !important;
    color: #0f172a !important;
}
[data-testid="stTabs"] button {
    font-family: 'Space Mono',monospace !important;
    font-size: .68rem !important;
    text-transform: uppercase !important;
    letter-spacing: .08em !important;
    color: #64748b !important;
    border: none !important;
    background: transparent !important;
    padding: .55rem .9rem !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #ffffff !important;
    background: #2563eb !important;
    border-radius: 10px !important;
    border-bottom: 2px solid #1d4ed8 !important;
}
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid #e2e8f0 !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 6px rgba(15,23,42,.04) !important;
}
[data-testid="stTextInput"] input {
    background:#fff !important;
    border:1px solid #e2e8f0 !important;
    border-radius:999px !important;
    padding:.55rem 1rem !important;
    font-size:.84rem !important;
    color:#0f172a !important;
}
[data-testid="stTextInput"] label {
    font-family:'Space Mono',monospace !important;
    font-size:.62rem !important;
    text-transform:uppercase !important;
    letter-spacing:.06em !important;
    color:#64748b !important;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background:#fff !important;
    border:1px solid #e2e8f0 !important;
    border-radius:8px !important;
    color:#0f172a !important;
}
[data-testid="stSelectbox"] label {
    font-family:'Space Mono',monospace !important;
    font-size:.62rem !important;
    text-transform:uppercase !important;
    letter-spacing:.06em !important;
    color:#64748b !important;
}
.stButton button {
    background: #2563eb !important;
    color:#fff !important;
    border:none !important;
    border-radius:8px !important;
    font-family:'Space Mono',monospace !important;
    font-size:.68rem !important;
    text-transform:uppercase !important;
    letter-spacing:.07em !important;
    padding:.55rem 1.1rem !important;
    box-shadow:0 2px 8px rgba(37,99,235,.2) !important;
    transition:background .15s,transform .1s !important;
}
.stButton button:hover {
    background:#1d4ed8 !important;
    transform:translateY(-1px) !important;
}
.stCaption,[data-testid="stCaptionContainer"] {
    font-family:'Space Mono',monospace !important;
    font-size:.68rem !important;
    color:#64748b !important;
}
[data-testid="stAlert"] {
    border-radius:8px !important;
    font-size:.84rem !important;
}
.week-panel {
    background:#fff;
    border:1px solid #e2e8f0;
    border-radius:16px;
    padding:1.25rem 1.4rem 1rem;
    box-shadow:0 4px 24px rgba(15,23,42,.06);
    margin-bottom:1.25rem;
}
.week-panel-title {
    font-family:'Space Mono',monospace;
    font-size:.8rem;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:.08em;
    color:#0f172a;
}
.week-panel-sub {
    font-size:.75rem;
    color:#64748b;
    margin-top:.15rem;
}
.week-range-badge {
    display:inline-block;
    background:#eff6ff;
    border:1px solid #bfdbfe;
    border-radius:999px;
    padding:.28rem .8rem;
    font-family:'Space Mono',monospace;
    font-size:.65rem;
    color:#1d4ed8;
    letter-spacing:.04em;
}
/* ── chips ── */
.m-chip {
    display:inline-flex;
    align-items:center;
    padding:.40rem .80rem;
    border-radius:999px;
    font-size:.78rem;
    font-weight:700;
    white-space:nowrap;
}
.m-entrada    { background:#dbeafe; color:#1d4ed8; }
.m-receso_ini { background:#fef3c7; color:#92400e; }
.m-receso_fin { background:#ede9fe; color:#5b21b6; }
.m-salida     { background:#dcfce7; color:#166534; }
.m-absent     { background:#f1f5f9; color:#94a3b8; }
.m-null       { background:#f8fafc; color:#94a3b8; border:1px dashed #cbd5e1; font-weight:400; font-style:italic; }

/* ── tabla ── */
.at-table { width:100%; border-collapse:collapse; font-size:.85rem; }
.at-table thead th {
    text-align:left;
    padding:.85rem .9rem;
    background:#f8fafc;
    color:#64748b;
    font-family:'Space Mono',monospace;
    font-size:.68rem;
    text-transform:uppercase;
    letter-spacing:.1em;
    border-bottom:1px solid #e2e8f0;
    white-space:nowrap;
}
.at-table tbody tr { border-bottom:1px solid #f1f5f9; }
.at-table tbody tr:hover { background:#fafbff; }
.at-table td { padding:1rem .9rem; vertical-align:middle; color:#1e293b; }
.at-table td.worker-td { min-width:160px; }
.worker-name { font-weight:700; color:#0f172a; font-size:.85rem; }
.worker-meta { font-size:.69rem; color:#64748b; margin-top:.15rem; }

::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:#f8fafc}
::-webkit-scrollbar-thumb{background:#e2e8f0;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#b0b7c3}
</style>
"""


# ── helpers ────────────────────────────────────────────────────────────────────
def _parse_date(row):
    value = row.get("fecha")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _week_start(d):
    return d - timedelta(days=d.weekday())


def _week_label(s):
    return f"{s.strftime('%d/%m/%Y')}  →  {(s + timedelta(days=6)).strftime('%d/%m/%Y')}"


def _hora(row, field):
    """
    Lee hora desde un campo de Firebase.
    Soporta:
      - formato Flutter: { "hora": "08:05", "marca": Timestamp }
      - formato legacy:  "08:05"  (string directo)
      - None / campo ausente → devuelve None  (NO "")
    """
    val = row.get(field)
    if val is None:
        return None                        # campo no existe en el documento
    if isinstance(val, dict):
        hora = val.get("hora")
        return hora if hora else None      # map existe pero hora vacía → None
    s = str(val).strip()
    return s if s else None


def _chip(hora, kind):
    """Chip con hora. Si hora es None → chip null."""
    if hora is None:
        label = kind.replace("_", " ")
        return f'<span class="m-chip m-null">{label}: null</span>'
    css = {
        "entrada":    "m-entrada",
        "receso_ini": "m-receso_ini",
        "receso_fin": "m-receso_fin",
        "salida":     "m-salida",
    }.get(kind, "m-absent")
    return f'<span class="m-chip {css}">{hora}</span>'


# ── mapa de asistencias por trabajador y fecha ─────────────────────────────────
def _build_attendance_map(asistencias, week_start, week_end):
    att_map = defaultdict(dict)
    for row in asistencias:
        d = _parse_date(row)
        if not d or not (week_start <= d <= week_end):
            continue
        wid = str(row.get("id_trabajador") or "").strip()
        att_map[wid][d] = row
    return att_map


# ── tabla HTML semanal ─────────────────────────────────────────────────────────
def _render_weekly_table(trabajadores, asistencias, week_start, week_end, query):
    att_map = _build_attendance_map(asistencias, week_start, week_end)
    q = query.strip().lower()
    days = [week_start + timedelta(days=i) for i in range(7)]

    day_headers = "".join(
        f'<th>{WEEK_DAYS[i]}<br>'
        f'<span style="font-weight:400;font-size:.6rem;">{d.strftime("%d/%m")}</span></th>'
        for i, d in enumerate(days)
    )
    header = f"""
    <thead><tr>
      <th>Trabajador</th>
      {day_headers}
      <th>Días</th>
    </tr></thead>"""

    rows_html = []
    for w in sorted(trabajadores, key=lambda x: x.get("nombre_trabajador", "")):
        nombre = w.get("nombre_trabajador", "Sin nombre")
        dni    = w.get("dni", "")
        sede   = w.get("nombre_sede") or w.get("nombre_tienda") or ""
        wid    = str(w.get("id_trabajador") or "").strip()

        if q and q not in f"{nombre} {dni} {sede}".lower():
            continue

        worker_att     = att_map.get(wid, {})
        dias_presentes = len(worker_att)

        day_cells = ""
        for d in days:
            row = worker_att.get(d)
            if row is None:
                # Sin documento ese día
                day_cells += (
                    '<td><span class="m-chip m-absent" '
                    'style="opacity:.55;">Sin registro</span></td>'
                )
            else:
                # Lee entrada — prueba campo Flutter primero, luego legacy
                entrada = (
                    _hora(row, "entrada")
                    or _hora(row, "hora_inicio")
                    or _hora(row, "hora_entrada")
                )
                # Lee salida
                salida = (
                    _hora(row, "salida")
                    or _hora(row, "hora_final")
                    or _hora(row, "hora_salida")
                )

                e_chip = _chip(entrada, "entrada")
                s_chip = _chip(salida,  "salida")
                cell = (
                    f'<div style="display:flex;flex-direction:column;gap:.3rem;">'
                    f'{e_chip}{s_chip}'
                    f'</div>'
                )
                day_cells += f"<td>{cell}</td>"

        # badge días con color semáforo
        if dias_presentes >= 5:
            p_bg, p_col = "#dcfce7", "#166534"
        elif dias_presentes >= 1:
            p_bg, p_col = "#fef3c7", "#92400e"
        else:
            p_bg, p_col = "#fee2e2", "#b91c1c"

        rows_html.append(f"""
        <tr>
          <td class="worker-td">
            <div class="worker-name">{nombre}</div>
            <div class="worker-meta">DNI {dni} · {sede}</div>
          </td>
          {day_cells}
          <td>
            <span class="m-chip" style="background:{p_bg};color:{p_col};">
              {dias_presentes}/7
            </span>
          </td>
        </tr>""")

    if not rows_html:
        return None

    body = "<tbody>" + "".join(rows_html) + "</tbody>"
    return f"""
    <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:12px;
                background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.04);">
      <table class="at-table">{header}{body}</table>
    </div>"""


# ── section header ─────────────────────────────────────────────────────────────
def _sh(title, subtitle=None):
    sub = (
        f'<div style="font-size:.78rem;color:#64748b;margin-top:.18rem;">{subtitle}</div>'
        if subtitle else ""
    )
    st.markdown(f"""
    <div style="margin:.5rem 0 1rem;padding-left:.7rem;border-left:3px solid #2563eb;">
      <div style="font-family:'Space Mono',monospace;font-size:.72rem;
                  text-transform:uppercase;letter-spacing:.1em;color:#2563eb;">
        {title}
      </div>{sub}
    </div>""", unsafe_allow_html=True)


# ── vista principal ────────────────────────────────────────────────────────────
def render_overview(api=None):
    st.markdown(OVERVIEW_CSS, unsafe_allow_html=True)

    # obtener datos
    if api is not None:
        tiendas      = api.get_tiendas()
        trabajadores = api.get_trabajadores()
        asistencias  = api.get_asistencias()
        store_col    = getattr(api, "STORE_COLLECTION",  "tienda")
        worker_col   = getattr(api, "WORKER_COLLECTION", "trabajador")
    else:
        from asistencias_data import get_tiendas, get_trabajadores, get_asistencias_full
        tiendas      = get_tiendas()
        trabajadores = get_trabajadores()
        asistencias  = get_asistencias_full()
        store_col    = "tienda"
        worker_col   = "trabajador"

    # métricas
    valid_dates = [_parse_date(r) for r in asistencias if _parse_date(r)]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tiendas",      len(tiendas))
    m2.metric("Trabajadores", len(trabajadores))
    m3.metric("Registros",    len(asistencias))
    m4.metric("Rango",
              f"{min(valid_dates).strftime('%d/%m')} – {max(valid_dates).strftime('%d/%m')}"
              if valid_dates else "—")

    st.markdown('<div style="height:1.25rem"></div>', unsafe_allow_html=True)

    tab_a, tab_w, tab_t = st.tabs([
        "⬡  Asistencias",
        "⬡  Trabajadores",
        "⬡  Tiendas",
    ])

    # ── TAB ASISTENCIAS ────────────────────────────────────────────────────────
    with tab_a:
        if "ov_week" not in st.session_state:
            st.session_state["ov_week"] = max(valid_dates) if valid_dates else date.today()

        current_start = _week_start(st.session_state["ov_week"])
        week_end      = current_start + timedelta(days=6)

        st.markdown(f"""
        <div class="week-panel">
          <div style="display:flex;align-items:center;justify-content:space-between;
                      flex-wrap:wrap;gap:.75rem;">
            <div>
              <div class="week-panel-title">Asistencias semanales</div>
              <div class="week-panel-sub">
                Entrada y salida por trabajador · null = sin dato en Firebase
              </div>
            </div>
            <span class="week-range-badge">{_week_label(current_start)}</span>
          </div>
        </div>""", unsafe_allow_html=True)

        sc1, sc2, sc3, sc4 = st.columns([3, 1, 1, 1])
        search_query = sc1.text_input(
            "Buscar", placeholder="Nombre, DNI o sede…",
            key="ov_search", label_visibility="collapsed",
        )
        if sc2.button("← Anterior", key="ov_prev", use_container_width=True):
            st.session_state["ov_week"] = current_start - timedelta(days=7)
            st.rerun()
        picked = sc3.date_input(
            "Semana", value=current_start,
            key="ov_picker", label_visibility="collapsed",
        )
        if sc4.button("Siguiente →", key="ov_next", use_container_width=True):
            st.session_state["ov_week"] = current_start + timedelta(days=7)
            st.rerun()

        if picked != current_start:
            st.session_state["ov_week"] = picked
            current_start = _week_start(picked)
            week_end = current_start + timedelta(days=6)

        st.caption(
            f"Semana: `{_week_label(current_start)}`  ·  {len(asistencias):,} registros totales"
        )
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)

        table_html = _render_weekly_table(
            trabajadores, asistencias, current_start, week_end, search_query
        )
        if table_html:
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="border:1px dashed #cbd5e1;border-radius:12px;padding:2rem;
                        text-align:center;color:#94a3b8;background:#fff;font-size:.84rem;">
                No hay registros para esta semana.
            </div>""", unsafe_allow_html=True)

    # ── TAB TRABAJADORES ───────────────────────────────────────────────────────
    with tab_w:
        st.caption(f"colección Firebase: `{worker_col}`")
        if not trabajadores:
            st.info("Todavía no hay trabajadores registrados.")
        else:
            q = st.text_input(
                "Buscar trabajador", placeholder="Nombre, DNI o área…",
                key="ov_worker_search", label_visibility="collapsed",
            )
            filtered = [
                w for w in trabajadores
                if not q or q.lower() in
                f"{w.get('nombre_trabajador','')} {w.get('dni','')} {w.get('area','')}".lower()
            ]
            st.caption(f"{len(filtered)} de {len(trabajadores)} trabajadores")
            st.dataframe(filtered, use_container_width=True, hide_index=True)

            if api is not None and hasattr(api, "worker_attendance_dialog"):
                st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
                worker_options = {
                    f"{w['nombre_trabajador']}  ·  {w['dni']}": w for w in trabajadores
                }
                sel = st.selectbox(
                    "Ver asistencias de trabajador",
                    options=list(worker_options.keys()),
                    index=None,
                    placeholder="Selecciona un trabajador…",
                )
                if st.button("Ver asistencias", disabled=not sel, use_container_width=False):
                    api.worker_attendance_dialog(worker_options[sel])

    # ── TAB TIENDAS ────────────────────────────────────────────────────────────
    with tab_t:
        st.caption(f"colección Firebase: `{store_col}`")
        if tiendas:
            st.dataframe(tiendas, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay tiendas registradas.")