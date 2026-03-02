# -*- coding: utf-8 -*-
"""
Created on Fri Feb 13 10:14:19 2026

@author: Wesley Mills and ChatGPT 
"""

import clr 
import sys 
import os
from System.IO import FileAccess 
from System import String
from System.Collections.Generic import List
import numpy as np 
import time 

sys.path.append(os.environ['LIGHTFIELD_ROOT'])
sys.path.append(os.environ['LIGHTFIELD_ROOT']+'\\AddInViews')
clr.AddReference("PrincetonInstruments.LightFieldViewV4")
clr.AddReference("PrincetonInstruments.LightField.AutomationV4")
clr.AddReference("PrincetonInstruments.LightFieldAddInSupportServices")

from PrincetonInstruments.LightField.Automation import Automation
from PrincetonInstruments.LightField.AddIns import CameraSettings
#from PrincetonInstruments.LightField.AddIns import ExperimentSettings
from PrincetonInstruments.LightField.AddIns import SpectrometerSettings
#from PrincetonInstruments.LightField.AddIns import ExportSettings 
from PrincetonInstruments.LightField.AddIns import DeviceType 

from SpectrometerWavelengthRanges import wavelength_ranges 

    
class LightField:
    # Params is a dict of values used to set up LightField 
    def __init__(self, params):
        # Launch LightField and set initial parameters 
        # First parameter is whether or not to display LightField GUI
        # Second parameter forces LF to load with no experiment 
        self.lf = Automation(True, List[String]())
        self.experiment = self.lf.LightFieldApplication.Experiment
        self.file_manager = self.lf.LightFieldApplication.FileManager 
        
        # Load experiment using built-in member 
        self.experiment.Load(params['experiment_name'])
        
        # Optionally, initialize a few settings using methods from this class 
        if 'exposure_time' in params: self.set_exposure_time(params['exposure_time'])
        if 'center_wavelength' in params: self.set_center_wavelength(params['center_wavelength'])
        if 'grating' in params: self.set_grating(params['grating']) 
        
        # Check that temp is locked and everything else is correct 
        input('Please check that: \n' +
              '(1) The camera and the spectrometer are connected in the Devices tab \n' + 
              '(2) The aquisition time units are ms \n' + 
              '(3) The image orientation is how you\'d like \n' + 
              '(4) The temperature is locked at -70 C \n' + 
              '(5) You\'ve checked the bfp focus and acquired / applied a background subtraction \n' + 
              '\n Press [Enter] when ready to proceed')
        self.did_first_acquire = False # see acquire_as_csv() below 
    
    def set_value(self, setting, value):
        # Check for existence before setting
        if self.experiment.Exists(setting):
            self.experiment.SetValue(setting, value)
        else:
            print("The setting" + str(setting) + " doesn\'t exist")
            return False 
    
    def get_value(self, setting):
        # Check for existence before setting
        if self.experiment.Exists(setting):
            return self.experiment.GetValue(setting) 
        else:
            print("The setting" + str(setting) + " doesn\'t exist")
            return False 
    
    def set_exposure_time(self, time):
        if self.camera_found():  
            self.set_value(CameraSettings.ShutterTimingExposureTime, float(time)) 
            print("The exposure time has been set to " + str(self.get_exposure_time()))
            
    def get_exposure_time(self):
        if self.camera_found():  
            return self.get_value(CameraSettings.ShutterTimingExposureTime) 
    
    def set_center_wavelength(self, wavelength):
        if self.spectrometer_found(): 
            self.set_value(SpectrometerSettings.GratingCenterWavelength, float(wavelength))
            print("The center wavelength has been set to " + str(self.get_center_wavelength()))
            
    def get_center_wavelength(self):
        if self.spectrometer_found(): 
            return self.get_value(SpectrometerSettings.GratingCenterWavelength)
    
    def set_grating(self, grating):
        if self.spectrometer_found(): 
           self.set_value(SpectrometerSettings.GratingSelected, grating)
           print("The grating has been set to " + str(self.get_grating()))
           
    def get_grating(self):
        if self.spectrometer_found(): 
           return self.get_value(SpectrometerSettings.GratingSelected)

    def camera_found(self):
        # Check if a camera is connected 
        for device in self.experiment.ExperimentDevices: 
            if (device.Type == DeviceType.Camera):
                return True 
        # If connected device is not a camera, inform the user 
        print("Camera not found. Please add a camera and try again.") 
        return False 
    
    def spectrometer_found(self):
        # Check is a spectrometer is connected 
        for device in  self.experiment.ExperimentDevices: 
            if (device.Type == DeviceType.Spectrometer):
                return True 
        print('Spectrometer not found. Please add a spectrometer and try again.') 
        return False 
    
    # Acquire and apply background 
    def acquire_background(self):
        input("Use the GUI to acquire and apply a background correction.\n" +
              "Maybe one day this will be automated...\n" + 
              "Press [Enter] when ready to proceed.")
    
    # Take "one look"
    def one_look(self):
        self.experiment.Acquire() 
        time.sleep(self.get_exposure_time()/1000 + 2.5) # Wait for the acquisition to finish 
    
    # Acquire and save image as csv 
    def acquire_as_csv(self, filename, directory=None):
        
        if not self.did_first_acquire: # Trying to save the first-acquired frame always results in an error, so this is my solution 
            self.experiment.Acquire() 
            time.sleep(self.get_exposure_time()/1000 + 4) # Wait for the acquisition to finish; this first one sometimes takes longer, it seems 
            self.did_first_acquire = True 
        
        # Acquire a frame 
        self.experiment.Acquire()          
        time.sleep(self.get_exposure_time()/1000 + 2.5) # Wait for the acquisition to finish 
        
        # Convert the frame into a numpy array 
        recent_file = self.file_manager.GetRecentlyAcquiredFileNames()[0]
        #print('Get Recently Acquired suceeded')
        image_set = self.file_manager.OpenFile(recent_file, FileAccess.ReadWrite)
        #print("Open File suceeded")
        frame = image_set.GetFrame(0, 0)
        data_1d = np.array(frame.GetData())
        data_2d = data_1d.reshape((frame.Height, frame.Width))
        
        # Get the wavelength info 
        try: 
            wavelengths = wavelength_ranges[str(int(self.get_center_wavelength()))]
        except KeyError:
            print('*** WARNING: ***')
            print('The current center wavelength hasn\'t been entered in SpectrometerWavelengthRanges.py')
            print('Using an array of zeros instead.')
            wavelengths = np.zeros(1024) 
                
        # Get the directory to save in; default to Desktop\data\misc\ 
        if directory:
            csv_path = os.path.join(directory, filename + ".csv")
        else:
            csv_path = os.path.join(r"C:\Users\schul\OneDrive\Desktop\data\misc", filename + ".csv")
        
        # Write the csv file line-by-line to ensure its a 2D matrix 
        with open(csv_path, 'w') as f:
            # Write wavelength row
            f.write("Wavelength:,")
            f.write(",".join(map(str, wavelengths)))
            f.write("\n")
            # Write the rest of the 2D array 
            for row in data_2d:
                f.write(",") # First column (column under "wavelength:") is blank)
                f.write(','.join(map(str, row)))
                f.write('\n')
        
        print("Image saved as " + filename + ".csv")

    # Exit/close LightField 
    def close(self):
        self.lf.Dispose() 
        print("LightField has been closed.")

