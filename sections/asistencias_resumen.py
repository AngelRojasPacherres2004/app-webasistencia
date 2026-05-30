from datetime import date, timedelta

import streamlit as st


def _parse_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _week_start(current_date):
    return current_date - timedelta(days=current_date.weekday())


def _week_label(start_date):
    end_date = start_date + timedelta(days=6)
    return f"{start_date.strftime('%d/%m/%Y')}  →  {end_date.strftime('%d/%m/%Y')}"


def _render_attendance_table(attendance_rows):
    if not attendance_rows:
        return None

    rows_html = []
    for row in attendance_rows:
        rows_html.append(
            f"""
            <tr>
              <td class="worker-td">
                <div class="worker-name">{row.get('nombre_trabajador', '—')}</div>
                <div class="worker-meta">DNI {row.get('dni', '—')} · {row.get('nombre_tienda', '—')}</div>
              </td>
              <td>{row.get('fecha', '—')}</td>
              <td>{row.get('hora_inicio', '—')}</td>
              <td>{row.get('inicio_receso', '—')}</td>
              <td>{row.get('final_receso', '—')}</td>
              <td>{row.get('hora_final', '—')}</td>
            </tr>
            """
        )

    return f"""
    <div style="overflow-x:auto;border:1px solid #e2e8f0;border-radius:12px;
                background:#fff;box-shadow:0 1px 6px rgba(15,23,42,.04);">
      <table class="at-table">
        <thead>
          <tr>
            <th>Trabajador</th>
            <th>Fecha</th>
            <th>Entrada</th>
            <th>Ini. receso</th>
            <th>Fin receso</th>
            <th>Salida</th>
          </tr>
        </thead>
        <tbody>{''.join(rows_html)}</tbody>
      </table>
    </div>
    """


def render_resumen(api=None):
    if api is None:
        st.error("Falta el contexto de la app.")
        return

    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.25rem;">
            <div style="font-size:1.4rem;color:#2563eb;">⬡</div>
            <div>
                <div style="font-family:'Space Mono',monospace;font-size:1.25rem;letter-spacing:0.03em;color:#111827;line-height:1.1;">
                    Asistencias
                </div>
                <div style="font-size:0.78rem;color:#6b7280;font-family:'DM Sans',sans-serif;margin-top:0.15rem;">
                    Vista semanal · PostgreSQL
                </div>
            </div>
        </div>
        <hr style="margin:0.75rem 0 1.5rem;border-color:#dde1ea;">
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("Cargando asistencias..."):
        asistencias = api.get_asistencias()

    valid_dates = [_parse_date(row.get("fecha")) for row in asistencias if _parse_date(row.get("fecha"))]
    m1, m2, m3 = st.columns(3)
    m1.metric("Registros", len(asistencias))
    m2.metric("Trabajadores", len({row.get("dni") for row in asistencias if row.get("dni")}))
    m3.metric(
        "Rango de fechas",
        f"{min(valid_dates).strftime('%d/%m')} – {max(valid_dates).strftime('%d/%m')}"
        if valid_dates else "—",
    )

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

    if "resumen_week" not in st.session_state:
        st.session_state["resumen_week"] = max(valid_dates) if valid_dates else date.today()

    current_start = _week_start(st.session_state["resumen_week"])
    week_end = current_start + timedelta(days=6)

    st.markdown(
        f"""
        <div class="week-panel">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.75rem;">
            <div>
              <div class="week-panel-title">Asistencias semanales</div>
              <div class="week-panel-sub">Solo marcas de asistencia, sin trabajadores ni tiendas</div>
            </div>
            <span class="week-range-badge">{_week_label(current_start)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sc1, sc2, sc3 = st.columns([3, 1, 1])
    search_query = sc1.text_input(
        "Buscar", placeholder="Nombre, DNI o fecha…", key="resumen_search", label_visibility="collapsed"
    )
    if sc2.button("← Anterior", use_container_width=True):
        st.session_state["resumen_week"] = current_start - timedelta(days=7)
        st.rerun()
    picked = sc3.date_input("Semana", value=current_start, key="resumen_picker", label_visibility="collapsed")
    if picked != current_start:
        st.session_state["resumen_week"] = picked
        current_start = _week_start(picked)
        week_end = current_start + timedelta(days=6)

    st.caption(f"Semana: `{_week_label(current_start)}` · `{len(asistencias):,}` registros")

    filtered_rows = []
    for row in asistencias:
        parsed = _parse_date(row.get("fecha"))
        if not parsed or not (current_start <= parsed <= week_end):
            continue
        text = f"{row.get('nombre_trabajador', '')} {row.get('dni', '')} {row.get('nombre_tienda', '')} {row.get('fecha', '')}".lower()
        if search_query and search_query.lower() not in text:
            continue
        filtered_rows.append(row)

    table_html = _render_attendance_table(filtered_rows)
    if table_html:
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("No hay asistencias para este rango.")
