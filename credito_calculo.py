# Página Crédito: precio de la acción frente a los spreads de crédito de EE. UU. publicados en FRED.
# Descarga y cálculo. La página solo presenta lo que sale de aquí.
import io
import json
import socket
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

INDICES = {
    "BBB": {"codigo": "BAMLC0A4CBBB", "nombre": "BBB EE. UU.",
            "texto": "Índice de bonos de empresas de EE. UU. con nota BBB, la más baja del grado de inversión. "
                     "Mide el crédito de las empresas grandes y estables."},
    "HY": {"codigo": "BAMLH0A0HYM2", "nombre": "High Yield EE. UU.",
           "texto": "Índice de bonos de empresas de EE. UU. con nota BB o inferior («bonos basura»). "
                    "Suele ser el primero en subir cuando el mercado se tensa."},
}
INDICE_AVISO = "HY"          # el aviso de crédito usa el índice que antes reacciona
VENTANAS = {20: "Corto plazo", 60: "Medio plazo"}
SESIONES_CORR = 60
MIN_MUESTRA = 40             # mínimo de cambios en 12 meses para calcular el umbral del aviso
URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={codigo}&cosd={desde}"
URL_API = ("https://api.stlouisfed.org/fred/series/observations?series_id={codigo}&observation_start={desde}"
           "&api_key={clave}&file_type=json")


class ErrorCredito(Exception):
    pass


def _leer(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (JJTrading_)", "Accept": "text/csv,application/json,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _motivo(e):
    if isinstance(e, urllib.error.HTTPError):
        return f"FRED ha respondido con error {e.code}"
    if isinstance(e, (TimeoutError, socket.timeout)) or "timed out" in str(e).lower():
        return "FRED no ha respondido a tiempo"
    if isinstance(e, urllib.error.URLError):
        return f"no se ha podido conectar con FRED ({e.reason})"
    return str(e) or type(e).__name__


def _serie_csv(codigo, desde):
    texto = _leer(URL_FRED.format(codigo=codigo, desde=desde))
    if texto.lstrip().startswith("<"):
        raise ErrorCredito("FRED ha devuelto una página web en lugar de datos (posible mantenimiento)")
    df = pd.read_csv(io.StringIO(texto))
    if df.shape[1] < 2 or df.empty:
        raise ErrorCredito("FRED no ha devuelto datos")
    return pd.to_datetime(df.iloc[:, 0], errors="coerce"), pd.to_numeric(df.iloc[:, 1], errors="coerce")


def _serie_api(codigo, desde, clave):
    js = json.loads(_leer(URL_API.format(codigo=codigo, desde=desde, clave=clave)))
    obs = js.get("observations") or []
    if not obs:
        raise ErrorCredito(js.get("error_message") or "la API de FRED no ha devuelto datos")
    return (pd.to_datetime([o.get("date") for o in obs], errors="coerce"),
            pd.to_numeric(pd.Series([o.get("value") for o in obs]), errors="coerce"))


def descargar_fred(codigo, desde, clave=None):
    """Serie diaria de FRED en puntos básicos (FRED la publica en %). Prueba la API (si hay clave) y el CSV, dos veces cada uno."""
    vias = ([("API", lambda: _serie_api(codigo, desde, clave))] if clave else []) + [("CSV", lambda: _serie_csv(codigo, desde))]
    motivos = []
    for nombre, via in vias:
        for intento in range(2):
            try:
                fechas, valores = via()
                s = pd.Series(np.asarray(valores, float) * 100, index=pd.DatetimeIndex(fechas)).dropna()
                s = s[s.index.notna()]
                if s.empty:
                    raise ErrorCredito("FRED no ha devuelto datos")
                return s.sort_index()
            except Exception as e:
                m = _motivo(e)
                if intento == 1 or isinstance(e, ErrorCredito):
                    motivos.append(f"{nombre}: {m}" if clave else m)
                    break
                time.sleep(2)
    raise ErrorCredito("; ".join(motivos))


def descargar_precio(simbolo):
    """Cierres diarios de 2 años (hacen falta para medir lo normal de los últimos 12 meses)."""
    h = yf.Ticker(simbolo).history(period="2y", interval="1d", auto_adjust=True)
    if h is None or h.empty or "Close" not in h:
        raise ErrorCredito(f"Yahoo no devuelve cotizaciones para {simbolo}")
    c = h["Close"].dropna()
    c.index = pd.DatetimeIndex(c.index).tz_localize(None).normalize()
    return c[~c.index.duplicated(keep="last")]


def _num(x, dec=None):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), dec) if dec is not None else float(x)


def correlacion(precio, spread, n=SESIONES_CORR):
    """Pearson entre variación diaria del precio (%) y variación diaria del spread (pb), últimos n pares válidos."""
    dp = precio.pct_change(fill_method=None) * 100
    ds = spread.diff()
    pares = pd.DataFrame({"p": dp, "s": ds}).dropna()
    if len(pares) < n:
        return None
    u = pares.tail(n)
    if u["p"].std() == 0 or u["s"].std() == 0:
        return None
    return _num(u["p"].corr(u["s"]), 2)


def aviso_credito(precio, spread, w, inicio):
    """Si el spread se ha movido en w sesiones más de lo habitual (una desviación típica en 12 meses) y qué ha hecho la acción."""
    cp = (precio / precio.shift(w) - 1) * 100
    cs = spread - spread.shift(w)
    df = pd.DataFrame({"p": cp, "s": cs}).dropna()
    hist = df[df.index >= inicio]
    if len(hist) < MIN_MUESTRA:
        return {"ventana": w, "nombre": VENTANAS[w], "estado": None}
    up, us = hist["p"].std(), hist["s"].std()
    ult = hist.iloc[-1]
    if ult["s"] > us:
        estado = "empeora_cae" if ult["p"] < 0 else "empeora_no_cae"
    elif ult["s"] < -us:
        estado = "mejora"
    else:
        estado = "estable"
    return {"ventana": w, "nombre": VENTANAS[w], "estado": estado, "fecha": hist.index[-1].strftime("%Y-%m-%d"),
            "precio_pct": _num(ult["p"], 1), "spread_pb": _num(ult["s"], 0),
            "umbral_pct": _num(up, 1), "umbral_pb": _num(us, 0)}


def calcular(precio, spreads):
    """precio: cierres diarios. spreads: {clave: serie en pb o un texto de error}. Ventana de 12 meses."""
    if precio is None or len(precio) < 2:
        raise ErrorCredito("No hay cotizaciones suficientes")
    corte = precio.index[-1]
    inicio = corte - pd.DateOffset(years=1)
    R = {"corte": corte.strftime("%Y-%m-%d"), "precio": precio[precio.index >= inicio],
         "precio_ultimo": _num(precio.iloc[-1], 2), "series": {}}
    for k, info in INDICES.items():
        s = spreads.get(k)
        d = {"clave": k, **info}
        if not isinstance(s, pd.Series) or s.empty:
            d.update(error=s if isinstance(s, str) else "sin datos", alineada=None)
            R["series"][k] = d
            continue
        al = s.reindex(precio.index)                     # fechas de la acción; sin dato = hueco, no se rellena
        en12 = al[al.index >= inicio].dropna()
        d.update(error=None, alineada=al[al.index >= inicio], ultimo_publicado=s.index[-1].strftime("%Y-%m-%d"))
        if en12.empty:
            d.update(error="la serie no tiene datos en los últimos 12 meses")
        else:
            d.update(actual=_num(en12.iloc[-1], 0), fecha_actual=en12.index[-1].strftime("%Y-%m-%d"),
                     var12=_num(en12.iloc[-1] - en12.iloc[0], 0), fecha_inicio=en12.index[0].strftime("%Y-%m-%d"),
                     corr=correlacion(precio[precio.index >= inicio], al[al.index >= inicio]))
            if k == INDICE_AVISO:
                d["avisos"] = [aviso_credito(precio, al, w, inicio) for w in VENTANAS]
        R["series"][k] = d
    return R
