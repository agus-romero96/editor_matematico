"""
Traducción de la interfaz, del verbalizador y de los documentos exportados.

El idioma de origen es el español: los textos se escriben en español en el código y
el catálogo locales/<idioma>.json da su traducción. Si falta una traducción, se
muestra el texto en español (nunca falla).

Uso:
    from i18n import tr, N_

    tr("Fracción: numerador {num}, entre denominador {den}", num=a, den=b)
    NOMBRE = N_("Expresión o ecuación")
    tr(NOMBRE)
"""
import json
import os
import sys
from typing import Dict

import configuracion
from configuracion import ruta_configuracion  # noqa: F401

IDIOMA_ORIGEN = "es"
IDIOMAS = {"es": "Español", "en": "English"}

_idioma = IDIOMA_ORIGEN
_catalogo: Dict[str, str] = {}


def carpeta_recursos() -> str:
    """Carpeta de la aplicación: junto al .exe si está compilada, si no la del código."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def carpeta_locales() -> str:
    return os.path.join(carpeta_recursos(), "locales")


def cargar_catalogo(codigo: str) -> Dict[str, str]:
    if codigo == IDIOMA_ORIGEN and os.environ.get("EDITOR_TEXTOS_ORIGEN") == "1":
        return {}
    ruta = os.path.join(carpeta_locales(), f"{codigo}.json")
    if not os.path.exists(ruta):
        return {} if codigo == IDIOMA_ORIGEN else _cargar_obligatorio(ruta)
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except Exception:
        if codigo == IDIOMA_ORIGEN:
            return {}
        raise


def _cargar_obligatorio(ruta: str) -> Dict[str, str]:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def establecer_idioma(codigo: str) -> None:
    global _idioma, _catalogo
    if codigo not in IDIOMAS:
        raise ValueError(f"Idioma no disponible: {codigo}")
    _catalogo = cargar_catalogo(codigo)
    _idioma = codigo


def idioma_actual() -> str:
    return _idioma


def tr(texto: str, **valores) -> str:
    """Traduce texto al idioma actual y rellena los {marcadores} con valores."""
    traducido = _catalogo.get(texto, texto)
    if valores:
        try:
            return traducido.format(**valores)
        except Exception:
            return texto.format(**valores)
    return traducido


def N_(texto: str) -> str:
    """Marca un texto para traducir más tarde con tr(texto). Devuelve el texto tal cual."""
    return texto


def detectar_idioma_sistema() -> str:
    """Español si el sistema está en español; inglés en cualquier otro caso."""
    try:
        import ctypes
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "es" if (langid & 0x3FF) == 0x0A else "en"
    except Exception:
        import locale
        nombre = (locale.getlocale()[0] or "").lower()
        return "es" if nombre.startswith(("es", "spanish")) else "en"


def idioma_guardado():
    codigo = configuracion.leer(configuracion.IDIOMA)
    return codigo if codigo in IDIOMAS else None


def guardar_idioma(codigo: str) -> None:
    configuracion.guardar(configuracion.IDIOMA, codigo)


def iniciar_idioma() -> str:
    """Idioma al arrancar la aplicación: el guardado o, la primera vez, el del sistema."""
    codigo = idioma_guardado() or detectar_idioma_sistema()
    try:
        establecer_idioma(codigo)
    except Exception:
        establecer_idioma(IDIOMA_ORIGEN)
    return idioma_actual()
