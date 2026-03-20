# -*- coding: utf-8 -*-
"""
Created on Fri Feb 20 14:58:18 2026

@author: Wesley Mills and ChatGPT 
"""

import pyvisa
import time


class PM100D:
    """
    Python interface for Thorlabs PM100D Power Meter using PyVISA.
    """

    def __init__(self, resource_name=None, timeout=5000):
        """
        Initialize connection to PM100D.

        :param resource_name: VISA resource string (if None, auto-detect)
        :param timeout: communication timeout in ms
        """
        try: 
            self.rm = pyvisa.ResourceManager()
            self.resource_name = resource_name or self._find_instrument()
            self.instrument = self.rm.open_resource(self.resource_name)
            self.instrument.timeout = timeout
        except Exception as e: 
            print(f"Failed to connect: {e}")
            return 
        
        # Use newline termination (PM100D standard)
        self.instrument.write_termination = '\n'
        self.instrument.read_termination = '\n'
        self.name = "power meter"

    def _find_instrument(self):
        """Auto-detect connected PM100D device."""
        resources = self.rm.list_resources()
        for resource in resources:
            if "USB" in resource:
                inst = self.rm.open_resource(resource)
                try:
                    idn = inst.query("*IDN?")
                    if "Thorlabs" in idn and "PM100D" in idn:
                        inst.close()
                        return resource
                except Exception:
                    pass
                inst.close()
        raise RuntimeError("PM100D not found.")

    def identify(self):
        """Return instrument identification string."""
        return self.instrument.query("*IDN?")

    def reset(self):
        """Reset instrument."""
        self.instrument.write("*RST")

    def set_wavelength(self, wavelength_nm:int):
        """Set measurement wavelength (nm)."""
        self.instrument.write(f"SENS:CORR:WAV {wavelength_nm}")

    def get_wavelength(self):
        """Get current wavelength setting."""
        return float(self.instrument.query("SENS:CORR:WAV?"))

    def set_averaging(self, count):
        """Set averaging count."""
        self.instrument.write(f"SENS:AVER:COUN {count}")

    def get_averaging(self):
        """Get averaging count."""
        return int(self.instrument.query("SENS:AVER:COUN?"))

    def read_power(self):
        """Read measured power (Watts)."""
        return float(self.instrument.query("READ?"))

    def read_power_fast(self):
        """Faster read (without triggering new measurement)."""
        return float(self.instrument.query("MEAS:POW?"))

    def zero(self):
        """Perform zero adjustment."""
        self.instrument.write("SENS:CORR:COLL:ZERO")

    def disconnect(self):
        """Close connection."""
        self.instrument.close()
        self.rm.close()