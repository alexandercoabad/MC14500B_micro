"""Random-program equivalence of the micro core against the original SoC.

Only the addresses both designs share are used: scratch RAM 0-3, output
latch C, and ui_in[7:5] (micro 9/A/B == original D/E/F). All 16 opcodes
(incl. IEN/OEN/skip/STOC) are exercised."""
import random, subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
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
    open('mic_prog.hex', 'w').write('\n'.join('%02x' % b for b in micro * 2) + '\n')   # 32 words
    open('ref_prog.hex', 'w').write('\n'.join('%02x' % b for b in ref * 4) + '\n')     # 64 words
    subprocess.run(['iverilog', '-g2012', '-o', 'eq.vvp', '-DMC_ROM_FILE="mic_prog.hex"',
                    'tb_equiv.v', 'ref_soc_extended.v', '../../src/project.v'], check=True)
    out = subprocess.run(['vvp', 'eq.vvp', '+seed=%d' % (t + 1)], capture_output=True, text=True).stdout
    if 'EQUIV PASS' not in out:
        bad += 1; print('program', t, 'FAILED\n', out)
print('equivalence: %d/%d random programs identical' % (N - bad, N))
sys.exit(1 if bad else 0)
