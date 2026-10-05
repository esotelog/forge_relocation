#!/usr/bin/env python
"""
Download the raw data for the FORGE 2024 relocation project.

  1. Microseismic catalog (Niemz et al. 2024, Zenodo 12817881).
  2. StationXML (response level) for public stations within --radius of well 16A(78)-32.
  3. Event-windowed miniSEED waveforms (one file per event) from EarthScope FDSN.

Why these networks:
  The catalog was built from network 5K (stacked nodal patches, DOI 10.7914/zt21-tn16),
  but as of Oct 2026 5K is not served by any public FDSN data center (station and
  dataselect both return nothing, also via the EarthScope and EIDA routers). Network Y2
  (FORGE 2024 stress-shadow nodes) has public metadata but restricted waveforms.
  So we use what is public:
    UU  - Univ. of Utah permanent FORGE stations (HH* 200 Hz; FORK geophone GH* 1000 Hz;
          FSB1-3 shallow borehole)
    6K  - Fervo Cape Modern monitoring network (GN* 1000 Hz)

Output layout (under --outdir, default <project>/data/raw_data):
  catalog/microseismic_catalog_Utah_FORGE_2024stim_niemzetal2024.csv
  stations/stations.xml
  waveforms/<eventID>.mseed

Usage (from scripts/py/; works from any directory):
  python 01_download_data.py                                          # whole catalog
  python 01_download_data.py --start 2024-04-05 --end 2024-04-06      # one day only
  python 01_download_data.py --max-events 5                           # quick test
Re-running skips events whose file already exists.
"""
import argparse
import logging
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from obspy import UTCDateTime, read_inventory
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.header import FDSNNoDataException

CATALOG_URL = ("https://zenodo.org/api/records/12817881/files/"
               "microseismic_catalog_Utah_FORGE_2024stim_niemzetal2024.csv/content")
CATALOG_NAME = "microseismic_catalog_Utah_FORGE_2024stim_niemzetal2024.csv"

# Project root = two levels above this file (scripts/py/), so the default output
# location is <project>/data/raw_data no matter where the script is run from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Reference point: well 16A(78)-32 wellhead (catalog local-coordinate origin)
WELL_LAT, WELL_LON = 38.50402147, -112.8963897

NETWORKS = "UU,6K"
# One instrument per station, in order of preference. FORK has EH, GH and GN; we keep
# the 1000 Hz geophone (GH). Accelerometers (EN, GN) are used only where nothing else
# exists (6K), and strain/tilt channels are ignored.
CHANNEL_PRIORITY = ["HH", "GH", "EH", "GN"]

log = logging.getLogger("download")


def download_catalog(outdir):
    path = outdir / "catalog" / CATALOG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        log.info("Downloading catalog from Zenodo")
        urllib.request.urlretrieve(CATALOG_URL, path)
    cat = pd.read_csv(path, dtype={"ID": str})
    cat["time"] = pd.to_datetime(cat["time(UTC)"])
    log.info("Catalog: %d events, %s to %s", len(cat), cat.time.min(), cat.time.max())
    return cat


def download_stations(client, outdir, t0, t1, radius):
    path = outdir / "stations" / "stations.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return read_inventory(str(path))
    log.info("Requesting StationXML for %s within %.2f deg", NETWORKS, radius)
    inv = client.get_stations(network=NETWORKS, latitude=WELL_LAT, longitude=WELL_LON,
                              maxradius=radius, starttime=t0, endtime=t1,
                              channel=",".join(c + "?" for c in CHANNEL_PRIORITY),
                              level="response")
    inv.write(str(path), format="STATIONXML")
    return inv


def pick_channels(inv):
    """Return [(net, sta, loc, 'XX?')] with one preferred instrument per station."""
    picks = []
    for net in inv:
        for sta in net:
            codes = {(ch.location_code, ch.code[:2]) for ch in sta}
            for band in CHANNEL_PRIORITY:
                locs = sorted(loc for loc, b in codes if b == band)
                if locs:
                    picks.append((net.code, sta.code, locs[0], band + "?"))
                    break
    return picks


def fetch_event(client, ev, channels, wavedir, pre, post, retries=3):
    path = wavedir / f"{ev.ID}.mseed"
    if path.exists():
        return ev.ID, "skip"
    t = UTCDateTime(ev.time.to_pydatetime())
    bulk = [(n, s, l, c, t - pre, t + post) for n, s, l, c in channels]
    for attempt in range(retries):
        try:
            st = client.get_waveforms_bulk(bulk)
            st.write(str(path), format="MSEED")
            return ev.ID, f"{len(st)} traces"
        except FDSNNoDataException:
            return ev.ID, "no data"
        except Exception as e:  # network hiccups: back off and retry
            err = e
            time.sleep(5 * (attempt + 1))
    return ev.ID, f"FAILED: {err}"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--outdir", default=str(PROJECT_ROOT / "data" / "raw_data"))
    p.add_argument("--radius", type=float, default=0.1,
                   help="station search radius around the well, degrees (0.1 ~ 11 km)")
    p.add_argument("--pre", type=float, default=5.0, help="seconds before origin")
    p.add_argument("--post", type=float, default=15.0, help="seconds after origin")
    p.add_argument("--start", help="only events after this time (UTC)")
    p.add_argument("--end", help="only events before this time (UTC)")
    p.add_argument("--max-events", type=int)
    p.add_argument("--threads", type=int, default=4)
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    outdir = Path(args.outdir)

    cat = download_catalog(outdir)
    if args.start:
        cat = cat[cat.time >= pd.Timestamp(args.start)]
    if args.end:
        cat = cat[cat.time < pd.Timestamp(args.end)]
    if args.max_events:
        cat = cat.head(args.max_events)

    client = Client("EARTHSCOPE", timeout=120)
    t0 = UTCDateTime(cat.time.min().to_pydatetime()) - 3600
    t1 = UTCDateTime(cat.time.max().to_pydatetime()) + 3600
    inv = download_stations(client, outdir, t0, t1, args.radius)
    channels = pick_channels(inv)
    log.info("Stations used (%d): %s", len(channels),
             " ".join(f"{n}.{s}.{l}.{c}" for n, s, l, c in channels))

    wavedir = outdir / "waveforms"
    wavedir.mkdir(parents=True, exist_ok=True)
    log.info("Fetching %d event windows [-%gs, +%gs]", len(cat), args.pre, args.post)
    failed = []
    with ThreadPoolExecutor(args.threads) as pool:
        jobs = [pool.submit(fetch_event, client, ev, channels, wavedir, args.pre, args.post)
                for ev in cat.itertuples()]
        for i, job in enumerate(as_completed(jobs), 1):
            evid, status = job.result()
            if status.startswith("FAILED") or status == "no data":
                failed.append(evid)
            if i % 100 == 0 or status.startswith("FAILED"):
                log.info("[%d/%d] %s %s", i, len(jobs), evid, status)
    log.info("Done. %d events without data/failed: %s", len(failed), failed[:20])


if __name__ == "__main__":
    main()
