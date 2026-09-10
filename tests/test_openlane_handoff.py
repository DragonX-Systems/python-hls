"""
Unit test suite for GPU-OpenLane handoff, SDC generation, report ingestion, and DSE calibration (Issue #3).
"""

import json
import os
import shutil
import tempfile
import unittest
from click.testing import CliRunner

from python_hls import (
    HLS,
    FlowManifest,
    DesignSpec,
    TechnologySpec,
    FlowConfig,
    DSEEstimateSpec,
    SDCGenerator,
    SDCConfig,
    ReportIngestionEngine,
    ImplementationReport,
    DSECalibrator,
    CalibrationReport,
    OpenLaneRunner,
)
from python_hls.cli import main as cli_main


class TestSDCGenerator(unittest.TestCase):
    """Test SDC constraints generation and port extraction."""

    def test_sdc_default_generation(self):
        gen = SDCGenerator(SDCConfig(clock_period_ns=4.0, clock_name="clk"))
        sdc_text = gen.generate(top_module="fir_filter")

        self.assertIn("current_design fir_filter", sdc_text)
        self.assertIn("create_clock -name clk -period 4.000 [get_ports clk]", sdc_text)
        self.assertIn("set_clock_uncertainty", sdc_text)
        self.assertIn("set_clock_transition", sdc_text)
        self.assertIn("set_input_delay -clock clk 0.800", sdc_text)
        self.assertIn("set_output_delay -clock clk 0.800", sdc_text)
        self.assertIn("set_load 0.0350", sdc_text)

    def test_extract_ports_from_verilog(self):
        sample_verilog = """
        module test_dut (
            input wire clk,
            input wire rst_n,
            input wire [31:0] data_in,
            input wire valid_in,
            output reg [31:0] data_out,
            output reg ready_out
        );
            always @(posedge clk) begin
                data_out <= data_in;
            end
        endmodule
        """
        ports = SDCGenerator.extract_ports_from_verilog(sample_verilog)
        self.assertEqual(ports["clock"], "clk")
        self.assertEqual(ports["reset"], "rst_n")
        self.assertIn("data_in", ports["inputs"])
        self.assertIn("valid_in", ports["inputs"])
        self.assertIn("data_out", ports["outputs"])
        self.assertIn("ready_out", ports["outputs"])

    def test_write_sdc_file(self):
        temp_dir = tempfile.mkdtemp()
        try:
            sdc_file = os.path.join(temp_dir, "test.sdc")
            gen = SDCGenerator(SDCConfig(clock_period_ns=5.0))
            path = gen.write(sdc_file, top_module="gcd")
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("create_clock -name clk -period 5.000", content)
        finally:
            shutil.rmtree(temp_dir)


class TestFlowManifest(unittest.TestCase):
    """Test flow manifest specification, validation, and script generation."""

    def test_manifest_validation(self):
        # Incomplete manifest should flag missing fields
        man = FlowManifest()
        errors = man.validate()
        self.assertIn("design.top_module is required", errors)
        self.assertIn("design.rtl_files cannot be empty", errors)
        self.assertIn("technology.liberty_file is required", errors)

        # Complete manifest
        man.design.top_module = "gcd"
        man.design.rtl_files = ["gcd.v"]
        man.design.sdc_file = "gcd.sdc"
        man.technology.liberty_file = "sky130.lib"
        self.assertEqual(len(man.validate()), 0)

    def test_manifest_json_roundtrip(self):
        temp_dir = tempfile.mkdtemp()
        try:
            json_file = os.path.join(temp_dir, "flow_manifest.json")
            man = FlowManifest(
                design=DesignSpec(
                    top_module="dot_product",
                    rtl_files=["dot.v"],
                    sdc_file="dot.sdc",
                    target_clock_period_ns=2.5,
                    target_clock_frequency_mhz=400.0,
                ),
                technology=TechnologySpec(
                    pdk="sky130A",
                    liberty_file="sky130_fd_sc_hd__tt_025C_1v80.lib",
                    corner="tt_025C_1v80",
                    voltage=1.8,
                    temperature=25.0,
                ),
                configuration=FlowConfig(
                    stage="synthesis",
                    use_gpu=False,
                    use_mlx=True,
                    threads=4,
                ),
                dse_estimates=DSEEstimateSpec(
                    total_area_um2=1200.0,
                    total_power_mw=5.5,
                    latency_cycles=16,
                ),
            )
            saved_path = man.save(json_file)
            self.assertTrue(os.path.exists(saved_path))

            loaded = FlowManifest.load(saved_path)
            self.assertEqual(loaded.design.top_module, "dot_product")
            self.assertEqual(loaded.technology.pdk, "sky130A")
            self.assertEqual(loaded.configuration.threads, 4)
            self.assertEqual(loaded.dse_estimates.total_area_um2, 1200.0)
            self.assertFalse(loaded.configuration.use_gpu)
        finally:
            shutil.rmtree(temp_dir)

    def test_generate_shell_script(self):
        temp_dir = tempfile.mkdtemp()
        try:
            script_file = os.path.join(temp_dir, "run_openlane_handoff.sh")
            man = FlowManifest(
                design=DesignSpec(top_module="gcd", rtl_files=["gcd.v"], sdc_file="gcd.sdc"),
                technology=TechnologySpec(liberty_file="sky130.lib"),
                configuration=FlowConfig(stage="all", threads=8),
            )
            out_script = man.generate_shell_script(script_file, openlane_root="/opt/gpu-openlane")
            self.assertTrue(os.path.exists(out_script))
            self.assertTrue(os.access(out_script, os.X_OK))
            with open(out_script, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("GPU_OPENLANE_ROOT=\"/opt/gpu-openlane\"", content)
            self.assertIn("--top \"gcd\"", content)
            self.assertIn("--lib \"sky130.lib\"", content)
        finally:
            shutil.rmtree(temp_dir)


class TestReportIngestion(unittest.TestCase):
    """Test physical implementation report ingestion and metric extraction."""

    def test_ingest_results_json(self):
        temp_dir = tempfile.mkdtemp()
        try:
            results_file = os.path.join(temp_dir, "eda_results.json")
            manifest_file = os.path.join(temp_dir, "flow_manifest.json")

            manifest_payload = {
                "manifest_version": "1.0",
                "design": {"top_module": "fir_filter", "target_clock_period_ns": 4.0},
                "technology": {"pdk": "sky130A", "corner": "tt_025C_1v80", "voltage": 1.8},
            }
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_payload, f)

            results_payload = {
                "synthesis": {
                    "cells": 512,
                    "area_um2": 2450.75,
                    "critical_path_ps": 1820.0,
                    "power_mw": 11.2,
                    "status": "ok",
                },
                "pnr": {
                    "hpwl_um": 3200.0,
                    "core_utilization": 55.0,
                    "status": "ok",
                },
                "signoff": {
                    "drc_violations": 0,
                    "wns_ps": 220.0,
                    "tns_ps": 0.0,
                    "status": "ok",
                },
                "tool_versions": {
                    "synthesis": "Yosys 0.38",
                    "pnr": "OpenROAD 2.0 (Metal GPU)",
                    "sta": "OpenSTA 2.6.0",
                },
                "_total_wall_s": 35.4,
            }
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(results_payload, f)

            engine = ReportIngestionEngine()
            report = engine.ingest_results_json(results_file, manifest_path=manifest_file)

            self.assertEqual(report.design, "fir_filter")
            self.assertEqual(report.cell_count, 512)
            self.assertEqual(report.total_area_um2, 2450.75)
            self.assertEqual(report.total_power_mw, 11.2)
            self.assertEqual(report.critical_path_ps, 1820.0)
            self.assertAlmostEqual(report.critical_path_ns, 1.820, places=3)
            self.assertEqual(report.wns_ps, 220.0)
            self.assertTrue(report.timing_met)
            self.assertEqual(report.drc_violations, 0)
            self.assertEqual(report.tool_versions["synthesis"], "Yosys 0.38")
            self.assertIn("Implementation Report: fir_filter", report.summary())

            # Effective period is 4.0 - 0.220 = 3.78 ns -> Fmax ~ 264.55 MHz
            self.assertGreater(report.fmax_mhz, 250.0)
        finally:
            shutil.rmtree(temp_dir)


class TestDSECalibration(unittest.TestCase):
    """Test DSE calibration calculation, metric deltas, and calibrated tech library overlays."""

    def test_calibration_comparison_and_scaling(self):
        dse_metrics = {
            "total_area": 2000.0,
            "total_power": 10.0,
            "clock_frequency_mhz": 200.0,
            "clock_period_ns": 5.0,
        }

        impl_report = ImplementationReport(
            design="matrix_mult",
            pdk="sky130A",
            corner="tt_025C_1v80",
            total_area_um2=2400.0,  # 20% larger than DSE
            total_power_mw=12.0,    # 20% higher than DSE
            critical_path_ps=4000.0,
            wns_ps=100.0,
            clock_period_ns=5.0,
            timing_met=True,
        )

        calibrator = DSECalibrator()
        report = calibrator.compare(dse_metrics, impl_report)

        self.assertEqual(report.design, "matrix_mult")
        self.assertAlmostEqual(report.area_calibration_factor, 1.20, places=2)
        self.assertAlmostEqual(report.power_calibration_factor, 1.20, places=2)

        area_comp = report.comparisons["area"]
        self.assertEqual(area_comp.dse_estimate, 2000.0)
        self.assertEqual(area_comp.implementation_measurement, 2400.0)
        self.assertEqual(area_comp.absolute_delta, -400.0)
        self.assertAlmostEqual(area_comp.relative_error_pct, -16.666, places=2)

        markdown_text = report.to_markdown()
        self.assertIn("# DSE Calibration Report: `matrix_mult`", markdown_text)
        self.assertIn("1.200x", markdown_text)
        self.assertIn("Signoff Disclaimer", markdown_text)

        # Test calibrated TechLibrary overlay generation
        temp_dir = tempfile.mkdtemp()
        try:
            base_lib = {
                "tech_node": 45,
                "resources": [
                    {
                        "name": "Adder_32bit",
                        "area": 100.0,
                        "energy_per_op": 1.0,
                        "leakage_power": 10.0,
                    }
                ]
            }
            out_lib_path = os.path.join(temp_dir, "calibrated_lib.json")
            calibrated_lib = calibrator.generate_calibrated_tech_library(
                base_lib,
                report,
                output_path=out_lib_path,
            )

            self.assertTrue(os.path.exists(out_lib_path))
            # 100.0 * 1.20 = 120.0
            self.assertEqual(calibrated_lib["resources"][0]["area"], 120.0)
            self.assertEqual(calibrated_lib["resources"][0]["energy_per_op"], 1.2)
            self.assertEqual(calibrated_lib["resources"][0]["leakage_power"], 12.0)
            self.assertEqual(calibrated_lib["calibration_metadata"]["area_scale_applied"], 1.2)
        finally:
            shutil.rmtree(temp_dir)


class TestOpenLaneRunner(unittest.TestCase):
    """Test OpenLane runner bundle export and mock execution."""

    def test_export_bundle(self):
        temp_dir = tempfile.mkdtemp()
        try:
            manifest = FlowManifest(
                design=DesignSpec(
                    top_module="gcd",
                    rtl_files=[],
                    sdc_file=os.path.join(temp_dir, "gcd.sdc"),
                ),
                technology=TechnologySpec(liberty_file="sky130.lib"),
            )
            # Create dummy SDC
            with open(manifest.design.sdc_file, "w") as f:
                f.write("# SDC")

            runner = OpenLaneRunner()
            bundle = runner.export_bundle(manifest, output_dir=temp_dir, copy_rtl=False)

            self.assertTrue(os.path.exists(bundle["manifest_file"]))
            self.assertTrue(os.path.exists(bundle["script_file"]))
        finally:
            shutil.rmtree(temp_dir)

    def test_mock_run(self):
        temp_dir = tempfile.mkdtemp()
        try:
            sdc_path = os.path.join(temp_dir, "test.sdc")
            with open(sdc_path, "w") as f:
                f.write("# SDC")

            manifest = FlowManifest(
                design=DesignSpec(
                    top_module="test_mod",
                    rtl_files=[],
                    sdc_file=sdc_path,
                    target_clock_period_ns=5.0,
                ),
                technology=TechnologySpec(liberty_file="sky130.lib"),
                dse_estimates=DSEEstimateSpec(total_area_um2=1000.0, total_power_mw=5.0),
            )

            runner = OpenLaneRunner()
            result = runner.run(manifest, output_dir=temp_dir, mock_mode=True)

            self.assertTrue(result.success)
            self.assertEqual(result.return_code, 0)
            self.assertIsNotNone(result.results_json_path)
            self.assertTrue(os.path.exists(result.results_json_path))

            with open(result.results_json_path, "r", encoding="utf-8") as f:
                res_data = json.load(f)
            self.assertIn("synthesis", res_data)
            self.assertIn("pnr", res_data)
            self.assertIn("signoff", res_data)
        finally:
            shutil.rmtree(temp_dir)


class TestEndToEndHandoffIntegration(unittest.TestCase):
    """Test full integration from HLS class methods."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_file = os.path.join(self.temp_dir, "gcd_simple.py")
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("""
def gcd_simple(a: int, b: int) -> int:
    while b != 0:
        a, b = b, a % b
    return a
""")
        self.liberty_file = "examples/technology_libraries/sky130_sample.lib"

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_export_and_mock_handoff(self):
        hls = HLS(tech_node=45)
        handoff_dir = os.path.join(self.temp_dir, "handoff")

        # 1. Export
        bundle = hls.export_openlane_handoff(
            source_file=self.source_file,
            liberty_file=self.liberty_file,
            output_dir=handoff_dir,
            clock_period_ns=4.0,
        )
        self.assertTrue(os.path.exists(bundle["manifest_file"]))
        self.assertTrue(os.path.exists(bundle["script_file"]))
        self.assertTrue(os.path.exists(bundle["sdc_file"]))

        # 2. Run mock
        result = hls.run_openlane_handoff(
            source_file=self.source_file,
            liberty_file=self.liberty_file,
            output_dir=handoff_dir,
            mock_mode=True,
        )
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.results_json_path))

        # 3. Calibrate
        calibrated_lib = os.path.join(self.temp_dir, "calibrated.json")
        cal_report = hls.calibrate_dse(
            source_file=self.source_file,
            implementation_results_or_dir=result.results_json_path,
            save_calibrated_tech_library=calibrated_lib,
        )
        self.assertEqual(cal_report.design, "gcd_simple")
        self.assertTrue(os.path.exists(calibrated_lib))
        self.assertIn("area", cal_report.comparisons)
        self.assertIn("power", cal_report.comparisons)
        self.assertEqual(cal_report.comparisons["area"].metric_name, "Total Area")


class TestCLIIntegration(unittest.TestCase):
    """Test CLI commands for openlane-handoff and calibrate-dse."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_file = os.path.join(self.temp_dir, "min_add.py")
        with open(self.source_file, "w", encoding="utf-8") as f:
            f.write("""
def min_add(a: int, b: int) -> int:
    return a + b
""")
        self.liberty_file = "examples/technology_libraries/sky130_sample.lib"
        self.runner = CliRunner()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_cli_openlane_handoff_export(self):
        out_dir = os.path.join(self.temp_dir, "cli_export")
        result = self.runner.invoke(cli_main, [
            "openlane-handoff",
            self.source_file,
            "-l", self.liberty_file,
            "-o", out_dir,
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Exported GPU-OpenLane handoff bundle", result.output)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "flow_manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "run_openlane_handoff.sh")))

    def test_cli_openlane_handoff_mock_and_calibrate(self):
        out_dir = os.path.join(self.temp_dir, "cli_mock")
        cal_lib = os.path.join(self.temp_dir, "cal_tech.json")
        result = self.runner.invoke(cli_main, [
            "openlane-handoff",
            self.source_file,
            "-l", self.liberty_file,
            "-o", out_dir,
            "--mock",
            "--save-calibrated-lib", cal_lib,
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Physical implementation finished successfully", result.output)
        self.assertIn("DSE Calibration Report", result.output)
        self.assertTrue(os.path.exists(cal_lib))

    def test_cli_calibrate_dse_standalone(self):
        out_dir = os.path.join(self.temp_dir, "cli_cal")
        # First run handoff mock
        self.runner.invoke(cli_main, [
            "openlane-handoff",
            self.source_file,
            "-l", self.liberty_file,
            "-o", out_dir,
            "--mock",
        ])
        results_json = os.path.join(out_dir, "eda_results.json")
        report_md = os.path.join(out_dir, "report.md")

        result = self.runner.invoke(cli_main, [
            "calibrate-dse",
            self.source_file,
            "-r", results_json,
            "--report-output", report_md,
        ])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("DSE Calibration Report", result.output)
        self.assertTrue(os.path.exists(report_md))


if __name__ == "__main__":
    unittest.main()
