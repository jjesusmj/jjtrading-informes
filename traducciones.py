# Traducción al castellano de sectores, industrias y textos de Yahoo (copia de las tablas de niveles.py).
import re

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


def traducir(txt, tabla=None):
    """Tabla fija primero; si no está, traductor automático. Si falla, devuelve el texto original."""
    if not txt:
        return ""
    if tabla and txt in tabla:
        return tabla[txt]
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="en", target="es").translate(txt) or txt
    except Exception:
        return txt


_ABREV = ("Inc", "Corp", "Co", "Ltd", "S.A", "S.p.A", "N.V", "plc", "Plc", "AG", "SE", "St", "Mr", "U.S", "No")


def primeras_frases(txt, n=2):
    """Las n primeras frases de un texto en inglés, sin cortar en abreviaturas como «Inc.»."""
    if not txt:
        return ""
    trozos = re.split(r"(?<=\.)\s+(?=[A-Z])", txt.strip())
    frases, actual = [], ""
    for t in trozos:
        actual = f"{actual} {t}".strip() if actual else t
        if any(actual.endswith(a + ".") for a in _ABREV):
            continue
        frases.append(actual)
        actual = ""
        if len(frases) == n:
            break
    if actual and len(frases) < n:
        frases.append(actual)
    return " ".join(frases)
