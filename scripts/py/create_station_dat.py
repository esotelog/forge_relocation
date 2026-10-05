#!/usr/bin/env python
"""
Create the station file for hypoDD and GrowClust from the FORGE StationXML.

Output format (one station per line, free format), used by both programs:
    STA  LAT  LON  ELEV
  - hypoDD  station.dat (user guide B.3.5): ELEV in metres.
  - GrowClust3D stlist with stlist_fmt = 2: same columns.

Why sensor elevation matters
  hypoDD and GrowClust need the elevation of the SENSOR, not of the ground surface.
  That matters most for UU.FORK: its sensor is 281 m down, roughly 0.1 s of P travel time
  through the slow basin fill. The 26-41 m boreholes (FSB1-5, most 6K stations) matter less.
  So for each station: sensor elevation = surface elevation - depth.

Why the surface elevation needs checking
  StationXML gives a station elevation, a channel elevation and a channel depth, but the
  FORGE stations do not use one convention:
    - UU.FORK GH: depth 281 m, channel elevation 1409 m  -> 1409 is the SENSOR
      UU.FORK GN: depth 282 m, channel elevation 1686 m  -> 1686 is the SURFACE
    - UU.FSB4:    depth 41 m, station 1578 m, channel 1619 m -> 1619 surface, 1578 sensor
    - FSB1-3, 6K: station = channel elevation, so the file alone can't tell which it is.
  We therefore check every elevation in the metadata against an independent ground elevation
  from the USGS Elevation Point Query Service (3DEP DEM, https://epqs.nationalmap.gov).
  The surface elevation is the metadata value closest to the DEM.
  In case of doubt (no metadata value within --tolerance of the DEM) we still use the StationXML
  value, because it is the elevation used in Niemz et al. (2025), and flag the station CHECK.
  (Example: FOR6 in the steep Mineral Mountains, metadata 2421 m vs DEM 2262 m.)

Outputs
  data/input_data/station.dat                      STA LAT LON SENSOR_ELEV(m)
  data/raw_data/stations/stations_corrected.dat    full check table (all candidates, DEM, choice)
The DEM values are cached in stations_corrected.dat; use --refresh to query USGS again.

Station selection
  --max-distance (km) restricts station.dat to stations within that distance of the wellhead of
  injection well 16A(78)-32 (catalog origin). The check table always lists all stations, with
  their distance and whether they were written (column `used`).

Usage
  python create_station_dat.py                      # all 18 stations
  python create_station_dat.py --max-distance 2.5   # only stations within 2.5 km of the wellhead
  python create_station_dat.py --tolerance 15 --refresh
"""
import argparse
import json
import math
import urllib.request
from pathlib import Path

import pandas as pd
from obspy import read_inventory
from obspy.geodetics import gps2dist_azimuth

# Project root = two levels above this file (scripts/py/).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIONXML = PROJECT_ROOT / "data" / "raw_data" / "stations" / "stations.xml"
CHECK_TABLE = PROJECT_ROOT / "data" / "raw_data" / "stations" / "stations_corrected.dat"
STATION_DAT = PROJECT_ROOT / "data" / "input_data" / "station.dat"

# Wellhead of injection well 16A(78)-32 (catalog local-coordinate origin)
WELL_LAT, WELL_LON = 38.50402147, -112.8963897

# Same preference as 01_download_data.py: the instrument whose waveforms we downloaded.
CHANNEL_PRIORITY = ["HH", "GH", "EH", "GN"]

EPQS_URL = "https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Meters&wkid=4326"


def dem_elevation(lat, lon):
    """Ground elevation (m) from the USGS 3DEP point query service."""
    with urllib.request.urlopen(EPQS_URL.format(lat=lat, lon=lon), timeout=60) as r:
        return float(json.load(r)["value"])


def used_channel(sta):
    """First channel of the preferred instrument (the one we downloaded)."""
    for band in CHANNEL_PRIORITY:
        chans = sorted((c for c in sta if c.code.startswith(band)),
                       key=lambda c: (c.location_code, c.code))
        if chans:
            return chans[0]
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tolerance", type=float, default=20.0,
                   help="flag stations whose metadata surface elevation differs from the DEM by more (m)")
    p.add_argument("--refresh", action="store_true",
                   help="query USGS again instead of using cached DEM values")
    p.add_argument("--max-distance", type=float, default=None,
                   help="only write stations within this distance (km) of the wellhead (default: all)")
    args = p.parse_args()

    cached = {}
    if CHECK_TABLE.exists() and not args.refresh:
        old = pd.read_csv(CHECK_TABLE, sep=r"\s+", comment="#")
        cached = dict(zip(old["net"] + "." + old["sta"], old["dem_elev"]))

    rows = []
    for net in read_inventory(str(STATIONXML)):
        for sta in net:
            ch = used_channel(sta)
            key = f"{net.code}.{sta.code}"
            dem = cached.get(key)
            if dem is None or (isinstance(dem, float) and math.isnan(dem)):
                print(f"Querying USGS DEM for {key}")
                dem = dem_elevation(sta.latitude, sta.longitude)

            # Every elevation the metadata gives for this site is a candidate for the surface.
            candidates = {"station": sta.elevation}
            for c in sta:
                candidates.setdefault(f"chan_{c.code[:2]}", c.elevation)
            # In case of doubt, keep the StationXML value (used by Niemz et al.) but flag it.
            src, surface = min(candidates.items(), key=lambda kv: abs(kv[1] - dem))
            doubtful = abs(surface - dem) > args.tolerance
            depth = ch.depth
            sensor = surface - depth
            dist_km = gps2dist_azimuth(WELL_LAT, WELL_LON, sta.latitude, sta.longitude)[0] / 1000
            used = args.max_distance is None or dist_km <= args.max_distance

            rows.append(dict(
                net=net.code, sta=sta.code, cha=ch.code,
                lat=sta.latitude, lon=sta.longitude, dist_km=round(dist_km, 2), depth=depth,
                sta_elev=round(sta.elevation, 1), ch_elev=round(ch.elevation, 1), dem_elev=round(dem, 1),
                surface_elev=round(surface, 1), surface_src=src,
                sensor_elev=round(sensor, 1),
                flag="CHECK" if doubtful else "ok",
                used="yes" if used else "no",
            ))

    df = pd.DataFrame(rows)

    # Labels must be unique (hypoDD: max 7 characters). Station codes alone are unique here.
    assert df["sta"].is_unique and df["sta"].str.len().max() <= 7

    CHECK_TABLE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECK_TABLE, "w") as f:
        f.write("# Station elevation check: StationXML vs USGS 3DEP DEM (epqs.nationalmap.gov)\n")
        f.write(f"# surface_elev = metadata value closest to DEM; CHECK = differs from DEM by more "
                f"than {args.tolerance:g} m (StationXML value kept); sensor_elev = surface_elev - depth. Elevations in m above sea level.\n")
        f.write(f"# dist_km = distance from wellhead 16A(78)-32; used = written to station.dat "
                f"(max distance: {args.max_distance if args.max_distance is not None else 'none'} km)\n")
        f.write(df.to_string(index=False) + "\n")

    STATION_DAT.parent.mkdir(parents=True, exist_ok=True)
    with open(STATION_DAT, "w") as f:
        for r in df[df["used"] == "yes"].itertuples():
            f.write(f"{r.sta:<7s} {r.lat:10.6f} {r.lon:12.6f} {r.sensor_elev:8.1f}\n")

    # Print only the stations written to station.dat (the check table file keeps all of them)
    print(df[df["used"] == "yes"][["net", "sta", "cha", "dist_km", "depth", "sta_elev", "ch_elev",
              "dem_elev", "surface_src", "sensor_elev", "flag"]].to_string(index=False))
    print(f"\nWrote {STATION_DAT} ({(df['used'] == 'yes').sum()} stations)\nWrote {CHECK_TABLE}")


if __name__ == "__main__":
    main()
