"""
Streaming pragma parser for handling streaming interface annotations.
"""

import ast
import re
from typing import Dict, List, Tuple, Optional, Any, Set

class StreamingPragma:
    """
    Represents a streaming interface annotation in the source code.
    
    This class parses and validates streaming interface pragmas in the source code,
    such as FIFO declarations, crossbar configurations, and channel mappings.
    """
    
    # Valid pragma patterns
    PRAGMA_PATTERNS = {
        "stream": r"pragma\s+hls\s+stream\s+(\w+)\s*(?:\((.*)\))?",
        "fifo": r"pragma\s+hls\s+fifo\s+(\w+)\s*(?:\((.*)\))?",
        "crossbar": r"pragma\s+hls\s+crossbar\s+(\w+)\s*(?:\((.*)\))?",
        "channel": r"pragma\s+hls\s+channel\s+(\w+)\s*(?:\((.*)\))?",
    }
    
    def __init__(self, pragma_type: str, name: str, params: Dict[str, Any] = None):
        """
        Initialize a streaming pragma.
        
        Args:
            pragma_type: Type of the pragma (stream, fifo, crossbar, channel)
            name: Name of the component
            params: Additional parameters for the pragma
        """
        self.pragma_type = pragma_type
        self.name = name
        self.params = params or {}
    
    @classmethod
    def parse_comment(cls, comment: str) -> Optional['StreamingPragma']:
        """
        Parse a comment string to extract streaming pragma information.
        
        Args:
            comment: Comment string to parse
            
        Returns:
            StreamingPragma object if the comment contains a valid pragma, None otherwise
        """
        for pragma_type, pattern in cls.PRAGMA_PATTERNS.items():
            match = re.search(pattern, comment, re.IGNORECASE)
            if match:
                name = match.group(1)
                params_str = match.group(2) if len(match.groups()) > 1 else ""
                params = cls._parse_params(params_str)
                return cls(pragma_type, name, params)
        return None
    
    @staticmethod
    def _parse_params(params_str: str) -> Dict[str, Any]:
        """
        Parse parameters from the pragma parameter string.
        
        Args:
            params_str: Parameter string in the format 'key1=value1, key2=value2'
            
        Returns:
            Dictionary of parameter key-value pairs
        """
        params = {}
        if not params_str:
            return params
        
        # Split by commas, but handle quoted values
        param_items = []
        current_item = ""
        in_quotes = False
        quote_char = None
        
        for char in params_str:
            if char in ['"', "'"]:
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
                current_item += char
            elif char == ',' and not in_quotes:
                param_items.append(current_item.strip())
                current_item = ""
            else:
                current_item += char
        
        if current_item:
            param_items.append(current_item.strip())
        
        # Parse each parameter
        for item in param_items:
            if '=' in item:
                key, value = item.split('=', 1)
                # Try to parse numeric values
                try:
                    # Handle quoted strings
                    if value.startswith('"') and value.endswith('"'):
                        params[key.strip()] = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        params[key.strip()] = value[1:-1]
                    # Handle booleans
                    elif value.lower() == 'true':
                        params[key.strip()] = True
                    elif value.lower() == 'false':
                        params[key.strip()] = False
                    # Handle integers
                    elif value.isdigit():
                        params[key.strip()] = int(value)
                    # Handle floats
                    elif re.match(r'^-?\d+\.\d+$', value):
                        params[key.strip()] = float(value)
                    else:
                        params[key.strip()] = value
                except ValueError:
                    params[key.strip()] = value
            else:
                # Flag parameters (no value)
                params[item.strip()] = True
        
        return params
    
    def validate(self) -> Tuple[bool, str]:
        """
        Validate the pragma parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.pragma_type == "fifo":
            return self._validate_fifo()
        elif self.pragma_type == "crossbar":
            return self._validate_crossbar()
        elif self.pragma_type == "channel":
            return self._validate_channel()
        elif self.pragma_type == "stream":
            return self._validate_stream()
        else:
            return False, f"Unknown pragma type: {self.pragma_type}"
    
    def _validate_fifo(self) -> Tuple[bool, str]:
        """Validate FIFO pragma parameters."""
        required_params = set()
        optional_params = {
            "depth", "width", "almost_full_threshold", "almost_empty_threshold",
            "input_interface", "output_interface",
            # AXI-Stream parameters
            "axis_tuser_width", "axis_tid_width", "axis_tdest_width", 
            "axis_tkeep", "axis_tlast",
            # AXI-Lite parameters
            "axilite_addr_width", "axilite_has_strb", "axilite_has_resp"
        }
        
        # Check for required parameters
        missing_params = required_params - set(self.params.keys())
        if missing_params:
            return False, f"Missing required FIFO parameters: {', '.join(missing_params)}"
        
        # Validate parameter types
        for param in ["depth", "width", "almost_full_threshold", "almost_empty_threshold",
                     "axis_tuser_width", "axis_tid_width", "axis_tdest_width", "axilite_addr_width"]:
            if param in self.params and not isinstance(self.params[param], int):
                return False, f"FIFO parameter '{param}' must be an integer"
        
        # Validate boolean parameters
        for param in ["axis_tkeep", "axis_tlast", "axilite_has_strb", "axilite_has_resp"]:
            if param in self.params and not isinstance(self.params[param], bool):
                return False, f"FIFO parameter '{param}' must be a boolean"
                
        # Validate interface types
        if "input_interface" in self.params:
            valid_interfaces = ["simple", "axis", "axilite"]
            if self.params["input_interface"] not in valid_interfaces:
                return False, f"Invalid input interface: {self.params['input_interface']}"
                
        if "output_interface" in self.params:
            valid_interfaces = ["simple", "axis", "axilite"]
            if self.params["output_interface"] not in valid_interfaces:
                return False, f"Invalid output interface: {self.params['output_interface']}"
        
        return True, ""
    
    def _validate_crossbar(self) -> Tuple[bool, str]:
        """Validate crossbar pragma parameters."""
        required_params = {"inputs", "outputs"}
        optional_params = {"width", "multicast", "broadcast", "arbitration"}
        
        # Check for required parameters
        missing_params = required_params - set(self.params.keys())
        if missing_params:
            return False, f"Missing required crossbar parameters: {', '.join(missing_params)}"
        
        # Validate parameter types
        for param in ["inputs", "outputs", "width"]:
            if param in self.params and not isinstance(self.params[param], int):
                return False, f"Crossbar parameter '{param}' must be an integer"
        
        for param in ["multicast", "broadcast"]:
            if param in self.params and not isinstance(self.params[param], bool):
                return False, f"Crossbar parameter '{param}' must be a boolean"
        
        if "arbitration" in self.params:
            valid_arbitration = ["round-robin", "fixed-priority", "fair"]
            if self.params["arbitration"] not in valid_arbitration:
                return False, f"Invalid arbitration scheme: {self.params['arbitration']}"
        
        return True, ""
    
    def _validate_channel(self) -> Tuple[bool, str]:
        """Validate channel pragma parameters."""
        required_params = {"source", "destination"}
        optional_params = {"width", "fifo", "crossbar", "valid", "ready", "type"}
        
        # Check for required parameters
        missing_params = required_params - set(self.params.keys())
        if missing_params:
            return False, f"Missing required channel parameters: {', '.join(missing_params)}"
        
        # Validate parameter types
        for param in ["width"]:
            if param in self.params and not isinstance(self.params[param], int):
                return False, f"Channel parameter '{param}' must be an integer"
        
        for param in ["valid", "ready"]:
            if param in self.params and not isinstance(self.params[param], bool):
                return False, f"Channel parameter '{param}' must be a boolean"
        
        if "type" in self.params:
            valid_types = ["data", "control", "address"]
            if self.params["type"] not in valid_types:
                return False, f"Invalid channel type: {self.params['type']}"
        
        return True, ""
    
    def _validate_stream(self) -> Tuple[bool, str]:
        """Validate stream pragma parameters."""
        # Stream pragmas are used to mark variables as streaming interfaces
        optional_params = {
            "direction", "width", "protocol",
            # AXI-Stream specific parameters
            "tuser_width", "tid_width", "tdest_width", "tkeep", "tlast",
            # AXI-Lite specific parameters
            "addr_width", "has_strb", "has_resp"
        }
        
        # Validate parameter types
        for param in ["width", "tuser_width", "tid_width", "tdest_width", "addr_width"]:
            if param in self.params and not isinstance(self.params[param], int):
                return False, f"Stream parameter '{param}' must be an integer"
        
        # Validate boolean parameters
        for param in ["tkeep", "tlast", "has_strb", "has_resp"]:
            if param in self.params and not isinstance(self.params[param], bool):
                return False, f"Stream parameter '{param}' must be a boolean"
        
        if "direction" in self.params:
            valid_directions = ["in", "out", "inout"]
            if self.params["direction"] not in valid_directions:
                return False, f"Invalid stream direction: {self.params['direction']}"
        
        if "protocol" in self.params:
            valid_protocols = ["simple", "axi", "axis", "axilite", "avalon"]
            if self.params["protocol"] not in valid_protocols:
                return False, f"Invalid stream protocol: {self.params['protocol']}"
        
        return True, ""
    
    def __str__(self) -> str:
        """Convert pragma to string representation."""
        params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"StreamingPragma({self.pragma_type}, {self.name}, {{{params_str}}})"


def extract_streaming_pragmas(source_lines: List[str]) -> Dict[str, List[StreamingPragma]]:
    """
    Extract streaming pragmas from source code.
    
    Args:
        source_lines: List of source code lines
        
    Returns:
        Dictionary mapping line numbers to lists of streaming pragmas
    """
    line_pragmas = {}
    
    for i, line in enumerate(source_lines):
        # Look for comments in the line
        comment_start = line.find('#')
        if comment_start != -1:
            comment = line[comment_start:].strip()
            pragma = StreamingPragma.parse_comment(comment)
            if pragma:
                # Check if the pragma is valid
                is_valid, error = pragma.validate()
                if is_valid:
                    if i not in line_pragmas:
                        line_pragmas[i] = []
                    line_pragmas[i].append(pragma)
                else:
                    print(f"Warning: Invalid pragma on line {i+1}: {error}")
    
    return line_pragmas


def extract_pragmas_from_node(node: ast.AST, source_lines: List[str], line_offset: int = 0) -> List[StreamingPragma]:
    """
    Extract streaming pragmas associated with an AST node.
    
    Args:
        node: AST node to extract pragmas from
        source_lines: Source code lines
        line_offset: Line offset (for nodes in functions)
        
    Returns:
        List of StreamingPragma objects
    """
    pragmas = []
    
    # Get line numbers for the node
    lineno = getattr(node, 'lineno', None)
    if lineno is None:
        return pragmas
    
    if not source_lines:
        return pragmas

    # Check the line before the node for pragmas
    idx_prior = lineno - 1 - line_offset
    if 0 <= idx_prior < len(source_lines):
        prior_line = source_lines[idx_prior]
        # Check for inline comment on the prior line
        comment_start = prior_line.find('#')
        if comment_start != -1:
            comment = prior_line[comment_start:].strip()
            pragma = StreamingPragma.parse_comment(comment)
            if pragma:
                pragmas.append(pragma)
    
    # Check the node's line for inline pragmas (after the statement)
    idx_node = lineno - line_offset
    if 0 <= idx_node < len(source_lines):
        node_line = source_lines[idx_node]
        comment_start = node_line.find('#')
        if comment_start != -1:
            comment = node_line[comment_start:].strip()
            pragma = StreamingPragma.parse_comment(comment)
            if pragma:
                pragmas.append(pragma)
    
    return pragmas 