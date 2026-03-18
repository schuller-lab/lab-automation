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

from Thorlabs.MotionControl.DeviceManagerCLI import DeviceNotReadyException # for error handling 
###############################################################################

import numpy as np 
from datetime import date 
import os # For mkdir, path.join, etc. 
from pathlib import Path 

def setup(lf_params, devices={}):
    
    input('Make sure: \n(1) the hwp, analyzer, and mirror mount are disconnected in Kinesis \n' + 
          '(2) there is no LightField window open \n' +
          "(3) the power meter and mirror mount's KCube are on \n" + 'Then press [Enter]')    
    
    # Serial numbers of the various cage rotation mounts 
    rotation_serials = {'attenuator': '55537294', 
                       'hwp' : '55535784',
                       'analyzer' : '55536784'}
    
    # Launch an instance of lightfield 
# =============================================================================
#     lf = LightField(lf_params) 
#     devices['lf'] = lf 
# =============================================================================
    
    # Connect to the attenuator 
    attenuator = K10CR2('attenuator', rotation_serials['attenuator'])
    attenuator.connect() 
    devices['attenuator'] = attenuator 
        
    # Connect to the half-wave plate 
    hwp = K10CR2('hwp', rotation_serials['hwp'])
    hwp.connect() 
    devices['hwp'] = hwp
        
    # Connect to the analyzing polarizer 
    analyzer = K10CR2('analyzer', rotation_serials['analyzer'])
    analyzer.connect()  
    devices['analyzer'] = analyzer 
        
    # Connect to the mirror rotation stage (number is KCube serial number) 
    mirror = PRMTZ8('mirror', '27270898')
    mirror.connect() 
    devices['mirror'] = mirror 
        
    # Connect to the power meter
    PM = PM100D('USB0::4883::32888::P0007396::0::INSTR') 
    devices['PM'] = PM 
    
    return devices 

def finish(devices): 
    
    # Unpack devices 
    try: 
        lf = devices['lf'] 
        attenuator = devices['attenuator']
        analyzer = devices['analyzer']
        hwp = devices['hwp'] 
        mirror = devices['mirror']
        PM = devices['PM'] 
        
        lf.get_center_wavelength() 
        attenuator.get_position() 
        analyzer.get_position() 
        hwp.get_position() 
        mirror.get_position() 
        PM.identify() 
    except Exception as e: 
        print(f"Error when unpacking devices. Its possible that some aren't connected. Aborting finish().\n{e}")
        return 
    
    # Call this function when the experiment is done 
    attenuator.disconnect() 
    hwp.disconnect()
    analyzer.disconnect() 
    mirror.disconnect() 
    PM.disconnect() 
    lf.close()
    
    return 

def set_power_and_pol(devices, power, pol):
    # Takes a desired power and polarization and sets the attenuator and hwp to achieve that (as closely as possible)
    
    # Power should be a string of the form "##.## mW", or "##.## %" (whitespace required) 
    try: 
        value, units = power.split() 
    except Exception as e: 
        print('Error parsing desired power. Should be a string of the form "##.## mW" or "##.## %" (whitespace required).')
        print(f"Full error: {e}")
        return 0
    if units != ('mW' or '%'): 
        print('Desired power should be a string of the form "##.## mW" or "##.## %" (whitespace required). Aborting set_power_and_pol().')
        return 0
    
    # pol should be 's' or 'p' (this can be expanded later)
    if pol != ('s' or 'p'):
        print('Desired polarization should be "s" or "p". Aborting set_power_and_pol().')
        return 0 
    
    # Unpack devices 
    try: 
        #lf = devices['lf'] 
        attenuator = devices['attenuator']
        #analyzer = devices['analyzer']
        hwp = devices['hwp'] 
        #mirror = devices['mirror']
        PM = devices['PM'] 
        
        #lf.get_center_wavelength() 
        attenuator.get_position() 
        #analyzer.get_position() 
        hwp.get_position() 
        #mirror.get_position() 
        PM.identify() 
    except Exception as e: 
        print(f"Error when unpacking devices. Its possible that some aren't connected. Aborting set_power_and_pol().\n{e}")
    
    if units == 'mW':
        print('I need to write this part still...')
        PM 
    elif units == '%':
        print("I need to write this part still...")
    attenuator
    hwp
    
    return 

def pixel_deg_calibration(devices, N_points):
    
    # Unpack devices 
    try: 
        lf = devices['lf'] 
        attenuator = devices['attenuator']
        analyzer = devices['analyzer']
        hwp = devices['hwp'] 
        mirror = devices['mirror']
        PM = devices['PM'] 
        
        lf.get_center_wavelength() 
        attenuator.get_position() 
        analyzer.get_position() 
        hwp.get_position() 
        mirror.get_position() 
        PM.identify() 
    except Exception as e: 
        print(f"Error when unpacking devices. Its possible that some aren't connected. Aborting pixel_deg_calibration().\n{e}")
        return
    
    # Callibrate the pixel/deg mapping 
    # Return an ordered array of degree values to move the mirror to 
    # N = the length of the returned array, i.e., the number of k0 points to measure at 
    NA = 1.3 
    
    # Ask for the zero value of the hwp, analyzer, and attenuator 
    #attenuator_zero = float(input("What degree setting on the attenuator mount corresponds to a vertical polarization axis?\n"))
    #hwp_zero = float(input("What degree setting on the hwp actuator corresponds to a vertical fast axis?\n"))
    #analyzer_zero = float(input("What degree setting on the analyzer actuator corresponds to a vertical polarization axis?\n")) 
    #attenuator_angle = float(input("What is the current degree setting of the attenuator?\n"))
    attenuator_offset = attenuator.get_position() - attenuator.vertical  
    
    # Set polarization optics to s/s
    hwp.move_to(attenuator_offset + (90 - attenuator_offset)/2 + hwp.vertical)
    analyzer.move_to(analyzer.vertical + 90) 
    attenuator.move_to(attenuator.vertical) 
    
    lf.set_center_wavelength(0)
    lf.set_exposure_time(10) 
    print("Make sure you've checked the bfp focus.")
    input("Focus the microscope on the top surface of your sample. Remove the slit and turn on the laser. \n" +
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
    

###############################################################################
# Reflection experiment (pump reflection)
def reflection_experiment(devices, degrees, k_values, pixels):
    """
    Measures reflected pump intensity across k-space for s/s and p/p polarizations.
    """
    # Unpack devices 
    try: 
        lf = devices['lf'] 
        attenuator = devices['attenuator']
        analyzer = devices['analyzer']
        hwp = devices['hwp'] 
        mirror = devices['mirror']
        PM = devices['PM'] 
        
        lf.get_center_wavelength() 
        attenuator.get_position() 
        analyzer.get_position() 
        hwp.get_position() 
        mirror.get_position() 
        PM.identify() 
    except Exception as e: 
        print(f"Error when unpacking devices. Its possible that some aren't connected. Aborting reflection_experiment().\n{e}")
        return
    
    sample = input("What's the name of the sample you're measuring reflection from? (no spaces)\n")
    lf.set_center_wavelength(params['pump wavelength']) 
    lf.set_exposure_time(10) 
    
    input("Set the exposure time you want, then press [Enter].")
    lf.acquire_background() 
    
    pol = ['s/s', 'p/p'] 
    
    mirror_0 = mirror.get_position()

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
    # interactive menu for choosing which polarization to run repeatedly
    allowed_pols = ['s/s', 'p/p']
    menu_text = "Choose which polarization to run for reflection (type number or name):\n"
    for idx, pp in enumerate(allowed_pols, start=1):
        menu_text += f"  {idx}) {pp}\n"
    menu_text += f"  {len(allowed_pols)+1}) finish\n"

    while True:
        choice = input(menu_text).strip()
        # allow numeric choice or direct string
        if choice == str(len(allowed_pols)+1) or choice.lower() in ['finish', 'f', 'q', 'quit', 'exit']:
            print("Finished polarization runs for reflection — exiting polarization menu.")
            break

        if choice.isdigit():
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(allowed_pols):
                p = allowed_pols[choice_idx]
            else:
                print("Invalid numeric choice, try again.")
                continue
        else:
            # normalize input like "s/s" or "S/S"
            choice_norm = choice.lower().replace(' ', '')
            matches = [pp for pp in allowed_pols if pp.lower() == choice_norm]
            if len(matches) == 1:
                p = matches[0]
            else:
                print("Invalid choice, try again.")
                continue
            
        # Ask for the zero value of the hwp, analyzer, and attenuator 
        #attenuator_zero = float(input("What degree setting on the attenuator mount corresponds to a vertical polarization axis?\n"))
        #hwp_zero = float(input("What degree setting on the hwp actuator corresponds to a vertical fast axis?\n"))
        #analyzer_zero = float(input("What degree setting on the analyzer actuator corresponds to a vertical polarization axis?\n")) 
    

        # Now run the selected polarization measurement (same logic as before)
        attenuator_angle = float(input(f"Doing a {p}-pol measurement now; make sure the laser is on. What is the current degree setting of the attenuator?\n"))
        attenuator_offset = attenuator_angle - attenuator.vertical 
        # As long as this is positive, it works as expected in the for loop (2026-02-27)  
        # its probably also correct if negative, I just haven't checked that 
        
        # Set hwp 
        if p[0] == 'p':
            hwp.move_to(attenuator_offset / 2 + hwp.vertical)
        elif p[0] == 's':
            hwp.move_to(attenuator_offset + (90 - attenuator_offset)/2 + hwp.vertical)
        else: 
            print("Something isn't right in the hwp orientation")
        
        # Set analyzer 
        if p[-1] == 'p':
            analyzer.move_to(analyzer.vertical) 
        elif p[-1] == 's': 
            analyzer.move_to(analyzer.vertical + 90) 
        else: 
            print("Something isn't right in the analyzer orientation")
            
        for i in range(len(degrees)): 
           # Move the mirror and save image as csv 
           mirror.move_to(degrees[i]) 
           filename = f"{params['pump wavelength']}nm-{np.round((PM.read_power() if PM is not None else 0)*1e6):.0f}uW-{p[0]}pol-ky={'-' if k_values[i] <0 else '+'}{np.abs(k_values[i]):.2f}_{sample}_{p[-1]}pol-{(lf.get_exposure_time()):.0f}ms"
           filename = filename.replace('.', ',') # Because .csv files can't have '.' in the name
           lf.acquire_as_csv(filename, directory)
        
        mirror.move_to(mirror_0) 
    
    return 

###############################################################################
# SHG experiment 
def SHG_experiment(devices, degrees, k_values, pixels):
    """
    Measures SHG response across k-space for s/p and p/p polarizations.
    """
    # Unpack devices 
    try: 
        lf = devices['lf'] 
        attenuator = devices['attenuator']
        analyzer = devices['analyzer']
        hwp = devices['hwp'] 
        mirror = devices['mirror']
        PM = devices['PM'] 
        
        lf.get_center_wavelength() 
        attenuator.get_position() 
        analyzer.get_position() 
        hwp.get_position() 
        mirror.get_position() 
        PM.identify() 
    except Exception as e: 
        print(f"Error when unpacking devices. Its possible that some aren't connected. Aborting SHG_experiment().\n{e}")
        return
    
    sample = input("What's the name of sample you're measuring SHG from? (no spaces)\n")
    lf.set_center_wavelength(params['pump wavelength']//2) 
    lf.set_exposure_time(500) 
    
    input("Set the exposure time you want, then press [Enter].")
    lf.acquire_background() 
    
    pol = ['s/p', 'p/p'] 
    folder = rf"C:\Users\schul\data\Wes\GaN-SHG\{date.today()}"
    
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
    
    mirror_0 = mirror.get_position()
    
    # Set the polarization optics 
    # interactive menu for choosing which polarization to run repeatedly (SHG)
    allowed_pols = ['s/p', 'p/p']
    menu_text = "Choose which polarization to run for SHG (type number or name):\n"
    for idx, pp in enumerate(allowed_pols, start=1):
        menu_text += f"  {idx}) {pp}\n"
    menu_text += f"  {len(allowed_pols)+1}) finish\n"

    while True:
        choice = input(menu_text).strip()
        # allow numeric choice or direct string
        if choice == str(len(allowed_pols)+1) or choice.lower() in ['finish', 'f', 'q', 'quit', 'exit']:
            print("Finished polarization runs for SHG — exiting polarization menu.")
            break

        if choice.isdigit():
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(allowed_pols):
                p = allowed_pols[choice_idx]
            else:
                print("Invalid numeric choice, try again.")
                continue
        else:
            # normalize input like "s/p" or "S/P"
            choice_norm = choice.lower().replace(' ', '')
            matches = [pp for pp in allowed_pols if pp.lower() == choice_norm]
            if len(matches) == 1:
                p = matches[0]
            else:
                print("Invalid choice, try again.")
                continue

        # Ask for the zero value of the hwp, analyzer, and attenuator 
        #attenuator_zero = float(input("What degree setting on the attenuator mount corresponds to a vertical polarization axis?\n"))
        #hwp_zero = float(input("What degree setting on the hwp actuator corresponds to a vertical fast axis?\n"))
        #analyzer_zero = float(input("What degree setting on the analyzer actuator corresponds to a vertical polarization axis?\n")) 
    

        # Now run the selected polarization measurement (same logic as before)
        attenuator_angle = float(input(f"Doing a {p}-pol measurement now; make sure the laser is on. What is the current degree setting of the attenuator?\n"))
        attenuator_offset = attenuator_angle - attenuator.vertical 
        # As long as this is positive, it works as expected in the for loop (2026-02-27)  
        # its probably also correct if negative, I just haven't checked that 
        
        # Set hwp 
        if p[0] == 'p':
            hwp.move_to(attenuator_offset / 2 + hwp.vertical)
        elif p[0] == 's':
            hwp.move_to(attenuator_offset + (90 - attenuator_offset)/2 + hwp.vertical)
        else: 
            print("Something isn't right in the hwp orientation")
        
        # Set analyzer 
        if p[-1] == 'p':
            analyzer.move_to(analyzer.vertical) 
        elif p[-1] == 's': 
            analyzer.move_to(analyzer.vertical + 90) 
        else: 
            print("Something isn't right in the analyzer orientation")
            
        for i in range(len(degrees)): 
           # Move the mirror and save image as csv 
           mirror.move_to(degrees[i]) 
           filename = f"{params['pump wavelength']//2}nm-{np.round((PM.read_power() if PM is not None else 0)*1e6):.0f}uW-{p[0]}pol-ky={'-' if k_values[i] <0 else '+'}{np.abs(k_values[i]):.2f}_{sample}_{p[-1]}pol-{(lf.get_exposure_time()):.0f}ms"
           filename = filename.replace('.', ',') # Because .csv files can't have '.' in the name
           lf.acquire_as_csv(filename, directory)
        
        mirror.move_to(mirror_0) 
    
    return 

# =============================================================================
# def device_methods_menu(devices):
#     menu = {} 
#     
#     while True: 
#         print('\nDevice Methods menu:')
#         device_count = 1
#         for key in devices: 
#             print(f'{str(device_count)}. {key}') 
#             menu[str(device_count)] = devices[key] 
#             device_count += 1 
#         print(f'{str(device_count)}. Back')
#         
#         choice = input('> ') 
#         
#         if choice == str(device_count):
#             break 
#         
#         func = menu.get(choice) 
#         
#         if func: 
#             print(func)
#         else:
#             print('invalid option')
# =============================================================================
        

lf_params = {'experiment_name' : 'SHG', # This is the only required parameter to initial a LightField experiment 
             # These are all optional 
             #'exposure_time' : 50.0, # Note that you need to use floating points, not integers, for all numeric values
             #'center_wavelength': 540.0, 
             #'grating': '[500nm,300][0][0]'
             }  
params = {"pump wavelength" : 1080, # (nm) 
          "power beamsplitter s-pol R,T" : [0, 0], # Use these to normalize the pump power label 
          "power beamsplitter p-pol R,T" : [0, 0]
          }

devices = {'lf' : None,
           'attenuator' : None,
           'hwp' : None, 
           'analyzer' : None, 
           'mirror' : None,
           'PM' : None
           }

# =============================================================================
# devices = setup(lf_params, devices) 
# N_points = int(input("How many points do you want to measure across k-space?\n")) # Number of points to move the mirror to and measure 
# input("Starting pixel_deg_callibration() next")
# degrees, k_values, pixels = pixel_deg_calibration(devices, N_points) 
# 
# # After calibration, let the user choose which measurement to perform (Reflection or SHG).
# measurement_options = ['Reflection', 'SHG']
# menu_text = "Choose which measurement to run next (type number or name):\n"
# for idx, m in enumerate(measurement_options, start=1):
#     menu_text += f"  {idx}) {m}\n"
# menu_text += f"  {len(measurement_options)+1}) finish\n"
# 
# while True:
#     choice = input(menu_text).strip()
#     if choice == str(len(measurement_options)+1) or choice.lower() in ['finish', 'f', 'q', 'quit', 'exit']:
#         print("No more measurements selected — proceeding to finish().")
#         break
# 
#     if choice.isdigit():
#         choice_idx = int(choice) - 1
#         if 0 <= choice_idx < len(measurement_options):
#             selection = measurement_options[choice_idx]
#         else:
#             print("Invalid numeric choice, try again.")
#             continue
#     else:
#         choice_norm = choice.lower().replace(' ', '')
#         matches = [m for m in measurement_options if m.lower() == choice_norm]
#         if len(matches) == 1:
#             selection = matches[0]
#         else:
#             print("Invalid choice, try again.")
#             continue
#     if selection == 'Reflection':
#         input("Starting reflection_experiment() next")
#         reflection_experiment(devices, degrees, k_values, pixels)
#     elif selection == 'SHG':
#         input("Starting SHG_experiment() next")
#         SHG_experiment(devices, degrees, k_values, pixels)
# 
# 
# input("Starting finish() next")
# finish(devices) 
# =============================================================================
