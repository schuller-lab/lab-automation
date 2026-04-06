# -*- coding: utf-8 -*-
"""
Created on Fri Feb 20 14:58:18 2026

@author: Wesley Mills and ChatGPT 

Source: https://github.com/Thorlabs/Motion_Control_Examples/tree/main/Python/Kinesis/Integrated%20Stages/Cage%20Rotator
"""

import clr
import time
import sys
from System import Decimal

# === Load Thorlabs DLLs ===
KINESIS_PATH = r"C:\Program Files\Thorlabs\Kinesis"
sys.path.append(KINESIS_PATH)

clr.AddReference(KINESIS_PATH + r"\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference(KINESIS_PATH + r"\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference(KINESIS_PATH + r"\Thorlabs.MotionControl.IntegratedStepperMotorsCLI.dll")
clr.AddReference(KINESIS_PATH + r"\Thorlabs.MotionControl.KCube.DCServoCLI.dll")

from Thorlabs.MotionControl.DeviceManagerCLI import (DeviceManagerCLI, DeviceConfiguration) 
from Thorlabs.MotionControl.GenericMotorCLI import MotorDirection
from Thorlabs.MotionControl.IntegratedStepperMotorsCLI import CageRotator
from Thorlabs.MotionControl.KCube.DCServoCLI import KCubeDCServo


class K10CR2:
    """
    Automation wrapper for Thorlabs K10CR2 Cage Rotator
    """

    def __init__(self, name, serial_number, polling_interval=250, timeout=60000):
        self.serial = str(serial_number)
        self.polling_interval = polling_interval
        self.device = None
        self._connected = False
        self.name = name 
        self.timeout = timeout 
        
    # -------------------------
    # Connection Handling
    # -------------------------

    def connect(self):
        print("Connecting...")
        DeviceManagerCLI.BuildDeviceList()
        
        try: 
            self.device = CageRotator.CreateCageRotator(self.serial)
            self.device.Connect(self.serial) # If the device is connected in Kinesis GUI, connect() will fail here with DeviceNotReadyException 
        except Exception as e: 
            print(f"Failed to connect to {self.name}: {e}")
            return None 
        
        if not self.device.IsSettingsInitialized():
            self.device.WaitForSettingsInitialized(10000)

        self.device.StartPolling(self.polling_interval)
        time.sleep(0.5)

        self.device.EnableDevice()
        time.sleep(1)

        self.device.LoadMotorConfiguration(
            self.serial,
            DeviceConfiguration.DeviceSettingsUseOptionType.UseDeviceSettings
        )

        self._connected = True
        print(f"K10CR2 {self.serial} ({self.name}) connected.")
        
        while True: 
            try: 
                self.vertical = float(input(f"What degree setting on {self.name} corresponds to a vertical axis (fast, transmission, etc.)\n> ")) 
                break 
            except: 
                print("Invalid . Try again.") 
        self.home() 
        self.move_to(self.vertical) 

    def disconnect(self):
        if self.device is not None:
            self.device.StopPolling()
            self.device.Disconnect()
            self._connected = False
            print(f"K10CR2 {self.serial} ({self.name}) disconnected.")

    # -------------------------
    # Motion Commands
    # -------------------------

    def home(self, ):
        self._ensure_connected()
        print("Homing...")
        self.device.Home(self.timeout)
        print("Home complete.")

    def move_to(self, angle_deg:float):
        if (angle_deg >= 0) & (angle_deg <= 360):
            self._ensure_connected()
            print(f"Moving {self.name} to {angle_deg} degrees...")
            self.device.MoveTo(Decimal(angle_deg), self.timeout)
            print("Move complete.")
        elif (angle_deg < 0) & (angle_deg >= -360):
            self._ensure_connected()
            print(f"Moving {self.name} to {angle_deg} degrees...")
            angle_deg += 360 
            self.device.MoveTo(Decimal(angle_deg), self.timeout)
            print("Move complete.")
        else: 
            print("Please enter an angle value betwen -360 and +360, inclusive.")

    def move_relative(self, delta_deg:float):
        self._ensure_connected()
        print(f"Moving {self.name} relative {delta_deg} degrees...")
        self.device.MoveRelative(MotorDirection.Forward, Decimal(delta_deg), self.timeout)
        print("Move complete.")

    def move_continuous(self, direction="forward"):
        self._ensure_connected()
        dir_enum = MotorDirection.Forward if direction.lower() == "forward" else MotorDirection.Backward
        self.device.MoveContinuous(dir_enum)

    def stop(self):
        self._ensure_connected()
        self.device.StopImmediate()

    # -------------------------
    # Status
    # -------------------------

    def get_position(self):
        self._ensure_connected()
        return float(str(self.device.Position)) 

    def is_connected(self):
        return self._connected

    # -------------------------
    # Internal Safety
    # -------------------------

    def _ensure_connected(self):
        if not self._connected:
            raise RuntimeError(f"{self.name} not connected. Call connect() first.")

    # -------------------------
    # Context Manager Support
    # -------------------------

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

class PRMTZ8:
    """
    Automation wrapper for Thorlabs PRMTZ8 Rotation Stage 
    """
    
    def __init__(self, name, serial_number, timeout=60000):
        self.serial = str(serial_number) 
        self.device = None
        self._connected = False 
        self.name = name 
        self.timeout = timeout 
    # -------------------------
    # Connection Handling
    # -------------------------
    
    def connect(self):
        DeviceManagerCLI.BuildDeviceList()
        
        try: 
            self.device = KCubeDCServo.CreateKCubeDCServo(self.serial)
            if self.device is None:
                raise RuntimeError("Could not create device instance.")
            print("Connecting...")
            self.device.Connect(self.serial)
        except Exception as e: 
            print(f"Failed to connect to {self.name}: {e}")
            return None 
        
        if not self.device.IsSettingsInitialized():
            self.device.WaitForSettingsInitialized(10000)

        self.device.StartPolling(250)
        time.sleep(0.5)

        self.device.EnableDevice()
        time.sleep(0.5)
        
        self.device.LoadMotorConfiguration(
            self.serial,
            DeviceConfiguration.DeviceSettingsUseOptionType.UseDeviceSettings
        )
        
        self._connected = True 
        print(f"PRMTZ8 {self.serial} connected.")
        self.home() 
        self.move_to(0) 

    def disconnect(self):
        if self.device is not None: 
            self.device.StopPolling()
            self.device.Disconnect()
            self._connected = False 
            print(f"PRMTZ8 {self.serial} disconnected.")
            
    # -------------------------
    # Motion Commands
    # -------------------------
    
    def home(self):
        self._ensure_connected() 
        print("Homing...")
        self.device.Home(self.timeout)
        print("Home complete") 

    def move_to(self, angle_deg:float):
        if (angle_deg >= 0) & (angle_deg <= 360):
            self._ensure_connected()
            print(f"Moving {self.name} to {angle_deg:0.3f} degrees...")
            self.device.MoveTo(Decimal(angle_deg), self.timeout)
            print("Move complete.")
        elif (angle_deg < 0) & (angle_deg >= -360):
            self._ensure_connected()
            print(f"Moving {self.name} to {angle_deg:0.3f} degrees...")
            angle_deg += 360 
            self.device.MoveTo(Decimal(angle_deg), self.timeout)
            print("Move complete.")
        else: 
            print("Please enter an angle value betwen -360 and +360, inclusive.")

    def move_relative(self, delta_deg:float):
        self._ensure_connected()
        print(f"Moving {self.name} relative {delta_deg:0.3f} degrees...") 
        self.device.MoveRelative(MotorDirection.Forward, Decimal(delta_deg), self.timeout)
        print("Move complete.")
    
    def move_continuous(self, direction="forward"):
        self._ensure_connected()
        dir_enum = MotorDirection.Forward if direction.lower() == "forward" else MotorDirection.Backward
        self.device.MoveContinuous(dir_enum)
        
    def stop(self):
        self.device.StopImmediate()
        
    # -------------------------
    # Status
    # -------------------------
    
    def get_position(self):
        self._ensure_connected()
        return float(str(self.device.Position)) 
    
    def is_connected(self):
        return self._connected
    
    # -------------------------
    # Internal Safety
    # -------------------------

    def _ensure_connected(self):
        if not self._connected:
            raise RuntimeError(f"{self.name} not connected. Call connect() first.")
    
    # -------------------------
    # Context Manager Support
    # -------------------------

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
    