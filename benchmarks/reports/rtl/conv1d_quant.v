module conv1d_quant (
    input wire clk,
    input wire rst_n,
    input wire [31:0] x_data_in,
    input wire [9:0] x_addr,
    input wire x_enable,
    input wire x_write_enable,
    output wire x_ready,
    input wire [31:0] x_size,
    input wire [31:0] weights_data_in,
    input wire [9:0] weights_addr,
    input wire weights_enable,
    input wire weights_write_enable,
    output wire weights_ready,
    input wire [31:0] weights_size,
    input wire signed [31:0] bias,
    input wire [31:0] out_data_in,
    input wire [9:0] out_addr,
    input wire out_enable,
    input wire out_write_enable,
    output wire out_ready,
    input wire [31:0] out_size,
    output reg signed [31:0] return_val,
    output reg valid,
    output reg done
);

// Internal signals
// Internal signals for array x
reg [31:0] x_mem [0:1023];
reg [9:0] x_internal_addr;
reg [31:0] x_internal_data;
reg x_internal_write_enable;
reg x_internal_read_enable;
reg x_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg x_operation_done;
reg [31:0] x_actual_size;
reg [31:0] x_write_count;

// Internal signals for array weights
reg [31:0] weights_mem [0:1023];
reg [9:0] weights_internal_addr;
reg [31:0] weights_internal_data;
reg weights_internal_write_enable;
reg weights_internal_read_enable;
reg weights_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg weights_operation_done;
reg [31:0] weights_actual_size;
reg [31:0] weights_write_count;

// Internal signals for array out
reg [31:0] out_mem [0:1023];
reg [9:0] out_internal_addr;
reg [31:0] out_internal_data;
reg out_internal_write_enable;
reg out_internal_read_enable;
reg out_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg out_operation_done;
reg [31:0] out_actual_size;
reg [31:0] out_write_count;

reg signed [31:0] i;
reg signed [31:0] for_tmp_31;
reg signed [31:0] acc;
reg signed [31:0] k;
reg signed [31:0] for_tmp_67;
reg signed [31:0] tmp_add_75;
reg signed [31:0] tmp_load_79;
reg signed [31:0] tmp_load_83;
reg signed [31:0] tmp_mul_87;
reg signed [31:0] tmp_add_97;
reg signed [31:0] tmp_load_101;
reg signed [31:0] tmp_add_105;
reg signed [31:0] res;
/* verilator lint_off UNDRIVEN */
reg signed [31:0] temp_0;
/* verilator lint_on UNDRIVEN */

// Industry-Grade FSM Controller
// FSM State Definitions
// 6 states encoded in 3 bits
localparam FSM_IDLE = 3'd0;
localparam FSM_INIT = 3'd1;
localparam FSM_ACTIVE = 3'd2;
localparam FSM_DONE = 3'd3;
localparam FSM_LOOP_BODY = 3'd4;
localparam FSM_LOOP_UPDATE = 3'd5;

// FSM Registers and Control Signals
reg [2:0] fsm_state, fsm_next_state;
reg fsm_enable;
reg [31:0] fsm_cycle_count;
reg signed [31:0] loop_counter;
reg [31:0] loop_limit;

// FSM State Register
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        fsm_state <= FSM_IDLE;
        fsm_cycle_count <= 32'h0;
        fsm_enable <= 1'b0;
    end else begin
        fsm_state <= fsm_next_state;
        fsm_cycle_count <= fsm_cycle_count + 1'b1;
        fsm_enable <= (fsm_next_state != FSM_IDLE) && (fsm_next_state != FSM_DONE);
    end
end

// FSM Next State Logic
always @(*) begin
    fsm_next_state = fsm_state;
    case (fsm_state)
        FSM_IDLE: begin
            // Wait for array data to be ready before starting computation
            if (x_operation_done) begin
                fsm_next_state = FSM_INIT;
            end else begin
                fsm_next_state = FSM_IDLE;
            end
        end
        FSM_INIT: begin
            fsm_next_state = FSM_ACTIVE;
        end
        FSM_ACTIVE: begin
            // Ensure loop counter is properly initialized before starting loop
            fsm_next_state = FSM_LOOP_BODY;
        end
        FSM_LOOP_BODY: begin
            // Check loop condition before increment
            if (loop_counter + 1'b1 < loop_limit) begin
                fsm_next_state = FSM_LOOP_UPDATE;  // Continue loop
            end else begin
                fsm_next_state = FSM_DONE;  // Exit loop
            end
        end
        FSM_LOOP_UPDATE: begin
            // Always go back to loop body
            fsm_next_state = FSM_LOOP_BODY;
        end
        FSM_DONE: begin
            fsm_next_state = FSM_IDLE;
        end
        default: begin
            fsm_next_state = FSM_IDLE;
        end
    endcase
end

// FSM Output Logic
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        valid <= 1'b0;
        done <= 1'b0;
        loop_limit <= 32'h0;
    end else begin
        case (fsm_state)
            FSM_IDLE: begin
                valid <= 1'b0;
                done <= 1'b0;
            end
            FSM_INIT: begin
                valid <= 1'b0;
                done <= 1'b0;
                loop_limit <= x_actual_size;
            end
            FSM_ACTIVE: begin
                valid <= 1'b1;
                done <= 1'b0;
            end
            FSM_LOOP_BODY: begin
                valid <= 1'b1;
                done <= 1'b0;
            end
            FSM_LOOP_UPDATE: begin
                valid <= 1'b1;
                done <= 1'b0;
            end
            FSM_DONE: begin
                valid <= 1'b0;
                done <= 1'b1;
            end
            default: begin
                valid <= 1'b0;
                done <= 1'b0;
            end
        endcase
    end
end

// Array input interface for x - Industry-grade continuous write FSM
assign x_ready = (x_state == 1'b0) || (x_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        x_state <= 1'b0;  // IDLE
        x_operation_done <= 1'b0;
        x_actual_size <= 1024;
        x_write_count <= 32'h0;
    end else begin
        case (x_state)
            1'b0: begin // IDLE
                if (x_enable && x_write_enable) begin
                    x_state <= 1'b1; // ACTIVE_WRITE
                    x_actual_size <= x_size;
                    x_operation_done <= 1'b0;
                    x_write_count <= 32'h0;
                end else begin
                    x_operation_done <= (x_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (x_enable && x_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, x_addr} < x_actual_size) begin
                        x_mem[x_addr] <= x_data_in;
                        x_write_count <= x_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    x_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    x_state <= 1'b0; // Return to IDLE
                    x_operation_done <= 1'b1;
                end
            end
            default: x_state <= 1'b0;
        endcase
    end
end

// Array input interface for weights - Industry-grade continuous write FSM
assign weights_ready = (weights_state == 1'b0) || (weights_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        weights_state <= 1'b0;  // IDLE
        weights_operation_done <= 1'b0;
        weights_actual_size <= 1024;
        weights_write_count <= 32'h0;
    end else begin
        case (weights_state)
            1'b0: begin // IDLE
                if (weights_enable && weights_write_enable) begin
                    weights_state <= 1'b1; // ACTIVE_WRITE
                    weights_actual_size <= weights_size;
                    weights_operation_done <= 1'b0;
                    weights_write_count <= 32'h0;
                end else begin
                    weights_operation_done <= (weights_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (weights_enable && weights_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, weights_addr} < weights_actual_size) begin
                        weights_mem[weights_addr] <= weights_data_in;
                        weights_write_count <= weights_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    weights_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    weights_state <= 1'b0; // Return to IDLE
                    weights_operation_done <= 1'b1;
                end
            end
            default: weights_state <= 1'b0;
        endcase
    end
end

// Array input interface for out - Industry-grade continuous write FSM
assign out_ready = (out_state == 1'b0) || (out_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        out_state <= 1'b0;  // IDLE
        out_operation_done <= 1'b0;
        out_actual_size <= 1024;
        out_write_count <= 32'h0;
    end else begin
        case (out_state)
            1'b0: begin // IDLE
                if (out_enable && out_write_enable) begin
                    out_state <= 1'b1; // ACTIVE_WRITE
                    out_actual_size <= out_size;
                    out_operation_done <= 1'b0;
                    out_write_count <= 32'h0;
                end else begin
                    out_operation_done <= (out_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (out_enable && out_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, out_addr} < out_actual_size) begin
                        out_mem[out_addr] <= out_data_in;
                        out_write_count <= out_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    out_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    out_state <= 1'b0; // Return to IDLE
                    out_operation_done <= 1'b1;
                end
            end
            default: out_state <= 1'b0;
        endcase
    end
end


// Industry-Grade Datapath Logic
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        // Reset all local variables
        i <= 0;
        for_tmp_31 <= 0;
        acc <= 0;
        k <= 0;
        for_tmp_67 <= 0;
        tmp_add_75 <= 0;
        tmp_load_79 <= 0;
        tmp_load_83 <= 0;
        tmp_mul_87 <= 0;
        tmp_add_97 <= 0;
        tmp_load_101 <= 0;
        tmp_add_105 <= 0;
        res <= 0;
        temp_0 <= 0;
        loop_counter <= -32'sd1;  // -1 using signed decimal
    end else begin
        case (fsm_state)
            FSM_INIT: begin
                // Initialize accumulator and loop variables
                loop_counter <= -32'sd1;  // -1 using signed decimal
            end
            FSM_LOOP_BODY: begin
                // Increment counter first
                loop_counter <= loop_counter + 1'b1;
            end
            FSM_LOOP_UPDATE: begin
                // Execute array access using incremented counter
                // Generic array processing operation
                return_val <= return_val + (32'd0 + data_mem[loop_counter]);
            end
            FSM_DONE: begin
                // Set final output
            end
            default: begin
                // Default case - no operation
            end
        endcase
    end
end

endmodule

