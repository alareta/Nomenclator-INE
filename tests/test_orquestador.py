"""Tests de orquestador.procesar_provincia con datos sintéticos (sin
depender de fixtures reales de Álava), centrados en casos límite de
combinación de años."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.orquestador import procesar_provincia
from nomenclator.tipos import UnidadRaw

DIR_TRABAJO = Path(__file__).resolve().parent.parent / "_work_tests"


def _unidades_1981():
    return [
        UnidadRaw(provincia="01", municipio="001", codigo="0000", nombre="ALEGRIA",
                   poblacion=1037, anio=1981, nivel="municipio"),
        UnidadRaw(provincia="01", municipio="001", codigo="0100", nombre="ALEGRIA",
                   poblacion=985, anio=1981, nivel="concejo"),
        UnidadRaw(provincia="01", municipio="001", codigo="0200", nombre="EGUILETA",
                   poblacion=52, anio=1981, nivel="concejo"),
    ]


def _unidades_1991():
    return [
        UnidadRaw(provincia="01", municipio="001", codigo="000000", nombre="ALEGRIA-DULANTZI",
                   poblacion=1050, anio=1991, nivel="municipio"),
        UnidadRaw(provincia="01", municipio="001", codigo="010000", nombre="ALEGRIA-DULANTZI",
                   poblacion=990, anio=1991, nivel="concejo"),
        UnidadRaw(provincia="01", municipio="001", codigo="020000", nombre="EGUILETA",
                   poblacion=55, anio=1991, nivel="concejo"),
    ]


class TestProcesarProvinciaSolo1981(unittest.TestCase):
    """El caso que dio el error original: se incluye únicamente el
    fichero de 1981, sin ningún año 1991+ en la misma ejecución. No hay
    con qué emparejar, así que no debe intentarse (antes: min() sobre
    secuencia vacía -> ValueError)."""

    def test_no_lanza_excepcion(self):
        with patch(
            "nomenclator.orquestador.parsear_fichero_anio",
            side_effect=lambda ruta, anio, dir_trabajo: _unidades_1981(),
        ):
            resultado = procesar_provincia({1981: "cualquiera.xlsx"}, DIR_TRABAJO)
        self.assertEqual(len(resultado.municipios), 1)
        self.assertEqual(len(resultado.concejos), 2)

    def test_concejos_llevan_solo_dato_1981(self):
        with patch(
            "nomenclator.orquestador.parsear_fichero_anio",
            side_effect=lambda ruta, anio, dir_trabajo: _unidades_1981(),
        ):
            resultado = procesar_provincia({1981: "cualquiera.xlsx"}, DIR_TRABAJO)
        for concejo in resultado.concejos:
            self.assertEqual(set(concejo.poblacion_por_anio), {1981})

    def test_no_marca_como_desaparecido(self):
        # "desaparecido" describe un concejo que falta en 1991+ TENIENDO
        # ambos años disponibles; aquí no se ha subido ningún 1991+, así
        # que no aplica esa etiqueta.
        with patch(
            "nomenclator.orquestador.parsear_fichero_anio",
            side_effect=lambda ruta, anio, dir_trabajo: _unidades_1981(),
        ):
            resultado = procesar_provincia({1981: "cualquiera.xlsx"}, DIR_TRABAJO)
        estados = {c.estado_emparejamiento for c in resultado.concejos}
        self.assertEqual(estados, {None})

    def test_no_hay_casos_dudosos(self):
        with patch(
            "nomenclator.orquestador.parsear_fichero_anio",
            side_effect=lambda ruta, anio, dir_trabajo: _unidades_1981(),
        ):
            resultado = procesar_provincia({1981: "cualquiera.xlsx"}, DIR_TRABAJO)
        self.assertEqual(resultado.casos_dudosos, [])


class TestProcesarProvincia1981Y1991(unittest.TestCase):
    """Caso normal (regresión): con 1981 + un año 1991+, el
    emparejamiento sigue funcionando igual que antes del fix."""

    def _procesar(self):
        datos = {1981: _unidades_1981(), 1991: _unidades_1991()}
        with patch(
            "nomenclator.orquestador.parsear_fichero_anio",
            side_effect=lambda ruta, anio, dir_trabajo: datos[anio],
        ):
            return procesar_provincia({1981: "a.xlsx", 1991: "b.xlsx"}, DIR_TRABAJO)

    def test_concejos_llevan_ambos_anios(self):
        resultado = self._procesar()
        for concejo in resultado.concejos:
            self.assertEqual(set(concejo.poblacion_por_anio), {1981, 1991})

    def test_estado_emparejamiento_no_es_none(self):
        resultado = self._procesar()
        for concejo in resultado.concejos:
            self.assertIsNotNone(concejo.estado_emparejamiento)


if __name__ == "__main__":
    unittest.main()
