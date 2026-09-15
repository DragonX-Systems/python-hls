"""
Example: Lowering and synthesizing a PyTorch Linear + ReLU module to Verilog RTL.

Usage:
    python -m python_hls.cli compile-torch examples/pytorch_linear_relu.py --input-shapes "4" -o linear_relu.v
    python examples/pytorch_linear_relu.py
"""

import torch
import torch.nn as nn
from python_hls.frontend.torch_fx import trace_torch_model, lower_torch_model, compile_torch_model


class LinearReLU(nn.Module):
    """Simple Linear layer followed by ReLU activation."""

    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(4, 2)
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.fc(x))


# Export model instance for CLI compile-torch
model = LinearReLU()


def main():
    print("1. Creating PyTorch LinearReLU model...")
    m = LinearReLU().eval()
    example_input = torch.tensor([1.0, 2.0, -1.0, 3.0])

    print("2. Tracing and Lowering PyTorch FX graph...")
    lowered_code, fx_graph = lower_torch_model(m, [example_input], embed_weights=True)
    print("\n--- Lowered Synthesizable Python Code ---")
    print(lowered_code)
    print("-----------------------------------------\n")

    print("3. Compiling lowered model to Verilog RTL...")
    netlist, _ = compile_torch_model(
        m,
        [example_input],
        target="verilog",
        output_file="linear_relu.v",
        embed_weights=True,
    )
    print("✅ Successfully generated linear_relu.v!")
    print(f"Modules synthesized: {list(netlist.modules.keys())}")


if __name__ == "__main__":
    main()
