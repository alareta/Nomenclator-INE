"""Utilidades de formateo de texto compartidas por varios generadores de
salida (Excel, CSV de espera, .tab de Commons).

Separado de salida_wikitexto.py a propósito: el wikitexto queda
desconectado del flujo activo de la herramienta (ver decisión en
proyecto_utilidad_web_nomenclator.md), pero `capitalizar_nombre_display`
la siguen necesitando el resto de generadores y no debían depender de
un módulo que ya no se ejecuta desde la webapp.
"""

from __future__ import annotations

PREPOSICIONES_MINUSCULA = {"de", "del", "la", "las", "los", "el", "y"}


def capitalizar_nombre_display(nombre: str) -> str:
    """Capitalización mecánica simple: mayúscula inicial por palabra
    (y por segmento separado por guión), preposiciones comunes en
    minúscula salvo al inicio. Los nombres duales ('X/Y') se capitalizan
    cada parte por separado, conservando la barra.

    No corrige topónimos (p.ej. no convierte 'Gamboa' en 'Ganboa'); eso
    queda a revisión manual del usuario (decisión tomada para el MVP).
    """
    partes_barra = nombre.split("/")
    resultado_partes = []
    for parte in partes_barra:
        palabras = parte.strip().split(" ")
        out_palabras = []
        for i, palabra in enumerate(palabras):
            segmentos = palabra.split("-")
            segmentos_cap = []
            for j, seg in enumerate(segmentos):
                es_inicio_absoluto = i == 0 and j == 0
                if not es_inicio_absoluto and seg.lower() in PREPOSICIONES_MINUSCULA:
                    segmentos_cap.append(seg.lower())
                else:
                    segmentos_cap.append(seg.capitalize())
            out_palabras.append("-".join(segmentos_cap))
        resultado_partes.append(" ".join(out_palabras))
    return "/".join(resultado_partes)
