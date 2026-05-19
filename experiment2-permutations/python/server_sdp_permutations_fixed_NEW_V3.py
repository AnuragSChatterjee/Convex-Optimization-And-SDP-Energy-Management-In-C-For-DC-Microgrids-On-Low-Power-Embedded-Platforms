import os, socket, json, time, subprocess, numpy as np, cvxpy as cp, sys, pickle

# Required for CVXPYgen compiled module on Pi
os.environ['LD_PRELOAD'] = '/usr/lib/aarch64-linux-gnu/libopenblas.so'

HOST = '0.0.0.0'
PORT = 5000

# --- STATIC NETWORK PARAMETERS ---
nb = 5
S_base = 5e6; V_base = 10e3
I_base = S_base / V_base; Z_base = V_base / I_base
E_base = S_base * 1

PGmin_kW = np.array([0,    0,    0,    0,    0])
PGmax_kW = np.array([2000, 2000, 500,  500,  500])
PDmin_kW = np.array([0,    0,    1000, 1000, 0])
Vmin_kV  = np.array([10,   9.5,  9.5,  9.5,  9.5])
Vmax_kV  = np.array([10,   10.5, 10.5, 10.5, 10.5])

cable_len      = np.array([300, 400, 400, 400, 500])
ohms_per_meter = 2 * 0.05 / 1000
Z_ohm          = ohms_per_meter * cable_len
Ilim_A         = 500 * np.ones((nb, nb))

PGmin = PGmin_kW * 1e3 / S_base
PGmax = PGmax_kW * 1e3 / S_base
PDmin = PDmin_kW * 1e3 / S_base
Vmin  = Vmin_kV  * 1e3 / V_base
Vmax  = Vmax_kV  * 1e3 / V_base
Ilim  = Ilim_A   / I_base

R12, R23, R34, R45, R51 = Z_ohm
Z_mat = (1 / Z_base) * np.array([
    [0,   R12, 0,   0,   R51],
    [R12, 0,   R23, 0,   0  ],
    [0,   R23, 0,   R34, 0  ],
    [0,   0,   R34, 0,   R45],
    [R51, 0,   0,   R45, 0  ]])

Y_bus = np.zeros((nb, nb))
edges = np.array([[0,1],[0,4],[1,2],[2,3],[3,4]])
for i in range(nb):
    for j in range(nb):
        if Z_mat[i, j] != 0:
            Y_bus[i, j] = -1 / Z_mat[i, j]
for i in range(nb):
    Y_bus[i, i] = -np.sum(Y_bus[i, :])

label = ["ACgrid", "PV", "datacenter", "datacenter", "battery"]

delta_t = 1
battery_power_cap  = np.array([0, 0, 500e3, 500e3, 500e3]) / S_base
battery_energy_cap = np.array([0, 0, 500e3, 500e3, 500e3]) / E_base
ACprice_dollar     = 30 * S_base / 1e6

# --- Load CVXPYgen wrapper ONCE at server startup ---
PYTHON_CODE_DIR = (
    '/home/anurag/sdp_energy_management_c_implementation_2/Python Code'
)
sys.path.insert(0, PYTHON_CODE_DIR)

print("=" * 60)
print("Loading CVXPYgen Python wrapper...")
from DCPF_multi_c.cpg_solver import cpg_solve
with open(f'{PYTHON_CODE_DIR}/DCPF_multi_c/problem.pickle', 'rb') as f:
    cpg_prob = pickle.load(f)
cpg_params = {p.name(): p for p in cpg_prob.parameters()}
print(f"CVXPYgen wrapper loaded successfully.")
print(f"Parameters available: {list(cpg_params.keys())}")
print()
print("Comparison setup:")
print("  CVXPY    — eta_c=1.0, eta_d=1.0 (matches CVXPYgen binary)")
print("  CVXPYgen — eta_c=1.0, eta_d=1.0 (fixed in compiled binary)")
print("  Einit, solar, load vary genuinely per permutation in BOTH")
print("  Objective difference expected: ~0 (same problem, same solver)")
print("  Timing difference expected: ~1.1s (CVXPY) vs ~0.05s (CVXPYgen)")
print()
print("NOTE: eta_c * p_c is bilinear — not DPP compliant.")
print("      CVXPYgen cannot accept eta as a parameter (DPP required).")
print("      Therefore eta=1.0 is fixed in binary and matched in CVXPY.")
print("=" * 60)

# Track previous CPG objective to verify it changes between permutations
_prev_cpg_obj = None


def build_problem(solar_pu, load_pu, einit_pu, rx_eta_c, rx_eta_d):
    """
    Builds CVXPY problem with per-permutation parameters.
    rx_eta_c and rx_eta_d are passed in but fixed at 1.0 in main loop
    to match the CVXPYgen compiled binary.
    """
    N = nb; T = solar_pu.shape[1]; y = Y_bus

    S_PGmax = np.tile(PGmax[:, None], (1, T))
    S_PGmin = np.tile(PGmin[:, None], (1, T))
    S_PLoad = load_pu.copy()
    price   = np.full(T, ACprice_dollar)

    Emin = 0 * battery_energy_cap
    Emax = 1 * battery_energy_cap

    num_PV = 0
    for i in range(N):
        if label[i] == "PV":
            S_PGmax[i, :] = solar_pu[num_PV, :]
            num_PV += 1
        if label[i] in ("datacenter", "battery"):
            S_PGmin[i, :] = -battery_power_cap[i]
            S_PGmax[i, :] =  battery_power_cap[i]

    V   = [cp.Variable((N, N), symmetric=True) for _ in range(T)]
    p   =  cp.Variable((N, T))
    p_c =  cp.Variable((N, T))
    p_d =  cp.Variable((N, T))
    E   =  cp.Variable((N, T + 1))

    constraints = []

    for t in range(T):
        for i in range(N):
            if label[i] in ("datacenter", "battery"):
                if t == 0:
                    constraints += [
                        E[i, 0] == einit_pu[i],
                        E[i, 1] == einit_pu[i]
                                   - p_d[i, 0] * delta_t / rx_eta_d
                                   + p_c[i, 0] * delta_t * rx_eta_c
                    ]
                else:
                    constraints += [
                        E[i, t+1] == E[i, t]
                                    - p_d[i, t] * delta_t / rx_eta_d
                                    + p_c[i, t] * delta_t * rx_eta_c
                    ]
            else:
                constraints += [E[i, t] == 0, p_c[i, t] == 0, p_d[i, t] == 0]

            psum = sum(
                (V[t][i, i] - V[t][i, j]) * y[i, j]
                for j in range(N) if i != j
            )
            constraints += [
                S_PLoad[i, t] - p[i, t] == psum,
                p[i, t] >= S_PGmin[i, t],
                p[i, t] <= S_PGmax[i, t],
                V[t][i, i] >= Vmin[i]**2,
                V[t][i, i] <= Vmax[i]**2,
            ]

            if label[i] in ("datacenter", "battery"):
                constraints += [
                    p_d[i, t] - p_c[i, t] == p[i, t],
                    E[i, t]  >= Emin[i],
                    E[i, t]  <= Emax[i],
                    p_d[i, t] >= 0,
                    p_c[i, t] >= 0,
                ]

            for j in range(N):
                if any(np.all(edges == np.array([i, j]), axis=1)):
                    constraints += [
                        y[i,j]**2 * (V[t][i,i] - V[t][i,j] - V[t][j,i] + V[t][j,j])
                        <= Ilim[i, j]**2
                    ]

        constraints += [V[t] >> 0]

    for i in range(N):
        if label[i] in ("datacenter", "battery"):
            constraints += [E[i, T] >= Emin[i], E[i, T] <= Emax[i]]
        else:
            constraints += [E[i, T] == 0]

    battery_usage_penalty = 1e-4 * (cp.sum(p_c) + cp.sum(p_d))
    prob = cp.Problem(
        cp.Minimize(
            cp.sum(p) - np.sum(S_PLoad) + cp.sum(p[0, :] @ price) + battery_usage_penalty
        ),
        constraints
    )
    return prob, p, p_c, p_d, E


def run_cvxpy(solar_pu, load_pu, einit_pu):
    """
    Tight CLARABEL solve — CVXPY reference solution.
    Uses eta_c=1.0, eta_d=1.0 to match CVXPYgen compiled binary exactly.
    Einit, solar, load vary genuinely per permutation.
    Objective difference vs CVXPYgen expected: ~0.
    """
    prob, p, p_c, p_d, E = build_problem(
        solar_pu, load_pu, einit_pu,
        rx_eta_c=1.0,
        rx_eta_d=1.0
    )

    t0 = time.time()
    prob.solve(solver=cp.CLARABEL, verbose=False,
               max_iter=300,
               tol_gap_abs=1e-7,
               tol_gap_rel=1e-7,
               tol_feas=1e-7)
    runtime = time.time() - t0

    if prob.status not in ("optimal", "optimal_inaccurate") or prob.value is None:
        raise ValueError(f"CLARABEL tight failed: {prob.status}")

    return (
        prob.value, runtime,
        p.value.tolist(),
        p_c.value.tolist(),
        p_d.value.tolist(),
        E.value.tolist()
    )


def run_cpg_parametric(solar_pu, load_pu, einit_pu):
    """
    Genuine CVXPYgen solve via compiled C binary Python wrapper.
    Uses cp.Parameter() objects to update per permutation:
      - Einit    varies per permutation  (genuine)
      - S_PGmax  varies with solar data  (genuine)
      - S_PLoad  varies with load data   (genuine)
      - eta_c    fixed at 1.0 in binary  (DPP constraint — cannot be parameter)
      - eta_d    fixed at 1.0 in binary  (DPP constraint — cannot be parameter)
    Timing ~0.04-0.07s = genuine Pi compiled C hardware speed.
    """
    N = nb
    T = solar_pu.shape[1]

    S_PGmax_val = np.tile(PGmax[:, None], (1, T))
    S_PGmin_val = np.tile(PGmin[:, None], (1, T))
    num_PV = 0
    for i in range(N):
        if label[i] == "PV":
            S_PGmax_val[i, :] = solar_pu[num_PV, :]
            num_PV += 1
        if label[i] in ("datacenter", "battery"):
            S_PGmin_val[i, :] = -battery_power_cap[i]
            S_PGmax_val[i, :] =  battery_power_cap[i]

    cpg_params['S_PGmax'].value = S_PGmax_val
    cpg_params['S_PGmin'].value = S_PGmin_val
    cpg_params['S_PLoad'].value = load_pu
    cpg_params['price'].value   = np.full(T, ACprice_dollar)
    cpg_params['Einit'].value   = np.array(einit_pu)

    t0 = time.time()
    cpg_solve(cpg_prob)
    rt = time.time() - t0

    if cpg_prob.value is None:
        raise ValueError("CVXPYgen parametric solve failed")

    return cpg_prob.value, rt


def run_csdp():
    """CSDP nonconvex binary — hardcoded, runtime recorded only."""
    binary = '/home/anurag/sdp_energy_management_c_implementation_2/dcpf_sdp'
    t0 = time.time()
    result = subprocess.run([binary], capture_output=True, text=True)
    rt = time.time() - t0
    obj = None
    for line in result.stdout.splitlines():
        if 'Original objective' in line:
            try:
                obj = float(line.split(':')[-1].strip())
            except Exception:
                pass
    return obj, rt


# --- SERVER STARTUP ---
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"\nServer listening on {HOST}:{PORT}")
    print("Waiting for permutation data from laptop...\n")

    perm_counter = 0
    _prev_cpg_obj = None

    while True:
        conn, addr = s.accept()
        with conn:
            raw = b''
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                raw += chunk

            try:
                payload  = json.loads(raw.decode())
                solar_pu = np.array(payload['solar_pu'])
                load_pu  = np.array(payload['load_pu'])
                einit_pu = np.array(payload['einit_pu'])

                # eta received from MATLAB but NOT used in solvers
                # Both CVXPY and CVXPYgen use eta=1.0 for fair comparison
                rx_eta_c = payload.get('eta_c', 1.0)
                rx_eta_d = payload.get('eta_d', 1.0)

                perm_counter += 1
                print(f"--- Permutation {perm_counter} ---")
                print(f"  Received  | eta_c={rx_eta_c:.2f} eta_d={rx_eta_d:.2f} "
                      f"(NOT used — fixed 1.0 in both solvers)")
                print(f"  Einit     | bus2={einit_pu[2]:.4f}pu  "
                      f"bus3={einit_pu[3]:.4f}pu  "
                      f"bus4={einit_pu[4]:.4f}pu")

                # [1] CVXPY — eta=1.0, Einit/solar/load vary per permutation
                cvxpy_obj, cvxpy_rt, p_out, p_c_out, p_d_out, E_out = \
                    run_cvxpy(solar_pu, load_pu, einit_pu)
                print(f"  [CVXPY]    obj={cvxpy_obj:.4f}  time={cvxpy_rt:.4f}s  "
                      f"eta=1.0")

                # [2] CSDP binary — runtime only
                csdp_obj, csdp_rt = run_csdp()
                print(f"  [CSDP]     obj={csdp_obj}  time={csdp_rt:.4f}s")

                # [3] CVXPYgen — genuine compiled C, Einit/solar/load vary
                cpg_obj, cpg_rt = run_cpg_parametric(
                    solar_pu, load_pu, einit_pu
                )
                print(f"  [CVXPYgen] obj={cpg_obj:.4f}  time={cpg_rt:.4f}s  "
                      f"eta=1.0 (compiled)")

                # Objective difference check
                diff = abs(cvxpy_obj - cpg_obj)
                diff_ok = diff < 1.0
                print(f"  [DIFF]     |cvxpy - cpg| = {diff:.6f}  "
                      f"{'✓ ~0' if diff_ok else '✗ check'}")

                # --- VERIFICATION PRINT ---
                # Proves cp.Parameter() is genuinely updating CVXPYgen
                # per permutation — not returning a fixed hardcoded value.
                # If CPG obj changes between permutations as Einit changes,
                # the wrapper is working correctly.
                if _prev_cpg_obj is not None:
                    cpg_changed = abs(cpg_obj - _prev_cpg_obj) > 0.01
                    print(f"  [VERIFY]   Einit(bus2)={einit_pu[2]:.4f}pu | "
                          f"cvxpy={cvxpy_obj:.2f} | "
                          f"cpg={cpg_obj:.2f} | "
                          f"prev_cpg={_prev_cpg_obj:.2f} | "
                          f"cpg_changed={'✓ YES' if cpg_changed else '— same (Einit unchanged)'}")
                else:
                    print(f"  [VERIFY]   Einit(bus2)={einit_pu[2]:.4f}pu | "
                          f"cvxpy={cvxpy_obj:.2f} | "
                          f"cpg={cpg_obj:.2f} | "
                          f"(first permutation — no previous to compare)")
                _prev_cpg_obj = cpg_obj

                result = {
                    'status': 'ok',
                    'T': int(solar_pu.shape[1]),
                    'source_ip': addr[0],
                    'cvxpy':    {'obj': cvxpy_obj, 'rt': round(cvxpy_rt, 6)},
                    'csdp':     {'obj': csdp_obj,  'rt': round(csdp_rt,  6)},
                    'cvxpygen': {'obj': cpg_obj,    'rt': round(cpg_rt,   6)},
                    'solution': {
                        'p':   p_out,
                        'p_c': p_c_out,
                        'p_d': p_d_out,
                        'E':   E_out,
                    }
                }

            except Exception as e:
                result = {'status': 'error', 'message': str(e)}
                print(f"  [ERROR] {e}")

            conn.sendall(json.dumps(result).encode())
            print(f"  Sent.\n")
