"""Parseo de las filas de un año concreto a UnidadRaw, y construcción de
las tablas de concejos/municipios con su validación cruzada.

Ver §3 y §4 de proyecto_utilidad_web_nomenclator.md para el formato de
entrada y el criterio de extracción de filas.
"""

from __future__ import annotations

from pathlib import Path

import re

from .lectura import detectar_hoja_y_filas, preparar_fichero
from .tipos import Discrepancia, UnidadRaw

FORMATO_1981 = "formato_1981"
FORMATO_1991PLUS = "formato_1991plus"

_RE_CODIGO_NOMBRE = re.compile(r"^(\d+)\s*(.*)$")


def detectar_formato(filas: list[tuple]) -> str:
    """Distingue el formato por el nº de columnas y la longitud del código
    de unidad poblacional en la primera fila de datos, sin asumir el año.
    """
    primera = filas[0]
    codigo, _ = _partir_codigo_nombre(primera[2])
    if len(primera) == 7 and len(codigo) == 4:
        return FORMATO_1981
    if len(primera) == 6 and len(codigo) == 6:
        return FORMATO_1991PLUS
    raise ValueError(
        f"Formato de fila no reconocido (columnas={len(primera)}, "
        f"código='{codigo}'): {primera!r}"
    )


def _partir_codigo_nombre(campo_unidad: str) -> tuple[str, str]:
    """'000000 ALEGRIA-DULANTZI' -> ('000000', 'ALEGRIA-DULANTZI').

    El código se extrae por el prefijo numérico, no por el primer
    "token" separado por espacio: alguna exportación del INE (visto en
    2011) pega el código al nombre sin espacio de por medio
    ('000000ALEGRIA-DULANTZI'), y un split por espacio se llevaría el
    campo entero como si fuera el código."""
    texto = str(campo_unidad).strip()
    coincidencia = _RE_CODIGO_NOMBRE.match(texto)
    if not coincidencia:
        raise ValueError(f"No se ha podido extraer el código de unidad poblacional de {texto!r}")
    codigo, nombre = coincidencia.group(1), coincidencia.group(2).strip()
    return codigo, nombre


def _limpiar_nombre_nivel(nombre: str) -> str:
    """Quita sufijos de nivel que a veces vienen pegados al nombre,
    p.ej. '*DISEMINADO* ALEGRÍA-DULANTZI' o 'MAESTU(NUCLEO)'."""
    nombre = nombre.replace("*DISEMINADO*", "").strip()
    for sufijo in ("(NUCLEO)", "(CAPITAL)"):
        if nombre.endswith(sufijo):
            nombre = nombre[: -len(sufijo)].strip()
    return nombre


def clasificar_codigo6(codigo: str) -> str:
    """AABBCC -> nivel de la fila.

    - municipio:  AABB == '0000' y CC == '00'
    - agregacion: CC == '00', BB == '00', AA != '00'  (agrupa concejos hijos)
    - concejo:    CC == '00', resto de casos (AABB propio, BB != '00',
                  o AA=='00' con BB!='00')
    - nucleo:     CC == '01'
    - diseminado: CC == '99'
    - otro:       cualquier otro caso no contemplado
    """
    if len(codigo) != 6:
        return "otro"
    aa, bb, cc = codigo[0:2], codigo[2:4], codigo[4:6]
    if aa == "00" and bb == "00" and cc == "00":
        return "municipio"
    if cc == "00" and bb == "00" and aa != "00":
        return "agregacion"
    if cc == "00":
        return "concejo"
    if cc == "01":
        return "nucleo"
    if cc == "99":
        return "diseminado"
    return "otro"


def clasificar_codigo4(codigo: str) -> str:
    """AABB (formato 1981) -> nivel de la fila. Análogo a
    clasificar_codigo6 para 1991+, pero sin desglose núcleo/diseminado
    (1981 no distingue eso, ver docstring de parsear_filas_1981):

    - municipio:  AABB == '0000'
    - agregacion: BB == '00', AA != '00' (fila "Diputación de X" /
                  "X (Diputación)" que agrupa a sus entidades hijas
                  AAyy -- mismo caso que las agregaciones de 1991+,
                  ver §3.1 del documento de diseño; hay que excluirla
                  para no duplicar población al sumar concejos)
    - concejo:    resto de casos (AABB propio, con BB != '00')
    - otro:       código que no tiene 4 dígitos
    """
    if len(codigo) != 4:
        return "otro"
    aa, bb = codigo[0:2], codigo[2:4]
    if aa == "00" and bb == "00":
        return "municipio"
    if bb == "00" and aa != "00":
        return "agregacion"
    return "concejo"


def parsear_filas_1981(filas: list[tuple], anio: int) -> list[UnidadRaw]:
    """Columnas: Provincia, Municipio, Unidad Poblacional, Pob.Hecho,
    Pob.Hecho Hombres, Pob.Hecho Mujeres, Pob.Derecho.

    Se usa Población de Derecho (última columna) para homogeneizar con
    el resto de años. Código de 4 dígitos AABB: '0000' = municipio;
    el resto son concejos u otras entidades, EXCEPTO las filas de
    agregación ("Diputación de X"), que se excluyen igual que en
    1991+ (ver clasificar_codigo4) -- no hay desglose núcleo/diseminado
    en este formato, esa distinción solo existe desde 1991.
    """
    unidades = []
    for fila in filas:
        provincia, municipio = str(fila[0]).strip(), str(fila[1]).strip()
        codigo, nombre_bruto = _partir_codigo_nombre(fila[2])
        poblacion_derecho = int(fila[6])
        nivel = clasificar_codigo4(codigo)
        unidades.append(
            UnidadRaw(
                provincia=provincia,
                municipio=municipio,
                codigo=codigo,
                nombre=_limpiar_nombre_nivel(nombre_bruto),
                poblacion=poblacion_derecho,
                anio=anio,
                nivel=nivel,
            )
        )
    return unidades


def parsear_filas_1991plus(filas: list[tuple], anio: int) -> list[UnidadRaw]:
    """Columnas: Provincia, Municipio, Unidad Poblacional, Total, Hombres, Mujeres."""
    unidades = []
    for fila in filas:
        provincia, municipio = str(fila[0]).strip(), str(fila[1]).strip()
        codigo, nombre_bruto = _partir_codigo_nombre(fila[2])
        total = int(fila[3])
        nivel = clasificar_codigo6(codigo)
        unidades.append(
            UnidadRaw(
                provincia=provincia,
                municipio=municipio,
                codigo=codigo,
                nombre=_limpiar_nombre_nivel(nombre_bruto),
                poblacion=total,
                anio=anio,
                nivel=nivel,
            )
        )
    return unidades


def parsear_fichero_anio(path_original: str | Path, anio: int, dir_trabajo: str | Path) -> list[UnidadRaw]:
    """Orquesta la lectura completa de un fichero de un año concreto."""
    path_xlsx = preparar_fichero(path_original, dir_trabajo)
    filas = detectar_hoja_y_filas(path_xlsx)
    formato = detectar_formato(filas)
    if formato == FORMATO_1981:
        return parsear_filas_1981(filas, anio)
    return parsear_filas_1991plus(filas, anio)


def extraer_municipios(unidades: list[UnidadRaw]) -> list[UnidadRaw]:
    return [u for u in unidades if u.nivel == "municipio"]


def extraer_concejos(unidades: list[UnidadRaw]) -> list[UnidadRaw]:
    """Filas de concejo de nivel más fino (agregaciones ya excluidas
    por clasificar_codigo6 / por ser formato plano en 1981)."""
    return [u for u in unidades if u.nivel == "concejo"]


def extraer_agregaciones(unidades: list[UnidadRaw]) -> list[UnidadRaw]:
    """Filas de agrupación estadística excluidas, para trazabilidad (§3.1)."""
    return [u for u in unidades if u.nivel == "agregacion"]


def validar_cuadre(unidades: list[UnidadRaw]) -> list[Discrepancia]:
    """Por cada municipio del año: suma de sus 'concejo' vs su fila 'municipio'.
    Devuelve solo las discrepancias (municipios que no cuadran)."""
    municipios = {(u.provincia, u.municipio): u for u in extraer_municipios(unidades)}
    sumas: dict[tuple[str, str], int] = {}
    for u in extraer_concejos(unidades):
        clave = (u.provincia, u.municipio)
        sumas[clave] = sumas.get(clave, 0) + u.poblacion

    discrepancias = []
    for clave, municipio in municipios.items():
        suma = sumas.get(clave, 0)
        if suma != municipio.poblacion:
            discrepancias.append(
                Discrepancia(
                    anio=municipio.anio,
                    provincia=municipio.provincia,
                    municipio=municipio.municipio,
                    municipio_nombre=municipio.nombre,
                    poblacion_municipio=municipio.poblacion,
                    suma_concejos=suma,
                )
            )
    return discrepancias
