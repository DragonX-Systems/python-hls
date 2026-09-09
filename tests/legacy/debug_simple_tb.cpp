#include <iostream>
#include <vector>
#include <verilated.h>
#include "Varray_sum.h"

// Helper function to write array data for data
void write_array_data(Varray_sum* dut, const std::vector<uint32_t>& data) {
    dut->data_size = data.size();
    dut->data_enable = 1;  // Keep enable high for entire write sequence
    for (size_t i = 0; i < data.size(); i++) {
        dut->data_addr = i;
        dut->data_data_in = data[i];
        dut->data_write_enable = 1;
        dut->clk = 0; dut->eval();
        dut->clk = 1; dut->eval();
        dut->data_write_enable = 0;
        dut->clk = 0; dut->eval();
    }
    // Signal completion by disabling enable
    dut->data_enable = 0;
    dut->clk = 0; dut->eval();
    dut->clk = 1; dut->eval();
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    Varray_sum* dut = new Varray_sum;

    // Reset
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    // Test case 1
    // Write array data for data
    std::vector<uint32_t> data_data_0 = {5, 10};
    write_array_data(dut, data_data_0);

    // Run until computation completes
    for (int cycle = 0; cycle < 100; cycle++) {
        dut->clk = 0;
        dut->eval();
        dut->clk = 1;
        dut->eval();
        if (dut->done) {
            break;
        }
    }

    // Output result
    std::cout << "RESULT: inputs={},output=" << dut->return_val << std::endl;

    // Test case 2
    // Reset DUT for clean state
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    // Write array data for data
    std::vector<uint32_t> data_data_1 = {100};
    write_array_data(dut, data_data_1);

    // Run until computation completes
    for (int cycle = 0; cycle < 100; cycle++) {
        dut->clk = 0;
        dut->eval();
        dut->clk = 1;
        dut->eval();
        if (dut->done) {
            break;
        }
    }

    // Output result
    std::cout << "RESULT: inputs={},output=" << dut->return_val << std::endl;

    // Test case 3
    // Reset DUT for clean state
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    // Write array data for data
    std::vector<uint32_t> data_data_2 = {};
    write_array_data(dut, data_data_2);

    // Run until computation completes
    for (int cycle = 0; cycle < 100; cycle++) {
        dut->clk = 0;
        dut->eval();
        dut->clk = 1;
        dut->eval();
        if (dut->done) {
            break;
        }
    }

    // Output result
    std::cout << "RESULT: inputs={},output=" << dut->return_val << std::endl;

    delete dut;
    return 0;
}