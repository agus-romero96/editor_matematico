import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuracion import LECTURA_BREVE, LECTURA_DETALLADA
import i18n
import verbalizador


class TestVerbalizadorEInspector(unittest.TestCase):
    def setUp(self):
        i18n.establecer_idioma("es")

    def tearDown(self):
        i18n.establecer_idioma("es")

    def test_lectura_detallada_y_breve_espanol(self):
        det = verbalizador.verbalizar("(x^2 + 1)/(x - 3)", modo=LECTURA_DETALLADA)
        self.assertIn("fracción: numerador", det)
        self.assertIn("fin de fracción", det)

        breve = verbalizador.verbalizar("(x^2 + 1)/(x - 3)", modo=LECTURA_BREVE)
        self.assertIn("sobre", breve)
        self.assertNotIn("fin de fracción", breve)

    def test_verbalizacion_todas_las_areas(self):
        casos = [
            ("raiz(x + 1, 3)", "raíz cúbica"),
            ("lim(sin(x)/x, x, 0+)", "por la derecha"),
            ("diff(x^4, x, 2)", "derivada de orden 2"),
            ("int(x^2, x, 0, 1)", "integral definida desde 0 hasta 1"),
            ("y'' - 3*y' + 2*y = 0", "y segunda"),
            ("laplace(heaviside(t), t, s)", "transformada de Laplace"),
            ("det([[1, 2], [3, 4]])", "Determinante de 2 por 2"),
        ]
        for expr, fragmento in casos:
            with self.subTest(expr=expr):
                lec = verbalizador.verbalizar(expr)
                self.assertIn(fragmento, lec)

    def test_verbalizacion_en_ingles(self):
        i18n.establecer_idioma("en")
        lec = verbalizador.verbalizar("int(x^2, x, 0, 1)")
        self.assertIn("definite integral from 0 to 1", lec)
        lec_edo = verbalizador.verbalizar("y' + 2*x*y = 0")
        self.assertIn("y prime", lec_edo)

    def test_inspector_estructural(self):
        arbol = verbalizador.inspeccionar("int((x + 1)/(x - 1), x, 0, 2)")
        self.assertEqual(arbol.etiqueta, "Integral definida")
        etiquetas = [h.etiqueta for h in arbol.hijos]
        self.assertEqual(
            etiquetas,
            ["Integrando", "Variable de integración", "Límite inferior", "Límite superior"],
        )
        integrando = arbol.hijos[0]
        self.assertEqual([h.etiqueta for h in integrando.hijos], ["Numerador", "Denominador"])


if __name__ == "__main__":
    unittest.main()
