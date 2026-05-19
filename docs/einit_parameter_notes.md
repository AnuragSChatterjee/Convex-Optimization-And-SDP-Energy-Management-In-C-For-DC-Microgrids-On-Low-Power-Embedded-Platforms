# E_init Parameter Notes

*Source: `notes_on_eint.txt` from experiment documentation*

---

## E_init Conversion: MATLAB Fraction → Python p.u. Energy

In the MATLAB permutation script, `Einit_var = 0.05:0.05:0.95` represents the battery state of charge as a **fraction** (5% to 95% full).

The Python client converts this to actual per-unit energy:

```python
einit_pu = (ei * battery_energy_cap).tolist()
```

Where `battery_energy_cap[2] = 500e3 / 5e6 = 0.1 p.u.`

### Conversion Table

| MATLAB `e_val` (SoC fraction) | `einit_pu[2]` in server log |
|-------------------------------|---------------------------|
| 0.05 (5% full) | 0.0050 p.u. |
| 0.10 (10% full) | 0.0100 p.u. |
| 0.15 (15% full) | 0.0150 p.u. |
| 0.20 (20% full) | 0.0200 p.u. |
| 0.50 (50% full) | 0.0500 p.u. |
| 0.95 (95% full) | 0.0950 p.u. |

The `[VERIFY]` line in the server log always shows `einit_pu` (the converted value), not the raw MATLAB fraction.

## Server Startup Command

```bash
cd ~/sdp_energy_management_c_implementation_2/Python\ Code
LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libopenblas.so \
    python3 server_sdp_permutations_fixed_NEW_V3.py
```

The `LD_PRELOAD` is required for the CVXPYgen Python wrapper to locate OpenBLAS at runtime on the Raspberry Pi's ARM64 architecture.
