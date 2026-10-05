#!/usr/bin/env python
"""
Map of the injection wellhead and the 18 downloaded stations.

Stations within --near-km of the wellhead get their own colour and marker. Default 2.5 km:
this captures the five permanent UU stations used by Niemz et al. (2025) - FORK, FSB3, FSB2,
FSB1, FOR2 (FOR2 is at 2.33 km, just outside 2.3 km) - plus 6K.CS01.
Left panel: all stations (far ones labelled). Right panel: zoom on the near stations.
Coordinates are plotted in km east/north of the wellhead of injection well 16A(78)-32,
the origin of the catalog's local coordinate system.

Input : data/raw_data/stations/stations.xml
Output: figures/station_map.png

Usage
  python plot_stations.py
  python plot_stations.py --near-km 3
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import obspy as obs
import obspy.geodetics as obsgeo

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIONXML = PROJECT_ROOT / "data" / "raw_data" / "stations" / "stations.xml"
OUTFILE = PROJECT_ROOT / "figures" / "station_map.png"

# Wellhead of injection well 16A(78)-32 (catalog local-coordinate origin)
WELL_LAT, WELL_LON = 38.50402147, -112.8963897

# Colours: first two slots of the categorical palette; text stays in neutral ink
NEAR_COLOR, FAR_COLOR = "#2a78d6", "#eb6834"
INK, MUTED = "#0b0b0b", "#52514e"


def station_table(inv):
    """Name, east (km), north (km) and distance (km) from the wellhead for every station."""
    rows = []
    for net in inv:
        for sta in net:
            dist, az, _ = obsgeo.gps2dist_azimuth(WELL_LAT, WELL_LON, sta.latitude, sta.longitude)
            east = dist * np.sin(np.radians(az)) / 1000     # azimuth from north, clockwise
            north = dist * np.cos(np.radians(az)) / 1000
            rows.append((f"{net.code}.{sta.code}", east, north, dist / 1000))
    return rows


def draw(ax, near, far, near_km, label_near):
    """Plot wellhead, near/far stations and the boundary circle on one axis."""
    ax.add_patch(plt.Circle((0, 0), near_km, fill=False, ls="--", lw=1, color=MUTED))
    for group, color, marker, label, labelled in [
            (far, FAR_COLOR, "v", f"≥ {near_km:g} km ({len(far)})", not label_near),
            (near, NEAR_COLOR, "^", f"< {near_km:g} km ({len(near)})", label_near)]:
        ax.scatter([s[1] for s in group], [s[2] for s in group], s=90, marker=marker,
                   color=color, edgecolor="white", linewidth=1.5, label=label, zorder=3)
        if labelled:   # label far stations on the full map, near ones on the zoom
            for name, e, n, d in group:
                ax.annotate(f"{name}\n{d:.1f} km", (e, n), xytext=(6, 4),
                            textcoords="offset points", fontsize=8, color=INK)
    ax.scatter(0, 0, marker="*", s=250, color=INK, zorder=4, label="Wellhead 16A(78)-32")
    ax.set_aspect("equal")
    ax.set_xlabel("East of wellhead (km)", color=INK)
    ax.set_ylabel("North of wellhead (km)", color=INK)
    ax.grid(color="#e6e6e3", lw=0.6)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color("#c8c7c2")
    ax.margins(0.15)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--near-km", type=float, default=2.5,
                   help="distance (km) separating near from far stations")
    args = p.parse_args()

    stations = station_table(obs.read_inventory(str(STATIONXML)))
    near = [s for s in stations if s[3] < args.near_km]
    far = [s for s in stations if s[3] >= args.near_km]

    fig, (ax_all, ax_zoom) = plt.subplots(1, 2, figsize=(15, 7.5),
                                          gridspec_kw={"width_ratios": [1, 1]})
    draw(ax_all, near, far, args.near_km, label_near=False)
    ax_all.set_title("All 18 stations", color=INK)
    draw(ax_zoom, near, far, args.near_km, label_near=True)
    lim = args.near_km + 0.7
    ax_zoom.set_xlim(-lim, lim)
    ax_zoom.set_ylim(-lim, lim)
    ax_zoom.set_title(f"Zoom: within {lim:g} km of the wellhead", color=INK)
    ax_all.legend(loc="lower left", frameon=False)
    fig.suptitle("Utah FORGE: downloaded stations (UU + 6K)", color=INK, fontsize=14)

    OUTFILE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTFILE, dpi=150, bbox_inches="tight")
    print(f"Wrote {OUTFILE}")
    for name, e, n, d in sorted(stations, key=lambda s: s[3]):
        print(f"  {name:9s} {d:5.1f} km  {'near' if d < args.near_km else 'far'}")


if __name__ == "__main__":
    main()
