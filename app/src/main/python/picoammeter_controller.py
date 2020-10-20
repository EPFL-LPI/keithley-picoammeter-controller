#!/usr/bin/env python
# coding: utf-8

# # Picoammeter Controller
# ## For use with a Keithley 6485 / 6487
# Keithley provides the ExceLINK Excel Add In to interact with the ammeter, but it is not user firendly. Thus, this implementation is designed to have a better UX.
# 
# **Note** Many instrument operations for the instrument depend on the line frequency. This defaults to 50 Hz.

# ## API
# ### SCPI Commands
# Generic SCPI commands can be executed by transforming the SCPI code in to attributes iva the hierarchy relationship, then calling it. Instrument properties can be queried by passing no arguments to the call. Commands with no arguments are run by passing an empty string to the call.
# 
# #### Examples
# `inst = Ammeter()`
# 
# **Turning on zero check:** `SYST:ZCH ON` --> `inst.syst.zch( 'ON' )`
# 
# **Aquiring the current range:** `CURR:RANG?` --> `inst.curr.rang()`
# 
# **Acquiring a zero check value:** `SYST:ZCOR:ACQ` --> `inst.syst.zcor.acq( '' )`
# 
# ### Methods
# **Ammeter(port, timeout, line_freq)** Creates an instance of an instrument
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
# **zero()** Zero corrects the instrument, and set it to auto current range
# 
# **rate( cycles )** Sets the integration time relative to power line cycles
# 
# **filter( type, state )** Sets the filter type to use
# 
# ### Properties
# **line_freq** The power line frequency the instrument is connected to 
# 
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

# import logging as log
# log.basicConfig( level = log.DEBUG )

# SCPI imports
import instrument_controller as ic
import visa


# In[2]:


class Ammeter( ic.Instrument ):
    """
    Represents the Keithley 6485 picoammeter
    
    Arbitrary SCPI commands can be performed
    treating the hieracrchy of the command as attributes.
    
    To read an property:  inst.p1.p2.p3()
    To call a function:   inst.p1.p2( 'value' )
    To execute a command: inst.p1.p2.p3( '' )
    """
    #--- inner classes ---
    
    class CurrentRange( MultiValueEnum ):
        """
        Valid current ranges to use
        """
        N2   = '2E-9', '2.100000E-09'
        N20  = '2E-8', '2.100000E-08'
        N200 = '2E-7', '2.100000E-07'
        U2   = '2E-6', '2.100000E-06'
        U20  = '2E-5', '2.100000E-05'
        U200 = '2E-4', '2.100000E-04'
        M2   = '2E-3', '2.100000E-03'
        M20  = '2E-2', '2.100000E-02'
        
        
    class Function( Enum ):
        """
        Valid function states to use. Enclosed in quotes.
        """
        CURRENT    = '"CURR"'
        CURRENT_DC = '"CURR:DC"'
        
        
    #--- methods ---
    
    def __init__( self, port = None, timeout = 10, line_freq = 50 ):
        ic.Instrument.__init__( self, port, timeout, '\r', '\r', '@py' )
        
        #--- public instance variables ---
        self.line_freq = line_freq # the power line frequency
        
        
    #--- private methods ---
    
    
    #--- public methods ---
    def zero( self ):
        """
        Zeroes the internal current of the meter.
        Performs a Zero Check
        """
        self.reset()
        self.func( self.Function.CURRENT )
        self.curr.range( self.CurrentRange.N2 )
        self.init()
        
        self.syst.zcor.stat( ic.Property.OFF )
        self.syst.zcor.aqc( '' )
        
        self.syst.zcor( ic.Property.ON )
        self.curr.rang.auto( ic.Property.ON )
        self.syst.zch( ic.Property.OFF )
        
        self.value
        
        
    def rate( self, cycles ):
        """
        Sets the integration time for the instrument
        
        :param cycles: The number of power line cycles to integrate over, 
            or a time string of the form <time> <units>,
            where <units> is the 1 or 2 letter abbreviation
            'ns', 'us', 'ms', 's'
            e.g. 20 ms
        """
        if isinstance( cycles, str ):
            # integration time passed
            pattern = re.compile( r'(\d+)\s*(\w{2})' ) # matches <time> <unit>
            matches = pattern.match( cycles.strip() )
            
            if matches is not None:
                # matches found
                time = float( matches.group( 1 ) )
                unit = matches.group( 2 )
                
                if unit == 'ns':
                    unit = 1e-9
                    
                elif unit == 'us':
                    unit = 1e-6
                    
                elif unit == 'ms':
                    unit = 1e-3
                
                elif unit == 's':
                    unit = 1
                    
                else:
                    # invalid time unit
                    raise ValueError( 'Invalid time unit' )
                
                # calculate cycles from time
                time *= unit # set time in seconds
                cycles = time* self.line_freq
                
            else:
                # invalid string
                raise ValueError( 'Invalid time string' )
                
        # check cycles is in valid range (0.01 - line_freq PLCs)
        if cycles < 0.01 or cycles > self.line_freq:
            raise ValueError( 'Integration cycles out of range. Must be between 0.01 and {}'.format( self.line_freq ) )

        return self.sens.curr.nplc( cycles )
    
        
    def filter( self, ftype, state ):
        """
        Sets the window size of each filter, and turns them on or off
        
        :param ftype: The filter type to set. 
            Valid values for 
                Median filter: 'median' or 'med'
                Average filter: 'average' or 'avg'; can be modified by ':moving' or ':repeat'
                    e.g. avg:moving, average:repeat
        
        :param state: An integer between 2 and 100 for average filter, 
            or 1 to 5 for medain filter,
            to set the size and enable filtering.
            To enable or disable, pass True or 'ON', and False or 'OFF', respectively.
        """
        # set filter state
        ftype = ftype.lower()
        if ftype == 'median' or ftype == 'med':
            # median filter
            if isinstance( state, int ):
                # validate size between 1 and 5
                if isinstance( state, int ):
                    if state < 1 or state > 5:
                        raise ValueError( 'Invalid window size' )
                        
                # set window and enable
                self.med.rank( state )
                self.med( ic.Property.ON )
                
            elif state == True or state.lower() == 'on':
                # enable filter
                self.med( ic.Property.ON )
            
            elif state == False or state.lower() == 'off':
                # disable filter
                self.med( ic.Property.OFF )
            
            else:
                # invalid state argument
                raise ValueError( 'Invalid filter state' )
            
        else:
            # parse ftype
            pattern = re.compile( r'(\w+)\s*:\s*(\w+)' )
            matches = pattern.match( ftype )
            if matches is not None:
                # modifier found, change window type
                ftype = matches.group( 1 )
                wtype = matches.group( 2 )
            
            else:
                # modifier not found, leave window type
                wtype = None
            
            if ftype == 'average' or ftype == 'avg':
                # average fitler
                if wtype is not None:
                    # set window type
                    if wtype == 'moving':
                        self.aver.tcon( 'MOV' )
                        
                    elif wtype == 'repeat':
                        self.aver.tcon( 'REP' )
                        
                    else:
                        # invalid window type
                        raise ValueError( 'invalid window type {}'.format( wtype ) )
                
                if isinstance( state, int ):
                    # validate size between 2 and 100
                    if isinstance( state, int ):
                        if state < 2 or state > 100:
                            raise ValueError( 'Invalid window size' )
                    
                    # set size, and enable
                    self.aver.coun( state )
                    self.aver( ic.Property.ON )
                    
                else:
                    # enable or disable filter
                    if state == True or state.lower() == 'on':
                        self.aver( ic.Property.ON )
                    
                    elif state == False or state.lower() == 'off':
                        self.aver( ic.Property.OFF )
                        
                    else:
                        # invalid filter
                        raise ValueError( 'Invalid filter type' )
                        
            else:
                # invalid filter
                raise ValueError( 'Invalid filter type "{}"'.format( ftype ) )
        
        
        


# # CLI

# In[1]:


if __name__ == '__main__':
    import getopt
    
    #--- helper functions ---
    
    def print_help():
        print( """
Keithley Picoammeter Controller CLI

Use:
python picoammeter_controller.py [port=<COM>] <function> [arguments]
<COM> is the port to connect to [Default: COM14]
<function> is the ammeter command to run
[arguments] is a space separated list of the arguments the function takes

API:
+ write()
+ query()

        """)
    


# In[13]:


# am = Ammeter( 'COM14', timeout = 15 )


# In[15]:


# del am


# In[14]:


# am.connect()


# In[7]:


# am.id


# In[ ]:


# am.disconnect()


# In[9]:


# print( am.trace.data() )


# In[30]:


# am.sens.curr.nplc()


# In[59]:


# am.arm.coun()


# In[27]:


# am.reset()
# am.form.elem( 'time,read' )
# am.trig.count( 20 )
# am.trac.poin( 20 )
# am.trac.feed( 'sens' )
# am.trac.feed.cont( 'next' )
# am.syst.zch( 'off' )
# am.init()
# print( am.trac.data() )


# In[13]:


# am.syst.zch( 'OFF' )


# In[8]:


# am.syst.zcor( 'OFF' )


# In[ ]:




