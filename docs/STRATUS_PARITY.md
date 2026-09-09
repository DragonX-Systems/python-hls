# Python-HLS and Cadence Stratus: capability comparison

This document compares the current Python-HLS implementation with the publicly documented Stratus HLS workflow. It is a planning aid, not a claim of compatibility, output equivalence, or production quality of results (QoR).

## Summary

Python-HLS overlaps with the front half of an HLS flow: source parsing, intermediate representation, scheduling, resource allocation, HDL generation, visualization, and simulation-oriented checking. It does **not** yet match Stratus as an implementation-accurate, production silicon flow.

The largest gaps are characterized PPA accuracy, constraint-driven automatic pipelining, broad language and datatype support, standard interfaces, formal verification, hierarchical and multi-clock design, and automated physical-design integration.

## Capability matrix

| Capability | Python-HLS status | Stratus reference capability | Parity assessment |
|---|---|---|---|
| High-level source to RTL | Supported Python subset lowered through AST and IR to Verilog; VHDL generation is available. | Synthesizes SystemC, C/C++, and MATLAB descriptions. | Different frontend; partial workflow overlap. |
| Single-block control/datapath synthesis | Implemented for supported constructs; the project is classified Alpha. | Production synthesis for control- and datapath-centric designs. | Early functional overlap, no production parity. |
| Scheduling | ASAP, ALAP, and list scheduling are exposed through the CLI. | Constraint-driven scheduling tied to target clock and implementation flow. | Partial. |
| Resource allocation and binding | Implemented, including resource sharing and resource reports; JSON resource models can overlay the built-in technology library. | Advanced datapath construction using characterized technology libraries. | Partial; imported numbers enable fast DSE, not implementation-accurate QoR. |
| Loop optimization | Constant folding, dead-code elimination, loop unrolling, and resource sharing are documented. | Broad optimization and architectural-exploration flow. | Partial. |
| Pipelining | Pipeline-related scheduling and experimental HDL-generation paths exist. | Fully and partially pipelined implementations, including stalls, draining, and bubble squashing. | Prototype only; needs correctness and QoR qualification. |
| Area, power, energy, and latency | Estimates use built-in or externally supplied resource-model numbers for fast DSE. | Timing/area use Genus; power analysis uses Joules. | Exploratory estimates only, not signoff-quality parity. |
| Low-power optimization | Experimental clock-gating and power-pattern generators exist. | Power-aware scheduling and implementation-aware low-power optimization. | Experimental; no parity until generated logic and measured results are validated. |
| Streaming and memory structures | FIFO, crossbar, streaming-channel, and modeled AXI-Stream/AXI-Lite elements exist. | Mature communication, bus, memory, and reusable IP libraries. | Partial modeling; not interface/IP parity. |
| Verification | Python-to-RTL comparison using generated testbenches and optional Verilator; equivalence command is available. | Mixed-language verification, assertion synthesis, and formal equivalence integration. | Partial simulation-oriented overlap; no formal parity. |
| Visual analysis | Datapath, scheduled datapath, control-flow, and netlist visualizations. | IDE with source links, graphs, schematics, pipeline analysis, and QoR visualization. | Partial. |
| Hierarchy, concurrency, and CDC | Streaming architecture support exists; no qualified SystemC-style hierarchy, threads, multi-clock, or CDC flow. | Hierarchical, mixed RTL/HLS blocks, multiple threads, and CDC support. | Major gap. |
| Physical implementation / signoff | Generated RTL can be handed to the companion GPU-OpenLane flow for synthesis, place-and-route, OpenSTA timing, DRC, and activity-based power estimation. The handoff is external rather than automated by Python-HLS. | Integrated Cadence digital implementation flow, physical awareness, and ECO support. | Downstream path available; automation, calibration, and ECO parity remain gaps. |

## What can be said today

> Python-HLS is an experimental, Python-first HLS project that provides inspectable scheduling, resource-allocation, HDL-generation, visualization, and simulation-oriented verification workflows for a supported subset of kernels.

Do not claim Stratus compatibility, feature parity, signoff-accurate PPA, or equivalent QoR.

## Evidence and current constraints

- The command surface includes `compile`, `analyze`, `optimize`, `visualize`, `verify-equivalence`, and `validate`.
- The project documents a restricted Python subset; dynamic memory and several dynamic-language behaviors are unsupported.
- The trading-demo test suite validates ten example workloads, but passing compilation tests do not establish RTL equivalence, timing closure, or PPA accuracy for every kernel.
- The RTL testing plan records known broken behavior for selected workloads, including covariance.

## Roadmap to meaningful parity

The best next target is not full product parity. It is a defensible **single-clock, single-block accelerator lane**:

1. Define a strict synthesizable Python subset with fixed-width integer semantics and deterministic type inference.
2. Make pipeline directives and initiation interval constraints produce correct, cycle-accounted RTL; validate on a benchmark suite.
3. Automate the GPU-OpenLane handoff with a characterized-library flow and calibrate estimates against synthesis results.
4. Add standard, verified streaming and memory interfaces with backpressure semantics.
5. Make equivalence checking formal or clearly label it as simulation-based.
6. Publish benchmark results: compile success, RTL equivalence, frequency, area, and power versus a baseline.

Only after this lane is reproducible should the project expand to hierarchy, multiple clocks, broad datatypes, physical awareness, and ECO support.
