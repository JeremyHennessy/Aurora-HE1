#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { WebXFOIL } from 'webxfoil-wasm';

const CONFIG_PATH = process.env.HE1_PHASE2C_CONFIG || 'config/phase2c_transition_sensitivity.json';
const AIRFOIL_DIR = process.env.HE1_AIRFOIL_DIR || 'analysis/airfoils';
const OUTPUT_ROOT = process.env.HE1_PHASE2C_POLAR_ROOT || 'analysis/phase2c/polars';

function alphaValues(start, end, step) {
  const values = [];
  const n = Math.round((end - start) / step);
  for (let i = 0; i <= n; i += 1) values.push(Number((start + i * step).toFixed(8)));
  return values;
}

function finiteScalar(output, key) {
  const value = output?.scalars?.[key]?.value;
  return Number.isFinite(value) ? value : null;
}

async function solvePoint({ airfoilText, airfoilName, reynolds, alphaDeg, scenario, cfg }) {
  const xfoil = await WebXFOIL.load();
  try {
    const input = WebXFOIL.input();
    input.loadAirfoilText(airfoilText, { path: `${airfoilName}.dat`, name: airfoilName.toUpperCase() });
    input.add('PANE').oper().add('MACH 0').add(`VISC ${reynolds}`).add(`ITER ${Number(cfg.iteration_limit)}`).add('VPAR').add(`N ${Number(scenario.ncrit)}`);
    if (scenario.forced_transition) {
      const upper = Number(scenario.forced_transition.upper_x_over_c);
      const lower = Number(scenario.forced_transition.lower_x_over_c);
      input.add(`XTR ${upper} ${lower}`);
    }
    input.blank().setAlpha(alphaDeg).quit();

    let result;
    try {
      result = xfoil.run(input.toString(), {
        workDir: '/work',
        files: input.files,
        scalarKeys: ['a', 'CL', 'CD', 'Cm'],
      });
    } catch (error) {
      return { ok: false, reason: `runtime:${error?.message || String(error)}` };
    }

    const cl = finiteScalar(result.output, 'CL');
    const cd = finiteScalar(result.output, 'CD');
    const cm = finiteScalar(result.output, 'Cm');
    const alphaSolved = finiteScalar(result.output, 'a');
    const valid = result.raw.exitCode === 0 && !result.output.hasNaN && !result.output.hasFortranError && !result.output.hasConvergenceFail && cl !== null && cd !== null && cm !== null && cd > 0 && cd < 0.25;
    if (!valid) {
      const flags = [];
      if (result.raw.exitCode !== 0) flags.push(`exit=${result.raw.exitCode}`);
      if (result.output.hasNaN) flags.push('nan');
      if (result.output.hasFortranError) flags.push('fortran-error');
      if (result.output.hasConvergenceFail) flags.push('convergence-fail');
      if (cl === null || cd === null || cm === null) flags.push('missing-scalars');
      if (cd !== null && !(cd > 0 && cd < 0.25)) flags.push(`cd=${cd}`);
      return { ok: false, reason: flags.join(',') || 'invalid-result' };
    }
    return { ok: true, alpha_deg: alphaSolved ?? alphaDeg, cl, cd, cm };
  } finally {
    xfoil.destroy();
  }
}

function writePolarCsv(filePath, points) {
  const rows = ['alpha_deg,cl,cd,cm'];
  for (const p of points) rows.push([p.alpha_deg.toFixed(6), p.cl.toFixed(8), p.cd.toFixed(8), p.cm.toFixed(8)].join(','));
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${rows.join('\n')}\n`);
}

async function main() {
  const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  const airfoilName = cfg.airfoil;
  const airfoilText = fs.readFileSync(path.join(AIRFOIL_DIR, `${airfoilName}.dat`), 'utf8');
  const alphas = alphaValues(Number(cfg.alpha_start_deg), Number(cfg.alpha_end_deg), Number(cfg.alpha_step_deg));
  const summary = [];

  for (const scenario of cfg.cases) {
    for (const reynolds of cfg.analysis_reynolds) {
      const points = [], failures = [];
      for (const alphaDeg of alphas) {
        const solved = await solvePoint({ airfoilText, airfoilName, reynolds, alphaDeg, scenario, cfg });
        if (solved.ok) points.push(solved); else failures.push({ alpha_deg: alphaDeg, reason: solved.reason });
      }
      points.sort((a, b) => a.alpha_deg - b.alpha_deg);
      if (points.length < Number(cfg.minimum_converged_points)) throw new Error(`${scenario.id} ${airfoilName} Re=${reynolds}: only ${points.length} valid points`);
      const alphaMin = points[0].alpha_deg, alphaMax = points[points.length - 1].alpha_deg;
      if (alphaMin > Number(cfg.required_alpha_min_deg) || alphaMax < Number(cfg.required_alpha_max_deg)) throw new Error(`${scenario.id} ${airfoilName} Re=${reynolds}: insufficient alpha coverage [${alphaMin}, ${alphaMax}]`);
      const outDir = path.join(OUTPUT_ROOT, scenario.id);
      const csvPath = path.join(outDir, `${airfoilName}_re${Math.trunc(reynolds)}.csv`);
      writePolarCsv(csvPath, points);
      const positive = points.filter((p) => p.cl > 0);
      summary.push({
        scenario_id: scenario.id,
        scenario_label: scenario.label,
        interpretation: scenario.interpretation,
        ncrit: scenario.ncrit,
        forced_transition: scenario.forced_transition,
        airfoil: airfoilName,
        reynolds: Math.trunc(reynolds),
        converged_points: points.length,
        failed_points: failures.length,
        failed_alpha: failures,
        alpha_min: alphaMin,
        alpha_max: alphaMax,
        cl_max_observed: Math.max(...points.map((p) => p.cl)),
        cd_min_observed: Math.min(...points.map((p) => p.cd)),
        best_section_ld_observed: Math.max(...positive.map((p) => p.cl / p.cd)),
        path: csvPath,
      });
      console.log(`${scenario.id} Re=${reynolds}: ${points.length}/${alphas.length} valid, alpha ${alphaMin}..${alphaMax}`);
    }
  }
  fs.mkdirSync(OUTPUT_ROOT, { recursive: true });
  fs.writeFileSync(path.join(OUTPUT_ROOT, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
  console.log(`generated ${summary.length} DAE51 transition-sensitivity polar cases`);
}

main().catch((error) => { console.error(error?.stack || error); process.exitCode = 1; });
