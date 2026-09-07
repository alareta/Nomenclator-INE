"""Tests de la Fase 2 (generadores de salida), incluyendo comparación
exacta del wikitexto generado contra el fichero de referencia real
aportado por el usuario (concejos_alava_wikitexto.txt)."""

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.orquestador import procesar_provincia
from nomenclator.salida_excel import generar_excels_provincia
from nomenclator.salida_wikitexto import (
    calcular_color_n,
    capitalizar_nombre_display,
    generar_ficheros_wikitexto_provincia,
    generar_nota_leyenda,
    generar_wikitexto_entidad,
    nombre_fichero_entidad,
    nombre_para_mostrar,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
DIR_TRABAJO = Path(__file__).resolve().parent.parent / "_work_tests"

FICHEROS_ALAVA = {
    1981: FIXTURES / "Provincia01_1981.xlsx",
    1991: FIXTURES / "Provincia01_1991.xlsx",
    2001: FIXTURES / "Provincia01_2001.xlsx",
    2011: FIXTURES / "Provincia01_2011.xlsx",
    2021: FIXTURES / "Provincia01_2021.xlsx",
    2025: FIXTURES / "Provincia01_2025.xlsx",
}
ANIOS_ALAVA = sorted(FICHEROS_ALAVA)
REFERENCIA_WIKITEXTO = FIXTURES / "concejos_alava_wikitexto.txt"

# Los ficheros reales de Álava no se incluyen en el repositorio público
# (ver README, sección Tests): las clases que los usan se saltan si
# fixtures/ no está presente. Los tests sintéticos corren siempre.
_HAY_FIXTURES = all(p.exists() for p in FICHEROS_ALAVA.values()) and REFERENCIA_WIKITEXTO.exists()
requiere_fixtures = unittest.skipUnless(
    _HAY_FIXTURES, "ficheros reales de Álava no presentes en fixtures/"
)

# Excepciones conocidas y aceptadas (ver §10.1 del documento de diseño):
# el pilotaje manual fusionó a mano el renombrado completo
# "Villarreal de Álava" (1981) -> "Legutio" (1991+), mientras que el
# emparejamiento automático por similitud de nombre no lo detecta.
NOMBRE_NO_ENCONTRADO_ESPERADO = "Villarreal de Alava (desaparecido/Agregado)"
NOMBRE_DIFERENTE_ESPERADO = "Legutio"


def _parsear_bloques_referencia(texto: str) -> dict[str, str]:
    bloques = {}
    partes = re.split(r"^### (.+)$", texto, flags=re.MULTILINE)
    for i in range(1, len(partes), 2):
        nombre = partes[i].strip()
        contenido = partes[i + 1]
        bloque = contenido.split("\n\n---")[0].split("\n\n##")[0].strip()
        bloques[nombre] = bloque
    return bloques


class TestCapitalizacionNombre(unittest.TestCase):
    def test_mayuscula_por_palabra(self):
        self.assertEqual(capitalizar_nombre_display("ALEGRIA-DULANTZI"), "Alegria-Dulantzi")

    def test_preposicion_en_minuscula(self):
        self.assertEqual(capitalizar_nombre_display("NANCLARES DE GAMBOA"), "Nanclares de Gamboa")

    def test_preposicion_al_inicio_se_capitaliza(self):
        # caso límite: si la preposición fuese la primera palabra, se capitaliza igualmente
        self.assertEqual(capitalizar_nombre_display("LA PUEBLA"), "La Puebla")

    def test_nombre_dual_conserva_barra(self):
        self.assertEqual(capitalizar_nombre_display("CICUJANO/ZEKUIANO"), "Cicujano/Zekuiano")


class TestColorYLeyenda(unittest.TestCase):
    def test_color_n_cuenta_anios(self):
        self.assertEqual(calcular_color_n([1981, 1991, 2001, 2011, 2021, 2025]), 6)
        self.assertEqual(calcular_color_n([2021, 2025]), 2)

    def test_leyenda_solo_padron(self):
        self.assertIn("padrón municipal", generar_nota_leyenda({1991: "padron", 2001: "padron"}))
        self.assertNotIn("derecho", generar_nota_leyenda({1991: "padron"}))

    def test_leyenda_solo_1981(self):
        nota = generar_nota_leyenda({1981: "derecho_1981"})
        self.assertIn("Población de derecho", nota)
        self.assertNotIn("padrón municipal", nota)

    def test_leyenda_mezcla(self):
        nota = generar_nota_leyenda({1981: "derecho_1981", 1991: "padron"})
        self.assertIn("Población de derecho", nota)
        self.assertIn("padrón municipal", nota)


@requiere_fixtures
class TestWikitextoContraReferenciaReal(unittest.TestCase):
    """Compara, entidad a entidad, el wikitexto generado por el motor
    contra el fichero de referencia real de Álava ya publicado."""

    @classmethod
    def setUpClass(cls):
        cls.resultado = procesar_provincia(FICHEROS_ALAVA, DIR_TRABAJO)
        cls.bloques_ref = _parsear_bloques_referencia(
            REFERENCIA_WIKITEXTO.read_text(encoding="utf-8")
        )

    def test_coincidencia_masiva_con_referencia(self):
        coincide, no_coincide, no_encontrado = [], [], []
        for c in self.resultado.concejos:
            nombre_mostrado = nombre_para_mostrar(c)
            generado = generar_wikitexto_entidad(c, "25 de agosto de 2026").strip()
            if nombre_mostrado not in self.bloques_ref:
                no_encontrado.append(nombre_mostrado)
            elif generado != self.bloques_ref[nombre_mostrado]:
                no_coincide.append(nombre_mostrado)
            else:
                coincide.append(nombre_mostrado)

        total = len(self.resultado.concejos)
        # Se admite exactamente la excepción conocida y documentada; nada más.
        self.assertEqual(no_encontrado, [NOMBRE_NO_ENCONTRADO_ESPERADO])
        self.assertEqual(no_coincide, [NOMBRE_DIFERENTE_ESPERADO])
        self.assertGreaterEqual(len(coincide) / total, 0.99)

    def test_caso_desaparecido_coincide_con_referencia(self):
        astobiza = next(c for c in self.resultado.concejos if "ASTOBIZA" in c.nombre.upper())
        generado = generar_wikitexto_entidad(astobiza, "25 de agosto de 2026").strip()
        self.assertEqual(generado, self.bloques_ref["Astobiza (desaparecido/Agregado)"])

    def test_caso_nuevo_coincide_con_referencia(self):
        barrundia = next(c for c in self.resultado.concejos if c.entidad_id == "01-013-0017")
        generado = generar_wikitexto_entidad(barrundia, "25 de agosto de 2026").strip()
        self.assertEqual(generado, self.bloques_ref["Barrundia"])


@requiere_fixtures
class TestFicherosPorEntidad(unittest.TestCase):
    def test_genera_un_fichero_por_entidad(self):
        resultado = procesar_provincia(FICHEROS_ALAVA, DIR_TRABAJO)
        dir_salida = DIR_TRABAJO / "wikitexto_concejos"
        rutas = generar_ficheros_wikitexto_provincia(
            resultado.concejos, dir_salida, fecha_acceso="25 de agosto de 2026"
        )
        self.assertEqual(len(rutas), len(resultado.concejos))
        self.assertEqual(len(set(rutas)), len(rutas))  # nombres únicos, sin colisiones
        for ruta in rutas[:5]:
            self.assertTrue(ruta.exists())
            self.assertIn("Gráfica de evolución", ruta.read_text(encoding="utf-8"))

    def test_nombre_fichero_incluye_entidad_id(self):
        resultado = procesar_provincia(FICHEROS_ALAVA, DIR_TRABAJO)
        alegria = next(c for c in resultado.concejos if c.entidad_id == "01-001-0001")
        nombre = nombre_fichero_entidad(alegria)
        self.assertIn("01-001-0001", nombre)
        self.assertTrue(nombre.endswith(".wikitext.txt"))


@requiere_fixtures
class TestGeneracionExcel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.resultado = procesar_provincia(FICHEROS_ALAVA, DIR_TRABAJO)
        cls.libro_concejos, cls.libro_municipios = generar_excels_provincia(cls.resultado, ANIOS_ALAVA)

    def test_hojas_presentes(self):
        self.assertIn("Concejos", self.libro_concejos.sheetnames)
        self.assertIn("Notas metodológicas", self.libro_concejos.sheetnames)
        self.assertIn("Municipios", self.libro_municipios.sheetnames)

    def test_cabecera_concejos(self):
        ws = self.libro_concejos["Concejos"]
        cabecera = [c.value for c in ws[1]]
        self.assertEqual(cabecera[0], "Municipio")
        self.assertEqual(cabecera[1], "Concejo")
        self.assertIn("Pob. 1981", cabecera)
        self.assertIn("Pob. 2025", cabecera)
        self.assertIn("Estado", cabecera)  # hay casos dudoso/nuevo/desaparecido

    def test_cabecera_municipios_sin_columna_concejo(self):
        ws = self.libro_municipios["Municipios"]
        cabecera = [c.value for c in ws[1]]
        self.assertEqual(cabecera[0], "Municipio")
        self.assertNotIn("Concejo", cabecera)

    def test_autofiltro_activo(self):
        ws = self.libro_concejos["Concejos"]
        self.assertIsNotNone(ws.auto_filter.ref)

    def test_columna_congelada(self):
        ws = self.libro_concejos["Concejos"]
        self.assertEqual(ws.freeze_panes, "C2")

    def test_numero_filas_igual_a_numero_entidades(self):
        ws = self.libro_concejos["Concejos"]
        filas_datos = ws.max_row - 1  # menos cabecera
        self.assertEqual(filas_datos, len(self.resultado.concejos))

    def test_celda_de_anio_sin_dato_esta_en_blanco(self):
        ws = self.libro_concejos["Concejos"]
        # localizar fila de Barrundia (nuevo, sin dato en 1981)
        col_concejo = 2
        col_1981 = 3  # Municipio, Concejo, Pob.1981...
        fila_barrundia = next(
            f for f in range(2, ws.max_row + 1)
            if ws.cell(row=f, column=col_concejo).value == "Barrundia"
        )
        self.assertIsNone(ws.cell(row=fila_barrundia, column=col_1981).value)

    def test_notas_reportan_sin_discrepancias(self):
        ws = self.libro_concejos["Notas metodológicas"]
        contenido = "\n".join(c.value for c in ws["A"] if c.value)
        self.assertIn("Sin discrepancias", contenido)


if __name__ == "__main__":
    unittest.main()
