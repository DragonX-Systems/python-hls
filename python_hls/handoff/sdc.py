"""
Synopsys Design Constraints (SDC) generator for Python-HLS designs.
Produces standard timing constraints required for synthesis and static timing analysis.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import os
import re
from typing import List, Optional, Sequence, Union


@dataclass
class SDCConfig:
    """Configuration parameters for SDC generation."""
    clock_name: str = "clk"
    clock_period_ns: float = 10.0  # 100 MHz default
    clock_uncertainty_ns: Optional[float] = None  # Defaults to 5% of period
    clock_transition_ns: float = 0.05
    input_delay_factor: float = 0.2  # 20% of period
    output_delay_factor: float = 0.2  # 20% of period
    output_load_pf: float = 0.035  # 35 fF typical load in sky130
    reset_name: Optional[str] = "rst"
    input_ports: List[str] = field(default_factory=list)
    output_ports: List[str] = field(default_factory=list)


class SDCGenerator:
    """Generates standard Synopsys Design Constraints (.sdc) files."""

    def __init__(self, config: Optional[SDCConfig] = None):
        self.config = config or SDCConfig()

    @staticmethod
    def extract_ports_from_verilog(verilog_code_or_file: str) -> dict:
        """
        Parse Verilog module declaration to extract clock, reset, inputs, and outputs.
        """
        content = verilog_code_or_file
        if os.path.exists(verilog_code_or_file):
            with open(verilog_code_or_file, "r", encoding="utf-8") as f:
                content = f.read()

        ports = {
            "clock": "clk",
            "reset": "rst",
            "inputs": [],
            "outputs": [],
        }

        # Match input ports
        input_matches = re.findall(r"\binput\s+(?:wire\s+|reg\s+)?(?:\[[^\]]+\]\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", content)
        for port in input_matches:
            port_lower = port.lower()
            if port_lower in ("clk", "clock", "i_clk", "clk_i"):
                ports["clock"] = port
            elif port_lower in ("rst", "rst_n", "reset", "i_rst", "rst_i", "reset_n"):
                ports["reset"] = port
            else:
                ports["inputs"].append(port)

        # Match output ports
        output_matches = re.findall(r"\boutput\s+(?:wire\s+|reg\s+)?(?:\[[^\]]+\]\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", content)
        for port in output_matches:
            ports["outputs"].append(port)

        return ports

    def generate(
        self,
        top_module: str,
        clock_period_ns: Optional[float] = None,
        clock_name: Optional[str] = None,
        input_ports: Optional[Sequence[str]] = None,
        output_ports: Optional[Sequence[str]] = None,
    ) -> str:
        """
        Generate SDC constraint string for the target top module.
        """
        period = clock_period_ns or self.config.clock_period_ns
        clk = clock_name or self.config.clock_name
        uncertainty = self.config.clock_uncertainty_ns if self.config.clock_uncertainty_ns is not None else (period * 0.05)
        in_delay = period * self.config.input_delay_factor
        out_delay = period * self.config.output_delay_factor
        freq_mhz = 1000.0 / period if period > 0 else 0.0

        lines = [
            "###############################################################################",
            f"# Synopsys Design Constraints (SDC) for {top_module}",
            "# Generated automatically by Python-HLS GPU-OpenLane Handoff",
            f"# Target Clock: {clk} | Period: {period:.3f} ns | Frequency: {freq_mhz:.2f} MHz",
            "###############################################################################",
            "",
            "# Current Design",
            f"current_design {top_module}",
            "",
            "# Clock Definition",
            f"create_clock -name {clk} -period {period:.3f} [get_ports {clk}]",
            f"set_clock_uncertainty {uncertainty:.3f} [get_clocks {clk}]",
            f"set_clock_transition {self.config.clock_transition_ns:.3f} [get_clocks {clk}]",
            "",
        ]

        # Inputs delay
        inputs = list(input_ports) if input_ports is not None else self.config.input_ports
        if inputs:
            port_list_str = " ".join(f"[get_ports {p}]" for p in inputs)
            lines.append("# Input Constraints")
            lines.append(f"set_input_delay -clock {clk} {in_delay:.3f} {port_list_str}")
        else:
            lines.append("# Input Constraints (all inputs except clock)")
            lines.append(f"set_input_delay -clock {clk} {in_delay:.3f} [remove_from_collection [all_inputs] [get_ports {clk}]]")

        lines.append("")

        # Outputs delay and load
        outputs = list(output_ports) if output_ports is not None else self.config.output_ports
        if outputs:
            out_port_str = " ".join(f"[get_ports {p}]" for p in outputs)
            lines.append("# Output Constraints")
            lines.append(f"set_output_delay -clock {clk} {out_delay:.3f} {out_port_str}")
            lines.append(f"set_load {self.config.output_load_pf:.4f} {out_port_str}")
        else:
            lines.append("# Output Constraints (all outputs)")
            lines.append(f"set_output_delay -clock {clk} {out_delay:.3f} [all_outputs]")
            lines.append(f"set_load {self.config.output_load_pf:.4f} [all_outputs]")

        lines.append("")
        lines.append("###############################################################################")
        lines.append("# End of SDC")
        lines.append("###############################################################################")
        lines.append("")

        return "\n".join(lines)

    def write(
        self,
        output_path: str,
        top_module: str,
        clock_period_ns: Optional[float] = None,
        clock_name: Optional[str] = None,
        verilog_file: Optional[str] = None,
    ) -> str:
        """
        Generate and write SDC file to disk.
        """
        inputs = None
        outputs = None
        clk = clock_name

        if verilog_file and os.path.exists(verilog_file):
            extracted = self.extract_ports_from_verilog(verilog_file)
            if not clk:
                clk = extracted.get("clock", "clk")
            inputs = extracted.get("inputs")
            outputs = extracted.get("outputs")

        content = self.generate(
            top_module=top_module,
            clock_period_ns=clock_period_ns,
            clock_name=clk,
            input_ports=inputs,
            output_ports=outputs,
        )

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return os.path.abspath(output_path)
