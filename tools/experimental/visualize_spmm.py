"""
Script to visualize the scheduled datapath for SPMM (Sparse Matrix-Matrix Multiplication).

This script uses the HLS framework to:
1. Compile the SPMM algorithm
2. Generate visualizations in all available formats:
   - Datapath (.dot/.gv files)
   - Scheduled datapath (.dot/.gv files)
   - Netlist (.dot/.gv files)
   - Netlist microarchitecture (.dot/.gv files)

Note: The PNG visualization may fail if Graphviz is not properly installed, but
      the script will still generate the DOT files that can be manually visualized.

Usage:
    python visualize_spmm.py [spmm_variant]

Where:
    spmm_variant - Optional: Use a specific SPMM variant
                   (default, simple_256, simple_512, fixed_256, fixed_512, 128, 256, 512)
"""

import os
import sys
import tempfile
import argparse
import glob

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from python_hls import HLS
except ImportError as e:
    print(f"Error importing python_hls module: {e}")
    print("Make sure you are running this script from the hls-python directory.")
    sys.exit(1)


def get_spmm_variants():
    """Get available SPMM variants in the directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    variants = {
        'default': 'spmm.py',
        'simple_256': 'spmm_simple_256.py',
        'simple_512': 'spmm_simple_512.py',
        'fixed_256': 'spmm_fixed_256.py',
        'fixed_512': 'spmm_fixed_512.py',
        '128': 'spmm_128_code.py',
        '256': 'spmm_256_code.py',
        '512': 'spmm_512_code.py'
    }
    
    # Filter to only include variants that exist
    available_variants = {}
    for name, filename in variants.items():
        if os.path.exists(os.path.join(current_dir, filename)):
            available_variants[name] = filename
    
    return available_variants


def read_spmm_program(variant='default'):
    """Read the specified SPMM program variant."""
    variants = get_spmm_variants()
    
    if variant not in variants:
        available = ', '.join(variants.keys())
        print(f"Error: Variant '{variant}' not found. Available variants: {available}")
        sys.exit(1)
    
    # Get the absolute path to the selected SPMM file
    spmm_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), variants[variant])
    
    try:
        with open(spmm_path, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading SPMM file '{spmm_path}': {e}")
        sys.exit(1)


def generate_visualization(hls, output_dir, prefix, vis_type):
    """Generate a specific visualization safely and find related files."""
    try:
        # Generate the visualization
        if vis_type == "datapath":
            output_file = os.path.join(output_dir, f"{prefix}_{vis_type}.png")
            hls.visualize_datapath(output_file=output_file)
        elif vis_type == "scheduled":
            output_file = os.path.join(output_dir, f"{prefix}_{vis_type}.png")
            hls.visualize_scheduled_datapath(output_file=output_file)
        elif vis_type == "netlist":
            output_file = os.path.join(output_dir, f"{prefix}_{vis_type}.png")
            hls.visualize_netlist(output_file=output_file)
        elif vis_type == "microarch":
            output_file = os.path.join(output_dir, f"{prefix}_{vis_type}.png")
            hls.visualize_netlist_microarch(output_file=output_file)
        else:
            return []
        
        # Find all related files regardless if the PNG was generated
        base_pattern = os.path.join(output_dir, f"{prefix}_{vis_type}*")
        found_files = glob.glob(base_pattern)
        
        # Also check for files with additional suffixes (microarch_microarch pattern)
        alt_pattern = os.path.join(output_dir, f"{prefix}_{vis_type}*{vis_type}*")
        found_files.extend([f for f in glob.glob(alt_pattern) if f not in found_files])
        
        return found_files
            
    except Exception as e:
        print(f"Warning: Error generating {vis_type} visualization: {e}")
        return []


def main():
    """Main function to visualize the SPMM scheduled datapath."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Visualize SPMM datapath')
    parser.add_argument('variant', nargs='?', default='default',
                      help='SPMM variant to visualize (default, simple_256, simple_512, etc.)')
    args = parser.parse_args()
    
    # Get the SPMM program
    spmm_program = read_spmm_program(args.variant)
    variant_name = args.variant
    
    # Create a temporary directory for our source file
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a copy of the SPMM program in the temp directory
        spmm_file = os.path.join(temp_dir, "spmm_temp.py")
        with open(spmm_file, 'w') as f:
            f.write(spmm_program)
        
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualization_output")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        print(f"Compiling SPMM program (variant: {variant_name})...")
        
        # Create an HLS instance
        # Using optimization_level=0 to preserve the structure for visualization
        hls = HLS(optimization_level=0, tech_node=45)
        
        try:
            # Compile the SPMM program
            netlist = hls.compile(spmm_file, target="verilog")
            
            print("Generating visualizations...")
            
            # Create prefix for filenames based on variant
            prefix = f"spmm_{variant_name}" if variant_name != 'default' else "spmm"
            
            # Generate visualizations and collect all related files
            all_files = {}
            for vis_type in ["datapath", "scheduled", "netlist", "microarch"]:
                files = generate_visualization(hls, output_dir, prefix, vis_type)
                if files:
                    all_files[vis_type] = files
            
            # Print summary of generated files
            if all_files:
                print(f"\nGenerated SPMM visualization files for variant '{variant_name}':")
                for vis_type, files in all_files.items():
                    file_count = len(files)
                    if file_count > 0:
                        print(f"  {vis_type.title():15}: {file_count} file(s)")
                        for f in files:
                            if os.path.exists(f):
                                extension = os.path.splitext(f)[1]
                                print(f"    - {os.path.basename(f)} ({extension} format)")
                
                # Print instructions for viewing the DOT/GV files
                print("\nTo view the DOT/GV files:")
                print("1. Install Graphviz: https://graphviz.org/download/")
                print("2. Run: dot -Tpng file.dot -o file.png")
                print("   or use an online viewer like https://dreampuf.github.io/GraphvizOnline/")
                
                # Get scheduled datapath files
                scheduled_files = all_files.get("scheduled", [])
                dot_files = [f for f in scheduled_files if f.endswith('.dot')]
                print(dot_files)
                if dot_files:
                    print("\nTo view the scheduled datapath specifically:")
                    for dot_file in dot_files:
                        print(f"  dot -Tpng {dot_file} -o {os.path.splitext(dot_file)[0]}.png")
            else:
                print("\nNo visualizations were successfully generated.")
        
        except Exception as e:
            print(f"Error during compilation/visualization: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
            
    finally:
        # Clean up the temporary directory
        import shutil
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    main() 