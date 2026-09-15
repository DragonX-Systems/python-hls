"""
Comprehensive regression tests for constraint-driven hardware pipelines
and standard interfaces in Python-HLS.

Covers Issue #8:
- Initiation interval (II >= 1) targets and cycle-accurate pacing
- Backpressure stalls with zero dropped or duplicate transactions
- Bubble propagation without spurious output assertion
- Drain semantics and pipeline_empty verification
- Standard interfaces: AXI4-Stream (axis), Ready-Valid (ready_valid), Memory (memory)
- Verilator co-simulation and CLI commands
"""

import os
import sys
import tempfile
import pytest
from typing import Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python_hls import HLS
from python_hls.pipeline import (
    PipelineSpec,
    PipelineInterfaceType,
    PipelineVerilogGenerator,
    PipelineVerifier,
    PipelineVerificationResult,
    PipelineCycleSimulator,
    pipeline,
    get_pipeline_spec,
    clear_pipeline_specs,
)
from python_hls.constraints.latency import (
    parse_latency_pragma,
    extract_latency_constraints_from_source,
    LatencyConstraint,
)


class TestPipelineSpec:
    """Tests for PipelineSpec dataclass and @pipeline decorator."""

    def setup_method(self):
        clear_pipeline_specs()

    def test_pipeline_spec_defaults_and_validation(self):
        spec = PipelineSpec()
        assert spec.ii == 1
        assert spec.depth == 2
        assert spec.interface == PipelineInterfaceType.AXIS
        assert spec.data_width == 32
        assert spec.enable_stall is True
        assert spec.enable_drain is True
        assert spec.enable_bubbles is True

        # Validation checks
        with pytest.raises(ValueError, match="Initiation interval"):
            PipelineSpec(ii=0)
        with pytest.raises(ValueError, match="Pipeline depth"):
            PipelineSpec(depth=0)
        with pytest.raises(ValueError, match="Unknown interface"):
            PipelineSpec(interface="unsupported_interface")

    def test_pipeline_spec_serialization(self):
        spec = PipelineSpec(ii=2, depth=4, interface="ready_valid", data_width=64)
        data = spec.to_dict()
        assert data["ii"] == 2
        assert data["depth"] == 4
        assert data["interface"] == "ready_valid"
        assert data["data_width"] == 64

        restored = PipelineSpec.from_dict(data)
        assert restored.ii == spec.ii
        assert restored.depth == spec.depth
        assert restored.interface == spec.interface
        assert restored.data_width == spec.data_width

    def test_pipeline_decorator(self):
        @pipeline(ii=2, depth=3, interface="ready_valid")
        def acc_lane(a: int, b: int) -> int:
            return a + b

        spec = get_pipeline_spec("acc_lane")
        assert spec is not None
        assert spec.ii == 2
        assert spec.depth == 3
        assert spec.interface == PipelineInterfaceType.READY_VALID
        assert getattr(acc_lane, "_hls_pipeline_spec", None) is spec


class TestPipelinePragmaParsing:
    """Tests for parsing pipeline and interface pragmas from comments and source."""

    def test_parse_pipeline_pragma_extended(self):
        pragma_str = "# pragma hls pipeline ii=2 depth=4 interface=axis"
        constraint = parse_latency_pragma(pragma_str)
        assert constraint is not None
        assert constraint.pipeline_ii == 2
        assert constraint.pipeline_depth == 4
        assert constraint.interface == "axis"

    def test_parse_interface_pragma_alone(self):
        pragma_str = "# pragma hls interface mode=memory"
        constraint = parse_latency_pragma(pragma_str)
        assert constraint is not None
        assert constraint.interface == "memory"

    def test_extract_pipeline_constraints_from_source(self):
        src = """
# pragma hls pipeline ii=1 depth=3 interface=ready_valid
def stream_kernel(x):
    return x * 2
"""
        constraints = extract_latency_constraints_from_source(src)
        assert "stream_kernel" in constraints
        c = constraints["stream_kernel"]
        assert c.pipeline_ii == 1
        assert c.pipeline_depth == 3
        assert c.interface == "ready_valid"


class TestPipelineVerilogGenerator:
    """Tests for synthesizable Verilog code generation."""

    def test_generate_axis_pipeline(self):
        src = """
def mac(a, b, c):
    return a * b + c
"""
        gen = PipelineVerilogGenerator(PipelineSpec(ii=1, depth=2, interface="axis"))
        verilog = gen.generate_from_source(src, "mac")

        assert "module mac" in verilog
        assert "s_axis_tdata" in verilog
        assert "s_axis_tvalid" in verilog
        assert "s_axis_tready" in verilog
        assert "m_axis_tdata" in verilog
        assert "m_axis_tvalid" in verilog
        assert "m_axis_tready" in verilog
        assert "pipeline_empty" in verilog
        assert "pipeline_busy" in verilog
        assert "pipe_stall = stage_valid[PIPELINE_DEPTH-1] && !lane_out_ready" in verilog
        assert "reg_s0_c_pipe_0" in verilog

    def test_generate_ready_valid_pipeline(self):
        src = """
def multiply_lane(x, y):
    return x * y
"""
        gen = PipelineVerilogGenerator(PipelineSpec(ii=2, depth=3, interface="ready_valid"))
        verilog = gen.generate_from_source(src, "multiply_lane")

        assert "module multiply_lane" in verilog
        assert "in_data" in verilog
        assert "in_valid" in verilog
        assert "in_ready" in verilog
        assert "out_data" in verilog
        assert "out_valid" in verilog
        assert "out_ready" in verilog
        assert "ii_counter" in verilog

    def test_generate_memory_pipeline(self):
        src = """
def mem_op(addr, wdata):
    return addr + wdata
"""
        gen = PipelineVerilogGenerator(PipelineSpec(ii=1, depth=2, interface="memory"))
        verilog = gen.generate_from_source(src, "mem_op")

        assert "module mem_op" in verilog
        assert "mem_req" in verilog
        assert "mem_ready" in verilog
        assert "mem_we" in verilog
        assert "mem_addr" in verilog
        assert "mem_wdata" in verilog
        assert "mem_rdata" in verilog
        assert "mem_rvalid" in verilog
        assert "mem_resp_ready" in verilog


class TestPipelineCycleSimulation:
    """Tests for pure Python cycle-accurate pipeline simulation."""

    def test_sustained_throughput_ii1(self):
        def adder(a, b):
            return a + b

        sim = PipelineCycleSimulator(adder, PipelineSpec(ii=1, depth=2))
        vectors = [(i, i * 2) for i in range(10)]
        res = sim.run_simulation(vectors)

        assert res["total_sent"] == 10
        assert res["total_received"] == 10
        assert res["stalled_cycles"] == 0
        assert res["pipeline_empty"] is True
        assert res["measured_ii"] == 1.0
        # Verify outputs match
        for idx, (_, data) in enumerate(res["received_items"]):
            assert data == vectors[idx][0] + vectors[idx][1]

    def test_throttled_throughput_ii2(self):
        def adder(a, b):
            return a + b

        sim = PipelineCycleSimulator(adder, PipelineSpec(ii=2, depth=3))
        vectors = [(i, i * 2) for i in range(10)]
        res = sim.run_simulation(vectors)

        assert res["total_sent"] == 10
        assert res["total_received"] == 10
        assert res["measured_ii"] == 2.0
        assert res["pipeline_empty"] is True

    def test_backpressure_stalls_without_loss(self):
        def adder(a, b):
            return a + b

        sim = PipelineCycleSimulator(adder, PipelineSpec(ii=1, depth=2))
        vectors = [(i, i * 2) for i in range(15)]
        # Downstream stalls periodically: ready for 2 cycles, stalled for 2 cycles
        stall_pattern = [True, True, False, False]
        res = sim.run_simulation(vectors, downstream_ready_pattern=stall_pattern)

        assert res["total_sent"] == 15
        assert res["total_received"] == 15
        assert res["stalled_cycles"] > 0
        assert res["pipeline_empty"] is True
        # Verify exact output sequence preserved
        for idx, (_, data) in enumerate(res["received_items"]):
            assert data == vectors[idx][0] + vectors[idx][1]

    def test_bubble_propagation_cleanliness(self):
        def adder(a, b):
            return a + b

        sim = PipelineCycleSimulator(adder, PipelineSpec(ii=1, depth=2))
        vectors = [(i, i + 5) for i in range(5)]
        # Upstream only valid every 3 cycles (injecting bubbles)
        bubble_pattern = [True, False, False]
        res = sim.run_simulation(vectors, upstream_valid_pattern=bubble_pattern)

        assert res["total_sent"] == 5
        assert res["total_received"] == 5
        assert res["bubble_cycles"] > 0
        assert res["pipeline_empty"] is True
        for idx, (_, data) in enumerate(res["received_items"]):
            assert data == vectors[idx][0] + vectors[idx][1]


class TestPipelineVerilatorCoSimulation:
    """Verilator co-simulation and protocol tests."""

    @pytest.fixture(autouse=True)
    def check_verilator(self):
        verifier = PipelineVerifier()
        if not verifier.verilator_available:
            pytest.skip("Verilator is not installed or available in PATH")

    def test_axis_pipeline_cosmo_ii1(self):
        src = """
def add_lane(a, b):
    return a + b
"""
        def add_lane(a: int, b: int) -> int:
            return a + b

        verifier = PipelineVerifier()
        res = verifier.verify_pipeline(
            add_lane,
            PipelineSpec(ii=1, depth=2, interface="axis"),
            source=src,
            test_stalls=True,
            test_bubbles=True
        )
        assert res.passed is True
        assert res.mismatches == 0
        assert res.total_transactions_received == res.total_transactions_sent
        assert res.drained_cleanly is True

    def test_axis_pipeline_cosmo_ii2_sustained(self):
        src = """
def add_lane(a, b):
    return a + b
"""
        def add_lane(a: int, b: int) -> int:
            return a + b

        verifier = PipelineVerifier()
        res = verifier.verify_pipeline(
            add_lane,
            PipelineSpec(ii=2, depth=3, interface="axis"),
            source=src,
            test_stalls=False,
            test_bubbles=False
        )
        assert res.passed is True
        assert res.mismatches == 0
        assert res.measured_ii == 2.0
        assert res.drained_cleanly is True

    def test_ready_valid_interface_cosmo(self):
        src = """
def mul_lane(a, b):
    return a * b
"""
        def mul_lane(a: int, b: int) -> int:
            return a * b

        verifier = PipelineVerifier()
        res = verifier.verify_pipeline(
            mul_lane,
            PipelineSpec(ii=1, depth=2, interface="ready_valid"),
            source=src,
            test_stalls=True,
            test_bubbles=True
        )
        assert res.passed is True
        assert res.mismatches == 0
        assert res.interface == "ready_valid"
        assert res.drained_cleanly is True

    def test_memory_interface_cosmo(self):
        src = """
def mem_lane(addr, wdata):
    return addr + wdata
"""
        def mem_lane(addr: int, wdata: int) -> int:
            return addr + wdata

        verifier = PipelineVerifier()
        res = verifier.verify_pipeline(
            mem_lane,
            PipelineSpec(ii=1, depth=2, interface="memory"),
            source=src,
            test_stalls=True,
            test_bubbles=True
        )
        assert res.passed is True
        assert res.mismatches == 0
        assert res.interface == "memory"
        assert res.drained_cleanly is True

    def test_three_arg_fir_tap_cosmo(self):
        src = """
def fir_tap(x, c, acc):
    return acc + (x * c)
"""
        def fir_tap(x: int, c: int, acc: int) -> int:
            return acc + (x * c)

        verifier = PipelineVerifier()
        res = verifier.verify_pipeline(
            fir_tap,
            PipelineSpec(ii=1, depth=2, interface="axis"),
            source=src,
            test_stalls=True,
            test_bubbles=True
        )
        assert res.passed is True
        assert res.mismatches == 0
        assert res.total_transactions_received == res.total_transactions_sent
        assert res.drained_cleanly is True


class TestPipelineCLIAndHLSAPI:
    """Tests for HLS compile_pipeline / verify_pipeline APIs and CLI commands."""

    def test_hls_compile_and_verify_pipeline_api(self):
        hls = HLS()
        code = """
def scale(x):
    return x * 3
"""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(code)
            path = f.name

        try:
            verilog = hls.compile_pipeline(path, ii=1, depth=2, interface="axis")
            assert "module scale" in verilog
            assert "s_axis_tdata" in verilog

            res = hls.verify_pipeline(path, ii=1, depth=2, interface="axis")
            assert res.passed is True
            assert res.total_transactions_received == 20
        finally:
            if os.path.exists(path):
                os.remove(path)
