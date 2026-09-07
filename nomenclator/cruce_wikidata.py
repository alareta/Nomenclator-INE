"""Cruce de los datos del INE con los códigos↔Q de Wikidata, y
generación del fichero tabular (.tab) combinado para Wikimedia Commons,
con el ítem Q ya adjudicado.

Es una herramienta independiente del procesado del Nomenclátor: parte de
dos ficheros y no necesita reprocesar los .xlsx del INE ni ninguna sesión
en memoria.

Entradas:
- CSV del INE (el que genera salida_csv_ine.py, un fichero por año):
  columnas codigo_ine, tipo, provincia, municipio, nombre,
  entidad_colectiva, poblacion.
- CSV de Wikidata (descarga de una consulta SPARQL): columnas item
  (URL .../Qxxxx) y value (código INE en crudo).

Salida:
- Un .tab combinado (municipios + unidades en el mismo fichero) que
  contiene SOLO las filas cuyo código encontró Q en Wikidata ese año.

Sustituye al generador anterior de .tab separados por tipo
(salida_tabular_commons.py, eliminado): un .tab sin Q no aporta nada para
Commons, así que el .tab pasa a ser exclusivamente producto de este
cruce. Las filas sin Q no aparecen en el .tab; el universo completo (con
y sin Q) queda en el CSV del INE, que las lleva todas.

Formato del .tab (revisado para caber bajo el límite de 2 MB de Commons,
ver bitácora §10.11):
- Sin columna "tipo": es deducible del propio código (termina en
  "000000" -> municipio) y de si "unidad" va vacío (municipio) o relleno
  (unidad). No aporta información que no esté ya en las otras columnas.
- Código INE sin guiones (PPMMMEEEECC en crudo), coherente con el
  formato del `value` de Wikidata (P772), que tampoco los lleva. Es un
  cambio cosmético: como el campo es de tipo "string" en el schema, los
  ceros a la izquierda están a salvo con o sin guiones.
- Títulos de columna solo en inglés (Commons es un proyecto
  internacional; no se usa el objeto multilingüe con "es"+"en", solo
  "en", igual que "description" y "sources").
- La columna se llama "unidad" en el .tab (antes "nombre"), para no
  confundirla con el nombre del municipio. Esto es solo el campo de
  salida de este fichero: el CSV del INE (salida_csv_ine.py) conserva su
  columna "nombre" tal cual, sin tocar.
- JSON compacto (sin indentado): el indentado de `json.dumps` resultó
  ser, medido sobre el fichero real de 2025, el mayor contribuyente al
  tamaño del fichero (más que la columna "tipo" y los guiones juntos:
  ~700 KB de los ~2,4 MB totales). Commons no necesita el indentado para
  nada (se edita vía la interfaz de Tabular Data), así que se elimina.

Normalización de los códigos de Wikidata: el `value` viene en crudo, sin
guiones, y con longitud variable según el nivel:
- 5 dígitos  -> municipio  PPMMM        -> "PP-MMM-000000"
- 11 dígitos -> unidad      PPMMMEEEE CC -> "PP-MMM-EEEECC"
- cualquier otra longitud (p.ej. 2 díg = provincia entera, o algún
  código de 6 díg suelto) no corresponde a un municipio ni a una unidad
  de nuestros datos: se deja sin normalizar y, al no coincidir con
  ningún código del INE, simplemente no cruza. No se inventan ceros ni
  se fuerza forma: el dato de Wikidata se respeta tal cual.

Esta normalización con guiones se mantiene tal cual como formato interno
de cruce (es el mismo formato que usa `codigo_ine` en el CSV del INE, así
que las claves de ambos lados coinciden); los guiones solo se quitan al
escribir la fila final en el .tab, no en la clave de cruce.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .tipos import (
    CRITERIO_CENSO_ANUAL,
    CRITERIO_DERECHO,
    CRITERIO_PADRON,
    criterio_poblacion_anio,
)

LICENCIA = "CC0-1.0"
PREFIJO_PAGINA = "Population ESP"

FUENTE_DATOS = (
    "Instituto Nacional de Estadística (Spain), Nomenclátor de "
    "población. Cross-matched with Wikidata items by INE code."
)

_CRITERIO_A_TEXTO = {
    CRITERIO_DERECHO: "1981 Population Census (de jure)",
    CRITERIO_PADRON: "Continuous Municipal Register",
    CRITERIO_CENSO_ANUAL: "Annual Population Census",
}

# Esquema del .tab combinado: municipios y unidades en el mismo fichero.
# Sin columna "tipo": el municipio se reconoce porque "unidad" va vacío
# (y el código termina en "000000"); la unidad, porque "unidad" va
# relleno. Títulos solo en inglés (ver docstring del módulo).
_CAMPOS = [
    {"name": "codigo_ine", "type": "string", "title": {"en": "INE code"}},
    {"name": "unidad", "type": "string", "title": {"en": "Unit"}},
    {"name": "municipio", "type": "string", "title": {"en": "Municipality"}},
    {"name": "poblacion", "type": "number", "title": {"en": "Population"}},
    {"name": "id_wikidata", "type": "string", "title": {"en": "Wikidata item"}},
]

_RE_Q = re.compile(r"(Q\d+)\s*$")
_RE_ANIO = re.compile(r"(\d{4})")


def normalizar_codigo_wikidata(value: str) -> str:
    """Convierte un código INE en crudo de Wikidata al formato
    PP-MMM-EEEECC (formato interno de cruce, con guiones, igual que
    `codigo_ine` en el CSV del INE). Si la longitud no es 5 ni 11,
    devuelve el valor tal cual (no casará con ningún código del INE, y
    así se queda fuera del cruce sin inventarle forma).

    Los guiones se quitan solo al escribir la fila final del .tab (ver
    `generar_datos_tab_cruzado`), no aquí: aquí hacen falta para que la
    clave coincida con la de `codigo_ine`."""
    v = value.strip()
    if len(v) == 5 and v.isdigit():
        return f"{v[0:2]}-{v[2:5]}-000000"
    if len(v) == 11 and v.isdigit():
        return f"{v[0:2]}-{v[2:5]}-{v[5:11]}"
    return v


def _extraer_q(item: str) -> str | None:
    """Saca el identificador Qxxxx de una URL de Wikidata (o de un valor
    que ya sea el propio Q). None si no se reconoce."""
    m = _RE_Q.search(item.strip())
    return m.group(1) if m else None


def construir_cruce(ruta_query_csv: str | Path) -> dict[str, str]:
    """Lee el CSV de Wikidata (columnas item, value) y devuelve el
    diccionario {codigo_ine_normalizado: Q}.

    Si un mismo código apareciera repetido, gana la última aparición
    (situación no esperada; Wikidata debería dar un Q por código)."""
    cruce: dict[str, str] = {}
    with Path(ruta_query_csv).open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            item = (fila.get("item") or "").strip()
            value = (fila.get("value") or "").strip()
            if not item or not value:
                continue
            q = _extraer_q(item)
            if not q:
                continue
            cruce[normalizar_codigo_wikidata(value)] = q
    return cruce


def detectar_anio_de_nombre(nombre: str) -> int | None:
    """Extrae un año de 4 dígitos del nombre de fichero (p.ej.
    'ine_2025.csv' -> 2025). None si no hay ninguno."""
    m = _RE_ANIO.search(nombre)
    return int(m.group(1)) if m else None


def _descripcion_anio(anio: int) -> dict[str, str]:
    criterio_texto = _CRITERIO_A_TEXTO[criterio_poblacion_anio(anio)]
    return {
        "en": (
            f"Population of Spanish municipalities and population entities "
            f"as of 1 January {anio} ({criterio_texto}), matched with the "
            f"corresponding Wikidata item. Only entities with a Wikidata "
            f"item are included."
        )
    }


def nombre_pagina_tab_anio(anio: int) -> str:
    """Nombre de página en Commons (sin el prefijo 'Data:'), p.ej.
    'Population ESP 2025.tab'. Sin sufijo de tipo: el fichero combina
    municipios y unidades."""
    return f"{PREFIJO_PAGINA} {anio}.tab"


def nombre_fichero_tab_anio(anio: int) -> str:
    """Como nombre_pagina_tab_anio pero apto para nombre de fichero en
    disco (espacios -> guiones bajos)."""
    return nombre_pagina_tab_anio(anio).replace(" ", "_")


def generar_datos_tab_cruzado(ruta_ine_csv: str | Path, cruce: dict[str, str], anio: int) -> dict:
    """Construye el contenido JSON del .tab combinado de un año a partir
    del CSV del INE y el diccionario de cruce.

    Conserva SOLO las filas cuyo codigo_ine está en `cruce` (tienen Q).
    Las filas sin población se omiten también (no se generan huecos).

    El código se escribe SIN guiones (coherente con el `value` crudo de
    Wikidata); no se incluye columna "tipo" (deducible de "unidad" vacío
    o no, y de la terminación del código)."""
    filas = []
    with Path(ruta_ine_csv).open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        for r in lector:
            codigo = (r.get("codigo_ine") or "").strip()
            q = cruce.get(codigo)
            if not q:
                continue  # sin correspondencia en Wikidata: fuera del .tab
            pob = (r.get("poblacion") or "").strip()
            if pob == "":
                continue  # sin dato de población ese año
            filas.append([
                codigo.replace("-", ""),
                (r.get("nombre") or "").strip(),
                (r.get("municipio") or "").strip(),
                int(pob),
                q,
            ])

    return {
        "license": LICENCIA,
        "description": _descripcion_anio(anio),
        "sources": FUENTE_DATOS,
        "schema": {"fields": _CAMPOS},
        "data": filas,
    }


def guardar_tab_cruzado(
    ruta_ine_csv: str | Path,
    ruta_query_csv: str | Path,
    anio: int,
    dir_salida: str | Path,
) -> tuple[Path, int, int]:
    """Genera y guarda el .tab combinado con Q para un año.

    Devuelve (ruta, n_filas_con_q, n_codigos_cruce): la ruta escrita, el
    número de filas que acabaron en el .tab (con Q y población), y el
    tamaño del diccionario de cruce (para informar al usuario).

    El JSON se escribe compacto (sin indentado): medido sobre el
    fichero real de 2025, el indentado por sí solo suponía ~700 KB de
    los ~2,4 MB totales, más que el resto de recortes juntos."""
    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    cruce = construir_cruce(ruta_query_csv)
    datos = generar_datos_tab_cruzado(ruta_ine_csv, cruce, anio)
    ruta = dir_salida / nombre_fichero_tab_anio(anio)
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return ruta, len(datos["data"]), len(cruce)
