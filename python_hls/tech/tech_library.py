"""
Technology library with models for different technology nodes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, Any
import json
import math

from .schema import (
    CharacterizationMetadata,
    NormalizedOperatingCondition,
    NormalizedUnits,
    NormalizedAssumptions,
    NormalizedProvenance,
    validate_normalized_schema,
)


@dataclass
class ResourceModel:
    """Model for a hardware resource at a specific technology node."""
    name: str  # e.g., "ALU", "Register", "Multiplier", etc.
    area: float  # in μm²
    latency: int  # in clock cycles
    energy_per_op: float  # in pJ
    leakage_power: float  # in μW
    tech_node: int  # in nm
    frequency: float  # in MHz
    provenance: Optional[Dict[str, Any]] = None
    
    def scale_to_node(self, new_node: int) -> 'ResourceModel':
        """
        Scale the resource model to a different technology node using improved scaling laws.
        
        This implementation uses more realistic scaling factors based on real-world
        semiconductor data, accounting for the slowing of Moore's Law and process
        limitations at advanced nodes.
        
        Args:
            new_node: Technology node in nm to scale to
            
        Returns:
            Scaled resource model
        """
        # Improved area scaling based on real-world semiconductor data
        # Classic scaling law was area ∝ (node_ratio)², but this breaks down
        # at advanced nodes due to physical limitations
        
        node_ratio = new_node / self.tech_node
        
        # Define realistic scaling factors based on industry data
        # These account for the diminishing returns in density scaling
        if self.tech_node >= 45 and new_node >= 45:
            # Legacy nodes (45nm and above) - closer to classical scaling
            area_scaling_exp = 1.85  # Slightly less than perfect quadratic
        elif self.tech_node >= 28 and new_node >= 28:
            # Mid-range nodes (28nm-45nm) - reduced scaling effectiveness
            area_scaling_exp = 1.70
        elif self.tech_node >= 16 and new_node >= 16:
            # Advanced nodes (16nm-28nm) - significant deviation from Moore's Law
            area_scaling_exp = 1.50
        elif self.tech_node >= 7 and new_node >= 7:
            # Leading edge nodes (7nm-16nm) - heavily diminished scaling
            area_scaling_exp = 1.25
        else:
            # Cutting edge nodes (3nm-7nm) - minimal scaling benefits
            area_scaling_exp = 1.10
        
        # Handle cross-regime scaling (e.g., 45nm -> 7nm)
        if (self.tech_node > new_node and 
            (self.tech_node >= 28 and new_node < 28) or
            (self.tech_node >= 16 and new_node < 16) or
            (self.tech_node >= 7 and new_node < 7)):
            # For large jumps across technology generations, use average scaling
            area_scaling_exp = 1.40
        elif (new_node > self.tech_node and 
              (new_node >= 28 and self.tech_node < 28) or
              (new_node >= 16 and self.tech_node < 16) or
              (new_node >= 7 and self.tech_node < 7)):
            # Reverse scaling (going to larger nodes)
            area_scaling_exp = 1.60
        
        # Apply realistic area scaling with the determined exponent
        area_scale = node_ratio ** area_scaling_exp
        
        # Add process-specific corrections based on real foundry data
        # TSMC scaling factors from industry reports
        correction_factor = 1.0
        if self.tech_node == 45 and new_node == 28:
            correction_factor = 0.95  # 45nm->28nm slightly better than model
        elif self.tech_node == 28 and new_node == 16:
            correction_factor = 1.10  # 28nm->16nm worse than model
        elif self.tech_node == 16 and new_node == 7:
            correction_factor = 1.15  # 16nm->7nm significantly worse
        elif self.tech_node == 28 and new_node == 7:
            correction_factor = 1.08  # 28nm->7nm aggregate effect
        
        area_scale *= correction_factor
        
        # Energy scales more linearly with voltage reduction
        # Voltage scaling has also slowed down significantly
        if node_ratio < 1:  # Going to smaller node (better technology)
            # Energy reduction is much less aggressive in modern nodes
            if new_node <= 7:
                energy_scale = node_ratio ** 0.8  # Very conservative energy scaling
            elif new_node <= 16:
                energy_scale = node_ratio ** 0.9  # Moderate energy scaling
            else:
                energy_scale = node_ratio ** 1.0  # Classical linear scaling
        else:  # Going to larger node (worse technology)
            energy_scale = node_ratio ** 1.1  # Penalty for going backwards
        
        # Leakage power scaling - depends heavily on voltage and threshold voltage
        # Modern nodes have worse leakage characteristics than classical scaling predicts
        if node_ratio < 1:  # Smaller nodes
            if new_node <= 7:
                leakage_scale = node_ratio ** 0.4  # Leakage increases rapidly at small nodes
            elif new_node <= 16:
                leakage_scale = node_ratio ** 0.6  # Moderate leakage scaling
            else:
                leakage_scale = node_ratio ** 0.7  # Classical scaling
        else:  # Larger nodes
            leakage_scale = node_ratio ** 0.8  # Better leakage control at larger nodes
        
        # Frequency scaling is very conservative in modern process nodes
        # Performance gains have significantly diminished
        raw_freq_ratio = self.tech_node / new_node
        
        if raw_freq_ratio > 1:
            # Improving technology (smaller node)
            if new_node <= 7:
                freq_scale = raw_freq_ratio ** 0.25  # Very limited frequency improvement
            elif new_node <= 16:
                freq_scale = raw_freq_ratio ** 0.30  # Modest frequency improvement
            else:
                freq_scale = raw_freq_ratio ** 0.35  # Classical scaling behavior
        else:
            # Larger technology node (worse performance)
            freq_scale = raw_freq_ratio ** 0.8  # Less penalty for going to larger nodes
        
        # Apply frequency scaling caps based on real-world limitations
        max_freq_scale = 2.0 if new_node <= 7 else 2.5  # Lower cap for advanced nodes
        min_freq_scale = 0.3
        freq_scale = max(min_freq_scale, min(max_freq_scale, freq_scale))
        
        scaled_prov = dict(self.provenance) if self.provenance else {}
        scaled_prov["scaled_from_node"] = self.tech_node
        scaled_prov["target_node"] = new_node
        scaled_prov["scaling_method"] = "empirical_process_scaling"

        return ResourceModel(
            name=self.name,
            area=self.area * area_scale,
            latency=self.latency,  # Latency in cycles remains the same
            energy_per_op=self.energy_per_op * energy_scale,
            leakage_power=self.leakage_power * leakage_scale,
            tech_node=new_node,
            frequency=self.frequency * freq_scale,
            provenance=scaled_prov,
        )


class TechLibrary:
    """Technology library with models for different resources and technology nodes."""
    
    def __init__(self, tech_node: int = 45):
        """
        Initialize the technology library.
        
        Args:
            tech_node: Default technology node in nm
        """
        self.tech_node = tech_node
        self.resources: Dict[str, Dict[int, ResourceModel]] = {}
        self.metadata: Optional[CharacterizationMetadata] = None
        
        # Initialize default library with 45nm models
        self._init_default_library()
    
    def _init_default_library(self) -> None:
        """Initialize default resource models at 45nm."""
        # 45nm models based on approximations from literature
        self.add_resource(ResourceModel(
            name="Register_1bit",
            area=1.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.01,  # pJ
            leakage_power=0.1,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Register_32bit",
            area=32.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.32,  # pJ
            leakage_power=3.2,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Register_64bit",
            area=64.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.64,  # pJ
            leakage_power=6.4,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        # More specialized ALU components
        self.add_resource(ResourceModel(
            name="Adder_32bit",
            area=180.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.8,  # pJ
            leakage_power=8.0,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Subtractor_32bit",
            area=200.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.9,  # pJ
            leakage_power=9.0,  # μW
            tech_node=45,
            frequency=950  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="BitOp_32bit",  # For bit-wise operations (AND, OR, XOR, etc.)
            area=150.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.5,  # pJ
            leakage_power=5.0,  # μW
            tech_node=45,
            frequency=1200  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Comparator_32bit",  # For equality comparisons (==, !=)
            area=120.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.4,  # pJ
            leakage_power=4.0,  # μW
            tech_node=45,
            frequency=1100  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="RelationalOp_32bit",  # For relational comparisons (<, >, <=, >=)
            area=140.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.5,  # pJ
            leakage_power=5.0,  # μW
            tech_node=45,
            frequency=1050  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Shifter_32bit",  # For shift operations (<<, >>)
            area=160.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=0.6,  # pJ
            leakage_power=6.0,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        # Add Multiplexer resource
        self.add_resource(ResourceModel(
            name="MUX_32bit",  # For input selection
            area=100.0,  # μm²
            latency=0,  # Combinational logic, no additional latency
            energy_per_op=0.3,  # pJ
            leakage_power=3.0,  # μW
            tech_node=45,
            frequency=1500  # MHz - typically faster than other components
        ))
        
        # Keep the general ALU for complex operations
        self.add_resource(ResourceModel(
            name="ALU_32bit",
            area=500.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=1.5,  # pJ
            leakage_power=20.0,  # μW
            tech_node=45,
            frequency=800  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Multiplier_32bit",
            area=2500.0,  # μm²
            latency=2,  # 2 cycles
            energy_per_op=10.0,  # pJ
            leakage_power=50.0,  # μW
            tech_node=45,
            frequency=600  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Divider_32bit",
            area=5000.0,  # μm²
            latency=10,  # 10 cycles
            energy_per_op=50.0,  # pJ
            leakage_power=100.0,  # μW
            tech_node=45,
            frequency=400  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Memory_1KB",
            area=10000.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=5.0,  # pJ
            leakage_power=200.0,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Memory_4KB",
            area=38000.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=15.0,  # pJ
            leakage_power=500.0,  # μW
            tech_node=45,
            frequency=950  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Scratchpad_1KB",
            area=8000.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=4.0,  # pJ
            leakage_power=150.0,  # μW
            tech_node=45,
            frequency=1200  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Scratchpad_4KB",
            area=30000.0,  # μm²
            latency=1,  # 1 cycle
            energy_per_op=12.0,  # pJ
            leakage_power=400.0,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Scratchpad_16KB",
            area=100000.0,  # μm²
            latency=2,  # 2 cycles 
            energy_per_op=35.0,  # pJ
            leakage_power=800.0,  # μW
            tech_node=45,
            frequency=800  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Scratchpad_64KB",
            area=380000.0,  # μm²
            latency=3,  # 3 cycles (larger memory has higher latency)
            energy_per_op=120.0,  # pJ
            leakage_power=2400.0,  # μW
            tech_node=45,
            frequency=750  # MHz
        ))
        
        self.add_resource(ResourceModel(
            name="Cache_16KB",
            area=150000.0,  # μm² (higher than scratchpad due to tag storage and control logic)
            latency=2,  # 2 cycles average case (can vary with hit/miss)
            energy_per_op=45.0,  # pJ
            leakage_power=1200.0,  # μW
            tech_node=45,
            frequency=900  # MHz
        ))
        
        # Add Address Generation Unit (AGU) and FSM Controller resources
        self.add_resource(ResourceModel(
            name="AGU_32bit",  # Address Generation Unit
            area=400.0,  # μm² - more complex than ALU due to address calculation logic
            latency=1,  # 1 cycle for address generation
            energy_per_op=1.2,  # pJ - moderate energy for address calculations
            leakage_power=12.0,  # μW
            tech_node=45,
            frequency=800  # MHz - slightly slower than simple ALU due to complexity
        ))
        
        self.add_resource(ResourceModel(
            name="FSM_Controller",  # Finite State Machine Controller
            area=250.0,  # μm² - includes state registers, next-state logic, and control decoders
            latency=1,  # 1 cycle for state transitions
            energy_per_op=0.8,  # pJ - mainly for state register updates
            leakage_power=8.0,  # μW
            tech_node=45,
            frequency=1000  # MHz - can run at full speed
        ))
        
        self.add_resource(ResourceModel(
            name="Memory_Controller",  # Memory Controller with address generation
            area=800.0,  # μm² - includes AGU, control logic, and interface logic
            latency=1,  # 1 cycle for memory access initiation
            energy_per_op=2.5,  # pJ - includes address generation and control
            leakage_power=25.0,  # μW
            tech_node=45,
            frequency=700  # MHz - limited by memory interface timing
        ))
        
        # FIFO resource for streaming applications
        self.add_resource(ResourceModel(
            name="FIFO_32bit",
            area=5000.0,  # μm² (sized for typical depth of 32 elements)
            latency=1,  # 1 cycle for read/write
            energy_per_op=3.0,  # pJ
            leakage_power=100.0,  # μW
            tech_node=45,
            frequency=1000  # MHz
        ))
        
        # Crossbar resource for streaming interconnect
        self.add_resource(ResourceModel(
            name="CROSSBAR_32bit",
            area=7500.0,  # μm² (sized for typical 4x4 crossbar)
            latency=1,  # 1 cycle for routing
            energy_per_op=4.5,  # pJ
            leakage_power=150.0,  # μW
            tech_node=45,
            frequency=900  # MHz
        ))
    
    def add_resource(self, resource: ResourceModel) -> None:
        """
        Add a resource model to the library.
        
        Args:
            resource: Resource model to add
        """
        if resource.name not in self.resources:
            self.resources[resource.name] = {}
        
        self.resources[resource.name][resource.tech_node] = resource

    @classmethod
    def from_json(cls, path: str, tech_node: Optional[int] = None) -> 'TechLibrary':
        """Create a technology library by overlaying resource models from JSON.

        Supports both normalized characterized technology libraries (Schema 1.0)
        and legacy JSON overlays. Supplied models replace the built-in models.
        """
        try:
            with open(path, 'r', encoding='utf-8') as source:
                payload = json.load(source)
        except OSError as error:
            raise ValueError(f"Unable to read technology library '{path}': {error}") from error
        except json.JSONDecodeError as error:
            raise ValueError(f"Technology library '{path}' is not valid JSON: {error}") from error

        if not isinstance(payload, dict) or not isinstance(payload.get('resources'), list):
            raise ValueError("Technology library JSON must contain a 'resources' array")

        selected_node = tech_node if tech_node is not None else payload.get('tech_node', 45)
        if not isinstance(selected_node, int):
            raise ValueError("Technology library 'tech_node' must be an integer")

        library = cls(tech_node=selected_node)

        # Check if this is a normalized characterization schema document
        if "schema_version" in payload or "operating_condition" in payload or "provenance" in payload:
            validate_normalized_schema(payload)
            metadata = CharacterizationMetadata.from_dict(payload)
            metadata.tech_node = selected_node
            library.metadata = metadata
        else:
            # Legacy hand-authored JSON overlay
            library.metadata = CharacterizationMetadata(
                library_name="custom_json_overlay",
                tech_node=selected_node,
                provenance=NormalizedProvenance(source_file=path, source_format="manual_json"),
                assumptions=NormalizedAssumptions(notes="Hand-authored JSON resource overlay."),
            )

        required_fields = {
            'name', 'area', 'latency', 'energy_per_op', 'leakage_power',
            'tech_node', 'frequency',
        }
        for index, item in enumerate(payload['resources']):
            if not isinstance(item, dict):
                raise ValueError(f"Technology library resource {index} must be an object")
            missing = required_fields - item.keys()
            if missing:
                raise ValueError(
                    f"Technology library resource {index} is missing: {', '.join(sorted(missing))}"
                )
            try:
                resource = ResourceModel(
                    name=str(item['name']),
                    area=float(item['area']),
                    latency=int(item['latency']),
                    energy_per_op=float(item['energy_per_op']),
                    leakage_power=float(item['leakage_power']),
                    tech_node=int(item['tech_node']),
                    frequency=float(item['frequency']),
                    provenance=item.get('provenance'),
                )
            except (TypeError, ValueError) as error:
                raise ValueError(f"Technology library resource {index} has an invalid value") from error
            library.add_resource(resource)

        return library

    @classmethod
    def from_liberty(
        cls,
        path: str,
        tech_node: Optional[int] = None,
        operating_condition: Optional[str] = None,
        target_frequency_mhz: float = 1000.0,
        drive_strength: str = "X1",
        user_cell_mapping: Optional[Dict[str, str]] = None,
    ) -> 'TechLibrary':
        """Create a technology library by ingesting a characterized Synopsys Liberty (.lib) file.

        Args:
            path: Filepath to the .lib file
            tech_node: Optional technology node in nm (defaults to library inferred or 45nm)
            operating_condition: Corner or operating condition name (e.g. 'typical', 'slow')
            target_frequency_mhz: Operating clock frequency in MHz for latency determination
            drive_strength: Preferred drive strength variant to match (e.g. 'X1', 'X2')
            user_cell_mapping: Optional custom cell-to-primitive mapping dictionary
        """
        import re
        from .liberty_parser import LibertyParser
        from .cell_mapping import CellToResourceMapper

        parsed_lib = LibertyParser.parse_file(path)

        # Determine native characterization node of the Liberty file
        m = re.search(r'(\d+)\s*nm', parsed_lib.name, re.IGNORECASE)
        native_node = int(m.group(1)) if m else 45

        mapper = CellToResourceMapper(
            tech_node=native_node,
            target_frequency_mhz=target_frequency_mhz,
            drive_strength=drive_strength,
            user_cell_mapping=user_cell_mapping,
        )

        resources, metadata = mapper.build_resource_models(
            parsed_lib,
            operating_condition_name=operating_condition,
        )

        active_node = tech_node if tech_node is not None else native_node
        metadata.tech_node = active_node

        # Compute provenance
        metadata.provenance = NormalizedProvenance.from_file(
            path,
            source_format="liberty",
            description=f"Ingested from {parsed_lib.name} ({parsed_lib.technology})"
        )

        library = cls(tech_node=active_node)
        library.metadata = metadata

        for item in resources:
            res = ResourceModel(
                name=str(item['name']),
                area=float(item['area']),
                latency=int(item['latency']),
                energy_per_op=float(item['energy_per_op']),
                leakage_power=float(item['leakage_power']),
                tech_node=int(item['tech_node']),
                frequency=float(item['frequency']),
                provenance=item.get('provenance'),
            )
            library.add_resource(res)

        return library

    @classmethod
    def from_file(cls, path: str, tech_node: Optional[int] = None, **kwargs) -> 'TechLibrary':
        """Load a technology library from either Liberty (.lib) or JSON (.json) file."""
        if path.endswith('.lib'):
            return cls.from_liberty(path, tech_node=tech_node, **kwargs)
        return cls.from_json(path, tech_node=tech_node)

    def to_normalized_json(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Export current library to normalized characterization JSON schema."""
        meta_dict = self.metadata.to_dict() if self.metadata else {
            "schema_version": "1.0",
            "library_name": f"TechnologyLibrary_{self.tech_node}nm",
            "tech_node": self.tech_node,
            "operating_condition": {
                "name": "nominal",
                "process": 1.0,
                "voltage": 1.10,
                "temperature": 25.0,
                "corner": "nominal"
            },
            "units": {
                "time": "ns",
                "voltage": "V",
                "power": "uW",
                "energy": "pJ",
                "area": "um2",
                "capacitance": "fF"
            },
            "assumptions": {
                "clock_frequency_mhz": 1000.0,
                "nominal_load_ff": 10.0,
                "switching_activity": 0.1,
                "drive_strength": "nominal",
                "is_signoff": False,
                "notes": "Exported from Python-HLS technology library."
            },
            "cell_mappings": {},
            "unsupported_cells": []
        }

        # Export active resources for current tech node
        resource_list = []
        for res_name in sorted(self.resources.keys()):
            res = self.get_resource(res_name, self.tech_node)
            res_dict = {
                "name": res.name,
                "area": round(res.area, 2),
                "latency": res.latency,
                "energy_per_op": round(res.energy_per_op, 4),
                "leakage_power": round(res.leakage_power, 3),
                "tech_node": res.tech_node,
                "frequency": round(res.frequency, 1),
            }
            if res.provenance:
                res_dict["provenance"] = res.provenance
            resource_list.append(res_dict)

        meta_dict["resources"] = resource_list

        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(meta_dict, f, indent=2)

        return meta_dict

    def get_metadata_summary(self) -> Dict[str, Any]:
        """Provide a concise metadata summary for DSE reports."""
        if self.metadata:
            return self.metadata.summary()
        return {
            "library_name": "built_in_default",
            "tech_node": f"{self.tech_node}nm",
            "corner": "nominal",
            "operating_voltage_v": 1.10,
            "temperature_c": 25.0,
            "drive_strength": "nominal",
            "is_signoff": False,
            "source_file": "built-in approximations",
        }
    
    def get_resource(self, name: str, tech_node: Optional[int] = None) -> ResourceModel:
        """
        Get a resource model from the library.
        
        Args:
            name: Resource name
            tech_node: Technology node (default is library default)
            
        Returns:
            Resource model
            
        Raises:
            ValueError: If resource not found
        """
        if tech_node is None:
            tech_node = self.tech_node
        
        if name not in self.resources:
            raise ValueError(f"Resource '{name}' not found in technology library")
        
        # If exact match for tech node exists, return it
        if tech_node in self.resources[name]:
            return self.resources[name][tech_node]
        
        # Otherwise find closest tech node and scale
        available_nodes = list(self.resources[name].keys())
        closest_node = min(available_nodes, key=lambda x: abs(x - tech_node))
        base_resource = self.resources[name][closest_node]
        
        # Scale resource to desired technology node
        return base_resource.scale_to_node(tech_node)
    
    def set_tech_node(self, tech_node: int) -> None:
        """
        Set the default technology node for the library.
        
        Args:
            tech_node: Technology node in nm
        """
        self.tech_node = tech_node
