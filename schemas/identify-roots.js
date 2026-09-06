// identify-roots.js — find root schemas in a schema perimeter

const fs = require("fs");
const path = require("path");

// ------------------------------------------------------------
// CONFIGURATION
// ------------------------------------------------------------
const BASE = "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas";

const folders = [
  `${BASE}/AIF/V3.0/data`,
  `${BASE}/AIH1/V1.0/data`,
  `${BASE}/CAE1/V2.4/data`,
  `${BASE}/MMC/V2.5/data`,
  `${BASE}/MMM4/V2.2/actions`,
  `${BASE}/MMM4/V2.2/data`,
  `${BASE}/OSD/V1.5/data`,
  `${BASE}/PAF/V1.6/data`,
  `${BASE}/PTF/V1.0/data`,
  `${BASE}/TFA/V1.5/data`,
  `${BASE}/TFA/V1.5/formats`,
  `${BASE}/TFA/V1.5/types`
];

// ------------------------------------------------------------
// UTILITIES
// ------------------------------------------------------------
function readJSON(file) {
  let text = fs.readFileSync(file, "utf8");
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  return JSON.parse(text);
}

function collectRefs(obj, refs) {
  if (Array.isArray(obj)) {
    obj.forEach(v => collectRefs(v, refs));
  } else if (obj && typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (k === "$ref" && typeof v === "string") {
        refs.add(v.split("#")[0]); // absolute ref target
      } else {
        collectRefs(v, refs);
      }
    }
  }
}

// ------------------------------------------------------------
// SCAN PERIMETER
// ------------------------------------------------------------
const schemas = [];
const ids = new Set();
const refs = new Set();

for (const dir of folders) {
  if (!fs.existsSync(dir)) continue;

  for (const file of fs.readdirSync(dir)) {
    if (!file.toLowerCase().endsWith(".json")) continue;

    const full = path.join(dir, file);
    const schema = readJSON(full);

    if (!schema.$id) continue;

    schemas.push({ id: schema.$id, file: full, schema });
    ids.add(schema.$id);

    collectRefs(schema, refs);
  }
}

// ------------------------------------------------------------
// FIND ROOTS
// ------------------------------------------------------------
const roots = schemas.filter(s => !refs.has(s.id));

// ------------------------------------------------------------
// OUTPUT
// ------------------------------------------------------------
console.log("\n=== ROOT SCHEMAS (ENTRY POINTS) ===\n");

roots.forEach(r => {
  console.log(r.id);
});

console.log(`\nTotal schemas: ${schemas.length}`);
console.log(`Referenced schemas: ${refs.size}`);
console.log(`Root schemas: ${roots.length}`);