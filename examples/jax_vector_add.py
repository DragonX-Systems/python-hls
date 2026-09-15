"""
JAX Vector Addition Kernel Example for Python-HLS.

Demonstrates tracing a statically bounded JAX function into a Jaxpr graph
and compiling it directly into synthesizable Verilog hardware RTL.
"""

import jax.numpy as jnp
from python_hls import HLS, jax_kernel, trace_jax_kernel


@jax_kernel(
    shapes={"a": (16,), "b": (16,)},
    dtypes={"a": "int32", "b": "int32"},
)
def vector_add(a, b):
    """Elementwise addition of two 16-element vectors."""
    return a + b


def main():
    print("=== Python-HLS JAX Vector Addition ===")

    # 1. Trace the kernel into an inspectable Jaxpr graph
    graph = trace_jax_kernel(vector_add)
    print("\n--- Traced Jaxpr Graph ---")
    print(graph.summary())

    # 2. Functional reference execution in Python/JAX
    a_in = jnp.arange(16, dtype=jnp.int32)
    b_in = jnp.ones(16, dtype=jnp.int32) * 10
    ref_out = vector_add(a_in, b_in)
    print("\nJAX Reference output:\n", ref_out)

    # 3. Compile to synthesizable Verilog RTL
    hls = HLS(optimization_level=1, tech_node=45)
    output_rtl = "jax_vector_add.v"

    print(f"\nCompiling JAX kernel to Verilog ({output_rtl})...")
    netlist, logs = hls.compile_jax(vector_add, output_file=output_rtl)

    print("Compilation successful!")
    print(f"Generated module ports and registers in {output_rtl}")


if __name__ == "__main__":
    main()
