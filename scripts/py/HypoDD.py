"""
Input files for ph2dt and hypoDD (HypoDD v2.1b user guide, Appendix A and B).

Use from a notebook in notebooks/:
    import sys
    sys.path.append("../scripts/py")
    import HypoDD as hdd

    hdd.ph2dt_input()                                  # defaults
    hdd.ph2dt_input(maxsep=0.5, minlnk=6)              # change any parameter

    hdd.run_ph2dt()                                    # run ph2dt in data/input_data
    hdd.create_hypodd_input()                          # write hypoDD.inp
    hdd.run_hypodd()                                   # run hypoDD in data/input_data

ph2dt runs inside data/input_data: the file names in ph2dt.inp are relative to that folder, and
its outputs (dt.ct, event.dat, event.sel, station.sel, ph2dt.log) are written there.
"""
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "data" / "input_data"
EXE_DIR = PROJECT_ROOT / "exe"                     # compiled hypoDD, ph2dt (tasks/INSTALL.md)


def ph2dt_input(station_file="station.dat", phase_file="phase.dat",
                minwght=0.0, maxdist=10.0, maxsep=1.0, maxngh=10,
                minlnk=4, minobs=4, maxobs=50, outfile=INPUT_DIR / "ph2dt.inp"):
    """
    Write the ph2dt control file (user guide A.3.1). Returns the path of the file.

    station_file : station list (STA LAT LON ELEV), relative to the folder where ph2dt runs
    phase_file   : phase file from phase_pick.create_phase_dat, same folder
    minwght      : min pick weight; picks with lower weight are not used (0 = use all)
    maxdist      : max distance (km) between the event pair and a station
    maxsep       : max separation (km) between the two events of a pair
    maxngh       : max number of neighbours per event (strong neighbours, see minlnk)
    minlnk       : min number of links (shared picks) for a neighbour to count as "strong"
    minobs       : min number of links for an event pair to be saved in dt.ct
    maxobs       : max number of links saved per pair (closest stations first)

    Defaults chosen for FORGE (Hayward-fault example values in brackets):
      maxdist 10 km  [200] : our stations are within ~11 km of the events
      maxsep  1 km   [10]  : the seismicity spans ~1-2 km; pairs closer than 1 km share
                             similar ray paths, the assumption behind double differences
      minlnk  4, minobs 4  [8, 8] : only ~13 stations and ~5-10 picks per event; 8 would drop
                             most pairs. 4 is the minimum for a 4-parameter (x, y, z, t) problem
      maxobs  50     [50]  : more than our number of P + S picks per pair, so all are kept
    """
    text = f"""* ph2dt.inp - input control file for program ph2dt
* written by scripts/py/HypoDD.py, ph2dt_input()
* Input station file:
{station_file}
* Input phase file:
{phase_file}
*MINWGHT: min. pick weight allowed [0]
*MAXDIST: max. distance in km between event pair and stations [200]
*MAXSEP: max. hypocentral separation in km [10]
*MAXNGH: max. number of neighbors per event [10]
*MINLNK: min. number of links required to define a neighbor [8]
*MINOBS: min. number of links per pair saved [8]
*MAXOBS: max. number of links per pair saved [20]
*MINWGHT MAXDIST MAXSEP MAXNGH MINLNK MINOBS MAXOBS
   {minwght:g}      {maxdist:g}     {maxsep:g}     {maxngh:d}      {minlnk:d}      {minobs:d}     {maxobs:d}
"""
    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(text)
    print(f"Wrote {outfile}")
    print(text)
    return outfile


def run_ph2dt(inp_file="ph2dt.inp", run_dir=INPUT_DIR, exe=EXE_DIR / "ph2dt"):
    """
    Run ph2dt with `inp_file` inside `run_dir` (default data/input_data) and print its output.
    Returns True if it finished without error.

    Outputs written in run_dir: dt.ct (catalog differential times), event.dat (all events),
    event.sel (events used), station.sel (stations used), ph2dt.log (statistics, outliers).
    """
    run_dir = Path(run_dir)
    if not (run_dir / inp_file).exists():
        raise FileNotFoundError(f"{run_dir / inp_file} not found: run ph2dt_input() first")
    result = subprocess.run([str(exe), inp_file], cwd=run_dir, capture_output=True, text=True,
                            errors="replace")   # hypoDD may print non-UTF-8 bytes
    print(result.stdout)
    if result.returncode != 0:
        print("ph2dt ERROR:", result.stderr)
        return False
    outputs = ["dt.ct", "event.dat", "event.sel", "station.sel", "ph2dt.log"]
    print("Outputs in", run_dir, ":", ", ".join(f for f in outputs if (run_dir / f).exists()))
    return True


# Default 1D model, depths in km below SEA LEVEL (the datum of phase.dat and station.dat).
# hypoDD hangs the model from each station: the first layer runs from the station down to the
# second layer's top. With a sea-level datum everything above sea level (basin fill, 0 to ~1.0 km
# below the wellhead, plus the top ~0.65 km of basement, wellhead at +1.65 km) is one layer, with
# the average velocity of that column (from the 3D model's profile at the seismicity centroid,
# travel-time average): Vp 3.7, Vs 2.0 km/s. Below sea level: granite basement, Vp 5.8, Vs 3.4.
VEL_TOP = [0.0, 0.01]              # km below sea level (second top just below 0: basement)
VEL_VP = [3.7, 5.8]                # km/s
VEL_RATIO = [1.83, 1.71]           # Vp/Vs

# Iteration sets (catalog-only run, Milestone 1). One tuple per set:
#  (NITER, WTCCP, WTCCS, WRCC, WDCC, WTCTP, WTCTS, WRCT, WDCT, DAMP)
ITER_CATALOG = [
    (5, -999, -999, -999, -999, 1.0, 0.5, -999, -999, 100),   # 1: all catalog data, no cutoffs
    (5, -999, -999, -999, -999, 1.0, 0.5,    6,  1.0, 100),   # 2: remove outliers > 6 std,
]                                                             #    pairs > 1 km apart


def create_hypodd_input(dtcc_file="", dtct_file="dt.ct", event_file="event.sel",
                        station_file="station.dat",
                        loc_file="hypoDD.loc", reloc_file="hypoDD.reloc", sta_file="hypoDD.sta",
                        res_file="hypoDD.res", src_file="hypoDD.src",
                        idat=2, ipha=3, dist=15.0,
                        obscc=0, obsct=4, minds=-999, maxds=-999, maxgap=-999,
                        istart=2, isolv=2, iaq=1,
                        iterations=ITER_CATALOG,
                        imod=1, top=VEL_TOP, vp=VEL_VP, ratio=VEL_RATIO,
                        cid=0, ids=None, outfile=INPUT_DIR / "hypoDD.inp"):
    """
    Write the hypoDD control file, version 2 format (user guide B.3.1). Returns its path.
    File names are relative to the folder where hypoDD runs (data/input_data).

    Input files
      dtcc_file   : cross-correlation differential times ("" = none)
      dtct_file   : catalog differential times from ph2dt
      event_file  : starting locations (event.sel from ph2dt)
      station_file: STA LAT LON ELEV(m a.s.l.)
    Output files: loc_file (starting locations), reloc_file (relocations), sta_file (station
      residuals), res_file (data residuals), src_file (take-off angles); "" = not written
    Data selection
      idat  : 1 = cross-corr only, 2 = catalog only, 3 = both
      ipha  : 1 = P, 2 = S, 3 = P and S
      dist  : max distance (km) between cluster centroid and stations
    Event clustering
      obscc, obsct : min cross-corr / catalog links per event pair to join a cluster (0 = none)
      minds, maxds : min / max distance (km) event pair - station (-999 = off)
      maxgap       : max azimuthal gap (deg) event pair - stations (-999 = off)
    Solution control
      istart : 1 = start from cluster centroid, 2 = from catalog locations
      isolv  : 1 = SVD (small problems, <= 215 events), 2 = LSQR (large problems)
      iaq    : 0 = keep air-quakes (reset depth), 1 = remove air-quakes
      iterations : list of tuples, one per set of iterations:
          (NITER, WTCCP, WTCCS, WRCC, WDCC, WTCTP, WTCTS, WRCT, WDCT, DAMP)
          NITER        number of iterations with these weights
          WTCCP, WTCCS a-priori weight of cross-corr P, S data (-999 = not used)
          WRCC, WRCT   outlier cutoff, cross-corr / catalog: < 1 = seconds, >= 1 = x std (-999 off)
          WDCC, WDCT   max event separation (km) for cross-corr / catalog pairs (-999 = off)
          WTCTP, WTCTS a-priori weight of catalog P, S data (-999 = not used)
          DAMP         LSQR damping; tune so that CND in the output is roughly 40-80
    Velocity model
      imod  : 0 = layered, constant Vp/Vs (first value of `ratio`); 1 = layered, Vp/Vs per layer
      top   : layer tops, km below the datum (sea level), first value 0
      vp    : P velocity of each layer, km/s
      ratio : Vp/Vs of each layer
    Event selection
      cid : cluster to relocate (0 = all); ids : list of event IDs to relocate (None = all)
    """
    if not (len(top) == len(vp) == len(ratio)):
        raise ValueError("top, vp and ratio must have the same length")
    fmt = lambda values: " ".join(f"{v:g}" for v in values)
    iter_lines = "\n".join(" ".join(f"{v:g}" for v in it) for it in iterations)
    if imod == 0:
        model = f"""* IMOD
0
* NLAY  RATIO
{len(top)}  {ratio[0]:g}
* TOP
{fmt(top)}
* VEL
{fmt(vp)}"""
    elif imod == 1:
        model = f"""* IMOD
1
* TOP (km below datum), end with -9
{fmt(top)} -9
* VELP (km/s), end with -9
{fmt(vp)} -9
* RAT (Vp/Vs), end with -9
{fmt(ratio)} -9"""
    else:
        raise ValueError("only imod 0 and 1 are implemented here")
    # no ID lines at all when relocating all events: an empty line would be read as event ID 0
    id_lines = "" if not ids else "\n" + "\n".join(
        " ".join(str(int(i)) for i in ids[k:k + 8]) for k in range(0, len(ids), 8))

    text = f"""hypoDD_2
* hypoDD.inp - written by scripts/py/HypoDD.py, create_hypodd_input()
*--- INPUT FILES
* cross-correlation diff. times (blank: none):
{dtcc_file}
* catalog diff. times:
{dtct_file}
* initial hypocenters:
{event_file}
* stations:
{station_file}
*--- OUTPUT FILES
* initial locations:
{loc_file}
* relocations:
{reloc_file}
* station residuals:
{sta_file}
* data residuals:
{res_file}
* take-off angles:
{src_file}
*--- DATA SELECTION
* IDAT  IPHA  DIST
  {idat}  {ipha}  {dist:g}
*--- EVENT CLUSTERING
* OBSCC  OBSCT  MINDS  MAXDS  MAXGAP
  {obscc}  {obsct}  {minds:g}  {maxds:g}  {maxgap:g}
*--- SOLUTION CONTROL
* ISTART  ISOLV  IAQ  NSET
  {istart}  {isolv}  {iaq}  {len(iterations)}
*--- DATA WEIGHTING AND RE-WEIGHTING
* NITER WTCCP WTCCS WRCC WDCC WTCTP WTCTS WRCT WDCT DAMP
{iter_lines}
*--- FORWARD MODEL
{model}
*--- CLUSTER/EVENT SELECTION
* CID
  {cid}
* ID{id_lines}
"""
    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(text)
    print(f"Wrote {outfile}")
    print(text)
    return outfile


def run_hypodd(inp_file="hypoDD.inp", run_dir=INPUT_DIR, exe=EXE_DIR / "hypoDD", show="table"):
    """
    Run hypoDD with `inp_file` inside `run_dir` (default data/input_data). Returns True if it
    finished without error.

    show : "table" = print only the summary (events, clusters) and the iteration table(s)
           "all"   = print hypoDD's complete screen output
    Outputs written in run_dir: hypoDD.loc, hypoDD.reloc (+ one hypoDD.reloc.CCC.III file per
    cluster and iteration), hypoDD.sta, hypoDD.res, hypoDD.src, hypoDD.log (full log).

    Iteration table columns: IT iteration, EV % events, CT % catalog data, RMSCT catalog RMS (ms),
    DX DY DZ DT mean change (m, ms), OS cluster centroid shift (m), AQ air-quakes,
    CND condition number (aim roughly 40-80; low = over-damped, high = under-damped).
    """
    run_dir = Path(run_dir)
    if not (run_dir / inp_file).exists():
        raise FileNotFoundError(f"{run_dir / inp_file} not found: run create_hypodd_input() first")
    result = subprocess.run([str(exe), inp_file], cwd=run_dir, capture_output=True, text=True,
                            errors="replace")   # hypoDD may print non-UTF-8 bytes
    out = result.stdout.replace("\x00", "")         # hypoDD prints NUL characters after dates
    if show == "all":
        print(out)
    else:
        keep = ("# events", "# stations", "# catalog", "# cross", "# dtimes", "Clustered",
                "Isolated", "# clusters", "Cluster ", "RELOCATION OF CLUSTER", "IT ", "%   %",
                "air quake", ">>>", "Warning", "Program hypoDD finished")
        for line in out.splitlines():
            s = line.strip()
            if any(k in line for k in keep) or (s[:1].isdigit() and len(s.split()) >= 10):
                print(line)
    if result.returncode != 0:
        print("hypoDD ERROR:", result.stderr)
        return False
    outputs = ["hypoDD.loc", "hypoDD.reloc", "hypoDD.sta", "hypoDD.res", "hypoDD.src", "hypoDD.log"]
    print("\nOutputs in", run_dir, ":", ", ".join(f for f in outputs if (run_dir / f).exists()))
    return True


RELOC_COLUMNS = ["ID", "LAT", "LON", "DEPTH", "X", "Y", "Z", "EX", "EY", "EZ",
                 "YR", "MO", "DY", "HR", "MI", "SC", "MAG",
                 "NCCP", "NCCS", "NCTP", "NCTS", "RCC", "RCT", "CID"]


def read_reloc(reloc_file=INPUT_DIR / "hypoDD.reloc", datum=0.0, wellhead_elev=1.65):
    """
    Read hypoDD.reloc (user guide B.4.2) into a DataFrame, one row per relocated event.

    Columns as in the guide (DEPTH km below the datum; X, Y, Z m relative to the cluster
    centroid; EX, EY, EZ errors in m (only meaningful with SVD); NCTP, NCTS number of catalog
    P, S data; RCT catalog residual RMS, s; CID cluster) plus:
      event_id     : catalog ID as text ("0002"), to match the catalog
      depth_well_km: depth below the wellhead, km = DEPTH + (wellhead_elev - datum), the
                     catalog's reference (datum and wellhead_elev in km a.s.l.)
    """
    import pandas as pd
    df = pd.read_csv(reloc_file, sep=r"\s+", header=None, names=RELOC_COLUMNS)
    df["event_id"] = df["ID"].map(lambda i: f"{int(i):04d}")
    df["depth_well_km"] = df["DEPTH"] + (wellhead_elev - datum)
    return df
