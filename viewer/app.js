import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const fmt = (n, d = 1) => Number(n).toFixed(d);
const pct = (n, d = 1) => `${fmt(Number(n) * 100, d)}%`;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

let D, G, P;
let sceneApi;

function card(cls, label, value, note) {
  return `<div class="metric ${cls}"><label>${label}</label><strong>${value}</strong><small>${note}</small></div>`;
}
function item(cls, title, body) {
  return `<div class="item ${cls}"><strong>${title}</strong><span>${body}</span></div>`;
}
function kv(rows) {
  return `<div class="kv">${rows.flatMap(([a, b]) => [`<div>${a}</div>`, `<div>${b}</div>`]).join('')}</div>`;
}
function esc(v) {
  return String(v).replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function renderModelMetrics() {
  const tail = selectedTail();
  $('#modelMetrics').innerHTML = [
    card('', 'Main wing', `${fmt(G.wing.span_m, 1)} m`, `${fmt(G.wing.area_m2, 1)} m² · AR ${fmt(G.wing.aspect_ratio, 2)}`),
    card('c', 'DAE section loft', '4 source profiles', 'DAE11 / 21 / 31 / 41 · exact source coordinates'),
    card('u', 'Selected H-tail', tail.id, `${fmt(tail.span_m, 2)} m span · AR ${fmt(tail.aspect_ratio, 1)}`),
    card('a', 'Static margin', pct(tail.static_margin_fraction_mac, 1), 'Phase 3B VLM · target screen 8–20% MAC'),
  ].join('');
}

function renderTailDetails() {
  const t = selectedTail();
  $('#tailDetails').innerHTML = kv([
    ['Case', esc(t.id)],
    ['Area', `${fmt(t.area_m2, 2)} m²`],
    ['Span', `${fmt(t.span_m, 3)} m`],
    ['AR / taper', `${fmt(t.aspect_ratio, 1)} / ${fmt(t.taper_ratio, 2)}`],
    ['Root / tip chord', `${fmt(t.root_chord_m, 3)} / ${fmt(t.tip_chord_m, 3)} m`],
    ['Quarter-MAC x', `${fmt(t.quarter_mac_x_m, 3)} m`],
    ['Static margin', pct(t.static_margin_fraction_mac, 2)],
    ['Neutral point x', `${fmt(t.neutral_point_x_m, 3)} m`],
  ]) + `<div class="callout warn" style="margin-top:12px">This is a <strong>Phase 3B comparison geometry</strong>. No horizontal-tail planform has been promoted to the baseline.</div>`;
}

function renderFidelityList() {
  $('#fidelityList').innerHTML = [
    item('blue', 'Tracked / authoritative inputs', 'Wing span, area, taper, root LE x, incidence, dihedral, twist stations, overall length, tail areas, tail AC x, mass stations and propeller clearance constraint.'),
    item('green', 'Computational geometry', 'Phase 3A wing convention and the five Phase 3B horizontal-tail planforms are generated from tracked inputs and explicit comparison assumptions.'),
    item('purple', 'DAE thickness/camber overlay', 'Exact MIT source coordinates are used for the visual wing loft. Phase 3A VLM itself used symmetric thin sections, so thickness is a visualization layer rather than a Phase 3A solver input.'),
    item('purple', 'Visual-only components', 'Pod, boom radius, pilot body and vertical-tail planform remain translucent proxies. They do not feed any aerodynamic or structural conclusion.'),
  ].join('');
}

function renderStability() {
  const cs = G.horizontal_tail.candidates;
  const values = cs.map((c) => c.static_margin_fraction_mac);
  $('#stabilityMetrics').innerHTML = [
    card('', 'Cases solved', String(cs.length), 'OpenVSP/VSPAERO VLM tail family'),
    card('a', 'Static-margin range', `${pct(Math.min(...values), 1)}–${pct(Math.max(...values), 1)}`, 'all at the baseline CG'),
    card('c', 'Inside 8–20% screen', '0', 'design-review target, not a safety limit'),
    card('u', 'Fixed tail volume', fmt(0.7197264994779412, 3), 'area and tail AC station held fixed'),
  ].join('');

  const W = 760, H = 330, l = 62, r = 22, t = 26, b = 62;
  const maxY = 0.52;
  const xStep = (W - l - r) / cs.length;
  const barW = xStep * 0.54;
  const y = (v) => H - b - (v / maxY) * (H - t - b);
  let svg = `<rect class="target" x="${l}" y="${y(0.20)}" width="${W-l-r}" height="${y(0.08)-y(0.20)}" rx="5"></rect>`;
  for (const tick of [0, .1, .2, .3, .4, .5]) {
    svg += `<line class="gridline" x1="${l}" x2="${W-r}" y1="${y(tick)}" y2="${y(tick)}"></line><text x="${l-8}" y="${y(tick)+4}" text-anchor="end">${Math.round(tick*100)}%</text>`;
  }
  cs.forEach((c, i) => {
    const x = l + i*xStep + (xStep-barW)/2;
    const yy = y(c.static_margin_fraction_mac);
    svg += `<rect class="bar" x="${x}" y="${yy}" width="${barW}" height="${H-b-yy}" rx="5"></rect>`;
    svg += `<text x="${x+barW/2}" y="${yy-8}" text-anchor="middle">${pct(c.static_margin_fraction_mac,1)}</text>`;
    svg += `<text x="${x+barW/2}" y="${H-b+19}" text-anchor="middle">${c.id}</text>`;
    svg += `<text x="${x+barW/2}" y="${H-b+35}" text-anchor="middle">AR ${fmt(c.aspect_ratio,1)}</text>`;
  });
  svg += `<line class="axis" x1="${l}" x2="${W-r}" y1="${H-b}" y2="${H-b}"></line>`;
  $('#stabilityChart').innerHTML = svg;

  $('#tailTable').innerHTML = `<table><thead><tr><th>Case</th><th>AR</th><th>Taper</th><th>Span</th><th>Root chord</th><th>Tip chord</th><th>Static margin</th><th>Neutral point x</th><th>8–20% screen</th></tr></thead><tbody>${
    cs.map((c, i) => `<tr class="${i===0?'bestrow':'badrow'}"><td>${c.id}</td><td>${fmt(c.aspect_ratio,1)}</td><td>${fmt(c.taper_ratio,2)}</td><td>${fmt(c.span_m,3)} m</td><td>${fmt(c.root_chord_m,3)} m</td><td>${fmt(c.tip_chord_m,3)} m</td><td>${pct(c.static_margin_fraction_mac,2)}</td><td>${fmt(c.neutral_point_x_m,3)} m</td><td>${c.inside_review_band?'inside':'outside'}</td></tr>`).join('')
  }</tbody></table>`;
}

function renderProp() {
  const pb = D.phase2b;
  const sel = pb.selected_design;
  const ref = pb.baseline_reference;
  $('#propMetrics').innerHTML = [
    card('', 'Baseline prop', `${fmt(ref.diameter_m,2)} m / ${fmt(ref.design_rpm,0)} rpm`, `${fmt(ref.ground_clearance_m,3)} m clearance`),
    card('c', 'Numerical candidate', `${fmt(sel.diameter_m,2)} m / ${fmt(sel.design_rpm,0)} rpm`, `${fmt(sel.ground_clearance_m,3)} m clearance · not promoted`),
    card('c', 'Candidate efficiency', pct(sel.result.propulsive_efficiency,2), `${fmt(sel.result.shaft_power_w,1)} W shaft at 9.5 m/s`),
    card('a', 'Power difference', `${fmt(ref.result.shaft_power_w-sel.result.shaft_power_w,2)} W`, 'small numerical advantage versus baseline reference'),
  ].join('');

  const env = pb.operating_envelope;
  $('#propTable').innerHTML = `<table><thead><tr><th>Speed</th><th>RPM</th><th>Aircraft drag</th><th>BEM thrust</th><th>Margin</th><th>Shaft power</th><th>η</th><th>Re range</th></tr></thead><tbody>${
    env.map((p) => `<tr><td>${fmt(p.speed_m_s,1)} m/s</td><td>${fmt(p.solution.rpm,0)}</td><td>${fmt(p.aircraft.drag_n,2)} N</td><td>${fmt(p.solution.result.thrust_n,2)} N</td><td>${fmt(p.solution.thrust_margin_n,2)} N</td><td>${fmt(p.solution.result.shaft_power_w,1)} W</td><td>${pct(p.solution.result.propulsive_efficiency,2)}</td><td>${Math.round(p.solution.result.min_reynolds).toLocaleString()}–${Math.round(p.solution.result.max_reynolds).toLocaleString()}</td></tr>`).join('')
  }</tbody></table>`;

  $('#propCompare').innerHTML = kv([
    ['Baseline shaft power', `${fmt(ref.result.shaft_power_w,2)} W`],
    ['Candidate shaft power', `${fmt(sel.result.shaft_power_w,2)} W`],
    ['Baseline η', pct(ref.result.propulsive_efficiency,2)],
    ['Candidate η', pct(sel.result.propulsive_efficiency,2)],
    ['Baseline clearance', `${fmt(ref.ground_clearance_m,3)} m`],
    ['Candidate clearance', `${fmt(sel.ground_clearance_m,3)} m`],
  ]);
}

function preprocessProfile(points) {
  const imin = points.reduce((best, p, i) => p[0] < points[best][0] ? i : best, 0);
  const upper = points.slice(0, imin + 1).reverse();
  const lower = points.slice(imin);
  return { upper, lower, perimeter: points };
}
function interpLine(points, x) {
  if (x <= points[0][0]) return points[0][1];
  if (x >= points[points.length - 1][0]) return points[points.length - 1][1];
  let lo = 0;
  for (let i = 1; i < points.length; i++) {
    if (points[i][0] >= x) { lo = i - 1; break; }
  }
  const a = points[lo], b = points[lo+1];
  const f = (x-a[0]) / Math.max(b[0]-a[0], 1e-9);
  return a[1] + f*(b[1]-a[1]);
}

function renderAero() {
  const names = ['DAE11','DAE21','DAE31','DAE41'];
  const palette = ['#5ea8ff','#31d6a0','#ffb547','#ba8cff'];
  const W=760,H=360,l=56,r=20,t=34,b=48;
  const sx=(x)=>l+x*(W-l-r), sy=(z)=>H/2-z*850;
  let svg='';
  for (const yv of [-.12,-.08,-.04,0,.04,.08,.12]) {
    svg += `<line class="gridline" x1="${l}" x2="${W-r}" y1="${sy(yv)}" y2="${sy(yv)}"></line>`;
    svg += `<text x="${l-8}" y="${sy(yv)+4}" text-anchor="end">${fmt(yv,2)}</text>`;
  }
  for (const xv of [0,.25,.5,.75,1]) {
    svg += `<line class="gridline" y1="${t}" y2="${H-b}" x1="${sx(xv)}" x2="${sx(xv)}"></line>`;
    svg += `<text x="${sx(xv)}" y="${H-b+20}" text-anchor="middle">${fmt(xv,2)}</text>`;
  }
  names.forEach((name, i)=>{
    const pts=P.profiles[name];
    const d=pts.map((p,j)=>`${j?'L':'M'} ${sx(clamp(p[0],0,1)).toFixed(2)} ${sy(p[1]).toFixed(2)}`).join(' ');
    svg += `<path d="${d}" fill="none" stroke="${palette[i]}" stroke-width="2"></path>`;
    svg += `<text x="${l+12+i*118}" y="20" fill="${palette[i]}">${name}</text>`;
  });
  svg += `<line class="axis" x1="${l}" x2="${W-r}" y1="${sy(0)}" y2="${sy(0)}"></line>`;
  $('#airfoilChart').innerHTML=svg;

  $('#stationMap').innerHTML = G.wing.stations.map((s)=>item(
    s.authority.includes('tracked')?'blue':'purple',
    `η ${fmt(s.eta,2)} · twist ${fmt(s.twist_deg,2)}°`,
    s.profile_b ? `${s.profile_a}/${s.profile_b} visual interpolation · ${s.authority}` : `${s.profile_a} · ${s.authority}`
  )).join('');

  const rows = Array.isArray(D.airfoils?.summary) ? D.airfoils.summary : [];
  const cols = rows.length ? Object.keys(rows[0]) : [];
  const preferred = ['airfoil','reynolds','best_ld','best_l_d','ld_max','max_ld','converged_points'];
  const selectedCols = preferred.filter(c=>cols.includes(c));
  const useCols = selectedCols.length ? selectedCols : cols.slice(0,6);
  $('#polarTable').innerHTML = rows.length
    ? `<table><thead><tr>${useCols.map(c=>`<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${useCols.map(c=>`<td>${typeof r[c]==='number'?fmt(r[c], r[c]>1000?0:2):esc(r[c]??'')}</td>`).join('')}</tr>`).join('')}</tbody></table>`
    : `<div class="callout">The verified snapshot does not expose a tabular airfoil summary in the expected shape.</div>`;
}

function renderCg() {
  const m=G.mass,w=G.wing;
  // Phase 3A uses aligned leading edges (zero sweep), so MAC LE is the tracked root LE x.
  const macLE = w.root_le_x_m;
  $('#cgMetrics').innerHTML=[
    card('', 'Empty mass', `${fmt(m.empty_mass_kg,1)} kg`, `${m.items.length} tracked component stations`),
    card('', 'Reference gross', `${fmt(m.gross_mass_kg,1)} kg`, `${fmt(m.reference_pilot_and_personal_gear_kg,1)} kg pilot + gear`),
    card('c', 'Gross CG x', `${fmt(m.gross_cg_x_m,3)} m`, `${pct(D.baseline.mass.gross_cg_fraction_mac,2)} wing MAC in verified snapshot`),
    card('u', 'Reference pilot CG x', `${fmt(m.reference_pilot_cg_x_m,2)} m`, 'body geometry is visual only'),
  ].join('');

  const L=G.overall_length_m, pos=(x)=>3+94*x/L;
  const targetX=macLE+D.baseline.mass.target_cg_fraction_mac*w.mean_aerodynamic_chord_m;
  const rangeLo=macLE+D.baseline.mass.provisional_cg_range_fraction_mac[0]*w.mean_aerodynamic_chord_m;
  const rangeHi=macLE+D.baseline.mass.provisional_cg_range_fraction_mac[1]*w.mean_aerodynamic_chord_m;
  $('#cgDiagram').innerHTML=`
    <div class="cg-axis"></div>
    <div class="cg-mac" style="left:${pos(macLE)}%;width:${94*w.mean_aerodynamic_chord_m/L}%">Wing MAC<br>${fmt(macLE,3)}–${fmt(macLE+w.mean_aerodynamic_chord_m,3)} m</div>
    <div class="cg-range" style="left:${pos(rangeLo)}%;width:${94*(rangeHi-rangeLo)/L}%"></div>
    <div class="cg-marker" style="left:${pos(m.gross_cg_x_m)}%"></div>
    <div class="cg-marker cg-target" style="left:${pos(targetX)}%"></div>
    <div class="cg-label" style="left:${pos(m.gross_cg_x_m)}%;top:29px">gross CG<br>${fmt(m.gross_cg_x_m,3)} m</div>
    <div class="cg-label" style="left:${pos(targetX)}%;top:170px">23% target</div>
    <div class="cg-label" style="left:3%;top:125px">x 0 m</div>
    <div class="cg-label" style="left:97%;top:125px">x ${fmt(L,1)} m</div>`;

  $('#massTable').innerHTML=`<table><thead><tr><th>Item</th><th>Mass</th><th>x station</th></tr></thead><tbody>${
    m.items.map(x=>`<tr><td>${esc(x.name)}</td><td>${fmt(x.mass_kg,1)} kg</td><td>${fmt(x.x_m,2)} m</td></tr>`).join('')
  }</tbody></table>`;
}

function renderSources() {
  const cards=[
    ['Baseline geometry / mass','config/he1_baseline.json','Tracked geometry, mass stations and unresolved boundaries.'],
    ['Phase 3A wing','main @ 3acd38ffee0665e8b202fbb05559c569c516b2f5','OpenVSP/VSPAERO main-wing validation and geometry convention.'],
    ['Phase 3B tail family',`head @ ${G.meta.source_phase3b_head}`,`Five tail cases. Validation run ${G.meta.phase3b_validation_run}. No candidate promoted.`],
    ['DAE wing coordinates','MIT Mark Drela HPA airfoil archive','Exact DAE11/21/31/41 coordinate files with repository-pinned SHA256 values.'],
    ['Verified performance snapshot',`baseline snapshot @ ${D.meta.baseline_commit}`,'Phase 1 / Phase 2 / Phase 2B values remain separately pinned.'],
    ['3D display boundary','viewer/data/geometry_fidelity.json','Every visual-only envelope and computational geometry assumption is declared explicitly.'],
  ];
  $('#sourcesGrid').innerHTML=cards.map(([a,b,c])=>`<div class="source"><strong>${esc(a)}</strong><span>${esc(c)}</span><code>${esc(b)}</code></div>`).join('');
}

function selectedTail() {
  const id=$('#tailSelect')?.value || G.horizontal_tail.default_display_case;
  return G.horizontal_tail.candidates.find(c=>c.id===id) || G.horizontal_tail.candidates[0];
}

function initTailSelect() {
  $('#tailSelect').innerHTML=G.horizontal_tail.candidates.map(c=>`<option value="${c.id}">${c.id} · AR ${fmt(c.aspect_ratio,1)} · SM ${pct(c.static_margin_fraction_mac,1)}</option>`).join('');
  $('#tailSelect').value=G.horizontal_tail.default_display_case;
  $('#tailSelect').addEventListener('change',()=>{
    renderModelMetrics();renderTailDetails();sceneApi?.replaceTail(selectedTail());
  });
}

function setupTabs() {
  $$('.tab').forEach(btn=>btn.addEventListener('click',()=>{
    $$('.tab').forEach(x=>x.classList.toggle('active',x===btn));
    $$('.section').forEach(x=>x.classList.toggle('active',x.id===btn.dataset.tab));
    if(btn.dataset.tab==='model') setTimeout(()=>sceneApi?.resize(),20);
  }));
}

function makeLine(points, color, opacity=1) {
  const g=new THREE.BufferGeometry().setFromPoints(points.map(p=>new THREE.Vector3(...p)));
  return new THREE.Line(g,new THREE.LineBasicMaterial({color,transparent:opacity<1,opacity}));
}

function makeWingLoft() {
  const stationProfiles={};
  for(const [name,pts] of Object.entries(P.profiles)) stationProfiles[name]=preprocessProfile(pts);
  const spanN=37,chordN=51;
  const xs=Array.from({length:chordN},(_,i)=>0.5*(1-Math.cos(Math.PI*i/(chordN-1))));
  const st=G.wing.stations;

  function stationSurface(s,x,upper){
    const A=stationProfiles[s.profile_a];
    const za=interpLine(upper?A.upper:A.lower,x);
    if(!s.profile_b) return za;
    const B=stationProfiles[s.profile_b];
    const zb=interpLine(upper?B.upper:B.lower,x);
    return za+(zb-za)*s.blend_fraction;
  }
  function stateAt(eta,x,upper){
    let i=0;
    while(i<st.length-2 && eta>st[i+1].eta) i++;
    const a=st[i], b=st[i+1];
    const f=clamp((eta-a.eta)/(b.eta-a.eta),0,1);
    return {
      zn:stationSurface(a,x,upper)+(stationSurface(b,x,upper)-stationSurface(a,x,upper))*f,
      twist:a.twist_deg+(b.twist_deg-a.twist_deg)*f
    };
  }
  const verts=[],inds=[];
  const root=G.wing.root_chord_m, tip=G.wing.tip_chord_m, semi=G.wing.span_m/2;
  const incidence=G.wing.incidence_deg*Math.PI/180, dih=G.wing.dihedral_deg*Math.PI/180;
  let offset=0;
  for(const side of [-1,1]){
    for(const upper of [true,false]){
      for(let i=0;i<spanN;i++){
        const eta=i/(spanN-1), y=side*semi*eta, chord=root+(tip-root)*eta, z0=Math.abs(y)*Math.tan(dih);
        for(let j=0;j<chordN;j++){
          const xn=xs[j], ss=stateAt(eta,xn,upper), theta=incidence+ss.twist*Math.PI/180;
          const dx=(xn-.25)*chord, dz=ss.zn*chord, qx=G.wing.root_le_x_m+.25*chord;
          const x=qx+dx*Math.cos(theta)+dz*Math.sin(theta);
          const z=z0-dx*Math.sin(theta)+dz*Math.cos(theta);
          verts.push(x,y,z);
        }
      }
      for(let i=0;i<spanN-1;i++) for(let j=0;j<chordN-1;j++){
        const a=offset+i*chordN+j,b=a+1,c=a+chordN,d=c+1;
        if(upper) inds.push(a,c,b,b,c,d); else inds.push(a,b,c,b,d,c);
      }
      offset+=spanN*chordN;
    }
  }
  const geo=new THREE.BufferGeometry();
  geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));
  geo.setIndex(inds);geo.computeVertexNormals();
  const mesh=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:0x5ea8ff,roughness:.62,metalness:.02,transparent:true,opacity:.88,side:THREE.DoubleSide}));
  mesh.name='DAE wing loft';
  return mesh;
}

function midPoint(eta, xn, side=1) {
  const root=G.wing.root_chord_m,tip=G.wing.tip_chord_m,semi=G.wing.span_m/2;
  const chord=root+(tip-root)*eta,y=side*semi*eta,z0=Math.abs(y)*Math.tan(G.wing.dihedral_deg*Math.PI/180);
  let i=0;const st=G.wing.stations;
  while(i<st.length-2 && eta>st[i+1].eta)i++;
  const a=st[i],b=st[i+1],f=clamp((eta-a.eta)/(b.eta-a.eta),0,1);
  const twist=(a.twist_deg+(b.twist_deg-a.twist_deg)*f+G.wing.incidence_deg)*Math.PI/180;
  const dx=(xn-.25)*chord,qx=G.wing.root_le_x_m+.25*chord;
  return [qx+dx*Math.cos(twist),y,z0-dx*Math.sin(twist)];
}
function makeVlmReference() {
  const group=new THREE.Group();
  const c=0x73e0ff;
  for(const side of [-1,1]){
    G.wing.stations.forEach(s=>group.add(makeLine([midPoint(s.eta,0,side),midPoint(s.eta,1,side)],c,.78)));
    group.add(makeLine(Array.from({length:31},(_,i)=>midPoint(i/30,0,side)),c,.65));
    group.add(makeLine(Array.from({length:31},(_,i)=>midPoint(i/30,1,side)),c,.65));
    group.add(makeLine(Array.from({length:31},(_,i)=>midPoint(i/30,.25,side)),c,.42));
  }
  return group;
}
function makeTail(t) {
  const g=new THREE.BufferGeometry();
  const b=t.span_m/2,le=t.root_le_x_m,cr=t.root_chord_m,ct=t.tip_chord_m,z=t.vertical_position_m;
  const v=[
    le,0,z, le+cr,0,z, le,b,z, le+ct,b,z,
    le,0,z, le+cr,0,z, le,-b,z, le+ct,-b,z
  ];
  const idx=[0,2,1,1,2,3,4,5,6,5,7,6];
  g.setAttribute('position',new THREE.Float32BufferAttribute(v,3));g.setIndex(idx);g.computeVertexNormals();
  const m=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0xba8cff,transparent:true,opacity:.78,side:THREE.DoubleSide,roughness:.7}));
  const outline=new THREE.LineSegments(new THREE.EdgesGeometry(g),new THREE.LineBasicMaterial({color:0xe1cfff}));
  const group=new THREE.Group();group.add(m,outline);group.name=`tail-${t.id}`;return group;
}
function makeBody() {
  const e=G.visual_envelopes.pod;
  const mesh=new THREE.Mesh(new THREE.SphereGeometry(1,40,20),new THREE.MeshStandardMaterial({color:0x8593a1,transparent:true,opacity:.18,roughness:.7,side:THREE.DoubleSide}));
  mesh.scale.set(e.length_m/2,e.width_m/2,e.height_m/2);mesh.position.set(e.center_x_m,0,.08);return mesh;
}
function makeBoom() {
  const e=G.visual_envelopes.boom,len=e.end_x_m-e.start_x_m;
  const mesh=new THREE.Mesh(new THREE.CylinderGeometry(e.radius_m,e.radius_m,len,14),new THREE.MeshStandardMaterial({color:0x8593a1,transparent:true,opacity:.42,roughness:.8}));
  mesh.rotation.z=Math.PI/2;mesh.position.set((e.start_x_m+e.end_x_m)/2,0,0);return mesh;
}
function makePilot() {
  const g=new THREE.Group(),mat=new THREE.MeshStandardMaterial({color:0x8593a1,transparent:true,opacity:.32,roughness:.8});
  const torso=new THREE.Mesh(new THREE.CapsuleGeometry(.18,.48,6,12),mat);torso.position.set(G.mass.reference_pilot_cg_x_m,0,.32);torso.rotation.z=-.18;
  const head=new THREE.Mesh(new THREE.SphereGeometry(.13,20,12),mat);head.position.set(G.mass.reference_pilot_cg_x_m+.08,0,.83);
  const legs=new THREE.Mesh(new THREE.CylinderGeometry(.07,.08,.78,10),mat);legs.rotation.z=Math.PI/2.6;legs.position.set(2.32,0,.05);
  g.add(torso,head,legs);return g;
}
function makeVtailProxy() {
  const side=G.vertical_tail.visual_proxy.side_m;
  const geo=new THREE.PlaneGeometry(side,side);
  const mesh=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({color:0xba8cff,transparent:true,opacity:.16,side:THREE.DoubleSide}));
  mesh.rotation.y=Math.PI/2;mesh.position.set(G.horizontal_tail.fixed_aerodynamic_center_x_m,0,side/2);
  return mesh;
}
function propRing(d,color,opacity=.9) {
  const m=new THREE.Mesh(new THREE.TorusGeometry(d/2,.018,8,96),new THREE.MeshBasicMaterial({color,transparent:true,opacity}));
  m.rotation.y=Math.PI/2;return m;
}
function makeProp() {
  const g=new THREE.Group();g.position.x=G.propeller.display_plane_x_m;
  const ref=G.propeller.baseline,sel=G.propeller.phase2b_numerical_candidate;
  g.add(propRing(ref.diameter_m,0xffb547,.9),propRing(sel.diameter_m,0x31d6a0,.72));
  const bladeMat=new THREE.MeshBasicMaterial({color:0xffb547,transparent:true,opacity:.7});
  const b1=new THREE.Mesh(new THREE.BoxGeometry(.025,ref.diameter_m*.92,.035),bladeMat);g.add(b1);
  const hub=new THREE.Mesh(new THREE.SphereGeometry(.075,16,10),new THREE.MeshBasicMaterial({color:0xdde9f5}));g.add(hub);
  return g;
}
function makeClearance() {
  const g=new THREE.Group(),z=-G.propeller.shaft_center_height_m,span=4.2,step=.35;
  for(let v=-span/2;v<=span/2+.01;v+=step){
    g.add(makeLine([[G.propeller.display_plane_x_m-span/2,v,z],[G.propeller.display_plane_x_m+span/2,v,z]],0x61798f,.35));
    g.add(makeLine([[G.propeller.display_plane_x_m+v,-span/2,z],[G.propeller.display_plane_x_m+v,span/2,z]],0x61798f,.35));
  }
  const clearanceZ=z+G.propeller.minimum_target_ground_clearance_m;
  const r=G.propeller.phase2b_numerical_candidate.diameter_m/2;
  g.add(makeLine([[G.propeller.display_plane_x_m,0,z],[G.propeller.display_plane_x_m,0,0]],0xffb547,.8));
  g.add(makeLine([[G.propeller.display_plane_x_m,-r,0],[G.propeller.display_plane_x_m,-r,clearanceZ]],0x31d6a0,.8));
  return g;
}
function makeMassStations() {
  const g=new THREE.Group();
  G.mass.items.forEach(it=>{
    const rad=.035+.018*Math.sqrt(it.mass_kg);
    const s=new THREE.Mesh(new THREE.SphereGeometry(rad,14,10),new THREE.MeshBasicMaterial({color:0xffd080,transparent:true,opacity:.85}));
    s.position.set(it.x_m,0,-.38);g.add(s);
  });
  g.add(makeLine([[G.mass.gross_cg_x_m,0,-.9],[G.mass.gross_cg_x_m,0,1.2]],0xffffff,.9));
  return g;
}
function makeLengthDatum() {
  const g=new THREE.Group();
  g.add(makeLine([[0,0,-.62],[G.overall_length_m,0,-.62]],0x55718a,.6));
  for(const x of [0,G.wing.root_le_x_m,G.mass.gross_cg_x_m,G.horizontal_tail.fixed_aerodynamic_center_x_m,G.overall_length_m]){
    g.add(makeLine([[x,-.09,-.62],[x,.09,-.62]],0x55718a,.8));
  }
  return g;
}

function setupScene() {
  const root=$('#scene');
  const scene=new THREE.Scene();scene.fog=new THREE.Fog(0x050c13,24,48);
  const camera=new THREE.PerspectiveCamera(38,1,.05,120);camera.up.set(0,0,1);
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;root.appendChild(renderer.domElement);
  const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.08;controls.target.set(5.2,0,.1);
  scene.add(new THREE.HemisphereLight(0xbfdcff,0x0a0d11,1.35));
  const dl=new THREE.DirectionalLight(0xffffff,2.0);dl.position.set(-3,-8,13);scene.add(dl);
  const fill=new THREE.DirectionalLight(0x8abfff,.9);fill.position.set(12,10,6);scene.add(fill);

  const groups={
    wing:makeWingLoft(),vlm:makeVlmReference(),tail:makeTail(selectedTail()),vtail:makeVtailProxy(),
    body:makeBody(),boom:makeBoom(),pilot:makePilot(),mass:makeMassStations(),prop:makeProp(),clearance:makeClearance(),datum:makeLengthDatum()
  };
  Object.values(groups).forEach(x=>scene.add(x));
  groups.vtail.visible=false;groups.pilot.visible=false;groups.mass.visible=false;groups.clearance.visible=false;

  const axes=new THREE.AxesHelper(1.2);axes.position.set(0,0,-.62);scene.add(axes);

  function setView(name){
    const map={
      iso:[[14,-19,10.5],[5.2,0,.2]],
      top:[[5.2,0,29],[5.2,0,0]],
      side:[[5.2,-29,2.5],[5.2,0,.15]],
      front:[[-20,0,2.4],[5.0,0,.15]]
    };
    const [p,t]=map[name];camera.position.set(...p);controls.target.set(...t);controls.update();
    $$('.view').forEach(b=>b.classList.toggle('active',b.dataset.view===name));
  }
  function resize(){
    const w=root.clientWidth,h=root.clientHeight;if(!w||!h)return;
    renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(root);resize();setView('iso');

  const layerMap={layerWing:'wing',layerVlm:'vlm',layerTail:'tail',layerVtail:'vtail',layerBody:'body',layerBoom:'boom',layerPilot:'pilot',layerMass:'mass',layerProp:'prop',layerClearance:'clearance'};
  Object.entries(layerMap).forEach(([id,key])=>$('#'+id).addEventListener('change',e=>groups[key].visible=e.target.checked));
  $$('.view').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
  function replaceTail(t){scene.remove(groups.tail);groups.tail.geometry?.dispose?.();groups.tail=makeTail(t);groups.tail.visible=$('#layerTail').checked;scene.add(groups.tail);}
  function reset(){setView('iso');controls.reset?.();setView('iso');}
  function animate(){requestAnimationFrame(animate);controls.update();renderer.render(scene,camera);}animate();
  return {resize,setView,replaceTail,reset};
}

async function boot(){
  try{
    [D,G,P]=await Promise.all([
      fetch('./data/verified_snapshot.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`snapshot HTTP ${r.status}`);return r.json()}),
      fetch('./data/geometry_fidelity.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`geometry HTTP ${r.status}`);return r.json()}),
      fetch('./data/wing_profiles.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`profiles HTTP ${r.status}`);return r.json()})
    ]);
    $('#status').textContent=`Snapshot ${D.meta.baseline_commit.slice(0,8)} verified · Phase 3 geometry loaded`;
    $('#status').className='pill candidate';
    initTailSelect();renderModelMetrics();renderTailDetails();renderFidelityList();renderStability();renderProp();renderAero();renderCg();renderSources();setupTabs();
    sceneApi=setupScene();$('#reset3d').addEventListener('click',()=>sceneApi.reset());
  }catch(err){
    console.error(err);$('#status').textContent='Engineering viewer unavailable';$('#status').className='pill unresolved';
    const root=$('#scene');if(root)root.innerHTML=`<div class="callout warn" style="margin:20px">Failed to load engineering model: ${esc(err.message)}</div>`;
  }
}
boot();
