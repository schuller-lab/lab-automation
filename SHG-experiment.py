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
import inspect 

def setup():
    
    input('Make sure: \n(1) the hwp, analyzer, and mirror mount are disconnected in Kinesis \n' + 
          '(2) there is no LightField window open \n' +
          "(3) the power meter and mirror mount's KCube are on \n" + 'Then press [Enter]')    
    
    # Serial numbers of the various cage rotation mounts 
    rotation_serials = {'attenuator': '55537294', 
                       'hwp' : '55535784',
                       'analyzer' : '55536784'}
    
    # Launch an instance of lightfield 
    devices['lf'] = LightField(lf_params) 
    devices['lf'].connect() 
# =============================================================================
#     try: devices['lf'].get_center_wavelength() 
#     except: devices['lf'] = LightField(lf_params) 
# =============================================================================
    
    # Connect to the attenuator 
    devices['attenuator'] = K10CR2('attenuator', rotation_serials['attenuator'])
    devices['attenuator'].connect() 
        
    # Connect to the half-wave plate 
    devices['hwp'] = K10CR2('hwp', rotation_serials['hwp'])
    devices['hwp'].connect() 
        
    # Connect to the analyzing polarizer 
    devices['analyzer'] = K10CR2('analyzer', rotation_serials['analyzer'])
    devices['analyzer'].connect()   
        
    # Connect to the mirror rotation stage (number is KCube serial number) 
    devices['mirror'] = PRMTZ8('mirror', '27270898')
    devices['mirror'].connect()  
        
    # Connect to the power meter
    devices['PM'] = PM100D('USB0::4883::32888::P0007396::0::INSTR') 
    
    return  

def check_devices():
    # Calls a 'get' method on each device to check that they're connected 
    try: 
        devices['lf'].get_center_wavelength() 
        devices['attenuator'].get_position() 
        devices['analyzer'].get_position() 
        devices['hwp'].get_position() 
        devices['mirror'].get_position() 
        devices['PM'].identify()
        print("All devices are connected")
        return True 
    except Exception as e: 
        print(f"check_devices() failed with error: {e}")
        return False 

def reconnect_lf():
    """Reconnect to LightField after a crash — without touching Kinesis or PM devices.
    After this, re-apply your background correction in the GUI before continuing."""
    if devices['lf'] is None:
        print("LightField was never initialized. Run setup() instead.")
        return
    devices['lf'].reconnect()

def finish(): 
    
    # Check devices 
    if not check_devices():
        print("Aborting finish().")
        return 
    
    while True: 
        answer = input("Are you sure you want to disconnect all devices? (y or n)")
        if answer == 'y': 
            # Call this function when the experiment is done to close everything 
            devices['attenuator'].disconnect() 
            devices['hwp'].disconnect()
            devices['analyzer'].disconnect() 
            devices['mirror'].disconnect() 
            devices['PM'].disconnect() 
            devices['lf'].close() 
            return 
        if answer == 'n':
            print("Aborting finish()")
            break

    return 

def set_power_and_pol(power, pol):
    # Takes a desired power and polarization and sets the attenuator and hwp to achieve that (as closely as possible)
    
    # Power should be a string of the form "##.## mW", or "##.## %" (whitespace required) 
    try: 
        value, units = power.split() 
        value = float(value) 
    except Exception as e: 
        print('Error parsing desired power. Should be a string of the form "##.## mW" or "##.## %" (whitespace required, decimal optional).')
        print(f"Full error: {e}")
        return 0
    if not (units == 'mW' or units == '%'): 
        print('Input power should be a string of the form "##.## mW" or "##.## %" (whitespace required). Aborting set_power_and_pol().')
        return 0
    
    # pol should be 's' or 'p' (this can be expanded later)
    if not (pol == 's' or pol == 'p'):
        print('Input polarization should be "s" or "p". Aborting set_power_and_pol().')
        return 0 
    
    # Check devices 
    if not check_devices():
        print("Aborting set_power_and_pol().")
        return 
    
    # Set attenuator 
    if units == 'mW':
        print('I need to write this part still...')
        devices['PM'] 
    elif units == '%':
        devices['attenuator'].move_to(np.rad2deg(np.arcsin(np.sqrt(value/100))) + devices['attenuator'].vertical)  
    
    # Set hwp 
    attenuator_offset = devices['attenuator'].get_position() - devices['attenuator'].vertical 
    if pol == 's':
        devices['hwp'].move_to(attenuator_offset + (90 - attenuator_offset)/2 + devices['hwp'].vertical)
    elif pol == 'p': 
        devices['hwp'].move_to(attenuator_offset / 2 + devices['hwp'].vertical) 
    
    # Data for the following calculation comes from:
        # https://www.thorlabs.com/uv-fused-silica-broadband-plate-beamsplitters-coating-700---1100-nm?pn=BSN11&tabName=Overview
    # Note that s-(p-)pol in the beamsplitter reference frame is p-(s-)pol in the sample frame 
    # Currently, we assume a pump wavelength of 1080 nm 
    if params['pump wavelength'] != 1080: print('Warning: the power label output by set_power_and_pol() is currently only valid at 1080 nm')
    power_to_microscope = devices['PM'].read_power()*.940/.039 if pol == 's' else devices['PM'].read_power()*.815/.178 
    
    return f"{np.abs(power_to_microscope)*1e3:.2f}mW-{pol}pol" 

def pixel_deg_calibration(N_points:int):
    
    # Check devices 
    if not check_devices():
        print("Aborting finish().")
        return 
    
    # Callibrate the pixel/deg mapping 
    # Return an ordered array of degree values to move the mirror to 
    # N = the length of the returned array, i.e., the number of k0 points to measure at 
    NA = 1.3  
    
    try: 
        N_points = int(N_points) 
    except: 
        print("The number of points should be an integer. Aborting pixel_deg_calibration().")
        return 
    
    # Set polarization optics to s/s and mirror to 0
    set_power_and_pol('0 %', 's')
    devices['analyzer'].move_to(devices['analyzer'].vertical + 90) 
    devices['mirror'].move_to(0) 
    
    devices['lf'].set_center_wavelength(0)
    devices['lf'].set_exposure_time(10) 
    print("Make sure you've checked the bfp focus.")
    input("Focus the microscope on the top surface of your sample. Remove the slit and turn on the laser. \n" +
          "Position the input momentum at k = 0 (then at pixel 512), then press [Enter]")
    
    devices['lf'].set_exposure_time(100) 
    
    while True: 
        try: 
            k_pos1_pix = int(input("Shut the laser, place the diffuser film and turn on the lamp. \n" + 
                                   "Bring the bfp into focus, then enter the pixel location of k = +1 (top)\n> "))
            break
        except: 
            print("Invalid input. Try again.")
    while True: 
        try: 
            k_neg1_pix = int(input("Enter the pixel location of k = -1 (bottom)\n> ")) 
            break
        except: 
            print("Invalid input. Try again.")
            
    pixels_per_2NA = round(NA * np.abs(k_neg1_pix - k_pos1_pix)) 
    devices['PM'].set_wavelength(params['pump wavelength']) 
    devices['PM'].zero() 
    
    
    input("Remove the diffuser film and turn off the lamp.\n" + 
          "Replace the coverslip with an in-focus sample and position the slit. Then open the laser and press [Enter].")          
    devices['lf'].set_center_wavelength(params['pump wavelength'])
    devices['lf'].set_exposure_time(100) 
    #mirror_0 = devices['mirror'].get_position() 
    while True: 
        try: 
            k_0_pix = int(input('Please enter the pixel location of the incident momentum. (Use "One Look" in the GUI) \n> ')) 
            break
        except: 
            print("Invalid input. Try again.")
    devices['mirror'].move_relative(0.200) # I hope this isn't too much; lower the value if it is 
    while True: 
        try: 
            k_200mdeg_pix = int(input('Please enter the new pixel location of the incident momentum. (Use "One Look" in the GUI) \n> ')) 
            break
        except: 
            print("Invalid input. Try again.")
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
    degrees_to_measure = 0.200/pixels_per_200mdeg * (k_0_pix - pixels_to_measure)  
    reordered_degrees = reorder_with_spacing(degrees_to_measure, 0.040)#[::-1] 
    
    # Make an array of corresponding k values 
    reordered_k_values = (reordered_degrees[::-1]) * pixels_per_200mdeg / 0.200 / pixels_per_2NA * 2*NA
    
    # Move back to original position before ending the expeirment 
    devices['mirror'].move_to(0) 
    
    # Set global arrays of (1) degrees to take measurements at, (2) corresponding k values, and (3) corresponding pixels on the CCD
    global degrees, k_values, pixels 
    degrees = reordered_degrees
    k_values = reordered_k_values
    pixels = reordered_pixels
    return 

###############################################################################
# Reflection experiment (pump reflection)
def reflection_experiment(power, pol_in, pol_out, resume_from=0):
    """
    Measures reflected pump intensity across E(k)-space.
    resume_from: index into degrees[] to start from (use after a crash to skip 
                 already-acquired points). Defaults to 0 (full run).
    """
    # Check devices 
    if not check_devices():
        print("Not all devices connected. Aborting reflection_experiment().")
        return 
    
    # Vet pol_out (power and pol_in are verified in set_power_and_pol())
    if not (pol_out == 's' or pol_out == 'p'):
        print('Output polarization should be "s" or "p". Aborting reflection_experiment().')
        return 
    
    global degrees, k_values, pixels 
    if len(degrees) == 0:
        print("You need to run pixel/k/degree calibration first. Aborting reflection_experiment().")
        return 
    
    while True: 
        sample = input("What's the name of the sample you're measuring reflection from? (no spaces)\n> ")
        if " " not in sample: 
            break
        else: 
            print("Please don't use any whitespace. Use '-' or '_' instead. Try again.") 
        
    devices['lf'].set_center_wavelength(params['pump wavelength']) 
    input("Make sure the slit is in place. Then press [Enter] to continue.")
    #devices['lf'].set_exposure_time(10) 
    
    while True: 
        result = input("Have you already set the exposure time you want? (y or n) \n> ")
        if result == 'y': 
            break 
        if result == 'n': 
            print("Aborting reflection_experiment() so you can set the exposure time you want")
            return 
    
    devices['lf'].acquire_background() 
    
    date_folder = rf"C:\Users\schul\data\Wes\reflection-experiments\{date.today()}"
    
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
    
    directory = make_unique_dir(os.path.join(date_folder, sample + '_' + pol_in + pol_out + '_' + 'R')) 
    # Save degrees, k_values, and pixels for later reference 
    np.save(os.path.join(directory, 'degrees'), degrees)
    np.save(os.path.join(directory, 'k_values'), k_values)
    np.save(os.path.join(directory, 'pixels'), pixels) 
    
    # Set the polarization optics 
    power_pol = set_power_and_pol(power, pol_in)
    if pol_out == 's': 
        devices['analyzer'].move_to(devices['analyzer'].vertical + 90) 
    elif pol_out == 'p': 
        devices['analyzer'].move_to(devices['analyzer'].vertical) 
    # The case where pol_out is neither 's' nor 'p' is handled earlier in this function 
    
    for i in range(resume_from, len(degrees)): 
       # Move the mirror and save image as csv 
       print(f"Acquiring point {i+1}/{len(degrees)} (index {i})")
       devices['mirror'].move_to(degrees[i]) 
       filename = f"{params['pump wavelength']}nm-{power_pol}-ky={'-' if k_values[i] <0 else '+'}{np.abs(k_values[i]):.2f}_{sample}_{pol_out}pol-{(devices['lf'].get_exposure_time()):.0f}ms"
       filename = filename.replace('.', ',') # Because .csv files can't have '.' in the name
       devices['lf'].acquire_as_csv(filename, directory)
    
    devices['mirror'].move_to(0) 

    return 

###############################################################################
# SHG experiment 
def SHG_experiment(power, pol_in, pol_out, resume_from=0):
    """
    Measures SHG response across E(k)-space.
    resume_from: index into degrees[] to start from (use after a crash to skip 
                 already-acquired points). Defaults to 0 (full run).
    """
    # Check devices 
    if not check_devices():
        print("Not all devices connected. Aborting SHG_experiment().")
        return 
    
    # Vet pol_out (power and pol_in are verified in set_power_and_pol())
    if not (pol_out == 's' or pol_out == 'p'):
        print('Output polarization should be "s" or "p". Aborting SHG_experiment().')
        return
    
    global degrees, k_values, pixels 
    if len(degrees) == 0:
        print("You need to run pixel/k/degree calibration first. Aborting SHG_experiment().")
        return 
    
    while True: 
        sample = input("What's the name of the sample you're measuring reflection from? (no spaces)\n> ")
        if " " not in sample: 
            break
        else: 
            print("Please don't use any whitespace. Use '-' or '_' instead. Try again.") 
    
    devices['lf'].set_center_wavelength(params['pump wavelength']//2) 
    input("Make sure the slit is in place. Then press [Enter] to continue.")
    #devices['lf'].set_exposure_time(500) 
    
    while True: 
        result = input("Have you already set the exposure time you want? (y or n) \n> ")
        if result == 'y': 
            break 
        if result == 'n': 
            print("Aborting SHG_experiment() so you can set the exposure time you want")
            return 
    
    devices['lf'].acquire_background() 
    
    date_folder = rf"C:\Users\schul\data\Wes\GaN-SHG\{date.today()}"
    
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
    
    directory = make_unique_dir(os.path.join(date_folder, sample + '_' + pol_in + pol_out + '_' + 'SHG')) 
    # Save degrees, k_values, and pixels for later reference 
    np.save(os.path.join(directory, 'degrees'), degrees)
    np.save(os.path.join(directory, 'k_values'), k_values)
    np.save(os.path.join(directory, 'pixels'), pixels) 
    
    # Set the polarization optics 
    power_pol = set_power_and_pol(power, pol_in)
    if pol_out == 's': 
        devices['analyzer'].move_to(devices['analyzer'].vertical + 90) 
    elif pol_out == 'p': 
        devices['analyzer'].move_to(devices['analyzer'].vertical) 
    # The case where pol_out is neither 's' nor 'p' is handled earlier in this function
    
    for i in range(resume_from, len(degrees)): 
       # Move the mirror and save image as csv 
       print(f"Acquiring point {i+1}/{len(degrees)} (index {i})")
       devices['mirror'].move_to(degrees[i]) 
       filename = f"{params['pump wavelength']}nm-{power_pol}-ky={'-' if k_values[i] <0 else '+'}{np.abs(k_values[i]):.2f}_{sample}_{pol_out}pol-{(devices['lf'].get_exposure_time()):.0f}ms"
       filename = filename.replace('.', ',') # Because .csv files can't have '.' in the name
       devices['lf'].acquire_as_csv(filename, directory)
        
    devices['mirror'].move_to(0) 
    
    return 

# =============================================================================
# ###############################################################################
# # bfp experiment (pump reflection)
# def bfp_experiment(power, pol_in, pol_out):
#     """
#     Measures reflected or SHG intensity across the bfp for 
#     """
#     # Check devices 
#     if not check_devices():
#         print("Not all devices connected. Aborting bfp_experiment().")
#         return 
#     
#     # Vet pol_out (power and pol_in are verified in set_power_and_pol())
#     if not (pol_out == 's' or pol_out == 'p'):
#         print('Output polarization should be "s" or "p". Aborting bfp_experiment().')
#         return 
#     
#     global degrees, k_values, pixels 
#     if len(degrees) == 0:
#         print("You need to run pixel/k/degree calibration first. Aborting bfp_experiment().")
#         return 
#     
#     while True: 
#         sample = input("What's the name of the sample you're measuring reflection from? (no spaces)\n> ")
#         if " " not in sample: 
#             break
#         else: 
#             print("Please don't use any whitespace. Use '-' or '_' instead. Try again.") 
#         
#     devices['lf'].set_center_wavelength(0) 
#     input("Make sure the slit is removed. Then press [Enter] to continue.")
#     #devices['lf'].set_exposure_time(10) 
#     
#     while True: 
#         result = input("Have you already set the exposure time you want? (y or n) \n> ")
#         if result == 'y': 
#             break 
#         if result == 'n': 
#             print("Aborting bfp_experiment() so you can set the exposure time you want")
#             return 
#     
#     devices['lf'].acquire_background() 
#     
#     date_folder = rf"C:\Users\schul\data\Wes\bfp-experiments\{date.today()}"
#     
#     def make_unique_dir(base_path):
#         if not os.path.exists(base_path):
#             os.makedirs(base_path)
#             return base_path
#         counter = 1
#         while True:
#             new_path = f"{base_path}({counter})"
#             if not os.path.exists(new_path):
#                 os.makedirs(new_path)
#                 return new_path
#             counter += 1
#     
#     directory = make_unique_dir(os.path.join(date_folder, sample + '_' + pol_in + pol_out + '_' + 'bfp')) 
#     # Save degrees, k_values, and pixels for later reference 
#     np.save(os.path.join(directory, 'degrees'), degrees)
#     np.save(os.path.join(directory, 'k_values'), k_values)
#     np.save(os.path.join(directory, 'pixels'), pixels) 
#     
#     # Set the polarization optics 
#     power_pol = set_power_and_pol(power, pol_in)
#     if pol_out == 's': 
#         devices['analyzer'].move_to(devices['analyzer'].vertical + 90) 
#     elif pol_out == 'p': 
#         devices['analyzer'].move_to(devices['analyzer'].vertical) 
#     # The case where pol_out is neither 's' nor 'p' is handled earlier in this function 
#     
#     for i in range(len(degrees)): 
#        # Move the mirror and save image as csv 
#        devices['mirror'].move_to(degrees[i]) 
#        filename = f"{params['pump wavelength']}nm-{power_pol}-ky={'-' if k_values[i] <0 else '+'}{np.abs(k_values[i]):.2f}_{sample}_{pol_out}pol-{(devices['lf'].get_exposure_time()):.0f}ms"
#        filename = filename.replace('.', ',') # Because .csv files can't have '.' in the name
#        devices['lf'].acquire_as_csv(filename, directory)
#     
#     devices['mirror'].move_to(0) 
# 
#     return 
# =============================================================================

def switch_to_1080():
    devices['lf'].set_center_wavelength(1080)
    devices['lf'].set_exposure_time(10) 
    print("Ready to measure 1080 nm")
    return 

def switch_to_540():
    devices['lf'].set_center_wavelength(540)
    devices['lf'].set_exposure_time(1000) 
    print("Ready to measure 540 nm")
    return 

###############################################################################
# Now here's the menu functions 
###############################################################################
def main_menu():
    options = {'1' : setup, 
            '2' : check_devices, 
            '3' : lambda : pixel_deg_calibration(input("Enter the number of points to measure across the bfp: \n> ")), 
            '4' : lambda : set_power_and_pol(input("Enter power: \n> "), 
                                             input("Enter polarization: \n> ")),
            '5' : lambda : reflection_experiment(input("Enter the input power: \n> "), 
                                                                     input("Enter the input polarization: \n> "), 
                                                                     input("Enter the output polarization: \n> "),
                                                                     int(input("Resume from index (0 for full run): \n> ") or 0)), 
            '6' : lambda : SHG_experiment(input("Enter the input power: \n> "), 
                                                        input("Enter the input polarization: \n> "), 
                                                        input("Enter the output polarization: \n> "),
                                                        int(input("Resume from index (0 for full run): \n> ") or 0)), 
            '7' : devices_menu, 
            '8' : reconnect_lf,
            '9' : finish,
            }
    while True: 
        print('\nMain menu:')
        print("(1) setup \n" +
              "(2) check devices \n" +
              "(3) pixel/degree/k calibration \n" +
              "(4) set power and polarization \n" + 
              "(5) reflection experiment \n" +
              "(6) SHG experiment \n" +
              "(7) see individual devices \n" + 
              "(8) reconnect LightField (after crash) \n" +
              "(9) close all devices \n" + 
              "(q) exit program"
              )
        choice = input("> ")
        
        if choice == "q":
            break
    
        func = options.get(choice) 
        if func: 
            result = func() 
            if result: 
                print(result) 
        else: 
            print("Invalid option") 
    return 

def devices_menu():
    options = {} 
    
    while True: 
        print('\nDevices menu:')
        device_count = 1
        for key in devices: 
            print(f'({str(device_count)}) {key}') 
            options[str(device_count)] = devices[key] 
            device_count += 1 
        print('(q) Back to main menu')
        
        choice = input('> ') 
        
        if choice == 'q':
            break 
        
        device_choice = options.get(choice) 
        
        if device_choice: 
            # Enter a sub-menu to call various methods of the chosen device 
            methods_menu(device_choice) 
        else:
            print('invalid option')

def methods_menu(device_choice):
    options = {} 
    
    def convert_with_retry(raw, annotation):
        while True:
            try:
                if annotation == int:
                    return int(raw)
                elif annotation == float:
                    return float(raw)
                elif annotation == bool:
                    if raw.lower() in ("true", "1", "yes", "y"):
                        return True
                    elif raw.lower() in ("false", "0", "no", "n"):
                        return False
                    else:
                        raise ValueError("Invalid boolean")
                else:
                    return raw  # string or no type
            except ValueError:
                print("Invalid input. Please try again.")
                raw = input("> ")
    
    while True: 
        print(f'\n{device_choice.name} methods menu:')
        method_count = 1
        for method_name in dir(device_choice): 
            method = getattr(device_choice, method_name)
            if (callable(method) and not method_name.startswith('_')):
                print(f'({method_count}) {method_name}') 
                options[str(method_count)] = method 
                method_count += 1 
        print('(q) Back to devices menu')
        
        choice = input('> ') 
        
        if choice == 'q':
            break 
        
        method_choice = options.get(choice) 
        
        if method_choice: 
            sig = inspect.signature(method_choice)
            args = []
            for name, param in sig.parameters.items():
                if name == "self":
                    continue
                raw = input(f"Enter {name}: \n> ")
                value = convert_with_retry(raw, param.annotation)
                args.append(value)
            
            result = method_choice(*args)
            if result:
                print(result) 
                

        else: 
            print("invalid option")
        
    return 

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

if not ('devices' in globals() or 'devices' in locals()):
    devices = {'lf' : None,
               'attenuator' : None,
               'hwp' : None, 
               'analyzer' : None, 
               'mirror' : None,
               'PM' : None
               }

degrees = []
k_values = []
pixels = []