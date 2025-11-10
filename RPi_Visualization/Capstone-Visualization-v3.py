from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QHBoxLayout, QPushButton, QGridLayout, QLabel
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QSize
from scipy.signal import butter, filtfilt

import pyqtgraph as pg
import sys
import numpy as np
import spidev
import gpiod
import time

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Demonstration of Electromechanical Relationships in a Controlled Electric Motor")
        self.resize(1920, 1080)

        vertLabelFontSize = '30pt'
        legendFontSize = '22pt'

        pg.setConfigOption('foreground', 'k')
        pg.setConfigOption('background', 'w')

        self.tabs = QTabWidget()

        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #edeceb;
                color: #000000;
                font-size: 30pt;
                height: 70px;
                width: 290px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #000000;
                outline: none
            }
            QTabBar::tab:focus {
                outline: none
            }
            QTabWidget::pane {
                background: #FFFFFF;
                border: 0;
            }                 
            """)

        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabIndex = 0

        # ----- TAB 1 ----- #
        self.timeDomainTab = QWidget()
        grid = QGridLayout()
        
        self.hallLen = 3000
        self.hallPlotLen = 1000
        self.encoderLen = 200
        self.encoderPlotLen = 200
        self.analogLen = 400
        self.analogPlotLen = 200
        self.plotBuffer = 100
        self.speedLen = 101
        self.maxCount = self.hallLen + self.encoderLen + self.analogLen + self.plotBuffer

        self.plotTimeVec = 0.19*np.arange(0,self.analogLen)
        self.hallPlotTimeVec = 0.034*np.arange(0,self.hallPlotLen)
        self.encoderPlotTimeVec = 0.0276*np.arange(0,self.encoderPlotLen)

        vertFont = QFont('Noto Sans', 22)
        vertFont.setWeight(QFont.Light)
        horizFont = QFont('Noto Sans', 22)
        horizFont.setWeight(QFont.Light)
        speedFont = QFont('Noto Sans', 15)
        speedFont.setWeight(QFont.Light)

        plotLineWidth = 6

        # UVW Motor Phase Voltages
        voltagePlot = pg.PlotWidget()
        voltagePlot.setLabel('left','Voltage (V)', **{'font-size': vertLabelFontSize})
        voltagePlot.showGrid(x = True, y = True, alpha = 0.2)
        voltagePlot.setYRange(-23, 23)
        voltagePlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.0f}") for i in [x * 10 for x in range(-2, 3)]]])
        voltagePlot.addLegend(offset = (0,0), labelTextSize = legendFontSize, colCount = 3)
        voltagePlot.getAxis('left').setStyle(tickFont = vertFont)
        voltagePlot.getAxis('bottom').setStyle(tickFont = horizFont)
        grid.addWidget(voltagePlot, 0, 0)

        self.uVolts = np.zeros(self.analogLen) # c95564, 81cca2, 8998d9
        self.uVoltsCurve = voltagePlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.uVolts[0:self.analogPlotLen], pen = pg.mkPen(color = '#EE6677', width = plotLineWidth), name = 'UV')

        self.vVolts = np.zeros(self.analogLen)
        self.vVoltsCurve = voltagePlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.vVolts[0:self.analogPlotLen], pen = pg.mkPen(color = '#228833', width = plotLineWidth), name = 'VW')

        self.wVolts = np.zeros(self.analogLen)
        self.wVoltsCurve = voltagePlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.wVolts[0:self.analogPlotLen], pen = pg.mkPen(color = '#4477AA', width = plotLineWidth), name = 'WU')
        
        # UVW Motor Phase Currents
        currentPlot = pg.PlotWidget()
        currentPlot.setLabel('left','Current (A)', **{'font-size': '27pt'})
        currentPlot.showGrid(x = True, y = True, alpha = 0.2)
        currentPlot.setYRange(-1.2, 1.2)
        currentPlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.1f}") for i in [x * 0.5 for x in range(-2, 3)]]])
        currentPlot.addLegend(offset = (0,0), labelTextSize = legendFontSize, colCount = 3)
        currentPlot.getAxis('left').setStyle(tickFont = vertFont)
        currentPlot.getAxis('bottom').setStyle(tickFont = horizFont)
        grid.addWidget(currentPlot, 0, 1)

        self.uAmps = np.zeros(self.analogLen)
        self.uAmpsCurve = currentPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.uAmps[0:self.analogPlotLen], pen = pg.mkPen(color = "#66CCEE", width = plotLineWidth), name = 'UV')

        self.vAmps = np.zeros(self.analogLen)
        self.vAmpsCurve = currentPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.vAmps[0:self.analogPlotLen], pen = pg.mkPen(color = "#AA3377", width = plotLineWidth), name = 'VW')

        self.wAmps = np.zeros(self.analogLen)
        self.wAmpsCurve = currentPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.wAmps[0:self.analogPlotLen], pen = pg.mkPen(color = "#CCBB44", width = plotLineWidth), name = 'WU')

        # Speed
        self.speedPlot = pg.PlotWidget()
        axis = self.speedPlot.getPlotItem().getAxis('left')
        axis.setLabel('Speed (rpm)', **{'font-size': vertLabelFontSize})
        axis.setWidth(112)
        self.speedPlot.setLabel('bottom','Sample #', **{'font-size': vertLabelFontSize})
        self.speedPlot.showGrid(x = True, y = True, alpha = 0.2)
        self.speedPlot.setYRange(0, 3535)
        self.speedPlot.setXRange(0, 101)
        self.speedPlot.getPlotItem().getAxis('left').setTicks([[(0,'0'),(500,'500'),(1000,'1000'),(1500,'1500'),(2000,'2000'),(2500,'2500'),(3000,'3000'),(3500,'3500'), \
            (-500,'-500'),(-1000,'-1000'),(-1500,'-1500'),(-2000,'-2000'),(-2500,'-2500'),(-3000,'-3000'),(-3500,'-3500')]])
        self.speedPlot.getAxis('left').setStyle(tickFont = speedFont)
        self.speedPlot.getAxis('bottom').setStyle(tickFont = horizFont)
        self.speedPlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 2)
        grid.addWidget(self.speedPlot, 2, 1)

        self.speed = np.zeros(self.speedLen)
        self.speedCurve = self.speedPlot.plot(self.speed, pen = pg.mkPen(color = '#000000', width = plotLineWidth), name = 'Speed')

        self.refSpeed = np.zeros(self.speedLen)
        self.refSpeedVec = np.zeros(self.speedLen+1)
        self.refSpeedCurve = self.speedPlot.plot(self.refSpeedVec[0:(len(self.refSpeedVec)-1)], pen = pg.mkPen(color = '#66CCEE', width = plotLineWidth-2), name = 'Reference')

        # dq0 Voltages
        vdqPlot = pg.PlotWidget()
        vdqPlot.setLabel('left','Voltage (V)', **{'font-size': vertLabelFontSize})
        vdqPlot.setLabel('bottom','T', **{'color': "#ffffff", 'font-size': vertLabelFontSize})
        vdqPlot.showGrid(x = True, y = True, alpha = 0.2)
        vdqPlot.setYRange(-23, 23)
        vdqPlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.0f}") for i in [x * 10 for x in range(-2, 3)]]])
        vdqPlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 3)
        vdqPlot.getAxis('left').setStyle(tickFont = vertFont)
        vdqPlot.getAxis('bottom').setStyle(tickFont = horizFont)
        grid.addWidget(vdqPlot, 1, 0)

        self.dVolts = np.zeros(self.analogLen)
        self.dVoltsVec = np.zeros(self.speedLen)
        self.dVoltsCurve = vdqPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.dVolts[0:self.analogPlotLen], pen = pg.mkPen(color = "#009988", width = plotLineWidth), name = 'd')

        self.qVolts = np.zeros(self.analogLen)
        self.qVoltsVec = np.zeros(self.speedLen)
        self.qVoltsCurve = vdqPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.qVolts[0:self.analogPlotLen], pen = pg.mkPen(color = "#E98043", width = plotLineWidth), name = 'q')

        self.zVolts = np.zeros(self.analogLen)
        self.zVoltsVec = np.zeros(self.speedLen)
        self.zVoltsCurve = vdqPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.zVolts[0:self.analogPlotLen], pen = pg.mkPen(color = '#696969', width = plotLineWidth), name = '0')

        # dq0 Currents
        idqPlot = pg.PlotWidget()
        idqPlot.setLabel('left','Current (A)', **{'font-size': '27pt'})
        idqPlot.setLabel('bottom','Time (ms)', **{'font-size': vertLabelFontSize})
        idqPlot.showGrid(x = True, y = True, alpha = 0.2)
        idqPlot.setYRange(-1.2, 1.2)
        idqPlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.1f}") for i in [x * 0.5 for x in range(-2, 3)]]])
        idqPlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 3)
        idqPlot.getAxis('left').setStyle(tickFont = vertFont)
        idqPlot.getAxis('bottom').setStyle(tickFont = horizFont)
        grid.addWidget(idqPlot, 1, 1)

        self.dAmps = np.zeros(self.analogLen)
        self.dAmpsVec = np.zeros(self.speedLen)
        self.dAmpsCurve = idqPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.dAmps[0:self.analogPlotLen], pen = pg.mkPen(color = "#332288", width = plotLineWidth), name = 'd')

        self.qAmps = np.zeros(self.analogLen)
        self.qAmpsVec = np.zeros(self.speedLen)
        self.qAmpsCurve = idqPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.qAmps[0:self.analogPlotLen], pen = pg.mkPen(color = "#CC6677", width = plotLineWidth), name = 'q')

        self.zAmps = np.zeros(self.analogLen)
        self.zAmpsVec = np.zeros(self.speedLen)
        self.zAmpsCurve = idqPlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.zAmps[0:self.analogPlotLen], pen = pg.mkPen(color = '#696969', width = plotLineWidth), name = '0')

        # Source Phase Voltages
        motorPhasePlot = pg.PlotWidget()
        axis = motorPhasePlot.getPlotItem().getAxis('left')
        axis.setLabel('Voltage (V)', **{'font-size': vertLabelFontSize})
        axis.setWidth(98)
        motorPhasePlot.setLabel('bottom','Time (ms)', **{'font-size': vertLabelFontSize})
        motorPhasePlot.getPlotItem().getAxis('left').setTicks([[(0,'0'),(5,'5'),(10,'10'),(15,'15'),(20,'20')]])
        motorPhasePlot.showGrid(x = True, y = True, alpha = 0.2)
        motorPhasePlot.setYRange(-1, 21)
        motorPhasePlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 3)
        motorPhasePlot.getAxis('left').setStyle(tickFont = vertFont)
        motorPhasePlot.getAxis('bottom').setStyle(tickFont = horizFont)
        grid.addWidget(motorPhasePlot, 2, 0)

        self.uLineVolts = np.zeros(self.analogLen)
        self.uLineVoltsCurve = motorPhasePlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.uLineVolts[0:self.analogPlotLen], pen = pg.mkPen(color = '#c95564', width = plotLineWidth), name = 'U')

        self.vLineVolts = np.zeros(self.analogLen)
        self.vLineVoltsCurve = motorPhasePlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.vLineVolts[0:self.analogPlotLen], pen = pg.mkPen(color = '#81cca2', width = plotLineWidth), name = 'V')

        self.wLineVolts = np.zeros(self.analogLen)
        self.wLineVoltsCurve = motorPhasePlot.plot(self.plotTimeVec[0:self.analogPlotLen],self.wLineVolts[0:self.analogPlotLen], pen = pg.mkPen(color = '#8998d9', width = plotLineWidth), name = 'W')

        self.plots = [voltagePlot, currentPlot, self.speedPlot, vdqPlot, idqPlot, motorPhasePlot]
        self.timeDomainTab.setLayout(grid)

        # ----- TAB 2 ----- #
        self.vectorTab = QWidget()
        grid = QGridLayout()
        leftCol = QGridLayout()
        rightCol = QGridLayout()

        # Vector plot
        dqPlot = pg.PlotWidget()
        dqPlot.getViewBox().setAspectLocked(True, ratio=1)
        dqPlot.setYRange(-15, 15)
        dqPlot.setXRange(-15, 15)
        dqPlot.setLabel('left','q-axis', **{'font-size': vertLabelFontSize})
        dqPlot.setLabel('bottom','d-axis', **{'font-size': vertLabelFontSize})
        container = QWidget()
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0,0,0,0)
        hbox.addStretch(1)
        hbox.addWidget(dqPlot, 10)
        hbox.addStretch(1)
        leftCol.addWidget(container, 1, 0)

        yAxis = pg.PlotDataItem([0, 0], [-30, 30], pen = pg.mkPen(color = "#000000", width = 1))
        dqPlot.addItem(yAxis)
        xAxis = pg.PlotDataItem([-30, 30], [0, 0], pen = pg.mkPen(color = "#000000", width = 1))
        dqPlot.addItem(xAxis)
        dqPlot.getAxis('left').setStyle(tickFont = vertFont)
        dqPlot.getAxis('bottom').setStyle(tickFont = vertFont)

        self.bemfdqVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#66CCEE", width = plotLineWidth))
        dqPlot.addItem(self.bemfdqVector)
        self.bemfdqCurve = dqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#66CCEE", width = plotLineWidth), symbolSize = 25, name = 'Back EMF')

        self.idqVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#AA3377", width = plotLineWidth))
        dqPlot.addItem(self.idqVector)
        self.idqCurve = dqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#AA3377", width = plotLineWidth), symbolSize = 25)

        self.vdqVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#228833", width = plotLineWidth))
        dqPlot.addItem(self.vdqVector)
        self.vdqCurve = dqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#228833", width = plotLineWidth), symbolSize = 25)

        self.CCdqVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#CCBB44", width = plotLineWidth))
        dqPlot.addItem(self.CCdqVector)
        self.CCdqCurve = dqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#CCBB44", width = plotLineWidth), symbolSize = 25)

        self.RsidqVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#4477AA", width = plotLineWidth))
        dqPlot.addItem(self.RsidqVector)
        self.RsidqCurve = dqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#4477AA", width = plotLineWidth), symbolSize = 25)

        legend = pg.LegendItem()
        legend.setParentItem(dqPlot.getPlotItem())
        fontSize = 30
        legend.addItem(self.vdqCurve, f'<span style="font-size:{fontSize}pt;">v<sub>dq</sub> Measured</span>')
        legend.addItem(self.idqCurve, f'<span style="font-size:{fontSize}pt;">v<sub>dq</sub> Estimated</span>')
        legend.addItem(self.RsidqCurve, f'<span style="font-size:{fontSize}pt;">R<sub>s</sub> \U000000d7 i<sub>dq</sub></span>')
        legend.addItem(self.CCdqCurve, f'<span style="font-size:{fontSize}pt;">Cross Coupling</span>')
        legend.addItem(self.bemfdqCurve, f'<span style="font-size:{fontSize}pt;">Back EMF</span>')
        legend.anchor((0, 0), (0, 0))
        legend.setOffset((130, -100))

        equationLabel = QLabel(
            '<span style="color:#AA3377; font-size:30pt; font-weight: bold;">dq Voltage </span>'
            '<span style="color:#000000; font-size:30pt;">&asymp;</span>'
            '<span style="color:#4477AA; font-size:30pt; font-weight: bold;"> Stator Reaction</span>'
            '<span style="color:#000000; font-size:30pt;"> +</span>'
            '<span style="color:#CCBB44; font-size:30pt; font-weight: bold;"> Cross Coupling</span>'
            '<span style="color:#000000; font-size:30pt;"> +</span>'
            '<span style="color:#66CCEE; font-size:30pt; font-weight: bold;"> Back EMF</span>'
        )

        equationLabel.setContentsMargins(0,0,0,0)
        equationLabel.setStyleSheet('padding-bottom: 5px; padding-left: 80px; padding-right: 0px;')
        leftCol.addWidget(equationLabel, 0, 0, alignment=Qt.AlignCenter)

        dqVoltsTimePlot = pg.PlotWidget()
        dqVoltsTimePlot.setLabel('left','Avg. Voltage (V)', **{'font-size': vertLabelFontSize})
        dqVoltsTimePlot.showGrid(x = True, y = True, alpha = 0.2)
        dqVoltsTimePlot.setYRange(-23, 23)
        dqVoltsTimePlot.setXRange(0, self.speedLen)
        dqVoltsTimePlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.0f}") for i in [x * 10 for x in range(-2, 3)]]])
        dqVoltsTimePlot.getAxis('left').setStyle(tickFont = vertFont)
        dqVoltsTimePlot.getAxis('bottom').setStyle(tickFont = horizFont)
        dqVoltsTimePlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 3)
        rightCol.addWidget(dqVoltsTimePlot, 0, 0)

        self.dVoltsTimeCurve = dqVoltsTimePlot.plot(self.dVoltsVec[0:self.speedLen], pen = pg.mkPen(color = "#009988", width = plotLineWidth), name = 'd')

        self.qVoltsTimeCurve = dqVoltsTimePlot.plot(self.qVoltsVec[0:self.speedLen], pen = pg.mkPen(color = "#E98043", width = plotLineWidth), name = 'q')

        self.zVoltsTimeCurve = dqVoltsTimePlot.plot(self.zVoltsVec[0:self.speedLen], pen = pg.mkPen(color = '#696969', width = plotLineWidth), name = '0')

        dqAmpsTimePlot = pg.PlotWidget()
        dqAmpsTimePlot.setLabel('left','Avg. Current (A)', **{'font-size': '27pt'})
        dqAmpsTimePlot.setLabel('bottom','Sample #', **{'font-size': vertLabelFontSize})
        dqAmpsTimePlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.1f}") for i in [x * 0.5 for x in range(-2, 3)]]])
        dqAmpsTimePlot.showGrid(x = True, y = True, alpha = 0.2)
        dqAmpsTimePlot.setYRange(-1.2, 1.2)
        dqAmpsTimePlot.setXRange(0, self.speedLen)
        dqAmpsTimePlot.getAxis('left').setStyle(tickFont = vertFont)
        dqAmpsTimePlot.getAxis('bottom').setStyle(tickFont = horizFont)
        dqAmpsTimePlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 3)
        rightCol.addWidget(dqAmpsTimePlot, 1, 0)

        self.dAmpsTimeCurve = dqAmpsTimePlot.plot(self.dAmpsVec[0:self.speedLen], pen = pg.mkPen(color = "#332288", width = plotLineWidth), name = 'd')

        self.qAmpsTimeCurve = dqAmpsTimePlot.plot(self.qAmpsVec[0:self.speedLen], pen = pg.mkPen(color = "#CC6677", width = plotLineWidth), name = 'q')

        self.zAmpsTimeCurve = dqAmpsTimePlot.plot(self.zAmpsVec[0:self.speedLen], pen = pg.mkPen(color = '#696969', width = plotLineWidth), name = '0')

        grid.addLayout(leftCol, 0, 0)
        grid.addLayout(rightCol, 0, 1)
        self.vectorTab.setLayout(grid)

        # ----- TAB 3 ----- #
        self.rawTab = QWidget()
        grid = QGridLayout()

        hallPlot = pg.PlotWidget()
        hallPlot.setYRange(0, 5)
        hallPlot.setLabel('left','State', **{'font-size': vertLabelFontSize})
        hallPlot.setLabel('bottom','Time (ms)', **{'font-size': vertLabelFontSize})
        hallPlot.getAxis('left').setStyle(tickFont = vertFont)
        hallPlot.getAxis('bottom').setStyle(tickFont = horizFont)
        hallPlot.getPlotItem().getAxis('left').setTicks([[(0,'0'),(1,'1'),(1.5,'0'),(2.5,'1'),(3,'0'),(4,'1')]])
        grid.addWidget(hallPlot, 0, 0)
        hallPlot.showGrid(x = True, y = True, alpha = 0.2)
        hallPlot.addLegend(offset = 1, labelTextSize = legendFontSize)

        self.hallA = np.zeros(self.hallLen)
        self.hallCurveA = hallPlot.plot(self.hallPlotTimeVec,self.hallA[0:self.hallPlotLen], pen = pg.mkPen(color = '#EE6677', width = plotLineWidth), name = 'Hall A')
        
        self.hallB = np.zeros(self.hallLen)
        self.hallCurveB = hallPlot.plot(self.hallPlotTimeVec,self.hallB[0:self.hallPlotLen], pen = pg.mkPen(color = '#228833', width = plotLineWidth), name = 'Hall B')

        self.hallC = np.zeros(self.hallLen)
        self.hallCurveC = hallPlot.plot(self.hallPlotTimeVec,self.hallC[0:self.hallPlotLen], pen = pg.mkPen(color = '#4477AA', width = plotLineWidth), name = 'Hall C')

        encoderPlot = pg.PlotWidget()
        encoderPlot.setYRange(0, 5)
        encoderPlot.setLabel('left','State', **{'font-size': vertLabelFontSize})
        encoderPlot.setLabel('bottom','Time (ms)', **{'font-size': vertLabelFontSize})
        encoderPlot.getAxis('left').setStyle(tickFont = vertFont)
        encoderPlot.getAxis('bottom').setStyle(tickFont = horizFont)
        encoderPlot.getPlotItem().getAxis('left').setTicks([[(0,'0'),(1,'1'),(1.5,'0'),(2.5,'1'),(3,'0'),(4,'1')]])
        grid.addWidget(encoderPlot, 0, 1)
        encoderPlot.showGrid(x = True, y = True, alpha = 0.2)
        encoderPlot.addLegend(offset = 1, labelTextSize = legendFontSize)

        self.encoderA = np.zeros(self.encoderLen)
        self.encoderCurveA = encoderPlot.plot(self.encoderPlotTimeVec, self.encoderA[0:self.encoderPlotLen], pen = pg.mkPen(color = '#66CCEE', width = plotLineWidth), name = 'Encoder A')
        
        self.encoderB = np.zeros(self.encoderLen)
        self.encoderCurveB = encoderPlot.plot(self.encoderPlotTimeVec, self.encoderB[0:self.encoderPlotLen], pen = pg.mkPen(color = '#AA3377', width = plotLineWidth), name = 'Encoder B')

        self.encoderZ = np.zeros(self.encoderLen)
        self.encoderCurveZ = encoderPlot.plot(self.encoderPlotTimeVec, self.encoderZ[0:self.encoderPlotLen], pen = pg.mkPen(color = '#CCBB44', width = plotLineWidth), name = 'Encoder Z')

        self.rawTab.setLayout(grid)

        # ----- TAB HOME ----- #
        self.homeTab = QWidget()
        grid = QGridLayout()
        leftCol = QGridLayout()
        rightCol = QGridLayout()

        homedqPlot = pg.PlotWidget()
        homedqPlot.getViewBox().setAspectLocked(True, ratio=1)
        homedqPlot.setYRange(-15, 15)
        homedqPlot.setXRange(-15, 15)
        homedqPlot.setLabel('left','q-axis', **{'font-size': vertLabelFontSize})
        homedqPlot.setLabel('bottom','d-axis', **{'font-size': vertLabelFontSize})
        container = QWidget()
        hbox = QHBoxLayout(container)
        hbox.setContentsMargins(0,0,0,0)
        hbox.addStretch(1)
        hbox.addWidget(homedqPlot, 10)
        hbox.addStretch(1)
        leftCol.addWidget(container, 1, 0)

        yAxis = pg.PlotDataItem([0, 0], [-30, 30], pen = pg.mkPen(color = "#000000", width = 1))
        homedqPlot.addItem(yAxis)
        xAxis = pg.PlotDataItem([-30, 30], [0, 0], pen = pg.mkPen(color = "#000000", width = 1))
        homedqPlot.addItem(xAxis)
        homedqPlot.getAxis('left').setStyle(tickFont = vertFont)
        homedqPlot.getAxis('bottom').setStyle(tickFont = vertFont)

        self.bemfdqHomeVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#66CCEE", width = plotLineWidth))
        homedqPlot.addItem(self.bemfdqHomeVector)
        self.bemfdqHomeCurve = homedqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#66CCEE", width = plotLineWidth), symbolSize = 25, name = 'Back EMF')

        self.idqHomeVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#AA3377", width = plotLineWidth))
        homedqPlot.addItem(self.idqHomeVector)
        self.idqHomeCurve = homedqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#AA3377", width = plotLineWidth), symbolSize = 25)

        self.vdqHomeVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#228833", width = plotLineWidth))
        homedqPlot.addItem(self.vdqHomeVector)
        self.vdqHomeCurve = homedqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#228833", width = plotLineWidth), symbolSize = 25)

        self.CCdqHomeVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#CCBB44", width = plotLineWidth))
        homedqPlot.addItem(self.CCdqHomeVector)
        self.CCdqHomeCurve = homedqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#CCBB44", width = plotLineWidth), symbolSize = 25)

        self.RsidqHomeVector = pg.PlotDataItem([0, 0], [0, 0], pen = pg.mkPen(color = "#4477AA", width = plotLineWidth))
        homedqPlot.addItem(self.RsidqHomeVector)
        self.RsidqHomeCurve = homedqPlot.plot([0], [0], symbol = 'o', symbolBrush = pg.mkBrush(color = "#4477AA", width = plotLineWidth), symbolSize = 25)

        legend = pg.LegendItem()
        legend.setParentItem(homedqPlot.getPlotItem())
        fontSize = 30
        legend.addItem(self.vdqHomeCurve, f'<span style="font-size:{fontSize}pt;">v<sub>dq</sub> Measured</span>')
        legend.addItem(self.idqHomeCurve, f'<span style="font-size:{fontSize}pt;">v<sub>dq</sub> Estimated</span>')
        legend.addItem(self.RsidqHomeCurve, f'<span style="font-size:{fontSize}pt;">R<sub>s</sub> \U000000d7 i<sub>dq</sub></span>')
        legend.addItem(self.CCdqHomeCurve, f'<span style="font-size:{fontSize}pt;">Cross Coupling</span>')
        legend.addItem(self.bemfdqHomeCurve, f'<span style="font-size:{fontSize}pt;">Back EMF</span>')
        legend.anchor((0, 0), (0, 0))
        legend.setOffset((130, -100))

        homeEquationLabel = QLabel(
            '<span style="color:#AA3377; font-size:30pt; font-weight: bold;">dq Voltage </span>'
            '<span style="color:#000000; font-size:30pt;">&asymp;</span>'
            '<span style="color:#4477AA; font-size:30pt; font-weight: bold;"> Stator Reaction</span>'
            '<span style="color:#000000; font-size:30pt;"> +</span>'
            '<span style="color:#CCBB44; font-size:30pt; font-weight: bold;"> Cross Coupling</span>'
            '<span style="color:#000000; font-size:30pt;"> +</span>'
            '<span style="color:#66CCEE; font-size:30pt; font-weight: bold;"> Back EMF</span>'
        )

        homeEquationLabel.setContentsMargins(0,0,0,0)
        homeEquationLabel.setStyleSheet('padding-bottom: 5px; padding-left: 80px; padding-right: 0px;')
        leftCol.addWidget(homeEquationLabel, 0, 0, alignment=Qt.AlignCenter)

        homeVoltagePlot = pg.PlotWidget()
        homeVoltagePlot.setLabel('left','Voltage (V)', **{'font-size': vertLabelFontSize})
        homeVoltagePlot.showGrid(x = True, y = True, alpha = 0.2)
        homeVoltagePlot.setYRange(-23, 23)
        homeVoltagePlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.0f}") for i in [x * 10 for x in range(-2, 3)]]])
        homeVoltagePlot.addLegend(offset = (0,0), labelTextSize = legendFontSize, colCount = 3)
        homeVoltagePlot.getAxis('left').setStyle(tickFont = vertFont)
        homeVoltagePlot.getAxis('bottom').setStyle(tickFont = horizFont)

        self.uVoltsHomeCurve = homeVoltagePlot.plot(self.plotTimeVec,self.uVolts, pen = pg.mkPen(color = '#EE6677', width = plotLineWidth), name = 'UV')

        self.vVoltsHomeCurve = homeVoltagePlot.plot(self.plotTimeVec,self.vVolts, pen = pg.mkPen(color = '#228833', width = plotLineWidth), name = 'VW')

        self.wVoltsHomeCurve = homeVoltagePlot.plot(self.plotTimeVec,self.wVolts, pen = pg.mkPen(color = '#4477AA', width = plotLineWidth), name = 'WU')
        
        # UVW Motor Currents
        homeCurrentPlot = pg.PlotWidget()
        homeCurrentPlot.setLabel('left','Current (A)', **{'font-size': '27pt'})
        homeCurrentPlot.showGrid(x = True, y = True, alpha = 0.2)
        homeCurrentPlot.setYRange(-1.2, 1.2)
        homeCurrentPlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.1f}") for i in [x * 0.5 for x in range(-2, 3)]]])
        homeCurrentPlot.addLegend(offset = (0,0), labelTextSize = legendFontSize, colCount = 3)
        homeCurrentPlot.getAxis('left').setStyle(tickFont = vertFont)
        homeCurrentPlot.getAxis('bottom').setStyle(tickFont = horizFont)

        self.uAmpsHomeCurve = homeCurrentPlot.plot(self.plotTimeVec,self.uAmps, pen = pg.mkPen(color = "#66CCEE", width = plotLineWidth), name = 'UV')

        self.vAmpsHomeCurve = homeCurrentPlot.plot(self.plotTimeVec,self.vAmps, pen = pg.mkPen(color = "#AA3377", width = plotLineWidth), name = 'VW')

        self.wAmpsHomeCurve = homeCurrentPlot.plot(self.plotTimeVec,self.wAmps, pen = pg.mkPen(color = "#CCBB44", width = plotLineWidth), name = 'WU')

        # dq0 Voltages
        homeVdqPlot = pg.PlotWidget()
        homeVdqPlot.setLabel('left','Voltage (V)', **{'font-size': vertLabelFontSize})
        homeVdqPlot.showGrid(x = True, y = True, alpha = 0.2)
        homeVdqPlot.setYRange(-23, 23)
        homeVdqPlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.0f}") for i in [x * 10 for x in range(-2, 3)]]])
        homeVdqPlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 3)
        homeVdqPlot.getAxis('left').setStyle(tickFont = vertFont)
        homeVdqPlot.getAxis('bottom').setStyle(tickFont = horizFont)

        self.dVoltsHomeCurve = homeVdqPlot.plot(self.plotTimeVec,self.dVolts, pen = pg.mkPen(color = "#009988", width = plotLineWidth), name = 'd')

        self.qVoltsHomeCurve = homeVdqPlot.plot(self.plotTimeVec,self.qVolts, pen = pg.mkPen(color = "#E98043", width = plotLineWidth), name = 'q')

        self.zVoltsHomeCurve = homeVdqPlot.plot(self.plotTimeVec,self.zVolts, pen = pg.mkPen(color = '#696969', width = plotLineWidth), name = '0')

        # dq0 Currents
        homeIdqPlot = pg.PlotWidget()
        homeIdqPlot.setLabel('left','Current (A)', **{'font-size': '27pt'})
        homeIdqPlot.setLabel('bottom','Time (ms)', **{'font-size': vertLabelFontSize})
        homeIdqPlot.showGrid(x = True, y = True, alpha = 0.2)
        homeIdqPlot.setYRange(-1.2, 1.2)
        homeIdqPlot.getPlotItem().getAxis('left').setTicks([[(i, f"{i:.1f}") for i in [x * 0.5 for x in range(-2, 3)]]])
        homeIdqPlot.addLegend(offset = 0, labelTextSize = legendFontSize, colCount = 3)
        homeIdqPlot.getAxis('left').setStyle(tickFont = vertFont)
        homeIdqPlot.getAxis('bottom').setStyle(tickFont = horizFont)

        self.dAmpsHomeCurve = homeIdqPlot.plot(self.plotTimeVec,self.dAmps, pen = pg.mkPen(color = "#332288", width = plotLineWidth), name = 'd')

        self.qAmpsHomeCurve = homeIdqPlot.plot(self.plotTimeVec,self.qAmps, pen = pg.mkPen(color = "#CC6677", width = plotLineWidth), name = 'q')

        self.zAmpsHomeCurve = homeIdqPlot.plot(self.plotTimeVec,self.zAmps, pen = pg.mkPen(color = '#696969', width = plotLineWidth), name = '0')

        rightCol.addWidget(homeVoltagePlot, 0, 0)
        rightCol.addWidget(homeVdqPlot, 1, 0)
        rightCol.addWidget(homeCurrentPlot, 2, 0)
        rightCol.addWidget(homeIdqPlot, 3, 0)

        rightCol.setRowStretch(0,83)
        rightCol.setRowStretch(1,83)
        rightCol.setRowStretch(2,83)
        rightCol.setRowStretch(3,100)
        
        grid.addLayout(leftCol, 0, 0)
        grid.addLayout(rightCol, 0, 1)
        self.homeTab.setLayout(grid)

        # ----- Setting Tabs ----- #
        self.tabs.addTab(self.homeTab, "Home")
        self.tabs.addTab(self.timeDomainTab, "Analog Signals")
        self.tabs.addTab(self.vectorTab, "Space Vectors")
        self.tabs.addTab(self.rawTab, "Digital Signals")

        self.setCentralWidget(self.tabs)

        # ----- Making Bar at the Bottom ----- #
        
        logo_label = QLabel()
        logo_pixmap = QPixmap("eng-logo.png").scaled(400, 168, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)

        team_label = QLabel("Team 34")
        team_label.setStyleSheet("font-size: 36pt; font-weight: bold; padding-right: 10px")
        logo_label.setFrameStyle(0)
        logo_label.setContentsMargins(0,0,0,0)
        logo_label.setStyleSheet('padding-top: 10px; padding-bottom: 10px; padding-left: 10px; padding-right: 20px')
        team_label.setFrameStyle(0)

        logo_widget = QWidget()
        logo_widget.setObjectName("Test")
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.addWidget(logo_label)
        logo_layout.addWidget(team_label)
        logo_layout.setContentsMargins(0,0,0,0)
        logo_widget.setStyleSheet("""
            QWidget#Test{
            border: 2px solid #C8C8C8; 
            border-radius: 6px; 
            padding: 4px 8px; 
            background: #FFFFFF
            }
            """)

        statusContainer = QWidget()
        main_layout = QHBoxLayout()

        main_layout.setSpacing(0)
        main_layout.addStretch(1)
        main_layout.addWidget(logo_widget)

        main_layout.setSpacing(0)
        main_layout.addStretch(55)
        self.value_display = QLabel("Speed:     0 rpm")
        self.value_display.setFixedHeight(90)
        self.value_display.setStyleSheet("""
            font: 48px;
            border: 2px solid #C8C8C8; 
            border-radius: 6px; 
            padding: 4px 8px; 
            background: #FFFFFF
            """)
        monospaceFont = QFont('Courier New')
        monospaceFont.setStyleHint(QFont.Monospace)
        self.value_display.setFont(monospaceFont)
        main_layout.addWidget(self.value_display)

        main_layout.setSpacing(0)
        main_layout.addStretch(100)
        self.center_button = QPushButton('\U000023F8 Pause') # 
        self.center_button.setStyleSheet("""
            QPushButton {
            font-size: 36pt;
            padding-top: 8px;
            border: 2px solid #C8C8C8; 
            border-radius: 6px; 
            background: #DEDEDE; 
            }
                                         
            QPushButton:focus {
            outline: none; 
            }                             
            """)
        self.center_button.setFixedWidth(230)
        self.center_button.setFixedHeight(90)
        self.center_button.clicked.connect(self.PausePlay)
        main_layout.addWidget(self.center_button)

        main_layout.setSpacing(0)
        main_layout.addStretch(3)
        self.save_button = QPushButton('\U0001F4E4 Export')
        self.save_button.setStyleSheet("""
            QPushButton {
            font-size: 36pt;
            padding-top: 8px;
            border: 2px solid #C8C8C8; 
            border-radius: 6px; 
            background: #DEDEDE; 
            }
                                         
            QPushButton:focus {
            outline: none; 
            }                             
            """)
        self.save_button.setFixedWidth(230)
        self.save_button.setFixedHeight(90)
        self.save_button.clicked.connect(self.SaveData)
        main_layout.addWidget(self.save_button)
        main_layout.addStretch(1)

        statusContainer.setLayout(main_layout)

        self.statusBar().addPermanentWidget(statusContainer, 1)
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #EDECEB;
                border: 0;
            }
            QStatusBar::item {
                background-color: #EDECEB;
                border: 0;
            }                           
            QLabel {
                color: #000000;
                font-weight: bold;
            }
            """)
        
        self.spi0 = spidev.SpiDev()
        self.spi0.open(0, 0)
        self.spi0.max_speed_hz = 1000000
        self.spi0.mode = 0

        chip = gpiod.Chip("gpiochip4")
        self.hallLines = chip.get_lines([23, 24, 25, 17, 27, 22, 5])
        self.hallLines.request(consumer = 'my_gpio_reader', type = gpiod.LINE_REQ_DIR_IN)

        self.counter = 0
        self.f_est = 0

        self.pauseExec = 1
        self.toggleSave = 0

        self.timeVec = np.zeros(self.analogLen)
        self.timeVecExt = np.zeros(self.hallLen)

        self.seq = 1
        self.timer = pg.QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(0)

    def update(self):
        if(self.pauseExec == 1):
            if (self.counter >= (self.maxCount - self.encoderLen)):
                GPIOvals = self.hallLines.get_values()

                self.encoderA[:-1] = self.encoderA[1:]
                self.encoderA[-1] = GPIOvals[4] + 3

                self.encoderB[:-1] = self.encoderB[1:]
                self.encoderB[-1] = GPIOvals[3] + 1.5

                self.encoderZ[:-1] = self.encoderZ[1:]
                self.encoderZ[-1] = GPIOvals[5]

            elif(self.counter >= (self.maxCount - self.hallLen - self.encoderLen)):
                GPIOvals = self.hallLines.get_values()

                self.hallA[:-1] = self.hallA[1:]
                self.hallA[-1] = GPIOvals[2] + 3

                self.hallB[:-1] = self.hallB[1:]
                self.hallB[-1] = GPIOvals[1] + 1.5

                self.hallC[:-1] = self.hallC[1:]
                self.hallC[-1] = GPIOvals[0]

                self.timeVecExt[:-1] = self.timeVecExt[1:]
                self.timeVecExt[-1] = time.time()
    
            elif(self.counter >= (self.maxCount - self.hallLen - self.encoderLen - self.analogLen - self.plotBuffer)):              
                frame = self.spi0.xfer2([0x00] * 16)

                parity = (frame[4] & 0b01111000) >> 3
                if (parity == 0 or parity == 1 or parity == 3):
                    self.uVolts[:-1] = self.uVolts[1:]
                    self.uVolts[-1] = 31/5250*(((frame[4] & 0b00000111) << 9) | (frame[5] << 1) | (frame[6] >> 7))

                parity = (frame[6] & 0b01111000) >> 3
                if (parity == 2 or parity == 6):
                    self.vVolts[:-1] = self.vVolts[1:]
                    self.vVolts[-1] = 31/5250*(((frame[6] & 0b00000111) << 9) | (frame[7] << 1) | (frame[8] >> 7))
                
                parity = (frame[8] & 0b01111000) >> 3
                if (parity == 7 or parity == 5):
                    self.wVolts[:-1] = self.wVolts[1:]
                    self.wVolts[-1] = 31/5250*(((frame[8] & 0b00000111) << 9) | (frame[9] << 1) | (frame[10] >> 7))
                
                parity = (frame[10] & 0b01111000) >> 3
                if (parity == 4 or parity == 12 or parity == 13):
                    self.uAmps[:-1] = self.uAmps[1:]
                    self.uAmps[-1] = 20/9009*(((frame[10] & 0b00000111) << 9) | (frame[11] << 1) | (frame[12] >> 7)) - 5
                
                parity = (frame[12] & 0b01111000) >> 3
                if (parity == 15 or parity == 14):
                    self.vAmps[:-1] = self.vAmps[1:]
                    self.vAmps[-1] = 20/9009*(((frame[12] & 0b00000111) << 9) | (frame[13] << 1) | (frame[14] >> 7)) - 5
                
                parity = (frame[14] & 0b01111000) >> 3
                if (parity == 10 or parity == 11):
                    self.wAmps[:-1] = self.wAmps[1:]
                    self.wAmps[-1] = 20/9009*(((frame[14] & 0b00000111) << 9) | (frame[15] << 1) | (frame[0] >> 7)) - 5
                
                parity = (frame[0] & 0b01111000) >> 3
                if (parity == 9 or parity == 8):
                    self.refSpeed[:-1] = self.refSpeed[1:]
                    self.refSpeed[-1] = 1*(((frame[0] & 0b00000111) << 9) | (frame[1] << 1) | (frame[2] >> 7))
                
                self.timeVec[:-1] = self.timeVec[1:]
                self.timeVec[-1] = time.time()

            self.counter = self.counter + 1

            if(self.counter == self.maxCount):
                self.counter = 0

                stopFlag = 0
                for i in range(0,self.hallLen - 1):
                    stopFlag = (self.hallA[i] == 3) and (self.hallA[i+1] > 3)
                    if(stopFlag == 1):
                        break
                
                if(i >= (self.hallLen - 2)):
                    i = 0

                ii = i
                if(i > (self.hallLen - self.hallPlotLen - 1)):
                    i = (self.hallLen - self.hallPlotLen - 2)

                t1 = self.timeVecExt[ii]
                modHallA = self.hallA[i:(self.hallPlotLen + i)]
                modHallB = self.hallB[i:(self.hallPlotLen + i)]
                modHallC = self.hallC[i:(self.hallPlotLen + i)]

                stopFlag = 0
                for i in range(ii,self.hallLen - 1):
                    stopFlag = (self.hallA[i] > 3) and (self.hallA[i+1] == 3)
                    if(stopFlag == 1):
                        break
                
                if(i >= (self.hallLen - 2)):
                    i = 3

                t3 = self.timeVecExt[i]

                stopFlag = 0
                for j in range(ii,self.hallLen - 1):
                    stopFlag = (self.hallB[j] == 1.5) and (self.hallB[j+1] > 1.5)
                    if(stopFlag == 1):
                        break
                
                if(j >= (self.hallLen - 2)):
                    j = 1

                t2 = self.timeVecExt[j]
                speedEnc = 5.331/abs((t2-t1))*np.sign(t3-t2)*(1+1*(np.sign(t3-t2) < 0))
                if(abs(speedEnc) > 3700):
                    speedEnc = 0
                elif(abs(speedEnc) > 3510):
                    speedEnc = np.sign(speedEnc)*3510
        
                stopFlag = 0
                for i in range(0,self.encoderLen-1):
                    stopFlag = (self.encoderZ[i] == 0) and (self.encoderZ[i+1] > 0)
                    if(stopFlag == 1):
                        break
                
                if(i > (self.encoderLen - self.encoderPlotLen)):
                    i = 0

                modEncoderA = self.encoderA[i:(self.encoderPlotLen + i+1)]
                modEncoderB = self.encoderB[i:(self.encoderPlotLen + i+1)]
                modEncoderZ = self.encoderZ[i:(self.encoderPlotLen + i+1)]

                self.hallCurveA.setData(self.hallPlotTimeVec,modHallA)
                self.hallCurveB.setData(self.hallPlotTimeVec,modHallB)
                self.hallCurveC.setData(self.hallPlotTimeVec,modHallC)

                self.encoderCurveA.setData(self.encoderPlotTimeVec,modEncoderA)
                self.encoderCurveB.setData(self.encoderPlotTimeVec,modEncoderB)
                self.encoderCurveZ.setData(self.encoderPlotTimeVec,modEncoderZ)

                # ----- DSP OF ANALOG SIGNALS ----- #
                uvVolts = self.uVolts - self.vVolts

                f_s = 1/np.median(np.diff(self.timeVec))
                f_n = f_s/self.analogLen*np.arange(0,int(self.analogLen/2)-1)

                UV = np.fft.fft(uvVolts)
                G_n = np.abs(UV[0:(int(self.analogLen/2)-1)])/self.analogLen
                f_i = np.argmax(G_n)
                if(G_n[f_i] < 0.5):
                    self.f_est = 0

                    uvVoltsPlot = np.zeros(self.analogPlotLen)
                    vwVoltsPlot = np.zeros(self.analogPlotLen)
                    wuVoltsPlot = np.zeros(self.analogPlotLen)

                    uAmpsPlot = np.zeros(self.analogPlotLen)
                    vAmpsPlot = np.zeros(self.analogPlotLen)
                    wAmpsPlot = np.zeros(self.analogPlotLen)

                    dVolts = np.zeros(self.analogPlotLen)
                    qVolts = np.zeros(self.analogPlotLen)
                    zVolts = np.zeros(self.analogPlotLen)

                    dAmps = np.zeros(self.analogPlotLen)
                    qAmps = np.zeros(self.analogPlotLen)
                    zAmps = np.zeros(self.analogPlotLen)

                    dAmpsAvg = 0
                    qAmpsAvg = 0
                    zAmpsAvg = 0

                    dVoltsAvg = 0
                    qVoltsAvg = 0
                    zVoltsAvg = 0
                else:            
                    f_i2 = 2*np.argmax([G_n[f_i-1], G_n[f_i+1]]) - 1
                    self.f_est = (G_n[f_i]*f_n[f_i] + G_n[f_i+f_i2]*f_n[f_i+f_i2])/(G_n[f_i] + G_n[f_i+f_i2])

                    UV = np.fft.fft(self.vVolts - self.wVolts)
                    G_n = np.abs(UV[0:(int(self.analogLen/2)-1)])/self.analogLen
                    f_i = np.argmax(G_n)
                    f_i2 = 2*np.argmax([G_n[f_i-1], G_n[f_i+1]]) - 1
                    f_est2 = (G_n[f_i]*f_n[f_i] + G_n[f_i+f_i2]*f_n[f_i+f_i2])/(G_n[f_i] + G_n[f_i+f_i2])

                    UV = np.fft.fft(self.wVolts - self.uVolts)
                    G_n = np.abs(UV[0:(int(self.analogLen/2)-1)])/self.analogLen
                    f_i = np.argmax(G_n)
                    f_i2 = 2*np.argmax([G_n[f_i-1], G_n[f_i+1]]) - 1
                    f_est3 = (G_n[f_i]*f_n[f_i] + G_n[f_i+f_i2]*f_n[f_i+f_i2])/(G_n[f_i] + G_n[f_i+f_i2])

                    UV = np.fft.fft(self.uAmps)
                    G_n = np.abs(UV[0:(int(self.analogLen/2)-1)])/self.analogLen
                    f_i = np.argmax(G_n)
                    f_i2 = 2*np.argmax([G_n[f_i-1], G_n[f_i+1]]) - 1
                    f_est4 = (G_n[f_i]*f_n[f_i] + G_n[f_i+f_i2]*f_n[f_i+f_i2])/(G_n[f_i] + G_n[f_i+f_i2])

                    UV = np.fft.fft(self.vAmps)
                    G_n = np.abs(UV[0:(int(self.analogLen/2)-1)])/self.analogLen
                    f_i = np.argmax(G_n)
                    f_i2 = 2*np.argmax([G_n[f_i-1], G_n[f_i+1]]) - 1
                    f_est5 = (G_n[f_i]*f_n[f_i] + G_n[f_i+f_i2]*f_n[f_i+f_i2])/(G_n[f_i] + G_n[f_i+f_i2])

                    UV = np.fft.fft(self.wAmps)
                    G_n = np.abs(UV[0:(int(self.analogLen/2)-1)])/self.analogLen
                    f_i = np.argmax(G_n)
                    f_i2 = 2*np.argmax([G_n[f_i-1], G_n[f_i+1]]) - 1
                    self.f_est = np.median([self.f_est, f_est2, f_est3, f_est4, f_est5, (G_n[f_i]*f_n[f_i] + G_n[f_i+f_i2]*f_n[f_i+f_i2])/(G_n[f_i] + G_n[f_i+f_i2])])

                    w_n = min(2*1.5*self.f_est/f_s, 99/100)
                    butterb, buttera = butter(4, w_n, btype = 'low')
                    uvFilt = filtfilt(butterb, buttera, self.uVolts - self.vVolts)
                    vwFilt = filtfilt(butterb, buttera, self.vVolts - self.wVolts)
                    wuFilt = filtfilt(butterb, buttera, self.wVolts - self.uVolts)
                    uFilt = filtfilt(butterb, buttera, self.uAmps)
                    vFilt = filtfilt(butterb, buttera, self.vAmps)
                    wFilt = filtfilt(butterb, buttera, self.wAmps)

                    # ----- START OF DQ0 ----- #

                    timeMod = np.zeros(2*len(self.timeVec) - 1)
                    for i in range(0,len(self.timeVec)-1):
                        timeMod[2*i] = self.timeVec[i]
                        timeMod[2*i+1] = (self.timeVec[i] + self.timeVec[i+1])/2
                    timeMod[-1] = self.timeVec[-1]

                    uFiltMod = np.interp(timeMod, self.timeVec, uFilt)
                    uFiltMod = uFiltMod - np.median(uFiltMod)
                    vFiltMod = np.interp(timeMod, self.timeVec, vFilt)
                    vFiltMod = vFiltMod - np.median(vFiltMod)
                    wFiltMod = np.interp(timeMod, self.timeVec, wFilt)
                    wFiltMod = wFiltMod - np.median(wFiltMod)

                    uvFiltMod = np.interp(timeMod, self.timeVec, uvFilt)
                    vwFiltMod = np.interp(timeMod, self.timeVec, vwFilt)
                    wuFiltMod = np.interp(timeMod, self.timeVec, wuFilt)

                    stopFlag = 0
                    
                    for i in range(0,len(uFiltMod)-2):
                        stopFlag = (uFiltMod[i] >= 0) and (uFiltMod[i+1] <= 0)
                        if(stopFlag == 1):
                            break

                    if (stopFlag == 0):
                        i = 1

                    stopFlag = 0
                    
                    for i1 in range(i,len(uFiltMod)-2):
                        stopFlag = (vFiltMod[i1] >= 0) and (vFiltMod[i1+1] <= 0)
                        if (stopFlag == 1):
                            break

                    if (stopFlag == 0):
                        i1 = 1

                    stopFlag = 0

                    for i2 in range(i,len(uFiltMod)-2):
                        stopFlag = (wFiltMod[i2] >= 0) and (wFiltMod[i2+1] <= 0)
                        if(stopFlag == 1):
                            break

                    if (stopFlag == 0):
                        p1 = 1
                    else:
                        p1 = i2 # going negative
                    
                    stopFlag = 0
                    
                    for i2 in range(i,len(uFiltMod)-2):
                        stopFlag = (wFiltMod[i2] <= 0) and (wFiltMod[i2+1] >= 0)
                        if(stopFlag == 1):
                            break

                    if (stopFlag == 0):
                        p2 = 1
                    else:
                        p2 = i2 # going positive
                    
                    if (i1 < p1) and (i1 > p2):
                        self.seq = 1
                    elif (i1 > p1) and (i1 < p2):
                        self.seq = -1

                    stopFlag = 0

                    for j in range(0,len(wuFiltMod)-2): # old: -3.44 going up
                        stopFlag = (uvFiltMod[j] >= -0.15*max(uvFiltMod)) and (uvFiltMod[j+1] <= -0.15*max(uvFiltMod))
                        if(stopFlag == 1): # -0.272
                            break

                    if (stopFlag == 0):
                        j = 1

                    timeModLim = timeMod[0:min(self.analogPlotLen+1,2*self.analogPlotLen-1-i)]
                    timeModLim = np.concatenate((np.array([0]), np.cumsum(np.diff(timeModLim))))

                    timeModLim2 = timeMod[0:min(self.analogPlotLen+1,2*self.analogPlotLen-1-j)]
                    timeModLim2 = np.concatenate((np.array([0]), np.cumsum(np.diff(timeModLim2))))

                    uFiltModLim = uFiltMod[i:(i + self.analogPlotLen)]
                    vFiltModLim = vFiltMod[i:(i + self.analogPlotLen)]
                    wFiltModLim = wFiltMod[i:(i + self.analogPlotLen)]
                    
                    uvFiltModLim = uvFiltMod[j:(j + self.analogPlotLen)]
                    vwFiltModLim = vwFiltMod[j:(j + self.analogPlotLen)]
                    wuFiltModLim = wuFiltMod[j:(j + self.analogPlotLen)]

                    dAmps = np.zeros(len(uFiltModLim)-1)
                    qAmps = np.zeros(len(uFiltModLim)-1)
                    zAmps = uFiltModLim + vFiltModLim + wFiltModLim
                    dVolts = np.zeros(len(uvFiltModLim)-1)
                    qVolts = np.zeros(len(uvFiltModLim)-1)
                    zVolts = uvFiltModLim + vwFiltModLim + wuFiltModLim

                    maxi = min(len(uFiltModLim), len(vFiltModLim), len(wFiltModLim), len(timeModLim))
                    fdq = self.seq*self.f_est
                    for i in range(0,maxi-1):
                        dAmps[i] = 2/3*(np.cos(2*np.pi*fdq*timeModLim[i])*uFiltModLim[i] + \
                            np.cos(2*np.pi*(fdq*timeModLim[i] - 1/3))*vFiltModLim[i] + \
                            np.cos(2*np.pi*(fdq*timeModLim[i] + 1/3))*wFiltModLim[i])
                        qAmps[i] = -2/3*(np.sin(2*np.pi*fdq*timeModLim[i])*uFiltModLim[i] + \
                            np.sin(2*np.pi*(fdq*timeModLim[i] - 1/3))*vFiltModLim[i] + \
                            np.sin(2*np.pi*(fdq*timeModLim[i] + 1/3))*wFiltModLim[i])
                    
                    maxi = min(len(uvFiltModLim), len(vwFiltModLim), len(wuFiltModLim), len(timeModLim2))
                    for i in range(0,maxi-1):
                        dVolts[i] = 2/3*(np.cos(2*np.pi*fdq*timeModLim2[i])*uvFiltModLim[i] + \
                            np.cos(2*np.pi*(fdq*timeModLim2[i] - 1/3))*vwFiltModLim[i] + \
                            np.cos(2*np.pi*(fdq*timeModLim2[i] + 1/3))*wuFiltModLim[i])
                        qVolts[i] = -2/3*(np.sin(2*np.pi*fdq*timeModLim2[i])*uvFiltModLim[i] + \
                            np.sin(2*np.pi*(fdq*timeModLim2[i] - 1/3))*vwFiltModLim[i] + \
                            np.sin(2*np.pi*(fdq*timeModLim2[i] + 1/3))*wuFiltModLim[i])
                    
                    dAmpsAvg = np.mean(dAmps)/np.sqrt(3)
                    qAmpsAvg = np.mean(qAmps)/np.sqrt(3)
                    zAmpsAvg = np.mean(zAmps)/np.sqrt(3)

                    dVoltsAvg = np.mean(dVolts)
                    qVoltsAvg = np.mean(qVolts)
                    zVoltsAvg = np.mean(zVolts)

                    uvVoltsPlot = uvFiltModLim
                    vwVoltsPlot = vwFiltModLim
                    wuVoltsPlot = wuFiltModLim

                    uAmpsPlot = uFiltModLim/np.sqrt(3)
                    vAmpsPlot = vFiltModLim/np.sqrt(3)
                    wAmpsPlot = wFiltModLim/np.sqrt(3)

                upperBound = min(self.analogPlotLen, len(dVolts), len(qVolts), len(zVolts), len(dAmps), len(qAmps), len(zAmps))
                self.uVoltsCurve.setData(self.plotTimeVec[0:upperBound],uvVoltsPlot[0:upperBound])
                self.vVoltsCurve.setData(self.plotTimeVec[0:upperBound],vwVoltsPlot[0:upperBound])
                self.wVoltsCurve.setData(self.plotTimeVec[0:upperBound],wuVoltsPlot[0:upperBound])

                self.uAmpsCurve.setData(self.plotTimeVec[0:upperBound],uAmpsPlot[0:upperBound])
                self.vAmpsCurve.setData(self.plotTimeVec[0:upperBound],vAmpsPlot[0:upperBound])
                self.wAmpsCurve.setData(self.plotTimeVec[0:upperBound],wAmpsPlot[0:upperBound])

                self.uVoltsHomeCurve.setData(self.plotTimeVec[0:upperBound],uvVoltsPlot[0:upperBound])
                self.vVoltsHomeCurve.setData(self.plotTimeVec[0:upperBound],vwVoltsPlot[0:upperBound])
                self.wVoltsHomeCurve.setData(self.plotTimeVec[0:upperBound],wuVoltsPlot[0:upperBound])

                self.uAmpsHomeCurve.setData(self.plotTimeVec[0:upperBound],uAmpsPlot[0:upperBound])
                self.vAmpsHomeCurve.setData(self.plotTimeVec[0:upperBound],vAmpsPlot[0:upperBound])
                self.wAmpsHomeCurve.setData(self.plotTimeVec[0:upperBound],wAmpsPlot[0:upperBound])

                self.dVoltsCurve.setData(self.plotTimeVec[0:upperBound], dVolts[0:upperBound])
                self.qVoltsCurve.setData(self.plotTimeVec[0:upperBound], qVolts[0:upperBound])
                self.zVoltsCurve.setData(self.plotTimeVec[0:upperBound], zVolts[0:upperBound])

                self.dAmpsCurve.setData(self.plotTimeVec[0:upperBound],dAmps[0:upperBound]/np.sqrt(3))
                self.qAmpsCurve.setData(self.plotTimeVec[0:upperBound],qAmps[0:upperBound]/np.sqrt(3))
                self.zAmpsCurve.setData(self.plotTimeVec[0:upperBound],zAmps[0:upperBound]/np.sqrt(3))

                self.dVoltsHomeCurve.setData(self.plotTimeVec[0:upperBound], dVolts[0:upperBound])
                self.qVoltsHomeCurve.setData(self.plotTimeVec[0:upperBound], qVolts[0:upperBound])
                self.zVoltsHomeCurve.setData(self.plotTimeVec[0:upperBound], zVolts[0:upperBound])

                self.dAmpsHomeCurve.setData(self.plotTimeVec[0:upperBound],dAmps[0:upperBound]/np.sqrt(3))
                self.qAmpsHomeCurve.setData(self.plotTimeVec[0:upperBound],qAmps[0:upperBound]/np.sqrt(3))
                self.zAmpsHomeCurve.setData(self.plotTimeVec[0:upperBound],zAmps[0:upperBound]/np.sqrt(3))

                Rs = 0.72
                Ld = 0.0012
                Lq = Ld
                #p = 4
                we = self.seq*self.f_est*2*np.pi
                fluxLinkage = 0.01

                self.vdqCurve.setData([dVoltsAvg], [qVoltsAvg])
                self.vdqVector.setData([0, dVoltsAvg], [0, qVoltsAvg])

                self.RsidqCurve.setData([Rs*dAmpsAvg], [Rs*qAmpsAvg])
                self.RsidqVector.setData([0, Rs*dAmpsAvg], [0, Rs*qAmpsAvg])

                self.CCdqCurve.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg])
                self.CCdqVector.setData([Rs*dAmpsAvg, -we*Lq*qAmpsAvg + Rs*dAmpsAvg], [Rs*qAmpsAvg, we*Ld*dAmpsAvg + Rs*qAmpsAvg])

                self.bemfdqCurve.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])
                self.bemfdqVector.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg, -we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg, we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])

                self.idqCurve.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])
                self.idqVector.setData([0, -we*Lq*qAmpsAvg + Rs*dAmpsAvg], [0, we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])

                # ----- HOME TAB ----- #
                self.vdqHomeCurve.setData([dVoltsAvg], [qVoltsAvg])
                self.vdqHomeVector.setData([0, dVoltsAvg], [0, qVoltsAvg])

                self.RsidqHomeCurve.setData([Rs*dAmpsAvg], [Rs*qAmpsAvg])
                self.RsidqHomeVector.setData([0, Rs*dAmpsAvg], [0, Rs*qAmpsAvg])

                self.CCdqHomeCurve.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg])
                self.CCdqHomeVector.setData([Rs*dAmpsAvg, -we*Lq*qAmpsAvg + Rs*dAmpsAvg], [Rs*qAmpsAvg, we*Ld*dAmpsAvg + Rs*qAmpsAvg])

                self.bemfdqHomeCurve.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])
                self.bemfdqHomeVector.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg, -we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg, we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])

                self.idqHomeCurve.setData([-we*Lq*qAmpsAvg + Rs*dAmpsAvg], [we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])
                self.idqHomeVector.setData([0, -we*Lq*qAmpsAvg + Rs*dAmpsAvg], [0, we*Ld*dAmpsAvg + Rs*qAmpsAvg + we*fluxLinkage])

                self.speed[:-1] = self.speed[1:]
                if(self.f_est*15.77 >= 500):
                    self.speed[-1] = min(3500+ np.random.randint(-5,11), self.seq*self.f_est*15.77)
                else:
                    self.speed[-1] = speedEnc
                
                speedLabelStr = f"Speed: {self.speed[-1]:.0f} rpm"
                self.speedCurve.setData(self.speed)
                self.value_display.setText(f'{speedLabelStr[0:6]} {speedLabelStr[7:len(speedLabelStr)].rjust(9)}')

                self.refSpeedVec[:-1] = self.refSpeedVec[1:]
                GPIOvals = self.hallLines.get_values()
                refSpeedAvg = np.median(self.refSpeed)
                if(GPIOvals[6] == 1):
                    tSpeed = ((175/106)*(refSpeedAvg - 165)+100)*(refSpeedAvg > 165)
                    if(tSpeed > 3500):
                        self.refSpeedVec[-1] = 3500 + np.random.randint(-5,11)
                    else:
                        self.refSpeedVec[-1] = tSpeed
                else:
                    tSpeed = (500/217)*(refSpeedAvg < 1033)*(refSpeedAvg - 1033) + \
                        (200/119)*(refSpeedAvg > 1200)*(refSpeedAvg - 1090)
                    if(tSpeed > 2000):
                        self.refSpeedVec[-1] = 2000 + np.random.randint(-5,11)
                    elif(tSpeed < -2000):
                        self.refSpeedVec[-1] = -2000 - np.random.randint(-5,11)
                    else:
                        self.refSpeedVec[-1] = tSpeed
                
                self.refSpeedCurve.setData(self.refSpeedVec[1:(len(self.refSpeedVec))])

                if(np.any(self.speed < 0) and (not(self.speed[-1] >= 2100))):
                    self.speedPlot.setYRange(-2010, 2010)
                else:
                    self.speedPlot.setYRange(0, 3535)

                self.uLineVoltsCurve.setData(self.plotTimeVec[0:upperBound],self.uVolts[0:upperBound])
                self.vLineVoltsCurve.setData(self.plotTimeVec[0:upperBound],self.vVolts[0:upperBound])
                self.wLineVoltsCurve.setData(self.plotTimeVec[0:upperBound],self.wVolts[0:upperBound])

                self.dVoltsVec[:-1] = self.dVoltsVec[1:]
                self.dVoltsVec[-1] = dVoltsAvg
                self.dVoltsTimeCurve.setData(self.dVoltsVec[0:self.speedLen])

                self.qVoltsVec[:-1] = self.qVoltsVec[1:]
                self.qVoltsVec[-1] =  qVoltsAvg
                self.qVoltsTimeCurve.setData(self.qVoltsVec[0:self.speedLen])

                self.zVoltsVec[:-1] = self.zVoltsVec[1:]
                self.zVoltsVec[-1] =  zVoltsAvg
                self.zVoltsTimeCurve.setData(self.zVoltsVec[0:self.speedLen])

                self.dAmpsVec[:-1] = self.dAmpsVec[1:]
                self.dAmpsVec[-1] = dAmpsAvg
                self.dAmpsTimeCurve.setData(self.dAmpsVec[0:self.speedLen])

                self.qAmpsVec[:-1] = self.qAmpsVec[1:]
                self.qAmpsVec[-1] = qAmpsAvg
                self.qAmpsTimeCurve.setData(self.qAmpsVec[0:self.speedLen])

                self.zAmpsVec[:-1] = self.zAmpsVec[1:]
                self.zAmpsVec[-1] =  zAmpsAvg
                self.zAmpsTimeCurve.setData(self.zAmpsVec[0:self.speedLen])

    def on_tab_changed(self, index):
        if index == 0:
            self.tabIndex = 0
        elif index == 1:
            self.tabIndex = 1
        elif index == 2:
            self.tabIndex = 2
        elif index == 3:
            self.tabIndex = 3
            self.counter = 0
    
    def GetDataSPI(self, spi0):
        resp = spi0.xfer2([0xFF, 0xFF])
        parity = (resp[1] & 0b01111000) >> 3

        resp = (resp[0] << 8) | (resp[1] & 0b10000111)

        return parity, (((resp << 9) & 0xFFFF) | ((resp >> 7) & 0xFFFF))
    
    def PausePlay(self):
        self.pauseExec = not self.pauseExec

        if(self.pauseExec == 1):
            self.center_button.setText('\U000023F8 Pause')
        else:
            self.center_button.setText('\U000023F5 Play')
    
    def SaveData(self):
        self.toggleSave = 1

        if (self.toggleSave == 1):
            self.toggleSave = 0
            with open('DataOut.csv', 'w') as f:
                np.savetxt(f, self.f_est[None], delimiter = ',')
                np.savetxt(f, self.uVoltsCurve.getData()[0][None], delimiter = ',')
                np.savetxt(f, self.uVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.vVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.wVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.dVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.qVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.zVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.uLineVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.vLineVoltsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.wLineVoltsCurve.getData()[1][None], delimiter = ',')

                np.savetxt(f, self.uAmpsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.vAmpsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.wAmpsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.dAmpsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.qAmpsCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.zAmpsCurve.getData()[1][None], delimiter = ',')

                np.savetxt(f, self.speedCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.refSpeedCurve.getData()[1][None], delimiter = ',')

                np.savetxt(f, self.dVoltsTimeCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.qVoltsTimeCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.zVoltsTimeCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.dAmpsTimeCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.qAmpsTimeCurve.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.zAmpsTimeCurve.getData()[1][None], delimiter = ',')

                np.savetxt(f, self.hallCurveA.getData()[0][None], delimiter = ',')
                np.savetxt(f, self.hallCurveA.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.hallCurveB.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.hallCurveC.getData()[1][None], delimiter = ',')

                np.savetxt(f, self.encoderCurveA.getData()[0][None], delimiter = ',')
                np.savetxt(f, self.encoderCurveA.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.encoderCurveB.getData()[1][None], delimiter = ',')
                np.savetxt(f, self.encoderCurveZ.getData()[1][None], delimiter = ',')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    runApp = app.exec_()
    sys.exit(runApp)
