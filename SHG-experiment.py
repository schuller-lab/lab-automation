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
from LaserControls import ChameleonLaser

from Thorlabs.MotionControl.DeviceManagerCLI import DeviceNotReadyException # for error handling 
###############################################################################

import numpy as np
from datetime import date
import os # For mkdir, path.join, etc.
from pathlib import Path
import inspect
import time

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

    # Connect to the tunable pump laser
    devices['laser'] = ChameleonLaser('laser')
    devices['laser'].connect()

    # Ask for pump wavelength
    set_pump_wavelength()
    
    return  

def set_pump_wavelength():
    while True:
        try:
            wavelength = float(input("What is the pump wavelength? (in nm) \n>"))
            break
        except ValueError:
            print("Only enter numbers please.")
    devices['laser'].set_wavelength(wavelength)
    params["pump wavelength"] = wavelength
    print(f"Pump wavelength set to {params['pump wavelength']} nm and laser driven to match.")
        
def check_devices():
    # Calls a 'get' method on each device to check that they're connected 
    try: 
        devices['lf'].get_center_wavelength() 
        devices['attenuator'].get_position() 
        devices['analyzer'].get_position() 
        devices['hwp'].get_position() 
        devices['mirror'].get_position()
        devices['PM'].identify()
        devices['laser'].get_wavelength()
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
            devices['laser'].disconnect()
            devices['lf'].close()
            return 
        if answer == 'n':
            print("Aborting finish()")
            break

    return 

def _set_hwp_for_pol(pol):
    # Set hwp to maintain the desired output polarization, given the attenuator's current position
    attenuator_offset = devices['attenuator'].get_position() - devices['attenuator'].vertical
    if pol == 's':
        devices['hwp'].move_to((90 + attenuator_offset) / 2 + devices['hwp'].vertical)
    elif pol == 'p':
        devices['hwp'].move_to((00 + attenuator_offset) / 2 + devices['hwp'].vertical)
    elif pol == '45':
        devices['hwp'].move_to((45 + attenuator_offset) / 2 + devices['hwp'].vertical)

def _measure_corrected_power_mw(pol):
    # Beamsplitter-corrected estimate of power delivered to the microscope (mW)
    ratio = .940/.039 if pol == 's' else .815/.178
    return devices['PM'].read_power() * ratio * 1e3

def _converge_power(target_mw, pol, tolerance_mw=0.1, angle_min=None, angle_max=None,
                     max_iter=50, settle_s=2.0):
    """
    Bisection search over the attenuator angle (hwp follows via _set_hwp_for_pol()
    to preserve polarization) until the beamsplitter-corrected power estimate at
    the microscope reaches target_mw, +/- tolerance_mw. angle_min/angle_max default
    to the attenuator's full 0-100% Malus's-law range (vertical to vertical+90),
    matching the '%' branch's own convention.
    Returns (final_angle_deg, final_power_mw).
    Raises ValueError if target_mw is outside the achievable range in
    [angle_min, angle_max], or RuntimeError if it doesn't converge within max_iter.
    """
    if params['pump wavelength'] != 1080:
        print('Warning: power convergence is currently only valid at 1080 nm')

    if angle_min is None:
        angle_min = devices['attenuator'].vertical
    if angle_max is None:
        angle_max = devices['attenuator'].vertical + 90

    def measure_at(angle):
        devices['attenuator'].move_to(angle)
        _set_hwp_for_pol(pol)
        time.sleep(settle_s)
        return _measure_corrected_power_mw(pol)

    p_now = _measure_corrected_power_mw(pol)
    if abs(p_now - target_mw) <= tolerance_mw:
        return devices['attenuator'].get_position(), p_now

    p_at_min = measure_at(angle_min)
    if abs(p_at_min - target_mw) <= tolerance_mw:
        return angle_min, p_at_min

    p_at_max = measure_at(angle_max)
    if abs(p_at_max - target_mw) <= tolerance_mw:
        return angle_max, p_at_max

    p_lo, p_hi = min(p_at_min, p_at_max), max(p_at_min, p_at_max)
    if target_mw < p_lo - tolerance_mw or target_mw > p_hi + tolerance_mw:
        raise ValueError(
            f"Target {target_mw:.3f} mW is outside the achievable power range "
            f"[{p_lo:.3f}, {p_hi:.3f}] mW for attenuator angles "
            f"[{angle_min:.2f}, {angle_max:.2f}] deg."
        )

    a, b = (angle_min, angle_max) if p_at_min <= p_at_max else (angle_max, angle_min)

    mid, p_mid = (a + b) / 2.0, None
    for i in range(max_iter):
        mid = (a + b) / 2.0
        p_mid = measure_at(mid)
        print(f"  iter {i+1}: attenuator = {mid:.4f} deg, power = {p_mid:.3f} mW (target {target_mw:.3f} mW)")
        if abs(p_mid - target_mw) <= tolerance_mw:
            return mid, p_mid
        if p_mid < target_mw:
            a = mid
        else:
            b = mid

    raise RuntimeError(
        f"Power convergence did not converge after {max_iter} iterations. "
        f"Last attenuator angle: {mid:.4f} deg, last power: {p_mid:.3f} mW, target: {target_mw:.3f} mW."
    )

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

    # pol should be 's', 'p', or '45' (this can be expanded later)
    if not (pol == 's' or pol == 'p' or pol=='45'):
        print('Input polarization should be "s", "p", or "45". Aborting set_power_and_pol().')
        return 0

    # Check devices
    if not check_devices():
        print("Aborting set_power_and_pol().")
        return

    # Set attenuator
    if units == 'mW':
        try:
            _converge_power(value, pol)
        except (ValueError, RuntimeError) as e:
            print(f"Power convergence failed: {e}")
            return 0
    elif units == '%':
        devices['attenuator'].move_to(np.rad2deg(np.arcsin(np.sqrt(value/100))) + devices['attenuator'].vertical)

    # Set hwp
    _set_hwp_for_pol(pol)

    # Data for the following calculation comes from:
        # https://www.thorlabs.com/uv-fused-silica-broadband-plate-beamsplitters-coating-700---1100-nm?pn=BSN11&tabName=Overview
    # Note that s-(p-)pol in the beamsplitter reference frame is p-(s-)pol in the sample frame 
    # Currently, we assume a pump wavelength of 1080 nm 
    if params['pump wavelength'] != 1080: print('Warning: the power label output by set_power_and_pol() is currently only valid at 1080 nm')
    power_to_microscope_mw = _measure_corrected_power_mw(pol)

    return f"{np.abs(power_to_microscope_mw):.2f}mW-{pol}pol"

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
# Reflection / SHG / TPPL-k / TPPL-lambda experiments
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

EXPERIMENT_TYPES = {
    'reflection':   {'folder': 'automated-reflection',   'suffix': 'R',
                     'warning': "Have you removed the 650SP filter and placed the ND filter?"},
    'SHG':          {'folder': 'automated-SHG',          'suffix': 'SHG',
                     'warning': "Have you removed the ND filter and placed the 650SP filter?"},
    'TPPL-k':       {'folder': 'automated-TPPL-k',       'suffix': 'TPPL-k',
                     'warning': "Have you removed the 650SP filter and placed the ND filter?"},
    'TPPL-lambda':  {'folder': 'automated-TPPL-lambda',  'suffix': 'TPPL-lambda',
                     'warning': "Have you aligned the laser and set the mirror where you want it?"},
}

POWER_CHECK_INTERVAL = 10       # re-check power every N acquisition loops (run_experiment() only)
POWER_DRIFT_TOLERANCE_MW = 0.1  # same default as _converge_power()'s own tolerance

def _check_and_correct_power(pol, expected_mw, tolerance_mw=POWER_DRIFT_TOLERANCE_MW):
    # Re-measure power and re-converge if it has drifted from expected_mw (laser power
    # drifts slowly over time; this catches that during a long mirror sweep, where
    # wavelength is constant so any change really is drift, not expected physics).
    current_mw = _measure_corrected_power_mw(pol)
    print(f"Power check: {current_mw:.3f} mW (expected {expected_mw:.3f} mW)")
    if abs(current_mw - expected_mw) > tolerance_mw:
        print(f"Power drifted by {current_mw - expected_mw:+.3f} mW. Re-adjusting...")
        try:
            _converge_power(expected_mw, pol, tolerance_mw=tolerance_mw)
        except (ValueError, RuntimeError) as e:
            print(f"Power re-adjustment failed: {e}. Continuing with current power.")

def _prepare_experiment(experiment_type, config, power, pol_in, pol_out, require_calibration):
    """
    Shared setup for all experiment types: filter-check warning, device check,
    pol_out validation, optional pixel/k calibration check, sample name prompt,
    slit/exposure confirmation, background acquisition, output directory, and
    polarization optics. Returns (sample, directory, power_pol, initial_power_mw),
    or None if the run should be aborted.
    """
    # Confirm the correct filter is in place before proceeding
    input(f"{config['warning']} Press [Enter] to continue.")

    # Check devices
    if not check_devices():
        print("Not all devices connected. Aborting run.")
        return None

    # Vet pol_out (power and pol_in are verified in set_power_and_pol())
    if not (pol_out == 's' or pol_out == 'p'):
        print('Output polarization should be "s" or "p". Aborting run.')
        return None

    if require_calibration and len(degrees) == 0:
        print("You need to run pixel/k/degree calibration first. Aborting run.")
        return None

    while True:
        sample = input(f"What's the name of the sample you're measuring {experiment_type} from? (no spaces)\n> ")
        if " " not in sample:
            break
        else:
            print("Please don't use any whitespace. Use '-' or '_' instead. Try again.")

    input("Make sure the slit & center wavelength are set as you want them. Then press [Enter] to continue.")

    while True:
        result = input("Have you already set the exposure time you want? (y or n) \n> ")
        if result == 'y':
            break
        if result == 'n':
            print("Aborting so you can set the exposure time you want")
            return None

    devices['lf'].acquire_background()

    date_folder = rf"C:\Users\schul\data\Wes\{config['folder']}\{date.today()}"
    directory = make_unique_dir(os.path.join(date_folder, sample + '_' + pol_in + pol_out + '_' + config['suffix']))

    # Set the polarization optics
    power_pol = set_power_and_pol(power, pol_in)
    if pol_out == 's':
        devices['analyzer'].move_to(devices['analyzer'].vertical + 90)
    elif pol_out == 'p':
        devices['analyzer'].move_to(devices['analyzer'].vertical)
    # The case where pol_out is neither 's' nor 'p' is handled earlier in this function

    initial_power_mw = _measure_corrected_power_mw(pol_in)

    return sample, directory, power_pol, initial_power_mw

def run_experiment(experiment_type, power, pol_in, pol_out, resume_from=0):
    """
    Measures reflected pump, SHG, or TPPL-k intensity across E(k)-space by
    sweeping the mirror through calibrated positions.
    experiment_type: 'reflection', 'SHG', or 'TPPL-k'
    resume_from: index into degrees[] to start from (use after a crash to skip
                 already-acquired points). Defaults to 0 (full run).
    """
    if experiment_type not in EXPERIMENT_TYPES:
        print(f"experiment_type should be one of {list(EXPERIMENT_TYPES)}. Aborting run_experiment().")
        return
    config = EXPERIMENT_TYPES[experiment_type]

    global degrees, k_values, pixels

    setup = _prepare_experiment(experiment_type, config, power, pol_in, pol_out, require_calibration=True)
    if setup is None:
        return
    sample, directory, power_pol, initial_power_mw = setup

    # Save degrees, k_values, and pixels for later reference
    np.save(os.path.join(directory, 'degrees'), degrees)
    np.save(os.path.join(directory, 'k_values'), k_values)
    np.save(os.path.join(directory, 'pixels'), pixels)

    for loop_count, i in enumerate(range(resume_from, len(degrees)), start=1):
       if loop_count % POWER_CHECK_INTERVAL == 0:
           _check_and_correct_power(pol_in, initial_power_mw)

       # Move the mirror and save image as csv
       print(f"Acquiring point {i+1}/{len(degrees)} (index {i})")
       devices['mirror'].move_to(degrees[i])
       filename = f"{params['pump wavelength']}nm-{power_pol}-ky={'-' if k_values[i] <0 else '+'}{np.abs(k_values[i]):.2f}_{sample}_{pol_out}pol-{(devices['lf'].get_exposure_time()):.0f}ms"
       filename = filename.replace('.', ',') # Because .csv files can't have '.' in the name
       devices['lf'].acquire_as_csv(filename, directory)

    devices['mirror'].move_to(0)

    return

def run_wavelength_experiment(power, pol_in, pol_out, wl_start, wl_stop, wl_step, resume_from=0):
    """
    Measures TPPL-lambda intensity while sweeping the pump laser wavelength, at
    whatever mirror position is currently set (the mirror is never moved).
    wl_start/wl_stop/wl_step: wavelength sweep range in nm; wl_stop is inclusive.
    resume_from: index into the wavelength list to start from (use after a crash
                 to skip already-acquired points). Defaults to 0 (full run).
    """
    experiment_type = 'TPPL-lambda'
    config = EXPERIMENT_TYPES[experiment_type]

    setup = _prepare_experiment(experiment_type, config, power, pol_in, pol_out, require_calibration=False)
    if setup is None:
        return
    sample, directory, _, _ = setup  # power_pol/initial_power_mw unused: measured fresh per point below

    wavelengths = []
    wl = wl_start
    while (wl >= wl_stop if wl_step < 0 else wl <= wl_stop):
        wavelengths.append(wl)
        wl += wl_step

    if not wavelengths:
        print("No wavelengths in range. Check start/stop/step values. Aborting run_wavelength_experiment().")
        return

    # Save the swept wavelengths for later reference
    np.save(os.path.join(directory, 'wavelengths'), wavelengths)

    original_wavelength = params['pump wavelength']

    for i in range(resume_from, len(wavelengths)):
       wl = wavelengths[i]
       print(f"Acquiring point {i+1}/{len(wavelengths)} (index {i}): {wl} nm")
       devices['laser'].set_wavelength(wl)
       params['pump wavelength'] = wl
       current_power_mw = _measure_corrected_power_mw(pol_in)
       power_pol = f"{current_power_mw:.2f}mW-{pol_in}pol"
       filename = f"{params['pump wavelength']}nm-{power_pol}-wl={wl:.2f}_{sample}_{pol_out}pol-{(devices['lf'].get_exposure_time()):.0f}ms"
       filename = filename.replace('.', ',') # Because .csv files can't have '.' in the name
       devices['lf'].acquire_as_csv(filename, directory)

    print(f"Restoring pump wavelength to {original_wavelength} nm...")
    devices['laser'].set_wavelength(original_wavelength)
    params['pump wavelength'] = original_wavelength

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
            '5' : experiments_menu,
            '6' : devices_menu,
            '7' : reconnect_lf,
            '8' : set_pump_wavelength,
            '9' : finish,
            }
    while True:
        print('\nMain menu:')
        print("(1) setup \n" +
              "(2) check devices \n" +
              "(3) pixel/degree/k calibration \n" +
              "(4) set power and polarization \n" +
              "(5) experiments \n" +
              "(6) see individual devices \n" +
              "(7) reconnect LightField (after crash) \n" +
              "(8) set pump wavelength \n" +
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

def experiments_menu():
    options = {'1' : lambda : run_experiment('reflection',
                                              input("Enter the input power: \n> "),
                                              input("Enter the input polarization: \n> "),
                                              input("Enter the output polarization: \n> "),
                                              int(input("Resume from index (0 for full run): \n> ") or 0)),
               '2' : lambda : run_experiment('SHG',
                                              input("Enter the input power: \n> "),
                                              input("Enter the input polarization: \n> "),
                                              input("Enter the output polarization: \n> "),
                                              int(input("Resume from index (0 for full run): \n> ") or 0)),
               '3' : lambda : run_experiment('TPPL-k',
                                              input("Enter the input power: \n> "),
                                              input("Enter the input polarization: \n> "),
                                              input("Enter the output polarization: \n> "),
                                              int(input("Resume from index (0 for full run): \n> ") or 0)),
               '4' : lambda : run_wavelength_experiment(input("Enter the input power: \n> "),
                                                         input("Enter the input polarization: \n> "),
                                                         input("Enter the output polarization: \n> "),
                                                         float(input("Start wavelength (nm): \n> ")),
                                                         float(input("Stop wavelength (nm, inclusive): \n> ")),
                                                         float(input("Step size (nm, negative to sweep down): \n> ")),
                                                         int(input("Resume from index (0 for full run): \n> ") or 0)),
               }
    while True:
        print('\nExperiments menu:')
        print("(1) reflection experiment \n" +
              "(2) SHG experiment \n" +
              "(3) TPPL-k experiment \n" +
              "(4) TPPL-lambda experiment \n" +
              "(q) Back to main menu"
              )
        choice = input('> ')

        if choice == 'q':
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
               'PM' : None,
               'laser' : None
               }

degrees = []
k_values = []
pixels = []