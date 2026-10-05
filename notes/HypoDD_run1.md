# hypoDD run 1: catalog-only (PhaseNet picks), 4 Oct 2026

See also: [processing_steps.md](processing_steps.md), [Forge_catalog.md](Forge_catalog.md).

## Settings
**Stations:** 13 within 6 km of the wellhead (`create_station_dat.py --max-distance=6`), NMU dropped
for picking → 12 used for picks. Datum: sea level (station elevations m a.s.l.).

**Picking:** PhaseNet ETHZ, pre-processing 10-40 Hz (`highpass_freq=10`, 40 Hz anti-alias
low-pass), noise padding; `P_threshold=0.1, S_threshold=0.1, blinding=(250, 250), overlap=2500,
stacking="max", strict=True`.

**phase.dat:** `create_phase_dat(picks_all, cat, weight="prob")`: weight = PhaseNet probability
(min 0.10, median 0.57, max 0.98); picks 0-5 s after origin; one P and one S per station;
≥ 4 picks and ≥ 3 stations per event; 4 suspicious events excluded; depths below sea level
(catalog depth − 1.65 km); 6 events above sea level removed.

**ph2dt.inp:** `MINWGHT 0, MAXDIST 10, MAXSEP 1, MAXNGH 10, MINLNK 4, MINOBS 4, MAXOBS 50`.

**hypoDD.inp:** catalog only (`IDAT 2`), P and S (`IPHA 3`), `DIST 15`, `OBSCT 4`, start from
catalog locations (`ISTART 2`), LSQR (`ISOLV 2`), remove air-quakes (`IAQ 1`).
Iterations (NITER, WTCCP, WTCCS, WRCC, WDCC, WTCTP, WTCTS, WRCT, WDCT, DAMP):

| set | NITER | WTCTP | WTCTS | WRCT | WDCT (km) | DAMP |
|---|---|---|---|---|---|---|
| 1 | 5 | 1.0 | 0.5 | off | off | 100 |
| 2 | 5 | 1.0 | 0.5 | 6 (× std) | 1.0 | 100 |

Velocity model (`IMOD 1`, depths below sea level): station → sea level Vp 3.7 km/s,
Vp/Vs 1.83; below sea level (basement) Vp 5.8, Vp/Vs 1.71.

## Statistics (relocated events vs. catalog, same events)
| | Value | Assessment |
|---|---|---|
| Events | catalog 2,900 → phase.dat 1,741 → ph2dt event.sel 1,741 → **relocated 1,388** | 353 lost in hypoDD (mostly air-quakes) |
| Catalog differential times | 85,650 dt.ct lines; median 67 per event (33 P, 35 S) | well connected |
| Clusters | 2 (1,386 events + 1 pair) | OK |
| Residual per event (RCT) | median 46 ms, 90 % 61 ms, max 221 ms | consistent with PhaseNet pick errors |
| Shift catalog → hypoDD, horizontal | median 180 m, 90 % 563 m, max 1,586 m | large (catalog relative errors ~10 m) |
| Shift catalog → hypoDD, vertical | median 193 m, 90 % 558 m, max 1,970 m; mean +89 m (deeper) | large |
| Centroid shift | E −47 m, N +63 m, Z +89 m | small, as expected for DD |
| Spread of the cloud (std) | catalog E 149, N 256, Z 176 m; **hypoDD E 310, N 310, Z 340 m** | **twice as diffuse** |
| Air-quakes removed | **276** (summed over iterations) | problem (see below) |
| Last iteration | RMSCT 309 ms, RMSST 276 ms, mean changes DX 3 / DY 0 / DZ 1 m, AQ 0, **CND 2** | strongly over-damped |

Figure: `plots.plot_relocation(cat, hdd.read_reloc())`. The catalog shows two sharp, roughly
N-S fracture zones at ~0.8 and ~1.1 km east of the wellhead; hypoDD gives a diffuse cloud around
the same area, with the structures blurred and some events down to ~4 km depth.

## Interpretation
1. **Blurring: the data are noisier than the starting locations.** The Niemz et al. catalog is
   already a cross-correlation (GrowClust) relocation with ~10 m relative errors. Our data are
   PhaseNet catalog picks with ~46 ms residuals (≈ 150-250 m at 3-5 km/s). hypoDD fits this
   noise and spreads the events. Catalog-only DD cannot improve on a CC catalog; the improvement
   has to come from cross-correlation data (dt.cc).
2. **Air-quakes caused by the sea-level datum.** Events less than ~1.65 km below the wellhead are
   above sea level; when noise moves an event up it becomes an "air-quake" and is removed
   (`IAQ 1`). This deletes real events and biases the result (upper part of the cloud lost).
3. **Over-damping (CND 2).** The guide suggests a condition number of roughly 40-80; a low value
   means the damping is too strong.

## Next steps (one change at a time, compare with this run)
1. **Datum**: use 1.40 km a.s.l. (just below the lowest sensor, FORK at 1,405 m), so events are
   allowed down to 0.25 km below the wellhead; or keep sea level with `IAQ 0` (keep air-quakes,
   reset depth). Expect far fewer lost events.
2. **Damping**: lower `DAMP` (try 50, 20, 10) until CND is roughly 40-80.
3. **Data quality**: ph2dt `MINWGHT 0.3` (drop low-probability picks); try `MAXSEP 0.5`;
   compare `weight="classes"`.
4. **Velocity model**: compare with the UUSS 2-layer model (sensitivity test).
5. **Cross-correlation dt.cc** (`IDAT 3`), then GrowClust with the same dt.cc: this is what should
   sharpen the fracture zones, as in Niemz et al. (2025).
