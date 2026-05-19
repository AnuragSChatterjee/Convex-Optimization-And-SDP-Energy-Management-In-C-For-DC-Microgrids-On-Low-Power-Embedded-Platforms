# Week 4: CVXPYgen Installation, Build, and Benchmarking on Raspberry Pi 5

**Dates:** Feb 23 – Mar 3, 2026

---

## Deliverables

- Install CVXPYgen and dependencies on Raspberry Pi 5
- Generate C solver code using `generate_c_code.py`
- Compile and build the C solver (`cpg_example`)
- Benchmark CVXPY vs CVXPYgen vs CSDP on Raspberry Pi 5

## Tasks Completed

- Transfer Python code files from GitLab to Raspberry Pi — **Feb 28, 2026**
- Install all prerequisites and dependencies — **Feb 28, 2026**
- Install Python packages (CVXPY, CVXPYgen) — **Feb 28, 2026**
- Run `DCPF_multi_convex.py` and record CVXPY runtime — **Feb 28, 2026**
- Compile and build C solver (`cpg_example`) — **Mar 1, 2026**
- Benchmarking and analysis — **Mar 2, 2026**

**Problem:** Many linker and library errors during `cmake .. && make -j4` due to BLAS/LAPACK symbiotic dependencies. Required complete rewrite of `CMakeLists.txt`.

---

## Step-by-Step: CVXPYgen on Raspberry Pi 5

### A. Transfer Python Files

```bash
# From laptop WSL
scp -r <Python_Code_folder> anurag@192.168.1.22:/home/anurag/sdp_energy_management_c_implementation_2/
```

### B. Install Prerequisites

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential cmake git
sudo apt install -y libblas-dev liblapack-dev libopenblas-dev gfortran

# Install Rust (required for Clarabel Rust backend)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Verify
cmake --version      # ≥ 3.10
rustc --version

pip3 install cvxpy cvxpygen scipy numpy
pip3 list | grep cvxpy    # CVXPY 1.8.1, cvxpygen 0.7.0
```

### C. Run DCPF_multi_convex.py (CVXPY baseline)

```bash
cd ~/sdp_energy_management_c_implementation_2/Python\ Code
python3 DCPF_multi_convex.py
```

**Runtime recorded:** ~1.04–1.14 s total (Python overhead + Clarabel solve).

### D. Generate C Code

```bash
python3 generate_c_code.py
```

This runs CVXPYgen on `DCPF_multi_convex.py`'s problem structure, generating a `DCPF_multi_c/c/` directory with the standalone C solver.

### E. Build the C Solver (CMakeLists.txt Fix)

**Initial build failure:** Undefined symbols for LAPACK/BLAS (`dgemm_`, `dpotrf_`, etc.) during linking. The auto-generated `CMakeLists.txt` could not locate OpenBLAS on the Pi's ARM64 Debian Trixie.

**Solution — Modified CMakeLists.txt (Mar 1, 2026):**

```cmake
# Auto-generated and Modified for Raspberry Pi (Debian Trixie)
# March 01, 2026

cmake_minimum_required(VERSION 3.10)
project(cvxpygen)

# Compiler configuration
if(NOT ${CMAKE_SYSTEM_NAME} STREQUAL "Windows")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3")
    set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} -O0 -g")
    set(CMAKE_C_STANDARD_LIBRARIES "${CMAKE_C_STANDARD_LIBRARIES} -lm")
endif()

set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(LIBRARY_OUTPUT_PATH ${PROJECT_BINARY_DIR}/out)

add_subdirectory(solver_code)

set(cpg_include
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/solver_code/include
)

set(cpg_head
    ${CMAKE_CURRENT_SOURCE_DIR}/include/cpg_workspace.h
    ${CMAKE_CURRENT_SOURCE_DIR}/include/cpg_solve.h
    ${solver_head}
)

set(cpg_src
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpg_workspace.c
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpg_solve.c
    ${solver_src}
)

include_directories(${cpg_include})

# --- Aggressive Linking Section ---
find_package(BLAS REQUIRED)
find_package(LAPACK REQUIRED)

# Order is vital: High-level Static Lib → Math Libs → System Libs
set(CPG_LIBS
    libclarabel_c_static
    ${LAPACK_LIBRARIES}
    ${BLAS_LIBRARIES}
    openblas       # Explicitly include — Pi needs this
    gfortran       # Required for Fortran symbols (dgemm_, etc.)
    m              # Math library
    pthread        # Threading
    dl             # Dynamic loader
)

add_executable(cpg_example
    ${cpg_head} ${cpg_src}
    ${CMAKE_CURRENT_SOURCE_DIR}/src/cpg_example.c
)
target_link_libraries(cpg_example PRIVATE ${CPG_LIBS})

add_library(cpg STATIC ${cpg_head} ${cpg_src})
target_link_libraries(cpg PRIVATE ${CPG_LIBS})
```

**Build commands:**
```bash
cd ~/sdp_energy_management_c_implementation_2/Python\ Code/DCPF_multi_c/c
rm -rf build && mkdir build && cd build
cmake ..
make -j4   # Initial build: 5–10 min. Subsequent builds: shorter.
```

**Successful build output:** `cpg_example` binary created in `build/`.

### F. Run the Compiled C Solver

```bash
./cpg_example
# obj = 990.7295   time = 0.0436s
```

**Expected final directory structure:**
```
DCPF_multi_c/
  c/
    build/
      cpg_example        ← standalone C solver binary
      out/
        libcpg.a
    include/
    src/
    solver_code/
    CMakeLists.txt       ← modified version above
```

---

## Benchmarking Results (Raspberry Pi 5)

| Solver | Runtime | Notes |
|--------|---------|-------|
| CVXPY / Clarabel | ~1.08–1.14 s | Includes Python parsing overhead |
| CSDP C binary | ~0.10 s | Single timestep only (27×27) |
| **CVXPYgen C binary** | **~0.043–0.055 s** | Multi-period, full SDP |
| **Speedup (CVXPY→CPG)** | **~25×** | Same problem, same solver, C vs Python |

**Clarabel problem size:**
```
variables     = 845
constraints   = 1667
nnz(P)        = 0
nnz(A)        = 2624
cones (total) = 26
  :        Zero = 1,  numel = 413
  : Nonnegative = 1,  numel = 894
  : PSDTriangle = 24, numel = (15 each)
```

**Solver convergence:** ~19–20 iterations to `Solved` status. `tol_gap_abs = 1e-7`, `tol_gap_rel = 1e-7`, `tol_feas = 1e-7`.

---

## Key Insight

`cpg_example` is a standalone C program generated by CVXPYgen that uses the generated library to solve the SDP problem directly in C, bypassing Python overhead entirely. The binary links against the Clarabel C static library (`libclarabel_c_static`) + LAPACK + BLAS.

**Memory footprint:** CVXPYgen C solver uses ~8 MB RAM vs ~45 MB for CVXPY Python. This is viable for embedded deployment.
