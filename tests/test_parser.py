import os
import sys
import unittest
import sympy as sp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser_matematico import (
    DeterminanteSimbolico,
    EvaluacionBarrow,
    ParserMatematico,
    TransformadaInversaLaplace,
    TransformadaLaplace,
)


class TestParserMatematico(unittest.TestCase):
    def setUp(self):
        self.p = ParserMatematico()
        self.x = self.p.simbolo("x")
        self.y = self.p.simbolo("y")

    def test_expresiones_algebraicas_y_aritmeticas(self):
        casos = [
            ("2x", 2 * self.x),
            ("2xy", 2 * self.x * self.y),
            ("3sin(x)", 3 * sp.sin(self.x)),
            ("sin^2(x) + cos^2(x)", sp.sin(self.x)**2 + sp.cos(self.x)**2),
            ("sqrt(x + 1)", sp.sqrt(self.x + 1)),
            ("raiz(x + 1, 3)", sp.root(self.x + 1, 3, evaluate=False)),
        ]
        for txt, esp in casos:
            with self.subTest(txt=txt):
                self.assertEqual(sp.simplify(self.p.parsear(txt) - esp), 0)

    def test_ecuaciones_e_inecuaciones(self):
        eq = self.p.parsear("2*x + 1 = 9")
        self.assertIsInstance(eq, sp.Eq)
        ineq = self.p.parsear("x^2 - 4 <= 0")
        self.assertIsInstance(ineq, sp.Le)
        estricta = self.p.parsear("x > 3")
        self.assertIsInstance(estricta, sp.Gt)

    def test_calculo_limites_derivadas_integrales(self):
        lim_lat = self.p.parsear("lim(1/x, x, 0+)")
        self.assertIsInstance(lim_lat, sp.Limit)
        self.assertEqual(str(lim_lat.args[3]), "+")

        der_n = self.p.parsear("diff(x^5, x, 3)")
        self.assertIsInstance(der_n, sp.Derivative)

        int_ind = self.p.parsear("int(x^2, x)")
        self.assertIsInstance(int_ind, sp.Integral)
        self.assertEqual(len(int_ind.limits[0]), 1)

        int_def = self.p.parsear("int(x^2, x, 0, 1)")
        self.assertIsInstance(int_def, sp.Integral)
        self.assertEqual(len(int_def.limits[0]), 3)

        barrow = self.p.parsear("barrow(x^3/3, x, 0, 1)")
        self.assertIsInstance(barrow, EvaluacionBarrow)

    def test_edo_primas_leibniz_y_laplace(self):
        edo1 = self.p.parsear("y' + 2*x*y = 0")
        self.assertIsInstance(edo1, sp.Eq)
        self.assertTrue(edo1.has(sp.Derivative))

        edo2 = self.p.parsear("d2y/dx2 + y = sin(x)")
        self.assertIsInstance(edo2, sp.Eq)
        self.assertTrue(edo2.has(sp.Derivative))

        lap = self.p.parsear("laplace(exp(2*t), t, s)")
        self.assertIsInstance(lap, TransformadaLaplace)

        ilap = self.p.parsear("ilaplace(1/(s - 2), s, t)")
        self.assertIsInstance(ilap, TransformadaInversaLaplace)

    def test_matrices_y_determinantes(self):
        m = self.p.parsear("1 2\n3 4")
        self.assertEqual(m, sp.Matrix([[1, 2], [3, 4]]))
        d = self.p.parsear("det([[1, 2], [3, 4]])")
        self.assertIsInstance(d, DeterminanteSimbolico)

    def test_sugerencias_funciones_mal_escritas(self):
        for entrada, sug in [("xsin(x)", "x*sin(x)"), ("sinx", "sin(x)"), ("3+lnx", "ln(x)")]:
            with self.subTest(entrada=entrada):
                with self.assertRaises(ValueError) as ctx:
                    self.p.parsear(entrada)
                self.assertIn(sug, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
