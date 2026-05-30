import streamlit as st


# ================================================================
#  HELPERS UI
# ================================================================

def _badge_estado(estado: bool) -> str:
    if estado:
        return '<span class="badge badge--active">ACTIVO</span>'
    return '<span class="badge badge--inactive">INACTIVO</span>'


def _badge_cargo(cargo: str) -> str:
    if not cargo:
        return '<span class="badge badge--gray">—</span>'
    return f'<span class="badge badge--blue">{cargo.upper()}</span>'


# ================================================================
#  HELPERS LÓGICA  (sin cambios)
# ================================================================

def _worker_label(worker):
    return f"{worker.get('nombre_trabajador', '')} · {worker.get('dni', '')}"


def _build_initial_schedule(horarios, dni):
    schedule = {}
    for row in horarios:
        if str(row.get("dni_trabajador", "")).strip() != str(dni).strip():
            continue
        schedule[row.get("dia_semana", "")] = {
            "horario_entrada":        row.get("horario_entrada", ""),
            "horario_inicio_receso":  row.get("horario_inicio_receso", ""),
            "horario_fin_receso":     row.get("horario_fin_receso", ""),
            "horario_salida":         row.get("horario_salida", ""),
        }
    return schedule


def _selected_days_from_worker(worker):
    if not worker:
        return []
    days = worker.get("dias_horario", [])
    if isinstance(days, list):
        return [day for day in days if day]
    if isinstance(days, str):
        return [part.strip() for part in days.split(",") if part.strip()]
    return []


def _schedule_rows_view(horarios):
    return [
        {
            "DNI":         row.get("dni_trabajador", ""),
            "Trabajador":  row.get("nombre_trabajador", ""),
            "Tienda":      row.get("nombre_tienda", ""),
            "Día":         row.get("dia_semana", ""),
            "Entrada":     row.get("horario_entrada", ""),
            "Ini. receso": row.get("horario_inicio_receso", ""),
            "Fin receso":  row.get("horario_fin_receso", ""),
            "Salida":      row.get("horario_salida", ""),
        }
        for row in horarios
    ]


# ================================================================
#  FORMULARIO  (lógica intacta, solo estilos en clases CSS)
# ================================================================

def _render_worker_form(api, worker=None):
    tiendas = api.get_tiendas()
    if not tiendas:
        st.warning("Primero registra al menos una tienda.")
        return

    form_kind = "edit" if worker else "create"
    form_seed = int(st.session_state.get(f"worker_{form_kind}_seed", 0))

    # ── Encabezado del formulario ────────────────────────────────
    card_class = "form-card form-card--edit" if worker else "form-card form-card--create"
    titulo     = "Editar trabajador" if worker else "Nuevo trabajador"
    st.markdown(f"""
    <div class="{card_class}">
        <p class="form-card__title">{titulo}</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Días laborables (fuera del form para multiselect reactivo) ─
    selected_days = st.multiselect(
        "Días laborables *",
        options=list(api.WEEK_DAYS),
        default=_selected_days_from_worker(worker) if worker else list(api.WEEK_DAYS),
        format_func=str.capitalize,
        key=f"worker_{form_kind}_days_{form_seed}",
    )
    if not selected_days:
        st.warning("Selecciona al menos un día para el horario.")

    initial_schedule  = _build_initial_schedule(api.get_horarios_trabajador(), worker.get("dni")) if worker else None
    existing_password = worker.get("contrasena", "") if worker else ""
    existing_photo    = worker.get("foto_dni", "")   if worker else ""
    estado_actual     = bool(worker.get("estado", True)) if worker else True

    tienda_options = {f"{t['nombre_tienda']} · {t['id_tienda']}": t for t in tiendas}
    selected_store_key = None
    if worker:
        for label, store in tienda_options.items():
            if store["id_tienda"] == worker.get("id_sede", ""):
                selected_store_key = label
                break

    button_text = "Guardar cambios" if worker else "Registrar trabajador"

    with st.form(f"worker_form_{form_kind}_{form_seed}", clear_on_submit=False):
        col_1, col_2 = st.columns(2)

        dni     = col_1.text_input("DNI *",            value=worker.get("dni", "")               if worker else "", placeholder="12345678",           key=f"{form_kind}_dni_{form_seed}")
        nombre  = col_1.text_input("Nombre completo *", value=worker.get("nombre_trabajador", "") if worker else "", placeholder="Juan Pérez",          key=f"{form_kind}_nombre_{form_seed}")
        cargo   = col_1.text_input("Cargo",             value=worker.get("area", "")              if worker else "", placeholder="Ventas",              key=f"{form_kind}_cargo_{form_seed}")
        sueldo  = col_1.number_input("Sueldo", min_value=0.0, step=50.0, format="%.2f",
                                     value=float(worker.get("sueldo") or 0) if worker else 0.0,   key=f"{form_kind}_sueldo_{form_seed}")

        correo   = col_2.text_input("Correo",      value=worker.get("correo", "")   if worker else "", placeholder="juan@empresa.com",      key=f"{form_kind}_correo_{form_seed}")
        password = col_2.text_input("Contraseña",  type="password", placeholder="Dejar vacío para mantener",                                key=f"{form_kind}_password_{form_seed}")
        telefono = col_2.text_input("Teléfono",    value=worker.get("telefono", "") if worker else "", placeholder="+51 999 999 999",        key=f"{form_kind}_telefono_{form_seed}")
        csi      = col_2.text_input("CSI / código interno", value=worker.get("csi", "") if worker else "", placeholder="CSI-001",           key=f"{form_kind}_csi_{form_seed}")
        estado   = col_2.selectbox(
            "Estado",
            options=[True, False],
            index=0 if estado_actual else 1,
            format_func=lambda value: "Activo" if value else "Inactivo",
            key=f"{form_kind}_estado_{form_seed}",
        )
        foto_dni = col_2.file_uploader(
            "Foto DNI" + (" *" if worker is None else ""),
            type=["jpg", "jpeg", "png", "pdf"],
            key=f"{form_kind}_foto_{form_seed}",
        )

        tienda_label = st.selectbox(
            "Tienda asignada *",
            options=list(tienda_options.keys()),
            index=list(tienda_options.keys()).index(selected_store_key) if selected_store_key in tienda_options else None,
            placeholder="Selecciona una tienda",
            key=f"{form_kind}_tienda_{form_seed}",
        )

        horario   = api.build_schedule_inputs(selected_days, key_prefix=f"{form_kind}_{form_seed}", initial_schedule=initial_schedule)
        submitted = st.form_submit_button(button_text, use_container_width=True)

    if not submitted:
        return None

    # ── Validaciones ─────────────────────────────────────────────
    missing = api.required_missing({"DNI": dni, "Nombre": nombre, "Tienda": tienda_label})
    if worker is None and not foto_dni:
        missing.append("Foto DNI")
    if not selected_days:
        missing.append("Días laborables")

    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return None

    # ── Subir foto ───────────────────────────────────────────────
    doc_id    = str(dni).strip()
    tienda    = tienda_options[tienda_label]
    photo_url = existing_photo
    if foto_dni:
        try:
            uploaded_dni = api.upload_worker_file(foto_dni, doc_id)
            photo_url    = uploaded_dni["secure_url"]
        except Exception as exc:
            st.error(f"No se pudo subir el archivo a Cloudinary: {exc}")
            return None
    elif not photo_url and worker is None:
        st.error("Debes subir la foto del DNI.")
        return None

    # ── Persistir ────────────────────────────────────────────────
    password_value  = password.strip() if password else ""
    stored_password = worker.get("contrasena", "") if worker else ""

    worker_data = {
        "dni":        doc_id,
        "id_tienda":  tienda["id_tienda"],
        "correo":     api.normalize_email(correo),
        "contrasena": api.hash_password(password_value) if password_value else stored_password,
        "nombre":     nombre.strip(),
        "cargo":      cargo.strip(),
        "sueldo":     float(sueldo) if sueldo is not None else None,
        "telefono":   telefono.strip(),
        "csi":        csi.strip(),
        "foto_dni":   photo_url,
        "estado":     bool(estado),
    }

    api.create_document(api.WORKER_COLLECTION, doc_id, worker_data)
    api.save_worker_schedule(worker_data, selected_days, horario)
    st.session_state["worker_success_message"] = f"✓  Trabajador guardado → `{api.WORKER_COLLECTION}/{doc_id}`"
    st.cache_data.clear()
    st.session_state[f"worker_{form_kind}_seed"] = form_seed + 1
    st.session_state["worker_form_mode"] = "list"
    st.rerun()


# ================================================================
#  VISTA PRINCIPAL
# ================================================================

def render_trabajadores(api):

    # ── Page header ──────────────────────────────────────────────
    st.markdown("""
    <div style="margin-bottom:24px;">
        <h2 class="page-title">Trabajadores</h2>
        <p class="page-subtitle">Gestión de personal, horarios y accesos</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Inicializar session_state ────────────────────────────────
    for key in ["worker_form_mode", "worker_success_message", "worker_id_editar"]:
        if key not in st.session_state:
            st.session_state[key] = None

    # ── Feedback ─────────────────────────────────────────────────
    msg = st.session_state.pop("worker_success_message", None)
    if msg:
        st.success(msg)

    tiendas     = api.get_tiendas()
    trabajadores = api.get_trabajadores()
    horarios    = api.get_horarios_trabajador()

    if not tiendas:
        st.warning("Primero registra al menos una tienda.")
        return

    # ── Barra superior ───────────────────────────────────────────
    col_busq, col_btn = st.columns([3, 1])
    with col_busq:
        busqueda = st.text_input(
            "🔍 Buscar por nombre, DNI o cargo",
            placeholder="Escribe para filtrar...",
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("➕ Nuevo trabajador", use_container_width=True):
            st.session_state["worker_form_mode"]  = "crear"
            st.session_state["worker_id_editar"]  = None
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Formulario CREAR ─────────────────────────────────────────
    if st.session_state["worker_form_mode"] == "crear":
        _render_worker_form(api, worker=None)
        if st.button("✖ Cancelar", key="btn_cancel_crear_worker"):
            st.session_state["worker_form_mode"] = None
            st.rerun()
        st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:20px 0'>", unsafe_allow_html=True)

    # ── Filtrar lista ────────────────────────────────────────────
    if busqueda:
        q = busqueda.lower()
        trabajadores = [
            w for w in trabajadores if
            q in w.get("nombre_trabajador", "").lower() or
            q in w.get("dni", "").lower() or
            q in (w.get("area", "") or "").lower()
        ]

    if not trabajadores:
        st.info("No se encontraron trabajadores.")
        return

    # ── Encabezado tabla ─────────────────────────────────────────
    st.markdown("""
    <div style='margin-bottom:12px;'>
        <span class='section-header__title'>Lista de trabajadores</span>
    </div>
    """, unsafe_allow_html=True)

    col_h = st.columns([2.5, 1.2, 1.2, 1.2, 1, 0.6, 0.6])
    headers = ["TRABAJADOR", "DNI", "CARGO", "TIENDA", "ESTADO", "", ""]
    for col, h in zip(col_h, headers):
        col.markdown(f"<span class='table-header'>{h}</span>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── Filas ────────────────────────────────────────────────────
    for w in trabajadores:
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([2.5, 1.2, 1.2, 1.2, 1, 0.6, 0.6])

            with col1:
                alias = w.get("nombre_sede", "") or ""
                st.markdown(f"""
                <div>
                    <span class="row-main">{w.get('nombre_trabajador', '—')}</span>
                    {'<br><span class="row-sub">' + alias + '</span>' if alias else ''}
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.caption(w.get("dni", "—"))

            with col3:
                st.markdown(_badge_cargo(w.get("area", "")), unsafe_allow_html=True)

            with col4:
                st.caption(w.get("nombre_sede", "—"))

            with col5:
                st.markdown(_badge_estado(w.get("estado", True)), unsafe_allow_html=True)

            # Toggle activo/inactivo
            with col6:
                estado_actual = w.get("estado", True)
                emoji = "🟢" if estado_actual else "🔴"
                nuevo_estado  = not estado_actual
                if st.button(emoji, key=f"toggle_w_{w['dni']}", help="Cambiar estado", use_container_width=True):
                    try:
                        api.update_document(
                            api.WORKER_COLLECTION,
                            w["dni"],
                            {"estado": bool(nuevo_estado)},
                            key_field="dni",
                        )
                        st.cache_data.clear()
                        st.session_state["worker_success_message"] = f"✅ Estado actualizado."
                    except Exception as e:
                        st.session_state["worker_success_message"] = f"Error: {e}"
                    st.rerun()

            # Editar
            with col7:
                if st.button("🖍", key=f"edit_w_{w['dni']}", help="Editar", use_container_width=True):
                    st.session_state["worker_form_mode"] = "editar"
                    st.session_state["worker_id_editar"] = w["dni"]
                    st.rerun()

        # ── Formulario editar inline ──────────────────────────────
        if (
            st.session_state["worker_form_mode"] == "editar"
            and st.session_state["worker_id_editar"] == w["dni"]
        ):
            _render_worker_form(api, worker=w)

            if st.button("✖ Cancelar edición", key=f"cancel_edit_w_{w['dni']}"):
                st.session_state["worker_form_mode"] = None
                st.session_state["worker_id_editar"] = None
                st.rerun()

            # ── Horario del trabajador (inline bajo el form) ──────
            st.markdown("""
            <div style="margin:16px 0 8px;">
                <span class="section-header__title" style="font-size:14px;">Horario registrado</span>
            </div>
            """, unsafe_allow_html=True)

            horarios_w = [
                r for r in horarios
                if str(r.get("dni_trabajador", "")).strip() == str(w.get("dni", "")).strip()
            ]
            if horarios_w:
                cols_h = st.columns([1.2, 1, 1, 1, 1])
                for col, label in zip(cols_h, ["Día", "Entrada", "Ini. receso", "Fin receso", "Salida"]):
                    col.markdown(f"<span class='table-header'>{label}</span>", unsafe_allow_html=True)
                for row in horarios_w:
                    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 1])
                    c1.caption(row.get("dia_semana", "—").capitalize())
                    c2.caption(row.get("horario_entrada", "—"))
                    c3.caption(row.get("horario_inicio_receso", "—"))
                    c4.caption(row.get("horario_fin_receso", "—"))
                    c5.caption(row.get("horario_salida", "—"))
            else:
                st.info("Este trabajador aún no tiene horarios registrados.")
