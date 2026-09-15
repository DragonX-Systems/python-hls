"""
Example: Constraint-Driven Streaming MAC Accelerator Lane.

Demonstrates:
- Pipelined accelerator lane generation with Initiation Interval (II=1)
- Standard AMBA AXI4-Stream slave and master interface
- Verilator co-simulation testing sustained throughput, backpressure stalls, and bubble propagation
"""

from python_hls import HLS
from python_hls.pipeline import pipeline, PipelineSpec, PipelineInterfaceType


# Define a pipelined MAC kernel using @pipeline decorator
@pipeline(ii=1, depth=3, interface=PipelineInterfaceType.AXIS)
def mac_lane(a: int, b: int, c: int) -> int:
    return a * b + c


def main():
    print("=== Python-HLS Constraint-Driven Pipeline Demonstration ===")
    hls = HLS()

    # 1. Compile to synthesizable Verilog
    print("\n[1] Compiling 'mac_lane' to synthesizable AXI4-Stream Verilog...")
    verilog = hls.compile_pipeline(
        source=mac_lane,
        ii=1,
        depth=3,
        interface="axis",
        output_file="mac_lane_axis.v"
    )
    print("Generated synthesizable Verilog written to 'mac_lane_axis.v'")

    # 2. Co-simulate and verify with Verilator
    print("\n[2] Running Verilator co-simulation with backpressure stalls and bubbles...")
    result = hls.verify_pipeline(
        source=mac_lane,
        ii=1,
        depth=3,
        interface="axis",
        test_stalls=True,
        test_bubbles=True
    )

    print(f"\nVerification Results:")
    print(f"  Passed: {result.passed}")
    print(f"  Interface: {result.interface.upper()}")
    print(f"  Target II: {result.target_ii}, Measured II: {result.measured_ii:.2f}")
    print(f"  Transactions Sent/Received: {result.total_transactions_sent}/{result.total_transactions_received}")
    print(f"  Mismatches: {result.mismatches}")
    print(f"  Stalls Tested: {result.stalls_tested}")
    print(f"  Bubbles Tested: {result.bubbles_tested}")
    print(f"  Drained Cleanly: {result.drained_cleanly}")

    if result.passed:
        print("\nSUCCESS: All pipeline protocol and equivalence checks passed!")
    else:
        print(f"\nFAILURE: {result.error_message}")


if __name__ == "__main__":
    main()
