#!/usr/bin/env python
# coding: utf-8

# # SCPI Instrument Controller
# Parent class for instrument control

# ## API
# ### SCPI Commands
# Generic SCPI commands can be executed by transforming the SCPI code in to attributes iva the hierarchy relationship, then calling it. Instrument properties can be queried by passing no arguments to the call. Commands with no arguments are run by passing an empty string to the call.
# 
# #### Examples
# `inst = Instrument()`
# 
# 
# ### Methods
# **Instrument(port, timeout)** Creates an instance of an instrument
# 
# **connect()** Connects the program to the instrument
# 
# **disconnect()** Disconnects the instrument from the program, closing the port
# 
# **write( msg )** Sends **msg** to the instrument 
# 
# **read()** Gets the most recent response from the instrument
# 
# **query( msg )** Sends **msg** to the instrument and returns its response
# 
# **reset()** Sets the instruemnt to its default state
# 
# **init()** Initializes the instrument for a measurement
# 
# ### Properties
# **port** The communication port
# 
# **rid** The resource id associated with the instrument [Read Only]
# 
# **timeout** The communication timeout of the instrument [Read Only]
# 
# **id** The manufacturer id of the instrument [Read Only]
# 
# **value** The current value of the instrument [Read Only]
# 
# **connected** Whether the instrument is connected or not [Read Only]

# In[1]:


# standard imports
import os
import sys
import serial
import re
from enum import Enum
from aenum import MultiValueEnum

# FREEZE
# import logging
# logging.basicConfig( level = logging.DEBUG )

# SCPI imports
import visa


# In[2]:


class Property( object ):
        """
        Represents a scpi property of the instrument 
        """
        
        #--- static variables ---
        ON  = 'ON'
        OFF = 'OFF'
        
        
        #--- class methods ---
        
        def __init__( self, inst, name ):
            self.__inst = inst # the instrument
            self.name = name.upper()

            
        def __getattr__( self, name ):
            return Property( 
                self.__inst, 
                ':'.join( ( self.name, name.upper() ) ) 
            )

        
        def __call__( self, value = None ):
            if value is None:
                # get property
                return self.__inst.query( self.name + '?')
                
            else:
                # set value
                if isinstance( value, Enum ):
                    # get value from enum
                    value = value.value
                    
                if not isinstance( value, str ):
                    # try to convert value to string
                    value = str( value )
                    
                return self.__inst.write( self.name + ' ' + value )
        
        
        #--- static methods ---
        
        @staticmethod
        def val2bool( val ):
            """
            Converts standard input to boolean values

            True:  'on',  '1', 1, True
            False: 'off', '0', 0, False
            """
            if isinstance( val, str ):
                # parse string input
                val = val.lower()

                if val == 'on' or val == '1':
                    return True

                elif val == 'off' or val == '0':
                    return False

                else:
                    raise ValueError( 'Invalid input' )

            return bool( val )
    
    
        @staticmethod
        def val2state( val ):
            """
            Converts standard input to scpi state

            ON:  True,  '1', 1, 'on',  'ON'
            OFF: False, '0', 0, 'off', 'OFF'
            """
            state = Property.val2bool( val )
            if state:
                return 'ON'

            else:
                return 'OFF'


# In[1]:


class SCPI_Instrument():
    """
    Represents an instrument
    
    Arbitrary SCPI commands can be performed
    treating the hieracrchy of the command as attributes.
    
    To read an property:  inst.p1.p2.p3()
    To call a function:   inst.p1.p2( 'value' )
    To execute a command: inst.p1.p2.p3( '' )
    """
  
    #--- methods ---
    
      
    def __getattr__( self, name ):
        return Property( self, name )
        
    
    def __init__( self, port = None, timeout = 10, read_terminator = None, write_terminator = None, backend = '' ):
        """
        Creates an instance of an Instrument, to communicate with VISA instruments
        
        :param port: The name of the port to connect to [Default: None]
        :param timeout: The communication timeout in seconds [Default: 10]
        :param read_terminator: The character that terminates data being read from the instrument [Default: pyvisa default]
        :param write_terminator: The character that terminates strings being written to the instrument [Default: pyvisa default]
        :param backend: The pyvisa backend to use for communication
        :returns: An Instrument communicator
        """
        #--- private instance vairables ---
        self.__backend = backend
        self.__rm = visa.ResourceManager( backend ) # the VISA resource manager
        self.__inst = None # the ammeter
        self.__port = None
        self.__rid = None # the resource id of the instrument
        self.__timeout = timeout* 1000
        
        self.__read_terminator = read_terminator
        self.__write_terminator = write_terminator
        
        
        
        # init connection
        self.port = port
        
        
    def __del__( self ):
        """
        Disconnects and deletes the Instrument
        """
        if self.connected:
            self.disconnect()
            
        del self.__inst
        del self.__rm
        
    #--- private methods ---
    
    
    #--- public methods ---
    
    @property
    def backend( self ):
        return self.__backend
    
    
    @property
    def instrument( self ):
        return self.__inst
    
    
    @property
    def port( self ):
        return self.__port
        
        
    @port.setter
    def port( self, port ):
        """
        Disconnects from current connection and updates port and id.
        Does not reconnect.
        """
        if self.__inst is not None:
            self.disconnect()
            
        self.__port = port
        
        # TODO: Make backend support more robust
        if port is not None:
            # adjust port name for resource id to match backend
            if self.__backend == '@py':
                if 'COM' not in port:
                    r_port = 'COM' + port
                
            else:
                r_port = port.replace( 'COM', '' )
                
            self.__rid = 'ASRL{}::INSTR'.format( r_port )    
            
        else:
            self.__rid = None
         
        
    @property
    def rid( self ):
        """
        Return the resource id of the instrument
        """
        return self.__rid
    
    
    @rid.setter
    def rid( self, rid ):
        self.__rid = rid
    
    
    @property
    def timeout( self ):
        return self.__timeout
    
    
    @property
    def id( self ):
        """
        Returns the id of the ammeter
        """
        return self.query( '*IDN?' )
            
          
    @property
    def value( self ):
        """
        Get current value
        """
        return self.query( 'READ?' )
    
        
    @property
    def connected( self ):
        """
        Returns if the instrument is connected
        """
        if self.__inst is None:
            return False
 
        try:
            # session throws excpetion if not connected
            self.__inst.session
            return True
        
        except visa.InvalidSession:
            return False
        
        
    def connect( self ):
        """
        Connects to the instrument on the given port
        """
        if self.__inst is None:
            self.__inst = self.__rm.open_resource( self.rid )
            self.__inst.timeout = self.__timeout
            
            # set terminators
            if self.__read_terminator is not None:
                self.__inst.read_termination = self.__read_terminator
                
            if self.__write_terminator is not None:
                self.__inst.write_termination = self.__write_terminator
            
        else:
            self.__inst.open()
            
        self.id # place instrument in remote control
        
        
    def disconnect( self ):
        """
        Disconnects from the instrument, and returns local control
        """
        if self.__inst is not None:
            self.syst.loc( '' )
            self.__inst.close()
            
            
    def write( self, msg ):
        """
        Delegates write to resource
        """
        if self.__inst is None:
            raise Exception( 'Can not write, instrument not connected.' )
            return
            
        return self.__inst.write( msg )
            
            
    def read( self ):
        """
        Delegates read to resource
        """
        if self.__inst is None:
            raise Exception( 'Can not read, instrument not connected' )
            return
            
        return self.__inst.read()
    
    
    def query( self, msg ):
        """
        Delegates query to resource
        """
        if self.__inst is None:
            raise Exception( 'Can not query, instrument not connected' )
        
        return self.__inst.query( msg )
            
        
    def reset( self ):
        """
        Resets the meter to inital state
        """
        return self.write( '*RST' )
    
    
    def init( self ):
        """
        Initialize the instrument
        """
        return self.write( 'INIT' )
        


# # CLI

# In[1]:


if __name__ == '__main__':
    import getopt
    
    #--- helper functions ---
    
    def print_help():
        print( """
Instrument Controller CLI

Use:
python instrument_controller.py [port=<COM>] <function> [arguments]
<COM> is the port to connect to [Default: COM14]
<function> is the ammeter command to run
[arguments] is a space separated list of the arguments the function takes

API:
+ write()
+ query()

        """)
    


# # Work

# In[5]:


len( ' +3.907985E-14,+0.000000E+00,+5.684342E-14,+3.214844E+00,+6.039613E-14,+4.215820E+00,+5.684342E-14,+5.216797E+00,+6.039613E-14,+6.217773E+00,+5.684342E-14,+7.218750E+00,+6.039613E-14,+8.219727E+00,+5.684342E-14,+9.220703E+00,+5.684342E-14,+1.022168E+01,+4.973799E-14,+1.122266E+01,+6.039613E-14,+1.222266E+01,+6.039613E-14,+1.322363E+01,+5.684342E-14,+1.422461E+01,+6.039613E-14,+1.522559E+01,+6.394885E-14,+1.622656E+01,+6.039613E-14,+1.722754E+01,+6.039613E-14,+1.822852E+01,+6.039613E-14,+1.922949E+01,+6.039613E-14,+2.023047E+01,+6.039613E-14,+2.123047E+01,+4.973799E-14,+2.223145E+01,+5.329071E-14,+2.323242E+01,+4.973799E-14,+2.423340E+01,+5.684342E-14,+2.523438E+01,+6.039613E-14,+2.623535E+01,+5.329071E-14,+2.723633E+01,+6.394885E-14,+2.823730E+01,+4.973799E-14,+2.923730E+01,+4.973799E-14,+3.023828E+01,+4.618528E-14,+3.123926E+01,+5.329071E-14,+3.224023E+01,+5.329071E-14,+3.324121E+01,+4.973799E-14,+3.424219E+01,+5.684342E-14,+3.524316E+01,+4.973799E-14,+3.624414E+01,+4.973799E-14,+3.724512E+01,+5.329071E-14,+3.824512E+01,+5.329071E-14,+3.924609E+01,+5.684342E-14,+4.024707E+01,+4.973799E-14,+4.124805E+01,+5.684342E-14,+4.224902E+01,+5.329071E-14,+4.325000E+01,+5.329071E-14,+4.425098E+01,+5.329071E-14,+4.525195E+01,+4.973799E-14,+4.625293E+01,+5.684342E-14,+4.725293E+01,+6.039613E-14,+4.825391E+01,+5.684342E-14,+4.925488E+01,+4.973799E-14,+5.025586E+01,+5.329071E-14,+5.125684E+01,+6.039613E-14,+5.225781E+01,+5.329071E-14,+5.325879E+01,+4.973799E-14,+5.425977E+01,+4.618528E-14,+5.526074E+01,+4.973799E-14,+5.626074E+01,+6.039613E-14,+5.726172E+01,+6.039613E-14,+5.826270E+01,+5.684342E-14,+5.926367E+01,+4.973799E-14,+6.026465E+01,+4.618528E-14,+6.126563E+01,+5.329071E-14,+6.226660E+01,+5.684342E-14,+6.326758E+01,+4.973799E-14,+6.426758E+01,+4.973799E-14,+6.526855E+01,+4.973799E-14,+6.626953E+01,+4.263256E-14,+6.727051E+01,+4.618528E-14,+6.827148E+01,+4.973799E-14,+6.927246E+01,+4.973799E-14,+7.027344E+01,+5.329071E-14,+7.127441E+01,+5.329071E-14,+7.227539E+01,+4.973799E-14,+7.327539E+01,+4.618528E-14,+7.427637E+01,+4.973799E-14,+7.527734E+01,+5.329071E-14,+7.627832E+01,+4.973799E-14,+7.727930E+01,+5.684342E-14,+7.828027E+01,+6.039613E-14,+7.928125E+01,+5.684342E-14,+8.028223E+01,+4.618528E-14,+8.128320E+01,+4.973799E-14,+8.228320E+01,+4.263256E-14,+8.328418E+01,+5.329071E-14,+8.428516E+01,+5.329071E-14,+8.528613E+01,+4.973799E-14,+8.628711E+01,+4.618528E-14,+8.728809E+01,+4.973799E-14,+8.828906E+01,+4.973799E-14,+8.929004E+01,+4.973799E-14,+9.029004E+01,+4.973799E-14,+9.129102E+01,+4.973799E-14,+9.229199E+01,+4.263256E-14,+9.329297E+01,+4.973799E-14,+9.429395E+01,+4.618528E-14,+9.529492E+01,+4.973799E-14,+9.629590E+01,+4.973799E-14,+9.729688E+01,+4.618528E-14,+9.829785E+01,+5.329071E-14,+9.929785E+01,+6.039613E-14,+1.002988E+02' )


# In[ ]:




