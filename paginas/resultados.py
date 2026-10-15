import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import evaluacion as ev
import hoja

st.markdown("## Resultados")
st.caption("Compara los niveles de cada informe guardado con lo que hizo el precio después. "
           "Datos de Yahoo Finance; el estado se decide con velas de 1H.")

if not hoja.configurada():
    st.error("Falta conectar la hoja de Google: añade SHEET_ID y GCP_JSON en los Secrets de la app.")
    st.stop()

ICONO = {"Entrada": "📥", "T1": "🎯", "T2": "🟢", "Stop": "🔴", "Activado": "🟡", "T1 alcanzado": "🟡", "Pendiente": "⚪", "Plazo": "🟠",
         "Caducado": "⚫", "Invalidado": "⛔", "Sin datos": "❔", "Datos inválidos": "❔"}
COLOR = {"verde": "#5fd17a", "rojo": "#ff6b6b", "ambar": "#f2c14e", "gris": "#8aa397", "zona": "rgba(95,209,122,0.15)",
         "fondo": "#07130d", "panel": "#0d1f16", "texto": "#eef5f0"}
MADRID = "Europe/Madrid"


# ---------------- Datos (cacheados) ----------------
@st.cache_data(ttl=1800, show_spinner=False)
def datos_ticker(ticker, desde_iso):
    return ev.descargar(ticker, pd.Timestamp(desde_iso))


@st.cache_data(ttl=1800, show_spinner=False)
def datos_5m(ticker, ini_iso, fin_iso):
    return ev.velas_5m(ticker, ini_iso, fin_iso)


def evaluar_todo(informes):
    por_ticker = {}
    for inf in informes:
        por_ticker.setdefault(inf["ticker"], []).append(inf)
    resultados, barra = {}, st.progress(0.0, text="Descargando precios…")
    for n, (t, lista) in enumerate(por_ticker.items(), start=1):
        barra.progress(n / len(por_ticker), text=f"Comparando {t} ({n}/{len(por_ticker)})…")
        desde = min(i["fecha"] for i in lista)
        try:
            datos = datos_ticker(t, desde.isoformat())
        except Exception:
            datos = None
        for inf in lista:
            if not datos or (datos["h1"].empty and datos["d1"].empty):
                resultados[inf["clave"]] = {"estado": "Sin datos", "entrada": None, "eventos": [], "t1": False,
                                            "r": None, "r_flotante": None, "resistencias": [], "niveles": {},
                                            "factor_split": 1.0}
                continue
            barras, fuente = ev.barras_para(datos, inf["fecha"])
            r = ev.evaluar(inf, barras, datos["splits"])
            r["fuente"] = fuente
            resultados[inf["clave"]] = r
    barra.empty()
    return resultados


# ---------------- Lectura del histórico ----------------
try:
    hist = hoja.leer_historico()
except Exception as e:
    st.error(f"No se pudo leer la pestaña «Histórico»: {e}")
    st.stop()

todos = ev.informes_desde_historico(hist)
if not todos:
    st.info("Todavía no hay informes guardados en el histórico. Añade acciones en «Seguimiento».")
    st.stop()

# ---------------- Filtros ----------------
with st.container(border=True):
    f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
    fechas = [i["fecha"].tz_convert(MADRID).date() for i in todos]
    rango = f1.date_input("Informes entre", value=(min(fechas), max(fechas)), min_value=min(fechas),
                          max_value=max(fechas), format="DD/MM/YYYY")
    agrupar = f2.toggle("Agrupar planes repetidos", value=True,
                        help="Si guardaste la misma acción varios días con los mismos niveles, cuenta como un solo "
                             "plan (el primero). Así no se repiten operaciones en el resumen.")
    g1, g2 = st.columns(2)
    bolsas = sorted({str(i["bolsa"]) for i in todos if i["bolsa"]})
    filtro_bolsa = g1.multiselect("Bolsa", bolsas, placeholder="Todas")
    tickers = sorted({i["ticker"] for i in todos})
    filtro_ticker = g2.multiselect("Ticker", tickers, placeholder="Todos")

informes = ev.quitar_repetidos(todos) if agrupar else list(todos)
if isinstance(rango, tuple) and len(rango) == 2:
    informes = [i for i in informes if rango[0] <= i["fecha"].tz_convert(MADRID).date() <= rango[1]]
if filtro_bolsa:
    informes = [i for i in informes if str(i["bolsa"]) in filtro_bolsa]
if filtro_ticker:
    informes = [i for i in informes if i["ticker"] in filtro_ticker]
if not informes:
    st.info("No hay informes con estos filtros.")
    st.stop()

b1, b2 = st.columns([1, 1])
if b1.button("🔄 Recalcular con precios nuevos", width="stretch"):
    datos_ticker.clear()
    datos_5m.clear()
    hoja.leer_historico.clear()
    st.rerun()

resultados = evaluar_todo(informes)

estados_presentes = [e for e in ev.ESTADOS if any(resultados[i["clave"]]["estado"] == e for i in informes)]
filtro_estado = st.pills("Estado", estados_presentes, selection_mode="multi", key="filtro_estado",
                         format_func=lambda e: f"{ICONO.get(e, '')} {e}")
visibles = [i for i in informes if not filtro_estado or resultados[i["clave"]]["estado"] in filtro_estado]

# ---------------- Cifras resumen ----------------
s = ev.resumen([resultados[i["clave"]] for i in visibles])
p = lambda x: "—" if x is None else f"{x:.0f} %"
rr = lambda x: "—" if x is None else f"{x:+.2f} R".replace(".", ",")
k = st.columns(4)
k[0].metric("Informes", s["informes"])
k[1].metric("Activados", p(s["activados_pct"]))
k[2].metric("Llegan a T1", p(s["t1_pct"]), help="Sobre los activados")
k[3].metric("Llegan a T2", p(s["t2_pct"]), help="Sobre los activados")
k = st.columns(4)
k[0].metric("Stop", p(s["stop_pct"]), help="Sobre los activados")
k[1].metric("Stops que pasaron por T1", p(s["stops_tras_t1_pct"]),
            help="De los que acabaron en stop, cuántos estuvieron antes en T1")
k[2].metric(f"R medio · {s['n_cerrados']} cerradas", rr(s["r_medio"]),
            help="Operaciones cerradas en T2, stop o plazo. No cuenta abiertas ni caducadas.")
k[3].metric(f"R flotante · {s['n_abiertos']} abiertas", rr(s["r_flotante"]),
            help="Media de las operaciones abiertas, al último precio")

# ---------------- Tabla ----------------
def fila_tabla(inf):
    r = resultados[inf["clave"]]
    n = r.get("niveles") or {}
    return {
        "Estado": f"{ICONO.get(r['estado'], '')} {r['estado']}",
        "Ticker": inf["ticker"],
        "Nombre": inf["nombre"],
        "Informe": inf["fecha"].tz_convert(MADRID).strftime("%d/%m/%y %H:%M"),
        "Sesiones": r.get("sesiones"),
        "R": r["r"] if r["r"] is not None else r.get("r_flotante"),
        "MFE (R)": r.get("mfe_r"),
        "MAE (R)": r.get("mae_r"),
        "Entrada": r.get("entrada"),
        "Zona": f"{n['zona_baja']:.2f} – {n['zona_alta']:.2f}" if n else "",
        "Stop": n.get("stop"),
        "T1": n.get("obj1"),
        "T2": n.get("obj2"),
        "Precio informe": inf["precio"],
        "_clave": inf["clave"],
        "_orden": inf["fecha"],
    }


tabla = pd.DataFrame([fila_tabla(i) for i in visibles]).sort_values("_orden", ascending=False).reset_index(drop=True)
n2 = lambda t, h=None: st.column_config.NumberColumn(t, format="%.2f", help=h)
ev_tabla = st.dataframe(
    tabla.drop(columns=["_clave", "_orden"]), hide_index=True, width="stretch", on_select="rerun",
    selection_mode="single-row", key="tabla_resultados",
    column_config={
        "Sesiones": st.column_config.NumberColumn("Sesiones", help="Sesiones desde el informe hasta resolverse "
                                                                  "(o hasta hoy si sigue abierto)"),
        "R": n2("R", "Cerradas: resultado final. Abiertas: flotante al último precio."),
        "MFE (R)": n2("MFE (R)", "Lo máximo que llegó a ir a favor desde la entrada"),
        "MAE (R)": n2("MAE (R)", "Lo máximo que llegó a ir en contra desde la entrada"),
        **{c: n2(c) for c in ["Entrada", "Stop", "T1", "T2", "Precio informe"]},
    })
st.caption("Pulsa una fila para ver el gráfico y la cronología. "
           f"Reglas: se activa al tocar la zona; caduca a las {ev.CADUCIDAD_SES} sesiones sin activarse; "
           f"abierta, sigue hasta T2, stop o {ev.PLAZO_SES} sesiones. Si una vela toca stop y objetivo, cuenta stop.")


def _filas_hoja():
    out = []
    for i in visibles:
        r = resultados[i["clave"]]
        fmt = lambda t: "" if t is None else pd.Timestamp(t).tz_convert(MADRID).strftime("%Y-%m-%d %H:%M")
        out.append({"Ticker": i["ticker"], "Informe": fmt(i["fecha"]), "Estado": r["estado"],
                    "Entrada": r.get("entrada"), "Fecha entrada": fmt(r.get("fecha_entrada")),
                    "Salida": r.get("salida"), "Fecha salida": fmt(r.get("fecha_salida")),
                    "T1 alcanzado": "Sí" if r.get("t1") else "No", "R": r.get("r"),
                    "R flotante": r.get("r_flotante"), "MFE R": r.get("mfe_r"), "MAE R": r.get("mae_r"),
                    "Sesiones": r.get("sesiones"),
                    "Calculado": pd.Timestamp.now(tz=MADRID).strftime("%Y-%m-%d %H:%M")})
    return out


if b2.button("💾 Guardar resultados en la hoja", width="stretch"):
    try:
        hoja.guardar_resultados(_filas_hoja())
        st.success("Resultados guardados en la pestaña «Resultados».")
    except Exception as e:
        st.error(f"No se pudo guardar: {e}")


# ---------------- Detalle ----------------
def _etiqueta_vela(ts, diario):
    t = pd.Timestamp(ts).tz_convert(MADRID)
    return t.strftime("%d/%m/%y") if diario else t.strftime("%d/%m %H:%M")


def grafico(velas, inf, r, diario):
    if velas.empty:
        st.info("Yahoo no devuelve velas para este periodo.")
        return
    x = [_etiqueta_vela(t, diario) for t in velas.index]
    fig = go.Figure(go.Candlestick(
        x=x, open=velas["Open"], high=velas["High"], low=velas["Low"], close=velas["Close"], name="Precio",
        increasing_line_color=COLOR["verde"], decreasing_line_color=COLOR["rojo"], showlegend=False))
    n = r["niveles"]
    fig.add_hrect(y0=n["zona_baja"], y1=n["zona_alta"], fillcolor=COLOR["zona"], line_width=0,
                  annotation_text="Zona", annotation_position="left", annotation_font_color=COLOR["verde"])
    for y, txt, col, dash in [(n["stop"], "Stop", COLOR["rojo"], "dash"), (n["obj1"], "T1", COLOR["verde"], "dot"),
                              (n["obj2"], "T2", COLOR["verde"], "dash")]:
        fig.add_hline(y=y, line_color=col, line_dash=dash, line_width=1.5, annotation_text=f"{txt} {y:.2f}",
                      annotation_position="right", annotation_font_color=col)
    for res in n.get("resistencias", []):
        if res not in (n["obj1"], n["obj2"]):
            fig.add_hline(y=res, line_color=COLOR["gris"], line_dash="dot", line_width=1, opacity=0.6)

    # Marcadores: salen del estado calculado (iguales en todas las temporalidades)
    idx = velas.index
    simbolos = {"Entrada": ("triangle-up", COLOR["ambar"]), "T1": ("circle", COLOR["verde"]),
                "T2": ("star", COLOR["verde"]), "Stop": ("x", COLOR["rojo"]), "Plazo": ("square", COLOR["ambar"]),
                "Caducado": ("square", COLOR["gris"]), "Invalidado": ("x", COLOR["gris"])}
    for e in r["eventos"]:
        ts = pd.Timestamp(e["fecha"]).tz_convert(idx.tz)
        if diario:
            pos = idx.normalize().searchsorted(ts.normalize(), side="right") - 1
        else:
            pos = idx.searchsorted(ts, side="right") - 1
        if pos < 0 or pos >= len(idx) or (not diario and ts - idx[pos] > pd.Timedelta(hours=1)):
            continue
        sym, col = simbolos.get(e["tipo"], ("circle", COLOR["texto"]))
        y = e["precio"] if e["precio"] is not None else velas["Close"].iloc[pos]
        fig.add_trace(go.Scatter(x=[x[pos]], y=[y], mode="markers+text", text=[e["tipo"]], textposition="top center",
                                 marker=dict(symbol=sym, size=13, color=col, line=dict(width=1, color=COLOR["fondo"])),
                                 textfont=dict(color=col), showlegend=False, hovertext=e["texto"]))
    ini = inf["fecha"].tz_convert(idx.tz)
    pos = idx.searchsorted(ini.normalize() if diario else ini)
    if 0 <= pos < len(idx):
        fig.add_vline(x=pos, line_color=COLOR["gris"], line_dash="dot", line_width=1)

    fig.update_layout(height=520, margin=dict(l=10, r=70, t=10, b=10), paper_bgcolor=COLOR["fondo"],
                      plot_bgcolor=COLOR["panel"], font_color=COLOR["texto"], xaxis_rangeslider_visible=False,
                      dragmode="pan", hovermode="x unified")
    fig.update_xaxes(type="category", nticks=8, showgrid=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.06)")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": True})


def _ver_dia(dia):
    st.session_state["tf_resultados"] = "5 min"
    st.session_state["dia_5m"] = dia


sel = ev_tabla.selection.rows if ev_tabla and ev_tabla.selection else []
if sel:
    clave = tabla.iloc[sel[0]]["_clave"]
    inf = next(i for i in visibles if i["clave"] == clave)
    r = resultados[clave]
    st.markdown(f"### {inf['ticker']} · {inf['nombre']}")
    st.caption(f"Informe del {inf['fecha'].tz_convert(MADRID):%d/%m/%Y %H:%M} · "
               f"{ICONO.get(r['estado'], '')} {r['estado']}")

    if r["estado"] in ("Sin datos", "Datos inválidos"):
        st.warning("No se puede dibujar: " + ("Yahoo no devuelve datos para este ticker." if r["estado"] == "Sin datos"
                                             else "los niveles guardados no son coherentes (revisa zona, stop y objetivos)."))
        st.stop()
    if r.get("factor_split", 1) != 1:
        st.info(f"Hubo un split después del informe: los niveles se han dividido entre {r['factor_split']:g} "
                "para compararlos con los precios actuales.")

    datos = datos_ticker(inf["ticker"], min(i["fecha"] for i in visibles if i["ticker"] == inf["ticker"]).isoformat())
    hay_5m = ev.disponible_5m(inf["fecha"]) or (r.get("fecha_salida") is None and r["estado"] in ev.ABIERTOS)
    opciones = ["Diario", "1H"] + (["5 min"] if hay_5m else [])
    if st.session_state.get("tf_resultados") not in opciones or st.session_state.get("_detalle") != clave:
        st.session_state["tf_resultados"] = "1H" if ev.disponible_1h(inf["fecha"]) else "Diario"
        st.session_state["dia_5m"] = None
        st.session_state["_detalle"] = clave
    tf = st.segmented_control("Temporalidad", opciones, key="tf_resultados") or "1H"
    if tf != "5 min":
        st.session_state["dia_5m"] = None
    if not hay_5m:
        st.caption("Sin velas de 5 min: Yahoo solo las guarda de los últimos 60 días.")

    inicio = inf["fecha"] - pd.Timedelta(days=3)
    fin = (pd.Timestamp(r["fecha_salida"]) if r.get("fecha_salida") is not None
           else pd.Timestamp.now(tz=MADRID)) + pd.Timedelta(days=3)
    if tf == "Diario":
        v = datos["d1"]
        v = v[(v.index >= inicio.tz_convert(v.index.tz).normalize() - pd.Timedelta(days=10)) &
              (v.index <= fin.tz_convert(v.index.tz))] if not v.empty else v
        grafico(v, inf, r, diario=True)
    elif tf == "1H":
        v = datos["h1"]
        v = v[(v.index >= inicio.tz_convert(v.index.tz)) & (v.index <= fin.tz_convert(v.index.tz))] if not v.empty else v
        grafico(v, inf, r, diario=False)
    else:
        dia = st.session_state.get("dia_5m")
        ini5 = pd.Timestamp(dia) if dia else max(inf["fecha"].tz_convert(MADRID).normalize(),
                                                 pd.Timestamp.now(tz=MADRID).normalize() - pd.Timedelta(days=ev.LIMITE_5M_DIAS))
        fin5 = pd.Timestamp(dia) if dia else min(fin, pd.Timestamp.now(tz=MADRID))
        if dia:
            st.caption(f"Día {pd.Timestamp(dia):%d/%m/%Y} en 5 min.")
        try:
            v = datos_5m(inf["ticker"], ini5.strftime("%Y-%m-%d"), fin5.strftime("%Y-%m-%d"))
        except Exception as e:
            v = pd.DataFrame()
            st.error(f"No se pudieron descargar las velas de 5 min: {e}")
        grafico(v, inf, r, diario=False)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**Cronología**")
        if not r["eventos"]:
            st.caption("Todavía no ha tocado ningún nivel.")
        for n_ev, e in enumerate(r["eventos"]):
            ts = pd.Timestamp(e["fecha"]).tz_convert(MADRID)
            precio = "" if e["precio"] is None else f" · {e['precio']:.2f}".replace(".", ",")
            a, b = st.columns([4, 1], vertical_alignment="center")
            a.markdown(f"{ICONO.get(e['tipo'], '•')} **{ts:%d/%m %H:%M}** {e['tipo']}{precio} — {e['texto']}")
            if ev.disponible_5m(ts):
                b.button("5 min", key=f"ev_{clave}_{n_ev}", on_click=_ver_dia, args=(ts.strftime("%Y-%m-%d"),),
                         help="Ver ese día en velas de 5 min")
        if r.get("entrada") is not None:
            st.caption(f"Entrada {r['entrada']:.2f} · riesgo {r['entrada'] - r['niveles']['stop']:.2f} por acción · "
                       f"MFE {r['mfe_r']:+.2f} R · MAE {r['mae_r']:+.2f} R".replace(".", ","))
    with c2:
        st.markdown("**Resistencias**")
        if not r["resistencias"]:
            st.caption("Este informe no guardó resistencias (los informes nuevos sí las guardan).")
        else:
            st.dataframe(pd.DataFrame([{
                "Nivel": x["nivel"], "Tests": x["tests"],
                "Rota": "No" if x["rota"] is None else f"Sí, {pd.Timestamp(x['rota']):%d/%m/%y}"}
                for x in r["resistencias"]]), hide_index=True, width="stretch",
                column_config={"Nivel": st.column_config.NumberColumn(format="%.2f"),
                               "Tests": st.column_config.NumberColumn(help="Sesiones con máximo a menos del "
                                                                          f"{ev.TEST_RES_PCT:g} % sin cerrar encima")})
