"""Lectura y normalización de los ficheros del Nomenclátor INE.

Esta versión NO depende de LibreOffice: trabaja únicamente con ficheros
.xlsx ya "limpios". Si el usuario tiene un .xls antiguo, debe abrirlo con
Excel/LibreOffice/Numbers y guardarlo como .xlsx antes de subirlo (paso
manual, en vez de la conversión automática que hacía la versión anterior
del pipeline mediante `soffice`).
"""

from __future__ import annotations

from pathlib import Path

import openpyxl

CABECERA_ESPERADA = "Provincia"

INSTRUCCION_CONVERSION_MANUAL = (
    "Ábrelo con Excel, LibreOffice o Numbers y guárdalo como .xlsx "
    "(Archivo > Guardar como... > formato .xlsx) antes de subirlo."
)


class FicheroIlegible(Exception):
    """El fichero no se pudo leer (no es .xlsx legible)."""


# Caché de un único slot: guarda las hojas (nombre, filas) ya leídas del
# último fichero abierto por `_hojas_de`. En todo el pipeline (y en los
# tests), `preparar_fichero` se llama siempre seguida inmediatamente de
# `detectar_hoja_y_filas`/`detectar_hoja_cabecera_y_filas` sobre el MISMO
# path -- nunca aisladas ni intercaladas con otro fichero. Este caché
# evita que ambas funciones abran y recorran el mismo .xlsx nacional dos
# veces (coste notable a escala nacional, ver §10.10). Si en algún caso se
# llamase con un path distinto al cacheado, simplemente se relee desde
# disco: nunca puede devolver datos de un fichero equivocado, en el peor
# caso se pierde el ahorro de la caché.
_CACHE_ULTIMA_LECTURA: dict | None = None


def _leer_todas_las_hojas(path: Path) -> list[tuple[str, list[tuple]]]:
    """Abre el workbook UNA sola vez y devuelve, por cada hoja, su nombre
    y todas sus filas ya materializadas en listas. Cierra el workbook
    explícitamente (`wb.close()`) para liberar el .zip subyacente y las
    estructuras internas de openpyxl en cuanto se termina de leer, en vez
    de depender de cuándo pase el recolector de basura -- relevante en
    máquinas con poca RAM libre."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        return [
            (nombre_hoja, list(wb[nombre_hoja].iter_rows(values_only=True)))
            for nombre_hoja in wb.sheetnames
        ]
    finally:
        wb.close()


def _hojas_de(path: Path) -> list[tuple[str, list[tuple]]]:
    """Devuelve las hojas (nombre, filas) de `path`, reutilizando la
    lectura si ya está en el caché de un único slot; si no, lee de disco
    y la deja cacheada para la siguiente llamada."""
    global _CACHE_ULTIMA_LECTURA
    path = Path(path)
    if _CACHE_ULTIMA_LECTURA is not None and _CACHE_ULTIMA_LECTURA["path"] == path:
        return _CACHE_ULTIMA_LECTURA["hojas"]
    hojas = _leer_todas_las_hojas(path)
    _CACHE_ULTIMA_LECTURA = {"path": path, "hojas": hojas}
    return hojas


def _xlsx_tiene_datos_legibles(path: Path) -> bool:
    """Comprueba que el fichero no solo carga, sino que además se pueden
    leer filas de datos reales (mínimo 2 filas con contenido). Filtra el
    caso de .xlsx con referencias internas corruptas, que "cargan" sin
    lanzar excepción pero devuelven las hojas vacías."""
    try:
        hojas = _hojas_de(path)
    except Exception:
        return False
    for _, filas in hojas:
        filas_con_datos = sum(1 for fila in filas if any(c is not None for c in fila))
        if filas_con_datos >= 2:
            return True
    return False


def preparar_fichero(path_original: str | Path, dir_trabajo: str | Path | None = None) -> Path:
    """Devuelve la ruta a un .xlsx legible por openpyxl.

    `dir_trabajo` se mantiene en la firma por compatibilidad con el resto
    del pipeline, pero no se usa: no hay conversión, solo validación.
    """
    path_original = Path(path_original)

    if path_original.suffix.lower() != ".xlsx":
        raise FicheroIlegible(
            f"'{path_original.name}' no es un fichero .xlsx (formato antiguo .xls "
            f"no soportado directamente en esta versión). {INSTRUCCION_CONVERSION_MANUAL}"
        )

    if not _xlsx_tiene_datos_legibles(path_original):
        raise FicheroIlegible(
            f"'{path_original.name}' no se puede leer correctamente (referencias "
            f"internas dañadas, un problema visto en algunos ficheros del INE). "
            f"{INSTRUCCION_CONVERSION_MANUAL}"
        )

    return path_original


def _es_fila_cabecera(fila: tuple) -> bool:
    return bool(fila) and fila[0] == CABECERA_ESPERADA


def _num_columnas_significativas(cabecera: tuple) -> int:
    """Nº de columnas reales de la cabecera, ignorando columnas
    fantasma al final (todo None) -- visto en algunas exportaciones
    del INE (p.ej. 2011) que añaden una columna de más sin datos ni
    título, y que si no se recorta rompe la detección de formato en
    parseo.detectar_formato (cuenta el nº de columnas)."""
    n = len(cabecera)
    while n > 0 and cabecera[n - 1] is None:
        n -= 1
    return n


def _recortar_a_columnas_significativas(filas: list[tuple], n: int) -> list[tuple]:
    """Recorta cabecera y datos a las `n` columnas reales, para que
    todas las filas del fichero (independientemente de si esa fila en
    concreto tenía o no relleno en la columna fantasma) queden con la
    misma longitud consistente."""
    return [fila[:n] for fila in filas]


def detectar_hoja_cabecera_y_filas(path_xlsx: str | Path) -> tuple[tuple, list[tuple]]:
    """Elige la hoja de datos y devuelve (fila_cabecera, filas_de_datos).

    - Escoge la primera hoja cuya primera fila no vacía sea la cabecera
      "Provincia..." (ignora hojas vacías o de desglose adicional, p.ej.
      'Nacionalidad'/'Edad' en ficheros recientes -- el Total es idéntico
      en todas, basta con la primera hoja de datos).
    - Salta dinámicamente todas las filas de cabecera repetidas (caso
      visto en 2011: dos filas de cabecera idénticas seguidas).
    - Recorta cualquier columna fantasma al final (todo None en la
      cabecera), también visto en 2011 -- si no, el nº de columnas no
      coincide con lo que espera detectar_formato.
    """
    for _, filas in _hojas_de(path_xlsx):
        primera_no_vacia = next((f for f in filas if any(c is not None for c in f)), None)
        if primera_no_vacia is not None and _es_fila_cabecera(primera_no_vacia):
            idx = 0
            while idx < len(filas) and _es_fila_cabecera(filas[idx]):
                idx += 1
            datos = [f for f in filas[idx:] if any(c is not None for c in f)]
            if datos:
                n = _num_columnas_significativas(primera_no_vacia)
                cabecera = primera_no_vacia[:n]
                datos = _recortar_a_columnas_significativas(datos, n)
                return cabecera, datos

    raise FicheroIlegible(f"No se encontró una hoja de datos válida en {path_xlsx}")


def detectar_hoja_y_filas(path_xlsx: str | Path) -> list[tuple]:
    """Como detectar_hoja_cabecera_y_filas, pero devuelve solo las filas de datos."""
    _, datos = detectar_hoja_cabecera_y_filas(path_xlsx)
    return datos
