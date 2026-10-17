# Descarga en bruto de Yahoo para la pestaña Riesgo.
# Solo datos publicados (cotizaciones, cuentas, consenso, fechas). Ningún ratio calculado por Yahoo.
import datetime as dt

import yfinance as yf

from traducciones import INDUSTRIAS, SECTORES, primeras_frases, traducir

CLAVES = ["TotalRevenue", "GrossProfit", "OperatingIncome", "EBIT", "EBITDA", "NetIncome", "DilutedEPS",
          "TaxRateForCalcs", "InterestExpense", "ResearchAndDevelopment", "DilutedAverageShares",
          "StockholdersEquity", "TotalAssets", "CurrentAssets", "CurrentLiabilities", "RetainedEarnings",
          "TotalLiabilitiesNetMinorityInterest", "TotalDebt", "CashCashEquivalentsAndShortTermInvestments",
          "OrdinarySharesNumber", "LongTermDebt", "OperatingCashFlow", "CapitalExpenditure", "CashDividendsPaid"]
Q2 = "https://query2.finance.yahoo.com"


class ErrorRiesgo(Exception):
    pass


def _v(x):
    return x.get("raw") if isinstance(x, dict) else x


def _d(ts):
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%d")


def _series(js, pre):
    m = {}
    for r in (js.get("timeseries") or {}).get("result") or []:
        ty = r["meta"]["type"][0]
        arr = sorted([e["asOfDate"], e["reportedValue"]["raw"]] for e in (r.get(ty) or []) if e)
        if arr:
            m[ty[len(pre):]] = arr
    return m


def descargar(simbolo):
    tk = yf.Ticker(simbolo)
    get = tk._data.get_raw_json
    p2 = int(dt.datetime.now(dt.timezone.utc).timestamp())
    p1 = p2 - 6 * 365 * 86400
    p1d = p2 - (5 * 365 + 20) * 86400
    R = {"ticker": simbolo, "avisos_descarga": []}

    c1 = get(f"{Q2}/v8/finance/chart/{simbolo}", params={"period1": p1d, "period2": p2, "interval": "1d"})["chart"]["result"]
    if not c1:
        raise ErrorRiesgo(f"{simbolo}: Yahoo no devuelve cotizaciones (¿ticker o bolsa incorrectos?)")
    c1 = c1[0]
    cl, aj = c1["indicators"]["quote"][0]["close"], c1["indicators"]["adjclose"][0]["adjclose"]
    R["diario5"] = [[_d(t), round(c, 4), round(a, 4)] for t, c, a in zip(c1["timestamp"], cl, aj) if c is not None and a is not None]
    if R["diario5"]:
        f = dt.date.fromisoformat(R["diario5"][-1][0])
        desde = f.replace(year=f.year - 1, day=28 if (f.month, f.day) == (2, 29) else f.day).isoformat()
        R["diario"] = [[d, c] for d, c, _ in R["diario5"] if d > desde]
    else:
        R["diario"] = []
    if len(R["diario"]) < 30:
        raise ErrorRiesgo(f"{simbolo}: Yahoo no devuelve cotizaciones suficientes")

    c5 = get(f"{Q2}/v8/finance/chart/{simbolo}",
             params={"range": "5y", "interval": "1mo", "events": "div,split"})["chart"]["result"][0]
    q5, a5 = c5["indicators"]["quote"][0]["close"], c5["indicators"]["adjclose"][0]["adjclose"]
    R["mensual"] = [[_d(t), round(c, 4), round(a, 4)] for t, c, a in zip(c5["timestamp"], q5, a5)
                    if c is not None and a is not None]
    R["dividendos"] = sorted([_d(e["date"]), e["amount"]] for e in ((c5.get("events") or {}).get("dividends") or {}).values())
    c10 = get(f"{Q2}/v8/finance/chart/{simbolo}",
              params={"range": "10y", "interval": "1mo", "events": "split"})["chart"]["result"][0]
    R["splits"] = sorted([_d(s["date"]), s["numerator"], s["denominator"]]
                         for s in ((c10.get("events") or {}).get("splits") or {}).values())

    for pre, dest in (("annual", "anual"), ("quarterly", "trimestral"), ("trailing", "ttm")):
        try:
            js = get(f"{Q2}/ws/fundamentals-timeseries/v1/finance/timeseries/{simbolo}",
                     params={"symbol": simbolo, "type": ",".join(pre + k for k in CLAVES),
                             "period1": p1, "period2": p2})
            R[dest] = _series(js, pre)
        except Exception as e:
            R[dest] = {}
            R["avisos_descarga"].append(f"Cuentas {dest}: {e}")

    q = {}
    try:
        js = get(f"{Q2}/v10/finance/quoteSummary/{simbolo}",
                 params={"modules": "price,assetProfile,financialData,defaultKeyStatistics,earningsTrend,"
                                    "earningsHistory,calendarEvents"})
        q = js["quoteSummary"]["result"][0]
    except Exception as e:
        R["avisos_descarga"].append(f"Consenso y ficha: {e}")
    pr, ap, fd, ks = (q.get(k) or {} for k in ("price", "assetProfile", "financialData", "defaultKeyStatistics"))
    R["nombre"] = pr.get("longName") or pr.get("shortName") or simbolo
    R["moneda"] = pr.get("currency") or c1["meta"].get("currency")
    R["bolsa"] = pr.get("exchangeName") or c1["meta"].get("exchangeName")
    R["sector"], R["industria"] = ap.get("sector"), ap.get("industry")
    R["sector_es"], R["industria_es"] = traducir(R["sector"], SECTORES), traducir(R["industria"], INDUSTRIAS)
    R["descripcion"] = primeras_frases(ap.get("longBusinessSummary"), 2)
    es = traducir(R["descripcion"]) if R["descripcion"] else ""
    R["descripcion_es"] = es if es and es != R["descripcion"] else None
    R["acciones"] = _v(ks.get("sharesOutstanding"))
    tr = {e.get("period"): _v(e.get("growth")) for e in (q.get("earningsTrend") or {}).get("trend") or []}
    R["consenso"] = {"objetivo": _v(fd.get("targetMeanPrice")), "analistas": _v(fd.get("numberOfAnalystOpinions")),
                     "bpa_est": _v(ks.get("forwardEps")), "crec_0y": tr.get("0y"), "crec_1y": tr.get("+1y")}
    R["batidas"] = [[_d(_v(h["quarter"])), _v(h.get("epsEstimate")), _v(h.get("epsActual"))]
                    for h in (q.get("earningsHistory") or {}).get("history") or []
                    if _v(h.get("quarter")) and _v(h.get("epsEstimate")) is not None and _v(h.get("epsActual")) is not None]
    ed = ((q.get("calendarEvents") or {}).get("earnings") or {}).get("earningsDate") or []
    R["proximos_resultados"] = _d(_v(ed[0])) if ed else None
    return R
