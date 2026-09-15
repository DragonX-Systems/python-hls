#!/usr/bin/env python3
"""
End-to-End Example: Automated GPU-OpenLane Handoff and DSE Calibration (#3).

This script demonstrates closing the loop between early architectural Python-HLS DSE
estimates and physical ASIC implementation measurements:
1. Compiles Python source to Verilog RTL.
2. Synthesizes standard SDC timing constraints.
3. Generates a reproducible flow manifest (flow_manifest.json).
4. Executes or exports the companion GPU-OpenLane flow.
5. Ingests implementation reports (synthesis area, OpenSTA timing, power, DRC, PVT corner).
6. Calibrates DSE models against physical QoR and outputs an updated TechLibrary JSON overlay.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python_hls import HLS, OpenLaneRunner, ReportIngestionEngine, DSECalibrator


def main():
    print("=================================================================")
    print(" Python-HLS: Automated GPU-OpenLane Handoff & DSE Calibration")
    print("=================================================================\n")

    # 1. Setup paths
    source_file = "examples/gcd.py"
    output_dir = "build/openlane_gcd_demo"
    liberty_file = "examples/technology_libraries/sky130_sample.lib"
    calibrated_lib_file = os.path.join(output_dir, "calibrated_sky130_gcd.json")

    print(f"1. Source Kernel     : {source_file}")
    print(f"   Target PDK        : sky130A (SkyWater 130nm HD)")
    print(f"   Liberty Library   : {liberty_file}")
    print(f"   Output Directory  : {output_dir}\n")

    # 2. Compile kernel and gather early DSE estimates
    print("2. Running Python-HLS compilation & early DSE estimation...")
    hls = HLS(tech_node=45, optimization_level=1)
    netlist, logs = hls.compile(source_file, target="verilog")
    dse_metrics = hls.get_performance_metrics()

    print(f"   Early DSE Area    : {dse_metrics.get('total_area', 0):.2f} μm²")
    print(f"   Early DSE Power   : {dse_metrics.get('total_power', 0):.3f} mW")
    print(f"   Latency           : {dse_metrics.get('latency_cycles', 0)} cycles")
    print(f"   Clock Frequency   : {dse_metrics.get('clock_frequency_mhz', 100):.2f} MHz\n")

    # 3. Export GPU-OpenLane handoff bundle
    print("3. Generating Flow Manifest and SDC constraints...")
    bundle = hls.export_openlane_handoff(
        source_file=source_file,
        liberty_file=liberty_file,
        output_dir=output_dir,
        clock_period_ns=5.0,  # 200 MHz target
        clock_name="clk",
        pdk="sky130A",
    )

    print(f"   Manifest JSON     : {bundle['manifest_file']}")
    print(f"   SDC Constraints   : {bundle['sdc_file']}")
    print(f"   Runner Script     : {bundle['script_file']}\n")

    # 4. Execute handoff flow (mock mode provides deterministic reports offline)
    print("4. Executing GPU-OpenLane physical implementation flow...")
    result = hls.run_openlane_handoff(
        source_file=source_file,
        liberty_file=liberty_file,
        output_dir=output_dir,
        mock_mode=True,
    )

    if not result.success:
        print(f"Error during handoff execution: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"   Implementation status: SUCCESS (exit code {result.return_code})")
    print(f"   Results JSON         : {result.results_json_path}\n")

    # 5. Ingest physical implementation reports
    print("5. Ingesting physical implementation measurements...")
    ingestion = ReportIngestionEngine()
    impl_report = ingestion.ingest_results_json(
        result.results_json_path,
        manifest_path=bundle['manifest_file'],
    )
    print("\n" + impl_report.summary() + "\n")

    # 6. Calibrate DSE estimates against physical implementation
    print("6. Comparing DSE estimates with physical implementation...")
    calibrator = DSECalibrator()
    calibration_report = calibrator.compare(dse_metrics, impl_report)

    # Print Markdown table report
    print("\n" + calibration_report.to_markdown() + "\n")

    # 7. Generate calibrated technology library overlay JSON
    print("7. Generating calibrated TechLibrary JSON overlay...")
    base_tech_lib = "examples/technology_libraries/example_45nm.json"
    calibrated_overlay = calibrator.generate_calibrated_tech_library(
        base_library_path_or_dict=base_tech_lib,
        calibration_report=calibration_report,
        output_path=calibrated_lib_file,
    )

    print(f"   Calibrated library written to: {calibrated_lib_file}")
    print(f"   Applied Area Scale Factor   : {calibrated_overlay['calibration_metadata']['area_scale_applied']}x")
    print(f"   Applied Power Scale Factor  : {calibrated_overlay['calibration_metadata']['power_scale_applied']}x\n")

    print("=================================================================")
    print(" End-to-end GPU-OpenLane handoff & DSE calibration successful!")
    print("=================================================================")


if __name__ == "__main__":
    main()
