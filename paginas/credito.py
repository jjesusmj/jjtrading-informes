import datetime as dt

import plotly.graph_objects as go
import streamlit as st

from comun import selector_ticker
from credito_calculo import INDICE_AVISO, INDICES, ErrorCredito, calcular, descargar_fred, descargar_precio
from niveles import ErrorInforme, ticker_yahoo

st.markdown("## Crédito")
st.caption("Precio de la acción frente a los spreads de crédito de EE. UU. publicados en FRED (ICE BofA). "
           "Es contexto de mercado: no cambia ninguna nota.")

COLOR = {"precio": "#0c447c", "precio_relleno": "rgba(24,95,165,0.08)", "BBB": "#0f766e", "HY": "#7c3aed", "zona20": "rgba(124,58,237,0.10)",
         "zona60": "rgba(124,58,237,0.04)", "fondo": "#f3f0ea", "panel": "#fffdf9", "texto": "#0f172a",
         "gris": "#64748b"}
ESTADO = {"empeora_cae": ("🔴", "Crédito empeora", "La acción también cae."),
          "empeora_no_cae": ("🟠", "Crédito empeora", "La acción no cae: todavía no lo refleja."),
          "mejora": ("🟢", "Crédito mejora", "El spread baja más de lo habitual."),
          "estable": ("⚪", "Crédito estable", "El spread se mueve dentro de lo habitual."),
          None: ("⚪", "Sin dato", "No hay sesiones suficientes para calcularlo.")}


def _clave_fred():
    try:
        return st.secrets.get("FRED_API_KEY", "") or None
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fred_cacheado(codigo, desde, clave):
    return descargar_fred(codigo, desde, clave)


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
            spreads[k] = fred_cacheado(info["codigo"], desde, _clave_fred())
        except Exception as e:
            spreads[k] = f"no se ha podido descargar la serie de FRED ({e})"
    return calcular(precio, spreads)


def grafico(R):
    p = R["precio"]
    fig = go.Figure()
    lo, hi = float(p.min()), float(p.max())
    pad = (hi - lo) * 0.08 or hi * 0.05
    for k, d in R["series"].items():
        if d.get("alineada") is None:
            continue
        s = d["alineada"]
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=f"Spread {d['nombre']} (pb, eje dcho.)", yaxis="y2",
                                 connectgaps=False, opacity=0.85, line=dict(color=COLOR[k], width=1.4, dash="dash"),
                                 hovertemplate="%{y:,.0f} pb<extra>" + d["nombre"] + "</extra>"))
        ult = s.dropna()
        if not ult.empty:
            fig.add_annotation(x=ult.index[-1], y=float(ult.iloc[-1]), yref="y2", text=f"{ult.iloc[-1]:,.0f}",
                               showarrow=False, xanchor="left", xshift=6, bgcolor=COLOR[k],
                               font=dict(color="#ffffff", size=11), borderpad=3)
    fig.add_trace(go.Scatter(x=p.index, y=p.values, name="Precio (eje izq.)", yaxis="y", fill="tozeroy",
                             fillcolor=COLOR["precio_relleno"], line=dict(color=COLOR["precio"], width=3),
                             hovertemplate="%{y:,.2f}<extra>Precio</extra>"))
    fig.add_trace(go.Scatter(x=[p.index[-1]], y=[float(p.iloc[-1])], mode="markers", yaxis="y", showlegend=False,
                             marker=dict(color=COLOR["precio"], size=8), hoverinfo="skip"))
    fig.add_annotation(x=p.index[-1], y=float(p.iloc[-1]), yref="y", text=_f(float(p.iloc[-1]), 2), showarrow=False,
                       xanchor="left", xshift=6, bgcolor=COLOR["precio"], font=dict(color="#ffffff", size=11), borderpad=3)
    if len(p) > 60:
        fig.add_vrect(x0=p.index[-61], x1=p.index[-1], fillcolor=COLOR["zona60"], line_width=0,
                      annotation_text="60 s.", annotation_position="top left", annotation_font_color=COLOR["gris"])
    if len(p) > 20:
        fig.add_vrect(x0=p.index[-21], x1=p.index[-1], fillcolor=COLOR["zona20"], line_width=0,
                      annotation_text="20 s.", annotation_position="top left", annotation_font_color=COLOR["gris"])
    hay_spread = any(d.get("alineada") is not None for d in R["series"].values())
    fig.update_layout(height=460, margin=dict(l=10, r=60, t=30, b=10), paper_bgcolor=COLOR["fondo"],
                      plot_bgcolor=COLOR["panel"], font_color=COLOR["texto"], hovermode="x unified", dragmode="pan",
                      legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0),
                      yaxis=dict(title=dict(text="Precio", font=dict(color=COLOR["precio"])), range=[lo - pad, hi + pad],
                                 tickfont=dict(color=COLOR["precio"]), gridcolor="rgba(15,23,42,0.07)"),
                      yaxis2=dict(title="Spread (pb)", overlaying="y", side="right", showgrid=False, visible=hay_spread))
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
    grafico(R)
    st.caption("Eje del spread normal: hacia arriba indica peor crédito.")

    cols = st.columns(len(INDICES))
    for col, (k, d) in zip(cols, R["series"].items()):
        with col.container(border=True):
            st.markdown(f"**{d['nombre']}** · `{d['codigo']}`")
            st.caption(d["texto"])
            if d.get("error") or d.get("actual") is None:
                st.markdown(f"Sin dato: {d.get('error') or 'sin datos'}.")
                continue
            a, b, c = st.columns(3)
            a.metric("Spread actual", f"{_f(d['actual'])} pb")
            b.metric("Variación 12 meses", f"{_f(d['var12'], 0, True)} pb")
            c.metric("Correlación 60 s.", _f(d["corr"], 2))
            st.caption(f"Spread a {d['fecha_actual']} · variación desde {d['fecha_inicio']}")

    st.markdown(f"#### Aviso de crédito · {INDICES[INDICE_AVISO]['nombre']}")
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
            "- **Aviso de crédito**: se mide cuánto se ha movido el spread High Yield (pb) y la acción (%) en las últimas 20 y 60 sesiones. "
            "El crédito *empeora* si el spread sube más de lo habitual, es decir, más de una desviación típica de esos movimientos en los últimos 12 meses; *mejora* si baja más de lo habitual. "
            "Cuando empeora, se indica si la acción ha caído en ese periodo (🔴) o no (🟠).\n"
            "- Las sesiones son días de bolsa: 20 sesiones son unas 4 semanas y 60, unos 3 meses.")

    fuentes = [f"Precio: Yahoo Finance, último cierre {R['corte']}."]
    for d in R["series"].values():
        ult = d.get("ultimo_publicado")
        fuentes.append(f"{d['nombre']}: FRED, ICE BofA Option-Adjusted Spread ({d['codigo']})"
                       + (f", último dato publicado {ult}." if ult else ", sin datos."))
    st.caption(" ".join(fuentes))
