"""ATENCIÓN: el informe actual incluye cambios hechos a mano en Power BI Desktop (cabecera, navegador, pie...).
Volver a ejecutar este script los sobrescribiría (se guardan en _respaldo/).

Genera las páginas del informe (formato PBIR) y el tema propio dentro de alquiler-vs-sueldo.Report.
Ejecutar con Power BI Desktop CERRADO. Las páginas anteriores se mueven a _respaldo/."""
from pathlib import Path
from datetime import datetime
import json

BASE = Path(__file__).parent
REP = BASE / "alquiler-vs-sueldo.Report"
DEF = REP / "definition"
PAGES = DEF / "pages"
VIS_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
W, H = 1280, 720
# Rejilla: margen 20 px, separación 12 px
MX, GAP = 20, 12
COL2_W = (W - 2 * MX - GAP) // 2            # 614
COL2_X = [MX, MX + COL2_W + GAP]            # 20, 646
KPI_W = (W - 2 * MX - 3 * GAP) // 4         # 301
KPI_X = [MX + i * (KPI_W + GAP) for i in range(4)]  # 20, 333, 646, 959
Y_KPI, H_KPI = 86, 104
Y_MAIN = Y_KPI + H_KPI + GAP                # 202
H_MAIN = 720 - MX - Y_MAIN                  # 498
H_MAIN_NOTA = H_MAIN - 32                   # deja sitio a una leyenda de 26 px
OSCURO, AZUL, AMBAR, LADRILLO, GRIS_AZ, TEXTO = "#0C3549", "#2E86AB", "#B9770E", "#A23B2A", "#8FA9BC", "#3D4B57"

L = lambda v: {"expr": {"Literal": {"Value": v}}}
def lit(t): return L("'" + t.replace("'", "''") + "'")
def solid(hexc): return {"solid": {"color": L(f"'{hexc}'")}}
def campo(entidad, prop, medida=False):
    return {"Measure" if medida else "Column": {"Expression": {"SourceRef": {"Entity": entidad}}, "Property": prop}}
def proy(entidad, prop, medida=False, nombre=None):
    p = {"field": campo(entidad, prop, medida), "queryRef": f"{entidad}.{prop}", "nativeQueryRef": prop}
    if nombre: p["displayName"] = nombre
    return p
M = lambda prop, nombre=None: proy("_Medidas", prop, True, nombre)
PROV = proy("dim_provincia", "provincia_corta", nombre="Provincia")
MUNI = proy("fact_alquiler_municipio", "municipio", nombre="Municipio")

def contenedor(titulo=None, alt=None):
    o = {"title": [{"properties": {"show": L("true"), "text": lit(titulo)}}] if titulo else [{"properties": {"show": L("false")}}]}
    if alt: o["general"] = [{"properties": {"altText": lit(alt)}}]
    return o

class Pagina:
    def __init__(self, nombre, titulo, filtro_prov=None):
        self.nombre, self.titulo, self.visuales, self.filtro_prov = nombre, titulo, [], filtro_prov
    def add(self, nombre, x, y, w, h, visual, extra=None):
        decorativo = visual["visualType"] == "textbox" and not nombre.startswith("v01Texto")
        v = {"$schema": VIS_SCHEMA, "name": nombre,
             "position": {"x": x, "y": y, "z": 1000 + len(self.visuales), "width": w, "height": h,
                          "tabOrder": -1 if decorativo else len(self.visuales)},
             "visual": visual}
        if extra: v.update(extra)
        self.visuales.append(v)

def texto(parrafos, alt=None):
    """parrafos: lista de párrafos; cada párrafo es (texto, pt, negrita, color) o una lista de esas tuplas (varios tramos)."""
    ps = []
    for par in parrafos:
        runs = par if isinstance(par, list) else [par]
        ps.append({"textRuns": [{"value": t, "textStyle": {"fontSize": f"{s}pt", "fontWeight": "bold" if b else "normal", "color": c}}
                                for t, s, b, c in runs]})
    return {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": ps}}]},
            "visualContainerObjects": {**contenedor(None, alt),
                                       "background": [{"properties": {"show": L("false")}}],
                                       "border": [{"properties": {"show": L("false")}}]},
            "drillFilterOtherVisuals": True}

def tarjeta(medida, titulo, ref=None, ref_nombre=None, alt=None):
    qs = {"Data": {"projections": [M(medida, titulo)]}}
    if ref: qs["ReferenceLabels"] = {"projections": [M(ref, ref_nombre)]}
    return {"visualType": "cardVisual", "query": {"queryState": qs},
            "visualContainerObjects": contenedor(None, alt), "drillFilterOtherVisuals": True}

def segmentador(entidad, prop, titulo, modo="Dropdown", valor_inicial=None):
    v = {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [{**proy(entidad, prop), "active": True}]}}},
         "objects": {"data": [{"properties": {"mode": L(f"'{modo}'")}}],
                     "header": [{"properties": {"show": L("true"), "text": lit(titulo)}}]},
         "visualContainerObjects": contenedor(None), "drillFilterOtherVisuals": True}
    extra = None
    if valor_inicial is not None:  # control numérico con valor guardado
        v["objects"]["data"][0]["properties"]["numericStart"] = L(f"{valor_inicial}D")
        v["objects"]["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2, "From": [{"Name": "t", "Entity": entidad, "Type": 0}],
            "Where": [{"Condition": {"Comparison": {"ComparisonKind": 0,
                "Left": {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}},
                "Right": {"Literal": {"Value": f"{valor_inicial}D"}}}}}]}}}}]
        extra = {"filterConfig": {"filters": [{"name": "filtroTuSueldo", "field": campo(entidad, prop), "type": "Advanced"}]}}
    return v, extra

def color_por_medida(medida):
    return [{"properties": {"fill": {"solid": {"color": {"expr": campo("_Medidas", medida, True)}}}},
             "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]

def barras(cat, medida, titulo, color_medida, tooltips=(), desc=True, alt=None):
    qs = {"Category": {"projections": [cat]}, "Y": {"projections": [medida]}}
    if tooltips: qs["Tooltips"] = {"projections": list(tooltips)}
    return {"visualType": "clusteredBarChart",
            "query": {"queryState": qs,
                      "sortDefinition": {"sort": [{"field": medida["field"], "direction": "Descending" if desc else "Ascending"}], "isDefaultSort": True}},
            "objects": {"dataPoint": color_por_medida(color_medida),
                        "labels": [{"properties": {"show": L("true")}}],
                        "legend": [{"properties": {"show": L("false")}}]},
            "visualContainerObjects": contenedor(titulo, alt), "drillFilterOtherVisuals": True}

def tabla(cols, titulo, orden, desc=True, alt=None):
    return {"visualType": "tableEx",
            "query": {"queryState": {"Values": {"projections": cols}},
                      "sortDefinition": {"sort": [{"field": orden["field"], "direction": "Descending" if desc else "Ascending"}], "isDefaultSort": True}},
            "visualContainerObjects": contenedor(titulo, alt), "drillFilterOtherVisuals": True}

def cabecera(p, titulo, subtitulo, ancho=1000):
    p.add("v00Titulo", MX, 8, ancho, 70, texto([(titulo, 20, True, OSCURO), (subtitulo, 10, False, "#5B6B78")]))

LEYENDA = [[("■ ", 11, True, AZUL), ("≤ 30 % del sueldo    ", 10, False, TEXTO),
            ("■ ", 11, True, AMBAR), ("30-40 %    ", 10, False, TEXTO),
            ("■ ", 11, True, LADRILLO), ("> 40 %    ", 10, False, TEXTO),
            ("■ ", 11, True, OSCURO), ("Alicante", 10, True, OSCURO)]]

paginas = []

# ---------- 1. Resumen ----------
p = Pagina("pg01Resumen", "Resumen")
cabecera(p, "En 27 de 48 provincias, alquilar hoy supera el 30 % del sueldo medio",
         "Alquiler de contrato nuevo frente al salario bruto medio, por provincia · 2024 · Sin el tramo de 18-25 años (muchos contratos parciales) · Fuentes: AEAT e INE")
v, e = segmentador("dim_tramo_edad", "etiqueta", "Edad")
p.add("v01SlicerEdad", 1030, 14, 230, 62, v, e)
p.add("v02Kpi", KPI_X[0], Y_KPI, KPI_W, H_KPI, tarjeta("% sueldo contrato nuevo", "% del sueldo para alquilar hoy", "Umbral 30 %", "Umbral recomendado",
      alt="Porcentaje del salario bruto medio que se va en el alquiler de un contrato nuevo, frente al umbral del 30 %"))
p.add("v03Kpi", KPI_X[1], Y_KPI, KPI_W, H_KPI, tarjeta("Texto provincias por encima del 30 %", "Provincias por encima del 30 %",
      alt="Número de provincias donde un alquiler nuevo supera el 30 % del salario medio"))
p.add("v04Kpi", KPI_X[2], Y_KPI, KPI_W, H_KPI, tarjeta("Alquiler nuevos contratos", "Alquiler contrato nuevo (€/mes)", "Alquiler medio", "Media de todos los contratos",
      alt="Alquiler mensual de un contrato nuevo frente a la media de todos los contratos"))
p.add("v05Kpi", KPI_X[3], Y_KPI, KPI_W, H_KPI, tarjeta("Salario mensual bruto", "Salario bruto mensual", "Salario 2024", "Salario bruto anual",
      alt="Salario bruto medio mensual y anual"))
p.add("v06BarEsfuerzo", COL2_X[0], Y_MAIN, COL2_W, H_MAIN_NOTA,
      barras(PROV, M("% sueldo contrato nuevo", "% del sueldo"), "% del sueldo bruto para un alquiler de contrato nuevo", "Color esfuerzo",
             tooltips=[M("Nivel de esfuerzo", "Nivel"), M("Alquiler nuevos contratos", "Alquiler contrato nuevo"), M("Salario 2024", "Salario bruto anual")],
             alt="Ranking de provincias por porcentaje del sueldo que cuesta un alquiler nuevo. Baleares y Málaga superan el 50 %; Alicante es la décima."))
p.add("v07LeyendaBar", COL2_X[0], 720 - MX - 26, COL2_W, 26, texto(LEYENDA))
p.add("v08Scatter", COL2_X[1], Y_MAIN, COL2_W, H_MAIN_NOTA,
      {"visualType": "scatterChart",
       "query": {"queryState": {"Category": {"projections": [PROV]},
                                "X": {"projections": [M("Salario 2024", "Salario bruto anual")]},
                                "Y": {"projections": [M("Alquiler nuevos contratos", "Alquiler contrato nuevo")]},
                                "Tooltips": {"projections": [M("% sueldo contrato nuevo", "% del sueldo"), M("Nivel de esfuerzo", "Nivel")]}}},
       "objects": {"dataPoint": color_por_medida("Color esfuerzo"),
                   "categoryLabels": [{"properties": {"show": L("false")}}],
                   "categoryAxis": [{"properties": {"showAxisTitle": L("true")}}],
                   "valueAxis": [{"properties": {"showAxisTitle": L("true")}}]},
       "visualContainerObjects": contenedor("Sueldo frente a alquiler de contrato nuevo",
            "Dispersión de provincias: salario bruto anual frente a alquiler de contrato nuevo. Alicante, en azul marino, combina sueldo bajo y alquiler alto."),
       "drillFilterOtherVisuals": True})
p.add("v09LeyendaScatter", COL2_X[1], 720 - MX - 26, COL2_W, 26, texto(LEYENDA))
paginas.append(p)

# ---------- 2. Provincias ----------
p = Pagina("pg02Provincias", "Provincias")
cabecera(p, "Quien busca piso hoy paga más que la media",
         "Sobrecoste del alquiler de un contrato nuevo frente a la media de contratos · 2024 · Ojo al tamaño: en Madrid el piso alquilado medio tiene 76 m²; en Alicante, 92 m²")
v, e = segmentador("dim_provincia", "ccaa", "Comunidad autónoma")
p.add("v01SlicerCcaa", 1030, 14, 230, 62, v, e)
p.add("v02BarSobrecoste", COL2_X[0], Y_KPI, COL2_W, 720 - MX - Y_KPI,
      barras(PROV, M("Sobrecoste contrato nuevo", "Sobrecoste"), "Cuánto más cuesta un contrato nuevo que la media", "Color sobrecoste",
             tooltips=[M("Alquiler medio", "Media de contratos"), M("Alquiler nuevos contratos", "Contrato nuevo")],
             alt="Ranking de provincias por sobrecoste de un contrato nuevo frente a la media. En España es del 11 %; en Alicante, del 17 %."))
p.add("v03Tabla", COL2_X[1], Y_KPI, COL2_W, 720 - MX - Y_KPI,
      tabla([PROV, M("Salario 2024", "Salario bruto"), M("Alquiler medio", "Alquiler medio"), M("Alquiler nuevos contratos", "Contrato nuevo"),
             M("Sobrecoste contrato nuevo", "Sobrecoste"), M("Alquiler €/m²", "€/m²"), M("m² medios", "m²"),
             M("% sueldo contrato nuevo", "% sueldo (nuevo)")],
            "Detalle por provincia", M("% sueldo contrato nuevo"),
            alt="Tabla por provincia con salario, alquiler medio y de contrato nuevo, sobrecoste, precio por metro cuadrado, superficie y porcentaje del sueldo"))
paginas.append(p)

# ---------- 3. ¿Dónde puedo vivir? ----------
p = Pagina("pg03TuSueldo", "¿Dónde puedo vivir?")
cabecera(p, "¿Dónde puedo vivir con mi sueldo?",
         "Mueve el control con tu sueldo bruto anual · Asumible = alquiler de contrato nuevo ≤ 30 % del sueldo bruto")
v, e = segmentador("Tu sueldo", "Tu sueldo bruto anual", "Tu sueldo bruto anual", modo="Single", valor_inicial=24000)
p.add("v01SlicerSueldo", COL2_X[0], Y_KPI, COL2_W, H_KPI, v, e)
p.add("v02KpiAsumibles", KPI_X[2], Y_KPI, KPI_W, H_KPI, tarjeta("Texto provincias asumibles", "Provincias asumibles",
      alt="Número de provincias donde el alquiler de un contrato nuevo no supera el 30 % del sueldo indicado"))
p.add("v03KpiPct", KPI_X[3], Y_KPI, KPI_W, H_KPI, tarjeta("% de tu sueldo", "% de tu sueldo (media España)", "Umbral 30 %", "Umbral recomendado",
      alt="Porcentaje del sueldo indicado que costaría un alquiler nuevo medio en España"))
p.add("v04BarTuSueldo", COL2_X[0], Y_MAIN, COL2_W, H_MAIN_NOTA,
      barras(PROV, M("% de tu sueldo", "% de tu sueldo"), "% de tu sueldo que se iría en alquiler", "Color tu sueldo",
             tooltips=[M("Veredicto", "Veredicto"), M("Alquiler nuevos contratos", "Alquiler (€/mes)"), M("Sueldo necesario (30 %)", "Sueldo necesario")],
             desc=False, alt="Provincias ordenadas de más a menos asequibles para el sueldo indicado"))
p.add("v05LeyendaBar", COL2_X[0], 720 - MX - 26, COL2_W, 26, texto(LEYENDA))
p.add("v06Tabla", COL2_X[1], Y_MAIN, COL2_W, H_MAIN,
      tabla([PROV, M("Alquiler nuevos contratos", "Alquiler (€/mes)"), M("% de tu sueldo", "% de tu sueldo"), M("Veredicto", "Veredicto"),
             M("Sueldo necesario (30 %)", "Sueldo necesario")],
            "Provincia a provincia", M("% de tu sueldo"), desc=False,
            alt="Tabla con el alquiler, el porcentaje del sueldo indicado, el veredicto y el sueldo necesario para no pasar del 30 %"))
paginas.append(p)

# ---------- 4. Evolución ----------
p = Pagina("pg04Evolucion", "Evolución 2015-2024")
cabecera(p, "Los contratos vigentes suben menos que los sueldos; el problema lo sufre quien firma hoy",
         "Índices 2015 = 100 · Alquiler: IPVA del INE (mismas viviendas año a año) · Salario: salario medio anual de la AEAT")
v, e = segmentador("dim_provincia", "provincia_corta", "Provincia")
p.add("v01SlicerProv", 1030, 14, 230, 62, v, e)
p.add("v02KpiAlq", KPI_X[0], Y_KPI, KPI_W, H_KPI, tarjeta("Subida alquiler 2015-2024", "Subida del alquiler vigente (INE)",
      alt="Subida acumulada del índice de alquiler del INE entre 2015 y 2024"))
p.add("v03KpiSal", KPI_X[1], Y_KPI, KPI_W, H_KPI, tarjeta("Subida salario 2015-2024", "Subida del salario medio",
      alt="Subida acumulada del salario medio entre 2015 y 2024"))
p.add("v04Nota", COL2_X[1], Y_KPI, COL2_W, H_KPI, texto([
    ("Cómo leerlo", 11, True, OSCURO),
    ("El índice del INE sigue sobre todo contratos ya firmados (en 2024 solo un 12 % eran nuevos), así que la media sube despacio. "
     "Quien firma hoy paga de media un 11 % más que la media de contratos (página Provincias).", 10, False, TEXTO)]))
p.add("v05Linea", MX, Y_MAIN, W - 2 * MX, H_MAIN,
      {"visualType": "lineChart",
       "query": {"queryState": {"Category": {"projections": [proy("dim_anio", "anio", nombre="Año")]},
                                "Y": {"projections": [M("Índice alquiler (INE)", "Alquiler vigente (INE)"), M("Índice salario", "Salario medio")]}}},
       "objects": {"labels": [{"properties": {"show": L("true")}}],
                   "legend": [{"properties": {"show": L("true"), "position": L("'Top'")}}],
                   "dataPoint": [{"properties": {"fill": solid(OSCURO)}, "selector": {"metadata": "_Medidas.Índice alquiler (INE)"}},
                                 {"properties": {"fill": solid(AZUL)}, "selector": {"metadata": "_Medidas.Índice salario"}}]},
       "visualContainerObjects": contenedor("Índice 2015 = 100",
            "Evolución 2015-2024 del índice de alquiler del INE y del salario medio, ambos con base 100 en 2015. El salario sube más que el alquiler de los contratos vigentes."),
       "drillFilterOtherVisuals": True})
paginas.append(p)

# ---------- 5. Foco Alicante ----------
p = Pagina("pg05Alicante", "Foco Alicante", filtro_prov="03")
cabecera(p, "Alicante: alquiler de ciudad cara con sueldo de provincia barata",
         "10.ª de 48 provincias donde más pesa el alquiler, con un salario medio un 16 % inferior al de España · Municipios de más de 20.000 habitantes")
p.add("v01Kpi", KPI_X[0], Y_KPI, KPI_W, H_KPI, tarjeta("% sueldo contrato nuevo", "% del sueldo (contrato nuevo)", "% sueldo contrato nuevo España", "España",
      alt="Porcentaje del sueldo medio de Alicante que cuesta un alquiler nuevo, frente a España"))
p.add("v02Kpi", KPI_X[1], Y_KPI, KPI_W, H_KPI, tarjeta("Texto ranking esfuerzo", "Puesto en esfuerzo", "Diferencia vs España (pp)", "Frente a España",
      alt="Puesto de Alicante entre las 48 provincias por peso del alquiler en el sueldo"))
p.add("v03Kpi", KPI_X[2], Y_KPI, KPI_W, H_KPI, tarjeta("Salario 2024", "Salario bruto anual", "Diferencia salario vs España", "Frente a España",
      alt="Salario bruto medio de Alicante y diferencia con la media de España"))
p.add("v04Kpi", KPI_X[3], Y_KPI, KPI_W, H_KPI, tarjeta("Alquiler nuevos contratos", "Alquiler contrato nuevo (€/mes)", "Sobrecoste contrato nuevo", "Sobre la media de contratos",
      alt="Alquiler mensual de un contrato nuevo en Alicante y sobrecoste frente a la media"))
p.add("v05BarMunicipios", COL2_X[0], Y_MAIN, COL2_W, H_MAIN,
      {**barras(MUNI, M("Alquiler nuevo municipio", "Contrato nuevo (€/mes)"), "Alquiler de contrato nuevo por municipio (€/mes)", "Color sobrecoste",
                tooltips=[M("Alquiler medio municipio", "Media de contratos")],
                alt="Municipios de la provincia de Alicante ordenados por alquiler de contrato nuevo. Jávea, Altea y El Campello encabezan la lista.")})
p.visuales[-1]["visual"]["objects"]["dataPoint"] = [{"properties": {"fill": solid(OSCURO)}}]
p.add("v06Tabla", COL2_X[1], Y_MAIN, COL2_W, H_MAIN,
      tabla([MUNI, M("Alquiler nuevo municipio", "Contrato nuevo (€/mes)"), M("Alquiler medio municipio", "Media (€/mes)"),
             M("% sueldo contrato nuevo municipio", "% sueldo (estimado)")],
            "Esfuerzo estimado por municipio (sobre el salario medio provincial)", M("% sueldo contrato nuevo municipio"),
            alt="Tabla de municipios de Alicante con alquiler nuevo, alquiler medio y porcentaje estimado del sueldo provincial"))
paginas.append(p)

# ---------- 6. Metodología ----------
p = Pagina("pg06Metodologia", "Metodología")
cabecera(p, "Metodología y fuentes", "Cómo se han calculado las cifras y qué limitaciones tienen")
g = TEXTO
p.add("v01Texto", MX, Y_KPI, W - 2 * MX, 720 - MX - Y_KPI, texto([
    ("Fuentes", 12, True, OSCURO),
    ("· Salarios: Agencia Tributaria (AEAT), «Mercado de trabajo y pensiones en las fuentes tributarias» 2015-2024. Salario medio anual bruto por provincia y edad.", 10, False, g),
    ("· Alquiler en euros: Agencia Tributaria (AEAT), «Estadística de viviendas declaradas en el IRPF» 2024. Alquiler medio mensual de vivienda habitual (todos los contratos y contratos nuevos), €/m² y superficie.", 10, False, g),
    ("· Evolución del alquiler: INE, Índice de Precios de Vivienda en Alquiler (IPVA), base 2015.", 10, False, g),
    ("Cálculos", 12, True, OSCURO),
    ("· % del sueldo = alquiler mensual × 12 / salario bruto anual medio. Las cifras de comunidades y del total se ponderan por viviendas arrendadas y por asalariados.", 10, False, g),
    ("· El umbral del 30 % suele aplicarse al sueldo neto; aquí se usa el bruto, así que el esfuerzo real es todavía mayor.", 10, False, g),
    ("Limitaciones", 12, True, OSCURO),
    ("· No incluye País Vasco ni Navarra (haciendas forales).", 10, False, g),
    ("· El salario medio de la AEAT incluye a quien trabajó solo parte del año. Por eso se excluye el tramo de 18 a 25 años, cuya media no es comparable.", 10, False, g),
    ("· La página de evolución compara dos medidas distintas: el IPVA sigue las mismas viviendas año a año (casi todas con contrato vigente), mientras que el salario medio cambia según quién trabaja cada año.", 10, False, g),
    ("· Alquileres declarados en el IRPF (medias), no precios de anuncio. El % de los municipios es una estimación con el salario medio de su provincia.", 10, False, g),
    ("Autor: Alfredo Brocal Serrano · Datos y código: github.com/alfredobrocalserrano", 10, True, AZUL),
], alt="Fuentes, cálculos y limitaciones del informe"))
paginas.append(p)

# ---------- Tema propio ----------
tema = {
    "name": "TemaAlquilerSueldo",
    "dataColors": [OSCURO, AZUL, GRIS_AZ, AMBAR, LADRILLO, "#5B6B78"],
    "background": "#FFFFFF", "foreground": "#1F2A33", "tableAccent": OSCURO,
    "textClasses": {
        "callout": {"fontSize": 26, "fontFace": "Segoe UI Semibold", "color": OSCURO},
        "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": OSCURO},
        "header": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": OSCURO},
        "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": TEXTO}},
    "visualStyles": {
        "*": {"*": {
            "title": [{"show": True, "fontColor": {"solid": {"color": OSCURO}}, "fontSize": 12, "bold": True}],
            "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}, "transparency": 0}],
            "border": [{"show": True, "color": {"solid": {"color": "#E3E7EB"}}, "radius": 10}],
            "dropShadow": [{"show": False}],
            "categoryAxis": [{"fontSize": 11, "showAxisTitle": False}],
            "valueAxis": [{"fontSize": 11, "showAxisTitle": False, "gridlineColor": {"solid": {"color": "#EEF1F4"}}}],
            "labels": [{"fontSize": 10}],
            "legend": [{"fontSize": 10}]}},
        "page": {"*": {"background": [{"color": {"solid": {"color": "#F4F6F8"}}, "transparency": 0}]}},
        "tableEx": {"*": {"columnHeaders": [{"fontSize": 10, "fontColor": {"solid": {"color": OSCURO}}}],
                          "values": [{"fontSize": 10}]}}}}
REG = REP / "StaticResources" / "RegisteredResources"
REG.mkdir(parents=True, exist_ok=True)
(REG / "TemaAlquilerSueldo.json").write_text(json.dumps(tema, ensure_ascii=False, indent=2), encoding="utf-8")
rj = json.loads((DEF / "report.json").read_text(encoding="utf-8"))
rj["themeCollection"]["customTheme"] = {"name": "TemaAlquilerSueldo.json",
    "reportVersionAtImport": rj["themeCollection"]["baseTheme"]["reportVersionAtImport"], "type": "RegisteredResources"}
rj["resourcePackages"] = [r for r in rj["resourcePackages"] if r["name"] != "RegisteredResources"] + [
    {"name": "RegisteredResources", "type": "RegisteredResources",
     "items": [{"name": "TemaAlquilerSueldo.json", "path": "TemaAlquilerSueldo.json", "type": "CustomTheme"}]}]
(DEF / "report.json").write_text(json.dumps(rj, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- Escritura de páginas ----------
resp = BASE / "_respaldo" / datetime.now().strftime("paginas_%Y%m%d_%H%M%S")
for d in [d for d in PAGES.iterdir() if d.is_dir()]:
    resp.mkdir(parents=True, exist_ok=True)
    d.rename(resp / d.name)
for p in paginas:
    vdir = PAGES / p.nombre / "visuals"
    vdir.mkdir(parents=True, exist_ok=True)
    page = {"$schema": PAGE_SCHEMA, "name": p.nombre, "displayName": p.titulo, "displayOption": "FitToPage", "height": H, "width": W}
    if p.filtro_prov:
        page["filterConfig"] = {"filters": [{"name": "filtroProvincia", "field": campo("dim_provincia", "cod_prov"), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "dim_provincia", "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "cod_prov"}}],
                                                       "Values": [[{"Literal": {"Value": f"'{p.filtro_prov}'"}}]]}}}]},
            "howCreated": "User", "isHiddenInViewMode": True}]}
    (PAGES / p.nombre / "page.json").write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding="utf-8")
    for v in p.visuales:
        d = vdir / v["name"]; d.mkdir(exist_ok=True)
        (d / "visual.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
pj = json.loads((PAGES / "pages.json").read_text(encoding="utf-8"))
pj["pageOrder"] = [p.nombre for p in paginas]
pj["activePageName"] = paginas[0].nombre
(PAGES / "pages.json").write_text(json.dumps(pj, ensure_ascii=False, indent=2), encoding="utf-8")

n = sum(1 for f in REP.rglob("*.json") if json.loads(f.read_text(encoding="utf-8")) is not None)
print(f"OK: {len(paginas)} páginas, {sum(len(p.visuales) for p in paginas)} visuales, {n} JSON válidos")
