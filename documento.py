"""
Modelo del documento matemático accesible (`DocumentoMatematico` y `BloqueDocumento`).

En lugar de un lienzo visual desestructurado donde el lector de pantalla pierde la
referencia entre texto y fórmulas, un documento del Editor Matemático es una secuencia
ordenada de bloques navegables con las flechas Arriba/Abajo:

- `"texto"`: título, enunciado de un problema o justificación escrita por el estudiante.
- `"expresion"`: expresión algebraica, igualdad, ecuación, inecuación, límite, derivada,
  integral indefinida o definida, polinomio de Taylor, sumatoria, ecuación diferencial
  o transformada de Laplace.
- `"sistema"`: sistema de ecuaciones o problema de valor inicial (una ecuación por línea
  o separadas por punto y coma).
- `"matriz"`: matriz o determinante editable por filas y columnas `(i, j)`.

Se guarda y carga en formato `.ema` (JSON UTF-8 estructurado y legible).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from _version import __version__
from configuracion import LECTURA_DETALLADA
from i18n import N_, tr
from parser_matematico import DeterminanteSimbolico, ParserMatematico
from verbalizador import (
    NodoEstructura,
    inspeccionar,
    verbalizar_objeto,
    verbalizar_sistema,
)

TIPO_TEXTO = "texto"
TIPO_EXPRESION = "expresion"
TIPO_SISTEMA = "sistema"
TIPO_MATRIZ = "matriz"

TIPOS_BLOQUE = {
    TIPO_TEXTO: N_("Texto o nota"),
    TIPO_EXPRESION: N_("Fórmula o paso matemático"),
    TIPO_SISTEMA: N_("Sistema de ecuaciones / PVI"),
    TIPO_MATRIZ: N_("Matriz o determinante"),
}

_PARSER = ParserMatematico()


@dataclass
class BloqueDocumento:
    """
    Una línea o paso dentro de un `DocumentoMatematico`.
    """
    tipo: str                                  # uno de TIPOS_BLOQUE
    contenido: str                             # lo que escribió el usuario
    comentario: str = ""                       # justificación opcional del paso ("Aplicamos regla de Barrow")
    subtipo: str = ""                          # para TIPO_MATRIZ: "matriz" o "determinante"

    def __post_init__(self):
        if self.tipo not in TIPOS_BLOQUE:
            raise ValueError(tr("Tipo de bloque desconocido: {tipo}", tipo=self.tipo))
        self.contenido = self.contenido.strip()
        self.comentario = self.comentario.strip()
        if self.tipo == TIPO_MATRIZ and not self.subtipo:
            self.subtipo = "determinante" if self.contenido.lower().startswith("det(") else "matriz"

    def nombre_tipo(self) -> str:
        if self.tipo == TIPO_MATRIZ and self.subtipo == "determinante":
            return tr("Determinante")
        return tr(TIPOS_BLOQUE[self.tipo])

    def objeto_sympy(self) -> Any:
        if self.tipo == TIPO_TEXTO:
            return None
        if self.tipo == TIPO_SISTEMA:
            lineas = [l.strip() for l in re.split(r"[\n;]+", self.contenido) if l.strip()]
            if not lineas:
                raise ValueError(tr("El sistema está vacío."))
            return [_PARSER.parsear(l) for l in lineas]
        if self.tipo == TIPO_MATRIZ:
            if self.contenido.lower().startswith("det("):
                return _PARSER.parsear(self.contenido)
            mat = _PARSER.parsear_matriz(self.contenido)
            return DeterminanteSimbolico(mat) if self.subtipo == "determinante" else mat
        return _PARSER.parsear(self.contenido)

    def es_valido(self) -> Tuple[bool, str]:
        if self.tipo == TIPO_TEXTO:
            return (bool(self.contenido), "" if self.contenido else tr("El bloque de texto está vacío."))
        try:
            self.objeto_sympy()
            return True, ""
        except Exception as e:
            return False, str(e)

    def lectura_accesible(self, indice: Optional[int] = None, modo: str = LECTURA_DETALLADA) -> str:
        prefijo = tr("Paso {n}", n=indice) + f" ({self.nombre_tipo()}): " if indice is not None else ""
        if self.tipo == TIPO_TEXTO:
            cuerpo = self.contenido or tr("Texto vacío")
        else:
            try:
                obj = self.objeto_sympy()
                if self.tipo == TIPO_SISTEMA:
                    cuerpo = verbalizar_sistema(obj, modo=modo)
                else:
                    cuerpo = verbalizar_objeto(obj, modo=modo)
            except Exception as e:
                cuerpo = tr("Error de sintaxis en '{contenido}': {error}", contenido=self.contenido, error=str(e))

        if self.comentario:
            cuerpo += f" — {tr('Justificación')}: {self.comentario}"
        return prefijo + cuerpo

    def resumen_visual(self, indice: Optional[int] = None) -> str:
        num = f"{indice}. " if indice is not None else ""
        contenido_una_linea = self.contenido.replace("\n", "; ")
        nota = f"  [{self.comentario}]" if self.comentario else ""
        return f"{num}[{self.nombre_tipo()}] {contenido_una_linea}{nota}"

    def arbol_estructura(self) -> NodoEstructura:
        if self.tipo == TIPO_TEXTO:
            return NodoEstructura(tr("Texto"), self.contenido, self.contenido, ())
        obj = self.objeto_sympy()
        if self.tipo == TIPO_SISTEMA:
            hijos = tuple(
                inspeccionar(ec, etiqueta_raiz=tr("Ecuación {n}", n=i))
                for i, ec in enumerate(obj, 1)
            )
            return NodoEstructura(
                tr("Sistema ({n} ecuaciones)", n=len(obj)),
                self.contenido.replace("\n", "; "),
                verbalizar_sistema(obj),
                hijos,
            )
        return inspeccionar(obj)

    def a_diccionario(self) -> Dict[str, Any]:
        datos: Dict[str, Any] = {
            "type": self.tipo,
            "content": self.contenido,
        }
        if self.comentario:
            datos["comment"] = self.comentario
        if self.subtipo:
            datos["subtype"] = self.subtipo
        return datos

    @classmethod
    def desde_diccionario(cls, datos: Dict[str, Any]) -> "BloqueDocumento":
        return cls(
            tipo=datos.get("type", TIPO_EXPRESION),
            contenido=datos.get("content", ""),
            comentario=datos.get("comment", ""),
            subtipo=datos.get("subtype", ""),
        )


class DocumentoMatematico:
    def __init__(self, titulo: str = "", autor: str = "", bloques: Optional[List[BloqueDocumento]] = None):
        self.titulo = titulo.strip() or tr("Documento sin título")
        self.autor = autor.strip()
        self.fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._bloques: List[BloqueDocumento] = list(bloques) if bloques else []
        self.modificado: bool = False
        self.ruta_archivo: Optional[str] = None

    def __len__(self) -> int:
        return len(self._bloques)

    def bloques(self) -> List[BloqueDocumento]:
        return list(self._bloques)

    def obtener(self, indice: int) -> BloqueDocumento:
        return self._bloques[indice]

    def agregar(
        self,
        contenido: str,
        tipo: str = TIPO_EXPRESION,
        comentario: str = "",
        subtipo: str = "",
        indice: Optional[int] = None,
    ) -> BloqueDocumento:
        bloque = BloqueDocumento(tipo=tipo, contenido=contenido, comentario=comentario, subtipo=subtipo)
        if indice is None or indice >= len(self._bloques):
            self._bloques.append(bloque)
        else:
            self._bloques.insert(max(0, indice), bloque)
        self.modificado = True
        return bloque

    def agregar_texto(self, texto: str, indice: Optional[int] = None) -> BloqueDocumento:
        return self.agregar(texto, tipo=TIPO_TEXTO, indice=indice)

    def agregar_expresion(self, expresion: str, comentario: str = "", indice: Optional[int] = None) -> BloqueDocumento:
        return self.agregar(expresion, tipo=TIPO_EXPRESION, comentario=comentario, indice=indice)

    def agregar_sistema(
        self, ecuaciones: List[str] | str, comentario: str = "", indice: Optional[int] = None
    ) -> BloqueDocumento:
        txt = "\n".join(ecuaciones) if isinstance(ecuaciones, (list, tuple)) else ecuaciones
        return self.agregar(txt, tipo=TIPO_SISTEMA, comentario=comentario, indice=indice)

    def agregar_matriz(
        self, filas: str, es_determinante: bool = False, comentario: str = "", indice: Optional[int] = None
    ) -> BloqueDocumento:
        sub = "determinante" if es_determinante else "matriz"
        return self.agregar(filas, tipo=TIPO_MATRIZ, comentario=comentario, subtipo=sub, indice=indice)

    def actualizar(
        self,
        indice: int,
        contenido: Optional[str] = None,
        tipo: Optional[str] = None,
        comentario: Optional[str] = None,
        subtipo: Optional[str] = None,
    ) -> BloqueDocumento:
        actual = self._bloques[indice]
        nuevo = BloqueDocumento(
            tipo=tipo if tipo is not None else actual.tipo,
            contenido=contenido if contenido is not None else actual.contenido,
            comentario=comentario if comentario is not None else actual.comentario,
            subtipo=subtipo if subtipo is not None else actual.subtipo,
        )
        self._bloques[indice] = nuevo
        self.modificado = True
        return nuevo

    def eliminar(self, indice: int) -> BloqueDocumento:
        eliminado = self._bloques.pop(indice)
        self.modificado = True
        return eliminado

    def mover(self, origen: int, destino: int) -> int:
        if not (0 <= origen < len(self._bloques)):
            raise IndexError("Índice de origen fuera de rango.")
        destino = max(0, min(len(self._bloques) - 1, destino))
        if origen == destino:
            return origen
        bloque = self._bloques.pop(origen)
        self._bloques.insert(destino, bloque)
        self.modificado = True
        return destino

    def duplicar(self, indice: int) -> BloqueDocumento:
        orig = self._bloques[indice]
        return self.agregar(
            contenido=orig.contenido,
            tipo=orig.tipo,
            comentario=orig.comentario,
            subtipo=orig.subtipo,
            indice=indice + 1,
        )

    def limpiar(self) -> None:
        self._bloques.clear()
        self.modificado = True

    def a_json(self) -> str:
        datos = {
            "application": "Editor Matemático Accesible",
            "version": __version__,
            "title": self.titulo,
            "author": self.autor,
            "date": self.fecha,
            "blocks": [b.a_diccionario() for b in self._bloques],
        }
        return json.dumps(datos, ensure_ascii=False, indent=2) + "\n"

    def guardar_archivo(self, ruta: str) -> None:
        with open(ruta, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.a_json())
        self.ruta_archivo = ruta
        self.modificado = False

    @classmethod
    def cargar_archivo(cls, ruta: str) -> "DocumentoMatematico":
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if not isinstance(datos, dict) or "blocks" not in datos:
            raise ValueError(tr("El archivo no es un documento válido del Editor Matemático (.ema)."))
        bloques = [BloqueDocumento.desde_diccionario(b) for b in datos.get("blocks", [])]
        doc = cls(
            titulo=datos.get("title", ""),
            autor=datos.get("author", ""),
            bloques=bloques,
        )
        if datos.get("date"):
            doc.fecha = str(datos["date"])
        doc.ruta_archivo = ruta
        doc.modificado = False
        return doc
