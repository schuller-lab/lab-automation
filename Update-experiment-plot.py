import os
import re
import glob
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------
# User inputs & calibration
# ---------------------------

DATA_FOLDER=r'C:\Users\schul\data\Wes\reflection-experiments\2026-03-02(1)'

print("\nNext, provide two calibration points for the ky -> y mapping.")
print("You will be asked for the y pixel corresponding to ky=+1 and ky=-1.")
print("Example: if ky=+1 -> y=200 and ky=-1 -> y=800 then y(0) will be 500.\n")

while True:
    try:
        y_pos1 = float(input("Enter the y-pixel that corresponds to ky=+1 (e.g. 200): ").strip())
        y_neg1 = float(input("Enter the y-pixel that corresponds to ky=-1 (e.g. 800): ").strip())
        break
    except ValueError:
        print("Invalid input — please enter numeric pixel values (integers or floats). Try again.\n")

# Linear mapping parameters: y = m*ky + c
m_ky_to_y = (y_pos1 - y_neg1) / 2.0
c_ky_to_y = (y_pos1 + y_neg1) / 2.0

def ky_to_y(ky_value):
    """Return the (float) y pixel corresponding to ky_value using linear mapping."""
    return m_ky_to_y * ky_value + c_ky_to_y

# fixed x-center (as you requested)
CENTER_X = 512

# ---------------------------
# Helper function to extract average from a CSV file
# ---------------------------

def get_avg_from_file(data_file, width, height, dimensions=None, bkgrnd_choice='None', background_file=None):
    """
    Compute the mean counts in a rectangular ROI read from a LightField CSV.

    Behavior:
    - width, height provided once per run and passed into this function.
    - Extracts ky from the filename (accepts '.' or ',' decimal separators).
    - Computes the y-center (cy) from ky using the ky_to_y(ky) mapping function.
    - Sets x-center (cx) to 512 (fixed).
    - Reads the entire CSV (no skiprows) and slices the ROI from the loaded array.
    - Returns the average counts (float) over the ROI.

    Note: 'dimensions' argument kept for compatibility but ignored.
    """
    # --- extract ky from filename (accept '.' or ',' decimal separators) ---
    fname = os.path.basename(data_file)
    ky_pattern = re.compile(r"ky=([+-]?\d+[.,]\d+|[+-]?\d+)")
    m = ky_pattern.search(fname)
    if not m:
        raise RuntimeError(f"Could not find ky=... in filename '{fname}'")

    ky_str = m.group(1).replace(',', '.')  # normalize comma decimals to dot
    try:
        ky_val = float(ky_str)
    except ValueError:
        raise RuntimeError(f"Could not parse ky value '{ky_str}' in filename '{fname}'")

    # -- compute center positions --
    cx = CENTER_X
    try:
        cy_float = ky_to_y(ky_val)
    except NameError:
        raise RuntimeError("ky_to_y(ky) mapping function is not defined in the script.")
    cy = int(round(cy_float))

    # Compute ROI integer bounds (inclusive)
    x0 = int(cx - (width // 2))
    x1 = x0 + width - 1
    y0 = int(cy - (height // 2))
    y1 = y0 + height - 1

    # safety clamp to non-negative indices
    x0 = max(0, x0)
    y0 = max(0, y0)

    # read the full CSV into a numpy array (no skiprows)
    try:
        full = np.loadtxt(data_file, delimiter=',')
    except Exception as e:
        raise RuntimeError(f"Error loading CSV file '{data_file}': {e}")

    # check bounds against array shape
    if full.ndim != 2:
        raise RuntimeError(f"Unexpected CSV shape for file '{data_file}': got ndim={full.ndim}")

    ny, nx = full.shape  # rows (y), cols (x)
    if x1 >= nx or y1 >= ny:
        raise RuntimeError(f"Requested ROI (({x0},{y0}),({x1},{y1})) out of image bounds ({nx}x{ny}).")

    # slice ROI and compute average
    roi = full[y0:y1+1, x0:x1+1]
    if roi.size == 0:
        raise RuntimeError(f"No ROI data extracted from '{data_file}' with bounds (({x0},{y0}),({x1},{y1})).")

    avg = float(np.mean(roi))
    return avg

# ---------------------------
# Main processing
# ---------------------------

# find CSV files in the folder
file_list = sorted(glob.glob(os.path.join(DATA_FOLDER, "*.csv")))

if not file_list:
    raise SystemExit(f"No CSV files found in {DATA_FOLDER}")

# Ask ROI size once for the whole run
while True:
    try:
        width = int(input("Enter ROI width in pixels (e.g. 11): ").strip())
        height = int(input("Enter ROI height in pixels (e.g. 11): ").strip())
        if width <= 0 or height <= 0:
            print("Width and height must be positive integers.")
            continue
        break
    except ValueError:
        print("Invalid input. Please enter integer values.")

# Pattern to extract ky value (supports comma or dot decimal)
pattern = re.compile(r"ky=([+-]?\d+[.,]\d+|[+-]?\d+)")

ky_vals = []
avg_vals = []
bad_files = []

for f in file_list:
    basename = os.path.basename(f)
    m = pattern.search(basename)
    if not m:
        # skip files that don't match the ky=... pattern
        continue
    ky_str = m.group(1).replace(',', '.')
    try:
        ky = float(ky_str)
    except ValueError:
        bad_files.append((f, f"could not parse ky value '{m.group(1)}'"))
        continue

    # compute continuous y center from the linear mapping and get ROI average
    try:
        avg = get_avg_from_file(f, width, height, None, bkgrnd_choice='None')
    except Exception as e:
        bad_files.append((f, str(e)))
        continue

    ky_vals.append(ky)
    avg_vals.append(float(avg))

# sort arrays by ky
sorted_pairs = sorted(zip(ky_vals, avg_vals), key=lambda p: p[0])
if not sorted_pairs:
    raise SystemExit("No matching CSV files found or no ky values extracted. Check folder and filenames.")

ky_sorted = np.array([p[0] for p in sorted_pairs])
avg_sorted = np.array([p[1] for p in sorted_pairs])

# normalize by the maximum average
max_val = np.max(avg_sorted)
if max_val == 0:
    norm = avg_sorted.copy()
else:
    norm = avg_sorted / max_val

# save a summary CSV with ky, avg, norm
summary_csv = os.path.join(DATA_FOLDER, "summary_normalized_avg_vs_ky.csv")
with open(summary_csv, 'w', newline='') as out:
    out.write("ky,avg,norm\n")
    for k, a, n in zip(ky_sorted, avg_sorted, norm):
        out.write(f"{k:+0.6f},{a:.6f},{n:.6f}\n")

# plotting
plt.figure(figsize=(7, 4.5))
plt.plot(ky_sorted, norm, marker='o', linestyle='-')
plt.xlabel('ky (normalized units)')
plt.ylabel('Normalized average photon counts')
plt.title('Normalized average photon counts vs ky')
plt.grid(True)
plt.tight_layout()
plt.savefig(os.path.join(DATA_FOLDER, "normalized_avg_vs_ky.png"), dpi=150)
plt.show()