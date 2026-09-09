#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'python_hls'))

from python_hls.hls import HLS

# Create test function
test_code = '''
def array_sum(data):
    total = 0
    for i in range(len(data)):
        total += data[i]
    return total
'''

with open('test_array_function.py', 'w') as f:
    f.write(test_code)

# Compile
hls = HLS()
result = hls.compile('test_array_function.py', entry_function='array_sum')

print(f"Result type: {type(result)}")
print(f"Result: {result}")

# Handle tuple result
if isinstance(result, tuple):
    netlist, _ = result
    print(f"Netlist type: {type(netlist)}")
    
    if hasattr(netlist, 'modules'):
        module = netlist.modules['array_sum']
        rtl_code = module.verilog_blocks[0]
        
        # Save to file
        with open('generated_rtl.v', 'w') as f:
            f.write(rtl_code)
        
        print("RTL saved to generated_rtl.v")
        print("First 50 lines:")
        print("=" * 50)
        lines = rtl_code.split('\n')
        for i, line in enumerate(lines[:50]):
            print(f"{i+1:3d}: {line}")
    else:
        print("No modules found in netlist")
else:
    print("Unexpected result format")

# Clean up
os.remove('test_array_function.py') 