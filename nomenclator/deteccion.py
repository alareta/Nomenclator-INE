"""Detección automática de año y provincias a partir del CONTENIDO de un
fichero del Nomenclátor (no del nombre de fichero, más fiable): el año
aparece en los nombres de columna de la cabecera (p.ej. 'Total 2021',
'Población de Hecho 1981') y las provincias en la columna 1 de cada
fila de datos.

Usado por la interfaz web (Fase 3) en la pantalla de confirmación. Con
ficheros nacionales no tiene sentido mostrar "la provincia" del
fichero (contiene todas): lo útil es el RECUENTO de provincias
distintas presentes, tanto para dar contexto al usuario como para que
salte a la vista si ha subido por error un fichero recortado (p.ej.
solo 1 provincia en vez de las ~52 esperadas).

`detectar_hoja_cabecera_y_filas` ya carga todas las filas de datos en
memoria (no hay forma más barata de leer un .xlsx con openpyxl), así
que recorrer esas filas para sacar el conjunto de provincias no cuesta
una lectura adicional del fichero: es aprovechar un dato que ya se
tiene, no un escaneo extra.
"""

from __future__ import annotations

import re
from pathlib import Path

from .lectura import detectar_hoja_cabecera_y_filas, preparar_fichero

_PATRON_ANIO = re.compile(r"(19|20)\d{2}")


def detectar_anio(fila_cabecera: tuple) -> int | None:
    """Busca un año de 4 dígitos (19xx/20xx) en los nombres de columna."""
    texto = " ".join(str(c) for c in fila_cabecera if c is not None)
    coincidencia = _PATRON_ANIO.search(texto)
    return int(coincidencia.group()) if coincidencia else None


def detectar_provincias(filas_datos: list[tuple]) -> set[str]:
    """Códigos de provincia (2 dígitos) distintos presentes en TODAS las
    filas de datos del fichero (columna 1, 'Provincia'). En un fichero
    nacional real da ~52 códigos distintos (50 provincias + Ceuta y
    Melilla); un valor bajo (1-2) es indicio de que el fichero subido
    no es nacional, o de que solo cubre una provincia."""
    provincias: set[str] = set()
    for fila in filas_datos:
        if not fila:
            continue
        valor = fila[0]
        if valor is None:
            continue
        valor = str(valor).strip()
        if valor:
            provincias.add(valor)
    return provincias


def detectar_anio_y_provincias(
    path_original: str | Path, dir_trabajo: str | Path
) -> tuple[int | None, set[str]]:
    """Prepara el fichero (validación si hace falta) y detecta el año
    (de la cabecera) y el conjunto de provincias distintas presentes en
    todas las filas de datos."""
    path_xlsx = preparar_fichero(path_original, dir_trabajo)
    cabecera, filas_datos = detectar_hoja_cabecera_y_filas(path_xlsx)
    anio = detectar_anio(cabecera)
    provincias = detectar_provincias(filas_datos)
    return anio, provincias
