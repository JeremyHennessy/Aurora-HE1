# Phase 3B — provisional horizontal-tail family and longitudinal stability

Status: **computational engineering trade / not for construction or flight clearance**.

## Purpose

Phase 3A established a reproducible OpenVSP/VSPAERO representation of the specified main wing. Phase 3B adds only enough provisional empennage geometry to answer the next defensible question: how sensitive longitudinal static stability is to horizontal-tail planform while preserving the baseline tail area and tail aerodynamic-center station.

This is deliberately **not** a final empennage design.

## Fixed inputs from the baseline

Phase 3B preserves:

- main wing geometry and twist distribution;
- horizontal-tail area = 1.77 m²;
- horizontal-tail aerodynamic-center x = 8.85 m;
- baseline mass model;
- reference gross mass = 110 kg;
- reference gross CG derived from the baseline mass table;
- the Phase 3A OpenVSP/VSPAERO method and toolchain.

The horizontal-tail volume coefficient is therefore fixed by the baseline area, tail arm, wing area and wing MAC.

## Provisional variables

The family varies horizontal-tail aspect ratio and taper ratio. It holds these assumptions fixed for the first sensitivity study:

- zero leading-edge sweep;
- zero dihedral;
- zero tail incidence relative to the aircraft reference line;
- z = 0 m reference position;
- symmetric thin VLM section;
- no elevator.

Those values are assumptions for comparison, not baseline geometry.

The five initial cases are:

| Case | AR | Taper | Purpose |
| --- | ---: | ---: | --- |
| HT35T70 | 3.5 | 0.70 | compact / lower aspect-ratio reference |
| HT45T65 | 4.5 | 0.65 | intermediate reference |
| HT55T65 | 5.5 | 0.65 | higher-efficiency reference |
| HT65T55 | 6.5 | 0.55 | high-AR / more tapered case |
| HT55T100 | 5.5 | 1.00 | rectangular-planform sensitivity at the same AR |

For every case, span and chords are derived from area, aspect ratio and taper. Root leading-edge x is then solved so the unswept tail's quarter-MAC remains at x = 8.85 m.

## VSPAERO reference convention

Pitching-moment interpretation requires a controlled reference length and CG.

Phase 3B therefore uses manual VSPAERO reference quantities:

- Sref = 18.0 m²;
- bref = 23.0 m;
- cref = the baseline main-wing mean aerodynamic chord;
- Xcg = the gross CG recomputed from the baseline mass table.

This avoids interpreting pitching moment with OpenVSP's default mean-geometric-chord reference.

## Analysis

Each provisional tail is run as a separate VSPAERO VLM case with:

- main wing + horizontal tail only;
- Mach 0.03;
- alpha sweep from -2° to +6°;
- five points;
- thin-surface geometry;
- native `.polar` output as the coefficient evidence source.

The parser extracts `CLtot`, `CDi`, and `CMytot`, then fits:

- CL versus alpha;
- Cm versus alpha;
- Cm versus CL.

With pitching moment normalized by main-wing MAC and referenced at the baseline CG:

`static margin = -dCm/dCL`

and

`x_NP = x_CG + static_margin * MAC`.

## Validation

CI rejects a case if:

- main-wing geometry no longer closes to the baseline;
- tail area/span/chords differ from the generated case definition;
- the baseline CG reference drifts;
- the requested alpha points are missing;
- any coefficient is non-finite;
- lift-curve slope is non-positive;
- pitching-moment slope is non-restoring;
- `dCm/dCL` is non-restoring;
- static margin falls outside a deliberately broad computational plausibility gate;
- the neutral-point conversion is internally inconsistent.

A provisional 8–20% MAC review band is reported only as a design-screening reference. It is **not** a certification, flight-test, or acceptance limit, and Phase 3B is allowed to show that none of the current fixed-area cases fall inside it.

## Not modeled yet

Phase 3B does not establish:

- trimmed cruise or climb;
- elevator authority or hinge moments;
- vertical-tail sizing;
- directional/lateral stability;
- fuselage aerodynamic interference;
- propeller slipstream effects;
- aeroelastic tail/boom deformation;
- structural adequacy;
- flutter margin;
- flight clearance.

If the family is consistently over- or under-stable, the next step should be a controlled trade of tail area and/or tail arm rather than quietly changing the baseline. If longitudinal stability is reasonable, the next phase can add an explicit elevator family for trim/control-authority analysis before any tail geometry is promoted.
