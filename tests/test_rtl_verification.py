"""
RTL verification tests. Run when Verilator is installed.
Compares Python execution vs Verilator simulation of generated Verilog.
"""

import os
import sys
import tempfile
import unittest
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS
from python_hls.verification.exceptions import (
    RTLVerificationError,
    RTLVerificationInterfaceError,
    RTLSimulationTimeoutError,
    RTLMismatchError
)


class TestRTLVerification(unittest.TestCase):
    """Verify RTL matches Python for key kernels and testbench qualification."""

    def _verify_demo(self, path: str, test_vectors: list = None, seed: int = 42, max_cycles: int = 1000) -> dict:
        """Compile and verify RTL. Returns verification result."""
        hls = HLS(optimization_level=1, tech_node=45)
        hls.compile(path, target='verilog')
        return hls.verify_rtl(
            test_vectors=test_vectors,
            seed=seed,
            max_cycles=max_cycles,
            save_report=False
        )

    def test_gcd_rtl_matches_python(self):
        """GCD Verilog produces same output as Python across while-loop iterations."""
        path = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading', 'gcd.py')
        vr = self._verify_demo(path, [{'a': 48, 'b': 18}, {'a': 12, 'b': 8}, {'a': 7, 'b': 5}])
        if vr.get('error') and 'Verilator' in vr.get('error', ''):
            self.skipTest("Verilator not available")
        results = vr.get('verification_results', {})
        mod_result = results.get('gcd', {})
        comp = mod_result.get('comparison', {})
        self.assertEqual(comp.get('failed', 1), 0, f"RTL mismatches: {comp.get('mismatches')}")
        self.assertGreaterEqual(comp.get('passed', 0), 1)

    def test_ema_rtl_matches_python(self):
        """EMA Verilog produces same output as Python across sequential arithmetic."""
        path = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading', 'ema.py')
        vr = self._verify_demo(path, [{'y_prev': 100, 'x': 110, 'alpha': 1}, {'y_prev': 50, 'x': 50, 'alpha': 0}])
        if vr.get('error') and 'Verilator' in vr.get('error', ''):
            self.skipTest("Verilator not available")
        results = vr.get('verification_results', {})
        mod_result = results.get('ema_update', {})
        comp = mod_result.get('comparison', {})
        self.assertEqual(comp.get('failed', 1), 0, f"RTL mismatches: {comp.get('mismatches')}")
        self.assertGreaterEqual(comp.get('passed', 0), 1)

    def test_deterministic_test_vectors(self):
        """Identical seeds produce identical test vectors and reproducible verification."""
        path = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading', 'gcd.py')
        hls1 = HLS()
        hls1.compile(path, target='verilog')
        vr1 = hls1.verify_rtl(num_random_tests=5, seed=12345, save_report=False)

        if vr1.get('error') and 'Verilator' in vr1.get('error', ''):
            self.skipTest("Verilator not available")

        hls2 = HLS()
        hls2.compile(path, target='verilog')
        vr2 = hls2.verify_rtl(num_random_tests=5, seed=12345, save_report=False)

        vecs1 = vr1['verification_results']['gcd']['test_vectors']
        vecs2 = vr2['verification_results']['gcd']['test_vectors']
        self.assertEqual(vecs1, vecs2, "Test vectors should match identically for the same seed")

    def test_corner_cases(self):
        """Verify handling of boundary conditions: 0, 1, and limits."""
        path = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading', 'ema.py')
        hls = HLS()
        hls.compile(path, target='verilog')
        corner_vectors = [
            {'y_prev': 0, 'x': 0, 'alpha': 0},
            {'y_prev': 1, 'x': 1, 'alpha': 1},
            {'y_prev': 1000, 'x': 500, 'alpha': 1},
        ]
        vr = hls.verify_rtl(test_vectors=corner_vectors, strict=True, save_report=False)
        comp = vr['verification_results']['ema_update']['comparison']
        self.assertEqual(comp['passed'], len(corner_vectors))
        self.assertEqual(comp['failed'], 0)

    def test_unsupported_interface_diagnostic(self):
        """Functions with multi-value returns emit explicit RTLVerificationInterfaceError."""
        code = """def multi_ret(a: int, b: int):
    return a + 1, b + 1
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            src_path = f.name

        try:
            hls = HLS()
            hls.compile(src_path, target='verilog')
            with self.assertRaises(RTLVerificationInterfaceError) as ctx:
                hls.verify_rtl(strict=True, save_report=False)
            self.assertIn("multi-value return", str(ctx.exception))
        finally:
            if os.path.exists(src_path):
                os.remove(src_path)

    def test_vcd_and_artifact_generation(self):
        """Verification preserves artifacts: .v, .cpp, binary, VCD waveform, and report."""
        path = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading', 'gcd.py')
        hls = HLS()
        hls.compile(path, target='verilog')

        with tempfile.TemporaryDirectory() as art_dir:
            vr = hls.verify_rtl(
                num_random_tests=3,
                seed=42,
                vcd=True,
                artifact_dir=art_dir,
                save_report=True
            )
            if vr.get('error') and 'Verilator' in vr.get('error', ''):
                self.skipTest("Verilator not available")

            # Check preserved files
            files = os.listdir(art_dir)
            self.assertTrue(any(f.endswith('.v') for f in files), f"Verilog not in {files}")
            self.assertTrue(any(f.endswith('.cpp') for f in files), f"C++ testbench not in {files}")
            self.assertTrue(any(f.endswith('.vcd') for f in files), f"VCD waveform not in {files}")
            self.assertTrue(any(f.startswith('V') for f in files), f"Simulation binary not in {files}")
            self.assertIn('verification_report.txt', files)
            self.assertIn('test_vectors.json', files)

    def test_simulation_timeout_diagnostic(self):
        """Exceeding max_cycles marks timeout and reports actionable failure."""
        path = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading', 'gcd.py')
        hls = HLS()
        hls.compile(path, target='verilog')

        # Run with max_cycles=1 (insufficient for GCD while loop)
        vr = hls.verify_rtl(
            test_vectors=[{'a': 48, 'b': 18}],
            max_cycles=1,
            strict=False,
            save_report=False
        )
        if vr.get('error') and 'Verilator' in vr.get('error', ''):
            self.skipTest("Verilator not available")

        comp = vr['verification_results']['gcd']['comparison']
        self.assertGreater(comp['timeouts'], 0)
        self.assertEqual(comp['failed'], 1)
        self.assertIn("TIMEOUT", comp['mismatches'][0]['rtl_result'])

    def test_cli_verify_rtl(self):
        """CLI verify-rtl executes cleanly with return code 0."""
        path = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading', 'gcd.py')
        cmd = [
            sys.executable, "-m", "python_hls.cli", "verify-rtl",
            path, "-n", "3", "--seed", "42", "--strict"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if "Verilator not available" in result.stderr:
            self.skipTest("Verilator not available")
        self.assertEqual(result.returncode, 0, f"CLI stderr: {result.stderr}\nstdout: {result.stdout}")
        self.assertIn("ALL RTL VERIFICATION CHECKS PASSED", result.stdout)


if __name__ == '__main__':
    unittest.main()
