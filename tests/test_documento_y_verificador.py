import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from documento import DocumentoMatematico
import verificador


class TestDocumentoYVerificador(unittest.TestCase):
    def test_guardar_y_cargar_ema(self):
        doc = DocumentoMatematico("Deber de Álgebra", "Agustin")
        doc.agregar_texto("Resolver la ecuación:")
        doc.agregar_expresion("2*(x + 3) = 14", comentario="Planteamiento")
        doc.agregar_expresion("2*x + 6 = 14", comentario="Propiedad distributiva")
        doc.agregar_expresion("x = 4", comentario="Solución")

        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "deber.ema")
            doc.guardar_archivo(ruta)
            recuperado = DocumentoMatematico.cargar_archivo(ruta)
            self.assertEqual(recuperado.titulo, "Deber de Álgebra")
            self.assertEqual(len(recuperado), 4)
            self.assertEqual(recuperado.obtener(2).contenido, "2*x + 6 = 14")

    def test_verificador_detecta_pasos_correctos_e_incorrectos(self):
        doc = DocumentoMatematico("Prueba Verificador")
        doc.agregar_expresion("2*(x + 1) = 10")
        doc.agregar_expresion("2*x + 2 = 10")
        doc.agregar_expresion("x = 4")
        resultados = verificador.verificar_documento_completo(doc)
        self.assertTrue(all(r.es_valido for r in resultados))

        doc.agregar_expresion("x = 6")
        res_err = verificador.verificar_en_documento(doc, 3)
        self.assertFalse(res_err.es_valido)

    def test_verificador_inecuaciones_integrales_edo_y_matrices(self):
        doc_int = DocumentoMatematico()
        doc_int.agregar_expresion("int(3*x^2, x)")
        doc_int.agregar_expresion("x^3 + C")
        self.assertTrue(verificador.verificar_en_documento(doc_int, 1).es_valido)

        doc_edo = DocumentoMatematico()
        doc_edo.agregar_expresion("y' = 2*x*y")
        doc_edo.agregar_expresion("y = C*exp(x^2)")
        self.assertTrue(verificador.verificar_en_documento(doc_edo, 1).es_valido)

        doc_mat = DocumentoMatematico()
        doc_mat.agregar_matriz("1 1 10\n1 -1 2")
        doc_mat.agregar_matriz("1 0 6\n0 1 4")
        self.assertTrue(verificador.verificar_en_documento(doc_mat, 1).es_valido)


if __name__ == "__main__":
    unittest.main()
