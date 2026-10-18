"""
Verbalizador matemático e Inspector Estructural para lectores de pantalla (NVDA / JAWS).

Resuelve el problema central de los editores visuales (como Word o EDICO), donde el
usuario ciego pierde el contexto de si el cursor está dentro de un numerador, un
denominador, una raíz, un exponente o los límites de una integral:

1. `verbalizar(entrada, modo)`: convierte cualquier expresión, ecuación, inecuación,
   límite, derivada, integral, sumatoria, ecuación diferencial, transformada de Laplace,
   matriz o conjunto en una frase clara en español o inglés, sin símbolos mudos:
   - Modo `"detallada"` (por defecto): anuncia inicio y fin de fracciones compuestas,
     raíces, potencias y argumentos para eliminar toda ambigüedad estructural.
   - Modo `"breve"`: lectura fluida y concisa para repasar un desarrollo rápido.

2. `inspeccionar(entrada) -> NodoEstructura`: descompone cualquier fórmula o bloque en
   un árbol navegable con las flechas del teclado, donde cada nodo indica su papel
   estructural ("Numerador", "Denominador", "Límite inferior", "Integrando",
   "Fila 2, Columna 1", etc.), su expresión lineal y su lectura verbalizada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

import sympy
from sympy.core.function import AppliedUndef
from sympy.core.relational import Relational

from configuracion import LECTURA_BREVE, LECTURA_DETALLADA
from i18n import N_, tr
from parser_matematico import (
    DeterminanteSimbolico,
    EvaluacionBarrow,
    ParserMatematico,
    TransformadaInversaLaplace,
    TransformadaLaplace,
)

_PARSER = ParserMatematico()


@dataclass(frozen=True)
class NodoEstructura:
    """
    Un nodo del árbol estructural de una expresión matemática para el Inspector (F2).
    """
    etiqueta: str                              # Papel estructural ("Numerador", "Exponente", "Lado izquierdo"...)
    expresion: str                             # Representación lineal limpia (con ^ en vez de **)
    lectura: str                               # Lectura en voz natural para el lector de pantalla
    hijos: Tuple["NodoEstructura", ...] = field(default_factory=tuple)

    def texto_nodo(self) -> str:
        """Texto que anuncia el lector de pantalla al situarse en este nodo del árbol."""
        return f"{self.etiqueta}: {self.lectura} ({self.expresion})"

    def a_lineas(self, nivel: int = 0) -> List[str]:
        """Vuelca el árbol completo como texto indentado para copia o revisión lineal."""
        prefijo = "  " * nivel + ("- " if nivel > 0 else "")
        lineas = [f"{prefijo}{self.texto_nodo()}"]
        for hijo in self.hijos:
            lineas.extend(hijo.a_lineas(nivel + 1))
        return lineas


def texto_lineal(expr: Any) -> str:
    """Formatea un objeto SymPy en la notación lineal legible del editor (`^` en lugar de `**`)."""
    if isinstance(expr, str):
        return expr.strip()
    if isinstance(expr, sympy.MatrixBase):
        filas = ["[" + ", ".join(texto_lineal(e) for e in fila) + "]" for fila in expr.tolist()]
        return "[" + ", ".join(filas) + "]"
    if isinstance(expr, DeterminanteSimbolico):
        return f"det({texto_lineal(expr.args[0])})"
    if isinstance(expr, EvaluacionBarrow):
        f, x, a, b = expr.args
        return f"barrow({texto_lineal(f)}, {texto_lineal(x)}, {texto_lineal(a)}, {texto_lineal(b)})"
    if isinstance(expr, TransformadaLaplace):
        f, t, s = expr.args
        return f"laplace({texto_lineal(f)}, {texto_lineal(t)}, {texto_lineal(s)})"
    if isinstance(expr, TransformadaInversaLaplace):
        F, s, t = expr.args
        return f"ilaplace({texto_lineal(F)}, {texto_lineal(s)}, {texto_lineal(t)})"
    if isinstance(expr, sympy.Eq):
        return f"{texto_lineal(expr.lhs)} = {texto_lineal(expr.rhs)}"
    if isinstance(expr, sympy.Le):
        return f"{texto_lineal(expr.lhs)} <= {texto_lineal(expr.rhs)}"
    if isinstance(expr, sympy.Ge):
        return f"{texto_lineal(expr.lhs)} >= {texto_lineal(expr.rhs)}"
    if isinstance(expr, sympy.Lt):
        return f"{texto_lineal(expr.lhs)} < {texto_lineal(expr.rhs)}"
    if isinstance(expr, sympy.Gt):
        return f"{texto_lineal(expr.lhs)} > {texto_lineal(expr.rhs)}"
    if isinstance(expr, sympy.Ne):
        return f"{texto_lineal(expr.lhs)} != {texto_lineal(expr.rhs)}"
    return str(expr).replace("**", "^")


def _es_atómica(expr: Any) -> bool:
    if isinstance(expr, (sympy.Symbol, sympy.Integer)):
        return expr >= 0 if isinstance(expr, sympy.Integer) else True
    return expr in (sympy.pi, sympy.E, sympy.oo)


def _es_compuesta(expr: Any) -> bool:
    if isinstance(expr, (sympy.Add, Relational)):
        return True
    if isinstance(expr, sympy.Rational) and expr.q != 1:
        return True
    if isinstance(expr, sympy.Mul):
        _, den = _separar_fraccion_sin_evaluar(expr)
        return den != 1
    return False


def _separar_fraccion_sin_evaluar(expr: Any):
    if isinstance(expr, sympy.Rational):
        return (sympy.Integer(expr.p), sympy.Integer(expr.q)) if expr.q != 1 else (expr, sympy.Integer(1))
    if isinstance(expr, sympy.Pow) and expr.exp == -1:
        return sympy.Integer(1), expr.base
    if isinstance(expr, sympy.Pow) and isinstance(expr.exp, sympy.Number) and expr.exp < 0:
        return sympy.Integer(1), sympy.Pow(arg_base := expr.base, -expr.exp, evaluate=False)
    if not isinstance(expr, sympy.Mul):
        return expr, sympy.Integer(1)

    numeradores = []
    denominadores = []
    for arg in expr.args:
        if isinstance(arg, sympy.Rational) and arg.q != 1:
            if arg.p != 1:
                numeradores.append(sympy.Integer(arg.p))
            denominadores.append(sympy.Integer(arg.q))
        elif isinstance(arg, sympy.Pow) and isinstance(arg.exp, sympy.Number) and arg.exp < 0:
            denominadores.append(
                arg.base if arg.exp == -1 else sympy.Pow(arg.base, -arg.exp, evaluate=False)
            )
        else:
            numeradores.append(arg)

    if not denominadores:
        return expr, sympy.Integer(1)
    num = sympy.Mul(*numeradores, evaluate=False) if numeradores else sympy.Integer(1)
    den = sympy.Mul(*denominadores, evaluate=False) if len(denominadores) > 1 else denominadores[0]
    return num, den


def _es_raiz(expr: Any) -> Optional[Tuple[Any, Any]]:
    if isinstance(expr, sympy.Pow):
        base, exp = expr.args
        if exp == sympy.Rational(1, 2):
            return base, sympy.Integer(2)
        if isinstance(exp, sympy.Rational) and exp.p == 1 and exp.q > 2:
            return base, sympy.Integer(exp.q)
        if isinstance(exp, sympy.Pow) and exp.exp == -1:
            return base, exp.base
    return None


NOMBRES_FUNCIONES = {
    sympy.sin: N_("seno"),
    sympy.cos: N_("coseno"),
    sympy.tan: N_("tangente"),
    sympy.cot: N_("cotangente"),
    sympy.sec: N_("secante"),
    sympy.csc: N_("cosecante"),
    sympy.asin: N_("arcoseno"),
    sympy.acos: N_("arcocoseno"),
    sympy.atan: N_("arcotangente"),
    sympy.acot: N_("arcocotangente"),
    sympy.sinh: N_("seno hiperbólico"),
    sympy.cosh: N_("coseno hiperbólico"),
    sympy.tanh: N_("tangente hiperbólica"),
    sympy.coth: N_("cotangente hiperbólica"),
    sympy.asinh: N_("arcoseno hiperbólico"),
    sympy.acosh: N_("arcocoseno hiperbólico"),
    sympy.atanh: N_("arcotangente hiperbólica"),
}


def verbalizar(entrada: Any, modo: str = LECTURA_DETALLADA) -> str:
    if isinstance(entrada, str):
        texto = entrada.strip()
        if not texto:
            return tr("Línea vacía")
        try:
            obj = _PARSER.parsear(texto)
        except Exception as e:
            return tr("Expresión sin interpretar ({texto}): {error}", texto=texto, error=str(e))
        return verbalizar_objeto(obj, modo=modo)
    return verbalizar_objeto(entrada, modo=modo)


def verbalizar_sistema(ecuaciones: Sequence[Any], modo: str = LECTURA_DETALLADA) -> str:
    if not ecuaciones:
        return tr("Sistema vacío")
    partes = []
    for idx, ec in enumerate(ecuaciones, 1):
        lectura_ec = verbalizar(ec, modo=modo)
        partes.append(tr("Ecuación {n}: {lectura}", n=idx, lectura=lectura_ec))
    encabezado = tr("Sistema de {total} ecuaciones", total=len(ecuaciones))
    return f"{encabezado}. " + "; ".join(partes)


def verbalizar_objeto(expr: Any, modo: str = LECTURA_DETALLADA) -> str:
    detallado = modo != LECTURA_BREVE

    if expr is None:
        return tr("vacío")

    if isinstance(expr, DeterminanteSimbolico):
        mat = expr.args[0]
        if isinstance(mat, sympy.MatrixBase):
            return tr("Determinante de {filas} por {cols}: {contenido}",
                      filas=mat.rows, cols=mat.cols,
                      contenido=_verbalizar_filas_matriz(mat, modo))
        return tr("determinante de {arg}", arg=verbalizar_objeto(mat, modo))

    if isinstance(expr, sympy.MatrixBase):
        return tr("Matriz de {filas} por {cols}: {contenido}",
                  filas=expr.rows, cols=expr.cols,
                  contenido=_verbalizar_filas_matriz(expr, modo))

    if isinstance(expr, Relational):
        nombres_rel = {
            sympy.Eq: tr("igual a"),
            sympy.Le: tr("menor o igual que"),
            sympy.Ge: tr("mayor o igual que"),
            sympy.Lt: tr("menor que"),
            sympy.Gt: tr("mayor que"),
            sympy.Ne: tr("distinto de"),
        }
        op_txt = nombres_rel.get(type(expr), tr("relacionado con"))
        izq = verbalizar_objeto(expr.lhs, modo)
        der = verbalizar_objeto(expr.rhs, modo)
        return f"{izq} {op_txt} {der}"

    if expr is sympy.oo:
        return tr("infinito")
    if expr == -sympy.oo:
        return tr("menos infinito")
    if expr is sympy.pi:
        return "pi"
    if expr is sympy.E:
        return "e"
    if expr is sympy.EmptySet:
        return tr("conjunto vacío")
    if expr is sympy.S.Reals:
        return tr("conjunto de los números reales")

    if isinstance(expr, sympy.Symbol):
        return expr.name

    if isinstance(expr, sympy.Integer):
        val = int(expr)
        return tr("menos {n}", n=abs(val)) if val < 0 else str(val)

    if isinstance(expr, sympy.Float):
        txt_num = str(expr).rstrip("0").rstrip(".") if "." in str(expr) else str(expr)
        return tr("menos {n}", n=txt_num[1:]) if txt_num.startswith("-") else txt_num

    if isinstance(expr, sympy.Interval):
        tipo_izq = tr("abierto en") if expr.left_open else tr("cerrado en")
        tipo_der = tr("abierto en") if expr.right_open else tr("cerrado en")
        a = verbalizar_objeto(expr.start, modo)
        b = verbalizar_objeto(expr.end, modo)
        if detallado:
            return tr("intervalo {tipo_izq} {a} hasta {b} ({tipo_der} {b})",
                      tipo_izq=tipo_izq, a=a, b=b, tipo_der=tipo_der)
        return tr("intervalo de {a} a {b}", a=a, b=b)

    if isinstance(expr, sympy.Union):
        partes = [verbalizar_objeto(arg, modo) for arg in expr.args]
        return f" {tr('unión')} ".join(partes)

    if isinstance(expr, sympy.FiniteSet):
        elementos = ", ".join(verbalizar_objeto(arg, modo) for arg in expr.args)
        return tr("conjunto con {elementos}", elementos=elementos)

    if isinstance(expr, sympy.Limit):
        fn, var, punto = expr.args[:3]
        dir_ = str(expr.args[3]) if len(expr.args) > 3 else "+-"
        lectura_fn = verbalizar_objeto(fn, modo)
        lectura_var = verbalizar_objeto(var, modo)
        lectura_pto = verbalizar_objeto(punto, modo)
        if dir_ == "+":
            lat = " " + tr("por la derecha")
        elif dir_ == "-":
            lat = " " + tr("por la izquierda")
        else:
            lat = ""
        if detallado:
            return tr("límite cuando {var} tiende a {punto}{lateral} de {funcion}",
                      var=lectura_var, punto=lectura_pto, lateral=lat, funcion=lectura_fn)
        return tr("límite con {var} hacia {punto}{lateral} de {funcion}",
                  var=lectura_var, punto=lectura_pto, lateral=lat, funcion=lectura_fn)

    if isinstance(expr, sympy.Derivative):
        fn = expr.expr
        pares = expr.variable_count
        var, orden = pares[0] if pares else (sympy.Symbol("x"), 1)
        orden_int = int(orden)
        if isinstance(fn, AppliedUndef):
            nombre_fn = fn.func.__name__
            if orden_int == 1:
                return tr("{y} prima", y=nombre_fn)
            if orden_int == 2:
                return tr("{y} segunda", y=nombre_fn)
            if orden_int == 3:
                return tr("{y} tercera", y=nombre_fn)
            return tr("derivada de orden {n} de {y}", n=orden_int, y=nombre_fn)

        lectura_fn = verbalizar_objeto(fn, modo)
        lectura_var = verbalizar_objeto(var, modo)
        if orden_int == 1:
            return tr("derivada respecto a {var} de {funcion}", var=lectura_var, funcion=lectura_fn)
        return tr("derivada de orden {n} respecto a {var} de {funcion}",
                  n=orden_int, var=lectura_var, funcion=lectura_fn)

    if isinstance(expr, sympy.Integral):
        fn = expr.function
        limites = expr.limits[0]
        lectura_fn = verbalizar_objeto(fn, modo)
        var = verbalizar_objeto(limites[0], modo)
        if len(limites) == 3:
            inf_txt = verbalizar_objeto(limites[1], modo)
            sup_txt = verbalizar_objeto(limites[2], modo)
            if detallado:
                return tr("integral definida desde {inf} hasta {sup} de {funcion}, diferencial de {var}",
                          inf=inf_txt, sup=sup_txt, funcion=lectura_fn, var=var)
            return tr("integral de {inf} a {sup} de {funcion} d {var}",
                      inf=inf_txt, sup=sup_txt, funcion=lectura_fn, var=var)
        if detallado:
            return tr("integral indefinida de {funcion}, diferencial de {var}", funcion=lectura_fn, var=var)
        return tr("integral de {funcion} d {var}", funcion=lectura_fn, var=var)

    if isinstance(expr, EvaluacionBarrow):
        f, x, a, b = expr.args
        return tr("{funcion} evaluada en {var} desde {inf} hasta {sup}",
                  funcion=verbalizar_objeto(f, modo),
                  var=verbalizar_objeto(x, modo),
                  inf=verbalizar_objeto(a, modo),
                  sup=verbalizar_objeto(b, modo))

    if isinstance(expr, sympy.Sum):
        fn = expr.function
        var, inf, sup = expr.limits[0]
        return tr("sumatoria desde {var} igual a {inf} hasta {sup} de {funcion}",
                  var=verbalizar_objeto(var, modo),
                  inf=verbalizar_objeto(inf, modo),
                  sup=verbalizar_objeto(sup, modo),
                  funcion=verbalizar_objeto(fn, modo))

    if isinstance(expr, sympy.Product):
        fn = expr.function
        var, inf, sup = expr.limits[0]
        return tr("productoria desde {var} igual a {inf} hasta {sup} de {funcion}",
                  var=verbalizar_objeto(var, modo),
                  inf=verbalizar_objeto(inf, modo),
                  sup=verbalizar_objeto(sup, modo),
                  funcion=verbalizar_objeto(fn, modo))

    if isinstance(expr, TransformadaLaplace):
        f, t, s = expr.args
        return tr("transformada de Laplace de {funcion} de {t} a {s}",
                  funcion=verbalizar_objeto(f, modo),
                  t=verbalizar_objeto(t, modo),
                  s=verbalizar_objeto(s, modo))

    if isinstance(expr, TransformadaInversaLaplace):
        F, s, t = expr.args
        return tr("transformada inversa de Laplace de {funcion} de {s} a {t}",
                  funcion=verbalizar_objeto(F, modo),
                  s=verbalizar_objeto(s, modo),
                  t=verbalizar_objeto(t, modo))

    if isinstance(expr, sympy.Heaviside):
        return tr("escalón unitario de {arg}", arg=verbalizar_objeto(expr.args[0], modo))

    if isinstance(expr, sympy.DiracDelta):
        return tr("delta de Dirac de {arg}", arg=verbalizar_objeto(expr.args[0], modo))

    if isinstance(expr, sympy.Abs):
        arg = verbalizar_objeto(expr.args[0], modo)
        if detallado and _es_compuesta(expr.args[0]):
            return tr("valor absoluto de {arg}, fin de valor absoluto", arg=arg)
        return tr("valor absoluto de {arg}", arg=arg)

    if isinstance(expr, sympy.factorial):
        return tr("{arg} factorial", arg=verbalizar_objeto(expr.args[0], modo))

    datos_raiz = _es_raiz(expr)
    if datos_raiz is not None:
        radicando, indice = datos_raiz
        lectura_rad = verbalizar_objeto(radicando, modo)
        if indice == 2:
            prefijo = tr("raíz cuadrada de {rad}", rad=lectura_rad)
        elif indice == 3:
            prefijo = tr("raíz cúbica de {rad}", rad=lectura_rad)
        else:
            prefijo = tr("raíz de índice {n} de {rad}", n=verbalizar_objeto(indice, modo), rad=lectura_rad)
        if detallado and _es_compuesta(radicando):
            return f"{prefijo}, {tr('fin de raíz')}"
        return prefijo

    num, den = _separar_fraccion_sin_evaluar(expr)
    if den != 1:
        lectura_num = verbalizar_objeto(num, modo)
        lectura_den = verbalizar_objeto(den, modo)
        if detallado and (_es_compuesta(num) or _es_compuesta(den)):
            return tr("fracción: numerador {num}, entre denominador {den}, fin de fracción",
                      num=lectura_num, den=lectura_den)
        return tr("{num} sobre {den}", num=lectura_num, den=lectura_den)

    if isinstance(expr, sympy.Pow):
        base, exp = expr.args
        lectura_base = verbalizar_objeto(base, modo)
        if isinstance(base, (sympy.Add, sympy.Mul, Relational)):
            lectura_base = tr("entre paréntesis {base} fin de paréntesis", base=lectura_base) if detallado else f"({lectura_base})"
        if exp == 2:
            return tr("{base} al cuadrado", base=lectura_base)
        if exp == 3:
            return tr("{base} al cubo", base=lectura_base)
        lectura_exp = verbalizar_objeto(exp, modo)
        if detallado and _es_compuesta(exp):
            return tr("{base} elevado a {exp}, fin de exponente", base=lectura_base, exp=lectura_exp)
        return tr("{base} elevado a {exp}", base=lectura_base, exp=lectura_exp)

    if isinstance(expr, sympy.exp):
        arg = expr.args[0]
        lectura_arg = verbalizar_objeto(arg, modo)
        if detallado and _es_compuesta(arg):
            return tr("e elevado a {exp}, fin de exponente", exp=lectura_arg)
        return tr("e elevado a {exp}", exp=lectura_arg)

    if isinstance(expr, sympy.log):
        if len(expr.args) == 2:
            arg, base = expr.args
            return tr("logaritmo en base {base} de {arg}",
                      base=verbalizar_objeto(base, modo),
                      arg=verbalizar_objeto(arg, modo))
        return tr("logaritmo natural de {arg}", arg=verbalizar_objeto(expr.args[0], modo))

    for clase_fn, nombre_tr in NOMBRES_FUNCIONES.items():
        if isinstance(expr, clase_fn):
            return tr("{funcion} de {arg}", funcion=tr(nombre_tr), arg=verbalizar_objeto(expr.args[0], modo))

    if isinstance(expr, AppliedUndef):
        args_txt = ", ".join(verbalizar_objeto(a, modo) for a in expr.args)
        return tr("{funcion} de {args}", funcion=expr.func.__name__, args=args_txt)

    if isinstance(expr, sympy.Mul):
        factores = list(expr.args)
        if factores and factores[0] == -1:
            resto = sympy.Mul(*factores[1:], evaluate=False) if len(factores) > 2 else factores[1]
            return tr("menos {expr}", expr=verbalizar_objeto(resto, modo))
        if factores and isinstance(factores[0], sympy.Integer) and factores[0] < 0:
            positivo = sympy.Mul(abs(int(factores[0])), *factores[1:], evaluate=False)
            return tr("menos {expr}", expr=verbalizar_objeto(positivo, modo))

        partes = []
        for f in factores:
            txt_f = verbalizar_objeto(f, modo)
            if isinstance(f, sympy.Add):
                txt_f = tr("entre paréntesis {expr} fin de paréntesis", expr=txt_f) if detallado else f"({txt_f})"
            partes.append(txt_f)
        return f" {tr('por')} ".join(partes)

    if isinstance(expr, sympy.Add):
        partes_suma = []
        for idx, termino in enumerate(expr.args):
            negativo = _extraer_negativo(termino)
            if idx == 0:
                partes_suma.append(verbalizar_objeto(termino, modo))
            elif negativo is not None:
                partes_suma.append(f"{tr('menos')} {verbalizar_objeto(negativo, modo)}")
            else:
                partes_suma.append(f"{tr('más')} {verbalizar_objeto(termino, modo)}")
        return " ".join(partes_suma)

    return texto_lineal(expr)


def _extraer_negativo(termino: Any) -> Optional[Any]:
    if isinstance(termino, (sympy.Integer, sympy.Float)) and termino < 0:
        return -termino
    if isinstance(termino, sympy.Rational) and termino < 0:
        return -termino
    if isinstance(termino, sympy.Mul) and termino.args:
        primero = termino.args[0]
        if primero == -1:
            return sympy.Mul(*termino.args[1:], evaluate=False) if len(termino.args) > 2 else termino.args[1]
        if isinstance(primero, (sympy.Integer, sympy.Rational)) and primero < 0:
            return sympy.Mul(-primero, *termino.args[1:], evaluate=False)
    return None


def _verbalizar_filas_matriz(mat: sympy.MatrixBase, modo: str) -> str:
    filas_txt = []
    for i in range(mat.rows):
        celdas = ", ".join(verbalizar_objeto(mat[i, j], modo) for j in range(mat.cols))
        filas_txt.append(tr("Fila {i}: {celdas}", i=i + 1, celdas=celdas))
    return "; ".join(filas_txt)


def inspeccionar(entrada: Any, etiqueta_raiz: Optional[str] = None) -> NodoEstructura:
    if isinstance(entrada, str):
        obj = _PARSER.parsear(entrada.strip())
    else:
        obj = entrada
    return _construir_nodo(obj, etiqueta_raiz or _etiqueta_por_tipo(obj))


def _etiqueta_por_tipo(expr: Any) -> str:
    if isinstance(expr, sympy.Eq):
        return tr("Ecuación")
    if isinstance(expr, Relational):
        return tr("Inecuación")
    if isinstance(expr, DeterminanteSimbolico):
        return tr("Determinante")
    if isinstance(expr, sympy.MatrixBase):
        return tr("Matriz ({filas}x{cols})", filas=expr.rows, cols=expr.cols)
    if isinstance(expr, sympy.Limit):
        return tr("Límite")
    if isinstance(expr, sympy.Derivative):
        return tr("Derivada")
    if isinstance(expr, sympy.Integral):
        return tr("Integral definida") if len(expr.limits[0]) == 3 else tr("Integral indefinida")
    if isinstance(expr, sympy.Sum):
        return tr("Sumatoria")
    if isinstance(expr, sympy.Product):
        return tr("Productoria")
    if isinstance(expr, TransformadaLaplace):
        return tr("Transformada de Laplace")
    if isinstance(expr, TransformadaInversaLaplace):
        return tr("Transformada inversa de Laplace")
    if _es_raiz(expr) is not None:
        return tr("Raíz")
    _, den = _separar_fraccion_sin_evaluar(expr)
    if den != 1:
        return tr("Fracción")
    if isinstance(expr, sympy.Pow):
        return tr("Potencia")
    if isinstance(expr, sympy.Add):
        return tr("Suma algebraica")
    if isinstance(expr, sympy.Mul):
        return tr("Producto")
    return tr("Expresión")


def _construir_nodo(expr: Any, etiqueta: str) -> NodoEstructura:
    lin = texto_lineal(expr)
    lec = verbalizar_objeto(expr, modo=LECTURA_DETALLADA)

    if isinstance(expr, Relational):
        hijos = (
            _construir_nodo(expr.lhs, tr("Lado izquierdo")),
            _construir_nodo(expr.rhs, tr("Lado derecho")),
        )
        return NodoEstructura(etiqueta, lin, lec, hijos)

    if isinstance(expr, DeterminanteSimbolico) and isinstance(expr.args[0], sympy.MatrixBase):
        return _construir_nodo_matriz(expr.args[0], etiqueta, lin, lec)

    if isinstance(expr, sympy.MatrixBase):
        return _construir_nodo_matriz(expr, etiqueta, lin, lec)

    if isinstance(expr, sympy.Limit):
        fn, var, punto = expr.args[:3]
        hijos_lim = [
            _construir_nodo(var, tr("Variable del límite")),
            _construir_nodo(punto, tr("Tendencia")),
            _construir_nodo(fn, tr("Expresión del límite")),
        ]
        return NodoEstructura(etiqueta, lin, lec, tuple(hijos_lim))

    if isinstance(expr, sympy.Derivative):
        fn = expr.expr
        var, orden = expr.variable_count[0] if expr.variable_count else (sympy.Symbol("x"), 1)
        if isinstance(fn, AppliedUndef):
            return NodoEstructura(etiqueta, lin, lec, ())
        hijos_der = [
            _construir_nodo(fn, tr("Función a derivar")),
            _construir_nodo(var, tr("Variable de derivación")),
        ]
        if int(orden) > 1:
            hijos_der.append(_construir_nodo(sympy.Integer(int(orden)), tr("Orden de derivación")))
        return NodoEstructura(etiqueta, lin, lec, tuple(hijos_der))

    if isinstance(expr, sympy.Integral):
        fn = expr.function
        limites = expr.limits[0]
        hijos_int = [_construir_nodo(fn, tr("Integrando")), _construir_nodo(limites[0], tr("Variable de integración"))]
        if len(limites) == 3:
            hijos_int.append(_construir_nodo(limites[1], tr("Límite inferior")))
            hijos_int.append(_construir_nodo(limites[2], tr("Límite superior")))
        return NodoEstructura(etiqueta, lin, lec, tuple(hijos_int))

    if isinstance(expr, (sympy.Sum, sympy.Product)):
        fn = expr.function
        var, inf, sup = expr.limits[0]
        hijos_sp = (
            _construir_nodo(var, tr("Índice")),
            _construir_nodo(inf, tr("Límite inferior")),
            _construir_nodo(sup, tr("Límite superior")),
            _construir_nodo(fn, tr("Término general")),
        )
        return NodoEstructura(etiqueta, lin, lec, hijos_sp)

    if isinstance(expr, (TransformadaLaplace, TransformadaInversaLaplace)):
        f, v_orig, v_dest = expr.args
        hijos_lap = (
            _construir_nodo(f, tr("Función")),
            _construir_nodo(v_orig, tr("Variable original")),
            _construir_nodo(v_dest, tr("Variable transformada")),
        )
        return NodoEstructura(etiqueta, lin, lec, hijos_lap)

    datos_raiz = _es_raiz(expr)
    if datos_raiz is not None:
        radicando, indice = datos_raiz
        hijos_raiz = [_construir_nodo(radicando, tr("Radicando"))]
        if indice != 2:
            hijos_raiz.insert(0, _construir_nodo(indice, tr("Índice de la raíz")))
        return NodoEstructura(etiqueta, lin, lec, tuple(hijos_raiz))

    num, den = _separar_fraccion_sin_evaluar(expr)
    if den != 1:
        hijos_frac = (
            _construir_nodo(num, tr("Numerador")),
            _construir_nodo(den, tr("Denominador")),
        )
        return NodoEstructura(etiqueta, lin, lec, hijos_frac)

    if isinstance(expr, sympy.Pow):
        base, exp = expr.args
        hijos_pow = (
            _construir_nodo(base, tr("Base")),
            _construir_nodo(exp, tr("Exponente")),
        )
        return NodoEstructura(etiqueta, lin, lec, hijos_pow)

    if isinstance(expr, sympy.Add):
        hijos_add = tuple(
            _construir_nodo(t, tr("Término {n}", n=i))
            for i, t in enumerate(expr.args, 1)
        )
        return NodoEstructura(etiqueta, lin, lec, hijos_add)

    if isinstance(expr, sympy.Mul):
        hijos_mul = tuple(
            _construir_nodo(f, tr("Factor {n}", n=i))
            for i, f in enumerate(expr.args, 1)
        )
        return NodoEstructura(etiqueta, lin, lec, hijos_mul)

    if isinstance(expr, sympy.Basic) and expr.args and not _es_atómica(expr):
        hijos_fn = tuple(
            _construir_nodo(a, tr("Argumento") if len(expr.args) == 1 else tr("Argumento {n}", n=i))
            for i, a in enumerate(expr.args, 1)
        )
        return NodoEstructura(etiqueta, lin, lec, hijos_fn)

    return NodoEstructura(etiqueta, lin, lec, ())


def _construir_nodo_matriz(mat: sympy.MatrixBase, etiqueta: str, lin: str, lec: str) -> NodoEstructura:
    nodos_filas = []
    for i in range(mat.rows):
        celdas_fila = tuple(
            _construir_nodo(mat[i, j], tr("Fila {i}, Columna {j}", i=i + 1, j=j + 1))
            for j in range(mat.cols)
        )
        exp_fila = "[" + ", ".join(texto_lineal(mat[i, j]) for j in range(mat.cols)) + "]"
        lec_fila = ", ".join(verbalizar_objeto(mat[i, j], LECTURA_DETALLADA) for j in range(mat.cols))
        nodos_filas.append(NodoEstructura(tr("Fila {i}", i=i + 1), exp_fila, lec_fila, celdas_fila))
    return NodoEstructura(etiqueta, lin, lec, tuple(nodos_filas))
