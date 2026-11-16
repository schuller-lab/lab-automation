# lab-automation

Python automation for an angle-resolved reflection / second-harmonic-generation (SHG)
measurement rig: a LightField spectrometer/camera, several Thorlabs Kinesis rotation stages,
and a Thorlabs power meter, driven together from a single interactive script.

Each instrument is wrapped in its own class (`LightField`, `K10CR2`/`PRMTZ8`, `PM100D`,
`ChameleonLaser`), and `SHG-experiment.py` composes them into a menu-driven workflow for
calibrating the rig and running reflection/SHG sweeps across E(k)-space.

## Requirements

This runs on the lab's Windows PC only — it talks directly to vendor SDKs, not generic
cross-platform drivers.

| Dependency | Used by | Notes |
| --- | --- | --- |
| [`pythonnet`](https://pythonnet.github.io/) (`clr`) | `KinesisControls.py`, `LightFieldControls.py` | Bridges Python to the .NET SDKs below |
| Thorlabs Kinesis (`Thorlabs.MotionControl.*` DLLs) | `KinesisControls.py` | Installed with the Kinesis desktop app |
| Princeton Instruments LightField Automation SDK | `LightFieldControls.py` | Installed with LightField |
| [`pyvisa`](https://pyvisa.readthedocs.io/) + NI-VISA (or Thorlabs' VISA driver) | `PowerMeterControls.py` | For the PM100D power meter |
| [`pyserial`](https://pyserial.readthedocs.io/) | `LaserControls.py` | For the pump laser's serial (COM port) interface |
| `numpy`, `pandas`, `scipy`, `matplotlib` | plotting scripts | Standard scientific stack |

Device identifiers are hardcoded per-rig and will need updating if you're setting this up on a
different bench:
- Rotation-stage serial numbers and the PM100D VISA resource string are set inside
  `setup()` in `SHG-experiment.py`.
- The LightField SDK path is set at the top of `LightFieldControls.py`.
- The pump laser's COM port/baud rate are set at the top of `LaserControls.py`.

## Quick start

```
python SHG-experiment.py
```

This drops you into a numbered menu (`main_menu()`). Typical first run:

1. **`(1) setup`** — connects to every device (asks for a pump wavelength at the end).
2. **`(2) check devices`** — confirms everything is still connected before you start.
3. **`(3) pixel/degree/k calibration`** — maps CCD pixels to incident k-values; required once
   before running an experiment.
4. **`(5) reflection experiment`** / **`(6) SHG experiment`** — sweeps the mirror across the
   calibrated k-range, acquiring and saving a CSV at each point.
5. **`(10) close all devices`** when you're done.

Option **`(7) see individual devices`** opens a generic sub-menu that can call *any* public
method on any connected device — handy for one-off moves/reads without writing a script.

## File reference

### Experiment scripts

| File | Purpose |
| --- | --- |
| `SHG-experiment.py` | Main interactive entry point: menu-driven setup, calibration, and reflection/SHG data acquisition. |
| `DemoExperiment.py` | Minimal, non-interactive example of the connect → home → acquire → disconnect pattern. |

### Device control modules

| File | Purpose |
| --- | --- |
| `LightFieldControls.py` | `LightField` class — launches/controls Princeton Instruments LightField (exposure, center wavelength, grating, CSV acquisition) via pythonnet. |
| `KinesisControls.py` | `K10CR2` / `PRMTZ8` classes — Thorlabs Kinesis rotation and motion stage control via pythonnet. |
| `PowerMeterControls.py` | `PM100D` class — Thorlabs power meter readout via PyVISA. |
| `mff101.py` | `MFF101` class — Thorlabs MFF101 flip mount that moves the power meter into (position 2) / out of (position 1) the pump path, via the Kinesis `FilterFlipperCLI` DLL (pythonnet). Serial number is hardcoded in `SHG-experiment.py`'s `setup()`. |
| `LaserControls.py` | `ChameleonLaser` class — sets/reads the pump laser's wavelength over serial, with confirm-and-retry polling until the laser settles on target. |
| `SpectrometerWavelengthRanges.py` | Per-center-wavelength pixel→wavelength lookup table, used by `LightFieldControls.py` to label CSV output columns. |

### Plotting / analysis

| File | Purpose |
| --- | --- |
| `plot_heatmap.py` | Builds E(k)-space heatmaps from acquired CSVs, grouped by sample and input/output polarization. |
| `plot_line.py` | Extracts and plots line cuts (specular/off-specular) from acquired CSVs using a user-calibrated pixel↔k mapping. |
| `plot_diffracted_orders.py` | Locates and plots diffracted-order peaks in a k-space counts map. |
| `old plotting scripts/` | Earlier, superseded versions of the plotting scripts above — kept for reference. |
