import streamlit as st


def render_tiendas(api):
    api.section_header("Nueva tienda / sede", "Registra un punto de venta en el sistema")

    with st.form("create_store_form", clear_on_submit=True):
        col_1, col_2 = st.columns(2)
        id_tienda = col_1.text_input("ID tienda *", placeholder="tienda_001")
        nombre_tienda = col_1.text_input("Nombre tienda *", placeholder="Tienda Centro")
        id_sede = col_1.text_input("ID sede *", placeholder="sede_001")
        correo = col_2.text_input("Correo *", placeholder="tienda@empresa.com")
        password = col_2.text_input("Contraseña del correo *", type="password")
        nombre_sede = col_2.text_input("Nombre sede *", placeholder="Sede Lima Norte")
        direccion = col_2.text_input("Dirección *", placeholder="Av. Principal 123")

        submitted = st.form_submit_button("⬡  Registrar tienda", use_container_width=True)

    if not submitted:
        return

    missing = api.required_missing({
        "ID tienda": id_tienda,
        "Correo": correo,
        "Contraseña": password,
        "Nombre tienda": nombre_tienda,
        "ID sede": id_sede,
        "Nombre sede": nombre_sede,
        "Dirección": direccion,
    })
    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    doc_id = api.normalize_doc_id(id_tienda)
    if api.document_exists(api.STORE_COLLECTION, doc_id):
        st.error(f"Ya existe una tienda con el ID `{doc_id}`.")
        return

    store_data = {
        "id_tienda": id_tienda.strip(),
        "correo": api.normalize_email(correo),
        "password": password,
        "contrasena": password,
        "nombre_tienda": nombre_tienda.strip(),
        "id_sede": id_sede.strip(),
        "nombre_sede": nombre_sede.strip(),
        "direccion": direccion.strip(),
    }
    qr_token = api.create_store_with_qr(doc_id, store_data)
    st.success(f"✓  Tienda registrada → `{api.STORE_COLLECTION}/{doc_id}`")
    st.caption(f"QR activo creado: `{api.QR_ACTIVE_COLLECTION}/{doc_id}` - token `{qr_token}`")
