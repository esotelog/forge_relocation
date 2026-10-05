# Installation guide — HypoDD, GrowClust3D.jl and supporting software (Red Hat / RHEL)

Target: Red Hat Enterprise Linux 8/9 (also Rocky/Alma/CentOS Stream), x86_64.
Everything except Step 1 is installed **without root**, inside the project folder.

## Folder convention

- `./sources` — everything downloaded (source code, tarballs, Julia and its packages)
- `./exe` — the executables we actually run (compiled binaries, links, driver scripts)

```
location_project/            # project root (CLAUDE.md, INSTALL.
├── sources/
│   ├── HypoDD/             # git clone, compiled here
│   ├── GrowClust3D.jl/     # git clone (examples + driver scripts)
│   ├── julia-<version>/    # Julia tarball, extracted
│   └── julia_depot/        # Julia packages (GrowClust3D, 
└── exe/
    ├── hypoDD
    ├── ph2dt
    ├── julia -> ../sources/julia-<version>/bin/julia
    ├── run_growclust3D.jl
    └── run_growclust3D-MP.jl
```

Set this once (adjust the path to where the project lives on the server) and add it to `~/.bashrc`:
```bash
export PROJ=$HOME/source_location
export PATH="$PROJ/exe:$PATH"
export JULIA_DEPOT_PATH="$PROJ/sources/julia_depot"   # keep Julia packages inside ./sources
```
```bash
mkdir -p $PROJ/sources $PROJ/exe
```

Add `sources/` and `exe/` to `.gitignore` (they are rebuilt from this guide, not versioned).

---

## 0. Check what the server already has

```bash
cat /etc/redhat-release        # OS version
uname -m                       # should print x86_64
gfortran --version             # Fortran compiler (needed for HypoDD)
make --version
git --version
module avail 2>/dev/null       # HPC servers often provide software as "modules"
df -h $PROJ                    # free disk space
```

If `gfortran`, `make` and `git` already exist, skip to Step 2.

---

## 1. Compilers and basic tools

**Option A — you have sudo (admin rights):**
```bash
sudo dnf install -y gcc gcc-gfortran make git wget curl tar
```

**Option B — HPC server with modules (no sudo):**
```bash
module avail gcc
module load gcc                # gcc module includes gfortran
gfortran --version
```
Add the `module load` line to `~/.bashrc`.

**Option C — no sudo, no modules:** ask the server admin to install `gcc-gfortran`.

---

## 2. HypoDD (Fortran, v2.1b)

Official source: https://github.com/fwaldhauser/HypoDD (archived: https://zenodo.org/records/14872913)

```bash
cd $PROJ/sources
git clone https://github.com/fwaldhauser/HypoDD.git
cd HypoDD
ls                      # expect: src/ include/ examples/ doc/ util/
cat README*             # read the build notes first
cd src
make
```

Copy the compiled programs into `./exe`:
```bash
find $PROJ/sources/HypoDD -type f -perm -u+x \( -name "hypoDD" -o -name "ph2dt" \)
cp <path-to>/hypoDD <path-to>/ph2dt $PROJ/exe/     # use the paths printed above
which hypoDD ph2dt                                  # should point to $PROJ/exe
```

**Array size limits:** maximum events, observations and stations are fixed at compile time in
`sources/HypoDD/include/hypoDD.inc`. If a run stops with an array-dimension error, raise the
values there, run `make clean && make` in `sources/HypoDD/src/`, and copy the new binaries to `./exe` again.

**Test:** run a dataset from `sources/HypoDD/examples/` following the user guide in `doc/`.

Common build problems:
- `gfortran: command not found` → Step 1 not done or module not loaded.
- Errors about old Fortran syntax with recent gfortran → add `-std=legacy` to the Fortran
  flags (`FFLAGS`) in the Makefile.

---

## 3. Julia (needed for GrowClust3D.jl)

Download the Linux x86_64 tarball into `./sources` (check https://julialang.org/downloads/ for
the current stable version and replace `1.11.x` below):
```bash
cd $PROJ/sources
wget https://julialang-s3.julialang.org/bin/linux/x64/1.11/julia-1.11.x-linux-x86_64.tar.gz
tar -xzf julia-1.11.x-linux-x86_64.tar.gz
ln -sf $PROJ/sources/julia-1.11.x/bin/julia $PROJ/exe/julia
julia --version           # needs >= 1.6; 1.8+ recommended
```

---

## 4. GrowClust3D.jl

The Fortran GrowClust is no longer fully maintained; use the Julia version.
Source: https://github.com/dttrugman/GrowClust3D.jl

Install the package (goes into `./sources/julia_depot` because of `JULIA_DEPOT_PATH`;
press `]` to enter package mode, Backspace to leave):
```julia
julia
pkg> add https://github.com/dttrugman/GrowClust3D.jl
pkg> add DataFrames
pkg> test GrowClust3D
```

Get the examples and driver scripts:
```bash
cd $PROJ/sources
git clone https://github.com/dttrugman/GrowClust3D.jl.git
cp GrowClust3D.jl/examples/run_growclust3D.jl GrowClust3D.jl/examples/run_growclust3D-MP.jl $PROJ/exe/
```

Run the examples (from the examples folder, so relative paths in the .inp files resolve):
```bash
cd $PROJ/sources/GrowClust3D.jl/examples
julia run_growclust3D.jl example.trace1D.inp                 # 1D ray tracing example
julia -t4 run_growclust3D.jl example.nboot100.inp            # bootstrap errors, 4 threads
```
For project runs: `julia $PROJ/exe/run_growclust3D.jl <your>.inp`.

---

## 5. Python environment

Already done: an existing Python 3.13 environment with ObsPy, NumPy/SciPy, pandas, matplotlib
(and SeisBench if needed) is installed. Nothing to install here; just activate it before running
the project scripts.

---

## 6. Final check

```bash
ls -l $PROJ/exe                        # hypoDD, ph2dt, julia, run_growclust3D*.jl
which hypoDD ph2dt julia
julia -e 'using GrowClust3D; println("GrowClust3D OK")'
python -c "import obspy, pandas, scipy; print('Python OK')"   # with your Python env activated
```

When all of these work, run the HypoDD and GrowClust examples, then start the FORGE workflow
(see CLAUDE.md, Milestone 1).

---

## Notes
- On a shared server, run long jobs with `nohup`, `tmux`/`screen`, or the batch scheduler (e.g. Slurm `sbatch`), not directly in a login shell.
- Keep raw waveform data outside git (`data/`, `sources/`, `exe/` in `.gitignore`).
- Cite: Waldhauser & Ellsworth (2000) for HypoDD; Trugman & Shearer (2017) and Trugman et al. (2023, SRL) for GrowClust / GrowClust3D.jl.
