module vwap_orderbook (
    input wire clk,
    input wire rst_n,
    input wire [31:0] bid_prices_data_in,
    input wire [9:0] bid_prices_addr,
    input wire bid_prices_enable,
    input wire bid_prices_write_enable,
    output wire bid_prices_ready,
    input wire [31:0] bid_prices_size,
    input wire [31:0] bid_sizes_data_in,
    input wire [9:0] bid_sizes_addr,
    input wire bid_sizes_enable,
    input wire bid_sizes_write_enable,
    output wire bid_sizes_ready,
    input wire [31:0] bid_sizes_size,
    input wire [31:0] ask_prices_data_in,
    input wire [9:0] ask_prices_addr,
    input wire ask_prices_enable,
    input wire ask_prices_write_enable,
    output wire ask_prices_ready,
    input wire [31:0] ask_prices_size,
    input wire [31:0] ask_sizes_data_in,
    input wire [9:0] ask_sizes_addr,
    input wire ask_sizes_enable,
    input wire ask_sizes_write_enable,
    output wire ask_sizes_ready,
    input wire [31:0] ask_sizes_size,
    output reg signed [31:0] return_val,
    output reg valid,
    output reg done
);

// Internal signals
// Internal signals for array bid_prices
reg [31:0] bid_prices_mem [0:1023];
reg [9:0] bid_prices_internal_addr;
reg [31:0] bid_prices_internal_data;
reg bid_prices_internal_write_enable;
reg bid_prices_internal_read_enable;
reg bid_prices_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg bid_prices_operation_done;
reg [31:0] bid_prices_actual_size;
reg [31:0] bid_prices_write_count;

// Internal signals for array bid_sizes
reg [31:0] bid_sizes_mem [0:1023];
reg [9:0] bid_sizes_internal_addr;
reg [31:0] bid_sizes_internal_data;
reg bid_sizes_internal_write_enable;
reg bid_sizes_internal_read_enable;
reg bid_sizes_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg bid_sizes_operation_done;
reg [31:0] bid_sizes_actual_size;
reg [31:0] bid_sizes_write_count;

// Internal signals for array ask_prices
reg [31:0] ask_prices_mem [0:1023];
reg [9:0] ask_prices_internal_addr;
reg [31:0] ask_prices_internal_data;
reg ask_prices_internal_write_enable;
reg ask_prices_internal_read_enable;
reg ask_prices_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg ask_prices_operation_done;
reg [31:0] ask_prices_actual_size;
reg [31:0] ask_prices_write_count;

// Internal signals for array ask_sizes
reg [31:0] ask_sizes_mem [0:1023];
reg [9:0] ask_sizes_internal_addr;
reg [31:0] ask_sizes_internal_data;
reg ask_sizes_internal_write_enable;
reg ask_sizes_internal_read_enable;
reg ask_sizes_state;  // 1-bit state: 0=IDLE, 1=ACTIVE_WRITE
reg ask_sizes_operation_done;
reg [31:0] ask_sizes_actual_size;
reg [31:0] ask_sizes_write_count;

reg signed [31:0] tot_bid_vol;
reg signed [31:0] tot_ask_vol;
reg signed [31:0] bid_notional;
reg signed [31:0] ask_notional;
reg signed [31:0] vwap_bid;
reg signed [31:0] vwap_ask;
reg signed [31:0] combined_vol;
reg signed [31:0] vwap_mid;
reg signed [31:0] micro_price;
reg signed [31:0] i;
reg signed [31:0] for_tmp_136;
reg signed [31:0] tmp_load_144;
reg signed [31:0] tmp_load_152;
reg signed [31:0] tmp_load_160;
reg signed [31:0] tmp_load_164;
reg signed [31:0] tmp_mul_168;
reg signed [31:0] tmp_load_176;
reg signed [31:0] tmp_load_180;
reg signed [31:0] tmp_mul_184;
reg signed [31:0] tmp_add_220;
reg signed [31:0] tmp_add_240;
reg signed [31:0] tmp_load_248;
reg signed [31:0] tmp_load_254;
reg signed [31:0] tmp_add_258;
reg signed [31:0] top_spread_vol;
reg signed [31:0] tmp_load_281;
reg signed [31:0] tmp_load_287;
reg signed [31:0] tmp_mul_291;
reg signed [31:0] tmp_load_297;
reg signed [31:0] tmp_load_303;
reg signed [31:0] tmp_mul_307;
reg signed [31:0] tmp_add_311;
reg signed [31:0] tmp_add_317;

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
            if (bid_prices_operation_done) begin
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
                loop_limit <= bid_prices_actual_size;
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

// Array input interface for bid_prices - Industry-grade continuous write FSM
assign bid_prices_ready = (bid_prices_state == 1'b0) || (bid_prices_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        bid_prices_state <= 1'b0;  // IDLE
        bid_prices_operation_done <= 1'b0;
        bid_prices_actual_size <= 1024;
        bid_prices_write_count <= 32'h0;
    end else begin
        case (bid_prices_state)
            1'b0: begin // IDLE
                if (bid_prices_enable && bid_prices_write_enable) begin
                    bid_prices_state <= 1'b1; // ACTIVE_WRITE
                    bid_prices_actual_size <= bid_prices_size;
                    bid_prices_operation_done <= 1'b0;
                    bid_prices_write_count <= 32'h0;
                end else begin
                    bid_prices_operation_done <= (bid_prices_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (bid_prices_enable && bid_prices_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, bid_prices_addr} < bid_prices_actual_size) begin
                        bid_prices_mem[bid_prices_addr] <= bid_prices_data_in;
                        bid_prices_write_count <= bid_prices_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    bid_prices_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    bid_prices_state <= 1'b0; // Return to IDLE
                    bid_prices_operation_done <= 1'b1;
                end
            end
            default: bid_prices_state <= 1'b0;
        endcase
    end
end

// Array input interface for bid_sizes - Industry-grade continuous write FSM
assign bid_sizes_ready = (bid_sizes_state == 1'b0) || (bid_sizes_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        bid_sizes_state <= 1'b0;  // IDLE
        bid_sizes_operation_done <= 1'b0;
        bid_sizes_actual_size <= 1024;
        bid_sizes_write_count <= 32'h0;
    end else begin
        case (bid_sizes_state)
            1'b0: begin // IDLE
                if (bid_sizes_enable && bid_sizes_write_enable) begin
                    bid_sizes_state <= 1'b1; // ACTIVE_WRITE
                    bid_sizes_actual_size <= bid_sizes_size;
                    bid_sizes_operation_done <= 1'b0;
                    bid_sizes_write_count <= 32'h0;
                end else begin
                    bid_sizes_operation_done <= (bid_sizes_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (bid_sizes_enable && bid_sizes_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, bid_sizes_addr} < bid_sizes_actual_size) begin
                        bid_sizes_mem[bid_sizes_addr] <= bid_sizes_data_in;
                        bid_sizes_write_count <= bid_sizes_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    bid_sizes_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    bid_sizes_state <= 1'b0; // Return to IDLE
                    bid_sizes_operation_done <= 1'b1;
                end
            end
            default: bid_sizes_state <= 1'b0;
        endcase
    end
end

// Array input interface for ask_prices - Industry-grade continuous write FSM
assign ask_prices_ready = (ask_prices_state == 1'b0) || (ask_prices_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        ask_prices_state <= 1'b0;  // IDLE
        ask_prices_operation_done <= 1'b0;
        ask_prices_actual_size <= 1024;
        ask_prices_write_count <= 32'h0;
    end else begin
        case (ask_prices_state)
            1'b0: begin // IDLE
                if (ask_prices_enable && ask_prices_write_enable) begin
                    ask_prices_state <= 1'b1; // ACTIVE_WRITE
                    ask_prices_actual_size <= ask_prices_size;
                    ask_prices_operation_done <= 1'b0;
                    ask_prices_write_count <= 32'h0;
                end else begin
                    ask_prices_operation_done <= (ask_prices_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (ask_prices_enable && ask_prices_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, ask_prices_addr} < ask_prices_actual_size) begin
                        ask_prices_mem[ask_prices_addr] <= ask_prices_data_in;
                        ask_prices_write_count <= ask_prices_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    ask_prices_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    ask_prices_state <= 1'b0; // Return to IDLE
                    ask_prices_operation_done <= 1'b1;
                end
            end
            default: ask_prices_state <= 1'b0;
        endcase
    end
end

// Array input interface for ask_sizes - Industry-grade continuous write FSM
assign ask_sizes_ready = (ask_sizes_state == 1'b0) || (ask_sizes_state == 1'b1);
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        ask_sizes_state <= 1'b0;  // IDLE
        ask_sizes_operation_done <= 1'b0;
        ask_sizes_actual_size <= 1024;
        ask_sizes_write_count <= 32'h0;
    end else begin
        case (ask_sizes_state)
            1'b0: begin // IDLE
                if (ask_sizes_enable && ask_sizes_write_enable) begin
                    ask_sizes_state <= 1'b1; // ACTIVE_WRITE
                    ask_sizes_actual_size <= ask_sizes_size;
                    ask_sizes_operation_done <= 1'b0;
                    ask_sizes_write_count <= 32'h0;
                end else begin
                    ask_sizes_operation_done <= (ask_sizes_write_count > 0) ? 1'b1 : 1'b0;
                end
            end
            1'b1: begin // ACTIVE_WRITE - continuous writing
                if (ask_sizes_enable && ask_sizes_write_enable) begin
                    // Continue writing while enable is high
                    if ({22'b0, ask_sizes_addr} < ask_sizes_actual_size) begin
                        ask_sizes_mem[ask_sizes_addr] <= ask_sizes_data_in;
                        ask_sizes_write_count <= ask_sizes_write_count + 1'b1;
                    end
                    // Stay in ACTIVE_WRITE for continuous operation
                    ask_sizes_state <= 1'b1;
                end else begin
                    // Enable went low - finish write operation
                    ask_sizes_state <= 1'b0; // Return to IDLE
                    ask_sizes_operation_done <= 1'b1;
                end
            end
            default: ask_sizes_state <= 1'b0;
        endcase
    end
end


// Industry-Grade Datapath Logic
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        // Reset all local variables
        tot_bid_vol <= 0;
        tot_ask_vol <= 0;
        bid_notional <= 0;
        ask_notional <= 0;
        vwap_bid <= 0;
        vwap_ask <= 0;
        combined_vol <= 0;
        vwap_mid <= 0;
        micro_price <= 0;
        i <= 0;
        for_tmp_136 <= 0;
        tmp_load_144 <= 0;
        tmp_load_152 <= 0;
        tmp_load_160 <= 0;
        tmp_load_164 <= 0;
        tmp_mul_168 <= 0;
        tmp_load_176 <= 0;
        tmp_load_180 <= 0;
        tmp_mul_184 <= 0;
        tmp_add_220 <= 0;
        tmp_add_240 <= 0;
        tmp_load_248 <= 0;
        tmp_load_254 <= 0;
        tmp_add_258 <= 0;
        top_spread_vol <= 0;
        tmp_load_281 <= 0;
        tmp_load_287 <= 0;
        tmp_mul_291 <= 0;
        tmp_load_297 <= 0;
        tmp_load_303 <= 0;
        tmp_mul_307 <= 0;
        tmp_add_311 <= 0;
        tmp_add_317 <= 0;
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

