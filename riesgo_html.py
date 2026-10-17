# HTML de la pestaña Riesgo. Solo presentación: todos los valores llegan calculados desde riesgo_calculo.
import html
import json
import math

from riesgo_calculo import BLOQUES, ORDEN, es, millones

E = html.escape
SECCIONES = [("resumen", "Resumen"), ("historia", "¿Cara o barata?"), ("evolucion", "Evolución"), ("valor", "Valor justo"),
             ("nota", "Base de la nota"), ("cuentas", "Sus cuentas"), ("tecnico", "Precio y técnicos"),
             ("resultados", "Resultados"), ("limites", "Límites")]
COL_BLOQUE = {"val": "#1e3a8a", "sal": "#6d28d9", "cre": "#475569"}
TXT_COLOR = {"verde": "Favorable", "ambar": "Precaución", "rojo": "Desfavorable", "gris": "Sin dato"}
COL_ETQ = {"Excelente": "verde", "Buena": "verde", "Aceptable": "ambar", "Débil": "rojo"}

# ---------------------------------------------------------------- textos de ayuda («?»)
QUE = {
    "per_fwd": "Cuántas veces pagas, con el precio de hoy, el beneficio por acción que se espera en los próximos 12 meses.",
    "ev_ebitda": "Lo que costaría comprar la empresa entera, deuda incluida, frente a lo que gana su negocio antes de intereses, impuestos y amortizaciones.",
    "rent_fcf": "La caja libre que genera la empresa en un año por cada 100 que vale en bolsa.",
    "peg": "El PER ajustado por el crecimiento del beneficio esperado a 5 años.",
    "ps": "Cuánto pagas por cada unidad que vende la empresa en un año.",
    "potencial": "Cuánto tendría que subir o bajar el precio para llegar al precio objetivo medio de los analistas.",
    "dn_ebitda": "Cuántos años de EBITDA necesitaría la empresa para pagar su deuda neta.",
    "liquidez": "Lo que la empresa tiene o cobrará a corto plazo frente a lo que debe pagar en menos de un año.",
    "cobertura": "Cuántas veces paga su beneficio operativo los intereses de la deuda.",
    "margen_fcf": "De cada 100 que vende, cuánto le queda en caja libre.",
    "roic": "Cuánto gana por cada 100 invertidos en el negocio, entre dinero propio y deuda.",
    "altman": "Una puntuación que combina 5 ratios del balance y los resultados para estimar el riesgo de quiebra.",
    "ventas_ia": "Cuánto han cambiado las ventas de los últimos 12 meses frente a los 12 meses anteriores.",
    "bpa_ia": "Cuánto ha cambiado el beneficio por acción de los últimos 12 meses frente a los 12 meses anteriores.",
    "cagr3": "El crecimiento medio anual de las ventas en los 3 últimos ejercicios.",
    "bpa_est": "Cuánto esperan los analistas que crezca el beneficio por acción en el ejercicio fiscal siguiente.",
    "batidas": "En cuántas de las 4 últimas presentaciones de resultados el beneficio real superó lo que esperaban los analistas.",
    "margen_op_var": "Cuántos puntos ha subido o bajado el margen operativo frente al año anterior."}
COMO = {
    "per_fwd": "Precio / beneficio por acción estimado por los analistas.",
    "ev_ebitda": "(Capitalización + deuda neta) / EBITDA de 12 meses.",
    "rent_fcf": "(Flujo de caja operativo − inversiones) / capitalización.",
    "peg": "PER forward / crecimiento del BPA estimado a 5 años. Yahoo no publica ese crecimiento, por eso sale sin dato.",
    "ps": "Capitalización / ventas de 12 meses.",
    "potencial": "(Precio objetivo medio − precio) / precio.",
    "dn_ebitda": "(Deuda total − caja) / EBITDA de 12 meses.",
    "liquidez": "Activo corriente / pasivo corriente del último balance.",
    "cobertura": "EBIT / gastos financieros de 12 meses.",
    "margen_fcf": "(Flujo de caja operativo − inversiones) / ventas de 12 meses.",
    "roic": "EBIT × (1 − tipo impositivo) / (patrimonio + deuda neta).",
    "altman": "1,2 × capital circulante + 1,4 × reservas + 3,3 × EBIT + 1,0 × ventas, todo dividido entre el activo, más 0,6 × capitalización / pasivo.",
    "ventas_ia": "(Ventas de 12 meses / ventas de los 12 meses anteriores − 1) × 100.",
    "bpa_ia": "(BPA de 12 meses − BPA de los 12 meses anteriores) / BPA anterior × 100, ajustado por splits.",
    "cagr3": "(Ventas del último ejercicio / ventas de hace 3 ejercicios) elevado a 1/3, menos 1.",
    "bpa_est": "Estimación media de los analistas que publica Yahoo.",
    "batidas": "Se cuentan las veces que el BPA real fue mayor que el estimado.",
    "margen_op_var": "Margen operativo de 12 meses − margen operativo de los 12 meses anteriores."}
BUENO = {
    "per_fwd": "Verde por debajo de 15 · ámbar de 15 a 25 · rojo por encima de 25 o si es negativo.",
    "ev_ebitda": "Verde por debajo de 10 · ámbar de 10 a 18 · rojo por encima de 18.",
    "rent_fcf": "Verde por encima del 5 % · ámbar del 2 al 5 % · rojo por debajo del 2 %.",
    "peg": "Verde por debajo de 1 · ámbar de 1 a 2 · rojo por encima de 2.",
    "ps": "Verde por debajo de 2 · ámbar de 2 a 6 · rojo por encima de 6.",
    "potencial": "Verde por encima del 15 % · ámbar del 0 al 15 % · rojo si es negativo.",
    "dn_ebitda": "Verde por debajo de 1,5 o con caja neta · ámbar de 1,5 a 3 · rojo por encima de 3.",
    "liquidez": "Verde por encima de 1,5 · ámbar de 1 a 1,5 · rojo por debajo de 1.",
    "cobertura": "Verde por encima de 8 · ámbar de 3 a 8 · rojo por debajo de 3.",
    "margen_fcf": "Verde por encima del 15 % · ámbar del 5 al 15 % · rojo por debajo del 5 %.",
    "roic": "Verde por encima del 15 % · ámbar del 8 al 15 % · rojo por debajo del 8 %.",
    "altman": "Verde por encima de 3 (zona segura) · ámbar de 1,8 a 3 · rojo por debajo de 1,8.",
    "ventas_ia": "Verde por encima del 10 % · ámbar del 0 al 10 % · rojo si bajan.",
    "bpa_ia": "Verde por encima del 10 % · ámbar del 0 al 10 % · rojo si baja.",
    "cagr3": "Verde por encima del 8 % · ámbar del 0 al 8 % · rojo si bajan.",
    "bpa_est": "Verde por encima del 10 % · ámbar del 0 al 10 % · rojo si se espera que baje.",
    "batidas": "Verde 4 de 4 · ámbar 2 o 3 · rojo 0 o 1.",
    "margen_op_var": "Verde si sube más de 1 punto · ámbar entre −1 y +1 · rojo si baja más de 1 punto."}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&family=JetBrains+Mono:wght@400;600;700&display=swap');
.jr{--bg:#f3f0ea;--card:#fffdf9;--card2:#f8f5ef;--line:#e3ddd2;--txt:#0f172a;--mut:#5b6474;--suave:#8a92a0;--osc:#161a2e;
--v:#15803d;--vb:#dcfce7;--vt:#14532d;--a:#d97706;--ab:#fef3c7;--at:#78350f;--r:#dc2626;--rb:#fee2e2;--rt:#7f1d1d;--g:#94a3b8;--gb:#eef1f5;--gt:#334155;
font-family:'DM Sans',-apple-system,Segoe UI,Roboto,sans-serif;color:var(--txt);font-size:15px;line-height:1.55;max-width:1100px;margin:0 auto}
.jr *{box-sizing:border-box}.jr .m{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums}
.jr h2{font-size:21px;font-weight:700;margin:0 0 2px;color:var(--txt)}.jr h3{font-size:16px;font-weight:700;margin:0 0 6px;color:var(--txt)}
.jr .sub{color:var(--mut);font-size:13px;margin:0 0 14px}.jr .sec{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin:14px 0}
.jr .nav{position:relative;z-index:50;will-change:transform;background:#fff;border:1.5px solid var(--osc);border-radius:14px;padding:8px 10px 8px 14px;display:flex;align-items:center;justify-content:space-between;gap:10px;margin:6px 0 4px}
.jr .nav .k{font-size:11px;color:var(--mut)}.jr .nav .n{font-weight:700;font-size:15px}
.jr .nav details{position:relative}.jr .nav summary{list-style:none;cursor:pointer;background:#f0a030;color:#1f1300;font-weight:700;border-radius:10px;padding:7px 14px;font-size:14px}
.jr .nav summary::-webkit-details-marker{display:none}.jr .nav .lista{position:absolute;right:0;top:44px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:6px;min-width:220px;box-shadow:0 8px 24px rgba(15,23,42,.12)}
.jr .nav .lista a{display:block;padding:8px 10px;border-radius:8px;color:var(--txt);text-decoration:none;font-size:14px}.jr .nav .lista a:hover{background:var(--card2)}
.jr .hero{background:var(--osc);color:#fff;border-radius:16px 16px 0 0;padding:18px 20px;display:flex;gap:16px;align-items:center}
.jr .hero .t{font-size:28px;font-weight:700;line-height:1.1}
.jr .notabox{position:relative;background:#fff;color:var(--txt);border-radius:12px;padding:8px 30px 8px 12px;text-align:center;min-width:96px}
.jr .notabox .n{font-size:30px;font-weight:700;line-height:1}.jr .notabox .l{font-size:10.5px;letter-spacing:1.5px;color:var(--mut);font-weight:700}
.jr .notabox .q{position:absolute;top:4px;right:4px}
.jr .chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:500;white-space:nowrap}
.jr .hero .chip{background:rgba(255,255,255,.12);color:#e2e8f0;border:1px solid rgba(255,255,255,.18);margin:6px 6px 0 0}
.jr .precio{background:#fff;border:1px solid var(--line);border-top:0;border-radius:0 0 16px 16px;padding:16px 20px;display:grid;gap:14px;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);align-items:start}
.jr .big{font-size:34px;font-weight:600}.jr .pill{display:inline-block;white-space:nowrap;border-radius:8px;padding:2px 9px;font-size:13px;font-weight:600}
.jr .verde{background:var(--vb);color:var(--vt)}.jr .ambar{background:var(--ab);color:var(--at)}.jr .rojo{background:var(--rb);color:var(--rt)}.jr .gris{background:var(--gb);color:var(--gt)}
.jr .bar52{position:relative;height:6px;border-radius:3px;background:#e9e3d8;margin:8px 0 4px}.jr .bar52 i{position:absolute;top:-4px;width:3px;height:14px;background:var(--osc);border-radius:2px}
.jr .grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr))}.jr .g2{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr))}
.jr .tile{position:relative;background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px}.jr .tile .l{font-size:12px;color:var(--mut)}.jr .tile .v{font-size:22px;font-weight:600}
.jr .tile.osc{background:var(--osc);color:#fff;border-color:var(--osc)}.jr .tile.osc .l{color:#cbd5e1}
.jr .aviso{background:#fff7e6;border:1px solid #f5d08a;color:#6b3f00;border-radius:12px;padding:10px 14px;font-size:14px;margin:10px 0}
.jr .eh{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:6px}.jr .eh span{color:var(--mut);font-size:13px}
.jr .ese{position:relative;display:flex;align-items:center;gap:10px;padding:7px 0;font-size:15px}
.jr .ese .ic{flex:0 0 28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px}
.jr .ic.ok{background:var(--vb);color:var(--v)}.jr .ic.ko{background:var(--rb);color:var(--r)}.jr .ic.neutro{background:var(--gb);color:var(--gt)}
.jr .ese .tx{flex:1;min-width:0}.jr .ese .vl{font-family:'JetBrains Mono',monospace;font-weight:700;white-space:nowrap;font-size:14.5px}
.jr .np{font-size:11px;color:var(--suave);border:1px solid var(--line);border-radius:6px;padding:0 6px;margin-left:6px;white-space:nowrap}
.jr .sep{border-top:1px solid var(--line);margin:14px 0 8px}
.jr .bloque{background:#fff;border:1px solid var(--line);border-top:4px solid;border-radius:0 0 12px 12px;padding:12px 14px}
.jr .bh{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}.jr .bh b{font-size:15px}
.jr .kpi{position:relative;padding:9px 0;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:8px}.jr .kpi:first-of-type{border-top:0}
.jr .q{flex:0 0 auto;width:20px;height:20px;border-radius:50%;border:1px solid #c9c2b5;background:#fff;color:var(--mut);font:700 12px/18px 'DM Sans',sans-serif;cursor:pointer;padding:0;margin-left:6px;vertical-align:middle}
.jr .q:hover,.jr .q.on{background:var(--osc);color:#fff;border-color:var(--osc)}
.jr .tip{display:none;position:absolute;left:0;top:100%;z-index:40;width:min(360px,calc(100vw - 24px));background:#fff;color:var(--txt);border:1px solid var(--line);border-radius:12px;
padding:10px 12px;font-size:13.5px;line-height:1.5;box-shadow:0 10px 28px rgba(15,23,42,.16);text-align:left;font-weight:400;letter-spacing:0}
.jr .tip b{font-weight:700}.jr .tip p{margin:0 0 6px}.jr .tip p:last-child{margin:0}.jr .tip.on{display:block}
@media(hover:hover){.jr .q:hover + .tip{display:block}}
.jr .barra{height:8px;border-radius:4px;background:#ebe5da;overflow:hidden}.jr .barra i{display:block;height:8px}
.jr .card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:6px}
.jr .card .top{position:relative;display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.jr .card .nm{font-weight:600;font-size:14px}
.jr .card .fr{font-size:14px}.jr .card .md{font-size:12px;color:var(--suave)}.jr .warn{background:var(--ab);color:var(--at);font-size:11.5px;border-radius:6px;padding:1px 7px;margin-right:4px}
.jr details.blq{border:1px solid var(--line);border-radius:12px;background:#fff;margin:10px 0}.jr details.blq > summary{list-style:none;cursor:pointer;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;gap:10px;border-left:5px solid;border-radius:12px}
.jr details.blq > summary::-webkit-details-marker{display:none}.jr details.blq > summary .fl{color:var(--mut);font-size:13px;white-space:nowrap}
.jr details.blq[open] > summary .fl{transform:rotate(180deg)}.jr details.blq .in{padding:0 14px 14px}
.jr table{width:100%;border-collapse:collapse;font-size:14px}.jr td,.jr th{padding:8px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.jr th{font-size:12px;color:var(--mut);font-weight:500}.jr td.n,.jr th.n{text-align:right;font-family:'JetBrains Mono',monospace}
.jr .tw{overflow-x:auto}.jr .sen{position:relative;background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin:8px 0}
.jr .sen .tg{font-size:11px;font-weight:700;letter-spacing:.5px;border-radius:6px;padding:2px 8px;margin-right:8px}
.jr .favor{background:var(--vb);color:var(--vt)}.jr .contra{background:var(--rb);color:var(--rt)}.jr .contexto{background:#e0e7ff;color:#3730a3}
.jr .tr{position:relative;display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr) minmax(0,1.3fr);gap:6px 10px;padding:9px 0;border-bottom:1px solid var(--line);font-size:14px;align-items:center}
.jr .tr .vv{font-family:'JetBrains Mono',monospace;text-align:right}.jr .tr .es{color:var(--mut);font-size:13px}
.jr .btns button,.jr .per button{font:inherit;font-size:14px;border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 14px;cursor:pointer;color:var(--txt)}
.jr .per button.on{border:2px solid var(--osc);font-weight:700}.jr .btns button{border-radius:10px;background:var(--osc);color:#fff;border-color:var(--osc)}
.jr .leg{font-size:12.5px;color:var(--mut)}.jr .leg span{display:inline-block;width:14px;height:3px;vertical-align:middle;margin:0 4px 0 10px}
.jr .nota-pie{font-size:12.5px;color:var(--suave);margin-top:10px}.jr svg{max-width:100%;height:auto;display:block}
.jr details.plg > summary{cursor:pointer;list-style:none;font-weight:600;padding:10px 0;color:var(--osc)}.jr details.plg > summary::-webkit-details-marker{display:none}
@media(max-width:640px){.jr .graf text{font-size:19px}.jr{font-size:14.5px}.jr .sec{padding:16px 14px}.jr .hero{padding:14px}.jr .hero .t{font-size:22px}.jr .big{font-size:28px}
.jr .precio{grid-template-columns:minmax(0,1fr)}.jr .notabox{min-width:70px}.jr .notabox .n{font-size:26px}.jr .tr{grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)}.jr .tr .es{grid-column:1 / -1}}
"""


def ayuda(que, como=None, bueno=None, lectura=None):
    """Botón «?» con su explicación. Va dentro de un contenedor con position:relative."""
    p = [f"<p><b>Qué es.</b> {que}</p>"]
    if como:
        p.append(f"<p><b>Cómo se calcula.</b> {como}</p>")
    if bueno:
        p.append(f"<p><b>Cuándo es bueno.</b> {bueno}</p>")
    if lectura:
        p.append(f"<p><b>En esta empresa.</b> {lectura}</p>")
    return f'<button class="q" type="button" aria-label="Qué significa">?</button><div class="tip">{"".join(p)}</div>'


def _pill(color, txt):
    return f'<span class="pill {color}">{E(txt)}</span>'


def _val(k, mon=None):
    v = k["valor"]
    if k.get("caja_neta"):
        return "Caja neta"
    if v is None:
        return "No aplica" if (k.get("gris") or "").startswith("No aplica") else ("Descartado" if (k.get("gris") or "").startswith("Valor descartado") else "Sin dato")
    u = k.get("unidad")
    if u == "%":
        return es(v, pct=True)
    if u == "pp":
        return es(v, signo=True) + " pp"
    if u == "de 4":
        return f"{int(v)} de 4"
    return es(v)


def _fmt_fecha(d):
    if not d:
        return "Sin dato"
    a, m, dd = d[:10].split("-")
    return f"{dd}/{m}/{a}"


# ---------------------------------------------------------------- gráficos SVG
def _linea(xs, ys, x0, x1, y0, y1, W, H, pad):
    pts = []
    for x, y in zip(xs, ys):
        if y is None:
            continue
        px = pad[0] + (x - x0) / (x1 - x0 or 1) * (W - pad[0] - pad[2])
        py = pad[1] + (1 - (y - y0) / (y1 - y0 or 1)) * (H - pad[1] - pad[3])
        pts.append(f"{px:.1f},{py:.1f}")
    return " ".join(pts)


def _paso(y0, y1, n=4):
    bruto = (y1 - y0) / n or 1
    e = 10 ** math.floor(math.log10(bruto))
    return next(m * e for m in (1, 2, 2.5, 5, 10) if m * e >= bruto)


def _rango(vals, margen=0.05):
    a, b = min(vals), max(vals)
    d = (b - a) or abs(b) or 1
    a, b = a - d * margen, b + d * margen
    p = _paso(a, b)
    return math.floor(a / p) * p, math.ceil(b / p) * p


def _ejes_y(y0, y1, W, H, pad, fmt=None, n=4):
    out = []
    p = _paso(y0, y1, n)
    if fmt is None:
        fmt = lambda v: es(v, 0 if p >= 1 else (1 if p >= 0.1 else 2))
    v = math.ceil(y0 / p - 1e-9) * p
    while v <= y1 + 1e-9:
        py = pad[1] + (1 - (v - y0) / (y1 - y0)) * (H - pad[1] - pad[3])
        out.append(f'<line x1="{pad[0]}" x2="{W - pad[2]}" y1="{py:.1f}" y2="{py:.1f}" stroke="#ece6db"/>'
                   f'<text x="{pad[0] - 6}" y="{py + 4:.1f}" font-size="11" fill="#8a92a0" text-anchor="end">{fmt(v)}</text>')
        v += p
    return "".join(out)


def _ejes_x(fechas, W, H, pad, cada=None):
    n = len(fechas)
    out, vistos, ultimo = [], set(), -999
    for i, d in enumerate(fechas):
        k = d[:4] if cada == "año" else d[:7]
        if k in vistos:
            continue
        vistos.add(k)
        if cada != "año" and int(d[5:7]) % 3 != 1:
            continue
        px = pad[0] + i / max(n - 1, 1) * (W - pad[0] - pad[2])
        if px - ultimo < 66:
            continue
        ultimo = px
        lab = d[:4] if cada == "año" else f"{d[5:7]}/{d[2:4]}"
        out.append(f'<text x="{px:.1f}" y="{H - 6}" font-size="11" fill="#8a92a0" text-anchor="middle">{lab}</text>')
    return "".join(out)


def svg_precio(D):
    s, T = D["serie"], D["tecnicos"]
    fechas = [d for d, _ in s]
    c = [v for _, v in s]
    lv = [x["valor"] for x in T["soportes"] + T["resistencias"]]
    y0, y1 = _rango(c + lv)
    W, H, pad = 760, 320, (56, 14, 118, 30)
    xs = list(range(len(c)))
    o = [f'<svg class="graf" viewBox="0 0 {W} {H}" role="img" aria-label="Precio de 12 meses con medias, soportes y resistencias">',
         _ejes_y(y0, y1, W, H, pad), _ejes_x(fechas, W, H, pad)]
    for x in T["soportes"] + T["resistencias"]:
        py = pad[1] + (1 - (x["valor"] - y0) / (y1 - y0)) * (H - pad[1] - pad[3])
        col = "#15803d" if x["valor"] < D["precio"] else "#dc2626"
        o.append(f'<line x1="{pad[0]}" x2="{W - pad[2]}" y1="{py:.1f}" y2="{py:.1f}" stroke="{col}" stroke-dasharray="5 4" stroke-width="1.2"/>'
                 f'<text x="{W - pad[2] + 4}" y="{py + 4:.1f}" font-size="11" fill="{col}">{"Sop." if x["valor"] < D["precio"] else "Res."} {es(x["valor"], 2)}</text>')
    o.append(f'<polyline fill="none" stroke="#a78bfa" stroke-width="1.4" points="{_linea(xs, T["serie_s200"], 0, len(c) - 1, y0, y1, W, H, pad)}"/>')
    o.append(f'<polyline fill="none" stroke="#f59e0b" stroke-width="1.4" points="{_linea(xs, T["serie_s50"], 0, len(c) - 1, y0, y1, W, H, pad)}"/>')
    o.append(f'<polyline fill="none" stroke="#0f172a" stroke-width="1.8" points="{_linea(xs, c, 0, len(c) - 1, y0, y1, W, H, pad)}"/>')
    for i, lab in ((c.index(max(c)), f"Máx. {es(max(c), 2)}"), (c.index(min(c)), f"Mín. {es(min(c), 2)}")):
        px = pad[0] + i / (len(c) - 1) * (W - pad[0] - pad[2])
        py = pad[1] + (1 - (c[i] - y0) / (y1 - y0)) * (H - pad[1] - pad[3])
        o.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#0f172a"/><text x="{min(max(px, 60), W - pad[2] - 60):.1f}" y="{py - 8 if "Máx" in lab else py + 18:.1f}" font-size="11" fill="#0f172a" text-anchor="middle">{lab} · {_fmt_fecha(fechas[i])}</text>')
    o.append("</svg>")
    return "".join(o)


def svg_gauge(riesgo):
    W, H, cx, cy, R = 300, 200, 150, 140, 120

    def pt(v, r):
        a = math.pi * (1 - v / 100)
        return cx + r * math.cos(a), cy - r * math.sin(a)
    tramos = [(0, 30, "#15803d"), (30, 50, "#65a30d"), (50, 70, "#d97706"), (70, 100, "#dc2626")]
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Velocímetro de riesgo {riesgo} de 100">']
    for a, b, col in tramos:
        x0, y0 = pt(a, R)
        x1, y1 = pt(b, R)
        o.append(f'<path d="M{x0:.1f},{y0:.1f} A{R},{R} 0 0 1 {x1:.1f},{y1:.1f}" stroke="{col}" stroke-width="18" fill="none"/>')
    if riesgo is not None:
        x, y = pt(riesgo, R - 34)
        o.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#0f172a" stroke-width="4" stroke-linecap="round"/>'
                 f'<circle cx="{cx}" cy="{cy}" r="7" fill="#0f172a"/>')
    o.append(f'<text x="{cx}" y="{cy + 48}" font-size="34" font-weight="700" text-anchor="middle" fill="#0f172a" font-family="JetBrains Mono,monospace">{riesgo if riesgo is not None else "—"}</text>'
             f'<text x="30" y="{cy + 22}" font-size="12" fill="#8a92a0" text-anchor="middle">0</text><text x="{W - 30}" y="{cy + 22}" font-size="12" fill="#8a92a0" text-anchor="middle">100</text></svg>')
    return "".join(o)


def svg_per(h):
    s = h["serie"] + [["hoy", round(h["hoy"], 2)]]
    v = [x[1] for x in s]
    y0, y1 = _rango(v)
    W, H, pad = 760, 240, (56, 14, 16, 30)
    xs = list(range(len(v)))
    pm = pad[1] + (1 - (h["mediana"] - y0) / (y1 - y0)) * (H - pad[1] - pad[3])
    px = W - pad[2]
    py = pad[1] + (1 - (h["hoy"] - y0) / (y1 - y0)) * (H - pad[1] - pad[3])
    return (f'<svg class="graf" viewBox="0 0 {W} {H}" role="img" aria-label="PER mensual de 4 años frente a su mediana">'
            f'<rect x="{pad[0]}" y="{pad[1]}" width="{W - pad[0] - pad[2]}" height="{H - pad[1] - pad[3]}" fill="#fdf4e3"/>'
            + _ejes_y(y0, y1, W, H, pad) + _ejes_x([x[0] for x in h["serie"]] + [h["serie"][-1][0]], W, H, pad, "año")
            + f'<line x1="{pad[0]}" x2="{W - pad[2]}" y1="{pm:.1f}" y2="{pm:.1f}" stroke="#64748b" stroke-dasharray="6 5"/>'
            f'<polyline fill="none" stroke="#dc2626" stroke-width="2" points="{_linea(xs, v, 0, len(v) - 1, y0, y1, W, H, pad)}"/>'
            f'<circle cx="{px}" cy="{py:.1f}" r="5" fill="#dc2626"/></svg>')




def svg_spark(serie, sube):
    c = [v for _, v in serie]
    if len(c) < 2:
        return ""
    W, H = 420, 90
    lo, hi = min(c), max(c)
    pts = [(i / (len(c) - 1) * W, 6 + (1 - (v - lo) / ((hi - lo) or 1)) * (H - 12)) for i, v in enumerate(c)]
    linea = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    col = "#15803d" if sube else "#dc2626"
    fondo = "#e8f3ec" if sube else "#fbeaea"
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" style="width:100%;height:90px" role="img" aria-label="Precio de 12 meses">'
            f'<polygon fill="{fondo}" points="0,{H} {linea} {W},{H}"/><polyline fill="none" stroke="{col}" stroke-width="2" points="{linea}"/></svg>')


def svg_evol(m, meses, pid):
    s = m[-1 - meses:] if len(m) > meses else m
    p = [(x[1] / s[0][1] - 1) * 100 for x in s]
    y0, y1 = _rango(p + [0])
    W, H, pad = 760, 260, (92, 14, 16, 30)
    xs = list(range(len(s)))
    pz = pad[1] + (1 - (0 - y0) / (y1 - y0)) * (H - pad[1] - pad[3])
    col = "#15803d" if p[-1] >= 0 else "#dc2626"
    return (f'<svg class="graf" id="{pid}" viewBox="0 0 {W} {H}" role="img" aria-label="Rentabilidad acumulada del precio">'
            + _ejes_y(y0, y1, W, H, pad, lambda v: es(v, 0) + " %") + _ejes_x([x[0] for x in s], W, H, pad, "año" if meses > 24 else None)
            + f'<line x1="{pad[0]}" x2="{W - pad[2]}" y1="{pz:.1f}" y2="{pz:.1f}" stroke="#94a3b8"/>'
            f'<polyline fill="none" stroke="{col}" stroke-width="2.2" points="{_linea(xs, p, 0, len(s) - 1, y0, y1, W, H, pad)}"/></svg>')


def svg_hist_nota(h):
    v = [x[1] for x in h]
    W, H = 160, 34
    lo, hi = min(v) - 2, max(v) + 2
    pts = " ".join(f"{i / (len(v) - 1) * W:.1f},{3 + (1 - (x - lo) / (hi - lo)) * (H - 6):.1f}" for i, x in enumerate(v))
    return f'<svg viewBox="0 0 {W} {H}" style="width:160px;height:34px;display:inline-block;vertical-align:middle"><polyline fill="none" stroke="#1e3a8a" stroke-width="2" points="{pts}"/></svg>'


# ---------------------------------------------------------------- ayudas compuestas
def ayuda_tarjeta(k):
    como = COMO[k["id"]]
    if k.get("formula"):
        como += f' En esta empresa: <span class="m">{E(k["formula"])}</span>.'
    if k.get("gris") and k["gris"] not in ("Sin dato",):
        como += f" {E(k['gris'])}"
    return ayuda(QUE[k["id"]], como, BUENO[k["id"]])


def ayuda_area(a, D):
    i = a["id"]
    if i.startswith("bloque_"):
        b = i[7:]
        nb = dict((x, y) for x, y, _ in BLOQUES)[b]
        return ayuda(f"La nota del bloque {nb}: resume sus 6 tarjetas en un número de 0 a 100.",
                     "Cada tarjeta vale 100 si es verde, 50 si es ámbar y 0 si es roja. Se hace la media; las grises no cuentan.",
                     "Excelente 75 o más · buena de 50 a 74 · aceptable de 25 a 49 · débil por debajo de 25.")
    if i == "tendencia":
        s = a["senales"]
        si = lambda x: "sí" if x else "no"
        return ayuda("Si la cotización va hacia arriba o hacia abajo a medio y largo plazo.",
                     f"Cuenta 3 señales: precio por encima de la media de 200 sesiones ({si(s[0])}), media de 50 por encima de la de 200 ({si(s[1])}) "
                     f"y media de 200 subiendo frente a hace un mes ({si(s[2])})." + (f" En un año el precio ha variado un {a['r1']}." if a.get("r1") else ""),
                     "3 de 3, buena · 0 de 3, mala · 1 o 2, mixta. No puntúa en la nota.")
    if i == "dividendo":
        dv = D["dividendo"]
        return ayuda("Lo que te paga en dividendos al año por cada 100 invertidos al precio de hoy.",
                     f"Dividendos de los últimos 12 meses ({es(dv['dpa'], 2)} {E(D['moneda'])}) / precio ({es(D['precio'], 2)}).",
                     "Bueno desde el 3 % · escaso por debajo del 1 %. No puntúa en la nota.")
    if i == "piotroski":
        return ayuda("Una nota de 0 a 9 que mide si las cuentas mejoran o empeoran frente al año anterior.",
                     "9 preguntas de sí o no sobre beneficio, caja, deuda, emisión de acciones y eficiencia. Cada sí suma 1 punto.",
                     "De 7 a 9, fuerte · de 4 a 6, media · de 0 a 3, débil. No puntúa en la nota.")
    if i == "historia":
        return ayuda("Si el PER de hoy es alto o bajo comparado con su propio PER de los últimos 4 años.",
                     "PER de hoy / mediana del PER mensual de 4 años − 1.",
                     "Más de un 10 % por debajo, más barata que de costumbre · más de un 10 % por encima, más cara. No puntúa en la nota.")
    return ""


AY_NOTA = ayuda("Resume las 18 tarjetas en un número de 0 a 100. Más es mejor.",
                "Cada tarjeta vale 100 si es verde, 50 si es ámbar y 0 si es roja. Se hace la media de cada bloque y se pondera: "
                "valoración 35 %, salud financiera 35 % y crecimiento 30 %.",
                "El riesgo es 100 − nota: bajo hasta 30, moderado hasta 50, elevado hasta 70 y alto por encima de 70.")


# ---------------------------------------------------------------- secciones
def sec_resumen(D):
    mon, T = D["moneda"], D["tecnicos"]
    r1 = (D["evolucion"] or {}).get("rent", {}).get(1, {})
    r12 = r1.get("precio")
    pos52 = (D["precio"] - T["min52"]) / (T["max52"] - T["min52"]) * 100 if T["max52"] > T["min52"] else 50
    chips = "".join(f'<span class="chip">{E(x)}</span>' for x in (D["bolsa"], D["sector_es"], D["industria_es"], mon) if x)
    prox = f'<span class="chip" style="background:#fff;color:#0f172a;border:1px solid #e3ddd2">Resultados: {_fmt_fecha(D["proximos"])}</span>' if D["proximos"] else ""
    o = [f'<section class="sec" id="resumen" style="padding:0;border:0;background:transparent">',
         f'<div class="hero"><div class="notabox"><div class="n m">{D["nota"] if D["nota"] is not None else "—"}</div><div class="l">NOTA</div>{AY_NOTA}</div>'
         f'<div style="min-width:0"><div class="t">{E(D["nombre"] or D["ticker"])} <span class="chip m" style="font-size:13px">{E(D["ticker"])}</span></div><div>{chips}</div></div></div>',
         f'<div class="precio"><div><div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:flex-start">'
         f'<div><span class="big m">{es(D["precio"], 2)}</span> <span class="m" style="color:var(--mut)">{E(mon)}</span></div>{prox}</div>'
         + (f'{_pill("verde" if r12 >= 0 else "rojo", ("▲ " if r12 >= 0 else "▼ ") + es(r12, pct=True, signo=True))} '
            f'<span style="color:var(--mut);font-size:13px">en un año (desde el {_fmt_fecha(r1.get("desde"))})</span>' if r12 is not None else "")
         + f'<div style="color:var(--mut);font-size:13px;margin-top:4px">Cierre del {_fmt_fecha(D["corte"])} · Capitalización {millones(D["mcap"], mon)}<br>'
         f'Cuentas hasta el {_fmt_fecha(D["fecha_cuentas"])}</div>'
         f'<div class="m" style="display:flex;justify-content:space-between;font-size:12px;color:var(--mut);margin-top:12px"><span>Mín. 52 sem. {es(T["min52"], 2)}</span><span>Máx. {es(T["max52"], 2)}</span></div>'
         f'<div class="bar52"><i style="left:calc({pos52:.1f}% - 1px)"></i></div></div>'
         f'<div>{svg_spark(D["serie"], (r12 or 0) >= 0)}<div class="leg" style="text-align:right">Cierres diarios de 12 meses</div></div></div>']
    for a in D["avisos"]:
        o.append(f'<div class="aviso">⚠ {E(a)}</div>')
    if D.get("descripcion"):
        o.append(f'<div class="sec"><h2>¿A qué se dedica?</h2><p style="margin:6px 0 0">{E(D["descripcion"])}</p>'
                 + ('' if D.get("descripcion_traducida") else '<p class="nota-pie">Texto original de Yahoo: no se ha podido traducir.</p>')
                 + '</div>')
    if D["areas"] or D["esencial"]:
        o.append('<div class="sec"><div class="eh"><h2>Lo esencial</h2><span>por áreas</span></div>')
        for a in D["areas"]:
            ic = {"ok": "✓", "ko": "✕", "neutro": "–"}[a["estado"]]
            o.append(f'<div class="ese"><span class="ic {a["estado"]}">{ic}</span><span class="tx">{E(a["texto"])}'
                     + ('' if a["puntua"] else '<span class="np">no puntúa</span>')
                     + f'</span><span class="vl">{E(a["valor"])}</span>{ayuda_area(a, D)}</div>')
        if D["esencial"]:
            o.append('<div class="sep"></div><div class="eh"><h3 style="margin:0">Lo que más pesa en la nota</h3><span>tarjetas en verde y en rojo</span></div>')
            for e in D["esencial"]:
                k = D["tarjetas"][e["id"]]
                o.append(f'<div class="ese"><span class="ic {"ok" if e["ok"] else "ko"}">{"✓" if e["ok"] else "✕"}</span>'
                         f'<span class="tx">{E(e["texto"])}</span><span class="vl">{_val(k)}</span>{ayuda_tarjeta(k)}</div>')
        o.append("</div>")
    tr_col = {"Riesgo bajo": "verde", "Riesgo moderado": "verde", "Riesgo elevado": "ambar", "Riesgo alto": "rojo"}.get(D["tramo"], "gris")
    hist = D.get("historial") or []
    evo = ""
    if len(hist) >= 2:
        d = hist[-1][1] - hist[0][1]
        evo = (f'<div style="margin-top:10px;font-size:14px"><b>Evolución de la nota:</b> <span class="m">{hist[0][1]} → {hist[-1][1]}</span> '
               f'{_pill("verde" if d > 0 else ("rojo" if d < 0 else "gris"), ("▲ " if d > 0 else ("▼ " if d < 0 else "")) + es(abs(d), 0))} '
               f'<span style="color:var(--mut);font-size:13px">desde el {_fmt_fecha(hist[0][0])} · {len(hist)} análisis</span><br>{svg_hist_nota(hist)}</div>')
    elif len(hist) == 1:
        evo = f'<div class="nota-pie">Primer análisis guardado ({_fmt_fecha(hist[0][0])}). La evolución de la nota aparecerá a partir del segundo día.</div>'
    o.append('<div class="sec"><div class="grid" style="align-items:center"><div style="width:100%;max-width:320px;margin:0 auto">' + svg_gauge(D["riesgo"]) + '</div><div>'
             f'<div class="sub" style="margin:0">Riesgo de 0 a 100 (100 = máximo) · riesgo = 100 − nota</div><h2>{_pill(tr_col, D["tramo"] or "Sin nota")}</h2>'
             f'<p style="margin:8px 0">{E(D["veredicto"] or "No hay datos suficientes para calcular la nota.")}</p>'
             + ('<p class="aviso" style="margin:6px 0">Confianza baja: algún bloque tiene menos de 4 tarjetas con dato y se ha excluido.</p>' if D["confianza_baja"] else "")
             + f'{evo}</div></div></div>')
    kpis = {"val": ["per_fwd", "rent_fcf", "potencial"], "sal": ["dn_ebitda", "roic"], "cre": ["ventas_ia"]}
    G = {g["id"]: g for g in D["glosario"]}
    o.append('<div class="sec"><h2>Los 6 indicadores clave</h2><p class="sub">Pulsa «?» para ver qué mide cada uno y cómo se calcula</p><div class="grid">')
    for b, nb, w in BLOQUES:
        nota, et = D["notas"][b], D["etiquetas"][b]
        o.append(f'<div class="bloque" style="border-top-color:{COL_BLOQUE[b]}"><div class="bh"><b>{nb} · {int(w * 100)} %</b>'
                 f'<span>{_pill(COL_ETQ.get(et, "gris"), et or "Sin nota")} <span class="m">{nota if nota is not None else "—"}</span></span></div>')
        for i in kpis[b]:
            k, g = D["tarjetas"][i], G[i]
            como = E(g["formula"]) + (f' = <span class="m">{E(g["con_cifras"])}</span>' if g["con_cifras"] else "")
            o.append(f'<div class="kpi"><span>{E(k["nombre"])}</span><span style="display:flex;align-items:center">{_pill(k["color"], _val(k))}'
                     f'{ayuda(E(g["que"]), como, BUENO[i], E(g["lectura"]))}</span></div>')
        o.append("</div>")
    o.append("</div>")
    c = D["consenso"]
    o.append(f'<p class="nota-pie">Consenso: precio objetivo {es(c["objetivo"], 2)} {E(mon)} · {c["analistas"] or "sin"} analistas · '
             f'Yahoo Finance · fecha de actualización no publicada' + (" · <b>consenso escaso</b>" if c["escaso"] else "") + "</p>")
    o.append('<h3 style="margin-top:16px">Cómo se forma la nota</h3>')
    for b, nb, _ in BLOQUES:
        n, w = D["notas"][b], (D.get("pesos") or {}).get(b, 0)
        ap = n * w if n is not None else 0
        o.append(f'<div style="display:flex;justify-content:space-between;font-size:14px;margin-top:8px"><span>{nb} · nota <span class="m">{n if n is not None else "—"}</span> · peso {es(w * 100, 0)} %</span>'
                 f'<span class="m">aporta {es(ap)}</span></div><div class="barra"><i style="width:{n or 0}%;background:{COL_BLOQUE[b]}"></i></div>')
    o.append("</div></section>")
    return "".join(o)


def _tile(lab, val, ay, extra="", cls=""):
    return f'<div class="tile{cls}"><div class="l" style="display:flex;justify-content:space-between;align-items:center">{lab}{ay}</div><div class="v m">{val}</div>{extra}</div>'


def sec_historia(D):
    h = D["historia"]
    o = ['<section class="sec" id="historia"><h2>¿Cara frente a su propia historia?</h2>']
    if not h or not h.get("ok"):
        return o[0] + f'<p class="sub">Sin dato: {E((h or {}).get("motivo", "Yahoo no publica datos suficientes"))}.</p></section>'
    col = "rojo" if h["dif"] > 10 else ("verde" if h["dif"] < -10 else "gris")
    mon = E(D["moneda"])
    o.append(f'<p class="sub">Su PER mes a mes desde {_fmt_fecha(h["desde"])[3:]} · No puntúa</p><div class="g2">'
             + _tile("PER hoy", es(h["hoy"]), ayuda("Cuántas veces paga el precio de hoy el beneficio por acción del último ejercicio publicado.",
                                                     f'Precio ({es(D["precio"], 2)}) / BPA de {h["ejercicio"][:4]} ({es(h["bpa"], 2)} {mon}).'))
             + _tile("Mediana de 4 años", es(h["mediana"]), ayuda("El PER típico de la empresa en los últimos 4 años: la mitad de los meses estuvo por encima y la otra mitad por debajo.",
                                                                    "Mediana de los PER mensuales. Cada mes: precio de cierre / BPA del último ejercicio publicado entonces (90 días después del cierre del ejercicio)."))
             + _tile("Rango", f'{es(h["min"])} – {es(h["max"])}', ayuda("El PER más bajo y el más alto de los últimos 4 años, incluido el de hoy."))
             + _tile("Frente a su mediana", es(h["dif"], 0, pct=True, signo=True), ayuda("Cuánto más alto o más bajo está el PER de hoy que su mediana.",
                                                                                       "PER de hoy / mediana − 1.", "Más de un 10 % por debajo, más barata que de costumbre · más de un 10 % por encima, más cara."))
             + f'</div><div style="margin-top:14px">{svg_per(h)}</div>'
             f'<p style="margin:10px 0 4px">Hoy cotiza {_pill(col, h["veredicto"])}: su PER está un {es(abs(h["dif"]), 0)} % '
             f'{"por encima" if h["dif"] >= 0 else "por debajo"} de su mediana de los últimos 4 años.</p>'
             f'<p class="nota-pie">Que esté más barata que de costumbre no significa que vaya a subir: puede que el mercado espere menos beneficio.</p></section>')
    return "".join(o)


def sec_evolucion(D):
    ev = D["evolucion"]
    o = ['<section class="sec" id="evolucion"><h2>Evolución y rentabilidad</h2>']
    if not ev:
        return o[0] + '<p class="sub">Sin dato: Yahoo no tiene 13 meses de cotización.</p></section>'
    disp = [(a, m) for a, m in ((1, 12), (3, 36), (5, 60)) if len(ev["serie"]) > m and a in ev["rent"]]
    o.append(f'<p class="sub">Cuánto ha subido o bajado el precio, en {E(D["moneda"])}, sin dividendos</p>'
             '<div class="per" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px">'
             + "".join(f'<button type="button" data-p="ev{a}" class="{"on" if a == disp[-1][0] else ""}">{a} año{"s" if a > 1 else ""}</button>' for a, _ in disp)
             + '</div>')
    for a, m in disp:
        o.append(f'<div class="evp" data-k="ev{a}" style="{"" if a == disp[-1][0] else "display:none"}">{svg_evol(ev["serie"], m, f"ev{a}")}</div>')
    o.append('<h3 style="margin-top:16px">Rentabilidad anual compuesta</h3><div class="g2">')
    for a, _ in disp:
        r = ev["rent"][a]
        osc = a == disp[-1][0]
        ay = ayuda("Lo que ha subido o bajado el precio de media cada año en ese plazo, sin dividendos.",
                   f'(Precio de hoy / precio del {_fmt_fecha(r["desde"])}) elevado a 1/{a}, menos 1.' if a > 1 else f'Precio de hoy / precio del {_fmt_fecha(r["desde"])} − 1.',
                   "Solo describe lo ocurrido; no predice la rentabilidad futura.")
        o.append(f'<div class="tile{" osc" if osc else ""}"><div class="l" style="display:flex;justify-content:space-between;align-items:center">{a} año{"s · al año" if a > 1 else ""}{ay}</div>'
                 f'<div class="v m" style="color:{"inherit" if osc else ("var(--v)" if r["anual_precio"] >= 0 else "var(--r)")}">{es(r["anual_precio"], pct=True, signo=True)}</div>'
                 f'<div class="l">Acumulada {es(r["precio"], 0, pct=True, signo=True)}</div></div>')
    o.append("</div>")
    p, z = D["piotroski"], D["tarjetas"]["altman"]
    o.append('<div class="grid" style="margin-top:12px">')
    if z["valor"] is not None:
        zt = "Zona segura" if z["valor"] > 3 else ("Zona gris" if z["valor"] >= 1.8 else "Zona de riesgo")
        o.append(f'<div class="tile"><div style="display:flex;justify-content:space-between;align-items:center"><b>Solidez del balance · <span class="m">Altman Z {es(z["valor"])}</span></b>{ayuda_tarjeta(z)}</div>'
                 f'{_pill(z["color"], zt)}<div class="l" style="margin-top:4px">Riesgo de quiebra según el balance y los resultados. Forma parte de la nota.</div></div>')
    if p:
        col = {"Fuerte": "verde", "Media": "ambar", "Débil": "rojo"}.get(p["etiqueta"], "gris")
        o.append(f'<div class="tile"><div style="display:flex;justify-content:space-between;align-items:center"><b>Calidad de las cuentas · <span class="m">Piotroski F {p["puntos"]}/{p["evaluables"]}</span></b>'
                 + ayuda_area({"id": "piotroski"}, D) + f'</div>{_pill(col, p["etiqueta"] or "Incompleto")}'
                 f'<div class="l" style="margin-top:4px">{p["ejercicio"]} frente a {p["anterior"]}. No puntúa.</div><details class="plg"><summary>Ver las 9 pruebas</summary><div style="font-size:13.5px">'
                 + "".join(f'{"✓" if x["ok"] else ("✕" if x["ok"] is False else "·")} {E(x["nombre"])}{"" if x["ok"] is not None else " (sin dato)"}<br>' for x in p["pruebas"])
                 + "</div></details></div>")
    o.append(f'</div><p class="nota-pie">Rentabilidades con el cierre diario del mismo día de hace 1, 3 y 5 años. Gráfico con cierres mensuales. Datos hasta el {_fmt_fecha(D["corte"])}.</p></section>')
    return "".join(o)


def sec_valor(D):
    V, P, mon = D["valor_justo"], D["precio"], D["moneda"]
    g = V["g"]
    gtxt = f'{es(g * 100)} %' if g is not None else "sin dato"
    AY = {"graham": ayuda("Valor según la fórmula clásica de Benjamin Graham, a partir del beneficio y de su crecimiento.",
                          f'BPA de 12 meses ({es((V["graham"] or {}).get("eps"), 2)}) × (8,5 + 2 × crecimiento {gtxt}).',
                          "Orientativo. Por encima del precio sugiere margen; no es una recomendación."),
          "dcf": ayuda("Lo que vale hoy la caja libre que generaría la empresa en los próximos 10 años y después.",
                       f'Flujo de caja libre por acción de 12 meses ({es((V["dcf"] or {}).get("fcf_accion"), 2)}); crece al {gtxt} 5 años y a la mitad otros 5; '
                       'crecimiento perpetuo 2,5 %; descuento 9 % (el rango usa 10 % y 8 %).', "Orientativo y muy sensible a los supuestos."),
          "dividendos": ayuda("Lo que valen hoy los dividendos futuros si crecen un 2,5 % al año.",
                              "Dividendo de 12 meses × 1,025 / (9 % − 2,5 %). Solo si reparte al menos el 20 % del beneficio.",
                              "Orientativo. Solo tiene sentido en empresas que reparten buena parte del beneficio.")}
    o = [f'<section class="sec" id="valor"><h2>Valor justo orientativo · {E(mon)}</h2><p class="sub">No puntúa. Tres fórmulas clásicas con supuestos fijos</p><div class="g2">']
    for k, nom in (("graham", "Graham"), ("dcf", "Flujo de caja (DCF)"), ("dividendos", "Dividendos")):
        x = V[k]
        if x["valor"] is None:
            o.append(_tile(nom, "—", AY[k], f'<div class="l">{E(x["motivo"])}</div>'))
        else:
            rng = f'<div class="l m">{es(x["bajo"], 2)} – {es(x["alto"], 2)}</div>' if "bajo" in x else ""
            o.append(_tile(nom, es(x["valor"], 2), AY[k], _pill("verde" if x["dist"] >= 0 else "rojo", ("▲ " if x["dist"] >= 0 else "▼ ") + es(x["dist"], 0, pct=True, signo=True) + " vs precio") + rng))
    o.append(f'<div class="tile osc"><div class="l">Precio</div><div class="v m">{es(P, 2)}</div><div class="l">último cierre</div></div></div>')
    gy = V.get("g_yahoo")
    o.append(f'<p class="nota-pie">Crecimiento usado: {gtxt}' + (f' (los analistas esperan {es(gy * 100)} % para el ejercicio fiscal siguiente; se limita entre 0 % y 10 %)' if gy is not None else "")
             + '. Descuento 9 %, crecimiento perpetuo 2,5 %. Son orientativos: cambian mucho con los supuestos y no son una recomendación.</p></section>')
    return "".join(o)


def _card(k):
    av = "".join(f'<span class="warn">{E(a)}</span>' for a in k["avisos"])
    gris = k.get("gris") if k["color"] == "gris" and k.get("gris") not in (None, "Sin dato") else None
    return (f'<div class="card"><div class="top"><span class="nm">{E(k["nombre"])}{ayuda_tarjeta(k)}</span>{_pill(k["color"], _val(k))}</div>'
            + (f'<div class="fr">{E(k["frase"])}</div>' if k.get("frase") else "")
            + (f'<div class="fr" style="color:var(--mut)">{E(gris)}</div>' if gris else "")
            + (f'<div>{av}</div>' if av else "")
            + f'<div class="md">{E(k["fuente"])} · {_fmt_fecha(k["fecha"])}</div></div>')


def sec_nota(D):
    o = ['<section class="sec" id="nota"><h2>Base de la nota</h2><p class="sub">Las 18 tarjetas que calculan la nota. Verde 100, ámbar 50, rojo 0; las grises no cuentan. Pulsa cada bloque para abrirlo</p>']
    for b, nb, w in BLOQUES:
        n, et = D["notas"][b], D["etiquetas"][b]
        cnt = {c: sum(1 for i in ORDEN[b] if D["tarjetas"][i]["color"] == c) for c in ("verde", "ambar", "rojo", "gris")}
        res = " · ".join(f"{cnt[c]} {t if cnt[c] > 1 else s}" for c, t, s in (("verde", "verdes", "verde"), ("ambar", "ámbar", "ámbar"),
                                                                              ("rojo", "rojas", "roja"), ("gris", "grises", "gris")) if cnt[c])
        o.append(f'<details class="blq"><summary style="border-left-color:{COL_BLOQUE[b]}"><span><b>{nb} · {int(w * 100)} %</b><br>'
                 f'<span style="font-size:13px;color:var(--mut)">{res}</span></span>'
                 f'<span style="display:flex;align-items:center;gap:8px">{_pill(COL_ETQ.get(et, "gris"), et or "Excluido")}<span class="m" style="font-weight:700">{n if n is not None else "—"}</span><span class="fl">▾</span></span></summary>'
                 '<div class="in"><div class="grid">' + "".join(_card(D["tarjetas"][i]) for i in ORDEN[b]) + "</div></div></details>")
    o.append('<p class="nota-pie">Etiqueta de bloque: 75 o más, Excelente; 50-74, Buena; 25-49, Aceptable; menos de 25, Débil. '
             'Un valor justo en un límite cuenta como ámbar. Crecimientos de más del 300 % llevan el aviso «Base baja» sin cambiar el color.</p></section>')
    return "".join(o)


def sec_cuentas(D):
    S = D["senales"]
    o = ['<section class="sec" id="cuentas"><h2>Lo que dicen sus cuentas</h2>']
    if not S:
        return o[0] + '<p class="sub">Sin dato: Yahoo no publica cuentas anuales suficientes.</p></section>'
    n = {t: sum(1 for s in S if s["tipo"] == t) for t in ("favor", "contra", "contexto")}
    o.append('<p class="sub">Señales de sus cuentas anuales · No puntúa</p><p>'
             + " ".join(f'<span class="chip {t}">{n[t]} {lab}</span>' for t, lab in (("favor", "a favor"), ("contra", "en contra"), ("contexto", "contexto")) if n[t]) + "</p>")
    for s in S:
        lab = {"favor": "A FAVOR", "contra": "EN CONTRA", "contexto": "CONTEXTO"}[s["tipo"]]
        o.append(f'<div class="sen"><div style="display:flex;justify-content:space-between;align-items:center;gap:8px"><span><span class="tg {s["tipo"]}">{lab}</span>'
                 f'<b>{E(s["texto"])}</b></span>{ayuda(E(s["por_que"]))}</div></div>')
    o.append('<p class="nota-pie">Reglas fijas sobre las cuentas publicadas, iguales para todas las empresas. No forman parte de la nota ni son una recomendación.</p></section>')
    return "".join(o)


AY_TEC = {
    "sma": ("El precio medio de las últimas {n} sesiones.", "Suma de los {n} últimos cierres / {n}. Distancia = precio / media − 1.",
            "Precio por encima de la media: tendencia alcista en ese plazo."),
    "cruce": ("Si la media de 50 sesiones está por encima o por debajo de la de 200.", "Se comparan las dos medias cada día; el cruce es el día en que cambian de posición.",
              "Media de 50 por encima de la de 200: tendencia de fondo alcista."),
    "macd": ("Mide si el impulso del precio se acelera o se frena.", "MACD = media exponencial de 12 sesiones − la de 26. Señal = media exponencial de 9 sesiones del MACD. Histograma = MACD − señal.",
             "MACD por encima de la señal: impulso alcista."),
    "rsi": ("Mide si la subida o la bajada reciente ha sido muy fuerte.", "Compara las subidas y bajadas medias de las últimas 14 {u} con el suavizado de Wilder, en una escala de 0 a 100.",
            "Por encima de 70, sobrecompra · por debajo de 30, sobreventa · de 30 a 70, neutral."),
    "rent": ("Cuánto ha subido o bajado el precio en ese plazo.", "Precio de hoy / precio de hace {n} sesiones − 1.", "Solo describe lo ocurrido; no predice."),
    "ytd": ("Cuánto ha subido o bajado el precio desde el 1 de enero.", "Precio de hoy / último cierre del año anterior − 1.", None),
    "max": ("El cierre más alto de los últimos 12 meses.", "Distancia = precio / máximo − 1.", None),
    "min": ("El cierre más bajo de los últimos 12 meses.", "Distancia = precio / mínimo − 1.", None),
    "sr": ("Un precio donde la cotización ha girado antes y puede volver a frenarse.",
           "Cierre más bajo (soporte) o más alto (resistencia) de las 10 sesiones anteriores y las 10 posteriores. Los niveles a menos de un 2 % se agrupan en su media.",
           "Soporte: posible freno a las caídas · resistencia: posible freno a las subidas."),
    "vol": ("Cuánto se mueve el precio en un año típico.", "Desviación típica de los rendimientos diarios × √252.", "Más volatilidad, más riesgo de movimientos bruscos."),
    "osc": ("Lo que suele moverse el precio en un día normal.", "Desviación típica de los rendimientos diarios × precio.", None)}


def _ay_tec(k, **f):
    q, c, b = AY_TEC[k]
    return ayuda(q.format(**f), c.format(**f) if c else None, b)


def sec_tecnico(D):
    T = D["tecnicos"]

    def est_rsi(v):
        return "Sin dato" if v is None else ("Sobrecompra" if v > 70 else ("Sobreventa" if v < 30 else "Neutral"))
    F = []
    for n in (20, 50, 200):
        d = T[f"dist_sma{n}"]
        F.append((f"Media {n} sesiones", es(T[f"sma{n}"], 2), (es(d, pct=True, signo=True) + " · " + ("precio por encima" if d >= 0 else "precio por debajo")) if d is not None else "Sin dato", _ay_tec("sma", n=n)))
    F.append(("Cruce de medias 50/200", "", f'{T["cruce_estado"] or "Sin dato"} · {("último cruce " + _fmt_fecha(T["cruce_fecha"])) if T["cruce_fecha"] else "sin cruce en 12 meses"}', _ay_tec("cruce")))
    F.append(("MACD (12, 26, 9)", f'{es(T["macd"], 2)} / {es(T["senal"], 2)}', f'{T["macd_estado"] or "Sin dato"}' + (f' · cruce {_fmt_fecha(T["macd_cruce"])}' if T["macd_cruce"] else ""), _ay_tec("macd")))
    F.append(("RSI 14 diario", es(T["rsi_d"]), est_rsi(T["rsi_d"]), _ay_tec("rsi", u="sesiones")))
    F.append(("RSI 14 semanal", es(T["rsi_s"]), est_rsi(T["rsi_s"]), _ay_tec("rsi", u="semanas")))
    for k, nom, n in (("r1m", "Rentabilidad 1 mes", 21), ("r3m", "Rentabilidad 3 meses", 63), ("r6m", "Rentabilidad 6 meses", 126)):
        F.append((nom, es(T[k], pct=True, signo=True) if T[k] is not None else "Sin dato", "", _ay_tec("rent", n=n)))
    F.append(("En lo que va de año", es(T["ytd"], pct=True, signo=True) if T["ytd"] is not None else "Sin dato", "", _ay_tec("ytd")))
    F.append(("Máximo 52 semanas", es(T["max52"], 2), f'{es(T["dist_max52"], pct=True, signo=True)} · {_fmt_fecha(T["max52_f"])}', _ay_tec("max")))
    F.append(("Mínimo 52 semanas", es(T["min52"], 2), f'{es(T["dist_min52"], pct=True, signo=True)} · {_fmt_fecha(T["min52_f"])}', _ay_tec("min")))
    for i, x in enumerate(T["resistencias"]):
        F.append((f"Resistencia {i + 1}", es(x["valor"], 2), f'{es(x["dist"], pct=True, signo=True)} · {_fmt_fecha(x["fecha"])}', _ay_tec("sr")))
    if not T["resistencias"]:
        F.append(("Resistencia", "", "Sin resistencia en 12 meses", _ay_tec("sr")))
    for i, x in enumerate(T["soportes"]):
        F.append((f"Soporte {i + 1}", es(x["valor"], 2), f'{es(x["dist"], pct=True, signo=True)} · {_fmt_fecha(x["fecha"])}', _ay_tec("sr")))
    if not T["soportes"]:
        F.append(("Soporte", "", "Sin soporte en 12 meses", _ay_tec("sr")))
    F.append(("Volatilidad anualizada", es(T["vol"], pct=True), "12 meses", _ay_tec("vol")))
    F.append(("Oscilación diaria típica", f'{es(T["osc"], 2)} {E(D["moneda"])}', "", _ay_tec("osc")))
    filas = "".join(f'<div class="tr"><span style="display:flex;align-items:center">{a}{ay}</span><span class="vv">{b}</span><span class="es">{c}</span></div>' for a, b, c, ay in F)
    return ('<section class="sec" id="tecnico"><h2>Precio y técnicos</h2><p class="sub">Cierres diarios de 12 meses · No puntúa</p>'
            + svg_precio(D) + '<div class="leg" style="margin:6px 0 4px"><span style="background:#0f172a"></span>Precio<span style="background:#f59e0b"></span>Media 50'
            '<span style="background:#a78bfa"></span>Media 200<span style="background:#15803d"></span>Soporte<span style="background:#dc2626"></span>Resistencia</div>'
            f'<details class="plg"><summary>Ver los {len(F)} indicadores técnicos ▾</summary>{filas}</details>'
            '<p class="nota-pie">Las fechas de presentación de resultados no se marcan en el gráfico: Yahoo solo da la fecha de cierre del trimestre.</p></section>')


def sec_resultados(D):
    t, mon = D["tendencia"], D["moneda"]
    o = [f'<section class="sec" id="resultados"><h2>Resultados</h2><p class="sub">Últimos {len(t["filas"])} {t["periodo"]}</p>']
    if t["periodo"] != "trimestres":
        o.append('<p class="aviso">Yahoo no publica trimestres de esta empresa: se muestran ejercicios anuales.</p>')
    o.append('<div class="tw"><table><tr><th>Periodo</th><th class="n">Ventas</th><th class="n">BPA</th><th class="n">Margen op.</th><th class="n">FCF</th></tr>')
    for f in t["filas"]:
        o.append(f'<tr><td>{_fmt_fecha(f["fecha"])}</td><td class="n">{millones(f["ventas"], "")}</td><td class="n">{es(f["bpa"], 2)}</td>'
                 f'<td class="n">{es(f["margen_op"], pct=True)}</td><td class="n">{millones(f["fcf"], "")}</td></tr>')
    o.append(f'</table></div><p class="nota-pie">Cifras en {E(mon)}. FCF = flujo operativo − inversiones. BPA ajustado por splits.</p>')
    u = D["ultima"]
    if u:
        sor = (u["real"] / u["est"] - 1) * 100 if u["est"] else None
        o.append(f'<h3 style="margin-top:14px">Última entrega (trimestre cerrado el {_fmt_fecha(u["fecha"])})</h3>'
                 f'<p>BPA real <span class="m">{es(u["real"], 2)}</span> frente a <span class="m">{es(u["est"], 2)}</span> esperado'
                 + (f' {_pill("verde" if u["real"] > u["est"] else "rojo", es(sor, pct=True, signo=True))}' if sor is not None else "")
                 + '. Ventas frente a consenso: sin dato. Cambios en la guía: sin dato (requieren leer documentos).</p>')
    else:
        o.append('<h3 style="margin-top:14px">Última entrega</h3><p>Sin dato: Yahoo no publica el historial de BPA frente a lo esperado.</p>')
    o.append(f'<h3 style="margin-top:14px">Próxima fecha de resultados</h3><p>{_fmt_fecha(D["proximos"]) if D["proximos"] else "Sin dato"}'
             f'{" · según Yahoo; puede ser una fecha estimada" if D["proximos"] else ""}</p></section>')
    return "".join(o)


def resumen_texto(D):
    T = D["tecnicos"]
    L = [f"{D['nombre']} ({D['ticker']}) · fecha de corte {_fmt_fecha(D['corte'])} · cuentas hasta {_fmt_fecha(D['fecha_cuentas'])}",
         f"Nota {D['nota']} · Riesgo {D['riesgo']} · {D['tramo']}: {D['veredicto']}" + (" · Confianza baja" if D["confianza_baja"] else ""), "",
         "Lo esencial:"]
    for a in D["areas"]:
        L.append(f"  {'✓' if a['estado'] == 'ok' else ('✕' if a['estado'] == 'ko' else '–')} {a['texto']}: {a['valor']}{'' if a['puntua'] else ' (no puntúa)'}")
    L.append("")
    for b, nb, _ in BLOQUES:
        L.append(f"{nb} (nota {D['notas'][b]}):")
        for i in ORDEN[b]:
            k = D["tarjetas"][i]
            L.append(f"  {k['nombre']}: {_val(k)} [{TXT_COLOR[k['color']]}]")
    L += ["", f"RSI diario: {es(T['rsi_d'])}",
          f"Precio frente a media 50: {es(T['dist_sma50'], pct=True, signo=True) if T['dist_sma50'] is not None else 'Sin dato'}",
          f"Precio frente a media 200: {es(T['dist_sma200'], pct=True, signo=True) if T['dist_sma200'] is not None else 'Sin dato'}",
          "Resistencias: " + (", ".join(f"{es(x['valor'], 2)} ({es(x['dist'], pct=True, signo=True)})" for x in T["resistencias"]) or "Sin resistencia en 12 meses"),
          "Soportes: " + (", ".join(f"{es(x['valor'], 2)} ({es(x['dist'], pct=True, signo=True)})" for x in T["soportes"]) or "Sin soporte en 12 meses"),
          "", "Datos: Yahoo Finance. Informe automático con fines informativos. No es asesoramiento financiero."]
    return "\n".join(L)


def datos_json(D):
    sal = {k: v for k, v in D.items() if k not in ("serie",)}
    sal = json.loads(json.dumps(sal, default=lambda x: float(x) if hasattr(x, "__float__") else str(x)))
    sal["tecnicos"].pop("serie_s50", None)
    sal["tecnicos"].pop("serie_s200", None)
    return json.dumps(sal, ensure_ascii=False, separators=(",", ":"))


def sec_limites(D):
    return ('<section class="sec" id="limites"><h2>Lo que este informe no dice</h2><div class="aviso" style="font-size:14.5px">'
            'No predice el precio ni dice si comprar o vender. Todos los datos salen de Yahoo Finance y pueden tener errores o retrasos: '
            'la app descarta los valores incoherentes que detecta, pero no todos. En empresas cíclicas los ratios engañan en los picos y en los valles. '
            'No compara con su sector. Sin noticias, catalizadores ni riesgos redactados: eso exige leer documentos. '
            'El valor justo depende de supuestos fijos y es solo orientativo.</div>'
            '<div class="btns" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px"><button type="button" id="cp-res">Copiar resumen</button>'
            '<button type="button" id="cp-dat">Copiar datos</button><span id="cp-ok" style="color:var(--v);font-size:14px;align-self:center"></span></div>'
            f'<textarea id="tx-res" style="position:absolute;left:-9999px" aria-hidden="true">{E(resumen_texto(D))}</textarea>'
            f'<textarea id="tx-dat" style="position:absolute;left:-9999px" aria-hidden="true">{E(datos_json(D))}</textarea>'
            f'<p class="nota-pie">Fecha de corte {_fmt_fecha(D["corte"])} · Fuente: Yahoo Finance · Consenso: Yahoo Finance · Metodología v2.1 adaptada a la app (sin IA). '
            'Informe automático con fines informativos. No es asesoramiento financiero.</p></section>')


JS = """
<script>
(function(){
 var raiz=document.querySelector('.jr'), nav=raiz.querySelector('.nav');
 var secs=[].slice.call(raiz.querySelectorAll('section.sec[id]'));
 var n=nav.querySelector('.n'), k=nav.querySelector('.k');
 var P=null, F=null;
 try{ if(window.frameElement){P=window.parent; F=window.frameElement;} }catch(e){P=null;}
 function arriba(){ if(!P) return 0; var hd=P.document.querySelector('header[data-testid="stHeader"]'); return hd?hd.getBoundingClientRect().bottom+6:8; }
 function act(){
  var off=0, top0=arriba();
  if(P&&F){ var r=F.getBoundingClientRect(); off=Math.max(0,Math.min(top0-r.top, raiz.offsetHeight-nav.offsetHeight-20)); }
  nav.style.transform='translateY('+off+'px)';
  var lim=(P&&F?top0-F.getBoundingClientRect().top:0)+nav.offsetHeight+30, cur=secs[0], idx=0;
  secs.forEach(function(s,j){ if(s.getBoundingClientRect().top<lim){cur=s;idx=j;} });
  if(P&&F&&F.getBoundingClientRect().bottom<=P.innerHeight+4){cur=secs[secs.length-1];idx=secs.length-1;}
  n.textContent=cur.getAttribute('data-t'); k.textContent='En esta ficha · '+(idx+1)+'/'+secs.length;
 }
 if(P){ P.addEventListener('scroll',act,true); P.addEventListener('resize',act); } else { nav.style.position='sticky'; nav.style.top='0'; }
 window.addEventListener('scroll',act,true); act(); setTimeout(act,500);
 raiz.querySelectorAll('.nav .lista a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();
  var t=raiz.querySelector(a.getAttribute('href')); a.closest('details').removeAttribute('open');
  if(!t) return;
  if(P&&F){ var c=F.getBoundingClientRect().top+t.getBoundingClientRect().top-arriba()-nav.offsetHeight-12;
    var m=P.document.querySelector('[data-testid="stMain"]')||P.document.scrollingElement;
    if(m&&m.scrollHeight>m.clientHeight){ m.scrollBy({top:c,behavior:'smooth'}); } else { P.scrollBy({top:c,behavior:'smooth'}); } }
  else t.scrollIntoView({behavior:'smooth'});
 });});
 function cerrar(){ raiz.querySelectorAll('.tip.on').forEach(function(t){t.classList.remove('on')}); raiz.querySelectorAll('.q.on').forEach(function(q){q.classList.remove('on')}); }
 function colocar(t){ t.style.left='0'; var r=t.getBoundingClientRect(), w=document.documentElement.clientWidth;
  if(r.right>w-8){ t.style.left=(-(r.right-(w-8)))+'px'; } r=t.getBoundingClientRect(); if(r.left<8){ t.style.left=(parseFloat(t.style.left)+(8-r.left))+'px'; } }
 raiz.querySelectorAll('.q').forEach(function(q){
  q.addEventListener('click',function(e){ e.stopPropagation(); e.preventDefault(); var t=q.nextElementSibling, abierta=t.classList.contains('on'); cerrar();
   if(!abierta){ t.classList.add('on'); q.classList.add('on'); colocar(t); } });
  q.addEventListener('mouseenter',function(){ colocar(q.nextElementSibling); });
 });
 document.addEventListener('click',function(e){ if(!e.target.closest('.tip')) cerrar(); });
 raiz.querySelectorAll('.per button').forEach(function(b){b.addEventListener('click',function(){
  raiz.querySelectorAll('.per button').forEach(function(x){x.classList.remove('on')});b.classList.add('on');
  raiz.querySelectorAll('.evp').forEach(function(d){d.style.display=d.getAttribute('data-k')==b.getAttribute('data-p')?'':'none'});});});
 function cp(id){var t=raiz.querySelector(id);var v=t.value;var ok=raiz.querySelector('#cp-ok');
  function fin(){ok.textContent='Copiado';setTimeout(function(){ok.textContent=''},2000);}
  function viejo(){t.style.position='fixed';t.style.left='0';t.select();try{document.execCommand('copy');fin();}catch(e){ok.textContent='No se pudo copiar';}t.style.left='-9999px';}
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(v).then(fin,viejo);}else viejo();}
 var a=raiz.querySelector('#cp-res'),b=raiz.querySelector('#cp-dat');if(a)a.onclick=function(){cp('#tx-res')};if(b)b.onclick=function(){cp('#tx-dat')};
})();
</script>"""


def generar_html(D):
    secs = [sec_resumen(D), sec_historia(D), sec_evolucion(D), sec_valor(D), sec_nota(D), sec_cuentas(D), sec_tecnico(D),
            sec_resultados(D), sec_limites(D)]
    for i, (sid, t) in enumerate(SECCIONES):
        secs[i] = secs[i].replace(f'id="{sid}"', f'id="rg-{sid}" data-t="{E(t)}"', 1)
    nav = (f'<div class="nav"><div><div class="k">En esta ficha · 1/{len(SECCIONES)}</div><div class="n">Resumen</div></div>'
           '<details><summary>Secciones ▾</summary><div class="lista">'
           + "".join(f'<a href="#rg-{sid}">{E(t)}</a>' for sid, t in SECCIONES) + '</div></details></div>')
    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>Riesgo {E(D["ticker"])}</title><style>html,body{{margin:0;padding:0;background:#f3f0ea}}{CSS}</style></head>'
            f'<body><div class="jr">{nav}{"".join(secs)}</div>{JS}</body></html>')
