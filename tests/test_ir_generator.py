"""
Tests for the IR generator module.
"""

import ast
import os
import sys
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls.frontend import PythonParser
from python_hls.ir import IRGenerator, IRFunction


class TestIRGenerator(unittest.TestCase):
    """Test cases for the IR generator."""
    
    def setUp(self):
        """Set up the test case."""
        self.parser = PythonParser()
        self.ir_generator = IRGenerator()
    
    def test_generate_simple_ir(self):
        """Test generating IR for a simple function."""
        source = """
def add(a, b):
    return a + b
"""
        tree = self.parser.parse_source(source)
        ir = self.ir_generator.generate(tree)
        
        self.assertIn('add', ir.functions)
        func = ir.functions['add']
        self.assertIsInstance(func, IRFunction)
        self.assertEqual(func.name, 'add')
        self.assertEqual(len(func.parameters), 2)
        
        # Check parameter names
        param_names = [param.name for param in func.parameters]
        self.assertIn('a', param_names)
        self.assertIn('b', param_names)
        
        # Check that blocks were created
        self.assertGreater(len(func.blocks), 0)
        
        # Check that entry block exists
        self.assertIsNotNone(func.entry_block)
    
    def test_generate_if_statement_ir(self):
        """Test generating IR for a function with an if statement."""
        source = """
def test_if(a, b):
    if a > b:
        return a
    else:
        return b
"""
        tree = self.parser.parse_source(source)
        ir = self.ir_generator.generate(tree)
        
        self.assertIn('test_if', ir.functions)
        func = ir.functions['test_if']
        
        # Check that we have the right number of blocks
        # (entry + if.then + if.else + if.merge)
        self.assertGreaterEqual(len(func.blocks), 4)
    
    def test_generate_while_loop_ir(self):
        """Test generating IR for a function with a while loop."""
        source = """
def test_while(n):
    i = 0
    while i < n:
        i += 1
    return i
"""
        tree = self.parser.parse_source(source)
        ir = self.ir_generator.generate(tree)
        
        self.assertIn('test_while', ir.functions)
        func = ir.functions['test_while']
        
        # Should have blocks for entry, loop header, loop body, and loop exit
        self.assertGreaterEqual(len(func.blocks), 4)
        
        # Check local variables
        self.assertIn('i', func.local_vars)
    
    def test_generate_for_loop_ir(self):
        """Test generating IR for a function with a for loop."""
        source = """
def test_for(n):
    sum = 0
    for i in range(n):
        sum += i
    return sum
"""
        tree = self.parser.parse_source(source)
        ir = self.ir_generator.generate(tree)
        
        self.assertIn('test_for', ir.functions)
        func = ir.functions['test_for']
        
        # Should have blocks for the loop structure
        self.assertGreaterEqual(len(func.blocks), 4)
        
        # Check local variables
        self.assertIn('sum', func.local_vars)


if __name__ == '__main__':
    unittest.main() 