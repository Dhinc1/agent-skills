# Pay-Item Catalog (Civil Site Work)

Derived from real Freshwater Landing bids. This is the target list the estimator
measures for. It is ~90% of typical scope, not exhaustive. Enrich as new
projects add items. When a plan shows something not here, add it, don't drop it.

Column meaning: **Item** = pay item as it appears in bids. **UOM** = unit it is
bid in. **Basis** = what the quantity is measured from on the plans.

> v2: every quantity here should land in the element ledger
> (`takeoff/elements.json`) with a source sheet and a High/Medium/Low
> confidence tag, not just a number in the worksheet. Any measured (not
> schedule-stated) length or area feeding a pay item gets the blind
> anchor-dimension check before it ships. See SKILL.md, "Reconcile before it
> ships."

## Units glossary
EA (each) · LS (lump sum) · LF (linear feet) · SY (square yard) · SF (square
foot) · CY (cubic yard) · AC (acre) · TN (ton) · VF (vertical foot) · Months ·
Day.

---

## 01 — General Conditions & Mobilization
UOM: EA, LS, Months
- Mobilization (dirt / utilities) — EA
- GPS model — EA
- Porta john, dumpster, misc — Months
- Construction staking / surveying — LS
- As-built surveying — LS
- Geotech / soil testing — LS (often excluded, note it)

## 02 — Clearing & Demolition
UOM: AC, EA, SF
- Clearing — AC (basis: limits of disturbance area)
- Demo of well — EA
- Demo of existing structures — SF (building footprint)

## 03 — Erosion & Sediment Control
UOM: EA, LF, SY, CY
- Construction entrance — EA
- Silt fence (incl. tree protection variant) — LF
- Silt fence rock outlets — EA
- Skimmers (by size) — EA
- Anti-float block, anti-seep collar — EA
- Outlet control structure (OCS) w/ trash rack — EA
- Skimmer-basin RCP + FES (by size) — LF / EA
- Rip rap apron (outfall, slope drain) — SF / EA
- Emergency spillway (riprap / concrete) — SF
- Baffles — LF
- Slope drain (HDPE, by size) — LF
- Erosion matting — SY
- Diversion ditch — LF
- Rock check dams — EA
- Stockpile to fill — CY
- Fine grade basin — SY
- Seeding — AC
- Basin fill-in / removal (skimmer, baffles, dewater, muck out) — EA / CY

## 04 — Earthwork / Grading
UOM: CY
- Strip topsoil (place onsite) — CY
- Cut to fill — CY
- Import / export fill — CY (often "not included", flag it)
- Mass/trench rock (usually excluded, note it)

## 05 — Fine Grading
UOM: LF, SY, SF
- Grade & backfill curb & gutter — LF
- Fine grade roadways — SY
- Shoulder slopes & pads — SY
- Sidewalk fine grade — SF

## 06 — Storm Drainage (Onsite)
UOM: LF, EA, LS
- RCP by size & class (15"–36", CL 3/4) — LF
- FES by size — EA
- Catch basins — EA
- Precast junction box — EA
- Adjust CB to curb — EA
- Inlet protection / silt sack — LF / EA
- Underground detention system — LS
- Flushing / CCTV — LF
- Mastic — LS
- Soft dig — Day
> Class III and Class IV pipe of the same size are different pay items, not the
> same line at a different depth band — a schedule can call out Class IV for
> one run (often a culvert crossing under a private drive) and Class III for
> everything else at the same diameter. If the budget template only has a
> Class III line for that size, that's a template gap, not a reason to price
> the Class IV run at the Class III rate — flag it.
> This is the Cottages at Back Creek pipe-schedule lesson: transcribe every
> pipe schedule row into the element ledger with size AND class as separate
> fields before pricing, then reconcile ledger rows against the schedule's own
> row count (see SKILL.md Step 5a) — that catch is what a 15"/12" transposition
> needs to surface before the budget ships.

## 07 — Sanitary Sewer (Main Line)
UOM: LF, EA, VF, Day
- Gravity main by material/depth band (SDR 26, RJDIP, by depth) — LF
- Casing — LF
- Sewer laterals (off main / off DI / off manhole) — EA
- Manholes (4' dia) — EA
- Extra depth manhole — VF
- Outside drop manhole assembly — EA
- Air/mandrel testing, camera main & laterals — LF / EA
- Adjust ring & cover, vac test — EA
- Soft dig — Day

## 08 — Sewer Pump Station / Force Main  [SEGREGATE]
UOM: LS, LF, EA
- Pump station (complete) — LS  ← own line, own section
- Force main (DR14 PVC / RJDIP, by size) — LF
- ARV, service, RPZ, blowoff, plug, hydrant — EA
- Fittings — LS
- Testing, soft dig — LF / Day
> A lift station or pump station is a standalone section, not folded into
> sanitary sewer. Same rule for any package plant / WWTP scope.

## 09 — Water Line
UOM: LF, EA, LS, Day
- Tie-in to existing main — EA
- DI / C-900 pipe by size — LF
- Casing — LF
- Gate valves by size — EA
- Fittings — LS
- Blow off (perm/temp), jumper — EA
- Fire hydrants — EA
- Services (long / short) — EA
- Pressure & Bac-T testing — LF
- Soft dig — Day

## 10 — Paving, Curb & Sidewalk (Onsite)
UOM: SY, TN, LF, SF, EA, LS
- ABC stone lifts (by depth) — SY
- Asphalt surface/binder lifts (S9.5B etc., by lift) — SY
- Parking lot section (ABC + surface) — SY
- Curb & gutter (ribbon / standard / valley, by type) — LF
- Sidewalk — SF
- Handicap ramps — EA
- Striping & signage — LS
> Count the lifts against the pavement section detail before pricing, not
> against how many lift line items the budget template happens to carry. A
> template can have two near-identical "1.5" intermediate course" rows active
> at once (a duplicate, or a leftover default) when the actual cross-section
> calls for one intermediate lift plus a separate final surface/overlay course
> — check whether a final surface course is already priced elsewhere (a
> post-construction overlay line, for instance) before assuming every active
> lift row in the paving section is distinct scope. This is the Cottages at
> Back Creek duplicate-lift lesson — audit every active row in a budget
> section against the actual pavement detail before touching a rate, not just
> the row you're editing.
> Curb LF: a `2 × road centerline` formula is a placeholder, not a takeoff —
> it misses cul-de-sac bulbs and intersection returns. Use a plan-stated
> total or a real measured curb linetype when one is available, and run the
> blind anchor-dimension check against it (a second, independently-sourced
> dimension — a plotted total, a different sheet's callout) before trusting a
> formula-derived total. This is the Cottages at Back Creek curb-formula
> lesson.

## 11 — BMP / Basin Conversion (permanent)
UOM: SF, CY, EA, SY, AC
- Sand filter — SF
- Forebay riprap berm — SF
- Dewater / de-muck basin — EA / CY
- Remove erosion devices — EA
- Fine grade basin & littoral shelf — SY
- Seeding — AC
- Orifice holes & plates — EA

---

## 12 — Offsite Roadway Improvements  [SEGREGATE, per road]
UOM: TN, LS, LF, EA, SY
Each offsite road is its own subsection with its own limits. Observed on
Freshwater: Bridges Farm Road, Bridges Farm Lane, NC-115, Presbyterian Rd.
Typical items per road:
- Full-depth asphalt (B25.0C / I19.0C / S9.5C, by lift) — TN
- Mill & overlay — TN
- Milling — LS
- Grading / tie-ins — LS
- Traffic control — LS
- Silt fence, wattles, seeding & matting — LF / EA / LS
- RCP / FES install — LF / EA
- Striping & signage — LS
- Railroad insurance / special — LS
> Offsite roadway can appear on a dedicated tab OR mixed into the onsite paving
> section. Catch it by callout ("OFFSITE", a named public road, an NCDOT
> encroachment, a station range outside the project boundary), not by location
> in the bid. Record the station limits so onsite and offsite don't double-count.
