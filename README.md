# IEEE 13-Node Test Feeder in OpenDSS

A complete, runnable OpenDSS model of the IEEE 13-node test feeder, with heavily
commented source so it doubles as a tutorial on **how to write OpenDSS code**.

| File | Purpose |
|------|---------|
| `IEEE13Nodeckt.dss` | Master script: circuit, transformers, regulators, lines, loads, capacitors, and the solve command |
| `IEEELineCodes.dss` | Line impedance / capacitance matrices referenced by the lines |
| `plot_voltage_profile.py` | Solves the model and dumps the voltage profile to CSV + PNG |

## Running it

**OpenDSS GUI / command line**

```
Redirect IEEE13Nodeckt.dss
Show Voltages LN Nodes
```

**Python** (`pip install OpenDSSDirect.py`)

```python
import opendssdirect as dss
dss.Command('Redirect IEEE13Nodeckt.dss')
print('Converged:', dss.Solution.Converged())
```

Expected result: the solution converges in ~11 iterations with total feeder
power ≈ 3.6 MW / 1.7 Mvar, losses ≈ 112 kW, and bus voltages between about
0.96 and 1.04 pu — matching the published IEEE 13-node benchmark.

## Plotting the voltage profile

`plot_voltage_profile.py` solves the model and writes two files:

- `voltage_profile.csv` — one row per energized node (bus, phase, base kV,
  pu magnitude, angle, distance from the substation)
- `voltage_profile.png` — per-unit voltage vs. distance, one series per phase,
  with the ANSI 0.95–1.05 pu band shaded

```bash
pip install OpenDSSDirect.py matplotlib
python plot_voltage_profile.py           # or: python plot_voltage_profile.py path/to/IEEE13Nodeckt.dss
```

It attaches an `EnergyMeter` at the head of the feeder (required for OpenDSS to
compute per-bus distances), re-solves, and prints a one-line summary. The plot
makes the feeder's phase unbalance obvious: phase B rides high while phase C
sags toward 0.96 pu at the feeder ends.

---

## How to write OpenDSS code for a feeder — the recipe

OpenDSS is a script-driven, object-oriented power-flow engine. You build a
circuit by declaring **elements** with `New Class.Name property=value ...`.
Follow this order and every distribution model falls into place:

### 1. Housekeeping
```
Clear
Set DefaultBaseFrequency=60
```
`Clear` wipes any previous circuit; set the system frequency (60 Hz in NA).

### 2. Define the circuit and its source
Every model has exactly one `Circuit`, which creates the grid equivalent
(`Vsource`) at a bus you name.
```
New Circuit.MyFeeder basekv=115 phases=3 bus1=SourceBus MVAsc3=20000 MVASC1=21000
```
`basekv` is line-to-line kV; `MVAsc3`/`MVASC1` set how "stiff" (strong) the
grid is behind the source.

### 3. Add power-delivery elements (series path)
- **Transformers** — `New Transformer.Name` with one `wdg=` block per winding,
  each giving its `bus`, `conn` (wye/delta), `kv`, `kva`, and `%r`; `XHL` is the
  leakage reactance.
- **Regulators** — a low-impedance transformer plus a `RegControl` that moves
  taps to hold a target voltage (`vreg`) within a `band`, using PT/CT ratios and
  line-drop compensation `R`/`X`.
- **Lines** — reference a **LineCode** (reusable R/X/C matrices) and a `Length`.
  Write phases explicitly on the bus name to model unbalance, e.g. `Bus1=632.3.2`
  connects only phases 3 and 2. A switch is just a short line with `Switch=y`.

### 4. Line codes (impedance data)
Store per-length matrices once and reuse them:
```
New linecode.601 nphases=3 units=mi
~ rmatrix = (r11 | r21 r22 | r31 r32 r33)   ! lower-triangular, ohms/mi
~ xmatrix = (...)
~ cmatrix = (...)                            ! nF/mi
```
The leading `~` continues the previous `New`/`Edit` command onto a new line.

### 5. Add shunt elements (loads, capacitors, generators)
```
New Load.671 Bus1=671.1.2.3 Phases=3 Conn=Delta Model=1 kV=4.16 kW=1155 kvar=660
New Capacitor.Cap1 Bus1=675 phases=3 kVAR=600 kV=4.16
```
Key load knobs: `Conn` (Wye/Delta) and `Model` — `1` = constant power (PQ),
`2` = constant impedance (Z), `5` = constant current (I). For a 1-phase wye
load, `kV` is line-to-neutral; otherwise it is line-to-line.

### 6. Set voltage bases and solve
```
Set VoltageBases=[115, 4.16, 0.48]   ! every nominal L-L kV level in the model
CalcVoltageBases                     ! propagate bases to all buses
Solve                                ! default = snapshot power flow
```

### 7. Report
```
Show Voltages LN Nodes
Show Powers kVA Elements
Show Taps
Show Losses
```

### Syntax reminders
- Commands are **case-insensitive**; `!` starts a comment.
- `~` = "continue the last command" (used for long element definitions).
- Bus nodes: `bus.a.b.c` picks phases; `.0` is neutral/ground.
- `Redirect file.dss` runs another script; `Compile` does the same but also
  changes the working directory to that file's folder.

---

## Feeder at a glance

- 4.16 kV unbalanced feeder fed from a 115 kV source through a 5 MVA substation
  transformer at node 650.
- Three single-phase LTC regulators (node 650 → RG60).
- Overhead and underground lines, 1/2/3-phase, defined by line codes 601–607.
- An in-line 500 kVA 4.16/0.48 kV transformer (633 → 634).
- Unbalanced spot loads (wye & delta; constant P, Z, and I models).
- Two shunt capacitor banks (675 and 611) and one closed switch (671–692).

## References

- IEEE PES Distribution Test Feeders: <https://cmte.ieee.org/pes-testfeeders/resources/>
- OpenDSS (EPRI): <https://www.epri.com/pages/sa/opendss>
