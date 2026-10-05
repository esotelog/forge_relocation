# Utah FORGE 2024 microseismic catalog (Niemz et al., 2025)

## Source
- **Paper:** Niemz, P., Pankow, K., Isken, M. P., Whidden, K., McLennan, J., & Moore, J. (2025).
  Mapping Fracture Zones with Nodal Geophone Patches: Insights from Induced Microseismicity During
  the 2024 Stimulations at Utah FORGE. *Seismol. Res. Lett.* 96(3), 1603–1618.
  doi:10.1785/0220240300. Local copy: `reference/Forge_stimulation.pdf`.
  (Zenodo says "2024, submitted"; the published version is 2025.)
- **Catalog:** Zenodo record 12817881 (concept DOI 10.5281/zenodo.12817880).
  File: `microseismic_catalog_Utah_FORGE_2024stim_niemzetal2024.csv`.
  Local copy: `data/raw_data/catalog/`, downloaded by `scripts/py/01_download_data.py`.
- **Supplement** (not downloaded yet): method details, Fig. S5 (location uncertainties), and a table of
  stage times, hydraulic parameters and event counts. **Needed to choose the first stage.**

## How the catalog was made (paper, Methods)
1. **Detection + preliminary location:** qseek (stacking-and-migration). Image functions =
   PhaseNet P/S probabilities (SeisBench, pretrained ETHZ model), band-pass 20–50 Hz, semblance
   threshold 0.08, 3D FORGE velocity model. Search volume 4.5 × 4.5 km, depth 0.5–5.5 km.
   - Real time: 5 permanent UU stations. Post-processing: UU + 16 nodal patch stacks (network 5K).
   - More than 9,300 detections, 3–19 April 2024. Cut at **M > −1** → 2,953 events.
2. **Magnitudes:** mean of single-station ML at UU.FORK, UU.FOR2, UU.FSB1 (horizontal amplitudes,
   20–40 Hz), calibrated to UUSS ML. **Not authoritative**, a proxy for ML.
3. **Cross-correlation differential times:** Clusty.
   - Resample to 2 kHz (cubic spline), band-pass 20–40 Hz.
   - Windows −0.05 to +0.35 s around qseek picks (2024) or manual picks (2022/2023 events).
   - **P:** vertical component. **S:** CC = mean of the two horizontals; lag from the horizontal with
     the higher CC.
   - Keep pairs with **≥ 6 phase pairs with CC > 0.7**. Result: 45 million dt, 71 % S.
4. **Relocation:** GrowClust.jl (GrowClust3D) with the 3D model and station elevations (up to 400 m
   elevation differences between stations). Lenient clustering (max pair distance = whole search
   volume), cluster-merge RMS threshold 0.1 s, **100 bootstraps** for uncertainty.
   → **2,900 of 2,953** events relocated. Relative uncertainty: median 10 m, 90 % < 15 m.
5. **Absolute calibration:** 2022 and 2023 events relocated together with the 2024 events, then the
   whole cloud **shifted so the largest 2022 event matches the 2022 downhole catalog** (Dyer,
   Karvounis & Bethmann, 2023). Perforation shots are not visible at the surface (> 100 Hz).

Velocity model: 3D composite FORGE model (Zhang & Pankow, 2021; Finger et al., 2024; GDR).

## File format
CSV, comma-separated, 1 header line, 2,900 rows (one event per row), events 2024-04-03 to 2024-04-15.

| Column | Example | Meaning |
|---|---|---|
| `time(UTC)` | `2024-04-03 17:47:29.411` | Origin time, UTC, ms precision |
| `ID` | `0001` | Event ID `0001`–`2900`, unique. **Read as string** (`dtype={"ID": str}`) to keep zeros |
| `lat`, `lon` | `38.50136`, `-112.88286` | Relocated epicentre, degrees (5 decimals ≈ 1 m) |
| `depth[m_local]` | `2427.85` | Depth in **metres** in the local system (datum: see open questions) |
| `east_shift[m_local]` | `1006.43` | Metres east of the local origin |
| `north_shift[m_local]` | `-200.84` | Metres north of the local origin |
| `magnitude` | `-0.93` | ML proxy (range −1.0 to 2.03, median −0.71) |
| `P_residual[s]` | `0.08` | GrowClust `qrmsP`: per-event **RMS of P differential-time residuals** |
| `S_residual[s]` | `0.08` | GrowClust `qrmsS`: same for S |
| `n_pairs` | `2879` | GrowClust `qnpair`: number of event pairs linked to this event |
| `ndiff_p`, `ndiff_s` | `8996`, `28539` | GrowClust `qndiffP`, `qndiffS`: number of CC differential times used |

GrowClust mapping checked against `sources/GrowClust3D.jl/src/postprocess.jl` (lines 143–183).

**Local coordinates** (Zenodo): relative to well 16A(78)-32, lat 38.50402147, lon −112.8963897,
elevation 1650 m.

**Not included:** phase picks or travel times, bootstrap uncertainties (EH/EZ; shown only as a
figure in Fig. S5), station list, stage labels.

## Value checks (my own, Oct 2026)
- **Depth distribution:** 2,891 events between 1.5 and 3.5 km. Suspicious events:

  | ID | depth (m) | M | P_residual (s) | note |
  |---|---|---|---|---|
  | 0769 | −627 | −0.64 | 0.54 | above the wellhead: airquake |
  | 1229 | 546 | −0.48 | 1.06 | shallow, high residual |
  | 2228 | 596 | −0.85 | 0.59 | shallow |
  | 2519 | 598 | −0.61 | 1.03 | shallow, high residual |

  → exclude or flag these.
- **Every depth ends in `.85`** (all 2,900).
- **lat/lon vs east/north_shift are offset by a constant.** Converting lat/lon to metres from the
  stated wellhead (WGS84 geodesic) gives values **≈ 174 m east and ≈ 95 m south** of
  `east_shift`/`north_shift`, with only 0.5 m scatter. So the two coordinate sets agree internally
  but don't share the same origin. **Use one set consistently.** Relative positions are not affected.

## Open questions
1. **Depth datum:** below the wellhead (1650 m) or below sea level? The paper text doesn't say.
   Below wellhead fits best: the wells reach about 2.6 km and the median event depth is 2.4 km.
2. **Cause of `.85` and the lat/lon offset.** Hypothesis: the single calibration shift (step 5) was
   applied as a constant, and to only one of the coordinate sets. Check the supplement, or ask the
   authors.
3. **Which coordinate set is "true":** lat/lon or east/north_shift?

## Waveform data availability
- **5K nodal stacks** (the network used for this catalog): EarthScope assembled dataset **24-037**,
  https://ds.iris.edu/mda/24-037/ — **restricted**, login required, about 127 GB. Not served by FDSN.
- **Public, used instead:** UU (FOR2, FOR5, FOR6, FOR7, FORK, FORU, FSB1–5, NMU) and **6K**
  (Fervo Cape Modern, CS01–CS06, 1000 Hz). Their real-time detection used only 5 permanent UU stations
  near the well (listed as FOR2, FSB1, FSB2, FSB1, FORK: FSB1 appears twice, probably a typo); we have
  all of them.
- **Y2** (FORGE 2024 stress-shadow nodes): public metadata, restricted waveforms.

## Use in this project
- **Starting locations** for hypoDD/GrowClust and **baseline for comparison.** It is already a
  GrowClust + CC result, so it directly benchmarks our pipeline.
- **No picks:** we must pick ourselves (PhaseNet via SeisBench), then build `phase.dat` for ph2dt.
- **Conversion to hypoDD `event.dat` / `.pha` header:**

  | hypoDD field | From the catalog |
  |---|---|
  | DATE, TIME | split `time(UTC)` |
  | LAT, LON | `lat`, `lon` (or convert east/north_shift; pick one, see offset) |
  | DEP (km) | `depth[m_local] / 1000`. The datum must match the velocity model and station elevations |
  | MAG | `magnitude` |
  | EH, EZ | 0 (not available) |
  | RMS | 0, or mean of P/S residuals |
  | ID | `int(ID)` |

- **Starting CC parameters** from the paper: 20–40 Hz, window −0.05/+0.35 s, resample to high rate,
  P on Z and S on the horizontals, CC > 0.7, ≥ 6 phase pairs per event pair.

## Velocity model (not in the catalog dataset)
The Zenodo record has no velocity model. The paper uses the **composite 3D FORGE model**:
- Finger, C., Niemz, P., Ermert, L., & Lanza, F. (2024). Utah FORGE: Composite 3D Seismic Velocity
  Model. Geothermal Data Repository, submission 1585, doi:10.15121/2305384. Free download.
- Local copy: `data/raw_data/velocity_model/` (zip + extracted files).
  - `FORGE_3Dv3_5_large.{P,S}.mod.buf/.hdr`: NonLinLoc grids, SLOW_LEN = (1/V) × grid spacing.
  - `FORGE_composite_3D.py`: script to rebuild or export the model (binary, netCDF, NLL).
  - `Utah_FORGE_comp3D_velmodel_documentation.pdf`: how the model was built.
- **Same local coordinate system as the catalog:** origin at wellhead 16A(78)-32 (1650 m elevation);
  **depth relative to the wellhead elevation, negative = above it** (documentation, step [1]).
  This supports reading `depth[m_local]` as **depth below the wellhead**.
- Grid (from the `.hdr`): 111 × 75 × 67 nodes, 50 m spacing. E −1.811 to 3.689 km, N −2.128 to
  1.572 km, depth −0.2 to 3.1 km.
- **Many of our stations lie outside the grid** (FOR5, FOR6, FOR7, FORU, FSB4, FSB5, NMU, most of 6K).
  The grid only covers about 5.5 × 3.7 km.
- 1D profile extracted at the seismicity centroid (E 0.91, N −0.21 km), every 200 m:

  | depth below wellhead (km) | Vp (km/s) | Vs (km/s) | Vp/Vs |
  |---|---|---|---|
  | −0.2 | 0.68 | 0.40 | 1.71 |
  | 0.0 | 1.45 | 0.68 | 2.12 |
  | 0.2 | 2.17 | 1.03 | 2.11 |
  | 0.4 | 2.94 | 1.47 | 2.00 |
  | 0.6 | 3.61 | 1.93 | 1.87 |
  | 0.8 | 4.22 | 2.37 | 1.78 |
  | ≥ 1.0 | 5.80 | 3.40 | 1.71 (granitoid basement, constant) |

  Basin fill over basement; the basement contact **dips** (shallower to the east), so the 1D profile
  varies with position. All events (~2.4 km) sit in the constant 5.8 / 3.4 km/s basement.
- Also in the documentation (Table 1): the **UUSS 1D model** (Bjarnason & Pechmann, 1989), with depths
  shifted to the wellhead reference: Vp 3.4 / Vs 1.95 from −0.2 to 1.69 km, then Vp 5.9 / Vs 3.39 to
  17.25 km, then 6.4 / 3.68 to 28.15 km, then 7.5 / 4.31 to 42.15 km, then 7.9 / 4.54.
- For hypoDD (1D, `IMOD` 0 or 1): start from the centroid profile above (layered), with depths in
  the wellhead datum and station elevations consistent with it.
