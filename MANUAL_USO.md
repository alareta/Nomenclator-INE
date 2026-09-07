# Manual de uso — Nomenclátor INE
Guía rápida para usar la herramienta: 

Se toma como punto de partida los ficheros de censo descargados del INE a los ficheros listos para Wikipedia, Wikidata y Wikimedia Commons.

No haces falta leer el código ni la documentación técnica para seguir este manual — está pensado para el uso normal, del día a día.

## Índice

1. [Antes de empezar: de dónde salen los datos](#1-antes-de-empezar-de-dónde-salen-los-datos)
2. [Arrancar la app](#2-arrancar-la-app)
3. [Paso 1 — Subir los ficheros del INE](#3-paso-1--subir-los-ficheros-del-ine)
4. [Paso 2 — Confirmar el año de cada fichero](#4-paso-2--confirmar-el-año-de-cada-fichero)
5. [Paso 3 — Revisar los resultados](#5-paso-3--revisar-los-resultados)
6. [Paso 4 — Descargar los ficheros generados](#6-paso-4--descargar-los-ficheros-generados)
7. [Paso 5 (opcional) — Cruzar con Wikidata](#7-paso-5-opcional--cruzar-con-wikidata)
8. [Problemas frecuentes](#8-problemas-frecuentes)

---

## 1. Origen de la información: de dónde salen los datos

La app **no descarga nada por ti**: tienes que bajarte tú los ficheros del INE y, si posteriormente vas a hacer el cruce con los datos de Wikidata, necesitaras el CSV de una consulta SPARQL en Wikidata. Son dos fuentes distintas:

### 1.1. Ficheros del INE (Nomenclátor)

Página oficial del Nomenclátor (Población por Unidad Poblacional):

**[https://ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177010&idp=1254735572981](https://ine.es/dyngs/INEbase/es/operacion.htm?c=Estadistica_C&cid=1254736177010&idp=1254735572981)**

Desde ahí puedes visualizar y descargar las tablas del Nomenclátor para cada año. Necesitas el fichero **nacional** de cada año que quieras procesar (el que trae **todas las provincias de España** en un único .xlsx`), no un fichero de una sola provincia.

Otras dos páginas del INE que te pueden servir de referencia (no hace falta entrar salvo que tengas dudas sobre el formato de los códigos o el criterio de población de cada año):

- Ayuda del Nomenclátor: https://www.ine.es/nomenclator/ayuda.htm
- Metodología: https://www.ine.es/nomenclator/metodologia.htm
- Porqué el nomenclator: https://www.ine.es/metodologia/Cifras_municipios.pdf

Años disponibles habitualmente: 1981, 1991 y luego cada año desde 2000 en adelante (2001, 2011, 2021, 2025...). No hace falta que los proceses todos a la vez ni que estén completos: puedes subir solo un año, o cualquier combinación.

> ⚠️ **Aviso — años 2024 en adelante:** desde el 1 de enero de 2024 el Nomenclátor cambia su fuente de población: pasa del Padrón Municipal al **Censo Anual de Población** (que cruza el padrón con registros de la Seguridad Social, Hacienda y educación). El fichero se descarga y se sube igual, pero las cifras de 2024/2025 **no son directamente comparables** con las de años anteriores (1981-2023) en cuanto a su fuente. Si vas a mostrar una evolución histórica de población en un artículo, ten esto en cuenta al interpretar el último dato. Más detalle en la nota oficial del INE (enlace de arriba, "Porqué el nomenclátor").

> 💡 **¿Cuántos años subir a la vez?** Depende de para qué lo quieras:
>
> - Si vas a **cruzar los datos con Wikidata** (sección 7), procesa **un año cada vez**. El cruce trabaja siempre sobre el CSV del INE de un único año, así que subir varios años juntos no aporta nada para ese fin y solo añade tiempo de procesado y ficheros de más a gestionar.
> - Subir **varios años a la vez** sí tiene sentido para otros usos: por ejemplo, incluir **1981 junto con uno o más años posteriores** para que la app haga el emparejamiento entre censos (ver sección 5) y genere los avisos de "desaparecida"/"nueva"/renombrada, o para tener de un vistazo la evolución de población de varios años en el mismo Excel.
>
> En resumen: para alimentar el cruce con Wikidata, ve año a año; para revisión y comparación entre censos, junta los años que necesites.

> ⚠️ Formato: la app solo admite `.xlsx`. Si el INE te da un `.xls 
> antiguo, ábrelo con Excel, LibreOffice o Numbers y guárdalo com `.xlsx` (Archivo → Guardar como…) antes de subirlo.
>
> ⚠️ A veces un `.xlsx` del INE "carga" sin dar error pero las hoja 
> salen vacías (referencias internas dañadas del propio fichero). Si t 
> pasa, ábrelo con Excel/LibreOffice/Numbers y guárdalo de nuevo com 
> `.xlsx`: eso lo regenera limpio. La app te avisará en pantalla s 
> detecta este problema.

### 1.2. CSV de Wikidata (solo si vas a hacer el cruce)

Este paso es aparte y solo hace falta si quieres generar el fichero `.tab` para Wikimedia Commons con el ítem Q de cada municipio/unidad ya  adjudicado.

Consulta SPARQL lista para usar (código INE ↔ ítem de Wikidata): *https://query.wikidata.org/#SELECT%20%3Fitem%20%3Fvalue%0AWHERE%20%7B%0A%20%20%3Fitem%20wdt%3AP772%20%3Fvalue%0A%7D**

Pasos para obtener el CSV:

1. Abre el enlace de arriba. Se abre el Wikidata Query Service con la consulta ya escrita (busca todos los ítems que tienen la propiedad **P772**, "código INE de municipio").
2. Pulsa el botón ▶ **"Run query" / "Ejecutar consulta"**.
3. Cuando termine, busca el icono de descarga (⬇) sobre los resultados y elige **CSV**.
4. Guarda el fichero — el nombre no importa, la app solo mira las columnas `item` (URL del ítem Qxxxx) y `value` (código INE en crudo).

Este CSV es el que subirás como "CSV de Wikidata" en el paso de cruce (sección 7).

---

## 2. Arrancar la app

**macOS**
Hacer doble clic en `NOMENCLATOR.command`.

**Linux/macOS** — desde una terminal:

```bash
./iniciar_linux.sh
```

**Windows** — doble clic en `iniciar_windows.bat`.

La primera vez tarda un poco más (crea el entorno virtual e instala las dependencias); las siguientes veces arranca directo. Se abre solo el navegador en `http://127.0.0.1:8080`. **Como cerrar la app en todos los sistemas**

Para cerrar la app: `Ctrl+C` en la ventana/terminal donde está corriendo (mejor que cerrar la ventana de golpe).

---

## 3. Paso 1 — Subir los ficheros del INE

En la pantalla inicial, pulsa el selector de ficheros y elige uno o varios `.xlsx` nacionales del Nomenclátor (uno por año). Puedes seleccionar varios a la vez.

Pulsa **"Subir y detectar año"**.

---

## 4. Paso 2 — Confirmar el año de cada fichero

La app detecta automáticamente el año de cada fichero mirando su contenido (no el nombre del fichero) y cuenta cuántas provincias distintas trae, para avisarte si un fichero no parece nacional de verdad (por ejemplo, si solo tiene una provincia).

En esta pantalla:

- Revisa que el año detectado sea correcto para cada fichero; corrígelo a mano si hace falta.
- Marca qué ficheros quieres incluir en el procesado (puedes dejar alguno fuera).
- No puedes incluir dos ficheros con el mismo año.

Cuando esté todo correcto, pulsa **"Procesar"**.

Los ficheros nacionales son grandes (~150.000 filas cada uno); procesar varios años completos de España puede tardar del orden de 1-2 minutos.

---

## 5. Paso 3 — Revisar los resultados

Al terminar el procesado verás un resumen con:

- Número de provincias, municipios y unidades poblacionales procesados, y los años incluidos.
- **Discrepancias de cuadre**: casos donde la suma de las unidades poblacionales de un municipio no coincide con la población total del municipio ese año.
- Si incluiste el fichero de **1981**, también verás un resumen de los casos de emparejamiento entre 1981 y años posteriores:
  - Entidades con el **mismo código INE pero nombre muy distinto** (renombrados o reactivaciones) — aviso, no error.
  - Entidades **sin coincidencia de código** (aparecen como "desaparecida" en 1981 o "nueva" en un año posterior), con una posible pista de nombre parecido — es solo una sugerencia para revisión manual, **nunca se fusiona automáticamente por nombre**.

Si no incluiste 1981, no verás esta sección: sin ese fichero no hay nada contra lo que comparar.

El detalle completo de todos estos casos (no solo los ejemplos que se muestran en pantalla) está en las columnas **"Estado"** y **"Sugerencia"** del Excel de unidades poblacionales.

---

## 6. Paso 4 — Descargar los ficheros generados

Desde la pantalla de resultados puedes descargar:

| Fichero                                   | Para qué sirve                                                                                                                                                                                                                          |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Excel de unidades poblacionales**       | Una fila por unidad poblacional (núcleo/entidad singular), con su Código INE, población de cada año incluido, entidad colectiva (si la tiene) y las columnas de emparejamiento (Estado/Sugerencia).                                     |
| **Excel de municipios**                   | Una fila por municipio, con Código INE y población de cada año incluido.                                                                                                                                                                |
| **Excel combinado**                       | Municipios y unidades poblacionales en una sola hoja jerárquica (cada municipio seguido de sus unidades), con columna "Tipo" y población en columnas separadas por nivel para no duplicar cifras. Pensado como vista única de revisión. |
| **CSV del INE (uno por año, en un .zip)** | Municipios y unidades combinados, todas las entidades, formato de intercambio. **Es el fichero que necesitas para el cruce con Wikidata** (paso siguiente).                                                                             |

---

## 7. Paso 5 (opcional) — Cruzar con Wikidata

Esta herramienta es independiente del procesado: no hace falta volver a subir los `.xlsx` del INE, solo necesitas dos CSV:

1. El **CSV del INE de un año** (el que descargaste en el paso anterior, `ine_<año>.csv`).
2. El **CSV de Wikidata** (ver sección 1.2 de este manual).

El cruce siempre es **de un año en un año**: si has procesado varios años, repite este paso una vez por cada `ine_<año>.csv` que quieras cruzar (el CSV de Wikidata es el mismo para todos, no hace falta volver a descargarlo).

Pasos:

1. Desde la pantalla inicial, entra en **"Cruzar con Wikidata"**.
2. Sube ambos ficheros.
3. La app intenta detectar el año a partir del nombre del CSV del INE (por ejemplo `ine_2025.csv` → 2025); revísalo o corrígelo si hace falta.
4. Pulsa **"Generar"**.
5. Descarga el fichero `.tab` resultante.

El `.tab` generado:

- Combina municipios y unidades poblacionales en un solo fichero, para un año.
- Contiene **solo** las entidades cuyo código INE ha encontrado un ítem Q en el CSV de Wikidata ese año (las que no tienen Q se quedan fuera del `.tab`, pero siguen estando en el CSV del INE completo).
- Está listo para subir al espacio `Data:` de Wikimedia Commons. La subida en sí (con el bot/cuenta correspondiente) queda fuera de esta herramienta.

---

## 8. Problemas frecuentes

**"Formato no soportado (solo .xlsx)"**
Tienes un `.xls` antiguo. Ábrelo con Excel/LibreOffice/Numbers y guárdalo como `.xlsx`.

**Aviso de "pocas provincias detectadas"**
El fichero que has subido probablemente no es el nacional completo (quizá es de una sola provincia). Revisa que hayas descargado el fichero de todas las provincias de España para ese año.

**Un `.xlsx` carga pero las hojas salen vacías**
Referencias internas dañadas del propio fichero del INE. Ábrelo con Excel/LibreOffice/Numbers y guárdalo de nuevo como `.xlsx`.

**"La subida ha expirado"**
El estado de la app se guarda en memoria mientras el servidor está corriendo; si lo reinicias o pasa mucho tiempo, tienes que volver a subir los ficheros.

**El cruce con Wikidata no encuentra casi ningún ítem Q**
Comprueba que el CSV de Wikidata sea el de la consulta de la sección 1.2 (columnas `item` y `value`, propiedad P772) y que lo hayas descargado completo (la consulta puede tardar unos segundos en ejecutarse antes de poder descargar).
