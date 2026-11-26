# MC14500B micro — instruction set and memory map

One byte per instruction: `[7:4]` opcode, `[3:0]` operand. The opcodes behave like the
full SoC (`tt_um_mc14500b_soc_extended`, `docs/ISA.md` in the MC14500B_IHP repo) with
**two deliberate differences**, listed below. The operand address map and the program memory also differ.
`test/equiv` checks it: 100 random programs, every opcode, compared clock by clock (RR, IEN, OEN,
skip, RAM, PC, output register) against the original RTL patched with those two changes.

## Differences from the full SoC

1. **IEN and OEN load the raw addressed bit.** In the full SoC `IEN <= bit & IEN`, so once IEN is 0 every
   read is 0 and IEN can never be set again (OEN too, because its bit is also read through IEN). The real
   MC14500B loads these registers straight from the data bus, and so does this chip. `LD`, `AND`, `OR`, ... still read through IEN.
2. **Every loop starts clean.** When PC = 15, IEN and OEN are set to 1 and the skip latch is cleared (the
   instruction at PC 15 still executes normally). A program can therefore never leave the CPU locked
   for the next loop, and switching programs is always safe. RR and RAM are *not* cleared.

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
| A | IEN | `IEN <= bit` (raw bit, not gated by IEN) |
| B | OEN | `OEN <= bit` (raw bit, not gated by IEN) |
| C | JMP | no-op (as in the full SoC) |
| D | RTN/SKZ | `skip <= !RR`: the next instruction has no effect |
| E | SKZ | no-op (as in the full SoC) |
| F | NOPF | none |

`d = (addressed bit) & IEN`. A write happens only if `OEN = 1` and the instruction is not skipped.
One instruction executes per clock; `PC` is 4 bits and wraps 15 → 0 (no jumps). One pass through the 16 words is a *loop*.

## Operand address map (changed)

| Address | Read | Write |
| :-: | :-- | :-- |
| 0–3 | scratch RAM bit 0–3 | stores the bit |
| 4–B | `ui_in[0]` … `ui_in[7]` (registered once, one clock old; `ui_in[4]` = debug view, `ui_in[7:6]` = slot) | ignored |
| C | bit 0 of the output shift register | shifts the bit into it (`{reg[6:0], bit}`); `uo_out` shows it once per loop |
| D–F | 0 | ignored |

## Program ROM, select and outputs (changed)

64 × 8, addressed by `{slot, PC[3:0]}`. Contents are fixed at tapeout. The slot is `ui_in[7:6]`,
**sampled once per loop** (when PC = 15), so changing the switches mid-loop never splices two programs.
After reset the first loop always runs slot 0.

| Slot (`ui_in[7:6]`) | Program | `uo_out` |
| :-: | :-- | :-- |
| 00 | ECHO | `ui_in` (bit 4 reads 0, bits 7:6 are the slot) |
| 01 | GATES | `AND NAND OR NOR XOR XNOR A&~B ~(A&~B)` of `in0`, `in1` |
| 10 | IEN/OEN | `H H H H G G G G`: `H` = latch of `in0`, enabled by `in2`; `G = in0 & in1` |
| 11 | SKIP MUX | `M M M M ~M ~M ~M ~M`, `M = in2 ? in0 : in1` |

`docs/labs.md` explains each program as a lab. Four more programs (LOGIC CHAIN, SR LATCH, TOGGLE FF,
JOHNSON) are written and tested in `test/model.py` and can be swapped into the ROM.

`STO C` shifts a bit into an 8-bit shift register. That register is **published to `uo_out` once per loop**
(when PC = 0), so the byte is steady while the loop runs. It is complete and visible one clock after the
loop that produced it ends.

**Debug view:** while `ui_in[4] = 1`, `uo_out = {PC[3:0], RR, IEN, OEN, skip}` instead (PC on `uo_out[7:4]`).
Run a slow clock and you can watch every instruction. `ui_in[4]` is registered like the other inputs
(it is also readable at address 8).

## What was removed from the full SoC, and why

| Removed | Cost in the full SoC |
| :-- | :-- |
| 64 × 8 program RAM + programming port (`uio_in`) | 512 flip-flops, by far the largest part; the micro tile has no `uio` pins anyway |
| Clock divider (address 9) | 13 flip-flops + 12-bit incrementer |
| Rising-edge detector (address 8) | 2 flip-flops |
| 4 of the 8 scratch RAM bits, 3 input-capture flops (now 8, all inputs readable) | – |
| Raw-IEN/OEN semantics and the loop-end clean-up are *changes*, not removals | see above |
| `uio` status outputs (PC, write strobe) | no pins on a micro tile |
