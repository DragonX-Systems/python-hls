"""
Example: Lowering an elementwise PyTorch module with broadcasting and clamp.

Usage:
    python -m python_hls.cli compile-torch examples/pytorch_elementwise.py --input-shapes "8;8" -o elem.v
    python examples/pytorch_elementwise.py
"""

import torch
import torch.nn as nn
from python_hls.frontend.torch_fx import lower_torch_model, compile_torch_model


class ElementwiseModel(nn.Module):
    """Elementwise add, multiply by constant, and clamp."""

    def forward(self, a, b):
        c = a + b
        d = c * 2
        return torch.clamp(d, min=0, max=100)


model = ElementwiseModel()


def main():
    print("1. Creating PyTorch ElementwiseModel...")
    m = ElementwiseModel().eval()
    a = torch.tensor([1, -2, 3, -4, 5, -6, 7, -8], dtype=torch.int32)
    b = torch.tensor([10, 10, 10, 10, 10, 10, 10, 10], dtype=torch.int32)

    print("2. Lowering to synthesizable HLS Python...")
    lowered_code, _ = lower_torch_model(m, [a, b])
    print("\n--- Lowered Code ---")
    print(lowered_code)
    print("--------------------\n")

    print("3. Compiling to Verilog RTL...")
    netlist, _ = compile_torch_model(m, [a, b], target="verilog", output_file="elem.v")
    print("✅ Successfully generated elem.v!")
    print(f"Modules synthesized: {list(netlist.modules.keys())}")


if __name__ == "__main__":
    main()
