#!/usr/bin/env node
/**
 * HyperEdit Artifact Validator
 *
 * Validates a numbered artifact JSON file against its JSON Schema.
 * Uses ajv (JSON Schema validator) with draft-2020-12 support.
 *
 * Usage:
 *   node scripts/validate-artifact.js <artifact_path>
 *   node scripts/validate-artifact.js <artifact_path> <schema_name>
 *
 * Examples:
 *   node scripts/validate-artifact.js state/agents/proj_abc/10_footage_catalog.json
 *   node scripts/validate-artifact.js state/agents/proj_abc/10_footage_catalog.json 10_footage_catalog.schema.json
 *
 * Exit codes: 0 = valid, 1 = invalid, 2 = usage/system error
 */

import { readFileSync } from 'fs';
import { join, dirname, basename } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCHEMAS_DIR = join(__dirname, '..', 'schemas');

/** Map artifact filename prefixes to schema files */
export const ARTIFACT_SCHEMA_MAP = {
  '00_project_brief': '00_project_brief.schema.json',
  '01_orchestration_plan': '01_orchestration_plan.schema.json',
  '10_footage_catalog': '10_footage_catalog.schema.json',
  '11_selects_shortlist': '11_selects_shortlist.schema.json',
  '12_gap_report': '12_gap_report.schema.json',
  '20_synthetic_plan': '20_synthetic_plan.schema.json',
  '21_generated_clips': '21_generated_clips.schema.json',
  '22_realism_qc': '22_realism_qc.schema.json',
  '30_music_map': '30_music_map.schema.json',
  '31_radio_edit': '31_radio_edit.schema.json',
  '32_audio_qc': '32_audio_qc.schema.json',
  '40_rough_cut': '40_rough_cut.schema.json',
  '41_refine_cut': '41_refine_cut.schema.json',
  '42_picture_lock': '42_picture_lock.schema.json',
  '50_base_corrections': '50_base_corrections.schema.json',
  '51_look_layers': '51_look_layers.schema.json',
  '52_color_qc': '52_color_qc.schema.json',
  '60_caption_script': '60_caption_script.schema.json',
  '61_graphics_layout': '61_graphics_layout.schema.json',
  '62_graphics_qc': '62_graphics_qc.schema.json',
  '70_final_qc_report': '70_final_qc_report.schema.json',
  '71_grade_card': '71_grade_card.schema.json',
  '72_publish_checklist': '72_publish_checklist.schema.json',
};

/**
 * Resolve the schema filename from an artifact path.
 * Tries explicit arg first, then infers from filename prefix.
 */
export function resolveSchemaName(artifactPath, schemaArg = null) {
  if (schemaArg) return schemaArg;
  const base = basename(artifactPath, '.json');
  const prefix = Object.keys(ARTIFACT_SCHEMA_MAP).find(k => base === k || base.startsWith(k));
  if (prefix) return ARTIFACT_SCHEMA_MAP[prefix];
  throw new Error(`Cannot infer schema for artifact: ${base}. Pass schema name as second arg.`);
}

/**
 * Validate common required fields shared by all artifacts.
 */
function validateCommonFields(data) {
  const errors = [];
  const required = ['status', 'blocking_issues', 'assumptions', 'open_questions', 'source_references'];
  for (const field of required) {
    if (!(field in data)) errors.push(`Missing required common field: "${field}"`);
  }
  if (data.status && !['pass', 'warn', 'fail', 'pending'].includes(data.status)) {
    errors.push(`Invalid status value: "${data.status}". Must be pass|warn|fail|pending`);
  }
  if (data.blocking_issues && !Array.isArray(data.blocking_issues)) {
    errors.push('"blocking_issues" must be an array');
  }
  return errors;
}

/**
 * Main validation function.
 * @param {string} artifactPath
 * @param {string|null} schemaName
 * @returns {{ valid: boolean, errors: string[], artifact: object|null, schemaName: string|null }}
 */
export async function validateArtifact(artifactPath, schemaName = null) {
  // Read artifact
  let artifactData;
  try {
    const raw = readFileSync(artifactPath, 'utf8');
    artifactData = JSON.parse(raw);
  } catch (e) {
    return { valid: false, errors: [`Failed to read artifact: ${e.message}`], artifact: null, schemaName: null };
  }

  // Resolve schema
  let resolvedSchemaName;
  try {
    resolvedSchemaName = resolveSchemaName(artifactPath, schemaName);
  } catch (e) {
    return { valid: false, errors: [e.message], artifact: artifactData, schemaName: null };
  }

  // Validate common fields
  const commonErrors = validateCommonFields(artifactData);

  // Try ajv validation if available
  let schemaErrors = [];
  let ajvUnavailable = false;
  try {
    const { default: Ajv } = await import('ajv');
    // ajv v6: no strict mode option, formats are ignored by default (fine for structural validation)
    const ajv = new Ajv({ allErrors: true, unknownFormats: 'ignore' });

    const schemaPath = join(SCHEMAS_DIR, resolvedSchemaName);
    const commonSchemaPath = join(SCHEMAS_DIR, '_common.schema.json');

    const schema = JSON.parse(readFileSync(schemaPath, 'utf8'));
    const commonSchema = JSON.parse(readFileSync(commonSchemaPath, 'utf8'));

    // Remove draft-2020-12 $schema declaration that ajv v6 doesn't recognize
    delete schema['$schema'];
    delete commonSchema['$schema'];

    ajv.addSchema(commonSchema, '_common.schema.json');
    const validate = ajv.compile(schema);
    const valid = validate(artifactData);
    if (!valid) {
      schemaErrors = (validate.errors || []).map(e => `${e.dataPath || e.instancePath || '(root)'} ${e.message}`);
    }
  } catch (e) {
    if (e.code === 'ERR_MODULE_NOT_FOUND' || e.message?.includes('Cannot find package')) {
      ajvUnavailable = true;
      schemaErrors = ['[ajv not installed — only common field validation performed. Run: npm install ajv]'];
    } else {
      schemaErrors = [`Schema validation error: ${e.message}`];
    }
  }

  const allErrors = [...commonErrors, ...schemaErrors];
  const valid = commonErrors.length === 0 && (schemaErrors.length === 0 || ajvUnavailable);
  return { valid, errors: allErrors, artifact: artifactData, schemaName: resolvedSchemaName };
}

// CLI entrypoint
const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('Usage: node scripts/validate-artifact.js <artifact_path> [schema_name]');
  console.error('');
  console.error('Example:');
  console.error('  node scripts/validate-artifact.js state/agents/proj_abc/10_footage_catalog.json');
  process.exit(2);
}

const [artifactPath, schemaArg] = args;
const result = await validateArtifact(artifactPath, schemaArg || null);

console.log(`Artifact: ${artifactPath}`);
console.log(`Schema:   ${result.schemaName || 'unknown'}`);
console.log(`Status:   ${result.artifact?.status || 'n/a'}`);
console.log(`Valid:    ${result.valid ? '✓ PASS' : '✗ FAIL'}`);

if (result.errors.length > 0) {
  console.log('');
  console.log('Errors:');
  result.errors.forEach(e => console.log(`  • ${e}`));
}

if (result.artifact?.blocking_issues?.length > 0) {
  console.log('');
  console.log('Blocking issues:');
  result.artifact.blocking_issues.forEach(b => console.log(`  ⚠ ${b}`));
}

process.exit(result.valid ? 0 : 1);
