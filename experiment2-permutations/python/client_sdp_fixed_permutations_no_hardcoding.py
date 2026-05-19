import socket, json, numpy as np, scipy.io, sys

PI_IP = '192.168.2.2'
PORT  = 5000

try:
    # 1. Load ALL parameters from MATLAB workspace — no hardcoded values
    inp = scipy.io.loadmat('temp_input.mat')
    ec    = inp['current_eta_c'].item()
    ed    = inp['current_eta_d'].item()
    ei    = inp['current_Einit'].item()
    S_base = inp['S_base'].item()
    E_base = S_base * 1  # delta_t = 1

    # 2. Solar data (1 x T) — scaled to pu using S_base from MATLAB
    sol_mat   = scipy.io.loadmat('solar_power_data.mat')
    solar_raw = sol_mat['power_output_kW'].flatten() * 1e3 / S_base
    solar_pu  = solar_raw[np.newaxis, :].tolist()
    T         = len(solar_raw)

    # 3. Load (5 x T) — PDmin comes from MATLAB, no hardcoding
    PDmin    = inp['PDmin'].flatten()           # loaded from temp_input.mat
    load_pu  = np.tile(PDmin[:, None], (1, T)).tolist()

    # 4. Initial battery energy (5-element vector, pu)
    #    battery_energy_cap comes from MATLAB, no hardcoding
    battery_energy_cap = inp['battery_energy_cap'].flatten()
    einit_pu           = (ei * battery_energy_cap).tolist()

    # 5. Transmit to Raspberry Pi
    payload = json.dumps({
        'solar_pu': solar_pu,
        'load_pu':  load_pu,
        'einit_pu': einit_pu,
        'eta_c':    ec,
        'eta_d':    ed,
    }).encode()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(60)
        s.connect((PI_IP, PORT))
        s.sendall(payload)
        s.shutdown(socket.SHUT_WR)

        response = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            response += chunk

    res = json.loads(response.decode())

    # 6. Save results for MATLAB
    if res.get('status') == 'ok':
        scipy.io.savemat('sdp_results_transfer.mat', {
            'cvxpy_obj': res['cvxpy']['obj'],
            'cvxpy_rt':  res['cvxpy']['rt'],
            'csdp_obj':  res['csdp']['obj'],
            'csdp_rt':   res['csdp']['rt'],
            'cpg_obj':   res['cvxpygen']['obj'],
            'cpg_rt':    res['cvxpygen']['rt'],
            'p_c':       np.array(res['solution']['p_c']),
            'p_d':       np.array(res['solution']['p_d']),
            'failed':    0.0,
        })
    else:
        scipy.io.savemat('sdp_results_transfer.mat', {
            'cvxpy_obj': float('nan'),
            'cvxpy_rt':  0.0,
            'csdp_obj':  float('nan'),
            'csdp_rt':   0.0,
            'cpg_obj':   float('nan'),
            'cpg_rt':    0.0,
            'p_c':       np.zeros((5, 1)),
            'p_d':       np.zeros((5, 1)),
            'failed':    1.0,
        })

except Exception:
    try:
        scipy.io.savemat('sdp_results_transfer.mat', {
            'cvxpy_obj': float('nan'),
            'cvxpy_rt':  0.0,
            'csdp_obj':  float('nan'),
            'csdp_rt':   0.0,
            'cpg_obj':   float('nan'),
            'cpg_rt':    0.0,
            'p_c':       np.zeros((5, 1)),
            'p_d':       np.zeros((5, 1)),
            'failed':    1.0,
        })
    except Exception:
        pass
    sys.exit(1)