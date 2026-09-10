"""
JAX Matrix Multiplication Kernel Example for Python-HLS.

Demonstrates 2D matrix multiplication using jnp.matmul, tracing through
Jaxpr dot_general equations, and compiling into hardware RTL.
"""

import jax.numpy as jnp
from python_hls import HLS, jax_kernel, trace_jax_kernel


@jax_kernel(
    shapes={"a": (4, 4), "b": (4, 4)},
    dtypes={"a": "int32", "b": "int32"},
)
def matrix_multiply(a, b):
    """Compute C = A @ B for 4x4 integer matrices in JAX."""
    return jnp.matmul(a, b)


def main():
    print("=== Python-HLS JAX Matrix Multiplication ===")

    # 1. Trace into Jaxpr graph
    graph = trace_jax_kernel(matrix_multiply)
    print("\n--- Traced Jaxpr Graph ---")
    print(graph.summary())

    # 2. Reference execution in JAX
    a = jnp.array([[1, 0, 2, 0],
                   [0, 3, 0, 4],
                   [0, 0, 5, 0],
                   [6, 0, 0, 7]], dtype=jnp.int32)
    b = jnp.eye(4, dtype=jnp.int32) * 2

    expected = jnp.matmul(a, b)
    print("\nJAX Reference A @ B:\n", expected)

    # 3. Compile to synthesizable Verilog RTL
    hls = HLS(optimization_level=1, tech_node=45)
    output_rtl = "jax_matmul_4x4.v"

    print(f"\nCompiling JAX matmul to Verilog ({output_rtl})...")
    netlist, logs = hls.compile_jax(matrix_multiply, output_file=output_rtl)

    print("Compilation successful!")


if __name__ == "__main__":
    main()
