#!/usr/bin/env node
/**
 * grade-pipeline.js
 *
 * Grades the AI auto-sort pipeline against a human editor's final cut.
 * Compares the AI's classifications, confidence scores, and bin assignments
 * against which clips the editor actually used.
 *
 * Usage:
 *   node scripts/grade-pipeline.js <project-path> --edit <edit-source>
 *
 * Edit sources (pick one):
 *   --edit clips-dir:<path>        Directory of clips/proxies used in final cut
 *   --edit clipwise:<session-id>   ClipWise session timeline
 *   --edit premiere:<xml-path>     Premiere Pro XML export
 *   --edit list:<txt-path>         Plain text file, one filename per line
 *   --edit bins:<bin1,bin2,...>     Grade specific bins only
 *
 * Examples:
 *   node scripts/grade-pipeline.js /Volumes/Charlie/.../20260227_Test_Pipeline --edit list:final_clips.txt
 *   node scripts/grade-pipeline.js /Volumes/Charlie/.../20260227_Test_Pipeline --edit clipwise:abc-123
 *   node scripts/grade-pipeline.js /Volumes/Charlie/.../20260227_Test_Pipeline --edit premiere:export.xml
 */

import { readFileSync, writeFileSync, existsSync, readdirSync } from 'fs';
import { join, basename, extname } from 'path';

// ─── CLI Args ────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const projectPath = args.find(a => !a.startsWith('--'));
const editArg = args.includes('--edit') ? args[args.indexOf('--edit') + 1] : null;

if (!projectPath) {
  console.error('Usage: node scripts/grade-pipeline.js <project-path> --edit <source>');
  console.error('  --edit list:<file.txt>         One clip filename per line');
  console.error('  --edit clips-dir:<path>        Directory of clips used');
  console.error('  --edit clipwise:<session-id>   ClipWise session');
  console.error('  --edit premiere:<xml-path>     Premiere XML');
  process.exit(1);
}

// ─── Load shot catalog ───────────────────────────────────────────────────────

const catalogPath = join(projectPath, 'shot-catalog.json');
if (!existsSync(catalogPath)) {
  console.error(`shot-catalog.json not found at: ${catalogPath}`);
  process.exit(1);
}

const catalog = JSON.parse(readFileSync(catalogPath, 'utf-8'));
const allClips = Object.entries(catalog);

// Build lookup by filename (case-insensitive)
const byFilename = new Map();
for (const [relPath, entry] of allClips) {
  const name = basename(relPath).toUpperCase();
  const stem = basename(relPath, extname(relPath)).toUpperCase();
  byFilename.set(name, { relPath, ...entry });
  byFilename.set(stem, { relPath, ...entry });
  // Also map proxy name
  byFilename.set(`${stem}_PROXY.MP4`, { relPath, ...entry });
}

// ─── Resolve edit source → set of clip filenames ─────────────────────────────

async function resolveEditClips() {
  if (!editArg) {
    // Interactive: ask user to provide clip list
    console.log('\nNo --edit source provided.');
    console.log('After you finish editing, run again with one of:');
    console.log('  --edit list:my_final_clips.txt   (one filename per line)');
    console.log('  --edit clips-dir:/path/to/used/   (directory of clips)');
    console.log('  --edit clipwise:<session-id>      (from ClipWise editor)');
    console.log('\nShowing catalog overview instead...\n');
    return null;
  }

  const [mode, value] = editArg.split(':');

  switch (mode) {
    case 'list': {
      if (!existsSync(value)) { console.error(`File not found: ${value}`); process.exit(1); }
      return readFileSync(value, 'utf-8')
        .split('\n')
        .map(l => l.trim())
        .filter(l => l && !l.startsWith('#'));
    }

    case 'clips-dir': {
      if (!existsSync(value)) { console.error(`Directory not found: ${value}`); process.exit(1); }
      return readdirSync(value).filter(f => /\.(mp4|mov|mxf|avi|mkv)$/i.test(f));
    }

    case 'clipwise': {
      // Read from ClipWise session
      const sessionDir = `state/local-ffmpeg/sessions/${value}`;
      const metaPath = join(sessionDir, 'assets.json');
      if (!existsSync(metaPath)) {
        console.error(`ClipWise session not found: ${metaPath}`);
        process.exit(1);
      }
      const assets = JSON.parse(readFileSync(metaPath, 'utf-8'));
      // Return original filenames from session assets
      return Object.values(assets).map(a => a.filename).filter(Boolean);
    }

    case 'premiere': {
      if (!existsSync(value)) { console.error(`XML not found: ${value}`); process.exit(1); }
      const xml = readFileSync(value, 'utf-8');
      // Extract clip filenames from Premiere XML (simplified parser)
      const filenames = [];
      const regex = /<pathurl>(?:file:\/\/)?(.+?)<\/pathurl>/g;
      let match;
      while ((match = regex.exec(xml)) !== null) {
        const path = decodeURIComponent(match[1]);
        const name = basename(path);
        if (/\.(mp4|mov|mxf|avi|mkv)$/i.test(name)) filenames.push(name);
      }
      // Deduplicate
      return [...new Set(filenames)];
    }

    case 'bins': {
      // Use all clips from specified bins
      const targetBins = value.split(',').map(b => b.trim().toLowerCase());
      return allClips
        .filter(([, entry]) => targetBins.includes((entry.bin || '').toLowerCase()))
        .map(([relPath]) => basename(relPath));
    }

    default:
      console.error(`Unknown edit source mode: ${mode}`);
      process.exit(1);
  }
}

// ─── Catalog Overview (when no edit provided) ────────────────────────────────

function showOverview() {
  const bins = {};
  const cameras = {};
  let totalDuration = 0;
  const confidences = [];

  for (const [, entry] of allClips) {
    const bin = entry.bin || 'unknown';
    bins[bin] = (bins[bin] || 0) + 1;
    const cam = entry.camera || 'unknown';
    cameras[cam] = (cameras[cam] || 0) + 1;
    totalDuration += entry.duration || 0;
    const conf = entry.classification?.confidence;
    if (typeof conf === 'number') confidences.push(conf);
  }

  const avgConf = confidences.length ? (confidences.reduce((a, b) => a + b, 0) / confidences.length) : 0;
  const minConf = confidences.length ? Math.min(...confidences) : 0;
  const selectCount = confidences.filter(c => c >= 0.7).length;
  const backupCount = confidences.filter(c => c >= 0.5 && c < 0.7).length;
  const rejectCount = confidences.filter(c => c < 0.5).length;

  console.log('━━━ Pipeline Catalog Overview ━━━\n');
  console.log(`Total clips:     ${allClips.length}`);
  console.log(`Total duration:  ${(totalDuration / 60).toFixed(1)} min`);
  console.log(`Avg confidence:  ${avgConf.toFixed(3)}`);
  console.log(`Min confidence:  ${minConf.toFixed(3)}`);
  console.log(`\nUsability breakdown:`);
  console.log(`  Select (≥0.7):  ${selectCount}`);
  console.log(`  Backup (≥0.5):  ${backupCount}`);
  console.log(`  Reject (<0.5):  ${rejectCount}`);
  console.log(`\nBins:`);
  for (const [bin, count] of Object.entries(bins).sort((a, b) => b[1] - a[1])) {
    const pct = ((count / allClips.length) * 100).toFixed(0);
    console.log(`  ${bin.padEnd(20)} ${String(count).padStart(4)}  (${pct}%)`);
  }
  console.log(`\nCameras:`);
  for (const [cam, count] of Object.entries(cameras).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${cam.padEnd(20)} ${count}`);
  }
}

// ─── Grade Against Edit ──────────────────────────────────────────────────────

function gradeAgainstEdit(editClips) {
  // Match edit clips to catalog entries
  const matched = [];
  const unmatched = [];

  for (const clip of editClips) {
    const upper = clip.toUpperCase();
    const stem = basename(clip, extname(clip)).toUpperCase();
    const entry = byFilename.get(upper) || byFilename.get(stem) || byFilename.get(`${stem}_PROXY.MP4`);
    if (entry) {
      matched.push({ editClip: clip, ...entry });
    } else {
      unmatched.push(clip);
    }
  }

  const usedSet = new Set(matched.map(m => m.relPath));
  const unused = allClips.filter(([relPath]) => !usedSet.has(relPath));

  console.log('━━━ Pipeline Grade Report ━━━\n');
  console.log(`Edit clips:       ${editClips.length}`);
  console.log(`Matched to catalog: ${matched.length}`);
  if (unmatched.length) {
    console.log(`Unmatched:        ${unmatched.length} (not in catalog)`);
    unmatched.forEach(u => console.log(`  - ${u}`));
  }
  console.log(`Unused from catalog: ${unused.length}\n`);

  // ── Classification accuracy ─────────────────────────────────────────────

  // Bin distribution of used clips
  const usedBins = {};
  const unusedBins = {};
  for (const m of matched) {
    const bin = m.bin || 'unknown';
    usedBins[bin] = (usedBins[bin] || 0) + 1;
  }
  for (const [, entry] of unused) {
    const bin = entry.bin || 'unknown';
    unusedBins[bin] = (unusedBins[bin] || 0) + 1;
  }

  console.log('Bin usage in your edit:');
  for (const [bin, count] of Object.entries(usedBins).sort((a, b) => b[1] - a[1])) {
    const totalInBin = allClips.filter(([, e]) => (e.bin || 'unknown') === bin).length;
    const pct = ((count / totalInBin) * 100).toFixed(0);
    console.log(`  ${bin.padEnd(20)} ${String(count).padStart(3)} / ${totalInBin} used (${pct}%)`);
  }

  // ── Confidence analysis ─────────────────────────────────────────────────

  const usedConfs = matched.map(m => m.classification?.confidence || 0);
  const unusedConfs = unused.map(([, e]) => e.classification?.confidence || 0);
  const avgUsedConf = usedConfs.length ? usedConfs.reduce((a, b) => a + b, 0) / usedConfs.length : 0;
  const avgUnusedConf = unusedConfs.length ? unusedConfs.reduce((a, b) => a + b, 0) / unusedConfs.length : 0;

  console.log(`\nConfidence scores:`);
  console.log(`  Used clips avg:    ${avgUsedConf.toFixed(3)}`);
  console.log(`  Unused clips avg:  ${avgUnusedConf.toFixed(3)}`);
  console.log(`  Delta:             ${(avgUsedConf - avgUnusedConf).toFixed(3)} ${avgUsedConf > avgUnusedConf ? '(AI prefers used clips ✓)' : '(AI missed quality clips ✗)'}`);

  // ── Usability accuracy ──────────────────────────────────────────────────

  const usedByUsability = { select: 0, backup: 0, reject: 0 };
  for (const m of matched) {
    const conf = m.classification?.confidence || 0;
    if (conf >= 0.7) usedByUsability.select++;
    else if (conf >= 0.5) usedByUsability.backup++;
    else usedByUsability.reject++;
  }

  const unusedByUsability = { select: 0, backup: 0, reject: 0 };
  for (const [, entry] of unused) {
    const conf = entry.classification?.confidence || 0;
    if (conf >= 0.7) unusedByUsability.select++;
    else if (conf >= 0.5) unusedByUsability.backup++;
    else unusedByUsability.reject++;
  }

  console.log(`\nUsability accuracy:`);
  console.log(`  Used clips:   ${usedByUsability.select} select, ${usedByUsability.backup} backup, ${usedByUsability.reject} reject`);
  console.log(`  Unused clips: ${unusedByUsability.select} select, ${unusedByUsability.backup} backup, ${unusedByUsability.reject} reject`);

  // False negatives: clips you used that AI marked as reject
  if (usedByUsability.reject > 0) {
    console.log(`\n  ⚠ FALSE NEGATIVES (you used, AI rejected):`);
    matched.filter(m => (m.classification?.confidence || 0) < 0.5).forEach(m => {
      console.log(`    ${basename(m.relPath)} → conf=${m.classification?.confidence?.toFixed(2)} bin=${m.bin}`);
    });
  }

  // False positives: high-confidence clips you didn't use
  const falsePositives = unused
    .filter(([, e]) => (e.classification?.confidence || 0) >= 0.85)
    .sort((a, b) => (b[1].classification?.confidence || 0) - (a[1].classification?.confidence || 0))
    .slice(0, 10);

  if (falsePositives.length) {
    console.log(`\n  ℹ TOP UNUSED HIGH-CONFIDENCE (AI thought these were great):`);
    falsePositives.forEach(([relPath, entry]) => {
      console.log(`    ${basename(relPath).padEnd(30)} conf=${entry.classification?.confidence?.toFixed(2)} bin=${entry.bin} room=${entry.classification?.room || '?'}`);
    });
  }

  // ── Room/location coverage ──────────────────────────────────────────────

  const usedRooms = {};
  const allRooms = {};
  for (const m of matched) {
    const room = m.classification?.room || 'unknown';
    usedRooms[room] = (usedRooms[room] || 0) + 1;
  }
  for (const [, entry] of allClips) {
    const room = entry.classification?.room || 'unknown';
    allRooms[room] = (allRooms[room] || 0) + 1;
  }

  console.log(`\nRoom coverage:`);
  for (const [room, total] of Object.entries(allRooms).sort((a, b) => b[1] - a[1])) {
    const used = usedRooms[room] || 0;
    const pct = total > 0 ? ((used / total) * 100).toFixed(0) : '0';
    const bar = '█'.repeat(Math.round(used / Math.max(1, total) * 20));
    console.log(`  ${room.padEnd(15)} ${String(used).padStart(3)}/${total.toString().padStart(3)} ${bar} (${pct}%)`);
  }

  // ── Overall grade ───────────────────────────────────────────────────────

  // Precision: what % of AI "selects" did you actually use?
  const totalSelects = allClips.filter(([, e]) => (e.classification?.confidence || 0) >= 0.7).length;
  const truePositives = usedByUsability.select;
  const precision = totalSelects > 0 ? truePositives / totalSelects : 0;

  // Recall: what % of your clips were AI "selects"?
  const recall = matched.length > 0 ? truePositives / matched.length : 0;

  // F1
  const f1 = (precision + recall) > 0 ? 2 * (precision * recall) / (precision + recall) : 0;

  console.log(`\n━━━ Pipeline Accuracy ━━━`);
  console.log(`  Precision:  ${(precision * 100).toFixed(1)}%  (of AI selects, you used this many)`);
  console.log(`  Recall:     ${(recall * 100).toFixed(1)}%  (of your clips, this many were AI selects)`);
  console.log(`  F1 Score:   ${(f1 * 100).toFixed(1)}%`);

  // Letter grade
  let grade;
  if (f1 >= 0.8) grade = 'A';
  else if (f1 >= 0.65) grade = 'B';
  else if (f1 >= 0.5) grade = 'C';
  else if (f1 >= 0.35) grade = 'D';
  else grade = 'F';

  console.log(`\n  GRADE: ${grade}\n`);

  // ── Recommendations ─────────────────────────────────────────────────────

  console.log('Recommendations:');
  if (usedByUsability.reject > 0) {
    console.log('  • Lower reject threshold — you used clips the AI rejected');
  }
  if (avgUsedConf < avgUnusedConf) {
    console.log('  • Confidence scores don\'t correlate with quality — review vision prompts');
  }
  if (precision < 0.3) {
    console.log('  • AI "select" pool is too broad — raise confidence threshold from 0.7');
  }
  if (recall < 0.5) {
    console.log('  • Many of your clips were low-confidence — AI is too conservative');
  }

  // Check if drone classification was accurate
  const usedDrone = matched.filter(m => m.bin === 'drone');
  const allDrone = allClips.filter(([, e]) => e.bin === 'drone');
  if (allDrone.length > 0) {
    console.log(`  • Drone: ${usedDrone.length}/${allDrone.length} used from drone bin`);
  }

  // ── Write report ────────────────────────────────────────────────────────

  const report = {
    generated_at: new Date().toISOString(),
    project_path: projectPath,
    edit_source: editArg,
    total_catalog_clips: allClips.length,
    total_edit_clips: editClips.length,
    matched: matched.length,
    unmatched: unmatched.length,
    accuracy: { precision, recall, f1, grade },
    usability: {
      used: usedByUsability,
      unused: unusedByUsability,
    },
    confidence: {
      avg_used: avgUsedConf,
      avg_unused: avgUnusedConf,
      delta: avgUsedConf - avgUnusedConf,
    },
    bin_usage: usedBins,
    room_coverage: usedRooms,
    false_negatives: matched.filter(m => (m.classification?.confidence || 0) < 0.5).map(m => basename(m.relPath)),
    top_unused_high_confidence: falsePositives.map(([p, e]) => ({ file: basename(p), confidence: e.classification?.confidence, bin: e.bin })),
  };

  const reportPath = join(projectPath, 'pipeline-grade-report.json');
  writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\nReport written to: ${reportPath}`);
}

// ─── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const editClips = await resolveEditClips();

  if (editClips === null) {
    showOverview();
  } else {
    gradeAgainstEdit(editClips);
  }
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
