# Tests

`make -B` (cocotb + iverilog): `test.py` drives both ROM programs, the program select and reset, and compares `uo_out` on every clock against `model.py`.

`equiv/` holds the original `tt_um_mc14500b_soc_extended` RTL and `run_equiv.py`, which runs random programs on both designs in lock-step and compares RR, IEN, OEN, skip, RAM, PC and `uo_out`.

For the gate-level test, copy the hardened netlist to `gate_level_netlist.v` and run `make -B GATES=yes` (the `gds` workflow does this).
