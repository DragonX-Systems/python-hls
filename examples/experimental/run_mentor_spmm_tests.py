#!/usr/bin/env python3
"""
Main script to run all Mentor SpMM tests and visualizations
"""

import os
import sys
import time
import logging
import subprocess
from pprint import pformat

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mentor_spmm_main.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mentor_spmm_main")

def install_dependencies():
    """Install required dependencies"""
    logger.info("Installing required dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        logger.info("Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install dependencies: {e}")
        raise

def run_test_script(script_name):
    """Run a test script and return the success status"""
    logger.info(f"Running {script_name}...")
    try:
        subprocess.check_call([sys.executable, script_name])
        logger.info(f"{script_name} executed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {script_name}: {e}")
        return False

def check_visualizations():
    """Check if visualization files were generated"""
    visualization_files = [
        "mentor_spmm_datapath.png",
        "mentor_spmm_scheduled_datapath.png",
        "mentor_spmm_control_flow.png",
        "mentor_spmm_netlist.png",
        "mentor_spmm_detailed_netlist.png",
        "mentor_spmm_pipeline.png"
    ]
    
    missing_files = [f for f in visualization_files if not os.path.exists(f)]
    
    if missing_files:
        logger.warning(f"The following visualization files were not generated: {missing_files}")
        return False
    else:
        logger.info("All visualization files were generated successfully")
        return True

def main():
    """Main function to run all tests and visualizations"""
    start_time = time.time()
    logger.info("=" * 80)
    logger.info("Starting Mentor SpMM testing and visualization")
    logger.info("=" * 80)
    
    # Install dependencies
    install_dependencies()
    
    # Run the functional test first
    functional_success = run_test_script("test_mentor_spmm.py")
    
    # Run the visualization script
    if functional_success:
        visualization_success = run_test_script("visualize_mentor_spmm.py")
    else:
        logger.error("Skipping visualization due to functional test failure")
        visualization_success = False
    
    # Check if visualizations were generated
    if visualization_success:
        check_visualizations()
    
    # Print summary
    elapsed_time = time.time() - start_time
    logger.info("=" * 80)
    logger.info(f"Mentor SpMM testing and visualization completed in {elapsed_time:.2f} seconds")
    logger.info(f"Functional test: {'SUCCESS' if functional_success else 'FAILED'}")
    logger.info(f"Visualization: {'SUCCESS' if visualization_success else 'FAILED'}")
    logger.info("=" * 80)
    
    return functional_success and visualization_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 