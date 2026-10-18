# Hoja de ruta de la versión 1.0.0 (`editor_matematico`)

Objetivo: llevar al **Editor Matemático Accesible** todas las áreas matemáticas de [`calculadora_accesible`](https://github.com/agus-romero96/calculadora_accesible) (v1.7.0), reemplazando la experiencia confusa de los editores visuales (como Word o EDICO) por un cuaderno estructurado por pasos con lectura verbalizada natural, inspección por árbol, asistentes guiados sin errores de paréntesis, verificador de equivalencia entre pasos y exportación directa a Word (`.docx` con ecuaciones nativas OMML), HTML+MathML y LaTeX.

Una tarea terminada se tacha (`~~...~~`).

## Plan de áreas y módulos

### 1. Infraestructura y compatibilidad con `calculadora_accesible`
1. ~~**Configuración y preferencias** (`configuracion.py`): idioma, modo de lectura (`detallada` o `breve`), verbalización al navegar y actualizaciones.~~ — **completada**
2. ~~**Internacionalización bilingüe ES/EN** (`i18n.py`, `catalogos.py`, `locales/es.json`, `locales/en.json`, `locales/ayuda_es.txt`, `locales/ayuda_en.txt`).~~ — **completada**
3. ~~**Serialización sin evaluar** (`serializacion.py`): conserva el árbol de SymPy tal como lo escribió el usuario (`1/3 + 1/6` no se aplana a `1/2`).~~ — **completada**
4. ~~**Interfaz desacoplada** (`PanelEditorMatematico` en `main.py`): lista para funcionar como programa independiente o incrustarse como pestaña/ventana en `calculadora_accesible`.~~ — **completada**

### 2. Áreas matemáticas cubiertas (equivalentes a `calculadora_accesible` v1.7.0)
5. ~~**Aritmética, fracciones, potencias y raíces** (`parser_matematico.py`, `verbalizador.py`, `asistentes.py`): fracciones simples y compuestas con anuncio de numerador/denominador, potencias, raíces cuadradas, cúbicas y de índice $n$ (`raiz(x, n)`), valor absoluto y factorial.~~ — **completada**
6. ~~**Álgebra: ecuaciones, inecuaciones, intervalos y sistemas** (`parser_matematico.py`, `documento.py`, `verificador.py`): relaciones `=`, `<`, `<=`, `>`, `>=`, `!=`, conjuntos e intervalos (`Interval`, `Union`), y bloques de sistemas de ecuaciones (`TIPO_SISTEMA`).~~ — **completada**
7. ~~**Álgebra lineal: matrices y determinantes** (`parser_matematico.py`, `verbalizador.py`, `documento.py`): lectura por filas y coordenadas $(i, j)$, bloques de matriz y determinante (`det(...)`), y verificación de equivalencia por filas (operaciones elementales de Gauss-Jordan).~~ — **completada**
8. ~~**Cálculo diferencial** (`parser_matematico.py`, `verbalizador.py`): derivadas de primer orden y de orden $N$ (`diff(f, x, n)`), notación de Leibniz (`dy/dx`, `d2y/dx2`) y notación de primas (`y'`, `y''`, `y'''`) para derivación implícita y EDO.~~ — **completada**
9. ~~**Cálculo integral, límites y series de Taylor** (`parser_matematico.py`, `verbalizador.py`, `asistentes.py`): límites bilaterales, laterales (`0+`, `0-`) y al infinito (`oo`, `-oo`), integrales indefinidas (`int(f, x)`), integrales definidas e impropias (`int(f, x, a, b)`), regla de Barrow (`barrow(F, x, a, b)`), sumatorias (`sum(...)`) y productorias (`prod(...)`).~~ — **completada**
10. ~~**Ecuaciones diferenciales ordinarias (EDO) y Transformada de Laplace** (`parser_matematico.py`, `verbalizador.py`, `verificador.py`): EDO de cualquier orden, problemas de valor inicial, escalón unitario (`heaviside(t)`), delta de Dirac (`dirac(t)`), transformada directa (`laplace(f, t, s)`), transformada inversa (`ilaplace(F, s, t)`) y comprobación de soluciones con `checkodesol`.~~ — **completada**

### 3. Herramientas de accesibilidad y entrega académica
11. ~~**Inspector estructural en árbol (`F2`)** (`verbalizador.inspeccionar`, `DialogoInspectorEstructura`): permite recorrer con las flechas cada parte de una expresión (numerador, denominador, índice, radicando, exponente, límites de integración, lado izquierdo/derecho, celda de matriz).~~ — **completada**
12. ~~**Verificador de pasos para estudiantes (`F5` / `Ctrl+Shift+V`)** (`verificador.py`): comprueba con SymPy si el paso actual equivale al anterior sin resolver el ejercicio por el estudiante.~~ — **completada**
13. ~~**Exportación a Word (`.docx` con OMML), HTML+MathML, LaTeX, Markdown y Texto** (`exportar.py`): genera ecuaciones nativas de Word (`<m:oMathPara><m:oMath>`) y páginas HTML5 con MathML válido sin `<mfenced>`.~~ — **completada**
