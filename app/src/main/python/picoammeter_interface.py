#!/usr/bin/env python
# coding: utf-8

# # GUI Interface for Keithley 6487 Picoammeter
# 
# ## Requirements
# Ensure that `import-ipynb` module is installed
# 
# ## Compiling
# 1. Ensure fbs is installed `pip install fbs`
# 2. Iniate a project `python3 -m fbs startproject`
# 3. Freeze the binary `python3 -m fbs freeze`
# 4. Create an installer `python3 -m fbs installer`
# 
# ## Converting to .py
# To save this file for use as a CLI, convert it to a .py file using `jupyter nbconvert --to python <filename>`

# In[3]:


import os
import sys
import re
import glob
import serial.tools.list_ports
from collections import namedtuple

# FREEZE
# import logging
# logging.basicConfig( level = logging.DEBUG )

# PyQt
from PyQt5 import QtGui

from PyQt5.QtCore import (
    Qt,
    QCoreApplication,
    QTimer,
    QThread
)

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QLineEdit,
    QFileDialog,
    QMessageBox
)

# controller
# import import_ipynb # FREEZE
import picoammeter_controller as pac

import visa


# In[4]:


class AmmeterInterface( QWidget ):
    
    #--- window close ---
    def closeEvent( self, event ):
        self.delete_controller()
        event.accept()
        
    
    #--- destructor ---
    def __del__( self ):
        self.delete_controller()
        
    
    #--- initializer ---
    def __init__( self, resources ): # FREEZE
    # def __init__( self ):
        super().__init__()
        
        #--- instance variables ---
        image_folder = resources + '/images/' # FREEZE
        # image_folder = os.getcwd() + '/images/'
        self.img_redLight = QtGui.QPixmap(    image_folder + 'red-light.png'    ).scaledToHeight( 32 )        
        self.img_greenLight = QtGui.QPixmap(  image_folder + 'green-light.png'  ).scaledToHeight( 32 )
        self.img_yellowLight = QtGui.QPixmap( image_folder + 'yellow-light.png' ).scaledToHeight( 32 )
        
        self.ports  = self.getComPorts()
        self.port   = None
        self.inst   = None # the instrument
        
        #--- timers ---
        self.read_attempts = 0
        
        self.read_timer = QTimer()
        self.read_timer.setSingleShot( True )
        self.read_timer.timeout.connect( self.get_readings )
        
        self.status_timer = QTimer()
        self.status_timer.timeout.connect( self.update_exp_status_ui )
        
        #--- init UI ---
        self.init_ui()
        self.register_connections()
        
        #--- init variables ---
        
#         self.updatePort()
        
        
    def init_ui( self ):
        #--- main window ---
        self.setGeometry( 100, 100, 700, 500 )
        self.setWindowTitle( 'Picoammeter Controller' )
        
        lo_main = QVBoxLayout()
        lo_main.addLayout( self.ui_mainToolbar() )
        lo_main.addLayout( self.ui_settings() )
        lo_main.addSpacing( 35 )
        lo_main.addWidget( self.ui_status() )
        lo_main.addLayout( self.ui_commands() )
        
        self.setLayout( lo_main )
        
        # update measurement time
        self.set_meas_time_ui()
        
        self.show()
       
    
    def ui_mainToolbar( self ):
        lo_mainToolbar = QHBoxLayout()
        
        self.ui_mainToolbar_comPorts( lo_mainToolbar )
        self.ui_mainToolbar_connect(  lo_mainToolbar )
        
        return lo_mainToolbar
    
    
    def ui_settings( self ):
        lo_settings = QVBoxLayout()
        
        lo_row_1 = QHBoxLayout()
        self.ui_settings_range( lo_row_1 )
        self.ui_settings_trigger( lo_row_1 )
        
        lo_row_2 = QHBoxLayout()
        self.ui_settings_readings( lo_row_2 )
        self.ui_settings_integration_time( lo_row_2 )
        self.ui_settings_measurement_time( lo_row_2 )
        self.ui_settings_step_time( lo_row_2 )
        
        lo_row_3 = QHBoxLayout()
        self.ui_settings_filter( lo_row_3 )
        
        lo_row_4 = QHBoxLayout()
        self.ui_folder( lo_row_4 )
        lo_row_4.addSpacing( 30 )
        self.ui_filename( lo_row_4 )
        
        lo_settings.addLayout( lo_row_1 )
        lo_settings.addLayout( lo_row_2 )
        lo_settings.addLayout( lo_row_3 )
        lo_settings.addLayout( lo_row_4 )
        
        return lo_settings
    
    
    def ui_status( self ):
        # experiment status
        self.w_exp_status = QWidget()
        self.w_exp_status.setVisible( False )
        lo_exp_status = QHBoxLayout( self.w_exp_status )
        
        self.ui_remaining_time( lo_exp_status )
        self.ui_measurement_status( lo_exp_status )
        
        # read status
        self.w_read_status = QWidget()
        self.w_read_status.setVisible( False )
        lo_read_status = QHBoxLayout( self.w_read_status )
        
        self.ui_read_status( lo_read_status )
        
        # main container
        self.w_status = QWidget()
        self.w_status.setVisible( False ) # initially hidden
        lo_status = QHBoxLayout( self.w_status )
        
        lo_status.addWidget( self.w_exp_status )
        lo_status.addWidget( self.w_read_status )
        lo_status.addSpacing( 10 )
        return self.w_status
    
    
    def ui_commands( self ):
        lo_commands = QVBoxLayout()
        self.ui_zero( lo_commands )
        self.ui_start( lo_commands )
        self.ui_last_experiment( lo_commands )
        
        return lo_commands
    
    
    def ui_mainToolbar_comPorts( self, parent ):
        self.cmb_comPort = QComboBox()
        self.update_ports_ui()
        
        lo_comPort = QFormLayout()
        lo_comPort.addRow( 'COM Port', self.cmb_comPort )
        
        parent.addLayout( lo_comPort )
        
    
    def ui_mainToolbar_connect( self, parent ):
        # connect / disconnect
        self.lbl_statusLight = QLabel()
        self.lbl_statusLight.setAlignment( Qt.AlignCenter )
        self.lbl_statusLight.setPixmap( self.img_redLight )
        
        self.lbl_status = QLabel( 'Disconnected' )
        self.btn_connect = QPushButton( 'Connect' )
    
        lo_statusView = QVBoxLayout()
        lo_statusView.addWidget( self.lbl_statusLight )
        lo_statusView.addWidget( self.lbl_status )
        lo_statusView.setAlignment( Qt.AlignHCenter )
        
        lo_status = QHBoxLayout()
        lo_status.addLayout( lo_statusView )
        lo_status.addWidget( self.btn_connect )
        lo_status.setAlignment( Qt.AlignLeft )
        
        parent.addLayout( lo_status )
        
        
    def ui_settings_range( self, parent ):
        ranges = [
            'Auto',
            '2 nA',
            '20 nA',
            '200 nA',
            '2 uA',
            '20 uA',
            '200 uA',
            '2 mA',
            '20 mA'
        ]
        
        self.cmb_range = QComboBox()
        self.cmb_range.addItems( ranges )
            
        lbl_range = QLabel( 'Range' )
            
        lo_range = QHBoxLayout()
        lo_range.setAlignment( Qt.AlignCenter )
        
        lo_range.addWidget( lbl_range )
        lo_range.addWidget( self.cmb_range )
        
        parent.addLayout( lo_range )
    
    
    def ui_settings_integration_time( self, parent ):
        ( low, high ) = self.get_integration_times()
        low  *= 1000 # convert seconds to ms
        high *= 1000
        
        self.sb_int_time = QDoubleSpinBox()
        self.sb_int_time.setMinimum( low ) 
        self.sb_int_time.setMaximum( high )
        self.sb_int_time.setValue( 100 )
        self.sb_int_time.setToolTip( 'Integration time can range from {} to {} ms'.format( low, high ) )
        
        lbl_int_time = QLabel( 'Integration Time' )
        lbl_unit = QLabel( 'ms' )
        
        lo_int_time = QHBoxLayout()
        lo_int_time.setAlignment( Qt.AlignCenter )
        
        lo_int_time.addWidget( lbl_int_time )
        lo_int_time.addWidget( self.sb_int_time )
        lo_int_time.addWidget( lbl_unit )
        
        parent.addLayout( lo_int_time )
        
    
    def ui_settings_readings( self, parent ):
        high = self.get_max_readings()
        
        self.sb_readings = QSpinBox()
        self.sb_readings.setMinimum( 1 )
        self.sb_readings.setMaximum( high )
        self.sb_readings.setToolTip( 'Can store between 1 and {} readings'.format( high ) )
        
        lbl_readings = QLabel( 'Readings' )
        
        lo_readings = QHBoxLayout()
        lo_readings.setAlignment( Qt.AlignCenter )
        
        lo_readings.addWidget( lbl_readings )
        lo_readings.addWidget( self.sb_readings )
        
        parent.addLayout( lo_readings )
        
        
    def ui_settings_trigger( self, parent ):
        self.cmb_trigger = QComboBox()
        self.cmb_trigger.addItem( 'Immediate' )
        self.cmb_trigger.addItem( 'External' )
        
        lbl_trigger = QLabel( 'Trigger' )
        
        lo_trigger = QHBoxLayout()
        lo_trigger.setAlignment( Qt.AlignCenter )
        
        lo_trigger.addWidget( lbl_trigger )
        lo_trigger.addWidget( self.cmb_trigger )
        
        parent.addLayout( lo_trigger )
        
        
    def ui_settings_measurement_time( self, parent ):
        self.lbl_meas_time = QLabel( '100' )
        self.lbl_meas_time_units = QLabel( 'ms' )
        lbl_title = QLabel( 'Total Time:' )
        
        lo_meas = QHBoxLayout()
        lo_meas.setAlignment( Qt.AlignCenter )
        
        lo_meas.addWidget( lbl_title )
        lo_meas.addWidget( self.lbl_meas_time )
        lo_meas.addWidget( self.lbl_meas_time_units )
        
        parent.addLayout( lo_meas )
        
        
    def ui_settings_step_time( self, parent ):
        self.lbl_step_time = QLabel( '100' )
        self.lbl_step_time_units = QLabel( 'ms' )
        lbl_title = QLabel( 'Step Time:' )
        
        lo_step = QHBoxLayout()
        lo_step.setAlignment( Qt.AlignCenter )
        
        lo_step.addWidget( lbl_title )
        lo_step.addWidget( self.lbl_step_time )
        lo_step.addWidget( self.lbl_step_time_units )
        
        parent.addLayout( lo_step )
        
    
    def ui_settings_filter( self, parent ):
        lo_filters = QHBoxLayout()
        self.ui_settings_filter_median( lo_filters )
        self.ui_settings_filter_mean( lo_filters )
        
        parent.addLayout( lo_filters )
        
        
    def ui_settings_filter_median( self, parent ):
        self.cb_filter_median = QCheckBox()
        self.cb_filter_median.setToolTip( 'Stores the median of data samples. Always rolling window. Performed first if both are enabled.' )
        lbl_enable = QLabel( 'Enable' )
        
        self.sb_filter_median_window = QSpinBox()
        self.sb_filter_median_window.setMinimum( 1 )
        self.sb_filter_median_window.setMaximum( 5 )
        self.sb_filter_median_window.setToolTip( 'The rank width between 1 and 5. Indicates the number of values to include on wither side of the current reading.' )
        lbl_window = QLabel( 'Rank' )
        
        lo_settings = QFormLayout()
        lo_settings.addRow( lbl_enable, self.cb_filter_median )
        lo_settings.addRow( lbl_window, self.sb_filter_median_window )
        
        lbl_title = QLabel( 'Median Filter' )
        lbl_title.setStyleSheet( 'font-size: 1.1em; font-weight: bold;' )
        lbl_title.setAlignment( Qt.AlignCenter )
        
        lo_median = QVBoxLayout()
        lo_median.setContentsMargins( 30, 30, 30, 30 )
        lo_median.setAlignment( Qt.AlignTop )
        
        lo_median.addWidget( lbl_title )
        lo_median.addLayout( lo_settings )
        
        parent.addLayout( lo_median )
        
        
    def ui_settings_filter_mean( self, parent ):
        self.cb_filter_mean = QCheckBox()
        self.cb_filter_mean.setToolTip( 'Stores the mean of data samples. Performed second if both are enabled.' )
        
        self.sb_filter_mean_window = QSpinBox()
        self.sb_filter_mean_window.setMinimum( 2 )
        self.sb_filter_mean_window.setMaximum( 100 )
        self.sb_filter_mean_window.setToolTip( 'The window width between 2 and 100.' )
        
        self.cmb_filter_mean_type = QComboBox()
        self.cmb_filter_mean_type.addItems( [
            'Moving',
            'Batch'
        ] )
        self.cmb_filter_mean_type.setToolTip( 'Moving sets the window to roll; Batch performs an average on a full window, then clears the buffer.' )
        
        
        lo_settings = QFormLayout()
        lo_settings.addRow( 'Enable', self.cb_filter_mean )
        lo_settings.addRow( 'Window', self.sb_filter_mean_window )
        lo_settings.addRow( 'Type', self.cmb_filter_mean_type )
        
        lo_mean = QVBoxLayout()
        lo_mean.setContentsMargins( 30, 30, 30, 30 )
        lo_mean.setAlignment( Qt.AlignTop )
        
        lbl_title = QLabel( 'Mean Filter' )
        lbl_title.setStyleSheet( 'font-size: 1.1em; font-weight: bold;' )
        lbl_title.setAlignment( Qt.AlignCenter )
        
        lo_mean.addWidget( lbl_title )
        lo_mean.addLayout( lo_settings )  
        
        parent.addLayout( lo_mean )
        
    
    def ui_folder( self, parent ):
        self.btn_open_location_chooser = QPushButton( 'Choose...')
        self.le_folder = QLineEdit()
        
        lbl_location = QLabel( 'Save in' )
        
        lo_storage = QHBoxLayout()
        lo_storage.addWidget( lbl_location )
        lo_storage.addWidget( self.le_folder)
        lo_storage.addWidget( self.btn_open_location_chooser )
        
        parent.addLayout( lo_storage )
        
        
    def ui_filename( self, parent ):
        self.le_filename = QLineEdit()
        lbl_filename = QLabel( 'File' )
        
        lo_filename = QHBoxLayout()
        lo_filename.addWidget( lbl_filename )
        lo_filename.addWidget( self.le_filename )
        
        parent.addLayout( lo_filename )
        
        
    def ui_remaining_time( self, parent ):        
        ( time, units ) = self.time_to_label( self.get_measurement_time() )
        
        lbl_title = QLabel( 'Remaining Time:' )
        self.lbl_remaining_time = QLabel( str( time ) )
        self.lbl_remaining_time_units = QLabel( units )
        
        lo_remaining_time = QHBoxLayout()
        lo_remaining_time.setAlignment( Qt.AlignHCenter )
        lo_remaining_time.addWidget( lbl_title )
        lo_remaining_time.addWidget( self.lbl_remaining_time )
        lo_remaining_time.addWidget( self.lbl_remaining_time_units )
        
        parent.addLayout( lo_remaining_time )
        
        
    def ui_measurement_status( self, parent ):
        lbl_title = QLabel( 'Measurement' )
        lbl_seperator = QLabel( 'of')
        self.lbl_total_measurements = QLabel( str( self.sb_readings.value() ) )
        self.lbl_measurements_taken = QLabel( '0' )
        
        lo_meas_status = QHBoxLayout()
        lo_meas_status.setAlignment( Qt.AlignHCenter )
        lo_meas_status.addWidget( lbl_title )
        lo_meas_status.addWidget( self.lbl_measurements_taken )
        lo_meas_status.addWidget( lbl_seperator )
        lo_meas_status.addWidget( self.lbl_total_measurements )
        
        parent.addLayout( lo_meas_status )
        
        
    def ui_read_status( self, parent ):
        lbl_title = QLabel( 'Reading data...' )
        
        lo_read_status = QHBoxLayout()
        lo_read_status.setAlignment( Qt.AlignHCenter )
        lo_read_status.addWidget( lbl_title )
        
        parent.addLayout( lo_read_status )
        
        
    def ui_zero( self, parent ):
        lo_zero = QHBoxLayout()
        
        self.btn_zero = QPushButton( 'Zero' )
        lo_zero.addWidget( self.btn_zero )
        
        parent.addLayout( lo_zero )
    
    
    def ui_start( self, parent ):
        lo_start = QHBoxLayout()
        
        self.btn_start = QPushButton( 'Start' )
        lo_start.addWidget( self.btn_start )
        
        parent.addLayout( lo_start )
    
    
    def ui_last_experiment( self, parent ):
        lo_last_exp = QHBoxLayout()
        
        self.btn_last_exp = QPushButton( 'Save Last Experiment' )
        lo_last_exp.addWidget( self.btn_last_exp )
        
        parent.addLayout( lo_last_exp )
        
    
    #--- ui functionality ---
    
    def register_connections( self ):
        self.cmb_comPort.currentTextChanged.connect( self.change_port )
        
        self.btn_connect.clicked.connect( self.toggle_connect )
        self.btn_open_location_chooser.clicked.connect( self.select_storage_location )
        
        # commands
        self.btn_start.clicked.connect( self.execute )
        self.btn_zero.clicked.connect( self.zero )
        self.btn_last_exp.clicked.connect( self.save_last_experiment )
        
        # update measurement time
        self.sb_readings.valueChanged.connect( self.set_meas_time_ui )
        self.sb_int_time.valueChanged.connect( self.set_meas_time_ui )
        
        self.cb_filter_median.stateChanged.connect( self.set_meas_time_ui )
        self.sb_filter_median_window.valueChanged.connect( self.set_meas_time_ui )
        
        self.cb_filter_mean.stateChanged.connect( self.set_meas_time_ui )
        self.cmb_filter_mean_type.currentTextChanged.connect( self.set_meas_time_ui )
        self.sb_filter_mean_window.valueChanged.connect( self.set_meas_time_ui )
    
    
    def getComPorts( self ):
        """ (from https://stackoverflow.com/a/14224477/2961550)
        Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
        """
        if sys.platform.startswith( 'win' ):
            ports = [ 'COM%s' % (i + 1) for i in range( 256 ) ]
            
        elif sys.platform.startswith( 'linux' ) or sys.platform.startswith( 'cygwin' ):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob( '/dev/tty[A-Za-z]*' )
            
        elif sys.platform.startswith( 'darwin' ):
            ports = glob.glob( '/dev/tty.*' )
            
        else:
            raise EnvironmentError( 'Unsupported platform' )

        result = []
        for port in ports:
            try:
                s = serial.Serial( port )
                s.close()
                result.append( port )
                
            except ( OSError, serial.SerialException ):
                pass
            
        return result    
    
    
    #--- slot functions ---
    
    def change_port( self ):
        """
        Changes port and disconnects from current port if required
        """
        # disconnect and delete controller
        self.delete_controller()
          
        # update port
        self.update_port()
        
        
    def update_ports( self ):
        """
        Check available COMs, and update UI list
        """
        self.ports = self.getComPorts()
        self.updatePortsUI()
        
    
    def toggle_connect( self ):
        """
        Toggles connection between selected com port
        """
        # show waiting for communication
        self.lbl_status.setText( 'Waiting...' )
        self.lbl_statusLight.setPixmap( self.img_yellowLight )
        self.repaint()
        
        # create laser controller if doesn't already exist, connect
        if self.inst is None:
            try:
                self.inst = pac.Ammeter( self.port, timeout = 30 )
                self.inst.connect()
                
            except Exception as err:
                self.update_connected_ui( False )
                
                warning = QMessageBox()
                warning.setWindowTitle( 'Picoammeter Controller Error' )
                warning.setText( 'Could not connect\n{}'.format( err ) )
                warning.exec()
            
        else:
            self.delete_controller()
        
        # update ui
        if self.inst is not None:
            self.update_connected_ui( self.inst.connected )
            
        else:
            self.update_connected_ui( False )
        
        
    def select_storage_location( self ):
        storage_location = QFileDialog()
        storage_location.setDefaultSuffix( '.csv' )
        storage_location.setFileMode( QFileDialog.Directory )
        storage_location.setOptions( QFileDialog.ShowDirsOnly )
        storage_location.setAcceptMode( QFileDialog.AcceptSave )
        
        location = storage_location.getExistingDirectory( self, 'Save Location' )
        self.le_folder.setText( location )

        
    def execute( self ):
        method = self.btn_start.text()
        if method == 'Start':
            self.run()
            
        elif method == 'Stop':
            self.stop()
        
    
    def stop( self ):
        self.inst.abort( '' )
        self.inst.trace.feed.control( 'never' )
        self.read_timer.stop()
        
        self.get_readings()
    
    
    def run( self ):
        LONG_EXPERIMENT = 10* 1e3
        
        # validate settings
        if not self.validate_settings():
            return
        
        # update ui
        self.update_measurement_ui( True )
        self.repaint()
        
        # set up measurement
        self.inst.reset()
        self.set_range( self.cmb_range.currentText() )
        self.set_integration_time( self.sb_int_time.value() )
        self.set_readings( self.sb_readings.value() )
        self.set_filters()
        self.set_arm( 'Immediate' )
        self.set_trigger( self.cmb_trigger.currentText() )
        self.set_units()
        
        # run measurement
        self.inst.syst.zch( 'off' ) # turn off zero corrections
        self.inst.syst.zcor( 'off' )
        self.inst.syst.azero( 'off' ) # turn off autozero
        self.inst.trace.clear( '' ) # clear buffer
        self.inst.trace.feed( 'sense' )
        self.inst.trace.feed.control( 'next' )
        self.inst.init() 
        
        # get data after readings
        self.read_attempts = 0
        run_time = self.get_measurement_time()
        
        if run_time >= LONG_EXPERIMENT:    
            # update experiment status
            self.lbl_total_measurements.setText( str( self.sb_readings.value() ) )                                  
            self.update_status_ui( True, False )

            self.status_timer.start( 1e3 )
            
        self.read_timer.start( run_time )
        
        
    def get_readings( self  ):
        MAX_ATTEMPTS = 5
        ATTEMPT_DELAY = 2000
        
        self.read_timer.stop()  # cancel read timer
        self.read_attempts += 1 # increment read attemtps
        
        # update ui
        self.update_status_ui( False, True )
        self.repaint()
        
        try:
            data = self.inst.trace.data()
            
        except visa.VisaIOError:
            # too many attempts, fail
            if self.read_attempts >= MAX_ATTEMPTS: 
                warning = QMessageBox()
                warning.setWindowTitle( 'Picoammeter Controller Error' )
                warning.setText( 'Communication timeout' )
                warning.exec()

                self.read_attemtps = 0 # reset read attempts for next run
                self.update_measurement_ui( False )
                return
            
            else:
                # failed to read, wait a bit and try again
                self.read_timer.start( ATTEMPT_DELAY )
                
        else: 
            #  data read succeeded
            location = self.get_location()
            
            # save data
            try:
                data = self.parse_data( data )
                
            except ValueError as err:
                # parse error
                # try again if attempts left
                if self.read_attempts < MAX_ATTEMPTS:
                    self.read_timer.start( ATTEMPT_DELAY )
                
                else: 
                    # no attempts left, write raw data, warn of parse error
                    with open( location, 'w' ) as f:
                        f.write( 'Time [s], Current [A]\n' ) # headers
                        f.write( data )
                    
                    warning = QMessageBox()
                    warning.setWindowTitle( 'Picoammeter Controller Error' )
                    warning.setText( 'Error parsing data. Raw data still saved.' )
                    warning.exec()

                    self.read_attemtps = 0 # reset read attempts for next run
                
            else:
                # parse successful
                with open( location, 'w' ) as f:
                    f.write( 'Time [s], Current [A]\n' ) # headers
                    for d in data:
                        f.write( '{}, {}\n'.format( d.time, d.value ) )
                  
                warning = QMessageBox()
                warning.setWindowTitle( 'Experiment Done' )
                warning.setText( 'Experiment is complete. Data has been saved.' )
                warning.exec()
                
                self.read_attemtps = 0 # reset read attempts for next run
                
        # update ui
        self.reset_status_ui()
        self.update_measurement_ui( False )
        
        
    def save_last_experiment( self ):
        if not self.validate_settings():
            return
        
        self.read_attempts = 0
        self.get_readings()

        
    def set_range( self, rng ):
        if rng == 'Auto':
            self.inst.curr.range.auto( 'on' )
            
        else:
            self.inst.curr.range( self.map_range( rng ) )
            
            
    def set_integration_time( self, time ):
        cycles = self.time_to_cycles( time )
        self.inst.sens.curr.nplc( cycles )
        
        
    def set_readings( self, readings ):
        self.inst.trig.count( readings )
        self.inst.trace.points( readings )
        
        
    def set_filters( self ):
        self.set_median_filter( 
            self.cb_filter_median.isChecked(), 
            self.sb_filter_median_window.value() 
        )
        
        # modify filter type to comply with controller
        ftype = self.cmb_filter_mean_type.currentText().lower()
        if ftype == 'batch':
            ftype = 'repeat'
        
        self.set_mean_filter( 
            self.cb_filter_mean.isChecked(), 
            ftype,
            self.sb_filter_mean_window.value() 
        )
        
        
    def set_median_filter( self, enable, window ):
        self.inst.filter( 'median', window )
        
        state = 'on' if enable else 'off'
        self.inst.sense.median( state )
            
            
    def set_mean_filter( self, enable, ftype, window ):
        self.inst.filter( 'average:' + ftype, window )
        
        state = 'on' if enable else 'off'
        self.inst.sense.average( state )
        
        
    def set_arm( self, arm ):
        if arm == 'Immediate':
            self.inst.arm.source( 'imm' )
            
    
    def set_trigger( self, trigger ):
        if trigger == 'Immediate':
            self.inst.trig.source( 'immediate' )
            
        elif trigger == 'External':
            self.inst.trig.source( 'tlink' )
            
        else:
            raise ValueException( 'Invalid trigger source {}'.format( trigger ) )
        
    
    def set_units( self ):
        self.inst.format.elements( 'time,reading' ) # set units to store [Default: time, reading]
        self.inst.trace.tstamp.format( 'absolute' ) # set time stamp relative to trigger
        
    
    def zero( self ):
        self.inst.zero()
        
        
    #--- helper functions ---
    
    def delete_controller( self ):
        if self.inst is not None:
            self.inst.disconnect()
            del self.inst
            self.inst = None
    
    
    def parse_com_port( self, name ):
        pattern = "(\w+)\s*(\(\s*\w*\s*\))?"
        matches = re.match( pattern, name )
        if matches:
            name = matches.group( 1 )
            if name == 'No COM ports available...':
                return None
            else:
                return name
        else:
            return None
        
        
    def update_port( self ):
        self.port = self.cmb_comPort.currentText()
        
        
    def update_ports_ui( self ):
        self.cmb_comPort.clear()
        
        if len( self.ports ):
            self.cmb_comPort.addItems( self.ports )
        else:
            self.cmb_comPort.addItem( 'No COM ports available...' )
            
    
    def update_connected_ui( self, connected ):
        if connected == True:
            statusText = 'Connected'
            statusLight = self.img_greenLight
            btnText = 'Disconnect'
            
        elif connected == False:
            statusText = 'Disconnected'
            statusLight = self.img_redLight
            btnText = 'Connect'
            
        else:
            statusText = 'Error'
            statusLight = self.img_yellowLight
            btnText = 'Connect'
        
        self.lbl_status.setText( statusText )
        self.lbl_statusLight.setPixmap( statusLight )
        self.btn_connect.setText( btnText )
        
        
    def update_measurement_ui( self, running ):
        if running == True:
            btnText = 'Stop'
            style = 'background-color: #f0a0a0;'
            
          
        elif running == False:
            btnText = 'Start'
            style = ''
           
        else:
            warning = QMessageBox()
            warning.setWindowTitle( 'Picoammeter Controller Error' )
            warning.setText( 'An error occurred' )
            btnText = 'Start'
            style = ''
        
        self.btn_start.setText( btnText )
        self.btn_start.setStyleSheet( style )
        
        
    def update_status_ui( self, experiment, reading ):
        show_status = ( experiment or reading )
        
        self.w_status.setVisible( show_status )
        self.w_exp_status.setVisible( experiment )
        self.w_read_status.setVisible( reading )
        
        
    def reset_status_ui( self ):
        self.status_timer.stop()
        self.update_status_ui( False, False )                                         
        self.lbl_measurements_taken.setText( '0' )
        
    
    def set_meas_time_ui( self ):
        # set step time
        ( step, units ) = self.time_to_label( self.get_measurement_step_time() )
        self.lbl_step_time_units.setText( units )
        self.lbl_step_time.setText( str( step ) )
        
        # set total time
        ( time, units ) = self.time_to_label( self.get_measurement_time() )
        self.lbl_meas_time_units.setText( units )
        self.lbl_meas_time.setText( str( time ) )
           
            
    def set_remaining_time_ui( self ):
        ( remaining, units ) = self.time_to_label( self.read_timer.remainingTime() ) 
        remaining = max( remaining, 0 )                        
                                                
        self.lbl_remaining_time.setText( str( int( remaining ) ) )
        self.lbl_remaining_time_units.setText( units )
    
    
    def set_remaining_meas_ui( self ):
        elapsed = self.read_timer.interval() - self.read_timer.remainingTime()
        taken = int( elapsed/ self.get_measurement_step_time() )
        taken = min( taken, self.sb_readings.value() )
                                                
        self.lbl_measurements_taken.setText( str( taken ) )
    
    
    def update_exp_status_ui( self ):
        self.set_remaining_time_ui()
        self.set_remaining_meas_ui()
    
            
    def time_to_label( self, time ):
        if time > 60* 1000:
            # minutes
            time = int( time/ ( 60* 1000 ) )
            units = 'min'
        
        elif time > 1000:
            # seconds
            time = round( time / 1000, 1 )
            units = 's'
            
        else:
            units = 'ms'
            
        return ( time, units )
        
    def get_integration_times( self ):
        """
        The picoammeter can integrate on the low end from 0.01 power line cycles,
        up to 1 second (regardless of line frequency).
        
        Assumes 50 Hz unless instrument is connected
        
        :returns: The smallest integration time in seconds.
        """
        if self.inst is not None:
            low  = 0.01/ self.inst.line_freq
        else:
            low = 0.01/ 50
            
        high = 1
        
        return ( low, high )
    
    
    def get_max_readings( self ):
        """
        Returns the maximum number of readings the ammeter can hold
        """
        return 2500
    
    
    def map_range( self, rng ):
        """
        Converts a string into a range for the instrument
        """
        rmap = {
            '2 nA':   pac.Ammeter.CurrentRange.N2,
            '20 nA':  pac.Ammeter.CurrentRange.N20,
            '200 nA': pac.Ammeter.CurrentRange.N200,
            '2 uA':   pac.Ammeter.CurrentRange.U2,
            '20 uA':  pac.Ammeter.CurrentRange.U20,
            '200 uA': pac.Ammeter.CurrentRange.U200,
            '2 mA':   pac.Ammeter.CurrentRange.M2,
            '20 mA':  pac.Ammeter.CurrentRange.M20
        }
        
        if rng in rmap:
            return rmap[ rng ]
            
        else:
            raise ValueError( 'Invalid range' )
            
            
    def time_to_cycles( self, time ):
        """
        converts time in ms to cycles
        """
        return ( time/ 1000 )* self.inst.line_freq
    
    
    def parse_data( self, data ):
        """
        Parses string of data into tuples for writing.
        
        TODO: Include units
        """
        data =  data.split( ',' )
        data = list( map( lambda x: x.strip(), data ) ) # remove white space
        # create data structure
        fields = [
            'time',
            'value'
        ]   
        Reading = namedtuple( 'Reading', fields )
        
        try:
            return [ Reading( time = float( data[ i + 1 ] ), value = float( data[ i ] ) ) for i in range( 0, len( data ), len( fields ) ) ]
    
        except ValueError as err:
            raise err
            
    
    def get_location( self ):
        return os.path.join( self.le_folder.text(), self.le_filename.text() )
    
    
    def validate_settings( self ):
        valid = True
        warning = QMessageBox()
        warning.setWindowTitle( 'Picoammeter Controller Error' )
        
        # check connection
        if ( self.inst is None ) or ( not self.inst.connected ):
            valid = False
            warning.setText( 'Not connected to instrument' )
            warning.exec()
        
        # is file is available
        try:
            file = self.get_location()
            f = open( file, 'w' )
            f.close()
            
        except FileNotFoundError as err:
            valid = False
            warning.setText( 'Can not write to file {}'.format( file ) )
            warning.exec()
            
        except Exception as err:
            valid = False
            warning.setText( 'An error occured\n{}'.format( str( err ) ) )
            warning.exec()
        
        return valid
    
    
    def get_measurement_step_time( self ):
        single_val_time = self.sb_int_time.value()
        
        # account for mean batch fitler
        if self.cb_filter_mean.isChecked() and self.cmb_filter_mean_type.currentText() == 'Batch':
            single_val_time *= self.sb_filter_mean_window.value()
            
        return int( single_val_time )
        
        
    def get_measurement_time( self ):
        single_val_time = self.sb_int_time.value()
        const_time = 0
        
        # account for fitlers, median performed first
        if self.cb_filter_median.isChecked():
            const_time += single_val_time* ( self.sb_filter_median_window.value() - 1 )
            
        if self.cb_filter_mean.isChecked():
            ftype = self.cmb_filter_mean_type.currentText()
            window = self.sb_filter_mean_window.value()
            
            if ftype == 'Moving':
                const_time += single_val_time* ( window - 1 )  
                
            elif ftype == 'Batch':
                single_val_time *= window
            
            else:
                raise ValueError( 'Invalid mean filter type {}'.format( ftype ) )
            
        
        total_time = single_val_time* ( self.sb_readings.value() ) + const_time # first reading at t = 0
        return int( total_time ) 


# In[5]:


# FREEZE
# app = QCoreApplication.instance()
# if app is None:
#     app = QApplication( sys.argv )
    
# main_window = AmmeterInterface()
# sys.exit( app.exec_() )


# # In[63]:


# # FREEZE
# get_ipython().run_line_magic('load_ext', 'autoreload')
# get_ipython().run_line_magic('autoreload', '1')





# In[ ]:




