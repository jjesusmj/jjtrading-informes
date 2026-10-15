# =====================================================================
#  JJTrading_ — evaluación de informes pasados
#  Compara los niveles teóricos de cada informe guardado (entrada, stop,
#  objetivos, resistencias) con lo que hizo el precio después.
#  Una sola fuente: Yahoo Finance, precios sin ajustar por dividendos,
#  solo horario regular. El estado se decide con velas de 1H.
# =====================================================================
import math

import numpy as np
import pandas as pd
import yfinance as yf

CADUCIDAD_SES = 20      # sesiones sin activarse → plan caducado
PLAZO_SES = 60          # sesiones máximas con la operación abierta (plazo del método, niveles.PLAZO_SES)
TEST_RES_PCT = 0.5      # un máximo a menos de este % de una resistencia cuenta como test
LIMITE_1H_DIAS = 729    # Yahoo da 1H de los últimos 730 días
LIMITE_5M_DIAS = 59     # Yahoo da 5 min de los últimos 60 días

ESTADOS = ["Pendiente", "Activado", "T1 alcanzado", "T2", "Stop", "Plazo", "Caducado", "Invalidado",
           "Sin datos", "Datos inválidos"]
ABIERTOS = {"Activado", "T1 alcanzado"}
CERRADOS = {"T2", "Stop", "Plazo"}

COLS = ["Open", "High", "Low", "Close"]


# ---------------- Descarga (única fuente: Yahoo) ----------------
def _limpiar(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=COLS)
    return df.dropna(subset=["Close"])


def descargar(ticker, desde):
    """Velas para evaluar todos los informes de un ticker desde `desde` (Timestamp con zona).
    Devuelve dict: h1 (velas 1H), d1 (velas diarias), splits (Serie fecha → ratio)."""
    tk = yf.Ticker(ticker)
    ahora = pd.Timestamp.now(tz="UTC")
    inicio_1h = max(desde.tz_convert("UTC"), ahora - pd.Timedelta(days=LIMITE_1H_DIAS))
    h1 = _limpiar(tk.history(start=inicio_1h.strftime("%Y-%m-%d"), interval="1h",
                             auto_adjust=False, prepost=False))
    d1 = tk.history(start=(desde - pd.Timedelta(days=10)).strftime("%Y-%m-%d"), interval="1d",
                    auto_adjust=False, prepost=False, actions=True)
    splits = d1["Stock Splits"] if "Stock Splits" in d1 else pd.Series(dtype=float)
    splits = splits[splits > 0]
    return {"h1": h1, "d1": _limpiar(d1), "splits": splits}


def velas_5m(ticker, dia_inicio, dia_fin):
    """Velas de 5 min entre dos fechas (solo últimos 60 días). Mismos parámetros que el resto."""
    fin = (pd.Timestamp(dia_fin) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    return _limpiar(yf.Ticker(ticker).history(start=pd.Timestamp(dia_inicio).strftime("%Y-%m-%d"), end=fin,
                                              interval="5m", auto_adjust=False, prepost=False))


def disponible_5m(fecha):
    return (pd.Timestamp.now(tz="UTC") - fecha.tz_convert("UTC")).days <= LIMITE_5M_DIAS


def disponible_1h(fecha):
    return (pd.Timestamp.now(tz="UTC") - fecha.tz_convert("UTC")).days <= LIMITE_1H_DIAS


# ---------------- Utilidades ----------------
def _num(x):
    try:
        v = float(str(x).replace(",", ".")) if isinstance(x, str) else float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def factor_split(splits, fecha):
    """Producto de los splits posteriores a la fecha del informe (Yahoo ya ajusta las velas por splits)."""
    if splits is None or splits.empty:
        return 1.0
    idx = splits.index
    f = fecha.tz_convert(idx.tz) if idx.tz is not None else fecha.tz_localize(None)
    post = splits[idx.normalize() > f.normalize()]
    return float(np.prod(post.values)) if len(post) else 1.0


def a_diario(barras):
    """Velas diarias construidas desde las de 1H (misma fuente que el estado)."""
    if barras.empty:
        return barras
    g = barras.groupby(barras.index.date)
    d = pd.DataFrame({"Open": g["Open"].first(), "High": g["High"].max(), "Low": g["Low"].min(),
                      "Close": g["Close"].last()})
    d.index = pd.DatetimeIndex(pd.to_datetime(d.index)).tz_localize(barras.index.tz)
    return d


def barras_para(datos, fecha):
    """Velas que decide el estado: 1H desde la hora del informe; diario si el informe tiene más de 730 días."""
    h1 = datos["h1"]
    if disponible_1h(fecha) and not h1.empty:
        return h1[h1.index >= fecha.tz_convert(h1.index.tz)], "1H"
    d1 = datos["d1"]
    if d1.empty:
        return d1, "Diario"
    f = fecha.tz_convert(d1.index.tz)
    return d1[d1.index.normalize() > f.normalize()], "Diario"


# ---------------- Evaluación de un informe ----------------
def evaluar(inf, barras, splits=None):
    """inf: dict con fecha (Timestamp con zona), zona_baja, zona_alta, stop, obj1, obj2,
    resistencias (lista), estado_inicial. barras: velas OHLC posteriores al informe (1H o diario)."""
    zb, za, st, o1, o2 = (_num(inf.get(k)) for k in ("zona_baja", "zona_alta", "stop", "obj1", "obj2"))
    res = {"estado": None, "eventos": [], "entrada": None, "salida": None, "r": None, "r_flotante": None,
           "mfe_r": None, "mae_r": None, "mfe_pct": None, "mae_pct": None, "sesiones": None,
           "t1": False, "fecha_entrada": None, "fecha_salida": None, "resistencias": [],
           "factor_split": 1.0, "niveles": {}}
    if None in (zb, za, st, o1, o2) or not (st < zb <= za < o1 <= o2):
        res["estado"] = "Datos inválidos"
        return res

    f = factor_split(splits, inf["fecha"])
    res["factor_split"] = f
    zb, za, st, o1, o2 = (x / f for x in (zb, za, st, o1, o2))
    resistencias = [r / f for r in (_num(x) for x in inf.get("resistencias") or []) if r]
    res["niveles"] = {"zona_baja": zb, "zona_alta": za, "stop": st, "obj1": o1, "obj2": o2,
                      "resistencias": resistencias}

    def evento(ts, tipo, precio, texto):
        res["eventos"].append({"fecha": ts, "tipo": tipo, "precio": precio, "texto": texto})

    res["resistencias"] = _resistencias(resistencias, barras)

    if str(inf.get("estado_inicial", "")).strip() == "Invalidado":
        res["estado"] = "Invalidado"
        return res
    if barras.empty:
        res["estado"] = "Pendiente"
        res["sesiones"] = 0
        return res

    dias = barras.index.date
    ses_idx = pd.Series(pd.factorize(dias)[0], index=barras.index)   # 0 = primera sesión tras el informe
    o, h, l, c = (barras[k].values.astype(float) for k in COLS)
    activo, ses_act, entrada, R = False, None, None, None
    mfe = mae = 0.0
    final = None

    for i in range(len(barras)):
        ts, s = barras.index[i], int(ses_idx.iloc[i])
        if not activo:
            if s >= CADUCIDAD_SES:
                final = ("Caducado", None, ts, f"{CADUCIDAD_SES} sesiones sin tocar la zona")
                break
            if l[i] <= za:
                if o[i] < st:
                    final = ("Invalidado", None, ts, "Abrió por debajo del stop sin pasar por la zona")
                    break
                entrada = min(o[i], za)
                R = entrada - st
                activo, ses_act = True, s
                res["entrada"], res["fecha_entrada"] = entrada, ts
                evento(ts, "Entrada", entrada, "Toca la zona de entrada")
                if l[i] <= st:                       # entrada y stop en la misma vela → peor caso
                    final = ("Stop", st, ts, "Entrada y stop en la misma vela (peor caso)")
                    mae = R
                    break
                mae = max(mae, entrada - l[i])
                mfe = max(mfe, c[i] - entrada)       # el máximo de esa vela pudo ser antes de entrar
            continue

        if s - ses_act >= PLAZO_SES:
            final = ("Plazo", c[i - 1], barras.index[i - 1], f"{PLAZO_SES} sesiones sin llegar a T2 ni al stop")
            break
        if l[i] <= st:                               # stop y T2 en la misma vela → stop (peor caso)
            salida = min(o[i], st)
            mae = max(mae, entrada - salida)
            final = ("Stop", salida, ts, "Toca el stop" + (" con hueco a la baja" if o[i] < st else ""))
            break
        mae = max(mae, entrada - l[i])
        mfe = max(mfe, h[i] - entrada)
        if not res["t1"] and h[i] >= o1:
            res["t1"] = True
            evento(ts, "T1", o1, "Toca el objetivo 1")
        if h[i] >= o2:
            final = ("T2", max(o[i], o2), ts, "Toca el objetivo 2")
            break

    ultimo = barras.index[-1]
    if final:
        estado, salida, ts, texto = final
        res["estado"] = estado
        res["fecha_salida"] = ts
        res["sesiones"] = int(ses_idx.loc[:ts].iloc[-1]) + 1
        if salida is not None:
            res["salida"] = salida
            res["r"] = (salida - entrada) / R
        evento(ts, estado, salida, texto)
    elif activo:
        res["estado"] = "T1 alcanzado" if res["t1"] else "Activado"
        res["r_flotante"] = (c[-1] - entrada) / R
        res["sesiones"] = int(ses_idx.iloc[-1]) + 1
    else:
        res["estado"] = "Pendiente"
        res["sesiones"] = int(ses_idx.iloc[-1]) + 1

    if entrada is not None:
        res["mfe_r"], res["mae_r"] = mfe / R, mae / R
        res["mfe_pct"], res["mae_pct"] = mfe / entrada * 100, mae / entrada * 100
    res["eventos"].sort(key=lambda e: e["fecha"])
    res["ultimo_dato"] = ultimo
    return res


def _resistencias(niveles, barras):
    """Por resistencia: sesiones que la testean sin cerrar encima y primera sesión que cierra por encima."""
    if not niveles or barras.empty:
        return [{"nivel": n, "tests": 0, "rota": None} for n in niveles]
    intradia = len(barras) > 1 and (barras.index[1:] - barras.index[:-1]).min() < pd.Timedelta(hours=20)
    d = a_diario(barras) if intradia else barras
    salida = []
    for n in niveles:
        tests, rota = 0, None
        for ts, fila in d.iterrows():
            if fila["Close"] > n:
                rota = ts
                break
            if fila["High"] >= n * (1 - TEST_RES_PCT / 100):
                tests += 1
        salida.append({"nivel": n, "tests": tests, "rota": rota})
    return salida


# ---------------- Lectura del Histórico ----------------
def informes_desde_historico(df):
    """Filas del Histórico → lista de informes. Columna 'clave' identifica cada fila."""
    if df is None or df.empty:
        return []
    out = []
    for _, f in df.iterrows():
        hora = str(f.get("Hora actualización") or f.get("Fecha") or "").strip()
        try:
            fecha = pd.Timestamp(hora)
            fecha = fecha.tz_localize("Europe/Madrid") if fecha.tzinfo is None else fecha
        except (ValueError, TypeError):
            continue
        res = str(f.get("Resistencias") or "")
        out.append({
            "clave": f"{f.get('Ticker')}|{hora}", "ticker": str(f.get("Ticker") or "").strip(),
            "nombre": f.get("Nombre", ""), "bolsa": f.get("Bolsa", ""), "moneda": f.get("Moneda", ""),
            "fecha": fecha, "precio": _num(f.get("Último precio")),
            "zona_baja": f.get("Zona baja"), "zona_alta": f.get("Zona alta"), "stop": f.get("Stop"),
            "obj1": f.get("Objetivo 1"), "obj2": f.get("Objetivo 2"),
            "resistencias": [x for x in res.replace(",", ".").split(";") if x.strip()] if res else [],
            "estado_inicial": f.get("Estado", ""),
        })
    return out


def quitar_repetidos(informes):
    """Si guardas la misma acción varios días con los mismos niveles, es el mismo plan:
    se queda el primero de cada racha."""
    vistos, out = {}, []
    for inf in sorted(informes, key=lambda x: (x["ticker"], x["fecha"])):
        firma = tuple(None if _num(inf[k]) is None else round(_num(inf[k]), 2)
                      for k in ("zona_baja", "zona_alta", "stop", "obj1", "obj2"))
        if vistos.get(inf["ticker"]) == firma:
            continue
        vistos[inf["ticker"]] = firma
        out.append(inf)
    return out


# ---------------- Resumen ----------------
def resumen(resultados):
    """resultados: lista de dicts de evaluar(). Devuelve cifras para la cabecera."""
    validos = [r for r in resultados if r["estado"] not in ("Sin datos", "Datos inválidos")]
    activados = [r for r in validos if r["entrada"] is not None]
    cerrados = [r for r in activados if r["estado"] in CERRADOS]
    abiertos = [r for r in activados if r["estado"] in ABIERTOS]
    stops = [r for r in activados if r["estado"] == "Stop"]
    pct = lambda a, b: (len(a) / len(b) * 100) if b else None
    return {
        "informes": len(validos),
        "activados_pct": pct(activados, validos),
        "t1_pct": pct([r for r in activados if r["t1"]], activados),
        "t2_pct": pct([r for r in activados if r["estado"] == "T2"], activados),
        "stop_pct": pct(stops, activados),
        "stops_tras_t1_pct": pct([r for r in stops if r["t1"]], stops),
        "r_medio": float(np.mean([r["r"] for r in cerrados])) if cerrados else None,
        "r_total": float(np.sum([r["r"] for r in cerrados])) if cerrados else None,
        "n_cerrados": len(cerrados),
        "r_flotante": float(np.mean([r["r_flotante"] for r in abiertos])) if abiertos else None,
        "n_abiertos": len(abiertos),
    }
