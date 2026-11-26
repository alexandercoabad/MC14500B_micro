"""Random-program equivalence of the micro core against the original SoC.

Only the addresses both designs share are used: scratch RAM 0-3, output
latch C, and ui_in[7:5] (micro 9/A/B == original D/E/F). All 16 opcodes
(incl. IEN/OEN/skip/STOC) are exercised.

The micro deliberately differs from the SoC in two places (docs/ISA.md), so the
reference RTL is patched in memory with the same two changes before the comparison:
  1. IEN / OEN load the raw addressed bit instead of the IEN-gated one;
  2. at PC[3:0] = 15, IEN and OEN are set to 1 and the skip latch is cleared.
Everything else (RR, RAM, output register, PC, every opcode) must stay identical.
The micro's program select, published output byte and debug view have no
counterpart in the SoC; the program is simply copied into all 4 ROM banks."""
import random, subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40


def patched_reference():
    s = open('ref_soc_extended.v', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    edits = [
        ("4'hA: r_ien  <= actual_data;", "4'hA: r_ien  <= core_data_in;"),
        ("4'hB: r_oen  <= actual_data;", "4'hB: r_oen  <= core_data_in;"),
        ("            // Advance to the next instruction only as fast as the (possibly",
         "            if (pc[3:0] == 4'hF) begin r_ien <= 1'b1; r_oen <= 1'b1; r_skip <= 1'b0; end" + nl +
         "            // Advance to the next instruction only as fast as the (possibly"),
    ]
    for old, new in edits:
        assert s.count(old) == 1, 'reference RTL changed, cannot patch: ' + old
        s = s.replace(old, new)
    open('ref_patched.v', 'w', newline='').write(s)


patched_reference()
bad = 0
for t in range(N):
    random.seed(t)
    micro, ref = [], []
    for _ in range(16):
        op = random.randrange(16)
        pool = [0, 1, 2, 3, 0xC, 9, 0xA, 0xB]
        m = random.choice(pool)
        r = {9: 0xD, 0xA: 0xE, 0xB: 0xF}.get(m, m)
        micro.append((op << 4) | m); ref.append((op << 4) | r)
    open('mic_prog.hex', 'w').write('\n'.join('%02x' % b for b in micro * 4) + '\n')   # 64 words
    open('ref_prog.hex', 'w').write('\n'.join('%02x' % b for b in ref * 4) + '\n')     # 64 words
    subprocess.run(['iverilog', '-g2012', '-o', 'eq.vvp', '-DMC_ROM_FILE="mic_prog.hex"',
                    'tb_equiv.v', 'ref_patched.v', '../../src/project.v'], check=True)
    out = subprocess.run(['vvp', 'eq.vvp', '+seed=%d' % (t + 1)], capture_output=True, text=True).stdout
    if 'EQUIV PASS' not in out:
        bad += 1; print('program', t, 'FAILED\n', out)
print('equivalence: %d/%d random programs identical' % (N - bad, N))
sys.exit(1 if bad else 0)
