/*
 * Copyright (c) 2026 Alexander Co Abad
 * SPDX-License-Identifier: Apache-2.0
 *
 * MC14500B 1-bit microcontroller, micro-tile edition (sky130 micro tile:
 * clk, rst_n, ui_in[7:0], uo_out[7:0] only).
 *
 * The full SoC (tt_um_mc14500b_soc_extended) has a 64 x 8 flip-flop program
 * RAM, an edge detector, a 12-bit clock divider and a parallel IO bus on uio.
 * None of that fits in ~3000 um2, so this version keeps the CPU core and its
 * instruction set exactly as they are, and replaces the rest:
 *   - program memory  : 32 x 8 ROM (two 16-word programs, chosen by ui_in[7])
 *   - scratch RAM     : 4 bits  (addresses 0-3)
 *   - inputs          : all 8 ui_in bits, registered once, readable (4-B)
 *   - outputs         : the 8-bit shift-in output latch on uo_out (address C)
 *   - dropped         : programming port, edge flag, clock divider, uio pins
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
    reg [7:0] out_q;     // output latch, address C shifts a bit in

    // ------------------------------------------------------------------
    // Program ROM: {program select = in_q[7], pc} -> instruction
    //   opcode = [7:4], operand = [3:0]   (see docs/ISA.md)
    // ------------------------------------------------------------------
    wire [4:0] rom_addr = {in_q[7], pc};
    wire [7:0] instr;

`ifdef MC_ROM_FILE
    // simulation only: load any program from a hex file (test/equiv)
    reg [7:0] rom [0:31];
    initial $readmemh(`MC_ROM_FILE, rom);
    assign instr = rom[rom_addr];
`else
    reg [7:0] rom_q;
    assign instr = rom_q;
    always @* begin
        case (rom_addr)
            // Program 0 (ui_in[7] = 0): ECHO. Shift in7..in0 into the output
            // latch, so uo_out follows ui_in (bit 7 reads 0 here).
            5'h00: rom_q = 8'h1B;  5'h01: rom_q = 8'h8C;   // LD  in7 ; STO C
            5'h02: rom_q = 8'h1A;  5'h03: rom_q = 8'h8C;   // LD  in6 ; STO C
            5'h04: rom_q = 8'h19;  5'h05: rom_q = 8'h8C;   // LD  in5 ; STO C
            5'h06: rom_q = 8'h18;  5'h07: rom_q = 8'h8C;   // LD  in4 ; STO C
            5'h08: rom_q = 8'h17;  5'h09: rom_q = 8'h8C;   // LD  in3 ; STO C
            5'h0A: rom_q = 8'h16;  5'h0B: rom_q = 8'h8C;   // LD  in2 ; STO C
            5'h0C: rom_q = 8'h15;  5'h0D: rom_q = 8'h8C;   // LD  in1 ; STO C
            5'h0E: rom_q = 8'h14;  5'h0F: rom_q = 8'h8C;   // LD  in0 ; STO C
            // Program 1 (ui_in[7] = 1): LOGIC CHAIN. RR runs through
            //   in0, &in1, |in2, xnor in3, &~in4, |~in5, xnor in6, xnor in7
            // and every intermediate RR is shifted into the output latch.
            5'h10: rom_q = 8'h14;  5'h11: rom_q = 8'h8C;   // LD    in0 ; STO  C
            5'h12: rom_q = 8'h35;  5'h13: rom_q = 8'h8C;   // AND   in1 ; STO  C
            5'h14: rom_q = 8'h56;  5'h15: rom_q = 8'h8C;   // OR    in2 ; STO  C
            5'h16: rom_q = 8'h77;  5'h17: rom_q = 8'h8C;   // XNOR  in3 ; STO  C
            5'h18: rom_q = 8'h48;  5'h19: rom_q = 8'h8C;   // ANDC  in4 ; STO  C
            5'h1A: rom_q = 8'h69;  5'h1B: rom_q = 8'h8C;   // ORC   in5 ; STO  C
            5'h1C: rom_q = 8'h7A;  5'h1D: rom_q = 8'h8C;   // XNOR  in6 ; STO  C
            5'h1E: rom_q = 8'h7B;  5'h1F: rom_q = 8'h9C;   // XNOR  in7 ; STOC C
            default: rom_q = 8'h00;
        endcase
    end
`endif

    wire [3:0] opcode  = instr[7:4];
    wire [3:0] operand = instr[3:0];

    // ------------------------------------------------------------------
    // Read path: operand -> one bit, gated by IEN
    //   0-3 ram[0..3]   4-B ui_in[0..7]   C output latch bit 0   D-F reserved (0)
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

    // ------------------------------------------------------------------
    // Execute: one instruction per clock
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            in_q  <= 8'h00;
            pc    <= 4'h0;
            rr    <= 1'b0;
            ien   <= 1'b1;
            oen   <= 1'b1;
            skip  <= 1'b0;
            ram   <= 4'h0;
            out_q <= 8'h00;
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
                    4'hA: ien  <= data;            // IEN
                    4'hB: oen  <= data;            // OEN
                    4'hD: skip <= ~rr;             // RTN / skip if RR = 0
                    default: ;                     // NOP0, STO, STOC, JMP, SKZ, NOPF
                endcase
            end

            if (wr) begin
                if (operand[3:2] == 2'b00) ram[operand[1:0]] <= wd;
                if (operand == 4'hC)       out_q <= {out_q[6:0], wd};
            end
        end
    end

    assign uo_out = out_q;

endmodule
