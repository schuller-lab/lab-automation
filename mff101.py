# -*- coding: utf-8 -*-
"""
Thorlabs MFF101 motorized filter flipper, used to move the power meter in and
out of the pump beam path.

Position 1 = power meter OUT of the beam (pump reaches the sample)
Position 2 = power meter IN the beam (pump is blocked by the meter)

Follows the conventions of KinesisControls.py (pythonnet + Kinesis DLLs).
"""

import clr
import time
import sys

# === Load Thorlabs DLLs ===
KINESIS_PATH = r"C:\Program Files\Thorlabs\Kinesis"
sys.path.append(KINESIS_PATH)

clr.AddReference(KINESIS_PATH + r"\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference(KINESIS_PATH + r"\Thorlabs.MotionControl.FilterFlipperCLI.dll")

from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
from Thorlabs.MotionControl.FilterFlipperCLI import FilterFlipper


class MFF101:
    """
    Automation wrapper for a Thorlabs MFF101 flip mount carrying the power meter.
    """

    POS_OUT = 1  # power meter out of the beam
    POS_IN = 2   # power meter in the beam

    def __init__(self, name, serial_number, polling_interval=250, timeout=10000):
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
            self.device = FilterFlipper.CreateFilterFlipper(self.serial)
            if self.device is None:
                raise RuntimeError("Could not create device instance.")
            self.device.Connect(self.serial)  # Fails if the device is open in the Kinesis GUI
        except Exception as e:
            print(f"Failed to connect to {self.name}: {e}")
            return None

        if not self.device.IsSettingsInitialized():
            self.device.WaitForSettingsInitialized(10000)

        self.device.StartPolling(self.polling_interval)
        time.sleep(0.5)

        self.device.EnableDevice()
        time.sleep(0.5)

        self._connected = True
        print(f"MFF101 {self.serial} ({self.name}) connected.")

    def disconnect(self):
        if self.device is not None:
            self.device.StopPolling()
            self.device.Disconnect()
            self._connected = False
            print(f"MFF101 {self.serial} ({self.name}) disconnected.")

    # -------------------------
    # Motion Commands
    # -------------------------

    def flip_in(self):
        """Put the power meter in the beam (position 2)."""
        self._move_to(self.POS_IN)

    def flip_out(self):
        """Take the power meter out of the beam (position 1)."""
        self._move_to(self.POS_OUT)

    def _move_to(self, position:int):
        self._ensure_connected()
        if self.get_position() != position:
            self.device.SetPosition(position, self.timeout)
            time.sleep(0.2)
        if self.get_position() != position:
            raise RuntimeError(f"{self.name} failed to reach position {position}.")

    # -------------------------
    # Status
    # -------------------------

    def get_position(self) -> int:
        self._ensure_connected()
        return int(self.device.Position)

    def is_in_beam(self) -> bool:
        return self.get_position() == self.POS_IN

    def is_connected(self) -> bool:
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
