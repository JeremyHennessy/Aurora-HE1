#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { WebXFOIL } from "webxfoil-wasm";

const CONFIG_PATH = process.env.HE1_AIRFOIL_CONFIG || "config/airfoil_sources.json";
const AIRFOIL_DIR = process.env.HE1_AIRFOIL_DIR || "analysis/airfoils";
const OUTPUT_DIR = process.env.HE1_POLAR_DIR || "analysis/polars";

function alphaValues(start, end, step) {
  const values = [];
  const n = Math.round((end - start) / step);
  for (let i = 0; i <= n; i += 1) {
    values.push(Number((start + i * step).toFixed(8)));
  }
  return values;
}

function finiteScalar(output, key) {
  const value = output?.scalars?.[key]?.value;
  return Number.isFinite(value) ? value : null;
}

async function solvePoint({ airfoilText, airfoilName, reynolds, alphaDeg, xcfg }) {
  const xfoil = await WebXFOIL.load();
  try {
    const input = WebXFOIL.input();
    input.loadAirfoilText(airfoilText, { path: `${airfoilName}.dat`, name: airfoilName.toUpperCase() });
    input
      .add("PANE")
      .oper()
      .add("MACH 0")
      .add(`VISC ${reynolds}`)
      .add(`ITER ${Number(xcfg.iteration_limit)}`)
      .add("VPAR")
      .add(`N ${Number(xcfg.ncrit)}`)
      .blank()
      .setAlpha(alphaDeg)
      .quit();

    let result;
    try {
      result = xfoil.run(input.toString(), {
        workDir: "/work",
        files: input.files,
        scalarKeys: ["a", "CL", "CD", "Cm"],
      });
    } catch (error) {
      return { ok: false, reason: `runtime:${error?.message || String(error)}` };
    }

    const cl = finiteScalar(result.output, "CL");
    const cd = finiteScalar(result.output, "CD");
    const cm = finiteScalar(result.output, "Cm");
    const alphaSolved = finiteScalar(result.output, "a");
    const valid =
      result.raw.exitCode === 0 &&
      !result.output.hasNaN &&
      !result.output.hasFortranError &&
      !result.output.hasConvergenceFail &&
      cl !== null &&
      cd !== null &&
      cm !== null &&
      cd > 0 &&
      cd < 0.25;

    if (!valid) {
      const flags = [];
      if (result.raw.exitCode !== 0) flags.push(`exit=${result.raw.exitCode}`);
      if (result.output.hasNaN) flags.push("nan");
      if (result.output.hasFortranError) flags.push("fortran-error");
      if (result.output.hasConvergenceFail) flags.push("convergence-fail");
      if (cl === null || cd === null || cm === null) flags.push("missing-scalars");
      if (cd !== null && !(cd > 0 && cd < 0.25)) flags.push(`cd=${cd}`);
      return { ok: false, reason: flags.join(",") || "invalid-result" };
    }

    return {
      ok: true,
      alpha_deg: alphaSolved ?? alphaDeg,
      cl,
      cd,
      cm,
    };
  } finally {
    xfoil.destroy();
  }
}

function writePolarCsv(filePath, points) {
  const rows = ["alpha_deg,cl,cd,cm"];
  for (const point of points) {
    rows.push([
      point.alpha_deg.toFixed(6),
      point.cl.toFixed(8),
      point.cd.toFixed(8),
      point.cm.toFixed(8),
    ].join(","));
  }
  fs.writeFileSync(filePath, `${rows.join("\n")}\n`);
}

async function main() {
  const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8"));
  const xcfg = cfg.xfoil;
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const alphas = alphaValues(Number(xcfg.alpha_start_deg), Number(xcfg.alpha_end_deg), Number(xcfg.alpha_step_deg));
  const summaries = [];

  for (const [name, meta] of Object.entries(cfg.airfoils)) {
    const airfoilText = fs.readFileSync(path.join(AIRFOIL_DIR, `${name}.dat`), "utf8");
    for (const reynolds of meta.analysis_reynolds) {
      const points = [];
      const failures = [];
      for (const alphaDeg of alphas) {
        const solved = await solvePoint({ airfoilText, airfoilName: name, reynolds, alphaDeg, xcfg });
        if (solved.ok) points.push(solved);
        else failures.push({ alpha_deg: alphaDeg, reason: solved.reason });
      }
      points.sort((a, b) => a.alpha_deg - b.alpha_deg);
      if (points.length < Number(xcfg.minimum_converged_points)) {
        throw new Error(`${name} Re=${reynolds}: only ${points.length} valid points`);
      }
      const alphaMin = points[0].alpha_deg;
      const alphaMax = points[points.length - 1].alpha_deg;
      if (alphaMin > Number(xcfg.required_alpha_min_deg) || alphaMax < Number(xcfg.required_alpha_max_deg)) {
        throw new Error(`${name} Re=${reynolds}: insufficient alpha coverage [${alphaMin}, ${alphaMax}]`);
      }
      const csvPath = path.join(OUTPUT_DIR, `${name}_re${Math.trunc(reynolds)}.csv`);
      writePolarCsv(csvPath, points);
      const positive = points.filter((p) => p.cl > 0);
      summaries.push({
        airfoil: name,
        reynolds: Math.trunc(reynolds),
        solver: "XFOIL 6.996 via webxfoil-wasm 0.1.1",
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
      console.log(`${name} Re=${reynolds}: ${points.length}/${alphas.length} points, alpha ${alphaMin}..${alphaMax}`);
    }
  }

  fs.writeFileSync(path.join(OUTPUT_DIR, "summary.json"), `${JSON.stringify(summaries, null, 2)}\n`);
  console.log(`generated ${summaries.length} viscous polar cases with isolated alpha solves`);
}

main().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
