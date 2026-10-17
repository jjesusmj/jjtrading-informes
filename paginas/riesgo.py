from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

import hoja
from comun import selector_ticker
from niveles import ErrorInforme, ticker_yahoo
from riesgo_calculo import calcular
from riesgo_datos import ErrorRiesgo, descargar
from riesgo_html import generar_html
from traducciones import traducir_texto

st.markdown("## JJTrading \\_ Análisis acción")
st.caption("Nota de 0 a 100, valor justo, cuentas y evolución, con datos de Yahoo Finance. Todos los ratios se calculan en la app. No incluye entradas, stops ni recomendaciones.")


@st.cache_data(ttl=900, show_spinner=False)
def riesgo_cacheado(simbolo):
    return calcular(descargar(simbolo))


def guardar_y_leer(D):
    """Guarda la nota de hoy en la hoja de Google y devuelve su historial. Sin hoja configurada, no hace nada."""
    if not hoja.configurada() or D.get("nota") is None:
        return []
    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    hoja.guardar_riesgo({"Fecha": f"{ahora:%Y-%m-%d}", "Ticker": D["ticker"], "Nombre": D["nombre"], "Nota": D["nota"],
                         "Riesgo": D["riesgo"], "Valoración": D["notas"]["val"], "Salud": D["notas"]["sal"],
                         "Crecimiento": D["notas"]["cre"], "Precio": D["precio"], "Moneda": D["moneda"],
                         "Hora": f"{ahora:%Y-%m-%d %H:%M}"})
    return hoja.historial_riesgo(D["ticker"])


@st.cache_data(ttl=86400, show_spinner=False)
def _traducir_ok(texto):
    t, error = traducir_texto(texto)
    if not t:
        raise RuntimeError(error)          # los fallos no se guardan en caché: se reintenta la próxima vez
    return t


def traducir_cacheado(texto):
    try:
        return _traducir_ok(texto), None
    except Exception as e:
        return None, str(e)


def traducir_descripcion(D):
    """Primero la hoja de Google (traducción ya guardada); si no está, dos traductores; si sale bien, se guarda."""
    en = D.get("descripcion_en")
    if not en or D.get("descripcion_traducida"):
        return
    usar_hoja = hoja.configurada()
    if usar_hoja:
        try:
            guardada = hoja.leer_traduccion(D["ticker"], en)
            if guardada:
                D.update(descripcion=guardada, descripcion_traducida=True)
                return
        except Exception:
            usar_hoja = False
    es_, error = traducir_cacheado(en)
    if es_:
        D.update(descripcion=es_, descripcion_traducida=True)
        if usar_hoja:
            try:
                hoja.guardar_traduccion(D["ticker"], en, es_)
            except Exception:
                pass
    else:
        D.update(descripcion=en, descripcion_traducida=False, traduccion_error=error)


pendiente = st.session_state.pop("rsg_pendiente", None)          # viene de Seguimiento: (ticker, bolsa)
if pendiente:
    st.session_state["rsg_ticker"], st.session_state["rsg_bolsa"] = pendiente

ticker, bolsa = selector_ticker("rsg")

if st.button("Generar análisis", type="primary") or pendiente:
    if not ticker:
        st.warning("Escribe un ticker.")
    else:
        try:
            simbolo = ticker_yahoo(ticker, bolsa)
            with st.spinner("Descargando cuentas y cotizaciones, y calculando…"):
                D = dict(riesgo_cacheado(simbolo))
                traducir_descripcion(D)
            try:
                D["historial"] = guardar_y_leer(D)
            except Exception as e:
                D["historial"] = []
                st.caption(f"No se pudo guardar la nota en la hoja de Google: {e}")
            st.session_state["riesgo"] = D
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
