module mlp_layer (
    input wire clk,
    input wire rst_n,
    input wire [31:0] x_data_in,
    input wire [9:0] x_addr,
    input wire x_enable,
    input wire x_write_enable,
    output wire x_ready,
    input wire [31:0] x_size,
    input wire [31:0] w_data_in,
    input wire [9:0] w_addr,
    input wire w_enable,
    input wire w_write_enable,
    output wire w_ready,
    input wire [31:0] w_size,
    input wire [31:0] b_data_in,
    input wire [9:0] b_addr,
    input wire b_enable,
    input wire b_write_enable,
    output wire b_ready,
    input wire [31:0] b_size,
    input wire [31:0] y_data_in,
    input wire [9:0] y_addr,
    input wire y_enable,
    input wire y_write_enable,
    output wire y_ready,
    input wire [31:0] y_size,
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

// Internal signals for array w
reg [31:0] w_mem [0:1023];
reg [9:0] w_internal_addr;
reg [31:0] w_internal_data;
reg w_internal_write_enable;
reg w_internal_read_enable;
reg w_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg w_operation_done;
reg [31:0] w_actual_size;
reg [31:0] w_write_count;

// Internal signals for array b
reg [31:0] b_mem [0:1023];
reg [9:0] b_internal_addr;
reg [31:0] b_internal_data;
reg b_internal_write_enable;
reg b_internal_read_enable;
reg b_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg b_operation_done;
reg [31:0] b_actual_size;
reg [31:0] b_write_count;

// Internal signals for array y
reg [31:0] y_mem [0:1023];
reg [9:0] y_internal_addr;
reg [31:0] y_internal_data;
reg y_internal_write_enable;
reg y_internal_read_enable;
reg y_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg y_operation_done;
reg [31:0] y_actual_size;
reg [31:0] y_write_count;

reg signed [31:0] i;
reg signed [31:0] for_tmp_31;
reg signed [31:0] tmp_load_39;
reg signed [31:0] acc;
reg signed [31:0] j;
reg signed [31:0] for_tmp_71;
reg signed [31:0] tmp_load_79;
reg signed [31:0] tmp_load_83;
reg signed [31:0] tmp_load_87;
reg signed [31:0] tmp_mul_91;
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

// Array input interface for w - Industry-grade continuous write FSM
assign w_ready = (w_state == 1'b0) || (w_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        w_state <= 1'b0;  // IDLE
        w_operation_done <= 1'b0;
        w_actual_size <= 1024;
        w_write_count <= 32'h0;
    end else begin
        case (w_state)
            1'b0: begin // IDLE
                if (w_enable && w_write_enable) begin
                    w_state <= 1'b1; // ACTIVE_WRITE
                    w_actual_size <= w_size;
                    w_operation_done <= 1'b0;
                    w_write_count <= 32'h0;
                end else begin
                    w_operation_done <= (w_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (w_enable && w_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, w_addr} < w_actual_size) begin
                        w_mem[w_addr] <= w_data_in;
                        w_write_count <= w_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    w_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    w_state <= 1'b0; // Return to IDLE
                    w_operation_done <= 1'b1;
                end
            end
            default: w_state <= 1'b0;
        endcase
    end
end

// Array input interface for b - Industry-grade continuous write FSM
assign b_ready = (b_state == 1'b0) || (b_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        b_state <= 1'b0;  // IDLE
        b_operation_done <= 1'b0;
        b_actual_size <= 1024;
        b_write_count <= 32'h0;
    end else begin
        case (b_state)
            1'b0: begin // IDLE
                if (b_enable && b_write_enable) begin
                    b_state <= 1'b1; // ACTIVE_WRITE
                    b_actual_size <= b_size;
                    b_operation_done <= 1'b0;
                    b_write_count <= 32'h0;
                end else begin
                    b_operation_done <= (b_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (b_enable && b_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, b_addr} < b_actual_size) begin
                        b_mem[b_addr] <= b_data_in;
                        b_write_count <= b_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    b_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    b_state <= 1'b0; // Return to IDLE
                    b_operation_done <= 1'b1;
                end
            end
            default: b_state <= 1'b0;
        endcase
    end
end

// Array input interface for y - Industry-grade continuous write FSM
assign y_ready = (y_state == 1'b0) || (y_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        y_state <= 1'b0;  // IDLE
        y_operation_done <= 1'b0;
        y_actual_size <= 1024;
        y_write_count <= 32'h0;
    end else begin
        case (y_state)
            1'b0: begin // IDLE
                if (y_enable && y_write_enable) begin
                    y_state <= 1'b1; // ACTIVE_WRITE
                    y_actual_size <= y_size;
                    y_operation_done <= 1'b0;
                    y_write_count <= 32'h0;
                end else begin
                    y_operation_done <= (y_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (y_enable && y_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, y_addr} < y_actual_size) begin
                        y_mem[y_addr] <= y_data_in;
                        y_write_count <= y_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    y_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    y_state <= 1'b0; // Return to IDLE
                    y_operation_done <= 1'b1;
                end
            end
            default: y_state <= 1'b0;
        endcase
    end
end


// Industry-Grade Datapath Logic
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        // Reset all local variables
        i <= 0;
        for_tmp_31 <= 0;
        tmp_load_39 <= 0;
        acc <= 0;
        j <= 0;
        for_tmp_71 <= 0;
        tmp_load_79 <= 0;
        tmp_load_83 <= 0;
        tmp_load_87 <= 0;
        tmp_mul_91 <= 0;
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

