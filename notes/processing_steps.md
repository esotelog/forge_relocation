# Processing steps: phase picking and waveform cross-correlation

See also: [processing_data.md](processing_data.md) (what data we have),
[Forge_catalog.md](Forge_catalog.md) (catalog, method of Niemz et al. 2025, velocity model).

Status: ✅ done · 🔧 script exists, needs review · ⬜ to do

---

## Station selection (decision)
**Process all 18 stations** (picking, `phase.dat`, CC) and let the relocation programs select by
distance: ph2dt `MAXDIST`, hypoDD `MAXDIST`/`MINDIST`/`MAXGAP`, GrowClust `delmax`.
- `station.dat` therefore lists all 18 stations (`create_station_dat.py` without `--max-distance`).
- Raw `.mseed` files are never filtered; any subset is selected in memory.
- This lets us compare, e.g., near stations only (< 2.5 km: Niemz et al.'s 5 UU stations + CS01)
  vs. all stations without re-picking.

---

## Part A: Phase picking → `phase.dat` (input to ph2dt)

### A1. Inputs ✅
| Input | File | Made by |
|---|---|---|
| Event windows, −5 to +15 s around each origin, 18 stations | `data/raw_data/waveforms/<ID>.mseed` | `scripts/py/01_download_data.py` |
| Catalog (origin times, locations) | `data/raw_data/catalog/…csv` | same |
| Station metadata | `data/raw_data/stations/stations.xml` | same |
| Station file (sensor elevations) | `data/input_data/station.dat` | `scripts/py/create_station_dat.py` |

### A2. Read and prepare waveforms (per event) 🔧
1. `obs.read()` the event file; `st.merge(fill_value=0)` → one trace per channel.
2. `detrend("demean")`, `taper(0.05)`.
3. **Downsample to 100 Hz** (PhaseNet's rate): zero-phase low-pass at 40 Hz (4 corners, below the
   50 Hz Nyquist), then decimate (200 Hz by 2, 1000 Hz by 10). 100 Hz stations unchanged.
   Done explicitly in the script, not left to SeisBench.
4. **Zero-pad to 40 s:** PhaseNet needs 30 s windows (3001 samples at 100 Hz) and our windows are
   20 s. Without padding it returns no picks.
5. **No band-pass** (other than the anti-alias low-pass): on test events the unfiltered data gave
   more and more plausible picks than 20–45 Hz. Niemz et al. used 20–50 Hz, so worth revisiting.

### A3. Run PhaseNet 🔧
- Model: `PhaseNet.from_pretrained("ethz")`, the same pretrained model as Niemz et al.
- `model.classify(st, P_threshold=0.2, S_threshold=0.2)`: low threshold, keep everything, filter later.
- Output: **all raw picks** → `data/picks/phasenet_raw_picks.csv`
  (event_id, network, station, phase, pick_time, t_rel = pick − origin, prob).
- Script: `scripts/py/02_run_phasenet.py`. Run on all 2,900 events and 18 stations (with explicit
  downsampling): 69,496 raw picks, about 0.3 s per event on CPU (about 15 min, sequential).
- Pre-processing functions for notebooks: `scripts/py/phase_pick.py`
  (`load_catalog`, `preprocess`, `read_and_preprocess`, `iter_preprocessed`).
- Known artefact: false P picks at about −4.9 s where the zero padding meets the real data.

### A3b. PhaseNet in parallel (planned) ⬜
- **Unit of work = one event.** Each event is independent, so events can be split across workers
  (CPU processes, or nodes on a cluster).
- **Worker function** `pick_event(evid)`: `read_and_preprocess` → `model.classify` → return the
  **picks** (a small table). Don't send processed streams back to the main process: moving several
  MB per event between processes costs more than the processing.
- **Load the model once per worker**, not per event (pool `initializer`).
- **One thread per worker:** `torch.set_num_threads(1)`, otherwise workers compete for the same
  cores (PyTorch alone already uses all 12). About 8–12 workers on this 12-core machine.
- Driver: `concurrent.futures.ProcessPoolExecutor` (or `multiprocessing.Pool`), collecting the pick
  tables and writing one CSV. On a cluster: split the event list into chunks, one job per chunk.
- The generator `iter_preprocessed` stays for sequential exploration in notebooks; the generator
  itself does not run anything in parallel (its advantage is memory: one event at a time).
- Worth it mainly when the work per event grows (more events, longer data, continuous data);
  for 2,900 events the sequential run takes about 15 min.

### A4. Associate picks with the event ⬜
Raw picks include artefacts, noise and possibly other events. For each event and station, keep at
most one P and one S:
1. **Predict arrival times** from the catalog location (distance + depth) and a simple velocity
   model (e.g. basement Vp 5.8 / Vs 3.4 km/s, or the 1D profile from the 3D model).
2. **Accept** a pick only inside a window around the prediction (first pass wide, e.g. ±0.5 s P,
   ±0.8 s S).
3. If several picks fall in the window, keep the **highest probability**.
4. Optional second pass: compute each station's median residual (pick − prediction) from good
   picks, correct the predictions and tighten the windows (station corrections).
5. Checks: S after P; S−P time consistent with distance; plot picks on record sections.

### A5. Pick weights ⬜
- PhaseNet probability → weight (0–1). Options: use the probability directly, or bin it into
  classes like the NCSN codes (e.g. ≥0.8 → 1.0, ≥0.6 → 0.5, ≥0.4 → 0.2, else drop).
- Decide a minimum probability for keeping a pick (e.g. 0.3).

### A6. Write `phase.dat` ⬜
Format (hypoDD user guide A.3.2), per event:
```
# YR MO DY HR MN SC  LAT LON DEP(km)  MAG  EH EZ RMS  ID
STA  TT  WGHT  PHA          <- one line per pick; TT = pick time − origin time (s)
```
- Header from the catalog: DEP = `depth[m_local]/1000`, EH = EZ = RMS = 0, ID = `int(ID)`.
- STA must match `station.dat` (station code only, e.g. `FORU`, `CS03`).
- Exclude suspicious catalog events (0769 airquake; 1229, 2228, 2519 shallow).
- Output: `data/input_data/phase.dat`.

### A7. Quality control ⬜
- Number of P/S picks per event and per station; events with too few picks (< 4?).
- Residual (pick − prediction) histograms per station and phase.
- Visual checks of picks on record sections for a few events of different magnitude.

**Then:** `ph2dt ph2dt.inp` → `dt.ct`, `event.sel`, `station.sel` (read `ph2dt.log`).

---

## Part B: Waveform cross-correlation → `dt.cc` (hypoDD) and `xcordata` (GrowClust)

### B1. Choose event pairs ⬜
- Pairs closer than a maximum separation (start: a few hundred m; FORGE clouds are small), and/or
  the N nearest neighbours per event.
- Only stations/phases picked (or predicted) for **both** events.
- Niemz et al. used lenient pairing (the whole search volume) and filtered by CC afterwards.

### B2. Cut windows ⬜
- Around each event's pick (or predicted time if no pick): **−0.05 to +0.35 s** (Niemz et al.).
  Short windows: FORGE events are tiny and close.
- **P on the vertical (Z)**; **S on both horizontals (1/2 or N/E)**. No rotation needed: we
  compare the same component at the same station, so orientation cancels.
- Take a longer search segment for the second event (window ± max lag) so the lag can be found.

### B3. Pre-process ⬜
1. `merge`, `detrend("demean")`, `taper`.
2. **Band-pass 20–40 Hz** (Niemz et al.), `zerophase=True` so times are not shifted.
   (Stations at 100 Hz have Nyquist 50 Hz: 40 Hz is the practical upper limit.)
3. **Increase time resolution:** resample to a high rate (Niemz et al.: cubic spline to 2 kHz)
   and/or interpolate the CC peak (parabolic fit) → sub-sample lag precision.

### B4. Cross-correlate ⬜
- Normalised time-domain CC (e.g. `obspy.signal.cross_correlation.correlate` + `xcorr_max`).
- Search lags within ± max lag (e.g. ±0.05–0.1 s; must exceed the pick/prediction uncertainty).
- Record: **lag** (s) and **CC coefficient** (peak height, −1 to 1; use only positive peaks).
- S: CC on each horizontal; keep the component with the higher CC (Niemz: lag from the best
  component, CC = mean of both).

### B5. Convert lag → differential travel time ⬜
- hypoDD and GrowClust want **DT = tt1 − tt2**: event 1's travel time minus event 2's, each
  relative to its own catalog origin time.
- If windows are cut at each event's own pick:
  `DT = (pick1 − OT1) − (pick2 − OT2) + lag_correction` (sign depends on the CC convention;
  **test on a synthetic shift** before trusting it).
- If windows are cut at the same time after each origin: DT is the lag itself.

### B6. Quality selection ⬜
- Keep measurements with **CC > 0.7** (Niemz et al.).
- Keep event pairs with **≥ 6 good phase pairs** (Niemz et al.).
- Reject lags at the edge of the search range (peak not found).

### B7. Write the files ⬜
Both programs use almost the same format:
```
# ID1 ID2 OTC        (hypoDD: OTC = 0.0 when catalog origin times are used)
STA  DT  WGHT  PHA
```
| | hypoDD `dt.cc` | GrowClust `xcordata` |
|---|---|---|
| 3rd column | weight, e.g. **CC²** (squared coherency) | the **CC value** itself |
| DT sign | DT = T1 − T2 | set `tdif_fmt = 12` (tt1 − tt2) in the `.inp` |

### B8. Quality control ⬜
- Histograms of CC values and lags; number of good pairs per event (connectivity).
- Plot aligned waveforms for a few high- and low-CC pairs.
- Consistency check: for 3 events, DT(1,2) + DT(2,3) ≈ DT(1,3).

---

### Note: Clusty (the CC tool used by Niemz et al.)
- **Clusty** (Petersen et al., 2021, GJI 224(3), doi:10.1093/gji/ggaa568), open source (GPL v3):
  https://git.pyrocko.org/clusty/clusty. A toolbox for **clustering** events by waveform similarity;
  computing CC values and lags is its first step, and that is the part Niemz et al. used for GrowClust.
- The CC itself is standard normalised time-domain CC. **Decision:** don't install Clusty for one
  function; reimplement the method (filter, windows, upsampling, S-component choice) in our own
  ObsPy script. Read Clusty's `src/` for the exact details.
- License: reimplementing the *method* is fine. Copying Clusty *code* verbatim would make that code
  GPL v3, so write our own and cite Clusty and Niemz et al. for the method.

---

## Note: Pyrocko (worth knowing)
- **Pyrocko** (Heimann et al., 2017; https://pyrocko.org): open-source Python seismology toolkit
  from GFZ Potsdam. Overlaps with ObsPy (waveform I/O, metadata, processing) and adds:
  - **Synthetic seismograms**: Green's-function databases (**Fomosto**) for forward modelling and
    source inversions (moment tensors, finite faults).
  - **Snuffler**: an interactive waveform viewer and manual picker (`snuffler file.mseed`).
  - Base of the GFZ tools used in this field:
    - **qseek**: ML-assisted (PhaseNet) stacking-and-migration detector/locator, run in quasi-real
      time at FORGE 2024 (Niemz et al., 2025): https://github.com/pyrocko/qseek
    - **Clusty**: waveform-similarity clustering (above).
- Not needed for our pipeline (ObsPy covers it), but a good next tool to learn: synthetic
  seismograms for testing the CC/relocation workflow, and qseek for real-time EGS monitoring,
  directly relevant to Fervo.

---

## Then: relocation
1. hypoDD with `dt.ct` only (`IDAT = 2`) → Milestone 1.
2. hypoDD with `dt.ct` + `dt.cc` (`IDAT = 3`).
3. GrowClust3D with `xcordata` (+ bootstrap uncertainties).
4. Compare with the Niemz et al. catalog.
