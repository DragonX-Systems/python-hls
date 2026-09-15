"""
Unit and regression test suite for representative ML, Data-Science, and Finance benchmarks.
"""

import os
import sys
import json
import tempfile
import subprocess
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from python_hls import HLS
from benchmarks.runner import BenchmarkRunner
from benchmarks.workloads import (
    load_all_workloads,
    get_workload,
    get_workloads_by_domain,
)


class TestBenchmarkSuite(unittest.TestCase):
    """Test the benchmark suite catalog, compilation, equivalence, and DSE."""

    def test_workload_discovery(self):
        """Verify all 9 workloads register correctly across ml, data_science, and finance."""
        workloads = load_all_workloads()
        self.assertEqual(len(workloads), 9)

        expected_ml = {"mlp_layer", "attention_slice", "conv1d_quant"}
        expected_ds = {"covariance_matrix", "zscore_normalize", "fir_filter_2d"}
        expected_fin = {"black_scholes_lattice", "vwap_orderbook", "portfolio_var"}

        all_keys = set(workloads.keys())
        self.assertTrue(expected_ml.issubset(all_keys))
        self.assertTrue(expected_ds.issubset(all_keys))
        self.assertTrue(expected_fin.issubset(all_keys))

        ml_workloads = get_workloads_by_domain("ml")
        self.assertEqual({w.name for w in ml_workloads}, expected_ml)

        ds_workloads = get_workloads_by_domain("data_science")
        self.assertEqual({w.name for w in ds_workloads}, expected_ds)

        fin_workloads = get_workloads_by_domain("finance")
        self.assertEqual({w.name for w in fin_workloads}, expected_fin)

    def test_workload_configs_valid(self):
        """Verify that every workload configuration has pinned metadata and test vectors."""
        workloads = load_all_workloads()
        for name, wl in workloads.items():
            self.assertTrue(os.path.exists(wl.source_file), f"Source missing: {wl.source_file}")
            self.assertGreater(len(wl.shapes), 0)
            self.assertGreater(len(wl.dtypes), 0)
            self.assertGreater(len(wl.hardware_assumptions), 0)
            self.assertGreater(len(wl.unsupported_operations), 0)
            self.assertGreater(len(wl.test_vectors), 0)
            self.assertIsNotNone(wl.reference_fn)

    def test_all_workloads_compile(self):
        """Verify that all 9 workloads compile to Verilog with python-hls."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = BenchmarkRunner(output_dir=tmp_dir)
            workloads = load_all_workloads()

            for name, wl in workloads.items():
                comp = runner._run_compilation(wl, emit_rtl=True)
                self.assertEqual(
                    comp.status, "PASS",
                    f"Compilation failed for {name}: {comp.error}"
                )
                self.assertGreater(comp.cycle_latency, 0)
                self.assertIsNotNone(comp.verilog_path)
                self.assertTrue(os.path.exists(comp.verilog_path))

    def test_all_workloads_simulation_equivalence(self):
        """Verify that all 9 workloads pass functional equivalence against reference implementations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = BenchmarkRunner(output_dir=tmp_dir)
            workloads = load_all_workloads()

            for name, wl in workloads.items():
                equiv = runner._run_equivalence(wl)
                self.assertEqual(
                    equiv.status, "PASS",
                    f"Equivalence failed for {name}: {equiv.mismatches}"
                )
                self.assertEqual(equiv.failed_vectors, 0)
                self.assertEqual(equiv.passed_vectors, len(wl.test_vectors))

    def test_dse_technology_scaling(self):
        """Verify multi-node scaling across 45nm, 28nm, 16nm, 7nm."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = BenchmarkRunner(output_dir=tmp_dir, tech_nodes=[45, 28, 16, 7])
            wl = get_workload("mlp_layer")
            self.assertIsNotNone(wl)

            ppa_by_node = runner._run_dse(wl)
            self.assertEqual(set(ppa_by_node.keys()), {45, 28, 16, 7})

            # Area must scale down with smaller tech nodes
            self.assertGreater(ppa_by_node[45].area_um2, ppa_by_node[28].area_um2)
            self.assertGreater(ppa_by_node[28].area_um2, ppa_by_node[16].area_um2)
            self.assertGreater(ppa_by_node[16].area_um2, ppa_by_node[7].area_um2)

            # Frequency must increase or stay consistent at advanced nodes
            self.assertGreaterEqual(ppa_by_node[7].frequency_mhz, ppa_by_node[45].frequency_mhz)

    def test_report_generation(self):
        """Verify JSON and Markdown report generation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = BenchmarkRunner(output_dir=tmp_dir)
            results = runner.run_suite(domain="ml", tier="dse")
            saved = runner.save_reports(results)

            self.assertTrue(os.path.exists(saved["json"]))
            self.assertTrue(os.path.exists(saved["markdown"]))

            with open(saved["json"]) as f:
                data = json.load(f)
            self.assertIn("mlp_layer", data)
            self.assertEqual(data["mlp_layer"]["compilation"]["status"], "PASS")

            with open(saved["markdown"]) as f:
                md = f.read()
            self.assertIn("Python-HLS Representative Workload Benchmarks", md)
            self.assertIn("mlp_layer", md)
            self.assertIn("45nm", md)


class TestBenchmarkCLI(unittest.TestCase):
    """Test CLI integration of benchmark commands."""

    def _run_cli(self, args):
        cmd = [sys.executable, "-m", "python_hls.cli"] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        )
        return result.returncode, result.stdout, result.stderr

    def test_cli_benchmark_help(self):
        """Verify benchmark command help message."""
        code, out, err = self._run_cli(["benchmark", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("benchmark", out.lower())
        self.assertIn("--domain", out)
        self.assertIn("--tier", out)

    def test_cli_benchmark_quick_ml(self):
        """Verify quick benchmark run for ML domain via CLI."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            code, out, err = self._run_cli([
                "benchmark",
                "--domain", "ml",
                "--tier", "quick",
                "--output-dir", tmp_dir,
            ])
            self.assertEqual(code, 0, f"CLI failed: {err}\n{out}")
            self.assertIn("mlp_layer", out)
            self.assertIn("attention_slice", out)
            self.assertIn("conv1d_quant", out)
            self.assertIn("PASS", out)

    def test_cli_benchmark_single_workload_json(self):
        """Verify JSON format output for single workload via CLI."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            code, out, err = self._run_cli([
                "benchmark",
                "--workload", "vwap_orderbook",
                "--tier", "quick",
                "--format", "json",
                "--output-dir", tmp_dir,
            ])
            self.assertEqual(code, 0, f"CLI failed: {err}\n{out}")
            # Locate JSON block in stdout
            json_start = out.find("{")
            self.assertNotEqual(json_start, -1)
            parsed = json.loads(out[json_start:])
            self.assertIn("vwap_orderbook", parsed)
            self.assertEqual(parsed["vwap_orderbook"]["compilation"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
