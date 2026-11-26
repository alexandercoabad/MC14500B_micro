// Lock-step equivalence: original tt_um_mc14500b_soc_extended (programmed
// through its prog port) vs the micro core running the same program from ROM.
// Compared every clock: output register, RR, IEN, OEN, skip, RAM[3:0], PC[3:0], random ui_in.
// The micro's output register (out_q) is compared, not its pins: uo_out is the published copy or the debug view.
// The reference is patched by run_equiv.py with the micro's two deliberate changes. Run via run_equiv.py.
`timescale 1ns/1ps
module tb_equiv;
  reg clk = 0; always #10 clk = ~clk;
  reg rst_n_ref, rst_n_mic;
  reg [7:0] ui_ref, ui_mic, uio_ref;
  wire [7:0] uo_ref, uo_mic, uio_o, uio_e;
  reg [7:0] prog [0:63];
  integer i, errs, cyc, seed;

  tt_um_mc14500b_soc_extended ref_dut (.ui_in(ui_ref), .uo_out(uo_ref), .uio_in(uio_ref),
      .uio_out(uio_o), .uio_oe(uio_e), .ena(1'b1), .clk(clk), .rst_n(rst_n_ref));
  tt_um_mc14500b_micro mic_dut (.ui_in(ui_mic), .uo_out(uo_mic), .clk(clk), .rst_n(rst_n_mic));

  initial begin
    errs = 0; seed = 1;
    if (!$value$plusargs("seed=%d", seed)) seed = 1;
    $readmemh("ref_prog.hex", prog);
    rst_n_ref = 0; rst_n_mic = 0; ui_ref = 0; ui_mic = 0; uio_ref = 0;
    repeat (3) @(posedge clk);
    rst_n_ref = 1;                       // ref leaves reset, enters prog mode
    for (i = 0; i < 64; i = i + 1) begin
      @(negedge clk); uio_ref = {2'b11, i[5:0]}; ui_ref = prog[i];
    end
    @(negedge clk); uio_ref = 8'h00; ui_ref = 0;     // run mode
    rst_n_mic = 1;                                   // same edge: both start at pc 0
    for (cyc = 0; cyc < 1200; cyc = cyc + 1) begin
      @(negedge clk);
      if ({uo_ref, ref_dut.r_rr, ref_dut.r_ien, ref_dut.r_oen, ref_dut.r_skip, ref_dut.ram_bank[3:0], ref_dut.pc[3:0]} !==
          {mic_dut.out_q, mic_dut.rr, mic_dut.ien, mic_dut.oen, mic_dut.skip, mic_dut.ram, mic_dut.pc}) begin
        errs = errs + 1;
        if (errs < 5) $display("MISMATCH cyc %0d out ref %02x micro %02x", cyc, uo_ref, mic_dut.out_q);
      end
      ui_ref = $random(seed); ui_mic = ui_ref;
    end
    if (errs == 0) $display("EQUIV PASS"); else $display("EQUIV FAIL %0d", errs);
    $finish;
  end
endmodule
