#!/usr/bin/env python
"""
Hardware Netlist Visualization Example

This example shows how to use the hardware netlist visualization functionality
in the HLS module to visualize the hardware architecture generated from code.
"""

import ast
import sys
import os

# Add the parent directory to the path so we can import the synthesis module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from synthesis.hls import display_hardware_netlist, display_hardware_dot, parse_graph
from ir.cfg.staticfg import CFGBuilder

def create_sample_graph():
    """Create a sample graph for matrix multiplication"""
    # Define a simple matrix multiplication function
    code = """
def matrix_multiply(A, B, C, N):
    for i in range(N):
        for j in range(N):
            for k in range(N):
                C[i][j] += A[i][k] * B[k][j]
    return C
    """
    
    # Build a control flow graph directly from the source code
    cfg = CFGBuilder().build_from_src("matrix_multiply", code)
    
    return cfg

def create_sample_letkf_graph():
    """Create a sample graph for LETKF algorithm"""
    # Define a simplified LETKF function with basic operations
    code = """
def simplified_letkf(ensemble, observations, N):
    # Calculate ensemble mean (simplified)
    ensemble_mean = [0] * N
    for i in range(N):
        for j in range(N):
            ensemble_mean[i] += ensemble[j][i]
        ensemble_mean[i] = ensemble_mean[i] / N
    
    # Calculate perturbations (simplified)
    perturbations = [[0 for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(N):
            perturbations[i][j] = ensemble[i][j] - ensemble_mean[j]
    
    # Simple covariance calculation
    covariance = [[0 for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(N):
            for k in range(N):
                covariance[i][j] += perturbations[k][i] * perturbations[k][j]
            covariance[i][j] /= (N - 1)
    
    # Update ensemble mean with simplified Kalman update
    for i in range(N):
        ensemble_mean[i] += 0.5 * (observations[i] - ensemble_mean[i])
    
    # Reconstruct updated ensemble (simplified)
    updated_ensemble = [[0 for _ in range(N)] for _ in range(N)]
    for i in range(N):
        for j in range(N):
            updated_ensemble[i][j] = ensemble_mean[j] + perturbations[i][j] * 0.8
    
    return updated_ensemble
    """
    
    # Build a control flow graph directly from the source code
    cfg = CFGBuilder().build_from_src("simplified_letkf", code)
    
    return cfg

def create_sample_aes_graph():
    """Create a sample graph for a simplified AES encryption algorithm"""
    # Define a very simplified AES function with basic bitwise operations
    code = """
def very_simplified_aes(plaintext, key, num_rounds=3):
    # Initial state as a flat array
    state = [0] * 16
    for i in range(16):
        state[i] = plaintext[i]
    
    # Copy key to a working array
    round_key = [0] * 16
    for i in range(16):
        round_key[i] = key[i]
    
    # Initial AddRoundKey
    for i in range(16):
        state[i] ^= round_key[i]
    
    # Main rounds
    for r in range(num_rounds):
        # SubBytes - simplified to a basic transformation
        for i in range(16):
            # Simple substitution: rotate bits and XOR with a constant
            state[i] = ((state[i] << 1) | (state[i] >> 7)) & 0xFF
            state[i] ^= 0x63  # Common S-box constant
        
        # ShiftRows - simplified
        # Just swap some bytes around in a predefined pattern
        temp = state[1]
        state[1] = state[5]
        state[5] = state[9]
        state[9] = state[13]
        state[13] = temp
        
        temp = state[2]
        state[2] = state[10]
        state[10] = temp
        temp = state[6]
        state[6] = state[14]
        state[14] = temp
        
        temp = state[3]
        state[3] = state[15]
        state[15] = state[11]
        state[11] = state[7]
        state[7] = temp
        
        # MixColumns - simplified to some XOR operations
        if r < num_rounds - 1:  # Skip in the last round
            for col in range(4):
                idx = col * 4
                t0 = state[idx]
                t1 = state[idx + 1]
                t2 = state[idx + 2]
                t3 = state[idx + 3]
                
                state[idx] = t0 ^ t1
                state[idx + 1] = t1 ^ t2
                state[idx + 2] = t2 ^ t3
                state[idx + 3] = t3 ^ t0
        
        # Generate a simple round key - just rotate and XOR
        for i in range(16):
            round_key[i] = ((round_key[i] << 1) | (round_key[i] >> 7)) & 0xFF
            if i % 4 == 0:
                round_key[i] ^= r + 1
        
        # AddRoundKey
        for i in range(16):
            state[i] ^= round_key[i]
    
    return state
    """
    
    # Build a control flow graph directly from the source code
    cfg = CFGBuilder().build_from_src("very_simplified_aes", code)
    
    return cfg

def main():
    """Main entry point for the example"""
    print("=" * 80)
    print("Hardware Netlist Visualization Example")
    print("=" * 80)
    
    # Generate and visualize all three algorithms
    run_example("Matrix Multiplication", create_sample_graph)
    run_example("AES Encryption", create_sample_aes_graph)
    run_example("LETKF Algorithm", create_sample_letkf_graph)
    
    print("\n" + "=" * 80)
    print("\nExample complete!")
    print("Note: To visualize the DOT files, you need to have GraphViz installed.")
    print("You can install GraphViz from https://graphviz.org/ or using your package manager.")
    print("For example: 'sudo apt-get install graphviz' on Ubuntu or 'brew install graphviz' on macOS.")

def run_example(algorithm_name, create_graph_func):
    """Run the synthesis and visualization for a given algorithm"""
    print(f"\n{'-' * 40}")
    print(f"Algorithm: {algorithm_name}")
    print(f"{'-' * 40}")
    
    # Generate graph
    print(f"\nGenerating hardware netlist for {algorithm_name}...")
    graph = create_graph_func()
    
    # Display the hardware netlist with default settings
    print(f"\nRunning hardware synthesis for {algorithm_name}...")
    netlist = display_hardware_netlist(graph)
    print(netlist)
    
    # Generate GraphViz DOT representation
    print(f"\nGenerating GraphViz DOT representation for {algorithm_name}...")
    output_file = f"{algorithm_name.lower().replace(' ', '_')}_hardware.dot"
    dot_result = display_hardware_dot(graph, output_file=output_file)
    print(f"GraphViz DOT file created: {output_file}")
    
    # Generate PNG file from DOT
    print(f"\nGenerating PNG visualization for {algorithm_name}...")
    os.system(f"dot -Tpng {output_file} -o {output_file.replace('.dot', '.png')}")
    print(f"PNG file created: {output_file.replace('.dot', '.png')}")
    
    return netlist

if __name__ == "__main__":
    main() 