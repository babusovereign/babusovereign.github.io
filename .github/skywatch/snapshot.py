#!/usr/bin/env python3
"""
SkyWatch snapshot builder (runs in GitHub Actions every 30 minutes).

Data sources (openly licensed, no keys, no paid services):
  - Aircraft positions: adsb.lol API  — Open Database License (ODbL) 1.0
  - Routes + airports:  Virtual Radar Server standing data — CC0 1.0 (public domain)

Privacy: aircraft flagged PIA (privacy ICAO address) or LADD (FAA "limit aircraft data displayed")
are dropped entirely; registrations and owner/operator fields are never stored.

Output: snapshot.json (compact). Usage: python3 snapshot.py <standing-data dir> <out file>
"""
import csv, json, math, re, sys, time, urllib.error, urllib.request
from pathlib import Path

UA = {"User-Agent": "SkyWatch snapshot for babusovereign.com (contact via github.com/babusovereign)"}
PIA, LADD, MIL = 4, 8, 1
HEX_RE = re.compile(r"~?[0-9a-f]{6}")  # ICAO 24-bit address (TIS-B prefixed with ~); hex lands in DOM attributes client-side
RADIUS = 250  # nm (adsb.lol maximum)
# Busy airspace, roughly 6-8 degrees apart; overlapping circles are de-duplicated by transponder id.
REGIONS = [
    # North America
    (42.0, -72.0), (38.6, -77.5), (33.6, -84.4), (28.2, -81.6), (41.9, -87.7), (44.9, -93.2), (39.8, -104.7),
    (32.9, -97.0), (29.8, -95.3), (33.4, -112.0), (36.1, -115.2), (34.0, -118.3), (37.6, -122.3), (47.5, -122.3),
    (45.5, -73.6), (43.7, -79.6), (49.2, -123.2), (19.4, -99.1), (21.3, -157.9), (61.2, -149.9),
    # Europe
    (51.5, -0.5), (48.9, 2.5), (50.1, 8.6), (52.3, 4.8), (40.5, -3.6), (41.8, 12.3), (47.5, 11.5),
    (55.6, 12.6), (52.2, 21.0), (41.1, 28.8), (37.9, 23.9), (53.4, -6.3), (59.6, 17.9), (60.3, 24.9),
    # Middle East, Africa, Asia, Oceania, South America
    (25.2, 55.4), (30.1, 31.4), (28.6, 77.1), (19.1, 72.9), (13.7, 100.7), (1.4, 104.0), (22.3, 114.0),
    (31.1, 121.6), (39.9, 116.6), (35.6, 139.8), (37.5, 126.5), (-33.9, 151.2), (-37.7, 144.8),
    (-23.4, -46.5), (-34.8, -58.5), (-26.1, 28.2), (6.5, 3.3),
]


def get(url, tries=4):
    """Fetch JSON. On HTTP 429, wait as long as the server asks (Retry-After), else back off 15/30/60 s."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as ex:
            wait = 15 * 2 ** i
            if ex.code == 429:
                try:
                    wait = max(wait, min(120, int(ex.headers.get("Retry-After") or 0)))
                except ValueError:
                    pass
            print(f"  {url} failed (HTTP {ex.code}); retry {i + 1} in {wait}s", flush=True)
        except Exception as ex:  # noqa: BLE001
            wait = 10 * (i + 1)
            print(f"  {url} failed ({ex}); retry {i + 1} in {wait}s", flush=True)
        if i < tries - 1:
            time.sleep(wait)
    return None


def load_routes(sd):
    routes = {}
    for f in (sd / "routes" / "schema-01").rglob("*.csv"):
        with f.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                cs, codes = row.get("Callsign"), row.get("AirportCodes")
                if cs and codes:
                    routes[cs.strip()] = codes.strip()
    return routes


def load_airports(sd):
    apts = {}
    for f in (sd / "airports" / "schema-01").rglob("*.csv"):
        with f.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                try:
                    apts[row["Code"]] = (row["Name"], row["IATA"], row["Location"], row["CountryISO2"],
                                         float(row["Latitude"]), float(row["Longitude"]))
                except (KeyError, ValueError):
                    pass
    return apts


def xtrack_nm(p, a, b):
    """Distance (nm) from point p to the great-circle segment a→b (approximate)."""
    R = 3440.065
    def rad(x): return [math.radians(x[0]), math.radians(x[1])]
    def dist(u, v):
        u, v = rad(u), rad(v)
        return 2 * R * math.asin(math.sqrt(math.sin((v[0] - u[0]) / 2) ** 2 + math.cos(u[0]) * math.cos(v[0]) * math.sin((v[1] - u[1]) / 2) ** 2))
    def brg(u, v):
        u, v = rad(u), rad(v)
        y = math.sin(v[1] - u[1]) * math.cos(v[0])
        x = math.cos(u[0]) * math.sin(v[0]) - math.sin(u[0]) * math.cos(v[0]) * math.cos(v[1] - u[1])
        return math.atan2(y, x)
    d_ap, d_ab = dist(a, p), dist(a, b)
    if d_ab < 1:
        return d_ap
    xt = abs(math.asin(max(-1, min(1, math.sin(d_ap / R) * math.sin(brg(a, p) - brg(a, b)))))) * R
    at = math.acos(max(-1, min(1, math.cos(d_ap / R) / max(1e-9, math.cos(xt / R))))) * R
    if math.cos(brg(a, p) - brg(a, b)) < 0 or at > d_ab:   # beyond the ends → distance to nearest endpoint
        return min(d_ap, dist(b, p))
    return xt


def main():
    sd, out = Path(sys.argv[1]), Path(sys.argv[2])
    routes, apts = load_routes(sd), load_airports(sd)
    print(f"{len(routes):,} routes, {len(apts):,} airports loaded", flush=True)

    seen, now, missed = {}, int(time.time()), []
    for lat, lon in REGIONS:
        d = get(f"https://api.adsb.lol/v2/point/{lat}/{lon}/{RADIUS}")
        time.sleep(3)                         # be gentle with a free community API
        if not d:
            missed.append(f"{lat},{lon}")
            continue
        now = int((d.get("now") or now * 1000) / 1000)
        for a in d.get("ac") or []:
            if a.get("lat") is None or a.get("lon") is None or (a.get("dbFlags") or 0) & (PIA | LADD):
                continue
            if not HEX_RE.fullmatch(str(a.get("hex") or "")):
                continue
            if a["hex"] in seen and (seen[a["hex"]].get("seen_pos") or 99) <= (a.get("seen_pos") or 99):
                continue
            seen[a["hex"]] = a
    print(f"{len(seen):,} aircraft after de-dup and privacy filter", flush=True)
    print(f"regions fetched: {len(REGIONS) - len(missed)}/{len(REGIONS)}"
          + (f"; skipped after retries: {' '.join(missed)}" if missed else ""), flush=True)

    route_ix, route_list, used_apts, flights = {}, [], {}, []
    for a in seen.values():
        cs = (a.get("flight") or "").strip()
        ground = a.get("alt_baro") == "ground"
        alt = 0 if ground else a.get("alt_baro") if isinstance(a.get("alt_baro"), (int, float)) else a.get("alt_geom")
        ri, ok = -1, 0
        codes = routes.get(cs) if len(cs) >= 4 and cs[:3].isalpha() and cs[3].isdigit() else None
        if codes:
            legs = [c for c in codes.split("-") if c in apts]
            if len(legs) >= 2:
                p = (a["lat"], a["lon"])
                near = min(xtrack_nm(p, apts[legs[i]][4:6], apts[legs[i + 1]][4:6]) for i in range(len(legs) - 1))
                ok = 1 if near <= 250 else 0
                key = "-".join(legs)
                if key not in route_ix:
                    route_ix[key] = len(route_list); route_list.append(key)
                    for c in legs:
                        n, iata, city, cc, _, _ = apts[c]
                        used_apts[c] = [n, iata, city, cc]
                ri = route_ix[key]
        flights.append([
            a["hex"], cs or a["hex"].upper(), round(a["lat"], 3), round(a["lon"], 3),
            None if alt is None else int(alt), 1 if ground else 0,
            None if a.get("gs") is None else round(a["gs"]), round(a.get("track") or a.get("true_heading") or 0),
            a.get("baro_rate") if a.get("baro_rate") is not None else a.get("geom_rate"),
            a.get("t"), ri, ok, 1 if (a.get("dbFlags") or 0) & MIL else 0,
        ])

    snap = {
        "t": now, "generated": int(time.time()),
        "source": "adsb.lol", "license": "Flight data © adsb.lol contributors, ODbL 1.0. Routes and airports: Virtual Radar Server standing data, CC0.",
        "fields": ["hex", "callsign", "lat", "lon", "alt_ft", "ground", "gs_kt", "track", "vrate_fpm", "type", "route", "route_plausible", "military"],
        "regions": [[la, lo, RADIUS] for la, lo in REGIONS],
        "routes": route_list, "airports": used_apts, "flights": flights,
    }
    out.write_text(json.dumps(snap, separators=(",", ":")))
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB): {len(flights):,} aircraft, {len(route_list):,} routes, "
          f"{sum(1 for f in flights if f[10] >= 0):,} with a route", flush=True)


if __name__ == "__main__":
    main()
