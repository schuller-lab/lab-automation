#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Feb 25 09:29:55 2026

@author: wkmills
"""

###############################################################################
# The following imports allow you to use the lab controls in any Python script 
import sys 

sys.path.append(r"C:\Users\schul\code\lab-automation")

from LightFieldControls import LightField 
from KinesisControls import (K10CR2, PRMTZ8) 
from PowerMeterControls import PM100D 
###############################################################################

import numpy as np 
from datetime import date 
import os # For mkdir, path.join, etc. 
from pathlib import Path 

def setup(lf_params):
    
    input('Make sure: \n(1) the hwp, analyzer, and mirror mount are disconnected in Kinesis \n' + 
          '(2) there is no LightField window open \n' +
          "(3) the power meter and mirror mount's KCube are on \n" + 'Then press [Enter]')
    # Launch an instance of lightfield 
    lf = LightField(lf_params) 
    
    # Connect to the half-wave plate (number is serial number) 
    hwp = K10CR2('55535784') 
    hwp.connect() 
    
    # Connect to the analyzing polarizer (number is serial number) 
    analyzer = K10CR2('55536784')
    analyzer.connect() 
    
    # Connect to the mirror rotation stage (number is KCube serial number) 
    mirror = PRMTZ8('27270898') 
    mirror.connect()
    
    # Connect to the power meter
    PM = PM100D('USB0::4883::32888::P0007396::0::INSTR') 
    
    # Home the rotation mounts 
    hwp.home() 
    analyzer.home() 
    mirror.home() 
    
    return lf, analyzer, hwp, mirror, PM 

def finish(lf, analyzer, hwp, mirror, PM): 
    # Call this function when the experiment is done 
    hwp.disconnect()
    analyzer.disconnect() 
    mirror.disconnect() 
    PM.disconnect() 
    lf.close()
    
def pixel_deg_callibration(lf, analyzer, hwp, mirror, PM, N_points):
    # Callibrate the pixel/deg mapping 
    # Return an ordered array of degree values to move the mirror to 
    # N = the length of the returned array, i.e., the number of k0 points to measure at 
    NA = 1.3 
    
    # Ask for the zero value of the hwp, analyzer, and attenuator 
    hwp_zero = float(input("What degree setting on the hwp actuator corresponds to a vertical fast axis?\n"))
    analyzer_zero = float(input("What degree setting on the analyzer actuator corresponds to a vertical polarization axis?\n")) 
    attenuator_zero = float(input("What degree setting on the attenuator mount corresponds to a vertical polarization axis?\n"))
    attenuator_angle = float(input("What is the current degree setting of the attenuator?\n"))
    attenuator_offset = attenuator_angle - attenuator_zero 
    
    # Set polarization optics to s/s
    hwp.move_to(attenuator_offset + (90 - attenuator_offset)/2 + hwp_zero)
    analyzer.move_to(analyzer_zero + 90) 
    
    lf.set_center_wavelength(0)
    lf.set_exposure_time(10) 
    input("Focus the microscope on the top surface of a coverslip. Remove the slit and turn on the laser. \n" +
          "Position the input momentum at k = 0 (then at pixel 512), then press [Enter]")
    
    lf.set_exposure_time(100) 
    k_pos1_pix = int(input("Shut the laser, place the diffuser film and turn on the lamp. \n" + 
                           "Bring the bfp into focus, then enter the pixel location of k = +1 (top)\n"))
    k_neg1_pix = int(input("Enter the pixel location of k = -1 (bottom)\n")) 
    pixels_per_2NA = round(NA * np.abs(k_neg1_pix - k_pos1_pix)) 
    PM.set_wavelength(params['pump wavelength']) 
    PM.zero() 
    
    
    input("Remove the diffuser film and turn off the lamp.\n" + 
          "Replace the coverslip with an in-focus sample and position the slit. Then open the laser and press [Enter].")          
    lf.set_center_wavelength(params['pump wavelength'])
    lf.set_exposure_time(100) 
    mirror_0 = mirror.get_position() 
    k_0_pix = int(input('Please enter the pixel location of the incident momentum. (Use "One Look" in the GUI) \n')) 
    
    mirror.move_relative(0.200) # I hope this isn't too much; lower the value if it is 
    #lf.one_look() 
    k_200mdeg_pix = int(input('Please enter the new pixel location of the incident momentum. (Use "One Look" in the GUI) \n')) 
    pixels_per_200mdeg = np.abs(k_0_pix - k_200mdeg_pix) 
    
    # Because the minimum repeatable increment is 0.04 deg (which is ~0.1k0), its best to 
    # (1) calculate the pixel location of every incident k you want to use 
    # (2) figure out how to order those pixels so that you never move by smaller than 0.04 deg
    # (3) convert the array of pixels to an array of degrees 
    # (4) return an ordered 2d array of degrees and k0 values for looping over and naming datafiles 
    
    def reorder_with_spacing(arr, min_spacing):
        # Function for resorting the array of pixels to 
        arr = np.sort(arr)
        n = len(arr)

        # Determine minimum safe index gap
        gap = 1
        while gap < n and np.any(arr[gap:] - arr[:-gap] <= min_spacing):
            gap += 1

        if gap == n:
            raise ValueError("No valid arrangement exists.")

        # Build permutation by stepping by gap
        result_indices = []
        for start in range(gap):
            result_indices.extend(range(start, n, gap))

        return arr[result_indices]
    
    
    pixels_to_measure = np.round(np.linspace(k_0_pix - NA*(k_0_pix-k_pos1_pix), k_0_pix + NA*(k_neg1_pix-k_0_pix), N_points)).astype(int)    
    reordered_pixels = reorder_with_spacing(pixels_to_measure, 0.040 * pixels_per_200mdeg/0.200)
    
    # Convert to degrees, then reorder 
    degrees_to_measure = 0.200/pixels_per_200mdeg * (k_0_pix - pixels_to_measure) + mirror_0 
    reordered_degrees = reorder_with_spacing(degrees_to_measure, 0.040)#[::-1] 
    
    # Make an array of corresponding k values 
    reordered_k_values = (reordered_degrees[::-1] - mirror_0) * pixels_per_200mdeg / 0.200 / pixels_per_2NA * 2*NA
    
    # Move back to original position before ending the expeirment 
    mirror.move_to(mirror_0) 
    
    # Return two ordered arrays of (1) degrees to take measurements at and (2) corresponding k values
    return reordered_degrees, reordered_k_values, reordered_pixels 

def reflection_experiment(lf, analyzer, hwp, mirror, PM, degrees, k_values, pixels):
    # Ask for the zero value of the hwp, analyzer, and attenuator 
    hwp_zero = float(input("What degree setting on the hwp actuator corresponds to a vertical fast axis?\n"))
    analyzer_zero = float(input("What degree setting on the analyzer actuator corresponds to a vertical polarization axis?\n")) 
    attenuator_zero = float(input("What degree setting on the attenuator mount corresponds to a vertical polarization axis?\n"))
    attenuator_angle = float(input("What is the current degree setting of the attenuator?\n"))
    attenuator_offset = attenuator_angle - attenuator_zero 
    
    # As long as this is positive, it works as expected in the for loop (2026-02-27)  
    # its probably also correct if negative, I just haven't checked that 
    
    input("If you ran pixel_deg_callibration(), then the slit should be positioned and the incident momentum should be k=0. \n" + 
          "Check this, then press [Enter]") 
    mirror_0 = mirror.get_position() 
    
    sample = input("What's the name of sample you're measuring reflection from? (no spaces)\n")
    lf.set_center_wavelength(params['pump wavelength']) 
    lf.set_exposure_time(10) 
    
    lf.acquire_background() 
    # Two schools of thought: 
        # Move the mirror on the outside loop because the polarization optics are doing larger movements, 
            # and thus should be less sensitive to small errors over many repititions 
        # Change the polarization on the outside loop because it will make the measurement faster 
            # (waiting for one small mirror movements is faster than waiting for two large polarization movements) 

    # This experiment measures the reflected intensity as a function of input momentum for s/s and p/p polarizations 
    pol = ['s/s', 'p/p'] 
    folder = rf"C:\Users\schul\data\Wes\reflection-experiments\{date.today()}"
    
    def make_unique_dir(base_path):
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            return base_path
    
        counter = 1
        while True:
            new_path = f"{base_path}({counter})"
            if not os.path.exists(new_path):
                os.makedirs(new_path)
                return new_path
            counter += 1
    
    directory = make_unique_dir(folder) 
    # Save degrees, k_values, and pixels for later reference 
    np.save(os.path.join(directory, 'degrees'), degrees)
    np.save(os.path.join(directory, 'k_values'), k_values)
    np.save(os.path.join(directory, 'pixels'), pixels) 
    
    # Set the polarization optics 
    for p in pol:
        # Set hwp 
        if p[0] == 'p':
            hwp.move_to(attenuator_offset / 2 + hwp_zero)
        elif p[0] == 's':
            hwp.move_to(attenuator_offset + (90 - attenuator_offset)/2 + hwp_zero)
        else: 
            print("Something isn't right in the hwp orientation")
        
        # Set analyzer 
        if p[-1] == 'p':
            analyzer.move_to(analyzer_zero) 
        elif p[-1] == 's': 
            analyzer.move_to(analyzer_zero + 90) 
        else: 
            print("Something isn't right in the analyzer orientation")
        
        for i in range(len(degrees)): 
            # Move the mirror and save image as csv 
            mirror.move_to(degrees[i]) 
            filename = f"{np.round(PM.read_power()*1e6):.0f}uW-{p[0]}pol-ky={'-' if k_values[i] <0 else '+'}{np.abs(k_values[i]):.2f}_{sample}_{p[-1]}pol-{(lf.get_exposure_time()):.0f}ms"
            filename.replace('.', ',') # Because .csv files can't have '.' in the name
            lf.acquire_as_csv(filename, directory)
        
        # After acquiring all the data you need, reset the mirror and clear the backup directory 
        mirror.move_to(mirror_0)
        for file in Path(r"C:\Users\schul\OneDrive\Documents\LightField").glob("*.spe"):
            try:
                file.unlink()
                #print(f"Deleted: {file}")
            except Exception as e:
                print(f"Error deleting {file}: {e}")

lf_params = {'experiment_name' : 'LEDs', # This is the only required parameter to initial a LightField experiment 
             # These are all optional 
             #'exposure_time' : 50.0, # Note that you need to use floating points, not integers, for all numeric values
             #'center_wavelength': 540.0, 
             #'grating': '[500nm,300][0][0]'
             }  

params = {"pump wavelength" : 1080, # (nm) 
          "power beamsplitter s-pol R,T" : [0, 0], # Use these to normalize the pump power label 
          "power beamsplitter p-pol R,T" : [0, 0]
          }

#lf, analyzer, hwp, mirror, PM = setup(lf_params) 
#input("Now you can do your experiment")
#N_points = 10 # Number of points to move the mirror to and measure 
#degrees, k_values, pixels = pixel_deg_callibration(lf, analyzer, hwp, mirror, PM, N_points) 
#reflection_experiment(lf, analyzer, hwp, mirror, PM, degrees, k_values, pixels) 
    
#finish(lf, analyzer, hwp, mirror, PM) 

