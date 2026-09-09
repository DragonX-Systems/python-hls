"""
Technology node specific patterns for Verilog generation.
Optimizations tailored to different process nodes and their characteristics.
"""

import logging
from typing import Dict, List, Optional, Set, Union, Any, Tuple
from dataclasses import dataclass

from ...ir.ir_nodes import (
    IRFunction, IRBlock, IRInstruction, IRVariable, IRConstant, 
    IROperation, OperationType, DataType
)
from ...netlist import NetlistResource

logger = logging.getLogger(__name__)

@dataclass
class TechNodeCharacteristics:
    """Characteristics of a technology node."""
    node_nm: int
    category: str  # "legacy", "mature", "advanced", "leading_edge"
    voltage_nominal: float
    voltage_min: float
    voltage_max: float
    leakage_factor: float
    variability_factor: float
    thermal_factor: float
    supports_finfet: bool
    supports_multi_vt: bool
    supports_power_gating: bool

class TechPatternGenerator:
    """Generator for technology node specific Verilog patterns."""
    
    def __init__(self, tech_node: int = 45):
        """
        Initialize technology pattern generator.
        
        Args:
            tech_node: Technology node in nm
        """
        self.tech_node = tech_node
        self.characteristics = self._get_tech_characteristics(tech_node)
        
    def generate_tech_optimized_module(self, func: IRFunction, ppa_objective: str) -> List[str]:
        """
        Generate technology node optimized module.
        
        Args:
            func: Function to generate module for
            ppa_objective: PPA optimization objective
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        # Add technology-specific header
        code.extend(self._generate_tech_header(func))
        
        # Add node-specific optimizations
        if self.characteristics.category == "legacy":
            code.extend(self._generate_legacy_node_optimizations(func, ppa_objective))
        elif self.characteristics.category == "mature":
            code.extend(self._generate_mature_node_optimizations(func, ppa_objective))
        elif self.characteristics.category == "advanced":
            code.extend(self._generate_advanced_node_optimizations(func, ppa_objective))
        elif self.characteristics.category == "leading_edge":
            code.extend(self._generate_leading_edge_optimizations(func, ppa_objective))
        
        return code
    
    def generate_voltage_domain_logic(self, func: IRFunction) -> List[str]:
        """
        Generate voltage domain logic based on technology capabilities.
        
        Args:
            func: Function to optimize
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        if not self.characteristics.supports_multi_vt:
            return code
        
        code.append("// Multi-VT voltage domain logic")
        
        # Generate voltage domain assignments
        code.extend(self._generate_voltage_domain_assignments(func))
        
        # Generate level shifters if needed
        code.extend(self._generate_level_shifters(func))
        
        # Generate voltage island control
        code.extend(self._generate_voltage_island_control(func))
        
        return code
    
    def generate_variability_mitigation(self, func: IRFunction) -> List[str]:
        """
        Generate variability mitigation logic.
        
        Args:
            func: Function to optimize
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        if self.characteristics.variability_factor < 1.5:
            return code
        
        code.append("// Variability mitigation logic")
        
        # Generate adaptive body biasing
        code.extend(self._generate_adaptive_body_biasing(func))
        
        # Generate timing error detection
        code.extend(self._generate_timing_error_detection(func))
        
        # Generate error correction
        code.extend(self._generate_error_correction(func))
        
        return code
    
    def generate_thermal_optimization(self, func: IRFunction) -> List[str]:
        """
        Generate thermal optimization logic.
        
        Args:
            func: Function to optimize
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        if self.characteristics.thermal_factor < 1.5:
            return code
        
        code.append("// Thermal optimization logic")
        
        # Generate thermal sensors
        code.extend(self._generate_thermal_sensors(func))
        
        # Generate thermal-aware routing
        code.extend(self._generate_thermal_aware_routing(func))
        
        # Generate hot spot mitigation
        code.extend(self._generate_hot_spot_mitigation(func))
        
        return code
    
    def generate_finfet_optimizations(self, func: IRFunction) -> List[str]:
        """
        Generate FinFET specific optimizations.
        
        Args:
            func: Function to optimize
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        if not self.characteristics.supports_finfet:
            return code
        
        code.append("// FinFET specific optimizations")
        
        # Generate back-gate biasing
        code.extend(self._generate_back_gate_biasing(func))
        
        # Generate fin width optimization
        code.extend(self._generate_fin_width_optimization(func))
        
        # Generate independent gate control
        code.extend(self._generate_independent_gate_control(func))
        
        return code
    
    def generate_leakage_mitigation(self, func: IRFunction) -> List[str]:
        """
        Generate leakage mitigation logic.
        
        Args:
            func: Function to optimize
            
        Returns:
            List of Verilog code lines
        """
        code = []
        
        if self.characteristics.leakage_factor < 2.0:
            return code
        
        code.append("// Leakage mitigation logic")
        
        # Generate power gating
        if self.characteristics.supports_power_gating:
            code.extend(self._generate_power_gating_cells(func))
        
        # Generate sleep transistors
        code.extend(self._generate_sleep_transistors(func))
        
        # Generate retention registers
        code.extend(self._generate_retention_registers(func))
        
        return code
    
    def _get_tech_characteristics(self, tech_node: int) -> TechNodeCharacteristics:
        """Get characteristics for a technology node."""
        
        if tech_node >= 90:
            return TechNodeCharacteristics(
                node_nm=tech_node,
                category="legacy",
                voltage_nominal=1.2,
                voltage_min=1.08,
                voltage_max=1.32,
                leakage_factor=1.0,
                variability_factor=1.0,
                thermal_factor=1.0,
                supports_finfet=False,
                supports_multi_vt=True,
                supports_power_gating=False
            )
        elif tech_node >= 28:
            return TechNodeCharacteristics(
                node_nm=tech_node,
                category="mature",
                voltage_nominal=1.0,
                voltage_min=0.9,
                voltage_max=1.1,
                leakage_factor=1.5,
                variability_factor=1.2,
                thermal_factor=1.2,
                supports_finfet=False,
                supports_multi_vt=True,
                supports_power_gating=True
            )
        elif tech_node >= 16:
            return TechNodeCharacteristics(
                node_nm=tech_node,
                category="advanced",
                voltage_nominal=0.8,
                voltage_min=0.72,
                voltage_max=0.88,
                leakage_factor=3.0,
                variability_factor=1.8,
                thermal_factor=1.5,
                supports_finfet=True,
                supports_multi_vt=True,
                supports_power_gating=True
            )
        else:  # 7nm and below
            return TechNodeCharacteristics(
                node_nm=tech_node,
                category="leading_edge",
                voltage_nominal=0.7,
                voltage_min=0.63,
                voltage_max=0.77,
                leakage_factor=5.0,
                variability_factor=2.5,
                thermal_factor=2.0,
                supports_finfet=True,
                supports_multi_vt=True,
                supports_power_gating=True
            )
    
    def _generate_tech_header(self, func: IRFunction) -> List[str]:
        """Generate technology-specific header."""
        code = []
        
        code.append(f"// Technology node: {self.tech_node}nm ({self.characteristics.category})")
        code.append(f"// Nominal voltage: {self.characteristics.voltage_nominal}V")
        code.append(f"// Leakage factor: {self.characteristics.leakage_factor}x")
        code.append(f"// Variability factor: {self.characteristics.variability_factor}x")
        code.append("")
        
        return code
    
    def _generate_legacy_node_optimizations(self, func: IRFunction, ppa_objective: str) -> List[str]:
        """Generate optimizations for legacy nodes (90nm+)."""
        code = []
        
        code.append("// Legacy node optimizations (90nm+)")
        
        # Focus on area and power efficiency
        if ppa_objective == "area":
            code.extend(self._generate_legacy_area_optimizations(func))
        elif ppa_objective == "power":
            code.extend(self._generate_legacy_power_optimizations(func))
        else:
            code.extend(self._generate_legacy_balanced_optimizations(func))
        
        return code
    
    def _generate_mature_node_optimizations(self, func: IRFunction, ppa_objective: str) -> List[str]:
        """Generate optimizations for mature nodes (28nm-65nm)."""
        code = []
        
        code.append("// Mature node optimizations (28nm-65nm)")
        
        # Balanced optimizations with some advanced features
        if ppa_objective == "area":
            code.extend(self._generate_mature_area_optimizations(func))
        elif ppa_objective == "performance":
            code.extend(self._generate_mature_performance_optimizations(func))
        elif ppa_objective == "power":
            code.extend(self._generate_mature_power_optimizations(func))
        else:
            code.extend(self._generate_mature_balanced_optimizations(func))
        
        return code
    
    def _generate_advanced_node_optimizations(self, func: IRFunction, ppa_objective: str) -> List[str]:
        """Generate optimizations for advanced nodes (16nm-22nm)."""
        code = []
        
        code.append("// Advanced node optimizations (16nm-22nm)")
        
        # FinFET optimizations and advanced power management
        if ppa_objective == "area":
            code.extend(self._generate_advanced_area_optimizations(func))
        elif ppa_objective == "performance":
            code.extend(self._generate_advanced_performance_optimizations(func))
        elif ppa_objective == "power":
            code.extend(self._generate_advanced_power_optimizations(func))
        else:
            code.extend(self._generate_advanced_balanced_optimizations(func))
        
        return code
    
    def _generate_leading_edge_optimizations(self, func: IRFunction, ppa_objective: str) -> List[str]:
        """Generate optimizations for leading edge nodes (7nm and below)."""
        code = []
        
        code.append("// Leading edge optimizations (7nm and below)")
        
        # Aggressive leakage and variability mitigation
        if ppa_objective == "area":
            code.extend(self._generate_leading_edge_area_optimizations(func))
        elif ppa_objective == "performance":
            code.extend(self._generate_leading_edge_performance_optimizations(func))
        elif ppa_objective == "power":
            code.extend(self._generate_leading_edge_power_optimizations(func))
        else:
            code.extend(self._generate_leading_edge_balanced_optimizations(func))
        
        return code
    
    def _generate_legacy_area_optimizations(self, func: IRFunction) -> List[str]:
        """Generate area optimizations for legacy nodes."""
        code = []
        
        # Simple resource sharing
        code.append("// Legacy area optimizations")
        code.append("// - Aggressive resource sharing")
        code.append("// - Minimal logic depth")
        code.append("reg shared_resource_busy;")
        code.append("reg [1:0] resource_arbiter;")
        code.append("")
        
        return code
    
    def _generate_legacy_power_optimizations(self, func: IRFunction) -> List[str]:
        """Generate power optimizations for legacy nodes."""
        code = []
        
        # Simple clock gating
        code.append("// Legacy power optimizations")
        code.append("// - Basic clock gating")
        code.append("// - Voltage scaling")
        code.append("wire gated_clock;")
        code.append("assign gated_clock = clk & clock_enable;")
        code.append("")
        
        return code
    
    def _generate_legacy_balanced_optimizations(self, func: IRFunction) -> List[str]:
        """Generate balanced optimizations for legacy nodes."""
        code = []
        
        code.append("// Legacy balanced optimizations")
        code.append("// - Moderate resource sharing")
        code.append("// - Basic power management")
        code.append("")
        
        return code
    
    def _generate_mature_area_optimizations(self, func: IRFunction) -> List[str]:
        """Generate area optimizations for mature nodes."""
        code = []
        
        code.append("// Mature node area optimizations")
        code.append("// - Multi-VT optimization")
        code.append("// - Power gating")
        code.append("reg [1:0] vt_selection;")
        code.append("reg power_gate_enable;")
        code.append("")
        
        return code
    
    def _generate_mature_performance_optimizations(self, func: IRFunction) -> List[str]:
        """Generate performance optimizations for mature nodes."""
        code = []
        
        code.append("// Mature node performance optimizations")
        code.append("// - Pipeline optimization")
        code.append("// - Parallel execution")
        code.append("reg [2:0] pipeline_stage;")
        code.append("reg parallel_enable;")
        code.append("")
        
        return code
    
    def _generate_mature_power_optimizations(self, func: IRFunction) -> List[str]:
        """Generate power optimizations for mature nodes."""
        code = []
        
        code.append("// Mature node power optimizations")
        code.append("// - Advanced clock gating")
        code.append("// - Power domains")
        code.append("reg [3:0] clock_gate_control;")
        code.append("reg [1:0] power_domain_select;")
        code.append("")
        
        return code
    
    def _generate_mature_balanced_optimizations(self, func: IRFunction) -> List[str]:
        """Generate balanced optimizations for mature nodes."""
        code = []
        
        code.append("// Mature node balanced optimizations")
        code.append("// - Balanced PPA trade-offs")
        code.append("// - Moderate complexity")
        code.append("")
        
        return code
    
    def _generate_advanced_area_optimizations(self, func: IRFunction) -> List[str]:
        """Generate area optimizations for advanced nodes."""
        code = []
        
        code.append("// Advanced node area optimizations")
        code.append("// - FinFET optimization")
        code.append("// - Advanced power gating")
        code.append("reg [2:0] finfet_config;")
        code.append("reg advanced_power_gate;")
        code.append("")
        
        return code
    
    def _generate_advanced_performance_optimizations(self, func: IRFunction) -> List[str]:
        """Generate performance optimizations for advanced nodes."""
        code = []
        
        code.append("// Advanced node performance optimizations")
        code.append("// - Advanced pipelining")
        code.append("// - Variability compensation")
        code.append("reg [3:0] advanced_pipeline_control;")
        code.append("reg [2:0] variability_compensation;")
        code.append("")
        
        return code
    
    def _generate_advanced_power_optimizations(self, func: IRFunction) -> List[str]:
        """Generate power optimizations for advanced nodes."""
        code = []
        
        code.append("// Advanced node power optimizations")
        code.append("// - Fine-grained power gating")
        code.append("// - Leakage mitigation")
        code.append("reg [7:0] fine_power_control;")
        code.append("reg [3:0] leakage_mitigation;")
        code.append("")
        
        return code
    
    def _generate_advanced_balanced_optimizations(self, func: IRFunction) -> List[str]:
        """Generate balanced optimizations for advanced nodes."""
        code = []
        
        code.append("// Advanced node balanced optimizations")
        code.append("// - FinFET aware design")
        code.append("// - Variability tolerance")
        code.append("")
        
        return code
    
    def _generate_leading_edge_area_optimizations(self, func: IRFunction) -> List[str]:
        """Generate area optimizations for leading edge nodes.""" 
        code = []
        
        code.append("// Leading edge area optimizations")
        code.append("// - Extreme leakage mitigation")
        code.append("// - Thermal awareness")
        code.append("reg [7:0] leakage_control;")
        code.append("reg [3:0] thermal_management;")
        code.append("")
        
        return code
    
    def _generate_leading_edge_performance_optimizations(self, func: IRFunction) -> List[str]:
        """Generate performance optimizations for leading edge nodes."""
        code = []
        
        code.append("// Leading edge performance optimizations")
        code.append("// - Aggressive variability mitigation")
        code.append("// - Thermal throttling")
        code.append("reg [7:0] variability_control;")
        code.append("reg [3:0] thermal_throttle;")
        code.append("")
        
        return code
    
    def _generate_leading_edge_power_optimizations(self, func: IRFunction) -> List[str]:
        """Generate power optimizations for leading edge nodes."""
        code = []
        
        code.append("// Leading edge power optimizations")
        code.append("// - Ultra-fine power gating")
        code.append("// - Dynamic thermal management")
        code.append("reg [15:0] ultra_fine_power_control;")
        code.append("reg [7:0] dynamic_thermal_control;")
        code.append("")
        
        return code
    
    def _generate_leading_edge_balanced_optimizations(self, func: IRFunction) -> List[str]:
        """Generate balanced optimizations for leading edge nodes."""
        code = []
        
        code.append("// Leading edge balanced optimizations")
        code.append("// - Comprehensive variability handling")
        code.append("// - Advanced thermal management")
        code.append("")
        
        return code
    
    def _generate_voltage_domain_assignments(self, func: IRFunction) -> List[str]:
        """Generate voltage domain assignments."""
        code = []
        
        code.append("// Voltage domain assignments")
        code.append("reg [1:0] vdd_core_level;")
        code.append("reg [1:0] vdd_io_level;")
        code.append("reg [1:0] vdd_memory_level;")
        code.append("")
        
        # Voltage level parameters
        code.append("localparam VDD_LOW = 2'b00;")
        code.append("localparam VDD_NOMINAL = 2'b01;")
        code.append("localparam VDD_HIGH = 2'b10;")
        code.append("")
        
        return code
    
    def _generate_level_shifters(self, func: IRFunction) -> List[str]:
        """Generate level shifters for voltage domains."""
        code = []
        
        code.append("// Level shifters")
        code.append("reg level_shifter_enable;")
        code.append("reg [31:0] level_shifted_data;")
        code.append("")
        
        code.append("always @(*) begin")
        code.append("    if (level_shifter_enable)")
        code.append("        level_shifted_data = input_data;")
        code.append("    else")
        code.append("        level_shifted_data = 32'h0;")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_voltage_island_control(self, func: IRFunction) -> List[str]:
        """Generate voltage island control."""
        code = []
        
        code.append("// Voltage island control")
        code.append("reg [2:0] voltage_island_state;")
        code.append("reg voltage_island_enable;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    if (voltage_island_enable) begin")
        code.append("        case (voltage_island_state)")
        code.append("            3'b000: vdd_core_level <= VDD_LOW;")
        code.append("            3'b001: vdd_core_level <= VDD_NOMINAL;")
        code.append("            3'b010: vdd_core_level <= VDD_HIGH;")
        code.append("            default: vdd_core_level <= VDD_NOMINAL;")
        code.append("        endcase")
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_adaptive_body_biasing(self, func: IRFunction) -> List[str]:
        """Generate adaptive body biasing."""
        code = []
        
        code.append("// Adaptive body biasing")
        code.append("reg [2:0] body_bias_control;")
        code.append("reg [7:0] process_monitor;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    if (process_monitor > 8'h80)")
        code.append("        body_bias_control <= 3'b001;  // Forward bias")
        code.append("    else if (process_monitor < 8'h40)")
        code.append("        body_bias_control <= 3'b010;  // Reverse bias")
        code.append("    else")
        code.append("        body_bias_control <= 3'b000;  // No bias")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_timing_error_detection(self, func: IRFunction) -> List[str]:
        """Generate timing error detection."""
        code = []
        
        code.append("// Timing error detection")
        code.append("reg timing_error_detected;")
        code.append("reg [31:0] error_detection_ff;")
        code.append("reg [31:0] delayed_data;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    error_detection_ff <= input_data;")
        code.append("    delayed_data <= error_detection_ff;")
        code.append("    timing_error_detected <= (error_detection_ff != delayed_data);")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_error_correction(self, func: IRFunction) -> List[str]:
        """Generate error correction."""
        code = []
        
        code.append("// Error correction")
        code.append("reg error_correction_enable;")
        code.append("reg [31:0] corrected_data;")
        code.append("")
        
        code.append("always @(*) begin")
        code.append("    if (timing_error_detected && error_correction_enable)")
        code.append("        corrected_data = delayed_data;")
        code.append("    else")
        code.append("        corrected_data = error_detection_ff;")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_thermal_sensors(self, func: IRFunction) -> List[str]:
        """Generate thermal sensors."""
        code = []
        
        code.append("// Thermal sensors")
        code.append("reg [7:0] thermal_sensor_0;")
        code.append("reg [7:0] thermal_sensor_1;")
        code.append("reg [7:0] thermal_sensor_2;")
        code.append("reg [7:0] thermal_sensor_3;")
        code.append("reg [7:0] max_temperature;")
        code.append("")
        
        code.append("always @(*) begin")
        code.append("    max_temperature = thermal_sensor_0;")
        code.append("    if (thermal_sensor_1 > max_temperature)")
        code.append("        max_temperature = thermal_sensor_1;")
        code.append("    if (thermal_sensor_2 > max_temperature)")
        code.append("        max_temperature = thermal_sensor_2;")
        code.append("    if (thermal_sensor_3 > max_temperature)")
        code.append("        max_temperature = thermal_sensor_3;")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_thermal_aware_routing(self, func: IRFunction) -> List[str]:
        """Generate thermal aware routing."""
        code = []
        
        code.append("// Thermal aware routing")
        code.append("reg [3:0] routing_select;")
        code.append("reg thermal_routing_enable;")
        code.append("")
        
        code.append("always @(*) begin")
        code.append("    if (thermal_routing_enable) begin")
        code.append("        if (max_temperature > 8'h60)")
        code.append("            routing_select = 4'b0001;  // Route to cooler area")
        code.append("        else")
        code.append("            routing_select = 4'b0000;  // Normal routing")
        code.append("    end else")
        code.append("        routing_select = 4'b0000;")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_hot_spot_mitigation(self, func: IRFunction) -> List[str]:
        """Generate hot spot mitigation."""
        code = []
        
        code.append("// Hot spot mitigation")
        code.append("reg [3:0] hot_spot_counter;")
        code.append("reg hot_spot_detected;")
        code.append("reg mitigation_active;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    if (max_temperature > 8'h70) begin")
        code.append("        hot_spot_counter <= hot_spot_counter + 1;")
        code.append("        if (hot_spot_counter > 4'h8)")
        code.append("            hot_spot_detected <= 1'b1;")
        code.append("    end else begin")
        code.append("        hot_spot_counter <= 4'h0;")
        code.append("        hot_spot_detected <= 1'b0;")
        code.append("    end")
        code.append("    ")
        code.append("    mitigation_active <= hot_spot_detected;")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_back_gate_biasing(self, func: IRFunction) -> List[str]:
        """Generate back gate biasing for FinFET."""
        code = []
        
        code.append("// FinFET back gate biasing")
        code.append("reg [2:0] back_gate_bias;")
        code.append("reg back_gate_enable;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    if (back_gate_enable) begin")
        code.append("        case (power_state)")
        code.append("            PWR_ACTIVE: back_gate_bias <= 3'b010;  // Performance mode")
        code.append("            PWR_IDLE: back_gate_bias <= 3'b001;    // Balanced mode")
        code.append("            PWR_SLEEP: back_gate_bias <= 3'b000;   // Low leakage mode")
        code.append("            default: back_gate_bias <= 3'b001;")
        code.append("        endcase")
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_fin_width_optimization(self, func: IRFunction) -> List[str]:
        """Generate fin width optimization."""
        code = []
        
        code.append("// FinFET fin width optimization")
        code.append("reg [1:0] fin_width_select;")
        code.append("reg fin_width_optimization_enable;")
        code.append("")
        
        code.append("always @(*) begin")
        code.append("    if (fin_width_optimization_enable) begin")
        code.append("        case (performance_requirement)")
        code.append("            2'b00: fin_width_select = 2'b00;  // Minimum width")
        code.append("            2'b01: fin_width_select = 2'b01;  // Medium width")
        code.append("            2'b10: fin_width_select = 2'b10;  // High width")
        code.append("            2'b11: fin_width_select = 2'b11;  // Maximum width")
        code.append("        endcase")
        code.append("    end else")
        code.append("        fin_width_select = 2'b01;  // Default")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_independent_gate_control(self, func: IRFunction) -> List[str]:
        """Generate independent gate control."""
        code = []
        
        code.append("// FinFET independent gate control")
        code.append("reg front_gate_enable;")
        code.append("reg back_gate_enable_ctrl;")
        code.append("reg [1:0] gate_control_mode;")
        code.append("")
        
        code.append("always @(*) begin")
        code.append("    case (gate_control_mode)")
        code.append("        2'b00: begin  // Both gates active")
        code.append("            front_gate_enable = 1'b1;")
        code.append("            back_gate_enable_ctrl = 1'b1;")
        code.append("        end")
        code.append("        2'b01: begin  // Front gate only")
        code.append("            front_gate_enable = 1'b1;")
        code.append("            back_gate_enable_ctrl = 1'b0;")
        code.append("        end")
        code.append("        2'b10: begin  // Back gate only")
        code.append("            front_gate_enable = 1'b0;")
        code.append("            back_gate_enable_ctrl = 1'b1;")
        code.append("        end")
        code.append("        2'b11: begin  // Both gates off")
        code.append("            front_gate_enable = 1'b0;")
        code.append("            back_gate_enable_ctrl = 1'b0;")
        code.append("        end")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_power_gating_cells(self, func: IRFunction) -> List[str]:
        """Generate power gating cells."""
        code = []
        
        code.append("// Power gating cells")
        code.append("reg power_gate_control;")
        code.append("reg power_gate_ack;")
        code.append("reg [7:0] power_gate_timer;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    if (power_gate_control) begin")
        code.append("        power_gate_timer <= power_gate_timer + 1;")
        code.append("        if (power_gate_timer > 8'h10)")
        code.append("            power_gate_ack <= 1'b1;")
        code.append("    end else begin")
        code.append("        power_gate_timer <= 8'h0;")
        code.append("        power_gate_ack <= 1'b0;")
        code.append("    end")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_sleep_transistors(self, func: IRFunction) -> List[str]:
        """Generate sleep transistors."""
        code = []
        
        code.append("// Sleep transistors")
        code.append("reg sleep_transistor_enable;")
        code.append("reg [3:0] sleep_transistor_size;")
        code.append("")
        
        code.append("always @(*) begin")
        code.append("    case (power_state)")
        code.append("        PWR_SLEEP: begin")
        code.append("            sleep_transistor_enable = 1'b0;")
        code.append("            sleep_transistor_size = 4'h1;")
        code.append("        end")
        code.append("        PWR_ACTIVE: begin")
        code.append("            sleep_transistor_enable = 1'b1;")
        code.append("            sleep_transistor_size = 4'hF;")
        code.append("        end")
        code.append("        default: begin")
        code.append("            sleep_transistor_enable = 1'b1;")
        code.append("            sleep_transistor_size = 4'h8;")
        code.append("        end")
        code.append("    endcase")
        code.append("end")
        code.append("")
        
        return code
    
    def _generate_retention_registers(self, func: IRFunction) -> List[str]:
        """Generate retention registers."""
        code = []
        
        code.append("// Retention registers")
        code.append("reg [31:0] retention_data;")
        code.append("reg retention_enable;")
        code.append("reg retention_restore;")
        code.append("")
        
        code.append("always @(posedge clk) begin")
        code.append("    if (retention_enable)")
        code.append("        retention_data <= main_data;")
        code.append("    else if (retention_restore)")
        code.append("        main_data <= retention_data;")
        code.append("end")
        code.append("")
        
        return code 