import os
import uuid
from datetime import date
from pathlib import Path

import streamlit as st

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config.db import get_connection


# ================================================================
#  HELPERS DB
# ================================================================

def _get_tiendas():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id_tienda, nombre FROM public.tienda ORDER BY nombre')
            return cur.fetchall()

def _get_configs():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM public.alerta_puntualidad_config ORDER BY tipo_reporte, hora_envio')
            return cur.fetchall()

def _create_config(payload: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.alerta_puntualidad_config
                    (id_config, id_tienda, correo_destino, minutos_tolerancia,
                     activo, tipo_reporte, nombre_reporte, hora_envio, ventana_minutos)
                VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s)
                """,
                (
                    payload["id_config"],
                    payload["id_tienda"],
                    payload["correo_destino"],
                    payload["minutos_tolerancia"],
                    payload["tipo_reporte"],
                    payload["nombre_reporte"],
                    payload["hora_envio"],
                    payload["ventana_minutos"],
                ),
            )
        conn.commit()

def _update_config(id_config: str, payload: dict):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.alerta_puntualidad_config SET
                    id_tienda          = %s,
                    correo_destino     = %s,
                    minutos_tolerancia = %s,
                    tipo_reporte       = %s,
                    nombre_reporte     = %s,
                    hora_envio         = %s,
                    ventana_minutos    = %s
                WHERE id_config = %s
                """,
                (
                    payload["id_tienda"],
                    payload["correo_destino"],
                    payload["minutos_tolerancia"],
                    payload["tipo_reporte"],
                    payload["nombre_reporte"],
                    payload["hora_envio"],
                    payload["ventana_minutos"],
                    id_config,
                ),
            )
        conn.commit()

def _delete_config(id_config: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM public.alerta_puntualidad_config WHERE id_config = %s',
                (id_config,),
            )
        conn.commit()


# ================================================================
#  VISTA PRINCIPAL
# ================================================================

def render_correo(api=None):
    st.markdown(
        """
        <div style="margin-bottom:24px;">
            <h2 class="page-title">Alertas de Puntualidad</h2>
            <p class="page-subtitle">Gestiona los reportes automáticos de asistencia por correo</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        tiendas = _get_tiendas()
        configs = _get_configs()
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        return

    tienda_map = {t["nombre"]: str(t["id_tienda"]) for t in tiendas}
    tienda_options = ["(General - Sin tienda)"] + list(tienda_map.keys())

    # Detecta si se acaba de crear una config para mostrar mensaje en tab lista
    ir_a_lista = st.session_state.pop("config_creada", False)

    tab_list, tab_create = st.tabs([" Configuraciones", " Nueva configuración"])

    # ================================================================
    #  TAB 1: LISTAR / EDITAR / ELIMINAR
    # ================================================================
    with tab_list:
        if ir_a_lista:
            st.success("✅ Configuración creada correctamente.")

        if not configs:
            st.info("No hay configuraciones registradas aún.")
        else:
            for cfg in configs:
                id_config   = str(cfg["id_config"])
                id_tienda   = cfg.get("id_tienda")
                nombre_sede = next(
                    (t["nombre"] for t in tiendas if str(t["id_tienda"]) == str(id_tienda)),
                    None,
                ) if id_tienda else None

                correo     = cfg.get("correo_destino", "-")
                nombre_rep = cfg.get("nombre_reporte", "-")
                hora       = str(cfg.get("hora_envio", "-"))[:5]
                minutos    = int(cfg.get("minutos_tolerancia", 10))
                ventana    = int(cfg.get("ventana_minutos", 5))

                label = f"{'🏪 ' + nombre_sede if nombre_sede else '🌐 General'} — {nombre_rep} — {hora} — {correo}"

                with st.expander(label):
                    with st.form(f"edit_form_{id_config}"):
                        col1, col2 = st.columns(2)

                        current_tienda = nombre_sede if nombre_sede else "(General - Sin tienda)"
                        selected_tienda = col1.selectbox(
                            "Tienda",
                            options=tienda_options,
                            index=tienda_options.index(current_tienda) if current_tienda in tienda_options else 0,
                            key=f"tienda_{id_config}",
                        )
                        new_correo = col2.text_input(
                            "Correo destino",
                            value=correo,
                            key=f"correo_{id_config}",
                        )

                        col3, col4, col5, col6 = st.columns(4)
                        nombre_options = ["Reporte mañana", "Reporte tarde"]
                        new_nombre = col3.selectbox(
                            "Nombre reporte",
                            options=nombre_options,
                            index=nombre_options.index(nombre_rep) if nombre_rep in nombre_options else 0,
                            key=f"nombre_{id_config}",
                        )
                        new_hora = col4.text_input(
                            "Hora envío (HH:MM)",
                            value=hora,
                            key=f"hora_{id_config}",
                        )
                        new_minutos = col5.number_input(
                            "Tolerancia (min)",
                            min_value=0, max_value=120,
                            value=minutos,
                            key=f"minutos_{id_config}",
                        )
                        new_ventana = col6.number_input(
                            "Ventana (min)",
                            min_value=1, max_value=60,
                            value=ventana,
                            key=f"ventana_{id_config}",
                        )

                        col_save, col_del = st.columns([3, 1])
                        save   = col_save.form_submit_button(" Guardar cambios", use_container_width=True)
                        delete = col_del.form_submit_button(" Eliminar", use_container_width=True)

                    if save:
                        id_tienda_new = tienda_map.get(selected_tienda) if selected_tienda != "(General - Sin tienda)" else None
                        hora_fmt = new_hora.strip() + ":00" if len(new_hora.strip()) == 5 else new_hora.strip()
                        try:
                            _update_config(id_config, {
                                "id_tienda":          id_tienda_new,
                                "correo_destino":     new_correo.strip(),
                                "minutos_tolerancia": int(new_minutos),
                                "tipo_reporte":       "TIENDA" if id_tienda_new else "GENERAL",
                                "nombre_reporte":     new_nombre,
                                "hora_envio":         hora_fmt,
                                "ventana_minutos":    int(new_ventana),
                            })
                            st.success("✅ Configuración actualizada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")

                    if delete:
                        try:
                            _delete_config(id_config)
                            st.success("✅ Configuración eliminada.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")

    # ================================================================
    #  TAB 2: CREAR NUEVA
    # ================================================================
    with tab_create:
        with st.form("create_config_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            selected_tienda = col1.selectbox("Tienda", options=tienda_options, key="new_tienda")
            new_correo      = col2.text_input("Correo destino", placeholder="ejemplo@correo.com")

            col3, col4, col5, col6 = st.columns(4)
            new_nombre  = col3.selectbox("Nombre reporte", options=["Reporte mañana", "Reporte tarde"])
            new_hora    = col4.text_input("Hora envío (HH:MM)", placeholder="08:30")
            new_minutos = col5.number_input("Tolerancia (min)", min_value=0, max_value=120, value=10)
            new_ventana = col6.number_input("Ventana (min)", min_value=1, max_value=60, value=5)

            submitted = st.form_submit_button(" Crear configuración", use_container_width=True)

        if submitted:
            if not new_correo.strip():
                st.error("El correo destino es obligatorio.")
            elif not new_hora.strip():
                st.error("La hora de envío es obligatoria.")
            else:
                id_tienda_new = tienda_map.get(selected_tienda) if selected_tienda != "(General - Sin tienda)" else None
                hora_fmt = new_hora.strip() + ":00" if len(new_hora.strip()) == 5 else new_hora.strip()
                try:
                    _create_config({
                        "id_config":          str(uuid.uuid4()),
                        "id_tienda":          id_tienda_new,
                        "correo_destino":     new_correo.strip(),
                        "minutos_tolerancia": int(new_minutos),
                        "tipo_reporte":       "TIENDA" if id_tienda_new else "GENERAL",
                        "nombre_reporte":     new_nombre,
                        "hora_envio":         hora_fmt,
                        "ventana_minutos":    int(new_ventana),
                    })
                    st.session_state["config_creada"] = True  # ← vuelve al tab lista con mensaje
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al crear: {e}")