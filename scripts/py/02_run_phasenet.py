#!/usr/bin/env python
"""
Run PhaseNet (SeisBench) on the event-windowed waveforms and save ALL raw picks.

This is the slow step, so it is kept separate from the association step
(03_create_phase_dat.py), which decides which picks belong to which event and writes phase.dat.

Model
  PhaseNet pretrained on the "ethz" dataset, the same pretrained model Niemz et al. (2025) used
  inside qseek. It works at 100 Hz; SeisBench resamples our 100/200/1000 Hz data automatically.

Pre-processing and why
  - merge gaps, demean, 5 % taper.
  - Downsample to 100 Hz (PhaseNet's rate): zero-phase low-pass at 40 Hz (4 corners), then
    decimate (200 Hz: by 2; 1000 Hz: by 10). 100 Hz stations (FORU, NMU) are left as they are.
  - NO band-pass: on test events the unfiltered data gave more and more plausible picks than
    20-45 Hz (the model normalises each window itself).
  - Zero-pad each trace to --pad-to seconds: PhaseNet needs 30 s windows (3001 samples) and our
    event windows are only 20 s (-5 to +15 s around the origin). Without padding it returns no picks.
    The padding creates spurious P picks where the real data starts (about -4.9 s); those are
    removed later by the time windows in the association step.

Output (one row per pick):
  data/picks/phasenet_raw_picks.csv
    event_id, network, station, location, phase, pick_time (UTC), t_rel (s after catalog origin),
    prob (PhaseNet peak probability), start/end of the probability window above threshold.

Usage
  python 02_run_phasenet.py                    # all events
  python 02_run_phasenet.py --max-events 20    # quick test
Re-running appends only events not yet in the output file.
"""
import argparse
import logging
import time
from pathlib import Path

import pandas as pd
import seisbench.models as sbm
from obspy import UTCDateTime, read

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG = (PROJECT_ROOT / "data" / "raw_data" / "catalog" /
           "microseismic_catalog_Utah_FORGE_2024stim_niemzetal2024.csv")
WAVEDIR = PROJECT_ROOT / "data" / "raw_data" / "waveforms"
OUTFILE = PROJECT_ROOT / "data" / "picks" / "phasenet_raw_picks.csv"

TARGET_RATE = 100.0     # PhaseNet sampling rate (Hz)
ANTIALIAS_FREQ = 40.0   # low-pass corner before decimation (Hz), below the 50 Hz Nyquist

log = logging.getLogger("phasenet")


def pick_event(model, path, origin, args):
    st = read(str(path))
    st.merge(fill_value=0)
    st.detrend("demean")
    st.taper(0.05)
    # Downsample to PhaseNet's 100 Hz: zero-phase anti-alias low-pass (corner below the
    # new Nyquist of 50 Hz), then decimate. Done explicitly here instead of inside SeisBench.
    for tr in st:
        sr = tr.stats.sampling_rate
        if sr == TARGET_RATE:
            continue
        if sr % TARGET_RATE == 0:
            tr.filter("lowpass", freq=ANTIALIAS_FREQ, corners=4, zerophase=True)
            tr.decimate(int(sr // TARGET_RATE), no_filter=True)
        else:
            tr.resample(TARGET_RATE)  # FFT resampling, drops energy above the new Nyquist
    # Centre the 20 s of data inside a window long enough for PhaseNet.
    half = args.pad_to / 2
    st.trim(origin + 5 - half, origin + 5 + half, pad=True, fill_value=0)
    out = model.classify(st, P_threshold=args.threshold, S_threshold=args.threshold)
    rows = []
    for p in out.picks:
        net, sta, loc = p.trace_id.split(".")[:3]
        rows.append(dict(network=net, station=sta, location=loc, phase=p.phase,
                         pick_time=str(p.peak_time), t_rel=round(p.peak_time - origin, 3),
                         prob=round(float(p.peak_value), 3),
                         start_rel=round(p.start_time - origin, 3),
                         end_rel=round(p.end_time - origin, 3)))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="ethz", help="PhaseNet pretrained weights")
    p.add_argument("--threshold", type=float, default=0.2,
                   help="min PhaseNet probability to report a pick (keep low; filter later)")
    p.add_argument("--pad-to", type=float, default=40.0, help="padded window length (s)")
    p.add_argument("--max-events", type=int)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    cat = pd.read_csv(CATALOG, dtype={"ID": str})
    if args.max_events:
        cat = cat.head(args.max_events)

    done = set()
    if OUTFILE.exists():
        done = set(pd.read_csv(OUTFILE, dtype={"event_id": str}, usecols=["event_id"]).event_id)
    todo = cat[~cat.ID.isin(done)]
    log.info("%d events in catalog selection, %d already picked, %d to do",
             len(cat), len(cat) - len(todo), len(todo))

    model = sbm.PhaseNet.from_pretrained(args.model)
    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    header = not OUTFILE.exists()
    t0 = time.time()
    batch = []
    for i, ev in enumerate(todo.itertuples(), 1):
        path = WAVEDIR / f"{ev.ID}.mseed"
        if not path.exists():
            log.warning("no waveforms for %s", ev.ID)
            continue
        origin = UTCDateTime(ev._1)  # column "time(UTC)"
        for r in pick_event(model, path, origin, args):
            batch.append(dict(event_id=ev.ID, **r))
        if i % 100 == 0 or i == len(todo):
            # write in chunks so an interrupted run keeps its progress
            pd.DataFrame(batch).to_csv(OUTFILE, mode="a", header=header, index=False)
            header, batch = False, []
            log.info("[%d/%d] %.1f s/event", i, len(todo), (time.time() - t0) / i)
    log.info("Done: %s", OUTFILE)


if __name__ == "__main__":
    main()
