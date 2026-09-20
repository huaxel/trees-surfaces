#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = __dirname;

function elementStore(defaultValues = {}) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      elements.set(id, {
        id,
        value: defaultValues[id] || "",
        textContent: "",
        innerHTML: "",
        hidden: true,
        href: "",
        addEventListener() {},
        setAttribute() {},
        classList: { toggle() {} },
      });
    }
    return elements.get(id);
  }
  return { elements, element };
}

async function loadPrototype(name, defaultValues = {}, dataOverrides = {}) {
  const html = fs.readFileSync(path.join(ROOT, name, "index.html"), "utf8");
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!match) throw new Error(`${name}: inline script not found`);
  const { element } = elementStore(defaultValues);
  const document = {
    getElementById: element,
    querySelectorAll() { return []; },
  };
  const fetch = async relative => ({
    json: async () => relative in dataOverrides
      ? JSON.parse(JSON.stringify(dataOverrides[relative]))
      : JSON.parse(fs.readFileSync(path.join(ROOT, name, relative), "utf8")),
  });
  const context = {
    document,
    fetch,
    console,
    Map,
    Math,
    Number,
    String,
    Object,
    Promise,
    encodeURIComponent,
    setTimeout,
  };
  vm.createContext(context);
  vm.runInContext(match[1], context, { filename: `${name}/index.html` });
  await new Promise(resolve => setTimeout(resolve, 100));
  return { context, element };
}

function requireIncludes(value, expected, label) {
  if (!value.includes(expected)) {
    throw new Error(`${label}: missing ${JSON.stringify(expected)}`);
  }
}

async function testTrees() {
  const { context, element } = await loadPrototype("trees-surfaces", { heat: "60", proximity: "40" });
  const quality = element("dataQuality").textContent;
  for (const expected of [
    "100/100 valid coordinates",
    "heat joined 100/100 with 0 NoData pixels",
    "nearest-counter joined 100/100",
    "measured-flow context 97/100",
    "vbx_58411, vbx_58413, vbx_58589",
    "all core analysis joins are complete",
  ]) requireIncludes(quality, expected, "Trees data completeness");
  requireIncludes(element("sensitivity").innerHTML, "9/10 with heat-only", "Trees sensitivity");
  requireIncludes(element("sensitivity").innerHTML, "1/10 with proximity-only", "Trees sensitivity");
  requireIncludes(element("sourceLinks").innerHTML, "City of Brussels/Data Management", "Trees managed-tree attribution");
  requireIncludes(element("sourceLinks").innerHTML, "Bruxelles Mobilité", "Trees managed-tree catalogue credits");
  requireIncludes(element("sourceLinks").innerHTML, "heritage.brussels", "Trees remarkable-tree attribution");
  requireIncludes(element("sourceLinks").innerHTML, "NGI-IGN, ngi.be", "Trees remarkable-tree catalogue credits");
  requireIncludes(element("sourceLinks").innerHTML, "Brussels Environment / Leefmilieu Brussel, CC BY 4.0", "Trees heat attribution");
  requireIncludes(element("sourceLinks").innerHTML, "Brussels Mobility, CC0 1.0", "Trees mobility attribution");
  requireIncludes(element("stakeholderDecision").innerHTML, "Stakeholder review pending", "Trees stakeholder state");
  requireIncludes(element("detail").innerHTML, "not a causal mobility estimate or a planting recommendation", "Trees interpretation boundary");

  const dataDir = path.join(ROOT, "trees-surfaces", "data");
  const artifact = JSON.parse(fs.readFileSync(path.join(dataDir, "tree-signal-sensitivity.json"), "utf8"));
  const browserRanking = vm.runInContext(
    "[...sites].map(site => ({id: site.id, signal: score(site, {h: 0.6, p: 0.4})})).sort(compareRanked)",
    context,
  );
  for (const [index, expected] of artifact.balanced_screening.entries()) {
    const actual = browserRanking[index];
    if (actual.id !== expected.id || actual.signal !== expected.signal) {
      throw new Error(`Trees artifact parity at rank ${index + 1}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`);
    }
  }
  const tiedIds = vm.runInContext("[{id: 'b', signal: 1}, {id: 'a', signal: 1}].sort(compareRanked).map(row => row.id).join(',')", context);
  if (tiedIds !== "a,b") throw new Error(`Trees tied ranking is unstable: ${tiedIds}`);
  vm.runInContext("$('heat').value = '0'; $('proximity').value = '0'", context);
  const zeroWeights = vm.runInContext("weights()", context);
  if (zeroWeights.h !== 0.5 || zeroWeights.p !== 0.5) {
    throw new Error(`Trees zero-sum weights are not normalized: ${JSON.stringify(zeroWeights)}`);
  }

  const joined = JSON.parse(fs.readFileSync(path.join(dataDir, "brussels-tree-bike-nearest.json"), "utf8"));
  const heat = JSON.parse(fs.readFileSync(path.join(dataDir, "brussels-tree-heat-sample.json"), "utf8"));
  const nearest = joined.records.reduce((best, row) =>
    row.nearest_counter_distance_m < best.nearest_counter_distance_m ? row : best
  );
  heat.records = heat.records.filter(row => row.id !== nearest.id);
  const incomplete = await loadPrototype(
    "trees-surfaces",
    { heat: "60", proximity: "40" },
    { "data/brussels-tree-heat-sample.json": heat },
  );
  const proximityRange = vm.runInContext(
    "[Math.min(...sites.map(site => site.proximityScore)), Math.max(...sites.map(site => site.proximityScore))]",
    incomplete.context,
  );
  if (proximityRange[0] !== 0 || proximityRange[1] !== 100) {
    throw new Error(`Trees incomplete-join normalization: expected 0–100, got ${proximityRange}`);
  }
}

(async () => {
  await testTrees();
  console.log("Trees & Surfaces UI smoke test passed");
})().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
