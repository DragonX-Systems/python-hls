module zscore_normalize (
    input wire clk,
    input wire rst_n,
    input wire [31:0] x_data_in,
    input wire [9:0] x_addr,
    input wire x_enable,
    input wire x_write_enable,
    output wire x_ready,
    input wire [31:0] x_size,
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

reg signed [31:0] s;
reg signed [31:0] var_sum;
reg signed [31:0] i;
reg signed [31:0] for_tmp_53;
reg signed [31:0] tmp_load_61;
reg signed [31:0] mean;
reg signed [31:0] for_tmp_102;
reg signed [31:0] tmp_load_110;
reg signed [31:0] tmp_sub_114;
reg signed [31:0] diff;
reg signed [31:0] tmp_mul_123;
reg signed [31:0] variance;
reg signed [31:0] std;
reg signed [31:0] _;
reg signed [31:0] for_tmp_170;
reg signed [31:0] for_tmp_216;
reg signed [31:0] tmp_load_224;
reg signed [31:0] tmp_sub_228;
reg signed [31:0] tmp_mul_234;

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
        s <= 0;
        var_sum <= 0;
        i <= 0;
        for_tmp_53 <= 0;
        tmp_load_61 <= 0;
        mean <= 0;
        for_tmp_102 <= 0;
        tmp_load_110 <= 0;
        tmp_sub_114 <= 0;
        diff <= 0;
        tmp_mul_123 <= 0;
        variance <= 0;
        std <= 0;
        _ <= 0;
        for_tmp_170 <= 0;
        for_tmp_216 <= 0;
        tmp_load_224 <= 0;
        tmp_sub_228 <= 0;
        tmp_mul_234 <= 0;
        loop_counter <= -32'sd1;  // -1 using signed decimal
    end else begin
        case (fsm_state)
            FSM_INIT: begin
                // Initialize accumulator and loop variables
                var_sum <= 0;
                loop_counter <= -32'sd1;  // -1 using signed decimal
            end
            FSM_LOOP_BODY: begin
                // Increment counter first
                loop_counter <= loop_counter + 1'b1;
            end
            FSM_LOOP_UPDATE: begin
                // Execute array access using incremented counter
                // Array access using current loop_counter
                var_sum <= var_sum + (32'd0 + x_mem[loop_counter]);
            end
            FSM_DONE: begin
                // Set final output
                return_val <= var_sum;
            end
            default: begin
                // Default case - no operation
            end
        endcase
    end
end

endmodule

