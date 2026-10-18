"""
Compila el ejecutable con cx_Freeze y verifica la suite de pruebas.
"""
import subprocess
import sys

from _version import __version__


def main():
    print(f"=== Verificando suite de pruebas para Editor Matemático Accesible v{__version__} ===")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], check=True)
    print("=== Compilando ejecutable con cx_Freeze ===")
    subprocess.run([sys.executable, "setup.py", "build"], check=True)
    print("Compilación finalizada correctamente.")


if __name__ == "__main__":
    main()
