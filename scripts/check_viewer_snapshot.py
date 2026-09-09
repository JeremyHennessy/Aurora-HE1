#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path

def require(condition: bool, message: str) -> None:
    if not condition: raise SystemExit(f"VIEWER VALIDATION FAILED: {message}")

def main() -> None:
    p=Path('viewer/data/verified_snapshot.json'); require(p.exists(),'verified snapshot missing')
    data=json.loads(p.read_text()); meta=data['meta']
    require(re.fullmatch(r'[0-9a-f]{40}',meta['baseline_commit']) is not None,'baseline commit is not a full SHA')
    b=data['baseline']; w=b['geometry']['wing']
    require(abs(w['span_m']-23.0)<1e-9,'wing span drifted from tracked baseline')
    require(abs(w['area_m2']-18.0)<1e-9,'wing area drifted from tracked baseline')
    require(abs(b['mass']['gross_mass_kg']-110.0)<1e-9,'gross mass drifted from tracked baseline')
    require(abs(b['performance']['design_cruise_m_s']-9.5)<1e-9,'design cruise drifted from tracked baseline')
    p2=data['phase2']; require(.80<=p2['bem']['propulsive_efficiency']<=.95,'Phase 2 BEM efficiency outside accepted computational gate')
    require(p2['bem']['thrust_n']>=p2['required_aircraft_cruise_thrust_n'],'Phase 2 reference no longer closes cruise thrust')
    p2b=data['phase2b']; selected=p2b['selected_design']
    require(selected['ground_clearance_ok'],'Phase 2B selected design violates clearance gate')
    require(selected['polar_envelope_ok'],'Phase 2B selected design leaves trusted polar envelope')
    require(selected['diameter_m']<=p2b['installation_constraint']['max_diameter_for_clearance_m']+1e-9,'selected prop exceeds current clearance diameter cap')
    require(len(p2b['operating_envelope'])==7,'expected seven off-design speed points')
    require(all(row['solution'] is not None for row in p2b['operating_envelope']),'an off-design speed point has no trusted solution')
    require(p2b['static_thrust']['supported'] is False,'viewer must not claim static thrust from forward-flight BEM')
    polars=data['airfoils']['summary']; require(len(polars)==22,f'expected 22 XFOIL polar cases, found {len(polars)}')
    for row in polars:
        require(row['converged_points']>=12,f"{row['airfoil']} Re={row['reynolds']} insufficient converged points")
        require(row['alpha_min']<=-2.0 and row['alpha_max']>=7.0,f"{row['airfoil']} Re={row['reynolds']} lacks trusted alpha coverage")
    print('VIEWER VALIDATION PASSED'); print(f"snapshot source baseline: {meta['baseline_commit']}")
    print(f"Phase 2B candidate: D={selected['diameter_m']:.2f} m @ {selected['design_rpm']:.0f} rpm")
    print(f"off-design solved points: {len(p2b['operating_envelope'])}/7"); print(f"airfoil cases: {len(polars)}")
if __name__=='__main__': main()
