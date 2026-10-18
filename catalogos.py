"""
Extracción y comprobación de textos marcados con tr("...") y N_("...") en el código.
"""
from __future__ import annotations

import ast
import json
import os
import string
from typing import Dict, Set

RAIZ = os.path.dirname(os.path.abspath(__file__))


def marcadores(texto: str) -> Set[str]:
    """Devuelve el conjunto de marcadores `{nombre}` presentes en una cadena de formato."""
    return {campo for _, campo, _, _ in string.Formatter().parse(texto) if campo}


def archivos_python() -> list[str]:
    rutas = []
    for base, carpetas, archivos in os.walk(RAIZ):
        carpetas[:] = [c for c in carpetas if c not in ("tests", "build", "dist", "__pycache__", ".git")]
        for nombre in sorted(archivos):
            if nombre.endswith(".py"):
                rutas.append(os.path.join(base, nombre))
    return rutas


def textos_marcados() -> Set[str]:
    """Recoge todas las cadenas literales pasadas como primer argumento a `tr()` o `N_()`."""
    encontrados: Set[str] = set()
    for ruta in archivos_python():
        with open(ruta, encoding="utf-8") as f:
            arbol = ast.parse(f.read(), filename=ruta)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                fn = nodo.func
                nombre = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
                if nombre in ("tr", "N_") and nodo.args:
                    arg0 = nodo.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        encontrados.add(arg0.value)
    return encontrados


def sincronizar_es_json() -> Dict[str, str]:
    """Actualiza locales/es.json con todos los textos marcados en el código."""
    ruta = os.path.join(RAIZ, "locales", "es.json")
    actual = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            actual = json.load(f)
    textos = sorted(textos_marcados())
    nuevo = {t: actual.get(t, t) for t in textos}
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(nuevo, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return nuevo


if __name__ == "__main__":
    cat = sincronizar_es_json()
    print(f"Catálogo es.json sincronizado ({len(cat)} textos).")
