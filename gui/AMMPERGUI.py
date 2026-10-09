# This Python file uses utf-8 encoding.

"""
Graphical User Interface for AMMPER v2.0

Created by Madeline Marous, in coordination with original code created by Amrita Singh and edited by Daniel Palacios & @dannyofmiami.
Review README and Credits for more information.

"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import ammper_paths as P  # noqa: E402  (resolves data/ and results/ paths)
# GUI modules
import sys
import subprocess
import random

from PyQt5.QtWidgets import QApplication, QWidget, QShortcut, QPushButton, QFileDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QIcon, QFontDatabase, QKeySequence
from PyQt5.QtCore import Qt, QRect
from vgui_form import Ui_Widget # AMMPER interface 
from gui.movieMaker import movie_maker as mm

# AMMPER modules
import numpy as np
import random as rand
import uuid as uuid
from ammper.cellDefinition import Cell
from ammper.genTraverse_groundTesting import genTraverse_groundTesting
from ammper.genTraverse_deepSpace import genTraverse_deepSpace
from ammper.genROS import genROS as _genROS_engine
from ammper.genROSOld import genROSOld
from ammper.cellPlot import cellPlot
from ammper.cellPlot_deepSpace import cellPlot_deepSpace
from ammper.GammaRadGen import GammaRadGen
import os
import time
import pandas as pd
import time
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
start_time = time.time()

# The Complex ROS generator builds all of its output in one blocking call, so the window cannot
# repaint while it runs (about 10 s at 2.5 Gy, minutes at higher doses). Say so on the progress
# screen first so the pause is not silent. Same call, same result: only a label update is added.
_running_sim = None


def genROS(radData, cells):
    if _running_sim is not None:
        _running_sim.label_2.setText(
            "Building Complex ROS data. This window may pause here (longer at higher doses).")
        QApplication.processEvents()
    return _genROS_engine(radData, cells)


class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Widget()
        self.ui.setupUi(self)

        # Accessibility: enable zoom to allow users to scale up or down UI
        self._zoom_level = 1.0
        self._zoom_baseline = self._captureZoomBaseline()
        self._shortcut_zoom_in = QShortcut(QKeySequence("Ctrl+="), self, self.zoomIn)
        self._shortcut_zoom_in_alt = QShortcut(QKeySequence(QKeySequence.ZoomIn), self, self.zoomIn)
        self._shortcut_zoom_out = QShortcut(QKeySequence(QKeySequence.ZoomOut), self, self.zoomOut)
        self._shortcut_zoom_reset = QShortcut(QKeySequence("Ctrl+0"), self, self.zoomReset)

        # Accessibility: buttons had no hover/pressed/keyboard-focus
        self.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #1a1a2e;
                border: 1px solid #8a8ea3;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #dfe1f5;
                color: #1a1a2e;
                border: 1px solid #50526b;
            }
            QPushButton:pressed {
                background-color: #a0a4e3;
                color: #1a1a2e;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #9a9a9a;
                border: 1px solid #cfcfcf;
            }
            QPushButton:focus {
                border: 2px solid #50526b;
            }
            QRadioButton:focus, QCheckBox:focus {
                outline: 2px solid #50526b;
            }
            /* Drawn by Qt, not the OS theme, so it keeps its colors even if the native macOS
               bar would render gray (e.g. when this window is not the active one). */
            QProgressBar {
                border: none;
                border-radius: 3px;
                background-color: #888cc1;
                margin: 8px 0px;
            }
            QProgressBar::chunk {
                background-color: #001f98;
                border-radius: 3px;
            }
        """)
        self.ui.progressBar.setTextVisible(False)

        for _btn in self.findChildren(QPushButton):
            _btn.setAttribute(Qt.WA_Hover, True)

        self.ui.stackedWidget.setCurrentIndex(0)
        self.ui.label_33.setStyleSheet("color: white;")
        self.ui.label_34.setStyleSheet("color: white;")

        # Confirming connection from UI layout.
        self.stackedWidget = self.ui.stackedWidget

        self.radioButton = self.ui.radioButton
        self.radioButton_2 = self.ui.radioButton_2
        self.radioButton_3 = self.ui.radioButton_3
        self.radioButton_4 = self.ui.radioButton_4
        
        self.radioButton_5 = self.ui.radioButton_5
        self.radioButton_6 = self.ui.radioButton_6

        self.radioButton_7 = self.ui.radioButton_7
        self.radioButton_8 = self.ui.radioButton_8

        self.horizontalSlider = self.ui.horizontalSlider
        
        self.progressBar = self.ui.progressBar

        self.plainTextEdit = self.ui.plainTextEdit

        self.label = self.ui.label
        self.label_2 = self.ui.label_2
        self.label_3 = self.ui.label_3
        self.label_4 = self.ui.label_4
        self.label_5 = self.ui.label_5
        self.label_6 = self.ui.label_6
        self.label_7 = self.ui.label_7

        self.checkBox = self.ui.checkBox
        self.checkBox_2 = self.ui.checkBox_2
        self.checkBox_2.setChecked(True)

        self.customExportPathValid = False
        self.path = ""

        self.pushButton_4 = self.ui.pushButton_4

        # Connecting GUI framework to AMMPER code.
        self.ui.pushButton.clicked.connect(self.pushButton_clicked) # Launch GUI
        self.ui.pushButton_2.clicked.connect(self.pushButton_2_clicked) # Launch CLI
        self.ui.pushButton_3.clicked.connect(self.pushButton_3_clicked) # Credits

        self.ui.pushButton_4.clicked.connect(self.pushButton_4_clicked) # Set Up + Run Simulation
        self.ui.pushButton_5.clicked.connect(self.pushButton_5_clicked) # Exit
        self.ui.pushButton_6.clicked.connect(self.goBack) # Backwards Credits
        self.ui.pushButton_7.clicked.connect(self.visualization) # Visualization
        self.ui.pushButton_8.clicked.connect(self.pushButton_5_clicked) # Exit
        self.ui.pushButton_9.clicked.connect(self.newSimulation) # New Simulation, from results page
        self.ui.pushButton_10.clicked.connect(self.newSimulation) # New Simulation, from visualization page

        # Connecting radio buttons.
        self.radioButton.toggled.connect(self.onRadioButtonClicked)
        self.radioButton_2.toggled.connect(self.onRadioButtonClicked)
        self.radioButton_3.toggled.connect(self.onRadioButtonClicked)
        self.radioButton_4.toggled.connect(self.onRadioButtonClicked)
        
        self.radioButton_5.toggled.connect(self.onRadioButtonClicked2)
        self.radioButton_6.toggled.connect(self.onRadioButtonClicked2)

        self.radioButton_7.toggled.connect(self.onRadioButtonClicked3)
        self.radioButton_8.toggled.connect(self.onRadioButtonClicked3)
        # Basic ROS is the default; Complex ROS is selectable, and Launch warns (never blocks)
        # when this machine looks short of memory for the chosen dose (_confirmComplexROS).
        self.radioButton_7.setChecked(True)

        self.ui.checkBox.stateChanged.connect(self.fileExport)
        self.ui.checkBox_2.stateChanged.connect(self.fileExport)

        self.ui.pushButton_11.clicked.connect(self.browseForExportPath)

        self.horizontalSlider.valueChanged.connect(self.Slider)
        self.slider = self.horizontalSlider.value()

        # Initializing variables.

        self.radAmount = 0.0
        self.cellType = "" 
        self.radType = ""  
        self.N = 0
        self.gen = 0
        self.ROSType = "Basic ROS"
        self.Gy = float(0)
        self.simDescription = ""
        self.sliderOn = True
        # Starting boolean
        self.display = True
        self.fileWritten = False
        self.pushButton_4.setEnabled(False)
        self.dirRadCells = []

    def _captureZoomBaseline(self):
        """Zoom feature to resize GUI
        """
        baseline = {"window": self.geometry()}
        for w in self.findChildren(QWidget):
            entry = {"geometry": w.geometry()}
            font = w.font()
            if font.pointSize() > 0:
                entry["pointSize"] = font.pointSize()
            baseline[w] = entry
        return baseline

    def _applyZoom(self):
        level = self._zoom_level
        win_geo = self._zoom_baseline["window"]
        self.setGeometry(QRect(
            win_geo.x(), win_geo.y(),
            int(win_geo.width() * level), int(win_geo.height() * level),
        ))
        for w, entry in self._zoom_baseline.items():
            if w == "window":
                continue
            geo = entry["geometry"]
            w.setGeometry(QRect(
                int(geo.x() * level), int(geo.y() * level),
                int(geo.width() * level), int(geo.height() * level),
            ))
            if "pointSize" in entry:
                font = w.font()
                # Floor of 6pt: below that, IBM Plex Sans (like most
                # fonts) stops being legible regardless of zoom intent.
                font.setPointSize(max(6, round(entry["pointSize"] * level)))
                w.setFont(font)

    def zoomIn(self):
        self._zoom_level = min(3.0, round(self._zoom_level + 0.1, 2))
        self._applyZoom()

    def zoomOut(self):
        self._zoom_level = max(0.5, round(self._zoom_level - 0.1, 2))
        self._applyZoom()

    def zoomReset(self):
        self._zoom_level = 1.0
        self._applyZoom()

    def pushButton_clicked(self):
        self.stackedWidget.setCurrentIndex(1)

    def pushButton_2_clicked(self):
        self.close() #corrected for closing GUI gracefully.
        QApplication.processEvents()
        subprocess.call([sys.executable, "-m", "ammper.AMMPERCLI"]) # Launch CLI
        QApplication.exit()

    def pushButton_3_clicked(self):
        self.stackedWidget.setCurrentIndex(4)

    def _confirmComplexROS(self):
        """Warn (not forbid) before a Complex ROS run this machine may not be able to hold.

        Returns True to go ahead. Complex ROS needs about 0.74 GB of RAM per Gy and can stall
        or crash a small machine, so ask first. Does nothing for Basic ROS, nor when this
        machine has the memory for the chosen dose.
        """
        if self.ROSType != "Complex ROS":
            return True
        from ammper import preflight
        # Gamma runs at a fixed 1 Gy; Proton uses the slider's dose
        dose = self.Gy if self.radType == "150 MeV Proton" else 1.0
        warning = preflight.complex_ros_warning(self.radType, dose)
        if warning is None:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Complex ROS may not run on this machine")
        box.setText("This computer may not have enough free memory for this Complex ROS run.")
        box.setInformativeText(warning + "\n\nRun it anyway?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        return box.exec_() == QMessageBox.Yes

    def pushButton_4_clicked(self):
        if not self._confirmComplexROS():
            return
        if self.display:
            self.stackedWidget.setCurrentIndex(2)
            self.progressBar.setValue(0)
            # fix for progress screen
            QApplication.processEvents()
            self.simSetup()
        else: 
            self.stackedWidget.setCurrentIndex(2)
            QApplication.exit()

    def pushButton_5_clicked(self):
        QApplication.exit()

    def goBack(self):
        self.stackedWidget.setCurrentIndex(0)

    def newSimulation(self):
        # adding newSimulation to rerun a new sim in GUI 
        self.progressBar.setValue(0)
        self.stackedWidget.setCurrentIndex(1)

    def onRadioButtonClicked(self):
        if self.radioButton.isChecked():
            self.sliderOn = True
            self.Gy = float(self.radAmount)
            self.radType = "150 MeV Proton"
            self.horizontalSlider.setEnabled(self.sliderOn)
            self.gen = 15
            self.radGen = 2
            self.N = 64

            if self.Gy == 0:
                self.radData = np.zeros([1,6],dtype = float)
                self.ROSData = np.zeros([1,6],dtype = float)

        if self.radioButton_2.isChecked():
            self.sliderOn = False
            self.radType = "GCRSim"
            self.horizontalSlider.setValue(1)
            self.ui.label_11.setText(str(0.5))
            self.horizontalSlider.setEnabled(self.sliderOn)
            self.gen = 15
            self.radGen = 2
            self.N = 64
            self.radData = np.zeros([1,6],dtype = float)
            self.ROSData = np.zeros([1,6],dtype = float)

        if self.radioButton_3.isChecked():
            self.sliderOn = False
            self.radType = "Deep Space"
            self.horizontalSlider.setValue(1)
            self.radAmount = 0
            self.ui.label_11.setText(str(0))
            self.horizontalSlider.setEnabled(self.sliderOn)
            self.gen = 15
            self.N = 300
            self.radGen = 0
            self.Gy = 0
            self.radData = np.zeros([1,6],dtype = float)
            self.ROSData = np.zeros([1,6],dtype = float)

        if self.radioButton_4.isChecked():
            self.sliderOn = False
            self.radType = "Gamma"
            self.horizontalSlider.setValue(1)
            self.ui.label_11.setText(str(0))
            self.horizontalSlider.setEnabled(self.sliderOn)
            self.gen = 15
            self.radGen = 10
            self.N = 64
            self.radData = np.zeros([1,6],dtype = float)
            self.ROSData = np.zeros([1,6],dtype = float)

        print(self.radType, self.sliderOn)
        self._updateLaunchEnabled()

    def Slider(self):
        if self.sliderOn:
            self.slider = self.horizontalSlider.value()
            if self.slider == 1:
                self.radAmount = 0
            elif self.slider == 2:
                self.radAmount = 2.5
            elif self.slider == 3:
                self.radAmount = 5
            elif self.slider == 4:
                self.radAmount = 10
            elif self.slider == 5:
                self.radAmount = 20
            elif self.slider == 6:
                self.radAmount = 30
        else:
            if self.radType == "GCRSim":
                self.radAmount = 0.5

            if self.radType == "Deep Space" or self.radType == "Gamma":
                self.radAmount = 0

        self.Gy = float(self.radAmount)
        self.ui.label_11.setText(str(self.radAmount))

    def onRadioButtonClicked2(self):
        if self.radioButton_5.isChecked():
            self.cellType = "wt"
        elif self.radioButton_6.isChecked():
            self.cellType = "rad51"
        self._updateLaunchEnabled()

    def onRadioButtonClicked3(self):
        if self.radioButton_7.isChecked():
            self.ROSType = "Basic ROS"
        elif self.radioButton_8.isChecked():
            self.ROSType = "Complex ROS"
        self._updateLaunchEnabled()

    def _updateLaunchEnabled(self):
        # Launch needs all three choices. Basic ROS is pre-selected, so this
        # can't depend on a ROS click; getattr covers the pre-selection firing
        # in __init__ before radType/cellType are initialized.
        ready = all(getattr(self, name, "") for name in ("radType", "cellType", "ROSType"))
        self.pushButton_4.setEnabled(ready)

    def browseForExportPath(self):
        # A native picker instead of specifying filepath to save results to. 
        start_dir = self.path or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(
            self, "Select a folder to export results to", start_dir
        )
        if chosen:
            self.path = chosen
            self.plainTextEdit.setPlainText(chosen)
            self.checkBox.setChecked(True)
            self.fileExport()

    def fileExport(self):
        if self.checkBox.isChecked():
            self.fileWritten = True
            if not self.path:
                self.customExportPathValid = False
                self.label_7.setText("Click Browse... to choose a folder.")
                self.label_7.setStyleSheet("color: red;")
            else:

                if os.path.isdir(self.path) and os.access(self.path, os.W_OK):
                    self.customExportPathValid = True
                    self.label_7.setText("Valid folder.")
                    self.label_7.setStyleSheet("color: green;")
                else:
                    self.customExportPathValid = False
                    self.label_7.setText("Folder no longer available - using default Results/ folder instead.")
                    self.label_7.setStyleSheet("color: red;")
        else:
            self.customExportPathValid = False
            self.label_7.setText("")
        self.display = self.checkBox_2.isChecked()

    def simSetup(self):
        global _running_sim
        _running_sim = self
        self.simDescription = "Cell Type: " + self.cellType + "\nRad Type: " + self.radType + "\nSim Dim: " +  str(self.N) + "microns\nNumGen: " + str(self.gen) + "ROS model: " + str(self.ROSType)
        if self.radType == "150 MeV Proton":
            self.simDescription += "\nDose: " + f"{self.Gy:g}" + " Gy"

        self.resultsName = "ammper_" + time.strftime('%Y-%m-%d_%H-%M-%S') + "/"
        # determine path that all results will be written to
        useCustomPath = self.checkBox.isChecked() and self.path and self.customExportPathValid
        if useCustomPath:
            resultsFolder = self.path.rstrip("/\\") + "/"
        else:
            resultsFolder = r"Results/"
        #currPath = os.path.dirname("AMMPER")
        allResults_path = os.path.join(resultsFolder)
        self.currResult_path = os.path.join(allResults_path,self.resultsName)
        plots_path = os.path.join(self.currResult_path,r"Plots/")

    # if any of the folders do not exist, create them
        if not os.path.isdir(resultsFolder):
            os.makedirs(resultsFolder)
        if not os.path.isdir(self.currResult_path):
            os.makedirs(self.currResult_path)
        if not os.path.isdir(plots_path):
            os.makedirs(plots_path)

        # write description to file
        np.savetxt(self.currResult_path+'simDescription.txt',[self.simDescription],fmt='%s')

    # SIMULATION SPACE INITIALIZATION

    # cubic space (0 = no cell, 1 = healthy cell, 2 = damaged cell, 3 = dead cell)
        T = np.zeros((self.N,self.N,self.N),dtype = int)
    # END OF SIMULATION SPACE INITIALIZATION
    # CELL INITIALIZATION

    # first cell is at center and is healthy
        firstCellPos = [int(self.N/2),int(self.N/2),int(self.N/2)]
        initCellHealth = 1

    # cells = list of cells - for new cells, cells.append
       # firstCellPos = initCellPos[0,:]
        firstUUID = uuid.uuid4()
        firstCell = Cell(firstUUID,firstCellPos,initCellHealth,0,0,0,0)
        T[firstCellPos[0],firstCellPos[1],firstCellPos[2]] = firstCell.health
        cells = [firstCell]
        # data: [generation, cellPosition, cellHealth]
        data = [0,firstCell.position[0],firstCell.position[1],firstCell.position[2],firstCell.health]    

    # END OF CELL INITIALIZATION

        self.ui.label_10.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label_10.setScaledContents(True)

    #placeholder initialization
        if self.radType == "Deep Space":
            self.radData = np.zeros([1,7],dtype = float)
            self.ROSData = np.zeros([1,7],dtype = float)

        self.fact_list = ["AMMPER incorporates data from BioSentinel, the first biological CubeSat to fly beyond Low Earth Orbit (LEO).",
                          "AMMPER models after yeast (Saccharomyces cerevisiae) cells because they are eukaryotic, therefore similar in biology to human cells.", 
                          "AMMPER was first created by Amrita Singh in 2021.", "AMMPER is currently available for download under an open-source agreement.", 
                          "AMMPER is the first microbial model (to our knowledge) to study the effects of deep-space radiation on individual cells."]
        self.random_item = random.choice(self.fact_list)
        self.label_3.setText("Did you know: " + self.random_item)

        self.label_2.setText("Simulation beginning.")
        current_value = 0
        for g in range(1,self.gen + 1):
            self.label_2.setText("Generation " + str(g))
            current_value = self.progressBar.value()
            self.progressBar.setValue(current_value + 5)
            QApplication.processEvents()


            if self.radType == "Gamma":
                if g == self.radGen:

                    dose = 1
                    # radData = np.zeros([1, 6], dtype=float)
                    # Dose input, radGenE stop point for gamma radiation.
                    self.radData = GammaRadGen(dose)
                    # radData = np.delete(radData, (0), axis=0)

                    if self.ROSType == "Complex ROS":
                        self.ROSData = genROS(self.radData, cells)
                    if self.ROSType == "Basic ROS":
                        self.ROSData = genROSOld(self.radData, cells)

            if self.radType == "150 MeV Proton":

                if g == self.radGen:
                    protonEnergy = 150
                    # these fluences are pre-calculated to deliver the dose to the volume of water
                    if self.Gy != 0:
                        if self.Gy == 2.5:
                            trackChoice = [1]
                            energyThreshold = 0
                        elif self.Gy == 5:
                            trackChoice = [1,1]
                            energyThreshold = 0
                        elif self.Gy == 10:
                            trackChoice = [1,1,1,1]
                            energyThreshold = 0
                        elif self.Gy == 20:
                            trackChoice = [1,1,1,1,1,1,1,1]
                            energyThreshold = 0
                        elif self.Gy == 30:
                            trackChoice = [1,1,1,1,1,1,1,1,1,1,1,1]
                            energyThreshold = 0

                        # placeholder initialization - will hold information on all radiation energy depositions
                        self.radData = np.zeros([1,6],dtype = float)
                        # ROSData = np.zeros([1,6],dtype = float)

                        for track in trackChoice:
                            trackNum = track
                            # creates a traverse for every track in trackChoice
                            radData_trans = genTraverse_groundTesting(self.N,protonEnergy,trackNum,energyThreshold,self.radType)
                            # compile all energy depositions from individual tracks together
                            self.radData = np.vstack([self.radData,radData_trans])

                        #remove placeholder of 0s from the beginning of radData
                        self.radData = np.delete(self.radData,(0),axis = 0)

                        # direct energy results in ROS generation - use energy depositions to calculate ROS species
                        if self.ROSType == "Complex ROS":
                            self.ROSData = genROS(self.radData,cells)
                        if self.ROSType == "Basic ROS":
                            self.ROSData = genROSOld(self.radData,cells)

                        #
                        # ROSData = np.delete(ROSData, (0), axis = 0)

            elif self.radType == "Deep Space":

                # take information from text file for #tracks of each proton energy
                deepSpaceFluenceDat = np.genfromtxt(P.fluence('DeepSpaceFluence0.1months_data.txt'))
                # NOTE: For Deep Space sim, radiation delivery is staggered over time
                for it in range(len(deepSpaceFluenceDat)):
                    # get generation at which traversal will occur
                    currG = int(deepSpaceFluenceDat[it,5])
                    # determine how many traversals occur at this generation
                    numTrav = int(deepSpaceFluenceDat[it,4])
                    if g == currG:
                        # determine what proton energy the traversal has
                        protonEnergy = deepSpaceFluenceDat[it,0]
                        # parameter that allows non-damaging energy depositions to be ignored (used to speed up simulation)
                        energyThreshold = 20
                        for track in range(numTrav):
                            # choose a random track out of the 8 available/proton energy
                            # @TODO TRACK RANGE: never picks Track7 (0-6 only). Full note in src/ammper/AMMPERCLI.py's Deep Space branch.
                            trackNum  = int(rand.uniform(0,7))
                            # generate traversal data for omnidirectional traversals
                            radData_trans = genTraverse_deepSpace(self.N,protonEnergy,trackNum,energyThreshold)
                            # generate ROS data from the traversal energy deposition
                            # ROSData_new = genROS(radData_trans,cells)
                            if self.ROSType == "Complex ROS":
                                ROSData_new = genROS(radData_trans, cells)
                            if self.ROSType == "Basic ROS":
                                ROSData_new = genROSOld(radData_trans, cells)

                            # creates a column indicating what generation the radData occured at
                            genArr = np.ones([len(radData_trans),1],dtype=int)*g
                            # compile radData with the generation indicator
                            radData_trans = np.hstack((radData_trans,genArr))
                            # compile radData from this traversal with all radData
                            self.radData = np.vstack([self.radData,radData_trans])

                            # fix for numpy row-count mismatch in hstack tp
                            # ROSData_new's actual row count.
                            genArr_ros = np.ones([len(ROSData_new),1],dtype=int)*g
                            ROSData_new = np.hstack((ROSData_new,genArr_ros))
                            #compile ROSData with all ROSData
                            self.ROSData = np.vstack([self.ROSData,ROSData_new])

            elif self.radType == "GCRSim":
                if g == self.radGen:
                    # placeholder initialization
                    self.radData = np.zeros([1,6],dtype = float)
                    # take information from text file on traversals that will occur
                    GCRSimFluenceDat = np.genfromtxt(P.fluence('GCRSimFluence_data.txt'),skip_header = 1)
                    for it in range(len(GCRSimFluenceDat)):
                        # for every traversal, get the proton energy of it
                        protonEnergy = int(GCRSimFluenceDat[it,0])
                        # parameter that allows non-damaging energy depositions to be ignored (used to speed up simulation)
                        energyThreshold = 20
                        # choose a random track out of the 8 available/proton energy
                        # @TODO TRACK RANGE: never picks Track7 (0-6 only). Full note in src/ammper/AMMPERCLI.py's Deep Space branch.
                        trackNum = int(rand.uniform(0,7))
                        # generate traversal data for unidirectional traversals
                        radData_trans = genTraverse_groundTesting(self.N,protonEnergy,trackNum,energyThreshold,self.radType)
                        # compile radData from this traversal with all radData
                        self.radData = np.vstack([self.radData,radData_trans])

                        #remove placeholder from beginning
                        # @TODO DROPPED EVENTS: this delete runs inside the loop, dropping 13 real GCRSim events per run. Full note in src/ammper/AMMPERCLI.py's GCRSim branch.
                        self.radData = np.delete(self.radData,(0),axis = 0)
                    # generate ROS data from all traversal energy depositions
                    #ROSData = genROS(radData,cells)
                    if self.ROSType == "Complex ROS":
                        self.ROSData = genROS(self.radData, cells)
                    if self.ROSType == "Basic ROS":
                        self.ROSData = genROSOld(self.radData, cells)


            # initialize list of cells that have moved
            movedCells = []
            # for every existing cell, determine whether a cell moves. If it does, write it to the list
            for c in cells:

                initPos = c.position
                initPos = [initPos[0],initPos[1],initPos[2]]
                movedCell = c.brownianMove(T,self.N,g)
                newPos = movedCell.position
                # if cell has moved
                if initPos != newPos and newPos != -1:
                    # document new position in simulation space, and assign old position to empty
                    T[initPos[0],initPos[1],initPos[2]] = 0
                    T[newPos[0],newPos[1],newPos[2]] = c.health

                    movedCells.append(c)

            # initialize list of new cells
            newCells = []
            # for every existing cell, determine whether a cell replicates. If it does, write the new cell to the list
            for c in cells:

                health = c.health
                #position = c.position
                UUID = c.UUID

                # cell replication
                if health == 1:
                    # cellRepl returns either new cell, or same cell if saturation conditions occur
                    newCell = c.cellRepl(T,self.N,g)
                    newCellPos = newCell.position
                    newCellUUID = newCell.UUID
                    # if newCell the same as old cell, then saturation conditions occurred, and no replication took place
                    if newCellUUID != UUID and newCellPos != -1:
                        # only document new cell if old cell replicated
                        # if new cell is avaialble, assign position as filled
                        T[newCellPos[0],newCellPos[1],newCellPos[2]] = 1
                        newCells.append(newCell)


            # if radiation traversal has occured
            if (self.radType == "150 MeV Proton" and g == self.radGen and self.Gy != 0) or (self.radType == "Deep Space") or (self.radType == "GCRSim" and g == self.radGen) or (self.radType == "Gamma" and g >= self.radGen):
                # initialize list of cells affected by ion/electron energy depositions
                self.dirRadCells = []
                for c in cells:
                    health = c.health
                    if self.cellType == "wt":
                        radCell = c.cellRad(g,self.radGen,self.radData,self.radType)
                    elif self.cellType == "rad51":
                        radCell = c.cellRad_rad51(g,self.radGen,self.radData,self.radType)
                    if type(radCell) == Cell:
                        newHealth = radCell.health
                        if health != newHealth:
                            radCellPos = radCell.position
                            T[radCellPos[0],radCellPos[1],radCellPos[2]] = newHealth
                            self.dirRadCells.append(radCell)
                            ######################################################################
            # if ROS generation has occured (post-radiation)
            if (self.radType == "150 MeV Proton" and g >= self.radGen and self.Gy != 0) or (self.radType == "Deep Space") or (self.radType == "GCRSim" and g >= self.radGen) or (self.radType == "Gamma" and g >= self.radGen):
                # initialize list of cells affected by ROS
                ROSCells = []
                for c in cells:
                    health = c.health
                    if self.cellType == "wt":
                        ROSCell = c.cellROS(g,self.radGen,self.ROSData,self.radType)
                    elif self.cellType == "rad51":
                        ROSCell = c.cellROS_rad51(g,self.radGen,self.ROSData,self.radType)
                    newHealth = ROSCell.health
                    if health != newHealth:
                        ROSCellPos = ROSCell.position
                        T[ROSCellPos[0],ROSCellPos[1],ROSCellPos[2]] = newHealth
                        ROSCells.append(ROSCell)
            # if radiation has occured and cell type is NOT rad51 (cellType = wild type)
            if (self.radType == "150 MeV Proton" and g > self.radGen and self.Gy != 0 and self.cellType != "rad51") or (self.radType == "Deep Space" and self.cellType != "rad51") or (self.radType == "GCRSim" and g > self.radGen and self.cellType != "rad51") or (self.radType == "Gamma" and g >= self.radGen and self.cellType != "rad51"):
                # initialize list of cells that have undergone repair mechanisms
                repairedCells = []
                for c in cells:
                    health = c.health
                    if health == 2:
                        repairedCell = c.cellRepair(g)
                        newHealth = repairedCell.health
                        repairedCellPos = repairedCell.position
                        T[repairedCellPos[0],repairedCellPos[1],repairedCellPos[2]] = newHealth
                        repairedCells.append(repairedCell)

            # documenting cell movement in the cells list
            for c in movedCells:
                cUUID = c.UUID
                newPos = c.position
                for c2 in cells:
                    c2UUID = c2.UUID
                    if cUUID == c2UUID:
                        c2.position = newPos

            # documenting cell replication in the cells list
            cells.extend(newCells)

            # documenting cell damage
            # if radiation has occurred
            if (self.radType == "150 MeV Proton" and g >= self.radGen and self.Gy != 0) or self.radType == "Deep Space" or (self.radType == "GCRSim" and g >= self.radGen) or (self.radType == "Gamma" and g >= self.radGen):
                # for every cell damaged by ion or electron energy depositions

                for c in self.dirRadCells:
                    # get information about damaged cell
                    cUUID = c.UUID
                    newHealth = c.health
                    newSSBs = c.numSSBs
                    newDSBs = c.numDSBs
                    # find cell in cell list that matches damaged cell ID
                    for c2 in cells:
                        c2UUID = c2.UUID
                        if cUUID == c2UUID:
                            # adjust information about cell in cell list to reflect damage
                            c2.health = newHealth
                            c2.numSSBs = newSSBs
                            c2.numDSBs = newDSBs
                # for every cell damaged by ROS
                for c in ROSCells:
                    # get information about damaged cell
                    cUUID = c.UUID
                    newHealth = c.health
                    newSSBs = c.numSSBs
                    # find cell in cell list that matches damaged cell ID
                    for c2 in cells:
                        c2UUID = c2.UUID
                        if cUUID == c2UUID:
                            # adjust information about cell in cell list to reflect damage
                            c2.health = newHealth
                            c2.numSSBs = newSSBs

            #documenting cell repair
            # if cell can repair (not rad51), and radiation has occured
            if (self.radType == "150 MeV Proton" and g > self.radGen and self.Gy != 0 and self.cellType != "rad51") or (self.radType == "Deep Space" and self.cellType != "rad51") or (self.radType == "GCRSim" and g > self.radGen and self.cellType != "rad51") or (self.radType == "Gamma" and g >= self.radGen and self.cellType != "rad51"):
                # for every cell that has undergone repair
                for c in repairedCells:
                    # get information about repaired cell
                    cUUID = c.UUID
                    newHealth = c.health
                    newSSBs = c.numSSBs
                    newDSBs = c.numDSBs
                    # find cell in cell list that matches repaired cell ID
                    for c2 in cells:
                        c2UUID = c2.UUID
                        if cUUID == c2UUID:
                            # adjust information about cell in cell list to reflect repair
                            c2.health = newHealth
                            c2.numSSBs = newSSBs
                            c2.numDSBs = newDSBs

            # adjust data with new generational data
            # column array to denote that new data entries are at the current generation
            genArr = np.ones([len(cells),1],dtype=int)*g
            # get cell information to store in data
            # initialize cellsHealth and cellsPos with placeholders
            cellsHealth = [0]
            cellsPos = [0,0,0]
            # for each cell, get all the associated information
            for c in cells:
                currPos = [c.position]
                currHealth = [c.health]
                # record all cell positions and healths in a list, with each cell being a new row
                cellsPos = np.vstack([cellsPos,currPos])
                cellsHealth = np.vstack([cellsHealth, currHealth])
            #remove placeholder values
            cellsPos = np.delete(cellsPos,(0),axis = 0)
            cellsHealth = cellsHealth[1:]
            # compile cell information with genArr
            newData = np.hstack([genArr,cellsPos,cellsHealth])

            # compile new generation data with the previous data
            data = np.vstack([data,newData])
        ######################################## Random decay, lifetime ROS for complex model ################################
            if self.ROSType == "Complex ROS":
                if g > self.radGen:
                    # half life 1 gen = .5, half life 2 gen = .707, half life 3 gen = .7937, 20 min half life = .125
                    if len(self.ROSData) > 1:
                        ROSDatak  , ROSData_decayed = train_test_split(self.ROSData, train_size = 0.5)
                        self.ROSData = ROSDatak
                    elif len(self.ROSData) == 1 and rand.random() < 0.5:
                        # a single remaining event can't be split 50/50 by count;
                        # apply the same half-life odds directly instead
                        self.ROSData = np.zeros([1,6],dtype = float)

        
        self.label_2.setText("Complete. Rendering plots - this can take a few seconds.")
        self.progressBar.setValue(current_value + 5)
        QApplication.processEvents()

        # for each simulation type, write the data to a text file titled by the radType
        # for each simulation type, plot the data as 1 figure/generation
  
        #fig, ax = plt.subplots()

        if self.radType == "150 MeV Proton":
            datName = str(self.radAmount)+'Gy'
            dat_path = self.currResult_path + datName + ".txt"
            if self.fileWritten: 
                np.savetxt(dat_path,data,delimiter = ',')
                # if ROSData != 0: for 0 Gy
                cellPlot(data, self.gen, self.radData,self.ROSData,self.radGen,self.N,plots_path)
            if self.display:
                cellPlot(data, self.gen, self.radData,str(self.ROSData),str(self.radGen),self.N, plots_path)

        elif self.radType == "Deep Space":
            datName = 'deepSpace'
            dat_path = self.currResult_path + datName + ".txt"
            if self.fileWritten: 
                np.savetxt(dat_path,data,delimiter = ',')
                cellPlot(data, self.gen, self.radData,self.ROSData,self.radGen,self.N,plots_path)
            if self.display:
                cellPlot(data, self.gen, self.radData,self.ROSData,self.radGen,self.N,plots_path)
            
        elif self.radType == "GCRSim":
            datName = 'GCRSim'
            dat_path = self.currResult_path + datName + ".txt"
            if self.fileWritten: 
                np.savetxt(dat_path,data,delimiter = ',')
                cellPlot(data, self.gen, self.radData,self.ROSData,self.radGen,self.N,plots_path)
            if self.display:
                cellPlot(data, self.gen, self.radData,self.ROSData,self.radGen,self.N,plots_path)

        elif self.radType == "Gamma":
            datName = 'Gamma'
            dat_path = self.currResult_path + datName + ".txt"
            if self.fileWritten: 
                np.savetxt(dat_path,data,delimiter = ',')
                cellPlot(data, self.gen, self.radData,self.ROSData,self.radGen,self.N,plots_path)
            if self.display:
                cellPlot(data, self.gen, self.radData,self.ROSData,self.radGen,self.N,plots_path)

        self.progressBar.setValue(100)
        self.label_2.setText("Plots and data written.")
        self.ui.label.setText("Time elapsed: \n{:.2f}s".format(time.time() - start_time))

        #gen1
        self.path1 = plots_path + "fig1.png"
        self.pixmapg1 = QPixmap(self.path1)

        #gen2
        self.path2 = plots_path + "fig2.png"
        self.pixmapg2 = QPixmap(self.path2)

        #gen3
        self.path3 = plots_path + "fig3.png"
        self.pixmapg3 = QPixmap(self.path3)
        
        #gen4
        self.path4 = plots_path + "fig4.png"
        self.pixmapg4 = QPixmap(self.path4)

        #gen5
        self.path5 = plots_path + "fig5.png"
        self.pixmapg5 = QPixmap(self.path5)

        #gen6
        self.path6 = plots_path + "fig6.png"
        self.pixmapg6 = QPixmap(self.path6)

        #gen7
        self.path7 = plots_path + "fig7.png"
        self.pixmapg7 = QPixmap(self.path7)

        #gen8
        self.path8 = plots_path + "fig8.png"
        self.pixmapg8 = QPixmap(self.path8)

        #gen9
        self.path9 = plots_path + "fig9.png"
        self.pixmapg9 = QPixmap(self.path9)

        #gen10
        self.path10 = plots_path + "fig10.png"
        self.pixmapg10 = QPixmap(self.path10)
        
        #gen11
        self.path11 = plots_path + "fig11.png"
        self.pixmapg11 = QPixmap(self.path11)

        #gen12
        self.path12 = plots_path + "fig12.png"
        self.pixmapg12 = QPixmap(self.path12)

        #gen13
        self.path13 = plots_path + "fig13.png"
        self.pixmapg13 = QPixmap(self.path13)

        #gen14
        self.path14 = plots_path + "fig14.png"
        self.pixmapg14 = QPixmap(self.path14)

        #gen15
        self.path15 = plots_path + "fig15.png"
        self.pixmapg15 = QPixmap(self.path15)


        self.ui.label_4.setPixmap(self.pixmapg1)
        self.ui.label_19.setPixmap(self.pixmapg5)
        self.ui.label_12.setPixmap(self.pixmapg9)
        self.ui.label_5.setPixmap(self.pixmapg12)
        self.ui.label_13.setPixmap(self.pixmapg15)

        # Setting label properties
        self.ui.label_4.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label_4.setScaledContents(True)
        self.ui.label_19.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label_19.setScaledContents(True)
        self.ui.label_12.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label_12.setScaledContents(True)
        self.ui.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label.setScaledContents(True)
        self.ui.label_5.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label_5.setScaledContents(True)
        self.ui.label_13.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label_13.setScaledContents(True)

        self.stackedWidget.setCurrentIndex(3)

    def _visualizationFilename(self):
        # Fixing file name for mp4 gen sim
        def _clean(value):
            return str(value).replace(" ", "").replace("/", "-")

        # self.resultsName itself now carries an "ammper_" prefix
        timestamp = self.resultsName.rstrip("/")
        if timestamp.startswith("ammper_"):
            timestamp = timestamp[len("ammper_"):]

        parts = [
            "ammper_sim",
            timestamp,
            _clean(self.radType),
            f"{self.Gy:g}Gy",
            self.cellType,
            _clean(self.ROSType),
            f"N{self.N}",
            f"gen{self.gen}",
        ]
        return "_".join(parts) + ".mp4"

    def visualization(self):
        self.stackedWidget.setCurrentIndex(5)
        self.ui.label_35.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.label_35.setScaledContents(True)
        video_filename = self._visualizationFilename()
        # Fix: Pass empty string to use already-correct paths
        mm("", self.path1, self.path2, self.path3, self.path4, self.path5, self.path6, self.path7, self.path8, self.path9, self.path10, self.path11, self.path12, self.path13, self.path14, self.path15, output_filename=video_filename)
        # Open in the OS default video player. "open" is macOS-only;
        # solution per platform so this works on Windows and Linux too.
        video_path = _os.path.join(P.ROOT, video_filename)
        if sys.platform == "darwin":
            subprocess.call(["open", video_path])
        elif sys.platform == "win32":
            _os.startfile(video_path)
        else:
            subprocess.call(["xdg-open", video_path])
        self.ui.label_35.setPixmap(QPixmap(self.path1))
       

# Widget initialization. 

if __name__ == "__main__":
    if sys.platform == "darwin":
        try:
            from Foundation import NSBundle
            bundle = NSBundle.mainBundle()
            if bundle is not None:
                info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                if info is not None:
                    info["CFBundleName"] = "AMMPER"
        except Exception:
            pass

    app = QApplication([])
    # The .ui-generated forms reference "IBM Plex Sans" (an open-source
    # replacement for "Franklin Gothic Medium/Book", which isn't installed
    _fonts_dir = _os.path.join(P.ROOT, "gui", "fonts", "IBMPlexSans")
    for _font_file in ("IBMPlexSans-Regular.ttf", "IBMPlexSans-Medium.ttf",
                       "IBMPlexSans-Italic.ttf", "IBMPlexSans-MediumItalic.ttf"):
        QFontDatabase.addApplicationFont(_os.path.join(_fonts_dir, _font_file))

    app.setApplicationName("AMMPER")
    app.setApplicationDisplayName("AMMPER")
    app.setOrganizationName("NASA AMMPER")
    app.setWindowIcon(QIcon(_os.path.join(P.ROOT, "images", "ammperbitlogo.ico")))
    widget = Widget()
    widget.show()
    sys.exit(app.exec())
    widget.simDescription()
