"""
Parser matemático accesible para el Editor Matemático.

Amplía el parser de `calculadora_accesible` para cubrir todas las construcciones que
un estudiante o docente escribe en un documento matemático:
  - Aritmética, polinomios, fracciones, potencias (`^`), raíces (`sqrt(x)`, `raiz(x, n)`)
  - Ecuaciones e inecuaciones (`=`, `<=`, `>=`, `<`, `>`, `!=`)
  - Límites (`lim(f, x, a)`, laterales `lim(f, x, a, '+')` o `lim(f, x, '0+')`)
  - Derivadas (`diff(f, x)`, `diff(f, x, n)`, `y'`, `y''`, `dy/dx`, `d2y/dx2`)
  - Integrales indefinidas y definidas (`int(f, x)`, `int(f, x, a, b)`)
  - Sumatorias y productorias (`sum(f, k, a, b)`, `prod(f, k, a, b)`)
  - Ecuaciones diferenciales y Laplace (`heaviside(t)`, `dirac(t)`, `laplace(f, t, s)`, `ilaplace(F, s, t)`)
  - Matrices (`1 2\\n3 4` o `Matrix([[1, 2], [3, 4]])`) y sistemas de ecuaciones
"""
from __future__ import annotations

import re
from typing import Any, Optional, Tuple

import sympy
from sympy.core.function import AppliedUndef
from sympy.parsing.sympy_parser import (
    _token_splittable,
    convert_xor,
    function_exponentiation,
    implicit_application,
    implicit_multiplication,
    parse_expr,
    split_symbols_custom,
    standard_transformations,
)

from i18n import tr

# Funciones conocidas ordenadas de más larga a más corta para evitar partir nombres
# como "xsin(x)" en "x*s*i*n*x" y proponer correcciones claras.
FUNCIONES_CONOCIDAS = (
    "heaviside", "factorial", "integral", "derivada", "producto",
    "ilaplace", "laplace", "derivar",
    "log10", "asinh", "acosh", "atanh",
    "asin", "acos", "atan", "acot", "sinh", "cosh", "tanh", "coth", "sqrt", "cbrt",
    "root", "raiz", "suma", "prod", "diff",
    "sin", "cos", "tan", "cot", "sec", "csc", "exp", "log", "abs", "lim", "int", "sum", "det",
    "ln",
)

# Funciones que se aceptan en una ecuación diferencial (como y(x), x(t), u(x))
FUNCIONES_EDO_PERMITIDAS = {"y", "x", "u", "v", "z", "f", "g", "r", "s", "p", "q"}


def _contiene_funcion(nombre: str) -> Optional[Tuple[str, str, str]]:
    """Devuelve (antes, funcion, despues) si el nombre contiene una función conocida."""
    for f in FUNCIONES_CONOCIDAS:
        i = nombre.find(f)
        if i != -1:
            return nombre[:i], f, nombre[i + len(f):]
    return None


def _se_puede_partir(nombre: str) -> bool:
    """
    Decide si un identificador de varias letras se interpreta como producto (xy -> x*y).
    No parte nombres que contienen funciones conocidas ni marcadores internos de derivadas.
    """
    if nombre.startswith("deriv_") or _contiene_funcion(nombre):
        return False
    return _token_splittable(nombre)


# Constructores simbólicos sin evaluar para el editor
class TransformadaLaplace(sympy.Function):
    """Representación simbólica sin evaluar de L{f(t)}(s)."""
    pass


class TransformadaInversaLaplace(sympy.Function):
    """Representación simbólica sin evaluar de L^-1{F(s)}(t)."""
    pass


class EvaluacionBarrow(sympy.Function):
    """Representación simbólica de [F(x)]_a^b (Regla de Barrow)."""
    pass


class DeterminanteSimbolico(sympy.Function):
    """Representación simbólica de |A| (determinante sin evaluar)."""
    pass


_PATRON_DY_DX = re.compile(r"\bd(\d*)([a-zA-Z])\s*/\s*d([a-zA-Z])(\d*)\b")
_PATRON_PRIMA = re.compile(r"\b([a-zA-Z])('+)")


class ParserMatematico:
    """
    Parser matemático seguro, tolerante y pensado para lectores de pantalla.
    - Conserva la estructura sin evaluar (`evaluate=False`) para que el editor muestre
      y verbalice exactamente lo que el usuario escribió.
    - Crea variables reales (`Symbol(..., real=True)`).
    - Soporta ecuaciones, inecuaciones, límites, derivadas, integrales, sumatorias,
      matrices y ecuaciones diferenciales.
    """

    def __init__(self):
        self.transformations = standard_transformations + (
            convert_xor,
            split_symbols_custom(_se_puede_partir),
            implicit_multiplication,
            implicit_application,
            function_exponentiation,
        )

        self.contexto = {
            "Symbol": self.simbolo,
            # Constantes
            "e": sympy.E,
            "pi": sympy.pi,
            # Infinito
            "oo": sympy.oo,
            "inf": sympy.oo,
            "infinito": sympy.oo,
            "infinity": sympy.oo,
            # Logaritmos y exponencial
            "log": sympy.log,
            "ln": sympy.log,
            "log10": lambda x: sympy.log(x, 10, evaluate=False),
            "exp": sympy.exp,
            # Trigonometría e hiperbólicas
            "sin": sympy.sin,
            "sen": sympy.sin,
            "cos": sympy.cos,
            "tan": sympy.tan,
            "tg": sympy.tan,
            "cot": sympy.cot,
            "sec": sympy.sec,
            "csc": sympy.csc,
            "asin": sympy.asin,
            "acos": sympy.acos,
            "atan": sympy.atan,
            "acot": sympy.acot,
            "sinh": sympy.sinh,
            "cosh": sympy.cosh,
            "tanh": sympy.tanh,
            "coth": sympy.coth,
            "asinh": sympy.asinh,
            "acosh": sympy.acosh,
            "atanh": sympy.atanh,
            # Raíces, valor absoluto y factorial
            "sqrt": sympy.sqrt,
            "cbrt": lambda x: sympy.root(x, 3, evaluate=False),
            "root": lambda x, n=2: sympy.root(x, n, evaluate=False),
            "raiz": lambda x, n=2: sympy.root(x, n, evaluate=False),
            "abs": sympy.Abs,
            "factorial": sympy.factorial,
            # Cálculo: límites, derivadas, integrales, sumatorias, productorias
            "lim": self._construir_limite,
            "diff": self._construir_derivada,
            "derivar": self._construir_derivada,
            "derivada": self._construir_derivada,
            "int": self._construir_integral,
            "integral": self._construir_integral,
            "barrow": self._construir_barrow,
            "sum": self._construir_sumatoria,
            "suma": self._construir_sumatoria,
            "prod": self._construir_productoria,
            "producto": self._construir_productoria,
            # Ecuaciones diferenciales y Laplace
            "heaviside": sympy.Heaviside,
            "dirac": sympy.DiracDelta,
            "laplace": self._construir_laplace,
            "ilaplace": self._construir_ilaplace,
            # Matrices y determinantes
            "matrix": sympy.Matrix,
            "det": lambda m: DeterminanteSimbolico(sympy.Matrix(m) if isinstance(m, list) else m),
            # Conjuntos e intervalos
            "interval": sympy.Interval,
            "intervalo": sympy.Interval,
            "union": sympy.Union,
            "reales": sympy.S.Reals,
            "vacio": sympy.EmptySet,
        }

    @staticmethod
    def simbolo(nombre: str) -> sympy.Symbol:
        """Crea una variable real con el mismo criterio que el parser (minúsculas, sin espacios)."""
        return sympy.Symbol(str(nombre).strip().lower(), real=True)

    def _construir_limite(self, expr: Any, var: Any = None, tendencia: Any = 0, direccion: Any = "+-"):
        v = self.simbolo(var) if var is not None else self.simbolo("x")
        dir_str = str(direccion).strip().strip("'\"")
        if isinstance(tendencia, str):
            t_txt = tendencia.strip().strip("'\"")
            if t_txt.endswith("+") and t_txt not in ("+",):
                dir_str = "+"
                tendencia = self.parsear(t_txt[:-1])
            elif t_txt.endswith("-") and t_txt not in ("-", "-oo", "-inf", "-infinito", "-infinity"):
                dir_str = "-"
                tendencia = self.parsear(t_txt[:-1])
            else:
                tendencia = self.parsear(t_txt)
        if dir_str not in ("+", "-", "+-"):
            dir_str = "+-"
        return sympy.Limit(expr, v, tendencia, dir=dir_str)

    def _construir_derivada(self, expr: Any, var: Any = None, orden: Any = 1):
        v = self.simbolo(var) if var is not None else self.simbolo("x")
        n = int(orden) if orden is not None else 1
        if n <= 1:
            return sympy.Derivative(expr, v, evaluate=False)
        return sympy.Derivative(expr, (v, n), evaluate=False)

    def _construir_integral(self, expr: Any, var: Any = None, inferior: Any = None, superior: Any = None):
        v = self.simbolo(var) if var is not None else self.simbolo("x")
        if inferior is not None and superior is not None:
            return sympy.Integral(expr, (v, inferior, superior))
        return sympy.Integral(expr, v)

    def _construir_barrow(self, expr: Any, var: Any = None, inferior: Any = 0, superior: Any = 1):
        v = self.simbolo(var) if var is not None else self.simbolo("x")
        return EvaluacionBarrow(expr, v, inferior, superior)

    def _construir_sumatoria(self, expr: Any, var: Any = None, inferior: Any = 1, superior: Any = None):
        v = self.simbolo(var) if var is not None else self.simbolo("k")
        sup = superior if superior is not None else self.simbolo("n")
        return sympy.Sum(expr, (v, inferior, sup))

    def _construir_productoria(self, expr: Any, var: Any = None, inferior: Any = 1, superior: Any = None):
        v = self.simbolo(var) if var is not None else self.simbolo("k")
        sup = superior if superior is not None else self.simbolo("n")
        return sympy.Product(expr, (v, inferior, sup))

    def _construir_laplace(self, expr: Any, var_origen: Any = None, var_destino: Any = None):
        t = self.simbolo(var_origen) if var_origen is not None else self.simbolo("t")
        s = self.simbolo(var_destino) if var_destino is not None else self.simbolo("s")
        return TransformadaLaplace(expr, t, s)

    def _construir_ilaplace(self, expr: Any, var_origen: Any = None, var_destino: Any = None):
        s = self.simbolo(var_origen) if var_origen is not None else self.simbolo("s")
        t = self.simbolo(var_destino) if var_destino is not None else self.simbolo("t")
        return TransformadaInversaLaplace(expr, s, t)

    def _preprocesar_derivadas(self, txt: str, indep_forzada: Optional[str] = None) -> Tuple[str, dict]:
        locales_extra = {}

        def _reemplazar_leibniz(m: re.Match) -> str:
            orden_num = m.group(1)
            dep = m.group(2).lower()
            indep = m.group(3).lower()
            orden_den = m.group(4)
            n = int(orden_num or orden_den or "1")
            clave = f"deriv_{n}_{dep}_{indep}"
            x_sym = self.simbolo(indep)
            y_fn = sympy.Function(dep)(x_sym)
            locales_extra[clave] = (
                sympy.Derivative(y_fn, x_sym, evaluate=False)
                if n == 1 else sympy.Derivative(y_fn, (x_sym, n), evaluate=False)
            )
            return f" {clave} "

        txt_proc = _PATRON_DY_DX.sub(_reemplazar_leibniz, txt)
        indep_defecto = indep_forzada or ("t" if ("t" in txt_proc and "x" not in txt_proc) else "x")

        def _reemplazar_prima(m: re.Match) -> str:
            dep = m.group(1).lower()
            n = len(m.group(2))
            clave = f"deriv_{n}_{dep}_{indep_defecto}"
            x_sym = self.simbolo(indep_defecto)
            y_fn = sympy.Function(dep)(x_sym)
            locales_extra[clave] = (
                sympy.Derivative(y_fn, x_sym, evaluate=False)
                if n == 1 else sympy.Derivative(y_fn, (x_sym, n), evaluate=False)
            )
            return f"{clave}"

        txt_proc = _PATRON_PRIMA.sub(_reemplazar_prima, txt_proc)
        return txt_proc, locales_extra

    def parsear(self, expresion: str) -> Any:
        if not expresion or not expresion.strip():
            raise ValueError(tr("La expresión está vacía."))

        texto_limpio = expresion.strip()

        if "\n" in texto_limpio and not any(op in texto_limpio for op in ("=", "<", ">")):
            return self.parsear_matriz(texto_limpio)

        if texto_limpio.count("(") != texto_limpio.count(")"):
            raise ValueError(tr("Paréntesis desbalanceados."))
        if texto_limpio.count("[") != texto_limpio.count("]"):
            raise ValueError(tr("Corchetes desbalanceados."))

        relacion = self._dividir_relacion_nivel_cero(texto_limpio)
        if relacion is not None:
            izq_txt, op, der_txt = relacion
            if not izq_txt.strip() or not der_txt.strip():
                raise ValueError(tr("Falta uno de los dos lados de la relación '{op}'.", op=op))
            indep = "t" if ("t" in texto_limpio.lower() and "x" not in texto_limpio.lower()) else "x"
            izq = self._parsear_expresion_simple(izq_txt, indep_forzada=indep)
            der = self._parsear_expresion_simple(der_txt, indep_forzada=indep)
            constructores = {
                "=": sympy.Eq,
                "==": sympy.Eq,
                "<=": sympy.Le,
                "≤": sympy.Le,
                ">=": sympy.Ge,
                "≥": sympy.Ge,
                "<": sympy.Lt,
                ">": sympy.Gt,
                "!=": sympy.Ne,
                "≠": sympy.Ne,
            }
            return constructores[op](izq, der, evaluate=False)

        return self._parsear_expresion_simple(texto_limpio)

    def _parsear_expresion_simple(self, expresion: str, indep_forzada: Optional[str] = None) -> Any:
        txt = expresion.strip()
        txt = re.sub(
            r"\blim\s*\(([^,]+),\s*([^,]+),\s*([+-]?\d+(?:\.\d+)?|\w+)\s*([+-])\s*\)",
            r"lim(\1, \2, \3, '\4')",
            txt,
            flags=re.IGNORECASE,
        )
        txt_min = txt.lower()
        txt_proc, locales_extra = self._preprocesar_derivadas(txt_min, indep_forzada=indep_forzada)
        contexto_actual = {**self.contexto, **locales_extra}

        try:
            resultado = parse_expr(
                txt_proc,
                transformations=self.transformations,
                local_dict=contexto_actual,
                evaluate=False,
            )
        except Exception as e:
            raise ValueError(tr("No se pudo interpretar la expresión: {error}", error=str(e)))

        if isinstance(resultado, list):
            resultado = sympy.Matrix(resultado)

        self._validar_nombres(resultado, txt_min)
        return resultado

    @staticmethod
    def _dividir_relacion_nivel_cero(texto: str) -> Optional[Tuple[str, str, str]]:
        nivel = 0
        operadores_dobles = ("<=", ">=", "!=", "==")
        operadores_simples = ("=", "<", ">", "≤", "≥", "≠")

        i = 0
        n = len(texto)
        encontrados = []
        while i < n:
            c = texto[i]
            if c in "([{":
                nivel += 1
            elif c in ")]}":
                nivel = max(0, nivel - 1)
            elif nivel == 0:
                if texto[i:i + 2] in operadores_dobles:
                    encontrados.append((i, texto[i:i + 2]))
                    i += 2
                    continue
                if c in operadores_simples:
                    encontrados.append((i, c))
            i += 1

        if not encontrados:
            return None
        if len(encontrados) > 1:
            raise ValueError(tr("Escriba solo un signo de relación (=, <, >, <=, >=) por línea."))
        pos, op = encontrados[0]
        return texto[:pos], op, texto[pos + len(op):]

    def parsear_matriz(self, texto: str) -> sympy.Matrix:
        limpio = texto.strip()
        if not limpio:
            raise ValueError(tr("La matriz está vacía."))
        if limpio.startswith("[") or limpio.lower().startswith("matrix"):
            res = self._parsear_expresion_simple(limpio)
            if isinstance(res, sympy.MatrixBase):
                return res
            if isinstance(res, list):
                return sympy.Matrix(res)
            raise ValueError(tr("Formato de matriz no válido."))

        lineas = [fila.strip() for fila in re.split(r"[\n;]+", limpio) if fila.strip()]
        filas = []
        columnas_esperadas = None
        for idx, linea in enumerate(lineas, 1):
            partes = [p.strip() for p in (linea.split(",") if "," in linea else linea.split()) if p.strip()]
            if not partes:
                continue
            if columnas_esperadas is None:
                columnas_esperadas = len(partes)
            elif len(partes) != columnas_esperadas:
                raise ValueError(
                    tr("La fila {fila} tiene {n} elementos, pero la primera fila tiene {m}.",
                       fila=idx, n=len(partes), m=columnas_esperadas)
                )
            filas.append([self.parsear(celda) for celda in partes])

        if not filas:
            raise ValueError(tr("La matriz está vacía."))
        return sympy.Matrix(filas)

    def _validar_nombres(self, obj: Any, txt: str) -> None:
        if isinstance(obj, (list, tuple, sympy.MatrixBase)):
            for item in obj:
                self._validar_nombres(item, txt)
            return
        if not isinstance(obj, sympy.Basic):
            return

        for f in obj.atoms(AppliedUndef):
            nombre = f.func.__name__
            if nombre in FUNCIONES_EDO_PERMITIDAS and len(f.args) == 1:
                continue
            args = ", ".join(str(a) for a in f.args)
            raise ValueError(self._mensaje_nombre(nombre, f"{nombre}({args})", args))

        for s in obj.free_symbols:
            if _contiene_funcion(s.name):
                args = self._argumento_tras(txt, s.name)
                escrito = f"{s.name}({args})" if args is not None else s.name
                raise ValueError(self._mensaje_nombre(s.name, escrito, args))

    @staticmethod
    def _argumento_tras(txt: str, nombre: str) -> Optional[str]:
        i = txt.find(nombre + "(")
        if i == -1:
            return None
        inicio = i + len(nombre) + 1
        nivel = 1
        for j in range(inicio, len(txt)):
            if txt[j] == "(":
                nivel += 1
            elif txt[j] == ")":
                nivel -= 1
                if nivel == 0:
                    return txt[inicio:j]
        return None

    def _mensaje_nombre(self, nombre: str, escrito: str, args: Optional[str]) -> str:
        partes = _contiene_funcion(nombre)
        if not partes:
            return tr("No se reconoce la función '{nombre}' en '{escrito}'. Si quería multiplicar, use '*'.",
                      nombre=nombre, escrito=escrito)

        antes, funcion, despues = partes
        if args is not None and not despues:
            sugerencia = f"{'*'.join(antes)}*{funcion}({args})" if antes else f"{funcion}({args})"
        elif args is None and despues and not antes:
            sugerencia = f"{funcion}({despues})"
        elif args is None and despues and antes:
            sugerencia = f"{'*'.join(antes)}*{funcion}({despues})"
        else:
            sugerencia = None

        msg = tr("No se reconoce '{escrito}'.", escrito=escrito)
        if sugerencia:
            msg += " " + tr("¿Quiso decir {sugerencia}?", sugerencia=sugerencia)
        return msg + " " + tr("Escriba '*' entre una variable y una función, y el argumento entre paréntesis.")
