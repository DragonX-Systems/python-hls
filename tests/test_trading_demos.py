"""
Test that trading demo kernels compile and produce RTL.
CI gate: ensures demos stay working.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS


DEMOS_DIR = os.path.join(os.path.dirname(__file__), '..', 'demos', 'trading')
TIER1_KERNELS = ['gcd', 'fir_filter', 'dot_product', 'matrix_multiply_simple', 'ema']
TIER2_KERNELS = ['macd', 'rsi', 'fft']
TIER3_KERNELS = ['covariance', 'bellman_ford']


class TestTradingDemos(unittest.TestCase):
    """Verify Tier 1, 2, and 3 trading kernels compile."""

    def _compile_demo(self, name: str):
        """Compile a demo kernel and return (netlist, metrics)."""
        path = os.path.join(DEMOS_DIR, f'{name}.py')
        self.assertTrue(os.path.exists(path), f"Demo {path} not found")
        hls = HLS(optimization_level=1, tech_node=45)
        result = hls.compile(path, target='verilog')
        netlist = result[0] if isinstance(result, tuple) else result
        metrics = hls.get_performance_metrics()
        return netlist, metrics

    def test_gcd_compiles(self):
        """GCD: control flow, equivalence demo."""
        netlist, metrics = self._compile_demo('gcd')
        self.assertIsNotNone(netlist)
        self.assertIn('gcd', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_fir_filter_compiles(self):
        """FIR filter: signal pipelines."""
        netlist, metrics = self._compile_demo('fir_filter')
        self.assertIsNotNone(netlist)
        self.assertIn('fir_filter', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_dot_product_compiles(self):
        """Dot product: latency-critical tick path."""
        netlist, metrics = self._compile_demo('dot_product')
        self.assertIsNotNone(netlist)
        self.assertIn('dot_product', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_matrix_multiply_simple_compiles(self):
        """Matrix multiply: linear algebra, factor models."""
        netlist, metrics = self._compile_demo('matrix_multiply_simple')
        self.assertIsNotNone(netlist)
        self.assertIn('matrix_multiply_simple', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_ema_compiles(self):
        """EMA: technical indicator building block."""
        netlist, metrics = self._compile_demo('ema')
        self.assertIsNotNone(netlist)
        self.assertIn('ema_update', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_macd_compiles(self):
        """MACD: momentum indicator."""
        netlist, metrics = self._compile_demo('macd')
        self.assertIsNotNone(netlist)
        self.assertIn('macd_update', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_rsi_compiles(self):
        """RSI: relative strength index."""
        netlist, metrics = self._compile_demo('rsi')
        self.assertIsNotNone(netlist)
        self.assertIn('rsi_update', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_fft_compiles(self):
        """FFT: spectral analysis, cycle detection."""
        netlist, metrics = self._compile_demo('fft')
        self.assertIsNotNone(netlist)
        self.assertIn('fft_32_point', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_covariance_compiles(self):
        """Covariance: portfolio risk, factor models."""
        netlist, metrics = self._compile_demo('covariance')
        self.assertIsNotNone(netlist)
        self.assertIn('covariance_8', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)

    def test_bellman_ford_compiles(self):
        """Bellman-Ford: arbitrage detection, shortest path."""
        netlist, metrics = self._compile_demo('bellman_ford')
        self.assertIsNotNone(netlist)
        self.assertIn('bellman_ford_4', netlist.modules)
        self.assertGreaterEqual(metrics['total_area'], 0)


if __name__ == '__main__':
    unittest.main()
