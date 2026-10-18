# Editor Matemático Accesible

Editor de matemáticas de escritorio diseñado **para personas que usan lectores de pantalla (NVDA, JAWS)**, construido con **Python + wxPython** y **SymPy** a partir de la base y las áreas matemáticas de [`calculadora_accesible`](https://github.com/agus-romero96/calculadora_accesible).

Nace para resolver las barreras del editor de ecuaciones de Word y de herramientas como EDICO: en lugar de moverte a ciegas por cursores visuales bidimensionales o memorizar códigos crípticos, trabajas en un **cuaderno estructurado paso a paso** donde puedes escribir en notación lineal natural o con asistentes guiados, escuchar cada expresión en voz natural, **inspeccionar su estructura en un árbol (`F2`)**, **verificar si tu paso equivale al anterior (`F5`)** y **exportar directamente a Word (`.docx` con ecuaciones nativas OMML), HTML con MathML o LaTeX**.

Disponible en **español e inglés** (interfaz, verbalizador matemático, verificador, ayuda y exportaciones).

## Características principales

| Función | Qué aporta frente a Word o EDICO |
| :--- | :--- |
| **Cuaderno por pasos navegables** | El documento es una lista ordenada de pasos (**Texto/nota**, **Fórmula**, **Sistema de ecuaciones/PVI** o **Matriz/Determinante**) que recorres con las flechas Arriba y Abajo escuchando su lectura hablada y tu justificación. |
| **Verbalizador matemático natural (`verbalizador.py`)** | Convierte cualquier expresión al español o inglés hablado sin símbolos mudos. Tiene modo **detallado** (*"fracción: numerador x al cuadrado más 1, entre denominador x menos 3, fin de fracción"*) y modo **breve** (`Ctrl+Shift+D`). |
| **Inspector estructural en árbol (`F2`)** | Abre un árbol navegable con las flechas que descompone la fórmula actual en sus partes exactas (*Lado izquierdo*, *Lado derecho*, *Numerador*, *Denominador*, *Índice*, *Radicando*, *Límite inferior/superior*, *Integrando*, *Fila i, Columna j*), eliminando la duda de "¿estoy dentro o fuera de la raíz/fracción?". |
| **16 asistentes guiados por atajo (`asistentes.py`)** | Si no quieres preocuparte por cerrar paréntesis en expresiones largas, cada área tiene un diálogo con campos separados y botón **Escuchar lectura previa** que arma la expresión por ti. |
| **Verificador de pasos (`F5` / `Ctrl+Shift+V`)** | Pensado para hacer deberes y exámenes: comprueba con SymPy si el paso que acabas de escribir equivale matemáticamente al anterior (en simplificaciones, despejes de ecuaciones/inecuaciones, integrales, EDO o Gauss-Jordan) y te avisa si hubo un error de signo sin hacerte la tarea. |
| **Exportación a Word (`.docx` OMML), HTML+MathML y LaTeX (`Ctrl+E`)** | Exporta tu cuaderno a un archivo **Word (`.docx`) con ecuaciones nativas de Word**, **HTML5 con MathML accesible** (para NVDA + MathCAT), **LaTeX (`.tex`)**, **Markdown (`.md`)** o **Texto plano (`.txt`)**. |
| **Arquitectura integrable con `calculadora_accesible`** | La interfaz está encapsulada en `PanelEditorMatematico(wx.Panel)` y la lógica en módulos sin `wx`, lista para abrirse como ventana o pestaña dentro de [`calculadora_accesible`](https://github.com/agus-romero96/calculadora_accesible). |

## Áreas matemáticas cubiertas

Cubre todas las áreas de la versión 1.7.0 de [`calculadora_accesible`](https://github.com/agus-romero96/calculadora_accesible):

1. **Aritmética, polinomios y radicales**: fracciones anidadas, potencias (`^`), raíces cuadradas (`sqrt(x)`), cúbicas (`cbrt(x)`) y de índice $n$ (`raiz(x, n)`), valor absoluto (`abs(x)`) y factorial (`factorial(n)`).
2. **Álgebra y sistemas**: ecuaciones e inecuaciones (`=`, `<`, `<=`, `>`, `>=`, `!=`), intervalos y uniones (`interval(a, b)`, `union(...)`), sistemas lineales y no lineales.
3. **Matrices y determinantes**: entrada natural por filas (`1 2\n3 4`) o `Matrix([[1,2],[3,4]])`, determinantes (`det(...)`), lectura por coordenadas $(i, j)$ y verificación de equivalencia por filas (Gauss-Jordan).
4. **Cálculo diferencial**: derivadas de primer orden (`diff(f, x)`) y de orden $N$ (`diff(f, x, n)`), notación de Leibniz (`dy/dx`, `d2y/dx2`) y notación de primas (`y'`, `y''`, `y'''`) para derivación implícita y EDO.
5. **Cálculo integral, límites y series de Taylor**: límites bilaterales, laterales (`lim(f, x, 0+)`, `lim(f, x, 0-)`) y al infinito (`oo`, `-oo`), integrales indefinidas (`int(f, x)`), integrales definidas e impropias (`int(f, x, a, b)`), evaluación de Barrow (`barrow(F, x, a, b)`), sumatorias (`sum(termino, k, a, b)`) y productorias (`prod(termino, k, a, b)`).
6. **Ecuaciones diferenciales (EDO) y Transformada de Laplace**: EDO de primer orden y orden superior, problemas de valor inicial (EDO + condiciones), escalón de Heaviside (`heaviside(t)`), delta de Dirac (`dirac(t)`), transformada de Laplace (`laplace(f, t, s)`), transformada inversa (`ilaplace(F, s, t)`) y verificación de soluciones con `checkodesol`.

## Atajos de teclado

| Atajo | Acción |
| :--- | :--- |
| `Ctrl+Enter` | Agregar el paso escrito al documento |
| `Ctrl+U` | Actualizar el paso seleccionado en la lista |
| `Alt+Flecha Arriba` / `Alt+Flecha Abajo` | Mover el paso seleccionado arriba o abajo |
| `Suprimir` | Eliminar el paso seleccionado |
| `F2` | **Inspeccionar estructura** de la fórmula actual en árbol |
| `F5` | **Verificar paso actual** respecto al paso matemático anterior |
| `Ctrl+Shift+V` | **Verificar todos los pasos** del documento |
| `Ctrl+Shift+D` | Alternar entre lectura detallada y lectura breve |
| `Ctrl+Shift+F` | Asistente: Insertar fracción |
| `Ctrl+Shift+P` | Asistente: Insertar potencia |
| `Ctrl+Shift+Q` | Asistente: Insertar raíz cuadrada o de índice $n$ |
| `Ctrl+R` | Asistente: Insertar ecuación o inecuación |
| `Ctrl+G` | Asistente: Insertar sistema de ecuaciones |
| `Ctrl+M` | Asistente: Insertar matriz |
| `Ctrl+K` | Asistente: Insertar determinante |
| `Ctrl+L` | Asistente: Insertar límite (incluye laterales) |
| `Ctrl+D` | Asistente: Insertar derivada (orden 1 o $N$) |
| `Ctrl+I` | Asistente: Insertar integral indefinida |
| `Ctrl+Shift+I` | Asistente: Insertar integral definida |
| `Ctrl+Shift+B` | Asistente: Insertar evaluación de Barrow $[F(x)]_a^b$ |
| `Ctrl+Shift+T` | Asistente: Insertar sumatoria / serie de Taylor |
| `Ctrl+Shift+R` | Asistente: Insertar ecuación diferencial (EDO) o PVI |
| `Ctrl+Shift+L` | Asistente: Insertar transformada de Laplace |
| `Ctrl+Shift+U` | Asistente: Insertar transformada inversa de Laplace |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` | Nuevo / Abrir (`.ema`) / Guardar (`.ema`) |
| `Ctrl+E` | Exportar a Word (`.docx`), HTML+MathML, LaTeX, Markdown o Texto |
| `Ctrl+Shift+C` | Copiar lectura accesible del paso actual |
| `Ctrl+Alt+L` / `Ctrl+Alt+M` | Copiar paso actual como LaTeX / como MathML |
| `F1` | Mostrar ayuda |

## Instalación y ejecución

```bash
pip install -r requirements.txt
python main.py
```

Para ejecutar las pruebas automatizadas:

```bash
python -X utf8 -m unittest discover -s tests -v
```

## Licencia

Distribuido bajo la licencia [MIT](LICENSE).
