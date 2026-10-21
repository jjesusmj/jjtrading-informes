import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from comun import selector_ticker
from credito_calculo import INDICE_AVISO, INDICES, ErrorCredito, calcular, descargar_fred, descargar_precio
from niveles import ErrorInforme, ticker_yahoo

st.markdown("## Crédito")
st.caption("Precio de la acción frente a los spreads de crédito de EE. UU. publicados en FRED (ICE BofA). "
           "Es contexto de mercado: no cambia ninguna nota.")

COLOR = {"precio": "#1e3a8a", "BBB": "#0f766e", "HY": "#7c3aed", "zona20": "rgba(124,58,237,0.10)",
         "zona60": "rgba(124,58,237,0.04)", "fondo": "#f3f0ea", "panel": "#fffdf9", "texto": "#0f172a",
         "gris": "#64748b"}
ESTADO = {"negativa": ("🔴", "Divergencia negativa", "La acción sube y el crédito empeora, los dos más de lo habitual."),
          "positiva": ("🟢", "Divergencia positiva", "La acción cae y el crédito mejora, los dos más de lo habitual."),
          "ninguna": ("⚪", "Sin divergencia", "No se cumplen las dos condiciones a la vez."),
          None: ("⚪", "Sin dato", "No hay sesiones suficientes para calcularlo.")}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fred_cacheado(codigo, desde):
    return descargar_fred(codigo, desde)


@st.cache_data(ttl=900, show_spinner=False)
def precio_cacheado(simbolo):
    return descargar_precio(simbolo)


def _f(x, dec=0, signo=False):
    if x is None:
        return "Sin dato"
    t = f"{x:+,.{dec}f}" if signo else f"{x:,.{dec}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def obtener(simbolo):
    precio = precio_cacheado(simbolo)
    desde = (precio.index[0] - dt.timedelta(days=7)).strftime("%Y-%m-%d")
    spreads = {}
    for k, info in INDICES.items():
        try:
            spreads[k] = fred_cacheado(info["codigo"], desde)
        except Exception:
            spreads[k] = "no se ha podido descargar la serie de FRED"
    return calcular(precio, spreads)


def grafico(R, moneda_txt):
    p = R["precio"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p.index, y=p.values, name=f"Precio {moneda_txt}".strip(), yaxis="y",
                             line=dict(color=COLOR["precio"], width=2),
                             hovertemplate="%{y:,.2f}<extra>Precio</extra>"))
    hay_spread = False
    for k, d in R["series"].items():
        if d.get("alineada") is None:
            continue
        hay_spread = True
        fig.add_trace(go.Scatter(x=d["alineada"].index, y=d["alineada"].values, name=f"Spread {d['nombre']} (pb)",
                                 yaxis="y2", connectgaps=False, line=dict(color=COLOR[k], width=1.6),
                                 hovertemplate="%{y:,.0f} pb<extra>" + d["nombre"] + "</extra>"))
    if len(p) > 60:
        fig.add_vrect(x0=p.index[-61], x1=p.index[-1], fillcolor=COLOR["zona60"], line_width=0,
                      annotation_text="60 s.", annotation_position="top left", annotation_font_color=COLOR["gris"])
    if len(p) > 20:
        fig.add_vrect(x0=p.index[-21], x1=p.index[-1], fillcolor=COLOR["zona20"], line_width=0,
                      annotation_text="20 s.", annotation_position="top left", annotation_font_color=COLOR["gris"])
    fig.update_layout(height=460, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor=COLOR["fondo"],
                      plot_bgcolor=COLOR["panel"], font_color=COLOR["texto"], hovermode="x unified", dragmode="pan",
                      legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0),
                      yaxis=dict(title="Precio", gridcolor="rgba(15,23,42,0.07)"),
                      yaxis2=dict(title="Spread (pb), invertido", overlaying="y", side="right",
                                  autorange="reversed", showgrid=False, visible=hay_spread))
    fig.update_xaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": False})


def bloque_aviso(a):
    icono, titulo, regla = ESTADO[a["estado"]]
    with st.container(border=True):
        st.markdown(f"**{a['nombre']} ({a['ventana']} sesiones)**")
        st.markdown(f"### {icono} {titulo}")
        if a["estado"] is not None:
            st.caption(f"Acción {_f(a['precio_pct'], 1, True)} % · Spread {_f(a['spread_pb'], 0, True)} pb · "
                       f"Habitual en 12 meses: ±{_f(a['umbral_pct'], 1)} % y ±{_f(a['umbral_pb'], 0)} pb · "
                       f"Hasta {a['fecha']}")
        st.caption(regla)


ticker, bolsa = selector_ticker("cre")
if st.button("Ver crédito", type="primary"):
    if not ticker:
        st.warning("Escribe un ticker.")
    else:
        try:
            simbolo = ticker_yahoo(ticker, bolsa)
            with st.spinner("Descargando cotizaciones y spreads…"):
                st.session_state["credito"] = {"simbolo": simbolo, "bolsa": bolsa, "R": obtener(simbolo)}
        except (ErrorInforme, ErrorCredito) as e:
            st.session_state.pop("credito", None)
            st.error(f"Sin dato: {e}.")
        except Exception as e:
            st.session_state.pop("credito", None)
            st.error(f"Sin dato: no se han podido descargar los datos ({e}). Si Yahoo está limitando peticiones, prueba en unos minutos.")

C = st.session_state.get("credito")
if C:
    R = C["R"]
    st.markdown(f"#### {C['simbolo']} · cierre {R['corte']}")
    if C["bolsa"] != "EEUU":
        st.caption("Los dos índices miden el crédito de empresas de EE. UU.")
    grafico(R, "")
    st.caption("Eje del spread invertido: hacia abajo indica peor crédito.")

    cols = st.columns(len(INDICES))
    for col, (k, d) in zip(cols, R["series"].items()):
        with col.container(border=True):
            st.markdown(f"**{d['nombre']}** · `{d['codigo']}`")
            if d.get("error") or d.get("actual") is None:
                st.markdown(f"Sin dato: {d.get('error') or 'sin datos'}.")
                continue
            a, b, c = st.columns(3)
            a.metric("Spread actual", f"{_f(d['actual'])} pb")
            b.metric("Variación 12 meses", f"{_f(d['var12'], 0, True)} pb")
            c.metric("Correlación 60 s.", _f(d["corr"], 2))
            st.caption(f"Spread a {d['fecha_actual']} · variación desde {d['fecha_inicio']}")

    st.markdown(f"#### Aviso de divergencia · {INDICES[INDICE_AVISO]['nombre']}")
    hy = R["series"][INDICE_AVISO]
    if hy.get("avisos"):
        c1, c2 = st.columns(2)
        for col, a in zip((c1, c2), hy["avisos"]):
            with col:
                bloque_aviso(a)
    else:
        st.markdown(f"Sin dato: {hy.get('error') or 'sin datos'}.")

    with st.expander("¿Cómo se calcula?"):
        st.markdown(
            "- **Spread**: diferencial de los bonos de empresas frente a la deuda pública de EE. UU., en puntos básicos (pb). FRED lo publica en % y aquí se multiplica por 100.\n"
            "- **Variación 12 meses**: último spread menos el primero de los últimos 12 meses.\n"
            "- **Correlación 60 s.**: correlación entre la variación diaria del precio (%) y la del spread (pb) en las últimas 60 sesiones con ambos datos. Va de −1 a +1.\n"
            "- **Aviso de divergencia**: se mide cuánto se han movido la acción (%) y el spread (pb) en las últimas 20 y 60 sesiones. "
            "Un movimiento es *más de lo habitual* si supera una desviación típica de esos movimientos en los últimos 12 meses. "
            "Divergencia negativa: la acción sube y el spread sube, los dos más de lo habitual. "
            "Divergencia positiva: la acción baja y el spread baja, los dos más de lo habitual.\n"
            "- Las sesiones son días de bolsa: 20 sesiones son unas 4 semanas y 60, unos 3 meses.")

    fuentes = [f"Precio: Yahoo Finance, último cierre {R['corte']}."]
    for d in R["series"].values():
        ult = d.get("ultimo_publicado")
        fuentes.append(f"{d['nombre']}: FRED, ICE BofA Option-Adjusted Spread ({d['codigo']})"
                       + (f", último dato publicado {ult}." if ult else ", sin datos."))
    st.caption(" ".join(fuentes))
