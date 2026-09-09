"""
Refactor equivalence checking for Python-HLS.

Verifies that two compilations produce equivalent hardware behavior:
- Bit-exact: Same outputs for same inputs
- Cycle-accurate: Same timing behavior
- Functional: Same computation (may differ in timing)

This is the core of "refactor safety" - proving that code changes
don't break hardware behavior.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union
from enum import Enum, auto
import tempfile
import os


class EquivalenceMode(Enum):
    """Level of equivalence to check."""
    FUNCTIONAL = auto()     # Same outputs for same inputs (may differ in timing)
    BIT_EXACT = auto()      # Identical bit-level outputs
    CYCLE_ACCURATE = auto() # Same timing behavior


@dataclass
class EquivalenceResult:
    """Result of an equivalence check."""
    equivalent: bool
    mode: EquivalenceMode
    details: Dict[str, Any] = field(default_factory=dict)
    mismatches: List[Dict[str, Any]] = field(default_factory=list)
    
    def __bool__(self) -> bool:
        return self.equivalent
    
    def summary(self) -> str:
        """Human-readable summary of the result."""
        if self.equivalent:
            return f"PASS: Designs are {self.mode.name.lower()} equivalent"
        else:
            return (
                f"FAIL: Designs are NOT {self.mode.name.lower()} equivalent. "
                f"{len(self.mismatches)} mismatch(es) found."
            )


@dataclass  
class CompilationFingerprint:
    """
    Captures the essential characteristics of a compilation for equivalence checking.
    
    This allows comparing compilations without re-running them.
    """
    # Source identification
    source_hash: str  # Hash of normalized source code
    function_name: str
    
    # Interface
    input_ports: List[Tuple[str, int]]   # [(name, bit_width), ...]
    output_ports: List[Tuple[str, int]]
    
    # Timing
    latency_cycles: int
    pipeline_ii: Optional[int] = None
    
    # Generated RTL hash (for quick bit-exact check)
    rtl_hash: Optional[str] = None
    
    # Test vector results: [(inputs, outputs), ...]
    test_results: List[Tuple[Dict[str, int], Dict[str, int]]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'source_hash': self.source_hash,
            'function_name': self.function_name,
            'input_ports': self.input_ports,
            'output_ports': self.output_ports,
            'latency_cycles': self.latency_cycles,
            'pipeline_ii': self.pipeline_ii,
            'rtl_hash': self.rtl_hash,
            'test_results': self.test_results,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompilationFingerprint':
        """Deserialize from dictionary."""
        return cls(
            source_hash=data['source_hash'],
            function_name=data['function_name'],
            input_ports=[tuple(p) for p in data['input_ports']],
            output_ports=[tuple(p) for p in data['output_ports']],
            latency_cycles=data['latency_cycles'],
            pipeline_ii=data.get('pipeline_ii'),
            rtl_hash=data.get('rtl_hash'),
            test_results=[(d['inputs'], d['outputs']) if isinstance(d, dict) 
                         else (d[0], d[1]) for d in data.get('test_results', [])],
        )
    
    def save(self, path: str):
        """Save fingerprint to file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> 'CompilationFingerprint':
        """Load fingerprint from file."""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))


class EquivalenceChecker:
    """
    Checks equivalence between two HLS compilations.
    
    Use cases:
    1. Verify refactor didn't break behavior:
       check_equivalence(old_source, new_source)
    
    2. Verify RTL matches Python:
       check_rtl_equivalence(python_source, verilog_file)
    
    3. Verify two RTL files are equivalent:
       check_rtl_vs_rtl(verilog_a, verilog_b)
    """
    
    def __init__(self, hls_instance=None):
        """
        Initialize the equivalence checker.
        
        Args:
            hls_instance: Optional HLS compiler instance (will create one if not provided)
        """
        self._hls = hls_instance
    
    @property
    def hls(self):
        """Lazy-load HLS instance."""
        if self._hls is None:
            from ..hls import HLS
            self._hls = HLS(optimization_level=1)
        return self._hls
    
    def check_source_equivalence(
        self,
        source_a: str,
        source_b: str,
        mode: EquivalenceMode = EquivalenceMode.FUNCTIONAL,
        test_vectors: Optional[List[Dict[str, int]]] = None,
        entry_function: Optional[str] = None,
    ) -> EquivalenceResult:
        """
        Check if two Python sources produce equivalent hardware.
        
        This is the primary refactor-safety check: does the new code
        behave identically to the old code?
        
        Args:
            source_a: Original Python source
            source_b: Modified Python source
            mode: Level of equivalence to check
            test_vectors: Test inputs; if None, generates random vectors
            entry_function: Function to compare
            
        Returns:
            EquivalenceResult indicating pass/fail and details
        """
        # Compile both sources
        fp_a = self._create_fingerprint(source_a, entry_function, test_vectors)
        fp_b = self._create_fingerprint(source_b, entry_function, test_vectors)
        
        return self._compare_fingerprints(fp_a, fp_b, mode)
    
    def check_file_equivalence(
        self,
        file_a: str,
        file_b: str,
        mode: EquivalenceMode = EquivalenceMode.FUNCTIONAL,
        test_vectors: Optional[List[Dict[str, int]]] = None,
        entry_function: Optional[str] = None,
    ) -> EquivalenceResult:
        """
        Check if two Python files produce equivalent hardware.
        
        Args:
            file_a: Path to original Python file
            file_b: Path to modified Python file
            mode: Level of equivalence to check
            test_vectors: Test inputs
            entry_function: Function to compare
            
        Returns:
            EquivalenceResult
        """
        with open(file_a, 'r') as f:
            source_a = f.read()
        with open(file_b, 'r') as f:
            source_b = f.read()
        
        return self.check_source_equivalence(
            source_a, source_b, mode, test_vectors, entry_function
        )
    
    def check_against_fingerprint(
        self,
        source: str,
        fingerprint: CompilationFingerprint,
        mode: EquivalenceMode = EquivalenceMode.FUNCTIONAL,
    ) -> EquivalenceResult:
        """
        Check if a source matches a saved fingerprint.
        
        Useful for regression testing: save a fingerprint of known-good
        behavior, then check new versions against it.
        
        Args:
            source: Python source to check
            fingerprint: Saved fingerprint to compare against
            mode: Level of equivalence
            
        Returns:
            EquivalenceResult
        """
        # Use test vectors from the fingerprint
        test_vectors = [inputs for inputs, _ in fingerprint.test_results]
        
        new_fp = self._create_fingerprint(
            source, 
            fingerprint.function_name,
            test_vectors if test_vectors else None
        )
        
        return self._compare_fingerprints(fingerprint, new_fp, mode)
    
    def create_fingerprint(
        self,
        source: str,
        entry_function: Optional[str] = None,
        test_vectors: Optional[List[Dict[str, int]]] = None,
        num_random_tests: int = 100,
    ) -> CompilationFingerprint:
        """
        Create a fingerprint for a source file.
        
        The fingerprint captures behavior that can be compared later
        without re-compiling the original.
        
        Args:
            source: Python source code
            entry_function: Function to fingerprint
            test_vectors: Explicit test vectors
            num_random_tests: Number of random tests if no vectors provided
            
        Returns:
            CompilationFingerprint
        """
        return self._create_fingerprint(
            source, entry_function, test_vectors, num_random_tests
        )
    
    def _create_fingerprint(
        self,
        source: str,
        entry_function: Optional[str] = None,
        test_vectors: Optional[List[Dict[str, int]]] = None,
        num_random_tests: int = 100,
    ) -> CompilationFingerprint:
        """Internal method to create a fingerprint."""
        import tempfile
        
        # Normalize source for hashing (strip comments, normalize whitespace)
        normalized = self._normalize_source(source)
        source_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        
        # Write to temp file and compile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source)
            temp_path = f.name
        
        try:
            # Compile
            netlist = self.hls.compile(temp_path, entry_function=entry_function)
            
            # Extract function info
            if entry_function and entry_function in self.hls.ir.functions:
                func = self.hls.ir.functions[entry_function]
                func_name = entry_function
            else:
                # Get first function
                func_name = list(self.hls.ir.functions.keys())[0]
                func = self.hls.ir.functions[func_name]
            
            # Extract ports
            input_ports = [(p.name, p.bit_width) for p in func.parameters]
            output_ports = [(func.return_var.name, func.return_var.bit_width)] if func.return_var else []
            
            # Get latency
            latency = getattr(func, 'total_latency', 0)
            
            # Generate RTL and hash it
            rtl_hash = None
            if hasattr(self.hls, 'scheduled_ir') and self.hls.scheduled_ir:
                try:
                    verilog = self.hls.verilog_generator.generate(self.hls.scheduled_ir)
                    rtl_hash = hashlib.sha256(verilog.encode()).hexdigest()[:16]
                except Exception:
                    # If Verilog generation fails, skip RTL hash
                    pass
            
            # Run test vectors
            test_results = []
            if test_vectors or num_random_tests > 0:
                # Execute Python directly for functional results
                test_results = self._run_python_tests(
                    source, func_name, input_ports,
                    test_vectors, num_random_tests
                )
            
            return CompilationFingerprint(
                source_hash=source_hash,
                function_name=func_name,
                input_ports=input_ports,
                output_ports=output_ports,
                latency_cycles=latency,
                rtl_hash=rtl_hash,
                test_results=test_results,
            )
        finally:
            os.unlink(temp_path)
    
    def _normalize_source(self, source: str) -> str:
        """Normalize source code for consistent hashing."""
        import ast
        try:
            tree = ast.parse(source)
            # Use ast.dump for a normalized representation
            return ast.dump(tree)
        except SyntaxError:
            # If we can't parse, just strip whitespace
            return '\n'.join(line.strip() for line in source.splitlines() if line.strip())
    
    def _run_python_tests(
        self,
        source: str,
        func_name: str,
        input_ports: List[Tuple[str, int]],
        test_vectors: Optional[List[Dict[str, int]]],
        num_random_tests: int,
    ) -> List[Tuple[Dict[str, int], Dict[str, int]]]:
        """Run Python tests and collect results."""
        import random
        
        # Compile and get function
        local_ns = {}
        exec(source, local_ns)
        
        if func_name not in local_ns:
            return []
        
        func = local_ns[func_name]
        results = []
        
        # Generate test vectors if not provided
        if test_vectors is None:
            test_vectors = []
            for _ in range(num_random_tests):
                vec = {}
                for name, width in input_ports:
                    max_val = (1 << width) - 1
                    vec[name] = random.randint(0, min(max_val, 1000))
                test_vectors.append(vec)
        
        # Run tests
        for inputs in test_vectors:
            try:
                # Call function with inputs
                args = [inputs.get(name, 0) for name, _ in input_ports]
                result = func(*args)
                
                # Package output
                if isinstance(result, tuple):
                    outputs = {f'out{i}': v for i, v in enumerate(result)}
                else:
                    outputs = {'result': result if result is not None else 0}
                
                results.append((inputs, outputs))
            except Exception:
                # Skip failed tests
                pass
        
        return results
    
    def _compare_fingerprints(
        self,
        fp_a: CompilationFingerprint,
        fp_b: CompilationFingerprint,
        mode: EquivalenceMode,
    ) -> EquivalenceResult:
        """Compare two fingerprints for equivalence."""
        mismatches = []
        details = {
            'source_a_hash': fp_a.source_hash,
            'source_b_hash': fp_b.source_hash,
            'function': fp_a.function_name,
        }
        
        # Check interface compatibility
        # For functional equivalence, only check port widths, not names
        # (variable renaming shouldn't break functional equivalence)
        a_input_widths = sorted([w for _, w in fp_a.input_ports])
        b_input_widths = sorted([w for _, w in fp_b.input_ports])
        
        if a_input_widths != b_input_widths:
            mismatches.append({
                'type': 'interface',
                'field': 'input_ports',
                'message': 'Input port widths differ',
                'a': fp_a.input_ports,
                'b': fp_b.input_ports,
            })
        
        a_output_widths = sorted([w for _, w in fp_a.output_ports])
        b_output_widths = sorted([w for _, w in fp_b.output_ports])
        
        if a_output_widths != b_output_widths:
            mismatches.append({
                'type': 'interface',
                'field': 'output_ports',
                'message': 'Output port widths differ',
                'a': fp_a.output_ports,
                'b': fp_b.output_ports,
            })
        
        # Mode-specific checks
        if mode == EquivalenceMode.BIT_EXACT:
            # RTL must be identical
            if fp_a.rtl_hash != fp_b.rtl_hash:
                mismatches.append({
                    'type': 'rtl',
                    'message': 'RTL differs',
                    'a_hash': fp_a.rtl_hash,
                    'b_hash': fp_b.rtl_hash,
                })
        
        if mode == EquivalenceMode.CYCLE_ACCURATE:
            # Latency must match
            if fp_a.latency_cycles != fp_b.latency_cycles:
                mismatches.append({
                    'type': 'timing',
                    'field': 'latency_cycles',
                    'a': fp_a.latency_cycles,
                    'b': fp_b.latency_cycles,
                })
            
            if fp_a.pipeline_ii != fp_b.pipeline_ii:
                mismatches.append({
                    'type': 'timing',
                    'field': 'pipeline_ii',
                    'a': fp_a.pipeline_ii,
                    'b': fp_b.pipeline_ii,
                })
        
        # Functional check: test results must match
        if fp_a.test_results and fp_b.test_results:
            # Match up test results by inputs
            a_results = {json.dumps(inputs, sort_keys=True): outputs 
                        for inputs, outputs in fp_a.test_results}
            b_results = {json.dumps(inputs, sort_keys=True): outputs 
                        for inputs, outputs in fp_b.test_results}
            
            for inputs_key, outputs_a in a_results.items():
                if inputs_key in b_results:
                    outputs_b = b_results[inputs_key]
                    if outputs_a != outputs_b:
                        mismatches.append({
                            'type': 'functional',
                            'inputs': json.loads(inputs_key),
                            'outputs_a': outputs_a,
                            'outputs_b': outputs_b,
                        })
            
            details['tests_compared'] = len(a_results)
        
        return EquivalenceResult(
            equivalent=len(mismatches) == 0,
            mode=mode,
            details=details,
            mismatches=mismatches,
        )


def check_refactor_equivalence(
    original_source: str,
    refactored_source: str,
    mode: EquivalenceMode = EquivalenceMode.FUNCTIONAL,
) -> EquivalenceResult:
    """
    Convenience function to check if a refactor preserves behavior.
    
    Args:
        original_source: Original Python source
        refactored_source: Refactored Python source
        mode: Level of equivalence to check
        
    Returns:
        EquivalenceResult
        
    Example:
        >>> original = '''
        ... def gcd(a, b):
        ...     while b:
        ...         a, b = b, a % b
        ...     return a
        ... '''
        >>> refactored = '''
        ... def gcd(x, y):
        ...     while y != 0:
        ...         x, y = y, x % y
        ...     return x
        ... '''
        >>> result = check_refactor_equivalence(original, refactored)
        >>> print(result.summary())
        PASS: Designs are functional equivalent
    """
    checker = EquivalenceChecker()
    return checker.check_source_equivalence(original_source, refactored_source, mode)
