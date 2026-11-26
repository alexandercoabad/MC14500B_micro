# Tests

`make -B` (cocotb + iverilog): `test.py` runs each lab program (checked against expected values computed independently of the model), the program select, the debug view and reset, then compares `uo_out` on every clock against `model.py`, including 6000 random-input clocks. `model.py` also holds the lab programs in assembly; `gen_rom.py --write` turns the ones in `ACTIVE` into the ROM table in `src/project.v`, and `test_rom_source_matches_model` fails if the two drift apart. Lab tests skip programs that are not in the ROM, so swapping in a spare program is checked by the same suite.

`equiv/` holds the original `tt_um_mc14500b_soc_extended` RTL and `run_equiv.py`. The script patches the original in memory with the micro's two deliberate changes (raw IEN/OEN, clean state at the end of each loop), then runs random programs on both designs in lock-step and compares RR, IEN, OEN, skip, RAM, PC and the output register.

For the gate-level test, copy the hardened netlist to `gate_level_netlist.v` and run `make -B GATES=yes` (the `gds` workflow does this). `test.py` samples `uo_out` 8 ns after each clock edge, because the sky130 models run with `-DUNIT_DELAY=#1`: sampling at +1 ns would race the flop outputs.
