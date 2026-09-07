"""Tests del cruce con Wikidata y la generación del .tab combinado
(cruce_wikidata). Sintéticos: corren siempre en CI."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.cruce_wikidata import (
    construir_cruce,
    detectar_anio_de_nombre,
    generar_datos_tab_cruzado,
    guardar_tab_cruzado,
    nombre_pagina_tab_anio,
    normalizar_codigo_wikidata,
)


class TestNormalizacion(unittest.TestCase):
    def test_municipio_5_digitos(self):
        self.assertEqual(normalizar_codigo_wikidata("01001"), "01-001-000000")

    def test_unidad_11_digitos(self):
        self.assertEqual(normalizar_codigo_wikidata("01001000100"), "01-001-000100")

    def test_provincia_2_digitos_sin_cambio(self):
        # no es municipio ni unidad: se deja tal cual, no cruzará
        self.assertEqual(normalizar_codigo_wikidata("12"), "12")

    def test_6_digitos_raro_sin_cambio(self):
        self.assertEqual(normalizar_codigo_wikidata("425074"), "425074")

    def test_conserva_ceros(self):
        # el cero de provincia no se pierde
        self.assertEqual(normalizar_codigo_wikidata("05022"), "05-022-000000")


class TestDeteccionAnio(unittest.TestCase):
    def test_detecta_de_nombre(self):
        self.assertEqual(detectar_anio_de_nombre("ine_2025.csv"), 2025)

    def test_sin_anio(self):
        self.assertIsNone(detectar_anio_de_nombre("datos.csv"))


class TestConstruirCruce(unittest.TestCase):
    def _query(self, filas):
        d = tempfile.mkdtemp()
        ruta = Path(d) / "query.csv"
        with ruta.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["item", "value"])
            for item, value in filas:
                w.writerow([item, value])
        return ruta

    def test_extrae_q_y_normaliza(self):
        ruta = self._query([
            ("http://www.wikidata.org/entity/Q978587", "50094"),
            ("http://www.wikidata.org/entity/Q1330796", "01001"),
        ])
        cruce = construir_cruce(ruta)
        self.assertEqual(cruce["50-094-000000"], "Q978587")
        self.assertEqual(cruce["01-001-000000"], "Q1330796")

    def test_provincia_queda_sin_normalizar(self):
        ruta = self._query([("http://www.wikidata.org/entity/Q54942", "12")])
        cruce = construir_cruce(ruta)
        # la clave es "12" tal cual, que no cruzará con ningún código INE
        self.assertIn("12", cruce)


class TestGenerarTab(unittest.TestCase):
    def _csv_ine(self, filas):
        d = tempfile.mkdtemp()
        ruta = Path(d) / "ine_2025.csv"
        with ruta.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["codigo_ine", "tipo", "provincia", "municipio", "nombre", "entidad_colectiva", "poblacion"])
            for fila in filas:
                w.writerow(fila)
        return ruta

    def test_solo_coincidencias(self):
        ine = self._csv_ine([
            ["01-001-000000", "municipio", "01", "Alegría-Dulantzi", "", "", "2961"],
            ["01-001-000100", "unidad", "01", "Alegría-Dulantzi", "Alegría-Dulantzi", "", "2842"],
            ["01-001-000200", "unidad", "01", "Alegría-Dulantzi", "Egileta", "", "119"],
        ])
        cruce = {"01-001-000000": "Q1", "01-001-000200": "Q3"}  # falta la 000100
        datos = generar_datos_tab_cruzado(ine, cruce, 2025)
        codigos = [f[0] for f in datos["data"]]
        # sin guiones en la salida, aunque la clave de cruce sí los lleva
        self.assertEqual(codigos, ["01001000000", "01001000200"])  # solo las 2 con Q
        # el Q va en la última columna
        self.assertEqual(datos["data"][0][-1], "Q1")

    def test_esquema_combinado(self):
        ine = self._csv_ine([["01-001-000000", "municipio", "01", "X", "", "", "100"]])
        datos = generar_datos_tab_cruzado(ine, {"01-001-000000": "Q1"}, 2025)
        campos = [c["name"] for c in datos["schema"]["fields"]]
        # sin "tipo"; "nombre" pasa a llamarse "unidad" en el .tab
        self.assertEqual(campos, ["codigo_ine", "unidad", "municipio", "poblacion", "id_wikidata"])
        # títulos solo en inglés, sin objeto multilingüe con "es"
        for campo in datos["schema"]["fields"]:
            self.assertEqual(set(campo["title"].keys()), {"en"})

    def test_omite_sin_poblacion(self):
        ine = self._csv_ine([["01-001-000000", "municipio", "01", "X", "", "", ""]])
        datos = generar_datos_tab_cruzado(ine, {"01-001-000000": "Q1"}, 2025)
        self.assertEqual(datos["data"], [])

    def test_poblacion_es_numero(self):
        ine = self._csv_ine([["01-001-000000", "municipio", "01", "X", "", "", "100"]])
        datos = generar_datos_tab_cruzado(ine, {"01-001-000000": "Q1"}, 2025)
        # sin columna "tipo", la población es ahora el índice 3
        self.assertEqual(datos["data"][0][3], 100)
        self.assertIsInstance(datos["data"][0][3], int)

    def test_codigo_sin_guiones_en_salida(self):
        ine = self._csv_ine([["01-001-000000", "municipio", "01", "X", "", "", "100"]])
        datos = generar_datos_tab_cruzado(ine, {"01-001-000000": "Q1"}, 2025)
        self.assertEqual(datos["data"][0][0], "01001000000")

    def test_columna_unidad_desde_nombre_csv(self):
        # "unidad" en el .tab viene de la columna "nombre" del CSV del
        # INE, que no se toca: solo se renombra en el .tab de salida.
        ine = self._csv_ine([["01-001-000100", "unidad", "01", "X", "Y", "", "60"]])
        datos = generar_datos_tab_cruzado(ine, {"01-001-000100": "Q1"}, 2025)
        self.assertEqual(datos["data"][0][1], "Y")

    def test_description_y_sources_solo_ingles(self):
        ine = self._csv_ine([["01-001-000000", "municipio", "01", "X", "", "", "100"]])
        datos = generar_datos_tab_cruzado(ine, {"01-001-000000": "Q1"}, 2025)
        self.assertEqual(set(datos["description"].keys()), {"en"})
        self.assertIsInstance(datos["sources"], str)

    def test_nombre_pagina(self):
        self.assertEqual(nombre_pagina_tab_anio(2025), "Population ESP 2025.tab")

    def test_guardar_devuelve_conteos(self):
        ine = self._csv_ine([
            ["01-001-000000", "municipio", "01", "X", "", "", "100"],
            ["01-001-000100", "unidad", "01", "X", "Y", "", "60"],
        ])
        d = tempfile.mkdtemp()
        q = Path(d) / "query.csv"
        with q.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["item", "value"])
            w.writerow(["http://www.wikidata.org/entity/Q1", "01001"])
        ruta, n_filas, n_cruce = guardar_tab_cruzado(ine, q, 2025, Path(d) / "out")
        self.assertTrue(ruta.exists())
        self.assertEqual(n_filas, 1)   # solo el municipio cruzó
        self.assertEqual(n_cruce, 1)   # 1 código en el query


if __name__ == "__main__":
    unittest.main()
