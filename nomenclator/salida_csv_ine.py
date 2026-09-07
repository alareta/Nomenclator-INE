"""Exportación de los datos del INE ya procesados a CSV, un fichero por
año, combinando municipios y unidades poblacionales.

Este CSV es la "foto" del lado INE pensada para cruzarse después, como
paso independiente, con el CSV de códigos↔Q descargado de Wikidata (ver
la ruta /cruce y el módulo de cruce). Sale del procesado normal junto a
los Excel y los .tab.

Contiene TODAS las filas (no se filtra nada aquí): el filtrado a solo las
que obtienen Q ocurre en la fase de cruce, no en esta exportación. Un
fichero por año porque el cruce se opera año a año; la población es, por
tanto, una sola columna (la del año del fichero).

Columnas: codigo_ine, tipo, provincia, municipio, nombre, entidad_colectiva, poblacion
- codigo_ine: identificador en formato PP-MMM-EEEECC (ver tipos.codigo_ine),
  la clave con la que se cruza contra Wikidata.
- tipo: "municipio" o "unidad".
- provincia: código de provincia de 2 díg, tal cual del INE.
- municipio: nombre del municipio (en TODAS las filas, también en las de
  unidad, para poder agrupar/filtrar).
- nombre: nombre de la unidad poblacional; en las filas de municipio va
  vacío (el nombre del municipio ya está en la columna municipio).
- entidad_colectiva: nombre de la entidad colectiva (p.ej. parroquia) si
  la unidad pertenece a una; vacío en municipios y en unidades sin EC.
- poblacion: población del año del fichero; vacío si la entidad no tiene
  dato ese año (nunca 0 por "no existe": vacío significa "sin dato")."""

from __future__ import annotations

import csv
from pathlib import Path

from .texto import capitalizar_nombre_display
from .tipos import EntidadResultado, ResultadoProvincia, codigo_ine

CABECERA = [
    "codigo_ine",
    "tipo",
    "provincia",
    "municipio",
    "nombre",
    "entidad_colectiva",
    "poblacion",
]


def _fila_csv(entidad: EntidadResultado, anio: int) -> list:
    """Construye una fila del CSV para una entidad y un año.

    En las filas de municipio, "nombre" y "entidad_colectiva" van vacíos
    (no aplican). La población va vacía si no hay dato ese año."""
    es_municipio = entidad.tipo == "municipio"
    tipo = "municipio" if es_municipio else "unidad"
    nombre = "" if es_municipio else capitalizar_nombre_display(entidad.nombre)
    ec = "" if es_municipio or not entidad.ec_nombre else capitalizar_nombre_display(entidad.ec_nombre)
    pob = entidad.poblacion_por_anio.get(anio)
    return [
        codigo_ine(entidad),
        tipo,
        entidad.provincia,
        capitalizar_nombre_display(entidad.municipio_nombre),
        nombre,
        ec,
        "" if pob is None else pob,
    ]


def _filas_ordenadas(resultado: ResultadoProvincia) -> list[EntidadResultado]:
    """Municipios y unidades intercalados jerárquicamente: cada municipio
    seguido de sus propias unidades. Mismo orden que el Excel combinado,
    agrupando por (provincia, municipio_codigo)."""
    unidades_por_muni: dict[tuple[str, str], list[EntidadResultado]] = {}
    for c in resultado.concejos:
        unidades_por_muni.setdefault((c.provincia, c.municipio_codigo), []).append(c)

    filas: list[EntidadResultado] = []
    for muni in sorted(resultado.municipios, key=lambda m: (m.provincia, m.municipio_codigo)):
        filas.append(muni)
        unidades = unidades_por_muni.get((muni.provincia, muni.municipio_codigo), [])
        filas.extend(sorted(unidades, key=lambda e: e.entidad_id))
    return filas


def guardar_csv_ine_por_anio(
    resultado: ResultadoProvincia, anios: list[int], dir_salida: str | Path
) -> list[Path]:
    """Guarda un CSV del INE por cada año y devuelve la lista de rutas.

    Cada fichero se llama `ine_<anio>.csv` y contiene municipios y
    unidades combinados, todas las filas, con la población de ese año."""
    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)

    filas_entidades = _filas_ordenadas(resultado)
    rutas: list[Path] = []
    for anio in anios:
        ruta = dir_salida / f"ine_{anio}.csv"
        with ruta.open("w", encoding="utf-8", newline="") as f:
            escritor = csv.writer(f)
            escritor.writerow(CABECERA)
            for entidad in filas_entidades:
                escritor.writerow(_fila_csv(entidad, anio))
        rutas.append(ruta)
    return rutas
