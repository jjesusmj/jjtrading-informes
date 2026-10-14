import streamlit as st

import hoja
from comun import informe_cacheado, mostrar_informe, selector_ticker
from niveles import ErrorInforme

st.markdown("## JJTrading_ · Plan de operación")
st.caption("Solo largos. Niveles de entrada, stop y objetivos calculados con datos de Yahoo Finance.")

ticker, bolsa = selector_ticker("inf")

if st.button("Generar informe", type="primary"):
    if not ticker:
        st.warning("Escribe un ticker.")
    else:
        try:
            with st.spinner("Descargando datos y calculando niveles…"):
                st.session_state["ultimo"] = informe_cacheado(ticker, bolsa)
                st.session_state["ultimo_bolsa"] = bolsa
        except ErrorInforme as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"No se pudo generar el informe: {e}. Si Yahoo está limitando peticiones, prueba en unos minutos.")

r = st.session_state.get("ultimo")
if r:
    if hoja.configurada() and st.button(f"⭐ Añadir {r['ticker']} a seguimiento"):
        try:
            nuevo = hoja.añadir_seguimiento(r["ticker"], r["nombre"], st.session_state["ultimo_bolsa"], r["moneda"])
            hoja.guardar_foto(r["fila"])
            hoja.limpiar_cache()
            st.success(f"{r['ticker']} añadido a seguimiento." if nuevo else f"{r['ticker']} ya estaba en seguimiento; datos actualizados.")
        except Exception as e:
            st.error(f"No se pudo guardar en la hoja: {e}")
    mostrar_informe(r)
