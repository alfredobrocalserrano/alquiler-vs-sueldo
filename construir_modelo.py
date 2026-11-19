"""
Reescribe el modelo semántico (TMDL) del proyecto Power BI:
  - tipos de columna correctos (códigos como texto, decimales con cultura en-US, CSV con comillas)
  - modelo en estrella (relaciones dimensión -> hechos)
  - tabla de medidas _Medidas y parámetro "Tu sueldo"
Ejecutar con Power BI Desktop CERRADO. Al abrir, pulsar "Actualizar".
"""
from pathlib import Path
import csv, re, uuid

BASE = Path(__file__).parent
SM = BASE / "alquiler-vs-sueldo.SemanticModel" / "definition"
TBL = SM / "tables"
WIN_DATA = "C:\\Users\\alfre\\Desktop\\alquiler-vs-sueldo\\datos_limpios\\"  # valor inicial del parámetro RutaDatos

# lineageTags existentes, para no romper la caché de Desktop
tags = {}
for f in TBL.glob("*.tmdl"):
    cur_table, cur_obj = None, None
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^table (.+)$", line)
        if m: cur_table = m.group(1).strip("'"); cur_obj = ("table", cur_table); continue
        m = re.match(r"^\t(column|measure) ('[^']+'|\S+)", line)
        if m: cur_obj = (cur_table, m.group(2).strip("'")); continue
        m = re.match(r"^\t*lineageTag: (.+)$", line)
        if m and cur_obj and cur_obj not in tags: tags[cur_obj] = m.group(1)
def tag(*key):
    return tags.setdefault(key, str(uuid.uuid4()))
def q(n):  # nombre TMDL
    return n if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) else "'" + n.replace("'", "''") + "'"

TEXT = {"cod_prov","provincia","ccaa","provincia_corta","ubicacion_mapa","tramo_edad","etiqueta","cod_muni","municipio"}
DEC = {"alquiler_m2","rentab","indice_alquiler"}
BOOL = {"es_alicante"}
HIDDEN = {("fact_alquiler_municipio","cod_prov"),("fact_alquiler_provincia","cod_prov"),("fact_alquiler_provincia","anio"),
          ("fact_ipva","cod_prov"),("fact_ipva","anio"),("fact_salarios","cod_prov"),("fact_salarios","anio"),
          ("fact_salarios","tramo_edad"),("fact_alquiler_espana","anio"),("fact_ipva_espana","anio"),("fact_salarios_espana","anio"),("fact_salarios_espana","tramo_edad"),("dim_tramo_edad","orden"),("dim_provincia","es_alicante"),("dim_provincia","provincia")}
CATEGORY = {("dim_provincia","provincia_corta"):"StateOrProvince",("dim_provincia","ubicacion_mapa"):"Place",
            ("fact_alquiler_municipio","ubicacion_mapa"):"Place",("fact_alquiler_municipio","municipio"):"City"}
SORTBY = {("dim_tramo_edad","etiqueta"):"orden"}
FMT = {"alquiler_medio":"#,0 €","alquiler_nuevos":"#,0 €","salario_medio_anual":"#,0 €","salario_medio_mensual":"#,0 €",
       "alquiler_m2":"#,0.0 €","indice_alquiler":"0.0","viv_arrendadas":"#,0","asalariados":"#,0","anio":"0"}

def tabla_csv(name):
    header = next(csv.reader(open(BASE/"datos_limpios"/f"{name}.csv", encoding="utf-8")))
    out = [f"table {name}", f"\tlineageTag: {tag('table', name)}", ""]
    types = []
    for c in header:
        if c in TEXT: dt, mt = "string", "type text"
        elif c in DEC: dt, mt = "double", "type number"
        elif c in BOOL: dt, mt = "boolean", "type logical"
        else: dt, mt = "int64", "Int64.Type"
        types.append(f'{{"{c}", {mt}}}')
        out.append(f"\tcolumn {c}")
        out.append(f"\t\tdataType: {dt}")
        if c in FMT and dt != "string": out.append(f"\t\tformatString: {FMT[c]}")
        if (name, c) in HIDDEN: out.append("\t\tisHidden")
        if (name, c) in CATEGORY: out.append(f"\t\tdataCategory: {CATEGORY[(name, c)]}")
        out.append(f"\t\tlineageTag: {tag(name, c)}")
        out.append("\t\tsummarizeBy: none")
        out.append(f"\t\tsourceColumn: {c}")
        if (name, c) in SORTBY: out.append(f"\t\tsortByColumn: {SORTBY[(name, c)]}")
        out += ["", "\t\tannotation SummarizationSetBy = User", ""]
    out += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
            f'\t\t\t\t    Origen = Csv.Document(File.Contents(RutaDatos & "{name}.csv"),[Delimiter=",", Columns={len(header)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
            '\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),',
            f'\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{", ".join(types)}}}, "en-US")',
            "\t\t\t\tin", "\t\t\t\t    Tipos", "", "\tannotation PBI_ResultType = Table", ""]
    (TBL/f"{name}.tmdl").write_text("\n".join(out), encoding="utf-8")

for t in ["dim_anio","dim_provincia","dim_tramo_edad","fact_alquiler_municipio","fact_alquiler_provincia","fact_ipva","fact_salarios",
          "fact_alquiler_espana","fact_ipva_espana","fact_salarios_espana"]:
    tabla_csv(t)

# ---------------- Medidas ----------------
A, S, I, M = "fact_alquiler_provincia", "fact_salarios", "fact_ipva", "fact_alquiler_municipio"
AE, SE, IE = "fact_alquiler_espana", "fact_salarios_espana", "fact_ipva_espana"
MEDIDAS = [
 # (carpeta, nombre, formato, DAX)
 ("1 Alquiler","Alquiler medio","#,0 €",f"""
VAR prov = DIVIDE(SUMX({A}, {A}[alquiler_medio] * {A}[viv_arrendadas]), SUM({A}[viv_arrendadas]))
VAR nac = SUM({AE}[alquiler_medio])
RETURN IF(ISFILTERED(dim_provincia), prov, nac)"""),
 ("1 Alquiler","Alquiler nuevos contratos","#,0 €",f"""
VAR prov = DIVIDE(SUMX({A}, {A}[alquiler_nuevos] * {A}[viv_arrendadas]), SUM({A}[viv_arrendadas]))
VAR nac = SUM({AE}[alquiler_nuevos])
RETURN IF(ISFILTERED(dim_provincia), prov, nac)"""),
 ("1 Alquiler","Sobrecoste contrato nuevo","+0.0%;-0.0%;0.0%","DIVIDE([Alquiler nuevos contratos], [Alquiler medio]) - 1"),
 ("2 Salario","Tramo seleccionado","",'SELECTEDVALUE(dim_tramo_edad[tramo_edad], "Total")'),
 ("2 Salario","Salario medio anual","#,0 €",f"""
VAR t = [Tramo seleccionado]
VAR ponderado = CALCULATE(
    DIVIDE(SUMX({S}, {S}[salario_medio_anual] * {S}[asalariados]), SUM({S}[asalariados])),
    dim_tramo_edad[tramo_edad] = t)
VAR simple = CALCULATE(AVERAGE({S}[salario_medio_anual]), dim_tramo_edad[tramo_edad] = t)
VAR nac = CALCULATE(AVERAGE({SE}[salario_medio_anual]), dim_tramo_edad[tramo_edad] = t)
RETURN IF(ISFILTERED(dim_provincia), COALESCE(ponderado, simple), nac)"""),
 ("2 Salario","Salario 2024","#,0 €","CALCULATE([Salario medio anual], dim_anio[anio] = 2024)"),
 ("2 Salario","Salario mensual bruto","#,0 €","DIVIDE([Salario 2024], 12)"),
 ("3 Esfuerzo","% sueldo contrato nuevo","0.0%","DIVIDE([Alquiler nuevos contratos] * 12, [Salario 2024])"),
 ("3 Esfuerzo","% sueldo contrato nuevo España","0.0%","CALCULATE([% sueldo contrato nuevo], REMOVEFILTERS(dim_provincia))"),
 ("3 Esfuerzo","Diferencia vs España (pp)",'+0.0" pp";-0.0" pp";0.0" pp"',"([% sueldo contrato nuevo] - [% sueldo contrato nuevo España]) * 100"),
 ("3 Esfuerzo","Umbral 30 %","0%","0.3"),
 ("3 Esfuerzo","Provincias por encima del 30 %","0",'COUNTROWS(FILTER(VALUES(dim_provincia[cod_prov]), NOT ISBLANK(dim_provincia[cod_prov]) && [% sueldo contrato nuevo] > 0.3))'),
 ("3 Esfuerzo","Color esfuerzo","",f"""
VAR p = [% sueldo contrato nuevo]
VAR ali = SELECTEDVALUE(dim_provincia[es_alicante], FALSE())
RETURN IF(ali, "#0C3549", SWITCH(TRUE(), ISBLANK(p), "#CCCCCC", p > 0.4, "#A23B2A", p > 0.3, "#B9770E", "#2E86AB"))"""),
 ("4 Evolución","Índice alquiler (INE)","0.0",f"""
VAR prov = AVERAGE({I}[indice_alquiler])
VAR nac = AVERAGE({IE}[indice_alquiler])
RETURN IF(ISFILTERED(dim_provincia), prov, nac)"""),
 ("4 Evolución","Índice salario","0.0",f"""
VAR base = CALCULATE([Salario medio anual], dim_anio[anio] = 2015, dim_tramo_edad[tramo_edad] = "Total")
RETURN DIVIDE(CALCULATE([Salario medio anual], dim_tramo_edad[tramo_edad] = "Total"), base) * 100"""),
 ("4 Evolución","Subida alquiler 2015-2024","+0.0%;-0.0%;0.0%","CALCULATE([Índice alquiler (INE)], dim_anio[anio] = 2024) / 100 - 1"),
 ("4 Evolución","Subida salario 2015-2024","+0.0%;-0.0%;0.0%","CALCULATE([Índice salario], dim_anio[anio] = 2024) / 100 - 1"),
 ("5 Tu sueldo","% de tu sueldo","0.0%","DIVIDE([Alquiler nuevos contratos] * 12, [Valor Tu sueldo])"),
 ("5 Tu sueldo","Veredicto","",f"""
VAR p = [% de tu sueldo]
RETURN IF(ISBLANK(p), BLANK(), IF(p <= 0.3, "Asumible", IF(p <= 0.4, "Justo", "No asumible")))"""),
 ("5 Tu sueldo","Color tu sueldo","",f"""
VAR p = [% de tu sueldo]
VAR ali = SELECTEDVALUE(dim_provincia[es_alicante], FALSE())
RETURN IF(ali, "#0C3549", SWITCH(TRUE(), ISBLANK(p), "#CCCCCC", p > 0.4, "#A23B2A", p > 0.3, "#B9770E", "#2E86AB"))"""),
 ("5 Tu sueldo","Provincias asumibles","0",'COUNTROWS(FILTER(VALUES(dim_provincia[cod_prov]), NOT ISBLANK(dim_provincia[cod_prov]) && [% de tu sueldo] <= 0.3))'),
 ("5 Tu sueldo","Texto provincias asumibles","",'FORMAT([Provincias asumibles], "0") & " de " & FORMAT(COUNTROWS(ALLNOBLANKROW(dim_provincia)), "0")'),
 ("5 Tu sueldo","Sueldo necesario (30 %)","#,0 €","DIVIDE([Alquiler nuevos contratos] * 12, 0.3)"),
 ("6 Municipios","Alquiler medio municipio","#,0 €",f"DIVIDE(SUMX({M}, {M}[alquiler_medio] * {M}[viv_arrendadas]), SUM({M}[viv_arrendadas]))"),
 ("6 Municipios","Alquiler nuevo municipio","#,0 €",f"DIVIDE(SUMX({M}, {M}[alquiler_nuevos] * {M}[viv_arrendadas]), SUM({M}[viv_arrendadas]))"),
 ("6 Municipios","Salario provincia del municipio","#,0 €",f"""
VAR c = SELECTEDVALUE({M}[cod_prov])
RETURN IF(ISBLANK(c), [Salario 2024], CALCULATE([Salario 2024], dim_provincia[cod_prov] = c))"""),
 ("6 Municipios","% sueldo contrato nuevo municipio","0.0%","DIVIDE([Alquiler nuevo municipio] * 12, [Salario provincia del municipio])"),
 ("6 Municipios","Color esfuerzo municipio","",f"""
VAR p = [% sueldo contrato nuevo municipio]
RETURN SWITCH(TRUE(), ISBLANK(p), "#5B6B78", p > 0.4, "#A23B2A", p > 0.3, "#B9770E", "#2E86AB")"""),
 ("2 Salario","Texto salario mensual","",'FORMAT([Salario mensual bruto], "#,0 €")'),
 ("2 Salario","Texto salario anual","",'FORMAT([Salario 2024], "#,0 €")'),
 ("1 Alquiler","Alquiler €/m²","#,0.0 €",f"""
VAR prov = DIVIDE(SUMX({A}, {A}[alquiler_m2] * {A}[viv_arrendadas]), SUM({A}[viv_arrendadas]))
VAR nac = SUM({AE}[alquiler_m2])
RETURN IF(ISFILTERED(dim_provincia), prov, nac)"""),
 ("1 Alquiler","m² medios","0",f"""
VAR prov = DIVIDE(SUMX({A}, {A}[m2_medios] * {A}[viv_arrendadas]), SUM({A}[viv_arrendadas]))
VAR nac = SUM({AE}[m2_medios])
RETURN IF(ISFILTERED(dim_provincia), prov, nac)"""),
 ("1 Alquiler","Color sobrecoste","",'IF(SELECTEDVALUE(dim_provincia[es_alicante], FALSE()), "#0C3549", "#5B6B78")'),
 ("2 Salario","Salario España","#,0 €","CALCULATE([Salario 2024], REMOVEFILTERS(dim_provincia))"),
 ("2 Salario","Diferencia salario vs España","+0%;-0%;0%","DIVIDE([Salario 2024], [Salario España]) - 1"),
 ("3 Esfuerzo","Ranking esfuerzo","0",f"""
VAR v = [% sueldo contrato nuevo]
RETURN IF(ISFILTERED(dim_provincia), COUNTROWS(FILTER(ALLNOBLANKROW(dim_provincia[cod_prov]), [% sueldo contrato nuevo] > v)) + 1)"""),
 ("3 Esfuerzo","Nivel de esfuerzo","",f"""
VAR p = [% sueldo contrato nuevo]
RETURN IF(ISBLANK(p), BLANK(), IF(p <= 0.3, "Asumible (≤ 30 %)", IF(p <= 0.4, "Elevado (30-40 %)", "Muy elevado (> 40 %)")))"""),
 ("3 Esfuerzo","Texto ranking esfuerzo","",'FORMAT([Ranking esfuerzo], "0") & ".º de " & FORMAT(COUNTROWS(ALLNOBLANKROW(dim_provincia)), "0")'),
 ("3 Esfuerzo","Texto provincias por encima del 30 %","",'FORMAT([Provincias por encima del 30 %], "0") & " de " & FORMAT(COUNTROWS(ALLNOBLANKROW(dim_provincia)), "0")'),
]

def bloque_medida(folder, name, fmt, dax):
    dax = dax.strip("\n")
    lines = [f"\tmeasure {q(name)} = ```"] + ["\t\t\t" + l for l in dax.splitlines()] + ["\t\t\t```"]
    if fmt: lines.append(f"\t\tformatString: {fmt}")
    lines += [f"\t\tdisplayFolder: {folder}", f"\t\tlineageTag: {tag('_Medidas', name)}", ""]
    return lines

out = ["table _Medidas", f"\tlineageTag: {tag('table','_Medidas')}", ""]
for m in MEDIDAS: out += bloque_medida(*m)
out += ["\tcolumn x", "\t\tdataType: int64", "\t\tisHidden", "\t\tisNameInferred", f"\t\tlineageTag: {tag('_Medidas','x')}",
        "\t\tsummarizeBy: none", "\t\tsourceColumn: [x]", "", "\t\tannotation SummarizationSetBy = User", "",
        "\tpartition _Medidas = calculated", "\t\tmode: import", '\t\tsource = ROW("x", 0)', "",
        "\tannotation PBI_Id = medidas", ""]
(TBL/"_Medidas.tmdl").write_text("\n".join(out), encoding="utf-8")

# ---------------- Parámetro "Tu sueldo" ----------------
out = ["table 'Tu sueldo'", f"\tlineageTag: {tag('table','Tu sueldo')}", "",
       "\tmeasure 'Valor Tu sueldo' = SELECTEDVALUE('Tu sueldo'[Tu sueldo bruto anual], 24000)", "\t\tformatString: #,0 €",
       f"\t\tlineageTag: {tag('Tu sueldo','Valor Tu sueldo')}", "",
       "\tcolumn 'Tu sueldo bruto anual'", "\t\tdataType: int64", "\t\tformatString: #,0 €",
       f"\t\tlineageTag: {tag('Tu sueldo','Tu sueldo bruto anual')}", "\t\tsummarizeBy: none", "\t\tsourceColumn: [Value]", "",
       "\t\textendedProperty ParameterMetadata =", "\t\t\t\t{", '\t\t\t\t  "version": 0', "\t\t\t\t}", "",
       "\t\tannotation SummarizationSetBy = User", "",
       "\tpartition 'Tu sueldo' = calculated", "\t\tmode: import", "\t\tsource = GENERATESERIES(12000, 60000, 500)", "",
       "\tannotation PBI_Id = tu_sueldo", ""]
(TBL/"Tu sueldo.tmdl").write_text("\n".join(out), encoding="utf-8")

# ---------------- Relaciones (estrella) ----------------
REL = [("fact_alquiler_provincia","cod_prov","dim_provincia","cod_prov"),
       ("fact_alquiler_provincia","anio","dim_anio","anio"),
       ("fact_alquiler_municipio","cod_prov","dim_provincia","cod_prov"),
       ("fact_salarios","cod_prov","dim_provincia","cod_prov"),
       ("fact_salarios","anio","dim_anio","anio"),
       ("fact_salarios","tramo_edad","dim_tramo_edad","tramo_edad"),
       ("fact_ipva","cod_prov","dim_provincia","cod_prov"),
       ("fact_ipva","anio","dim_anio","anio"),
       ("fact_alquiler_espana","anio","dim_anio","anio"),
       ("fact_ipva_espana","anio","dim_anio","anio"),
       ("fact_salarios_espana","anio","dim_anio","anio"),
       ("fact_salarios_espana","tramo_edad","dim_tramo_edad","tramo_edad")]
rel = []
for ft, fc, dt, dc in REL:
    rid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ft}.{fc}->{dt}.{dc}"))
    rel += [f"relationship {rid}", f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {dt}.{dc}", ""]
(SM/"relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")

# ---------------- Parámetro de ruta (Power Query) ----------------
(SM/"expressions.tmdl").write_text("\n".join([
    f'expression RutaDatos = "{WIN_DATA}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
    f"\tlineageTag: {tag('expr','RutaDatos')}", "", "\tannotation PBI_ResultType = Text", ""]), encoding="utf-8")

# ---------------- model.tmdl: referencias de tablas ----------------
model = (SM/"model.tmdl").read_text(encoding="utf-8")
for t in ["_Medidas", "Tu sueldo", "fact_alquiler_espana", "fact_ipva_espana", "fact_salarios_espana"]:
    ref = f"ref table {q(t)}"
    if ref not in model:
        model = model.replace("ref table dim_anio", f"{ref}\nref table dim_anio", 1)
model = model.replace("__PBI_TimeIntelligenceEnabled = 1", "__PBI_TimeIntelligenceEnabled = 0")
(SM/"model.tmdl").write_text(model, encoding="utf-8")
print("Modelo reescrito:", sorted(p.name for p in TBL.glob("*.tmdl")))
