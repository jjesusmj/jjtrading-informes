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
    filas = ws.get_all_records()
    return pd.DataFrame(filas) if filas else pd.DataFrame(columns=_cabecera(ws))


def limpiar_cache():
    leer_seguimiento.clear()
    leer_datos.clear()


# ---------------- Seguimiento ----------------
def añadir_seguimiento(ticker, nombre, bolsa, moneda):
    ws = _pestaña(SEG)
    if ticker in ws.col_values(1)[1:]:
        return False
    hoy = datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d")
    ws.append_row([ticker, nombre, bolsa, moneda, "No", hoy], value_input_option="RAW")
    return True


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


def _escribir(ws, filas, clave, cols_clave):
    cab = _cabecera(ws)
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
