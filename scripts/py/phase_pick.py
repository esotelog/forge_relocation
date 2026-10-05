"""
Pre-processing of the event waveforms for PhaseNet (see notes/processing_steps.md, A2).

Import it from a notebook in notebooks/:
    import sys
    sys.path.append("../scripts/py")
    import phase_pick as pp

    cat = pp.load_catalog()
    st_pn, origin = pp.read_and_preprocess("0002", cat, highpass_freq=20)   # one event, 20-40 Hz
    st_pn, origin = pp.read_and_preprocess("0002", cat, pad="noise")        # noise padding

    # PhaseNet on all events in parallel (8 worker processes)
    picks, errors = pp.pick_events_parallel(cat.index, params, stations=stations,
                                            highpass_freq=10, pad="noise", n_workers=8)

Steps applied to every trace (same as in the notebook view_data_eg.ipynb):
  0. merge gap-split traces (one trace per channel)
  1. demean
  2. 5 % cosine taper
  3. downsample to 100 Hz (PhaseNet's rate): zero-phase low-pass at 40 Hz, then decimate
     (200 Hz: every 2nd sample, 1000 Hz: every 10th; 100 Hz stations unchanged;
     non-integer ratios: FFT resampling)
  4. optional high-pass at `highpass_freq` (zero-phase). With the 40 Hz low-pass of step 3 this
     makes a band-pass highpass_freq-40 Hz (Niemz et al. 2025 used 20-50 Hz before PhaseNet).
     Default None = no high-pass.
  5. pad to 40 s around the centre of the -5/+15 s window (PhaseNet needs 30 s windows)

Padding options (`pad`):
  "zero"  (default) pad with zeros AFTER the steps above. The jump from zeros to noise at the data
          start creates false P picks at about -4.9 s.
  "noise" pad with the trace's own noise, BEFORE tapering and filtering:
          the first `noise_len` s (-5 to -2 s: before any arrival) are mirrored back and forth to
          fill the start, the last `noise_len` s (+12 to +15 s) to fill the end. Mirroring keeps the
          joins continuous (no jumps). Order: merge, demean, noise-pad, taper (ends of the padded
          trace, far from the data), downsample, optional high-pass.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import obspy as obs

# Project root = two levels above this file (scripts/py/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG = (PROJECT_ROOT / "data" / "raw_data" / "catalog" /
           "microseismic_catalog_Utah_FORGE_2024stim_niemzetal2024.csv")
WAVEDIR = PROJECT_ROOT / "data" / "raw_data" / "waveforms"

# Download window around each origin time (01_download_data.py: --pre 5 --post 15)
WINDOW_PRE, WINDOW_POST = 5.0, 15.0

TARGET_RATE = 100.0      # PhaseNet sampling rate (Hz)
ANTIALIAS_FREQ = 40.0    # low-pass corner (Hz), below the new Nyquist of 50 Hz
PAD_TO = 40.0            # padded window length (s)
NOISE_LEN = 3.0          # length (s) of the noise sample at each end used for noise padding


def load_catalog():
    """Niemz et al. catalog, indexed by event ID as text ("0001")."""
    return pd.read_csv(CATALOG, dtype={"ID": str}).set_index("ID")


def _mirror_fill(seg, n):
    """n samples continuing a signal by reflecting `seg` back and forth (seg[0] is next to the data)."""
    reps = int(np.ceil(n / (2 * len(seg)))) + 1
    return np.concatenate([seg, seg[::-1]] * reps)[:n]


def noise_pad(tr, t_start, t_end, noise_len=NOISE_LEN):
    """Extend trace `tr` (in place) to t_start..t_end with mirrored noise from its own ends."""
    sr, data = tr.stats.sampling_rate, tr.data.astype(np.float64)
    n_noise = int(noise_len * sr)
    n_pre = max(0, int(round((tr.stats.starttime - t_start) * sr)))
    n_post = max(0, int(round((t_end - tr.stats.endtime) * sr)))
    # start: reflect the first noise_len s about the first sample (going back in time)
    pre = _mirror_fill(data[1:n_noise + 1], n_pre)[::-1]
    # end: reflect the last noise_len s about the last sample (going forward in time)
    post = _mirror_fill(data[-n_noise - 1:-1][::-1], n_post)
    tr.data = np.concatenate([pre, data, post])
    tr.stats.starttime -= n_pre / sr


def preprocess(st, origin, highpass_freq=None, pad="zero", noise_len=NOISE_LEN,
               target_rate=TARGET_RATE, antialias_freq=ANTIALIAS_FREQ, pad_to=PAD_TO):
    """
    Return a PhaseNet-ready copy of stream `st` (the input stays unchanged).

    highpass_freq : lower corner (Hz) of the band; the upper corner is the 40 Hz
                    anti-alias low-pass. None = no high-pass.
    pad           : "zero" (default) or "noise" (see module docstring)
    noise_len     : seconds of noise taken from each end for pad="noise"
    """
    if pad not in ("zero", "noise"):
        raise ValueError('pad must be "zero" or "noise"')
    centre = origin + (WINDOW_POST - WINDOW_PRE) / 2     # centre of the -5/+15 s data window
    t_start, t_end = centre - pad_to / 2, centre + pad_to / 2

    st_pn = st.copy()
    st_pn.merge(fill_value=0)                # 0. one trace per channel
    st_pn.detrend("demean")                  # 1. remove the mean
    if pad == "noise":                       # 1b. noise padding before taper and filters
        for tr in st_pn:
            noise_pad(tr, t_start, t_end, noise_len)
    st_pn.taper(0.05)                        # 2. 5 % cosine taper at each end

    for tr in st_pn:                         # 3. downsample to target_rate
        sr = tr.stats.sampling_rate
        if sr == target_rate:
            continue                         #    FORU, NMU: already 100 Hz
        if sr % target_rate == 0:
            tr.filter("lowpass", freq=antialias_freq, corners=4, zerophase=True)  # no time shift
            tr.decimate(int(sr // target_rate), no_filter=True)                    # every n-th sample
        else:
            tr.resample(target_rate)         #    non-integer ratio: FFT resampling

    if highpass_freq is not None:            # 4. optional high-pass -> band highpass_freq-40 Hz
        st_pn.filter("highpass", freq=highpass_freq, corners=4, zerophase=True)

    # 5. pad_to s around the window centre: zero padding, or (noise) just trim to the exact length
    st_pn.trim(t_start, t_end, pad=True, fill_value=0)
    return st_pn


def read_and_preprocess(evid, cat, highpass_freq=None, pad="zero"):
    """
    Read one event's waveforms and pre-process them. Returns (stream, origin time).

    highpass_freq : lower corner (Hz) of the band (upper corner 40 Hz); None = no high-pass.
    pad           : "zero" (default) or "noise"
    """
    origin = obs.UTCDateTime(cat.loc[evid, "time(UTC)"])
    st = obs.read(str(WAVEDIR / f"{evid}.mseed"))
    return preprocess(st, origin, highpass_freq=highpass_freq, pad=pad), origin


# Elevation (m above sea level) of the wellhead of 16A(78)-32: datum of the catalog depths
WELLHEAD_ELEV = 1650.0


def calculate_distance(cat, stations_data):
    """
    Distance from every catalog event to every station. Returns one row per (event, station):
      event_id, station,
      epi_km   : epicentral (horizontal) distance, km (WGS84 ellipsoid)
      azimuth  : from the event to the station, degrees clockwise from north
      vert_km  : vertical distance event -> sensor, km
      hypo_km  : straight-line (hypocentral) distance, km = sqrt(epi_km^2 + vert_km^2)

    cat           : catalog from load_catalog() (lat, lon, depth[m_local])
    stations_data : station.dat as a DataFrame with columns sta, lat, lon, elev (sensor elevation,
                    m above sea level)

    Depths: catalog depth is m below the wellhead (1650 m a.s.l.); the sensor is
    (WELLHEAD_ELEV - elev) m below the wellhead, so vert = depth - (WELLHEAD_ELEV - elev).
    """
    from obspy.geodetics import gps2dist_azimuth
    rows = []
    for evid, ev in cat.iterrows():
        for s in stations_data.itertuples():
            dist_m, az, _ = gps2dist_azimuth(ev["lat"], ev["lon"], s.lat, s.lon)
            vert_m = ev["depth[m_local]"] - (WELLHEAD_ELEV - s.elev)
            rows.append(dict(event_id=evid, station=s.sta, epi_km=dist_m / 1000,
                             azimuth=az, vert_km=vert_m / 1000,
                             hypo_km=np.hypot(dist_m, vert_m) / 1000))
    return pd.DataFrame(rows).round({"epi_km": 3, "azimuth": 1, "vert_km": 3, "hypo_km": 3})


# ---------------------------------------------------------------------------------------------
# PhaseNet on one event, and on many events in parallel (see notes/processing_steps.md, A3b)
# ---------------------------------------------------------------------------------------------

def pick_event(evid, cat, model, params, stations=None, highpass_freq=None, pad="zero"):
    """
    One event: read + pre-process + keep `stations` + PhaseNet. Returns a DataFrame of picks
    (event_id, network, station, phase, pick_time, t_rel = s after origin, prob).

    model    : a loaded SeisBench model, e.g. sbm.PhaseNet.from_pretrained("ethz")
    params   : dict passed to model.classify (P_threshold, S_threshold, blinding, ...)
    stations : set of station codes to keep (None = all)
    """
    st_pn, origin = read_and_preprocess(evid, cat, highpass_freq=highpass_freq, pad=pad)
    if stations is not None:
        st_pn = obs.Stream([tr for tr in st_pn if tr.stats.station in stations])
    rows = []
    for p in model.classify(st_pn, **params).picks:
        net, sta, loc = p.trace_id.split(".")[:3]
        rows.append(dict(event_id=evid, network=net, station=sta, phase=p.phase,
                         pick_time=str(p.peak_time),
                         t_rel=round(p.peak_time - origin, 3),     # travel time (s)
                         prob=round(float(p.peak_value), 3)))      # PhaseNet probability
    return pd.DataFrame(rows, columns=["event_id", "network", "station", "phase",
                                       "pick_time", "t_rel", "prob"])


# Each worker process keeps its own catalog, model and settings (loaded once per worker).
_WORKER = {}


def _init_worker(model_name, settings):
    import torch
    import seisbench.models as sbm
    torch.set_num_threads(1)                     # one CPU core per worker (avoid oversubscription)
    _WORKER.update(cat=load_catalog(), model=sbm.PhaseNet.from_pretrained(model_name), **settings)


def _pick_one(evid):
    try:
        return evid, pick_event(evid, _WORKER["cat"], _WORKER["model"], _WORKER["params"],
                                _WORKER["stations"], _WORKER["highpass_freq"], _WORKER["pad"]), None
    except Exception as e:                       # one bad event must not stop the whole run
        return evid, None, f"{type(e).__name__}: {e}"


def pick_events_parallel(evids, params, stations=None, highpass_freq=None, pad="zero",
                         model_name="ethz", n_workers=8, report_every=200):
    """
    PhaseNet on many events in parallel: each worker process handles one event at a time.
    Returns (picks DataFrame for all events, dict {event_id: error message} for failed events).
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    settings = dict(params=params, stations=stations, highpass_freq=highpass_freq, pad=pad)
    tables, errors = [], {}
    with ProcessPoolExecutor(n_workers, initializer=_init_worker,
                             initargs=(model_name, settings)) as pool:
        jobs = [pool.submit(_pick_one, evid) for evid in evids]
        for i, job in enumerate(as_completed(jobs), 1):
            evid, table, err = job.result()
            if err:
                errors[evid] = err
            else:
                tables.append(table)
            if i % report_every == 0 or i == len(jobs):
                print(f"{i}/{len(jobs)} events done, {len(errors)} errors")
    picks = pd.concat(tables, ignore_index=True).sort_values(["event_id", "station", "phase"])
    return picks.reset_index(drop=True), errors


# ---------------------------------------------------------------------------------------------
# Picks -> hypoDD/ph2dt phase file (user guide A.3.2)
# ---------------------------------------------------------------------------------------------

PHASE_DAT = PROJECT_ROOT / "data" / "input_data" / "phase.dat"

# Binned weights (like the NCSN pick classes 0-3): (minimum probability, weight), best class first
WEIGHT_CLASSES = ((0.7, 1.0), (0.4, 0.5), (0.2, 0.2), (0.0, 0.1))

# Suspicious catalog events (notes/Forge_catalog.md): 0769 above the wellhead, others shallow
BAD_EVENTS = ("0769", "1229", "2228", "2519")


def pick_weight(prob, weight="prob", classes=WEIGHT_CLASSES):
    """
    hypoDD weight (0-1) of a pick from its PhaseNet probability.
    weight="prob"    : the probability itself
    weight="classes" : the weight of the first class whose minimum probability is reached
    """
    if weight == "prob":
        return float(prob)
    if weight == "classes":
        for pmin, w in classes:
            if prob >= pmin:
                return w
        return 0.0
    raise ValueError('weight must be "prob" or "classes"')


def create_phase_dat(picks, cat, weight="prob", classes=WEIGHT_CLASSES, t_window=(0.0, 5.0),
                     min_picks=4, min_stations=3, exclude_events=BAD_EVENTS, datum=0.0,
                     remove_airquakes=True, outfile=PHASE_DAT):
    """
    Write the ph2dt phase file from PhaseNet picks. Returns the table of picks written.

    picks          : DataFrame from pick_events_parallel (event_id, station, phase, t_rel, prob)
    cat            : catalog from load_catalog()
    weight         : "prob" (weight = PhaseNet probability) or "classes" (binned, see `classes`)
    classes        : ((min_prob, weight), ...) for weight="classes", best class first
    t_window       : (t_min, t_max) s after origin; picks outside are dropped (padding artefacts,
                     noise, other events). Simple time check, not a full association.
    min_picks      : events with fewer picks (P + S) are not written
    min_stations   : events with picks at fewer stations are not written
    exclude_events : catalog events never written
    datum          : elevation (km above sea level) of hypoDD's depth 0. Default 0 = sea level,
                     the same reference as the station elevations in station.dat (m a.s.l.)
    remove_airquakes : drop events whose depth is above the datum (DEP <= 0); hypoDD would treat
                     them as air-quakes

    File format (hypoDD user guide A.3.2), per event:
      # YR MO DY HR MN SC LAT LON DEP MAG EH EZ RMS ID     (header from the catalog)
      STA TT WGHT PHA                                       (one line per pick, TT = t_rel)
    DEP = km below the datum = depth[m_local]/1000 - (WELLHEAD_ELEV/1000 - datum).
          The catalog depth is below the wellhead (1650 m a.s.l.); with datum = 0 (sea level)
          DEP = catalog depth - 1.65 km. The velocity model in hypoDD.inp must use the same datum.
    EH, EZ, RMS = 0 (not available). ID = catalog ID as an integer (0010 -> 10).
    """
    p = picks.copy()
    # 1. time window: keep picks between t_min and t_max after the origin
    p = p[(p.t_rel >= t_window[0]) & (p.t_rel <= t_window[1])]
    # 2. one P and one S per event and station: the highest probability
    p = p.sort_values("prob", ascending=False).drop_duplicates(["event_id", "station", "phase"])
    # 3. weights
    p["weight"] = [pick_weight(pr, weight, classes) for pr in p.prob]
    # 4. events: drop excluded ones and those with too few picks or stations
    p = p[~p.event_id.isin(exclude_events)]
    # 4b. depth below the datum; events above it would be air-quakes in hypoDD
    dep_km = cat["depth[m_local]"] / 1000 - (WELLHEAD_ELEV / 1000 - datum)
    if remove_airquakes:
        air = sorted(set(p.event_id) & set(dep_km[dep_km <= 0].index))
        if air:
            print(f"Removed {len(air)} events above the datum ({datum:g} km a.s.l.): {air}")
        p = p[~p.event_id.isin(air)]
    n_picks = p.groupby("event_id").size()
    n_sta = p.groupby("event_id").station.nunique()
    keep = n_picks[(n_picks >= min_picks) & (n_sta.loc[n_picks.index] >= min_stations)].index
    p = p[p.event_id.isin(keep)].sort_values(["event_id", "phase", "t_rel"])

    outfile = Path(outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with open(outfile, "w") as f:
        for evid, ev_picks in p.groupby("event_id", sort=True):
            ev = cat.loc[evid]
            t = obs.UTCDateTime(ev["time(UTC)"])
            sec = t.second + t.microsecond / 1e6
            f.write(f"# {t.year:4d} {t.month:2d} {t.day:2d} {t.hour:2d} {t.minute:2d} {sec:6.3f} "
                    f"{ev['lat']:9.5f} {ev['lon']:10.5f} {dep_km.loc[evid]:7.3f} "
                    f"{ev['magnitude']:5.2f} 0.00 0.00 0.00 {int(evid):9d}\n")
            for r in ev_picks.itertuples():
                f.write(f"{r.station:<7s} {r.t_rel:8.3f} {r.weight:7.4f} {r.phase}\n")

    print(f"Wrote {outfile}: {p.event_id.nunique()} events, {len(p)} picks "
          f"(P {(p.phase == 'P').sum()}, S {(p.phase == 'S').sum()}), weight = {weight}; "
          f"{picks.event_id.nunique() - p.event_id.nunique()} events not written")
    return p.reset_index(drop=True)
