"""Generación de los Excel de tabla resumen (concejos y municipios).

Ver §6.1 del documento de diseño.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .texto import capitalizar_nombre_display
from .tipos import Discrepancia, EntidadResultado, ResultadoProvincia, codigo_ine

RELLENO_CABECERA = PatternFill(start_color="D9E7EC", end_color="D9E7EC", fill_type="solid")
FUENTE_CABECERA = Font(bold=True)
ALINEACION_CABECERA = Alignment(horizontal="center", vertical="center", wrap_text=True)

ESTADOS_A_ETIQUETA = {
    "directo": "",
    "directo_renombrado": "Mismo código INE, nombre muy distinto (revisar)",
    "nuevo": "Entidad nueva (sin dato anterior a 1991)",
    "desaparecido": "Desaparecido/agregado (sin dato desde 1991)",
}


def _escribir_cabecera(ws: Worksheet, columnas: list[str]) -> None:
    for col_idx, titulo in enumerate(columnas, start=1):
        celda = ws.cell(row=1, column=col_idx, value=titulo)
        celda.font = FUENTE_CABECERA
        celda.fill = RELLENO_CABECERA
        celda.alignment = ALINEACION_CABECERA
    ws.auto_filter.ref = f"A1:{get_column_letter(len(columnas))}1"


def _ajustar_anchos(ws: Worksheet, anchos: list[int]) -> None:
    for idx, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = ancho


def generar_excel_tabla(
    entidades: list[EntidadResultado],
    anios: list[int],
    titulo_hoja: str,
    incluir_columna_concejo: bool,
    discrepancias: list[Discrepancia] | None = None,
) -> Workbook:
    """Genera un libro con una hoja de datos y una hoja de notas metodológicas.

    Columnas: Municipio | [Concejo] | Código INE | Pob. <año1> | ... | [Estado] | [Sugerencia]
    - incluir_columna_concejo=False para la tabla de municipios.
    - la columna 'Estado' (solo si hay entidades con estado_emparejamiento
      distinto de directo) resume el resultado del emparejamiento
      1981<->1991+ para que el usuario sepa qué revisar.
    - la columna 'Sugerencia' (solo si hay entidades "desaparecido"/"nuevo"
      con una sugerencia por nombre, ver §10.7) muestra el mejor candidato
      del otro año por similitud de nombre -- puramente informativa, NO
      implica que sea la misma entidad ni fusiona su población.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = titulo_hoja

    hay_estado = any(e.estado_emparejamiento not in (None, "directo") for e in entidades)
    hay_sugerencia = any(e.sugerencia_nombre for e in entidades)
    # Columna "Entidad colectiva" (EC del INE, p.ej. parroquia gallega):
    # solo en la tabla de unidades poblacionales y solo si alguna la tiene
    # (la mayoría de España, fuera de Galicia, no tiene entidades
    # colectivas, así que la columna no aparece). Ver ec_nombre en tipos.py.
    hay_ec = incluir_columna_concejo and any(e.ec_nombre for e in entidades)

    columnas = ["Municipio"]
    if incluir_columna_concejo:
        columnas.append("Unidad poblacional")
    if hay_ec:
        columnas.append("Entidad colectiva")
    columnas.append("Código INE")
    columnas += [f"Pob. {anio}" for anio in anios]
    if hay_estado:
        columnas.append("Estado")
    if hay_sugerencia:
        columnas.append("Sugerencia")

    _escribir_cabecera(ws, columnas)

    entidades_ordenadas = sorted(entidades, key=lambda e: (e.municipio_nombre, e.nombre))

    for fila_idx, entidad in enumerate(entidades_ordenadas, start=2):
        col = 1
        ws.cell(row=fila_idx, column=col, value=capitalizar_nombre_display(entidad.municipio_nombre))
        col += 1
        if incluir_columna_concejo:
            ws.cell(row=fila_idx, column=col, value=capitalizar_nombre_display(entidad.nombre))
            col += 1
        if hay_ec:
            ec_txt = capitalizar_nombre_display(entidad.ec_nombre) if entidad.ec_nombre else ""
            ws.cell(row=fila_idx, column=col, value=ec_txt)  # "" si la unidad no cuelga de EC
            col += 1
        ws.cell(row=fila_idx, column=col, value=codigo_ine(entidad))
        col += 1
        for anio in anios:
            valor = entidad.poblacion_por_anio.get(anio)
            ws.cell(row=fila_idx, column=col, value=valor)  # None -> celda en blanco
            col += 1
        if hay_estado:
            etiqueta = ESTADOS_A_ETIQUETA.get(entidad.estado_emparejamiento or "", "")
            ws.cell(row=fila_idx, column=col, value=etiqueta)
            col += 1
        if hay_sugerencia:
            if entidad.sugerencia_nombre:
                sugerencia_txt = (
                    f"¿{capitalizar_nombre_display(entidad.sugerencia_nombre)}? "
                    f"(código {entidad.sugerencia_codigo}, score {entidad.sugerencia_score:.2f})"
                )
            else:
                sugerencia_txt = ""
            ws.cell(row=fila_idx, column=col, value=sugerencia_txt)

    anchos = (
        [28]
        + ([28] if incluir_columna_concejo else [])
        + ([28] if hay_ec else [])
        + [16]
        + [11] * len(anios)
        + ([32] if hay_estado else [])
        + ([40] if hay_sugerencia else [])
    )
    _ajustar_anchos(ws, anchos)
    ws.freeze_panes = "B2" if not incluir_columna_concejo else "C2"

    _anadir_hoja_notas(wb, titulo_hoja, discrepancias or [])
    return wb


def _anadir_hoja_notas(wb: Workbook, titulo_hoja: str, discrepancias: list[Discrepancia]) -> None:
    ws = wb.create_sheet("Notas metodológicas")
    ws.column_dimensions["A"].width = 100

    lineas = [
        f"Notas metodológicas — {titulo_hoja}",
        "",
        "Fuente: INE, Nomenclátor de población (Censo/Padrón continuo).",
        "Población de 1981: Población de Derecho. Resto de años: Población del Padrón continuo (Total).",
        "",
        "Criterio de extracción: se excluyen las filas de agrupación estadística "
        "(unidades poblacionales que agrupan a otras del mismo municipio) para no "
        "duplicar población; se usan siempre las entidades de nivel más fino.",
        "",
        "Emparejamiento entre 1981 y 1991 en adelante: el código de entidad es la ÚNICA "
        "clave que fusiona población entre años (es estable desde el Censo de 1981 por "
        "diseño del INE, ver https://www.ine.es/nomenclator/metodologia.htm). Si el "
        "código de 1981 coincide con el de una entidad de 1991+ en el mismo municipio, "
        "se fusionan sin exigir que el nombre coincida (puede haber cambiado por "
        "completo: casos marcados 'directo_renombrado', a revisar sin más). Si el "
        "código no coincide en ningún año, NO se fusiona población: la unidad de 1981 "
        "queda 'desaparecida/agregada' y la de 1991+ queda 'entidad nueva', cada una con "
        "su propia serie de población. La similitud de nombre entre ambos, si la hay, se "
        "muestra solo como sugerencia informativa en la columna 'Sugerencia' -- revisar "
        "y decidir manualmente si de verdad son la misma entidad antes de darlo por "
        "bueno; el sistema nunca fusiona por esa vía.",
        "",
        "Columna 'Código INE': identificador único de cada entidad, en formato "
        "'provincia-municipio-código de unidad' (p.ej. municipio A Estrada = "
        "'36-017-000000'; entidad singular = '36-017-380100'). El código de unidad son "
        "los 6 dígitos EC+ES+NUC del Nomenclátor (ver "
        "https://www.ine.es/nomenclator/ayuda.htm); es el formato con el que se cruza "
        "contra los códigos de Wikidata. Excepción: las entidades 'desaparecidas' que "
        "solo tienen dato de 1981 conservan su código de 4 dígitos de aquel año "
        "(p.ej. '36-017-3801'), que pertenece a un esquema distinto y no se rellena a 6 "
        "dígitos para no fabricar un código de unidad de 1991+ inexistente. Con el "
        "código como única clave de fusión (ver nota anterior), dos entidades distintas "
        "del mismo municipio nunca pueden compartir código dentro de un mismo resultado.",
        "",
        "Columna 'Entidad colectiva' (solo aparece si el conjunto contiene alguna): "
        "según la codificación del INE (ver https://www.ine.es/nomenclator/ayuda.htm), "
        "la entidad colectiva es el nivel que agrupa entidades singulares dentro de un "
        "municipio -- en Galicia se corresponde con la parroquia. No todos los "
        "municipios la tienen (fuera de Galicia es infrecuente); cuando existe, se "
        "indica aquí a título informativo para situar cada unidad poblacional y "
        "distinguir homónimas del mismo municipio. Su población NO se suma aparte: la "
        "fila de la entidad colectiva es el total de sus entidades singulares y por eso "
        "se excluye del cuadre, igual que las demás agrupaciones.",
        "",
    ]

    if discrepancias:
        lineas.append(
            f"⚠ Se han detectado {len(discrepancias)} discrepancia(s) de cuadre "
            "(la suma de las unidades poblacionales de un municipio no coincide con la población "
            "del municipio en ese año). Revisar antes de publicar:"
        )
        for d in discrepancias:
            lineas.append(
                f"  · {d.anio} — {capitalizar_nombre_display(d.municipio_nombre)}: "
                f"municipio={d.poblacion_municipio}, suma unidades={d.suma_concejos}, "
                f"diferencia={d.diferencia}"
            )
    else:
        lineas.append("✓ Sin discrepancias de cuadre unidades poblacionales/municipio en ningún año.")

    for idx, linea in enumerate(lineas, start=1):
        ws.cell(row=idx, column=1, value=linea)
        if idx == 1:
            ws.cell(row=idx, column=1).font = Font(bold=True, size=13)


def generar_excel_combinado(resultado: ResultadoProvincia, anios: list[int]) -> Workbook:
    """Genera un libro de UNA sola hoja con municipios y unidades
    poblacionales juntos, en orden jerárquico: cada municipio seguido
    inmediatamente de sus propias unidades poblacionales.

    Columnas: Tipo | Municipio | Unidad poblacional | [Entidad colectiva]
              | Código INE | Pob. municipio <año> | Pob. unidad <año> ...

    - "Tipo" distingue "Municipio" de "Unidad" (única forma de separar
      ambos niveles al estar mezclados en la misma hoja).
    - La población se separa en DOS columnas por año: "Pob. municipio
      <año>" (rellena solo en filas Tipo=Municipio) y "Pob. unidad
      <año>" (rellena solo en filas Tipo=Unidad). Es imprescindible: en
      esta hoja conviven el municipio y sus unidades, y las unidades SON
      el municipio desglosado (su población suma la del municipio). Una
      única columna de población sumaría ambos niveles y DUPLICARÍA la
      población (a escala nacional, ~94 M en vez de ~47 M). Con las
      columnas separadas, cada una cuadra por su lado y nunca se suman
      dos niveles a la vez; además queda a la vista el caso frecuente de
      la entidad singular capital homónima del municipio (mismo nombre,
      cifras distintas: p.ej. municipio Alegría-Dulantzi 2961 vs su
      entidad singular capital 2842, con el resto repartido en otras
      unidades).
    - En las filas de municipio, "Unidad poblacional" y "Entidad
      colectiva" van vacías: no aplican a un municipio. Vacío significa
      "no aplica", nunca 0 -- un 0 en población afirmaría que el
      municipio tiene cero habitantes, que es falso.
    - La agrupación municipio->unidades usa (provincia, municipio_codigo),
      no solo el código de municipio: dos provincias distintas reutilizan
      los mismos números de municipio, y agrupar solo por el número los
      mezclaría.
    - "Entidad colectiva" solo aparece si alguna unidad la tiene (mismo
      criterio que en la tabla de unidades)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Municipios y unidades"

    hay_ec = any(e.ec_nombre for e in resultado.concejos)

    columnas = ["Tipo", "Municipio", "Unidad poblacional"]
    if hay_ec:
        columnas.append("Entidad colectiva")
    columnas.append("Código INE")
    for anio in anios:
        columnas.append(f"Pob. municipio {anio}")
        columnas.append(f"Pob. unidad {anio}")
    _escribir_cabecera(ws, columnas)

    # Índice de unidades por municipio, para intercalarlas tras cada uno.
    unidades_por_muni: dict[tuple[str, str], list[EntidadResultado]] = {}
    for c in resultado.concejos:
        unidades_por_muni.setdefault((c.provincia, c.municipio_codigo), []).append(c)

    municipios_ordenados = sorted(
        resultado.municipios, key=lambda m: (m.provincia, m.municipio_codigo)
    )

    fila_idx = 2
    for muni in municipios_ordenados:
        fila_idx = _escribir_fila_combinada(ws, fila_idx, muni, "Municipio", anios, hay_ec)
        unidades = unidades_por_muni.get((muni.provincia, muni.municipio_codigo), [])
        for unidad in sorted(unidades, key=lambda e: e.entidad_id):
            fila_idx = _escribir_fila_combinada(ws, fila_idx, unidad, "Unidad", anios, hay_ec)

    anchos = [10, 28, 28] + ([28] if hay_ec else []) + [16] + [16, 16] * len(anios)
    _ajustar_anchos(ws, anchos)
    ws.freeze_panes = "C2"  # congela Tipo + Municipio

    _anadir_hoja_notas(wb, "Municipios y unidades", resultado.discrepancias or [])
    return wb


def _escribir_fila_combinada(
    ws: Worksheet,
    fila_idx: int,
    entidad: EntidadResultado,
    tipo_etiqueta: str,
    anios: list[int],
    hay_ec: bool,
) -> int:
    """Escribe una fila del Excel combinado y devuelve el índice de la
    siguiente. Para un municipio, las celdas de "Unidad poblacional" y
    "Entidad colectiva" quedan vacías (no aplican)."""
    es_municipio = entidad.tipo == "municipio"
    col = 1
    ws.cell(row=fila_idx, column=col, value=tipo_etiqueta)
    col += 1
    ws.cell(row=fila_idx, column=col, value=capitalizar_nombre_display(entidad.municipio_nombre))
    col += 1
    # "Unidad poblacional": vacía para municipios
    ws.cell(
        row=fila_idx,
        column=col,
        value="" if es_municipio else capitalizar_nombre_display(entidad.nombre),
    )
    col += 1
    if hay_ec:
        ec_txt = "" if es_municipio or not entidad.ec_nombre else capitalizar_nombre_display(entidad.ec_nombre)
        ws.cell(row=fila_idx, column=col, value=ec_txt)
        col += 1
    ws.cell(row=fila_idx, column=col, value=codigo_ine(entidad))
    col += 1
    # Dos columnas de población por año: la del propio nivel lleva el
    # dato, la del otro nivel queda vacía. Así ninguna columna suma
    # municipio + unidades a la vez (ver docstring de generar_excel_combinado).
    for anio in anios:
        pob = entidad.poblacion_por_anio.get(anio)
        if es_municipio:
            ws.cell(row=fila_idx, column=col, value=pob)      # Pob. municipio
            col += 1
            col += 1                                          # Pob. unidad -> vacía
        else:
            col += 1                                          # Pob. municipio -> vacía
            ws.cell(row=fila_idx, column=col, value=pob)      # Pob. unidad
            col += 1
    return fila_idx + 1


def generar_excels_provincia(resultado: ResultadoProvincia, anios: list[int]) -> tuple[Workbook, Workbook]:
    """Devuelve (libro_concejos, libro_municipios)."""
    libro_concejos = generar_excel_tabla(
        resultado.concejos,
        anios,
        titulo_hoja="Unidades poblacionales",
        incluir_columna_concejo=True,
        discrepancias=resultado.discrepancias,
    )
    libro_municipios = generar_excel_tabla(
        resultado.municipios,
        anios,
        titulo_hoja="Municipios",
        incluir_columna_concejo=False,
        discrepancias=resultado.discrepancias,
    )
    return libro_concejos, libro_municipios


def guardar_excels_provincia(resultado: ResultadoProvincia, anios: list[int], dir_salida: str | Path) -> tuple[Path, Path]:
    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    libro_concejos, libro_municipios = generar_excels_provincia(resultado, anios)
    ruta_concejos = dir_salida / "concejos.xlsx"
    ruta_municipios = dir_salida / "municipios.xlsx"
    libro_concejos.save(ruta_concejos)
    libro_municipios.save(ruta_municipios)
    return ruta_concejos, ruta_municipios


def guardar_excel_combinado(resultado: ResultadoProvincia, anios: list[int], dir_salida: str | Path) -> Path:
    """Guarda el Excel combinado (municipios + unidades, una hoja
    jerárquica) y devuelve su ruta."""
    dir_salida = Path(dir_salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    libro = generar_excel_combinado(resultado, anios)
    ruta = dir_salida / "municipios_y_unidades.xlsx"
    libro.save(ruta)
    return ruta
