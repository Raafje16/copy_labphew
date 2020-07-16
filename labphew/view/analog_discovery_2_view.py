"""
labphew.view.monitor_view.py
==============
The MonitorWindow class displays a plot or other data that updates over time at a given rate. (TODO: or view images)
All the processes that are not relating to user interaction are handled by the Operator class in the model folder

To change parameters the user needs to open the configuration window.
To execute a special routine, one should run an instance of scan_view.
For inspiration: the initiation of scan_view routines can be implemented as buttons on the monitor_view
TODO:
    - build the UI without a design file necessary
    - connect the UI parameters to config file

"""

import os
import numpy as np
import pyqtgraph as pg   # used for additional plotting features

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import * # QMainWindow, QWidget, QPushButton, QVBoxLayout, QApplication, QSlider, QLabel, QMessageBox
from PyQt5.QtGui import QFont, QIcon
from labphew.core.tools.gui_tools import set_spinbox_stepsize

from labphew.core.base.general_worker import WorkThread

import logging

# TODO: the following imports are necessary for child windows, they have to be adjusted and tested
#from .config_view import ConfigWindow  # to adjust experiment parameters
#from .scan_view import ScanWindow      # to perform single scan


class MonitorWindow(QMainWindow):
    def __init__(self, operator, parent=None):
        self.logger = logging.getLogger(__name__)
        super().__init__(parent)
        self.setWindowTitle('Analog Discovery 2')
        self.operator = operator

        # # For loading a .ui file (created with QtDesigner):
        # p = os.path.dirname(__file__)
        # uic.loadUi(os.path.join(p, 'design/UI/main_window.ui'), self)

        self.set_UI()

        # create thread and timer objects for monitor
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.update_monitor)
        self.monitor_thread = WorkThread(self.operator._monitor_loop)

        # TODO: uncomment for testing the child windows
        # self.config_window = ConfigWindow(operator, parent=self)
        # self.config_window.propertiesChanged.connect(self.update_properties)
        # self.actionConfig.triggered.connect(self.config_window.show)
        #
        # self.scan_window = ScanWindow(operator)
        # self.actionScan.triggered.connect(self.scan_window.show)

    def set_UI(self):
        """
        Code-based generation of the user-interface based on PyQT
        """

        ### General layout
        central_widget = QWidget()
        central_layout = QHBoxLayout(central_widget)

        # Layout for left hand controls
        control_layout = QVBoxLayout()

        ### Analog Out
        box_ao = QGroupBox('Analog Out')
        layout_ao = QFormLayout()
        box_ao.setLayout(layout_ao)
        control_layout.addWidget(box_ao)

        self.ao1_spinbox = QDoubleSpinBox()
        self.ao1_spinbox.setSuffix('V')
        self.ao1_spinbox.setMinimum(-100)  # limits are checked by the Operator
        self.ao1_spinbox.valueChanged.connect(self.ao1_value)
        self.ao1_spinbox.setDecimals(3)
        self.ao1_spinbox.setSingleStep(0.001)

        self.ao2_spinbox = QDoubleSpinBox()
        self.ao2_spinbox.setSuffix('V')
        self.ao2_spinbox.setMinimum(-100)  # limits are checked by the Operator
        self.ao2_spinbox.valueChanged.connect(self.ao2_value)
        self.ao2_spinbox.setDecimals(3)
        self.ao2_spinbox.setSingleStep(0.001)

        self.ao1_label = QLabel()
        self.ao2_label = QLabel()
        layout_ao.addRow(self.ao1_label, self.ao1_spinbox)
        layout_ao.addRow(self.ao2_label, self.ao2_spinbox)

        ### Monitor
        box_monitor = QGroupBox('Monitor')
        layout_monitor = QVBoxLayout()
        box_monitor.setLayout(layout_monitor)
        control_layout.addWidget(box_monitor)

        layout_monitor_form  = QFormLayout()
        layout_monitor.addLayout(layout_monitor_form)
        layout_monitor_buttons = QHBoxLayout()
        layout_monitor.addLayout(layout_monitor_buttons)


        self.time_step_spinbox = QDoubleSpinBox()
        self.time_step_spinbox.setSuffix('s')
        self.time_step_spinbox.setMinimum(.01)
        self.time_step_spinbox.valueChanged.connect(self.time_step)
        self.time_step_spinbox.setSingleStep(0.01)
        layout_monitor_form.addRow(QLabel('Time step'), self.time_step_spinbox)

        self.plot_points_spinbox = QSpinBox()
        self.plot_points_spinbox.setMinimum(2)
        self.plot_points_spinbox.setMaximum(1000)
        self.plot_points_spinbox.valueChanged.connect(self.plot_points)
        self.plot_points_spinbox.setSingleStep(10)
        layout_monitor_form.addRow(QLabel('Plot points'), self.plot_points_spinbox)

        self.start_button = QPushButton('Start')
        self.start_button.clicked.connect(self.start_monitor)
        self.stop_button = QPushButton('Stop')
        self.stop_button.clicked.connect(self.stop_monitor)

        layout_monitor_buttons.addWidget(self.start_button)
        layout_monitor_buttons.addWidget(self.stop_button)

        ### Graphs:
        self.graph_win = pg.GraphicsWindow()
        self.graph_win.resize(1000, 600)

        self.plot1 = self.graph_win.addPlot()
        self.plot1.setLabel('bottom', 'time', units='s')
        self.plot1.setLabel('left', 'voltage', units='V')
        self.curve1 = self.plot1.plot(pen='y')
        self.graph_win.nextRow()
        self.plot2 = self.graph_win.addPlot()
        self.plot2.setLabel('bottom', 'time', units='s')
        self.plot2.setLabel('left', 'voltage', units='V')
        self.curve2 = self.plot2.plot(pen='c')
        # self.plot2.hide()

        # Add an empty widget at the bottom of the control layout to make layout nicer
        dummy = QWidget()
        dummy.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        control_layout.addWidget(dummy)
        # Add control layout and graph window to central layout and apply central layout to window
        central_layout.addLayout(control_layout)
        central_layout.addWidget(self.graph_win)
        self.setCentralWidget(central_widget)

        self.apply_properties(self.operator.properties)

    def apply_properties(self, props):
        """
        Apply properties dictionary to gui elements
        :param props: properties
        :type props: dict
        """
        self.ao1_label.setText(props['ao'][1]['name'])
        self.ao2_label.setText(props['ao'][2]['name'])

        self.time_step_spinbox.setValue(props['monitor']['time_step'])
        self.plot_points_spinbox.setValue(props['monitor']['plot_points'])

        self.plot1.setTitle(props['monitor'][1]['name'])
        self.plot2.setTitle(props['monitor'][2]['name'])


    def ao1_value(self):
        """
        Called when AO Channel 2 spinbox is modified.
        Updates the parameter using a method of operator (which checks validity) and forces the (corrected) parameter in the gui element
        """
        value = self.operator.analog_out(1, self.ao1_spinbox.value())
        self.ao1_spinbox.setValue(value)
        set_spinbox_stepsize(self.ao1_spinbox)

    def ao2_value(self):
        """
        Called when AO Channel 2 spinbox is modified.
        Updates the parameter using a method of operator (which checks validity) and forces the (corrected) parameter in the gui element
        """
        value = self.operator.analog_out(2, self.ao2_spinbox.value())
        self.ao2_spinbox.setValue(value)
        set_spinbox_stepsize(self.ao2_spinbox)

    def time_step(self):
        """
        Called when time step spinbox is modified.
        Updates the parameter using a method of operator (which checks validity) and forces the (corrected) parameter in the gui element
        """
        self.operator._set_monitor_time_step(self.time_step_spinbox.value())
        self.time_step_spinbox.setValue(self.operator.properties['monitor']['time_step'])
        set_spinbox_stepsize(self.time_step_spinbox)

    def plot_points(self):
        """
        Called when plot points spinbox is modified.
        Updates the parameter using a method of operator (which checks validity) and forces the (corrected) parameter in the gui element
        """
        self.operator._set_monitor_plot_points(self.plot_points_spinbox.value())
        self.plot_points_spinbox.setValue(self.operator.properties['monitor']['plot_points'])
        set_spinbox_stepsize(self.plot_points_spinbox)

    def start_monitor(self):
        """
        Called when start button is pressed.
        Starts the monitor (thread and timer) and disables some gui elements
        """
        if self.operator._busy:
            self.logger.debug("Operator is busy")
            return
        else:
            self.logger.debug('Starting monitor')
            self.operator._allow_monitor = True  # enable operator monitor loop to run
            self.monitor_thread.start()  # start the operator monitor
            self.monitor_timer.start(self.operator.properties['monitor']['gui_refresh_time'])  # start the update timer
            self.plot_points_spinbox.setEnabled(False)
            self.start_button.setEnabled(False)

    def stop_monitor(self):
        """
        Called when stop button is pressed.
        Stops the monitor:
        - flags the operator to stop
        - uses the Workthread stop method to wait a bit for the operator to finish, or terminate thread if timeout occurs
        """
        if not self.monitor_thread.isRunning():
            self.logger.debug('Monitor is not running')
            return
        else:
            # set flag to to tell the operator to stop:
            self.logger.debug('Stopping monitor')
            self.operator._stop = True
            self.monitor_thread.stop(self.operator.properties['monitor']['stop_timeout'])
            self.operator._allow_monitor = False  # disable monitor again
            self.operator._busy = False  # Reset in case the monitor was not stopped gracefully, but forcefully stopped

    def update_monitor(self):
        """
        Checks if new data is available and updates the graph.
        Checks if thread is still running and if not: stops timer and reset gui elements
        """
        if self.operator._new_monitor_data:
            self.operator._new_monitor_data = False
            self.curve1.setData(self.operator.analog_monitor_time, self.operator.analog_monitor_1)
            self.curve2.setData(self.operator.analog_monitor_time, self.operator.analog_monitor_2)
        if self.monitor_thread.isFinished():
            self.logger.debug('Monitor thread is finished')
            self.monitor_timer.stop()
            self.plot_points_spinbox.setEnabled(True)
            self.start_button.setEnabled(True)

    def closeEvent(self, event):
        """ Gets called when the window is closed. Could be used to do some cleanup before closing. """

        # # Use this bit to display an "Are you sure"-dialogbox
        # quit_msg = "Are you sure you want to exit labphew monitor?"
        # reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)
        # if reply == QMessageBox.No:
        #     event.ignore()
        #     return
        self.stop_monitor()  # stop monitor if it was running
        self.monitor_timer.stop()  # stop monitor timer, just to be nice
        # perhaps also disconnect devices
        event.accept()


if __name__ == "__main__":
    import labphew  # import this to use labphew style logging

    import sys
    from PyQt5.QtWidgets import QApplication
    from labphew.model.analog_discovery_2_model import Operator

    # To use with real device
    # from labphew.controller.digilent.waveforms import DfwController

    # To test with simulated device
    from labphew.controller.digilent.waveforms import SimulatedDfwController as DfwController


    instrument = DfwController()
    opr = Operator(instrument)
    opr.load_config()

    app = QApplication(sys.argv)
    gui = MonitorWindow(opr)
    gui.show()  # display the GUI
    app.exit(app.exec_())