#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
Copyright 2015, Luis Javier Gonzalez (luis.j.glez.devel@gmail.com)

This program is licensed under the GNU GPL 3.0 license.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

from sys import argv
import json
import math

from PyQt4.QtGui import QApplication, QMainWindow, QFileDialog, QImage, QPixmap
from PyQt4.QtCore import QSettings, pyqtSlot

from wand.image import Image
from wand.color import Color
from wand.display import display

from PyQt4 import QtCore, QtGui

from window import Ui_Form as Central

"""
-history empieza con [[]] es decir, un array de pngs vacio. tamaño = 1, maxhist = 0, currenthist = 0
-cuando se realiza cualquier accion: abrir ficheros, dividir, quitar bordes, poner bordes, agrupar, ... se hace la accion y se añade el nuevo array al historial. [[], [imagen1,imagen2,imagen3]] tamaño = 2, maxhist = 1, currenthist = 1
-cuando se deshace [[], [imagen1,imagen2,imagen3]] tamaño = 2, maxhist = 1, currenthist = 0 -> debemos mostrar y trabajar con el array []
-cuando se rehace [[], [...]] tamaño = 2, maxhist = 1, currenthist = 1 -> mostrar y trabajar con [...]
-cuando hacemos algo habiendo dado a deshacer anteriormente [[],[...]] primero sacamos todos los elementos necesarios hasta que maxhist == currenthist y despues añadimos el elementoal historial.

Formato del fichero de modos en json:
[ [NombreDeLaConfiguracion, QuieresBorde?, color (0,1) , EsquinasRedondeadas?, Formato (0,1,2), N,M], [...], ... ]
"""

class ConvertAndHold:
	def __init__(self, parent = None):
		self.history = [[]]
		self.maxhist = 0
		self.currenthist = 0
		self.parent = parent
		self.clear()

	def clear(self):
		self.basename = None
		self.png = []

	def saveHistory(self):
		while self.maxhist > self.currenthist:
			print "Borrando: %r" % len(self.history)
			self.maxhist -= 1
			self.history.pop()
		self.history.append(self.getPngList())
		self.maxhist += 1
		self.currenthist += 1

	def undo(self):
		if self.currenthist > 0:
			self.currenthist -= 1
			self.setPngList(self.history[self.currenthist])
			self.parent.updatePreview()
		self.parent.say("Paso " + str(self.currenthist + 1) + " de " + str(len(self.history)))

	def redo(self):
		if self.currenthist < self.maxhist:
			self.currenthist += 1
			self.setPngList(self.history[self.currenthist])
			self.parent.updatePreview()
		self.parent.say("Paso " + str(self.currenthist + 1) + " de " + str(len(self.history)))

	def imgImport(self, filenames):
		self.clear()
		self.parent.resetPercent()
		self.parent.say("Abriendo")
		for el2 in filenames:
			el = str(el2)
			if el.rfind(".pdf") > 0:
				self.pdfToPng(el)
			else:
				self.png.append(Image(filename = el))
			self.parent.nextPercent(filenames)
		self.parent.completePercent()

	def pdfToPng(self, pdf):
		im = Image(file=open(pdf))
		self.parent.resetPercent()
		for el in im.sequence:
			self.png.append(Image(el))
			self.parent.nextPercent(im.sequence)
		self.parent.completePercent()

	def getPngList(self):
		return [el.clone() for el in self.png]

	def setPngList(self, pngs):
		self.png = [el.clone() for el in pngs]

	def trimAll(self, um):
		self.parent.resetPercent()
		for el in self.png:
			el.trim(fuzz = um)
			self.parent.nextPercent()
			el.reset_coords()
		self.parent.completePercent()

	def setBaseName(self, name):
		self.basename = name

	def writePngFiles(self):
		if self.basename != None:
			base_name = self.basename
		else:
			base_name = "im"
		a=0
		self.parent.resetPercent()
		for el in self.png:
			a+=1
			self.parent.nextPercent()
			self.parent.say("Salvando " + str(a) + " de " + str(len(self.png)))
			el.save(filename = base_name + "-" + str (a) + ".png")
		self.parent.completePercent()

class MainWindow(QMainWindow, Central):

	default_modes = [
		["Personalizado",False, 0, False, 1, 1, 1],
		["PrinterStudio", True, 0, True, 1, 1, 1],
		["CowCow", True, 0, False, 1, 1, 1],
		["Compartir Online", False, 0, False, 0, 3,3]]

	def __init__(self):
		QMainWindow.__init__(self)
		Central.__init__(self)
		self.setupUi(self)
		self.readSettings()
		self.show()
		self.cv = ConvertAndHold(self)
		self.setSignals()
		self.say("Cargado")
		self.percent(100)

	def setSignals(self):
		self.elegir_boton.clicked.connect(self.openfil)
		self.guardar_como_boton.clicked.connect(self.saveimgs)
		self.dividir_boton.clicked.connect(self.divide)
		self.preview_slider.valueChanged.connect(self.preview)
		self.deshacer_boton.clicked.connect(self.cv.undo)
		self.rehacer_boton.clicked.connect(self.cv.redo)
		self.borrar_boton.clicked.connect(self.borrarimg)
		self.negro_boton.clicked.connect(self.ponerBordeNegro)
		self.blanco_boton.clicked.connect(self.ponerBordeBlanco)
		self.quitar_boton.clicked.connect(self.recortarBorde)
		self.auto_boton.clicked.connect(self.myTrim)

	def myTrim(self):
		umb = self.umbral_spin.value()
		if self.todas_radio.isChecked():
			self.cv.trimAll(umb)
		else:
			self.cv.png[self.preview_slider.value()].trim(fuzz = umb)
			self.cv.png[self.preview_slider.value()].reset_coords()
		self.updatePreview()
		self.cv.saveHistory()

	def recortarBorde(self):
		if self.todas_radio.isChecked():
			self.resetPercent()
			for el in self.cv.png:
				w, h = el.size
				ri = w - self.right_spin.value()
				bo = h - self.bottom_spin.value()
				el.crop(left = self.left_spin.value(), top = self.top_spin.value(), right = ri, bottom = bo)
				el.reset_coords()
				self.nextPercent()
			self.completePercent()
		else:
			el = self.cv.png[self.preview_slider.value()]
			w, h = el.size
			ri = w - self.right_spin.value()
			bo = h - self.bottom_spin.value()
			el.crop(left = self.left_spin.value(), top = self.top_spin.value(), right = ri, bottom = bo)
			el.reset_coords()
		self.updatePreview()
		self.cv.saveHistory()

	def split(self, im, n, m):
		width, hight = im.size
		sep = self.sep_spin.value()
		width, hight = (int(width), int(hight))
		cardWidth = (width - sep * (m-1)) / m
		cardHight = (hight - sep * (n-1)) / n
		res = []
		for i in range(n):
			for j in range(m):
				with im.clone() as clon:
					clon.crop(top=i*cardHight+i*sep, width=cardWidth, left=j*cardWidth+j*sep, height=cardHight)
					res.append(clon.clone())

		return res

	def divide(self):
		n = self.n_spin_2.value()
		m = self.m_spin_2.value()
		images = self.cv.getPngList()
		end_images = []
		self.resetPercent()
		for el in images:
			end_images.extend(self.split(el, n, m))
			self.nextPercent(images)
		self.completePercent()
		self.say("Divididas")
		self.cv.setPngList(end_images)
		self.updatePreview(0)
		self.cv.saveHistory()

	def openfil(self):
		files = QFileDialog.getOpenFileNames(self, "Elige uno o mas ficheros", "./") #, "Images (*.png *.jpg);; PDF (*.pdf)")
		names = '"' + str(files[0])[str(files[0]).rfind("/")+1:] +'"'
		for el in files[1:]: names += ', "' + str(el)[str(el).rfind("/")+1:] + '"'
		self.fichero_edit.setText(names)
		self.cv.imgImport(files)
		self.updatePreview(0)
		self.cv.saveHistory()
		self.say("Hecho")

	def saveimgs(self):
		name = QFileDialog.getSaveFileName(self, "Nombre del fichero a guardar", "./")
		self.cv.setBaseName(str(name))
		self.cv.writePngFiles()

	def borrarimg(self):
		num = self.preview_slider.value()
		self.say("Borrando")
		self.cv.png.pop(num)
		self.say("Imagen eliminada")
		if num < len(self.cv.png):
			self.updatePreview(num)
		else:
			self.updatePreview(-1)
		self.cv.saveHistory()

	def ponerBordeNegro(self):
		tam = self.border_spin.value()
		for im in self.cv.png:
			im.border(Color("black"), tam, tam)
		self.updatePreview()
		self.cv.saveHistory()

	def ponerBordeBlanco(self):
		tam = self.border_spin.value()
		for im in self.cv.png:
			im.border(Color("white"), tam, tam)
		self.updatePreview()
		self.cv.saveHistory()

	def say(self, text):
		self.msg_label.setText(text)

	def percent(self, num):
		self.progress_bar.setValue(num)

	def resetPercent(self):
		self.percent(0)

	def nextPercent(self, lis=None):
		if lis == None:
			self.percent(self.progress_bar.value()+100/len(self.cv.png))
		else:
			self.percent(self.progress_bar.value()+100/len(lis))

	def completePercent(self):
		self.percent(100)

	def updatePreview(self, num = None):
		if len(self.cv.png)>0:
			self.preview_slider.setMaximum(len(self.cv.png)-1)
		else:
			self.preview_slider.setMaximum(0)
		if num == None:
			self.preview(self.preview_slider.value())
		else:
			self.preview(num)

	def preview(self, num):
		self.preview_label.clear()
		try:
			self.preview_label.setPixmap(QPixmap(QImage.fromData(self.cv.png[num].make_blob(), self.cv.png[num].format)))
		except:
			self.preview_label.setText("Sin imagenes")

	@pyqtSlot()
	def closeEvent(self, e):
		settings = QSettings("LuisjaCorp", "PnPCards")
		settings.setValue("geometry", self.saveGeometry())
		settings.setValue("windowState", self.saveState())
		QMainWindow.closeEvent(self, e)

	def readSettings(self):
		settings = QSettings("LuisjaCorp", "PnPCards")
		self.restoreGeometry(settings.value("geometry").toByteArray())
		self.restoreState(settings.value("windowState").toByteArray())


#if __name__ == "__main__":
app = QApplication(argv)
ventana = MainWindow()
ventana.show()
app.exec_()
