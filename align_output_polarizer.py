# -*- coding: utf-8 -*-
"""
align_output_polarizer.py

Rotates the "Output polarizer" (Thorlabs K10CR2, serial 55536784) until the
four-lobed bright pattern seen on the CCD (via LightField, SHG experiment)
is aligned with the pixel grid -- lobes at +x, -x, +y, -y -- i.e. the
pattern's rotation angle (mod 90 deg) is driven to ~0.

Usage:
    C:\\Users\\schul\\anaconda3\\envs\\lab-controls\\python.exe align_output_polarizer.py

Prerequisites:
    - "Output polarizer" must be disconnected in the Kinesis GUI (or Kinesis closed).
    - The LightField GUI window must be closed (this script relaunches it, GUI visible).
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

LAB_AUTOMATION_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LAB_AUTOMATION_DIR)
sys.path.insert(0, r"C:\Users\schul\2p-ple-auto")

from LightFieldControls import LightField, is_lightfield_running  # noqa: E402
from k10cr2 import open_stage, get_angle, set_angle, close_stage  # noqa: E402

from System.IO import FileAccess  # noqa: E402

POLARIZER_SERIAL = "55536784"
EXPERIMENT_NAME = "SHG"

TOLERANCE_DEG = 1.0
PROBE_STEP_DEG = 2.0
MAX_STEP_DEG = 15.0
MAX_ITERATIONS = 10


def acquire_frame(lf):
    """Acquire one frame from LightField and return it as a 2D numpy array."""
    lf.experiment.Acquire()
    while lf.experiment.IsRunning:
        time.sleep(0.1)
    recent_file = lf.file_manager.GetRecentlyAcquiredFileNames()[0]
    image_set = lf.file_manager.OpenFile(recent_file, FileAccess.ReadWrite)
    frame = image_set.GetFrame(0, 0)
    data = np.array(frame.GetData()).reshape((frame.Height, frame.Width))
    del image_set, frame
    Path(recent_file).unlink()
    return data


def measure_residual(frame):
    """
    Given a 2D image containing a 4-lobed bright pattern, return
    (residual_deg, centroids, center) where residual_deg is the signed
    misalignment (degrees, in [-45, 45]) of the pattern from the pixel
    row/column axes, computed via circular averaging over the pattern's
    4-fold symmetry (handles the +/-90 deg branch cut correctly).
    """
    baseline = np.percentile(frame, 10)
    signal = frame.astype(np.float64) - baseline
    signal[signal < 0] = 0

    threshold = 0.5 * signal.max()
    mask = signal > threshold

    labeled, n = ndimage.label(mask)
    if n < 4:
        raise RuntimeError(
            f"Only found {n} bright region(s); expected 4. "
            "Check focus/exposure/alignment before continuing."
        )

    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    top4 = np.argsort(sizes)[-4:] + 1  # labels of the 4 largest blobs

    centroids = np.array(ndimage.center_of_mass(signal, labeled, top4))  # (row, col) x4

    row_c, col_c = centroids.mean(axis=0)
    angles = np.arctan2(centroids[:, 0] - row_c, centroids[:, 1] - col_c)

    mean_sin = np.mean(np.sin(4 * angles))
    mean_cos = np.mean(np.cos(4 * angles))
    residual_rad = np.arctan2(mean_sin, mean_cos) / 4.0
    return np.degrees(residual_rad), centroids, (row_c, col_c)


def main():
    if is_lightfield_running():
        print("LightField is still running under the GUI. Close it and re-run.")
        sys.exit(1)

    print("Connecting to output polarizer...")
    stage = open_stage(POLARIZER_SERIAL)

    print(f"Launching LightField, loading experiment '{EXPERIMENT_NAME}'...")
    lf = LightField({'experiment_name': EXPERIMENT_NAME})
    lf._launch(show_GUI=True)

    try:
        print("Acquiring initial frame for a sanity check...")
        frame = acquire_frame(lf)
        print(f"Frame shape={frame.shape}, dtype={frame.dtype}, "
              f"min={frame.min()}, max={frame.max()}")
        if frame.max() == 0:
            raise RuntimeError("Frame is all zeros -- check camera/laser/shutter.")
        if np.issubdtype(frame.dtype, np.integer) and frame.max() >= np.iinfo(frame.dtype).max:
            print("WARNING: frame may be saturated.")

        history = []

        def measure_at(angle):
            set_angle(stage, angle)
            time.sleep(0.2)
            f = acquire_frame(lf)
            residual, centroids, center = measure_residual(f)
            actual = get_angle(stage)
            history.append((actual, residual))
            print(f"  angle={actual:8.3f} deg   residual={residual:+7.3f} deg")
            return residual

        a0 = get_angle(stage)
        print(f"Starting angle: {a0:.3f} deg")
        e0 = measure_at(a0)

        if abs(e0) < TOLERANCE_DEG:
            print("Already within tolerance.")
        else:
            a1 = a0 + PROBE_STEP_DEG
            e1 = measure_at(a1)
            prev_a, prev_e = a0, e0
            cur_a, cur_e = a1, e1

            for i in range(MAX_ITERATIONS):
                if abs(cur_e) < TOLERANCE_DEG:
                    print(f"Converged after {i} correction(s).")
                    break

                d_e = cur_e - prev_e
                d_a = cur_a - prev_a
                if abs(d_e) < 1e-6:
                    print("Degenerate gain (no measurable response) -- stopping.")
                    break
                gain = d_e / d_a

                step = -cur_e / gain
                step = max(-MAX_STEP_DEG, min(MAX_STEP_DEG, step))
                next_a = cur_a + step

                prev_a, prev_e = cur_a, cur_e
                cur_e = measure_at(next_a)
                cur_a = next_a
            else:
                best = min(history, key=lambda h: abs(h[1]))
                print(f"Did not converge within {MAX_ITERATIONS} iterations. "
                      f"Best point so far: angle={best[0]:.3f} deg, residual={best[1]:+.3f} deg")

        final_angle = get_angle(stage)
        final_frame = acquire_frame(lf)
        final_residual, centroids, center = measure_residual(final_frame)
        print(f"\nFinal angle: {final_angle:.3f} deg, residual: {final_residual:+.3f} deg")

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        out_png = os.path.join(LAB_AUTOMATION_DIR, "output_polarizer_alignment_result.png")
        plt.figure(figsize=(6, 6))
        plt.imshow(final_frame, cmap="inferno")
        plt.scatter(centroids[:, 1], centroids[:, 0], marker="x", color="cyan")
        plt.axhline(center[0], color="lime", lw=0.5)
        plt.axvline(center[1], color="lime", lw=0.5)
        plt.title(f"angle={final_angle:.3f} deg, residual={final_residual:+.3f} deg")
        plt.savefig(out_png, dpi=150)
        print(f"Saved confirmation image: {out_png}")

    finally:
        close_stage(stage)
        print("Polarizer connection closed (Kinesis GUI can reclaim it).")
        # Deliberately NOT closing LightField -- leave it open for the user.


if __name__ == "__main__":
    main()
