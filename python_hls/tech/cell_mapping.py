"""
Cell-to-Resource Mapping for Python-HLS.

Defines public mapping rules from characterized Liberty cells / macros to
Python-HLS ResourceModel functional units (Adders, Multipliers, Registers,
Multiplexers, Comparators, ALUs, and Memories).
"""

import re
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set

from .liberty_parser import LibertyLibrary, LibertyCell
from .schema import (
    CharacterizationMetadata,
    NormalizedOperatingCondition,
    NormalizedUnits,
    NormalizedAssumptions,
    NormalizedProvenance,
)


@dataclass
class CellPattern:
    """Pattern matching rule for recognizing standard cell types."""
    cell_type: str
    name_regex: str
    min_inputs: int = 1
    description: str = ""


# Default recognition patterns for standard cell libraries
DEFAULT_CELL_PATTERNS = [
    CellPattern("FA", r"^(FA|FADD|ADDF)(_X\d+|X\d+)?$", min_inputs=3, description="1-bit Full Adder"),
    CellPattern("HA", r"^(HA|HADD|ADDH)(_X\d+|X\d+)?$", min_inputs=2, description="1-bit Half Adder"),
    CellPattern("DFF", r"^(DFF|DFCN|DFFR|DFFQ|dff)(_X\d+|X\d+)?$", min_inputs=1, description="D Flip-Flop"),
    CellPattern("MUX2", r"^(MUX2|MX2|MUX21|mux2)(_X\d+|X\d+)?$", min_inputs=3, description="2-to-1 Multiplexer"),
    CellPattern("XOR2", r"^(XOR2|XOR)(_X\d+|X\d+)?$", min_inputs=2, description="2-input XOR gate"),
    CellPattern("XNOR2", r"^(XNOR2|XNOR)(_X\d+|X\d+)?$", min_inputs=2, description="2-input XNOR gate"),
    CellPattern("AND2", r"^(AND2|AND)(_X\d+|X\d+)?$", min_inputs=2, description="2-input AND gate"),
    CellPattern("OR2", r"^(OR2|OR)(_X\d+|X\d+)?$", min_inputs=2, description="2-input OR gate"),
    CellPattern("NAND2", r"^(NAND2|NAND)(_X\d+|X\d+)?$", min_inputs=2, description="2-input NAND gate"),
    CellPattern("NOR2", r"^(NOR2|NOR)(_X\d+|X\d+)?$", min_inputs=2, description="2-input NOR gate"),
    CellPattern("INV", r"^(INV|NOT|INVERTER)(_X\d+|X\d+)?$", min_inputs=1, description="Inverter"),
]

# Patterns for recognizing unsupported or unhandled constructs
UNSUPPORTED_CONSTRUCT_PATTERNS = [
    (r"^(LS_|LEVEL_SHIFTER|LSID|LSDI)", "Level shifter (multi-voltage domain logic unsupported in early DSE)"),
    (r"^(ISO_|ISOLATION)", "Isolation cell (power-domain isolation unsupported in early DSE)"),
    (r"^(HEADER_|FOOTER_|POWER_SWITCH)", "Power gating switch (physical power domains unsupported in early DSE)"),
    (r"^(PAD_|IOCELL_|IO_)", "Analog or I/O pad cell (external interface pads unsupported in RTL core DSE)"),
    (r"^(SCAN_|SDFF_)", "Scan-test sequential cell (DFT/scan-chains unsupported in early synthesis DSE)"),
]


class CellToResourceMapper:
    """
    Public mapping contract converting characterized Liberty cell/macro data
    to Python-HLS ResourceModel objects.
    """

    def __init__(
        self,
        tech_node: int = 45,
        target_frequency_mhz: float = 1000.0,
        drive_strength: str = "X1",
        user_cell_mapping: Optional[Dict[str, str]] = None,
    ):
        self.tech_node = tech_node
        self.target_frequency_mhz = target_frequency_mhz
        self.drive_strength = drive_strength
        self.user_cell_mapping = user_cell_mapping or {}

    def discover_cells(self, library: LibertyLibrary) -> Tuple[Dict[str, LibertyCell], List[str]]:
        """
        Scan LibertyLibrary cells to match standard primitive cells and identify unsupported constructs.

        Returns:
            (matched_primitives, unsupported_cells_log)
        """
        matched: Dict[str, LibertyCell] = {}
        unsupported_log: List[str] = []

        # First check explicit user overrides
        for primitive_name, cell_name in self.user_cell_mapping.items():
            if cell_name in library.cells:
                matched[primitive_name] = library.cells[cell_name]

        # Scan for standard cell patterns
        for cell_name, cell in library.cells.items():
            # Check for unsupported constructs
            is_unsupported = False
            for pattern, reason in UNSUPPORTED_CONSTRUCT_PATTERNS:
                if re.search(pattern, cell_name, re.IGNORECASE):
                    unsupported_log.append(f"{cell_name}: {reason}")
                    is_unsupported = True
                    break
            if is_unsupported:
                continue

            # Match standard primitives if not already matched
            for pat in DEFAULT_CELL_PATTERNS:
                if pat.cell_type not in matched:
                    if re.search(pat.name_regex, cell_name, re.IGNORECASE):
                        # If drive_strength is specified, prefer matching drive strength
                        if self.drive_strength and f"_{self.drive_strength}" in cell_name.upper():
                            matched[pat.cell_type] = cell
                        elif pat.cell_type not in matched:
                            matched[pat.cell_type] = cell

        # Fallback: if FA or DFF not found by name, inspect boolean functions or pin names
        if "FA" not in matched:
            for cell in library.cells.values():
                has_sum = any(p.function and ("^" in p.function or "xor" in p.function.lower()) for p in cell.pins.values())
                if len(cell.pins) >= 5 and has_sum:  # A, B, CI, S, CO
                    matched["FA"] = cell
                    break

        if "DFF" not in matched:
            for cell in library.cells.values():
                has_clk = any("clk" in p.name.lower() or "ck" in p.name.lower() for p in cell.pins.values())
                has_q = any("q" in p.name.lower() for p in cell.pins.values() if p.direction == "output")
                if has_clk and has_q:
                    matched["DFF"] = cell
                    break

        return matched, unsupported_log

    def build_resource_models(
        self,
        library: LibertyLibrary,
        operating_condition_name: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], CharacterizationMetadata]:
        """
        Build all Python-HLS resource models from characterized Liberty data.

        Returns:
            (resource_dicts, characterization_metadata)
        """
        matched_cells, unsupported_log = self.discover_cells(library)
        op_cond = library.get_operating_condition(operating_condition_name)

        # Characterization assumptions
        nominal_voltage = op_cond.voltage
        clock_period_ns = 1000.0 / self.target_frequency_mhz

        # Extract cell characteristics (or default realistic 45nm reference fallbacks if cell missing)
        fa_cell = matched_cells.get("FA")
        dff_cell = matched_cells.get("DFF")
        mux_cell = matched_cells.get("MUX2")
        xor_cell = matched_cells.get("XOR2")
        xnor_cell = matched_cells.get("XNOR2") or xor_cell
        and_cell = matched_cells.get("AND2")
        nand_cell = matched_cells.get("NAND2")
        inv_cell = matched_cells.get("INV")

        # Leaf cell values (normalized in μm², μW, ns, pJ)
        fa_area = fa_cell.area if fa_cell else 3.724
        fa_leakage = fa_cell.cell_leakage_power if fa_cell else 0.15
        fa_delay = fa_cell.get_max_delay() if fa_cell and fa_cell.get_max_delay() > 0 else 0.12
        fa_energy = 0.02 * (nominal_voltage / 1.1) ** 2  # pJ

        dff_area = dff_cell.area if dff_cell else 4.256
        dff_leakage = dff_cell.cell_leakage_power if dff_cell else 0.18
        dff_delay = dff_cell.get_max_delay() if dff_cell and dff_cell.get_max_delay() > 0 else 0.10
        dff_energy = 0.01 * (nominal_voltage / 1.1) ** 2

        mux_area = mux_cell.area if mux_cell else 1.862
        mux_leakage = mux_cell.cell_leakage_power if mux_cell else 0.08
        mux_delay = mux_cell.get_max_delay() if mux_cell and mux_cell.get_max_delay() > 0 else 0.06
        mux_energy = 0.008 * (nominal_voltage / 1.1) ** 2

        xor_area = xor_cell.area if xor_cell else 1.596
        xor_leakage = xor_cell.cell_leakage_power if xor_cell else 0.06
        xor_delay = xor_cell.get_max_delay() if xor_cell and xor_cell.get_max_delay() > 0 else 0.05
        xor_energy = 0.006 * (nominal_voltage / 1.1) ** 2

        xnor_area = xnor_cell.area if xnor_cell else xor_area
        xnor_leakage = xnor_cell.cell_leakage_power if xnor_cell else xor_leakage
        xnor_delay = xnor_cell.get_max_delay() if xnor_cell and xnor_cell.get_max_delay() > 0 else xor_delay
        xnor_energy = 0.006 * (nominal_voltage / 1.1) ** 2

        and_area = and_cell.area if and_cell else 1.064
        and_leakage = and_cell.cell_leakage_power if and_cell else 0.04
        and_delay = and_cell.get_max_delay() if and_cell and and_cell.get_max_delay() > 0 else 0.04
        and_energy = 0.004 * (nominal_voltage / 1.1) ** 2

        # Check for direct macro cells in the library
        adder_macro = library.cells.get("ADDER32") or library.cells.get("ADD32")
        mult_macro = library.cells.get("MULT32") or library.cells.get("MUL32")
        sram1k_macro = library.cells.get("SRAM_1KB") or library.cells.get("MEM_1KB")

        resources = []

        # 1. Register_1bit
        resources.append({
            "name": "Register_1bit",
            "area": round(dff_area, 2),
            "latency": 1,
            "energy_per_op": round(dff_energy, 4),
            "leakage_power": round(dff_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz, 1),
            "provenance": {
                "source": "characterized_liberty",
                "derived_from": [dff_cell.name if dff_cell else "default_dff"],
                "formula": "1 * area(DFF)"
            }
        })

        # 2. Register_32bit
        reg32_area = 32 * dff_area * 1.10  # 10% clock buffer/routing overhead
        reg32_leakage = 32 * dff_leakage
        reg32_energy = 32 * dff_energy
        resources.append({
            "name": "Register_32bit",
            "area": round(reg32_area, 2),
            "latency": 1,
            "energy_per_op": round(reg32_energy, 4),
            "leakage_power": round(reg32_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz, 1),
            "provenance": {
                "source": "characterized_liberty",
                "derived_from": [dff_cell.name if dff_cell else "default_dff"],
                "formula": "32 * area(DFF) * 1.10"
            }
        })

        # 3. Register_64bit
        reg64_area = 64 * dff_area * 1.12
        resources.append({
            "name": "Register_64bit",
            "area": round(reg64_area, 2),
            "latency": 1,
            "energy_per_op": round(reg32_energy * 2, 4),
            "leakage_power": round(reg32_leakage * 2, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz, 1),
            "provenance": {
                "source": "characterized_liberty",
                "derived_from": [dff_cell.name if dff_cell else "default_dff"],
                "formula": "64 * area(DFF) * 1.12"
            }
        })

        # 4. Adder_32bit
        if adder_macro:
            add32_area = adder_macro.area
            add32_leakage = adder_macro.cell_leakage_power
            add32_delay = adder_macro.get_max_delay()
            add32_latency = 1 if add32_delay <= clock_period_ns else math.ceil(add32_delay / clock_period_ns)
            add32_prov = {"source": "characterized_macro", "macro_cell": adder_macro.name}
        else:
            # 32-bit parallel-prefix adder model (~32 FA equivalents + prefix tree logic ~1.25x)
            add32_area = 32 * fa_area * 1.25
            add32_leakage = 32 * fa_leakage * 1.25
            # Delay across 5 prefix levels
            prefix_delay = 5 * (xor_delay + and_delay)
            add32_latency = 1 if prefix_delay <= clock_period_ns else math.ceil(prefix_delay / clock_period_ns)
            add32_prov = {
                "source": "characterized_liberty",
                "derived_from": [fa_cell.name if fa_cell else "default_fa", xor_cell.name if xor_cell else "default_xor"],
                "formula": "32 * area(FA) * 1.25 prefix tree"
            }

        resources.append({
            "name": "Adder_32bit",
            "area": round(add32_area, 2),
            "latency": add32_latency,
            "energy_per_op": round(32 * fa_energy * 1.2, 4),
            "leakage_power": round(add32_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz, 1),
            "provenance": add32_prov
        })

        # 5. Subtractor_32bit
        sub32_area = add32_area + 32 * xor_area
        resources.append({
            "name": "Subtractor_32bit",
            "area": round(sub32_area, 2),
            "latency": add32_latency,
            "energy_per_op": round(32 * fa_energy * 1.3, 4),
            "leakage_power": round(add32_leakage + 32 * xor_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 0.95, 1),
            "provenance": {
                "source": "characterized_liberty",
                "formula": "Adder_32bit + 32 * area(XOR2)"
            }
        })

        # 6. Multiplier_32bit
        if mult_macro:
            mul32_area = mult_macro.area
            mul32_leakage = mult_macro.cell_leakage_power
            mul32_delay = mult_macro.get_max_delay()
            mul32_latency = 2 if mul32_delay <= (clock_period_ns * 2) else math.ceil(mul32_delay / clock_period_ns)
            mul32_prov = {"source": "characterized_macro", "macro_cell": mult_macro.name}
        else:
            # Booth-Wallace tree multiplier: ~900 FA equivalents
            mul32_area = 900 * fa_area
            mul32_leakage = 900 * fa_leakage
            mul32_latency = 2  # standard 2-cycle pipelined multiplier
            mul32_prov = {
                "source": "characterized_liberty",
                "derived_from": [fa_cell.name if fa_cell else "default_fa"],
                "formula": "900 * area(FA) Booth-Wallace tree"
            }

        resources.append({
            "name": "Multiplier_32bit",
            "area": round(mul32_area, 2),
            "latency": mul32_latency,
            "energy_per_op": round(900 * fa_energy * 0.2, 4),
            "leakage_power": round(mul32_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 0.75, 1),
            "provenance": mul32_prov
        })

        # 7. Divider_32bit (Radix-2 non-restoring divider)
        div32_area = mul32_area * 1.8
        resources.append({
            "name": "Divider_32bit",
            "area": round(div32_area, 2),
            "latency": 10,  # 10 cycles
            "energy_per_op": round(mul32_area * 0.02, 4),
            "leakage_power": round(mul32_leakage * 1.8, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 0.5, 1),
            "provenance": {
                "source": "characterized_liberty",
                "formula": "1.8 * Multiplier_32bit array"
            }
        })

        # 8. BitOp_32bit (32 XOR2 gates)
        bitop_area = 32 * xor_area
        resources.append({
            "name": "BitOp_32bit",
            "area": round(bitop_area, 2),
            "latency": 1,
            "energy_per_op": round(32 * xor_energy, 4),
            "leakage_power": round(32 * xor_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 1.2, 1),
            "provenance": {
                "source": "characterized_liberty",
                "derived_from": [xor_cell.name if xor_cell else "default_xor"],
                "formula": "32 * area(XOR2)"
            }
        })

        # 9. Comparator_32bit (32 XNOR2 + 31 AND2 tree)
        comp_area = 32 * xnor_area + 31 * and_area
        resources.append({
            "name": "Comparator_32bit",
            "area": round(comp_area, 2),
            "latency": 1,
            "energy_per_op": round(32 * xor_energy * 0.8, 4),
            "leakage_power": round(32 * xnor_leakage + 31 * and_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 1.1, 1),
            "provenance": {
                "source": "characterized_liberty",
                "formula": "32 * area(XNOR2) + 31 * area(AND2)"
            }
        })

        # 10. RelationalOp_32bit (<, <=, >, >=)
        rel_area = sub32_area * 0.8
        resources.append({
            "name": "RelationalOp_32bit",
            "area": round(rel_area, 2),
            "latency": 1,
            "energy_per_op": round(32 * fa_energy * 0.9, 4),
            "leakage_power": round(sub32_area * 0.8 * 0.05, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 1.05, 1),
            "provenance": {
                "source": "characterized_liberty",
                "formula": "0.8 * Subtractor_32bit"
            }
        })

        # 11. MUX_32bit (32 2:1 MUXes, combinational latency 0)
        mux32_area = 32 * mux_area
        resources.append({
            "name": "MUX_32bit",
            "area": round(mux32_area, 2),
            "latency": 0,
            "energy_per_op": round(32 * mux_energy, 4),
            "leakage_power": round(32 * mux_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 1.5, 1),
            "provenance": {
                "source": "characterized_liberty",
                "derived_from": [mux_cell.name if mux_cell else "default_mux"],
                "formula": "32 * area(MUX2)"
            }
        })

        # 12. Shifter_32bit (5-stage barrel shifter: 160 MUXes)
        shift_area = 160 * mux_area
        resources.append({
            "name": "Shifter_32bit",
            "area": round(shift_area, 2),
            "latency": 1,
            "energy_per_op": round(160 * mux_energy * 0.5, 4),
            "leakage_power": round(160 * mux_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz, 1),
            "provenance": {
                "source": "characterized_liberty",
                "formula": "160 * area(MUX2) 5-stage barrel shifter"
            }
        })

        # 13. ALU_32bit (Adder + BitOp + Mux)
        alu_area = add32_area + bitop_area + 2 * mux32_area
        resources.append({
            "name": "ALU_32bit",
            "area": round(alu_area, 2),
            "latency": 1,
            "energy_per_op": round(32 * fa_energy * 1.5, 4),
            "leakage_power": round(add32_leakage + 32 * xor_leakage + 64 * mux_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 0.85, 1),
            "provenance": {
                "source": "characterized_liberty",
                "formula": "Adder_32bit + BitOp_32bit + 2 * MUX_32bit"
            }
        })

        # 14. AGU_32bit
        resources.append({
            "name": "AGU_32bit",
            "area": round(add32_area * 1.2, 2),
            "latency": 1,
            "energy_per_op": round(32 * fa_energy * 1.3, 4),
            "leakage_power": round(add32_leakage * 1.2, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 0.85, 1),
            "provenance": {"source": "characterized_liberty", "formula": "1.2 * Adder_32bit"}
        })

        # 15. FSM_Controller
        fsm_area = 16 * dff_area + 40 * and_area
        resources.append({
            "name": "FSM_Controller",
            "area": round(fsm_area, 2),
            "latency": 1,
            "energy_per_op": round(16 * dff_energy + 40 * and_energy, 4),
            "leakage_power": round(16 * dff_leakage + 40 * and_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz, 1),
            "provenance": {"source": "characterized_liberty", "formula": "16 * DFF + 40 * logic gates"}
        })

        # 16. Memory_Controller
        resources.append({
            "name": "Memory_Controller",
            "area": round(fsm_area + add32_area * 1.2, 2),
            "latency": 1,
            "energy_per_op": round(2.5, 4),
            "leakage_power": round(25.0 * (self.tech_node / 45.0), 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 0.75, 1),
            "provenance": {"source": "characterized_liberty", "formula": "AGU + FSM + interface"}
        })

        # 17. FIFO_32bit
        fifo_area = 32 * reg32_area * 0.7  # 32 words of 32-bit registers with shared decode
        resources.append({
            "name": "FIFO_32bit",
            "area": round(fifo_area, 2),
            "latency": 1,
            "energy_per_op": round(3.0 * (self.tech_node / 45.0), 4),
            "leakage_power": round(32 * reg32_leakage * 0.7, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz, 1),
            "provenance": {"source": "characterized_liberty", "formula": "32 * Register_32bit * 0.7"}
        })

        # 18. CROSSBAR_32bit
        xbar_area = 16 * mux32_area
        resources.append({
            "name": "CROSSBAR_32bit",
            "area": round(xbar_area, 2),
            "latency": 1,
            "energy_per_op": round(16 * 32 * mux_energy, 4),
            "leakage_power": round(16 * 32 * mux_leakage, 3),
            "tech_node": self.tech_node,
            "frequency": round(self.target_frequency_mhz * 0.9, 1),
            "provenance": {"source": "characterized_liberty", "formula": "16 * MUX_32bit"}
        })

        # 19. Memories (SRAM macro or node-scaled estimates)
        mem_scale = (self.tech_node / 45.0) ** 1.85
        memories = [
            ("Memory_1KB", 10000.0 * mem_scale, 1, 5.0, 200.0 * mem_scale),
            ("Memory_4KB", 38000.0 * mem_scale, 1, 15.0, 500.0 * mem_scale),
            ("Scratchpad_1KB", 8000.0 * mem_scale, 1, 4.0, 150.0 * mem_scale),
            ("Scratchpad_4KB", 30000.0 * mem_scale, 1, 12.0, 400.0 * mem_scale),
            ("Scratchpad_16KB", 100000.0 * mem_scale, 2, 35.0, 800.0 * mem_scale),
            ("Scratchpad_64KB", 380000.0 * mem_scale, 3, 120.0, 2400.0 * mem_scale),
            ("Cache_16KB", 150000.0 * mem_scale, 2, 45.0, 1200.0 * mem_scale),
        ]
        for mem_name, area_val, lat_val, energy_val, leak_val in memories:
            resources.append({
                "name": mem_name,
                "area": round(area_val, 2),
                "latency": lat_val,
                "energy_per_op": round(energy_val, 3),
                "leakage_power": round(leak_val, 3),
                "tech_node": self.tech_node,
                "frequency": round(self.target_frequency_mhz * (0.9 if lat_val == 1 else 0.8), 1),
                "provenance": {
                    "source": "sram_macro" if sram1k_macro else "characterized_memory_model",
                    "formula": f"SRAM bitcell model scaled to {self.tech_node}nm"
                }
            })

        # Assemble characterization metadata
        metadata = CharacterizationMetadata(
            library_name=library.name,
            tech_node=self.tech_node,
            operating_condition=NormalizedOperatingCondition(
                name=op_cond.name,
                process=op_cond.process,
                voltage=op_cond.voltage,
                temperature=op_cond.temperature,
                corner=op_cond.name,
            ),
            units=NormalizedUnits(
                time="ns",
                voltage="V",
                power="uW",
                energy="pJ",
                area="um2",
                capacitance="fF",
            ),
            assumptions=NormalizedAssumptions(
                clock_frequency_mhz=self.target_frequency_mhz,
                drive_strength=self.drive_strength,
                notes="Synthesized resource models mapped from characterized Liberty cell data."
            ),
            cell_mappings={k: v.name for k, v in matched_cells.items()},
            unsupported_cells=unsupported_log,
        )

        return resources, metadata
