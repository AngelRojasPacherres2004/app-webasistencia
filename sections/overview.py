import streamlit as st


def render_overview(api):
    tiendas = api.get_tiendas()
    trabajadores = api.get_trabajadores()
    asistencias = api.get_asistencias()

    m1, m2, m3 = st.columns(3)
    m1.metric("Tiendas", len(tiendas))
    m2.metric("Trabajadores", len(trabajadores))
    m3.metric("Asistencias recientes", len(asistencias))

    st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)

    tab_t, tab_w, tab_a = st.tabs(["Tiendas", "Trabajadores", "Asistencias"])

    with tab_t:
        st.caption(f"colección Firebase: `{api.STORE_COLLECTION}`")
        if tiendas:
            st.dataframe(tiendas, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay tiendas registradas.")

    with tab_w:
        st.caption(f"colección Firebase: `{api.WORKER_COLLECTION}`")
        if trabajadores:
            st.dataframe(trabajadores, use_container_width=True, hide_index=True)
            worker_options = {
                f"{t['nombre_trabajador']}  ·  {t['dni']}": t for t in trabajadores
            }
            selected_worker_label = st.selectbox(
                "Ver asistencias de trabajador",
                options=list(worker_options.keys()),
                index=None,
                placeholder="Selecciona un trabajador",
            )
            if st.button(
                "Ver asistencias",
                disabled=not selected_worker_label,
                use_container_width=True,
            ):
                api.worker_attendance_dialog(worker_options[selected_worker_label])
        else:
            st.info("Todavía no hay trabajadores registrados.")

    with tab_a:
        st.caption(f"colección Firebase: `{api.ATTENDANCE_COLLECTION}`  ·  últimos 30 registros")
        if asistencias:
            st.dataframe(asistencias, use_container_width=True, hide_index=True)
        else:
            st.info("Todavía no hay asistencias registradas.")
