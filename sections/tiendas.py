from datetime import date

import streamlit as st


def _badge_estado(estado: bool) -> str:
    if estado:
        return '<span class="badge badge--active">ACTIVA</span>'
    return '<span class="badge badge--inactive">INACTIVA</span>'


def _store_label(store):
    return f"{store.get('nombre_tienda', '')} · {store.get('id_tienda', '')}"


def _render_store_form(api, store=None):
    form_kind = "edit" if store else "create"
    form_seed = int(st.session_state.get(f"store_{form_kind}_seed", 0))

    card_class = "form-card form-card--edit" if store else "form-card form-card--create"
    titulo = "Editar tienda" if store else "Nueva tienda"
    st.markdown(
        f"""
        <div class="{card_class}">
            <p class="form-card__title">{titulo}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    estado_actual = bool(store.get("estado", True)) if store else True
    fecha_default = (
        date.fromisoformat(str(store.get("fecha_apertura"))[:10])
        if store and store.get("fecha_apertura")
        else date.today()
    )

    with st.form(f"store_form_{form_kind}_{form_seed}", clear_on_submit=False):
        col_1, col_2 = st.columns(2)
        nombre_tienda = col_1.text_input(
            "Nombre tienda *",
            value=store.get("nombre_tienda", "") if store else "",
            placeholder="Tienda Centro",
            key=f"{form_kind}_store_nombre_{form_seed}",
        )
        correo = col_1.text_input(
            "Correo *",
            value=store.get("correo", "") if store else "",
            placeholder="tienda@empresa.com",
            key=f"{form_kind}_store_correo_{form_seed}",
        )
        telefono = col_1.text_input(
            "Teléfono",
            value=store.get("telefono", "") if store else "",
            placeholder="+51 999 999 999",
            key=f"{form_kind}_store_telefono_{form_seed}",
        )
        direccion = col_2.text_input(
            "Dirección",
            value=store.get("direccion", "") if store else "",
            placeholder="Av. Principal 123",
            key=f"{form_kind}_store_direccion_{form_seed}",
        )
        fecha_apertura = col_2.date_input(
            "Fecha apertura",
            value=fecha_default,
            key=f"{form_kind}_store_fecha_{form_seed}",
        )
        password = col_2.text_input(
            "Contraseña" + (" *" if store is None else ""),
            type="password",
            placeholder="Dejar vacío para mantener" if store else "",
            key=f"{form_kind}_store_password_{form_seed}",
        )
        estado = col_2.selectbox(
            "Estado",
            options=[True, False],
            index=0 if estado_actual else 1,
            format_func=lambda value: "Activa" if value else "Inactiva",
            key=f"{form_kind}_store_estado_{form_seed}",
        )
        submitted = st.form_submit_button(
            "Guardar cambios" if store else "⬡  Registrar tienda",
            use_container_width=True,
        )

    return {
        "submitted": submitted,
        "nombre_tienda": nombre_tienda,
        "correo": correo,
        "telefono": telefono,
        "direccion": direccion,
        "fecha_apertura": fecha_apertura,
        "password": password,
        "estado": estado,
        "form_seed": form_seed,
        "form_kind": form_kind,
    }


def render_tiendas(api):
    api.section_header("Tiendas", "CRUD completo para sedes y accesos")
    tiendas = api.get_tiendas()

    success_message = st.session_state.pop("store_success_message", None)
    if success_message:
        st.success(success_message)

    for key in ["store_form_mode", "store_id_editar"]:
        if key not in st.session_state:
            st.session_state[key] = None

    mode = st.session_state.get("store_form_mode", "list")

    col_busq, col_btn = st.columns([3, 1])
    with col_busq:
        busqueda = st.text_input(
            "🔍 Buscar por nombre, correo o dirección",
            placeholder="Escribe para filtrar...",
            label_visibility="collapsed",
        )
    with col_btn:
        if st.button("➕ Nueva tienda", use_container_width=True):
            st.session_state["store_form_mode"] = "create"
            st.session_state["store_id_editar"] = None
            st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if not tiendas:
        st.warning("Todavía no hay tiendas registradas.")
        if mode == "create":
            st.markdown("---")
            form = _render_store_form(api, store=None)
            if form["submitted"]:
                _handle_store_create(api, form)
        return

    if busqueda:
        q = busqueda.lower()
        tiendas = [
            t for t in tiendas
            if q in t.get("nombre_tienda", "").lower()
            or q in t.get("correo", "").lower()
            or q in t.get("direccion", "").lower()
        ]

    if not tiendas:
        st.info("No se encontraron tiendas.")
        return

    st.markdown(
        """
        <div style='margin-bottom:12px;'>
            <span class='section-header__title'>Lista de tiendas</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    headers = ["TIENDA", "ID", "CORREO", "DIRECCIÓN", "ESTADO", "", ""]
    cols_head = st.columns([2.5, 1.4, 1.6, 1.8, 1, 0.6, 0.6])
    for col, header in zip(cols_head, headers):
        col.markdown(f"<span class='table-header'>{header}</span>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    for store in tiendas:
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6, col7 = st.columns([2.5, 1.4, 1.6, 1.8, 1, 0.6, 0.6])

            with col1:
                st.markdown(
                    f"""
                    <div>
                        <span class="row-main">{store.get('nombre_tienda', '—')}</span>
                        <br><span class="row-sub">{store.get('telefono', '') or 'Sin teléfono'}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                st.caption(store.get("id_tienda", "—"))
            with col3:
                st.caption(store.get("correo", "—"))
            with col4:
                st.caption(store.get("direccion", "—"))
            with col5:
                st.markdown(_badge_estado(store.get("estado", True)), unsafe_allow_html=True)

            with col6:
                estado_actual = bool(store.get("estado", True))
                emoji = "🟢" if estado_actual else "🔴"
                nuevo_estado = not estado_actual
                if st.button(emoji, key=f"toggle_store_{store['id_tienda']}", help="Cambiar estado", use_container_width=True):
                    try:
                        api.update_document(
                            api.STORE_COLLECTION,
                            store["id_tienda"],
                            {"estado": bool(nuevo_estado)},
                            key_field="id_tienda",
                        )
                        st.cache_data.clear()
                        st.session_state["store_success_message"] = "✅ Estado actualizado."
                    except Exception as exc:
                        st.session_state["store_success_message"] = f"Error: {exc}"
                    st.rerun()

            with col7:
                if st.button("🖍", key=f"edit_store_{store['id_tienda']}", help="Editar", use_container_width=True):
                    st.session_state["store_form_mode"] = "edit"
                    st.session_state["store_id_editar"] = store["id_tienda"]
                    st.rerun()

        if st.session_state.get("store_form_mode") == "edit" and st.session_state.get("store_id_editar") == store["id_tienda"]:
            st.markdown("---")
            form = _render_store_form(api, store=store)
            if form["submitted"]:
                _handle_store_update(api, store, form)

            if st.button("✖ Cancelar edición", key=f"cancel_edit_store_{store['id_tienda']}"):
                st.session_state["store_form_mode"] = "list"
                st.session_state["store_id_editar"] = None
                st.rerun()

    if mode == "create":
        st.markdown("---")
        form = _render_store_form(api, store=None)
        if form["submitted"]:
            _handle_store_create(api, form)


def _handle_store_create(api, form):
    missing = api.required_missing({
        "Nombre tienda": form["nombre_tienda"],
        "Correo": form["correo"],
        "Contraseña": form["password"],
    })
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    store_id = api.normalize_doc_id(form["nombre_tienda"])
    if api.document_exists(api.STORE_COLLECTION, store_id):
        st.error(f"Ya existe una tienda con el ID `{store_id}`.")
        return

    store_data = {
        "correo": api.normalize_email(form["correo"]),
        "contrasena": api.hash_password(form["password"]),
        "nombre": form["nombre_tienda"].strip(),
        "telefono": form["telefono"].strip(),
        "direccion": form["direccion"].strip(),
        "fecha_apertura": form["fecha_apertura"].isoformat() if form["fecha_apertura"] else None,
        "estado": bool(form["estado"]),
    }
    api.create_store_with_qr(store_id, store_data)
    st.cache_data.clear()
    st.session_state["store_success_message"] = f"✓  Tienda registrada → `{api.STORE_COLLECTION}/{store_id}`"
    st.session_state["store_form_seed"] = form["form_seed"] + 1
    st.session_state["store_form_mode"] = "list"
    st.rerun()


def _handle_store_update(api, store, form):
    missing = api.required_missing({
        "Nombre tienda": form["nombre_tienda"],
        "Correo": form["correo"],
    })
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    store_data = {
        "correo": api.normalize_email(form["correo"]),
        "nombre": form["nombre_tienda"].strip(),
        "telefono": form["telefono"].strip(),
        "direccion": form["direccion"].strip(),
        "fecha_apertura": form["fecha_apertura"].isoformat() if form["fecha_apertura"] else None,
        "estado": bool(form["estado"]),
    }
    if form["password"].strip():
        store_data["contrasena"] = api.hash_password(form["password"])

    api.update_document(api.STORE_COLLECTION, store["id_tienda"], store_data, key_field="id_tienda")
    st.cache_data.clear()
    st.session_state["store_success_message"] = f"✓  Tienda guardada → `{store['id_tienda']}`"
    st.session_state["store_form_seed"] = form["form_seed"] + 1
    st.session_state["store_form_mode"] = "list"
    st.session_state["store_id_editar"] = None
    st.rerun()
