import socket, json, time, subprocess, numpy as np, scipy.io, cvxpy as cp

HOST = '0.0.0.0'
PORT = 5000

# Network parameters - same as your DCPF_multi_convex.py
nb = 5
eta_c = 0.99
eta_d = 0.99
S_base = 5e6; V_base = 10e3
I_base = S_base/V_base; Z_base = V_base/I_base
E_base = S_base * 1
PGmin_kW = np.array([0,0,0,0,0])
PGmax_kW = np.array([2000,2000,500,500,500])
PDmin_kW = np.array([0,0,1000,1000,0])
Vmin_kV  = np.array([10,9.5,9.5,9.5,9.5])
Vmax_kV  = np.array([10,10.5,10.5,10.5,10.5])
cable_len = np.array([300,400,400,400,500])
ohms_per_meter = 2*0.05/1000
Z_ohm = ohms_per_meter * cable_len
Ilim_A = 500 * np.ones((nb,nb))
PGmin = PGmin_kW*1e3/S_base
PGmax = PGmax_kW*1e3/S_base
PDmin = PDmin_kW*1e3/S_base
Vmin  = Vmin_kV*1e3/V_base
Vmax  = Vmax_kV*1e3/V_base
Ilim  = Ilim_A/I_base
R12,R23,R34,R45,R51 = Z_ohm
Z_mat = (1/Z_base)*np.array([
    [0,R12,0,0,R51],[R12,0,R23,0,0],
    [0,R23,0,R34,0],[0,0,R34,0,R45],[R51,0,0,R45,0]])
Y_bus = np.zeros((nb,nb))
edges = np.array([[0,1],[0,4],[1,2],[2,3],[3,4]])
for i in range(nb):
    for j in range(nb):
        if Z_mat[i,j] != 0: Y_bus[i,j] = -1/Z_mat[i,j]
for i in range(nb): Y_bus[i,i] = -np.sum(Y_bus[i,:])
label = ["ACgrid","PV","datacenter","datacenter","battery"]
delta_t = 1
battery_power_cap  = np.array([0,0,500e3,500e3,500e3])/S_base
battery_energy_cap = np.array([0,0,500e3,500e3,500e3])/E_base
ACprice_dollar = 30*S_base/1e6

def run_cvxpy(solar_pu, load_pu, einit_pu):
    N=nb; T=solar_pu.shape[1]; y=Y_bus
    S_PGmax = np.tile(PGmax[:,None],(1,T))
    S_PGmin = np.tile(PGmin[:,None],(1,T))
    S_PLoad = load_pu.copy()
    price   = np.full(T, ACprice_dollar)
    Emin=0*battery_energy_cap
    Emax=1*battery_energy_cap
    num_PV=0
    for i in range(N):
        if label[i]=="PV":
            S_PGmax[i,:]=solar_pu[num_PV,:]; num_PV+=1
        if label[i] in ("datacenter","battery"):
            S_PGmin[i,:]=-battery_power_cap[i]
            S_PGmax[i,:]=battery_power_cap[i]
    V=[cp.Variable((N,N),symmetric=True) for _ in range(T)]
    p=cp.Variable((N,T)); p_c=cp.Variable((N,T))
    p_d=cp.Variable((N,T)); E=cp.Variable((N,T+1))
    constraints=[]
    for t in range(T):
        for i in range(N):
            if label[i] in ("datacenter","battery"):
                if t==0:
                    constraints+=[E[i,0]==einit_pu[i],
                        E[i,1]==einit_pu[i]-p_d[i,0]*delta_t / eta_d + p_c[i,0]*delta_t * eta_c]
                else:
                    constraints+=[E[i,t+1]==E[i,t]-p_d[i,t]*delta_t / eta_d + p_c[i,t]*delta_t * eta_c]
            else:
                constraints+=[E[i,t]==0,p_c[i,t]==0,p_d[i,t]==0]
            psum=sum((V[t][i,i]-V[t][i,j])*y[i,j] for j in range(N) if i!=j)
            constraints+=[S_PLoad[i,t]-p[i,t]==psum,
                p[i,t]>=S_PGmin[i,t],p[i,t]<=S_PGmax[i,t],
                V[t][i,i]>=Vmin[i]**2,V[t][i,i]<=Vmax[i]**2]
            if label[i] in ("datacenter","battery"):
                constraints+=[p_d[i,t]-p_c[i,t]==p[i,t],
                    E[i,t]>=Emin[i],E[i,t]<=Emax[i],
                    p_d[i,t]>=0,p_c[i,t]>=0]
            for j in range(N):
                if any(np.all(edges==np.array([i,j]),axis=1)):
                    constraints+=[y[i,j]**2*(V[t][i,i]-V[t][i,j]-V[t][j,i]+V[t][j,j])<=Ilim[i,j]**2]
        constraints+=[V[t]>>0]
    for i in range(N):
        if label[i] in ("datacenter","battery"):
            constraints+=[E[i,T]>=Emin[i],E[i,T]<=Emax[i]]
        else: constraints+=[E[i,T]==0]

    # MODIFIED: Added Complementarity Penalty to ensure p_c and p_d don't occur together
    battery_usage_penalty = 1e-4 * (cp.sum(p_c) + cp.sum(p_d))

    prob=cp.Problem(cp.Minimize(
        cp.sum(p)-np.sum(S_PLoad)+cp.sum(p[0,:]@price) + battery_usage_penalty),constraints)
    t0=time.time()
    prob.solve(solver=cp.CLARABEL,verbose=False)
    runtime = time.time()-t0

    # DEBUG - add this temporarily
    print(f"  DEBUG p_c Bus 2 hour 0: {p_c.value[2,0]:.6f} p.u.")
    print(f"  DEBUG p_c Bus 2 max:    {np.max(p_c.value):.6f} p.u.")
    print(f"  DEBUG battery_power_cap: {battery_power_cap}")

    # Extract solution arrays - same variables as DCPF_multi_convex.py
    p_out   = p.value.tolist()    # power generation per bus per timestep
    p_c_out = p_c.value.tolist()  # charging power per bus per timestep
    p_d_out = p_d.value.tolist()  # discharging power per bus per timestep
    E_out   = E.value.tolist()    # battery SOC per bus per timestep

    return prob.value, runtime, p_out, p_c_out, p_d_out, E_out

def run_csdp():
    binary = '/home/anurag/sdp_energy_management_c_implementation_2/dcpf_sdp'
    t0=time.time()
    result=subprocess.run([binary],capture_output=True,text=True)
    rt=time.time()-t0
    obj=None
    for line in result.stdout.splitlines():
        if 'Original objective' in line:
            try: obj=float(line.split(':')[-1].strip())
            except: pass
    return obj, rt

def run_cpg():
    binary = ('/home/anurag/sdp_energy_management_c_implementation_2'
              '/Python Code/DCPF_multi_c/c/build/cpg_example')
    t0=time.time()
    result=subprocess.run([binary],capture_output=True,text=True)
    rt=time.time()-t0
    obj=None
    for line in result.stdout.splitlines():
        if line.strip().startswith('obj ='):
            try: obj=float(line.split('=')[1].strip())
            except: pass
    return obj, rt

# Socket server - IPv4 over Ethernet
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen()
    print(f"SDP server listening on {HOST}:{PORT}...")
    print("Waiting for data from laptop over Ethernet (192.168.2.x)...")

    while True:
        conn, addr = s.accept()
        with conn:
            print(f"\nConnection from {addr}")
            raw = b''
            while True:
                chunk = conn.recv(65536)
                if not chunk: break
                raw += chunk
            try:
                payload  = json.loads(raw.decode())
                solar_pu = np.array(payload['solar_pu'])
                load_pu  = np.array(payload['load_pu'])
                einit_pu = np.array(payload['einit_pu'])
                T = solar_pu.shape[1]
                print(f"  Received T={T} timesteps of solar/load data")

                print("  [1/3] Running CVXPY...")
                cvxpy_obj, cvxpy_rt, p_out, p_c_out, p_d_out, E_out = run_cvxpy(solar_pu, load_pu, einit_pu)
                print(f"        obj={cvxpy_obj:.4f}, time={cvxpy_rt:.4f}s")

                print("  [2/3] Running CSDP...")
                csdp_obj, csdp_rt = run_csdp()
                print(f"        obj={csdp_obj}, time={csdp_rt:.4f}s")

                print("  [3/3] Running CVXPYgen...")
                cpg_obj, cpg_rt = run_cpg()
                print(f"        obj={cpg_obj:.4f}, time={cpg_rt:.4f}s")

                result = {
                    'status': 'ok',
                    'T': T,
                    'source_ip': addr[0],
                    'cvxpy':    {'obj': cvxpy_obj, 'runtime_s': round(cvxpy_rt,4)},
                    'csdp':     {'obj': csdp_obj,  'runtime_s': round(csdp_rt,4)},
                    'cvxpygen': {'obj': cpg_obj,   'runtime_s': round(cpg_rt,4)},

                    # Solution arrays from CVXPY (same as DCPF_multi_convex.py outputs)
                    'solution': {
                        'p':   p_out,    # (5, 24) power generation
                        'p_c': p_c_out,  # (5, 24) charging power
                        'p_d': p_d_out,  # (5, 24) discharging power
                        'E':   E_out,    # (5, 25) battery SOC
                         }
                }
            except Exception as e:
                result = {'status': 'error', 'message': str(e)}
                print(f"  Error: {e}")

            conn.sendall(json.dumps(result).encode())
            print(f"  Results sent back to {addr[0]}")
