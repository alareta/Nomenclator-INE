"""Generación del wikitexto de {{Gráfica de evolución}} por entidad.

⚠ DESCONECTADO del flujo activo de la herramienta (decisión: se
abandona el plan de generar wikitexto por entidad al pasar a trabajar
con ficheros nacionales por año — ver proyecto_utilidad_web_nomenclator.md).
`app.py` ya no importa ni llama a nada de este módulo. Se conserva el
fichero tal cual, sin mantenimiento activo, por si en algún momento
hiciera falta recuperar el formato; puede eliminarse sin más impacto
que borrar este comentario y `test_salida.py`::TestWikitexto* si se
decide limpiar el repositorio del todo.

Replica literalmente el formato validado manualmente para Álava
(ver concejos_alava_wikitexto.txt aportado por el usuario y §6.2 del
documento de diseño, ahora también marcado como abandonado en ese
documento).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

from .texto import capitalizar_nombre_display
from .tipos import EntidadResultado

URL_NOMENCLATOR = "http://www.ine.es/nomen2/index.do"
TITULO_CITA = "Nomenclátor: Población del Padrón Continuo por Unidad Poblacional"
AUTOR_CITA = "Instituto Nacional de Estadística (España)"
COLOR_LEYENDA = "#88c2cc"

LEYENDA_SOLO_PADRON = (
    "Población del [[padrón municipal]] según el "
    "[[Instituto Nacional de Estadística (España)|INE]]."
)
LEYENDA_SOLO_1981 = (
    "[[Población de derecho]] según los censos de población del "
    "[[Instituto Nacional de Estadística (España)|INE]]."
)
LEYENDA_MEZCLA = (
    "[[Población de derecho]] (1981) y población del [[padrón municipal]] "
    "(resto de años) según el [[Instituto Nacional de Estadística (España)|INE]]."
)

SUFIJO_DESAPARECIDO = " (desaparecido/Agregado)"


def nombre_para_mostrar(entidad: EntidadResultado) -> str:
    """Nombre capitalizado, con el sufijo de 'desaparecido' si aplica."""
    base = capitalizar_nombre_display(entidad.nombre)
    if entidad.estado_emparejamiento == "desaparecido":
        return base + SUFIJO_DESAPARECIDO
    return base


def calcular_color_n(anios_con_dato: list[int]) -> int:
    """N para 'color_N=blue' = nº de años con dato disponible."""
    return len(anios_con_dato)


def generar_nota_leyenda(origenes_por_anio: dict[int, str]) -> str:
    """Elige la variante de leyenda según la mezcla de fuentes presente."""
    fuentes = set(origenes_por_anio.values())
    tiene_1981 = "derecho_1981" in fuentes
    tiene_padron = "padron" in fuentes
    if tiene_1981 and tiene_padron:
        return LEYENDA_MEZCLA
    if tiene_1981:
        return LEYENDA_SOLO_1981
    return LEYENDA_SOLO_PADRON


def _slug_fichero(texto: str) -> str:
    """Nombre de fichero seguro: sin acentos, sin barras/paréntesis, con guiones bajos."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Za-z0-9]+", "_", texto).strip("_")
    return texto


def generar_wikitexto_entidad(entidad: EntidadResultado, fecha_acceso: str) -> str:
    """Genera el bloque <center>{{Gráfica de evolución...}}</center> de una entidad,
    listando solo los años con dato disponible (sin huecos)."""
    nombre_mostrado = nombre_para_mostrar(entidad)
    anios_ordenados = sorted(entidad.poblacion_por_anio)
    color_n = calcular_color_n(anios_ordenados)

    pares_anio_valor = "".join(
        f"|{anio}|{entidad.poblacion_por_anio[anio]} " for anio in anios_ordenados
    )

    nota = generar_nota_leyenda(entidad.origen_por_anio)

    cita = (
        f"<ref>{{{{cita web|url={URL_NOMENCLATOR}|título={TITULO_CITA}"
        f"|autor={AUTOR_CITA}|fechaacceso={fecha_acceso}}}}}</ref>"
    )

    return (
        "<center>\n"
        f"{{{{Gráfica de evolución|tipo=demográfica|anchura=600|color_{color_n}=blue"
        f"|nombre={nombre_mostrado}{cita}{pares_anio_valor}|notas=<small>\n"
        f"{{{{leyenda|{COLOR_LEYENDA}|{nota}}}}}\n"
        "</small>}}\n"
        "</center>\n"
    )


def nombre_fichero_entidad(entidad: EntidadResultado) -> str:
    """Nombre de fichero único por entidad: municipio + nombre + código
    (el código evita colisiones entre entidades homónimas de municipios
    distintos y entre una entidad actual y una desaparecida del mismo nombre)."""
    tipo = "municipio" if entidad.tipo == "municipio" else "concejo"
    return (
        f"{_slug_fichero(entidad.municipio_nombre)}__"
        f"{_slug_fichero(entidad.nombre)}__{tipo}__{entidad.entidad_id}.wikitext.txt"
    )


def generar_ficheros_wikitexto_provincia(
    entidades: list[EntidadResultado],
    dir_salida: str | Path,
    fecha_acceso: str | None = None,
) -> list[Path]:
    """Escribe un fichero .txt por entidad (concejo o municipio) con su
    wikitexto, en dir_salida. Devuelve la lista de rutas generadas."""
    if fecha_acceso is None:
        fecha_acceso = _fecha_acceso_hoy()

    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)

    rutas = []
    for entidad in entidades:
        contenido = generar_wikitexto_entidad(entidad, fecha_acceso)
        ruta = dir_salida / nombre_fichero_entidad(entidad)
        ruta.write_text(contenido, encoding="utf-8")
        rutas.append(ruta)
    return rutas


def _fecha_acceso_hoy() -> str:
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    hoy = date.today()
    return f"{hoy.day} de {meses[hoy.month - 1]} de {hoy.year}"
