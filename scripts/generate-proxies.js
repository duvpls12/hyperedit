#!/usr/bin/env node
/**
 * generate-proxies.js
 * Generate 720p H.264 proxy files for all clips in a HyperEdit project folder.
 *
 * Usage:
 *   node scripts/generate-proxies.js <project-path>
 *   node scripts/generate-proxies.js <project-path> --concurrency 4
 */

import { execSync, spawn } from 'child_process';
import { existsSync, mkdirSync, readFileSync } from 'fs';
import { join, basename, extname } from 'path';
import { resolve } from 'path';

// ---------------------------------------------------------------------------
// Args
// ---------------------------------------------------------------------------
const args = process.argv.slice(2);
const projectPath = args.find(a => !a.startsWith('--'));

if (!projectPath) {
  console.error('Usage: node scripts/generate-proxies.js <project-path> [--concurrency N]');
  process.exit(1);
}

const concurrencyFlagIdx = args.indexOf('--concurrency');
const CONCURRENCY = concurrencyFlagIdx !== -1 ? parseInt(args[concurrencyFlagIdx + 1], 10) : 4;

const PROJECT = resolve(projectPath);

if (!existsSync(PROJECT)) {
  console.error(`Project path not found: ${PROJECT}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Video extensions to scan for
// ---------------------------------------------------------------------------
const VIDEO_EXTS = new Set(['.mp4', '.mov', '.mxf', '.avi', '.mkv', '.m4v', '.mts', '.m2ts']);

// ---------------------------------------------------------------------------
// Collect source clips
// ---------------------------------------------------------------------------

/**
 * Recursively walk a directory and return all video file paths.
 * @param {string} dir
 * @param {string[]} acc
 * @returns {string[]}
 */
function walkDir(dir, acc = []) {
  let entries;
  try {
    // Use execSync to list entries (avoids readdirSync quirks on external drives)
    entries = execSync(`ls -1A "${dir}"`, { encoding: 'utf8' })
      .split('\n')
      .filter(Boolean);
  } catch {
    return acc;
  }

  for (const entry of entries) {
    if (entry === '.DS_Store' || entry.startsWith('.')) continue;
    const fullPath = join(dir, entry);
    const ext = extname(entry).toLowerCase();

    if (VIDEO_EXTS.has(ext)) {
      acc.push(fullPath);
    } else {
      // Try to recurse — if it's a directory
      try {
        walkDir(fullPath, acc);
      } catch {
        // not a directory, skip
      }
    }
  }
  return acc;
}

/**
 * Resolve clips either from shot-catalog.json or by scanning footage dir.
 * Returns array of absolute source file paths.
 */
function resolveClips() {
  const catalogPath = join(PROJECT, 'shot-catalog.json');

  if (existsSync(catalogPath)) {
    console.log(`Reading clips from shot-catalog.json...`);
    let catalog;
    try {
      catalog = JSON.parse(readFileSync(catalogPath, 'utf8'));
    } catch (err) {
      console.warn(`  Warning: could not parse shot-catalog.json (${err.message}). Falling back to footage scan.`);
      return scanFootage();
    }

    // Catalog keys are relative paths like "footage/subdir/JG4579.MP4"
    const keys = Object.keys(catalog);
    if (keys.length === 0) {
      console.warn('  shot-catalog.json is empty. Falling back to footage scan.');
      return scanFootage();
    }

    return keys.map(rel => {
      const abs = join(PROJECT, rel);
      return abs;
    }).filter(p => {
      if (!existsSync(p)) {
        console.warn(`  Missing source file (skipping): ${p}`);
        return false;
      }
      return true;
    });
  }

  console.log('shot-catalog.json not found. Scanning footage directory...');
  return scanFootage();
}

function scanFootage() {
  const footageDir = join(PROJECT, 'footage');
  if (!existsSync(footageDir)) {
    console.error(`No footage directory found at: ${footageDir}`);
    process.exit(1);
  }
  const files = walkDir(footageDir);
  if (files.length === 0) {
    console.error('No video files found in footage directory.');
    process.exit(1);
  }
  return files;
}

// ---------------------------------------------------------------------------
// Proxy output path
// ---------------------------------------------------------------------------

/**
 * Derive a unique clip_id from its path (filename without extension).
 * If two clips share the same basename, include enough of the relative path
 * to disambiguate.
 */
function proxyPath(sourcePath, proxiesDir, usedIds) {
  const base = basename(sourcePath, extname(sourcePath));
  let clipId = base;

  // Avoid collisions — shouldn't happen with camera-named files but be safe
  if (usedIds.has(clipId)) {
    // Use last two path segments
    const parts = sourcePath.replace(/\\/g, '/').split('/');
    clipId = parts.slice(-2).join('_').replace(/\.[^.]+$/, '');
  }
  usedIds.add(clipId);
  return join(proxiesDir, `${clipId}_proxy.mp4`);
}

// ---------------------------------------------------------------------------
// FFmpeg runner (Promise-based)
// ---------------------------------------------------------------------------

/**
 * Run FFmpeg for one clip. Returns duration in seconds.
 */
function runFFmpeg(inputPath, outputPath) {
  return new Promise((resolve, reject) => {
    const scaleFilter = "scale='if(gt(iw,ih),720,-2)':'if(gt(iw,ih),-2,720)'";
    const ffmpegArgs = [
      '-i', inputPath,
      '-vf', scaleFilter,
      '-c:v', 'libx264',
      '-crf', '23',
      '-preset', 'ultrafast',
      '-c:a', 'aac',
      '-b:a', '128k',
      outputPath,
      '-y',
      '-loglevel', 'error',
    ];

    const start = Date.now();
    const proc = spawn('ffmpeg', ffmpegArgs, { stdio: ['ignore', 'ignore', 'pipe'] });

    let stderrBuf = '';
    proc.stderr.on('data', chunk => { stderrBuf += chunk.toString(); });

    proc.on('close', code => {
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      if (code === 0) {
        resolve(elapsed);
      } else {
        reject(new Error(stderrBuf.trim() || `FFmpeg exited with code ${code}`));
      }
    });

    proc.on('error', err => reject(err));
  });
}

// ---------------------------------------------------------------------------
// Semaphore / concurrency queue
// ---------------------------------------------------------------------------

function createSemaphore(limit) {
  let active = 0;
  const queue = [];

  function next() {
    if (queue.length === 0 || active >= limit) return;
    active++;
    const { fn, resolve, reject } = queue.shift();
    fn().then(v => { active--; resolve(v); next(); })
        .catch(e => { active--; reject(e); next(); });
  }

  return function acquire(fn) {
    return new Promise((resolve, reject) => {
      queue.push({ fn, resolve, reject });
      next();
    });
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const wallStart = Date.now();

  console.log(`\nHyperEdit Proxy Generator`);
  console.log(`  Project  : ${PROJECT}`);
  console.log(`  Concurrency: ${CONCURRENCY}`);
  console.log('');

  // Resolve clips
  const clips = resolveClips();
  console.log(`Found ${clips.length} video files.\n`);

  // Ensure proxies directory
  const proxiesDir = join(PROJECT, 'proxies');
  if (!existsSync(proxiesDir)) {
    mkdirSync(proxiesDir, { recursive: true });
    console.log(`Created proxies directory: ${proxiesDir}`);
  }

  // Build work list — resolve output paths, detect already-done
  const usedIds = new Set();
  const tasks = clips.map(srcPath => ({
    srcPath,
    outPath: proxyPath(srcPath, proxiesDir, usedIds),
  }));

  let generated = 0;
  let skipped = 0;
  let failed = 0;
  const failures = [];

  const sem = createSemaphore(CONCURRENCY);
  const total = tasks.length;

  // Track sequential index for progress display (thread-safe via closure counter)
  let completedCount = 0;

  const promises = tasks.map(({ srcPath, outPath }) =>
    sem(async () => {
      const clipName = basename(srcPath);
      const proxyName = basename(outPath);

      // Idempotency check
      if (existsSync(outPath)) {
        completedCount++;
        const idx = completedCount;
        console.log(`[${String(idx).padStart(String(total).length)}/${total}] SKIP  ${clipName} (proxy exists)`);
        skipped++;
        return;
      }

      let elapsed;
      try {
        elapsed = await runFFmpeg(srcPath, outPath);
        completedCount++;
        const idx = completedCount;
        generated++;
        console.log(`[${String(idx).padStart(String(total).length)}/${total}] OK    ${clipName} → proxies/${proxyName} (${elapsed}s)`);
      } catch (err) {
        completedCount++;
        const idx = completedCount;
        failed++;
        failures.push({ clipName, err: err.message });
        console.error(`[${String(idx).padStart(String(total).length)}/${total}] FAIL  ${clipName}: ${err.message.split('\n')[0]}`);
      }
    })
  );

  await Promise.all(promises);

  // ---------------------------------------------------------------------------
  // Summary
  // ---------------------------------------------------------------------------
  const wallElapsed = ((Date.now() - wallStart) / 1000).toFixed(1);

  console.log('\n' + '─'.repeat(60));
  console.log('Proxy generation complete.');
  console.log(`  Generated : ${generated}`);
  console.log(`  Skipped   : ${skipped} (already existed)`);
  console.log(`  Failed    : ${failed}`);
  console.log(`  Total time: ${wallElapsed}s`);
  console.log('─'.repeat(60));

  if (failures.length > 0) {
    console.log('\nFailed clips:');
    for (const { clipName, err } of failures) {
      console.log(`  ${clipName}: ${err}`);
    }
  }

  // macOS notification
  try {
    const msg = `${generated} generated, ${skipped} skipped, ${failed} failed`;
    execSync(
      `osascript -e 'display notification "${msg}" with title "HyperEdit Proxies" sound name "Glass"'`,
      { stdio: 'ignore' }
    );
  } catch {
    // Notification is best-effort; silently ignore on non-macOS or if blocked
  }

  if (failed > 0) process.exit(1);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
