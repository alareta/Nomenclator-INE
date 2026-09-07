"""App Flask local para la Fase 3: subida de ficheros NACIONALES del
Nomenclátor (uno por año, cada fichero con todas las provincias de
España), confirmación del año detectado, y descarga de los
entregables (Excel de concejos, Excel de municipios y .tab para
Commons).

Se abandona el plan de "una provincia por ejecución": el motor
(parseo/emparejamiento, ver orquestador.py) ya agrupaba internamente
por (provincia, municipio) y nunca filtró de verdad por una sola
provincia, así que admite ficheros nacionales sin tocar nada ahí; lo
que cambia aquí es la interfaz, que ya no exige ni valida que todos
los ficheros sean de la misma provincia.

También se retira el wikitexto de la descarga (decisión: no se va a
usar; ver proyecto_utilidad_web_nomenclator.md). El módulo
salida_wikitexto.py se conserva sin usar por si hiciera falta
recuperarlo más adelante, pero esta app ya no lo importa.

Ejecutar con: python app.py
Requiere: el paquete `nomenclator` (Fase 1+2) accesible en el PYTHONPATH.
Solo admite ficheros .xlsx ya "limpios" (sin conversión automática desde
.xls ni reparación de referencias corruptas): si el usuario tiene un .xls
antiguo, debe abrirlo con Excel/LibreOffice/Numbers y guardarlo como
.xlsx antes de subirlo.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.cruce_wikidata import detectar_anio_de_nombre, guardar_tab_cruzado
from nomenclator.deteccion import detectar_anio_y_provincias
from nomenclator.orquestador import procesar_anios
from nomenclator.salida_csv_ine import guardar_csv_ine_por_anio
from nomenclator.salida_excel import guardar_excel_combinado, guardar_excels_provincia
from nomenclator.tipos import codigo_ine

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 256 * 1024 * 1024  # 256 MB: fichero nacional completo, no solo una provincia

EXTENSIONES_PERMITIDAS = {".xlsx"}

# Estado en memoria del proceso (sin backend persistente, ver §8 del diseño).
# Se pierde si se reinicia el servidor: aceptable para una herramienta local
# de un único usuario en el MVP.
UPLOADS: dict[str, dict] = {}
JOBS: dict[str, dict] = {}

DIR_BASE_TMP = Path(tempfile.gettempdir()) / "nomenclator_webapp"


def _dir_upload(upload_id: str) -> Path:
    return DIR_BASE_TMP / "uploads" / upload_id


def _dir_conversion(upload_id: str) -> Path:
    return DIR_BASE_TMP / "uploads" / upload_id / "_conv"


def _dir_salida(job_id: str) -> Path:
    return DIR_BASE_TMP / "jobs" / job_id


@app.route("/")
def subir():
    return render_template("subir.html")


@app.route("/subir", methods=["POST"])
def procesar_subida():
    ficheros_subidos = request.files.getlist("ficheros")
    ficheros_subidos = [f for f in ficheros_subidos if f and f.filename]

    if not ficheros_subidos:
        return render_template("subir.html", error="No se ha seleccionado ningún fichero.")

    invalidos = [f.filename for f in ficheros_subidos if Path(f.filename).suffix.lower() not in EXTENSIONES_PERMITIDAS]
    if invalidos:
        return render_template(
            "subir.html",
            error=(
                f"Formato no soportado (solo .xlsx): {', '.join(invalidos)}. "
                "Si tienes ficheros .xls antiguos, ábrelos con Excel/LibreOffice/Numbers "
                "y guárdalos como .xlsx antes de subirlos."
            ),
        )

    upload_id = uuid.uuid4().hex
    dir_upload = _dir_upload(upload_id)
    dir_upload.mkdir(parents=True, exist_ok=True)

    ficheros_meta = []
    for f in ficheros_subidos:
        nombre_seguro = secure_filename(f.filename)
        ruta_destino = dir_upload / nombre_seguro
        f.save(ruta_destino)
        error_deteccion = None
        try:
            # Recuento de provincias distintas en TODO el fichero (no solo
            # la primera fila): en un fichero nacional real da ~52 (50
            # provincias + Ceuta y Melilla), así que un valor bajo avisa
            # de que probablemente no es un fichero nacional.
            anio, provincias = detectar_anio_y_provincias(ruta_destino, _dir_conversion(upload_id))
            n_provincias = len(provincias)
        except Exception as exc:  # fichero ilegible: se deja para revisión manual
            anio, n_provincias = None, None
            error_deteccion = str(exc)
            app.logger.warning("No se pudo detectar el año de %s: %s", nombre_seguro, exc)
        ficheros_meta.append(
            {
                "nombre_original": f.filename,
                "nombre_fichero": nombre_seguro,
                "anio_detectado": anio,
                "n_provincias_detectadas": n_provincias,
                # Umbral bajo a propósito (>=1): solo queremos avisar del
                # caso claro de "esto no parece un fichero nacional", no
                # generar ruido por provincias mal codificadas puntuales.
                "aviso_pocas_provincias": n_provincias is not None and n_provincias <= 2,
                "error_deteccion": error_deteccion,
            }
        )

    UPLOADS[upload_id] = {"dir": dir_upload, "ficheros": ficheros_meta}

    return render_template(
        "confirmar.html",
        upload_id=upload_id,
        ficheros=ficheros_meta,
    )


@app.route("/procesar", methods=["POST"])
def procesar():
    upload_id = request.form.get("upload_id", "")
    subida = UPLOADS.get(upload_id)
    if subida is None:
        return render_template("subir.html", error="La subida ha expirado, vuelve a subir los ficheros.")

    ficheros_incluidos: dict[int, Path] = {}
    errores = []

    for idx, meta in enumerate(subida["ficheros"]):
        if request.form.get(f"incluir_{idx}") != "on":
            continue
        anio_texto = request.form.get(f"anio_{idx}", "").strip()
        if not anio_texto.isdigit():
            errores.append(f"Falta año válido para «{meta['nombre_original']}».")
            continue
        anio = int(anio_texto)
        if anio in ficheros_incluidos:
            errores.append(f"Año {anio} repetido en más de un fichero incluido.")
            continue
        ficheros_incluidos[anio] = subida["dir"] / meta["nombre_fichero"]

    if not ficheros_incluidos:
        errores.append("No has incluido ningún fichero para procesar.")

    if errores:
        return render_template(
            "confirmar.html",
            upload_id=upload_id,
            ficheros=subida["ficheros"],
            errores=errores,
        )

    resultado = procesar_anios(ficheros_incluidos, _dir_conversion(upload_id))
    anios = sorted(ficheros_incluidos)
    provincias_resultado = sorted({e.provincia for e in resultado.municipios})

    job_id = uuid.uuid4().hex
    dir_salida = _dir_salida(job_id)
    dir_salida.mkdir(parents=True, exist_ok=True)

    ruta_excel_concejos, ruta_excel_municipios = guardar_excels_provincia(resultado, anios, dir_salida / "excel")

    # Excel combinado: municipios y unidades poblacionales en una sola
    # hoja jerárquica (cada municipio seguido de sus unidades), pensado
    # como vista única para revisión y para el cruce con Wikidata (mismo
    # formato de código en ambos niveles).
    ruta_excel_combinado = guardar_excel_combinado(resultado, anios, dir_salida / "excel")

    # CSV del INE, uno por año, combinando municipios y unidades. Es la
    # "foto" del lado INE pensada para cruzarse luego, como paso aparte
    # (ruta /cruce), con el CSV de códigos↔Q de Wikidata. Lleva todas las
    # filas; el filtrado a coincidencias ocurre en el cruce, no aquí.
    rutas_csv_ine = guardar_csv_ine_por_anio(resultado, anios, dir_salida / "csv_ine")
    ruta_zip_csv_ine = Path(
        shutil.make_archive(str(dir_salida / "csv_ine"), "zip", dir_salida / "csv_ine")
    )

    # El .tab para Commons ya NO se genera aquí: sale de la herramienta de
    # cruce (ruta /cruce), que combina el CSV del INE con los códigos↔Q de
    # Wikidata y produce un .tab con el ítem Q ya adjudicado. Un .tab sin Q
    # no aporta nada para Commons, así que el procesado solo entrega los
    # Excel y el CSV del INE.

    JOBS[job_id] = {
        "resultado": resultado,
        "anios": anios,
        "n_provincias": len(provincias_resultado),
        "rutas": {
            "excel_concejos": ruta_excel_concejos,
            "excel_municipios": ruta_excel_municipios,
            "excel_combinado": ruta_excel_combinado,
            "csv_ine": ruta_zip_csv_ine,
        },
    }

    return redirect(url_for("resultados", job_id=job_id))


@app.route("/resultados/<job_id>")
def resultados(job_id):
    job = JOBS.get(job_id)
    if job is None:
        return render_template("subir.html", error="El resultado ha expirado, vuelve a subir los ficheros.")

    resultado = job["resultado"]

    # Resumen agregado en vez de listar cada caso: a escala nacional
    # pueden ser miles de filas, inviable de enseñar una a una en esta
    # pantalla. Se agrupa en dos bloques (ver §10.7 del documento de
    # diseño: el código es la única clave que fusiona población; el
    # nombre ya no fusiona, solo sugiere) y se muestran solo unos pocos
    # ejemplos (los de score más bajo, los más llamativos) por bloque;
    # el detalle completo de cada caso queda en las columnas "Estado" y
    # "Sugerencia" del Excel de concejos.
    N_EJEMPLOS = 8
    resumen_casos_dudosos = []

    renombrados = [c for c in resultado.casos_dudosos if c.estado_emparejamiento == "directo_renombrado"]
    if renombrados:
        renombrados.sort(key=lambda c: c.score_emparejamiento if c.score_emparejamiento is not None else 0)
        resumen_casos_dudosos.append(
            {
                "etiqueta": "Mismo código INE, nombre muy distinto (renombrado o reactivación)",
                "n": len(renombrados),
                "n_ocultos": max(0, len(renombrados) - N_EJEMPLOS),
                "ejemplos": [
                    {
                        "entidad": c,
                        "codigo_ine": codigo_ine(c),
                        "score": c.score_emparejamiento,
                        "detalle": None,
                    }
                    for c in renombrados[:N_EJEMPLOS]
                ],
            }
        )

    con_sugerencia = [c for c in resultado.casos_dudosos if c.sugerencia_nombre]
    if con_sugerencia:
        con_sugerencia.sort(key=lambda c: c.sugerencia_score if c.sugerencia_score is not None else 0)
        resumen_casos_dudosos.append(
            {
                "etiqueta": (
                    "Sin coincidencia de código: desaparecido/nuevo por separado, "
                    "con una posible relación por nombre (NO fusionada, solo sugerida)"
                ),
                "n": len(con_sugerencia),
                "n_ocultos": max(0, len(con_sugerencia) - N_EJEMPLOS),
                "ejemplos": [
                    {
                        "entidad": c,
                        "codigo_ine": codigo_ine(c),
                        "score": c.sugerencia_score,
                        "detalle": f"¿{c.sugerencia_nombre}? (código {c.sugerencia_codigo})",
                    }
                    for c in con_sugerencia[:N_EJEMPLOS]
                ],
            }
        )

    return render_template(
        "resultados.html",
        job_id=job_id,
        n_provincias=job["n_provincias"],
        anios=job["anios"],
        n_municipios=len(resultado.municipios),
        n_concejos=len(resultado.concejos),
        hay_1981=1981 in job["anios"],
        discrepancias=resultado.discrepancias,
        resumen_casos_dudosos=resumen_casos_dudosos,
        n_casos_dudosos=len(resultado.casos_dudosos),
        n_nuevos=sum(1 for c in resultado.concejos if c.estado_emparejamiento == "nuevo"),
        n_desaparecidos=sum(1 for c in resultado.concejos if c.estado_emparejamiento == "desaparecido"),
    )


@app.route("/descargar/<job_id>/<tipo>")
def descargar(job_id, tipo):
    job = JOBS.get(job_id)
    if job is None or tipo not in job["rutas"]:
        return "No encontrado", 404
    ruta = job["rutas"][tipo]
    return send_file(ruta, as_attachment=True, download_name=ruta.name)


# --- Herramienta de cruce con Wikidata (independiente del procesado) ---

CRUCES: dict[str, dict] = {}


@app.route("/cruce")
def cruce():
    return render_template("cruce.html")


@app.route("/cruce", methods=["POST"])
def cruce_subir():
    csv_ine = request.files.get("csv_ine")
    query_csv = request.files.get("query_csv")
    if not csv_ine or not csv_ine.filename or not query_csv or not query_csv.filename:
        return render_template("cruce.html", error="Faltan ficheros: sube el CSV del INE y el query.csv de Wikidata.")

    cruce_id = uuid.uuid4().hex
    dir_cruce = _dir_conversion(cruce_id)
    dir_cruce.mkdir(parents=True, exist_ok=True)
    ruta_ine = dir_cruce / secure_filename(csv_ine.filename)
    ruta_query = dir_cruce / secure_filename(query_csv.filename)
    csv_ine.save(ruta_ine)
    query_csv.save(ruta_query)

    anio = detectar_anio_de_nombre(csv_ine.filename)
    CRUCES[cruce_id] = {"ine": ruta_ine, "query": ruta_query, "dir": dir_cruce}

    return render_template(
        "cruce.html",
        cruce_id=cruce_id,
        anio_detectado=anio,
        nombre_ine=csv_ine.filename,
        nombre_query=query_csv.filename,
    )


@app.route("/cruce/generar", methods=["POST"])
def cruce_generar():
    cruce_id = request.form.get("cruce_id", "")
    datos = CRUCES.get(cruce_id)
    if datos is None:
        return render_template("cruce.html", error="La subida ha expirado, vuelve a subir los ficheros.")

    anio_texto = request.form.get("anio", "").strip()
    if not anio_texto.isdigit():
        return render_template(
            "cruce.html",
            cruce_id=cruce_id,
            anio_detectado=None,
            nombre_ine=datos["ine"].name,
            nombre_query=datos["query"].name,
            error="Indica un año válido (4 dígitos).",
        )
    anio = int(anio_texto)

    dir_salida = datos["dir"] / "salida"
    ruta_tab, n_filas, n_cruce = guardar_tab_cruzado(datos["ine"], datos["query"], anio, dir_salida)
    datos["tab"] = ruta_tab

    return render_template(
        "cruce.html",
        cruce_id=cruce_id,
        listo=True,
        anio=anio,
        n_filas=n_filas,
        n_cruce=n_cruce,
        nombre_tab=ruta_tab.name,
    )


@app.route("/cruce/descargar/<cruce_id>")
def cruce_descargar(cruce_id):
    datos = CRUCES.get(cruce_id)
    if datos is None or "tab" not in datos:
        return "No encontrado", 404
    ruta = datos["tab"]
    return send_file(ruta, as_attachment=True, download_name=ruta.name)


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="127.0.0.1", port=puerto)
