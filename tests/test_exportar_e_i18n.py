import io
import json
import os
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asistentes import REGISTRO_ASISTENTES
import catalogos
from documento import BloqueDocumento, DocumentoMatematico
import exportar
import i18n


class TestExportarAsistentesEI18n(unittest.TestCase):
    def setUp(self):
        i18n.establecer_idioma("es")

    def test_mathml_es_xml_valido_sin_mfenced(self):
        expresiones = [
            "(x^2 + 1)/(x - 3)",
            "x^2 - 4 < 0",
            "int(x*exp(x), x, 0, 1) = 1",
            "lim(sin(x)/x, x, 0) = 1",
            "det([[1, 2], [3, 4]]) = -2",
            "laplace(exp(2*t), t, s) = 1/(s - 2)",
        ]
        for expr in expresiones:
            with self.subTest(expr=expr):
                b = BloqueDocumento(tipo="expresion", contenido=expr)
                mml = exportar.mathml_bloque(b)
                self.assertNotIn("<mfenced", mml)
                ET.fromstring(mml)

    def test_exportar_docx_omml_y_todos_los_formatos(self):
        doc = DocumentoMatematico("Examen de Cálculo", "Agustin Romero")
        doc.agregar_texto("Problema 1")
        doc.agregar_expresion("int(x^2, x, 0, 1) = barrow(x^3/3, x, 0, 1)", comentario="Regla de Barrow")
        doc.agregar_expresion("laplace(exp(2*t), t, s) = 1/(s - 2)")
        doc.agregar_expresion("ilaplace(1/(s - 2), s, t) = exp(2*t)")
        doc.agregar_expresion("sin(x) - 2*ln(x) + factorial(n) = 0")
        doc.agregar_sistema(["x + y = 10", "x - y = 2"])
        doc.agregar_matriz("1 2\n3 4", es_determinante=True)

        for fmt in ("txt", "md", "tex", "html", "ema"):
            salida = exportar.exportar(doc, fmt)
            self.assertTrue(len(salida) > 50)

        docx_bytes = exportar.a_docx_bytes(doc)
        with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
            self.assertIn("word/document.xml", zf.namelist())
            xml_word = zf.read("word/document.xml").decode("utf-8")
            self.assertIn("<m:oMathPara>", xml_word)
            self.assertIn("<m:nary>", xml_word)
            self.assertIn("<m:sSubSup>", xml_word)
            self.assertNotIn("barrow(", xml_word)
            self.assertNotIn("laplace(", xml_word)
            ET.fromstring(xml_word)

    def test_todos_los_asistentes_construyen_bloques_validos(self):
        ejemplos = {
            "fraccion": {"numerador": "x^2 + 1", "denominador": "x - 1"},
            "potencia": {"base": "x + 1", "exponente": "3"},
            "raiz": {"radicando": "x^2 + 4", "indice": "3"},
            "ecuacion": {"izquierda": "2*x + 1", "operador": "<=", "derecha": "9"},
            "sistema": {"ecuaciones": "x + y = 5\nx - y = 1"},
            "matriz": {"filas": "1 2\n3 4"},
            "determinante": {"filas": "1 2\n3 4"},
            "limite": {"expresion": "sin(x)/x", "variable": "x", "tendencia": "0+"},
            "derivada": {"expresion": "x^3*sin(x)", "variable": "x", "orden": "2"},
            "integral": {"integrando": "x*exp(x)", "variable": "x"},
            "integral_definida": {"integrando": "x^2", "variable": "x", "inferior": "0", "superior": "1"},
            "barrow": {"primitiva": "x^3/3", "variable": "x", "inferior": "0", "superior": "1"},
            "sumatoria": {"termino": "x^k/factorial(k)", "indice": "k", "inferior": "0", "superior": "n"},
            "edo": {"ecuacion": "y' + 2*x*y = 0", "condiciones": "y(0) = 3"},
            "laplace": {"expresion": "exp(2*t)", "var_origen": "t", "var_destino": "s"},
            "ilaplace": {"expresion": "1/(s - 2)", "var_origen": "s", "var_destino": "t"},
        }
        atajos = [a.atajo.lower() for a in REGISTRO_ASISTENTES if a.atajo]
        self.assertEqual(len(atajos), len(set(atajos)), "Hay atajos repetidos en REGISTRO_ASISTENTES")
        for asist in REGISTRO_ASISTENTES:
            with self.subTest(clave=asist.clave):
                tipo, contenido, subtipo = asist.constructor(ejemplos[asist.clave])
                bloque = BloqueDocumento(tipo=tipo, contenido=contenido, subtipo=subtipo)
                ok, err = bloque.es_valido()
                self.assertTrue(ok, err)

    def test_catalogos_es_y_en_completos(self):
        marcados = catalogos.textos_marcados()
        with open(os.path.join(catalogos.RAIZ, "locales", "es.json"), encoding="utf-8") as f:
            es = json.load(f)
        with open(os.path.join(catalogos.RAIZ, "locales", "en.json"), encoding="utf-8") as f:
            en = json.load(f)
        self.assertEqual(set(es.keys()), marcados)
        self.assertEqual(set(en.keys()), marcados)
        for k in marcados:
            self.assertEqual(catalogos.marcadores(k), catalogos.marcadores(en[k]))


if __name__ == "__main__":
    unittest.main()
