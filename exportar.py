"""
Exportación de documentos y bloques del Editor Matemático Accesible.

Formatos soportados:
- `html`: Página HTML5 accesible con fórmulas MathML de presentación válidas en XML
  (sin `<mfenced>`, con entidades numéricas y `alttext` verbalizado) para NVDA + MathCAT o JAWS.
- `docx`: Documento de Microsoft Word (`.docx`) con ecuaciones nativas de Word (OMML:
  `<m:oMathPara><m:oMath>...</m:oMath></m:oMathPara>`), para entregar deberes o exámenes
  a docentes videntes sin tener que usar nunca el editor de ecuaciones de Word.
- `tex`: Documento LaTeX completo listo para compilar con `pdflatex`, `xelatex` o `lualatex`.
- `md`: Documento Markdown con bloques `$$...$$`.
- `txt`: Informe en texto plano accesible con la expresión lineal y su lectura verbalizada.
- `ema`: Archivo nativo JSON del Editor Matemático Accesible.
"""
from __future__ import annotations

import html
import io
import re
from typing import Any, List
import zipfile

import sympy
from sympy.core.function import AppliedUndef
from sympy.core.relational import Relational

from _version import __version__
from configuracion import LECTURA_DETALLADA
from documento import (
    TIPO_SISTEMA,
    TIPO_TEXTO,
    BloqueDocumento,
    DocumentoMatematico,
)
from i18n import N_, idioma_actual, tr
from parser_matematico import (
    DeterminanteSimbolico,
    EvaluacionBarrow,
    TransformadaInversaLaplace,
    TransformadaLaplace,
)
from verbalizador import (
    _es_raiz,
    _separar_fraccion_sin_evaluar,
    texto_lineal,
)

FORMATOS = {
    "html": (N_("HTML con fórmulas MathML (accesible)"), "html"),
    "docx": (N_("Documento de Word con ecuaciones nativas (.docx)"), "docx"),
    "tex": (N_("Documento LaTeX (.tex)"), "tex"),
    "md": (N_("Markdown (.md)"), "md"),
    "txt": (N_("Texto plano accesible (.txt)"), "txt"),
    "ema": (N_("Documento del Editor Matemático (.ema)"), "ema"),
}


def _escapar_latex(texto: str) -> str:
    reemplazos = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "&": r"\&",
        "#": r"\#",
        "_": r"\_",
        "%": r"\%",
        "^": r"\^{}",
        "~": r"\~{}",
    }
    return "".join(reemplazos.get(c, c) for c in texto)


def latex_de_objeto(obj: Any) -> str:
    """Convierte un objeto SymPy (incluidos constructores propios del editor) a LaTeX."""
    if isinstance(obj, DeterminanteSimbolico) and isinstance(obj.args[0], sympy.MatrixBase):
        mat = obj.args[0]
        filas = [r" & ".join(latex_de_objeto(mat[i, j]) for j in range(mat.cols)) for i in range(mat.rows)]
        return r"\begin{vmatrix} " + r" \\ ".join(filas) + r" \end{vmatrix}"
    if isinstance(obj, EvaluacionBarrow):
        f, x, a, b = obj.args
        return rf"\left[ {latex_de_objeto(f)} \right]_{{{latex_de_objeto(x)}={latex_de_objeto(a)}}}^{{{latex_de_objeto(b)}}}"
    if isinstance(obj, TransformadaLaplace):
        f, _, s = obj.args
        return rf"\mathcal{{L}}\left\{{{latex_de_objeto(f)}\right\}}\left({latex_de_objeto(s)}\right)"
    if isinstance(obj, TransformadaInversaLaplace):
        F, _, t = obj.args
        return rf"\mathcal{{L}}^{{-1}}\left\{{{latex_de_objeto(F)}\right\}}\left({latex_de_objeto(t)}\right)"
    if isinstance(obj, Relational):
        ops = {
            sympy.Eq: "=",
            sympy.Le: r"\le",
            sympy.Ge: r"\ge",
            sympy.Lt: "<",
            sympy.Gt: ">",
            sympy.Ne: r"\ne",
        }
        op = ops.get(type(obj), "=")
        return f"{latex_de_objeto(obj.lhs)} {op} {latex_de_objeto(obj.rhs)}"
    return sympy.latex(obj)


def latex_bloque(bloque: BloqueDocumento) -> str:
    """Devuelve la representación LaTeX de un bloque matemático."""
    if bloque.tipo == TIPO_TEXTO:
        return _escapar_latex(bloque.contenido)
    obj = bloque.objeto_sympy()
    if bloque.tipo == TIPO_SISTEMA and isinstance(obj, list):
        filas = [latex_de_objeto(ec) for ec in obj]
        return r"\begin{cases} " + r" \\ ".join(filas) + r" \end{cases}"
    return latex_de_objeto(obj)


def _sin_mfenced(mathml: str) -> str:
    """Sustituye `<mfenced>` por `<mrow><mo>(</mo>...<mo>)</mo></mrow>` (MathML Core)."""
    pila: List[str] = []

    def reemplazar(m: re.Match) -> str:
        if m.group(0).startswith("</"):
            return f"<mo>{pila.pop()}</mo></mrow>"
        attrs = m.group(1) or ""
        abre = re.search(r'open="([^"]*)"', attrs)
        cierra = re.search(r'close="([^"]*)"', attrs)
        pila.append(html.escape(cierra.group(1) if cierra else ")"))
        return f"<mrow><mo>{html.escape(abre.group(1) if abre else '(')}</mo>"

    return re.sub(r"<mfenced([^>]*)>|</mfenced>", reemplazar, mathml)


def _entidades_numericas(marcado: str) -> str:
    """Convierte entidades con nombre (&pi;) a numéricas (&#x3C0;) para que el MathML sea XML válido."""
    def convertir(m: re.Match) -> str:
        caracteres = html.unescape(m.group(0))
        if caracteres == m.group(0):
            return m.group(0)
        return "".join(f"&#x{ord(c):X};" for c in caracteres)

    return re.sub(r"&(?!#)[A-Za-z][A-Za-z0-9]*;", convertir, marcado)


def _escapar_comparadores_en_mo(marcado: str) -> str:
    """Escapa `<` y `>` crudos que SymPy deja dentro de `<mo><</mo>` en desigualdades estrictas."""
    return marcado.replace("<mo><</mo>", "<mo>&lt;</mo>").replace("<mo>></mo>", "<mo>&gt;</mo>")


def _mathml_interno(obj: Any) -> str:
    if isinstance(obj, DeterminanteSimbolico) and isinstance(obj.args[0], sympy.MatrixBase):
        mat = obj.args[0]
        filas = "".join(
            "<mtr>" + "".join(f"<mtd>{_mathml_interno(mat[i, j])}</mtd>" for j in range(mat.cols)) + "</mtr>"
            for i in range(mat.rows)
        )
        return f"<mrow><mo>|</mo><mtable>{filas}</mtable><mo>|</mo></mrow>"
    if isinstance(obj, EvaluacionBarrow):
        f, x, a, b = obj.args
        return (
            f"<msubsup><mrow><mo>[</mo>{_mathml_interno(f)}<mo>]</mo></mrow>"
            f"<mrow>{_mathml_interno(x)}<mo>=</mo>{_mathml_interno(a)}</mrow>"
            f"<mrow>{_mathml_interno(b)}</mrow></msubsup>"
        )
    if isinstance(obj, TransformadaLaplace):
        f, _, s = obj.args
        return f"<mrow><mi>L</mi><mo>{{</mo>{_mathml_interno(f)}<mo>}}</mo><mo>(</mo>{_mathml_interno(s)}<mo>)</mo></mrow>"
    if isinstance(obj, TransformadaInversaLaplace):
        F, _, t = obj.args
        return (
            f"<mrow><msup><mi>L</mi><mrow><mo>-</mo><mn>1</mn></mrow></msup>"
            f"<mo>{{</mo>{_mathml_interno(F)}<mo>}}</mo><mo>(</mo>{_mathml_interno(t)}<mo>)</mo></mrow>"
        )
    bruto = sympy.mathml(obj, printer="presentation")
    return _entidades_numericas(_sin_mfenced(_escapar_comparadores_en_mo(bruto)))


def mathml_bloque(bloque: BloqueDocumento) -> str:
    """Genera un elemento `<math ...>` completo y válido como XML para un bloque."""
    if bloque.tipo == TIPO_TEXTO:
        return f"<p>{html.escape(bloque.contenido)}</p>"
    obj = bloque.objeto_sympy()
    if bloque.tipo == TIPO_SISTEMA and isinstance(obj, list):
        filas = "".join(f"<mtr><mtd>{_mathml_interno(ec)}</mtd></mtr>" for ec in obj)
        cuerpo = f"<mrow><mo>{{</mo><mtable>{filas}</mtable></mrow>"
    else:
        cuerpo = _mathml_interno(obj)
    alt = html.escape(bloque.lectura_accesible(modo=LECTURA_DETALLADA), quote=True)
    return (
        f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="block" alttext="{alt}">'
        f"<mrow>{cuerpo}</mrow></math>"
    )


NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _omml_run(texto: str) -> str:
    return f"<m:r><m:t>{html.escape(str(texto))}</m:t></m:r>"


def omml_de_objeto(expr: Any) -> str:
    if expr is None:
        return _omml_run("")

    if isinstance(expr, DeterminanteSimbolico) and isinstance(expr.args[0], sympy.MatrixBase):
        return _omml_matriz(expr.args[0], abre="|", cierra="|")
    if isinstance(expr, sympy.MatrixBase):
        return _omml_matriz(expr, abre="[", cierra="]")

    if isinstance(expr, Relational):
        ops = {
            sympy.Eq: "=",
            sympy.Le: "≤",
            sympy.Ge: "≥",
            sympy.Lt: "<",
            sympy.Gt: ">",
            sympy.Ne: "≠",
        }
        op = ops.get(type(expr), "=")
        return f"{omml_de_objeto(expr.lhs)}{_omml_run(op)}{omml_de_objeto(expr.rhs)}"

    if expr is sympy.oo:
        return _omml_run("∞")
    if expr == -sympy.oo:
        return _omml_run("-∞")
    if expr is sympy.pi:
        return _omml_run("π")
    if expr is sympy.E:
        return _omml_run("e")
    if isinstance(expr, (sympy.Symbol, sympy.Integer, sympy.Float)):
        return _omml_run(texto_lineal(expr))

    if isinstance(expr, sympy.Limit):
        fn, var, punto = expr.args[:3]
        dir_ = str(expr.args[3]) if len(expr.args) > 3 else "+-"
        sufijo = "⁺" if dir_ == "+" else ("⁻" if dir_ == "-" else "")
        sub = f"{omml_de_objeto(var)}{_omml_run('→')}{omml_de_objeto(punto)}{_omml_run(sufijo) if sufijo else ''}"
        return f"<m:limLow><m:e>{_omml_run('lim')}</m:e><m:lim>{sub}</m:lim></m:limLow>{omml_de_objeto(fn)}"

    if isinstance(expr, sympy.Derivative):
        fn = expr.expr
        var, orden = expr.variable_count[0] if expr.variable_count else (sympy.Symbol("x"), 1)
        n = int(orden)
        if isinstance(fn, AppliedUndef):
            primas = "'" * n
            return _omml_run(f"{fn.func.__name__}{primas}")
        num_d = _omml_run("d") if n == 1 else f"<m:sSup><m:e>{_omml_run('d')}</m:e><m:sup>{_omml_run(str(n))}</m:sup></m:sSup>"
        den_d = _omml_run(f"d{var}") if n == 1 else f"{_omml_run('d')}<m:sSup><m:e>{omml_de_objeto(var)}</m:e><m:sup>{_omml_run(str(n))}</m:sup></m:sSup>"
        frac_d = f"<m:f><m:num>{num_d}</m:num><m:den>{den_d}</m:den></m:f>"
        return f"{frac_d}<m:d><m:e>{omml_de_objeto(fn)}</m:e></m:d>"

    if isinstance(expr, sympy.Integral):
        fn = expr.function
        limites = expr.limits[0]
        var = limites[0]
        integrando_dx = f"{omml_de_objeto(fn)}{_omml_run(' d')}{omml_de_objeto(var)}"
        if len(limites) == 3:
            return (
                f"<m:nary><m:naryPr><m:chr m:val=\"∫\"/><m:limLoc m:val=\"subSup\"/></m:naryPr>"
                f"<m:sub>{omml_de_objeto(limites[1])}</m:sub>"
                f"<m:sup>{omml_de_objeto(limites[2])}</m:sup>"
                f"<m:e>{integrando_dx}</m:e></m:nary>"
            )
        return (
            f"<m:nary><m:naryPr><m:chr m:val=\"∫\"/><m:limLoc m:val=\"undOvr\"/></m:naryPr>"
            f"<m:sub/><m:sup/><m:e>{integrando_dx}</m:e></m:nary>"
        )

    if isinstance(expr, (sympy.Sum, sympy.Product)):
        simbolo = "∑" if isinstance(expr, sympy.Sum) else "∏"
        fn = expr.function
        var, inf, sup = expr.limits[0]
        return (
            f"<m:nary><m:naryPr><m:chr m:val=\"{simbolo}\"/><m:limLoc m:val=\"undOvr\"/></m:naryPr>"
            f"<m:sub>{omml_de_objeto(var)}{_omml_run('=')}{omml_de_objeto(inf)}</m:sub>"
            f"<m:sup>{omml_de_objeto(sup)}</m:sup>"
            f"<m:e>{omml_de_objeto(fn)}</m:e></m:nary>"
        )

    datos_raiz = _es_raiz(expr)
    if datos_raiz is not None:
        radicando, indice = datos_raiz
        if indice == 2:
            return f"<m:rad><m:radPr><m:degHide m:val=\"1\"/></m:radPr><m:deg/><m:e>{omml_de_objeto(radicando)}</m:e></m:rad>"
        return f"<m:rad><m:deg>{omml_de_objeto(indice)}</m:deg><m:e>{omml_de_objeto(radicando)}</m:e></m:rad>"

    num, den = _separar_fraccion_sin_evaluar(expr)
    if den != 1:
        return f"<m:f><m:num>{omml_de_objeto(num)}</m:num><m:den>{omml_de_objeto(den)}</m:den></m:f>"

    if isinstance(expr, sympy.Pow):
        base, exp = expr.args
        base_omml = f"<m:d><m:e>{omml_de_objeto(base)}</m:e></m:d>" if isinstance(base, (sympy.Add, sympy.Mul, Relational)) else omml_de_objeto(base)
        return f"<m:sSup><m:e>{base_omml}</m:e><m:sup>{omml_de_objeto(exp)}</m:sup></m:sSup>"

    if isinstance(expr, sympy.exp):
        return f"<m:sSup><m:e>{_omml_run('e')}</m:e><m:sup>{omml_de_objeto(expr.args[0])}</m:sup></m:sSup>"

    if isinstance(expr, sympy.Abs):
        return f"<m:d><m:dPr><m:begChr m:val=\"|\"/><m:endChr m:val=\"|\"/></m:dPr><m:e>{omml_de_objeto(expr.args[0])}</m:e></m:d>"

    if isinstance(expr, sympy.Add):
        partes = []
        for idx, t in enumerate(expr.args):
            txt_t = texto_lineal(t)
            if idx > 0 and not txt_t.startswith("-"):
                partes.append(_omml_run("+"))
            partes.append(omml_de_objeto(t))
        return "".join(partes)

    if isinstance(expr, sympy.Mul):
        partes_mul = []
        for f in expr.args:
            if isinstance(f, sympy.Add):
                partes_mul.append(f"<m:d><m:e>{omml_de_objeto(f)}</m:e></m:d>")
            else:
                partes_mul.append(omml_de_objeto(f))
        return _omml_run("·").join(partes_mul)

    return _omml_run(texto_lineal(expr))


def _omml_matriz(mat: sympy.MatrixBase, abre: str = "[", cierra: str = "]") -> str:
    filas = "".join(
        "<m:mr>" + "".join(f"<m:e>{omml_de_objeto(mat[i, j])}</m:e>" for j in range(mat.cols)) + "</m:mr>"
        for i in range(mat.rows)
    )
    return (
        f"<m:d><m:dPr><m:begChr m:val=\"{html.escape(abre)}\"/><m:endChr m:val=\"{html.escape(cierra)}\"/></m:dPr>"
        f"<m:e><m:m>{filas}</m:m></m:e></m:d>"
    )


def omml_bloque(bloque: BloqueDocumento) -> str:
    obj = bloque.objeto_sympy()
    if bloque.tipo == TIPO_SISTEMA and isinstance(obj, list):
        filas = "".join(f"<m:mr><m:e>{omml_de_objeto(ec)}</m:e></m:mr>" for ec in obj)
        cuerpo = (
            f"<m:d><m:dPr><m:begChr m:val=\"{{\" /><m:endChr m:val=\"\"/></m:dPr>"
            f"<m:e><m:m>{filas}</m:m></m:e></m:d>"
        )
    else:
        cuerpo = omml_de_objeto(obj)
    return f"<m:oMathPara><m:oMath>{cuerpo}</m:oMath></m:oMathPara>"


def a_texto(doc: DocumentoMatematico) -> str:
    lineas = [
        doc.titulo,
        "=" * max(len(doc.titulo), 20),
    ]
    if doc.autor:
        lineas.append(f"{tr('Autor')}: {doc.autor}")
    lineas.append(f"{tr('Fecha')}: {doc.fecha}")
    lineas.append("")

    for idx, b in enumerate(doc.bloques(), 1):
        if b.tipo == TIPO_TEXTO:
            lineas.append(f"{idx}. {b.contenido}")
        else:
            lineas.append(f"{idx}. [{b.nombre_tipo()}] {b.contenido}")
            lineas.append(f"   {tr('Lectura')}: {b.lectura_accesible(modo=LECTURA_DETALLADA)}")
            if b.comentario:
                lineas.append(f"   {tr('Justificación')}: {b.comentario}")
        lineas.append("")

    lineas.append(tr("Generado por Editor Matemático Accesible {version}", version=__version__))
    return "\n".join(lineas).rstrip() + "\n"


def a_markdown(doc: DocumentoMatematico) -> str:
    lineas = [f"# {doc.titulo}", ""]
    if doc.autor:
        lineas.append(f"**{tr('Autor')}:** {doc.autor}  ")
    lineas.append(f"**{tr('Fecha')}:** {doc.fecha}")
    lineas.append("")

    for idx, b in enumerate(doc.bloques(), 1):
        if b.tipo == TIPO_TEXTO:
            lineas.append(b.contenido)
            lineas.append("")
        else:
            lineas.append("$$")
            lineas.append(latex_bloque(b))
            lineas.append("$$")
            if b.comentario:
                lineas.append(f"> *{tr('Justificación')} ({tr('Paso {n}', n=idx)}):* {b.comentario}")
            lineas.append("")

    lineas.append(f"_{tr('Generado por Editor Matemático Accesible {version}', version=__version__)}_")
    return "\n".join(lineas).rstrip() + "\n"


def a_latex(doc: DocumentoMatematico) -> str:
    lineas = [
        "% " + tr("Generado por Editor Matemático Accesible {version}", version=__version__),
        r"\documentclass[12pt]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath,amssymb}",
        r"\title{" + _escapar_latex(doc.titulo) + "}",
        r"\author{" + _escapar_latex(doc.autor) + "}",
        r"\date{" + _escapar_latex(doc.fecha) + "}",
        r"\begin{document}",
        r"\maketitle",
        "",
    ]

    for b in doc.bloques():
        if b.tipo == TIPO_TEXTO:
            lineas.append(_escapar_latex(b.contenido))
            lineas.append("")
        else:
            lineas.append(r"\begin{equation*}")
            lineas.append(latex_bloque(b))
            lineas.append(r"\end{equation*}")
            if b.comentario:
                lineas.append(r"\noindent\textit{" + _escapar_latex(b.comentario) + r"}\medskip")
            lineas.append("")

    lineas.append(r"\end{document}")
    return "\n".join(lineas) + "\n"


def a_html(doc: DocumentoMatematico) -> str:
    e = html.escape
    lang = idioma_actual()
    partes = [
        "<!DOCTYPE html>",
        f'<html lang="{e(lang)}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{e(doc.titulo)}</title>",
        "<style>"
        "body{font-family:sans-serif;max-width:52rem;margin:1.5rem auto;padding:0 1rem;line-height:1.6;color:#111}"
        ".paso{margin:1rem 0;padding:0.75rem 1rem;background:#f8f9fa;border-left:4px solid #2b579a;border-radius:4px}"
        ".comentario{color:#444;font-style:italic;margin-top:0.4rem}"
        "math{font-size:1.3em}"
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        f"<h1>{e(doc.titulo)}</h1>",
    ]
    if doc.autor:
        partes.append(f"<p><strong>{e(tr('Autor'))}:</strong> {e(doc.autor)}</p>")
    partes.append(f"<p><strong>{e(tr('Fecha'))}:</strong> {e(doc.fecha)}</p>")

    for idx, b in enumerate(doc.bloques(), 1):
        if b.tipo == TIPO_TEXTO:
            partes.append(f"<p>{e(b.contenido)}</p>")
        else:
            partes.append(f'<section class="paso" aria-label="{e(tr("Paso {n}", n=idx))}">')
            partes.append(mathml_bloque(b))
            if b.comentario:
                partes.append(f'<p class="comentario">{e(b.comentario)}</p>')
            partes.append("</section>")

    partes += [
        "</main>",
        f"<footer><p>{e(tr('Generado por Editor Matemático Accesible {version}', version=__version__))} — {e(doc.fecha)}</p></footer>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(partes)


def a_docx_bytes(doc: DocumentoMatematico) -> bytes:
    parrafos = [
        f'<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>'
        f'<w:r><w:rPr><w:b/><w:sz w:val="36"/></w:rPr><w:t>{html.escape(doc.titulo)}</w:t></w:r></w:p>'
    ]
    if doc.autor:
        parrafos.append(
            f"<w:p><w:r><w:t>{html.escape(tr('Autor'))}: {html.escape(doc.autor)}</w:t></w:r></w:p>"
        )
    parrafos.append(
        f"<w:p><w:r><w:t>{html.escape(tr('Fecha'))}: {html.escape(doc.fecha)}</w:t></w:r></w:p>"
    )

    for b in doc.bloques():
        if b.tipo == TIPO_TEXTO:
            parrafos.append(f"<w:p><w:r><w:t>{html.escape(b.contenido)}</w:t></w:r></w:p>")
        else:
            parrafos.append(f"<w:p>{omml_bloque(b)}</w:p>")
            if b.comentario:
                parrafos.append(
                    f"<w:p><w:r><w:rPr><w:i/></w:rPr><w:t>{html.escape(b.comentario)}</w:t></w:r></w:p>"
                )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{NS_W}" xmlns:m="{NS_M}">'
        "<w:body>"
        + "".join(parrafos)
        + "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/><w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/></w:sectPr>"
        "</w:body></w:document>"
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


CONVERSORES_TEXTO = {
    "txt": a_texto,
    "md": a_markdown,
    "tex": a_latex,
    "html": a_html,
    "ema": lambda doc: doc.a_json(),
}


def exportar(doc: DocumentoMatematico, formato: str) -> str:
    if formato not in CONVERSORES_TEXTO:
        raise ValueError(f"Formato de texto no soportado: {formato}")
    return CONVERSORES_TEXTO[formato](doc)


def guardar(doc: DocumentoMatematico, formato: str, ruta: str) -> None:
    if formato == "docx":
        with open(ruta, "wb") as f:
            f.write(a_docx_bytes(doc))
        return
    contenido = exportar(doc, formato)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenido)
