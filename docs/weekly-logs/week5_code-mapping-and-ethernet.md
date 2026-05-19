# Week 5: C Source Code Mapping & Ethernet Interface Implementation

**Dates:** Mar 3 – Mar 14, 2026

---

## Deliverables

- Map generated C source code to battery SOC, demand, and solar profiles
- Connect Raspberry Pi via Ethernet and automate data collection

## Tasks Completed

- Read and documented CVXPY (`DCPF_multi_convex.py`), CVXPYgen (`generate_c_code.py`), and C solver (`cpg_example.c`) code — **Mar 11, 2026**
- Ethernet TCP/IP interface implemented (Experiment 1 pipeline)

---

## CVXPYgen Code Mapping: Battery SOC, Demand, and Solar Profile

### Code Translation Pipeline

```
DCPF_multi_convex.py     →    generate_c_code.py      →    C Solver (cpg_example.c)
(Pure CVXPY)                  (CVXPY + CVXPYgen)            (Fast embedded solver)
Hard-coded data               cp.Parameter() for inputs      ~47× speedup
Direct solve                  cpg.generate_code()
```

**Key difference:** `generate_c_code.py` uses identical optimization logic but wraps changeable data in `cp.Parameter()` to enable C code generation.

---

### Data Structure Mapping (N=5 buses, T=24 timesteps)

#### Parameters (Input: Python → C)

| Quantity | Python shape | C array size | Index formula | C function |
|---------|-------------|-------------|--------------|-----------|
| Solar profile `S_PGmax` | (5, 24) | 120 | `bus * 24 + time` | `cpg_update_S_PGmax(idx, val)` |
| Load demand `S_PLoad` | (5, 24) | 120 | `bus * 24 + time` | `cpg_update_S_PLoad(idx, val)` |
| Min generation `S_PGmin` | (5, 24) | 120 | `bus * 24 + time` | `cpg_update_S_PGmin(idx, val)` |
| Electricity price | (24,) | 24 | `time` | `cpg_update_price(time, val)` |
| Initial SOC `Einit` | (5,) | 5 | `bus` | `cpg_update_Einit(bus, val)` |

#### Variables (Output: C → Python)

| Quantity | Python shape | C array size | Index formula |
|---------|-------------|-------------|--------------|
| Power generation `p` | (5, 24) | 120 | `bus * 24 + time` |
| Battery SOC `E` | (5, 25) | 125 | `bus * 25 + time` (t=0 to t=24) |
| Charging power `p_c` | (5, 24) | 120 | `bus * 24 + time` |
| Discharging power `p_d` | (5, 24) | 120 | `bus * 24 + time` |
| Voltage matrices `V[t]` | 24×(5,5) | 24×25 | `bus * 5 + bus` (diagonal for V²) |

### Worked Examples

```python
# Example 1: Solar profile for Bus 1 (PV) at 10 AM
Python: S_PGmax_param[1, 10] = 0.35
C:      cpg_update_S_PGmax(1*24 + 10, 0.35)   # index = 34

# Example 2: Load demand for Bus 2 (datacenter) at 5 PM
Python: S_PLoad_param[2, 17] = 0.20
C:      cpg_update_S_PLoad(2*24 + 17, 0.20)   # index = 65

# Example 3: Battery SOC for Bus 3 at 3 PM (hour 15)
Python: soc = E.value[3, 15]
C:      soc = CPG_Result.prim->E[3*25 + 15]   # index = 90

# Example 4: Charging power for Bus 4 (battery) at noon
Python: charge = p_c.value[4, 12]
C:      charge = CPG_Result.prim->p_c[4*24 + 12]  # index = 108
```

---

## Ethernet Real-Time Interface (Experiment 1 Pipeline)

### Network Setup

Direct Ethernet connection (no router needed):
```
Laptop IP:       192.168.2.1   (MATLAB client)
Raspberry Pi IP: 192.168.2.2   (Python server)
Port:            5000 (TCP)
```

If DHCP fails (no router), configure static IPs:
```bash
# On Pi — edit /etc/dhcpcd.conf
interface eth0
static ip_address=192.168.2.2/24
static routers=192.168.2.1
```

Alternatively, use IPv6 link-local (`fe80::...%eth0`) which requires zero configuration.

### Server Startup

```bash
# On Raspberry Pi
cd ~/sdp_energy_management_c_implementation_2/Python\ Code
python3 server_sdp.py
# SDP server listening on 0.0.0.0:5000...
# Waiting for data from laptop over Ethernet (192.168.2.x)...
```

### MATLAB Client Flow

```matlab
% plot_sdp_results.m — runs on laptop
pyrunfile('client_sdp_matlab_Plot_Data_Results.py');
% Loads solar_power_data.mat → builds JSON → sends to Pi (TCP port 5000)
% Pi runs CVXPY → CSDP → CVXPYgen → returns JSON
% MATLAB loads sdp_results_transfer.mat → plots 7 figures
```

### JSON Payload Structure

**Client → Pi:**
```json
{
  "solar_pu": [[...], [...], [...], [...], [...]], // (5, 24)
  "load_pu":  [[...], [...], [...], [...], [...]], // (5, 24)
  "einit_pu": [0.0, 0.0, 0.01, 0.01, 0.01]        // (5,) initial SOC in p.u.
}
```

**Pi → Client:**
```json
{
  "status": "ok",
  "cvxpy":    {"obj": 990.72, "runtime_s": 1.084},
  "csdp":     {"obj": -2733.4, "runtime_s": 0.099},
  "cvxpygen": {"obj": 990.73, "runtime_s": 0.043},
  "solution": {
    "p":   [...],  // (5, 24)
    "p_c": [...],  // (5, 24)
    "p_d": [...],  // (5, 24)
    "E":   [...]   // (5, 25)
  }
}
```

### Server Sequential Solver Pipeline

```python
# server_sdp.py — three solvers run in order

print("  [1/3] Running CVXPY...")
cvxpy_obj, cvxpy_rt, p_out, p_c_out, p_d_out, E_out = run_cvxpy(solar_pu, load_pu, einit_pu)

print("  [2/3] Running CSDP...")
csdp_obj, csdp_rt = run_csdp()   # hardcoded binary, timing reference only

print("  [3/3] Running CVXPYgen...")
cpg_obj, cpg_rt = run_cpg()      # standalone C binary via subprocess
```

Note: CSDP binary (`dcpf_sdp`) is hardcoded (single timestep, fixed parameters). Its objective (`-2733.4`) is from the non-convex formulation with different cost structure — it is used as a timing reference only, not for comparison.
