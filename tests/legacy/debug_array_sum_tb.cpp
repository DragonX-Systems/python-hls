#include <iostream>
#include <vector>
#include <verilated.h>
#include "Varray_sum.h"

// Helper function to write array data for data
void write_array_data(Varray_sum* dut, const std::vector<uint32_t>& data) {
    dut->data_size = data.size();
    for (size_t i = 0; i < data.size(); i++) {
        dut->data_addr = i;
        dut->data_data_in = data[i];
        dut->data_enable = 1;
        dut->data_write_enable = 1;
        dut->clk = 0; dut->eval();
        dut->clk = 1; dut->eval();
        dut->data_enable = 0;
        dut->data_write_enable = 0;
        dut->clk = 0; dut->eval();
    }
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
    std::vector<uint32_t> data_data_0 = {720, 901, 79, 267, 247, 303, 912, 849, 455, 226, 608, 997, 268, 738, 702, 559};
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
    std::vector<uint32_t> data_data_1 = {352, 167, 197, 596, 780};
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
    std::vector<uint32_t> data_data_2 = {728, 85, 4, 524, 453, 762, 154, 24, 664, 225, 77, 400, 798, 37, 600, 51, 247};
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

    // Test case 4
    // Reset DUT for clean state
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    // Write array data for data
    std::vector<uint32_t> data_data_3 = {};
    write_array_data(dut, data_data_3);

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

    // Test case 5
    // Reset DUT for clean state
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    // Write array data for data
    std::vector<uint32_t> data_data_4 = {1000};
    write_array_data(dut, data_data_4);

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

    // Test case 6
    // Reset DUT for clean state
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    // Write array data for data
    std::vector<uint32_t> data_data_5 = {0};
    write_array_data(dut, data_data_5);

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