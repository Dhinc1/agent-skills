# Electrical — Takeoff Coverage Checklist

A **starting-point** coverage list for a electrical takeoff: the quantities a complete electrical BOQ usually needs. It exists to stop the takeoff under-extracting — work through every category here and decide, for *this* project, whether each line is present, absent, or needs splitting. **It is not exhaustive.** Real drawings always carry items no generic list anticipates, so after working through this, scan the actual sheets and schedules for anything extra and add it.

## How to use this list

- **Don't skip a category because it looks irrelevant** — check it against the drawings first. A category with nothing on the drawings becomes a one-line note ("no [category] in scope"), not a silent omission.
- **These are the PRIMARY quantities** — the things you measure or count directly. Each becomes a line on Tab 1 (Primary Quantities). Everything else (the components, consumables, labour, plant) is a **secondary**, derived from the primary by the assembly — see the worked example at the foot of this file and `../derivation_library.md`.
- **Split a line only where it changes the result** — by type, size, grade, or installation method (e.g. a light fixed off a ladder vs. the same light off a scissor lift). The `(size: ___)` / `(dia: ___)` placeholders mark exactly the splits that usually matter on this trade; fill them from the schedule.
- **Always land a quantity, even low-confidence.** If an item is clearly present but hard to measure precisely, estimate it off the building footprint / a count × a rate / a perimeter and flag it **Low** with the basis in the notes — never leave it blank. (But never fabricate a quantity the drawings don't contain — see SKILL.md "Honesty about confidence".)

## Coverage checklist — Electrical


### CABLE CONTAINMENT

| Item | Unit | Measurement type |
|---|---|---|
| Cable tray - heavy duty (width: ___mm) | LM | Linear (measure runs) |
| Cable tray - medium duty (width: ___mm) | LM | Linear (measure runs) |
| Cable tray - light duty (width: ___mm) | LM | Linear (measure runs) |
| Cable ladder (width: ___mm) | LM | Linear (measure runs) |
| Cable tray bends / tees / crosses | No. | Count (off plan/schedule, once) |
| Cable tray risers / drops | No. | Count (off plan/schedule, once) |
| Cable tray supports / brackets | No. | Count (off plan/schedule, once) |
| Basket tray | LM | Linear (measure runs) |

### CONDUIT & TRUNKING

| Item | Unit | Measurement type |
|---|---|---|
| Galvanised steel conduit - 20mm | LM | Linear (measure runs) |
| Galvanised steel conduit - 25mm | LM | Linear (measure runs) |
| Galvanised steel conduit - 32mm | LM | Linear (measure runs) |
| PVC conduit - 20mm | LM | Linear (measure runs) |
| PVC conduit - 25mm | LM | Linear (measure runs) |
| Underground conduit (HDPE/uPVC) - 50mm | LM | Linear (measure runs) |
| Underground conduit (HDPE/uPVC) - 100mm | LM | Linear (measure runs) |
| Underground conduit (HDPE/uPVC) - 150mm | LM | Linear (measure runs) |
| Cable trunking (___mm x ___mm) | LM | Linear (measure runs) |
| Conduit junction boxes | No. | Count (off plan/schedule, once) |
| Draw pits / manholes | No. | Count (off plan/schedule, once) |

### CABLES

| Item | Unit | Measurement type |
|---|---|---|
| LV power cable - single core (___mm²) | LM | Linear (measure runs) |
| LV power cable - multicore (___mm²) | LM | Linear (measure runs) |
| HV cable (___kV, ___mm²) | LM | Linear (measure runs) |
| Control cable | LM | Linear (measure runs) |
| Data / comms cable (Cat6/Cat6A) | LM | Linear (measure runs) |
| Fibre optic cable | LM | Linear (measure runs) |
| Fire alarm cable | LM | Linear (measure runs) |
| Armoured cable | LM | Linear (measure runs) |
| Cable terminations / glands | No. | Count (off plan/schedule, once) |

### LIGHTING

| Item | Unit | Measurement type |
|---|---|---|
| LED panel light (600x600) | No. | Count (off plan/schedule, once) |
| LED downlight | No. | Count (off plan/schedule, once) |
| LED batten / linear luminaire | No. | Count (off plan/schedule, once) |
| High bay luminaire | No. | Count (off plan/schedule, once) |
| Bulkhead / wall-mounted light | No. | Count (off plan/schedule, once) |
| External / floodlight | No. | Count (off plan/schedule, once) |
| Emergency luminaire (maintained) | No. | Count (off plan/schedule, once) |
| Emergency luminaire (non-maintained) | No. | Count (off plan/schedule, once) |
| Exit sign luminaire | No. | Count (off plan/schedule, once) |
| Lighting control sensor / PIR | No. | Count (off plan/schedule, once) |
| Dimmer / lighting control module | No. | Count (off plan/schedule, once) |

### SWITCHBOARDS & DISTRIBUTION

| Item | Unit | Measurement type |
|---|---|---|
| Main switchboard (MSB) | No. | Count (off plan/schedule, once) |
| Sub-main distribution board (SMDB) | No. | Count (off plan/schedule, once) |
| Final distribution board (DB) | No. | Count (off plan/schedule, once) |
| Automatic transfer switch (ATS) | No. | Count (off plan/schedule, once) |
| Capacitor bank / PFC unit | No. | Count (off plan/schedule, once) |
| Transformer (kVA: ___) | No. | Count (off plan/schedule, once) |
| UPS system (kVA: ___) | No. | Count (off plan/schedule, once) |
| Generator (kVA: ___) | No. | Count (off plan/schedule, once) |

### POWER OUTLETS & ACCESSORIES

| Item | Unit | Measurement type |
|---|---|---|
| Single GPO (general power outlet) | No. | Count (off plan/schedule, once) |
| Double GPO | No. | Count (off plan/schedule, once) |
| Floor box / service outlet | No. | Count (off plan/schedule, once) |
| Weatherproof GPO (IP56) | No. | Count (off plan/schedule, once) |
| Dedicated outlet (equipment) | No. | Count (off plan/schedule, once) |
| 20A/32A industrial outlet | No. | Count (off plan/schedule, once) |
| Isolator switch | No. | Count (off plan/schedule, once) |
| Connection to mechanical equipment | No. | Count (off plan/schedule, once) |
| Connection to BMS | No. | Count (off plan/schedule, once) |

### FIRE DETECTION & ALARM

| Item | Unit | Measurement type |
|---|---|---|
| Smoke detector (photoelectric) | No. | Count (off plan/schedule, once) |
| Heat detector | No. | Count (off plan/schedule, once) |
| Beam detector | No. | Count (off plan/schedule, once) |
| Manual call point (MCP/break glass) | No. | Count (off plan/schedule, once) |
| Fire alarm sounder / horn | No. | Count (off plan/schedule, once) |
| Fire alarm strobe / beacon | No. | Count (off plan/schedule, once) |
| Speaker (EWIS/voice evacuation) | No. | Count (off plan/schedule, once) |
| Fire alarm panel (FACP) | No. | Count (off plan/schedule, once) |
| Fire door hold-open device | No. | Count (off plan/schedule, once) |

### DATA & COMMUNICATIONS

| Item | Unit | Measurement type |
|---|---|---|
| Data outlet (single) | No. | Count (off plan/schedule, once) |
| Data outlet (double) | No. | Count (off plan/schedule, once) |
| Patch panel (24-port) | No. | Count (off plan/schedule, once) |
| Comms rack / cabinet | No. | Count (off plan/schedule, once) |
| WAP (wireless access point) | No. | Count (off plan/schedule, once) |
| CCTV camera | No. | Count (off plan/schedule, once) |
| Intercom / door station | No. | Count (off plan/schedule, once) |
| Access control reader | No. | Count (off plan/schedule, once) |
| PA speaker | No. | Count (off plan/schedule, once) |

### EARTHING & LIGHTNING PROTECTION

| Item | Unit | Measurement type |
|---|---|---|
| Earth electrode / rod | No. | Count (off plan/schedule, once) |
| Earth bar | No. | Count (off plan/schedule, once) |
| Earth conductor (bare copper) | LM | Linear (measure runs) |
| Earth pit / inspection chamber | No. | Count (off plan/schedule, once) |
| Lightning protection air terminal | No. | Count (off plan/schedule, once) |
| Lightning down conductor | LM | Linear (measure runs) |
| Equipotential bonding | No. | Count (off plan/schedule, once) |

## Worked assembly — how one primary expands into secondaries

This is the pattern every line above follows: you measure/count the **primary (P)** once, and the assembly multiplies it out into the components, consumables, labour, and plant — each a *ratio × primary*. Volume secondaries are always `area × depth`. Replicate this shape for every primary in the takeoff; the full library of ratios lives in `../derivation_library.md` and the source spreadsheets.

**Primary:** LED panel light 600x600 complete — *No.* (measured/counted directly)

| Secondary component | Unit | Ratio / primary | Trade | Note |
|---|---|---|---|---|
| Mounting clips / spring kit | Set | 1 | Electrical | 4x clips per fitting |
| Ceiling tile support frame (if req'd) | No. | 0.5 | Electrical | Assume 50% need frame |
| Junction box (round/loop-in) | No. | 1 | Electrical | JB per fitting |
| Flex cable (1.0mm² 3C, 1.5m avg) | LM | 1.5 | Electrical | JB to fitting |
| Circuit cable (2.5mm² TPS) | LM | 8 | Electrical | Avg run per fitting |
| Cable clips / fixings | No. | 6 | Electrical |  |
| Connector strip / Wago | No. | 2 | Electrical |  |
| Circuit breaker (share of) | No. | 0.1 | Electrical | ~10 fittings per MCB |
| Labour - electrician install | Hr | 0.5 | Labour | Install & wire |
| Labour - electrician T&C | Hr | 0.15 | Labour | Test & commission |
| Labour - apprentice/offsider | Hr | 0.25 | Labour |  |
| Scissor lift / mobile platform | Hr | 0.4 | Plant | Ceiling access |
