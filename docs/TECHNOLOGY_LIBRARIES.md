# Characterized Foundry Technology Libraries for DSE

Python-HLS supports traceable ingestion of characterized foundry technology data for early design-space exploration (DSE). This allows hardware exploration to move beyond illustrative approximations and uncalibrated overlays by ingesting industry-standard Synopsys Liberty (`.lib`) files and normalized characterization JSON libraries.

---

## 1. Non-Goal & Purpose

> [!IMPORTANT]
> **Not a Foundry Signoff Tool**: Python-HLS uses characterized technology data for **early architectural and design-space exploration (DSE)**—evaluating operation scheduling, resource binding, cycle latencies, and rough PPA trade-offs across nodes and corners. Final timing closure, physical DRC/LVS, signal integrity, and tapeout signoff remain the domain of downstream ASIC physical synthesis pipelines (e.g. GPU-OpenLane, Cadence, or Synopsys).

---

## 2. Ingestion & DSE Architecture

```
                               Foundry Liberty (.lib)
                                        │
                                        ▼
                                 [LibertyParser]
                     (Extracts PVT, units, timing, power, area)
                                        │
                                        ▼
                              [CellToResourceMapper]
               (Maps leaf/macro cells to 32-bit HLS functional units)
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
       [Normalized Characterization]               [TechLibrary Instance]
                 (JSON)                     (Resources + CharacterizationMetadata)
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        ▼
                           [HLS Scheduler & Allocator]
                                        │
                                        ▼
                             [Traceable DSE Reports]
                (Provenance, SHA256, PVT, Voltage, Temp, Assumptions)
```

---

## 3. Public Cell-to-Resource Mapping Specification

Python-HLS defines an inspectable public mapping from characterized standard cell primitives and macro blocks into HLS `ResourceModel`s.

### 3.1 Mapping Strategy

Libraries may provide either **macro-level characterizations** (e.g., dedicated arithmetic blocks) or **standard cell libraries** (leaf logic gates and flip-flops). Python-HLS supports both:

1. **Direct Macro Mapping**: If the library contains characterized macros (such as `ADDER32`, `MULT32`, `SRAM_1KB`), their characterized area, delay, leakage, and energy are mapped directly.
2. **Standard-Cell Compositional Synthesis**: If only standard leaf cells are provided (e.g., Nangate45, FreePDK45, SkyWater 130nm), structural synthesis formulas estimate 32-bit datapath functional units:

| HLS Resource Model | Cell Composition Formula | Latency (Cycles) | Description |
|---|---|:---:|---|
| `Register_1bit` | $1 \times \text{area}(\text{DFF})$ | 1 | 1-bit register flip-flop |
| `Register_32bit` | $32 \times \text{area}(\text{DFF}) \times 1.10$ | 1 | 32-bit register with clock network overhead |
| `Register_64bit` | $64 \times \text{area}(\text{DFF}) \times 1.12$ | 1 | 64-bit register with clock network overhead |
| `Adder_32bit` | $32 \times \text{area}(\text{FA}) \times 1.25$ | 1 (or $\lceil t_{\text{delay}} / T_{\text{clk}} \rceil$) | 32-bit parallel-prefix adder tree |
| `Subtractor_32bit` | $\text{Adder\_32bit} + 32 \times \text{area}(\text{XOR2})$ | 1 | 32-bit subtractor with two's complement logic |
| `Multiplier_32bit` | $900 \times \text{area}(\text{FA})$ (Booth-Wallace tree) | 2 | 32-bit pipelined hardware multiplier |
| `Divider_32bit` | $1.8 \times \text{Multiplier\_32bit}$ | 10 | 32-bit multi-cycle non-restoring divider |
| `BitOp_32bit` | $32 \times \text{area}(\text{XOR2})$ | 1 | 32-bit bitwise logic unit (AND, OR, XOR) |
| `Comparator_32bit` | $32 \times \text{area}(\text{XNOR2}) + 31 \times \text{area}(\text{AND2})$ | 1 | 32-bit equality/inequality comparator |
| `RelationalOp_32bit` | $0.8 \times \text{Subtractor\_32bit}$ | 1 | 32-bit magnitude comparator ($<, \le, >, \ge$) |
| `MUX_32bit` | $32 \times \text{area}(\text{MUX2})$ | 0 | 32-bit 2:1 multiplexer (combinational) |
| `Shifter_32bit` | $160 \times \text{area}(\text{MUX2})$ | 1 | 32-bit 5-stage logarithmic barrel shifter |
| `ALU_32bit` | $\text{Adder} + \text{BitOp} + 2 \times \text{MUX}$ | 1 | Unified 32-bit Arithmetic Logic Unit |
| `AGU_32bit` | $1.2 \times \text{Adder\_32bit}$ | 1 | Address Generation Unit |
| `FSM_Controller` | $16 \times \text{DFF} + 40 \times \text{Logic}$ | 1 | Control state machine and decoders |
| `FIFO_32bit` | $32 \times \text{Register\_32bit} \times 0.70$ | 1 | 32-word circular streaming FIFO buffer |
| `CROSSBAR_32bit` | $16 \times \text{MUX\_32bit}$ | 1 | $4 \times 4$ 32-bit streaming interconnect crossbar |
| `Memory_1KB..64KB` | SRAM bitcell array model scaled to node | 1 - 3 | Static memory / scratchpad models |

### 3.2 Supported Standard Cells

The ingester automatically matches standard library naming conventions and boolean pin functions:
- **Full Adders**: `FA_X1`, `FADD`, `ADDF`
- **Half Adders**: `HA_X1`, `HADD`, `ADDH`
- **Flip-Flops**: `DFF_X1`, `DFCN`, `DFFR`, `DFFQ`
- **Multiplexers**: `MUX2_X1`, `MX2`, `MUX21`
- **Logic Gates**: `XOR2_X1`, `XNOR2_X1`, `AND2_X1`, `OR2_X1`, `NAND2_X1`, `NOR2_X1`, `INV_X1`
- **Arithmetic Macros**: `ADDER32`, `ADD32`, `MULT32`, `MUL32`, `DIV32`, `SRAM_1KB`

### 3.3 Unsupported Constructs

The following physical/backend constructs are explicitly ignored during early HLS DSE and logged in the characterization report:
- **Level Shifters** (`LS_`, `LEVEL_SHIFTER`): Multi-voltage domain crossing cells.
- **Isolation Cells** (`ISO_`): Power-domain boundary clamps.
- **Power Switches** (`HEADER_`, `FOOTER_`): Sleep transistor arrays.
- **I/O & Analog Pads** (`PAD_`, `IOCELL_`): External chip boundary pads.
- **Scan/DFT Sequential Cells** (`SCAN_`, `SDFF_`): Test scan-chain multiplexers.
- **Asynchronous/Multi-clock FIFOs**: Uncharacterized clock-domain crossing circuits.

---

## 4. Normalized Characterization JSON Schema (v1.0)

Characterized technology libraries can be saved and shared in a normalized JSON format that preserves full provenance, PVT corner, operating conditions, and characterization assumptions:

```json
{
  "schema_version": "1.0",
  "library_name": "reference_45nm",
  "tech_node": 45,
  "operating_condition": {
    "name": "typical",
    "process": 1.0,
    "voltage": 1.10,
    "temperature": 25.0,
    "corner": "typical"
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
    "drive_strength": "X1",
    "is_signoff": false,
    "notes": "Synthesized resource models mapped from characterized Liberty cell data."
  },
  "cell_mappings": {
    "FA": "FA_X1",
    "DFF": "DFF_X1",
    "MUX2": "MUX2_X1"
  },
  "unsupported_cells": [
    "LEVEL_SHIFTER_X1: Level shifter (multi-voltage domain logic unsupported in early DSE)"
  ],
  "provenance": {
    "source_file": "examples/technology_libraries/reference_45nm.lib",
    "source_format": "liberty",
    "sha256": "ea13d5f1fd0b79483d930ff295b43ac45a6d1e20a191133c9c12323c6535551e",
    "ingested_at": "2026-09-10T13:43:47Z",
    "tool": "python-hls-characterization-ingester"
  },
  "resources": [
    {
      "name": "Adder_32bit",
      "area": 148.96,
      "latency": 1,
      "energy_per_op": 0.768,
      "leakage_power": 0.616,
      "tech_node": 45,
      "frequency": 1000.0,
      "provenance": {
        "source": "characterized_liberty",
        "derived_from": ["FA_X1", "XOR2_X1"],
        "formula": "32 * area(FA) * 1.25 prefix tree"
      }
    }
  ]
}
```

---

## 5. Usage Workflows

### 5.1 Ingest a Liberty File and Export Normalized JSON

Use the CLI `ingest-liberty` command:

```bash
python -m python_hls.cli ingest-liberty \
  examples/technology_libraries/reference_45nm.lib \
  --output examples/technology_libraries/reference_45nm_characterized.json \
  --tech-node 45 \
  --corner typical \
  --frequency 1000.0 \
  --drive-strength X1
```

### 5.2 Compile with a Characterized Library

Pass either a `.lib` file or a normalized `.json` file to `compile`:

```bash
python -m python_hls.cli compile examples/gcd.py \
  --tech-node 45 \
  --tech-library examples/technology_libraries/reference_45nm.lib
```

Output includes traceability:
```
Compiled examples/gcd.py to examples/gcd.v
Technology node: 45 nm
Tech library: reference_45nm (Corner: typical, Voltage: 1.10V, Temp: 25.0°C)
Provenance: examples/technology_libraries/reference_45nm.lib [SHA256: ea13d5f1fd0b]
Assumptions: Synthesized resource models mapped from characterized Liberty cell data.
```

The generated report (`<kernel>_report.json`) preserves the full `technology_metadata` block.

### 5.3 Multi-Node DSE Analysis

Compare a kernel across multiple technology nodes using characterized reference data:

```bash
python -m python_hls.cli analyze examples/gcd.py \
  --tech-nodes 45,28,16,7 \
  --tech-library examples/technology_libraries/reference_45nm_characterized.json
```

Output comparison table:
```
Technology comparison:
=========================================================================================
Node (nm)  Corner/Library           Area (μm²)     Power (mW)     Latency (cycles)
-----------------------------------------------------------------------------------------
7          typical/reference_45nm   84.10          2.49           34             
16         typical/reference_45nm   267.57         3.72           34             
28         typical/reference_45nm   482.61         5.09           34             
45         typical/reference_45nm   1138.05        6.93           34             

Library Source: examples/technology_libraries/reference_45nm.lib
Assumptions: Synthesized resource models mapped from characterized Liberty cell data.
```

### 5.4 Python API Usage

```python
from python_hls import HLS
from python_hls.tech import TechLibrary

# Load directly from Liberty
library = TechLibrary.from_liberty(
    "examples/technology_libraries/reference_45nm.lib",
    tech_node=45,
    operating_condition="typical"
)

# Inspect characterization metadata
metadata = library.get_metadata_summary()
print("Library:", metadata["library_name"])
print("PVT Corner:", metadata["corner"])
print("Voltage:", metadata["operating_voltage_v"], "V")

# Export to normalized JSON
library.to_normalized_json("my_characterized_45nm.json")

# Compile with HLS
hls = HLS(tech_node=45, tech_library=library)
netlist = hls.compile("examples/gcd.py", target="verilog")
metrics = hls.get_performance_metrics()
print("Total Area:", metrics["total_area"], "μm²")
print("Provenance:", metrics["technology_metadata"]["source_file"])
```
