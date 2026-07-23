# Imports
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# Setup repository root and import path for the packaged backend.
repo_root = Path(__file__).resolve().parent.parent
if not (repo_root / "Dev" / "12_IO").is_dir():
    repo_root = Path.cwd()
    if repo_root.name == "12_IO":
        repo_root = repo_root.parents[1]
    elif (repo_root / "Dev" / "12_IO").is_dir():
        pass

src_path = repo_root / "src"
if src_path.is_dir() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from optics_gui.orbit_correction import (
    bpm_measurements_from_twiss,
    normalise_corrector_selection,
    plot_corrector_suggestions,
    plot_orbit_with_bpm,
)
from optics_gui.snapshot import (
    SnapshotConfig,
    SnapshotOrbitCorrectionConfig,
    build_machine_snapshot,
    copy_snapshot_config,
)

st.set_page_config(page_title="Orbit GUI", layout="wide")
st.title("Orbit GUI")

# Model configuration
lattice_folder = repo_root / "Dev" / "Lattice_Files" / "00_Simplified_Lattice"
error_table_path = repo_root / "Dev" / "Error_Tables" / "jan26_survey_corrected.tfs"
output_dir = repo_root / "Dev" / "12_IO" / "student_runs" / "orbit"

base_snapshot_config = SnapshotConfig(
    cycle_time_ms=0.0,
    label="student_orbit_gui",
    case="nominal",
    snapshot_id="student_orbit_gui",
    lattice_folder=str(lattice_folder),
    output_dir=str(output_dir),
    run_envelope=False,
    run_aperture=False,
)

nominal_snapshot_config = copy_snapshot_config(
    base_snapshot_config,
    snapshot_id="student_nominal_orbit",
    label="Nominal orbit snapshot",
    error_table_paths=[],
    orbit_correction_configs=[],
)

error_snapshot_config = copy_snapshot_config(
    base_snapshot_config,
    snapshot_id="student_error_table_orbit",
    label="Error-table orbit snapshot",
    error_table_paths=[str(error_table_path)] if error_table_path.exists() else [],
    orbit_correction_configs=[],
)


def select_correctors_for_demo(plane, names):
    correctors = normalise_corrector_selection(plane=plane)
    selected = {name.lower() for name in names}
    correctors["enabled"] = correctors["corrector"].str.lower().isin(selected)
    return correctors


def get_orbit_snapshot(key):
    cache = st.session_state.setdefault("orbit_gui_snapshots", {})
    if key not in cache:
        if key == "nominal":
            cache[key] = build_machine_snapshot(nominal_snapshot_config)
        elif key == "error":
            cache[key] = build_machine_snapshot(error_snapshot_config)
        elif key == "correction":
            error_snapshot = get_orbit_snapshot("error")
            bpm_h = bpm_measurements_from_twiss(error_snapshot.table("twiss"), plane="H")
            bpm_v = bpm_measurements_from_twiss(error_snapshot.table("twiss"), plane="V")
            h_correctors = select_correctors_for_demo(
                "H",
                ["r0hd1_kick", "r3hd1_kick", "r5hd1_kick", "r9hd1_kick"],
            )
            v_correctors = select_correctors_for_demo(
                "V",
                ["r0vd1_kick", "r3vd1_kick", "r5vd1_kick", "r9vd1_kick"],
            )
            correction_snapshot_config = copy_snapshot_config(
                base_snapshot_config,
                snapshot_id="student_error_table_orbit_correction",
                label="Error-table orbit correction snapshot",
                error_table_paths=[str(error_table_path)] if error_table_path.exists() else [],
                orbit_correction_configs=[
                    SnapshotOrbitCorrectionConfig(
                        plane="H",
                        label="horizontal_error_table_orbit",
                        bpm_measurements=bpm_h,
                        correctors=h_correctors,
                    ),
                    SnapshotOrbitCorrectionConfig(
                        plane="V",
                        label="vertical_error_table_orbit",
                        bpm_measurements=bpm_v,
                        correctors=v_correctors,
                    ),
                ],
            )
            cache[key] = build_machine_snapshot(correction_snapshot_config)
        else:
            raise KeyError(f"Unknown orbit snapshot key: {key}")
    return cache[key]


def orbit_line_chart(df, y_columns, title):
    if df is None or df.empty:
        st.write("No orbit data available.")
        return
    chart_df = df.set_index("s")[y_columns].copy()
    chart_df.index.name = "s"
    st.line_chart(chart_df)


def display_snapshot_tables(snapshot, title):
    st.header(title)
    with st.expander("Orbit summary and tables", expanded=True):
        st.subheader("Orbit summary")
        st.dataframe(snapshot.table("orbit_summary"), width="stretch")
        st.subheader("Orbit table")
        st.dataframe(snapshot.table("orbit"), width="stretch")
        if "twiss" in snapshot.available_tables():
            st.subheader("TWISS table (first 20 rows)")
            st.dataframe(snapshot.table("twiss").head(20), width="stretch")


def display_correction_results(snapshot):
    if not snapshot.orbit_correction_results:
        st.warning("No orbit correction results are available for this snapshot.")
        return

    st.header("Correction suggestions")
    st.subheader("Correction summary")
    st.dataframe(snapshot.table("orbit_correction_summary"), width="stretch")

    st.subheader("Corrector suggestion table")
    st.dataframe(snapshot.table("orbit_correction_correctors"), width="stretch")

    st.subheader("BPM before/after comparison")
    st.dataframe(snapshot.table("orbit_correction_bpm_comparison"), width="stretch")

    st.subheader("Before / after monitor summaries")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Before correction")
        st.dataframe(snapshot.table("orbit_correction_before"), width="stretch")
    with col2:
        st.write("After correction")
        st.dataframe(snapshot.table("orbit_correction_after"), width="stretch")

    for result in snapshot.orbit_correction_results:
        st.subheader(f"Orbit correction: {result.label} ({result.plane})")
        fig, ax = plt.subplots(figsize=(11, 4))
        plot_orbit_with_bpm(
            result.result.measured_twiss_df,
            result.result.bpm_measurements,
            plane=result.plane,
            ax=ax,
            label="Measured orbit",
            title=f"{result.plane} plane measured orbit and correction suggestion",
        )
        plot_orbit_with_bpm(
            result.result.corrected_twiss_df,
            result.result.bpm_measurements,
            plane=result.plane,
            ax=ax,
            label="Corrected orbit",
            orbit_kwargs={"linestyle": "--"},
        )
        st.pyplot(fig)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 4))
        plot_corrector_suggestions(
            result.result.correctors,
            ax=ax,
            value="delta_current_A",
            title=f"{result.plane} corrector current suggestions",
        )
        st.pyplot(fig)
        plt.close(fig)

        if not snapshot.table("orbit_correction_warnings").empty:
            st.subheader("Correction warnings")
            st.dataframe(snapshot.table("orbit_correction_warnings"), use_container_width=True)


with st.sidebar:
    st.header("Orbit GUI controls")
    orbit_mode = st.selectbox(
        "Select orbit source mode",
        ["Nominal", "Error Table", "Measured BPMs"],
    )
    enable_correction = st.checkbox("Show correction suggestions", value=True)

st.write("This GUI displays the nominal orbit, the error-table orbit, and a simple measured BPM orbit example. The error-table mode can also show read-only correction suggestions using the packaged optics backend.")

try:
    nominal_snapshot = get_orbit_snapshot("nominal")
    error_snapshot = get_orbit_snapshot("error")
except Exception as exc:
    st.error(f"Failed to build base orbit snapshots: {exc}")
    raise

if orbit_mode == "Nominal":
    st.subheader("Nominal model orbit")
    orbit_line_chart(nominal_snapshot.table("orbit"), ["x_mm", "y_mm"], "Nominal orbit")
    display_snapshot_tables(nominal_snapshot, "Nominal orbit model")
elif orbit_mode == "Error Table":
    st.subheader("Error-table model orbit")
    orbit_line_chart(error_snapshot.table("orbit"), ["x_mm", "y_mm"], "Error-table orbit")
    display_snapshot_tables(error_snapshot, "Error-table orbit model")
    if enable_correction:
        try:
            correction_snapshot = get_orbit_snapshot("correction")
            display_correction_results(correction_snapshot)
        except Exception as exc:
            st.error(f"Failed to build orbit correction snapshot: {exc}")
elif orbit_mode == "Measured BPMs":
    st.subheader("Measured BPM orbit example")
    measured_bpm = bpm_measurements_from_twiss(error_snapshot.table("twiss"), plane="H").head(12)
    measured_bpm["closed_orbit_mm"] = measured_bpm["closed_orbit_mm"].round(3)
    st.dataframe(measured_bpm, width="stretch")
    if not measured_bpm.empty:
        chart_df = measured_bpm.set_index("s")["closed_orbit_mm"].copy()
        chart_df.index.name = "s"
        st.line_chart(chart_df)


#RUN THIS VIA $ cd C:\Users\Visitor\Desktop\Work-experience-2026-ISIS-RCS-optics-GUI, in your gitbash!