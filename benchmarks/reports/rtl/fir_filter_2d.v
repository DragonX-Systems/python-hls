module fir_filter_2d (
    input wire clk,
    input wire rst_n,
    input wire [31:0] img_data_in,
    input wire [9:0] img_addr,
    input wire img_enable,
    input wire img_write_enable,
    output wire img_ready,
    input wire [31:0] img_size,
    input wire [31:0] kernel_data_in,
    input wire [9:0] kernel_addr,
    input wire kernel_enable,
    input wire kernel_write_enable,
    output wire kernel_ready,
    input wire [31:0] kernel_size,
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
// Internal signals for array img
reg [31:0] img_mem [0:1023];
reg [9:0] img_internal_addr;
reg [31:0] img_internal_data;
reg img_internal_write_enable;
reg img_internal_read_enable;
reg img_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg img_operation_done;
reg [31:0] img_actual_size;
reg [31:0] img_write_count;

// Internal signals for array kernel
reg [31:0] kernel_mem [0:1023];
reg [9:0] kernel_internal_addr;
reg [31:0] kernel_internal_data;
reg kernel_internal_write_enable;
reg kernel_internal_read_enable;
reg kernel_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg kernel_operation_done;
reg [31:0] kernel_actual_size;
reg [31:0] kernel_write_count;

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

reg signed [31:0] r;
reg signed [31:0] for_tmp_30;
reg signed [31:0] c;
reg signed [31:0] for_tmp_61;
reg signed [31:0] val;
reg signed [31:0] kr;
reg signed [31:0] for_tmp_99;
reg signed [31:0] kc;
reg signed [31:0] for_tmp_130;
reg signed [31:0] tmp_add_138;
reg signed [31:0] tmp_load_142;
reg signed [31:0] tmp_add_146;
reg signed [31:0] tmp_load_150;
reg signed [31:0] tmp_load_154;
reg signed [31:0] tmp_load_158;
reg signed [31:0] tmp_mul_162;
reg signed [31:0] tmp_load_172;

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
            if (img_operation_done) begin
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
                loop_limit <= img_actual_size;
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

// Array input interface for img - Industry-grade continuous write FSM
assign img_ready = (img_state == 1'b0) || (img_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        img_state <= 1'b0;  // IDLE
        img_operation_done <= 1'b0;
        img_actual_size <= 1024;
        img_write_count <= 32'h0;
    end else begin
        case (img_state)
            1'b0: begin // IDLE
                if (img_enable && img_write_enable) begin
                    img_state <= 1'b1; // ACTIVE_WRITE
                    img_actual_size <= img_size;
                    img_operation_done <= 1'b0;
                    img_write_count <= 32'h0;
                end else begin
                    img_operation_done <= (img_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (img_enable && img_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, img_addr} < img_actual_size) begin
                        img_mem[img_addr] <= img_data_in;
                        img_write_count <= img_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    img_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    img_state <= 1'b0; // Return to IDLE
                    img_operation_done <= 1'b1;
                end
            end
            default: img_state <= 1'b0;
        endcase
    end
end

// Array input interface for kernel - Industry-grade continuous write FSM
assign kernel_ready = (kernel_state == 1'b0) || (kernel_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        kernel_state <= 1'b0;  // IDLE
        kernel_operation_done <= 1'b0;
        kernel_actual_size <= 1024;
        kernel_write_count <= 32'h0;
    end else begin
        case (kernel_state)
            1'b0: begin // IDLE
                if (kernel_enable && kernel_write_enable) begin
                    kernel_state <= 1'b1; // ACTIVE_WRITE
                    kernel_actual_size <= kernel_size;
                    kernel_operation_done <= 1'b0;
                    kernel_write_count <= 32'h0;
                end else begin
                    kernel_operation_done <= (kernel_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (kernel_enable && kernel_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, kernel_addr} < kernel_actual_size) begin
                        kernel_mem[kernel_addr] <= kernel_data_in;
                        kernel_write_count <= kernel_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    kernel_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    kernel_state <= 1'b0; // Return to IDLE
                    kernel_operation_done <= 1'b1;
                end
            end
            default: kernel_state <= 1'b0;
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
        r <= 0;
        for_tmp_30 <= 0;
        c <= 0;
        for_tmp_61 <= 0;
        val <= 0;
        kr <= 0;
        for_tmp_99 <= 0;
        kc <= 0;
        for_tmp_130 <= 0;
        tmp_add_138 <= 0;
        tmp_load_142 <= 0;
        tmp_add_146 <= 0;
        tmp_load_150 <= 0;
        tmp_load_154 <= 0;
        tmp_load_158 <= 0;
        tmp_mul_162 <= 0;
        tmp_load_172 <= 0;
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

