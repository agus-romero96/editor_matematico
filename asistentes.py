"""
Registro de asistentes guiados (`REGISTRO_ASISTENTES`) para construir expresiones y
bloques sin errores de paréntesis.

Sigue el mismo principio arquitectónico que `puente.REGISTRO` en `calculadora_accesible`:
cada asistente se declara una sola vez con su clave, nombre visible, menú, etiqueta,
atajo de teclado, campos que pide al usuario y función constructora que devuelve
`(tipo_bloque, contenido_lineal, subtipo)`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from documento import TIPO_EXPRESION, TIPO_MATRIZ, TIPO_SISTEMA
from i18n import N_


@dataclass(frozen=True)
class CampoAsistente:
    """Un campo de entrada que el diálogo del asistente pide al usuario."""
    clave: str
    etiqueta: str
    valor_defecto: str = ""
    multilinea: bool = False


@dataclass(frozen=True)
class Asistente:
    """Declaración de un asistente guiado de escritura matemática."""
    clave: str
    nombre: str
    menu: str                              # "aritmetica", "algebra", "calculo", "edo"
    etiqueta: str                          # Texto en el menú (con & para acelerador)
    atajo: Optional[str]                   # Atajo de teclado (ej. "Ctrl+Shift+F")
    campos: Tuple[CampoAsistente, ...]
    constructor: Callable[[Dict[str, str]], Tuple[str, str, str]]  # -> (tipo_bloque, contenido, subtipo)
    separador_antes: bool = False


def _parentesis_si_compuesto(txt: str) -> str:
    t = txt.strip()
    if not t:
        return "0"
    if t.startswith("(") and t.endswith(")"):
        nivel = 0
        for i, c in enumerate(t):
            if c == "(":
                nivel += 1
            elif c == ")":
                nivel -= 1
                if nivel == 0 and i < len(t) - 1:
                    break
        else:
            return t
    if any(op in t for op in ("+", "-", "/", " ", "=", "<", ">")):
        return f"({t})"
    return t


def _armar_fraccion(d: Dict[str, str]) -> Tuple[str, str, str]:
    num = _parentesis_si_compuesto(d["numerador"])
    den = _parentesis_si_compuesto(d["denominador"])
    return TIPO_EXPRESION, f"{num}/{den}", ""


def _armar_potencia(d: Dict[str, str]) -> Tuple[str, str, str]:
    base = _parentesis_si_compuesto(d["base"])
    exp = _parentesis_si_compuesto(d["exponente"])
    return TIPO_EXPRESION, f"{base}^{exp}", ""


def _armar_raiz(d: Dict[str, str]) -> Tuple[str, str, str]:
    rad = d["radicando"].strip()
    ind = d.get("indice", "2").strip() or "2"
    if ind == "2":
        return TIPO_EXPRESION, f"sqrt({rad})", ""
    return TIPO_EXPRESION, f"raiz({rad}, {ind})", ""


def _armar_ecuacion(d: Dict[str, str]) -> Tuple[str, str, str]:
    izq = d["izquierda"].strip()
    op = d.get("operador", "=").strip() or "="
    der = d["derecha"].strip()
    return TIPO_EXPRESION, f"{izq} {op} {der}", ""


def _armar_sistema(d: Dict[str, str]) -> Tuple[str, str, str]:
    lineas = [l.strip() for l in d["ecuaciones"].replace(";", "\n").splitlines() if l.strip()]
    return TIPO_SISTEMA, "\n".join(lineas), ""


def _armar_matriz(d: Dict[str, str]) -> Tuple[str, str, str]:
    return TIPO_MATRIZ, d["filas"].strip(), "matriz"


def _armar_determinante(d: Dict[str, str]) -> Tuple[str, str, str]:
    return TIPO_MATRIZ, d["filas"].strip(), "determinante"


def _armar_limite(d: Dict[str, str]) -> Tuple[str, str, str]:
    expr = d["expresion"].strip()
    var = d.get("variable", "x").strip() or "x"
    tend = d.get("tendencia", "0").strip() or "0"
    if tend.endswith("+") and tend not in ("+",):
        return TIPO_EXPRESION, f"lim({expr}, {var}, {tend[:-1]}, '+')", ""
    if tend.endswith("-") and tend not in ("-", "-oo", "-inf", "-infinito", "-infinity"):
        return TIPO_EXPRESION, f"lim({expr}, {var}, {tend[:-1]}, '-')", ""
    return TIPO_EXPRESION, f"lim({expr}, {var}, {tend})", ""


def _armar_derivada(d: Dict[str, str]) -> Tuple[str, str, str]:
    expr = d["expresion"].strip()
    var = d.get("variable", "x").strip() or "x"
    orden = d.get("orden", "1").strip() or "1"
    if orden == "1":
        return TIPO_EXPRESION, f"diff({expr}, {var})", ""
    return TIPO_EXPRESION, f"diff({expr}, {var}, {orden})", ""


def _armar_integral_indefinida(d: Dict[str, str]) -> Tuple[str, str, str]:
    expr = d["integrando"].strip()
    var = d.get("variable", "x").strip() or "x"
    return TIPO_EXPRESION, f"int({expr}, {var})", ""


def _armar_integral_definida(d: Dict[str, str]) -> Tuple[str, str, str]:
    expr = d["integrando"].strip()
    var = d.get("variable", "x").strip() or "x"
    inf = d["inferior"].strip()
    sup = d["superior"].strip()
    return TIPO_EXPRESION, f"int({expr}, {var}, {inf}, {sup})", ""


def _armar_barrow(d: Dict[str, str]) -> Tuple[str, str, str]:
    prim = d["primitiva"].strip()
    var = d.get("variable", "x").strip() or "x"
    inf = d["inferior"].strip()
    sup = d["superior"].strip()
    return TIPO_EXPRESION, f"barrow({prim}, {var}, {inf}, {sup})", ""


def _armar_sumatoria(d: Dict[str, str]) -> Tuple[str, str, str]:
    termino = d["termino"].strip()
    ind = d.get("indice", "k").strip() or "k"
    inf = d.get("inferior", "0").strip() or "0"
    sup = d.get("superior", "n").strip() or "n"
    return TIPO_EXPRESION, f"sum({termino}, {ind}, {inf}, {sup})", ""


def _armar_edo(d: Dict[str, str]) -> Tuple[str, str, str]:
    ec = d["ecuacion"].strip()
    cond = d.get("condiciones", "").strip()
    if cond:
        partes = [ec] + [c.strip() for c in cond.replace(";", ",").split(",") if c.strip()]
        return TIPO_SISTEMA, "\n".join(partes), ""
    return TIPO_EXPRESION, ec, ""


def _armar_laplace(d: Dict[str, str]) -> Tuple[str, str, str]:
    expr = d["expresion"].strip()
    t = d.get("var_origen", "t").strip() or "t"
    s = d.get("var_destino", "s").strip() or "s"
    return TIPO_EXPRESION, f"laplace({expr}, {t}, {s})", ""


def _armar_ilaplace(d: Dict[str, str]) -> Tuple[str, str, str]:
    expr = d["expresion"].strip()
    s = d.get("var_origen", "s").strip() or "s"
    t = d.get("var_destino", "t").strip() or "t"
    return TIPO_EXPRESION, f"ilaplace({expr}, {s}, {t})", ""


REGISTRO_ASISTENTES: List[Asistente] = [
    Asistente(
        clave="fraccion",
        nombre=N_("Fracción"),
        menu="aritmetica",
        etiqueta=N_("Insertar &fracción"),
        atajo="Ctrl+Shift+F",
        campos=(
            CampoAsistente("numerador", N_("Numerador:")),
            CampoAsistente("denominador", N_("Denominador:")),
        ),
        constructor=_armar_fraccion,
    ),
    Asistente(
        clave="potencia",
        nombre=N_("Potencia"),
        menu="aritmetica",
        etiqueta=N_("Insertar &potencia"),
        atajo="Ctrl+Shift+P",
        campos=(
            CampoAsistente("base", N_("Base:")),
            CampoAsistente("exponente", N_("Exponente:"), "2"),
        ),
        constructor=_armar_potencia,
    ),
    Asistente(
        clave="raiz",
        nombre=N_("Raíz"),
        menu="aritmetica",
        etiqueta=N_("Insertar &raíz"),
        atajo="Ctrl+Shift+Q",
        campos=(
            CampoAsistente("radicando", N_("Radicando (expresión dentro de la raíz):")),
            CampoAsistente("indice", N_("Índice de la raíz (2 para cuadrada, 3 para cúbica):"), "2"),
        ),
        constructor=_armar_raiz,
    ),
    Asistente(
        clave="ecuacion",
        nombre=N_("Ecuación o inecuación"),
        menu="algebra",
        etiqueta=N_("Insertar &ecuación o inecuación"),
        atajo="Ctrl+R",
        campos=(
            CampoAsistente("izquierda", N_("Lado izquierdo:")),
            CampoAsistente("operador", N_("Signo (=, <, <=, >, >=, !=):"), "="),
            CampoAsistente("derecha", N_("Lado derecho:")),
        ),
        constructor=_armar_ecuacion,
    ),
    Asistente(
        clave="sistema",
        nombre=N_("Sistema de ecuaciones"),
        menu="algebra",
        etiqueta=N_("Insertar &sistema de ecuaciones"),
        atajo="Ctrl+G",
        campos=(
            CampoAsistente("ecuaciones", N_("Ecuaciones (una por línea o separadas por punto y coma):"), multilinea=True),
        ),
        constructor=_armar_sistema,
    ),
    Asistente(
        clave="matriz",
        nombre=N_("Matriz"),
        menu="algebra",
        etiqueta=N_("Insertar &matriz"),
        atajo="Ctrl+M",
        separador_antes=True,
        campos=(
            CampoAsistente("filas", N_("Filas de la matriz (una fila por línea, elementos separados por espacios):"), multilinea=True),
        ),
        constructor=_armar_matriz,
    ),
    Asistente(
        clave="determinante",
        nombre=N_("Determinante"),
        menu="algebra",
        etiqueta=N_("Insertar &determinante"),
        atajo="Ctrl+K",
        campos=(
            CampoAsistente("filas", N_("Filas del determinante (una fila por línea, elementos separados por espacios):"), multilinea=True),
        ),
        constructor=_armar_determinante,
    ),
    Asistente(
        clave="limite",
        nombre=N_("Límite"),
        menu="calculo",
        etiqueta=N_("Insertar &límite"),
        atajo="Ctrl+L",
        campos=(
            CampoAsistente("expresion", N_("Expresión del límite:")),
            CampoAsistente("variable", N_("Variable:"), "x"),
            CampoAsistente("tendencia", N_("Tendencia (ej: 0, oo, -oo, 0+, 0-):"), "0"),
        ),
        constructor=_armar_limite,
    ),
    Asistente(
        clave="derivada",
        nombre=N_("Derivada"),
        menu="calculo",
        etiqueta=N_("Insertar &derivada"),
        atajo="Ctrl+D",
        campos=(
            CampoAsistente("expresion", N_("Función a derivar:")),
            CampoAsistente("variable", N_("Variable de derivación:"), "x"),
            CampoAsistente("orden", N_("Orden de la derivada (1, 2, 3...):"), "1"),
        ),
        constructor=_armar_derivada,
    ),
    Asistente(
        clave="integral",
        nombre=N_("Integral indefinida"),
        menu="calculo",
        etiqueta=N_("Insertar &integral indefinida"),
        atajo="Ctrl+I",
        separador_antes=True,
        campos=(
            CampoAsistente("integrando", N_("Integrando:")),
            CampoAsistente("variable", N_("Variable de integración:"), "x"),
        ),
        constructor=_armar_integral_indefinida,
    ),
    Asistente(
        clave="integral_definida",
        nombre=N_("Integral definida"),
        menu="calculo",
        etiqueta=N_("Insertar integral de&finida"),
        atajo="Ctrl+Shift+I",
        campos=(
            CampoAsistente("integrando", N_("Integrando:")),
            CampoAsistente("variable", N_("Variable de integración:"), "x"),
            CampoAsistente("inferior", N_("Límite inferior:"), "0"),
            CampoAsistente("superior", N_("Límite superior:"), "1"),
        ),
        constructor=_armar_integral_definida,
    ),
    Asistente(
        clave="barrow",
        nombre=N_("Evaluación de Barrow"),
        menu="calculo",
        etiqueta=N_("Insertar evaluación de &Barrow [F(x)]_a^b"),
        atajo="Ctrl+Shift+B",
        campos=(
            CampoAsistente("primitiva", N_("Primitiva F(x):")),
            CampoAsistente("variable", N_("Variable:"), "x"),
            CampoAsistente("inferior", N_("Límite inferior a:"), "0"),
            CampoAsistente("superior", N_("Límite superior b:"), "1"),
        ),
        constructor=_armar_barrow,
    ),
    Asistente(
        clave="sumatoria",
        nombre=N_("Sumatoria / Serie de Taylor"),
        menu="calculo",
        etiqueta=N_("Insertar &sumatoria"),
        atajo="Ctrl+Shift+T",
        separador_antes=True,
        campos=(
            CampoAsistente("termino", N_("Término general:")),
            CampoAsistente("indice", N_("Índice de suma:"), "k"),
            CampoAsistente("inferior", N_("Valor inicial:"), "0"),
            CampoAsistente("superior", N_("Valor final (ej: n, oo, 5):"), "n"),
        ),
        constructor=_armar_sumatoria,
    ),
    Asistente(
        clave="edo",
        nombre=N_("Ecuación diferencial (EDO)"),
        menu="edo",
        etiqueta=N_("Insertar &ecuación diferencial o PVI"),
        atajo="Ctrl+Shift+R",
        campos=(
            CampoAsistente("ecuacion", N_("Ecuación diferencial (ej: y' + 2*x*y = 0, y'' + y = sin(x)):")),
            CampoAsistente("condiciones", N_("Condiciones iniciales opcionales (ej: y(0) = 1, y'(0) = 0):"), ""),
        ),
        constructor=_armar_edo,
    ),
    Asistente(
        clave="laplace",
        nombre=N_("Transformada de Laplace"),
        menu="edo",
        etiqueta=N_("Insertar transformada de &Laplace"),
        atajo="Ctrl+Shift+L",
        separador_antes=True,
        campos=(
            CampoAsistente("expresion", N_("Función f(t):")),
            CampoAsistente("var_origen", N_("Variable original:"), "t"),
            CampoAsistente("var_destino", N_("Variable transformada:"), "s"),
        ),
        constructor=_armar_laplace,
    ),
    Asistente(
        clave="ilaplace",
        nombre=N_("Transformada inversa de Laplace"),
        menu="edo",
        etiqueta=N_("Insertar transformada &inversa de Laplace"),
        atajo="Ctrl+Shift+U",
        campos=(
            CampoAsistente("expresion", N_("Función F(s):")),
            CampoAsistente("var_origen", N_("Variable transformada:"), "s"),
            CampoAsistente("var_destino", N_("Variable de tiempo:"), "t"),
        ),
        constructor=_armar_ilaplace,
    ),
]

ASISTENTE_POR_CLAVE: Dict[str, Asistente] = {a.clave: a for a in REGISTRO_ASISTENTES}
