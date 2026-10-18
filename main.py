"""
Interfaz gráfica accesible en wxPython para el Editor Matemático Accesible.

Diseñada específicamente para personas que usan un lector de pantalla (NVDA / JAWS):
- `PanelEditorMatematico(wx.Panel)`: componente desacoplado que puede usarse dentro
  de esta aplicación independiente o integrarse directamente en `calculadora_accesible`.
- `VentanaEditorMatematico(wx.Frame)`: ventana principal con barra de menús completa
  (Archivo, Edición, Aritmética, Álgebra, Cálculo, Ecuaciones Diferenciales, Verificar,
  Opciones, Idioma y Ayuda).
- `DialogoInspectorEstructura(wx.Dialog)`: árbol (`wx.TreeCtrl`) navegable con las
  flechas para inspeccionar cada parte de la expresión actual (numerador, denominador,
  índice, radicando, límites de integración, lado izquierdo/derecho, fila/columna).
- `DialogoAsistente(wx.Dialog)`: diálogo accesible generado a partir de
  `asistentes.REGISTRO_ASISTENTES` para insertar fracciones, raíces, límites, derivadas,
  integrales, sumatorias, matrices, sistemas y EDO sin errores de paréntesis.
"""
from __future__ import annotations

import multiprocessing
import os
import threading
import time
import webbrowser
from typing import Optional

import wx

from _version import __version__
import actualizador
from asistentes import ASISTENTE_POR_CLAVE, REGISTRO_ASISTENTES, Asistente
import configuracion
from documento import (
    TIPO_EXPRESION,
    TIPOS_BLOQUE,
    BloqueDocumento,
    DocumentoMatematico,
)
import exportar
import i18n
from i18n import N_, tr
import verbalizador
from verbalizador import NodoEstructura
import verificador


def _limpiar_acelerador(etiqueta: str) -> str:
    return etiqueta.replace("&", "").rstrip(":").strip()


class DialogoInspectorEstructura(wx.Dialog):
    def __init__(self, parent: wx.Window, bloque: BloqueDocumento):
        super().__init__(
            parent,
            title=tr("Inspector de estructura matemática"),
            size=(680, 480),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.bloque = bloque
        self.expresion_seleccionada: Optional[str] = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_instrucciones = wx.StaticText(
            self,
            label=tr("Use las flechas Arriba/Abajo e Izquierda/Derecha para explorar cada parte de la fórmula:"),
        )
        sizer.Add(lbl_instrucciones, 0, wx.ALL, 8)

        self.arbol = wx.TreeCtrl(
            self,
            style=wx.TR_DEFAULT_STYLE | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT,
        )
        self.arbol.SetName(tr("Estructura de la expresión"))
        sizer.Add(self.arbol, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        lbl_detalle_txt = tr("&Detalle de la parte seleccionada:")
        lbl_detalle = wx.StaticText(self, label=lbl_detalle_txt)
        sizer.Add(lbl_detalle, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.txt_detalle = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 90),
        )
        self.txt_detalle.SetName(_limpiar_acelerador(lbl_detalle_txt))
        sizer.Add(self.txt_detalle, 0, wx.EXPAND | wx.ALL, 8)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_copiar_parte = wx.Button(self, wx.ID_ANY, tr("&Copiar esta subexpresión"))
        self.btn_cerrar = wx.Button(self, wx.ID_CANCEL, tr("Ce&rrar"))
        btn_sizer.Add(self.btn_copiar_parte, 0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_cerrar, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        self.SetSizer(sizer)

        raiz_estructura = bloque.arbol_estructura()
        item_raiz = self._poblar_nodo(None, raiz_estructura)
        self.arbol.ExpandAll()
        self.arbol.SelectItem(item_raiz)

        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_seleccion_cambiada, self.arbol)
        self.Bind(wx.EVT_BUTTON, self.on_copiar_parte, self.btn_copiar_parte)
        self.arbol.SetFocus()

    def _poblar_nodo(self, padre, nodo: NodoEstructura):
        texto = nodo.texto_nodo()
        if padre is None:
            item = self.arbol.AddRoot(texto, data=nodo)
        else:
            item = self.arbol.AppendItem(padre, texto, data=nodo)
        for hijo in nodo.hijos:
            self._poblar_nodo(item, hijo)
        return item

    def on_seleccion_cambiada(self, event):
        item = event.GetItem()
        if not item.IsOk():
            return
        nodo: Optional[NodoEstructura] = self.arbol.GetItemData(item)
        if nodo is None:
            return
        self.expresion_seleccionada = nodo.expresion
        detalle = "\n".join([
            f"{tr('Parte')}: {nodo.etiqueta}",
            f"{tr('Lectura')}: {nodo.lectura}",
            f"{tr('Expresión lineal')}: {nodo.expresion}",
        ])
        self.txt_detalle.SetValue(detalle)

    def on_copiar_parte(self, event):
        if self.expresion_seleccionada:
            copiar_al_portapapeles(self.expresion_seleccionada)
            wx.MessageBox(
                tr("Subexpresión copiada al portapapeles: {expr}", expr=self.expresion_seleccionada),
                tr("Copiado"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )


class DialogoAsistente(wx.Dialog):
    def __init__(self, parent: wx.Window, asistente: Asistente):
        super().__init__(
            parent,
            title=tr("Asistente: {nombre}", nombre=tr(asistente.nombre)),
            size=(540, 420),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.asistente = asistente
        self.controles = {}
        self.resultado: Optional[tuple] = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        for campo in asistente.campos:
            etiqueta_tr = tr(campo.etiqueta)
            lbl = wx.StaticText(self, label=etiqueta_tr)
            sizer.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
            estilo = wx.TE_MULTILINE if campo.multilinea else 0
            ctrl = wx.TextCtrl(self, value=campo.valor_defecto, style=estilo, size=(-1, 80 if campo.multilinea else -1))
            ctrl.SetName(_limpiar_acelerador(etiqueta_tr))
            sizer.Add(ctrl, 1 if campo.multilinea else 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            self.controles[campo.clave] = ctrl

        lbl_previa_txt = tr("&Lectura accesible y verificación:")
        lbl_previa = wx.StaticText(self, label=lbl_previa_txt)
        sizer.Add(lbl_previa, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.txt_previa = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 60))
        self.txt_previa.SetName(_limpiar_acelerador(lbl_previa_txt))
        sizer.Add(self.txt_previa, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_probar = wx.Button(self, wx.ID_ANY, tr("&Escuchar lectura previa"))
        self.btn_aceptar = wx.Button(self, wx.ID_OK, tr("&Aceptar"))
        self.btn_cancelar = wx.Button(self, wx.ID_CANCEL, tr("&Cancelar"))
        self.btn_aceptar.SetDefault()

        btn_sizer.Add(self.btn_probar, 0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_aceptar, 0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_cancelar, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.SetSizerAndFit(sizer)
        self.SetMinSize((480, 320))

        self.Bind(wx.EVT_BUTTON, self.on_probar, self.btn_probar)
        self.Bind(wx.EVT_BUTTON, self.on_aceptar, self.btn_aceptar)

        if asistente.campos:
            self.controles[asistente.campos[0].clave].SetFocus()

    def _construir(self) -> Optional[tuple]:
        valores = {clave: ctrl.GetValue().strip() for clave, ctrl in self.controles.items()}
        for campo in self.asistente.campos:
            if not valores.get(campo.clave) and campo.clave != "condiciones":
                wx.MessageBox(
                    tr("Complete el campo: {campo}", campo=tr(campo.etiqueta)),
                    tr("Dato requerido"),
                    wx.OK | wx.ICON_WARNING,
                    self,
                )
                self.controles[campo.clave].SetFocus()
                return None
        tipo, contenido, subtipo = self.asistente.constructor(valores)
        bloque_prueba = BloqueDocumento(tipo=tipo, contenido=contenido, subtipo=subtipo)
        ok, err = bloque_prueba.es_valido()
        if not ok:
            wx.MessageBox(
                tr("Error de sintaxis en la expresión generada ({contenido}):\n{error}",
                   contenido=contenido, error=err),
                tr("Error de Validación"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return None
        return tipo, contenido, subtipo, bloque_prueba

    def on_probar(self, event):
        construido = self._construir()
        if construido is None:
            return
        _, contenido, _, bloque = construido
        self.txt_previa.SetValue(
            f"{tr('Lectura')}: {bloque.lectura_accesible()}\n{tr('Notación lineal')}: {contenido}"
        )
        self.txt_previa.SetFocus()

    def on_aceptar(self, event):
        construido = self._construir()
        if construido is None:
            return
        self.resultado = construido[:3]
        self.EndModal(wx.ID_OK)


def copiar_al_portapapeles(texto: str) -> bool:
    for _ in range(20):
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(texto))
                wx.TheClipboard.Flush()
                return True
            finally:
                wx.TheClipboard.Close()
        time.sleep(0.05)
    return False


class PanelEditorMatematico(wx.Panel):
    def __init__(self, parent: wx.Window, documento: Optional[DocumentoMatematico] = None):
        super().__init__(parent)
        self.documento = documento or DocumentoMatematico()
        self.modo_lectura = configuracion.leer(configuracion.MODO_LECTURA)
        self.verbalizar_al_navegar = configuracion.leer(configuracion.VERBALIZAR_AL_NAVEGAR)
        self._construir_interfaz()
        self._configurar_atajos_locales()
        self.refrescar_lista(cargar_controles=True)

    def _construir_interfaz(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        fila_titulo = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_titulo = wx.StaticText(self, label=tr("&Título del documento:"))
        self.txt_titulo = wx.TextCtrl(self, value=self.documento.titulo)
        self.txt_titulo.SetName(_limpiar_acelerador(tr("&Título del documento:")))
        self.lbl_autor = wx.StaticText(self, label=f"{tr('Autor')}:")
        self.txt_autor = wx.TextCtrl(self, value=self.documento.autor)
        self.txt_autor.SetName(tr("Autor"))

        fila_titulo.Add(self.lbl_titulo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fila_titulo.Add(self.txt_titulo, 2, wx.EXPAND | wx.RIGHT, 12)
        fila_titulo.Add(self.lbl_autor, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fila_titulo.Add(self.txt_autor, 1, wx.EXPAND)
        sizer.Add(fila_titulo, 0, wx.EXPAND | wx.ALL, 6)

        self.lbl_pasos = wx.StaticText(self, label=tr("&Pasos del documento (use Arriba/Abajo para navegar):"))
        sizer.Add(self.lbl_pasos, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)

        self.lista_pasos = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL)
        self.lista_pasos.SetName(tr("Pasos del documento"))
        sizer.Add(self.lista_pasos, 1, wx.EXPAND | wx.ALL, 6)

        self.lbl_lectura = wx.StaticText(self, label=tr("&Lectura accesible y verificación:"))
        sizer.Add(self.lbl_lectura, 0, wx.LEFT | wx.RIGHT, 6)

        self.output_lectura = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 95),
        )
        self.output_lectura.SetName(tr("Lectura accesible"))
        sizer.Add(self.output_lectura, 0, wx.EXPAND | wx.ALL, 6)

        fila_tipo = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_tipo = wx.StaticText(self, label=tr("T&ipo de bloque:"))
        self.claves_tipos = list(TIPOS_BLOQUE.keys())
        self.choice_tipo = wx.Choice(self, choices=[tr(TIPOS_BLOQUE[k]) for k in self.claves_tipos])
        self.choice_tipo.SetName(_limpiar_acelerador(tr("T&ipo de bloque:")))
        self.choice_tipo.SetSelection(1)

        self.lbl_comentario = wx.StaticText(self, label=tr("&Justificación opcional:"))
        self.txt_comentario = wx.TextCtrl(self)
        self.txt_comentario.SetName(_limpiar_acelerador(tr("&Justificación opcional:")))

        fila_tipo.Add(self.lbl_tipo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fila_tipo.Add(self.choice_tipo, 0, wx.RIGHT, 14)
        fila_tipo.Add(self.lbl_comentario, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fila_tipo.Add(self.txt_comentario, 1, wx.EXPAND)
        sizer.Add(fila_tipo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)

        self.lbl_entrada = wx.StaticText(
            self,
            label=tr("&Expresión o texto del paso (Ctrl+Enter para agregar como paso nuevo):"),
        )
        sizer.Add(self.lbl_entrada, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)

        self.input_text = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 80))
        self.input_text.SetName(tr("Expresión o texto del paso"))
        sizer.Add(self.input_text, 0, wx.EXPAND | wx.ALL, 6)

        fila_botones = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_agregar = wx.Button(self, wx.ID_ANY, tr("&Agregar paso (Ctrl+Enter)"))
        self.btn_actualizar = wx.Button(self, wx.ID_ANY, tr("Act&ualizar paso seleccionado"))
        self.btn_inspeccionar = wx.Button(self, wx.ID_ANY, tr("I&nspeccionar estructura (F2)"))
        self.btn_verificar = wx.Button(self, wx.ID_ANY, tr("&Verificar paso (F5)"))
        self.btn_eliminar = wx.Button(self, wx.ID_ANY, tr("E&liminar paso (Supr)"))

        for btn in (self.btn_agregar, self.btn_actualizar, self.btn_inspeccionar, self.btn_verificar, self.btn_eliminar):
            fila_botones.Add(btn, 0, wx.RIGHT, 6)
        sizer.Add(fila_botones, 0, wx.ALL, 6)

        self.SetSizer(sizer)

        self.Bind(wx.EVT_TEXT, self.on_titulo_cambiado, self.txt_titulo)
        self.Bind(wx.EVT_TEXT, self.on_autor_cambiado, self.txt_autor)
        self.Bind(wx.EVT_LISTBOX, self.on_seleccionar_paso, self.lista_pasos)
        self.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.on_cargar_paso_en_edicion(), self.lista_pasos)
        self.lista_pasos.Bind(wx.EVT_KEY_DOWN, self._on_tecla_lista)
        self.input_text.Bind(wx.EVT_KEY_DOWN, self._on_tecla_input)
        self.Bind(wx.EVT_BUTTON, self.on_agregar_paso, self.btn_agregar)
        self.Bind(wx.EVT_BUTTON, self.on_actualizar_paso, self.btn_actualizar)
        self.Bind(wx.EVT_BUTTON, self.on_inspeccionar_estructura, self.btn_inspeccionar)
        self.Bind(wx.EVT_BUTTON, self.on_verificar_paso_actual, self.btn_verificar)
        self.Bind(wx.EVT_BUTTON, self.on_eliminar_paso, self.btn_eliminar)

    def _configurar_atajos_locales(self):
        id_agregar = wx.NewIdRef()
        id_actualizar = wx.NewIdRef()
        id_inspeccionar = wx.NewIdRef()
        id_previsualizar = wx.NewIdRef()
        id_verificar = wx.NewIdRef()
        id_cargar = wx.NewIdRef()

        self.Bind(wx.EVT_MENU, self.on_agregar_paso, id=id_agregar)
        self.Bind(wx.EVT_MENU, self.on_actualizar_paso, id=id_actualizar)
        self.Bind(wx.EVT_MENU, self.on_inspeccionar_estructura, id=id_inspeccionar)
        self.Bind(wx.EVT_MENU, self.on_previsualizar_entrada, id=id_previsualizar)
        self.Bind(wx.EVT_MENU, self.on_verificar_paso_actual, id=id_verificar)
        self.Bind(wx.EVT_MENU, lambda e: self.on_cargar_paso_en_edicion(enfocar=True), id=id_cargar)

        entradas = [
            (wx.ACCEL_CTRL, wx.WXK_RETURN, id_agregar),
            (wx.ACCEL_CTRL, ord("U"), id_actualizar),
            (wx.ACCEL_NORMAL, wx.WXK_F2, id_inspeccionar),
            (wx.ACCEL_NORMAL, wx.WXK_F3, id_cargar),
            (wx.ACCEL_NORMAL, wx.WXK_F4, id_previsualizar),
            (wx.ACCEL_NORMAL, wx.WXK_F5, id_verificar),
        ]
        self.SetAcceleratorTable(wx.AcceleratorTable(entradas))

    def _on_tecla_lista(self, event: wx.KeyEvent):
        code = event.GetKeyCode()
        if code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and not event.HasAnyModifiers():
            self.on_eliminar_paso()
            return
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not event.HasAnyModifiers():
            self.on_cargar_paso_en_edicion(enfocar=True)
            return
        if event.AltDown() and code == wx.WXK_UP:
            self.on_mover_paso(-1)
            return
        if event.AltDown() and code == wx.WXK_DOWN:
            self.on_mover_paso(1)
            return
        event.Skip()

    def _on_tecla_input(self, event: wx.KeyEvent):
        if event.ControlDown() and event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_agregar_paso()
            return
        event.Skip()

    def actualizar_idioma(self):
        self.lbl_titulo.SetLabel(tr("&Título del documento:"))
        self.txt_titulo.SetName(_limpiar_acelerador(tr("&Título del documento:")))
        self.lbl_autor.SetLabel(f"{tr('Autor')}:")
        self.txt_autor.SetName(tr("Autor"))
        self.lbl_pasos.SetLabel(tr("&Pasos del documento (use Arriba/Abajo para navegar):"))
        self.lista_pasos.SetName(tr("Pasos del documento"))
        self.lbl_lectura.SetLabel(tr("&Lectura accesible y verificación:"))
        self.output_lectura.SetName(tr("Lectura accesible"))
        self.lbl_tipo.SetLabel(tr("T&ipo de bloque:"))

        sel_tipo = self.choice_tipo.GetSelection()
        self.choice_tipo.Clear()
        for k in self.claves_tipos:
            self.choice_tipo.Append(tr(TIPOS_BLOQUE[k]))
        self.choice_tipo.SetSelection(sel_tipo if sel_tipo != wx.NOT_FOUND else 1)
        self.choice_tipo.SetName(_limpiar_acelerador(tr("T&ipo de bloque:")))

        self.lbl_comentario.SetLabel(tr("&Justificación opcional:"))
        self.txt_comentario.SetName(_limpiar_acelerador(tr("&Justificación opcional:")))
        self.lbl_entrada.SetLabel(tr("&Expresión o texto del paso (Ctrl+Enter para agregar como paso nuevo):"))
        self.input_text.SetName(tr("Expresión o texto del paso"))

        self.btn_agregar.SetLabel(tr("&Agregar paso (Ctrl+Enter)"))
        self.btn_actualizar.SetLabel(tr("Act&ualizar paso seleccionado"))
        self.btn_inspeccionar.SetLabel(tr("I&nspeccionar estructura (F2)"))
        self.btn_verificar.SetLabel(tr("&Verificar paso (F5)"))
        self.btn_eliminar.SetLabel(tr("E&liminar paso (Supr)"))
        self.Layout()

    def anunciar_estado(self, texto: str):
        top = self.GetTopLevelParent()
        if isinstance(top, wx.Frame) and top.GetStatusBar() is not None:
            top.SetStatusText(texto)

    def on_titulo_cambiado(self, event):
        nuevo = self.txt_titulo.GetValue().strip() or tr("Documento sin título")
        if nuevo != self.documento.titulo:
            self.documento.titulo = nuevo
            self.documento.modificado = True

    def on_autor_cambiado(self, event):
        nuevo = self.txt_autor.GetValue().strip()
        if nuevo != self.documento.autor:
            self.documento.autor = nuevo
            self.documento.modificado = True

    def refrescar_lista(self, seleccion: Optional[int] = None, cargar_controles: bool = False):
        self.lista_pasos.Clear()
        for idx, b in enumerate(self.documento.bloques(), 1):
            if self.verbalizar_al_navegar:
                texto_item = b.lectura_accesible(indice=idx, modo=self.modo_lectura)
            else:
                texto_item = b.resumen_visual(indice=idx)
            self.lista_pasos.Append(texto_item)
        if len(self.documento) > 0:
            sel = seleccion if (seleccion is not None and 0 <= seleccion < len(self.documento)) else len(self.documento) - 1
            self.lista_pasos.SetSelection(sel)
            self._mostrar_lectura_bloque(sel)
            if cargar_controles or not self.input_text.GetValue().strip():
                self._cargar_bloque_en_controles(sel)
        else:
            self.output_lectura.SetValue(tr("Documento vacío. Escriba una expresión o use un asistente del menú para agregar el primer paso."))

    def _mostrar_lectura_bloque(self, indice: int):
        if not (0 <= indice < len(self.documento)):
            return
        b = self.documento.obtener(indice)
        lectura = b.lectura_accesible(indice=indice + 1, modo=self.modo_lectura)
        self.output_lectura.SetValue(f"{lectura}\n{tr('Notación lineal')}: {b.contenido}")

    def _cargar_bloque_en_controles(self, indice: int):
        if not (0 <= indice < len(self.documento)):
            return
        b = self.documento.obtener(indice)
        if b.tipo in self.claves_tipos:
            self.choice_tipo.SetSelection(self.claves_tipos.index(b.tipo))
        self.input_text.SetValue(b.contenido)
        self.txt_comentario.SetValue(b.comentario)
        self._mostrar_lectura_bloque(indice)

    def on_cargar_paso_en_edicion(self, enfocar: bool = True):
        sel = self.lista_pasos.GetSelection()
        if sel != wx.NOT_FOUND:
            self._cargar_bloque_en_controles(sel)
            if enfocar:
                self.input_text.SetFocus()
                self.input_text.SetSelection(-1, -1)

    def on_seleccionar_paso(self, event):
        sel = self.lista_pasos.GetSelection()
        if sel != wx.NOT_FOUND:
            self._mostrar_lectura_bloque(sel)
            if not self.input_text.IsModified():
                self._cargar_bloque_en_controles(sel)

    def tipo_seleccionado(self) -> str:
        idx = self.choice_tipo.GetSelection()
        return self.claves_tipos[idx] if idx != wx.NOT_FOUND else TIPO_EXPRESION

    def on_previsualizar_entrada(self, event=None):
        txt = self.input_text.GetValue().strip()
        if not txt:
            sel = self.lista_pasos.GetSelection()
            if sel != wx.NOT_FOUND:
                self._mostrar_lectura_bloque(sel)
                self.output_lectura.SetFocus()
            return
        bloque = BloqueDocumento(
            tipo=self.tipo_seleccionado(),
            contenido=txt,
            comentario=self.txt_comentario.GetValue().strip(),
        )
        lectura = bloque.lectura_accesible(modo=self.modo_lectura)
        self.output_lectura.SetValue(f"{lectura}\n{tr('Notación lineal')}: {bloque.contenido}")
        self.anunciar_estado(lectura)

    def on_agregar_paso(self, event=None, subtipo: str = ""):
        contenido = self.input_text.GetValue().strip()
        if not contenido:
            wx.MessageBox(tr("Escriba una expresión o texto antes de agregar el paso."), tr("Aviso"), wx.OK | wx.ICON_INFORMATION, self)
            self.input_text.SetFocus()
            return
        tipo = self.tipo_seleccionado()
        comentario = self.txt_comentario.GetValue().strip()
        prueba = BloqueDocumento(tipo=tipo, contenido=contenido, comentario=comentario, subtipo=subtipo)
        ok, err = prueba.es_valido()
        if not ok:
            wx.MessageBox(tr("Error de Validación: {error}", error=err), tr("Error"), wx.OK | wx.ICON_ERROR, self)
            self.input_text.SetFocus()
            return
        nuevo_bloque = self.documento.agregar(contenido=contenido, tipo=tipo, comentario=comentario, subtipo=subtipo)
        nuevo_idx = len(self.documento) - 1
        self.txt_comentario.Clear()
        self.input_text.SetModified(False)
        self.refrescar_lista(seleccion=nuevo_idx, cargar_controles=False)
        self.anunciar_estado(nuevo_bloque.lectura_accesible(indice=nuevo_idx + 1, modo=self.modo_lectura))
        self.input_text.SetFocus()
        self.input_text.SetSelection(-1, -1)

    def on_actualizar_paso(self, event=None):
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox(tr("Seleccione primero un paso de la lista para actualizarlo."), tr("Aviso"), wx.OK | wx.ICON_INFORMATION, self)
            return
        contenido = self.input_text.GetValue().strip()
        tipo = self.tipo_seleccionado()
        comentario = self.txt_comentario.GetValue().strip()
        actual = self.documento.obtener(sel)
        subtipo = actual.subtipo if tipo == actual.tipo else ""
        prueba = BloqueDocumento(tipo=tipo, contenido=contenido, comentario=comentario, subtipo=subtipo)
        ok, err = prueba.es_valido()
        if not ok:
            wx.MessageBox(tr("Error de Validación: {error}", error=err), tr("Error"), wx.OK | wx.ICON_ERROR, self)
            self.input_text.SetFocus()
            return
        actualizado = self.documento.actualizar(sel, contenido=contenido, tipo=tipo, comentario=comentario, subtipo=subtipo)
        self.input_text.SetModified(False)
        self.refrescar_lista(seleccion=sel, cargar_controles=True)
        self.anunciar_estado(actualizado.lectura_accesible(indice=sel + 1, modo=self.modo_lectura))
        self.output_lectura.SetFocus()

    def on_duplicar_paso(self, event=None):
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        dup = self.documento.duplicar(sel)
        self.refrescar_lista(seleccion=sel + 1, cargar_controles=True)
        self.anunciar_estado(dup.lectura_accesible(indice=sel + 2, modo=self.modo_lectura))
        self.input_text.SetFocus()
        self.input_text.SetSelection(-1, -1)

    def on_deshacer(self, event=None):
        if self.documento.deshacer():
            sel = min(self.lista_pasos.GetSelection(), len(self.documento) - 1) if len(self.documento) > 0 else None
            self.refrescar_lista(seleccion=sel, cargar_controles=True)

    def on_rehacer(self, event=None):
        if self.documento.rehacer():
            sel = min(self.lista_pasos.GetSelection(), len(self.documento) - 1) if len(self.documento) > 0 else None
            self.refrescar_lista(seleccion=sel, cargar_controles=True)

    def on_eliminar_paso(self, event=None):
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        self.documento.eliminar(sel)
        nuevo_sel = min(sel, len(self.documento) - 1) if len(self.documento) > 0 else None
        self.refrescar_lista(seleccion=nuevo_sel, cargar_controles=True)
        self.lista_pasos.SetFocus()

    def on_mover_paso(self, delta: int):
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        nuevo = self.documento.mover(sel, sel + delta)
        self.refrescar_lista(seleccion=nuevo, cargar_controles=False)
        self.lista_pasos.SetFocus()

    def on_inspeccionar_estructura(self, event=None):
        txt = self.input_text.GetValue().strip()
        sel = self.lista_pasos.GetSelection()
        if self.FindFocus() == self.input_text and txt:
            bloque = BloqueDocumento(tipo=self.tipo_seleccionado(), contenido=txt)
        elif sel != wx.NOT_FOUND:
            bloque = self.documento.obtener(sel)
        elif txt:
            bloque = BloqueDocumento(tipo=self.tipo_seleccionado(), contenido=txt)
        else:
            wx.MessageBox(tr("Seleccione un paso o escriba una expresión para inspeccionar su estructura."), tr("Aviso"), wx.OK | wx.ICON_INFORMATION, self)
            return
        ok, err = bloque.es_valido()
        if not ok:
            wx.MessageBox(tr("Error de Validación: {error}", error=err), tr("Error"), wx.OK | wx.ICON_ERROR, self)
            return
        dlg = DialogoInspectorEstructura(self, bloque)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()

    def on_verificar_paso_actual(self, event=None):
        if len(self.documento) == 0:
            wx.MessageBox(tr("El documento no tiene pasos para verificar."), tr("Verificar"), wx.OK | wx.ICON_INFORMATION, self)
            return
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            sel = len(self.documento) - 1
        res = verificador.verificar_en_documento(self.documento, sel)
        self.output_lectura.SetValue(res.mensaje)
        self.anunciar_estado(res.mensaje)
        self.output_lectura.SetFocus()

    def on_verificar_documento_completo(self, event=None):
        if len(self.documento) == 0:
            wx.MessageBox(tr("El documento no tiene pasos para verificar."), tr("Verificar"), wx.OK | wx.ICON_INFORMATION, self)
            return
        resultados = verificador.verificar_documento_completo(self.documento)
        fallos = [r for r in resultados if not r.es_valido]
        encabezado = (
            tr("VERIFICACIÓN COMPLETA: todos los pasos matemáticos ({n}) son coherentes.", n=len(resultados))
            if not fallos
            else tr("VERIFICACIÓN COMPLETA: se detectaron {f} pasos por revisar de {n}.", f=len(fallos), n=len(resultados))
        )
        lineas = [encabezado, "=" * 35] + [r.mensaje for r in resultados]
        self.output_lectura.SetValue("\n".join(lineas))
        self.anunciar_estado(encabezado)
        self.output_lectura.SetFocus()

    def ejecutar_asistente(self, clave: str):
        asist = ASISTENTE_POR_CLAVE[clave]
        dlg = DialogoAsistente(self, asist)
        try:
            if dlg.ShowModal() == wx.ID_OK and dlg.resultado is not None:
                tipo, contenido, subtipo = dlg.resultado
                if tipo in self.claves_tipos:
                    self.choice_tipo.SetSelection(self.claves_tipos.index(tipo))
                self.input_text.SetValue(contenido)
                self.on_agregar_paso(subtipo=subtipo)
        finally:
            dlg.Destroy()


class VentanaEditorMatematico(wx.Frame):
    MENUS_ASISTENTES = {
        "aritmetica": N_("A&ritmética y Raíces"),
        "algebra": N_("Á&lgebra y Matrices"),
        "calculo": N_("&Cálculo"),
        "edo": N_("Ecuaciones &Diferenciales"),
    }

    def __init__(self, documento: Optional[DocumentoMatematico] = None):
        super().__init__(
            None,
            title=f"{tr('Editor Matemático Accesible')} {__version__}",
            size=(920, 700),
        )
        self.CreateStatusBar()
        self.panel = PanelEditorMatematico(self, documento=documento)
        self.crear_menus()
        self.Bind(wx.EVT_CLOSE, self.on_cerrar_ventana)
        self.Centre()

        if configuracion.leer(configuracion.BUSCAR_ACTUALIZACIONES):
            threading.Thread(target=self._comprobar_actualizacion_segundo_plano, daemon=True).start()

    def _item(self, menu: wx.Menu, etiqueta_n: str, atajo: Optional[str], handler):
        texto = tr(etiqueta_n) + (f"\t{atajo}" if atajo else "")
        item = menu.Append(wx.ID_ANY, texto)
        self.Bind(wx.EVT_MENU, handler, item)
        return item

    def crear_menus(self):
        menubar = wx.MenuBar()

        m_archivo = wx.Menu()
        self._item(m_archivo, N_("&Nuevo documento"), "Ctrl+N", self.on_nuevo)
        self._item(m_archivo, N_("&Abrir documento (.ema)..."), "Ctrl+O", self.on_abrir)
        self._item(m_archivo, N_("&Guardar documento (.ema)..."), "Ctrl+S", self.on_guardar)
        self._item(m_archivo, N_("Guardar &como (.ema)..."), "Ctrl+Shift+S", lambda e: self.on_guardar(forzar_dialogo=True))
        m_archivo.AppendSeparator()
        self._item(m_archivo, N_("&Exportar documento (Word, HTML+MathML, LaTeX, Markdown)..."), "Ctrl+E", self.on_exportar)
        m_archivo.AppendSeparator()
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), m_archivo.Append(wx.ID_EXIT, tr("&Salir") + "\tAlt+F4"))

        m_edicion = wx.Menu()
        self._item(m_edicion, N_("&Deshacer cambio en pasos"), "Ctrl+Z", self.on_deshacer_menu)
        self._item(m_edicion, N_("&Rehacer cambio en pasos"), "Ctrl+Y", self.on_rehacer_menu)
        m_edicion.AppendSeparator()
        self._item(m_edicion, N_("&Agregar paso actual"), "Ctrl+Enter", self.panel.on_agregar_paso)
        self._item(m_edicion, N_("Act&ualizar paso seleccionado"), "Ctrl+U", self.panel.on_actualizar_paso)
        self._item(m_edicion, N_("&Cargar paso seleccionado para editar"), "F3", lambda e: self.panel.on_cargar_paso_en_edicion(enfocar=True))
        self._item(m_edicion, N_("D&uplicar paso seleccionado"), "Ctrl+Shift+A", self.panel.on_duplicar_paso)
        self._item(m_edicion, N_("Subir paso seleccionado"), "Alt+Up", lambda e: self.panel.on_mover_paso(-1))
        self._item(m_edicion, N_("Bajar paso seleccionado"), "Alt+Down", lambda e: self.panel.on_mover_paso(1))
        self._item(m_edicion, N_("&Eliminar paso seleccionado"), None, self.panel.on_eliminar_paso)
        m_edicion.AppendSeparator()
        self._item(m_edicion, N_("Copiar &lectura accesible del paso"), "Ctrl+Shift+C", self.on_copiar_lectura)
        self._item(m_edicion, N_("Copiar paso como &LaTeX"), "Ctrl+Alt+L", self.on_copiar_latex)
        self._item(m_edicion, N_("Copiar paso como &MathML"), "Ctrl+Alt+M", self.on_copiar_mathml)

        menus_asist = {clave: wx.Menu() for clave in self.MENUS_ASISTENTES}
        for asist in REGISTRO_ASISTENTES:
            menu = menus_asist[asist.menu]
            if asist.separador_antes:
                menu.AppendSeparator()
            self._item(
                menu,
                asist.etiqueta,
                asist.atajo,
                lambda e, c=asist.clave: self.panel.ejecutar_asistente(c),
            )

        m_verificar = wx.Menu()
        self._item(m_verificar, N_("&Inspeccionar estructura de la fórmula"), "F2", self.panel.on_inspeccionar_estructura)
        self._item(m_verificar, N_("&Escuchar lectura previa"), "F4", self.panel.on_previsualizar_entrada)
        self._item(m_verificar, N_("&Verificar paso actual con el anterior"), "F5", self.panel.on_verificar_paso_actual)
        self._item(m_verificar, N_("Verificar &todo el documento"), "Ctrl+Shift+V", self.panel.on_verificar_documento_completo)

        m_opciones = wx.Menu()
        item_modo = m_opciones.AppendCheckItem(wx.ID_ANY, tr("Lectura &detallada (anunciar inicio y fin de estructuras)") + "\tCtrl+Shift+D")
        item_modo.Check(self.panel.modo_lectura == configuracion.LECTURA_DETALLADA)
        self.Bind(wx.EVT_MENU, self.on_alternar_modo_lectura, item_modo)

        item_nav = m_opciones.AppendCheckItem(wx.ID_ANY, tr("&Verbalizar pasos en la lista del documento"))
        item_nav.Check(self.panel.verbalizar_al_navegar)
        self.Bind(wx.EVT_MENU, self.on_alternar_verbalizar_navegacion, item_nav)

        m_idioma = wx.Menu()
        for codigo, nombre in i18n.IDIOMAS.items():
            item = m_idioma.AppendRadioItem(wx.ID_ANY, nombre)
            item.Check(codigo == i18n.idioma_actual())
            self.Bind(wx.EVT_MENU, lambda e, c=codigo: self.on_cambiar_idioma(c), item)

        m_ayuda = wx.Menu()
        self._item(m_ayuda, N_("&Manual de usuario y atajos"), "F1", self.mostrar_ayuda)

        menubar.Append(m_archivo, tr("&Archivo"))
        menubar.Append(m_edicion, tr("&Edición"))
        for clave, titulo in self.MENUS_ASISTENTES.items():
            menubar.Append(menus_asist[clave], tr(titulo))
        menubar.Append(m_verificar, tr("&Verificar e Inspeccionar"))
        menubar.Append(m_opciones, tr("&Opciones"))
        menubar.Append(m_idioma, tr("&Idioma / Language"))
        menubar.Append(m_ayuda, tr("A&yuda"))
        self.SetMenuBar(menubar)

    def on_deshacer_menu(self, event):
        foco = self.FindFocus()
        if isinstance(foco, wx.TextCtrl) and foco.CanUndo():
            foco.Undo()
        else:
            self.panel.on_deshacer()

    def on_rehacer_menu(self, event):
        foco = self.FindFocus()
        if isinstance(foco, wx.TextCtrl) and foco.CanRedo():
            foco.Redo()
        else:
            self.panel.on_rehacer()

    def _confirmar_descartar_cambios(self) -> bool:
        if not self.panel.documento.modificado:
            return True
        resp = wx.MessageBox(
            tr("El documento tiene cambios sin guardar. ¿Desea guardarlos antes de continuar?"),
            tr("Cambios sin guardar"),
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
            self,
        )
        if resp == wx.CANCEL:
            return False
        if resp == wx.YES:
            return self.on_guardar()
        return True

    def on_cerrar_ventana(self, event):
        if event.CanVeto() and not self._confirmar_descartar_cambios():
            event.Veto()
            return
        self.Destroy()

    def on_nuevo(self, event):
        if not self._confirmar_descartar_cambios():
            return
        self.panel.documento = DocumentoMatematico()
        self.panel.txt_titulo.ChangeValue(self.panel.documento.titulo)
        self.panel.txt_autor.ChangeValue(self.panel.documento.autor)
        self.panel.input_text.Clear()
        self.panel.txt_comentario.Clear()
        self.panel.refrescar_lista(cargar_controles=True)
        self.panel.input_text.SetFocus()

    def on_abrir(self, event):
        if not self._confirmar_descartar_cambios():
            return
        with wx.FileDialog(
            self,
            tr("Abrir documento matemático"),
            wildcard="Editor Matemático (*.ema)|*.ema|JSON (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            ruta = dlg.GetPath()
        try:
            self.panel.documento = DocumentoMatematico.cargar_archivo(ruta)
            self.panel.txt_titulo.ChangeValue(self.panel.documento.titulo)
            self.panel.txt_autor.ChangeValue(self.panel.documento.autor)
            self.panel.refrescar_lista(seleccion=0, cargar_controles=True)
            self.SetStatusText(tr("Documento abierto: {ruta}", ruta=ruta))
        except Exception as e:
            wx.MessageBox(tr("No se pudo abrir el archivo:\n{error}", error=str(e)), tr("Error"), wx.OK | wx.ICON_ERROR, self)

    def on_guardar(self, event=None, forzar_dialogo: bool = False) -> bool:
        ruta = self.panel.documento.ruta_archivo
        if not ruta or forzar_dialogo:
            with wx.FileDialog(
                self,
                tr("Guardar documento matemático"),
                defaultFile=f"{self.panel.documento.titulo}.ema",
                wildcard="Editor Matemático (*.ema)|*.ema",
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return False
                ruta = dlg.GetPath()
        try:
            self.panel.documento.guardar_archivo(ruta)
            msg = tr("Documento guardado en {ruta}", ruta=ruta)
            self.SetStatusText(msg)
            self.panel.output_lectura.SetValue(msg)
            return True
        except Exception as e:
            wx.MessageBox(tr("No se pudo guardar el archivo:\n{error}", error=str(e)), tr("Error"), wx.OK | wx.ICON_ERROR, self)
            return False

    def on_exportar(self, event):
        if len(self.panel.documento) == 0:
            wx.MessageBox(tr("El documento está vacío."), tr("Exportar"), wx.OK | wx.ICON_INFORMATION, self)
            return
        claves = list(exportar.FORMATOS.keys())
        filtros = "|".join(f"{tr(exportar.FORMATOS[k][0])} (*.{exportar.FORMATOS[k][1]})|*.{exportar.FORMATOS[k][1]}" for k in claves)
        with wx.FileDialog(
            self,
            tr("Exportar documento"),
            defaultFile=self.panel.documento.titulo,
            wildcard=filtros,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            ruta = dlg.GetPath()
            formato = claves[dlg.GetFilterIndex()]
        try:
            exportar.guardar(self.panel.documento, formato, ruta)
            msg = tr("Documento exportado correctamente a:\n{ruta}", ruta=ruta)
            self.SetStatusText(msg.replace("\n", " "))
            wx.MessageBox(msg, tr("Exportación completada"), wx.OK | wx.ICON_INFORMATION, self)
        except Exception as e:
            wx.MessageBox(tr("Error al exportar el documento:\n{error}", error=str(e)), tr("Error"), wx.OK | wx.ICON_ERROR, self)

    def _bloque_actual(self) -> Optional[BloqueDocumento]:
        sel = self.panel.lista_pasos.GetSelection()
        if sel != wx.NOT_FOUND:
            return self.panel.documento.obtener(sel)
        txt = self.panel.input_text.GetValue().strip()
        if txt:
            b = BloqueDocumento(tipo=self.panel.tipo_seleccionado(), contenido=txt)
            if b.es_valido()[0]:
                return b
        return None

    def on_copiar_lectura(self, event):
        b = self._bloque_actual()
        if b is None:
            return
        lectura = b.lectura_accesible(modo=self.panel.modo_lectura)
        copiar_al_portapapeles(lectura)
        msg = tr("Lectura accesible copiada al portapapeles.")
        self.SetStatusText(msg)
        self.panel.output_lectura.SetValue(f"{msg}\n{lectura}")

    def on_copiar_latex(self, event):
        b = self._bloque_actual()
        if b is None:
            return
        codigo = exportar.latex_bloque(b)
        copiar_al_portapapeles(codigo)
        msg = tr("Código LaTeX del paso copiado al portapapeles.")
        self.SetStatusText(msg)
        self.panel.output_lectura.SetValue(f"{msg}\n{codigo}")

    def on_copiar_mathml(self, event):
        b = self._bloque_actual()
        if b is None:
            return
        codigo = exportar.mathml_bloque(b)
        copiar_al_portapapeles(codigo)
        msg = tr("Código MathML del paso copiado al portapapeles.")
        self.SetStatusText(msg)
        self.panel.output_lectura.SetValue(f"{msg}\n{codigo}")

    def on_alternar_modo_lectura(self, event):
        detallada = self.panel.modo_lectura != configuracion.LECTURA_DETALLADA
        self.panel.modo_lectura = configuracion.LECTURA_DETALLADA if detallada else configuracion.LECTURA_BREVE
        configuracion.guardar(configuracion.MODO_LECTURA, self.panel.modo_lectura)
        self.crear_menus()
        sel = self.panel.lista_pasos.GetSelection()
        self.panel.refrescar_lista(seleccion=sel if sel != wx.NOT_FOUND else None, cargar_controles=False)

    def on_alternar_verbalizar_navegacion(self, event):
        self.panel.verbalizar_al_navegar = not self.panel.verbalizar_al_navegar
        configuracion.guardar(configuracion.VERBALIZAR_AL_NAVEGAR, self.panel.verbalizar_al_navegar)
        self.crear_menus()
        sel = self.panel.lista_pasos.GetSelection()
        self.panel.refrescar_lista(seleccion=sel if sel != wx.NOT_FOUND else None, cargar_controles=False)

    def on_cambiar_idioma(self, codigo: str):
        titulo_def_ant = tr("Documento sin título")
        i18n.establecer_idioma(codigo)
        i18n.guardar_idioma(codigo)
        if self.panel.documento.titulo == titulo_def_ant:
            self.panel.documento.titulo = tr("Documento sin título")
            self.panel.txt_titulo.ChangeValue(self.panel.documento.titulo)
        self.SetTitle(f"{tr('Editor Matemático Accesible')} {__version__}")
        self.crear_menus()
        self.panel.actualizar_idioma()
        sel = self.panel.lista_pasos.GetSelection()
        self.panel.refrescar_lista(seleccion=sel if sel != wx.NOT_FOUND else None, cargar_controles=False)

    def _comprobar_actualizacion_segundo_plano(self):
        info = actualizador.consultar_ultima_release()
        if not info:
            return
        omitida = configuracion.leer(configuracion.VERSION_OMITIDA)
        if omitida == info["version"]:
            return
        wx.CallAfter(self._notificar_actualizacion, info)

    def _notificar_actualizacion(self, info: dict):
        resp = wx.MessageBox(
            tr("Hay una nueva versión disponible ({version}). ¿Desea abrir la página de descarga?",
               version=info["version"]),
            tr("Actualización disponible"),
            wx.YES_NO | wx.ICON_INFORMATION,
            self,
        )
        if resp == wx.YES:
            webbrowser.open(info["url"])
        else:
            configuracion.guardar(configuracion.VERSION_OMITIDA, info["version"])

    def mostrar_ayuda(self, event=None):
        ruta = os.path.join(i18n.carpeta_locales(), f"ayuda_{i18n.idioma_actual()}.txt")
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                texto = f.read()
        else:
            texto = tr("Manual de ayuda del Editor Matemático Accesible.")
        self.panel.output_lectura.SetValue(texto)
        self.panel.output_lectura.SetFocus()


def main():
    multiprocessing.freeze_support()
    i18n.iniciar_idioma()
    app = wx.App(False)
    ventana = VentanaEditorMatematico()
    ventana.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
