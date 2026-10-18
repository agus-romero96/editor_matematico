"""
Serialización de objetos SymPy sin evaluar sus expresiones al reconstruirlos.

Por defecto, pickle reconstruye los objetos SymPy llamando a su constructor normal,
que evalúa la expresión: por ejemplo, "1/6 + 1/3" se convertiría en "1/2" y una
integral o derivada planteada podría simplificarse. Este módulo conserva el árbol
exacto tal como lo escribió el usuario.
"""
import io
import pickle
from typing import Any

from sympy.core.function import AppliedUndef
from sympy import Atom, Basic, Function, Order, Set


def _reconstruir_sin_evaluar(clase, args):
    return clase(*args, evaluate=False)


def _reconstruir_funcion_indefinida(nombre: str, args):
    return Function(nombre)(*args)


class _PicklerSinEvaluar(pickle.Pickler):
    def reducer_override(self, obj: Any):
        if isinstance(obj, Basic) and not isinstance(obj, (Atom, Set, Order)):
            if isinstance(obj, AppliedUndef):
                return _reconstruir_funcion_indefinida, (obj.func.__name__, obj.args)
            try:
                obj.func(*obj.args, evaluate=False)
                return _reconstruir_sin_evaluar, (obj.func, obj.args)
            except TypeError:
                pass
        return NotImplemented


def volcar(obj: Any) -> bytes:
    """Serializa obj a bytes conservando las expresiones SymPy sin evaluar."""
    buf = io.BytesIO()
    _PicklerSinEvaluar(buf, protocol=pickle.HIGHEST_PROTOCOL).dump(obj)
    return buf.getvalue()


def cargar(datos: bytes) -> Any:
    """Reconstruye el objeto serializado con volcar()."""
    return pickle.loads(datos)
