module attention_slice (
    input wire clk,
    input wire rst_n,
    input wire [31:0] q_data_in,
    input wire [9:0] q_addr,
    input wire q_enable,
    input wire q_write_enable,
    output wire q_ready,
    input wire [31:0] q_size,
    input wire [31:0] k_data_in,
    input wire [9:0] k_addr,
    input wire k_enable,
    input wire k_write_enable,
    output wire k_ready,
    input wire [31:0] k_size,
    input wire [31:0] v_data_in,
    input wire [9:0] v_addr,
    input wire v_enable,
    input wire v_write_enable,
    output wire v_ready,
    input wire [31:0] v_size,
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
// Internal signals for array q
reg [31:0] q_mem [0:1023];
reg [9:0] q_internal_addr;
reg [31:0] q_internal_data;
reg q_internal_write_enable;
reg q_internal_read_enable;
reg q_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg q_operation_done;
reg [31:0] q_actual_size;
reg [31:0] q_write_count;

// Internal signals for array k
reg [31:0] k_mem [0:1023];
reg [9:0] k_internal_addr;
reg [31:0] k_internal_data;
reg k_internal_write_enable;
reg k_internal_read_enable;
reg k_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg k_operation_done;
reg [31:0] k_actual_size;
reg [31:0] k_write_count;

// Internal signals for array v
reg [31:0] v_mem [0:1023];
reg [9:0] v_internal_addr;
reg [31:0] v_internal_data;
reg v_internal_write_enable;
reg v_internal_read_enable;
reg v_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg v_operation_done;
reg [31:0] v_actual_size;
reg [31:0] v_write_count;

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

reg signed [31:0] total;
reg signed [31:0] scores;
reg signed [31:0] i;
reg signed [31:0] for_tmp_45;
reg signed [31:0] s;
reg signed [31:0] d;
reg signed [31:0] for_tmp_83;
reg signed [31:0] tmp_load_91;
reg signed [31:0] tmp_load_95;
reg signed [31:0] tmp_load_99;
reg signed [31:0] tmp_mul_103;
reg signed [31:0] for_tmp_155;
reg signed [31:0] tmp_load_163;
reg signed [31:0] for_tmp_205;
reg signed [31:0] ctx;
reg signed [31:0] for_tmp_242;
reg signed [31:0] tmp_load_250;
reg signed [31:0] tmp_load_254;
reg signed [31:0] tmp_load_258;
reg signed [31:0] tmp_mul_262;

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
            if (q_operation_done) begin
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
                loop_limit <= q_actual_size;
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

// Array input interface for q - Industry-grade continuous write FSM
assign q_ready = (q_state == 1'b0) || (q_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        q_state <= 1'b0;  // IDLE
        q_operation_done <= 1'b0;
        q_actual_size <= 1024;
        q_write_count <= 32'h0;
    end else begin
        case (q_state)
            1'b0: begin // IDLE
                if (q_enable && q_write_enable) begin
                    q_state <= 1'b1; // ACTIVE_WRITE
                    q_actual_size <= q_size;
                    q_operation_done <= 1'b0;
                    q_write_count <= 32'h0;
                end else begin
                    q_operation_done <= (q_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (q_enable && q_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, q_addr} < q_actual_size) begin
                        q_mem[q_addr] <= q_data_in;
                        q_write_count <= q_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    q_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    q_state <= 1'b0; // Return to IDLE
                    q_operation_done <= 1'b1;
                end
            end
            default: q_state <= 1'b0;
        endcase
    end
end

// Array input interface for k - Industry-grade continuous write FSM
assign k_ready = (k_state == 1'b0) || (k_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        k_state <= 1'b0;  // IDLE
        k_operation_done <= 1'b0;
        k_actual_size <= 1024;
        k_write_count <= 32'h0;
    end else begin
        case (k_state)
            1'b0: begin // IDLE
                if (k_enable && k_write_enable) begin
                    k_state <= 1'b1; // ACTIVE_WRITE
                    k_actual_size <= k_size;
                    k_operation_done <= 1'b0;
                    k_write_count <= 32'h0;
                end else begin
                    k_operation_done <= (k_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (k_enable && k_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, k_addr} < k_actual_size) begin
                        k_mem[k_addr] <= k_data_in;
                        k_write_count <= k_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    k_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    k_state <= 1'b0; // Return to IDLE
                    k_operation_done <= 1'b1;
                end
            end
            default: k_state <= 1'b0;
        endcase
    end
end

// Array input interface for v - Industry-grade continuous write FSM
assign v_ready = (v_state == 1'b0) || (v_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        v_state <= 1'b0;  // IDLE
        v_operation_done <= 1'b0;
        v_actual_size <= 1024;
        v_write_count <= 32'h0;
    end else begin
        case (v_state)
            1'b0: begin // IDLE
                if (v_enable && v_write_enable) begin
                    v_state <= 1'b1; // ACTIVE_WRITE
                    v_actual_size <= v_size;
                    v_operation_done <= 1'b0;
                    v_write_count <= 32'h0;
                end else begin
                    v_operation_done <= (v_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (v_enable && v_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, v_addr} < v_actual_size) begin
                        v_mem[v_addr] <= v_data_in;
                        v_write_count <= v_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    v_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    v_state <= 1'b0; // Return to IDLE
                    v_operation_done <= 1'b1;
                end
            end
            default: v_state <= 1'b0;
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
        total <= 0;
        scores <= 0;
        i <= 0;
        for_tmp_45 <= 0;
        s <= 0;
        d <= 0;
        for_tmp_83 <= 0;
        tmp_load_91 <= 0;
        tmp_load_95 <= 0;
        tmp_load_99 <= 0;
        tmp_mul_103 <= 0;
        for_tmp_155 <= 0;
        tmp_load_163 <= 0;
        for_tmp_205 <= 0;
        ctx <= 0;
        for_tmp_242 <= 0;
        tmp_load_250 <= 0;
        tmp_load_254 <= 0;
        tmp_load_258 <= 0;
        tmp_mul_262 <= 0;
        loop_counter <= -32'sd1;  // -1 using signed decimal
    end else begin
        case (fsm_state)
            FSM_INIT: begin
                // Initialize accumulator and loop variables
                total <= 0;
                loop_counter <= -32'sd1;  // -1 using signed decimal
            end
            FSM_LOOP_BODY: begin
                // Increment counter first
                loop_counter <= loop_counter + 1'b1;
            end
            FSM_LOOP_UPDATE: begin
                // Execute array access using incremented counter
                // Array access using current loop_counter
                total <= total + (32'd0 + q_mem[loop_counter]);
            end
            FSM_DONE: begin
                // Set final output
                return_val <= total;
            end
            default: begin
                // Default case - no operation
            end
        endcase
    end
end

endmodule

