module covariance_matrix (
    input wire clk,
    input wire rst_n,
    input wire [31:0] data_data_in,
    input wire [9:0] data_addr,
    input wire data_enable,
    input wire data_write_enable,
    output wire data_ready,
    input wire [31:0] data_size,
    input wire [31:0] cov_data_in,
    input wire [9:0] cov_addr,
    input wire cov_enable,
    input wire cov_write_enable,
    output wire cov_ready,
    input wire [31:0] cov_size,
    output reg signed [31:0] return_val,
    output reg valid,
    output reg done
);

// Internal signals
// Internal signals for array data
reg [31:0] data_mem [0:1023];
reg [9:0] data_internal_addr;
reg [31:0] data_internal_data;
reg data_internal_write_enable;
reg data_internal_read_enable;
reg data_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg data_operation_done;
reg [31:0] data_actual_size;
reg [31:0] data_write_count;

// Internal signals for array cov
reg [31:0] cov_mem [0:1023];
reg [9:0] cov_internal_addr;
reg [31:0] cov_internal_data;
reg cov_internal_write_enable;
reg cov_internal_read_enable;
reg cov_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg cov_operation_done;
reg [31:0] cov_actual_size;
reg [31:0] cov_write_count;

reg signed [31:0] means;
reg signed [31:0] f;
reg signed [31:0] for_tmp_34;
reg signed [31:0] s;
reg signed [31:0] t;
reg signed [31:0] for_tmp_72;
reg signed [31:0] tmp_load_80;
reg signed [31:0] tmp_load_84;
reg signed [31:0] f1;
reg signed [31:0] for_tmp_119;
reg signed [31:0] f2;
reg signed [31:0] for_tmp_150;
reg signed [31:0] c_sum;
reg signed [31:0] for_tmp_187;
reg signed [31:0] tmp_load_195;
reg signed [31:0] tmp_load_199;
reg signed [31:0] tmp_load_203;
reg signed [31:0] tmp_sub_207;
reg signed [31:0] tmp_load_211;
reg signed [31:0] tmp_load_215;
reg signed [31:0] tmp_load_219;
reg signed [31:0] tmp_sub_223;
reg signed [31:0] tmp_mul_227;
reg signed [31:0] tmp_load_237;

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
            if (data_operation_done) begin
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
                loop_limit <= data_actual_size;
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

// Array input interface for data - Industry-grade continuous write FSM
assign data_ready = (data_state == 1'b0) || (data_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        data_state <= 1'b0;  // IDLE
        data_operation_done <= 1'b0;
        data_actual_size <= 1024;
        data_write_count <= 32'h0;
    end else begin
        case (data_state)
            1'b0: begin // IDLE
                if (data_enable && data_write_enable) begin
                    data_state <= 1'b1; // ACTIVE_WRITE
                    data_actual_size <= data_size;
                    data_operation_done <= 1'b0;
                    data_write_count <= 32'h0;
                end else begin
                    data_operation_done <= (data_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (data_enable && data_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, data_addr} < data_actual_size) begin
                        data_mem[data_addr] <= data_data_in;
                        data_write_count <= data_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    data_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    data_state <= 1'b0; // Return to IDLE
                    data_operation_done <= 1'b1;
                end
            end
            default: data_state <= 1'b0;
        endcase
    end
end

// Array input interface for cov - Industry-grade continuous write FSM
assign cov_ready = (cov_state == 1'b0) || (cov_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        cov_state <= 1'b0;  // IDLE
        cov_operation_done <= 1'b0;
        cov_actual_size <= 1024;
        cov_write_count <= 32'h0;
    end else begin
        case (cov_state)
            1'b0: begin // IDLE
                if (cov_enable && cov_write_enable) begin
                    cov_state <= 1'b1; // ACTIVE_WRITE
                    cov_actual_size <= cov_size;
                    cov_operation_done <= 1'b0;
                    cov_write_count <= 32'h0;
                end else begin
                    cov_operation_done <= (cov_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (cov_enable && cov_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, cov_addr} < cov_actual_size) begin
                        cov_mem[cov_addr] <= cov_data_in;
                        cov_write_count <= cov_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    cov_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    cov_state <= 1'b0; // Return to IDLE
                    cov_operation_done <= 1'b1;
                end
            end
            default: cov_state <= 1'b0;
        endcase
    end
end


// Industry-Grade Datapath Logic
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        // Reset all local variables
        means <= 0;
        f <= 0;
        for_tmp_34 <= 0;
        s <= 0;
        t <= 0;
        for_tmp_72 <= 0;
        tmp_load_80 <= 0;
        tmp_load_84 <= 0;
        f1 <= 0;
        for_tmp_119 <= 0;
        f2 <= 0;
        for_tmp_150 <= 0;
        c_sum <= 0;
        for_tmp_187 <= 0;
        tmp_load_195 <= 0;
        tmp_load_199 <= 0;
        tmp_load_203 <= 0;
        tmp_sub_207 <= 0;
        tmp_load_211 <= 0;
        tmp_load_215 <= 0;
        tmp_load_219 <= 0;
        tmp_sub_223 <= 0;
        tmp_mul_227 <= 0;
        tmp_load_237 <= 0;
        loop_counter <= -32'sd1;  // -1 using signed decimal
    end else begin
        case (fsm_state)
            FSM_INIT: begin
                // Initialize accumulator and loop variables
                c_sum <= 0;
                loop_counter <= -32'sd1;  // -1 using signed decimal
            end
            FSM_LOOP_BODY: begin
                // Increment counter first
                loop_counter <= loop_counter + 1'b1;
            end
            FSM_LOOP_UPDATE: begin
                // Execute array access using incremented counter
                // Array access using current loop_counter
                c_sum <= c_sum + (32'd0 + data_mem[loop_counter]);
            end
            FSM_DONE: begin
                // Set final output
                return_val <= c_sum;
            end
            default: begin
                // Default case - no operation
            end
        endcase
    end
end

endmodule

