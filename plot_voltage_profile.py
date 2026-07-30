#!/usr/bin/env python3
"""
Solve the IEEE 13-node feeder and dump / plot its voltage profile.

Outputs (written next to this script):
  - voltage_profile.csv : per-node results (bus, phase, base kV, pu magnitude, angle, distance)
  - voltage_profile.png : per-unit voltage vs. distance from the substation, one series per phase

Usage:
    python plot_voltage_profile.py [path/to/IEEE13Nodeckt.dss]

Requires: OpenDSSDirect.py, matplotlib
    pip install OpenDSSDirect.py matplotlib
"""

import csv
import sys
from pathlib import Path

import opendssdirect as dss

# matplotlib is only needed for the PNG; the CSV works without it.
try:
    import matplotlib
    matplotlib.use("Agg")  # headless backend so it runs on a server / CI
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False

HERE = Path(__file__).resolve().parent
PHASE_COLORS = {1: "tab:blue", 2: "tab:orange", 3: "tab:green"}
PHASE_LABELS = {1: "Phase A", 2: "Phase B", 3: "Phase C"}


def solve(model_path: Path) -> None:
    """Compile the model, attach an EnergyMeter (needed for bus distances), and solve."""
    dss.Text.Command("Clear")
    dss.Text.Command(f'Redirect "{model_path}"')
    # Bus.Distance() is only populated when an EnergyMeter defines the feeder tree.
    # Place one at the head of the feeder (first line out of the regulator bus) and
    # re-solve so the radial distances propagate to every bus.
    dss.Text.Command("New EnergyMeter.Feeder element=Line.650632 terminal=1")
    dss.Text.Command("Set Maxiterations=20")
    dss.Text.Command("Solve")
    if not dss.Solution.Converged():
        raise RuntimeError("Power flow did not converge.")


def collect_profile() -> list[dict]:
    """Return one record per energized node: bus, phase, base kV, pu V, angle, distance."""
    records = []
    for bus in dss.Circuit.AllBusNames():
        dss.Circuit.SetActiveBus(bus)
        base_kv = dss.Bus.kVBase()          # line-neutral kV base
        distance = dss.Bus.Distance()        # miles from the energy source
        nodes = dss.Bus.Nodes()              # phase numbers present at this bus
        vmag_pu = dss.Bus.puVmagAngle()[0::2]
        vang = dss.Bus.puVmagAngle()[1::2]
        for node, vpu, ang in zip(nodes, vmag_pu, vang):
            if node == 0:                    # skip neutral / ground
                continue
            records.append(
                {
                    "bus": bus,
                    "phase": node,
                    "base_kv_ln": round(base_kv, 4),
                    "vmag_pu": round(vpu, 5),
                    "vang_deg": round(ang, 3),
                    "distance_mi": round(distance, 5),
                }
            )
    return records


def write_csv(records: list[dict], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["bus", "phase", "base_kv_ln", "vmag_pu", "vang_deg", "distance_mi"],
        )
        writer.writeheader()
        writer.writerows(records)


def print_summary(records: list[dict]) -> None:
    tp = dss.Circuit.TotalPower()            # kW, kvar delivered by the source (negative = into feeder)
    losses = dss.Circuit.Losses()            # W, var
    vmags = [r["vmag_pu"] for r in records]
    print(f"Converged        : {dss.Solution.Converged()} "
          f"({dss.Solution.Iterations()} iterations)")
    print(f"Total load power : {-tp[0]:.1f} kW  {-tp[1]:.1f} kvar")
    print(f"Total losses     : {losses[0] / 1000:.2f} kW  {losses[1] / 1000:.2f} kvar")
    print(f"Voltage range    : {min(vmags):.4f} - {max(vmags):.4f} pu "
          f"across {len(records)} nodes")


def plot_profile(records: list[dict], path: Path) -> None:
    if not HAVE_MPL:
        print("matplotlib not installed - skipping PNG (CSV still written).")
        return
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for phase in (1, 2, 3):
        pts = sorted(
            ((r["distance_mi"], r["vmag_pu"], r["bus"]) for r in records if r["phase"] == phase),
            key=lambda t: t[0],
        )
        if not pts:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, "o-", color=PHASE_COLORS[phase], label=PHASE_LABELS[phase])
        for x, y, bus in pts:
            ax.annotate(bus, (x, y), textcoords="offset points", xytext=(0, 6),
                        fontsize=7, ha="center", color=PHASE_COLORS[phase])

    ax.axhspan(0.95, 1.05, color="green", alpha=0.06, label="ANSI 0.95-1.05 pu")
    ax.axhline(1.0, color="grey", lw=0.8, ls="--")
    ax.set_xlabel("Distance from substation (miles)")
    ax.set_ylabel("Voltage magnitude (pu)")
    ax.set_title("IEEE 13-Node Test Feeder - Voltage Profile")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    print(f"Wrote {path}")


def main() -> int:
    model_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "IEEE13Nodeckt.dss"
    if not model_path.exists():
        print(f"Model file not found: {model_path}", file=sys.stderr)
        return 1

    solve(model_path)
    records = collect_profile()
    print_summary(records)

    csv_path = HERE / "voltage_profile.csv"
    png_path = HERE / "voltage_profile.png"
    write_csv(records, csv_path)
    print(f"Wrote {csv_path}")
    plot_profile(records, png_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
