"""
Bounded NumPy Vector Addition Example.

Demonstrates fixed-shape, hardware-friendly NumPy vector addition
entering the Python-HLS compilation flow without writing manual loops or C++ models.
"""

import numpy as np
from python_hls import HLS, numpy_kernel


# Define a hardware-bounded kernel with fixed shapes and data types
@numpy_kernel(
    shapes={"a": (16,), "b": (16,)},
    dtypes={"a": "int32", "b": "int32"},
)
def vector_add(a, b):
    """Elementwise addition of two 16-element vectors."""
    return a + b


def main():
    print("=== Python-HLS Bounded NumPy Vector Addition ===")
    
    # 1. Functional reference execution in Python
    a_in = np.arange(16, dtype=np.int32)
    b_in = np.ones(16, dtype=np.int32) * 10
    ref_out = vector_add(a_in, b_in)
    print("NumPy Reference output:\n", ref_out)

    # 2. Compile to synthesizable Verilog hardware RTL
    hls = HLS(optimization_level=1, tech_node=45)
    output_rtl = "vector_add.v"
    
    print(f"\nCompiling vector_add to Verilog ({output_rtl})...")
    netlist, logs = hls.compile_numpy(vector_add, output_file=output_rtl)
    
    print("Compilation successful!")
    print(f"Generated module ports and registers in {output_rtl}")


if __name__ == "__main__":
    main()
