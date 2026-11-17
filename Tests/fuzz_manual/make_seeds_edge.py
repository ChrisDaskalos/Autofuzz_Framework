# tools/build_extra_seeds.py
import os, random, pathlib, struct, itertools

DIR = pathlib.Path(__file__).resolve().parent / "fuzz_corpus"
DIR.mkdir(exist_ok=True)

PASSWORD   = "1234\n"
BAD_PASS   = "letmein\n"

ANGLES = [-1, 0, 1, 164, 165, 166, 255, 2**31-1]
STEPS  = [0, 1, 45, 46, 255, 2**31-1]

def checksum(a, s):                     # reproduce firmware overflow
    return (a + s) & 0xFF               # uint8_t behaviour

def one_cmd(a, s, force_sum=None):
    cks = force_sum if force_sum is not None else checksum(a, s)
    return f"{a},{s},{cks}\n"

def one_session(cmds):
    """1234\n1\n<cmds>\n"""
    return PASSWORD + "1\n" + "".join(cmds)

def save(idx, blob):
    (DIR / f"autogen_{idx:04d}.txt").write_bytes(blob.encode())

# ------------------------------------------------------------------ #

idx = 0
# 1. Boundary-value single commands
for a, s in itertools.product(ANGLES, STEPS):
    save(idx, one_session([one_cmd(a, s)]))
    idx += 1

# 2. Wrong checksum (INT_MAX overflows in firmware)
save(idx, one_session([one_cmd(165, 45, 2**31-1)])); idx += 1

# 3. Ten-cycle menu storms (some with cancellations)
for _ in range(100):
    cmds = []
    for i in range(random.randint(6, 10)):
        if i and random.random() < 0.2:
            cmds.append("B\n")                      # cancel
        else:
            a = random.choice(ANGLES)
            s = random.choice(STEPS)
            cmds.append(one_cmd(a, s))
    save(idx, one_session(cmds)); idx += 1

# 4. Garbage before login, bad passwords, empty lines, long delimiters
garb = [
    BAD_PASS, "\n", ";;;;;\n", PASSWORD, "1\n",
    one_cmd(90, 5), "2\n", "B\n", one_cmd(0, 1)
]
save(idx, "".join(garb)); idx += 1

print(f"Wrote {idx} extra seed files into {DIR}")
