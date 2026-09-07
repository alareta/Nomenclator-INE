"""Test end-to-end de la Fase 3: simula el flujo completo del navegador
(subir -> confirmar -> procesar -> descargar) usando el test client de
Flask, con los ficheros reales de Álava."""

import re
import sys
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "webapp"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as webapp_module

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
FICHEROS_ALAVA = [
    "Provincia01_1981.xlsx", "Provincia01_1991.xlsx", "Provincia01_2001.xlsx",
    "Provincia01_2011.xlsx", "Provincia01_2021.xlsx", "Provincia01_2025.xlsx",
]

# Los ficheros reales de Álava no se incluyen en el repositorio público
# (ver README, sección Tests): este test end-to-end se salta si
# fixtures/ no está presente, en vez de fallar con FileNotFoundError.
_HAY_FIXTURES = all((FIXTURES / n).exists() for n in FICHEROS_ALAVA)


@unittest.skipUnless(_HAY_FIXTURES, "ficheros reales de Álava no presentes en fixtures/")
class TestFlujoWebCompleto(unittest.TestCase):
    def setUp(self):
        webapp_module.app.testing = True
        self.client = webapp_module.app.test_client()

    def _subir_ficheros(self, nombres):
        data = {
            "ficheros": [
                (BytesIO((FIXTURES / n).read_bytes()), n) for n in nombres
            ]
        }
        return self.client.post("/subir", data=data, content_type="multipart/form-data")

    def test_pagina_inicio_carga(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Nomenclator INE" if False else "Nomenclátor INE".encode(), r.data)

    def test_subida_detecta_anio_y_provincia_de_los_6_ficheros(self):
        r = self._subir_ficheros(FICHEROS_ALAVA)
        self.assertEqual(r.status_code, 200)
        texto = r.data.decode("utf-8")
        # cada uno de los 6 años detectados debe aparecer en la tabla de confirmación
        for anio in ["1981", "1991", "2001", "2011", "2021", "2025"]:
            self.assertIn(f'value="{anio}"', texto)
        self.assertNotIn("no detectado", texto)
        self.assertIsNone(re.search(r"aviso-error", texto))  # sin aviso de provincias distintas

    def test_flujo_completo_hasta_descargas(self):
        r_subir = self._subir_ficheros(FICHEROS_ALAVA)
        texto_confirmar = r_subir.data.decode("utf-8")
        upload_id = re.search(r'name="upload_id" value="([a-f0-9]+)"', texto_confirmar).group(1)

        datos_procesar = {"upload_id": upload_id}
        for i in range(len(FICHEROS_ALAVA)):
            datos_procesar[f"incluir_{i}"] = "on"
        # los años ya vienen pre-rellenados correctamente por la detección;
        # replicamos lo que el navegador enviaría leyendo el value de cada input
        anios_por_indice = re.findall(r'name="anio_\d+"\s+value="(\d+)"', texto_confirmar)
        for i, anio in enumerate(anios_por_indice):
            datos_procesar[f"anio_{i}"] = anio

        r_procesar = self.client.post("/procesar", data=datos_procesar, follow_redirects=True)
        self.assertEqual(r_procesar.status_code, 200)
        texto_resultados = r_procesar.data.decode("utf-8")

        self.assertIn("51", texto_resultados)  # nº municipios
        self.assertIn("444", texto_resultados)  # nº concejos
        self.assertIn("Sin discrepancias", texto_resultados)

        job_id = re.search(r"/descargar/([a-f0-9]+)/", texto_resultados).group(1)

        r_excel_concejos = self.client.get(f"/descargar/{job_id}/excel_concejos")
        self.assertEqual(r_excel_concejos.status_code, 200)
        self.assertGreater(len(r_excel_concejos.data), 1000)

        r_excel_municipios = self.client.get(f"/descargar/{job_id}/excel_municipios")
        self.assertEqual(r_excel_municipios.status_code, 200)

        r_zip_concejos = self.client.get(f"/descargar/{job_id}/wikitexto_concejos")
        self.assertEqual(r_zip_concejos.status_code, 200)
        with zipfile.ZipFile(BytesIO(r_zip_concejos.data)) as zf:
            self.assertEqual(len(zf.namelist()), 444)

        r_zip_municipios = self.client.get(f"/descargar/{job_id}/wikitexto_municipios")
        self.assertEqual(r_zip_municipios.status_code, 200)
        with zipfile.ZipFile(BytesIO(r_zip_municipios.data)) as zf:
            self.assertEqual(len(zf.namelist()), 51)

    def test_error_si_no_se_suben_ficheros(self):
        r = self.client.post("/subir", data={}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertIn("No se ha seleccionado", r.data.decode("utf-8"))

    def test_error_si_extension_no_soportada(self):
        data = {"ficheros": [(BytesIO(b"contenido"), "fichero.csv")]}
        r = self.client.post("/subir", data=data, content_type="multipart/form-data")
        self.assertIn("Formato no soportado", r.data.decode("utf-8"))

    def test_descarga_inexistente_devuelve_404(self):
        r = self.client.get("/descargar/no-existe/excel_concejos")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
