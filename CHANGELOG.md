# Registro de cambios (Changelog)

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [1.0.0] - 2026-10-18

Primera versión del **Editor Matemático Accesible**, diseñada a partir de la arquitectura y cobertura matemática de [`calculadora_accesible`](https://github.com/agus-romero96/calculadora_accesible) (v1.7.0) para que personas que usan lectores de pantalla (NVDA / JAWS) puedan redactar, explorar, verificar y entregar desarrollos matemáticos sin depender del editor visual de Word ni de códigos crípticos como EDICO.

### Añadido

- **Modelo de documento por bloques navegables** (`documento.py`):
  - Bloques de **Texto o nota**, **Fórmula o paso matemático**, **Sistema de ecuaciones / PVI** y **Matriz o determinante**, con justificación opcional en cada paso y guardado/carga en formato `.ema` (JSON estructurado).
- **Parser matemático extendido** (`parser_matematico.py`):
  - Cubre todas las áreas de la calculadora: aritmética, polinomios, raíces enésimas (`raiz(x, n)`), ecuaciones e inecuaciones (`=`, `<`, `<=`, `>`, `>=`, `!=`), límites bilaterales y laterales (`lim(f, x, a, '+')`, `0+`, `0-`), derivadas de orden $N$ (`diff(f, x, n)`), notación de Leibniz (`dy/dx`, `d2y/dx2`) y primas (`y'`, `y''`), integrales indefinidas y definidas (`int(f, x, a, b)`), regla de Barrow (`barrow(F, x, a, b)`), sumatorias/Taylor (`sum(...)`), ecuaciones diferenciales con `heaviside`/`dirac`, transformadas de Laplace (`laplace`, `ilaplace`) y matrices/determinantes.
- **Verbalizador matemático natural e Inspector Estructural (`F2`)** (`verbalizador.py`):
  - Modo **detallado** (anuncia inicio y fin de fracciones compuestas, raíces, exponentes y límites) y modo **breve** (`Ctrl+Shift+D`), en **español e inglés**.
  - Árbol estructural (`inspeccionar()`) que descompone cualquier fórmula en sus partes (numerador, denominador, índice, radicando, base, exponente, integrando, límites, lado izquierdo/derecho, filas y celdas $(i, j)$ de una matriz).
- **Registro de 16 asistentes guiados por atajo** (`asistentes.py`):
  - Diálogos con campos separados y vista previa verbalizada para insertar fracciones (`Ctrl+Shift+F`), potencias (`Ctrl+Shift+P`), raíces (`Ctrl+Shift+Q`), ecuaciones/inecuaciones (`Ctrl+R`), sistemas (`Ctrl+G`), matrices (`Ctrl+M`), determinantes (`Ctrl+K`), límites (`Ctrl+L`), derivadas (`Ctrl+D`), integrales indefinidas (`Ctrl+I`) y definidas (`Ctrl+Shift+I`), Barrow (`Ctrl+Shift+B`), sumatorias (`Ctrl+Shift+T`), EDO/PVI (`Ctrl+Shift+R`) y transformadas de Laplace (`Ctrl+Shift+L`, `Ctrl+Shift+U`).
- **Verificador de pasos para deberes y exámenes (`F5` / `Ctrl+Shift+V`)** (`verificador.py`):
  - Comprueba con SymPy si el paso escrito por el estudiante equivale al paso anterior (identidades algebraicas, conjunto solución de ecuaciones/inecuaciones con `solveset`, primitivas por derivación, resultados de límites/derivadas/integrales definidas, soluciones de EDO con `checkodesol` y operaciones elementales por filas en matrices).
- **Exportación a Word (`.docx` con OMML nativo), HTML+MathML, LaTeX, Markdown y Texto** (`exportar.py`):
  - Genera archivos `.docx` con ecuaciones nativas de Microsoft Word (`<m:oMathPara><m:oMath>`), además de HTML5 accesible con MathML Core válido (sin `<mfenced>` y con entidades numéricas), LaTeX, Markdown y texto plano.
- **Interfaz desacoplada en wxPython** (`main.py`):
  - `PanelEditorMatematico` reutilizable para integrarse en `calculadora_accesible` y `VentanaEditorMatematico` independiente, con soporte completo en español e inglés (`locales/es.json`, `locales/en.json`).
