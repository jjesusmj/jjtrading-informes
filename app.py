import streamlit as st

from niveles import BOLSAS, ErrorInforme, generar

st.set_page_config(page_title="JJTrading_ · Plan de operación", page_icon="📈", layout="wide")

# Contraseña opcional: si en Streamlit Cloud defines APP_PASSWORD en "Secrets", la app la pide
try:
    clave = st.secrets.get("APP_PASSWORD", "")
except Exception:          # sin fichero de secretos: app sin contraseña
    clave = ""
if clave and not st.session_state.get("ok"):
    st.markdown("### JJTrading_")
    if st.text_input("Contraseña", type="password") == clave:
        st.session_state["ok"] = True
        st.rerun()
    st.stop()

st.markdown("## JJTrading_ · Plan de operación")
st.caption("Solo largos. Niveles de entrada, stop y objetivos calculados con datos de Yahoo Finance.")

with st.form("pedir"):
    c1, c2, c3 = st.columns([2, 2, 1])
    ticker = c1.text_input("Ticker", placeholder="ACN, ITX, SAN, AAPL…")
    bolsa = c2.selectbox("Bolsa", BOLSAS, index=0)
    c3.write(""); c3.write("")
    enviar = c3.form_submit_button("Generar informe", use_container_width=True, type="primary")


@st.cache_data(ttl=900, show_spinner=False)          # 15 minutos: no repite descargas del mismo valor
def informe_cacheado(t, b):
    return generar(t, b)


if enviar:
    if not ticker.strip():
        st.warning("Escribe un ticker.")
    else:
        try:
            with st.spinner("Descargando datos y calculando niveles…"):
                r = informe_cacheado(ticker.strip().upper(), bolsa)
            st.session_state["ultimo"] = r
        except ErrorInforme as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"No se pudo generar el informe: {e}. Si Yahoo está limitando peticiones, prueba en unos minutos.")

r = st.session_state.get("ultimo")
if r:
    st.download_button("Descargar informe (HTML)", r["html"], file_name=f"informe_{r['ticker']}_{r['fecha']}.html",
                       mime="text/html")
    if hasattr(st, "iframe"):
        st.iframe(r["html"], height=1900)
    else:
        import streamlit.components.v1 as components
        components.html(r["html"], height=1900, scrolling=True)
