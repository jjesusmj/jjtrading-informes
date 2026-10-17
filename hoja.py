# =====================================================================
#  JJTrading_ — lectura y escritura en Google Sheets
#  Pestañas: Seguimiento (tu lista), Datos (última foto por acción),
#  Histórico (una foto por acción y día; nunca se borra).
#  Credenciales en Streamlit Secrets: SHEET_ID y GCP_JSON.
# =====================================================================
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st

SEG = "Seguimiento"
DATOS = "Datos"
HIST = "Histórico"
COLS_SEG = ["Ticker", "Nombre", "Bolsa", "Moneda", "Favorita", "Fecha alta"]


def configurada():
    try:
        return bool(st.secrets.get("SHEET_ID")) and bool(st.secrets.get("GCP_JSON"))
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _libro():
    cred = json.loads(st.secrets["GCP_JSON"])
    return gspread.service_account_from_dict(cred).open_by_key(st.secrets["SHEET_ID"])


def _pestaña(nombre):
    return _libro().worksheet(nombre)


def _cabecera(ws):
    return ws.row_values(1)


def _fila_a_lista(cab, fila):
    return [("" if fila.get(c) is None else fila.get(c)) for c in cab]


# ---------------- Lectura ----------------
@st.cache_data(ttl=60, show_spinner=False)
def leer_seguimiento():
    df = pd.DataFrame(_pestaña(SEG).get_all_records(numericise_ignore=["all"]))
    if df.empty:
        return pd.DataFrame(columns=COLS_SEG)
    df["Favorita"] = df["Favorita"].astype(str).str.lower().isin(["sí", "si", "true", "1", "x"])
    return df


@st.cache_data(ttl=60, show_spinner=False)
def leer_datos():
    ws = _pestaña(DATOS)
    # Valores sin formato: la hoja está en formato español (coma decimal) y leer el texto
    # convertiría "133,135" en 133135. Así llegan los números tal cual se guardaron.
    filas = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    return pd.DataFrame(filas) if filas else pd.DataFrame(columns=_cabecera(ws))


@st.cache_data(ttl=300, show_spinner=False)
def leer_historico():
    ws = _pestaña(HIST)
    filas = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    return pd.DataFrame(filas) if filas else pd.DataFrame(columns=_cabecera(ws))


def limpiar_cache():
    leer_seguimiento.clear()
    leer_datos.clear()
    leer_historico.clear()


# ---------------- Seguimiento ----------------
def añadir_seguimiento(ticker, nombre, bolsa, moneda):
    ws = _pestaña(SEG)
    if ticker in ws.col_values(1)[1:]:
        return False
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    ws.append_row([ticker, nombre, bolsa, moneda, "No", hoy], value_input_option="RAW")
    return True


def añadir_varias(filas_seg):
    """filas_seg: lista de (ticker, nombre, bolsa, moneda). Añade las que no estén ya. Devuelve los tickers añadidos."""
    ws = _pestaña(SEG)
    existentes = set(ws.col_values(1)[1:])
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    nuevas, añadidos = [], []
    for t, n, b, m in filas_seg:
        if t not in existentes:
            nuevas.append([t, n, b, m, "No", hoy]); añadidos.append(t); existentes.add(t)
    if nuevas:
        ws.append_rows(nuevas, value_input_option="RAW")
    return añadidos


def quitar_varias(tickers):
    """Quita varias acciones de tu lista y de Datos (de abajo arriba, para no descolocar filas). El Histórico se conserva."""
    tickers = set(tickers)
    for nombre, col in ((SEG, 1), (DATOS, 3)):
        ws = _pestaña(nombre)
        filas = [i for i, v in enumerate(ws.col_values(col), start=1) if i > 1 and v in tickers]
        for i in sorted(filas, reverse=True):
            ws.delete_rows(i)


def _fila_de(ws, ticker, col):
    vals = ws.col_values(col)
    for i, v in enumerate(vals[1:], start=2):
        if v == ticker:
            return i
    return None


def marcar_favorita(ticker, valor):
    ws = _pestaña(SEG)
    i = _fila_de(ws, ticker, 1)
    if i:
        ws.update_cell(i, COLS_SEG.index("Favorita") + 1, "Sí" if valor else "No")


def quitar_seguimiento(ticker):
    """Quita la acción de tu lista y de Datos. El Histórico se conserva."""
    for nombre, col in ((SEG, 1), (DATOS, 3)):
        ws = _pestaña(nombre)
        i = _fila_de(ws, ticker, col)
        if i:
            ws.delete_rows(i)


# ---------------- Datos e Histórico ----------------
def guardar_fotos(filas):
    """Escribe varias fotos de una vez (pocas llamadas a Google, para no superar su límite por minuto).
    Datos: una fila por ticker, se sustituye. Histórico: una fila por ticker y día; si ya existe la de hoy, se sustituye."""
    if not filas:
        return
    _escribir(_pestaña(DATOS), filas, clave=lambda f: f["Ticker"], cols_clave=["Ticker"])
    _escribir(_pestaña(HIST), filas, clave=lambda f: (f["Fecha"], f["Ticker"]), cols_clave=["Fecha", "Ticker"])


def guardar_foto(fila):
    guardar_fotos([fila])


def _asegurar_columnas(ws, cab, filas):
    """Si la fila trae campos nuevos (p. ej. «Resistencias»), los añade al final de la cabecera."""
    nuevas = [k for f in filas for k in f if k not in cab]
    nuevas = list(dict.fromkeys(nuevas))
    if not nuevas:
        return cab
    total = len(cab) + len(nuevas)
    if ws.col_count < total:
        ws.add_cols(total - ws.col_count)
    ws.update([nuevas], gspread.utils.rowcol_to_a1(1, len(cab) + 1), value_input_option="RAW")
    return cab + nuevas


def _escribir(ws, filas, clave, cols_clave):
    cab = _asegurar_columnas(ws, _cabecera(ws), filas)
    columnas = [ws.col_values(cab.index(c) + 1) for c in cols_clave]
    existentes = {}
    for n, vals in enumerate(zip(*columnas), start=1):
        if n > 1:
            existentes[vals if len(vals) > 1 else vals[0]] = n
    actualizar, nuevas = [], []
    for f in filas:
        valores = _fila_a_lista(cab, f)
        n = existentes.get(clave(f))
        if n:
            actualizar.append({"range": f"A{n}", "values": [valores]})
        else:
            nuevas.append(valores)
    if actualizar:
        ws.batch_update(actualizar, value_input_option="RAW")
    if nuevas:
        ws.append_rows(nuevas, value_input_option="RAW")


# ---------------- Resultados (comparación de informes con el precio real) ----------------
RES = "Resultados"


def guardar_resultados(filas):
    """Sustituye la pestaña «Resultados» por el último cálculo. La crea si no existe."""
    if not filas:
        return
    libro = _libro()
    try:
        ws = libro.worksheet(RES)
    except gspread.WorksheetNotFound:
        ws = libro.add_worksheet(RES, rows=max(len(filas) + 10, 100), cols=len(filas[0]) + 2)
    cab = list(filas[0].keys())
    ws.clear()
    ws.update([cab] + [_fila_a_lista(cab, f) for f in filas], "A1", value_input_option="RAW")


# ---------------- Riesgo (una nota por acción y día; sirve para ver cómo evoluciona) ----------------
RIESGO = "Riesgo"


def _pestaña_riesgo():
    libro = _libro()
    try:
        return libro.worksheet(RIESGO)
    except gspread.WorksheetNotFound:
        return libro.add_worksheet(RIESGO, rows=1000, cols=12)


def guardar_riesgo(fila):
    """Guarda la nota de riesgo de hoy. Si ya hay una de hoy para ese ticker, la sustituye."""
    _escribir(_pestaña_riesgo(), [fila], clave=lambda f: (f["Fecha"], f["Ticker"]), cols_clave=["Fecha", "Ticker"])
    leer_riesgo.clear()


@st.cache_data(ttl=300, show_spinner=False)
def leer_riesgo():
    try:
        ws = _libro().worksheet(RIESGO)
    except gspread.WorksheetNotFound:
        return pd.DataFrame(columns=["Fecha", "Ticker", "Nota"])
    filas = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    return pd.DataFrame(filas) if filas else pd.DataFrame(columns=["Fecha", "Ticker", "Nota"])


def historial_riesgo(ticker):
    df = leer_riesgo()
    if df.empty:
        return []
    df = df[df["Ticker"] == ticker].copy()
    df["Nota"] = pd.to_numeric(df["Nota"], errors="coerce")
    df = df.dropna(subset=["Nota"]).sort_values("Fecha")
    return [[str(f)[:10], int(n)] for f, n in zip(df["Fecha"], df["Nota"])]


def ultima_nota_riesgo():
    """Última nota guardada de cada ticker: {ticker: (nota, fecha)}."""
    df = leer_riesgo()
    if df.empty:
        return {}
    df = df.copy()
    df["Nota"] = pd.to_numeric(df["Nota"], errors="coerce")
    df = df.dropna(subset=["Nota"]).sort_values("Fecha")
    return {t: (int(g["Nota"].iloc[-1]), str(g["Fecha"].iloc[-1])[:10]) for t, g in df.groupby("Ticker")}


# ---------------- Traducciones (la descripción de cada empresa se traduce una vez y se guarda) ----------------
TRAD = "Traducciones"


def leer_traduccion(ticker, texto_en):
    try:
        ws = _libro().worksheet(TRAD)
    except gspread.WorksheetNotFound:
        return None
    for f in ws.get_all_records():
        if f.get("Ticker") == ticker and f.get("Inglés") == texto_en and f.get("Castellano"):
            return f["Castellano"]
    return None


def guardar_traduccion(ticker, texto_en, texto_es):
    libro = _libro()
    try:
        ws = libro.worksheet(TRAD)
    except gspread.WorksheetNotFound:
        ws = libro.add_worksheet(TRAD, rows=500, cols=4)
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    _escribir(ws, [{"Ticker": ticker, "Inglés": texto_en, "Castellano": texto_es, "Fecha": hoy}],
              clave=lambda f: f["Ticker"], cols_clave=["Ticker"])
