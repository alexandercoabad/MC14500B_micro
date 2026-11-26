# Lab handout: a 1-bit CPU on a chip

Hardware: 8 switches on `ui_in`, 8 LEDs on `uo_out`, a clock you can slow down (1 to 10 Hz is comfortable).
Reset: hold `rst_n` low for a few clocks, then release it.

## How to read the chip

- The CPU executes **one instruction per clock** and loops over 16 instructions forever (the *loop*).
- `ui_in[7:6]` chooses the program (the *slot*). It is read at the end of each loop, so a change takes effect cleanly at the next loop.
- `ui_in[4]` is the **debug switch**. Set it and the LEDs show `PC3 PC2 PC1 PC0 | RR IEN OEN skip` (`uo_out[7]` = PC3 ... `uo_out[0]` = skip).
- With the debug switch off, the LEDs show the byte the program built during the **previous** loop (`STO C` shifts bits in; the byte is published at the start of the next loop).
- Data inputs for the labs are `in0` ... `in3` (`ui_in[3:0]`). Inputs are registered once, so the CPU sees them one clock late.

Instruction format: one byte, opcode in `[7:4]`, operand in `[3:0]`. Operand `0-3` = RAM bit, `4-B` = input `in0-in7`, `C` = output register.
`d` below means "the addressed bit AND IEN".

| Op | Name | Effect | Op | Name | Effect |
| :-: | :-- | :-- | :-: | :-- | :-- |
| 1 | LD | RR = d | 8 | STO | write RR |
| 2 | LDC | RR = ~d | 9 | STOC | write ~RR |
| 3 | AND | RR = RR & d | A | IEN | IEN = raw bit |
| 4 | ANDC | RR = RR & ~d | B | OEN | OEN = raw bit |
| 5 | OR | RR = RR \| d | D | RTN | skip next if RR = 0 |
| 6 | ORC | RR = RR \| ~d | 0 | NOP0 | nothing |
| 7 | XNOR | RR = ~(RR ^ d) | | | |

(`IEN` and `OEN` take the raw addressed bit. A write happens only when OEN = 1 and the instruction is not skipped.)

---

## Lab 0: Echo, slot 00 (`ui_in[7:6] = 00`)

```
LD in7 ; STO C      LD in6 ; STO C   ...   LD in0 ; STO C
```
Each `LD`/`STO C` pair reads one input into RR and shifts it into the output register. After eight pairs the register holds `ui_in`: a **serial-to-parallel converter**.
Bits 7:6 read as 0 (slot) and bit 4 as 0 (debug switch), so `uo_out = ui_in` with those bits clear.

1. Set `0x0A`, then `0x05`. How long until the LEDs follow the switches? (Between 16 and 32 clocks. Why?)
2. Turn on the debug switch and follow `PC`. Which PC values execute `STO C`?
3. Slow the clock to 1 Hz and flip a switch just after PC = 0. When does the LED change?

## Lab 1: Gates, slot 01 (`ui_in = 0x40 | in`)

```
LD in0 ; AND in1 ; STO C ; STOC C          -> AND, NAND
LD in0 ; OR  in1 ; STO C ; STOC C          -> OR, NOR
LD in0 ; XNOR in1 ; STOC C ; STO C         -> XOR, XNOR
LD in0 ; ANDC in1 ; STO C ; STOC C         -> A&~B, its complement
```
`STOC` stores the complement for free, so one gate gives two outputs. LEDs, bit 7 first:

| A (in0) | B (in1) | uo_out | AND NAND OR NOR XOR XNOR A&~B ~(A&~B) |
| :-: | :-: | :-: | :-- |
| 0 | 0 | `0x55` | 0 1 0 1 0 1 0 1 |
| 1 | 0 | `0x6A` | 0 1 1 0 1 0 1 0 |
| 0 | 1 | `0x69` | 0 1 1 0 1 0 0 1 |
| 1 | 1 | `0xA5` | 1 0 1 0 0 1 0 1 |

1. Verify the table on the board. Which instruction would give `~A & B`?
2. Write `NAND` as `LD`, `ANDC`, ... Hint: only the complement store is needed.
3. Why does `XOR` use `XNOR` followed by `STOC`?

## Lab 2: IEN and OEN, slot 10 (`ui_in = 0x80 | in`)

```
LD in0 ; OEN in2 ; STO ram1 ; OEN in7 ; LD ram1  ... STO C x4     (H)
IEN in1 ; LD in0 ; STO C x4                                         (G)
```
`uo_out = H H H H G G G G`.

- **OEN is a write enable.** `OEN in2` sets OEN = in2. When `in2 = 0` the `STO ram1` is blocked, so `ram1` (H) **holds** its old value: a one-bit **gated latch**. When `in2 = 1`, H follows `in0`. (`OEN in7` re-enables writes: in7 = 1 in this slot.)
- **IEN is an input gate.** `IEN in1` sets IEN = in1. When `in1 = 0` every following read returns 0, so `LD in0` gives 0 and G = `in0 & in1`.
- At the end of every loop the chip sets IEN = OEN = 1 again.

| in2 | in0 | H after the loop |
| :-: | :-: | :-- |
| 1 | 1 | 1 |
| 1 | 0 | 0 |
| 0 | x | unchanged |

1. Set in0 = 1, in2 = 1; then in2 = 0, in0 = 0. Which LEDs stay on?
2. The full SoC has a bug: `IEN` is loaded through IEN, so `IEN in1` with IEN = 0 can never set IEN again. Why can the real MC14500B not have this behavior? (Hint: how would a program ever re-enable input?)

## Lab 3: Skip mux, slot 11 (`ui_in = 0xC0 | in`)

```
LD in2 ; RTN ; LD in0 ; STO ram0         RR = sel; if sel = 0 skip the LD in0
LDC in2 ; RTN ; LD in1 ; OR ram0         RR = ~sel; if sel = 1 skip the LD in1
STO C x4 ; STOC C x4
```
`RTN` (opcode D) means *skip the next instruction if RR = 0*. Here it is an `if`: the guarded load only runs for one value of `in2`; the other path leaves RR = 0, so `OR ram0` merges the two halves. Result `M = in2 ? in0 : in1`, shown as `MMMM ~M~M~M~M` (`0xF0` or `0x0F`).

1. Use the debug view and find the clock at which `skip` goes to 1. Which instruction is skipped?
2. A skipped `STO` does not write. Why does that matter for the design?
3. Build the same mux without `RTN` using only `AND`, `ANDC`, `OR`.

---

## Spare programs (swap them into the ROM, see `test/model.py`)

| Name | Idea |
| :-- | :-- |
| LOGIC CHAIN | the running value of RR through eight ALU steps |
| SR LATCH | `Q = (Q \| S) & ~R` held in a RAM bit (S = in0, R = in1) |
| TOGGLE FF | a rising edge on in0 toggles Q: edge detection with a RAM bit |
| JOHNSON | a 3-bit twisted-ring counter, six states, one step per loop |

## Ladder logic

The MC14500B was made for PLC-style control: inputs are contacts, outputs are coils. A motor start/stop "seal-in" circuit is `Q = (START | Q) & ~STOP`, which is exactly the SR LATCH program.
