#!/usr/bin/env node
/**
 * bridge-catalog.js
 *
 * Transforms the auto-sort pipeline's shot-catalog.json into the orchestrator's
 * expected artifacts: 10_footage_catalog.json and 11_selects_shortlist.json.
 *
 * Usage:
 *   node scripts/bridge-catalog.js <project-path>
 *
 * Example:
 *   node scripts/bridge-catalog.js /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, basename, extname, dirname } from 'path';
import { fileURLToPath } from 'url';
import { spawnSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Shot-class mapping
// ---------------------------------------------------------------------------

/**
 * Map classification.primary + classification.location to the shot_class enum.
 *
 * Enum values: wide_exterior | wide_interior | medium | close_up | aerial | transition | unknown
 *
 * Input primary tags from the auto-sort taxonomy:
 *   wide, tight, detail, drone, agent-on-camera
 *
 * Input location values:
 *   exterior, interior
 */
function toShotClass(primary, location) {
  const p = (primary || '').toLowerCase().trim();
  const loc = (location || '').toLowerCase().trim();

  if (p === 'drone') return 'aerial';

  if (p === 'wide') {
    if (loc === 'exterior') return 'wide_exterior';
    if (loc === 'interior') return 'wide_interior';
    // Default wide with no location info
    return 'wide_exterior';
  }

  if (p === 'tight' || p === 'medium') return 'medium';

  if (p === 'detail' || p === 'close-up' || p === 'close_up') return 'close_up';

  if (p === 'agent-on-camera' || p === 'agent_on_camera') return 'medium';

  if (p === 'transition') return 'transition';

  return 'unknown';
}

// ---------------------------------------------------------------------------
// Usability from confidence
// ---------------------------------------------------------------------------

function toUsability(confidence) {
  const c = typeof confidence === 'number' ? confidence : 0;
  if (c >= 0.7) return 'select';
  if (c >= 0.5) return 'backup';
  return 'reject';
}

// ---------------------------------------------------------------------------
// Quality score (0-10) from confidence (0-1)
// ---------------------------------------------------------------------------

function toQualityScore(confidence) {
  const c = typeof confidence === 'number' ? confidence : 0;
  return Math.round(Math.min(10, Math.max(0, c * 10)) * 10) / 10;
}

// ---------------------------------------------------------------------------
// Derive clip_id from path (stem of filename, no extension)
// ---------------------------------------------------------------------------

function toClipId(filePath) {
  const file = basename(filePath);
  const ext = extname(file);
  return ext ? file.slice(0, -ext.length) : file;
}

// ---------------------------------------------------------------------------
// Select reason string
// ---------------------------------------------------------------------------

function buildSelectReason(confidence, shotClass, roomZone) {
  const pct = Math.round((typeof confidence === 'number' ? confidence : 0) * 100);
  const parts = [`High confidence (${typeof confidence === 'number' ? confidence.toFixed(2) : '0.00'})`];
  if (shotClass && shotClass !== 'unknown') parts.push(`${shotClass.replace(/_/g, ' ')} coverage`);
  if (roomZone) parts.push(`zone: ${roomZone}`);
  return parts.join(', ');
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error('Usage: node scripts/bridge-catalog.js <project-path>');
    console.error('');
    console.error('Example:');
    console.error('  node scripts/bridge-catalog.js /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline');
    process.exit(2);
  }

  const projectPath = args[0].replace(/\/$/, '');

  // ------------------------------------------------------------------
  // Derive project_id
  // ------------------------------------------------------------------
  let projectId = basename(projectPath);

  // Override from brief.json if available
  const briefPath = join(projectPath, 'brief.json');
  if (existsSync(briefPath)) {
    try {
      const brief = JSON.parse(readFileSync(briefPath, 'utf8'));
      if (brief.project_id && typeof brief.project_id === 'string') {
        projectId = brief.project_id;
      }
    } catch (e) {
      console.warn(`[warn] Could not parse brief.json: ${e.message}. Using folder name as project_id.`);
    }
  }

  // ------------------------------------------------------------------
  // Read shot-catalog.json
  // ------------------------------------------------------------------
  const catalogPath = join(projectPath, 'shot-catalog.json');
  if (!existsSync(catalogPath)) {
    console.error(`[error] shot-catalog.json not found at: ${catalogPath}`);
    process.exit(1);
  }

  let shotCatalog;
  try {
    shotCatalog = JSON.parse(readFileSync(catalogPath, 'utf8'));
  } catch (e) {
    console.error(`[error] Failed to parse shot-catalog.json: ${e.message}`);
    process.exit(1);
  }

  const entries = Object.entries(shotCatalog);
  if (entries.length === 0) {
    console.warn('[warn] shot-catalog.json is empty. Output artifacts will have zero clips.');
  }

  // ------------------------------------------------------------------
  // Build clips array for 10_footage_catalog.json
  // ------------------------------------------------------------------
  const clips = [];

  for (const [relativePath, entry] of entries) {
    const classification = entry.classification || {};
    let primary = classification.primary || entry.bin || 'unknown';
    const location = classification.location || '';
    const roomZone = classification.room || '';
    const confidence = typeof classification.confidence === 'number' ? classification.confidence : 0;

    // Camera-aware drone override: only DJI-named files can be drone
    const fnameUpper = basename(relativePath).toUpperCase();
    if (primary === 'drone' && !fnameUpper.startsWith('DJI_')) {
      primary = 'wide';
    }

    const shotClass = toShotClass(primary, location);
    const qualityScore = toQualityScore(confidence);
    const usability = toUsability(confidence);

    const filename = basename(relativePath);
    const clipId = toClipId(relativePath);

    clips.push({
      clip_id: clipId,
      filename,
      path: relativePath,
      duration_seconds: typeof entry.duration === 'number' ? entry.duration : 0,
      shot_class: shotClass,
      room_zone: roomZone || 'unknown',
      direction: 'unknown',
      quality_score: qualityScore,
      usability,
      proxy_path: `proxies/${clipId}_proxy.mp4`,
    });
  }

  const totalDurationAll = clips.reduce((sum, c) => sum + c.duration_seconds, 0);

  // ------------------------------------------------------------------
  // Build 10_footage_catalog.json
  // ------------------------------------------------------------------
  const footageCatalog = {
    status: 'pass',
    blocking_issues: [],
    assumptions: [
      'quality_score derived from classification.confidence * 10',
      'direction defaulted to "unknown" — not available from shot-catalog',
      'proxy_path assumes standard proxies/<clip_id>_proxy.mp4 convention',
      'room_zone falls back to "unknown" when classification.room is absent',
    ],
    open_questions: [],
    source_references: [
      { type: 'file', path: catalogPath, description: 'Auto-sort pipeline shot-catalog.json' },
    ],
    project_id: projectId,
    footage_directory: join(projectPath, 'footage'),
    total_clips: clips.length,
    total_duration_seconds: Math.round(totalDurationAll * 100) / 100,
    clips,
  };

  // ------------------------------------------------------------------
  // Build selects list for 11_selects_shortlist.json
  // ------------------------------------------------------------------

  // Filter to "select" usability only
  const selectedClips = clips.filter(c => c.usability === 'select');

  // Group by room_zone
  const byRoom = {};
  for (const clip of selectedClips) {
    const zone = clip.room_zone || 'unknown';
    if (!byRoom[zone]) byRoom[zone] = [];
    byRoom[zone].push(clip);
  }

  // Within each room_zone, sort by quality_score descending
  for (const zone of Object.keys(byRoom)) {
    byRoom[zone].sort((a, b) => b.quality_score - a.quality_score);
  }

  // Enforce coverage: at least 1 wide + 1 detail per room_zone where available.
  // We reorder within each zone so that the mandatory coverage clips come first,
  // then the rest sorted by quality_score.
  const orderedSelects = [];
  const roomCoverage = {};

  for (const zone of Object.keys(byRoom).sort()) {
    const zoneClips = byRoom[zone];

    // Find the best wide (wide_exterior | wide_interior) and best detail (close_up) for this zone
    const wideClip = zoneClips.find(c => c.shot_class === 'wide_exterior' || c.shot_class === 'wide_interior');
    const detailClip = zoneClips.find(c => c.shot_class === 'close_up');

    // Gather the mandatory coverage clips first (deduped), then the rest
    const mandatoryIds = new Set();
    const zoneOrdered = [];

    if (wideClip) {
      mandatoryIds.add(wideClip.clip_id);
      zoneOrdered.push(wideClip);
    }
    if (detailClip && !mandatoryIds.has(detailClip.clip_id)) {
      mandatoryIds.add(detailClip.clip_id);
      zoneOrdered.push(detailClip);
    }

    // Remaining clips for this zone, already sorted by quality_score desc
    for (const clip of zoneClips) {
      if (!mandatoryIds.has(clip.clip_id)) {
        zoneOrdered.push(clip);
      }
    }

    orderedSelects.push(...zoneOrdered);
    roomCoverage[zone] = zoneOrdered.length;
  }

  // Assign sequence_position (1-based)
  const selects = orderedSelects.map((clip, idx) => {
    const classification = shotCatalog[clip.path]?.classification || {};
    const confidence = typeof classification.confidence === 'number' ? classification.confidence : 0;

    return {
      clip_id: clip.clip_id,
      sequence_position: idx + 1,
      in_point_seconds: 0,
      out_point_seconds: clip.duration_seconds,
      usable_duration_seconds: clip.duration_seconds,
      shot_class: clip.shot_class,
      room_zone: clip.room_zone,
      direction: clip.direction,
      select_reason: buildSelectReason(confidence, clip.shot_class, clip.room_zone),
    };
  });

  const totalDurationSelects = selects.reduce((sum, s) => sum + s.usable_duration_seconds, 0);

  const selectsShortlist = {
    status: 'pass',
    blocking_issues: [],
    assumptions: [
      'Auto-generated from classification confidence scores',
      'in_point_seconds defaults to 0 (full clip used)',
      'Sequence ordered by room_zone (alphabetical) then quality_score descending within each zone',
      'Coverage enforcement: at least 1 wide + 1 detail per room_zone placed first in zone group',
    ],
    open_questions: [],
    source_references: [
      { type: 'artifact', path: '10_footage_catalog.json' },
      { type: 'file', path: catalogPath, description: 'Auto-sort pipeline shot-catalog.json' },
    ],
    project_id: projectId,
    total_selected: selects.length,
    total_duration_seconds: Math.round(totalDurationSelects * 100) / 100,
    selects,
    room_coverage: roomCoverage,
  };

  // ------------------------------------------------------------------
  // Write outputs to state/agents/<project_id>/
  // ------------------------------------------------------------------
  const repoRoot = join(__dirname, '..');
  const outputDir = join(repoRoot, 'state', 'agents', projectId);
  mkdirSync(outputDir, { recursive: true });

  const footageCatalogPath = join(outputDir, '10_footage_catalog.json');
  const selectsShortlistPath = join(outputDir, '11_selects_shortlist.json');

  writeFileSync(footageCatalogPath, JSON.stringify(footageCatalog, null, 2), 'utf8');
  writeFileSync(selectsShortlistPath, JSON.stringify(selectsShortlist, null, 2), 'utf8');

  // ------------------------------------------------------------------
  // Validation (optional — only if validate-artifact.js exists)
  // ------------------------------------------------------------------
  const validatorPath = join(__dirname, 'validate-artifact.js');
  const validationResults = [];

  if (existsSync(validatorPath)) {
    for (const [label, filePath] of [
      ['10_footage_catalog.json', footageCatalogPath],
      ['11_selects_shortlist.json', selectsShortlistPath],
    ]) {
      const result = spawnSync('node', [validatorPath, filePath], {
        encoding: 'utf8',
        cwd: repoRoot,
      });
      const passed = result.status === 0;
      validationResults.push({ label, passed, output: (result.stdout || '') + (result.stderr || '') });
    }
  } else {
    validationResults.push({ label: 'validator', passed: null, output: 'validate-artifact.js not found — skipped' });
  }

  // ------------------------------------------------------------------
  // Summary
  // ------------------------------------------------------------------
  console.log('');
  console.log('=== bridge-catalog.js summary ===');
  console.log('');
  console.log(`Project ID      : ${projectId}`);
  console.log(`Project path    : ${projectPath}`);
  console.log(`Output dir      : ${outputDir}`);
  console.log('');
  console.log(`Total clips     : ${footageCatalog.total_clips}`);
  console.log(`Total duration  : ${footageCatalog.total_duration_seconds}s`);
  console.log(`  selects       : ${selectsShortlist.total_selected}`);
  console.log(`  backup        : ${clips.filter(c => c.usability === 'backup').length}`);
  console.log(`  reject        : ${clips.filter(c => c.usability === 'reject').length}`);
  console.log(`Selects duration: ${selectsShortlist.total_duration_seconds}s`);
  console.log('');
  console.log('Room coverage (selects):');
  for (const [zone, count] of Object.entries(roomCoverage)) {
    console.log(`  ${zone.padEnd(20)} ${count} clip${count !== 1 ? 's' : ''}`);
  }
  if (Object.keys(roomCoverage).length === 0) {
    console.log('  (none)');
  }
  console.log('');
  console.log('Shot class breakdown (all clips):');
  const classCounts = {};
  for (const clip of clips) {
    classCounts[clip.shot_class] = (classCounts[clip.shot_class] || 0) + 1;
  }
  for (const [sc, count] of Object.entries(classCounts)) {
    console.log(`  ${sc.padEnd(20)} ${count}`);
  }
  console.log('');
  console.log('Outputs written:');
  console.log(`  ${footageCatalogPath}`);
  console.log(`  ${selectsShortlistPath}`);
  console.log('');
  console.log('Validation:');
  for (const { label, passed, output } of validationResults) {
    if (passed === null) {
      console.log(`  ${label}: SKIPPED — ${output}`);
    } else {
      const marker = passed ? 'PASS' : 'FAIL';
      console.log(`  ${label}: ${marker}`);
      if (output.trim()) {
        // Indent validation output for readability
        for (const line of output.trim().split('\n')) {
          console.log(`    ${line}`);
        }
      }
    }
  }
  console.log('');

  // Exit non-zero if any validation failed
  const anyFailed = validationResults.some(r => r.passed === false);
  if (anyFailed) {
    console.error('[error] One or more artifact validations failed.');
    process.exit(1);
  }
}

main().catch(err => {
  console.error('[fatal]', err);
  process.exit(1);
});
