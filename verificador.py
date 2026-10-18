"""
Verificador matemático de pasos para deberes y exámenes (`verificador.py`).

Comprueba con SymPy si un paso escrito por el usuario es matemáticamente coherente
con el paso anterior (sin hacerle la tarea, pero avisándole al instante si cometió
un error de signo, de despeje o de derivación/integración).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import sympy
from sympy.core.function import AppliedUndef
from sympy.core.relational import Relational
from sympy.solvers.ode import checkodesol

from documento import (
    TIPO_TEXTO,
    BloqueDocumento,
    DocumentoMatematico,
)
from i18n import tr
from parser_matematico import (
    DeterminanteSimbolico,
    EvaluacionBarrow,
    ParserMatematico,
    TransformadaInversaLaplace,
    TransformadaLaplace,
)
from verbalizador import texto_lineal

_PARSER = ParserMatematico()


@dataclass(frozen=True)
class ResultadoVerificacion:
    """Resultado de comprobar un paso respecto al paso matemático anterior."""
    es_valido: bool
    mensaje: str
    indice_anterior: Optional[int] = None
    indice_actual: Optional[int] = None


def _evaluar_construcciones_editor(expr: Any) -> Any:
    if not isinstance(expr, sympy.Basic):
        return expr
    expr = expr.replace(
        lambda e: isinstance(e, EvaluacionBarrow),
        lambda e: e.args[0].subs(e.args[1], e.args[3]) - e.args[0].subs(e.args[1], e.args[2]),
    )
    expr = expr.replace(
        lambda e: isinstance(e, DeterminanteSimbolico),
        lambda e: e.args[0].det() if isinstance(e.args[0], sympy.MatrixBase) else e.args[0],
    )
    expr = expr.replace(
        lambda e: isinstance(e, TransformadaLaplace),
        lambda e: sympy.laplace_transform(e.args[0], e.args[1], e.args[2], noconds=True),
    )
    expr = expr.replace(
        lambda e: isinstance(e, TransformadaInversaLaplace),
        lambda e: sympy.inverse_laplace_transform(e.args[0], e.args[1], e.args[2]),
    )
    return expr.doit()


def _quitar_constante_integracion(expr: Any) -> Any:
    if not isinstance(expr, sympy.Basic):
        return expr
    c_syms = {s for s in expr.free_symbols if s.name in ("c", "c1", "c2", "k")}
    for s in c_syms:
        expr = expr.subs(s, 0)
    return expr


def _es_edo(expr: Any) -> bool:
    if not isinstance(expr, sympy.Eq):
        return False
    for d in expr.atoms(sympy.Derivative):
        if isinstance(d.expr, AppliedUndef):
            return True
    return False


def _verificar_solucion_edo(edo_eq: sympy.Eq, paso_sol: sympy.Eq) -> Optional[ResultadoVerificacion]:
    derivs = [d for d in edo_eq.atoms(sympy.Derivative) if isinstance(d.expr, AppliedUndef)]
    if not derivs:
        return None
    y_fn = derivs[0].expr
    nombre_y = y_fn.func.__name__
    simbolo_y = _PARSER.simbolo(nombre_y)

    edo_funcional = sympy.Eq(
        edo_eq.lhs.subs(simbolo_y, y_fn),
        edo_eq.rhs.subs(simbolo_y, y_fn),
    )
    sol_funcional = sympy.Eq(
        paso_sol.lhs.subs(simbolo_y, y_fn),
        paso_sol.rhs.subs(simbolo_y, y_fn),
    )
    c_sym = _PARSER.simbolo("c")
    if sol_funcional.has(c_sym):
        sol_funcional = sol_funcional.subs(c_sym, sympy.Symbol("C1"))

    try:
        ok, residuo = checkodesol(edo_funcional, sol_funcional, func=y_fn)
        if ok:
            return ResultadoVerificacion(
                True,
                tr("Paso correcto: {sol} satisface la ecuación diferencial {edo}.",
                   sol=texto_lineal(paso_sol), edo=texto_lineal(edo_eq)),
            )
        return ResultadoVerificacion(
            False,
            tr("Atención: al sustituir {sol} en la ecuación diferencial {edo}, el residuo no se anula ({residuo}).",
               sol=texto_lineal(paso_sol), edo=texto_lineal(edo_eq), residuo=texto_lineal(residuo)),
        )
    except Exception:
        return None


def verificar_par(anterior: BloqueDocumento, actual: BloqueDocumento) -> ResultadoVerificacion:
    ok_ant, err_ant = anterior.es_valido()
    if not ok_ant:
        return ResultadoVerificacion(False, tr("El paso anterior tiene un error de sintaxis: {error}", error=err_ant))
    ok_act, err_act = actual.es_valido()
    if not ok_act:
        return ResultadoVerificacion(False, tr("El paso actual tiene un error de sintaxis: {error}", error=err_act))

    obj_ant = anterior.objeto_sympy()
    obj_act = actual.objeto_sympy()

    if isinstance(obj_ant, DeterminanteSimbolico):
        obj_ant = obj_ant.args[0].det() if isinstance(obj_ant.args[0], sympy.MatrixBase) else obj_ant.args[0]
    if isinstance(obj_act, DeterminanteSimbolico):
        obj_act = obj_act.args[0].det() if isinstance(obj_act.args[0], sympy.MatrixBase) else obj_act.args[0]

    if isinstance(obj_ant, sympy.MatrixBase) and isinstance(obj_act, sympy.MatrixBase):
        if obj_ant.shape != obj_act.shape:
            return ResultadoVerificacion(
                False,
                tr("Atención: las dimensiones de la matriz cambiaron de {f1}x{c1} a {f2}x{c2}.",
                   f1=obj_ant.rows, c1=obj_ant.cols, f2=obj_act.rows, c2=obj_act.cols),
            )
        if obj_ant.equals(obj_act):
            return ResultadoVerificacion(True, tr("Paso correcto: las dos matrices son iguales."))
        try:
            rref_ant, piv_ant = obj_ant.rref()
            rref_act, piv_act = obj_act.rref()
            if piv_ant == piv_act and rref_ant.equals(rref_act):
                return ResultadoVerificacion(
                    True,
                    tr("Paso correcto: la matriz actual es equivalente por filas a la anterior (operación elemental de Gauss-Jordan válida)."),
                )
        except Exception:
            pass
        return ResultadoVerificacion(
            False,
            tr("Atención: la matriz actual no es equivalente por filas a la matriz anterior."),
        )

    if isinstance(obj_ant, sympy.MatrixBase) and not isinstance(obj_act, (sympy.MatrixBase, list)):
        if obj_ant.rows == obj_ant.cols:
            det_val = obj_ant.det()
            val_act = _evaluar_construcciones_editor(obj_act)
            if sympy.simplify(det_val - val_act) == 0:
                return ResultadoVerificacion(
                    True,
                    tr("Paso correcto: el valor coincide con el determinante de la matriz ({det}).",
                       det=texto_lineal(det_val)),
                )

    if isinstance(obj_ant, list) or isinstance(obj_act, list):
        ecs_ant = obj_ant if isinstance(obj_ant, list) else [obj_ant]
        ecs_act = obj_act if isinstance(obj_act, list) else [obj_act]
        if all(isinstance(e, sympy.Eq) for e in ecs_ant) and all(isinstance(e, sympy.Eq) for e in ecs_act):
            vars_todas = sorted(
                set().union(*(e.free_symbols for e in ecs_ant + ecs_act)),
                key=lambda s: s.name,
            )
            if vars_todas:
                sol_ant = sympy.solve(ecs_ant, vars_todas, dict=True)
                sol_act = sympy.solve(ecs_act, vars_todas, dict=True)
                if sol_ant == sol_act:
                    return ResultadoVerificacion(
                        True,
                        tr("Paso correcto: el sistema o despeje mantiene exactamente la misma solución."),
                    )
                return ResultadoVerificacion(
                    False,
                    tr("Atención: el conjunto solución del sistema cambió respecto al paso anterior."),
                )

    if isinstance(obj_ant, Relational) and isinstance(obj_act, Relational):
        if _es_edo(obj_ant) and isinstance(obj_act, sympy.Eq) and not _es_edo(obj_act):
            ver_edo = _verificar_solucion_edo(obj_ant, obj_act)
            if ver_edo is not None:
                return ver_edo

        val_ant_der = _evaluar_construcciones_editor(obj_ant.rhs)
        val_act_izq = _evaluar_construcciones_editor(obj_act.lhs)
        val_act_der = _evaluar_construcciones_editor(obj_act.rhs)
        if isinstance(obj_ant, sympy.Eq) and isinstance(obj_act, sympy.Eq):
            if _expresiones_equivalentes(val_ant_der, val_act_izq) and _expresiones_equivalentes(val_act_izq, val_act_der):
                return ResultadoVerificacion(
                    True,
                    tr("Paso correcto: ambos lados de la igualdad coinciden con el paso anterior."),
                )

        vars_rel = sorted((obj_ant.free_symbols | obj_act.free_symbols) - {_PARSER.simbolo("c")}, key=lambda s: s.name)
        if len(vars_rel) == 1:
            v = vars_rel[0]
            try:
                set_ant = sympy.solveset(_evaluar_construcciones_editor(obj_ant), v, domain=sympy.S.Reals)
                set_act = sympy.solveset(_evaluar_construcciones_editor(obj_act), v, domain=sympy.S.Reals)
                if set_ant == set_act:
                    return ResultadoVerificacion(
                        True,
                        tr("Paso correcto: la ecuación o inecuación es equivalente a la anterior (misma solución para {var}).",
                           var=v.name),
                    )
                return ResultadoVerificacion(
                    False,
                    tr("Atención: la solución para {var} cambió de {s1} a {s2}. Revise signos, despejes o si dividió entre un negativo.",
                       var=v.name, s1=texto_lineal(set_ant), s2=texto_lineal(set_act)),
                )
            except Exception:
                pass

        if isinstance(obj_ant, sympy.Eq) and isinstance(obj_act, sympy.Eq):
            dif_ant = sympy.expand(_evaluar_construcciones_editor(obj_ant.lhs - obj_ant.rhs))
            dif_act = sympy.expand(_evaluar_construcciones_editor(obj_act.lhs - obj_act.rhs))
            if dif_ant != 0 and dif_act != 0:
                cociente = sympy.simplify(dif_ant / dif_act)
                if cociente.is_number and cociente != 0:
                    return ResultadoVerificacion(
                        True,
                        tr("Paso correcto: la ecuación es algebraicamente equivalente a la anterior."),
                    )
            return ResultadoVerificacion(
                False,
                tr("Atención: la ecuación actual ({act}) no es equivalente a la anterior ({ant}).",
                   act=texto_lineal(obj_act), ant=texto_lineal(obj_ant)),
            )

    if not isinstance(obj_ant, Relational) and isinstance(obj_act, sympy.Eq):
        if _expresiones_equivalentes(obj_ant, obj_act.lhs) and _expresiones_equivalentes(obj_act.lhs, obj_act.rhs):
            return ResultadoVerificacion(
                True,
                tr("Paso correcto: la igualdad planteada es verdadera y continúa la expresión anterior."),
            )
        if _expresiones_equivalentes(obj_ant, obj_act.rhs):
            return ResultadoVerificacion(
                True,
                tr("Paso correcto: el resultado coincide con el valor de la expresión anterior."),
            )

    if not isinstance(obj_ant, (Relational, list, sympy.MatrixBase)) and not isinstance(obj_act, (Relational, list, sympy.MatrixBase)):
        if isinstance(obj_ant, sympy.Integral) and len(obj_ant.limits[0]) == 1:
            var_int = obj_ant.limits[0][0]
            integrando = obj_ant.function
            primitiva = _quitar_constante_integracion(_evaluar_construcciones_editor(obj_act))
            try:
                derivada_prim = sympy.diff(primitiva, var_int)
                if sympy.simplify(derivada_prim - integrando) == 0:
                    return ResultadoVerificacion(
                        True,
                        tr("Paso correcto: la derivada de {prim} respecto a {var} coincide con el integrando {f}.",
                           prim=texto_lineal(obj_act), var=var_int.name, f=texto_lineal(integrando)),
                    )
            except Exception:
                pass

        if _expresiones_equivalentes(obj_ant, obj_act):
            return ResultadoVerificacion(
                True,
                tr("Paso correcto: {act} es equivalente a {ant}.",
                   act=texto_lineal(obj_act), ant=texto_lineal(obj_ant)),
            )
        return ResultadoVerificacion(
            False,
            tr("Atención: {act} no equivale a {ant}.",
               act=texto_lineal(obj_act), ant=texto_lineal(obj_ant)),
        )

    return ResultadoVerificacion(
        False,
        tr("Atención: no se pudo confirmar la equivalencia entre '{ant}' y '{act}'.",
           ant=anterior.contenido, act=actual.contenido),
    )


def _expresiones_equivalentes(a: Any, b: Any) -> bool:
    try:
        va = _quitar_constante_integracion(_evaluar_construcciones_editor(a))
        vb = _quitar_constante_integracion(_evaluar_construcciones_editor(b))
        dif = sympy.simplify(va - vb)
        if dif == 0:
            return True
        if sympy.simplify(sympy.expand(va) - sympy.expand(vb)) == 0:
            return True
        if sympy.trigsimp(va - vb) == 0:
            return True
    except Exception:
        pass
    return False


def verificar_en_documento(doc: DocumentoMatematico, indice_actual: int) -> ResultadoVerificacion:
    bloques = doc.bloques()
    if not (0 <= indice_actual < len(bloques)):
        raise IndexError("Índice de bloque fuera de rango.")

    actual = bloques[indice_actual]
    if actual.tipo == TIPO_TEXTO:
        return ResultadoVerificacion(
            True,
            tr("El paso {n} es un bloque de texto explicativo.", n=indice_actual + 1),
            indice_actual=indice_actual,
        )

    indice_previo = None
    for j in range(indice_actual - 1, -1, -1):
        if bloques[j].tipo != TIPO_TEXTO:
            indice_previo = j
            break

    if indice_previo is None:
        ok, err = actual.es_valido()
        if not ok:
            return ResultadoVerificacion(
                False,
                tr("Error de sintaxis en el paso {n}: {error}", n=indice_actual + 1, error=err),
                indice_actual=indice_actual,
            )
        obj = actual.objeto_sympy()
        if isinstance(obj, sympy.Eq) and not _es_edo(obj):
            if any(isinstance(a, (sympy.Integral, sympy.Derivative, sympy.Limit, sympy.Sum, EvaluacionBarrow, TransformadaLaplace, TransformadaInversaLaplace)) for a in sympy.preorder_traversal(obj.lhs)):
                if isinstance(obj.lhs, sympy.Integral) and len(obj.lhs.limits[0]) == 1:
                    var_int = obj.lhs.limits[0][0]
                    prim = _quitar_constante_integracion(_evaluar_construcciones_editor(obj.rhs))
                    if sympy.simplify(sympy.diff(prim, var_int) - obj.lhs.function) == 0:
                        return ResultadoVerificacion(
                            True,
                            tr("Paso {n} correcto: la igualdad de integración es válida.", n=indice_actual + 1),
                            indice_actual=indice_actual,
                        )
                if _expresiones_equivalentes(obj.lhs, obj.rhs):
                    return ResultadoVerificacion(
                        True,
                        tr("Paso {n} correcto: ambos lados de la igualdad tienen el mismo valor.", n=indice_actual + 1),
                        indice_actual=indice_actual,
                    )
                return ResultadoVerificacion(
                    False,
                    tr("Atención en el paso {n}: el lado derecho ({der}) no coincide con el cálculo del lado izquierdo ({izq}).",
                       n=indice_actual + 1, der=texto_lineal(obj.rhs), izq=texto_lineal(obj.lhs)),
                    indice_actual=indice_actual,
                )
        return ResultadoVerificacion(
            True,
            tr("El paso {n} es el planteamiento inicial y su sintaxis es válida.", n=indice_actual + 1),
            indice_actual=indice_actual,
        )

    res = verificar_par(bloques[indice_previo], actual)
    return ResultadoVerificacion(
        es_valido=res.es_valido,
        mensaje=tr("Comparando paso {actual} con paso {previo}: {mensaje}",
                   actual=indice_actual + 1, previo=indice_previo + 1, mensaje=res.mensaje),
        indice_anterior=indice_previo,
        indice_actual=indice_actual,
    )


def verificar_documento_completo(doc: DocumentoMatematico) -> List[ResultadoVerificacion]:
    resultados = []
    for i, bloque in enumerate(doc.bloques()):
        if bloque.tipo != TIPO_TEXTO:
            resultados.append(verificar_en_documento(doc, i))
    return resultados
