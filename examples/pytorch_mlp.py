"""
Example: Multi-Layer Perceptron (MLP) lowering and compilation to Verilog.

Demonstrates:
  - Stacking multiple Linear layers with ReLU activation
  - Static weight embedding and parameter buffers
  - End-to-end hardware synthesis into Verilog RTL

Usage:
    python examples/pytorch_mlp.py
"""

import torch
import torch.nn as nn
from python_hls.frontend.torch_fx import lower_torch_model, compile_torch_model


class TinyMLP(nn.Module):
    """2-layer perceptron: 4 inputs -> 4 hidden -> 2 outputs."""

    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(4, 4)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(4, 2)

    def forward(self, x):
        h = self.relu(self.fc1(x))
        return self.fc2(h)


def main():
    print("1. Creating TinyMLP PyTorch model...")
    torch.manual_seed(42)
    model = TinyMLP().eval()
    example_x = torch.randn(4, dtype=torch.float32)

    print("2. Tracing and Lowering PyTorch FX model...")
    lowered_code, graph = lower_torch_model(model, [example_x])
    print("\n--- Lowered Synthesizable Python Code ---")
    print(lowered_code)
    print("-----------------------------------------\n")

    print("3. Compiling to Verilog RTL...")
    netlist, _ = compile_torch_model(
        model,
        [example_x],
        target="verilog",
        output_file="mlp.v",
    )
    print("✅ Successfully generated mlp.v!")
    print(f"Synthesized modules: {list(netlist.modules.keys())}")


if __name__ == "__main__":
    main()
