from datetime import date, datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components


def _parse_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _week_start(current_date):
    return current_date - timedelta(days=current_date.weekday())


def _week_label(start_date):
    end_date = start_date + timedelta(days=6)
    return f"{start_date.strftime('%d/%m/%Y')} -> {end_date.strftime('%d/%m/%Y')}"


def _cell_html(attendance_row):
    if not attendance_row:
        return '<span class="m-empty">-</span>'

    entrada = attendance_row.get("hora_inicio") or "-"
    salida = attendance_row.get("hora_final") or "-"
    is_late = bool(attendance_row.get("late"))
    entrada_color = "#dc2626" if is_late else "#1d4ed8"
    return (
        '<div style="display:flex;flex-direction:column;gap:.12rem;line-height:1.15;">'
        f'<span style="font-family:Space Mono,monospace;font-size:.78rem;color:{entrada_color};font-weight:700;">{entrada}</span>'
        f'<span style="font-family:Space Mono,monospace;font-size:.78rem;color:#166534;font-weight:700;">{salida}</span>'
        "</div>"
    )


def _render_weekly_matrix(workers, attendance_map, days):
    rows_html = []
    for worker in workers:
        dni = worker.get("dni", "")
        worker_attendance = attendance_map.get(dni, {})
        day_cells = []
        for current_day in days:
            attendance_row = worker_attendance.get(current_day)
            day_cells.append(f"<td>{_cell_html(attendance_row)}</td>")

        rows_html.append(
            f"""
            <tr>
              <td class="worker-td">
                <div class="worker-name">{worker.get('nombre_trabajador', '-')}</div>
                <div class="worker-meta">DNI {dni} · {worker.get('nombre_sede', '-')}</div>
              </td>
              {''.join(day_cells)}
            </tr>
            """
        )

    header_cells = "".join(
        f"<th>{day.strftime('%A')}<br><span style='font-weight:400;font-size:.6rem;'>{day.strftime('%d/%m')}</span></th>"
        for day in days
    )

    return f"""
    <html>
    <head>
      <style>
        body {{ margin:0; font-family:'DM Sans', sans-serif; }}
        .wrap {{
          overflow-x:auto;
          border:1px solid #e2e8f0;
          border-radius:12px;
          background:#fff;
          box-shadow:0 1px 6px rgba(15,23,42,.04);
        }}
        .at-table {{ width:100%; border-collapse:collapse; font-size:.85rem; }}
        .at-table thead th {{
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
        }}
        .at-table tbody tr {{ border-bottom:1px solid #f1f5f9; }}
        .at-table tbody tr:hover {{ background:#fafbff; }}
        .at-table td {{ padding:1rem .9rem; vertical-align:middle; color:#1e293b; }}
        .at-table td.worker-td {{ min-width:180px; }}
        .worker-name {{ font-weight:700; color:#0f172a; font-size:.85rem; }}
        .worker-meta {{ font-size:.69rem; color:#64748b; margin-top:.15rem; }}
        .m-empty {{
            color:#94a3b8;
            font-family:'Space Mono',monospace;
            font-size:.78rem;
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <table class="at-table">
          <thead>
            <tr>
              <th>Trabajador</th>
              {header_cells}
            </tr>
          </thead>
          <tbody>{''.join(rows_html)}</tbody>
        </table>
      </div>
    </body>
    </html>
    """


def render_resumen(api=None):
    if api is None:
        st.error("Falta el contexto de la app.")
        return

    with st.spinner("Cargando asistencias..."):
        asistencias = api.get_asistencias()
        trabajadores = api.get_trabajadores()
        tiendas = api.get_tiendas()
        horarios = api.get_horarios_trabajador()

    store_options = {"Todas": None}
    store_options.update({f"{store['nombre_tienda']} · {store['id_tienda']}": store for store in tiendas})

    if "resumen_week" not in st.session_state:
        all_dates = [_parse_date(row.get("fecha")) for row in asistencias if _parse_date(row.get("fecha"))]
        st.session_state["resumen_week"] = max(all_dates) if all_dates else date.today()

    current_start = _week_start(st.session_state["resumen_week"])
    week_end = current_start + timedelta(days=6)
    week_days = [current_start + timedelta(days=i) for i in range(7)]

    sc1, sc2, sc3, sc4 = st.columns([2.4, 1.3, 0.9, 1.1])
    search_query = sc1.text_input(
        "Buscar", placeholder="Nombre, DNI o sede...", key="resumen_search", label_visibility="collapsed"
    )
    selected_store_label = sc2.selectbox(
        "Tienda",
        options=list(store_options.keys()),
        index=0,
        key="resumen_store_filter",
        label_visibility="collapsed",
    )
    if sc3.button("Anterior", use_container_width=True, key="resumen_prev_button"):
        st.session_state["resumen_week"] = current_start - timedelta(days=7)
        st.rerun()
    picked = sc4.date_input("Semana", value=current_start, key="resumen_picker", label_visibility="collapsed")
    if picked != current_start:
        st.session_state["resumen_week"] = picked
        current_start = _week_start(picked)
        week_end = current_start + timedelta(days=6)
        week_days = [current_start + timedelta(days=i) for i in range(7)]

    if selected_store_label != "Todas":
        selected_store = store_options[selected_store_label]
        trabajadores = [
            worker for worker in trabajadores
            if str(worker.get("id_sede", "")).strip() == str(selected_store["id_tienda"]).strip()
        ]
        worker_ids = {worker.get("dni", "") for worker in trabajadores}
        asistencias = [row for row in asistencias if str(row.get("dni", "")).strip() in worker_ids]

    valid_dates = [_parse_date(row.get("fecha")) for row in asistencias if _parse_date(row.get("fecha"))]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Tiendas", len(tiendas))
    m2.metric("Trabajadores", len(trabajadores))
    m3.metric("Registros", len(asistencias))
    m4.metric(
        "Rango de fechas",
        f"{min(valid_dates).strftime('%d/%m')} - {max(valid_dates).strftime('%d/%m')}"
        if valid_dates else "-",
    )

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    st.caption(f"Semana: `{_week_label(current_start)}` · `{len(asistencias):,}` registros")

    attendance_map = {}
    for row in asistencias:
        parsed = _parse_date(row.get("fecha"))
        if not parsed or not (current_start <= parsed <= week_end):
            continue
        worker_key = str(row.get("dni", "")).strip()
        attendance_map.setdefault(worker_key, {})[parsed] = row

    schedule_map = {}
    for row in horarios:
        dni = str(row.get("dni_trabajador", "")).strip()
        day_name = str(row.get("dia_semana", "")).strip()
        entrada_schedule = row.get("horario_entrada")
        if isinstance(entrada_schedule, str):
            try:
                entrada_schedule = datetime.strptime(entrada_schedule[:5], "%H:%M").time()
            except ValueError:
                entrada_schedule = None
        schedule_map.setdefault(dni, {})[day_name] = entrada_schedule

    day_name_map = {
        0: "lunes",
        1: "martes",
        2: "miercoles",
        3: "jueves",
        4: "viernes",
        5: "sabado",
        6: "domingo",
    }

    for worker_dni, worker_days in attendance_map.items():
        for day_date, attendance_row in worker_days.items():
            worker_schedule = schedule_map.get(worker_dni, {})
            scheduled_time = worker_schedule.get(day_name_map.get(day_date.weekday(), ""))
            actual_time = attendance_row.get("hora_inicio")
            if isinstance(actual_time, str):
                actual_time = actual_time[:5]
            if scheduled_time and actual_time:
                try:
                    actual_obj = datetime.strptime(actual_time[:5], "%H:%M").time()
                    attendance_row["late"] = actual_obj > scheduled_time
                except ValueError:
                    attendance_row["late"] = False
            else:
                attendance_row["late"] = False

    filtered_workers = []
    for worker in trabajadores:
        text = f"{worker.get('nombre_trabajador', '')} {worker.get('dni', '')} {worker.get('nombre_sede', '')}".lower()
        if search_query and search_query.lower() not in text:
            continue
        filtered_workers.append(worker)

    total_present = sum(
        1
        for worker in filtered_workers
        for current_day in week_days
        if attendance_map.get(worker.get("dni", ""), {}).get(current_day)
    )
    total_possible = len(filtered_workers) * 7

    c1, c2 = st.columns(2)
    c1.metric("Marcas en la semana", total_present)
    c2.metric("Faltas en la semana", max(total_possible - total_present, 0))

    if not filtered_workers:
        st.info("No hay trabajadores o asistencias para este rango.")
        return

    table_html = _render_weekly_matrix(filtered_workers, attendance_map, week_days)
    components.html(table_html, height=max(320, 92 + (len(filtered_workers) * 88)), scrolling=True)
