import streamlit as st

from comun import selector_ticker
from niveles import ErrorInforme, ticker_yahoo
from riesgo_calculo import calcular
from riesgo_datos import ErrorRiesgo, descargar
from riesgo_html import generar_html

st.markdown("## JJTrading_ · Riesgo")
st.caption("Nota de riesgo de 0 a 100 con datos de Yahoo Finance. Todos los ratios se calculan en la app. No incluye entradas, stops ni recomendaciones.")


@st.cache_data(ttl=900, show_spinner=False)
def riesgo_cacheado(simbolo):
    return calcular(descargar(simbolo))


ticker, bolsa = selector_ticker("rsg")

if st.button("Generar informe de riesgo", type="primary"):
    if not ticker:
        st.warning("Escribe un ticker.")
    else:
        try:
            simbolo = ticker_yahoo(ticker, bolsa)
            with st.spinner("Descargando cuentas y cotizaciones, y calculando…"):
                st.session_state["riesgo"] = riesgo_cacheado(simbolo)
        except (ErrorInforme, ErrorRiesgo) as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"No se pudo generar el informe: {e}. Si Yahoo está limitando peticiones, prueba en unos minutos.")

D = st.session_state.get("riesgo")
if D:
    contenido = generar_html(D)
    st.download_button("Descargar informe (HTML)", contenido, file_name=f"riesgo_{D['ticker']}_{D['corte']}.html", mime="text/html")
    if hasattr(st, "iframe"):
        st.iframe(contenido, height="content")
    else:
        import streamlit.components.v1 as components
        components.html(contenido, height=9000, scrolling=True)
