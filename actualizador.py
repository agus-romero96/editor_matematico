"""
Actualizador automático desde las Releases de GitHub (`agus-romero96/editor_matematico`).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple
import urllib.request

from _version import __version__

REPOSITORIO = "agus-romero96/editor_matematico"
URL_ULTIMA_RELEASE = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"


def tupla_version(version_str: str) -> Tuple[int, ...]:
    limpio = version_str.strip().lstrip("vV")
    partes = re.findall(r"\d+", limpio)
    return tuple(int(p) for p in partes) if partes else (0,)


def es_mas_nueva(remota: str, actual: str = __version__) -> bool:
    return tupla_version(remota) > tupla_version(actual)


def consultar_ultima_release(timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(
            URL_ULTIMA_RELEASE,
            headers={"Accept": "application/vnd.github+json", "User-Agent": f"EditorMatematico/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
        tag = datos.get("tag_name", "")
        if not tag or not es_mas_nueva(tag):
            return None
        return {
            "version": tag.lstrip("vV"),
            "nombre": datos.get("name") or tag,
            "notas": datos.get("body") or "",
            "url": datos.get("html_url") or f"https://github.com/{REPOSITORIO}/releases",
        }
    except Exception:
        return None
