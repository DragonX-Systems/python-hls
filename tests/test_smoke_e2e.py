"""
End-to-end smoke tests.

Verifies the core pipeline works: parse → IR → schedule → allocate → Verilog.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls import HLS
from python_hls.constraints import validate_semantics, check_refactor_equivalence


class TestSmokeE2E:
    """Smoke tests for the full compilation pipeline."""

    def test_simple_add_compiles(self):
        """Simplest function: a + b."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
def add(a, b):
    return a + b
""")
            path = f.name

        try:
            hls = HLS(optimization_level=1)
            result = hls.compile(path, target='verilog')
            netlist = result[0] if isinstance(result, tuple) else result

            assert netlist is not None
            assert hasattr(netlist, 'modules')
            assert 'add' in netlist.modules

            # Verify Verilog was written (default path)
            base = path.replace('.py', '')
            v_path = base + '.v'
            assert os.path.exists(v_path)
            with open(v_path) as vf:
                v = vf.read()
            assert 'module add' in v or 'module add' in v.lower()
        finally:
            os.unlink(path)
            v_path = path.replace('.py', '.v')
            if os.path.exists(v_path):
                os.unlink(v_path)

    def test_gcd_compiles(self):
        """GCD with loop compiles."""
        gcd_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'gcd.py')
        if not os.path.exists(gcd_file):
            pytest.skip("examples/gcd.py not found")

        hls = HLS(optimization_level=1)
        result = hls.compile(gcd_file, target='verilog')
        netlist = result[0] if isinstance(result, tuple) else result

        assert netlist is not None
        assert 'gcd' in netlist.modules

        metrics = hls.get_performance_metrics()
        assert 'latency_cycles' in metrics
        assert metrics['latency_cycles'] > 0

    def test_constraints_workflow(self):
        """Constraints: validate → compile with strict."""
        source = """
def compute(a, b):
    return a * b + a
"""
        violations = validate_semantics(source)
        assert len(violations) == 0

        # Refactor equivalence
        refactored = """
def compute(x, y):
    t = x * y
    return t + x
"""
        result = check_refactor_equivalence(source, refactored)
        assert result.equivalent
