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
import time
from typing import Optional

import wx

from _version import __version__
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
from verbalizador import NodoEstructura
import verificador


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

        lbl_detalle = wx.StaticText(self, label=tr("&Detalle de la parte seleccionada:"))
        sizer.Add(lbl_detalle, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.txt_detalle = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 90),
        )
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
            size=(540, 380),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.asistente = asistente
        self.controles = {}
        self.resultado: Optional[tuple] = None

        sizer = wx.BoxSizer(wx.VERTICAL)

        for campo in asistente.campos:
            lbl = wx.StaticText(self, label=tr(campo.etiqueta))
            sizer.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
            estilo = wx.TE_MULTILINE if campo.multilinea else 0
            ctrl = wx.TextCtrl(self, value=campo.valor_defecto, style=estilo, size=(-1, 80 if campo.multilinea else -1))
            sizer.Add(ctrl, 1 if campo.multilinea else 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            self.controles[campo.clave] = ctrl

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
        self.SetMinSize((480, 260))

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
        wx.MessageBox(
            f"{tr('Lectura')}: {bloque.lectura_accesible()}\n{tr('Notación lineal')}: {contenido}",
            tr("Vista previa accesible"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

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
        self._construir_interfaz()
        self.refrescar_lista()

    def _construir_interfaz(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        fila_titulo = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_titulo = wx.StaticText(self, label=tr("&Título del documento:"))
        self.txt_titulo = wx.TextCtrl(self, value=self.documento.titulo)
        fila_titulo.Add(self.lbl_titulo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fila_titulo.Add(self.txt_titulo, 1, wx.EXPAND)
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
        self.choice_tipo.SetSelection(1)

        self.lbl_comentario = wx.StaticText(self, label=tr("&Justificación opcional:"))
        self.txt_comentario = wx.TextCtrl(self)

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
        self.Bind(wx.EVT_LISTBOX, self.on_seleccionar_paso, self.lista_pasos)
        self.Bind(wx.EVT_BUTTON, self.on_agregar_paso, self.btn_agregar)
        self.Bind(wx.EVT_BUTTON, self.on_actualizar_paso, self.btn_actualizar)
        self.Bind(wx.EVT_BUTTON, self.on_inspeccionar_estructura, self.btn_inspeccionar)
        self.Bind(wx.EVT_BUTTON, self.on_verificar_paso_actual, self.btn_verificar)
        self.Bind(wx.EVT_BUTTON, self.on_eliminar_paso, self.btn_eliminar)

    def on_titulo_cambiado(self, event):
        nuevo = self.txt_titulo.GetValue().strip()
        if nuevo:
            self.documento.titulo = nuevo
            self.documento.modificado = True

    def refrescar_lista(self, seleccion: Optional[int] = None):
        self.lista_pasos.Clear()
        for idx, b in enumerate(self.documento.bloques(), 1):
            self.lista_pasos.Append(b.lectura_accesible(indice=idx, modo=self.modo_lectura))
        if len(self.documento) > 0:
            sel = seleccion if (seleccion is not None and 0 <= seleccion < len(self.documento)) else len(self.documento) - 1
            self.lista_pasos.SetSelection(sel)
            self._cargar_bloque_en_controles(sel)
        else:
            self.output_lectura.SetValue(tr("Documento vacío. Escriba una expresión o use un asistente del menú para agregar el primer paso."))

    def _cargar_bloque_en_controles(self, indice: int):
        if not (0 <= indice < len(self.documento)):
            return
        b = self.documento.obtener(indice)
        if b.tipo in self.claves_tipos:
            self.choice_tipo.SetSelection(self.claves_tipos.index(b.tipo))
        self.input_text.SetValue(b.contenido)
        self.txt_comentario.SetValue(b.comentario)
        lectura = b.lectura_accesible(indice=indice + 1, modo=self.modo_lectura)
        self.output_lectura.SetValue(f"{lectura}\n{tr('Notación lineal')}: {b.contenido}")

    def on_seleccionar_paso(self, event):
        sel = self.lista_pasos.GetSelection()
        if sel != wx.NOT_FOUND:
            self._cargar_bloque_en_controles(sel)

    def tipo_seleccionado(self) -> str:
        idx = self.choice_tipo.GetSelection()
        return self.claves_tipos[idx] if idx != wx.NOT_FOUND else TIPO_EXPRESION

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
        self.documento.agregar(contenido=contenido, tipo=tipo, comentario=comentario, subtipo=subtipo)
        nuevo_idx = len(self.documento) - 1
        self.refrescar_lista(seleccion=nuevo_idx)
        self.output_lectura.SetFocus()

    def on_actualizar_paso(self, event=None):
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox(tr("Seleccione primero un paso de la lista para actualizarlo."), tr("Aviso"), wx.OK | wx.ICON_INFORMATION, self)
            return
        contenido = self.input_text.GetValue().strip()
        tipo = self.tipo_seleccionado()
        comentario = self.txt_comentario.GetValue().strip()
        prueba = BloqueDocumento(tipo=tipo, contenido=contenido, comentario=comentario)
        ok, err = prueba.es_valido()
        if not ok:
            wx.MessageBox(tr("Error de Validación: {error}", error=err), tr("Error"), wx.OK | wx.ICON_ERROR, self)
            self.input_text.SetFocus()
            return
        self.documento.actualizar(sel, contenido=contenido, tipo=tipo, comentario=comentario)
        self.refrescar_lista(seleccion=sel)
        self.output_lectura.SetFocus()

    def on_eliminar_paso(self, event=None):
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        self.documento.eliminar(sel)
        nuevo_sel = min(sel, len(self.documento) - 1) if len(self.documento) > 0 else None
        self.refrescar_lista(seleccion=nuevo_sel)

    def on_mover_paso(self, delta: int):
        sel = self.lista_pasos.GetSelection()
        if sel == wx.NOT_FOUND:
            return
        nuevo = self.documento.mover(sel, sel + delta)
        self.refrescar_lista(seleccion=nuevo)
        self.lista_pasos.SetFocus()

    def on_inspeccionar_estructura(self, event=None):
        sel = self.lista_pasos.GetSelection()
        if sel != wx.NOT_FOUND:
            bloque = self.documento.obtener(sel)
        else:
            txt = self.input_text.GetValue().strip()
            if not txt:
                wx.MessageBox(tr("Seleccione un paso o escriba una expresión para inspeccionar su estructura."), tr("Aviso"), wx.OK | wx.ICON_INFORMATION, self)
                return
            bloque = BloqueDocumento(tipo=self.tipo_seleccionado(), contenido=txt)
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
            size=(920, 680),
        )
        self.panel = PanelEditorMatematico(self, documento=documento)
        self.crear_menus()
        self.Centre()

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
        m_archivo.AppendSeparator()
        self._item(m_archivo, N_("&Exportar documento (Word, HTML+MathML, LaTeX, Markdown)..."), "Ctrl+E", self.on_exportar)
        m_archivo.AppendSeparator()
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), m_archivo.Append(wx.ID_EXIT, tr("&Salir") + "\tAlt+F4"))

        m_edicion = wx.Menu()
        self._item(m_edicion, N_("&Agregar paso actual"), "Ctrl+Enter", self.panel.on_agregar_paso)
        self._item(m_edicion, N_("Act&ualizar paso seleccionado"), "Ctrl+U", self.panel.on_actualizar_paso)
        self._item(m_edicion, N_("Subir paso seleccionado"), "Alt+Up", lambda e: self.panel.on_mover_paso(-1))
        self._item(m_edicion, N_("Bajar paso seleccionado"), "Alt+Down", lambda e: self.panel.on_mover_paso(1))
        self._item(m_edicion, N_("&Eliminar paso seleccionado"), "Delete", self.panel.on_eliminar_paso)
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
        self._item(m_verificar, N_("&Verificar paso actual con el anterior"), "F5", self.panel.on_verificar_paso_actual)
        self._item(m_verificar, N_("Verificar &todo el documento"), "Ctrl+Shift+V", self.panel.on_verificar_documento_completo)

        m_opciones = wx.Menu()
        item_modo = m_opciones.AppendCheckItem(wx.ID_ANY, tr("Lectura &detallada (anunciar inicio y fin de estructuras)") + "\tCtrl+Shift+D")
        item_modo.Check(self.panel.modo_lectura == configuracion.LECTURA_DETALLADA)
        self.Bind(wx.EVT_MENU, self.on_alternar_modo_lectura, item_modo)

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

    def on_nuevo(self, event):
        self.panel.documento = DocumentoMatematico()
        self.panel.txt_titulo.SetValue(self.panel.documento.titulo)
        self.panel.input_text.Clear()
        self.panel.txt_comentario.Clear()
        self.panel.refrescar_lista()
        self.panel.input_text.SetFocus()

    def on_abrir(self, event):
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
            self.panel.txt_titulo.SetValue(self.panel.documento.titulo)
            self.panel.refrescar_lista(seleccion=0)
        except Exception as e:
            wx.MessageBox(tr("No se pudo abrir el archivo:\n{error}", error=str(e)), tr("Error"), wx.OK | wx.ICON_ERROR, self)

    def on_guardar(self, event):
        with wx.FileDialog(
            self,
            tr("Guardar documento matemático"),
            defaultFile=f"{self.panel.documento.titulo}.ema",
            wildcard="Editor Matemático (*.ema)|*.ema",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            ruta = dlg.GetPath()
        try:
            self.panel.documento.guardar_archivo(ruta)
            wx.MessageBox(tr("Documento guardado en {ruta}", ruta=ruta), tr("Guardado"), wx.OK | wx.ICON_INFORMATION, self)
        except Exception as e:
            wx.MessageBox(tr("No se pudo guardar el archivo:\n{error}", error=str(e)), tr("Error"), wx.OK | wx.ICON_ERROR, self)

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
            wx.MessageBox(tr("Documento exportado correctamente a:\n{ruta}", ruta=ruta), tr("Exportación completada"), wx.OK | wx.ICON_INFORMATION, self)
        except Exception as e:
            wx.MessageBox(tr("Error al exportar el documento:\n{error}", error=str(e)), tr("Error"), wx.OK | wx.ICON_ERROR, self)

    def _bloque_actual(self) -> Optional[BloqueDocumento]:
        sel = self.panel.lista_pasos.GetSelection()
        if sel != wx.NOT_FOUND:
            return self.panel.documento.obtener(sel)
        return None

    def on_copiar_lectura(self, event):
        b = self._bloque_actual()
        if b is None:
            return
        copiar_al_portapapeles(b.lectura_accesible(modo=self.panel.modo_lectura))
        wx.MessageBox(tr("Lectura accesible copiada al portapapeles."), tr("Copiado"), wx.OK | wx.ICON_INFORMATION, self)

    def on_copiar_latex(self, event):
        b = self._bloque_actual()
        if b is None:
            return
        copiar_al_portapapeles(exportar.latex_bloque(b))
        wx.MessageBox(tr("Código LaTeX del paso copiado al portapapeles."), tr("Copiado"), wx.OK | wx.ICON_INFORMATION, self)

    def on_copiar_mathml(self, event):
        b = self._bloque_actual()
        if b is None:
            return
        copiar_al_portapapeles(exportar.mathml_bloque(b))
        wx.MessageBox(tr("Código MathML del paso copiado al portapapeles."), tr("Copiado"), wx.OK | wx.ICON_INFORMATION, self)

    def on_alternar_modo_lectura(self, event):
        detallada = self.panel.modo_lectura != configuracion.LECTURA_DETALLADA
        self.panel.modo_lectura = configuracion.LECTURA_DETALLADA if detallada else configuracion.LECTURA_BREVE
        configuracion.guardar(configuracion.MODO_LECTURA, self.panel.modo_lectura)
        self.crear_menus()
        sel = self.panel.lista_pasos.GetSelection()
        self.panel.refrescar_lista(seleccion=sel if sel != wx.NOT_FOUND else None)

    def on_cambiar_idioma(self, codigo: str):
        i18n.establecer_idioma(codigo)
        i18n.guardar_idioma(codigo)
        self.SetTitle(f"{tr('Editor Matemático Accesible')} {__version__}")
        self.crear_menus()
        sel = self.panel.lista_pasos.GetSelection()
        self.panel.refrescar_lista(seleccion=sel if sel != wx.NOT_FOUND else None)

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
