const fs = require("fs");
const path = require("path");
const JSON5 = require("json5");
const Ajv = require("ajv/dist/2020");

// ✅ Ajv configuration
const ajv = new Ajv({
  allErrors: true,
  strict: false,
  validateSchema: false,

  // ✅ IMPORTANT: disable format warnings like "date-time"
  validateFormats: false
});

// ✅ YOUR EXACT VALID DIRECTORIES
const schemaDirs = [
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/AIF/V3.0/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/AIH1/V1.0/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/AIP/V1.0/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/CAE1/V2.4/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/CAV2/V1.1/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/CUI1/V2.0/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/MMC/V2.5/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/MMM4/V2.2/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/MMM4/V2.2/actions",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/OSD/V1.5/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/PAF/V1.6/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/PTF/V1.0/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/TFA/V1.5/data",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/TFA/V1.5/types",
  "C:/Users/leona/OneDrive - CEDEO/My Standards/mpai/schemas/TFA/V1.5/formats"
];

// ✅ Load schemas
function loadSchemas() {
  const schemas = [];

  for (const dir of schemaDirs) {
    if (!fs.existsSync(dir)) {
      console.log("⚠ Missing folder:", dir);
      continue;
    }

    const files = fs.readdirSync(dir);

    for (const file of files) {
      if (!file.endsWith(".json")) continue;

      const full = path.join(dir, file);

      try {
        const schema = JSON5.parse(fs.readFileSync(full, "utf8"));
        schemas.push({ schema, file: full });

      } catch (e) {
        console.log("❌ Invalid JSON:", full);
      }
    }
  }

  return schemas;
}

const allSchemas = loadSchemas();

console.log(`✅ Loaded ${allSchemas.length} schemas\n`);


// ✅ STEP 1 — REGISTER SCHEMAS (only problems)
for (const s of allSchemas) {
  try {
    if (s.schema.$id) {
      ajv.addSchema(s.schema);
    } else {
      console.log("⚠ Missing $id:", s.file);
    }
  } catch (e) {
    console.log("❌ FAILED TO ADD:", s.file);
    console.log("   ", e.message);
  }
}


// ✅ STEP 2 — VALIDATION (NO OK output)
let ok = 0;
let errors = 0;

for (const s of allSchemas) {
  try {
    ajv.compile(s.schema);
    ok++;   // ✅ counted but NOT printed
  } catch (e) {
    console.log("❌ ERROR:", s.file);
    console.log("   ", e.message);
    errors++;
  }
}


// ✅ FINAL SUMMARY
console.log("\n===============================");
console.log("SUMMARY");
console.log("===============================");
console.log("✅ OK:", ok);
console.log("❌ Errors:", errors);
console.log("Total:", allSchemas.length);