module portfolio_var (
    input wire clk,
    input wire rst_n,
    input wire [31:0] weights_data_in,
    input wire [9:0] weights_addr,
    input wire weights_enable,
    input wire weights_write_enable,
    output wire weights_ready,
    input wire [31:0] weights_size,
    input wire [31:0] cov_matrix_data_in,
    input wire [9:0] cov_matrix_addr,
    input wire cov_matrix_enable,
    input wire cov_matrix_write_enable,
    output wire cov_matrix_ready,
    input wire [31:0] cov_matrix_size,
    output reg signed [31:0] return_val,
    output reg valid,
    output reg done
);

// Internal signals
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

// Internal signals for array cov_matrix
reg [31:0] cov_matrix_mem [0:1023];
reg [9:0] cov_matrix_internal_addr;
reg [31:0] cov_matrix_internal_data;
reg cov_matrix_internal_write_enable;
reg cov_matrix_internal_read_enable;
reg cov_matrix_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg cov_matrix_operation_done;
reg [31:0] cov_matrix_actual_size;
reg [31:0] cov_matrix_write_count;

reg signed [31:0] port_var;
reg signed [31:0] i;
reg signed [31:0] for_tmp_44;
reg signed [31:0] row_sum;
reg signed [31:0] j;
reg signed [31:0] for_tmp_82;
reg signed [31:0] tmp_load_90;
reg signed [31:0] tmp_load_94;
reg signed [31:0] tmp_load_98;
reg signed [31:0] tmp_mul_102;
reg signed [31:0] tmp_load_110;
reg signed [31:0] x;
reg signed [31:0] r;
reg signed [31:0] _;
reg signed [31:0] for_tmp_163;
reg signed [31:0] tmp_mul_183;
reg signed [31:0] var_99;

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
            if (weights_operation_done) begin
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
                loop_limit <= weights_actual_size;
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

// Array input interface for cov_matrix - Industry-grade continuous write FSM
assign cov_matrix_ready = (cov_matrix_state == 1'b0) || (cov_matrix_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        cov_matrix_state <= 1'b0;  // IDLE
        cov_matrix_operation_done <= 1'b0;
        cov_matrix_actual_size <= 1024;
        cov_matrix_write_count <= 32'h0;
    end else begin
        case (cov_matrix_state)
            1'b0: begin // IDLE
                if (cov_matrix_enable && cov_matrix_write_enable) begin
                    cov_matrix_state <= 1'b1; // ACTIVE_WRITE
                    cov_matrix_actual_size <= cov_matrix_size;
                    cov_matrix_operation_done <= 1'b0;
                    cov_matrix_write_count <= 32'h0;
                end else begin
                    cov_matrix_operation_done <= (cov_matrix_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (cov_matrix_enable && cov_matrix_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, cov_matrix_addr} < cov_matrix_actual_size) begin
                        cov_matrix_mem[cov_matrix_addr] <= cov_matrix_data_in;
                        cov_matrix_write_count <= cov_matrix_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    cov_matrix_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    cov_matrix_state <= 1'b0; // Return to IDLE
                    cov_matrix_operation_done <= 1'b1;
                end
            end
            default: cov_matrix_state <= 1'b0;
        endcase
    end
end


// Industry-Grade Datapath Logic
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        // Reset all local variables
        port_var <= 0;
        i <= 0;
        for_tmp_44 <= 0;
        row_sum <= 0;
        j <= 0;
        for_tmp_82 <= 0;
        tmp_load_90 <= 0;
        tmp_load_94 <= 0;
        tmp_load_98 <= 0;
        tmp_mul_102 <= 0;
        tmp_load_110 <= 0;
        x <= 0;
        r <= 0;
        _ <= 0;
        for_tmp_163 <= 0;
        tmp_mul_183 <= 0;
        var_99 <= 0;
        loop_counter <= -32'sd1;  // -1 using signed decimal
    end else begin
        case (fsm_state)
            FSM_INIT: begin
                // Initialize accumulator and loop variables
                row_sum <= 0;
                loop_counter <= -32'sd1;  // -1 using signed decimal
            end
            FSM_LOOP_BODY: begin
                // Increment counter first
                loop_counter <= loop_counter + 1'b1;
            end
            FSM_LOOP_UPDATE: begin
                // Execute array access using incremented counter
                // Array access using current loop_counter
                row_sum <= row_sum + (32'd0 + weights_mem[loop_counter]);
            end
            FSM_DONE: begin
                // Set final output
                return_val <= row_sum;
            end
            default: begin
                // Default case - no operation
            end
        endcase
    end
end

endmodule

