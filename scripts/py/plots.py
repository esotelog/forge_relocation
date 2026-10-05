"""
Plotting helpers for the notebooks.

Use from a notebook in notebooks/:
    import sys
    sys.path.append("../scripts/py")
    import plots

    plots.plot_station_picks(st_pn, picks, origin, "CS01")   # one station, static figure

    %matplotlib widget                                        # interactive backend (ipympl)
    plots.browse_picks(st_pn, picks, origin)                  # click the plot or press a key: next station
    %matplotlib inline                                        # back to normal static plots afterwards

    reloc = hdd.read_reloc()                                  # hypoDD output (import HypoDD as hdd)
    plots.plot_relocation(cat, reloc)                         # catalog vs hypoDD: map + 2 sections
"""
import matplotlib.pyplot as plt
from IPython.display import display

PHASE_COLORS = {"P": "#2a78d6", "S": "#eb6834"}   # P blue, S orange


def draw_station_picks(fig, st, picks, origin, station, tmin=-5, tmax=15, title=""):
    """
    Draw the components of one station with its picks (vertical lines) into figure `fig`.

    st      : ObsPy Stream (raw or pre-processed) of one event
    picks   : DataFrame with columns station, phase, t_rel (s after origin), prob
    origin  : event origin time (UTCDateTime); time axis = seconds after origin
    """
    fig.clear()                                     # reuse the same figure (browse_picks)
    st_sta = st.select(station=station)
    sta_picks = picks[picks["station"] == station]
    # Only picks inside the plotted window: labels of picks outside it (e.g. the false P at
    # -4.9 s when zoomed in) would otherwise be drawn outside the axes.
    shown = sta_picks[(sta_picks["t_rel"] >= tmin) & (sta_picks["t_rel"] <= tmax)]

    axes = fig.subplots(len(st_sta), 1, sharex=True, squeeze=False)[:, 0]
    for ax, tr in zip(axes, st_sta):
        ax.plot(tr.times(reftime=origin), tr.data, color="k", lw=0.5)
        ax.set_ylabel(tr.stats.channel)
        for pk in shown.itertuples():               # one vertical line per pick
            color = PHASE_COLORS.get(pk.phase, "gray")
            ax.axvline(pk.t_rel, color=color, lw=1.5)
            ax.text(pk.t_rel, 0.95, f" {pk.phase} {pk.prob:.2f}", color=color,
                    transform=ax.get_xaxis_transform(), va="top", fontsize=9, clip_on=True)
    axes[-1].set_xlim(tmin, tmax)
    axes[-1].set_xlabel("time after origin (s)")
    axes[0].set_title(f"{st_sta[0].stats.network}.{station}  {title}  "
                      f"({len(shown)} of {len(sta_picks)} picks in window)")
    fig.tight_layout()
    fig.canvas.draw_idle()                          # refresh the figure on screen


FIGSIZE = (9, 5)                                   # default figure size (inches): width, height


def plot_station_picks(st, picks, origin, station, tmin=-5, tmax=15, title="", figsize=FIGSIZE):
    """One station in a new (static) figure. Shown once; returns nothing (a returned figure
    would be displayed a second time by Jupyter)."""
    plt.close("all")                                # close any figures left from earlier calls
    with plt.ioff():                                # don't auto-display while building it
        fig = plt.figure(figsize=figsize)
    draw_station_picks(fig, st, picks, origin, station, tmin, tmax, title)
    display(fig)                                    # show exactly once
    plt.close(fig)


def browse_picks(st, picks, origin, stations=None, tmin=-5, tmax=15, title="", figsize=FIGSIZE):
    """
    One figure; a mouse click on the plot or any key press shows the next station.
    Needs the interactive backend: run `%matplotlib widget` in the notebook first.

    stations : list of station codes in the order to show (default: alphabetical, all in `st`)
    figsize  : (width, height) in inches, e.g. (8, 4) for a smaller figure
    """
    if stations is None:
        stations = sorted({tr.stats.station for tr in st})
    plt.close("all")                                # close any figures left from earlier calls
    with plt.ioff():                                # don't auto-display on creation
        fig = plt.figure(figsize=figsize)
    if hasattr(fig.canvas, "header_visible"):      # ipympl: hide the "Figure 1" header bar
        fig.canvas.header_visible = False
    state = {"i": 0}                                # index of the station on screen

    def show():
        i = state["i"]
        draw_station_picks(fig, st, picks, origin, stations[i], tmin, tmax,
                           f"{title}  [{i + 1}/{len(stations)}]  click / key: next")

    def next_station(event):
        state["i"] = (state["i"] + 1) % len(stations)   # after the last station, start again
        show()

    fig.canvas.mpl_connect("button_press_event", next_station)   # mouse click on the plot
    fig.canvas.mpl_connect("key_press_event", next_station)      # any key (click the plot first)
    show()
    display(fig.canvas)                             # show the interactive figure exactly once


# Wellhead of injection well 16A(78)-32: origin of the local coordinates (km east/north)
WELL_LAT, WELL_LON = 38.50402147, -112.8963897
CAT_COLOR, DD_COLOR = "#9a9993", "#2a78d6"            # catalog grey, hypoDD blue


def _to_local_km(lat, lon):
    """lat/lon (deg) -> km east and north of the wellhead (flat-earth approximation, fine at km scale)."""
    import numpy as np
    north = (np.asarray(lat) - WELL_LAT) * 111.195
    east = (np.asarray(lon) - WELL_LON) * 111.195 * np.cos(np.radians(WELL_LAT))
    return east, north


def plot_relocation(cat, reloc, same_events=True, size=4, figsize=(13, 9), title=""):
    """
    Catalog vs hypoDD locations: map view, east-west section, north-south section.

    cat         : catalog (phase_pick.load_catalog()); depth[m_local] = m below the wellhead
    reloc       : hypoDD output from HypoDD.read_reloc() (depth_well_km = km below the wellhead)
    same_events : True = plot only catalog events that hypoDD relocated (fair comparison)
    Coordinates: km east / north of the wellhead (both from lat/lon); depth: km below the wellhead.
    """
    c = cat.loc[cat.index.isin(reloc.event_id)] if same_events else cat
    ce, cn = _to_local_km(c["lat"], c["lon"])
    cz = c["depth[m_local]"] / 1000
    re, rn = _to_local_km(reloc["LAT"], reloc["LON"])
    rz = reloc["depth_well_km"]

    plt.close("all")
    with plt.ioff():
        fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.3, 1])
    ax_map = fig.add_subplot(gs[0, 0])
    ax_ns = fig.add_subplot(gs[0, 1], sharey=ax_map)        # north-south section: depth vs north
    ax_ew = fig.add_subplot(gs[1, 0], sharex=ax_map)        # east-west section: east vs depth

    kw_c = dict(s=size, color=CAT_COLOR, alpha=0.6, lw=0, label=f"catalog ({len(c)})")
    kw_r = dict(s=size, color=DD_COLOR, alpha=0.7, lw=0, label=f"hypoDD ({len(reloc)})")
    ax_map.scatter(ce, cn, **kw_c); ax_map.scatter(re, rn, **kw_r)
    ax_map.plot(0, 0, "k*", ms=12, label="wellhead 16A")
    ax_map.set(xlabel="East of wellhead (km)", ylabel="North of wellhead (km)", title="Map view")
    ax_map.set_aspect("equal", adjustable="box")    # 1 km east = 1 km north
    leg = ax_map.legend(loc="lower left", fontsize=8)
    for h in leg.legend_handles[:2]:                     # bigger dots in the legend only
        h.set_sizes([25])

    ax_ew.scatter(ce, cz, **kw_c); ax_ew.scatter(re, rz, **kw_r)
    ax_ew.set(xlabel="East of wellhead (km)", ylabel="Depth below wellhead (km)",
              title="East-west section (looking north)")
    ax_ew.invert_yaxis()

    ax_ns.scatter(cz, cn, **kw_c); ax_ns.scatter(rz, rn, **kw_r)
    ax_ns.set(xlabel="Depth below wellhead (km)", ylabel="North of wellhead (km)",
              title="North-south section (looking east)")

    for ax in (ax_map, ax_ew, ax_ns):
        ax.grid(color="#e6e6e3", lw=0.6)
    fig.suptitle(title or "Catalog (Niemz et al. 2025) vs hypoDD relocations")
    fig.tight_layout()
    display(fig)
    plt.close(fig)
