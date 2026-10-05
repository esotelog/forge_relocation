# Moment tensors at Utah FORGE 2024 (future work)

See also: [Forge_catalog.md](Forge_catalog.md), [processing_steps.md](processing_steps.md) (Pyrocko note).

## Paper
Niemz, P., Petersen, G., Rutledge, J., Whidden, K., & Pankow, K. (2026). Isotropic components of
microseismic moment tensors at Utah FORGE reveal a diversity of fluid pathway creation processes in
EGS development. *Scientific Reports* 16:12916. doi:10.1038/s41598-026-42493-0.
Local copy: `reference/MT.pdf`.

Main result: mostly homogeneous **strike-slip** mechanisms consistent with the local stress field, with
small rotations between fracture zones. Many events have a **positive isotropic component** (tensile
opening during slip), more common where existing faults are reactivated than in the zone dominated by
a hydraulic macrofracture. The isotropic part grows with injected volume.

## Method in brief
**Full moment tensor inversion by waveform fitting:** compute synthetic seismograms for trial moment
tensors (6 components + source duration) and search for the ones that best fit the observed P and S
waveforms. They fit **all three types of information together**:
- **waveforms** (time domain, and cross-correlation misfits, which are less sensitive to small time shifts),
- **amplitude spectra** (frequency domain),
- **polarities** (first-motion up/down), with a low weight (0.1 vs 1.0), mainly as a sanity check.

The search is **probabilistic** (Grond: uniform search, then directed search) with **bootstrapping** to get
uncertainties, not a single least-squares solution.

## Software (all open source, Pyrocko ecosystem)
| Tool | Role | License |
|---|---|---|
| **Grond** (Heimann et al., 2018, doi:10.5880/GFZ.2.1.2018.003) | Probabilistic full MT inversion: search, misfits, bootstrap uncertainties, HTML reports | GPL v3. https://pyrocko.org/grond, https://git.pyrocko.org/pyrocko/grond |
| **Pyrocko** (Heimann et al., 2017) | Base library | GPL v3. https://github.com/pyrocko/pyrocko |
| **Fomosto** (in Pyrocko) + **QSEIS** (Wang, 1999) | Pre-computed Green's function databases (synthetic seismograms, layered Earth) | GPL v3. `pyrocko/fomosto-qseis` |

Fomosto computes the synthetic seismograms; Grond compares them with the data.

## Set-up details
- **Events:** 229 candidates, ML 0.0–1.9 → **189 MT solutions**; **109** well resolved enough to
  interpret the isotropic (ISO) component.
- **Parameters:** 7 = 6 independent MT components + source duration (half-sine source time function).
  **Locations fixed** at the GrowClust relocations in the 3D model (the catalog we use).
- **Uncertainty:** 100 bootstrap chains with random station weights + 1 global chain (stations weighted
  equally after a distance correction). The 10 best models per chain (1,010 in total) give the
  uncertainty and trade-offs.
- **Velocity model:** **2-layer** (the UUSS model): Vp 3.4 / Vs 1.95 km/s from 0 to 1.69 km, then
  Vp 5.8 / Vs 3.4 km/s to 17.25 km. No 3D waveform modelling is fast enough for this inversion.
- **Green's functions:** sampled at 50 Hz, source depths 0.5–4.5 km; grid 50 m out to 5 km distance,
  100 m depth / 200 m distance to 40 km, 250 m / 500 m to 150 km.
- **Data:**
  - band-pass **3–7 Hz**; windows **0.34–0.4 s** around **manual P and S picks**;
  - **P on vertical**, **SH on transverse**; **radial excluded** (noisy: P coda, P-to-S conversions);
  - misfit groups (P CC, S CC, P spectra, S spectra) weighted equally; polarities weight 0.1;
  - manual picks aligned with the theoretical arrivals, so the fit focuses on waveform shape.
- **Stations:** UU + **5K nodal patches**, whose horizontal orientations had to be checked (geophones
  set with hand-held compasses). Distances 0.5–40 km, up to 150 km for the largest events.

## Results available
MT tables (best MT, mean MT, standard deviations) and **Grond HTML reports for every event** on
Zenodo: doi:10.5281/zenodo.15783808.

## Relevance for this project
- Reproducing their MTs is hard with our data: it needs horizontal orientations (6K has none; 5K is
  restricted) and good azimuthal coverage.
- **Realistic next step:** download their MT tables and plot the mechanisms (beachballs) on our
  relocated fracture zones, to link locations with source mechanisms and the stress field. Very
  relevant to EGS operations at Fervo.

## Summary of their findings

### Mechanisms
- **189 MT solutions** (Mw 0.6–2.3), covering the whole active volume and about **90 % of the total
  seismic moment**. Two fracture zones: **FR1** (stages S3R–S7, extends the 2022 zone) and **FR2**
  (stages S8–S10, clearly offset from the injection intervals).
- **Remarkably homogeneous strike-slip** mechanisms; a few oblique toward normal faulting.
  Nodal planes NNW–SSE to NNE–SSW (and the conjugate ENE–WSW to ESE–WNW).
  **Fault plane = the ~N–S nodal plane** (it follows the microseismic cloud, the regional geology, and
  opening against SHmax on the other plane would be implausible).
- P-axes sub-horizontal NNE–SSW to NE–SW, consistent with the local **SHmax N15°E–N25°E**.
- **FR2 mechanisms rotated ~30°** relative to FR1; FR2 faults are **optimally oriented for slip**,
  FR1 faults (northern part) align close to SHmax, so less favourable.
- **Shear dominates:** double couple (DC) = 60 % to ~100 % of the moment.
- **Isotropic (ISO) part resolved for 109 events, mostly positive** (volume increase = tensile
  opening during slip). FR2: larger ISOs, many > 20 %; FR1: smaller. Max ISO reaches 25–40 %.
  CLVD poorly resolved, not interpreted.
- **Maximum ISO increases with injected volume** in both fracture zones (newly reported; analogous
  to the known injected-volume vs. maximum-magnitude relation).

### Interpretation
- More injected fluid → more fluid reaches microseismic faults → they **open while slipping**.
  Growing ISO = microseismic faults increasingly become **fluid pathways**. Faults in stress shadows or
  poorly connected still slip in pure shear.
- FR2 offset from the injection points: fluid probably travelled **aseismically** along a conductive
  feature sub-parallel to the wells (not oriented for shear, so invisible) until it reached a fault
  prone to slip. **MTs only illuminate faults prone to slip.**
- **Three types of reservoir enhancement, only a few hundred metres apart:**
  - **T1, hydraulic macrofracture** (northern FR1): cloud elongated along SHmax, fault planes aligned
    with SHmax, small ISOs. A mainly **aseismic** hydraulic fracture (reopened from 2022/2023); the
    microseismicity maps microfractures around its tip. End-member: tensile fracture growth.
  - **T2, reactivation of a pre-existing fault zone** (southern FR2): tight, well-aligned cluster,
    consistently **large ISOs**, growing in time. A pre-existing conductive fault becomes a major
    flow path; shear dilatation matters. End-member: **hydroshearing**.
  - **T3, mixed-mode fracture network** (central/northern FR2, southern FR1): dense, sub-parallel,
    well-oriented microfaults, poorly connected by themselves; new hydraulic fractures link them
    (a **fracture mesh**), with shear + tensile events.
- **"Paradox":** events reactivating a fault optimally oriented for **shear** show the **largest
  opening**, while events mapping hydraulic **fracture** growth show little opening.
- In all three types, **the geometry and connectivity of pre-existing fractures control** how
  permeability is created.

### Impact
- **Non-double-couple components (especially ISO) are a practical tool** to tell complex fracture
  networks from single hydraulic macrofractures, and a possible **proxy for increased conductivity**.
- **Safety:** an interlinked network or fault zone can carry fluid quickly beyond the target reservoir,
  toward larger faults prone to slip (worst case); or it can form an efficient, safe conductive
  network (best case). Monitoring the link between hydraulic fracturing and microseismicity is
  **required for safe reservoir development**.
- **Future use they propose:** if large ISOs on slip-prone fault zones generalise, they could show
  whether distal microseismicity is just a **pressure response** or a real **fluid flow path**,
  improving prediction and management of fluid-fault interaction. **Directly relevant to EGS
  operations** (stage design, well placement, induced-seismicity risk).
