"""Tests de la exportación del CSV del INE (salida_csv_ine).

Sintéticos: corren siempre en CI."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.salida_csv_ine import CABECERA, guardar_csv_ine_por_anio
from nomenclator.tipos import EntidadResultado, ResultadoProvincia


def _municipio(poblacion=None):
    e = EntidadResultado(
        tipo="municipio",
        provincia="36",
        municipio_codigo="017",
        municipio_nombre="ESTRADA (A)",
        entidad_id="36-017",
        nombre="ESTRADA (A)",
    )
    e.poblacion_por_anio = poblacion if poblacion is not None else {2025: 20101}
    return e


def _concejo(nombre, entidad_id, ec_nombre=None, poblacion=None):
    e = EntidadResultado(
        tipo="concejo",
        provincia="36",
        municipio_codigo="017",
        municipio_nombre="ESTRADA (A)",
        entidad_id=entidad_id,
        nombre=nombre,
        estado_emparejamiento="directo",
        ec_nombre=ec_nombre,
        ec_codigo=(entidad_id.rsplit("-", 1)[-1][0:2] if ec_nombre else None),
    )
    e.poblacion_por_anio = poblacion if poblacion is not None else {2025: 9}
    return e


def _leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return list(csv.reader(f))


class TestCsvIne(unittest.TestCase):
    def _resultado(self):
        muni = _municipio()
        c1 = _concejo("GONXAR", "36-017-0101")
        c2 = _concejo("ALDEA GRANDE (A)", "36-017-3801", ec_nombre="RIBELA (SANTA MARIÑA P.)")
        return ResultadoProvincia(municipios=[muni], concejos=[c1, c2], discrepancias=[])

    def test_un_fichero_por_anio(self):
        with tempfile.TemporaryDirectory() as d:
            rutas = guardar_csv_ine_por_anio(self._resultado(), [1981, 2025], d)
            nombres = sorted(r.name for r in rutas)
            self.assertEqual(nombres, ["ine_1981.csv", "ine_2025.csv"])

    def test_cabecera_y_conteo(self):
        with tempfile.TemporaryDirectory() as d:
            rutas = guardar_csv_ine_por_anio(self._resultado(), [2025], d)
            filas = _leer(rutas[0])
            self.assertEqual(filas[0], CABECERA)
            self.assertEqual(len(filas) - 1, 3)  # 1 municipio + 2 unidades

    def test_orden_jerarquico(self):
        with tempfile.TemporaryDirectory() as d:
            rutas = guardar_csv_ine_por_anio(self._resultado(), [2025], d)
            filas = _leer(rutas[0])[1:]
            self.assertEqual(filas[0][1], "municipio")
            self.assertTrue(all(f[1] == "unidad" for f in filas[1:]))

    def test_municipio_nombre_y_ec_vacios(self):
        with tempfile.TemporaryDirectory() as d:
            rutas = guardar_csv_ine_por_anio(self._resultado(), [2025], d)
            fila_muni = _leer(rutas[0])[1]
            # codigo_ine, tipo, provincia, municipio, nombre, ec, poblacion
            self.assertEqual(fila_muni[0], "36-017-000000")
            self.assertEqual(fila_muni[4], "")  # nombre vacío
            self.assertEqual(fila_muni[5], "")  # entidad_colectiva vacía
            self.assertEqual(fila_muni[6], "20101")

    def test_unidad_con_entidad_colectiva(self):
        with tempfile.TemporaryDirectory() as d:
            rutas = guardar_csv_ine_por_anio(self._resultado(), [2025], d)
            filas = _leer(rutas[0])
            fila_ec = [f for f in filas if len(f) > 4 and "Aldea Grande" in f[4]][0]
            self.assertEqual(fila_ec[0], "36-017-380100")
            self.assertIn("Ribela", fila_ec[5])

    def test_poblacion_vacia_si_no_hay_dato(self):
        # entidad con dato solo en 2025, se pide CSV de 1981 -> población vacía
        muni = _municipio(poblacion={2025: 100})
        c = _concejo("X", "36-017-0101", poblacion={2025: 100})
        res = ResultadoProvincia(municipios=[muni], concejos=[c], discrepancias=[])
        with tempfile.TemporaryDirectory() as d:
            rutas = guardar_csv_ine_por_anio(res, [1981], d)
            filas = _leer(rutas[0])[1:]
            for f in filas:
                self.assertEqual(f[6], "")  # sin dato en 1981 -> vacío, no 0


if __name__ == "__main__":
    unittest.main()
