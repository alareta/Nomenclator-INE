# Nomenclátor INE → tablas de población

Herramienta local (Flask) para procesar los ficheros **nacionales** del Nomenclátor de población del INE (1981 y 1991 en adelante, uno por año, cada fichero con todas las provincias de España) y generar tablas de población de municipios y unidades poblacionales listas para reutilizar en Wikipedia y Wikimedia Commons.

Corre en tu propio ordenador; no necesita conexión a internet salvo para instalar las dependencias la primera vez.

## Índice

- [Qué genera](#qué-genera)
- [Qué hace exactamente](#qué-hace-exactamente)
- [Requisitos](#requisitos)
- [Cómo arrancarla](#cómo-arrancarla)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tests](#tests)
- [Licencia](#licencia)

## Qué genera

El procesado de los ficheros del INE genera:

- **Excel** resumen de unidades poblacionales y de municipios, con el Código INE de cada entidad y la población de cada año. El de unidades incluye, cuando procede, la **entidad colectiva** (p. ej. la parroquia gallega) a la que pertenece cada unidad.
- **Excel combinado** de municipios y unidades poblacionales en una sola hoja jerárquica: cada municipio seguido de sus propias unidades, con una columna «Tipo» para distinguirlos.
- **CSV del INE**, uno por año, combinando municipios y unidades. Es la «foto» del lado INE que sirve de entrada, como paso posterior independiente, para la herramienta de cruce con Wikidata.

Y una segunda herramienta, **Cruzar con Wikidata** (independiente del procesado, accesible desde la pantalla inicial), genera:

- **Fichero `.tab` para Wikimedia Commons**, combinado (municipios y unidades en el mismo fichero) y por año, con el ítem Q de Wikidata ya adjudicado. Contiene solo las entidades que tienen ítem en Wikidata ese año. A partir del CSV del INE + un CSV de códigos↔Q descargado de una consulta de Wikidata.

> El wikitexto de `{{Gráfica de evolución}}`, que formaba parte de versiones anteriores de esta herramienta, se ha retirado: ya no se usa. El módulo que lo generaba (`salida_wikitexto.py`) sigue en el repositorio sin uso activo, por si hiciera falta recuperarlo, pero la app no lo genera ni lo ofrece para descarga.

## Qué hace exactamente

### 1. Entrada: ficheros nacionales, uno por año

Subes 1 o más ficheros `.xlsx` del Nomenclátor descargados del INE, cada uno con **todas las provincias de España** para un año dado (1981, 1991, 2001, 2011, 2021, 2025...). La app detecta automáticamente el año de cada fichero a partir de su contenido (no del nombre del fichero) y cuenta cuántas provincias distintas hay en él, como aviso si el fichero subido no parece nacional de verdad. No hace falta que todos los ficheros sean
del mismo año-tipo ni que estén completos: puedes subir un solo año o cualquier combinación.
URL de descarga: https://ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177010&idp=1254735572981

> **Aviso metodológico — 2024 en adelante:** desde el 1 de enero de 2024 el Nomenclátor cambia su fuente de población: pasa del Padrón Municipal al **Censo Anual de Población** (que cruza el padrón con registros de la Seguridad Social, Hacienda y educación). El formato del fichero `.xlsx` es idéntico, pero los datos de 2024 y 2025 **no son directamente comparables** con los de 1981-2023 en cuanto a la fuente subyacente, aunque el propio INE considera el Censo Anual una aproximación metodológicamente superior a la población real residente. Más detalle en la nota oficial del INE: https://www.ine.es/metodologia/Cifras_municipios.pdf

### 2. Extracción de municipios y unidades poblacionales

De cada fichero se extraen dos niveles:

- **Municipios**: población total del municipio, cada año.
- **Unidades poblacionales** (entidades singulares / núcleos de población): se excluyen las filas de agregación (parroquias u otras agrupaciones intermedias) y
  las de desglose núcleo/diseminado, para no duplicar población — se usa siempre el total de la entidad singular.

### 3. Emparejamiento 1981 ↔ 1991 en adelante: el código INE es la referencia correcta.

Esta es la parte más delicada, y la que ha cambiado más veces durante el desarrollo. La versión actual se basa en el hecho confirmado según la metodología oficial del INE (ver
[https://www.ine.es/nomenclator/metodologia.htm](https://www.ine.es/nomenclator/metodologia.htm)): el código de entidad (provincia + municipio + 4 dígitos) se asignó por primera vez, por orden alfabético dentro de cada municipio, con ocasión del Censo de Población de 1981, y se ha mantenido sin cambios desde entonces; el código de una entidad que desaparece **no se reutiliza** para otra distinta (la única excepción documentada por el INE es que, si esa misma entidad se da de alta de nuevo más adelante, recupera el código que tenía antes de la baja — no se le asigna a una entidad diferente).

Por eso:

- **El código es la ÚNICA clave que fusiona población desde 1981.** Si el código de una entidad de 1981 coincide con el de una entidad de 1991 en adelante (dentro del mismo municipio), se fusionan en una sola fila con toda la serie histórica — **sin exigir que el nombre coincida**: el nombre puede haber cambiado por completo (se marca `directo_renombrado` como aviso, no bloqueante).
- **Sin coincidencia de código, NO se fusiona población.** La unidad poblacional de 1981 queda como fila propia (`desaparecido`, solo dato de 1981) y la unidad poblacional de años posteriores queda como fila propia (`nuevo`, sin dato de 1981) — nunca se combinan por parecido de nombre. Fusionar por nombre mezclaría, con alta probabilidad, datos de dos lugares distintos. Se comprobó con los 6 ficheros nacionales reales: el 100% de los emparejamientos "solo por nombre" de una versión anterior de esta herramienta unían una entidad posterior a 1981 cuyo código no había existido nunca en ese año. Es exactamente el tipo de mezcla que el propio INE dice que su sistema de códigos evita.
- Aun así, se calcula una **sugerencia informativa** por similitud de nombre entre las entidades sin código coincidente (columna "Sugerencia" del Excel de unidades poblacionales: p. ej. "¿Castelo? (código 2301, score 0.53)"). Es solo una pista para revisión manual — el sistema nunca la da por buena ni fusiona población con ella.
- El emparejamiento por código busca en **todos** los años posteriores a 1981 incluidos en la ejecución, no solo en el primero: una entidad puede faltar en el fichero de un año concreto y reaparecer en años posteriores con el mismo código.
- Todo esto (columna "Estado", `desaparecido`/`nuevo`/sugerencias) solo aparece si el fichero de **1981** forma parte de la ejecución. Si procesas años posteriores sin incluir 1981, no hay nada contra lo que emparejar y ninguna entidad se marca como `nuevo` ni `desaparecido` — decirlo sería engañoso, ya que no se ha comprobado nada, solo no se ha buscado.
- Cuando una entidad aparece en varios años con nombres distintos (evolución normal de la ortografía o un renombrado real), el nombre que se muestra es siempre el del **año más reciente incluido** en la ejecución — el mismo criterio que usarías para nombrar el artículo de Wikipedia hoy. Aplica igual a municipios y a unidades poblacionales.

Los cuatro estados posibles de emparejamiento son, en resumen:

| Estado               | Significado                                                     |
| -------------------- | --------------------------------------------------------------- |
| `directo`            | Mismo código en 1981 y 1991+, nombre igual o muy parecido.      |
| `directo_renombrado` | Mismo código, pero el nombre cambió bastante (aviso, no error). |
| `desaparecido`       | Unidad poblacional de 1981 sin código correspondiente en 1991+. |
| `nuevo`              | Unidad poblacional de 1991+ cuyo código no existía en 1981.     |

### 4. Comprobación de cuadre

Para cada municipio y año se comprueba que la suma de sus unidades poblacionales coincida con la población del municipio en ese año. Las discrepancias se listan en pantalla y en la hoja de notas metodológicas del Excel.

### 5. Salidas

- **Excel de unidades poblacionales y de municipios**: columnas Municipio, Unidad poblacional (solo en el de unidades poblacionales), Entidad colectiva (solo en el de unidades y solo si alguna la tiene), Código INE, población de cada año incluido, y opcionalmente Estado (avisos de emparejamiento) y Sugerencia (candidato por nombre sin fusionar). Incluye una hoja de notas metodológicas con la fuente, el criterio de extracción, el criterio de emparejamiento y las discrepancias de cuadre si las hay.
- **Excel combinado de municipios y unidades poblacionales**: una sola hoja jerárquica con cada municipio seguido de sus unidades, con columna «Tipo» (Municipio / Unidad). En las filas de municipio, las columnas Unidad poblacional y Entidad colectiva van vacías (no aplican). La población se da en dos columnas por año, «Pob. municipio» y «Pob. unidad», cada una rellena solo en su nivel: así ninguna columna suma municipio y unidades a la vez (evita duplicar la población), y queda a la vista el caso frecuente de la entidad singular capital homónima del
  municipio. Pensado como vista única de revisión y para el cruce con Wikidata, ya que municipios y unidades comparten el mismo formato de Código INE.
- **CSV del INE** (uno por año, `ine_<año>.csv`): municipios y unidades combinados, todas las filas, con columnas codigo_ine, tipo, provincia, municipio, nombre, entidad_colectiva y poblacion del año. Es el fichero de intercambio hacia la herramienta de cruce; lleva todas las entidades (el filtrado a las que tienen ítem de Wikidata ocurre en el cruce).
- **Fichero `.tab` para Commons** (lo produce la herramienta de cruce, no el procesado): combinado (municipios y unidades en el mismo fichero), por año, con columnas codigo_ine (sin guiones, formato crudo de Wikidata), unidad, municipio, poblacion e id_wikidata. Sin columna «tipo»: se deduce de si «unidad» va vacío (municipio) o relleno (unidad). Títulos de columna y textos (`description`, `sources`) solo en inglés, por ser Commons un proyecto internacional. JSON compacto, sin indentado, para no acercarse al límite de 2 MB de Commons. Contiene solo las entidades con ítem de Wikidata ese año. Listo para subir al espacio `Data:` de Wikimedia Commons (la subida en sí queda fuera del alcance de la herramienta).

El **Código INE** que identifica a cada entidad tiene formato de unidad poblacional del Nomenclátor: `provincia-municipio-código de unidad` de 6 dígitos (entidad colectiva + entidad singular + núcleo/diseminado). Así, un municipio es `01-037-000000` y una entidad singular `01-037-010100` (ver https://www.ine.es/nomenclator/ayuda.htm). Es el mismo formato con el que se cruza contra los códigos de Wikidata. Única excepción: las entidades «desaparecidas» que solo tienen dato de 1981 conservan su código de 4 dígitos de aquel año (p. ej. `01-037-0101`), que pertenece a un esquema distinto (sin desglose de 6 dígitos) y no se rellena para no fabricar un código de unidad en años posteriores inexistente. Es seguro que el identificador sea así de directo porque el código es la única clave que fusiona población (ver sección 3): si el código de una entidad sin pareja
coincidiera con el de otra entidad real del mismo municipio, ya se habrían fusionado en una sola fila antes de llegar a mostrarse por separado. Comprobado también con los 6 ficheros nacionales reales: cero colisiones.

## Requisitos

- Python 3.10 o superior.
- Ficheros del Nomenclátor en formato **.xlsx**. Esta versión no admite `.xls` antiguo directamente ni hace conversión automática: si tienes un `.xls`, ábrelo con Excel, LibreOffice o Numbers y guárdalo como `.xlsx` (Archivo → Guardar como…) antes de subirlo.
- Algunos `.xlsx` descargados del INE traen referencias internas dañadas: "cargan" sin dar error pero al leerlos las hojas salen vacías. La herramienta lo detecta y avisa en pantalla en vez de fallar en silencio; si te ocurre, abre el fichero con Excel/LibreOffice/Numbers y guárdalo de nuevo como `.xlsx` para regenerarlo limpio.
- Los ficheros nacionales son grandes (~150 000 filas cada uno): procesar 6 años completos de España tarda del orden de 1-2 minutos.

Las dependencias de Python (Flask y openpyxl) se instalan solas la primera vez que arrancas la app; también puedes instalarlas a mano con
`pip install -r requirements.txt`.

## Cómo arrancarla

### Windows

Doble clic en `iniciar_windows.bat`. 
### macOS

Hacer doble clic en `iniciar_mac.command` (la primera vez, macOS puede bloquearlo por Gatekeeper — ver instrucciones dentro del propio fichero).

### Linux

Desde una terminal:

```bash
./iniciar_linux.sh
```
### Windows · macOS · Linux

La primera vez tarda un poco más (crea el entorno virtual e instala las dependencias); las siguientes veces arranca directo. Se abre solo el navegador en `http://127.0.0.1:8080`

El puerto por defecto es el 8080; puedes cambiarlo con la variable de entorno `PORT` (p. ej. `PORT=9000 ./iniciar_linux.sh`).

Para cerrar la app en cualquier sistema: `Ctrl+C` en la ventana/terminal donde está corriendo (mejor que cerrar la ventana de golpe, para que el puerto quede libre en el siguiente arranque).

## Estructura del proyecto

```
.
├── nomenclator/                     Motor: parseo, emparejamiento y salidas
│   ├── __init__.py
│   ├── tipos.py                     Estructuras de datos (UnidadRaw, EntidadResultado…)
│   ├── lectura.py                   Apertura del .xlsx y detección de hoja/filas útiles
│   ├── deteccion.py                 Detección del año y del ámbito (provincias presentes)
│   ├── parseo.py                    Filas → UnidadRaw; clasificación de códigos
│   ├── emparejamiento.py            Cruce 1981 ↔ 1991+ por código (§3 de este README)
│   ├── orquestador.py               Encadena todo y construye el resultado por año
│   ├── texto.py                     Utilidades de texto compartidas
│   ├── salida_excel.py              Genera los Excel de unidades poblacionales y municipios
│   ├── salida_csv_ine.py            Genera el CSV del INE por año (entrada del cruce)
│   ├── cruce_wikidata.py            Cruce con Wikidata y generación del .tab de Commons
│   └── salida_wikitexto.py          {{Gráfica de evolución}} (retirado, sin uso activo)
│
├── webapp/                          App Flask (subida, confirmación, descarga)
│   ├── app.py                       Rutas y arranque del servidor local
│   ├── templates/                   Plantillas Jinja2
│   │   ├── base.html
│   │   ├── subir.html
│   │   ├── confirmar.html
│   │   ├── cruce.html
│   │   └── resultados.html
│   └── static/
│       └── estilo.css
│
├── tests/                           Suite de tests (unittest)
│   ├── test_parseo.py
│   ├── test_emparejamiento.py
│   ├── test_orquestador.py
│   ├── test_salida.py
│   ├── test_salida_csv_ine.py
│   ├── test_cruce_wikidata.py
│   ├── test_entidad_colectiva.py
│   └── test_webapp.py
│
├── fixtures/                        Ficheros reales de prueba, ver sección Tests
│
├── iniciar_windows.bat              Arranque en Windows
├── iniciar_linux.sh                 Arranque en Linux
├── iniciar_mac.command              Arranque por doble clic en macOS
├── requirements.txt                 Dependencias (Flask, openpyxl)
├── .gitignore
├── LICENSE                          MIT
└── README.md                        Este fichero
```

## Tests

```bash
python -m unittest discover
```

`tests/` y `fixtures/` son para desarrollo y mantenimiento (verificar que el motor sigue produciendo los resultados correctos tras un cambio de código); no son necesarios para usar la app normalmente.

Los tests se dividen en dos grupos: los **sintéticos**, que construyen sus propios datos en memoria y se ejecutan siempre, y los de **fixture real**, que cotejan la salida carácter a carácter contra los wikitextos de referencia de Álava y solo corren si los ficheros de `fixtures/` están presentes. Los ficheros reales del INE no se incluyen en el repositorio público, así que al clonar solo desde GitHub correrán los sintéticos.

## Licencia

MIT. Ver el fichero `LICENSE` (o el encabezado del repositorio) para el texto completo.
