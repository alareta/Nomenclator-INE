"""Tests del motor de parseo (Fase 1), usando como fixture los ficheros
reales del Nomenclátor de Álava 1981-2025 (§10 del documento de diseño).
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nomenclator.emparejamiento import normalizar_nombre, similitud
from nomenclator.lectura import (
    _num_columnas_significativas,
    _recortar_a_columnas_significativas,
    detectar_hoja_y_filas,
    preparar_fichero,
)
from nomenclator.parseo import (
    _partir_codigo_nombre,
    clasificar_codigo4,
    clasificar_codigo6,
    detectar_formato,
    extraer_agregaciones,
    extraer_concejos,
    extraer_municipios,
    parsear_fichero_anio,
    parsear_filas_1981,
    parsear_filas_1991plus,
    validar_cuadre,
)
from nomenclator.orquestador import procesar_provincia

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

# Los ficheros reales de Álava no se incluyen en el repositorio público
# (ver README, sección Tests): las clases que los usan se saltan con
# elegancia si fixtures/ no está presente, en vez de fallar con
# FileNotFoundError. Los tests sintéticos de este módulo corren siempre.
_HAY_FIXTURES = all(p.exists() for p in FICHEROS_ALAVA.values())
requiere_fixtures = unittest.skipUnless(
    _HAY_FIXTURES, "ficheros reales de Álava no presentes en fixtures/"
)


class TestClasificacionCodigo6(unittest.TestCase):
    def test_municipio(self):
        self.assertEqual(clasificar_codigo6("000000"), "municipio")

    def test_concejo_normal(self):
        self.assertEqual(clasificar_codigo6("000200"), "concejo")

    def test_agregacion(self):
        # 010000: AA=01 (!=00), BB=00, CC=00 -> agrupación estadística
        self.assertEqual(clasificar_codigo6("010000"), "agregacion")

    def test_concejo_dentro_de_agregacion(self):
        # 010300: AA=01, BB=03 (!=00) -> concejo normal, no agregación
        self.assertEqual(clasificar_codigo6("010300"), "concejo")

    def test_nucleo(self):
        self.assertEqual(clasificar_codigo6("000101"), "nucleo")

    def test_diseminado(self):
        self.assertEqual(clasificar_codigo6("000199"), "diseminado")


class TestClasificacionCodigo4(unittest.TestCase):
    """Formato 1981 (AABB): mismo concepto de agregación ('Diputación
    de X') que clasificar_codigo6 para 1991+, sin desglose
    núcleo/diseminado. Caso real que dio discrepancias de cuadre a
    escala nacional: municipio Cuevas del Almanzora (04-035)."""

    def test_municipio(self):
        self.assertEqual(clasificar_codigo4("0000"), "municipio")

    def test_concejo_normal(self):
        self.assertEqual(clasificar_codigo4("0002"), "concejo")

    def test_agregacion_diputacion(self):
        # 0300: AA=03 (!=00), BB=00 -> "Diputación de Cuevas del
        # Almanzora", agrupa a sus hijas 0301..0307.
        self.assertEqual(clasificar_codigo4("0300"), "agregacion")

    def test_concejo_dentro_de_agregacion(self):
        # 0305: AA=03, BB=05 (!=00) -> concejo real, no agregación.
        self.assertEqual(clasificar_codigo4("0305"), "concejo")

    def test_codigo_no_valido(self):
        self.assertEqual(clasificar_codigo4("03"), "otro")


class TestNormalizacionNombre(unittest.TestCase):
    def test_quita_acentos_y_mayusculas(self):
        self.assertEqual(normalizar_nombre("Eguíleta"), "EGUILETA")

    def test_quita_sufijos_nivel(self):
        self.assertEqual(normalizar_nombre("MAESTU(NUCLEO)"), "MAESTU")
        self.assertEqual(normalizar_nombre("*DISEMINADO* ALEGRÍA-DULANTZI"), "ALEGRIA-DULANTZI")

    def test_quita_parte_tras_barra(self):
        self.assertEqual(normalizar_nombre("Vitoria-Gasteiz/Gasteiz"), "VITORIA-GASTEIZ")

    def test_renombrado_municipio(self):
        # Caso real: 1981 "MAESTU" -> 1991+ "ARRAIA-MAEZTU". No son el mismo
        # nombre, así que la similitud NO debe ser alta (se emparejan por
        # código de municipio en el pipeline, no por nombre de municipio).
        self.assertLess(similitud("MAESTU", "ARRAIA-MAEZTU"), 0.6)


@requiere_fixtures
class TestLecturaFicheros(unittest.TestCase):
    """Verifica que los 6 ficheros reales de Álava (ya en .xlsx limpio, ver
    §10.4: esta versión no depende de LibreOffice) son legibles, incluyendo
    los casos límite anticipados en §3.3 (cabecera duplicada, hojas
    múltiples de desglose adicional)."""

    def test_todos_los_ficheros_son_legibles(self):
        for anio, path in FICHEROS_ALAVA.items():
            with self.subTest(anio=anio):
                path_xlsx = preparar_fichero(path, DIR_TRABAJO)
                filas = detectar_hoja_y_filas(path_xlsx)
                self.assertGreater(len(filas), 0, f"Sin filas de datos en {anio}")
                # ninguna fila de datos debe colarse como cabecera
                self.assertNotEqual(filas[0][0], "Provincia")

    def test_formato_1981_detectado(self):
        path_xlsx = preparar_fichero(FICHEROS_ALAVA[1981], DIR_TRABAJO)
        filas = detectar_hoja_y_filas(path_xlsx)
        self.assertEqual(detectar_formato(filas), "formato_1981")

    def test_formato_1991_detectado(self):
        path_xlsx = preparar_fichero(FICHEROS_ALAVA[1991], DIR_TRABAJO)
        filas = detectar_hoja_y_filas(path_xlsx)
        self.assertEqual(detectar_formato(filas), "formato_1991plus")

    def test_2011_sin_filas_de_cabecera_duplicadas(self):
        # el fichero de 2011 trae 2 filas de cabecera idénticas seguidas;
        # deben saltarse ambas.
        path_xlsx = preparar_fichero(FICHEROS_ALAVA[2011], DIR_TRABAJO)
        filas = detectar_hoja_y_filas(path_xlsx)
        cabeceras_colgadas = [f for f in filas if f[0] == "Provincia"]
        self.assertEqual(len(cabeceras_colgadas), 0)


class TestPartirCodigoNombre(unittest.TestCase):
    """Caso real visto en el fichero nacional de 2011: el código va
    pegado al nombre sin espacio ('000000ALEGRIA-DULANTZI'), a
    diferencia del resto de años ('000000 ALEGRIA-DULANTZI'). El
    código se extrae por el prefijo numérico, no por separación de
    espacios."""

    def test_con_espacio(self):
        self.assertEqual(_partir_codigo_nombre("000000 ALEGRIA-DULANTZI"), ("000000", "ALEGRIA-DULANTZI"))

    def test_sin_espacio(self):
        self.assertEqual(_partir_codigo_nombre("000000ALEGRIA-DULANTZI"), ("000000", "ALEGRIA-DULANTZI"))

    def test_1981_sin_espacio(self):
        self.assertEqual(_partir_codigo_nombre("0002EGUILETA"), ("0002", "EGUILETA"))

    def test_varios_espacios(self):
        self.assertEqual(_partir_codigo_nombre("0000   ALEGRIA"), ("0000", "ALEGRIA"))


class TestDetectarFormatoSinEspacio(unittest.TestCase):
    """detectar_formato debe seguir funcionando con el código pegado al
    nombre (usa _partir_codigo_nombre, no un split por espacio)."""

    def test_1991plus_sin_espacio(self):
        filas = [("01", "001", "000000ALEGRIA-DULANTZI", 2803, 1466, 1337)]
        self.assertEqual(detectar_formato(filas), "formato_1991plus")

    def test_1981_sin_espacio(self):
        filas = [("01", "001", "0000ALEGRIA", 1054, 548, 506, 1037)]
        self.assertEqual(detectar_formato(filas), "formato_1981")


class TestColumnaFantasmaAlFinal(unittest.TestCase):
    """Caso real de 2011: una 7ª columna de más, siempre None, que sin
    recortar hace que detectar_formato vea 7 columnas donde debería ver
    6 y lo confunda con el formato de 1981 (que también tiene 7, pero
    con código de 4 dígitos en vez de 6)."""

    def test_recorta_columna_fantasma(self):
        cabecera = ("Provincia", "Municipio", "Unidad Poblacional", "Total 2011", "Hombres 2011", "Mujeres 2011", None)
        n = _num_columnas_significativas(cabecera)
        self.assertEqual(n, 6)

    def test_filas_de_datos_recortadas_a_la_misma_longitud(self):
        datos = [
            ("01", "001", "000000ALEGRIA-DULANTZI", 2803, 1466, 1337, None),
            ("01", "001", "000100ALEGRIA-DULANTZI", 2688, 1408, 1280, None),
        ]
        recortadas = _recortar_a_columnas_significativas(datos, 6)
        for fila in recortadas:
            self.assertEqual(len(fila), 6)
        self.assertEqual(detectar_formato(recortadas), "formato_1991plus")


@requiere_fixtures
class TestParseoPorFormato(unittest.TestCase):
    def test_1981_usa_poblacion_de_derecho(self):
        unidades = parsear_fichero_anio(FICHEROS_ALAVA[1981], 1981, DIR_TRABAJO)
        maestu = next(u for u in unidades if u.municipio == "037" and u.codigo == "0000")
        self.assertEqual(maestu.nombre, "MAESTU")
        self.assertEqual(maestu.poblacion, 813)  # Población de Derecho, no de Hecho (789)
        self.assertEqual(maestu.nivel, "municipio")

    def test_1991_clasifica_niveles(self):
        unidades = parsear_fichero_anio(FICHEROS_ALAVA[1991], 1991, DIR_TRABAJO)
        niveles = {u.codigo: u.nivel for u in unidades if u.municipio == "037"}
        self.assertEqual(niveles["000000"], "municipio")
        self.assertEqual(niveles["010000"], "agregacion")  # Cicujano (agrupación)
        self.assertEqual(niveles["020000"], "agregacion")  # Virgala Mayor (agrupación)
        self.assertEqual(niveles["010300"], "concejo")  # Cicujano (concejo real)


class TestParseo1981Agregaciones(unittest.TestCase):
    """Regresión del caso real reportado a escala nacional: municipios
    de 1981 con filas de 'Diputación' (agregación de sus concejos
    hijos) que antes se contaban como concejos normales, duplicando
    población al validar el cuadre.

    Ejemplo sintético equivalente al caso real (municipio Cuevas del
    Almanzora, 04-035, que sí dio la discrepancia con el fichero
    nacional de 1981): un municipio con dos "Diputaciones", cada una
    agrupando a sus concejos hijos, y población de municipio = suma
    de las hojas (no de las Diputaciones)."""

    FILAS = [
        ("04", "035", "0000   MUNICIPIO EJEMPLO", 0, 0, 0, 100),
        ("04", "035", "0100   DIPUTACION DE A", 0, 0, 0, 60),  # agregación: 40+20
        ("04", "035", "0101   A UNO", 0, 0, 0, 40),
        ("04", "035", "0102   A DOS", 0, 0, 0, 20),
        ("04", "035", "0200   DIPUTACION DE B", 0, 0, 0, 40),  # agregación: 25+15
        ("04", "035", "0201   B UNO", 0, 0, 0, 25),
        ("04", "035", "0202   B DOS", 0, 0, 0, 15),
    ]

    def _unidades(self):
        return parsear_filas_1981(self.FILAS, 1981)

    def test_filas_diputacion_clasificadas_como_agregacion(self):
        niveles = {u.codigo: u.nivel for u in self._unidades()}
        self.assertEqual(niveles["0100"], "agregacion")
        self.assertEqual(niveles["0200"], "agregacion")

    def test_filas_hoja_clasificadas_como_concejo(self):
        niveles = {u.codigo: u.nivel for u in self._unidades()}
        for codigo in ("0101", "0102", "0201", "0202"):
            self.assertEqual(niveles[codigo], "concejo")

    def test_agregaciones_excluidas_de_concejos(self):
        concejos = extraer_concejos(self._unidades())
        codigos = {u.codigo for u in concejos}
        self.assertNotIn("0100", codigos)
        self.assertNotIn("0200", codigos)

    def test_cuadre_correcto_tras_excluir_diputaciones(self):
        # Antes del fix: suma_concejos incluía también las Diputaciones
        # (60+40+40+20+25+15=200, el doble de 100). Con el fix, solo
        # las hojas: 40+20+25+15=100, cuadra con el municipio.
        discrepancias = validar_cuadre(self._unidades())
        self.assertEqual(discrepancias, [])


@requiere_fixtures
class TestValidacionCuadre(unittest.TestCase):
    def test_arraia_maeztu_1991_cuadra_excluyendo_agregaciones(self):
        unidades = parsear_fichero_anio(FICHEROS_ALAVA[1991], 1991, DIR_TRABAJO)
        discrepancias = validar_cuadre(unidades)
        afecta_arraia = [d for d in discrepancias if d.municipio == "037"]
        self.assertEqual(afecta_arraia, [], "Arraia-Maeztu debe cuadrar excluyendo agregaciones")

    def test_1981_maestu_cuadra(self):
        unidades = parsear_fichero_anio(FICHEROS_ALAVA[1981], 1981, DIR_TRABAJO)
        discrepancias = validar_cuadre(unidades)
        afecta_maestu = [d for d in discrepancias if d.municipio == "037"]
        self.assertEqual(afecta_maestu, [])

    def test_sin_discrepancias_generalizadas_1991(self):
        # No forzamos cero discrepancias en toda la provincia (podría haber
        # casos reales de descuadre en el propio INE), pero sí que sean
        # una fracción pequeña del total de municipios.
        unidades = parsear_fichero_anio(FICHEROS_ALAVA[1991], 1991, DIR_TRABAJO)
        discrepancias = validar_cuadre(unidades)
        total_municipios = len(extraer_municipios(unidades))
        self.assertLess(len(discrepancias), total_municipios * 0.1)


@requiere_fixtures
class TestAgregacionesExcluidas(unittest.TestCase):
    def test_cicujano_virgala_excluidos_en_1991(self):
        unidades = parsear_fichero_anio(FICHEROS_ALAVA[1991], 1991, DIR_TRABAJO)
        agregaciones = extraer_agregaciones(unidades)
        codigos_arraia = {a.codigo for a in agregaciones if a.municipio == "037"}
        self.assertEqual(codigos_arraia, {"010000", "020000"})

    def test_agregaciones_no_aparecen_en_concejos(self):
        unidades = parsear_fichero_anio(FICHEROS_ALAVA[1991], 1991, DIR_TRABAJO)
        concejos = extraer_concejos(unidades)
        codigos_concejos_arraia = {c.codigo for c in concejos if c.municipio == "037"}
        self.assertNotIn("010000", codigos_concejos_arraia)
        self.assertNotIn("020000", codigos_concejos_arraia)


@requiere_fixtures
class TestProcesarProvinciaAlava(unittest.TestCase):
    """Test de referencia contra las cifras conocidas del piloto (§10):
    51 municipios, ~443 concejos, 11 desaparecidos, 4 nuevos, 1 caso de
    agrupación estadística (Arraia-Maeztu)."""

    @classmethod
    def setUpClass(cls):
        cls.resultado = procesar_provincia(FICHEROS_ALAVA, DIR_TRABAJO)

    def test_51_municipios(self):
        self.assertEqual(len(self.resultado.municipios), 51)

    def test_numero_concejos_en_rango_esperado(self):
        # ~443 según §10; toleramos un margen razonable dado que "~" no es exacto
        n = len(self.resultado.concejos)
        self.assertTrue(400 <= n <= 470, f"nº de concejos fuera de rango: {n}")

    def test_un_solo_municipio_con_agregaciones(self):
        municipios_con_agregacion = {a.municipio for a in self.resultado.agregaciones_excluidas}
        self.assertEqual(municipios_con_agregacion, {"037"})

    def test_arraia_maeztu_agregaciones_excluidas_en_todos_los_anios_1991plus(self):
        # agregaciones_excluidas guarda una entrada por año (trazabilidad),
        # así que con 5 años 1991-2025 y 2 filas de agregación por año
        # esperamos 10 entradas, con exactamente 2 códigos distintos.
        agregaciones_037 = [a for a in self.resultado.agregaciones_excluidas if a.municipio == "037"]
        self.assertEqual(len(agregaciones_037), 10)
        self.assertEqual({a.codigo for a in agregaciones_037}, {"010000", "020000"})

    def test_hay_concejos_desaparecidos_y_nuevos(self):
        desaparecidos = [c for c in self.resultado.concejos if c.estado_emparejamiento == "desaparecido"]
        nuevos = [c for c in self.resultado.concejos if c.estado_emparejamiento == "nuevo"]
        # No forzamos el número exacto (11/4) porque depende del umbral de
        # similitud; comprobamos que el pipeline produce ambas categorías
        # y en un orden de magnitud razonable.
        self.assertGreater(len(desaparecidos), 0)
        self.assertGreater(len(nuevos), 0)
        self.assertLess(len(desaparecidos), 30)
        self.assertLess(len(nuevos), 30)

    def test_todos_los_concejos_tienen_al_menos_un_anio_con_dato(self):
        for c in self.resultado.concejos:
            self.assertGreater(len(c.poblacion_por_anio), 0, f"{c.entidad_id} sin ningún dato")

    def test_municipio_maestu_arraia_maeztu_nombre_final(self):
        m = next(m for m in self.resultado.municipios if m.municipio_codigo == "037")
        # el nombre final debe ser el del año más reciente (2025), no "MAESTU"
        self.assertIn("ARRAIA", m.nombre.upper())

    def test_alecha_emparejado_entre_1981_y_1991(self):
        # Alecha es concejo hijo de la agrupación Cicujano; debe encontrarse
        # como concejo real con dato en 1981 y en 1991+ (no como "nuevo"
        # ni como "desaparecido"). Se busca por entidad_id (AABB=0101,
        # estable en 1991+) porque el nombre mostrado varía entre años
        # ("ALECHA" en 1981 -> "ALETXA" en el nombre dual reciente).
        alecha = next(
            (c for c in self.resultado.concejos if c.entidad_id == "01-037-0101"),
            None,
        )
        self.assertIsNotNone(alecha)
        self.assertEqual(alecha.estado_emparejamiento, "directo")
        self.assertIn(1981, alecha.poblacion_por_anio)
        self.assertIn(1991, alecha.poblacion_por_anio)


if __name__ == "__main__":
    unittest.main()
