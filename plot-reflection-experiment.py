#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 12:30:15 2026

@author: wkmills
"""
import matplotlib.pyplot as plt 
import numpy as np 
import csv 
from pathlib import Path 

def max_counts_vs_k(k_values, pol): 
    # Opens up csv files to grab the max value and returns a corresponding array 
    max_counts = [] 
    for k in k_values: 
        '0mW-spol-ky=+0.01_glass_spol-10ms.csv'
        #filename = 
        #data = np.genfromtxt(filename, delimiter=',', skip_header=1)
        #max_counts.append(data.max()) 
        print(1) 
    return 

def extract_max_counts(directory, pol):
    # Loops through csv files in the provided folder and of the provided polarization 
    # extracts the pump power, pump k, and max counts into a dict of arrays
    
    directory = Path(directory) 
    csv_files = [f.name for f in directory.glob(f"*{pol[0]}pol*{pol[-1]}pol*.csv")] 
    
    results = {'pump power' : np.zeros(len(csv_files)), 
               'pump ky': np.zeros(len(csv_files)),
               'max counts' : np.zeros(len(csv_files))
               }
    
    for i in range(len(csv_files)): 
        filename = csv_files[i] 
        results['pump power'][i] = float(filename.split('W')[0][:-1]) 
        results['pump ky'][i] = float(filename.split('ky=')[1][0:5])
        data = np.genfromtxt(filename, delimiter=',', skip_header=1)[:,1:]
        results['max counts'][i] = data.max() 
        
    
    return results 


directory = r'/home/wkmills/Dropbox/research/measurements/SHG-from-GaN/2026-03-02'

# =============================================================================
# ss_data = extract_max_counts(directory, 's/s')
# pp_data = extract_max_counts(directory, 'p/p')
# =============================================================================

# normalize 
denominator = max(max(ss_data['max counts']), max(pp_data['max counts']))
ss_data['max counts'] /= denominator 
pp_data['max counts'] /= denominator 

plt.scatter(ss_data['pump ky'], ss_data['max counts'], label='s-pol')
plt.scatter(pp_data['pump ky'], pp_data['max counts'], label='p-pol')
plt.legend() 

plt.xlabel('$k_y/k_0$')
plt.ylabel('Counts (normalized)')

plt.show() 

