# Piezas compartidas por las dos páginas
import streamlit as st
import streamlit.components.v1 as components

from niveles import BOLSAS, FILTROS_BUSQUEDA, buscar, generar

ETIQUETAS_FILTRO = {"EEUU": "EEUU (NYSE y Nasdaq)", "MADRID": "Madrid", "PARIS": "París", "MILAN": "Milán",
                    "Todas las bolsas": "Todas las bolsas"}


@st.cache_data(ttl=900, show_spinner=False)          # 15 minutos: no repite descargas del mismo valor
def informe_cacheado(t, b):
    return generar(t, b)


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_cacheado(texto, filtro):
    return buscar(texto, filtro)


def _usar(k, r):
    st.session_state[f"{k}_ticker"] = r["simbolo"]
    st.session_state[f"{k}_bolsa"] = r["bolsa"]


def selector_ticker(k):
    """Buscador por nombre (filtrado por bolsa) + campos de ticker y bolsa. Devuelve (ticker, bolsa)."""
    with st.expander("🔎 No sé el ticker: buscar por nombre de empresa"):
        filtro = st.segmented_control("Bolsa", FILTROS_BUSQUEDA, key=f"{k}_filtro", default="Todas las bolsas",
                                      format_func=lambda x: ETIQUETAS_FILTRO.get(x, x)) or "Todas las bolsas"
        texto = st.text_input("Nombre de la empresa", key=f"{k}_texto", placeholder="Iberdrola, Nvidia, LVMH…")
        if texto.strip():
            try:
                res = buscar_cacheado(texto.strip(), filtro)
            except Exception as e:
                res = None
                st.error(f"La búsqueda no ha funcionado: {e}")
            if res == []:
                st.info("Sin resultados en esa bolsa. Prueba con otro nombre o con «Todas las bolsas».")
            elif res:
                i = st.selectbox("Resultados", range(len(res)), key=f"{k}_res",
                                 format_func=lambda i: f"{res[i]['nombre']} — {res[i]['simbolo']} · {res[i]['exchange']}")
                st.button("Usar este ticker", key=f"{k}_usar", on_click=_usar, args=(k, res[i]))
    c1, c2 = st.columns(2)
    ticker = c1.text_input("Ticker", key=f"{k}_ticker", placeholder="ACN, ITX, SAN, AAPL…")
    bolsa = c2.selectbox("Bolsa", BOLSAS, key=f"{k}_bolsa")
    return ticker.strip().upper(), bolsa


def mostrar_informe(r):
    st.download_button("Descargar informe (HTML)", r["html"], file_name=f"informe_{r['ticker']}_{r['fecha']}.html",
                       mime="text/html", key=f"dl_{r['ticker']}")
    if hasattr(st, "iframe"):
        st.iframe(r["html"], height=1900)
    else:
        components.html(r["html"], height=1900, scrolling=True)
