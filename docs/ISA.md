# MC14500B micro — instruction set and memory map

One byte per instruction: `[7:4]` opcode, `[3:0]` operand. Opcodes and their
behaviour are **identical** to the full SoC (`tt_um_mc14500b_soc_extended`,
`docs/ISA.md` in the MC14500B_IHP repo); only the operand address map and the
program memory differ. `test/equiv` proves it: 100 random programs, every opcode,
compared clock by clock (RR, IEN, OEN, skip, RAM, PC, `uo_out`) against the original RTL.

## Opcodes (unchanged)

| Hex | Name | Effect |
| :-: | :-- | :-- |
| 0 | NOP0 | none |
| 1 | LD | `RR <= d` |
| 2 | LDC | `RR <= !d` |
| 3 | AND | `RR <= RR & d` |
| 4 | ANDC | `RR <= RR & !d` |
| 5 | OR | `RR <= RR \| d` |
| 6 | ORC | `RR <= RR \| !d` |
| 7 | XNOR | `RR <= !(RR ^ d)` |
| 8 | STO | write `RR` to the operand address |
| 9 | STOC | write `!RR` to the operand address |
| A | IEN | `IEN <= d` |
| B | OEN | `OEN <= d` |
| C | JMP | no-op (as in the full SoC) |
| D | RTN/SKZ | `skip <= !RR`: the next instruction has no effect |
| E | SKZ | no-op (as in the full SoC) |
| F | NOPF | none |

`d = (addressed bit) & IEN`. A write happens only if `OEN = 1` and the instruction is not skipped.
One instruction executes per clock; `PC` is 4 bits and wraps 15 → 0 (no jumps).

## Operand address map (changed)

| Address | Read | Write |
| :-: | :-- | :-- |
| 0–3 | scratch RAM bit 0–3 | stores the bit |
| 4–B | `ui_in[0]` … `ui_in[7]` (registered once, one clock old) | ignored |
| C | `uo_out[0]` | shifts the bit into `uo_out` (`{uo_out[6:0], bit}`) |
| D–F | 0 | ignored |

## Program ROM (changed)

32 × 8, addressed by `{ui_in[7] (registered), PC[3:0]}`. Contents are fixed at tapeout.

| `ui_in[7]` | Program | Loop of 16 instructions |
| :-: | :-- | :-- |
| 0 | ECHO | `LD in7; STO C; LD in6; STO C; … LD in0; STO C` → `uo_out` shows `ui_in` (bit 7 reads 0) |
| 1 | LOGIC CHAIN | `LD in0; AND in1; OR in2; XNOR in3; ANDC in4; ORC in5; XNOR in6; XNOR in7`, each followed by `STO C` (the last by `STOC C`) → the 8 successive values of RR, first one in `uo_out[7]` |

`uo_out` is a shift register, so it ripples while a loop runs and is complete on the
clock after the last `STO C` (when `PC` wraps to 0).

## What was removed from the full SoC, and why

| Removed | Cost in the full SoC |
| :-- | :-- |
| 64 × 8 program RAM + programming port (`uio_in`) | 512 flip-flops, by far the largest part; the micro tile has no `uio` pins anyway |
| Clock divider (address 9) | 13 flip-flops + 12-bit incrementer |
| Rising-edge detector (address 8) | 2 flip-flops |
| 4 of the 8 scratch RAM bits, 3 input-capture flops (now 8, all inputs readable) | – |
| `uio` status outputs (PC, write strobe) | no pins on a micro tile |
