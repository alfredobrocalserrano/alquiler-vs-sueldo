"""
Prepara los datos del reporte "¿Se puede vivir de alquiler con un sueldo español?"
Fuentes:
  - AEAT, Mercado de trabajo y pensiones en las fuentes tributarias (salarios por provincia y edad, 2015-2024)
  - AEAT, Estadística de viviendas declaradas en el IRPF 2024 (alquiler medio, total y nuevos contratos)
  - INE, Índice de Precios de Vivienda en Alquiler (IPVA), tabla 59059, base 2015
Ámbito: territorio fiscal común (sin País Vasco ni Navarra, que tienen haciendas forales).
Salida: carpeta datos_limpios/ con un modelo en estrella listo para Power BI.
"""
from pathlib import Path
import pandas as pd

BASE = Path(__file__).parent
RAW = BASE / "raw"
OUT = BASE / "datos_limpios"
OUT.mkdir(exist_ok=True)

def guarda(df, nombre):
    """CSV en UTF-8 sin BOM; las columnas numéricas sin decimales se escriben como enteros."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype.kind == "f" and df[c].dropna().apply(float.is_integer).all():
            df[c] = df[c].astype("Int64")
    df.to_csv(OUT/nombre, index=False, encoding="utf-8")

def num(s):
    """'1.234,5' -> 1234.5"""
    s = str(s).strip()
    if s in ("", "nan", "-"):
        return None
    return float(s.replace(".", "").replace(",", "."))

# ---------- Dimensión provincia ----------
PROV = [  # cod, nombre INE, CCAA
 ("02","Albacete","Castilla-La Mancha"),("03","Alicante/Alacant","Comunitat Valenciana"),("04","Almería","Andalucía"),
 ("05","Ávila","Castilla y León"),("06","Badajoz","Extremadura"),("07","Balears, Illes","Illes Balears"),
 ("08","Barcelona","Cataluña"),("09","Burgos","Castilla y León"),("10","Cáceres","Extremadura"),("11","Cádiz","Andalucía"),
 ("12","Castellón/Castelló","Comunitat Valenciana"),("13","Ciudad Real","Castilla-La Mancha"),("14","Córdoba","Andalucía"),
 ("15","Coruña, A","Galicia"),("16","Cuenca","Castilla-La Mancha"),("17","Girona","Cataluña"),("18","Granada","Andalucía"),
 ("19","Guadalajara","Castilla-La Mancha"),("21","Huelva","Andalucía"),("22","Huesca","Aragón"),("23","Jaén","Andalucía"),
 ("24","León","Castilla y León"),("25","Lleida","Cataluña"),("26","Rioja, La","La Rioja"),("27","Lugo","Galicia"),
 ("28","Madrid","Comunidad de Madrid"),("29","Málaga","Andalucía"),("30","Murcia","Región de Murcia"),("32","Ourense","Galicia"),
 ("33","Asturias","Principado de Asturias"),("34","Palencia","Castilla y León"),("35","Palmas, Las","Canarias"),
 ("36","Pontevedra","Galicia"),("37","Salamanca","Castilla y León"),("38","Santa Cruz de Tenerife","Canarias"),
 ("39","Cantabria","Cantabria"),("40","Segovia","Castilla y León"),("41","Sevilla","Andalucía"),("42","Soria","Castilla y León"),
 ("43","Tarragona","Cataluña"),("44","Teruel","Aragón"),("45","Toledo","Castilla-La Mancha"),("46","Valencia/València","Comunitat Valenciana"),
 ("47","Valladolid","Castilla y León"),("49","Zamora","Castilla y León"),("50","Zaragoza","Aragón"),("51","Ceuta","Ceuta"),("52","Melilla","Melilla"),
]
dim = pd.DataFrame(PROV, columns=["cod_prov","provincia","ccaa"])
# Nombre corto para mostrar y nombre para el mapa (reconocible por Bing/Azure Maps)
corto = {"Alicante/Alacant":"Alicante","Castellón/Castelló":"Castellón","Valencia/València":"Valencia","Balears, Illes":"Illes Balears",
         "Coruña, A":"A Coruña","Rioja, La":"La Rioja","Palmas, Las":"Las Palmas"}
dim["provincia_corta"] = dim.provincia.map(lambda p: corto.get(p, p))
dim["ubicacion_mapa"] = dim.provincia_corta + ", España"
dim["es_alicante"] = dim.cod_prov.eq("03")  # para resaltar Alicante en los gráficos
guarda(dim, "dim_provincia.csv")

alias = {r.provincia: r.cod_prov for r in dim.itertuples()}
alias.update({r.provincia_corta: r.cod_prov for r in dim.itertuples()})
alias.update({
 "Asturias, Principado de":"33","Principado de Asturias":"33","Balears,Illes":"07","Illes Balears":"07",
 "S. C. Tenerife":"38","Madrid, Comunidad de":"28","Comunidad de Madrid":"28","Murcia, Región de":"30","Región de Murcia":"30",
 "Ciudad de Ceuta":"51","Ciudad de Melilla":"52","Castellón":"12","Alicante":"03","Valencia":"46",
})
def cod(nombre):
    return alias.get(nombre.strip())

# ---------- Salarios ----------
rows = []
for line in (RAW/"salarios_edad_2024.txt").read_text(encoding="utf-8").splitlines():
    if line.startswith("#") or not line.strip():
        continue
    nombre, *celdas = line.split(";")
    c = "00" if nombre == "Total" else cod(nombre)
    assert c, f"Provincia no reconocida (salarios): {nombre}"
    for tramo, cel in zip(["Total","18-25","26-35","36-45","46-55","56-65"], celdas):
        if tramo == "18-25":  # excluido: muchos contratos parciales, el salario anual medio no es comparable
            continue
        asal, sal = cel.split("/")
        rows.append((c, 2024, tramo, num(asal), num(sal)))
for line in (RAW/"salarios_historico_2015_2023.txt").read_text(encoding="utf-8").splitlines():
    anio, datos = line.split(";", 1)
    for par in datos.split("|"):
        nombre, sal = par.split("=")
        c = "00" if nombre == "Total" else cod(nombre)
        assert c, f"Provincia no reconocida (histórico {anio}): {nombre}"
        rows.append((c, int(anio), "Total", None, num(sal)))
sal = pd.DataFrame(rows, columns=["cod_prov","anio","tramo_edad","asalariados","salario_medio_anual"])
assert sal.groupby(["anio","tramo_edad"]).size().eq(49).all(), "Faltan provincias en salarios"
guarda(sal[sal.cod_prov != "00"], "fact_salarios.csv")
guarda(sal[sal.cod_prov == "00"].drop(columns="cod_prov"), "fact_salarios_espana.csv")  # total España en tabla aparte: sin filas huérfanas en dim_provincia

# ---------- Alquiler por provincia (2024) ----------
def lee_pipes(f):
    return [l.split("|") for l in (RAW/f).read_text(encoding="utf-8").splitlines() if l.strip()]
a = pd.DataFrame(lee_pipes("alquiler_prov_2024.txt"),
                 columns=["nombre","viv_con_valor","viv_arrendadas","alquiler_medio","alquiler_m2","m2_medios","dias_alquiler","valor_ref","rentab"])
n = pd.DataFrame(lee_pipes("alquiler_nuevos_prov_2024.txt"),
                 columns=["nombre","alq_medio_chk","alquiler_nuevos","m2_chk","m2_nuevos","vr","vr_n","rent","rent_n"])
alq = a.merge(n[["nombre","alq_medio_chk","alquiler_nuevos","m2_nuevos"]], on="nombre")
for col in alq.columns[1:]:
    alq[col] = alq[col].map(num)
assert (alq.alquiler_medio == alq.alq_medio_chk).all(), "Las dos tablas de alquiler no cuadran"
alq["cod_prov"] = alq.nombre.map(lambda x: "00" if x == "Total" else cod(x))
assert alq.cod_prov.notna().all()
alq["anio"] = 2024
alq = alq[["cod_prov","anio","viv_arrendadas","alquiler_medio","alquiler_nuevos","alquiler_m2","m2_medios"]]
guarda(alq[alq.cod_prov != "00"], "fact_alquiler_provincia.csv")
guarda(alq[alq.cod_prov == "00"].drop(columns="cod_prov"), "fact_alquiler_espana.csv")

# ---------- Alquiler por municipio (>20.000 hab., 2024) ----------
m = pd.read_csv(RAW/"alquiler_municipios_2024.txt", sep=";", header=None, dtype=str,
                names=["cod_muni","municipio","prov_nombre","viv_arrendadas","alquiler_medio","alquiler_m2","m2_medios"])
nv = pd.Series(dict(x.split(";") for x in (RAW/"alquiler_nuevos_municipios_2024.txt").read_text(encoding="utf-8").split()))
m["alquiler_nuevos"] = m.cod_muni.map(nv)
for col in ["viv_arrendadas","alquiler_medio","alquiler_m2","m2_medios","alquiler_nuevos"]:
    m[col] = m[col].map(num)
m["cod_prov"] = m.cod_muni.str[:2]
assert set(m.cod_prov) <= set(dim.cod_prov), "Municipio con provincia desconocida"
assert m.alquiler_nuevos.notna().all()
m["ubicacion_mapa"] = m.municipio.str.split("/").str[0] + ", " + m.cod_prov.map(dim.set_index("cod_prov").provincia_corta) + ", España"
guarda(m.drop(columns=["prov_nombre","alquiler_m2","m2_medios"]), "fact_alquiler_municipio.csv")

# ---------- IPVA (INE) ----------
ip = pd.read_csv(BASE/"59059.csv", sep=";", encoding="utf-8-sig", dtype=str)
ip = ip[(ip["Type of data"] == "Index") & (ip["Size of the dwelling"] == "Total")].copy()
ip["cod_prov"] = ip["Provinces"].fillna("00 Total").str[:2]
ip["anio"] = ip["Periodo"].astype(int)
ip["indice_alquiler"] = ip["Total"].map(num)
ip = ip[ip.anio >= 2015][["cod_prov","anio","indice_alquiler"]].sort_values(["cod_prov","anio"])
guarda(ip[ip.cod_prov != "00"], "fact_ipva.csv")
guarda(ip[ip.cod_prov == "00"].drop(columns="cod_prov"), "fact_ipva_espana.csv")

# ---------- Tablas auxiliares ----------
guarda(pd.DataFrame({"anio": range(2015, 2025)}), "dim_anio.csv")
guarda(pd.DataFrame({"tramo_edad":["Total","26-35","36-45","46-55","56-65"],"orden":range(5),
              "etiqueta":["Todas las edades","26 a 35 años","36 a 45 años","46 a 55 años","56 a 65 años"]}
            ), "dim_tramo_edad.csv")

print("OK")
for f in sorted(OUT.glob("*.csv")):
    print(f.name, len(pd.read_csv(f)))
