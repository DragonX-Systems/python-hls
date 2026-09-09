"""
Integration tests for CLI commands.

Tests the command-line interface end-to-end.
"""

import os
import sys
import tempfile
import subprocess

import pytest

# Ensure we can import python_hls
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _run_cli(args):
    """Run python-hls CLI with given args. Returns (returncode, stdout, stderr)."""
    cmd = [sys.executable, '-m', 'python_hls.cli'] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=os.path.dirname(os.path.dirname(__file__)))
    return result.returncode, result.stdout, result.stderr


class TestCLICompile:
    """Test compile command."""

    def test_compile_help(self):
        """Compile command shows help."""
        code, out, err = _run_cli(['compile', '--help'])
        assert code == 0
        assert 'compile' in out.lower()
        assert 'source_file' in out or 'SOURCE_FILE' in out

    def test_compile_gcd(self):
        """Compile examples/gcd.py produces Verilog."""
        gcd_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'gcd.py')
        if not os.path.exists(gcd_file):
            pytest.skip("examples/gcd.py not found")

        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, 'gcd.v')
            code, out, err = _run_cli(['compile', gcd_file, '-o', output, '--no-visualize'])
            assert code == 0, f"stderr: {err}\nstdout: {out}"
            assert os.path.exists(output)
            with open(output) as f:
                content = f.read()
            assert 'module' in content


class TestCLIValidate:
    """Test validate command."""

    def test_validate_help(self):
        """Validate command shows help."""
        code, out, err = _run_cli(['validate', '--help'])
        assert code == 0

    def test_validate_clean_file(self):
        """Validate passes on clean HLS-compatible code."""
        gcd_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'gcd.py')
        if not os.path.exists(gcd_file):
            pytest.skip("examples/gcd.py not found")

        code, out, err = _run_cli(['validate', gcd_file])
        assert code == 0
        assert 'PASS' in out or 'pass' in out.lower()

    def test_validate_rejects_global_state(self):
        """Validate fails on global mutable state."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
counter = 0
def bad():
    global counter
    counter += 1
    return counter
""")
            path = f.name

        try:
            code, out, err = _run_cli(['validate', path])
            assert code != 0 or 'violation' in out.lower() or 'forbidden' in out.lower()
        finally:
            os.unlink(path)


class TestCLIVerifyEquivalence:
    """Test verify-equivalence command."""

    def test_verify_equivalence_help(self):
        """verify-equivalence shows help."""
        code, out, err = _run_cli(['verify-equivalence', '--help'])
        assert code == 0

    def test_verify_equivalence_identical(self):
        """Identical files are equivalent."""
        gcd_file = os.path.join(os.path.dirname(__file__), '..', 'examples', 'gcd.py')
        refactored = os.path.join(os.path.dirname(__file__), '..', 'examples', 'gcd_refactored.py')

        if not os.path.exists(gcd_file) or not os.path.exists(refactored):
            pytest.skip("gcd examples not found")

        code, out, err = _run_cli(['verify-equivalence', gcd_file, refactored])
        assert code == 0
        assert 'PASS' in out or 'equivalent' in out.lower()
