"""
Bounded NumPy ReLU and Reduction Pipeline Example.

Demonstrates activation functions (ReLU via np.maximum) and
reductions (np.sum) lowered to synthesizable hardware datapath pipelines.
"""

import numpy as np
from python_hls import HLS, numpy_kernel


@numpy_kernel(
    shapes={"x": (8,)},
    dtypes={"x": "int32"},
)
def relu_sum_pipeline(x):
    """
    Applies ReLU activation (maximum with 0) and computes sum reduction.
    """
    activated = np.maximum(0, x)
    return np.sum(activated)


def main():
    print("=== Python-HLS Bounded NumPy ReLU + Reduction Pipeline ===")
    
    # Reference NumPy execution
    x = np.array([-10, 5, -2, 8, -1, 4, 3, -7], dtype=np.int32)
    expected_act = np.maximum(0, x)
    expected_sum = int(np.sum(expected_act))
    
    print("Input:", x)
    print("Expected activated:", expected_act)
    print("Expected sum:", expected_sum)

    # Compile to Verilog
    hls = HLS(optimization_level=1, tech_node=45)
    output_rtl = "relu_sum_pipeline.v"
    
    print(f"\nCompiling relu_sum_pipeline to Verilog ({output_rtl})...")
    netlist, logs = hls.compile_numpy(relu_sum_pipeline, output_file=output_rtl)
    print("Compilation successful!")


if __name__ == "__main__":
    main()
