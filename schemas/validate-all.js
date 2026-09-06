// validate-all.js — ROOT-BASED STRICT VALIDATION
// Automatically identifies root schemas and validates only those
// Perimeter = all families at the indicated versions (together)

const fs = require("fs");
const path = require("path");
const Ajv = require("ajv/dist/2020");
const addFormats = require("ajv-formats");

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
function readJSON(filePath) {
  let text = fs.readFileSync(filePath, "utf8");
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  return JSON.parse(text);
}

function collectRefs(obj, refs) {
  if (Array.isArray(obj)) {
    obj.forEach(v => collectRefs(v, refs));
  } else if (obj && typeof obj === "object") {
    for (const [k, v] of Object.entries(obj)) {
      if (k === "$ref" && typeof v === "string") {
        refs.add(v.split("#")[0]); // absolute $id target
      } else {
        collectRefs(v, refs);
      }
    }
  }
}

// ------------------------------------------------------------
// PHASE 1 — LOAD ALL SCHEMAS (NO VALIDATION)
// ------------------------------------------------------------
const ajv = new Ajv({ strict: false, validateSchema: false });
addFormats(ajv);

const schemas = [];
const ids = new Set();
const refs = new Set();

console.log("\n=== LOADING SCHEMAS ===");

for (const dir of folders) {
  if (!fs.existsSync(dir)) continue;

  for (const file of fs.readdirSync(dir)) {
    if (!file.toLowerCase().endsWith(".json")) continue;

    const full = path.join(dir, file);
    const schema = readJSON(full);

    if (!schema.$id) {
      console.warn(`⚠️  Missing $id: ${full}`);
      continue;
    }

    if (ajv.getSchema(schema.$id)) {
      throw new Error(
        `DUPLICATE $id IN PERIMETER\n` +
        `  $id : ${schema.$id}\n` +
        `  file: ${full}`
      );
    }

    ajv.addSchema(schema, schema.$id);
    schemas.push(schema);
    ids.add(schema.$id);

    collectRefs(schema, refs);

    console.log(`Loaded: ${schema.$id}`);
  }
}

// ------------------------------------------------------------
// PHASE 2 — IDENTIFY ROOT SCHEMAS
// ------------------------------------------------------------
const rootIds = [...ids].filter(id => !refs.has(id));

console.log("\n=== ROOT SCHEMAS (ENTRY POINTS) ===");
rootIds.forEach(id => console.log(id));

if (rootIds.length === 0) {
  throw new Error("No root schemas found — invalid schema graph");
}

// ------------------------------------------------------------
// PHASE 3 — STRICT VALIDATION VIA ROOTS
// ------------------------------------------------------------
const ajvStrict = new Ajv({
  strict: true,
  allErrors: true,
  validateSchema: true
});
addFormats(ajvStrict);

// Re-register schemas in strict AJV
for (const schema of schemas) {
  ajvStrict.addSchema(schema, schema.$id);
}

console.log("\n=== VALIDATING ROOT SCHEMAS (STRICT MODE) ===");

let invalidCount = 0;

for (const rootId of rootIds) {
  try {
    // ✅ Compile ROOTS ONLY
    ajvStrict.compile({ $ref: rootId });
  } catch (err) {
    invalidCount++;
    console.log(`\n❌ INVALID ROOT SCHEMA: ${rootId}`);
    console.log(err.message);
  }
}

// ------------------------------------------------------------
// SUMMARY
// ------------------------------------------------------------
if (invalidCount === 0) {
  console.log("\n🎉 ALL ROOT SCHEMAS VALIDATED SUCCESSFULLY");
} else {
  console.log(`\n⚠️  ${invalidCount} ROOT SCHEMA(S) INVALID`);
  process.exitCode = 1;
}
