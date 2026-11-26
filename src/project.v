/*
 * Copyright (c) 2026 Alexander Co Abad
 * SPDX-License-Identifier: Apache-2.0
 *
 * MC14500B 1-bit microcontroller, micro-tile edition (sky130 micro tile:
 * clk, rst_n, ui_in[7:0], uo_out[7:0] only), set up for teaching.
 *
 * The full SoC (tt_um_mc14500b_soc_extended) has a 64 x 8 flip-flop program
 * RAM, an edge detector, a 12-bit clock divider and a parallel IO bus on uio.
 * None of that fits in ~3000 um2, so this version keeps the CPU core and its
 * instruction set, and replaces the rest:
 *   - program memory  : 64 x 8 ROM = four 16-word lab programs
 *   - program select  : ui_in[7:6], latched once per 16-instruction loop
 *   - scratch RAM     : 4 bits  (addresses 0-3)
 *   - inputs          : all 8 ui_in bits, registered once, readable (4-B)
 *   - output          : an 8-bit shift register (address C) published to uo_out
 *                       once per loop, so the byte is steady while the loop runs
 *   - debug view      : ui_in[4] = 1 shows PC, RR, IEN, OEN and skip on uo_out
 *   - dropped         : programming port, edge flag, clock divider, uio pins
 *
 * Differences from the full SoC (see docs/ISA.md):
 *   - IEN / OEN load the raw addressed bit (as on the real MC14500B), so a
 *     program can always re-enable them;
 *   - at the end of each loop (PC = 15) IEN and OEN are set to 1 and the skip
 *     latch is cleared, so a program (or a program switch) always starts clean.
 */

`default_nettype none

module tt_um_mc14500b_micro (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

    // ------------------------------------------------------------------
    // State
    // ------------------------------------------------------------------
    reg [7:0] in_q;      // ui_in, registered once (synchroniser + stable read)
    reg [3:0] pc;        // program counter, free-running, wraps 15 -> 0
    reg       rr;        // result register
    reg       ien;       // input enable
    reg       oen;       // output enable
    reg       skip;      // next instruction is skipped
    reg [3:0] ram;       // scratch bits, addresses 0-3
    reg [7:0] out_q;     // output shift register, address C shifts a bit in
    reg [1:0] sel;       // program select, sampled from ui_in[7:6] at loop end
    reg [7:0] shadow;    // out_q published at the start of each loop -> uo_out

    // ------------------------------------------------------------------
    // Program ROM: {program select, pc} -> instruction
    //   opcode = [7:4], operand = [3:0]   (see docs/ISA.md)
    //   The table between the markers is generated from test/model.py
    //   (python3 test/gen_rom.py --write); test.py checks it is in sync.
    // ------------------------------------------------------------------
    wire [5:0] rom_addr = {sel, pc};
    wire [7:0] instr;

`ifdef MC_ROM_FILE
    // simulation only: load any program from a hex file (test/equiv)
    reg [7:0] rom [0:63];
    initial $readmemh(`MC_ROM_FILE, rom);
    assign instr = rom[rom_addr];
`else
    reg [7:0] rom_q;
    assign instr = rom_q;
    always @* begin
        case (rom_addr)
            // BEGIN ROM
            // ---- program 0: ECHO
            6'h00: rom_q = 8'h1B;   // LD in7
            6'h01: rom_q = 8'h8C;   // STO C
            6'h02: rom_q = 8'h1A;   // LD in6
            6'h03: rom_q = 8'h8C;   // STO C
            6'h04: rom_q = 8'h19;   // LD in5
            6'h05: rom_q = 8'h8C;   // STO C
            6'h06: rom_q = 8'h18;   // LD in4
            6'h07: rom_q = 8'h8C;   // STO C
            6'h08: rom_q = 8'h17;   // LD in3
            6'h09: rom_q = 8'h8C;   // STO C
            6'h0A: rom_q = 8'h16;   // LD in2
            6'h0B: rom_q = 8'h8C;   // STO C
            6'h0C: rom_q = 8'h15;   // LD in1
            6'h0D: rom_q = 8'h8C;   // STO C
            6'h0E: rom_q = 8'h14;   // LD in0
            6'h0F: rom_q = 8'h8C;   // STO C
            // ---- program 1: GATES
            6'h10: rom_q = 8'h14;   // LD in0
            6'h11: rom_q = 8'h35;   // AND in1
            6'h12: rom_q = 8'h8C;   // STO C
            6'h13: rom_q = 8'h9C;   // STOC C
            6'h14: rom_q = 8'h14;   // LD in0
            6'h15: rom_q = 8'h55;   // OR in1
            6'h16: rom_q = 8'h8C;   // STO C
            6'h17: rom_q = 8'h9C;   // STOC C
            6'h18: rom_q = 8'h14;   // LD in0
            6'h19: rom_q = 8'h75;   // XNOR in1
            6'h1A: rom_q = 8'h9C;   // STOC C
            6'h1B: rom_q = 8'h8C;   // STO C
            6'h1C: rom_q = 8'h14;   // LD in0
            6'h1D: rom_q = 8'h45;   // ANDC in1
            6'h1E: rom_q = 8'h8C;   // STO C
            6'h1F: rom_q = 8'h9C;   // STOC C
            // ---- program 2: IEN/OEN
            6'h20: rom_q = 8'h14;   // LD in0
            6'h21: rom_q = 8'hB6;   // OEN in2
            6'h22: rom_q = 8'h81;   // STO ram1
            6'h23: rom_q = 8'hBB;   // OEN in7
            6'h24: rom_q = 8'h11;   // LD ram1
            6'h25: rom_q = 8'h8C;   // STO C
            6'h26: rom_q = 8'h8C;   // STO C
            6'h27: rom_q = 8'h8C;   // STO C
            6'h28: rom_q = 8'h8C;   // STO C
            6'h29: rom_q = 8'hA5;   // IEN in1
            6'h2A: rom_q = 8'h14;   // LD in0
            6'h2B: rom_q = 8'h8C;   // STO C
            6'h2C: rom_q = 8'h8C;   // STO C
            6'h2D: rom_q = 8'h8C;   // STO C
            6'h2E: rom_q = 8'h8C;   // STO C
            6'h2F: rom_q = 8'h00;   // NOP0
            // ---- program 3: SKIP MUX
            6'h30: rom_q = 8'h16;   // LD in2
            6'h31: rom_q = 8'hD0;   // RTN
            6'h32: rom_q = 8'h14;   // LD in0
            6'h33: rom_q = 8'h80;   // STO ram0
            6'h34: rom_q = 8'h26;   // LDC in2
            6'h35: rom_q = 8'hD0;   // RTN
            6'h36: rom_q = 8'h15;   // LD in1
            6'h37: rom_q = 8'h50;   // OR ram0
            6'h38: rom_q = 8'h8C;   // STO C
            6'h39: rom_q = 8'h8C;   // STO C
            6'h3A: rom_q = 8'h8C;   // STO C
            6'h3B: rom_q = 8'h8C;   // STO C
            6'h3C: rom_q = 8'h9C;   // STOC C
            6'h3D: rom_q = 8'h9C;   // STOC C
            6'h3E: rom_q = 8'h9C;   // STOC C
            6'h3F: rom_q = 8'h9C;   // STOC C
            // END ROM
            default: rom_q = 8'h00;
        endcase
    end
`endif

    wire [3:0] opcode  = instr[7:4];
    wire [3:0] operand = instr[3:0];

    // ------------------------------------------------------------------
    // Read path: operand -> one bit
    //   0-3 ram[0..3]   4-B ui_in[0..7]   C output register bit 0   D-F reserved (0)
    //   LD/AND/... see the bit through IEN (data); IEN and OEN load the raw bit.
    // ------------------------------------------------------------------
    reg rd_bit;
    always @* begin
        case (operand)
            4'h0: rd_bit = ram[0];
            4'h1: rd_bit = ram[1];
            4'h2: rd_bit = ram[2];
            4'h3: rd_bit = ram[3];
            4'h4: rd_bit = in_q[0];
            4'h5: rd_bit = in_q[1];
            4'h6: rd_bit = in_q[2];
            4'h7: rd_bit = in_q[3];
            4'h8: rd_bit = in_q[4];
            4'h9: rd_bit = in_q[5];
            4'hA: rd_bit = in_q[6];
            4'hB: rd_bit = in_q[7];
            4'hC: rd_bit = out_q[0];
            default: rd_bit = 1'b0;
        endcase
    end
    wire data = rd_bit & ien;

    // ------------------------------------------------------------------
    // Write path: STO (8) writes RR, STOC (9) writes !RR
    // ------------------------------------------------------------------
    wire is_sto = (opcode == 4'h8) | (opcode == 4'h9);
    wire wr     = ~skip & oen & is_sto;
    wire wd     = (opcode == 4'h9) ? ~rr : rr;

    wire loop_start = (pc == 4'h0);
    wire loop_end   = (pc == 4'hF);

    // ------------------------------------------------------------------
    // Execute: one instruction per clock
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            in_q   <= 8'h00;
            pc     <= 4'h0;
            rr     <= 1'b0;
            ien    <= 1'b1;
            oen    <= 1'b1;
            skip   <= 1'b0;
            ram    <= 4'h0;
            out_q  <= 8'h00;
            sel    <= 2'h0;
            shadow <= 8'h00;
        end else begin
            in_q <= ui_in;
            pc   <= pc + 4'h1;

            if (skip) begin
                skip <= 1'b0;
            end else begin
                case (opcode)
                    4'h1: rr   <= data;            // LD
                    4'h2: rr   <= ~data;           // LDC
                    4'h3: rr   <= rr & data;       // AND
                    4'h4: rr   <= rr & ~data;      // ANDC
                    4'h5: rr   <= rr | data;       // OR
                    4'h6: rr   <= rr | ~data;      // ORC
                    4'h7: rr   <= ~(rr ^ data);    // XNOR
                    4'hA: ien  <= rd_bit;          // IEN (raw bit)
                    4'hB: oen  <= rd_bit;          // OEN (raw bit)
                    4'hD: skip <= ~rr;             // RTN / skip if RR = 0
                    default: ;                     // NOP0, STO, STOC, JMP, SKZ, NOPF
                endcase
            end

            if (wr) begin
                if (operand[3:2] == 2'b00) ram[operand[1:0]] <= wd;
                if (operand == 4'hC)       out_q <= {out_q[6:0], wd};
            end

            // the byte shifted in during the last loop is complete now: publish it
            if (loop_start) shadow <= out_q;

            // end of loop: clean CPU state, and pick the program for the next loop
            if (loop_end) begin
                ien  <= 1'b1;
                oen  <= 1'b1;
                skip <= 1'b0;
                sel  <= ui_in[7:6];
            end
        end
    end

    // ------------------------------------------------------------------
    // Output: the published byte, or (ui_in[4] = 1) the CPU state
    // ------------------------------------------------------------------
    assign uo_out = in_q[4] ? {pc, rr, ien, oen, skip} : shadow;

endmodule
