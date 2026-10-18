"""
Configuración de cx_Freeze para generar el ejecutable de Windows sin ventana de consola.
"""
import os
import sys

from cx_Freeze import Executable, setup
from _version import __version__

base = "Win32GUI" if sys.platform == "win32" else None

include_files = [
    "asistentes.py",
    "actualizador.py",
    "autoprueba.py",
    "catalogos.py",
    "configuracion.py",
    "documento.py",
    "exportar.py",
    "i18n.py",
    "parser_matematico.py",
    "serializacion.py",
    "verbalizador.py",
    "verificador.py",
    "_version.py",
    "locales/",
    "LICENSE",
    "README.md",
]

build_exe_options = {
    "packages": ["sympy", "wx", "json", "zipfile", "xml"],
    "include_files": [f for f in include_files if os.path.exists(f)],
}

setup(
    name="EditorMatematicoAccesible",
    version=__version__,
    description="Editor de matemáticas accesible para lectores de pantalla (NVDA / JAWS)",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "main.py",
            base=base,
            target_name="editor-matematico-accesible.exe",
        )
    ],
)
