#!/usr/bin/env python3
"""
Validation script for improved area scaling in HLS technology library.

This script demonstrates the enhanced area scaling that better reflects
real-world semiconductor scaling behaviors, particularly the slowing
of Moore's Law at advanced technology nodes.
"""

import sys
import os

# Add the python_hls directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.tech.tech_library import TechLibrary, ResourceModel

def compare_scaling_models():
    """Compare the improved scaling model with the old quadratic scaling."""
    
    print("="*80)
    print("IMPROVED AREA SCALING VALIDATION")
    print("="*80)
    print()
    
    lib = TechLibrary()
    
    # Test different resource types
    resource_types = ["ALU_32bit", "Multiplier_32bit", "Register_32bit", "Memory_1KB"]
    tech_nodes = [45, 28, 16, 7, 5, 3]
    
    for res_type in resource_types:
        try:
            base_resource = lib.get_resource(res_type, 45)  # Start from 45nm
            
            print(f"\n{res_type} Scaling Analysis:")
            print(f"Base 45nm: Area = {base_resource.area:.1f} μm², Freq = {base_resource.frequency:.0f} MHz")
            print("-" * 60)
            
            for node in tech_nodes:
                if node == 45:
                    continue
                    
                scaled = base_resource.scale_to_node(node)
                
                # Calculate old quadratic scaling for comparison
                old_quadratic_area = base_resource.area * (node / 45) ** 2
                old_quadratic_freq = base_resource.frequency * (45 / node) ** 0.35
                
                # Calculate improvement ratios
                area_ratio = scaled.area / old_quadratic_area
                freq_ratio = scaled.frequency / old_quadratic_freq if old_quadratic_freq > 0 else 1.0
                
                print(f"{node:2d}nm: Area = {scaled.area:6.1f} μm² (vs {old_quadratic_area:6.1f} old) | "
                      f"Freq = {scaled.frequency:4.0f} MHz | "
                      f"Area ratio: {area_ratio:.2f}x")
            
        except ValueError as e:
            print(f"Resource {res_type} not found: {e}")
    
    print("\n" + "="*80)
    print("KEY DIFFERENCES FROM OLD QUADRATIC SCALING:")
    print("="*80)
    
    # Demonstrate specific scaling scenarios
    alu_45nm = lib.get_resource("ALU_32bit", 45)
    
    scenarios = [
        (45, 28, "Mid-range transition"),
        (28, 16, "Advanced node transition"), 
        (16, 7, "Leading edge transition"),
        (45, 7, "Multi-generation jump"),
    ]
    
    for start_node, end_node, description in scenarios:
        if start_node != 45:
            # Scale from 45nm to start_node first
            temp_resource = alu_45nm.scale_to_node(start_node)
        else:
            temp_resource = alu_45nm
            
        scaled = temp_resource.scale_to_node(end_node)
        
        # Old quadratic scaling
        node_ratio = end_node / start_node
        old_area = temp_resource.area * (node_ratio ** 2)
        
        # Calculate scaling exponent that would give our result
        actual_exp = math.log(scaled.area / temp_resource.area) / math.log(node_ratio) if node_ratio != 1 else 2.0
        
        print(f"\n{description} ({start_node}nm → {end_node}nm):")
        print(f"  Old quadratic (^2.0): {old_area:.1f} μm²")
        print(f"  Improved model:       {scaled.area:.1f} μm²")
        print(f"  Effective exponent:   {actual_exp:.2f}")
        print(f"  Difference:          {((scaled.area - old_area) / old_area * 100):+.1f}%")

def validate_cross_regime_scaling():
    """Test scaling across different technology regimes."""
    
    print("\n" + "="*80)
    print("CROSS-REGIME SCALING VALIDATION")
    print("="*80)
    
    lib = TechLibrary()
    
    # Test cross-regime scenarios
    test_cases = [
        ("Legacy to Advanced", 65, 16),
        ("Advanced to Leading Edge", 28, 7),
        ("Leading Edge to Cutting Edge", 7, 3),
        ("Large Jump", 45, 3),
    ]
    
    alu = lib.get_resource("ALU_32bit", 45)
    
    for description, start, end in test_cases:
        # Get resource at start node
        if start != 45:
            start_resource = alu.scale_to_node(start)
        else:
            start_resource = alu
            
        # Scale to end node
        end_resource = start_resource.scale_to_node(end)
        
        # Calculate various metrics
        area_ratio = end_resource.area / start_resource.area
        freq_ratio = end_resource.frequency / start_resource.frequency
        energy_ratio = end_resource.energy_per_op / start_resource.energy_per_op
        
        print(f"\n{description} ({start}nm → {end}nm):")
        print(f"  Area scaling:   {area_ratio:.3f}x")
        print(f"  Freq scaling:   {freq_ratio:.3f}x") 
        print(f"  Energy scaling: {energy_ratio:.3f}x")

def demonstrate_real_world_accuracy():
    """Show how the improved model compares to known industry data."""
    
    print("\n" + "="*80)
    print("REAL-WORLD ACCURACY COMPARISON")
    print("="*80)
    
    # Industry data points (approximate from TSMC/Intel reports)
    industry_data = {
        (45, 28): {"area_improvement": 2.0, "description": "TSMC 45nm→28nm"},
        (28, 16): {"area_improvement": 1.6, "description": "TSMC 28nm→16nm"}, 
        (16, 7):  {"area_improvement": 1.3, "description": "TSMC 16nm→7nm"},
        (28, 7):  {"area_improvement": 2.0, "description": "TSMC 28nm→7nm"},
    }
    
    lib = TechLibrary()
    alu = lib.get_resource("ALU_32bit", 45)
    
    print("\nComparison with Industry Data:")
    print("-" * 50)
    
    for (start_node, end_node), data in industry_data.items():
        # Get our model's prediction
        if start_node != 45:
            start_resource = alu.scale_to_node(start_node)
        else:
            start_resource = alu
            
        end_resource = start_resource.scale_to_node(end_node)
        our_improvement = start_resource.area / end_resource.area
        
        # Compare with industry data
        industry_improvement = data["area_improvement"]
        accuracy = (1 - abs(our_improvement - industry_improvement) / industry_improvement) * 100
        
        print(f"{data['description']:20}: Industry={industry_improvement:.1f}x, "
              f"Our Model={our_improvement:.1f}x, Accuracy={accuracy:.1f}%")

if __name__ == "__main__":
    import math
    
    compare_scaling_models()
    validate_cross_regime_scaling() 
    demonstrate_real_world_accuracy()
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("The improved scaling model provides:")
    print("1. More realistic area scaling that accounts for Moore's Law slowdown")
    print("2. Technology-regime specific scaling factors")
    print("3. Better alignment with real foundry data")
    print("4. Conservative frequency and energy scaling for advanced nodes")
    print("5. Correction factors for known process transitions")
    print()
    print("This replaces the simple quadratic area scaling (node_ratio)² with")
    print("a sophisticated model that better reflects semiconductor physics.") 