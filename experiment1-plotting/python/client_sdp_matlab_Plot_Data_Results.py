# client_sdp_matlab.py
import socket, json, numpy as np, scipy.io

PI_HOST = '192.168.2.2'
PORT = 5000
 
# 1. Load solar data
mat_data = scipy.io.loadmat('solar_power_data.mat')
power_output_kW = mat_data['power_output_kW']
S_base = 5e6
E_base = S_base * 1
T = int(power_output_kW.shape[1])  

# 2. Build inputs - NOT FINE BECAUSE THIS WOULD BE READ AUTOMATICALLY FROM THE MAT DATA FILE 
solar_pu = (power_output_kW * 1e3 / S_base).tolist()
PDmin_kW = np.array([0, 0, 1000, 1000, 0])
load_pu = np.tile((PDmin_kW * 1e3 / S_base)[:, None], (1, T)).tolist()
battery_energy_kWh = np.array([0, 0, 500e3, 500e3, 500e3])
battery_energy_cap = battery_energy_kWh / E_base
einit_pu = (0.10 * battery_energy_cap).tolist()
 
# 3. Ethernet Communication - FINE 
payload = json.dumps({'solar_pu': solar_pu, 'load_pu': load_pu, 'einit_pu': einit_pu}).encode()
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((PI_HOST, PORT))
    s.sendall(payload)
    s.shutdown(socket.SHUT_WR)
    raw = b''
    while True:
        chunk = s.recv(65536)
        if not chunk: break
        raw += chunk

result = json.loads(raw.decode())
sol = result['solution'] 

# 4. Prepare results for MATLAB - FINE
# Note: We save these as a dictionary so MATLAB can load them directly
results_to_save = {
    'p_kW': np.array(sol['p']) * S_base / 1e3,
    'p_c_kW': np.array(sol['p_c']) * S_base / 1e3,
    'p_d_kW': np.array(sol['p_d']) * S_base / 1e3,
    'E_soc': np.array(sol['E']),
    'hours': np.arange(0, T),
    'cvxpy_obj': float(result['cvxpy']['obj']),
    'cvxpy_rt': float(result['cvxpy']['runtime_s']),
    'csdp_obj': float(result['csdp']['obj']),
    'csdp_rt': float(result['csdp']['runtime_s']),
    'cpg_obj': float(result['cvxpygen']['obj']),
    'cpg_rt': float(result['cvxpygen']['runtime_s'])
}

# 5. Save to .mat file for robust transfer to MATLAB - FINE
scipy.io.savemat('sdp_results_transfer.mat', results_to_save)
print("Data received from Pi and saved to sdp_results_transfer.mat")