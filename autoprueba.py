"""
Autoprueba de humo para verificar que todos los módulos del Editor Matemático Accesible
funcionan correctamente en conjunto.
"""
from __future__ import annotations

from typing import Callable, List, Tuple

import asistentes
from documento import DocumentoMatematico
import exportar
import i18n
import verbalizador
import verificador


def ejecutar_autoprueba() -> Tuple[bool, List[str]]:
    informe: List[str] = []
    fallos = 0

    casos: List[Tuple[str, Callable[[], bool]]] = [
        ("Aritmética y fracción verbalizada", lambda: "numerador" in verbalizador.verbalizar("(x^2 + 1)/(x - 3)")),
        ("Raíz enésima", lambda: "cúbica" in verbalizador.verbalizar("raiz(x + 1, 3)")),
        ("Ecuación e inecuación", lambda: "menor o igual" in verbalizador.verbalizar("x^2 - 4 <= 0")),
        ("Límite lateral", lambda: "derecha" in verbalizador.verbalizar("lim(1/x, x, 0+)")),
        ("Derivada de orden N", lambda: "orden 3" in verbalizador.verbalizar("diff(x^5, x, 3)")),
        ("Integral definida", lambda: "integral definida" in verbalizador.verbalizar("int(x^2, x, 0, 1)")),
        ("Evaluación de Barrow", lambda: "evaluada" in verbalizador.verbalizar("barrow(x^3/3, x, 0, 1)")),
        ("Sumatoria / Taylor", lambda: "sumatoria" in verbalizador.verbalizar("sum(x^k/factorial(k), k, 0, n)")),
        ("Ecuación diferencial", lambda: "prima" in verbalizador.verbalizar("y' + 2*x*y = 0")),
        ("Transformada de Laplace", lambda: "Laplace" in verbalizador.verbalizar("laplace(exp(2*t), t, s)")),
        ("Matriz y determinante", lambda: "Determinante" in verbalizador.verbalizar("det([[1, 2], [3, 4]])")),
        ("Inspector estructural", lambda: len(verbalizador.inspeccionar("(x + 1)/(x - 1)").hijos) == 2),
        ("Registro de asistentes", lambda: len(asistentes.REGISTRO_ASISTENTES) == 16),
        ("Verificador de pasos algebraicos", _probar_verificador),
        ("Exportación HTML+MathML y Word (.docx)", _probar_exportacion),
        ("Traducción al inglés", _probar_ingles),
    ]

    for nombre, fn in casos:
        try:
            ok = bool(fn())
        except Exception as e:
            ok = False
            informe.append(f"FALLO [{nombre}]: {e}")
        else:
            informe.append(f"{'OK' if ok else 'FALLO'} [{nombre}]")
        if not ok:
            fallos += 1

    return fallos == 0, informe


def _probar_verificador() -> bool:
    doc = DocumentoMatematico("Prueba")
    doc.agregar_expresion("2*(x + 1) = 10")
    doc.agregar_expresion("2*x + 2 = 10")
    doc.agregar_expresion("x = 4")
    res = verificador.verificar_documento_completo(doc)
    return all(r.es_valido for r in res)


def _probar_exportacion() -> bool:
    doc = DocumentoMatematico("Prueba Exportación")
    doc.agregar_texto("Enunciado")
    doc.agregar_expresion("int(x^2, x, 0, 1) = 1/3")
    html_out = exportar.a_html(doc)
    docx_out = exportar.a_docx_bytes(doc)
    return "<math" in html_out and len(docx_out) > 500


def _probar_ingles() -> bool:
    anterior = i18n.idioma_actual()
    try:
        i18n.establecer_idioma("en")
        txt = verbalizador.verbalizar("int(x^2, x, 0, 1)")
        return "definite integral" in txt.lower()
    finally:
        i18n.establecer_idioma(anterior)
