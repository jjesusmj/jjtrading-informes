# =====================================================================
#  JJTrading_ — motor del informe de plan de operación (solo largos)
#  Mismo método que el cuaderno de Colab. Reglas calibradas con 162 acciones,
#  diario 2006-2026. No cambiar parámetros sin recalibrar.
# =====================================================================
import warnings, math, html
import numpy as np, pandas as pd, yfinance as yf
from datetime import datetime
warnings.filterwarnings("ignore")
try:
    from numba import njit
except ImportError:
    def njit(f=None, **k):
        return f if f is not None else (lambda g: g)

# ---------------- Parámetros del método (no tocar sin recalibrar) ----------------
ATR_LEN        = 14
OB_MAX_ATR     = 3.0    # OB alcista válido si su techo está a ≤ 3 ATR bajo el precio
ZONA_ATR       = 0.25   # la zona de entrada sube 0,25 ATR sobre el soporte
STOP_OB_ATR    = 1.0    # stop: 1 ATR bajo el suelo del OB
STOP_SOP_ATR   = 1.5    # stop: 1,5 ATR bajo otros soportes
STOP_MIN_PCT   = 2.0    # stop mínimo: 2 % bajo la entrada
STOP_SWING_ATR = 1.0    # si hay un mínimo swing entre entrada y stop, stop ≥ 1 ATR bajo él
OBJ1_R, OBJ2_R = 2.0, 3.0
ESPERA_ATR     = 2.0    # a más de 2 ATR de la zona → "esperar retroceso"
PLAZO_SES      = 60
AVISO_STOP_PCT = 8.0
PIVOT_R        = 10     # mínimos/máximos swing: 10 velas a cada lado

# ---------------- Funciones de indicadores (mismas que en la calibración) ----------------
@njit(cache=True)
def _seeded(x, n, alpha):
    out = np.full(x.shape[0], np.nan); f = -1
    for i in range(x.shape[0]):
        if not np.isnan(x[i]): f = i; break
    if f < 0 or f + n > x.shape[0]: return out
    s = f + n - 1; acc = 0.0
    for i in range(f, s + 1): acc += x[i]
    out[s] = acc / n
    for i in range(s + 1, x.shape[0]):
        out[i] = out[i-1] if np.isnan(x[i]) else alpha * x[i] + (1 - alpha) * out[i-1]
    return out
def ema(x, n): return _seeded(np.asarray(x, float), n, 2.0 / (n + 1))
def rma(x, n): return _seeded(np.asarray(x, float), n, 1.0 / n)
def shift(x, k=1):
    out = np.full(len(x), np.nan); out[k:] = x[:-k]; return out
def true_range(h, l, c):
    c1 = shift(c); tr = np.maximum(h - l, np.maximum(np.abs(h - c1), np.abs(l - c1))); tr[0] = h[0] - l[0]; return tr

@njit(cache=True)
def supertrend(h, l, c, atr, mult):
    N = c.shape[0]; up = np.full(N, np.nan); dn = np.full(N, np.nan); tr = np.ones(N, np.int64)
    for t in range(N):
        prev = tr[t-1] if t > 0 else 1
        if np.isnan(atr[t]): tr[t] = prev; continue
        hl2 = (h[t] + l[t]) / 2; u = hl2 - mult * atr[t]; d = hl2 + mult * atr[t]
        u1 = up[t-1] if (t > 0 and not np.isnan(up[t-1])) else u
        d1 = dn[t-1] if (t > 0 and not np.isnan(dn[t-1])) else d
        if t > 0 and c[t-1] > u1: u = max(u, u1)
        if t > 0 and c[t-1] < d1: d = min(d, d1)
        up[t] = u; dn[t] = d; cur = prev
        if prev == -1 and c[t] > d1: cur = 1
        elif prev == 1 and c[t] < u1: cur = -1
        tr[t] = cur
    return tr, up, dn

@njit(cache=True)
def leg_changes(h, l, sz):
    N = h.shape[0]; ch = np.zeros(N, np.int64); cur = 0; prev = 0
    for t in range(N):
        if t >= sz:
            hh = -1e300; ll = 1e300
            for j in range(t - sz + 1, t + 1):
                if h[j] > hh: hh = h[j]
                if l[j] < ll: ll = l[j]
            if h[t - sz] > hh: cur = 0
            elif l[t - sz] < ll: cur = 1
        if t > 0: ch[t] = cur - prev
        prev = cur
    return ch

@njit(cache=True)
def smc(h, l, c, phi, plo, sw_ch, in_ch, isz, ssz):
    """Estructura interna LuxAlgo. Devuelve CHoCH alcistas y la lista FINAL de OB activos (techo, suelo, sesgo)."""
    N = c.shape[0]; choch = np.zeros(N, np.bool_)
    swH = np.nan; swL = np.nan; inH = np.nan; inL = np.nan
    inHi = -1; inLi = -1; inHx = False; inLx = False; bias = 0; prevH = np.nan; prevL = np.nan
    cap = 100; oH = np.zeros(cap); oL = np.zeros(cap); oB = np.zeros(cap, np.int64); n = 0
    for t in range(N):
        if sw_ch[t] == 1: swL = l[t - ssz]
        elif sw_ch[t] == -1: swH = h[t - ssz]
        if in_ch[t] == 1: inL = l[t - isz]; inLi = t - isz; inLx = False
        elif in_ch[t] == -1: inH = h[t - isz]; inHi = t - isz; inHx = False
        if (t > 0 and not np.isnan(inH) and not np.isnan(prevH) and c[t] > inH and c[t-1] <= prevH
                and not inHx and not np.isnan(swH) and inH != swH):
            if bias == -1: choch[t] = True
            inHx = True; bias = 1; idx = inHi; mv = plo[inHi]
            for j in range(inHi, t):
                if plo[j] < mv: mv = plo[j]; idx = j
            if n >= cap: n = cap - 1
            for j in range(n, 0, -1): oH[j] = oH[j-1]; oL[j] = oL[j-1]; oB[j] = oB[j-1]
            oH[0] = phi[idx]; oL[0] = plo[idx]; oB[0] = 1; n += 1
        if (t > 0 and not np.isnan(inL) and not np.isnan(prevL) and c[t] < inL and c[t-1] >= prevL
                and not inLx and not np.isnan(swL) and inL != swL):
            inLx = True; bias = -1; idx = inLi; mv = phi[inLi]
            for j in range(inLi, t):
                if phi[j] > mv: mv = phi[j]; idx = j
            if n >= cap: n = cap - 1
            for j in range(n, 0, -1): oH[j] = oH[j-1]; oL[j] = oL[j-1]; oB[j] = oB[j-1]
            oH[0] = phi[idx]; oL[0] = plo[idx]; oB[0] = -1; n += 1
        m = 0
        for j in range(n):
            if not ((oB[j] == -1 and h[t] > oH[j]) or (oB[j] == 1 and l[t] < oL[j])):
                oH[m] = oH[j]; oL[m] = oL[j]; oB[m] = oB[j]; m += 1
        n = m; prevH = inH; prevL = inL
    return choch, oH[:n].copy(), oL[:n].copy(), oB[:n].copy()

def pivotes(h, l, R):
    """Máximos y mínimos swing confirmados (R velas a cada lado): lista de (índice, precio)."""
    altos, bajos = [], []
    for p in range(R, len(h) - R):
        if h[p] == h[p-R:p+R+1].max() and (h[p-R:p+R+1] == h[p]).sum() == 1: altos.append((p, h[p]))
        if l[p] == l[p-R:p+R+1].min() and (l[p-R:p+R+1] == l[p]).sum() == 1: bajos.append((p, l[p]))
    return altos, bajos

def poc_volume_profile(h, l, v, lookback=200, nbins=300):
    """Réplica del Volume Profile de tu script (reparto del volumen entre los niveles que toca cada vela)."""
    h, l, v = h[-lookback:], l[-lookback:], v[-lookback:]
    hh, ll = h.max(), l.min(); step = (hh - ll) / nbins
    P = ll + step * np.arange(1, nbins + 1)
    vol = np.zeros(nbins)
    for i in range(len(h)):
        m = (l[i] < P) & (h[i] > P); k = m.sum()
        if k: vol[m] += v[i] / k
    return P[vol.argmax()]


# ---------------- Bolsas ----------------
SUFIJOS = {"EEUU": "", "USA": "", "NYSE": "", "NASDAQ": "",
           "MADRID": ".MC", "ESPAÑA": ".MC", "BME": ".MC", "IBEX": ".MC",
           "PARIS": ".PA", "FRANCFORT": ".DE", "XETRA": ".DE", "ALEMANIA": ".DE",
           "AMSTERDAM": ".AS", "MILAN": ".MI", "LONDRES": ".L", "LISBOA": ".LS",
           "SUIZA": ".SW", "BRUSELAS": ".BR", "TORONTO": ".TO"}
BOLSAS = ["EEUU", "MADRID", "PARIS", "FRANCFORT", "AMSTERDAM", "MILAN", "LONDRES", "LISBOA", "SUIZA", "BRUSELAS", "TORONTO"]

class ErrorInforme(Exception):
    pass

def ticker_yahoo(ticker, bolsa):
    b = bolsa.strip().upper().replace("Á", "A").replace("Í", "I")
    if b not in SUFIJOS:
        raise ErrorInforme(f"Bolsa '{bolsa}' no reconocida")
    t = ticker.strip().upper()
    if not t:
        raise ErrorInforme("Falta el ticker")
    return t.replace(".", "-") if SUFIJOS[b] == "" else t.split(".")[0] + SUFIJOS[b]


def generar(ticker, bolsa="EEUU"):
    """Devuelve dict con: ticker, html, resumen (niveles del plan)."""
    TICKER = ticker_yahoo(ticker, bolsa)
    # ---------------- Datos ----------------
    tk = yf.Ticker(TICKER)
    D = tk.history(period="5y", interval="1d", auto_adjust=True).dropna(subset=["Close"])
    H1 = tk.history(period="60d", interval="1h", prepost=False).dropna(subset=["Close"])
    if len(D) < 260: raise ErrorInforme(f"{TICKER}: Yahoo no devuelve datos suficientes (¿ticker o bolsa incorrectos?)")
    info = {}
    try: info = tk.info or {}
    except Exception: pass

    o, h, l, c, v = (D[k].values.astype(float) for k in ("Open", "High", "Low", "Close", "Volume"))
    fechas = D.index
    tr = true_range(h, l, c); atr = rma(tr, ATR_LEN)[-1]; atr200 = rma(tr, 200)
    P = c[-1]; P_ant = c[-2]
    e21, e55, e200 = ema(c, 21)[-1], ema(c, 55)[-1], ema(c, 200)[-1]
    st, stUp, stDn = supertrend(h, l, c, rma(tr, 10), 3.0)
    hv = np.where(np.isnan(atr200), False, (h - l) >= 2 * np.nan_to_num(atr200, nan=1e300))
    phi = np.where(hv, l, h); plo = np.where(hv, h, l)
    chochD, obT, obS, obB = smc(h, l, c, phi, plo, leg_changes(h, l, 50), leg_changes(h, l, 5), 5, 50)
    obT, obS, obB = obT[:5], obS[:5], obB[:5]          # los 5 más recientes, como en tu indicador
    altos, bajos = pivotes(h, l, PIVOT_R)
    poc = poc_volume_profile(h, l, v)
    max52 = h[-252:].max(); min52 = l[-252:].min()

    # ---------------- Tendencia diaria ----------------
    if P > e200 and st[-1] == 1:   tendencia = ("Alcista", "Precio sobre la EMA 200 y SuperTrend diario alcista")
    elif P < e200 and st[-1] == -1: tendencia = ("Bajista", "Precio bajo la EMA 200 y SuperTrend diario bajista")
    else:                           tendencia = ("Mixta", f"Precio {'sobre' if P > e200 else 'bajo'} la EMA 200 y SuperTrend diario {'alcista' if st[-1] == 1 else 'bajista'}")

    # ---------------- Mapa de niveles ----------------
    niveles = []
    for t_, s_, b_ in zip(obT, obS, obB):
        if b_ == 1: niveles.append(("Order Block alcista", t_, s_, "soporte"))
        else:       niveles.append(("Order Block bajista", s_, t_, "resistencia"))
    niveles += [("EMA 55", e55, None, "soporte" if e55 < P else "resistencia"),
                ("EMA 200", e200, None, "soporte" if e200 < P else "resistencia"),
                ("POC (Volume Profile 200)", poc, None, "soporte" if poc < P else "resistencia")]
    if st[-1] == 1: niveles.append(("Línea SuperTrend", stUp[-1], None, "soporte"))
    for i, p in [b for b in bajos if b[0] >= len(c) - 250][-3:]: niveles.append((f"Mínimo swing {fechas[i]:%d/%m/%y}", p, None, "soporte" if p < P else "resistencia"))
    for i, p in [a for a in altos if a[0] >= len(c) - 250][-4:]: niveles.append((f"Máximo swing {fechas[i]:%d/%m/%y}", p, None, "resistencia" if p > P else "soporte"))
    niveles.append(("Máximo 52 semanas", max52, None, "resistencia"))

    # ---------------- Plan ----------------
    obs_validos = [(t_, s_) for t_, s_, b_ in zip(obT, obS, obB) if b_ == 1 and s_ < P and (P - t_) <= OB_MAX_ATR * atr]
    if obs_validos:
        techo, suelo = max(obs_validos, key=lambda x: x[0])
        soporte_nombre, soporte = "Order Block alcista", min(techo, P)
        stop = suelo - STOP_OB_ATR * atr; regla_stop = f"{STOP_OB_ATR:g} ATR bajo el suelo del Order Block ({suelo:.2f})".replace(".", ",")
    else:
        cands = [("EMA 55", e55), ("EMA 200", e200), ("POC", poc)] + ([("Línea SuperTrend", stUp[-1])] if st[-1] == 1 else [])
        cands = [x for x in cands if x[1] < P]
        if cands:
            soporte_nombre, soporte = max(cands, key=lambda x: x[1])
        else:
            soporte_nombre, soporte = "Mínimo 52 semanas (sin soportes por debajo)", min52
        stop = soporte - STOP_SOP_ATR * atr; regla_stop = f"{STOP_SOP_ATR:g} ATR bajo el soporte".replace(".", ",")
    zona_baja, zona_alta = soporte, soporte + ZONA_ATR * atr
    entrada = min(zona_alta, P)                          # referencia: techo de la zona (o el precio si ya está dentro)
    # mínimo swing entre stop y entrada → stop por debajo de él
    sw = [p for i, p in bajos if i >= len(c) - 250 and stop < p < entrada]
    if sw:
        stop = min(stop, min(sw) - STOP_SWING_ATR * atr); regla_stop += f"; bajado bajo el mínimo swing {min(sw):.2f}".replace(".", ",")
    if (entrada - stop) / entrada * 100 < STOP_MIN_PCT:
        stop = entrada * (1 - STOP_MIN_PCT / 100); regla_stop += f"; ampliado al mínimo del {STOP_MIN_PCT:g} %"
    R = entrada - stop
    res_arriba = sorted({round(x[1], 4) for x in niveles if x[3] == "resistencia" and x[1] > entrada})
    def objetivo(mult):
        base = entrada + mult * R; r = [x for x in res_arriba if x >= base]
        return (r[0], "resistencia") if r else (base, f"{mult:g}R")
    obj1, origen1 = objetivo(OBJ1_R)
    obj2, origen2 = objetivo(OBJ2_R)
    if obj2 <= obj1: obj2, origen2 = obj1 + R, "obj. 1 + 1R"
    riesgo_pct = R / entrada * 100; ratio = (obj1 - entrada) / R
    if P <= zona_alta and P >= stop: estado = ("En zona", "El precio está dentro de la zona de entrada")
    elif P < stop:                   estado = ("Invalidado", "El precio está por debajo del stop: plan no válido")
    elif P - zona_alta > ESPERA_ATR * atr: estado = ("Esperar retroceso", f"El precio está a {(P - zona_alta)/atr:.1f} ATR de la zona".replace(".", ","))
    else:                            estado = ("Cerca", f"El precio está a {(P - zona_alta)/atr:.1f} ATR de la zona".replace(".", ","))

    # ---------------- Confirmación 1H ----------------
    conf = []
    if len(H1) > 100:
        h1, l1, c1 = (H1[k].values.astype(float) for k in ("High", "Low", "Close"))
        tr1 = true_range(h1, l1, c1); st1, _, _ = supertrend(h1, l1, c1, rma(tr1, 10), 3.0)
        a2001 = rma(tr1, 200); hv1 = np.where(np.isnan(a2001), False, (h1 - l1) >= 2 * np.nan_to_num(a2001, nan=1e300))
        ch1, *_ = smc(h1, l1, c1, np.where(hv1, l1, h1), np.where(hv1, h1, l1), leg_changes(h1, l1, 50), leg_changes(h1, l1, 5), 5, 50)
        m1 = ema(c1, 12) - ema(c1, 26); s1 = ema(m1, 9)
        macd_up = (m1 > s1) & (shift(m1) <= shift(s1))
        st_buy = (st1 == 1) & (np.r_[1, st1[:-1]] == -1)
        def ultimo(mask):
            idx = np.where(mask)[0]
            if len(idx) == 0: return "sin señal en 60 días"
            i = idx[-1]; hace = len(c1) - 1 - i
            return f"{H1.index[i].tz_convert('Europe/Madrid'):%d/%m %H:%M} (hace {hace} velas)"
        conf = [("SuperTrend 1H", "Alcista" if st1[-1] == 1 else "Bajista", "último giro alcista: " + ultimo(st_buy)),
                ("CHoCH alcista 1H", "—", "último: " + ultimo(ch1)),
                ("Cruce MACD 1H", "Línea sobre señal" if m1[-1] > s1[-1] else "Línea bajo señal", "último cruce al alza: " + ultimo(macd_up))]

    # ---------------- Resultados trimestrales ----------------
    proximos = None
    try:
        cal = tk.calendar
        ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if ed: proximos = pd.Timestamp(ed[0] if isinstance(ed, (list, tuple)) else ed)
    except Exception:
        pass

    # ---------------- Avisos ----------------
    avisos = []
    if tendencia[0] == "Bajista": avisos.append("Tendencia diaria bajista: compra contra tendencia.")
    if riesgo_pct > AVISO_STOP_PCT: avisos.append(f"Stop a {riesgo_pct:.1f} % de la entrada: riesgo por operación alto.".replace(".", ",", 1))
    if proximos is not None:
        dias = (proximos.normalize() - pd.Timestamp.now().normalize()).days
        if 0 <= dias <= PLAZO_SES * 1.45:
            avisos.append(f"Resultados el {proximos:%d/%m/%Y} (en {dias} días): riesgo de gap. Un gap puede saltar el stop sin ejecutarse a su precio.")
    r_intermedias = [x for x in res_arriba if entrada < x < entrada + OBJ1_R * R]
    if r_intermedias: avisos.append(f"Resistencia en {r_intermedias[0]:.2f}".replace(".", ",") + " antes del objetivo 1: posible freno.")
    if estado[0] == "Invalidado": avisos.append("El precio ya está por debajo del stop calculado.")

    # ---------------- HTML ----------------
    def d1(x, signo=False): return (f"{x:+.1f}" if signo else f"{x:.1f}").replace(".", ",")
    def f2(x): return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    def pct(x): return f"{x:+.2f} %".replace(".", ",")
    nombre = info.get("longName") or info.get("shortName") or TICKER
    SECTORES = {"Technology": "Tecnología", "Healthcare": "Salud", "Financial Services": "Servicios financieros",
                "Consumer Cyclical": "Consumo cíclico", "Consumer Defensive": "Consumo defensivo", "Industrials": "Industria",
                "Energy": "Energía", "Utilities": "Servicios públicos", "Real Estate": "Inmobiliario",
                "Basic Materials": "Materiales básicos", "Communication Services": "Servicios de comunicación"}
    INDUSTRIAS = {"Information Technology Services": "Servicios de tecnologías de la información", "IT Services": "Servicios de tecnologías de la información", "Software - Application": "Software de aplicaciones",
        "Software - Infrastructure": "Software de infraestructura", "Semiconductors": "Semiconductores", "Semiconductor Equipment & Materials": "Equipos y materiales para semiconductores",
        "Consumer Electronics": "Electrónica de consumo", "Computer Hardware": "Hardware informático", "Communication Equipment": "Equipos de comunicación",
        "Internet Content & Information": "Contenidos e información en internet", "Internet Retail": "Comercio minorista online", "Banks - Diversified": "Banca diversificada",
        "Banks - Regional": "Banca regional", "Capital Markets": "Mercados de capitales", "Asset Management": "Gestión de activos", "Insurance - Diversified": "Seguros diversificados",
        "Insurance - Property & Casualty": "Seguros de daños", "Insurance - Life": "Seguros de vida", "Credit Services": "Servicios de crédito",
        "Financial Data & Stock Exchanges": "Datos financieros y bolsas", "Drug Manufacturers - General": "Farmacéuticas", "Drug Manufacturers - Specialty & Generic": "Farmacéuticas especializadas y genéricos",
        "Biotechnology": "Biotecnología", "Medical Devices": "Dispositivos médicos", "Medical Instruments & Supplies": "Instrumental y material médico",
        "Healthcare Plans": "Seguros de salud", "Diagnostics & Research": "Diagnóstico e investigación", "Medical Care Facilities": "Centros sanitarios",
        "Oil & Gas Integrated": "Petróleo y gas integrado", "Oil & Gas E&P": "Exploración y producción de petróleo y gas", "Oil & Gas Midstream": "Transporte y almacenamiento de petróleo y gas",
        "Oil & Gas Refining & Marketing": "Refino y comercialización de petróleo y gas", "Oil & Gas Equipment & Services": "Equipos y servicios petroleros",
        "Utilities - Regulated Electric": "Eléctricas reguladas", "Utilities - Diversified": "Servicios públicos diversificados", "Utilities - Renewable": "Renovables",
        "Utilities - Independent Power Producers": "Productores independientes de electricidad", "Utilities - Regulated Gas": "Gas regulado",
        "Aerospace & Defense": "Aeroespacial y defensa", "Specialty Industrial Machinery": "Maquinaria industrial especializada", "Farm & Heavy Construction Machinery": "Maquinaria agrícola y de construcción",
        "Conglomerates": "Conglomerados", "Railroads": "Ferrocarriles", "Integrated Freight & Logistics": "Transporte y logística", "Airlines": "Aerolíneas",
        "Waste Management": "Gestión de residuos", "Staffing & Employment Services": "Servicios de empleo", "Engineering & Construction": "Ingeniería y construcción",
        "Electrical Equipment & Parts": "Equipos y componentes eléctricos", "Building Products & Equipment": "Productos y equipos de construcción",
        "Specialty Business Services": "Servicios empresariales especializados", "Consulting Services": "Servicios de consultoría",
        "Discount Stores": "Grandes superficies de descuento", "Home Improvement Retail": "Bricolaje y hogar", "Apparel Retail": "Moda (minorista)",
        "Apparel Manufacturing": "Fabricación de ropa", "Footwear & Accessories": "Calzado y complementos", "Restaurants": "Restauración",
        "Lodging": "Hoteles", "Travel Services": "Servicios de viajes", "Auto Manufacturers": "Fabricantes de automóviles", "Auto Parts": "Componentes de automoción",
        "Specialty Retail": "Comercio especializado", "Beverages - Non-Alcoholic": "Bebidas sin alcohol", "Beverages - Brewers": "Cerveceras",
        "Household & Personal Products": "Productos del hogar y cuidado personal", "Packaged Foods": "Alimentación envasada", "Confectioners": "Confitería",
        "Tobacco": "Tabaco", "Grocery Stores": "Supermercados", "Telecom Services": "Telecomunicaciones", "Entertainment": "Entretenimiento",
        "Electronic Gaming & Multimedia": "Videojuegos y multimedia", "Advertising Agencies": "Agencias de publicidad",
        "REIT - Specialty": "SOCIMI especializada", "REIT - Industrial": "SOCIMI industrial", "REIT - Retail": "SOCIMI comercial", "REIT - Healthcare Facilities": "SOCIMI sanitaria",
        "REIT - Office": "SOCIMI de oficinas", "REIT - Residential": "SOCIMI residencial", "Real Estate Services": "Servicios inmobiliarios",
        "Specialty Chemicals": "Química especializada", "Chemicals": "Química", "Gold": "Oro", "Copper": "Cobre", "Steel": "Acero",
        "Building Materials": "Materiales de construcción", "Infrastructure Operations": "Gestión de infraestructuras", "Scientific & Technical Instruments": "Instrumentos científicos y técnicos",
        "Electronic Components": "Componentes electrónicos", "Solar": "Solar", "Trucking": "Transporte por carretera", "Marine Shipping": "Transporte marítimo"}
    def traducir(txt, tabla):
        if not txt: return ""
        if txt in tabla: return tabla[txt]
        try:
            from deep_translator import GoogleTranslator
            return GoogleTranslator(source="en", target="es").translate(txt)
        except Exception:
            return txt
    sector = " · ".join([x for x in (traducir(info.get("sector"), SECTORES), traducir(info.get("industry"), INDUSTRIAS)) if x])
    mcap = info.get("marketCap")
    MERCADOS = {"NYQ": "NYSE", "NMS": "Nasdaq", "NGM": "Nasdaq", "NCM": "Nasdaq", "ASE": "NYSE American", "PCX": "NYSE Arca",
                "MCE": "Bolsa de Madrid", "PAR": "Euronext París", "GER": "Xetra (Fráncfort)", "FRA": "Bolsa de Fráncfort",
                "AMS": "Euronext Ámsterdam", "MIL": "Borsa Italiana (Milán)", "LSE": "Bolsa de Londres", "LIS": "Euronext Lisboa",
                "EBS": "SIX (Suiza)", "BRU": "Euronext Bruselas", "TOR": "Bolsa de Toronto"}
    bolsa = MERCADOS.get(info.get("exchange", ""), info.get("exchange", ""))
    moneda = info.get("currency") or "USD"
    simbolo = {"USD": "$", "EUR": "€", "GBP": "£", "GBp": "p", "CHF": "CHF"}.get(moneda, moneda)
    mcap_txt = (f"{mcap/1e9:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + (" B$" if moneda == "USD" else f" mil M {simbolo}")) if mcap else "—"
    hoy = fechas[-1]

    # Gráfico SVG: 120 sesiones + niveles
    N = 120; cc = c[-N:]; ff = fechas[-N:]
    lo = min(cc.min(), stop) * 0.985; hi = max(cc.max(), obj2) * 1.015
    W, Hh, PADL, PADR, PADT, PADB = 760, 320, 10, 70, 12, 26
    X = lambda i: PADL + i * (W - PADL - PADR) / (len(cc) - 1)
    Y = lambda p: PADT + (hi - p) * (Hh - PADT - PADB) / (hi - lo)
    path = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(p):.1f}" for i, p in enumerate(cc))
    area = path + f" L{X(len(cc)-1):.1f},{Hh-PADB} L{X(0):.1f},{Hh-PADB} Z"
    def hline(p, col, txt, dash="4 4"):
        return (f'<line x1="{PADL}" x2="{W-PADR}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" stroke="{col}" stroke-dasharray="{dash}" stroke-width="1.2"/>'
                f'<text x="{W-PADR+6}" y="{Y(p)+4:.1f}" fill="{col}" font-size="11">{f2(p)}</text>'
                f'<text x="{PADL+4}" y="{Y(p)-5:.1f}" fill="{col}" font-size="10" font-weight="600">{txt}</text>')
    MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    ticks = "".join(f'<text x="{X(i):.1f}" y="{Hh-6}" fill="var(--muted)" font-size="10" text-anchor="middle">{ff[i].day} {MESES[ff[i].month-1]}</text>'
                    for i in range(0, len(cc), 24))
    svg = f'''<svg viewBox="0 0 {W} {Hh}" width="100%" role="img" aria-label="Precio y niveles">
    <rect x="{PADL}" y="{Y(zona_alta):.1f}" width="{W-PADL-PADR}" height="{max(Y(zona_baja)-Y(zona_alta),2):.1f}" fill="var(--acc)" opacity=".16"/>
    <path d="{area}" fill="var(--acc)" opacity=".07"/><path d="{path}" fill="none" stroke="var(--acc)" stroke-width="2"/>
    {hline(obj2, "var(--acc)", "OBJ 2")}{hline(obj1, "var(--warn)", "OBJ 1")}{hline(entrada, "var(--txt)", "ENTRADA", "2 3")}{hline(stop, "var(--neg)", "STOP")}
    <circle cx="{X(len(cc)-1):.1f}" cy="{Y(cc[-1]):.1f}" r="4" fill="var(--acc)"/>{ticks}</svg>'''

    filas_niv = "".join(
        f'<tr><td>{html.escape(n)}</td><td class="{"pos" if t=="soporte" else "neg"}">{t}</td><td class="num">{f2(p)}'
        + (f' – {f2(s)}' if s is not None else '') + f'</td><td class="num">{pct((p/P-1)*100)}</td><td class="num">{d1((p-P)/atr, True)}</td></tr>'
        for n, p, s, t in sorted(niveles, key=lambda x: -x[1]))
    filas_conf = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{html.escape(cmt)}</td></tr>" for a, b, cmt in conf) or '<tr><td colspan="3">Sin datos 1H</td></tr>'
    html_avisos = "".join(f"<li>{html.escape(a)}</li>" for a in avisos) or "<li>Sin avisos.</li>"
    color_estado = {"En zona": "var(--acc)", "Cerca": "var(--warn)", "Esperar retroceso": "var(--muted)", "Invalidado": "var(--neg)"}[estado[0]]
    color_tend = {"Alcista": "var(--acc)", "Mixta": "var(--warn)", "Bajista": "var(--neg)"}[tendencia[0]]

    INFORME = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>JJTrading_ {TICKER} plan</title><style>
    :root{{--bg:#f3f0ea;--card:#fffdf9;--line:#e3ddd2;--txt:#0f172a;--muted:#5b6474;--acc:#15803d;--warn:#b45309;--neg:#dc2626}}
    *{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}}
    .wrap{{max-width:1100px;margin:0 auto;padding:24px 16px}}.top{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:14px;flex-wrap:wrap;gap:8px}}
    .brand{{font-weight:800;font-size:26px;letter-spacing:-.5px}}.brand span{{color:var(--acc)}}.sub{{color:var(--muted);font-size:11px;letter-spacing:2px;text-transform:uppercase}}
    .kick{{color:var(--acc);font-size:12px;letter-spacing:2px;text-transform:uppercase;margin:22px 0 4px}}h1{{font-size:44px;margin:0;line-height:1.05;color:#0f172a}}h3{{color:var(--txt)}}h1 small{{color:var(--acc);font-size:20px;margin-left:8px}}
    .kpis{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-radius:14px;margin:20px 0;overflow:hidden}}.kpi{{padding:14px 18px;border-right:1px solid var(--line)}}.kpi:last-child{{border:0}}
    .lab{{color:var(--muted);font-size:11px;letter-spacing:1.5px;text-transform:uppercase}}.big{{font-size:28px;font-weight:700}}.small{{color:var(--muted);font-size:12px}}
    .grid{{display:grid;grid-template-columns:1.6fr 1fr;gap:16px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
    .card h3{{margin:0 0 12px;font-size:17px}}.row{{display:flex;justify-content:space-between;align-items:center;border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:8px}}
    .row b{{font-size:22px}}.row.stop{{border-color:#f5c2c2;background:#fee2e2}}.row.stop b{{color:var(--neg)}}.row.o2 b{{color:var(--acc)}}
    .pos{{color:var(--acc)}}.neg{{color:var(--neg)}}table{{width:100%;border-collapse:collapse;font-size:13px}}td,th{{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:1px}}.num{{text-align:right;font-variant-numeric:tabular-nums}}
    .tag{{display:inline-block;padding:3px 10px;border-radius:99px;font-size:12px;font-weight:600;border:1px solid currentColor}}ul{{margin:6px 0 0;padding-left:18px}}li{{margin:4px 0}}
    .foot{{color:var(--muted);font-size:12px;margin-top:18px;line-height:1.6}}@media(max-width:820px){{.grid{{grid-template-columns:1fr}}.kpis{{grid-template-columns:1fr 1fr}}.kpi{{border-bottom:1px solid var(--line)}}h1{{font-size:32px}}}}
    </style></head><body><div class="wrap">
    <div class="top"><div><span class="brand">JJTrading<span>_</span></span> &nbsp;<span class="sub">Plan de operación · solo largos</span></div>
    <div class="sub" style="text-align:right">{hoy:%d/%m/%Y} · {html.escape(bolsa)}<br><span style="color:var(--acc)">Datos: Yahoo Finance</span></div></div>
    <div class="kick">{html.escape(sector) or "&nbsp;"}</div><h1>{html.escape(nombre)}<small>{TICKER}</small></h1>
    <div class="kpis"><div class="kpi"><div class="lab">Último precio</div><div class="big">{f2(P)} <span style="font-size:15px">{html.escape(moneda)}</span></div><div class="small">cierre/último dato {hoy:%d/%m/%Y}</div></div>
    <div class="kpi"><div class="lab">Variación diaria</div><div class="big {'pos' if P>=P_ant else 'neg'}">{pct((P/P_ant-1)*100)}</div><div class="small">anterior {f2(P_ant)}</div></div>
    <div class="kpi"><div class="lab">Capitalización</div><div class="big">{mcap_txt}</div><div class="small">ATR(14) diario {f2(atr)} · {d1(atr/P*100)} %</div></div>
    <div class="kpi"><div class="lab">Rango 52 semanas</div><div class="big">{f2(min52)}–{f2(max52)}</div><div class="small">a {d1((P/max52-1)*100)} % del máximo</div></div></div>
    <div class="grid"><div class="card"><h3>Precio (120 sesiones) y plan</h3>{svg}
    <div class="small">Banda verde: zona de entrada. Líneas: objetivos, entrada de referencia y stop.</div></div>
    <div class="card"><h3>Plan de operación</h3>
    <div class="row"><span class="lab">Estado</span><span class="tag" style="color:{color_estado}">{estado[0]}</span></div>
    <div class="row"><span class="lab">Zona de entrada</span><b>{f2(zona_baja)}–{f2(zona_alta)} {html.escape(simbolo)}</b></div>
    <div class="row stop"><span class="lab">Stop de pérdidas</span><b>{f2(stop)} {html.escape(simbolo)}</b></div>
    <div class="row"><span class="lab">Objetivo 1 · {origen1}</span><b>{f2(obj1)} {html.escape(simbolo)}</b></div>
    <div class="row o2"><span class="lab">Objetivo 2 · {origen2}</span><b>{f2(obj2)} {html.escape(simbolo)}</b></div>
    <div class="row"><div><div class="lab">Riesgo potencial</div><b class="neg">−{d1(riesgo_pct)} %</b><div class="small">−{f2(R)} {html.escape(simbolo)}/acción</div></div>
    <div style="text-align:right"><div class="lab">Ratio B°/riesgo</div><b class="pos">{f2(ratio)}×</b><div class="small">objetivo 1: {pct((obj1/entrada-1)*100)}</div></div></div>
    <div class="small">{html.escape(estado[1])}. Entrada de referencia {f2(entrada)}. Soporte: {html.escape(soporte_nombre)}. Stop: {html.escape(regla_stop)}. Plazo máximo {PLAZO_SES} sesiones.</div></div></div>
    <div class="grid" style="margin-top:16px"><div class="card"><h3>Mapa de niveles (diario)</h3><table><tr><th>Nivel</th><th>Tipo</th><th class="num">Precio</th><th class="num">vs precio</th><th class="num">ATR</th></tr>{filas_niv}</table></div>
    <div class="card"><h3>Contexto</h3><div class="row"><span class="lab">Tendencia diaria</span><span class="tag" style="color:{color_tend}">{tendencia[0]}</span></div>
    <div class="small">{html.escape(tendencia[1])}. EMA 21 {f2(e21)} · EMA 55 {f2(e55)} · EMA 200 {f2(e200)}.</div>
    <h3 style="margin-top:16px">Confirmación 1H <span class="small">(informativa)</span></h3><table>{filas_conf}</table>
    <h3 style="margin-top:16px">Avisos</h3><ul>{html_avisos}</ul>
    <div class="small" style="margin-top:8px">Próximos resultados: {f"{proximos:%d/%m/%Y}" if proximos is not None else "sin fecha en Yahoo"}</div></div></div>
    <div class="foot"><b>Método.</b> Niveles calculados con tus indicadores (Order Blocks LuxAlgo, EMAs, SuperTrend 10/3, POC 200 velas, mínimos/máximos swing de 10 velas) y reglas calibradas con 162 acciones en diario 2006-2026:
    stop corto (&lt; 2 %) y stop justo bajo un mínimo swing dieron peores resultados; el Order Block mostró una ventaja pequeña frente a niveles al azar con stops ≥ 2 %; el resto de soportes rindió como un nivel al azar.
    Los niveles definen dónde se invalida la idea y cuánto arriesgas; no predicen el rebote. La simulación supone salida al precio del stop: con gaps la pérdida puede ser mayor.
    <br>Informe automático con fines de análisis personal. No es una recomendación de inversión.</div>
    </div></body></html>'''

    # ---------------- Fila completa para Google Sheets (Datos / Histórico) ----------------
    # Mismas variables que el informe: no se recalcula nada.
    ahora = pd.Timestamp.now(tz="Europe/Madrid")
    def r4(x): return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)
    conf_d = {a: (b, cmt) for a, b, cmt in conf}
    fila = {
        "Fecha": f"{ahora:%Y-%m-%d}", "Hora actualización": f"{ahora:%Y-%m-%d %H:%M}",
        "Ticker": TICKER, "Nombre": nombre, "Bolsa": bolsa, "Moneda": moneda, "Sector": sector,
        "Último precio": r4(P), "Cierre anterior": r4(P_ant), "Variación día %": r4((P / P_ant - 1) * 100),
        "Mínimo 52 sem": r4(min52), "Máximo 52 sem": r4(max52), "Distancia máx 52 sem %": r4((P / max52 - 1) * 100),
        "Capitalización": mcap if mcap else None, "ATR 14": r4(atr), "ATR %": r4(atr / P * 100),
        "Tendencia diaria": tendencia[0], "EMA 21": r4(e21), "EMA 55": r4(e55), "EMA 200": r4(e200),
        "SuperTrend diario": "Alcista" if st[-1] == 1 else "Bajista",
        "Estado": estado[0], "Distancia zona (ATR)": r4((P - zona_alta) / atr), "Soporte": soporte_nombre,
        "Zona baja": r4(zona_baja), "Zona alta": r4(zona_alta), "Entrada ref.": r4(entrada), "Stop": r4(stop),
        "Regla stop": regla_stop, "Objetivo 1": r4(obj1), "Origen obj. 1": origen1, "Objetivo 2": r4(obj2),
        "Origen obj. 2": origen2, "Riesgo %": r4(riesgo_pct), "Riesgo por acción": r4(R), "Ratio B/R": r4(ratio),
        "% hasta obj. 1": r4((obj1 / entrada - 1) * 100),
        "SuperTrend 1H": conf_d.get("SuperTrend 1H", ("", ""))[0],
        "Último giro ST 1H": conf_d.get("SuperTrend 1H", ("", ""))[1].replace("último giro alcista: ", ""),
        "Último CHoCH 1H": conf_d.get("CHoCH alcista 1H", ("", ""))[1].replace("último: ", ""),
        "MACD 1H": conf_d.get("Cruce MACD 1H", ("", ""))[0],
        "Próximos resultados": f"{proximos:%Y-%m-%d}" if proximos is not None else "",
        "Avisos": " | ".join(avisos),
        # Resistencias por encima de la entrada, para comparar después con lo que hizo el precio
        "Resistencias": ";".join(f"{x:.4f}" for x in res_arriba[:8]),
    }

    return {"ticker": TICKER, "html": INFORME, "fecha": f"{hoy:%Y-%m-%d}", "nombre": nombre, "moneda": moneda,
            "fila": fila,
            "resumen": {"estado": estado[0], "zona": (zona_baja, zona_alta), "stop": stop, "obj1": obj1, "obj2": obj2,
                        "riesgo_pct": riesgo_pct, "ratio": ratio, "moneda": moneda}}


# ---------------- Búsqueda de tickers por nombre ----------------
# Códigos de bolsa de Yahoo → clave de BOLSAS que usa generar()
EXCHANGE_A_BOLSA = {"NYQ": "EEUU", "NMS": "EEUU", "NGM": "EEUU", "NCM": "EEUU", "ASE": "EEUU", "PCX": "EEUU",
                    "NYS": "EEUU", "NAS": "EEUU", "BTS": "EEUU",
                    "MCE": "MADRID", "PAR": "PARIS", "MIL": "MILAN", "GER": "FRANCFORT", "FRA": "FRANCFORT",
                    "AMS": "AMSTERDAM", "LSE": "LONDRES", "LIS": "LISBOA", "EBS": "SUIZA", "BRU": "BRUSELAS",
                    "TOR": "TORONTO"}
FILTROS_BUSQUEDA = ["EEUU", "MADRID", "PARIS", "MILAN", "Todas las bolsas"]


def buscar(texto, filtro="Todas las bolsas", max_resultados=25):
    """Busca acciones por nombre en Yahoo. Devuelve lista de dicts: simbolo, nombre, bolsa (clave), exchange."""
    texto = (texto or "").strip()
    if len(texto) < 2:
        return []
    quotes = yf.Search(texto, max_results=max_resultados, news_count=0, lists_count=0,
                       include_cb=False, raise_errors=False).quotes or []
    salida, vistos = [], set()
    for q in quotes:
        if q.get("quoteType") != "EQUITY":
            continue
        b = EXCHANGE_A_BOLSA.get(q.get("exchange", ""))
        if b is None or (filtro != "Todas las bolsas" and b != filtro):
            continue
        sim = q.get("symbol", "")
        if not sim or sim in vistos:
            continue
        vistos.add(sim)
        salida.append({"simbolo": sim, "nombre": q.get("longname") or q.get("shortname") or sim,
                       "bolsa": b, "exchange": q.get("exchDisp") or q.get("exchange", "")})
    return salida
