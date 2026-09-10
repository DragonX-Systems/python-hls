"""
Synopsys Liberty (.lib) format parser for Python-HLS.

Parses Liberty libraries containing standard cells, macro models, operating
conditions, timing tables, leakage power, and pin definitions into an inspectable
object hierarchy without external dependencies.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union
import logging

logger = logging.getLogger(__name__)


@dataclass
class LibertyTiming:
    """Timing arc definition from Liberty cell pin."""
    related_pin: Optional[str] = None
    timing_type: Optional[str] = None
    timing_sense: Optional[str] = None
    cell_rise: float = 0.0  # in ns
    cell_fall: float = 0.0  # in ns
    rise_transition: float = 0.0  # in ns
    fall_transition: float = 0.0  # in ns

    @property
    def nominal_delay(self) -> float:
        """Max of cell_rise and cell_fall as conservative delay in ns."""
        return max(self.cell_rise, self.cell_fall)


@dataclass
class LibertyPin:
    """Pin in a Liberty cell."""
    name: str
    direction: str = "internal"  # input, output, inout, internal
    capacitance: float = 0.0  # in fF
    function: Optional[str] = None
    timing: List[LibertyTiming] = field(default_factory=list)


@dataclass
class LibertyCell:
    """Standard cell or macro block in a Liberty library."""
    name: str
    area: float = 0.0  # in μm²
    cell_leakage_power: float = 0.0  # in μW
    dynamic_energy_per_toggle: float = 0.0  # in pJ
    pins: Dict[str, LibertyPin] = field(default_factory=dict)
    cell_footprint: Optional[str] = None
    is_macro: bool = False
    raw_attributes: Dict[str, Any] = field(default_factory=dict)

    def get_max_delay(self) -> float:
        """Get the maximum propagation delay across all output pin timing arcs."""
        max_d = 0.0
        for pin in self.pins.values():
            if pin.direction in ("output", "inout"):
                for t in pin.timing:
                    if t.nominal_delay > max_d:
                        max_d = t.nominal_delay
        return max_d

    def get_output_pins(self) -> List[LibertyPin]:
        """Return all output pins."""
        return [p for p in self.pins.values() if p.direction in ("output", "inout")]

    def get_input_pins(self) -> List[LibertyPin]:
        """Return all input pins."""
        return [p for p in self.pins.values() if p.direction == "input"]


@dataclass
class OperatingCondition:
    """Operating condition / PVT corner extracted from Liberty library."""
    name: str
    process: float = 1.0
    voltage: float = 1.10  # in V
    temperature: float = 25.0  # in °C


@dataclass
class LibertyLibrary:
    """Top-level representation of a parsed Liberty library."""
    name: str
    technology: str = "cmos"
    delay_model: str = "table_lookup"
    time_unit_ns: float = 1.0  # multiplier to convert to ns
    voltage_unit_v: float = 1.0  # multiplier to convert to V
    power_unit_uw: float = 1.0  # multiplier to convert to μW
    capacitive_load_unit_ff: float = 1.0  # multiplier to convert to fF
    nom_process: float = 1.0
    nom_voltage: float = 1.10
    nom_temperature: float = 25.0
    default_operating_condition_name: Optional[str] = None
    operating_conditions: Dict[str, OperatingCondition] = field(default_factory=dict)
    cells: Dict[str, LibertyCell] = field(default_factory=dict)
    raw_attributes: Dict[str, Any] = field(default_factory=dict)

    def get_operating_condition(self, name: Optional[str] = None) -> OperatingCondition:
        """Retrieve specified or default operating condition."""
        if name and name in self.operating_conditions:
            return self.operating_conditions[name]
        if self.default_operating_condition_name and self.default_operating_condition_name in self.operating_conditions:
            return self.operating_conditions[self.default_operating_condition_name]
        if self.operating_conditions:
            first_key = next(iter(self.operating_conditions))
            return self.operating_conditions[first_key]
        return OperatingCondition(
            name="nominal",
            process=self.nom_process,
            voltage=self.nom_voltage,
            temperature=self.nom_temperature,
        )


class LibertyLexer:
    """Tokenizer for Synopsys Liberty files."""

    def __init__(self, content: str):
        self.content = content
        self.pos = 0
        self.length = len(content)

    def _strip_comments_and_whitespace(self):
        while self.pos < self.length:
            # Skip standard whitespace and line continuations
            if self.content[self.pos].isspace():
                self.pos += 1
                continue
            # Line continuation with backslash \
            if self.content[self.pos] == '\\' and self.pos + 1 < self.length and self.content[self.pos + 1] in ('\r', '\n'):
                self.pos += 2
                continue
            # C-style comment /* ... */
            if self.pos + 1 < self.length and self.content[self.pos:self.pos + 2] == '/*':
                end = self.content.find('*/', self.pos + 2)
                if end == -1:
                    self.pos = self.length
                else:
                    self.pos = end + 2
                continue
            # C++-style comment // ...
            if self.pos + 1 < self.length and self.content[self.pos:self.pos + 2] == '//':
                end = self.content.find('\n', self.pos + 2)
                if end == -1:
                    self.pos = self.length
                else:
                    self.pos = end + 1
                continue
            break

    def next_token(self) -> Optional[Tuple[str, str]]:
        """Return (token_type, token_value) or None if EOF."""
        self._strip_comments_and_whitespace()
        if self.pos >= self.length:
            return None

        char = self.content[self.pos]

        # Single-character tokens
        if char in ('{', '}', '(', ')', ':', ';', ','):
            self.pos += 1
            return (char, char)

        # Quoted strings
        if char in ('"', "'"):
            quote = char
            self.pos += 1
            start = self.pos
            val = []
            while self.pos < self.length:
                if self.content[self.pos] == '\\':
                    # escaped character or line continuation
                    if self.pos + 1 < self.length:
                        if self.content[self.pos + 1] in ('\n', '\r'):
                            self.pos += 2
                            continue
                        val.append(self.content[self.pos + 1])
                        self.pos += 2
                        continue
                if self.content[self.pos] == quote:
                    self.pos += 1
                    break
                val.append(self.content[self.pos])
                self.pos += 1
            return ('STRING', "".join(val))

        # Identifiers, numbers, keywords
        start = self.pos
        while self.pos < self.length:
            c = self.content[self.pos]
            if c.isspace() or c in ('{', '}', '(', ')', ':', ';', ',', '"', "'"):
                break
            self.pos += 1

        val = self.content[start:self.pos]
        return ('IDENT', val)


class LibertyParser:
    """Parser for Synopsys Liberty files."""

    def __init__(self, content: str):
        self.lexer = LibertyLexer(content)
        self.current_token = self.lexer.next_token()

    def _advance(self):
        self.current_token = self.lexer.next_token()

    def _peek(self) -> Optional[Tuple[str, str]]:
        return self.current_token

    def _match(self, expected_type: str) -> str:
        if not self.current_token or self.current_token[0] != expected_type:
            got = self.current_token[0] if self.current_token else "EOF"
            raise ValueError(f"Liberty parse error: expected '{expected_type}', got '{got}'")
        val = self.current_token[1]
        self._advance()
        return val

    def parse(self) -> LibertyLibrary:
        """Parse Liberty file into LibertyLibrary."""
        tok = self._peek()
        if not tok:
            raise ValueError("Empty Liberty content")

        # Expect top-level library group: library ( NAME ) { ... }
        if tok[0] == 'IDENT' and tok[1] == 'library':
            self._advance()
            name = "unknown"
            if self._peek() and self._peek()[0] == '(':
                self._advance()
                if self._peek() and self._peek()[0] in ('IDENT', 'STRING'):
                    name = self._peek()[1]
                    self._advance()
                self._match(')')
            self._match('{')
            library = LibertyLibrary(name=name)
            self._parse_library_body(library)
            return library
        else:
            raise ValueError(f"Liberty root must start with 'library', got '{tok[1]}'")

    def _parse_library_body(self, lib: LibertyLibrary):
        while self._peek() and self._peek()[0] != '}':
            tok = self._peek()
            if tok[0] not in ('IDENT', 'STRING'):
                self._advance()
                continue

            name = tok[1]
            self._advance()

            # Check what follows: ':' (attribute) or '(' (group or complex attribute)
            next_tok = self._peek()
            if not next_tok:
                break

            if next_tok[0] == ':':
                self._advance()
                val = self._parse_value()
                if self._peek() and self._peek()[0] == ';':
                    self._advance()
                self._handle_library_attribute(lib, name, val)

            elif next_tok[0] == '(':
                # Group or complex attribute
                args = self._parse_arg_list()
                following = self._peek()
                if following and following[0] == '{':
                    # Group definition
                    self._advance()
                    self._handle_library_group(lib, name, args)
                elif following and following[0] == ';':
                    self._advance()
                    self._handle_library_complex_attr(lib, name, args)
                else:
                    if following and following[0] == '}':
                        break
                    self._advance()
            else:
                self._advance()

        if self._peek() and self._peek()[0] == '}':
            self._advance()

    def _parse_arg_list(self) -> List[str]:
        self._match('(')
        args = []
        while self._peek() and self._peek()[0] != ')':
            tok = self._peek()
            if tok[0] in ('IDENT', 'STRING'):
                args.append(tok[1])
                self._advance()
            elif tok[0] == ',':
                self._advance()
            else:
                self._advance()
        self._match(')')
        return args

    def _parse_value(self) -> str:
        tok = self._peek()
        if not tok:
            return ""
        val = tok[1]
        self._advance()
        return val

    def _handle_library_attribute(self, lib: LibertyLibrary, name: str, val: str):
        val_clean = val.strip().strip('"').strip("'")
        lib.raw_attributes[name] = val_clean

        if name == 'technology':
            lib.technology = val_clean
        elif name == 'delay_model':
            lib.delay_model = val_clean
        elif name == 'nom_process':
            try:
                lib.nom_process = float(val_clean)
            except ValueError:
                pass
        elif name == 'nom_voltage':
            try:
                lib.nom_voltage = float(val_clean)
            except ValueError:
                pass
        elif name == 'nom_temperature':
            try:
                lib.nom_temperature = float(val_clean)
            except ValueError:
                pass
        elif name == 'default_operating_conditions':
            lib.default_operating_condition_name = val_clean
        elif name == 'time_unit':
            # e.g., "1ns" -> 1.0, "1ps" -> 0.001
            lib.time_unit_ns = self._parse_time_unit(val_clean)
        elif name == 'voltage_unit':
            # e.g., "1V" -> 1.0, "100mV" -> 0.1, "1mV" -> 0.001
            lib.voltage_unit_v = self._parse_voltage_unit(val_clean)
        elif name == 'leakage_power_unit':
            # e.g., "1pW" -> 1e-6, "1nW" -> 1e-3, "1uW" -> 1.0, "1mW" -> 1000.0
            lib.power_unit_uw = self._parse_power_unit(val_clean)

    def _handle_library_complex_attr(self, lib: LibertyLibrary, name: str, args: List[str]):
        lib.raw_attributes[name] = args
        if name == 'capacitive_load_unit':
            # e.g. (1, ff) or (0.1, pf)
            if len(args) >= 2:
                try:
                    mult = float(args[0])
                    unit = args[1].lower()
                    if 'pf' in unit:
                        lib.capacitive_load_unit_ff = mult * 1000.0
                    elif 'ff' in unit:
                        lib.capacitive_load_unit_ff = mult * 1.0
                except ValueError:
                    pass

    def _handle_library_group(self, lib: LibertyLibrary, group_name: str, args: List[str]):
        if group_name == 'cell':
            cell_name = args[0] if args else "unnamed_cell"
            cell = LibertyCell(name=cell_name)
            self._parse_cell_body(lib, cell)
            lib.cells[cell_name] = cell
        elif group_name == 'operating_conditions':
            cond_name = args[0] if args else "default"
            cond = OperatingCondition(
                name=cond_name,
                process=lib.nom_process,
                voltage=lib.nom_voltage,
                temperature=lib.nom_temperature
            )
            self._parse_operating_conditions(cond)
            lib.operating_conditions[cond_name] = cond
        else:
            # Skip unknown group
            self._skip_group_body()

    def _parse_operating_conditions(self, cond: OperatingCondition):
        while self._peek() and self._peek()[0] != '}':
            tok = self._peek()
            if tok[0] in ('IDENT', 'STRING'):
                name = tok[1]
                self._advance()
                if self._peek() and self._peek()[0] == ':':
                    self._advance()
                    val = self._parse_value().strip().strip('"')
                    if self._peek() and self._peek()[0] == ';':
                        self._advance()
                    try:
                        if name == 'process':
                            cond.process = float(val)
                        elif name == 'voltage':
                            cond.voltage = float(val)
                        elif name == 'temperature':
                            cond.temperature = float(val)
                    except ValueError:
                        pass
                else:
                    self._advance()
            else:
                self._advance()
        if self._peek() and self._peek()[0] == '}':
            self._advance()

    def _parse_cell_body(self, lib: LibertyLibrary, cell: LibertyCell):
        while self._peek() and self._peek()[0] != '}':
            tok = self._peek()
            if tok[0] not in ('IDENT', 'STRING'):
                self._advance()
                continue

            name = tok[1]
            self._advance()

            next_tok = self._peek()
            if not next_tok:
                break

            if next_tok[0] == ':':
                self._advance()
                val = self._parse_value().strip().strip('"')
                if self._peek() and self._peek()[0] == ';':
                    self._advance()
                cell.raw_attributes[name] = val

                if name == 'area':
                    try:
                        cell.area = float(val)
                    except ValueError:
                        pass
                elif name == 'cell_leakage_power':
                    try:
                        # Convert to μW using power_unit_uw
                        cell.cell_leakage_power = float(val) * lib.power_unit_uw
                    except ValueError:
                        pass
                elif name == 'cell_footprint':
                    cell.cell_footprint = val
                elif name == 'is_macro_cell':
                    cell.is_macro = val.lower() in ('true', '1')

            elif next_tok[0] == '(':
                args = self._parse_arg_list()
                following = self._peek()
                if following and following[0] == '{':
                    self._advance()
                    if name == 'pin':
                        pin_name = args[0] if args else "P"
                        pin = LibertyPin(name=pin_name)
                        self._parse_pin_body(lib, pin)
                        cell.pins[pin_name] = pin
                    else:
                        self._skip_group_body()
                elif following and following[0] == ';':
                    self._advance()
                else:
                    self._advance()
            else:
                self._advance()

        if self._peek() and self._peek()[0] == '}':
            self._advance()

    def _parse_pin_body(self, lib: LibertyLibrary, pin: LibertyPin):
        while self._peek() and self._peek()[0] != '}':
            tok = self._peek()
            if tok[0] not in ('IDENT', 'STRING'):
                self._advance()
                continue

            name = tok[1]
            self._advance()

            next_tok = self._peek()
            if not next_tok:
                break

            if next_tok[0] == ':':
                self._advance()
                val = self._parse_value().strip().strip('"')
                if self._peek() and self._peek()[0] == ';':
                    self._advance()

                if name == 'direction':
                    pin.direction = val.lower()
                elif name == 'capacitance':
                    try:
                        # Convert to fF
                        pin.capacitance = float(val) * lib.capacitive_load_unit_ff
                    except ValueError:
                        pass
                elif name == 'function':
                    pin.function = val

            elif next_tok[0] == '(':
                args = self._parse_arg_list()
                following = self._peek()
                if following and following[0] == '{':
                    self._advance()
                    if name == 'timing':
                        timing = LibertyTiming()
                        self._parse_timing_body(lib, timing)
                        pin.timing.append(timing)
                    else:
                        self._skip_group_body()
                elif following and following[0] == ';':
                    self._advance()
                else:
                    self._advance()
            else:
                self._advance()

        if self._peek() and self._peek()[0] == '}':
            self._advance()

    def _parse_timing_body(self, lib: LibertyLibrary, timing: LibertyTiming):
        while self._peek() and self._peek()[0] != '}':
            tok = self._peek()
            if tok[0] not in ('IDENT', 'STRING'):
                self._advance()
                continue

            name = tok[1]
            self._advance()

            next_tok = self._peek()
            if not next_tok:
                break

            if next_tok[0] == ':':
                self._advance()
                val = self._parse_value().strip().strip('"')
                if self._peek() and self._peek()[0] == ';':
                    self._advance()

                if name == 'related_pin':
                    timing.related_pin = val
                elif name == 'timing_type':
                    timing.timing_type = val
                elif name == 'timing_sense':
                    timing.timing_sense = val

            elif next_tok[0] == '(':
                args = self._parse_arg_list()
                following = self._peek()
                if following and following[0] == '{':
                    self._advance()
                    # Table lookup groups: cell_rise, cell_fall, etc.
                    delay_val = self._extract_table_nominal_value(lib)
                    if name == 'cell_rise':
                        timing.cell_rise = delay_val
                    elif name == 'cell_fall':
                        timing.cell_fall = delay_val
                    elif name == 'rise_transition':
                        timing.rise_transition = delay_val
                    elif name == 'fall_transition':
                        timing.fall_transition = delay_val
                elif following and following[0] == ';':
                    self._advance()
                else:
                    self._advance()
            else:
                self._advance()

        if self._peek() and self._peek()[0] == '}':
            self._advance()

    def _extract_table_nominal_value(self, lib: LibertyLibrary) -> float:
        """Extract average/representative delay from table lookup values."""
        delays = []
        while self._peek() and self._peek()[0] != '}':
            tok = self._peek()
            if tok[0] in ('IDENT', 'STRING') and tok[1] == 'values':
                self._advance()
                if self._peek() and self._peek()[0] == '(':
                    args = self._parse_arg_list()
                    # Parse comma-separated numbers inside quoted string args
                    for arg in args:
                        for part in arg.replace('"', '').split(','):
                            part = part.strip()
                            if part:
                                try:
                                    delays.append(float(part))
                                except ValueError:
                                    pass
                if self._peek() and self._peek()[0] == ';':
                    self._advance()
            else:
                self._advance()
        if self._peek() and self._peek()[0] == '}':
            self._advance()

        if delays:
            # Representative delay: nominal average converted to ns
            avg_delay = (sum(delays) / len(delays)) * lib.time_unit_ns
            return avg_delay
        return 0.0

    def _skip_group_body(self):
        """Skip nested braces until group close."""
        depth = 1
        while self._peek() and depth > 0:
            tok = self._peek()
            if tok[0] == '{':
                depth += 1
            elif tok[0] == '}':
                depth -= 1
            self._advance()

    def _parse_time_unit(self, unit_str: str) -> float:
        """Parse time unit string to nanoseconds conversion factor."""
        unit_str = unit_str.lower().strip()
        if 'ps' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 0.001
        elif 'ns' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 1.0
        elif 'us' in unit_str or 'μs' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 1000.0
        return 1.0

    def _parse_voltage_unit(self, unit_str: str) -> float:
        """Parse voltage unit string to Volts conversion factor."""
        unit_str = unit_str.lower().strip()
        if 'mv' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 0.001
        elif 'v' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 1.0
        return 1.0

    def _parse_power_unit(self, unit_str: str) -> float:
        """Parse power unit string to microwatts (μW) conversion factor."""
        unit_str = unit_str.lower().strip()
        if 'pw' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 1e-6
        elif 'nw' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 1e-3
        elif 'uw' in unit_str or 'μw' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 1.0
        elif 'mw' in unit_str:
            num = re.findall(r"[\d\.]+", unit_str)
            mult = float(num[0]) if num else 1.0
            return mult * 1000.0
        return 1.0

    @classmethod
    def parse_file(cls, path: str) -> LibertyLibrary:
        """Read and parse a Liberty file from disk."""
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except OSError as err:
            raise ValueError(f"Unable to read Liberty file '{path}': {err}") from err
        parser = cls(content)
        return parser.parse()
