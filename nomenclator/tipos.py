"""Estructuras de datos intermedias usadas por todo el motor de parseo."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UnidadRaw:
    """Una fila ya parseada del fichero de un año, sin agregar entre años."""

    provincia: str  # "01"
    municipio: str  # "037"
    codigo: str  # "010000" (6 díg, 1991+) o "0006" (4 díg, 1981)
    nombre: str  # nombre tal cual viene en el fichero (sin sufijos de nivel)
    poblacion: int  # Total (1991+) o Población de Derecho (1981)
    anio: int
    nivel: str  # "municipio" | "concejo" | "nucleo" | "diseminado" | "agregacion" | "otro"


@dataclass
class Discrepancia:
    """Fallo de cuadre entre suma de concejos y población del municipio."""

    anio: int
    provincia: str
    municipio: str
    municipio_nombre: str
    poblacion_municipio: int
    suma_concejos: int

    @property
    def diferencia(self) -> int:
        return self.poblacion_municipio - self.suma_concejos


@dataclass
class MatchResultado:
    """Resultado de emparejar un concejo de 1981 con uno de 1991+ (o su ausencia).

    Desde §10.6/§10.7: el código es la única clave que produce una
    fusión real (concejo_1981 y concejo_1991 ambos presentes). Cuando
    no hay coincidencia de código, concejo_1981 y concejo_1991 NUNCA
    aparecen ambos presentes a la vez -- la entidad queda como
    "desaparecido" o "nuevo" por separado, y la similitud de nombre se
    guarda solo como sugerencia informativa (`sugerencia_*`), sin
    fusionar población."""

    provincia: str
    municipio: str
    concejo_1981: UnidadRaw | None
    concejo_1991: UnidadRaw | None
    metodo: str | None  # "codigo" | None (ya no "nombre": el nombre no fusiona, ver docstring)
    score: float | None  # similitud (None si metodo=="codigo")
    estado: str  # "directo" | "directo_renombrado" | "nuevo" | "desaparecido"
    sugerencia_nombre: str | None = None
    """Nombre de la entidad más parecida del otro año, sin coincidencia
    de código, solo para "desaparecido"/"nuevo" (ver Paso 2 de
    emparejar_municipio). None si no hay ningún candidato por encima
    del umbral de sugerencia."""
    sugerencia_codigo: str | None = None
    """Código (tal cual, del año correspondiente) de la entidad sugerida."""
    sugerencia_score: float | None = None
    """Similitud de nombre con la entidad sugerida."""


@dataclass
class EntidadResultado:
    """Fila final de la estructura intermedia, una por concejo o municipio."""

    tipo: str  # "municipio" | "concejo"
    provincia: str
    municipio_codigo: str
    municipio_nombre: str
    entidad_id: str
    nombre: str
    poblacion_por_anio: dict[int, int] = field(default_factory=dict)
    origen_por_anio: dict[int, str] = field(default_factory=dict)
    estado_emparejamiento: str | None = None
    score_emparejamiento: float | None = None
    codigo_1981: str | None = None
    """Se mantiene sin usar en los generadores de salida (la columna
    "Código 1981" del Excel se retiró: no aportaba nada que
    `codigo_ine()` no diera ya de forma unívoca). Se conserva el campo
    en la estructura intermedia por si conviene depurar visualmente un
    emparejamiento concreto desde código; no hace falta tocarlo salvo
    para eso."""
    entidad_id_es_plano_1981: bool = False
    """True cuando `entidad_id` se ha construido con el esquema "plano"
    de 1981 (`provincia-municipio-1981-código`, ver `_entidad_id_1981`
    en orquestador.py) en vez del esquema de 1991+
    (`provincia-municipio-código`, ver `_entidad_id_1991`). Se da en dos
    casos: entidades "desaparecidas" (solo dato de 1981, sin pareja en
    1991+) y, si en la ejecución solo se ha incluido el fichero de
    1981, TODAS las entidades. Se conserva el campo por si conviene
    depurar visualmente un emparejamiento concreto desde código; ya no
    lo usa `codigo_ine()` (ver más abajo), que desde que el código pasó
    a ser la única clave de fusión ya no necesita distinguir el esquema
    de 1981 con ningún prefijo."""
    sugerencia_nombre: str | None = None
    """Solo para entidades "desaparecido" o "nuevo": nombre de la
    entidad más parecida del otro año (sin coincidencia de código, ver
    §10.7 del documento de diseño), puramente informativa -- NO se ha
    fusionado población con ella. None si no hay ningún candidato con
    similitud suficiente."""
    sugerencia_codigo: str | None = None
    """Código de la entidad sugerida en `sugerencia_nombre` (tal cual
    aparece en su propio año: 4 dígitos si la sugerencia viene del
    fichero de 1981, 6 dígitos si viene de 1991+)."""
    sugerencia_score: float | None = None
    """Similitud de nombre con la entidad de `sugerencia_nombre`."""
    ec_codigo: str | None = None
    """Código de entidad colectiva (EC, 2 dígitos) a la que pertenece
    esta entidad singular, según la codificación EC-ES-NUC del INE (ver
    ine.es/nomenclator/ayuda.htm). Son los 2 primeros dígitos del código
    de unidad poblacional AABBCC de 1991+. Solo aplica a entidades
    singulares (tipo "concejo") con dato de 1991+; queda None para
    municipios, para entidades sin entidad colectiva (EC=00, la mayoría
    de España fuera de Galicia) y para entidades "desaparecidas" que solo
    tienen dato de 1981 (formato AABB de 4 díg, sin desglose EC-ES-NUC)."""
    ec_nombre: str | None = None
    """Denominación de la entidad colectiva de `ec_codigo` (p.ej. la
    parroquia gallega "Ribela (Santa Mariña)"), recuperada de la fila
    de cabecera AA0000 del propio municipio. None en los mismos casos
    que `ec_codigo`. Puramente informativa: la entidad colectiva se
    excluye del cuadre de población (es la suma de sus entidades
    singulares); aquí solo se usa como columna descriptiva en el Excel
    de entidades y para desambiguar homónimas dentro de un municipio."""


@dataclass
class ResultadoProvincia:
    """Salida completa de la Fase 1 para una provincia."""

    concejos: list[EntidadResultado] = field(default_factory=list)
    municipios: list[EntidadResultado] = field(default_factory=list)
    discrepancias: list[Discrepancia] = field(default_factory=list)
    casos_dudosos: list[EntidadResultado] = field(default_factory=list)
    agregaciones_excluidas: list[UnidadRaw] = field(default_factory=list)


def codigo_ine(entidad: EntidadResultado) -> str:
    """Código INE usado como identificador único de la entidad, en
    formato "PP-MMM-EEEECC" (provincia-municipio-código de unidad
    poblacional de 6 díg), que es el formato con el que se cruza contra
    los códigos de municipio/unidad de Wikidata (ver
    ine.es/nomenclator/ayuda.htm; el código de unidad son los 6 díg
    EC+ES+NUC).

    Casos:
    - Municipio: EC=ES=NUC=00, luego "PP-MMM-000000"
      (p.ej. A Estrada = "36-017-000000").
    - Entidad singular 1991+: su entidad_id guarda AABB (= EC+ES, 4
      díg); el NUC de una entidad singular es siempre 00, así que el
      código de unidad de 6 díg es AABB+"00" y el resultado es
      "PP-MMM-AABB00" (p.ej. "36-017-380100").
    - Entidad "desaparecida" solo-1981 (entidad_id_es_plano_1981): su
      código es AABB de 4 díg del esquema de 1981, que NO tiene la
      estructura EC-ES-NUC de 6 díg. Se conserva TAL CUAL como
      "PP-MMM-AABB" (4 díg), como excepción visible: no se rellena a 6
      díg porque sería fabricar un código de unidad de 1991+ que no
      existe y que no casaría con nada en Wikidata. Estas entidades son
      de revisión manual de todos modos.

    Por qué es seguro no marcar de otro modo el esquema de 1981: con el
    código como ÚNICA clave de fusión entre 1981 y 1991+ (buscando en
    TODOS los años 1991+ procesados, no solo el primero -- ver
    orquestador._representantes_1991plus), si el código de una entidad
    "desaparecida" coincidiera con el de otra entidad real de 1991+ del
    mismo municipio, el Paso 1 del emparejamiento ya las habría
    fusionado antes de que ninguna llegara a "desaparecido". Es decir:
    dentro de un mismo resultado, ninguna entidad "desaparecida" puede
    compartir código con una entidad 1991+ real, así que la longitud
    dispar (4 vs 6 díg) nunca genera colisión ni ambigüedad."""
    if entidad.tipo == "municipio":
        return f"{entidad.provincia}-{entidad.municipio_codigo}-000000"
    codigo = entidad.entidad_id.rsplit("-", 1)[-1]
    if not entidad.entidad_id_es_plano_1981:
        codigo = f"{codigo}00"  # AABB -> AABB+NUC(00) = código de unidad de 6 díg
    return f"{entidad.provincia}-{entidad.municipio_codigo}-{codigo}"


def codigo_ine_11(entidad: EntidadResultado) -> str:
    """Alias histórico de `codigo_ine` para el municipio, conservado por
    compatibilidad con la columna del Excel de municipios. Devuelve el
    mismo identificador de unidad poblacional en formato con guiones
    "PP-MMM-000000" (p.ej. "36-017-000000").

    Antes devolvía los 11 dígitos pegados sin guiones (PPMMM000000);
    se armonizó al formato con guiones cuando se unificó `codigo_ine`
    al código de unidad de 6 díg, para que municipios y entidades
    compartan un único formato de código cruzable con Wikidata.

    Solo aplica a municipios (mantiene el contrato anterior); para
    cualquier otra entidad usar directamente `codigo_ine`."""
    if entidad.tipo != "municipio":
        raise ValueError(
            "codigo_ine_11 está pensado solo para municipios "
            f"(recibido tipo={entidad.tipo!r})"
        )
    return codigo_ine(entidad)


ANIO_DERECHO_1981 = 1981
ANIO_INICIO_CENSO_ANUAL = 2024

CRITERIO_DERECHO = "derecho"
CRITERIO_PADRON = "padron"
CRITERIO_CENSO_ANUAL = "censo_anual"


def criterio_poblacion_anio(anio: int) -> str:
    """Criterio de determinación de la población según el año, siguiendo
    la metodología del INE para el Nomenclátor: 1981 es Población de
    derecho (censo); 1991-2023 es Padrón municipal continuo; desde 2024
    (incluido 2025) es Censo Anual de Población, que ya NO es Padrón.
    Ver: https://ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177010&idp=1254735572981
    """
    if anio == ANIO_DERECHO_1981:
        return CRITERIO_DERECHO
    if anio < ANIO_INICIO_CENSO_ANUAL:
        return CRITERIO_PADRON
    return CRITERIO_CENSO_ANUAL
