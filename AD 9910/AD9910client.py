from PyQt4 import QtGui
from PyQt4.QtCore import QTimer, pyqtSignal, pyqtSlot, Qt, QEvent, QSettings, QVariant
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from connection import connection

import sys
from LEDindicator import LEDindicator

debug = True

class myLineEdit(QtGui.QLineEdit):
    onspecialkeypress = pyqtSignal(int)

    def keyPressEvent(self,keyevent):
        if keyevent.key() in [Qt.Key_Enter,Qt.Key_Return,Qt.Key_Up,Qt.Key_Down]:
            self.onspecialkeypress.emit(keyevent.key())
        else:
            super(myLineEdit,self).keyPressEvent(keyevent)


class AD9910client(QtGui.QWidget):
    def __init__(self,reactor,cnx=None):
        super(AD9910client, self).__init__()
        self.tracking = False
        self.reactor = reactor
        self.cnx = cnx
        self.connect()
        self.initializeGUI()
        self.restore_GUI()


    def start_loops(self):
        loop1 = LoopingCall(self.update_console)
        loop1.start(10)
      
    @inlineCallbacks
    def connect(self):
        if self.cnx is  None:
            self.cnx = connection()
            yield self.cnx.connect()
        self.context = yield self.cnx.context()
        yield self.setupListeners()
        self.start_loops()

    def initializeGUI(self):
        frequencypanel = self.make_frequencypanel()
        console = self.make_consolepanel()
        console.setHidden(True)
        self.consolebutton.pressed.connect(lambda: console.setHidden(not console.isHidden()))
        layout = QtGui.QVBoxLayout()
        layout.addWidget(frequencypanel)
        layout.addWidget(console)
        self.setLayout(layout)
        self.show()

    def make_frequencypanel(self):
        widget = QtGui.QWidget()
        self.frequency = QtGui.QDoubleSpinBox()
        frequencylabel = QtGui.QLabel('Frequency')
        tracking = QtGui.QCheckBox('Tracking Parameter number: ')
        self.trackingnum = QtGui.QSpinBox()
        trackinglabel = QtGui.QLabel('From ParameterVault (0. indexed)')
        self.PLLled = LEDindicator('PLL',offcolor='Red')
        self.consolebutton = QtGui.QPushButton('Console')
        self.trackingnum.setObjectName('Trackingnum')
        self.frequency.setObjectName('Frequency')
        
        self.frequency.setRange(0,1000)
        self.frequency.setSingleStep(1e-6)
        self.frequency.setSuffix(' MHz')
        self.frequency.setDecimals(6)

        self.frequency.editingFinished.connect(lambda :self.set_frequency(self.frequency.value()))

        tracking.stateChanged.connect(self.tracking_checked)
        

        trackinglayout = QtGui.QHBoxLayout()
        trackinglayout.addWidget(tracking)
        trackinglayout.addWidget(self.trackingnum)
        trackinglayout.addWidget(trackinglabel)
        trackinglayout.setSpacing(1)
        trackinglayout.addStretch()

        freqlayout = QtGui.QHBoxLayout()
        freqlayout.addWidget(frequencylabel)
        freqlayout.addWidget(self.frequency)
        freqlayout.addWidget(self.PLLled)
        freqlayout.addWidget(self.consolebutton)
        freqlayout.addStretch()

        layout = QtGui.QVBoxLayout()
        layout.addLayout(freqlayout)
        layout.addLayout(trackinglayout)
        widget.setLayout(layout)
        return widget

    def make_consolepanel(self):
        widget = QtGui.QWidget()
        Instructionlabel = QtGui.QLabel('[W]rite, [R]ead, IO[U]pdate, IOre[S]et, [M]asterreset, e[C]ho')
        self.commandlinehistory = []
        self.commandlinehistoryindex = 0
        self.commandline = myLineEdit()
        self.console = QtGui.QTextEdit()

        self.commandline.onspecialkeypress.connect(self.commandline_keypress)

        self.console.setReadOnly(True)
        
        layout = QtGui.QVBoxLayout()
        layout.addWidget(Instructionlabel)
        layout.addWidget(self.console)
        layout.addWidget(self.commandline)
        widget.setLayout(layout)
        return widget

    def commandline_keypress(self,key):
        if key == Qt.Key_Enter or key == Qt.Key_Return:
            text = self.commandline.text()
            self.commandline.setText("")
            self.commandlinehistory.append(text)
            self.commandlinehistoryindex = len(self.commandlinehistory)-1
            self.write_serial(text)
        elif key == Qt.Key_Up:
            if self.commandlinehistoryindex < 0:
                self.commanlinehistoryindex -= 1
            text = self.commandlinehistory[self.commandlinehistoryindex]
            self.commandline.setText(text)
        elif key == Qt.Key_Down:
            if self.commandlinehistoryindex < (len(self.commandlinehistory)-1):
                self.commanlinehistoryindex += 1
            text = self.commandlinehistory[self.commandlinehistoryindex]
            self.commandline.setText(text)

    @inlineCallbacks
    def write_serial(self,text):
        server = yield self.cnx.get_server('AD9910server')
        yield server.write(str(text)+'\r')
        self.console.append(text)

    @inlineCallbacks
    def update_console(self):
        server = yield self.cnx.get_server('AD9910server')
        data = yield server.read_serial()
        if len(data) > 0:
            self.console.append(data)
        self.update_pll()

    @inlineCallbacks
    def set_frequency(self,freq):
        server = yield self.cnx.get_server('AD9910server')
        yield server.set_frequency(freq)

    @inlineCallbacks
    def update_pll(self):
        server = yield self.cnx.get_server('AD9910server')
        b = yield server.read_pll()
        self.PLLled.setState(b)
        
    def restore_GUI(self):
        settings = QSettings('ad9910clientsettings.ini',QSettings.IniFormat)
        settings.setFallbacksEnabled(False)

        for aspinbox in self.findChildren(QtGui.QDoubleSpinBox) + self.findChildren(QtGui.QSpinBox):
            name = aspinbox.objectName()
            if settings.contains(name):
                value= settings.value(name).toDouble()[0]
                aspinbox.setValue(value)
        
        if settings.contains('windowposition'):
            self.move(settings.value("windowposition").toPoint());
        if settings.contains('windowsize'):
            self.resize(settings.value("windowsize").toSize());

    def closeEvent(self,e):
        settings = QSettings('ad9910clientsettings.ini',QSettings.IniFormat)
        for aspinbox in self.findChildren(QtGui.QDoubleSpinBox) + self.findChildren(QtGui.QSpinBox):
            name = aspinbox.objectName()
            value= aspinbox.value()
            settings.setValue(name,value)
        
        settings.setValue('windowposition',self.pos())
        settings.setValue('windowsize',self.size())
        
        for asplitter in self.findChildren(QtGui.QSplitter):
            name = asplitter.objectName()
            value = asplitter.sizes()
            settings.setValue(name,value)
        settings.sync()

        self.reactor.stop()

    def tracking_checked(self,state):
        if state == 2: #being checked
            self.tracking = True
            self.frequency.setReadOnly(True)
            self.frequency.setStyleSheet("background-color:lightgrey")
            self.trackingnum.setReadOnly(True)
            self.trackingnum.setStyleSheet("background-color:lightgrey")
        else:
            self.tracking = False
            self.frequency.setReadOnly(False)
            self.trackingnum.setReadOnly(False)
            self.frequency.setStyleSheet("background-color:white")
            self.trackingnum.setStyleSheet("background-color:white")

    @inlineCallbacks
    def follow_parameterserver(self,x,data):
        if self.tracking:
            server = yield self.cnx.get_server('ParameterVault')
            value = yield server.get_parameter('Raman','announce')
            freq = float(value[self.trackingnum.value()]) 
            self.frequency.setValue(freq)
            self.set_frequency(freq)
        


    @inlineCallbacks
    def setupListeners(self):
        server = yield self.cnx.get_server('ParameterVault')
        yield server.addListener(listener = self.follow_parameterserver, source = server.ID, ID = 112345, context = self.context)
        yield server.signal__parameter_change(112345, context = self.context)
      

if __name__=="__main__":
    a = QtGui.QApplication( [] )
    import qt4reactor
    qt4reactor.install()
    from twisted.internet import reactor
    Widget = AD9910client(reactor)
    Widget.show()
    reactor.run()



