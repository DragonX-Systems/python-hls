#include <iostream>
#include <vector>
#include <verilated.h>
#include "Vema_update.h"

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    Vema_update* dut = new Vema_update;

    // Reset
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    // Test case 1
    dut->y_prev = 100;
    dut->x = 110;
    dut->alpha = 1;
    // Run until computation completes
    int cycles_to_done = -1;
    for (int cycle = 0; cycle < 100; cycle++) {
        dut->clk = 0;
        dut->eval();
        dut->clk = 1;
        dut->eval();
        if (dut->done) {
            cycles_to_done = cycle + 1;
            break;
        }
    }

    // Output result
    std::cout << "RESULT: inputs={y_prev=100,x=110,alpha=1},output=" << dut->return_val << ",cycles=" << cycles_to_done << std::endl;

    // Test case 2
    // Reset DUT for clean state
    dut->rst_n = 0;
    dut->clk = 0;
    dut->eval();
    dut->clk = 1;
    dut->eval();
    dut->rst_n = 1;

    dut->y_prev = 100;
    dut->x = 110;
    dut->alpha = 0;
    // Run until computation completes
    int cycles_to_done = -1;
    for (int cycle = 0; cycle < 100; cycle++) {
        dut->clk = 0;
        dut->eval();
        dut->clk = 1;
        dut->eval();
        if (dut->done) {
            cycles_to_done = cycle + 1;
            break;
        }
    }

    // Output result
    std::cout << "RESULT: inputs={y_prev=100,x=110,alpha=0},output=" << dut->return_val << ",cycles=" << cycles_to_done << std::endl;

    delete dut;
    return 0;
}