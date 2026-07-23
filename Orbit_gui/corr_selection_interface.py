# Import the notebook support helpers and the orbit-correction package.
# These imports make the notebook self-contained: it can build snapshots,
# read the error table, and call the plotting helpers without extra setup.
from cpymad.madx import Madx

try:
    from IPython.display import display
except ImportError:
    def display(value):
        print(value)

from nominal_orbit_model import RUN_FULL_MODEL, RUN_ORBIT_CORRECTION_EXAMPLE, repo_root
import pandas as pd
import matplotlib.pyplot as plt

from optics_gui.snapshot import (
    SnapshotConfig,
    SnapshotOrbitCorrectionConfig,
    copy_snapshot_config,
    build_machine_snapshot,
)
from optics_gui.orbit_correction import (
    bpm_measurements_from_twiss,
    normalise_bpm_measurements,
    normalise_corrector_selection,
    plot_orbit_with_bpm,
    plot_corrector_suggestions,
)

# Configure the base machine snapshot.
# This is the common starting point used by the correction workflow.
orbit_base_config = SnapshotConfig(
    cycle_time_ms=0.0,
    requested_qx=4.31,
    requested_qy=3.83,
    lattice_folder=str(repo_root / "Dev" / "Lattice_Files" / "00_Simplified_Lattice"),
    output_dir=str(repo_root / "Dev" / "12_IO" / "student_runs" / "orbit"),
    run_envelope=False,
    run_aperture=False,
)

# Point to the Jan26 error table that provides the orbit distortion to correct.
jan26_error_table = repo_root / "Dev" / "Error_Tables" / "jan26_survey_corrected.tfs"
if not jan26_error_table.is_file():
    raise FileNotFoundError(f"Expected error table at {jan26_error_table}")

print("Setup complete")








# Helper function for the demo interface.
# It starts from the default corrector table, then turns on only the names
# supplied by the caller. This makes the interface easy to drive from a GUI
# or from a small notebook example.
def select_correctors_for_demo(plane, corrector_names):
    correctors = normalise_corrector_selection(plane=plane)
    selected = {name.lower() for name in corrector_names}
    correctors["enabled"] = correctors["corrector"].str.lower().isin(selected)
    return correctors

# Build a snapshot from the error table and then create two correction jobs:
# one for the horizontal plane and one for the vertical plane.
# This is the core of the selection workflow: BPM measurements are derived
# from the distorted orbit, and the selected correctors are passed into the
# orbit-correction config.
if RUN_FULL_MODEL and RUN_ORBIT_CORRECTION_EXAMPLE:
    error_orbit_config = copy_snapshot_config(
        orbit_base_config,
        snapshot_id="student_error_table_orbit",
        label="student error-table orbit",
        error_table_paths=[str(jan26_error_table)],
        orbit_correction_configs=[],
    )
    error_orbit_snapshot = build_machine_snapshot(error_orbit_config)

    error_orbit_bpm_h = bpm_measurements_from_twiss(error_orbit_snapshot.table("twiss"), plane="H")
    error_orbit_bpm_v = bpm_measurements_from_twiss(error_orbit_snapshot.table("twiss"), plane="V")

    h_correctors = select_correctors_for_demo("H", ["r0hd1_kick", "r3hd1_kick", "r5hd1_kick", "r9hd1_kick"])
    v_correctors = select_correctors_for_demo("V", ["r0vd1_kick", "r3vd1_kick", "r5vd1_kick", "r9vd1_kick"])

    error_orbit_correction_config = copy_snapshot_config(
        orbit_base_config,
        snapshot_id="student_error_table_orbit_correction",
        label="student error-table orbit correction",
        error_table_paths=[str(jan26_error_table)],
        orbit_correction_configs=[
            SnapshotOrbitCorrectionConfig(
                plane="H",
                label="horizontal_error_table_orbit",
                bpm_measurements=error_orbit_bpm_h,
                correctors=h_correctors,
            ),
            SnapshotOrbitCorrectionConfig(
                plane="V",
                label="vertical_error_table_orbit",
                bpm_measurements=error_orbit_bpm_v,
                correctors=v_correctors,
            ),
        ],
    )
    error_orbit_correction_snapshot = build_machine_snapshot(error_orbit_correction_config)
    display(error_orbit_correction_snapshot.table("orbit_correction_summary"))
    display(error_orbit_correction_snapshot.table("orbit_correction_correctors"))
else:
    print("Correction example skipped. Keep RUN_FULL_MODEL and RUN_ORBIT_CORRECTION_EXAMPLE true to run it.")










    # Plot the before/after orbit and the suggested corrector currents.
# The first figure shows the fitted orbit and the corrected orbit for both planes.
# The second figure is more GUI-friendly: it visualises the correction values
# that the backend has suggested for the selected correctors.
if RUN_FULL_MODEL and RUN_ORBIT_CORRECTION_EXAMPLE:
    h_correction = next(
        result.result
        for result in error_orbit_correction_snapshot.orbit_correction_results
        if result.plane == "H"
    )
    v_correction = next(
        result.result
        for result in error_orbit_correction_snapshot.orbit_correction_results
        if result.plane == "V"
    )

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=False)
    plot_orbit_with_bpm(
        h_correction.measured_twiss_df,
        h_correction.bpm_measurements,
        plane="H",
        ax=axes[0],
        label="Jan26 error-table fitted orbit",
        title="Horizontal orbit before and after correction suggestion",
    )
    
    plot_orbit_with_bpm(
        h_correction.corrected_twiss_df,
        h_correction.bpm_measurements,
        plane="H",
        ax=axes[0],
        label="After MAD-X CORRECT suggestion",
        orbit_kwargs={"linestyle": "--"},
    )
    plot_orbit_with_bpm(
        v_correction.measured_twiss_df,
        v_correction.bpm_measurements,
        plane="V",
        ax=axes[1],
        label="Jan26 error-table fitted orbit",
        title="Vertical orbit before and after correction suggestion",
    )
    plot_orbit_with_bpm(
        v_correction.corrected_twiss_df,
        v_correction.bpm_measurements,
        plane="V",
        ax=axes[1],
        label="After MAD-X CORRECT suggestion",
        orbit_kwargs={"linestyle": "--"},
    )
    fig.tight_layout()
    plt.show()

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=False)
    plot_corrector_suggestions(
        h_correction.correctors,
        ax=axes[0],
        value="delta_current_A",
        title="Horizontal corrector current suggestions",
    )
    plot_corrector_suggestions(
        v_correction.correctors,
        ax=axes[1],
        value="delta_current_A",
        title="Vertical corrector current suggestions",
    )
    fig.tight_layout()
    
else:
    print("Correction plots skipped. Keep RUN_FULL_MODEL and RUN_ORBIT_CORRECTION_EXAMPLE true to run them.")