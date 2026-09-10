"""
JAX ReLU Activation & Reduction Pipeline Example for Python-HLS.

Demonstrates activation (jnp.maximum) and reduction (jnp.sum)
in a JAX neural network layer kernel compiled into hardware RTL.
"""

import jax.numpy as jnp
from python_hls import HLS, jax_kernel, trace_jax_kernel


@jax_kernel(
    shapes={"x": (8,)},
    dtypes={"x": "int32"},
)
def relu_sum_pipeline(x):
    """Applies ReLU activation and computes sum reduction in JAX."""
    act = jnp.maximum(0, x)
    return jnp.sum(act)


def main():
    print("=== Python-HLS JAX ReLU + Reduction Pipeline ===")

    # 1. Trace into Jaxpr graph
    graph = trace_jax_kernel(relu_sum_pipeline)
    print("\n--- Traced Jaxpr Graph ---")
    print(graph.summary())

    # 2. Reference execution in JAX
    x = jnp.array([-10, 5, -2, 8, -1, 4, 3, -7], dtype=jnp.int32)
    expected_act = jnp.maximum(0, x)
    expected_sum = int(jnp.sum(expected_act))

    print("\nInput:", x)
    print("Expected activated:", expected_act)
    print("Expected sum:", expected_sum)

    # 3. Compile to synthesizable Verilog RTL
    hls = HLS(optimization_level=1, tech_node=45)
    output_rtl = "jax_relu_sum_pipeline.v"

    print(f"\nCompiling JAX pipeline to Verilog ({output_rtl})...")
    netlist, logs = hls.compile_jax(relu_sum_pipeline, output_file=output_rtl)

    print("Compilation successful!")


if __name__ == "__main__":
    main()
