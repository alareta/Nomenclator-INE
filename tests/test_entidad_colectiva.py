"""Tests de las funcionalidades de entidad colectiva (EC), código INE
unificado en formato de unidad poblacional, y Excel combinado
municipios+unidades.

Todos sintéticos: no dependen de los ficheros reales de Álava, así que
corren siempre en CI. Ver la entrada correspondiente del documento de
diseño (proyecto_utilidad_web_nomenclator.md)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.salida_excel import (
    generar_excel_combinado,
    generar_excels_provincia,
)
from nomenclator.tipos import (
    EntidadResultado,
    ResultadoProvincia,
    codigo_ine,
    codigo_ine_11,
)


def _municipio(nombre="ESTRADA (A)", provincia="36", municipio_codigo="017", poblacion=None):
    e = EntidadResultado(
        tipo="municipio",
        provincia=provincia,
        municipio_codigo=municipio_codigo,
        municipio_nombre=nombre,
        entidad_id=f"{provincia}-{municipio_codigo}",
        nombre=nombre,
    )
    e.poblacion_por_anio = poblacion if poblacion is not None else {2025: 20101}
    return e


def _concejo(
    nombre="ALDEA GRANDE (A)",
    provincia="36",
    municipio_codigo="017",
    entidad_id="36-017-3801",
    municipio_nombre="ESTRADA (A)",
    ec_codigo=None,
    ec_nombre=None,
    plano_1981=False,
    poblacion=None,
):
    e = EntidadResultado(
        tipo="concejo",
        provincia=provincia,
        municipio_codigo=municipio_codigo,
        municipio_nombre=municipio_nombre,
        entidad_id=entidad_id,
        nombre=nombre,
        estado_emparejamiento="directo",
        ec_codigo=ec_codigo,
        ec_nombre=ec_nombre,
        entidad_id_es_plano_1981=plano_1981,
    )
    e.poblacion_por_anio = poblacion if poblacion is not None else {2025: 9}
    return e


class TestCodigoIneUnificado(unittest.TestCase):
    """El código INE debe salir en formato de unidad poblacional de 6 díg
    (PP-MMM-EEEECC), cruzable con Wikidata, con la excepción de las
    entidades solo-1981 que conservan su código corto de 4 díg."""

    def test_municipio_seis_ceros(self):
        self.assertEqual(codigo_ine(_municipio()), "36-017-000000")

    def test_entidad_singular_rellena_nuc_00(self):
        # AABB=3801 -> +NUC(00) = 380100
        self.assertEqual(codigo_ine(_concejo(entidad_id="36-017-3801")), "36-017-380100")

    def test_desaparecida_1981_conserva_codigo_corto(self):
        # Excepción: código de 4 díg del esquema de 1981, sin rellenar.
        desap = _concejo(entidad_id="36-017-1981-0038", plano_1981=True)
        self.assertEqual(codigo_ine(desap), "36-017-0038")

    def test_codigo_ine_11_alias_municipio(self):
        self.assertEqual(codigo_ine_11(_municipio()), "36-017-000000")

    def test_codigo_ine_11_rechaza_no_municipio(self):
        with self.assertRaises(ValueError):
            codigo_ine_11(_concejo())


class TestColumnaEntidadColectiva(unittest.TestCase):
    """La columna 'Entidad colectiva' aparece solo en la tabla de
    unidades y solo si alguna unidad tiene ec_nombre."""

    def _resultado(self, concejos):
        return ResultadoProvincia(
            municipios=[_municipio()],
            concejos=concejos,
            discrepancias=[],
        )

    def test_columna_aparece_con_ec(self):
        concejo = _concejo(ec_codigo="38", ec_nombre="RIBELA (SANTA MARIÑA P.)")
        libro_c, _ = generar_excels_provincia(self._resultado([concejo]), [2025])
        cabecera = [c.value for c in libro_c["Unidades poblacionales"][1]]
        self.assertIn("Entidad colectiva", cabecera)
        # y el valor sale capitalizado en su fila
        idx = cabecera.index("Entidad colectiva")
        fila = [c.value for c in libro_c["Unidades poblacionales"][2]]
        self.assertIn("Ribela", str(fila[idx]))

    def test_columna_ausente_sin_ec(self):
        concejo = _concejo(ec_codigo=None, ec_nombre=None)
        libro_c, _ = generar_excels_provincia(self._resultado([concejo]), [2025])
        cabecera = [c.value for c in libro_c["Unidades poblacionales"][1]]
        self.assertNotIn("Entidad colectiva", cabecera)

    def test_municipios_nunca_tienen_columna_ec(self):
        concejo = _concejo(ec_codigo="38", ec_nombre="RIBELA (SANTA MARIÑA P.)")
        _, libro_m = generar_excels_provincia(self._resultado([concejo]), [2025])
        cabecera = [c.value for c in libro_m["Municipios"][1]]
        self.assertNotIn("Entidad colectiva", cabecera)


class TestExcelCombinado(unittest.TestCase):
    """El Excel combinado mezcla municipios y unidades en una hoja
    jerárquica: cada municipio seguido de sus unidades."""

    def _resultado(self):
        muni = _municipio()
        c1 = _concejo(nombre="GONXAR", entidad_id="36-017-0101")
        c2 = _concejo(nombre="ALDEA GRANDE (A)", entidad_id="36-017-3801",
                      ec_codigo="38", ec_nombre="RIBELA (SANTA MARIÑA P.)")
        return ResultadoProvincia(municipios=[muni], concejos=[c1, c2], discrepancias=[])

    def test_orden_jerarquico_municipio_primero(self):
        wb = generar_excel_combinado(self._resultado(), [2025])
        ws = wb["Municipios y unidades"]
        filas = list(ws.iter_rows(min_row=2, values_only=True))
        # primera fila de datos: el municipio
        self.assertEqual(filas[0][0], "Municipio")
        # siguientes: unidades del municipio
        self.assertTrue(all(f[0] == "Unidad" for f in filas[1:]))
        self.assertEqual(len(filas), 3)  # 1 municipio + 2 unidades

    def test_fila_municipio_tiene_vacias_unidad_y_ec(self):
        wb = generar_excel_combinado(self._resultado(), [2025])
        ws = wb["Municipios y unidades"]
        cabecera = [c.value for c in ws[1]]
        fila_muni = [c.value for c in ws[2]]
        # "Unidad poblacional" vacía en el municipio
        idx_unidad = cabecera.index("Unidad poblacional")
        self.assertIn(fila_muni[idx_unidad], ("", None))
        # población real, NO cero
        # población real del municipio en su columna, NO cero
        idx_pob = cabecera.index("Pob. municipio 2025")
        self.assertEqual(fila_muni[idx_pob], 20101)
        # y la columna de unidad va vacía en la fila-municipio (no duplica)
        idx_pob_u = cabecera.index("Pob. unidad 2025")
        self.assertIn(fila_muni[idx_pob_u], ("", None))
        # código en formato largo
        idx_cod = cabecera.index("Código INE")
        self.assertEqual(fila_muni[idx_cod], "36-017-000000")

    def test_unidad_lleva_su_entidad_colectiva(self):
        wb = generar_excel_combinado(self._resultado(), [2025])
        ws = wb["Municipios y unidades"]
        cabecera = [c.value for c in ws[1]]
        idx_ec = cabecera.index("Entidad colectiva")
        # buscar la fila de Aldea Grande (con EC Ribela)
        encontrada = False
        for fila in ws.iter_rows(min_row=2, values_only=True):
            if fila[0] == "Unidad" and "Aldea Grande" in str(fila[2]):
                self.assertIn("Ribela", str(fila[idx_ec]))
                encontrada = True
        self.assertTrue(encontrada)

    def test_poblacion_no_se_duplica(self):
        """Cada columna de población (municipio / unidad) debe sumar el
        total una sola vez. Es el motivo de separar la población en dos
        columnas: una única columna sumaría municipio + unidades y
        duplicaría la población."""
        # municipio 100 hab = 2 unidades de 60 y 40
        muni = _municipio(poblacion={2025: 100})
        u1 = _concejo(nombre="A", entidad_id="36-017-0101", poblacion={2025: 60})
        u2 = _concejo(nombre="B", entidad_id="36-017-0102", poblacion={2025: 40})
        res = ResultadoProvincia(municipios=[muni], concejos=[u1, u2], discrepancias=[])
        wb = generar_excel_combinado(res, [2025])
        ws = wb["Municipios y unidades"]
        cabecera = [c.value for c in ws[1]]
        im = cabecera.index("Pob. municipio 2025")
        iu = cabecera.index("Pob. unidad 2025")
        suma_m = sum(f[im] for f in ws.iter_rows(min_row=2, values_only=True) if f[im] is not None)
        suma_u = sum(f[iu] for f in ws.iter_rows(min_row=2, values_only=True) if f[iu] is not None)
        self.assertEqual(suma_m, 100)  # una vez, no 200
        self.assertEqual(suma_u, 100)  # 60 + 40, una vez


if __name__ == "__main__":
    unittest.main()
