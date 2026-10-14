import io

import pandas as pd
import streamlit as st

import hoja
from comun import informe_cacheado, mostrar_informe, selector_ticker
from niveles import BOLSAS, ErrorInforme

st.markdown("## Seguimiento")
st.caption("Tu lista de acciones con el resumen del plan. Los datos se guardan en Google Sheets, con histórico diario.")

if not hoja.configurada():
    st.error("Falta conectar la hoja de Google: añade SHEET_ID y GCP_JSON en los Secrets de la app.")
    st.stop()


def actualizar(pares):
    """pares: lista de (ticker, bolsa). Genera los informes y guarda todas las fotos de una vez."""
    filas, errores = [], []
    barra = st.progress(0.0, text="Actualizando…")
    informe_cacheado.clear()                             # al actualizar, siempre datos nuevos
    for n, (t, b) in enumerate(pares, start=1):
        barra.progress(n / len(pares), text=f"Actualizando {t} ({n}/{len(pares)})…")
        try:
            filas.append(informe_cacheado(t, b)["fila"])
        except Exception as e:
            errores.append(f"{t}: {e}")
    barra.empty()
    if filas:
        hoja.guardar_fotos(filas)
        hoja.limpiar_cache()
    for e in errores:
        st.warning(e)
    return len(filas)


# ---------------- Añadir acción ----------------
with st.container(border=True):
    st.markdown("**Añadir acción**")
    ticker, bolsa = selector_ticker("seg")
    if st.button("Añadir a seguimiento", type="primary"):
        if not ticker:
            st.warning("Escribe un ticker o búscalo por nombre.")
        else:
            try:
                with st.spinner(f"Calculando {ticker}…"):
                    r = informe_cacheado(ticker, bolsa)
                    nuevo = hoja.añadir_seguimiento(r["ticker"], r["nombre"], bolsa, r["moneda"])
                    hoja.guardar_foto(r["fila"])
                    hoja.limpiar_cache()
                st.success(f"{r['ticker']} añadido." if nuevo else f"{r['ticker']} ya estaba en la lista; datos actualizados.")
            except ErrorInforme as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"No se pudo añadir: {e}")

# ---------------- Tabla ----------------
try:
    seg, datos = hoja.leer_seguimiento(), hoja.leer_datos()
except Exception as e:
    st.error(f"No se pudo leer la hoja de Google: {e}")
    st.stop()

if seg.empty:
    st.info("Todavía no hay acciones en seguimiento. Añade la primera arriba.")
    st.stop()

solo_fav = st.toggle("Solo favoritas", key="solo_fav")
base = seg[seg["Favorita"]] if solo_fav else seg
if base.empty:
    st.info("No tienes favoritas marcadas.")
    st.stop()

d = base[["Ticker", "Bolsa", "Favorita"]].merge(datos, on="Ticker", how="left", suffixes=("_seg", ""))
num = lambda c: pd.to_numeric(d.get(c), errors="coerce")
p, za = num("Último precio"), num("Zona alta")
fmt = lambda x: "" if pd.isna(x) else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
tabla = pd.DataFrame({
    "★": d["Favorita"].map({True: "★", False: ""}),
    "Ticker": d["Ticker"],
    "Nombre": d.get("Nombre"),
    "Último precio": p,
    "Var. día %": num("Variación día %"),
    "Rango 52 sem": [f"{fmt(a)} – {fmt(b)}" for a, b in zip(num("Mínimo 52 sem"), num("Máximo 52 sem"))],
    "Estado": d.get("Estado"),
    "Zona de entrada": [f"{fmt(a)} – {fmt(b)}" for a, b in zip(num("Zona baja"), za)],
    "Dist. zona %": (p / za - 1) * 100,
    "Stop": num("Stop"),
    "Obj. 1": num("Objetivo 1"),
    "Obj. 2": num("Objetivo 2"),
    "Riesgo %": num("Riesgo %"),
    "Ratio B/R": num("Ratio B/R"),
    "Tendencia diaria": d.get("Tendencia diaria"),
    "Próx. resultados": d.get("Próximos resultados"),
    "Moneda": d.get("Moneda"),
    "Actualizado": d.get("Hora actualización"),
}).sort_values("Dist. zona %", na_position="last").reset_index(drop=True)

n2 = lambda t: st.column_config.NumberColumn(t, format="%.2f")
ev = st.dataframe(
    tabla, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="tabla",
    column_config={"★": st.column_config.TextColumn("★", width="small"),
                   **{c: n2(c) for c in ["Último precio", "Var. día %", "Dist. zona %", "Stop", "Obj. 1", "Obj. 2",
                                         "Riesgo %", "Ratio B/R"]}})
st.caption("Pulsa una fila para ver su informe, actualizarla, marcarla como favorita o quitarla. "
           "Ordena pulsando en el nombre de cualquier columna.")

c1, c2, c3 = st.columns(3)
if c1.button(f"🔄 Actualizar las {len(base)} visibles", width="stretch"):
    ok = actualizar(list(zip(base["Ticker"], base["Bolsa"])))
    st.success(f"{ok} acciones actualizadas.")
    st.rerun()
c2.download_button("Descargar CSV", tabla.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
                   file_name="seguimiento.csv", mime="text/csv", width="stretch")
xls = io.BytesIO()
tabla.to_excel(xls, index=False, sheet_name="Seguimiento")
c3.download_button("Descargar Excel", xls.getvalue(), file_name="seguimiento.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

# ---------------- Acciones sobre la fila seleccionada ----------------
sel = ev.selection.rows if ev and ev.selection else []
if sel:
    t = tabla.iloc[sel[0]]["Ticker"]
    fila_seg = seg[seg["Ticker"] == t].iloc[0]
    b = fila_seg["Bolsa"] if fila_seg["Bolsa"] in BOLSAS else "EEUU"
    st.markdown(f"### {t} · {fila_seg['Nombre']}")
    a1, a2, a3, a4 = st.columns(4)
    if a1.button("🔄 Actualizar", width="stretch"):
        actualizar([(t, b)])
        st.rerun()
    fav = bool(fila_seg["Favorita"])
    if a2.button("Quitar de favoritas" if fav else "⭐ Marcar favorita", width="stretch"):
        hoja.marcar_favorita(t, not fav)
        hoja.limpiar_cache()
        st.rerun()
    confirmar = a4.checkbox("Confirmar", key=f"conf_{t}")
    if a3.button("🗑️ Quitar de la lista", width="stretch", disabled=not confirmar):
        hoja.quitar_seguimiento(t)
        hoja.limpiar_cache()
        st.rerun()
    st.caption("Quitar borra la acción de tu lista y de «Datos». Su histórico se conserva.")
    try:
        with st.spinner("Cargando informe…"):
            mostrar_informe(informe_cacheado(t, b))
    except Exception as e:
        st.error(f"No se pudo generar el informe: {e}")
