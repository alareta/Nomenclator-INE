"""Emparejamiento de concejos entre el fichero de 1981 y los de 1991 en
adelante, por CÓDIGO -- única clave que fusiona población entre años
(ver §5 y §10.6/§10.7 de proyecto_utilidad_web_nomenclator.md: el
código de entidad es estable desde el Censo de 1981 por diseño del
INE, que además advierte explícitamente que su numeración existe para
"asegurar la trazabilidad histórica... y evitar que los investigadores
o los sistemas informáticos mezclen datos de lugares diferentes").

La similitud de nombre YA NO fusiona población (ver §10.7: se
comprobó con los 6 ficheros nacionales reales que el 100% de las
fusiones por nombre unían una entidad de 1991+ sin ningún código
precedente en 1981 -- es decir, exactamente el mezclado de lugares
distintos que el propio INE dice que su sistema de códigos evita). Se
conserva solo como sugerencia informativa adjunta a las entidades
"desaparecido"/"nuevo", para revisión manual.
"""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

from .tipos import MatchResultado, UnidadRaw

UMBRAL_ACEPTACION_DEFECTO = 0.45
"""Umbral mínimo de similitud de nombre para que una entidad "desaparecido"
o "nuevo" lleve una sugerencia (`sugerencia_*` en MatchResultado). Ya no
fusiona población -- ver docstring del módulo y §10.7."""
UMBRAL_VALIDACION_CODIGO = 0.3
"""Ya NO es un umbral de aceptación (un código coincidente se acepta
SIEMPRE, ver docstring de emparejar_municipio). Se usa solo para decidir
la etiqueta informativa: por debajo de este umbral, el nombre ha
cambiado tanto que se marca 'directo_renombrado' en vez de 'directo',
como aviso no bloqueante (renombrado real, o la excepción de
reactivación de código de una entidad con un uso distinto que
documenta la metodología del INE)."""


def normalizar_nombre(nombre: str) -> str:
    """Mayúsculas, sin acentos, sin la parte tras '/' (nombres duales
    euskera/castellano), sin sufijos de nivel, espacios colapsados."""
    nombre = nombre.split("/")[0]
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c))
    nombre = nombre.upper()
    for sufijo in ("(NUCLEO)", "(CAPITAL)", "*DISEMINADO*"):
        nombre = nombre.replace(sufijo, "")
    nombre = " ".join(nombre.split())
    return nombre


def similitud(nombre_a: str, nombre_b: str) -> float:
    return SequenceMatcher(None, normalizar_nombre(nombre_a), normalizar_nombre(nombre_b)).ratio()


def _codigo_aabb_1991(codigo6: str) -> str:
    return codigo6[0:4]


def emparejar_municipio(
    concejos_1981: list[UnidadRaw],
    concejos_1991: list[UnidadRaw],
    umbral_aceptacion: float = UMBRAL_ACEPTACION_DEFECTO,
) -> list[MatchResultado]:
    """Empareja los concejos de 1981 y 1991 de UN mismo municipio.

    1) Candidatos por código textual igual (código 1981 == AABB de
       1991+): ÚNICO criterio que fusiona población entre años. Se
       acepta SIEMPRE, sin exigir similitud de nombre (el código es la
       clave de identificación oficial del INE desde 1981, ver
       §5/§10.6 del documento de diseño). Estado 'directo' si el
       nombre además es razonablemente parecido (score >=
       UMBRAL_VALIDACION_CODIGO); 'directo_renombrado' si el nombre ha
       cambiado por completo -- aviso informativo, no bloqueante.
    2) Para el resto (código sin coincidencia en ningún lado): NO se
       fusiona población. Se calcula, solo con fines informativos, el
       mejor candidato por similitud de nombre en el otro año (voraz,
       de mayor a menor score, cortando por umbral_aceptacion) y se
       adjunta como sugerencia (`sugerencia_nombre/codigo/score`) a la
       entidad "desaparecido"/"nuevo" correspondiente -- ver §10.7:
       fusionar aquí mezclaría, con toda probabilidad, datos de lugares
       distintos (confirmado empíricamente a escala nacional).
    3) Concejos de 1981 sin código coincidente -> estado 'desaparecido'
       (con sugerencia si la hay).
    4) Concejos de 1991 sin código coincidente -> estado 'nuevo'
       (con sugerencia si la hay).

    `concejos_1991` debe representar el universo de códigos de CUALQUIER
    año 1991+ procesado (no solo el primero) -- ver
    orquestador._representantes_1991plus, que construye ese universo
    antes de llamar aquí. Si solo se mirara el primer año 1991+
    disponible, una entidad ausente en ese año concreto pero presente
    en años posteriores con el mismo código nunca se emparejaría (bug
    real detectado a escala nacional, ver Hallazgo 3 de §10.6).
    """
    if not concejos_1981:
        return []

    provincia = concejos_1981[0].provincia
    municipio = concejos_1981[0].municipio

    pendientes_1981 = list(concejos_1981)
    pendientes_1991 = list(concejos_1991)
    resultados: list[MatchResultado] = []

    # Paso 1: coincidencia directa por código -- ÚNICO criterio que
    # fusiona población entre años.
    for c81 in list(pendientes_1981):
        candidato = next(
            (c91 for c91 in pendientes_1991 if _codigo_aabb_1991(c91.codigo) == c81.codigo),
            None,
        )
        if candidato is None:
            continue
        score = similitud(c81.nombre, candidato.nombre)
        estado = "directo" if score >= UMBRAL_VALIDACION_CODIGO else "directo_renombrado"
        resultados.append(
            MatchResultado(
                provincia=provincia,
                municipio=municipio,
                concejo_1981=c81,
                concejo_1991=candidato,
                metodo="codigo",
                score=score,
                estado=estado,
            )
        )
        pendientes_1981.remove(c81)
        pendientes_1991.remove(candidato)

    # Paso 2: sugerencias por nombre entre lo que quedó SIN código
    # coincidente en ningún lado -- puramente informativo, no fusiona
    # población (ver docstring del módulo y §10.7). Emparejamiento
    # voraz uno-a-uno para no repetir la misma sugerencia en varias
    # entidades a la vez.
    candidatos_pares = sorted(
        (
            (similitud(c81.nombre, c91.nombre), c81, c91)
            for c81 in pendientes_1981
            for c91 in pendientes_1991
        ),
        key=lambda t: t[0],
        reverse=True,
    )
    sugerencia_de_1981: dict[int, tuple[UnidadRaw, float]] = {}
    sugerencia_de_1991: dict[int, tuple[UnidadRaw, float]] = {}
    usados_1981: set[int] = set()
    usados_1991: set[int] = set()
    for score, c81, c91 in candidatos_pares:
        if score < umbral_aceptacion:
            break
        if id(c81) in usados_1981 or id(c91) in usados_1991:
            continue
        sugerencia_de_1981[id(c81)] = (c91, score)
        sugerencia_de_1991[id(c91)] = (c81, score)
        usados_1981.add(id(c81))
        usados_1991.add(id(c91))

    # Paso 3: desaparecidos (1981 sin código coincidente), con sugerencia si la hay
    for c81 in pendientes_1981:
        sugerencia = sugerencia_de_1981.get(id(c81))
        resultados.append(
            MatchResultado(
                provincia=provincia,
                municipio=municipio,
                concejo_1981=c81,
                concejo_1991=None,
                metodo=None,
                score=None,
                estado="desaparecido",
                sugerencia_nombre=sugerencia[0].nombre if sugerencia else None,
                sugerencia_codigo=sugerencia[0].codigo if sugerencia else None,
                sugerencia_score=sugerencia[1] if sugerencia else None,
            )
        )

    # Paso 4: nuevos (1991 sin código coincidente), con sugerencia si la hay
    for c91 in pendientes_1991:
        sugerencia = sugerencia_de_1991.get(id(c91))
        resultados.append(
            MatchResultado(
                provincia=provincia,
                municipio=municipio,
                concejo_1981=None,
                concejo_1991=c91,
                metodo=None,
                score=None,
                estado="nuevo",
                sugerencia_nombre=sugerencia[0].nombre if sugerencia else None,
                sugerencia_codigo=sugerencia[0].codigo if sugerencia else None,
                sugerencia_score=sugerencia[1] if sugerencia else None,
            )
        )

    return resultados


def emparejar_provincia_1981_1991(
    concejos_1981: list[UnidadRaw],
    concejos_1991_base: list[UnidadRaw],
    umbral_aceptacion: float = UMBRAL_ACEPTACION_DEFECTO,
) -> list[MatchResultado]:
    """Agrupa por (provincia, municipio) y llama a emparejar_municipio en
    cada uno. `concejos_1991_base` debe ser el universo de representantes
    de TODOS los años 1991+ (ver orquestador._representantes_1991plus),
    no los de un único año.

    Importante: se agrupa por (provincia, municipio), NO solo por
    código de municipio -- el código de municipio (3 dígitos) NO es
    único a escala nacional (todas las provincias numeran sus
    municipios desde 001), así que agrupar solo por ese código
    mezclaría concejos de municipios homónimos de provincias distintas
    en el mismo emparejamiento voraz, con resultados sin sentido. Con
    una sola provincia por ejecución (caso de uso original) esto no se
    notaba, porque ahí el código de municipio ya era único de por sí.
    """
    claves = sorted(
        {(u.provincia, u.municipio) for u in concejos_1981}
        | {(u.provincia, u.municipio) for u in concejos_1991_base}
    )

    resultados: list[MatchResultado] = []
    for provincia, municipio in claves:
        c81 = [u for u in concejos_1981 if u.provincia == provincia and u.municipio == municipio]
        c91 = [u for u in concejos_1991_base if u.provincia == provincia and u.municipio == municipio]
        if not c81 and not c91:
            continue
        if not c81:
            # municipio sin concejos en 1981 (no debería darse, pero por
            # robustez: todos los de 1991 quedan como 'nuevo')
            for u in c91:
                resultados.append(
                    MatchResultado(
                        provincia=provincia,
                        municipio=municipio,
                        concejo_1981=None,
                        concejo_1991=u,
                        metodo=None,
                        score=None,
                        estado="nuevo",
                    )
                )
            continue
        resultados.extend(
            emparejar_municipio(c81, c91, umbral_aceptacion=umbral_aceptacion)
        )
    return resultados


