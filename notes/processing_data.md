# Processing data: what the catalog was built from, and what we can use

See also: [Forge_catalog.md](Forge_catalog.md) (catalog format, method, velocity model).

## Data behind the Niemz et al. (2025) catalog

| Input they used | What it is | Available? |
|---|---|---|
| Waveforms, 5 permanent UU stations near the well (paper lists FOR2, FSB1, FSB2, FSB1, FORK; FSB1 twice, probably a typo) | Continuous seismograms | ✅ Public (FDSN, EarthScope). **Downloaded** for all 2,900 events. |
| Waveforms, 16 nodal geophone patches (network **5K**, 3×3 nodes stacked per patch) | Their main addition; improved locations | ❌ **Restricted**: EarthScope assembled dataset **MDA 24-037** (https://ds.iris.edu/mda/24-037/), login required, about 127 GB. Not served by FDSN. |
| UU waveforms, 2022 stimulation + 2023 circulation | Used to tie 2024 events to earlier activity | ✅ Public (same UU stations). Not downloaded. |
| Manual picks for 2022/2023 events (Niemz et al. 2024, *Geothermics*) | CC windows for pre-2024 events | ❓ Unknown. GDR 1584 has the 2022/2023 surface *catalogs*; check whether it includes picks. |
| qseek detections, picks, preliminary locations (about 9,300 detections) | Intermediate products | ❌ Not published |
| CC differential times (45 million, Clusty) | GrowClust input | ❌ Not published |
| 3D composite velocity model (Finger et al. 2024, GDR 1585) | Location + relocation | ✅ Public. **Downloaded** (`data/raw_data/velocity_model/`). |
| 2022 downhole catalog (Dyer, Karvounis & Bethmann, 2023) | Absolute calibration shift | ✅ Most likely on GDR. Not checked yet. |

**Bottom line:** we have the permanent-station waveforms, the velocity model and the final catalog.
We are missing the nodal patches (5K) and all intermediate products (picks, preliminary
locations, differential times). **We cannot reproduce their catalog exactly.**

## Our approach
Rebuild the same *kind* of result from public data, with every step our own:

1. **Picks:** our own (PhaseNet via SeisBench) on the downloaded event windows.
2. **Starting locations:** first the Niemz catalog (Milestone 1). Later, optionally, our own
   independent locations (NonLinLoc with the 3D model, which is already in NLL format), for a real
   before/after.
3. **Catalog differential times:** ph2dt → `dt.ct`.
4. **CC differential times:** our own ObsPy script → `dt.cc`. Start from the paper's parameters:
   20–40 Hz, window −0.05/+0.35 s around picks, resample to a high rate, P on Z, S on the
   horizontals, CC > 0.7, ≥ 6 phase pairs per event pair.
5. **Relocation:** hypoDD (catalog only, then catalog + CC) and GrowClust3D with the same `dt.cc`.
6. **Benchmark:** compare our results with the Niemz catalog.

**Stations** (public, downloaded):
- Their UU stations: FOR2, FORK, FSB1, FSB2 (+ FSB3, likely the duplicated entry).
- Additional UU: FORU, FOR5, FOR6, FOR7, FSB4, FSB5, NMU.
- Fervo's Cape Modern network **6K**: CS01–CS06 (1000 Hz).

Why this is the stronger portfolio story: the whole pipeline is ours, built from public data, and
the published catalog serves as an independent benchmark.

**Expected differences vs. Niemz:** no 5K patches, so fewer nearby stations and weaker azimuthal
coverage. Our relative locations may be less sharp than theirs; quantify this in the comparison.

## Optional: getting 5K
Request access through EarthScope (MDA 24-037), or email Peter Niemz (UUSS;
pniemz.seismology@gmail.com, from the velocity-model documentation). The data are restricted, not
secret, and research access is often granted. Worth asking at the same time:
- which coordinate set is correct (lat/lon vs east/north_shift are offset by about 190 m),
- the depth datum used in the catalog.

## Data downloaded so far
| What | Where | Made by |
|---|---|---|
| Niemz catalog (CSV) | `data/raw_data/catalog/` | `scripts/py/01_download_data.py` |
| StationXML (UU + 6K within 0.1°, response level) | `data/raw_data/stations/stations.xml` | same |
| Event waveforms, −5 to +15 s, 2,900 events, 18 stations | `data/raw_data/waveforms/<ID>.mseed` | same |
| 3D velocity model + documentation | `data/raw_data/velocity_model/` | manual download (GDR 1585) |

## Other public FORGE 2024 datasets (not used yet)
- **GDR 1725:** triggered DAS (well 16B) + continuous downhole geophone data, April 2024 (AWS data lake).
- **GDR 1765:** DAS-based event catalog, April 2024 (source imaging, no phase picks).
- **GDR 1584:** surface network catalogs, 2022 stimulation + 2023 circulation.
