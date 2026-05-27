import streamlit as st


def render_trabajadores(api):
    api.section_header("Nuevo trabajador", "Crea el perfil de un colaborador con su horario")
    tiendas = api.get_tiendas()

    if not tiendas:
        st.warning("Primero registra al menos una tienda para asignar la sede.")
        return

    tienda_options = {
        f"{t['nombre_tienda']}  ·  {t['nombre_sede']}": t for t in tiendas
    }

    selected_days = st.multiselect(
        "Días laborables *",
        options=list(api.WEEK_DAYS),
        default=list(api.WEEK_DAYS),
        format_func=str.capitalize,
    )
    if not selected_days:
        st.warning("Selecciona al menos un día para el horario.")

    with st.form("create_worker_form", clear_on_submit=True):
        col_1, col_2 = st.columns(2)
        id_trabajador = col_1.text_input("ID trabajador *", placeholder="trab_001")
        nombre_trabajador = col_1.text_input("Nombre completo *", placeholder="Juan Pérez")
        dni = col_1.text_input("DNI *", placeholder="12345678")
        area = col_1.text_input("Área *", placeholder="Ventas")
        correo = col_2.text_input("Correo *", placeholder="juan@empresa.com")
        password = col_2.text_input("Contraseña del correo *", type="password")
        cuenta_bancaria = col_2.text_input("Cuenta bancaria *", placeholder="0011-0123-...")
        foto_dni = col_2.file_uploader(
            "Foto DNI *",
            type=["jpg", "jpeg", "png", "pdf"],
        )
        tienda_label = st.selectbox(
            "Tienda / sede asignada *",
            options=list(tienda_options.keys()),
            index=None,
            placeholder="Selecciona una tienda",
        )
        horario = api.build_schedule_inputs(selected_days)
        submitted = st.form_submit_button("⬡  Registrar trabajador", use_container_width=True)

    if not submitted:
        return

    missing = api.required_missing({
        "ID trabajador": id_trabajador,
        "Correo": correo,
        "Contraseña": password,
        "Área": area,
        "DNI": dni,
        "Foto DNI": foto_dni,
        "Tienda / sede": tienda_label,
        "Nombre": nombre_trabajador,
        "Cuenta bancaria": cuenta_bancaria,
    })
    if not selected_days:
        missing.append("Días laborables")

    if missing:
        st.error("Campos requeridos: " + ", ".join(missing))
        return

    doc_id = api.normalize_doc_id(id_trabajador)
    if api.document_exists(api.WORKER_COLLECTION, doc_id):
        st.error(f"Ya existe un trabajador con el ID `{doc_id}`.")
        return

    tienda = tienda_options[tienda_label]
    try:
        uploaded_dni = api.upload_worker_file(foto_dni, doc_id)
    except Exception as exc:
        st.error(f"No se pudo subir el archivo a Cloudinary: {exc}")
        return

    api.create_document(api.WORKER_COLLECTION, doc_id, {
        "id_trabajador": id_trabajador.strip(),
        "correo": api.normalize_email(correo),
        "password": password,
        "contrasena": password,
        "area": area.strip(),
        "dni": dni.strip(),
        "foto_dni": uploaded_dni["secure_url"],
        "foto_dni_public_id": uploaded_dni["public_id"],
        "foto_dni_asset_id": uploaded_dni["asset_id"],
        "foto_dni_resource_type": uploaded_dni["resource_type"],
        "foto_dni_nombre_archivo": uploaded_dni["name"],
        "id_sede": tienda["id_sede"],
        "nombre_sede": tienda["nombre_sede"],
        "nombre_trabajador": nombre_trabajador.strip(),
        "cuenta_bancaria": cuenta_bancaria.strip(),
        "fecha_creada": api.firestore.SERVER_TIMESTAMP,
        "horario": horario,
    })
    st.success(f"✓  Trabajador registrado → `{api.WORKER_COLLECTION}/{doc_id}`")
