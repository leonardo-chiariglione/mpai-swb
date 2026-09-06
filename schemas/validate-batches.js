// validate-batches.js
// HARD JSON-SCHEMA VALIDATION BY CLOSED BATCHES
// Correctly distinguishes schemas vs non-schema JSON (AIMs / AIWs)

const fs = require("fs");
const path = require("path");
const Ajv = require("ajv/dist/2020");
const addFormats = require("ajv-formats");

// ============================================================
// CONFIGURATION
// ============================================================

const BASE = "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas";

const BATCHES = {
  "OSD-V1.5": [
    "OSD/V1.5/data"
  ],

  "AIH1-V1.0": [
    "AIH1/V1.0/data",
    "AIH1/V1.0/AIMs",
    "AIH1/V1.0/AIWs"
  ],

  "PTF-V1.0": [
    "PTF/V1.0/data"
  ],

  "TFA-V1.5": [
    "TFA/V1.5/data",
    "TFA/V1.5/formats",
    "TFA/V1.5/types"
  ],

  "MMM4-V2.2": [
    "MMM4/V2.2/data",
    "MMM4/V2.2/actions"
  ],

  "MMC-V2.5": [
    "MMC/V2.5/data"
  ],

  "PAF-V1.6": [
    "PAF/V1.6/data"
  ],

  "AIF-V3.0": [
    "AIF/V3.0/data"
  ]
};

// ============================================================
// UTILITIES
// ============================================================

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
        refs.add(v.split("#")[0]);
      } else {
        collectRefs(v, refs);
      }
    }
  }
}

function isSchemaFile(fullPath) {
  return (
    fullPath.includes(`${path.sep}data${path.sep}`) ||
    fullPath.includes(`${path.sep}formats${path.sep}`) ||
    fullPath.includes(`${path.sep}types${path.sep}`)
  );
}

// ============================================================
// VALIDATE ONE BATCH
// ============================================================

function validateBatch(batchName, relFolders) {
  console.log(`\n==============================`);
  console.log(`VALIDATING BATCH: ${batchName}`);
  console.log(`==============================`);

  const ajv = new Ajv({
    strict: true,
    allErrors: true,
    validateSchema: true
  });
  addFormats(ajv);

  const schemas = [];
  const ids = new Set();
  const refs = new Set();

  // --------------------------
  // LOAD FILES
  // --------------------------
  for (const rel of relFolders) {
    const dir = path.join(BASE, rel);
    if (!fs.existsSync(dir)) {
      throw new Error(`Missing folder for batch ${batchName}: ${dir}`);
    }

    for (const file of fs.readdirSync(dir)) {
      if (!file.endsWith(".json")) continue;

      const full = path.join(dir, file);
      const json = readJSON(full);

      const isSchema = isSchemaFile(full);

      // Enforce $id only for schemas
      if (isSchema) {
        if (!json.$id) {
          throw new Error(`Missing $id in schema ${full}`);
        }

        if (ids.has(json.$id)) {
          throw new Error(
            `Duplicate $id inside batch ${batchName}\n` +
            `  $id: ${json.$id}\n` +
            `  file: ${full}`
          );
        }

        ajv.addSchema(json, json.$id);
        schemas.push(json);
        ids.add(json.$id);
        collectRefs(json, refs);
      }
      // Non-schema JSON (AIMs / AIWs) is intentionally ignored for schema graph
    }
  }

  // --------------------------
  // FIND ROOT SCHEMAS
  // --------------------------
  const roots = schemas.filter(s => !refs.has(s.$id));

  if (roots.length === 0) {
    throw new Error(`No root schemas found in batch ${batchName}`);
  }

  console.log(`Roots (${roots.length}):`);
  roots.forEach(r => console.log(`  ${r.$id}`));

  // --------------------------
  // COMPILE ROOTS ONLY
  // --------------------------
  let errors = 0;

  for (const root of roots) {
    try {
      ajv.compile({ $ref: root.$id });
    } catch (e) {
      errors++;
      console.log(`\n❌ INVALID ROOT in ${batchName}`);
      console.log(`  ${root.$id}`);
      console.log(e.message);
    }
  }

  if (errors === 0) {
    console.log(`✅ ${batchName} PASSED`);
  } else {
    console.log(`❌ ${batchName} FAILED (${errors} errors)`);
    process.exitCode = 1;
  }
}

// ============================================================
// MAIN
// ============================================================

for (const [name, folders] of Object.entries(BATCHES)) {
  validateBatch(name, folders);
}

console.log("\n==============================");
console.log("BATCH VALIDATION COMPLETE");
console.log("==============================");