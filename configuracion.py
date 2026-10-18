"""
Preferencias del usuario, guardadas en %APPDATA%\\EditorMatematico\\config.json.

    from configuracion import leer, guardar, MODO_LECTURA, LECTURA_DETALLADA
    leer(MODO_LECTURA)            # el valor guardado o, si no hay, el de PREFERENCIAS
    guardar(MODO_LECTURA, LECTURA_DETALLADA)

Nunca falla: un archivo ausente o dañado da los valores por defecto, y si no se puede
escribir, el editor sigue funcionando (la preferencia solo dura la sesión).
"""
import json
import os
from typing import Any

# Claves de config.json
IDIOMA = "idioma"
MODO_LECTURA = "modo_lectura"
VERBALIZAR_AL_NAVEGAR = "verbalizar_al_navegar"
BUSCAR_ACTUALIZACIONES = "buscar_actualizaciones"
VERSION_OMITIDA = "version_omitida"

# Valores de MODO_LECTURA
LECTURA_DETALLADA = "detallada"  # marca inicio y fin de fracciones, raíces, integrales, etc.
LECTURA_BREVE = "breve"          # lectura ágil para repasar rápido

# Valor por defecto de cada preferencia, y los valores válidos (None: cualquiera de ese tipo)
PREFERENCIAS = {
    IDIOMA: (None, None),  # None: el del sistema (lo decide i18n)
    MODO_LECTURA: (LECTURA_DETALLADA, {LECTURA_DETALLADA, LECTURA_BREVE}),
    VERBALIZAR_AL_NAVEGAR: (True, {True, False}),
    BUSCAR_ACTUALIZACIONES: (True, {True, False}),
    VERSION_OMITIDA: (None, None),
}


def ruta_configuracion() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "EditorMatematico", "config.json")


def _leer_archivo() -> dict:
    try:
        with open(ruta_configuracion(), encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except Exception:
        return {}


def leer(clave: str) -> Any:
    """Valor guardado de una preferencia, o su valor por defecto si falta o no es válido."""
    defecto, validos = PREFERENCIAS[clave]
    valor = _leer_archivo().get(clave, defecto)
    if validos is not None and valor not in validos:
        return defecto
    return valor


def guardar(clave: str, valor: Any) -> None:
    """Guarda una preferencia conservando las demás. Si no se puede, no hace nada."""
    ruta = ruta_configuracion()
    try:
        datos = _leer_archivo()
        datos[clave] = valor
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        temporal = ruta + ".tmp"
        with open(temporal, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta)
    except Exception:
        pass
