import os
import re
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from matplotlib.colors import LogNorm

# ---------------------------
# User settings
# ---------------------------


DATA_FOLDER = r"C:\Users\schul\data\Wes\reflection-experiments\2026-04-02(2)"  # change to your folder path if needed

FILE_GLOB = os.path.join(DATA_FOLDER, "*ky=*.csv")

# Accept ky from filename like ky=+0,02 or ky=-0.10
KY_PATTERN = re.compile(r"(?:ky|k)=([+-]?\d+[.,]\d+|[+-]?\d+)")

print("\nProvide calibration for ky -> y conversion.")
print("Enter the y pixel corresponding to ky = +1 and ky = -1.\n")

while True:
    try:
        y_pos1 = float(input("Enter y pixel for ky = +1 (e.g. 200): ").strip())
        y_neg1 = float(input("Enter y pixel for ky = -1 (e.g. 800): ").strip())
        break
    except ValueError:
        print("Invalid input. Please enter numeric values.\n")

while True:
    try:
        avg_width = int(input("Enter averaging width around x = 512 (e.g. 5): ").strip())
        if avg_width <= 0:
            print("Averaging width must be a positive integer.\n")
            continue
        break
    except ValueError:
        print("Invalid input. Please enter an integer.\n")

# Linear relation: y = m*ky + c
m_ky_to_y = (y_pos1 - y_neg1) / 2.0
c_ky_to_y = (y_pos1 + y_neg1) / 2.0

def ky_to_y(ky_value):
    """Convert ky to y pixel using the forward linear mapping."""
    return m_ky_to_y * ky_value + c_ky_to_y

def y_to_ky(y_value):
    """Convert y pixel to ky using the inverse linear mapping."""
    if m_ky_to_y == 0:
        raise RuntimeError("Invalid calibration: slope is zero.")
    return (y_value - c_ky_to_y) / m_ky_to_y

# Fixed x center
CENTER_X = 512

# The reflected ky range you want to keep
REFLECTED_KY_MIN = -1.3
REFLECTED_KY_MAX = 1.3

# ---------------------------
# CSV helpers
# ---------------------------

def load_counts_matrix(csv_file):
    """
    Load the LightField CSV in the format shown in your screenshot.

    Assumptions:
    - first row is wavelength header -> ignored
    - first column is y labels / blank -> ignored
    - remaining block is photon counts
    """
    try:
        df = pd.read_csv(csv_file, header=None, skiprows=1)
        df = df.apply(pd.to_numeric, errors='coerce')
    except Exception as e:
        raise RuntimeError(f"Error reading {csv_file}: {e}")

    if df.empty or df.shape[1] < 2:
        raise RuntimeError(f"Unexpected or empty CSV format in {csv_file}")

    counts = df.iloc[:, 1:].to_numpy(dtype=float)

    if counts.size == 0:
        raise RuntimeError(f"No photon-count data found in {csv_file}")

    return counts

def select_x_window(n_cols, center=CENTER_X, width=avg_width):
    """
    Select an x-window around the given center, clipped to valid bounds.
    """
    width = max(1, int(width))
    center = int(center)

    if width >= n_cols:
        return 0, n_cols - 1

    half = width // 2
    x0 = max(0, center - half)
    x1 = x0 + width - 1

    if x1 >= n_cols:
        x1 = n_cols - 1
        x0 = max(0, x1 - width + 1)

    return x0, x1

def extract_expected_ky(filename):
    """
    Extract expected ky from filename.
    """
    m = KY_PATTERN.search(filename)
    if not m:
        return None
    return float(m.group(1).replace(',', '.'))

def get_reflected_profile(csv_file):
    """
    For one CSV file:
    - load the counts matrix
    - average over a small x-window around x = 512
    - convert each y pixel to reflected ky using the calibration
    - keep only reflected ky in [-1.3, +1.3]
    - sort by reflected ky so the axis is in the correct order
    - return reflected ky axis and intensity profile
    """
    counts = load_counts_matrix(csv_file)
    n_rows, n_cols = counts.shape

    x0, x1 = select_x_window(n_cols, CENTER_X, avg_width)

    # average over a small x-window around 512
    vertical_profile = np.nanmean(counts[:, x0:x1 + 1], axis=1)

    # clean any possible NaNs
    if not np.isfinite(vertical_profile).any():
        raise RuntimeError(f"No finite intensity values in {csv_file}")

    fill_value = np.nanmedian(vertical_profile[np.isfinite(vertical_profile)])
    if not np.isfinite(fill_value):
        fill_value = 0.0
    vertical_profile = np.nan_to_num(vertical_profile, nan=fill_value)

    # Convert every y pixel to reflected ky directly
    y_pixels = np.arange(n_rows, dtype=float)
    reflected_ky_axis = y_to_ky(y_pixels)

    # Keep only the reflected ky range you want
    mask = (reflected_ky_axis >= REFLECTED_KY_MIN) & (reflected_ky_axis <= REFLECTED_KY_MAX)

    if not np.any(mask):
        raise RuntimeError(
            f"No reflected ky values fall within [{REFLECTED_KY_MIN}, {REFLECTED_KY_MAX}] in {csv_file}"
        )

    reflected_ky_kept = reflected_ky_axis[mask]
    profile_kept = vertical_profile[mask]

    # IMPORTANT: sort by reflected ky so the map is not vertically flipped
    order = np.argsort(reflected_ky_kept)
    reflected_ky_kept = reflected_ky_kept[order]
    profile_kept = profile_kept[order]

    return reflected_ky_kept, profile_kept

# ---------------------------
# Main processing
# ---------------------------

file_list = sorted(glob.glob(FILE_GLOB))
if not file_list:
    raise SystemExit(f"No CSV files found in {DATA_FOLDER}")

expected_ky_vals = []
profiles = []
reflected_ky_axis_common = None
bad_files = []

for f in file_list:
    basename = os.path.basename(f)

    expected_ky = extract_expected_ky(basename)
    if expected_ky is None:
        continue

    try:
        reflected_ky_axis, profile = get_reflected_profile(f)
    except Exception as e:
        bad_files.append((basename, str(e)))
        continue

    # Use the first valid file as the common reflected ky axis
    if reflected_ky_axis_common is None:
        reflected_ky_axis_common = reflected_ky_axis
        profiles.append(profile)
        expected_ky_vals.append(expected_ky)
        continue

    # If needed, interpolate onto the first file's reflected ky axis
    if len(reflected_ky_axis) != len(reflected_ky_axis_common) or not np.allclose(reflected_ky_axis, reflected_ky_axis_common):
        profile = np.interp(
            reflected_ky_axis_common,
            reflected_ky_axis,
            profile,
            left=profile[0],
            right=profile[-1]
        )

    expected_ky_vals.append(expected_ky)
    profiles.append(profile)

if not profiles:
    raise SystemExit("No valid data extracted.")

# Sort by expected ky
order = np.argsort(expected_ky_vals)
expected_ky_sorted = np.array(expected_ky_vals)[order]
profiles_sorted = [profiles[i] for i in order]

# Build final 2D map:
# x = expected ky
# y = reflected ky
# intensity = averaged photon counts
Z = np.column_stack(profiles_sorted)

# Smooth a little for a polished look
Z = gaussian_filter(Z, sigma=(1.2, 0.6))

positive = Z[Z > 0]
if positive.size == 0:
    raise SystemExit("No positive intensity values to plot.")

vmin = max(np.percentile(positive, 2), 1e-6)
vmax = np.percentile(positive, 99.7)

masked_Z = np.ma.masked_less_equal(Z, 0)
cmap = plt.cm.inferno.copy()
cmap.set_bad("black")
cmap.set_under("black")

# ---------------------------
# Plot
# ---------------------------

plt.figure(figsize=(9, 6))

im = plt.imshow(
    masked_Z,
    origin='lower',
    aspect='auto',
    extent=[
        expected_ky_sorted.min(),
        expected_ky_sorted.max(),
        reflected_ky_axis_common.min(),
        reflected_ky_axis_common.max()
    ],
    cmap=cmap,
    norm=LogNorm(vmin=vmin, vmax=vmax),
    interpolation='bicubic'
)

# im = plt.imshow(
#     Z,
#     origin='lower',
#     aspect='auto',
#     extent=[
#         expected_ky_sorted.min(),
#         expected_ky_sorted.max(),
#         reflected_ky_axis_common.min(),
#         reflected_ky_axis_common.max()
#     ],
#     cmap=cmap,
#     vmin=0,
#     vmax=Z.max(),
#     interpolation='bicubic'
# )


plt.xlabel("Expected ky")
plt.ylabel("Reflected ky")
plt.title("2D Map: Intensity vs Expected ky and Reflected ky")
cbar = plt.colorbar(im)
cbar.set_label("Average photon counts (log scale)")

# cbar.set_label("Average photon counts")


plt.tight_layout()

out_png = os.path.join(DATA_FOLDER, "2D_map_expected_ky_reflected_ky_full.png")
plt.savefig(out_png, dpi=150)
plt.show()

print(f"Saved 2D map to: {out_png}")

if bad_files:
    print("\nSome files were skipped or had errors:")
    for item in bad_files:
        print(item)