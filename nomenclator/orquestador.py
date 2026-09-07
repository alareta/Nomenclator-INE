"""Orquestador de la Fase 1: de los ficheros por año a la estructura
intermedia lista para que la Fase 2 genere Excel/wikitexto.
"""

from __future__ import annotations

from pathlib import Path

from .emparejamiento import emparejar_provincia_1981_1991
from .parseo import (
    extraer_agregaciones,
    extraer_concejos,
    extraer_municipios,
    parsear_fichero_anio,
    validar_cuadre,
)
from .tipos import EntidadResultado, ResultadoProvincia, UnidadRaw

ORIGEN_1981 = "derecho_1981"
ORIGEN_PADRON = "padron"


def _entidad_id_1991(unidad: UnidadRaw) -> str:
    aabb = unidad.codigo[0:4]
    return f"{unidad.provincia}-{unidad.municipio}-{aabb}"


def _entidad_id_1981(unidad: UnidadRaw) -> str:
    return f"{unidad.provincia}-{unidad.municipio}-1981-{unidad.codigo}"


def _representantes_1991plus(unidades_por_anio: dict[int, list[UnidadRaw]]) -> list[UnidadRaw]:
    """Un representante (UnidadRaw) por cada entidad (código AABB)
    distinta que aparece en CUALQUIER año 1991+ procesado -- no solo el
    primero.

    Necesario porque el código de entidad es estable desde 1981 por
    diseño del INE (ver §5 y §10.6 de proyecto_utilidad_web_nomenclator.md,
    con la metodología oficial del INE como fuente), pero una entidad
    concreta puede faltar en el fichero de un año 1991+ concreto
    (reclasificación puntual, hueco de datos) y reaparecer en años
    posteriores con el mismo código. Si el emparejamiento con 1981 solo
    mirara el primer año 1991+ disponible, esas entidades nunca se
    emparejarían aunque el código coincida -- bug real detectado al
    procesar España completa (Hallazgo 3 de §10.6): el 99.8% de un
    conjunto de ~820 casos de "misma entidad tratada como desaparecida
    + nueva" no tenían dato en el primer año 1991+ pero sí en años
    posteriores con el mismo código.

    Cuando el mismo código aparece en varios años con nombres distintos
    (evolución normal del nombre), se queda con el del año más
    reciente disponible."""
    representantes: dict[str, UnidadRaw] = {}
    for anio in sorted(a for a in unidades_por_anio if a != 1981):
        for u in extraer_concejos(unidades_por_anio[anio]):
            clave = _entidad_id_1991(u)
            representantes[clave] = u  # se sobreescribe: se queda con el año más reciente
    return list(representantes.values())


def _mapa_entidades_colectivas(
    unidades_por_anio: dict[int, list[UnidadRaw]],
) -> dict[tuple[str, str, str], str]:
    """Mapa (provincia, municipio, EC) -> nombre de la entidad colectiva,
    construido a partir de las filas de agregación de 1991+.

    La entidad colectiva (EC, ver ine.es/nomenclator/ayuda.htm) es el
    nivel que agrupa entidades singulares dentro de un municipio; en
    Galicia se corresponde con la parroquia. Sus filas llegan como
    UnidadRaw de nivel "agregacion" con código AA0000 (6 díg), de las
    que EC = codigo[0:2] y el nombre ya viene limpio. Este mapa permite
    poner el nombre de la colectiva como columna informativa en las
    entidades singulares que cuelgan de ella (ver
    `_asignar_entidad_colectiva`), sin alterar el cuadre: la fila de la
    colectiva se sigue excluyendo de la suma (es el total de sus hijas).

    Solo se usan las agregaciones de 1991+ (código de 6 díg). Las de
    1981 (clasificar_codigo4) son las "Diputaciones", una agrupación
    estadística distinta que NO es una entidad colectiva del sistema
    EC-ES-NUC, así que se dejan fuera (sus códigos son de 4 díg y no
    entran en este bucle porque solo recorremos años != 1981).

    Cuando la misma EC aparece en varios años con el nombre
    evolucionado, se conserva el del año más reciente, por coherencia
    con `_construir_tabla_municipios` y `_representantes_1991plus`."""
    mapa: dict[tuple[str, str, str], str] = {}
    for anio in sorted(a for a in unidades_por_anio if a != 1981):
        for u in extraer_agregaciones(unidades_por_anio[anio]):
            if len(u.codigo) != 6:
                continue  # cinturón: solo agregaciones de 6 díg tienen EC
            ec = u.codigo[0:2]
            mapa[(u.provincia, u.municipio, ec)] = u.nombre  # año más reciente gana
    return mapa


def _asignar_entidad_colectiva(
    concejos: dict[str, EntidadResultado],
    mapa_ec: dict[tuple[str, str, str], str],
) -> None:
    """Rellena ec_codigo/ec_nombre en cada entidad singular que pertenezca
    a una entidad colectiva, in situ.

    El EC de una entidad singular son los dos primeros dígitos de su
    código AABB, recuperables del final de su entidad_id
    (`provincia-municipio-AABB` en el esquema 1991+). Solo se asigna
    cuando:
      - la entidad NO usa el esquema plano de 1981
        (entidad_id_es_plano_1981 == False): las "desaparecidas" solo
        tienen código AABB de 4 díg de 1981, sin desglose EC-ES-NUC, así
        que sus dos primeros dígitos NO son una EC de este sistema y
        asignarles una sería un falso positivo;
      - EC != "00": EC=00 significa "sin entidad colectiva" (la mayoría
        de España fuera de Galicia);
      - (provincia, municipio, EC) está en el mapa: garantiza que hay
        una fila de cabecera AA0000 de la que sale el nombre. La
        verificación a escala nacional (fichero 2025) dio 0 EC
        referidas sin cabecera, así que en la práctica este filtro no
        descarta nada, pero se deja por robustez."""
    for entidad in concejos.values():
        if entidad.entidad_id_es_plano_1981:
            continue
        aabb = entidad.entidad_id.rsplit("-", 1)[-1]
        ec = aabb[0:2]
        if ec == "00":
            continue
        nombre = mapa_ec.get((entidad.provincia, entidad.municipio_codigo, ec))
        if nombre is None:
            continue
        entidad.ec_codigo = ec
        entidad.ec_nombre = nombre


def _construir_tabla_municipios(unidades_por_anio: dict[int, list[UnidadRaw]]) -> list[EntidadResultado]:
    municipios: dict[tuple[str, str], EntidadResultado] = {}
    for anio in sorted(unidades_por_anio):
        for u in extraer_municipios(unidades_por_anio[anio]):
            clave = (u.provincia, u.municipio)
            if clave not in municipios:
                municipios[clave] = EntidadResultado(
                    tipo="municipio",
                    provincia=u.provincia,
                    municipio_codigo=u.municipio,
                    municipio_nombre=u.nombre,
                    entidad_id=f"{u.provincia}-{u.municipio}",
                    nombre=u.nombre,
                )
            entidad = municipios[clave]
            entidad.nombre = u.nombre  # se queda con el nombre del año más reciente
            entidad.municipio_nombre = u.nombre
            entidad.poblacion_por_anio[anio] = u.poblacion
            entidad.origen_por_anio[anio] = ORIGEN_1981 if anio == 1981 else ORIGEN_PADRON
    return sorted(municipios.values(), key=lambda e: (e.provincia, e.municipio_codigo))


def _construir_tabla_concejos_1991plus(
    unidades_por_anio: dict[int, list[UnidadRaw]],
    nombres_municipio: dict[tuple[str, str], str],
) -> list[EntidadResultado]:
    concejos: dict[str, EntidadResultado] = {}
    for anio in sorted(a for a in unidades_por_anio if a != 1981):
        for u in extraer_concejos(unidades_por_anio[anio]):
            entidad_id = _entidad_id_1991(u)
            if entidad_id not in concejos:
                concejos[entidad_id] = EntidadResultado(
                    tipo="concejo",
                    provincia=u.provincia,
                    municipio_codigo=u.municipio,
                    municipio_nombre=nombres_municipio.get((u.provincia, u.municipio), ""),
                    entidad_id=entidad_id,
                    nombre=u.nombre,
                    estado_emparejamiento=None,  # solo se marca "nuevo" si esta
                    # ejecución incluye 1981 y de verdad se ha buscado y no
                    # encontrado predecesor (ver bloque "if 1981 in
                    # unidades_por_anio" más abajo). Si 1981 no forma parte de
                    # la ejecución, no hay nada que "buscar" -- se deja sin
                    # estado en vez de decir "nueva", que sería engañoso: no
                    # es que se haya comprobado que no tiene predecesor, es
                    # que no se ha mirado en absoluto.
                )
            entidad = concejos[entidad_id]
            entidad.nombre = u.nombre
            entidad.poblacion_por_anio[anio] = u.poblacion
            entidad.origen_por_anio[anio] = ORIGEN_PADRON
    return concejos


def procesar_anios(
    ficheros: dict[int, str | Path],
    dir_trabajo: str | Path,
) -> ResultadoProvincia:
    """Procesa uno o varios ficheros del Nomenclátor, uno por año.

    Nombre histórico "procesar_provincia" (todavía disponible como
    alias más abajo, ver `procesar_provincia`) de cuando el alcance era
    una sola provincia por ejecución. La función en sí nunca filtró por
    provincia: agrupa siempre por la tupla (provincia, municipio) (ver
    docstring de `emparejar_provincia_1981_1991` en emparejamiento.py),
    así que acepta indistintamente ficheros provinciales o ficheros
    nacionales (con todas las provincias de España) sin cambios. El
    plan actual es trabajar solo con ficheros nacionales por año.

    1. Parsea cada fichero de año.
    2. Construye la tabla de municipios (join directo por código de municipio).
    3. Construye la tabla de concejos 1991+ (join directo por entidad_id AABB).
    4. Si hay fichero de 1981, empareja sus concejos contra el universo
       de códigos de TODOS los años 1991+ procesados (no solo el
       primero, ver `_representantes_1991plus`) y fusiona el resultado
       (añade la columna 1981 a los concejos ya existentes, o crea
       entidades sintéticas para los "desaparecidos").
    5. Valida cuadre concejos/municipio en cada año y recopila discrepancias.
    """
    anios_ordenados = sorted(ficheros)
    unidades_por_anio: dict[int, list[UnidadRaw]] = {
        anio: parsear_fichero_anio(ficheros[anio], anio, dir_trabajo) for anio in anios_ordenados
    }

    discrepancias = []
    agregaciones_excluidas: list[UnidadRaw] = []
    for anio, unidades in unidades_por_anio.items():
        discrepancias.extend(validar_cuadre(unidades))
        agregaciones_excluidas.extend(extraer_agregaciones(unidades))

    municipios_resultado = _construir_tabla_municipios(unidades_por_anio)
    nombres_municipio = {(m.provincia, m.municipio_codigo): m.nombre for m in municipios_resultado}

    concejos_dict = _construir_tabla_concejos_1991plus(unidades_por_anio, nombres_municipio)

    casos_dudosos: list[EntidadResultado] = []

    if 1981 in unidades_por_anio:
        concejos_1981 = extraer_concejos(unidades_por_anio[1981])
        anios_1991plus = [a for a in unidades_por_anio if a != 1981]

        if anios_1991plus:
            concejos_1991_base = _representantes_1991plus(unidades_por_anio)

            matches = emparejar_provincia_1981_1991(concejos_1981, concejos_1991_base)

            for m in matches:
                if m.concejo_1991 is not None:
                    entidad_id = _entidad_id_1991(m.concejo_1991)
                    entidad = concejos_dict[entidad_id]
                    entidad.estado_emparejamiento = m.estado
                    entidad.score_emparejamiento = m.score
                    if m.concejo_1981 is not None:
                        # "directo"/"directo_renombrado": única vía que fusiona
                        # población (ver §10.7 -- el código es la clave).
                        entidad.poblacion_por_anio[1981] = m.concejo_1981.poblacion
                        entidad.origen_por_anio[1981] = ORIGEN_1981
                        entidad.codigo_1981 = m.concejo_1981.codigo
                    else:
                        # "nuevo": sin dato de 1981; puede llevar una sugerencia
                        # informativa (no fusionada) de una posible entidad
                        # relacionada en el fichero de 1981.
                        entidad.sugerencia_nombre = m.sugerencia_nombre
                        entidad.sugerencia_codigo = m.sugerencia_codigo
                        entidad.sugerencia_score = m.sugerencia_score
                else:
                    # desaparecido: entidad sintética, solo con dato de 1981,
                    # con sugerencia informativa opcional (no fusionada).
                    c81 = m.concejo_1981
                    entidad_id = _entidad_id_1981(c81)
                    entidad = EntidadResultado(
                        tipo="concejo",
                        provincia=c81.provincia,
                        municipio_codigo=c81.municipio,
                        municipio_nombre=nombres_municipio.get((c81.provincia, c81.municipio), ""),
                        entidad_id=entidad_id,
                        nombre=c81.nombre,
                        estado_emparejamiento="desaparecido",
                        score_emparejamiento=None,
                        codigo_1981=c81.codigo,
                        entidad_id_es_plano_1981=True,
                        sugerencia_nombre=m.sugerencia_nombre,
                        sugerencia_codigo=m.sugerencia_codigo,
                        sugerencia_score=m.sugerencia_score,
                    )
                    entidad.poblacion_por_anio[1981] = c81.poblacion
                    entidad.origen_por_anio[1981] = ORIGEN_1981
                    concejos_dict[entidad_id] = entidad

                # "directo_renombrado" (mismo código, nombre muy distinto) y
                # cualquier entidad "desaparecido"/"nuevo" con sugerencia son
                # avisos no bloqueantes para revisión manual -- ver §10.6/§10.7.
                if m.estado == "directo_renombrado" or m.sugerencia_score is not None:
                    casos_dudosos.append(concejos_dict.get(_entidad_id_1991(m.concejo_1991))
                                          if m.concejo_1991 is not None
                                          else concejos_dict[_entidad_id_1981(m.concejo_1981)])
        else:
            # Solo se ha incluido el fichero de 1981 en esta ejecución:
            # no hay ningún año 1991+ contra el que emparejar, así que
            # no tiene sentido intentar el emparejamiento (ni marcar
            # nada como "desaparecido", que describe un concejo que
            # falta en 1991+ teniendo ambos años disponibles). Se listan
            # los concejos de 1981 tal cual, con su código plano de 1981
            # como entidad_id y sin estado de emparejamiento.
            for c81 in concejos_1981:
                entidad_id = _entidad_id_1981(c81)
                entidad = EntidadResultado(
                    tipo="concejo",
                    provincia=c81.provincia,
                    municipio_codigo=c81.municipio,
                    municipio_nombre=nombres_municipio.get((c81.provincia, c81.municipio), ""),
                    entidad_id=entidad_id,
                    nombre=c81.nombre,
                    estado_emparejamiento=None,
                    codigo_1981=c81.codigo,
                    entidad_id_es_plano_1981=True,
                )
                entidad.poblacion_por_anio[1981] = c81.poblacion
                entidad.origen_por_anio[1981] = ORIGEN_1981
                concejos_dict[entidad_id] = entidad

    # Enriquecimiento informativo: nombre de la entidad colectiva (EC,
    # p.ej. parroquia gallega) de cada entidad singular. No altera el
    # cuadre ni qué filas se exponen; solo añade ec_codigo/ec_nombre.
    mapa_ec = _mapa_entidades_colectivas(unidades_por_anio)
    _asignar_entidad_colectiva(concejos_dict, mapa_ec)

    concejos_resultado = sorted(
        concejos_dict.values(), key=lambda e: (e.provincia, e.municipio_codigo, e.entidad_id)
    )

    return ResultadoProvincia(
        concejos=concejos_resultado,
        municipios=municipios_resultado,
        discrepancias=discrepancias,
        casos_dudosos=casos_dudosos,
        agregaciones_excluidas=agregaciones_excluidas,
    )


# Alias de compatibilidad con el nombre anterior (usado todavía por
# algunos tests): mantenlo hasta que se actualicen todas las
# referencias, luego se puede eliminar.
procesar_provincia = procesar_anios
