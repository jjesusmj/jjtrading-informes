# Cálculo de la pestaña Riesgo (metodología v2.1 sin IA + mejoras MeridIAn).
# Entrada: dict en bruto de riesgo_datos.descargar(). Todo ratio se calcula aquí, nunca se toma de Yahoo.
import datetime as dt
import math
import statistics as stt

import numpy as np

FUENTE = "Yahoo Finance"
VEREDICTOS = [(30, "Riesgo bajo", "Los indicadores de valoración, salud y crecimiento están mayoritariamente en zona favorable."),
              (50, "Riesgo moderado", "Predominan los indicadores favorables, con algunos puntos que vigilar."),
              (70, "Riesgo elevado", "Varios indicadores están en zona de precaución o desfavorable."),
              (100, "Riesgo alto", "La mayoría de los indicadores están en zona desfavorable.")]
BLOQUES = [("val", "Valoración", 0.35), ("sal", "Salud financiera", 0.35), ("cre", "Crecimiento", 0.30)]
NO_APLICA_FIN = {"ev_ebitda", "dn_ebitda", "liquidez", "cobertura", "margen_fcf", "altman"}
TASA, TASA_BAJA, TASA_ALTA, PERPETUO, TOPE_G = 0.09, 0.08, 0.10, 0.025, 0.10


# ---------------------------------------------------------------- utilidades
def _f(x):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else x
    except (TypeError, ValueError):
        return None


def _fecha(s):
    return dt.date.fromisoformat(s[:10])


def _dias(a, b):
    return (_fecha(b) - _fecha(a)).days


def _ult(serie):
    return (serie[-1][0], _f(serie[-1][1])) if serie else (None, None)


def _factor_split(fecha, splits):
    f = 1.0
    for d, num, den in splits:
        if d > fecha and den:
            f *= num / den
    return f


def _ajustar_acciones(serie, splits, ref):
    """Pasa un número de acciones a la base actual si Yahoo no lo ha reexpresado tras un split."""
    out = []
    for d, v in serie:
        v = _f(v)
        f = _factor_split(d, splits)
        if v and ref and f != 1 and abs(math.log(v * f / ref)) < abs(math.log(v / ref)):
            out.append([d, v * f, f])
        else:
            out.append([d, v, 1.0])
    return out


def _ajustar_bpa(bpa, acciones_aj):
    m = {d: f for d, _, f in acciones_aj}
    return [[d, (_f(v) / m.get(d, 1.0)) if _f(v) is not None else None] for d, v in bpa]


def es(x, dec=1, pct=False, signo=False):
    if x is None:
        return "Sin dato"
    s = f"{x:+,.{dec}f}" if signo else f"{x:,.{dec}f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + (" %" if pct else "")


def millones(x, mon):
    if x is None:
        return "Sin dato"
    a = abs(x)
    if a >= 1e12:
        return f"{es(x / 1e12, 2)} billones {mon}"
    if a >= 1e9:
        return f"{es(x / 1e9, 1)} mil M {mon}"
    return f"{es(x / 1e6, 1)} M {mon}"


# ---------------------------------------------------------------- preparación de cuentas
class Cuentas:
    def __init__(self, R):
        self.R = R
        self.A, self.Q, self.T = R.get("anual") or {}, R.get("trimestral") or {}, R.get("ttm") or {}
        sp = R.get("splits") or []
        ref = _f(R.get("acciones")) or _ult(self.Q.get("OrdinarySharesNumber") or self.A.get("OrdinarySharesNumber") or [])[1]
        self.ref = ref
        for D in (self.A, self.Q, self.T):
            for k in ("DilutedAverageShares", "OrdinarySharesNumber"):
                if k in D:
                    D[k + "_aj"] = _ajustar_acciones(D[k], sp, ref)
            if "DilutedEPS" in D:
                base = D.get("DilutedAverageShares_aj") or D.get("OrdinarySharesNumber_aj") or []
                D["DilutedEPS_aj"] = _ajustar_bpa(D["DilutedEPS"], base)

    def ttm(self, k):
        """(fecha, valor) de 12 meses: serie TTM de Yahoo; si falta, último ejercicio anual."""
        s = self.T.get(k)
        if s:
            d, v = _ult(s)
            return d, v, "12 meses"
        d, v = _ult(self.A.get(k) or [])
        return d, v, "último ejercicio"

    def ttm_previo(self, k):
        s = self.T.get(k) or []
        if len(s) >= 2:
            d1, v1 = _ult(s)
            for d0, v0 in reversed(s[:-1]):
                if 330 <= _dias(d0, d1) <= 400:
                    return d0, _f(v0)
        return None, None

    def balance(self, k):
        cands = [s[-1] for s in (self.Q.get(k), self.A.get(k)) if s]
        if not cands:
            return None, None
        d, v = max(cands, key=lambda x: x[0])
        return d, _f(v)

    def balance_en(self, k, fecha):
        for s in (self.Q.get(k), self.A.get(k)):
            for d, v in s or []:
                if d == fecha:
                    return _f(v)
        return None

    def anual(self, k):
        return [[d, _f(v)] for d, v in (self.A.get(k) or [])]


# ---------------------------------------------------------------- técnicos (sección 6)
def sma(x, n):
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        c = np.cumsum(np.insert(x, 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def ema_sembrada(x, n):
    out = np.full(len(x), np.nan)
    idx = np.where(~np.isnan(x))[0]
    if len(idx) < n:
        return out
    i0 = idx[0]
    out[i0 + n - 1] = np.mean(x[i0:i0 + n])
    a = 2 / (n + 1)
    for i in range(i0 + n, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi_wilder(x, n=14):
    if len(x) <= n:
        return None
    d = np.diff(x)
    g, p = np.maximum(d, 0), np.maximum(-d, 0)
    ag, ap = g[:n].mean(), p[:n].mean()
    for i in range(n, len(d)):
        ag = (ag * (n - 1) + g[i]) / n
        ap = (ap * (n - 1) + p[i]) / n
    return 100.0 if ap == 0 else 100 - 100 / (1 + ag / ap)


def _ultimo_cruce(a, b, fechas):
    s = np.sign(a - b)
    ult = None
    for i in range(1, len(s)):
        if not np.isnan(s[i]) and not np.isnan(s[i - 1]) and s[i] != s[i - 1] and s[i] != 0:
            ult = fechas[i]
    return ult


def tecnicos(diario):
    f = [d for d, _ in diario]
    c = np.array([v for _, v in diario], float)
    P = c[-1]
    T = {}
    for n in (20, 50, 200):
        m = sma(c, n)[-1]
        T[f"sma{n}"] = None if np.isnan(m) else float(m)
        T[f"dist_sma{n}"] = None if np.isnan(m) else float((P / m - 1) * 100)
    s50, s200 = sma(c, 50), sma(c, 200)
    if T["sma50"] is not None and T["sma200"] is not None:
        T["cruce_estado"] = "Media 50 por encima de la 200" if T["sma50"] > T["sma200"] else "Media 50 por debajo de la 200"
        T["cruce_fecha"] = _ultimo_cruce(s50, s200, f)
    else:
        T["cruce_estado"], T["cruce_fecha"] = None, None
    e12, e26 = ema_sembrada(c, 12), ema_sembrada(c, 26)
    macd = e12 - e26
    sen = ema_sembrada(macd, 9)
    if not np.isnan(sen[-1]):
        T.update(macd=float(macd[-1]), senal=float(sen[-1]), hist=float(macd[-1] - sen[-1]),
                 macd_estado="Por encima de la señal" if macd[-1] > sen[-1] else "Por debajo de la señal",
                 macd_cruce=_ultimo_cruce(macd, sen, f))
    else:
        T.update(macd=None, senal=None, hist=None, macd_estado=None, macd_cruce=None)
    T["rsi_d"] = rsi_wilder(c)
    sem = {}
    for d, v in diario:
        k = _fecha(d).isocalendar()[:2]
        sem[k] = v
    T["rsi_s"] = rsi_wilder(np.array(list(sem.values()), float))
    for n, k in ((21, "r1m"), (63, "r3m"), (126, "r6m")):
        T[k] = float((P / c[-1 - n] - 1) * 100) if len(c) > n else None
    anio = f[-1][:4]
    prev = [v for d, v in diario if d[:4] < anio]
    T["ytd"] = float((P / prev[-1] - 1) * 100) if prev else None
    i_max, i_min = int(np.argmax(c)), int(np.argmin(c))
    T.update(max52=float(c[i_max]), max52_f=f[i_max], dist_max52=float((P / c[i_max] - 1) * 100),
             min52=float(c[i_min]), min52_f=f[i_min], dist_min52=float((P / c[i_min] - 1) * 100))
    niveles = []
    for i in range(10, len(c) - 10):
        ventana = c[i - 10:i + 11]
        if c[i] == ventana.min():
            niveles.append((c[i], f[i]))
        elif c[i] == ventana.max():
            niveles.append((c[i], f[i]))
    grupos = []
    for v, d in sorted(niveles):
        if grupos and abs(v / np.mean([x for x, _ in grupos[-1]]) - 1) < 0.02:
            grupos[-1].append((v, d))
        else:
            grupos.append([(v, d)])
    lv = [(float(np.mean([x for x, _ in g])), max(d for _, d in g)) for g in grupos]
    T["resistencias"] = [{"valor": v, "fecha": d, "dist": (v / P - 1) * 100} for v, d in sorted([x for x in lv if x[0] > P])[:2]]
    T["soportes"] = [{"valor": v, "fecha": d, "dist": (v / P - 1) * 100} for v, d in sorted([x for x in lv if x[0] < P], reverse=True)[:2]]
    r = np.diff(np.log(c))
    sd = float(np.std(r, ddof=1)) if len(r) > 2 else None
    T["vol"] = sd * math.sqrt(252) * 100 if sd else None
    T["osc"] = sd * P if sd else None
    T["serie_s50"] = [None if np.isnan(x) else round(float(x), 4) for x in s50]
    T["serie_s200"] = [None if np.isnan(x) else round(float(x), 4) for x in s200]
    return T


# ---------------------------------------------------------------- umbrales (sección 4)
def color(id_, v):
    if v is None:
        return "gris"
    U = {"per_fwd": (15, 25, False), "ev_ebitda": (10, 18, False), "rent_fcf": (5, 2, True), "ps": (2, 6, False),
         "potencial": (15, 0, True), "dn_ebitda": (1.5, 3, False), "liquidez": (1.5, 1, True), "cobertura": (8, 3, True),
         "margen_fcf": (15, 5, True), "roic": (15, 8, True), "altman": (3, 1.8, True), "ventas_ia": (10, 0, True),
         "bpa_ia": (10, 0, True), "cagr3": (8, 0, True), "bpa_est": (10, 0, True), "batidas": (4, 1, True),
         "margen_op_var": (1, -1, True)}
    if id_ == "per_fwd" and v < 0:
        return "rojo"
    if id_ == "batidas":
        return "verde" if v >= 4 else ("rojo" if v <= 1 else "ambar")
    g, r, mayor = U[id_]
    if mayor:
        return "verde" if v > g else ("rojo" if v < r else "ambar")
    return "verde" if v < g else ("rojo" if v > r else "ambar")


UMBRAL_TXT = {"per_fwd": "< 15 / 15–25 / > 25 · negativo = rojo", "ev_ebitda": "< 10 / 10–18 / > 18",
              "rent_fcf": "> 5 % / 2–5 % / < 2 %", "peg": "< 1 / 1–2 / > 2", "ps": "< 2 / 2–6 / > 6",
              "potencial": "> 15 % / 0–15 % / < 0 %", "dn_ebitda": "< 1,5 / 1,5–3 / > 3 · caja neta = verde",
              "liquidez": "> 1,5 / 1–1,5 / < 1", "cobertura": "> 8 / 3–8 / < 3", "margen_fcf": "> 15 % / 5–15 % / < 5 %",
              "roic": "> 15 % / 8–15 % / < 8 %", "altman": "> 3 / 1,8–3 / < 1,8", "ventas_ia": "> 10 % / 0–10 % / < 0 %",
              "bpa_ia": "> 10 % / 0–10 % / < 0 %", "cagr3": "> 8 % / 0–8 % / < 0 %", "bpa_est": "> 10 % / 0–10 % / < 0 %",
              "batidas": "4 / 2–3 / 0–1", "margen_op_var": "> +1 pp / −1 a +1 pp / < −1 pp"}

NOMBRES = {"per_fwd": "PER forward", "ev_ebitda": "EV/EBITDA", "rent_fcf": "Rentabilidad FCF", "peg": "PEG",
           "ps": "Precio/Ventas", "potencial": "Potencial frente al precio objetivo", "dn_ebitda": "Deuda neta/EBITDA",
           "liquidez": "Liquidez corriente", "cobertura": "Cobertura de intereses", "margen_fcf": "Margen FCF",
           "roic": "ROIC", "altman": "Altman Z-Score", "ventas_ia": "Ventas interanual", "bpa_ia": "BPA interanual",
           "cagr3": "CAGR de ventas a 3 años", "bpa_est": "Crecimiento estimado del BPA", "batidas": "Batidas de BPA",
           "margen_op_var": "Variación del margen operativo"}
ORDEN = {"val": ["per_fwd", "ev_ebitda", "rent_fcf", "peg", "ps", "potencial"],
         "sal": ["dn_ebitda", "liquidez", "cobertura", "margen_fcf", "roic", "altman"],
         "cre": ["ventas_ia", "bpa_ia", "cagr3", "bpa_est", "batidas", "margen_op_var"]}
UNIDAD = {"rent_fcf": "%", "potencial": "%", "margen_fcf": "%", "roic": "%", "ventas_ia": "%", "bpa_ia": "%",
          "cagr3": "%", "bpa_est": "%", "margen_op_var": "pp", "batidas": "de 4"}
POR_QUE = {
    "per_fwd": "Indica cuánto pagas hoy por cada unidad de beneficio que se espera. Cuanto más alto, más optimismo hay ya en el precio.",
    "ev_ebitda": "Compara lo que vale la empresa entera, deuda incluida, con su resultado de explotación. Permite comparar empresas con distinta deuda.",
    "rent_fcf": "Es la caja que genera el negocio en relación con lo que cuesta en bolsa. Esa caja paga dividendos, recompras o deuda.",
    "peg": "Ajusta el PER por el crecimiento esperado. Un PER alto puede estar justificado si el beneficio crece rápido.",
    "ps": "Útil cuando el beneficio es bajo o negativo: dice cuánto pagas por cada unidad de ventas.",
    "potencial": "Mide la distancia hasta el precio que los analistas consideran razonable. Es una opinión de terceros, no una garantía.",
    "dn_ebitda": "Dice cuántos años de resultado de explotación harían falta para pagar la deuda neta. Más deuda es más riesgo si el negocio flojea.",
    "liquidez": "Compara lo que la empresa cobrará o tiene en caja a corto plazo con lo que debe pagar en menos de un año.",
    "cobertura": "Indica cuántas veces cubre el beneficio operativo los intereses de la deuda. Si es baja, una subida de tipos o una caída del negocio aprieta.",
    "margen_fcf": "De cada unidad que vende, cuánto le queda en caja libre. Un margen alto da margen de maniobra.",
    "roic": "Mide lo bien que la empresa usa el dinero invertido, propio y prestado. Un ROIC alto y estable suele indicar ventaja competitiva.",
    "altman": "Combina cinco ratios del balance y los resultados para estimar el riesgo de quiebra a dos años.",
    "ventas_ia": "Muestra si el negocio está creciendo o encogiendo en el último año.",
    "bpa_ia": "Muestra si el beneficio por acción, que es lo que corresponde al accionista, sube o baja.",
    "cagr3": "Suaviza los altibajos de un solo año: es el crecimiento medio anual de las ventas en tres años.",
    "bpa_est": "Es lo que los analistas esperan que crezca el beneficio por acción el próximo ejercicio.",
    "batidas": "Cuenta cuántas veces el beneficio real superó lo que esperaban los analistas. Repetirlo indica previsiones prudentes o un negocio que sorprende.",
    "margen_op_var": "Si el margen operativo sube, la empresa gana más por cada unidad vendida; si baja, sus costes crecen más que sus ventas."}


def frase(id_, v, mon, extra):
    """Frase en moneda de cotización bajo cada tarjeta (grupo A)."""
    if v is None:
        return None
    m = mon
    F = {
        "per_fwd": f"Pagas {es(v)} {m} por cada 1 {m} de beneficio que se espera ganar en un año." if v > 0 else "Se esperan pérdidas: no hay beneficio que pagar.",
        "ev_ebitda": f"La empresa entera, con su deuda, vale {es(v)} veces lo que gana antes de intereses, impuestos y amortizaciones.",
        "rent_fcf": f"Por cada 100 {m} que vale en bolsa, generó {es(v)} {m} de caja libre en 12 meses.",
        "ps": f"Pagas {es(v, 2)} {m} por cada 1 {m} que vende al año.",
        "potencial": f"El precio objetivo medio queda {es(abs(v))} % {'por encima' if v >= 0 else 'por debajo'} del cierre.",
        "dn_ebitda": (f"Tiene más caja que deuda." if extra.get("caja_neta") else f"Necesitaría {es(v)} años de resultado de explotación para pagar su deuda neta."),
        "liquidez": f"Por cada 1 {m} que debe pagar este año, tiene {es(v, 2)} {m} en activos a corto plazo.",
        "cobertura": f"Su beneficio operativo cubre {es(v)} veces los intereses de su deuda.",
        "margen_fcf": f"De cada 100 {m} que vende, le quedan {es(v)} {m} de caja libre.",
        "roic": f"Por cada 100 {m} invertidos en el negocio, obtiene {es(v)} {m} de beneficio operativo después de impuestos.",
        "altman": "Zona segura: riesgo de quiebra bajo." if v > 3 else ("Zona gris: vigilar." if v >= 1.8 else "Zona de riesgo de quiebra."),
        "ventas_ia": f"Por cada 100 {m} que vendía hace un año, ahora vende {es(100 + v)} {m}.",
        "bpa_ia": f"Por cada 100 {m} de beneficio por acción hace un año, ahora gana {es(100 + v)} {m}.",
        "cagr3": f"Sus ventas han crecido de media un {es(v)} % cada año durante tres años.",
        "bpa_est": f"Los analistas esperan que el beneficio por acción {'suba' if v >= 0 else 'baje'} un {es(abs(v))} % el próximo ejercicio.",
        "batidas": f"Superó la previsión de beneficio en {int(v)} de las últimas 4 presentaciones.",
        "margen_op_var": f"Su margen operativo ha {'subido' if v >= 0 else 'bajado'} {es(abs(v))} puntos en un año."}
    return F.get(id_)


ESENCIAL = {
    "per_fwd": ("Barata frente a su beneficio estimado", "Cara frente a su beneficio estimado"),
    "ev_ebitda": ("Valoración moderada con deuda incluida", "Valoración exigente con deuda incluida"),
    "rent_fcf": ("Genera mucha caja para su precio", "Genera poca caja para su precio"),
    "ps": ("Precio bajo frente a sus ventas", "Precio alto frente a sus ventas"),
    "potencial": ("Los analistas ven recorrido al alza", "Cotiza por encima del objetivo de los analistas"),
    "dn_ebitda": ("Deuda baja", "Deuda alta"), "liquidez": ("Holgura para pagar a corto plazo", "Poca holgura a corto plazo"),
    "cobertura": ("Paga sus intereses con holgura", "Le cuesta cubrir sus intereses"),
    "margen_fcf": ("Convierte mucha venta en caja", "Convierte poca venta en caja"),
    "roic": ("Saca mucho partido al capital invertido", "Saca poco partido al capital invertido"),
    "altman": ("Balance sólido", "Señal de riesgo financiero"), "ventas_ia": ("Ventas creciendo con fuerza", "Ventas a la baja"),
    "bpa_ia": ("Beneficio por acción creciendo", "Beneficio por acción a la baja"),
    "cagr3": ("Crecimiento sostenido de ventas", "Ventas encogiendo en tres años"),
    "bpa_est": ("Se espera más beneficio", "Se espera menos beneficio"),
    "batidas": ("Suele superar las previsiones", "Suele quedarse por debajo de las previsiones"),
    "margen_op_var": ("Margen operativo mejorando", "Margen operativo empeorando")}


# ---------------------------------------------------------------- cálculo principal
def calcular(R):
    C = Cuentas(R)
    mon = R.get("moneda") or ""
    diario = R["diario"]
    corte, P = diario[-1][0], float(diario[-1][1])
    D = {"ticker": R["ticker"], "nombre": R.get("nombre"), "moneda": mon, "bolsa": R.get("bolsa"),
         "sector": R.get("sector"), "industria": R.get("industria"), "corte": corte, "precio": P, "avisos": list(R.get("avisos_descarga") or [])}
    fin = (R.get("sector") or "") == "Financial Services" and any(w in (R.get("industria") or "") for w in ("Bank", "Insurance"))
    D["financiera"] = fin

    # cuentas: fecha de la información más reciente
    fechas_c = [s[-1][0] for s in (C.T.get("TotalRevenue"), C.Q.get("TotalRevenue"), C.A.get("TotalRevenue")) if s]
    D["fecha_cuentas"] = max(fechas_c) if fechas_c else None
    if D["fecha_cuentas"] and _dias(D["fecha_cuentas"], corte) > 400:
        D["avisos"].append(f"Yahoo no tiene cuentas posteriores al {D['fecha_cuentas']}. Las métricas de cuentas pueden estar desfasadas.")
    D["solo_anual"] = not C.Q.get("TotalRevenue")

    acciones = _f(R.get("acciones")) or C.ref
    mcap = P * acciones if acciones else None
    D["mcap"], D["acciones"] = mcap, acciones

    dv, deuda = C.balance("TotalDebt")
    dc, caja = C.balance("CashCashEquivalentsAndShortTermInvestments")
    deuda_neta = (deuda - (caja or 0)) if deuda is not None else None
    fd, ebitda, base_e = C.ttm("EBITDA")
    _, ebit, _ = C.ttm("EBIT")
    _, ventas, base_v = C.ttm("TotalRevenue")
    fo, ocf, _ = C.ttm("OperatingCashFlow")
    _, capex, _ = C.ttm("CapitalExpenditure")
    _, intereses, _ = C.ttm("InterestExpense")
    _, tasa, _ = C.ttm("TaxRateForCalcs")
    _, ni, _ = C.ttm("NetIncome")
    _, opinc, _ = C.ttm("OperatingIncome")
    db, patrimonio = C.balance("StockholdersEquity")
    _, activos = C.balance("TotalAssets")
    _, ac = C.balance("CurrentAssets")
    _, pc = C.balance("CurrentLiabilities")
    _, re_ = C.balance("RetainedEarnings")
    _, pasivo = C.balance("TotalLiabilitiesNetMinorityInterest")

    fcf, fcf_aviso = None, None
    if ocf is not None and capex is not None:
        if capex > 0:
            fcf_aviso = "Capex con signo positivo en Yahoo: dato incoherente"
        else:
            fcf = ocf + capex
            if fcf > ocf:
                fcf, fcf_aviso = None, "FCF mayor que el flujo operativo: dato incoherente"
    D["comp"] = {"deuda_total": deuda, "caja": caja, "deuda_neta": deuda_neta, "ebitda": ebitda, "ebit": ebit,
                 "ventas": ventas, "ocf": ocf, "capex": capex, "fcf": fcf, "intereses": intereses, "tasa": tasa,
                 "beneficio": ni, "patrimonio": patrimonio, "activos": activos, "activo_corriente": ac,
                 "pasivo_corriente": pc, "reservas": re_, "pasivo": pasivo, "mcap": mcap, "acciones": acciones,
                 "fecha_balance": db, "fecha_12m": fo, "base_12m": base_v}

    K = {}

    def tarjeta(id_, v, fuente_txt, fecha, avisos=None, gris=None, formula=None):
        av = list(avisos or [])
        if gris:
            K[id_] = {"id": id_, "valor": None, "color": "gris", "gris": gris, "avisos": av, "fuente": fuente_txt, "fecha": fecha, "formula": formula}
            return
        K[id_] = {"id": id_, "valor": v, "color": color(id_, v) if v is not None else "gris",
                  "gris": None if v is not None else "Sin dato", "avisos": av, "fuente": fuente_txt, "fecha": fecha, "formula": formula}

    cons = R.get("consenso") or {}
    na = cons.get("analistas")
    esc = [f"Consenso escaso ({na} analistas)"] if na is not None and na < 3 else []
    bpa_e = _f(cons.get("bpa_est"))
    tarjeta("per_fwd", P / bpa_e if bpa_e else None, f"{FUENTE}: precio / BPA estimado 12 meses ({es(bpa_e, 2)} {mon})", corte, esc,
            formula=f"{es(P, 2)} / {es(bpa_e, 2)}" if bpa_e else None)
    ev = mcap + deuda_neta if mcap is not None and deuda_neta is not None else None
    if ebitda is not None and ebitda <= 0 and ev is not None:
        tarjeta("ev_ebitda", None, FUENTE, fd, gris="EBITDA negativo: el ratio no tiene sentido")
    else:
        tarjeta("ev_ebitda", ev / ebitda if ev is not None and ebitda else None, f"Cálculo: (capitalización + deuda neta) / EBITDA {base_e}", fd)
    tarjeta("rent_fcf", fcf / mcap * 100 if fcf is not None and mcap else None, f"Cálculo: (flujo operativo − capex) / capitalización", fo,
            gris=fcf_aviso, formula=f"({millones(ocf, mon)} − {millones(abs(capex) if capex else None, mon)}) / {millones(mcap, mon)}" if fcf is not None else None)
    tarjeta("peg", None, FUENTE, corte, gris="Yahoo no publica el crecimiento estimado a 5 años")
    tarjeta("ps", mcap / ventas if mcap and ventas else None, f"Cálculo: capitalización / ventas {base_v}", fo)
    obj = _f(cons.get("objetivo"))
    tarjeta("potencial", (obj / P - 1) * 100 if obj else None, f"{FUENTE}: precio objetivo medio {es(obj, 2)} {mon}, {na or 'sin'} analistas", corte, esc,
            formula=f"({es(obj, 2)} − {es(P, 2)}) / {es(P, 2)}" if obj else None)

    caja_neta = deuda_neta is not None and deuda_neta < 0
    if caja_neta:
        K["dn_ebitda"] = {"id": "dn_ebitda", "valor": deuda_neta / ebitda if ebitda else None, "color": "verde", "gris": None,
                          "avisos": ["Caja neta"], "fuente": "Cálculo: deuda total − caja y equivalentes", "fecha": dv, "caja_neta": True,
                          "formula": f"{millones(deuda, mon)} − {millones(caja, mon)}"}
    elif ebitda is not None and ebitda <= 0 and deuda_neta is not None:
        K["dn_ebitda"] = {"id": "dn_ebitda", "valor": None, "color": "rojo", "gris": None, "avisos": ["EBITDA negativo con deuda neta: rojo por regla"],
                          "fuente": "Cálculo: deuda neta / EBITDA", "fecha": dv, "formula": None}
    else:
        tarjeta("dn_ebitda", deuda_neta / ebitda if deuda_neta is not None and ebitda else None,
                f"Cálculo: (deuda total − caja) / EBITDA {base_e}", dv,
                formula=f"({millones(deuda, mon)} − {millones(caja, mon)}) / {millones(ebitda, mon)}" if deuda_neta is not None and ebitda else None)
    liq = ac / pc if ac is not None and pc else None
    if liq is not None and not 0 <= liq <= 20:
        tarjeta("liquidez", None, FUENTE, db, gris=f"Valor descartado: {es(liq)} fuera de 0–20")
    else:
        tarjeta("liquidez", liq, "Cálculo: activo corriente / pasivo corriente", db)
    if intereses is None or intereses == 0:
        tarjeta("cobertura", None, FUENTE, fo, gris="Yahoo no publica gastos financieros")
    else:
        tarjeta("cobertura", ebit / abs(intereses) if ebit is not None else None, "Cálculo: EBIT / gastos financieros", fo)
    mf = fcf / ventas * 100 if fcf is not None and ventas else None
    if mf is not None and abs(mf) > 200:
        tarjeta("margen_fcf", None, FUENTE, fo, gris=f"Valor descartado: {es(mf)} % fuera de ±200 %")
    else:
        tarjeta("margen_fcf", mf, "Cálculo: FCF / ventas", fo, gris=fcf_aviso)
    roic, roic_g = None, None
    capital = patrimonio + deuda_neta if patrimonio is not None and deuda_neta is not None else None
    if ebit is not None and tasa is not None and capital:
        if not 0 <= tasa <= 0.6:
            roic_g = f"Tipo impositivo de Yahoo ({es(tasa * 100)} %) fuera de rango"
        elif capital <= 0:
            roic_g = "Capital invertido negativo"
        else:
            roic = ebit * (1 - tasa) / capital * 100
            if abs(roic) > 200:
                roic, roic_g = None, f"Valor descartado: {es(roic)} % fuera de ±200 %"
    tarjeta("roic", roic, "Cálculo: EBIT × (1 − tipo efectivo) / (patrimonio + deuda neta)", fo, gris=roic_g,
            formula=f"{millones(ebit, mon)} × (1 − {es(tasa * 100 if tasa is not None else None)} %) / ({millones(patrimonio, mon)} + {millones(deuda_neta, mon)})" if roic is not None else None)
    z = None
    if None not in (ac, pc, re_, ebit, mcap, ventas) and activos and pasivo:
        z = 1.2 * (ac - pc) / activos + 1.4 * re_ / activos + 3.3 * ebit / activos + 0.6 * mcap / pasivo + 1.0 * ventas / activos
    if z is not None and not -10 <= z <= 30:
        tarjeta("altman", None, FUENTE, db, gris=f"Valor descartado: {es(z)} fuera de −10 a 30")
    else:
        tarjeta("altman", z, "Cálculo: Altman Z original (5 ratios)", db)

    # crecimiento
    def crec(k):
        d1, v1, b = C.ttm(k)
        d0, v0 = C.ttm_previo(k) if b == "12 meses" else (None, None)
        if v0 is None:
            s = C.anual(k)
            if len(s) >= 2:
                (d0, v0), (d1, v1) = s[-2], s[-1]
                b = "último ejercicio"
        return (v1, v0, d1, b)
    v1, v0, dvt, bv = crec("TotalRevenue")
    g = (v1 / v0 - 1) * 100 if v1 is not None and v0 else None
    tarjeta("ventas_ia", g, f"Cálculo: ventas {bv} frente al año anterior", dvt, ["Base baja"] if g is not None and abs(g) > 300 else [],
            formula=f"({millones(v1, mon)} / {millones(v0, mon)} − 1) × 100" if g is not None else None)
    D["comp"]["ventas_previas"] = v0
    eps_t = C.T.get("DilutedEPS_aj") or []
    b1 = b0 = None
    if eps_t:
        d1, b1 = eps_t[-1]
        for d0, x in reversed(eps_t[:-1]):
            if 330 <= _dias(d0, d1) <= 400:
                b0 = x
                break
        fb, bb = d1, "12 meses"
    if b0 is None:
        ea = C.A.get("DilutedEPS_aj") or []
        if len(ea) >= 2:
            (_, b0), (fb, b1) = ea[-2], ea[-1]
            bb = "último ejercicio"
    gb, avb = None, []
    if b1 is not None and b0:
        gb = (b1 - b0) / abs(b0) * 100
        if b0 < 0:
            avb.append("Base negativa")
        if abs(gb) > 300:
            avb.append("Base baja")
    tarjeta("bpa_ia", gb, f"Cálculo: BPA diluido {bb if b0 is not None else ''} frente al año anterior", fb if b0 is not None else None, avb)
    va = C.anual("TotalRevenue")
    cg = ((va[-1][1] / va[-4][1]) ** (1 / 3) - 1) * 100 if len(va) >= 4 and va[-4][1] and va[-4][1] > 0 and va[-1][1] and va[-1][1] > 0 else None
    tarjeta("cagr3", cg, f"Cálculo: ventas anuales {va[-4][0][:4] if len(va) >= 4 else ''}–{va[-1][0][:4] if va else ''}", va[-1][0] if va else None)
    ce = _f(cons.get("crec_1y"))
    tarjeta("bpa_est", ce * 100 if ce is not None else None, f"{FUENTE}: crecimiento del BPA estimado para el ejercicio fiscal siguiente", corte,
            esc + (["Base baja"] if ce is not None and abs(ce) > 3 else []))
    bt = (R.get("batidas") or [])[-4:]
    tarjeta("batidas", sum(1 for _, e, a in bt if a > e) if len(bt) == 4 else None, f"{FUENTE}: BPA real frente al estimado", bt[-1][0] if bt else None,
            gris=None if len(bt) == 4 else "Yahoo no tiene las 4 últimas presentaciones")
    mo1 = mo0 = None
    d1, o1, bo = C.ttm("OperatingIncome")
    d0, o0 = C.ttm_previo("OperatingIncome") if bo == "12 meses" else (None, None)
    _, vv0 = C.ttm_previo("TotalRevenue") if bo == "12 meses" else (None, None)
    if o0 is None or not vv0:
        so, sv = C.anual("OperatingIncome"), C.anual("TotalRevenue")
        if len(so) >= 2 and len(sv) >= 2 and sv[-1][1] and sv[-2][1]:
            mo1, mo0, d1 = so[-1][1] / sv[-1][1] * 100, so[-2][1] / sv[-2][1] * 100, so[-1][0]
    elif o1 is not None and ventas:
        mo1, mo0 = o1 / ventas * 100, o0 / vv0 * 100
    D["margen_op"] = mo1
    if mo1 is not None and abs(mo1) > 200:
        tarjeta("margen_op_var", None, FUENTE, d1, gris="Valor descartado: margen operativo fuera de ±200 %")
    else:
        tarjeta("margen_op_var", mo1 - mo0 if mo1 is not None and mo0 is not None else None, "Cálculo: margen operativo frente al año anterior", d1)

    if fin:
        for k in NO_APLICA_FIN:
            K[k].update(valor=None, color="gris", gris="No aplica a bancos y aseguradoras")

    # nota (sección 5)
    puntos = {"verde": 100, "ambar": 50, "rojo": 0}
    notas, validas = {}, {}
    for b, _, _ in BLOQUES:
        vs = [puntos[K[i]["color"]] for i in ORDEN[b] if K[i]["color"] != "gris"]
        validas[b] = len(vs)
        notas[b] = round(sum(vs) / len(vs)) if vs else None
    activos_b = [(b, w) for b, _, w in BLOQUES if validas[b] >= 4]
    conf_baja = len(activos_b) < 3
    tw = sum(w for _, w in activos_b)
    nota = round(sum(notas[b] * w / tw for b, w in activos_b)) if activos_b else None
    riesgo = 100 - nota if nota is not None else None
    tramo = next((t for t in VEREDICTOS if riesgo is not None and riesgo <= t[0]), None)
    D.update(tarjetas=K, notas=notas, validas=validas, nota=nota, riesgo=riesgo, confianza_baja=conf_baja,
             tramo=tramo[1] if tramo else None, veredicto=tramo[2] if tramo else None,
             pesos={b: (w / tw if b in dict(activos_b) else 0) for b, _, w in BLOQUES} if tw else {})
    D["etiquetas"] = {b: etiqueta(notas[b]) if validas[b] >= 4 else None for b, _, _ in BLOQUES}

    for id_, k in K.items():
        k["nombre"] = NOMBRES[id_]
        k["umbral"] = UMBRAL_TXT[id_]
        k["por_que"] = POR_QUE[id_]
        k["unidad"] = UNIDAD.get(id_, "")
        k["frase"] = frase(id_, k["valor"], mon, k) if k["color"] != "gris" else None

    # lo esencial
    orden_total = [i for b in ("val", "sal", "cre") for i in ORDEN[b]]
    buenos = [i for i in orden_total if K[i]["color"] == "verde" and i in ESENCIAL][:3]
    malos = [i for i in orden_total if K[i]["color"] == "rojo" and i in ESENCIAL][:2]
    D["esencial"] = [{"ok": True, "texto": ESENCIAL[i][0], "id": i} for i in buenos] + [{"ok": False, "texto": ESENCIAL[i][1], "id": i} for i in malos]

    D["consenso"] = {"objetivo": obj, "analistas": na, "bpa_est": bpa_e, "escaso": bool(esc)}
    D["tecnicos"] = tecnicos(diario)
    D["serie"] = diario
    D["historia"] = historia_per(R, C, P)
    D["evolucion"] = evolucion(R)
    D["valor_justo"] = valor_justo(R, C, P, fcf, acciones, ni, cons)
    D["piotroski"] = piotroski(C)
    D["senales"] = senales(C, mon)
    D["tendencia"] = tendencia(C)
    bt_all = R.get("batidas") or []
    D["ultima"] = {"fecha": bt_all[-1][0], "est": bt_all[-1][1], "real": bt_all[-1][2]} if bt_all else None
    D["proximos"] = R.get("proximos_resultados")
    D["glosario"] = glosario(D)
    return D


def etiqueta(n):
    if n is None:
        return None
    return "Excelente" if n >= 75 else ("Buena" if n >= 50 else ("Aceptable" if n >= 25 else "Débil"))


# ---------------------------------------------------------------- ¿cara frente a su historia?
def historia_per(R, C, P):
    eps = [(d, v) for d, v in (C.A.get("DilutedEPS_aj") or []) if v is not None]
    if not eps:
        return {"ok": False, "motivo": "Yahoo no publica el beneficio por acción anual"}
    ult_ej = max((s[-1][0] for s in (C.A.get("TotalRevenue"), C.A.get("NetIncome")) if s), default=eps[-1][0])
    if eps[-1][0] < ult_ej:
        return {"ok": False, "motivo": f"Yahoo no publica el beneficio por acción del ejercicio {ult_ej[:4]}"}
    disp = [((_fecha(d) + dt.timedelta(days=90)).isoformat(), v, d) for d, v in eps]
    puntos = []
    for d, c, _ in (R.get("mensual") or [])[-48:]:
        e = [x for x in disp if x[0] <= d]
        if e and e[-1][1] > 0:
            puntos.append([d, round(c / e[-1][1], 2)])
    corte = R["diario"][-1][0]
    e = [x for x in disp if x[0] <= corte]
    if not e or e[-1][1] <= 0 or len(puntos) < 24:
        return {"ok": False, "motivo": "Menos de 24 meses con beneficio positivo publicado" if e and e[-1][1] > 0 else "Beneficio por acción del último ejercicio negativo o sin dato"}
    hoy = P / e[-1][1]
    vals = [v for _, v in puntos]
    med = stt.median(vals)
    dif = (hoy / med - 1) * 100
    txt = "más cara que de costumbre" if dif > 10 else ("más barata que de costumbre" if dif < -10 else "en línea con su historia")
    return {"ok": True, "hoy": hoy, "mediana": med, "min": min(vals + [hoy]), "max": max(vals + [hoy]), "dif": dif,
            "veredicto": txt, "serie": puntos, "bpa": e[-1][1], "ejercicio": e[-1][2], "desde": puntos[0][0]}


# ---------------------------------------------------------------- evolución y rentabilidad
def _hace(fecha, anos):
    f = _fecha(fecha)
    return f.replace(year=f.year - anos, day=28 if (f.month, f.day) == (2, 29) else f.day).isoformat()


def evolucion(R):
    m = R.get("mensual") or []
    d5 = R.get("diario5") or []
    if len(m) < 13:
        return None
    out = {"serie": m, "rent": {}, "base": "diaria" if d5 else "mensual"}
    for anos in (1, 3, 5):
        previos = []
        if d5:
            fin = d5[-1]
            obj = _hace(fin[0], anos)
            previos = [x for x in d5 if x[0] <= obj]
        if previos and (_fecha(obj) - _fecha(previos[-1][0])).days <= 7:
            ini = previos[-1]
        else:
            n = 12 * anos
            if len(m) <= n:
                continue
            ini, fin = m[-1 - n], m[-1]
        p = fin[1] / ini[1] - 1
        t = fin[2] / ini[2] - 1
        out["rent"][anos] = {"precio": p * 100, "total": t * 100, "desde": ini[0],
                             "anual_precio": ((1 + p) ** (1 / anos) - 1) * 100, "anual_total": ((1 + t) ** (1 / anos) - 1) * 100}
    if 1 not in out["rent"]:
        return None
    out["con_dividendos"] = bool(R.get("dividendos"))
    return out


# ---------------------------------------------------------------- valor justo orientativo (no puntúa)
def _dcf(f0, g, r):
    v, f = 0.0, f0
    for t in range(1, 11):
        f *= 1 + (g if t <= 5 else g / 2)
        v += f / (1 + r) ** t
    return v + f * (1 + PERPETUO) / (r - PERPETUO) / (1 + r) ** 10


def valor_justo(R, C, P, fcf, acciones, ni, cons):
    g0 = _f(cons.get("crec_1y"))
    g = None if g0 is None else min(max(g0, 0.0), TOPE_G)
    eps_t = C.T.get("DilutedEPS_aj") or C.A.get("DilutedEPS_aj") or []
    eps = eps_t[-1][1] if eps_t else None
    M = {"g": g, "g_yahoo": g0, "tasa": TASA, "perpetuo": PERPETUO}
    if eps is None or eps <= 0:
        M["graham"] = {"valor": None, "motivo": "Beneficio por acción negativo o sin dato"}
    elif g is None:
        M["graham"] = {"valor": None, "motivo": "Yahoo no publica crecimiento estimado"}
    else:
        v = eps * (8.5 + 2 * g * 100) * 4.4 / 4.4
        M["graham"] = {"valor": v, "dist": (v / P - 1) * 100, "eps": eps}
    fps = fcf / acciones if fcf is not None and acciones else None
    if fps is None or fps <= 0:
        M["dcf"] = {"valor": None, "motivo": "Flujo de caja libre negativo o sin dato"}
    elif g is None:
        M["dcf"] = {"valor": None, "motivo": "Yahoo no publica crecimiento estimado"}
    else:
        v = _dcf(fps, g, TASA)
        M["dcf"] = {"valor": v, "dist": (v / P - 1) * 100, "bajo": _dcf(fps, g, TASA_ALTA), "alto": _dcf(fps, g, TASA_BAJA), "fcf_accion": fps}
    corte = _fecha(R["diario"][-1][0])
    dpa = sum(a for d, a in (R.get("dividendos") or []) if (corte - _fecha(d)).days <= 365)
    _, pagados, _ = C.ttm("CashDividendsPaid")
    payout = abs(pagados) / ni if pagados is not None and ni and ni > 0 else None
    if not dpa:
        M["dividendos"] = {"valor": None, "motivo": "No paga dividendo"}
    elif payout is None or payout < 0.2:
        M["dividendos"] = {"valor": None, "motivo": f"Reparte menos del 20 % del beneficio ({es(payout * 100 if payout is not None else None)} %)"}
    else:
        f = lambda r: dpa * (1 + PERPETUO) / (r - PERPETUO)
        v = f(TASA)
        M["dividendos"] = {"valor": v, "dist": (v / P - 1) * 100, "bajo": f(TASA_ALTA), "alto": f(TASA_BAJA), "dpa": dpa, "payout": payout * 100}
    return M


# ---------------------------------------------------------------- Piotroski F
def piotroski(C):
    def a(k):
        return {d: v for d, v in C.anual(k)}
    NI, TA, OCF, LTD, CA, CL, GP, REV = (a(k) for k in ("NetIncome", "TotalAssets", "OperatingCashFlow", "LongTermDebt",
                                                         "CurrentAssets", "CurrentLiabilities", "GrossProfit", "TotalRevenue"))
    SH = {d: v for d, v, _ in (C.A.get("OrdinarySharesNumber_aj") or [])}
    anos = sorted(TA)
    if len(anos) < 3:
        return None
    y0, y1, y2 = anos[-1], anos[-2], anos[-3]
    pruebas = []

    def p(nombre, cond):
        pruebas.append({"nombre": nombre, "ok": cond})
    roa0 = NI.get(y0) / TA[y1] if NI.get(y0) is not None and TA.get(y1) else None
    roa1 = NI.get(y1) / TA[y2] if NI.get(y1) is not None and TA.get(y2) else None
    p("Beneficio positivo", None if roa0 is None else roa0 > 0)
    p("Flujo operativo positivo", None if OCF.get(y0) is None else OCF[y0] > 0)
    p("Rentabilidad sobre activos mejora", None if roa0 is None or roa1 is None else roa0 > roa1)
    p("Caja operativa mayor que el beneficio", None if OCF.get(y0) is None or NI.get(y0) is None else OCF[y0] > NI[y0])
    l0 = LTD.get(y0) / TA[y0] if LTD.get(y0) is not None and TA.get(y0) else None
    l1 = LTD.get(y1) / TA[y1] if LTD.get(y1) is not None and TA.get(y1) else None
    p("Menos deuda a largo plazo", None if l0 is None or l1 is None else l0 < l1)
    c0 = CA.get(y0) / CL[y0] if CA.get(y0) is not None and CL.get(y0) else None
    c1 = CA.get(y1) / CL[y1] if CA.get(y1) is not None and CL.get(y1) else None
    p("Mejor liquidez corriente", None if c0 is None or c1 is None else c0 > c1)
    p("No ha emitido acciones", None if SH.get(y0) is None or SH.get(y1) is None else SH[y0] <= SH[y1])
    m0 = GP.get(y0) / REV[y0] if GP.get(y0) is not None and REV.get(y0) else None
    m1 = GP.get(y1) / REV[y1] if GP.get(y1) is not None and REV.get(y1) else None
    p("Mejor margen bruto", None if m0 is None or m1 is None else m0 > m1)
    t0 = REV.get(y0) / TA[y1] if REV.get(y0) is not None and TA.get(y1) else None
    t1 = REV.get(y1) / TA[y2] if REV.get(y1) is not None and TA.get(y2) else None
    p("Mejor rotación de activos", None if t0 is None or t1 is None else t0 > t1)
    ev = [x for x in pruebas if x["ok"] is not None]
    pts = sum(1 for x in ev if x["ok"])
    et = None
    if len(ev) == 9:
        et = "Fuerte" if pts >= 7 else ("Media" if pts >= 4 else "Débil")
    return {"puntos": pts, "evaluables": len(ev), "etiqueta": et, "pruebas": pruebas, "ejercicio": y0[:4], "anterior": y1[:4]}


# ---------------------------------------------------------------- lo que dicen sus cuentas
def senales(C, mon):
    S = []
    NI = [(d, v) for d, v in C.anual("NetIncome") if v is not None]
    if len(NI) >= 2:
        n, neg = len(NI), sum(1 for _, v in NI if v < 0)
        a, b = NI[0][0][:4], NI[-1][0][:4]
        if neg == 0:
            S.append(("favor", f"Ha ganado dinero los {n} últimos ejercicios ({a}-{b})",
                      "Una empresa que gana dinero de forma constante depende menos de pedir prestado o de ampliar capital."))
        else:
            S.append(("contra", f"Ha perdido dinero en {neg} de los {n} últimos ejercicios ({a}-{b})",
                      "Las pérdidas repetidas consumen patrimonio y pueden obligar a endeudarse o a emitir acciones."))
    E = [(d, v) for d, v in (C.A.get("DilutedEPS_aj") or []) if v is not None]
    if len(E) >= 3 and E[0][1] > 0 and E[-1][1] > 0:
        n = len(E) - 1
        g = ((E[-1][1] / E[0][1]) ** (1 / n) - 1) * 100
        S.append(("favor" if g > 0 else "contra", f"Su beneficio por acción {'crece' if g > 0 else 'cae'} un {es(abs(g))} % al año ({E[0][0][:4]}-{E[-1][0][:4]})",
                  "El beneficio por acción es lo que corresponde a cada accionista; si crece, cada acción vale más a largo plazo."))
    OCF = {d: v for d, v in C.anual("OperatingCashFlow") if v is not None}
    NId = dict(NI)
    comunes = [d for d in OCF if d in NId]
    if len(comunes) >= 2 and sum(NId[d] for d in comunes) > 0:
        r = sum(OCF[d] for d in comunes) / sum(NId[d] for d in comunes)
        tipo = "favor" if r >= 1 else ("contra" if r < 0.8 else "contexto")
        txt = (f"Su caja de las operaciones es negativa en conjunto aunque declara beneficio ({len(comunes)} años)" if r < 0 else
               f"Su caja de las operaciones {'supera' if r >= 1 else 'no llega a'} su beneficio ({es(r)} veces en {len(comunes)} años)")
        S.append((tipo, txt,
                  "Si la caja que entra es menor que el beneficio contable, parte de ese beneficio puede no convertirse en dinero."))
    CX = {d: v for d, v in C.anual("CapitalExpenditure") if v is not None}
    F = [(d, OCF[d] + CX[d]) for d in sorted(OCF) if d in CX]
    if len(F) >= 2:
        neg = sum(1 for _, v in F if v < 0)
        S.append(("favor" if neg == 0 else "contra",
                  f"Flujo de caja libre positivo los {len(F)} últimos años" if neg == 0 else f"Flujo de caja libre negativo en {neg} de los {len(F)} últimos años",
                  "El flujo de caja libre es el dinero que queda tras invertir en el negocio; con él se pagan dividendos, recompras o deuda."))
    SH = [(d, v) for d, v, _ in (C.A.get("OrdinarySharesNumber_aj") or []) if v]
    if len(SH) >= 2:
        c = (SH[-1][1] / SH[0][1] - 1) * 100
        rng = f"({SH[0][0][:4]}-{SH[-1][0][:4]})"
        if c <= -1:
            S.append(("favor", f"Ha reducido sus acciones un {es(abs(c))} % {rng}: recompras",
                      "Con menos acciones, cada una se queda con una parte mayor del beneficio."))
        elif c >= 3:
            S.append(("contra", f"Ha aumentado sus acciones un {es(c)} % {rng}: dilución",
                      "Si hay más acciones, el beneficio se reparte entre más accionistas y cada uno recibe menos."))
        else:
            S.append(("contexto", f"Número de acciones estable {rng}", "Ni recompra ni diluye de forma significativa."))
    TD = {d: v for d, v in C.anual("TotalDebt") if v is not None}
    CJ = {d: v for d, v in C.anual("CashCashEquivalentsAndShortTermInvestments") if v is not None}
    DN = [(d, TD[d] - CJ.get(d, 0)) for d in sorted(TD)]
    if len(DN) >= 2:
        a, b = DN[0][1], DN[-1][1]
        if b < 0:
            S.append(("favor", f"Tiene más caja que deuda ({millones(-b, mon)} de caja neta en {DN[-1][0][:4]})",
                      "La caja neta protege en épocas malas y da libertad para invertir o remunerar al accionista."))
        elif b < a:
            S.append(("favor", f"Ha reducido su deuda neta de {millones(a, mon)} a {millones(b, mon)} ({DN[0][0][:4]}-{DN[-1][0][:4]})",
                      "Menos deuda reduce el pago de intereses y el riesgo si el negocio se complica."))
        elif a > 0 and b > a * 1.2:
            S.append(("contra", f"Su deuda neta ha subido un {es((b / a - 1) * 100)} % ({DN[0][0][:4]}-{DN[-1][0][:4]})",
                      "Más deuda aumenta los intereses a pagar y el riesgo si el negocio se complica."))
        else:
            S.append(("contexto", f"Deuda neta estable ({millones(b, mon)} en {DN[-1][0][:4]})", "La deuda no ha cambiado de forma relevante."))
    V = [(d, v) for d, v in C.anual("TotalRevenue") if v]
    if len(V) >= 2 and V[0][1] > 0:
        n = len(V) - 1
        g = ((V[-1][1] / V[0][1]) ** (1 / n) - 1) * 100
        S.append(("contexto", f"Ventas: {es(g, signo=True)} % al año ({V[0][0][:4]}-{V[-1][0][:4]})",
                  "El ritmo de ventas ayuda a entender si el beneficio crece por el negocio o por recortes de costes."))
    RD = {d: v for d, v in C.anual("ResearchAndDevelopment") if v}
    if V and V[-1][0] in RD:
        S.append(("contexto", f"Dedica un {es(RD[V[-1][0]] / V[-1][1] * 100)} % de sus ventas a I+D ({V[-1][0][:4]})",
                  "La inversión en I+D reduce el beneficio de hoy, pero puede sostener las ventas futuras."))
    DV = [v for _, v in C.anual("CashDividendsPaid") if v is not None]
    if len(DV) >= 2 and all(v < 0 for v in DV):
        S.append(("contexto", f"Ha pagado dividendo los {len(DV)} últimos ejercicios",
                  "Un dividendo constante indica que la empresa genera caja de forma regular."))
    return [{"tipo": t, "texto": x, "por_que": p} for t, x, p in S]


# ---------------------------------------------------------------- tendencia de 5 periodos
def tendencia(C):
    D = C.Q if C.Q.get("TotalRevenue") else C.A
    fuente = "trimestres" if D is C.Q else "ejercicios anuales"
    fechas = [d for d, _ in (D.get("TotalRevenue") or [])][-5:]
    def m(k):
        return {d: _f(v) for d, v in (D.get(k) or [])}
    V, OI, OCF, CX = m("TotalRevenue"), m("OperatingIncome"), m("OperatingCashFlow"), m("CapitalExpenditure")
    E = {d: v for d, v in (D.get("DilutedEPS_aj") or [])}
    filas = []
    for d in fechas:
        filas.append({"fecha": d, "ventas": V.get(d), "bpa": E.get(d),
                      "margen_op": OI[d] / V[d] * 100 if OI.get(d) is not None and V.get(d) else None,
                      "fcf": OCF[d] + CX[d] if OCF.get(d) is not None and CX.get(d) is not None else None})
    return {"periodo": fuente, "filas": filas}


# ---------------------------------------------------------------- glosario (página 4 de la v2.1)
GLOS = [("per_fwd", "PER forward", "Cuántas veces paga el precio el beneficio por acción estimado para los próximos 12 meses.", "Precio / BPA estimado"),
        ("rent_fcf", "Rentabilidad FCF", "El flujo de caja libre de 12 meses en relación con el valor en bolsa.", "(Flujo de caja operativo − capex) / capitalización"),
        ("potencial", "Potencial", "Distancia entre el cierre y el precio objetivo medio de los analistas.", "(Precio objetivo − precio) / precio"),
        ("dn_ebitda", "Deuda neta/EBITDA", "Cuántos años de EBITDA harían falta para pagar la deuda neta.", "Deuda neta / EBITDA 12 meses"),
        ("roic", "ROIC", "Beneficio operativo después de impuestos por cada unidad de capital invertido, sea propio o de deuda.",
         "EBIT × (1 − tipo impositivo efectivo) / (patrimonio neto + deuda neta)"),
        ("ventas_ia", "Ventas interanual", "Cambio de las ventas de 12 meses frente a los 12 meses anteriores.", "(Ventas 12 meses / ventas 12 meses anteriores − 1) × 100")]
LIMITES = {"per_fwd": ("menor", 15, 25), "rent_fcf": ("mayor", 5, 2), "potencial": ("mayor", 15, 0), "dn_ebitda": ("menor", 1.5, 3),
           "roic": ("mayor", 15, 8), "ventas_ia": ("mayor", 10, 0)}


def glosario(D):
    K, c, mon, emp = D["tarjetas"], D["comp"], D["moneda"], D["nombre"]
    out = []
    for id_, nom, que, form in GLOS:
        k = K[id_]
        v = k["valor"]
        if k["color"] == "gris" or (v is None and not k.get("caja_neta")):
            out.append({"id": id_, "nombre": nom, "que": que, "formula": form, "con_cifras": None,
                        "lectura": k.get("gris") if k.get("gris") and k["gris"] != "Sin dato" else "Sin dato: ninguna fuente lo publica a la fecha de corte."})
            continue
        if id_ == "per_fwd":
            lec = f"{emp} cotiza a {es(v)} veces el beneficio estimado." if v >= 0 else "El BPA estimado es negativo: se prevén pérdidas. Está en rojo por regla."
        elif id_ == "rent_fcf":
            lec = f"Por cada 100 de capitalización, {emp} generó {es(v)} de flujo de caja libre en 12 meses."
        elif id_ == "potencial":
            lec = (f"El precio objetivo medio ({es(D['consenso']['objetivo'], 2)} {mon}) está un {es(abs(v))} % por "
                   f"{'encima' if v >= 0 else 'debajo'} del cierre, según Yahoo Finance ({D['consenso']['analistas']} analistas).")
        elif id_ == "dn_ebitda":
            lec = (f"{emp} tiene más caja que deuda ({millones(-c['deuda_neta'], mon)}). Está en verde por regla." if k.get("caja_neta")
                   else f"La deuda neta de {emp} equivale a {es(v)} veces su EBITDA anual.")
        elif id_ == "roic":
            lec = f"Por cada 100 de capital invertido, {emp} obtuvo {es(v)} de beneficio operativo después de impuestos."
        else:
            lec = f"Las ventas de los últimos 12 meses son un {es(abs(v))} % {'mayores' if v >= 0 else 'menores'} que las del año anterior."
        if not (id_ == "per_fwd" and v < 0) and not k.get("caja_neta"):
            sentido, g, r = LIMITES[id_]
            col = k["color"]
            unidad = " %" if id_ in ("rent_fcf", "potencial", "roic", "ventas_ia") else ""
            if col == "verde":
                lec += f" Está en verde porque es {'menor' if sentido == 'menor' else 'mayor'} que {es(g)}{unidad}."
            elif col == "rojo":
                lec += f" Está en rojo porque es {'mayor' if sentido == 'menor' else 'menor'} que {es(r)}{unidad}."
            else:
                lo, hi = sorted((g, r))
                lec += f" Está en ámbar porque está entre {es(lo)}{unidad} y {es(hi)}{unidad}."
        out.append({"id": id_, "nombre": nom, "que": que, "formula": form, "con_cifras": k.get("formula"), "lectura": lec})
    return out
