"""Tests de emparejamiento.py con datos sintéticos (sin fixtures)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.emparejamiento import emparejar_provincia_1981_1991
from nomenclator.tipos import UnidadRaw


def _u(provincia, municipio, codigo, nombre, poblacion, anio, nivel="concejo"):
    return UnidadRaw(provincia=provincia, municipio=municipio, codigo=codigo,
                      nombre=nombre, poblacion=poblacion, anio=anio, nivel=nivel)


class TestColisionMunicipiosHomonimos(unittest.TestCase):
    """Regresión del bug real encontrado a escala nacional: el código de
    municipio (3 dígitos) se repite en las 52 provincias (todas
    numeran desde 001), así que agrupar solo por ese código -- en vez
    de por (provincia, municipio) -- mezclaba en el mismo
    emparejamiento voraz concejos de municipios homónimos de
    provincias completamente distintas."""

    def test_no_mezcla_concejos_de_provincias_distintas(self):
        # Dos provincias distintas, mismo código de municipio "001",
        # cada una con un único concejo que en 1981 se llamaba distinto
        # a su propio candidato de 1991 (nombre parcialmente parecido
        # entre sí PERO deberían emparejarse cada uno con el de su
        # propia provincia, no con el de la otra).
        concejos_1981 = [
            _u("01", "001", "0001", "ALDEA VIEJA", 100, 1981),
            _u("02", "001", "0001", "ALDEA NUEVA", 200, 1981),
        ]
        concejos_1991 = [
            _u("01", "001", "000100", "ALDEA VIEJA (NUCLEO)", 105, 1991),
            _u("02", "001", "000100", "ALDEA NUEVA (NUCLEO)", 210, 1991),
        ]
        matches = emparejar_provincia_1981_1991(concejos_1981, concejos_1991)

        # cada 1981 debe emparejarse con el 1991 de SU MISMA provincia,
        # no con el de la otra (que también tendría alta similitud de
        # nombre y podría "robarlo" si se agrupara solo por municipio).
        for m in matches:
            if m.concejo_1981 is not None and m.concejo_1991 is not None:
                self.assertEqual(m.concejo_1981.provincia, m.concejo_1991.provincia)

    def test_no_deja_desaparecidos_ni_nuevos_espurios(self):
        # Con el bug: al mezclar provincias, uno de los dos pares podía
        # quedarse sin candidato (todo "robado" por el otro) y salir
        # como desaparecido/nuevo espurio. Aquí ambos deben emparejar.
        concejos_1981 = [
            _u("01", "001", "0001", "SAN PEDRO", 100, 1981),
            _u("02", "001", "0001", "SAN PEDRO", 200, 1981),
        ]
        concejos_1991 = [
            _u("01", "001", "000100", "SAN PEDRO", 105, 1991),
            _u("02", "001", "000100", "SAN PEDRO", 210, 1991),
        ]
        matches = emparejar_provincia_1981_1991(concejos_1981, concejos_1991)
        estados = {(m.provincia, m.municipio): m.estado for m in matches}
        self.assertEqual(estados[("01", "001")], "directo")
        self.assertEqual(estados[("02", "001")], "directo")
        # y cada uno con la población de SU provincia, no la de la otra
        por_prov = {m.provincia: m for m in matches}
        self.assertEqual(por_prov["01"].concejo_1981.poblacion, 100)
        self.assertEqual(por_prov["02"].concejo_1981.poblacion, 200)

    def test_provincia_del_resultado_es_correcta_para_nuevo(self):
        # Municipio "001" existe en dos provincias; en una de ellas hay
        # un concejo "nuevo" (solo en 1991). Antes del fix, la
        # provincia de ese MatchResultado podía salir mal (se tomaba de
        # la lista global en vez de la del propio concejo).
        concejos_1981 = [
            _u("01", "001", "0001", "SAN PEDRO", 100, 1981),
        ]
        concejos_1991 = [
            _u("01", "001", "000100", "SAN PEDRO", 105, 1991),
            _u("02", "001", "000100", "CONCEJO NUEVO", 50, 1991),
        ]
        matches = emparejar_provincia_1981_1991(concejos_1981, concejos_1991)
        nuevo = next(m for m in matches if m.estado == "nuevo")
        self.assertEqual(nuevo.provincia, "02")
        self.assertEqual(nuevo.concejo_1991.nombre, "CONCEJO NUEVO")


if __name__ == "__main__":
    unittest.main()
