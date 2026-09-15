"""
Normalized Technology Library Schema and Metadata tracking for Python-HLS.

This module defines the schema and data classes for characterized technology
libraries, tracking provenance, PVT corners, operating conditions, units,
cell mappings, and design-space exploration (DSE) assumptions.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
from typing import Dict, List, Optional, Any, Union
import json


SCHEMA_VERSION = "1.0"


@dataclass
class NormalizedProvenance:
    """Provenance tracking for an ingested technology library."""
    source_file: str
    source_format: str = "liberty"  # "liberty", "normalized_json", "manual_json"
    sha256: str = ""
    ingested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tool: str = "python-hls-characterization-ingester"
    description: Optional[str] = None

    @classmethod
    def from_file(cls, path: str, source_format: str = "liberty", description: Optional[str] = None) -> 'NormalizedProvenance':
        """Compute SHA256 checksum and build provenance from file."""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return cls(
            source_file=path,
            source_format=source_format,
            sha256=hasher.hexdigest(),
            description=description,
        )


@dataclass
class NormalizedOperatingCondition:
    """PVT (Process, Voltage, Temperature) operating conditions and corner."""
    name: str = "typical"
    process: float = 1.0  # Normalized process factor (1.0 = nominal, >1 slow, <1 fast)
    voltage: float = 1.10  # Operating voltage in Volts
    temperature: float = 25.0  # Temperature in Celsius
    corner: str = "typical"  # e.g., "typical", "slow", "fast", "ss", "ff", "tt"


@dataclass
class NormalizedUnits:
    """Engineering units for characterization values."""
    time: str = "ns"
    voltage: str = "V"
    power: str = "uW"  # Leakage power in microwatts
    energy: str = "pJ"  # Dynamic energy in picojoules
    area: str = "um2"  # Area in square micrometers
    capacitance: str = "fF"  # Load capacitance in femtofarads


@dataclass
class NormalizedAssumptions:
    """DSE characterization assumptions and boundary conditions."""
    clock_frequency_mhz: float = 1000.0
    nominal_load_ff: float = 10.0
    switching_activity: float = 0.1
    drive_strength: str = "X1"
    is_signoff: bool = False
    notes: str = (
        "Early design-space exploration estimates derived from characterized cell data. "
        "Not a foundry signoff model."
    )


@dataclass
class CharacterizationMetadata:
    """Full characterization metadata for a technology library."""
    library_name: str
    tech_node: int  # in nm
    schema_version: str = SCHEMA_VERSION
    provenance: Optional[NormalizedProvenance] = None
    operating_condition: NormalizedOperatingCondition = field(default_factory=NormalizedOperatingCondition)
    units: NormalizedUnits = field(default_factory=NormalizedUnits)
    assumptions: NormalizedAssumptions = field(default_factory=NormalizedAssumptions)
    cell_mappings: Dict[str, str] = field(default_factory=dict)
    unsupported_cells: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        data = {
            "schema_version": self.schema_version,
            "library_name": self.library_name,
            "tech_node": self.tech_node,
            "operating_condition": asdict(self.operating_condition),
            "units": asdict(self.units),
            "assumptions": asdict(self.assumptions),
            "cell_mappings": dict(self.cell_mappings),
            "unsupported_cells": list(self.unsupported_cells),
        }
        if self.provenance:
            data["provenance"] = asdict(self.provenance)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CharacterizationMetadata':
        """Construct CharacterizationMetadata from a dictionary."""
        op_cond_data = data.get("operating_condition", {})
        op_cond = NormalizedOperatingCondition(
            name=str(op_cond_data.get("name", "typical")),
            process=float(op_cond_data.get("process", 1.0)),
            voltage=float(op_cond_data.get("voltage", 1.10)),
            temperature=float(op_cond_data.get("temperature", 25.0)),
            corner=str(op_cond_data.get("corner", "typical")),
        )

        units_data = data.get("units", {})
        units = NormalizedUnits(
            time=str(units_data.get("time", "ns")),
            voltage=str(units_data.get("voltage", "V")),
            power=str(units_data.get("power", "uW")),
            energy=str(units_data.get("energy", "pJ")),
            area=str(units_data.get("area", "um2")),
            capacitance=str(units_data.get("capacitance", "fF")),
        )

        assump_data = data.get("assumptions", {})
        assumptions = NormalizedAssumptions(
            clock_frequency_mhz=float(assump_data.get("clock_frequency_mhz", 1000.0)),
            nominal_load_ff=float(assump_data.get("nominal_load_ff", 10.0)),
            switching_activity=float(assump_data.get("switching_activity", 0.1)),
            drive_strength=str(assump_data.get("drive_strength", "X1")),
            is_signoff=bool(assump_data.get("is_signoff", False)),
            notes=str(assump_data.get("notes", "")),
        )

        provenance = None
        if "provenance" in data and isinstance(data["provenance"], dict):
            prov_data = data["provenance"]
            provenance = NormalizedProvenance(
                source_file=str(prov_data.get("source_file", "")),
                source_format=str(prov_data.get("source_format", "liberty")),
                sha256=str(prov_data.get("sha256", "")),
                ingested_at=str(prov_data.get("ingested_at", "")),
                tool=str(prov_data.get("tool", "python-hls")),
                description=prov_data.get("description"),
            )

        return cls(
            library_name=str(data.get("library_name", "Unknown")),
            tech_node=int(data.get("tech_node", 45)),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            provenance=provenance,
            operating_condition=op_cond,
            units=units,
            assumptions=assumptions,
            cell_mappings=dict(data.get("cell_mappings", {})),
            unsupported_cells=list(data.get("unsupported_cells", [])),
        )

    def summary(self) -> Dict[str, Any]:
        """Produce a concise summary dict suitable for DSE reports."""
        summary_dict = {
            "library_name": self.library_name,
            "tech_node": f"{self.tech_node}nm",
            "corner": self.operating_condition.corner,
            "operating_voltage_v": self.operating_condition.voltage,
            "temperature_c": self.operating_condition.temperature,
            "drive_strength": self.assumptions.drive_strength,
            "is_signoff": self.assumptions.is_signoff,
        }
        if self.provenance:
            summary_dict["source_file"] = self.provenance.source_file
            if self.provenance.sha256:
                summary_dict["sha256_short"] = self.provenance.sha256[:12]
        if self.assumptions.notes:
            summary_dict["assumptions_notes"] = self.assumptions.notes
        return summary_dict


def validate_normalized_schema(payload: Dict[str, Any]) -> None:
    """
    Validate a dictionary against the normalized technology library schema.

    Raises ValueError if payload does not conform to the schema.
    """
    if not isinstance(payload, dict):
        raise ValueError("Technology library payload must be a JSON object")

    if not isinstance(payload.get("resources"), list):
        raise ValueError("Technology library must contain a 'resources' list")

    if not payload["resources"]:
        raise ValueError("Technology library 'resources' list cannot be empty")

    required_resource_fields = {
        "name", "area", "latency", "energy_per_op", "leakage_power",
        "tech_node", "frequency"
    }

    for idx, res in enumerate(payload["resources"]):
        if not isinstance(res, dict):
            raise ValueError(f"Resource item at index {idx} must be an object")
        missing = required_resource_fields - set(res.keys())
        if missing:
            raise ValueError(
                f"Resource item {idx} ('{res.get('name', 'unnamed')}') is missing fields: {', '.join(sorted(missing))}"
            )
        try:
            float(res["area"])
            int(res["latency"])
            float(res["energy_per_op"])
            float(res["leakage_power"])
            int(res["tech_node"])
            float(res["frequency"])
        except (ValueError, TypeError) as err:
            raise ValueError(f"Resource item {idx} has invalid numerical values: {err}") from err

    # Validate tech_node if present
    if "tech_node" in payload:
        try:
            int(payload["tech_node"])
        except (ValueError, TypeError) as err:
            raise ValueError(f"Invalid 'tech_node' in payload: {payload['tech_node']}") from err
