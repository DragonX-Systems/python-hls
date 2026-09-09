"""
Tests for the Python parser module.
"""

import ast
import os
import sys
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_hls.frontend import PythonParser


class TestParser(unittest.TestCase):
    """Test cases for the Python parser."""
    
    def setUp(self):
        """Set up the test case."""
        self.parser = PythonParser()
    
    def test_parse_simple_function(self):
        """Test parsing a simple function."""
        source = """
def add(a, b):
    return a + b
"""
        tree = self.parser.parse_source(source)
        self.assertIsInstance(tree, ast.Module)
        self.assertEqual(len(tree.body), 1)
        self.assertIsInstance(tree.body[0], ast.FunctionDef)
        self.assertEqual(tree.body[0].name, 'add')
    
    def test_parse_supported_constructs(self):
        """Test parsing supported constructs."""
        source = """
def test_constructs(a, b):
    c = a + b
    d = a * b
    if a > b:
        e = a - b
    else:
        e = b - a
    
    i = 0
    while i < 10:
        i += 1
    
    for j in range(5):
        c += j
    
    return c + d + e
"""
        tree = self.parser.parse_source(source)
        self.assertIsInstance(tree, ast.Module)
        self.assertEqual(len(tree.body), 1)
        self.assertIsInstance(tree.body[0], ast.FunctionDef)
    
    def test_parse_unsupported_constructs(self):
        """Test parsing unsupported constructs raises an exception."""
        source = """
class TestClass:
    def __init__(self):
        self.value = 0
"""
        with self.assertRaises(ValueError):
            self.parser.parse_source(source)
    
    def test_parse_file(self):
        """Test parsing a file."""
        # Create a temporary file
        file_path = "temp_test_file.py"
        with open(file_path, 'w') as f:
            f.write("def add(a, b):\n    return a + b\n")
        
        try:
            tree = self.parser.parse_file(file_path)
            self.assertIsInstance(tree, ast.Module)
            self.assertEqual(len(tree.body), 1)
            self.assertIsInstance(tree.body[0], ast.FunctionDef)
            self.assertEqual(tree.body[0].name, 'add')
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)


if __name__ == '__main__':
    unittest.main() 