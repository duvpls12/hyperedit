#!/usr/bin/env node
/**
 * HyperEdit Auto-Sort Pipeline — Local LM Studio Runner
 *
 * Two-pass vision + sort + grade:
 *   Pass 1: Low-res 5fps frames → LM Studio vision → shot classification per frame
 *   Pass 2: Full-res single screenshot → color profile + detail confirmation
 *   Sort:   Symlink into bins/
 *   Grade:  Apply matched LUT → graded/
 *
 * Usage:
 *   node scripts/run-pipeline-local.js /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline
 *   node scripts/run-pipeline-local.js /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline --model qwen/qwen3-vl-4b
 *   node scripts/run-pipeline-local.js /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline --concurrency 4
 */

import { execSync, spawn } from 'child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, statSync, symlinkSync, unlinkSync } from 'fs';
import { join, basename, extname, resolve, relative } from 'path';
import { readFile } from 'fs/promises';

// ─── Config ──────────────────────────────────────────────────────────────────

const LM_STUDIO_FPS = 5;
const LM_STUDIO_LOW_RES = 720;    // longest edge px for pass 1
const LM_STUDIO_CONCURRENCY = 2;  // parallel vision requests
const FFMPEG_QUALITY = 3;         // JPEG quality (2=best, 5=decent)

function loadEnv() {
  const envPath = join(process.cwd(), '.env');
  if (!existsSync(envPath)) return {};
  const out = {};
  for (const line of readFileSync(envPath, 'utf-8').split('\n')) {
    const [key, ...rest] = line.split('=');
    if (key?.trim() && rest.length) out[key.trim()] = rest.join('=').trim();
  }
  return out;
}

const env = loadEnv();
const OLLAMA_HOST = process.env.OLLAMA_HOST || env.OLLAMA_HOST || 'http://localhost:8080';

// ─── CLI Args ────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const projectPath = args.find(a => !a.startsWith('--'));
if (!projectPath) {
  console.error('Usage: node scripts/run-pipeline-local.js <project-path> [--model <id>] [--concurrency <n>] [--dry-run]');
  process.exit(1);
}

const MODEL = args.includes('--model') ? args[args.indexOf('--model') + 1] : 'qwen2.5vl:7b';
const CONCURRENCY = args.includes('--concurrency') ? parseInt(args[args.indexOf('--concurrency') + 1]) : LM_STUDIO_CONCURRENCY;
const DRY_RUN = args.includes('--dry-run');

const FOOTAGE_DIR = join(projectPath, 'footage');
const BINS_DIR = join(projectPath, 'bins');
const GRADED_DIR = join(projectPath, 'graded');
const FRAMES_DIR = join(projectPath, '.frames');
const CATALOG_PATH = join(projectPath, 'shot-catalog.json');
const LEDGER_PATH = join(projectPath, 'run-ledger.json');
const LUT_ROOT = '/Volumes/Charlie/hyperedit-studio/assets/luts';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function isVideo(f) { return /\.(mp4|mov|mxf|avi|mkv|m4v|mts|m2ts)$/i.test(f); }
function isImage(f) { return /\.(jpg|jpeg|png|tiff|tif|heic|dng|arw|cr2|cr3)$/i.test(f); }

function findFiles(dir, filter) {
  const results = [];
  if (!existsSync(dir)) return results;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith('.')) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) results.push(...findFiles(full, filter));
    else if (filter(entry.name)) results.push(full);
  }
  return results;
}

function exec(cmd, timeout = 120_000) {
  return execSync(cmd, { encoding: 'utf-8', timeout, stdio: ['pipe', 'pipe', 'pipe'] }).trim();
}

function getDuration(videoPath) {
  try {
    const out = exec(`ffprobe -v quiet -print_format json -show_entries format=duration "${videoPath}"`);
    return parseFloat(JSON.parse(out).format.duration) || 0;
  } catch { return 0; }
}

function getContainerBrand(videoPath) {
  try {
    const out = exec(`ffprobe -v quiet -print_format json -show_entries format_tags=major_brand "${videoPath}"`);
    return (JSON.parse(out).format?.tags?.major_brand || '').toUpperCase();
  } catch { return ''; }
}

function getPixFmt(videoPath) {
  try {
    const out = exec(`ffprobe -v quiet -print_format json -show_entries stream=pix_fmt,color_transfer,color_range -select_streams v:0 "${videoPath}"`);
    const s = JSON.parse(out).streams?.[0];
    return { pix_fmt: s?.pix_fmt || '', color_transfer: s?.color_transfer || '', color_range: s?.color_range || '' };
  } catch { return { pix_fmt: '', color_transfer: '', color_range: '' }; }
}

function detectCamera(filename, brand) {
  const base = basename(filename, extname(filename)).toUpperCase();
  if (/^C0\d{3}|^C\d{4}/.test(base)) return 'sony';
  if (/^DJI_/.test(base)) return 'dji';
  if (/^GOPR|^GX|^GH/.test(base)) return 'gopro';
  if (/^IMG_\d+/.test(base)) return 'iphone';
  if (/^MVI_/.test(base)) return 'canon';
  if (/^DSC_/.test(base)) return 'nikon';
  if (/^DSCF/.test(base)) return 'fujifilm';
  // Container brand fallback
  if (brand === 'XAVC' || brand.startsWith('XAVC')) return 'sony';
  if (brand.startsWith('DJI') || brand.startsWith('DJMD')) return 'dji';
  return 'unknown';
}

function detectColorProfile(camera, pixInfo) {
  const { pix_fmt, color_transfer, color_range } = pixInfo;
  // Explicit color_transfer tag
  if (color_transfer.includes('slog') || color_transfer.includes('bt2020')) return 'slog3';
  if (color_transfer.includes('dlog')) return 'dlog';
  // Heuristic: 10-bit + full range on Sony = S-Log3
  if (camera === 'sony' && pix_fmt.includes('10') && color_range === 'pc') return 'slog3';
  if (camera === 'sony' && pix_fmt.includes('10')) return 'slog3-cine';
  if (camera === 'sony') return 'rec709';
  if (camera === 'dji' && pix_fmt.includes('10')) return 'dlog';
  if (camera === 'dji') return 'dlogm';
  if (camera === 'gopro') return 'gopro-flat';
  return 'rec709';
}

const PROFILE_TO_LUT_DIR = {
  'slog3': 'sony-slog3',
  'slog3-cine': 'sony-slog3-cine',
  'dlog': 'dji-dlog',
  'dlogm': 'dji-dlogm',
  'gopro-flat': 'gopro-flat',
  'rec709': 'rec709',
};

function findBestLut(profile) {
  const lutDir = join(LUT_ROOT, PROFILE_TO_LUT_DIR[profile] || 'generic');
  if (!existsSync(lutDir)) return null;
  const luts = readdirSync(lutDir).filter(f => f.endsWith('.cube') || f.endsWith('.CUBE'));
  if (luts.length === 0) return null;
  // Return first alphabetically — user can curate order by naming
  luts.sort();
  return join(lutDir, luts[0]);
}

// ─── Ollama Vision API ───────────────────────────────────────────────────────

async function ollamaVision(prompt, imageBase64) {
  const body = {
    model: MODEL,
    messages: [{
      role: 'user',
      content: prompt,
      images: [imageBase64],
    }],
    stream: false,
    options: { temperature: 0.1 },
  };

  const res = await fetch(`${OLLAMA_HOST}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Ollama ${res.status}: ${err.slice(0, 200)}`);
  }

  const data = await res.json();
  return data.message?.content || '';
}

function parseJSON(text) {
  // Extract JSON from markdown code fences or raw text
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  const jsonStr = fenced ? fenced[1].trim() : text.trim();
  try { return JSON.parse(jsonStr); }
  catch { return null; }
}

// ─── Pass 1: Low-Res 5fps Classification ─────────────────────────────────────

const PASS1_PROMPT = `You are a real estate video shot classifier. Analyze this frame from a property listing video.

Return STRICT JSON only (no markdown, no commentary):
{
  "primary": "wide|tight|detail|drone|agent-on-camera",
  "sub": "establishing|low-angle|high-angle|eye-level|close-up|medium-close-up|hardware|fixture|texture|architectural|landscape|aerial-wide|aerial-orbit|aerial-reveal|aerial-tracking|talking-head|walk-through|stand-up",
  "location": "interior|exterior",
  "room": "kitchen|bathroom|bedroom|living|dining|office|garage|pool|yard|hallway|foyer|patio|balcony|exterior|unknown",
  "lighting": "natural|artificial|mixed|golden-hour",
  "confidence": 0.0
}

Rules:
- Drone/aerial footage: always primary="drone"
- Person speaking to camera: primary="agent-on-camera"
- Architectural details, fixtures, hardware close-ups: primary="detail"
- Full room or property views: primary="wide"
- Tight framings of areas: primary="tight"
- confidence is 0.0-1.0`;

async function extractLowResFrames(videoPath, outDir) {
  mkdirSync(outDir, { recursive: true });
  const scale = `'if(gt(iw\\,ih)\\,${LM_STUDIO_LOW_RES}\\,-2)':'if(gt(iw\\,ih)\\,-2\\,${LM_STUDIO_LOW_RES})'`;
  const cmd = `ffmpeg -i "${videoPath}" -vf "fps=${LM_STUDIO_FPS},scale=${scale}" -q:v ${FFMPEG_QUALITY} "${join(outDir, 'f_%06d.jpg')}" -y -loglevel error`;
  try {
    exec(cmd, 300_000);
  } catch (e) {
    console.error(`  [WARN] Frame extraction failed for ${basename(videoPath)}: ${e.message?.slice(0, 100)}`);
    return [];
  }
  return readdirSync(outDir).filter(f => f.startsWith('f_')).sort().map(f => join(outDir, f));
}

async function classifyFramesBatch(framePaths) {
  const results = [];
  for (let i = 0; i < framePaths.length; i += CONCURRENCY) {
    const batch = framePaths.slice(i, i + CONCURRENCY);
    const promises = batch.map(async (fp) => {
      const imgBuf = readFileSync(fp);
      const b64 = imgBuf.toString('base64');
      try {
        const raw = await ollamaVision(PASS1_PROMPT, b64);
        const parsed = parseJSON(raw);
        return { frame: basename(fp), ...parsed };
      } catch (e) {
        return { frame: basename(fp), error: e.message?.slice(0, 100), primary: 'wide', sub: 'establishing', confidence: 0 };
      }
    });
    results.push(...(await Promise.all(promises)));
  }
  return results;
}

function majorityVote(frameResults) {
  // Tally primary tags across all frames, pick the most common
  const counts = {};
  const subCounts = {};
  const locationCounts = {};
  const roomCounts = {};
  const lightingCounts = {};

  for (const fr of frameResults) {
    if (!fr.primary) continue;
    counts[fr.primary] = (counts[fr.primary] || 0) + 1;
    if (fr.sub) subCounts[fr.sub] = (subCounts[fr.sub] || 0) + 1;
    if (fr.location) locationCounts[fr.location] = (locationCounts[fr.location] || 0) + 1;
    if (fr.room) roomCounts[fr.room] = (roomCounts[fr.room] || 0) + 1;
    if (fr.lighting) lightingCounts[fr.lighting] = (lightingCounts[fr.lighting] || 0) + 1;
  }

  const pick = (obj) => Object.entries(obj).sort((a, b) => b[1] - a[1])[0]?.[0] || 'unknown';
  const avgConf = frameResults.reduce((s, f) => s + (f.confidence || 0), 0) / (frameResults.length || 1);

  return {
    primary: pick(counts),
    sub: pick(subCounts),
    location: pick(locationCounts),
    room: pick(roomCounts),
    lighting: pick(lightingCounts),
    confidence: Math.round(avgConf * 100) / 100,
    frame_count: frameResults.length,
    vote_distribution: counts,
  };
}

// ─── Pass 2: Full-Res Single Screenshot ──────────────────────────────────────

const PASS2_PROMPT = `You are an expert cinematographer analyzing a FULL RESOLUTION frame from a real estate listing video.

Provide a detailed assessment. Return STRICT JSON only:
{
  "primary": "wide|tight|detail|drone|agent-on-camera",
  "sub": "establishing|low-angle|high-angle|eye-level|close-up|medium-close-up|hardware|fixture|texture|architectural|landscape|aerial-wide|aerial-orbit|aerial-reveal|aerial-tracking|talking-head|walk-through|stand-up",
  "location": "interior|exterior",
  "room": "kitchen|bathroom|bedroom|living|dining|office|garage|pool|yard|hallway|foyer|patio|balcony|exterior|unknown",
  "lighting": "natural|artificial|mixed|golden-hour",
  "color_notes": "describe the color: is it flat/desaturated (log), normal contrast (rec709), or stylized?",
  "composition_notes": "brief composition description",
  "quality_flags": ["sharp|soft", "well-exposed|over-exposed|under-exposed", "stable|shaky"],
  "confidence": 0.0
}`;

async function extractFullResFrame(videoPath, outPath) {
  const duration = getDuration(videoPath);
  const midpoint = (duration / 2).toFixed(3);
  const cmd = `ffmpeg -ss ${midpoint} -i "${videoPath}" -frames:v 1 -q:v 2 "${outPath}" -y -loglevel error`;
  try {
    exec(cmd, 60_000);
    return true;
  } catch { return false; }
}

// ─── Sort & Grade ────────────────────────────────────────────────────────────

function sortToBin(filePath, binName) {
  const binDir = join(BINS_DIR, binName);
  mkdirSync(binDir, { recursive: true });
  const linkPath = join(binDir, basename(filePath));
  try {
    if (existsSync(linkPath)) unlinkSync(linkPath);
    symlinkSync(filePath, linkPath);
    return true;
  } catch (e) {
    console.error(`  [WARN] Symlink failed: ${e.message?.slice(0, 80)}`);
    return false;
  }
}

function applyLut(inputPath, lutPath, outputPath) {
  mkdirSync(GRADED_DIR, { recursive: true });
  const cmd = `ffmpeg -i "${inputPath}" -vf "lut3d='${lutPath}'" -c:v libx264 -crf 18 -preset fast -c:a copy "${outputPath}" -y -loglevel error`;
  try {
    exec(cmd, 600_000);
    return true;
  } catch (e) {
    console.error(`  [WARN] LUT apply failed for ${basename(inputPath)}: ${e.message?.slice(0, 100)}`);
    return false;
  }
}

// ─── Main Pipeline ───────────────────────────────────────────────────────────

async function main() {
  console.log(`\n━━━ HyperEdit Auto-Sort Pipeline ━━━`);
  console.log(`Project:     ${projectPath}`);
  console.log(`Model:       ${MODEL}`);
  console.log(`Concurrency: ${CONCURRENCY}`);
  console.log(`Ollama:      ${OLLAMA_HOST}`);
  console.log(`Dry run:     ${DRY_RUN}\n`);

  // Validate
  if (!existsSync(FOOTAGE_DIR)) { console.error('No footage/ directory found.'); process.exit(1); }
  if (existsSync(LEDGER_PATH)) { console.log('⚠ run-ledger.json already exists — project already processed. Delete it to re-run.'); process.exit(0); }

  // Read brief
  const briefPath = join(projectPath, 'brief.json');
  let brief = null;
  if (existsSync(briefPath)) {
    brief = JSON.parse(readFileSync(briefPath, 'utf-8'));
    console.log(`Brief:       ${brief.property_address || brief.project_id || 'loaded'}`);
  } else {
    console.log('Brief:       not found (continuing without)');
  }

  // Discover footage
  const videos = findFiles(FOOTAGE_DIR, isVideo);
  const photos = findFiles(FOOTAGE_DIR, isImage);
  console.log(`\nFound ${videos.length} video clips, ${photos.length} photos\n`);

  if (videos.length === 0 && photos.length === 0) {
    console.error('No footage files found.'); process.exit(1);
  }

  // Setup dirs
  mkdirSync(BINS_DIR, { recursive: true });
  mkdirSync(GRADED_DIR, { recursive: true });
  mkdirSync(FRAMES_DIR, { recursive: true });

  const catalog = {};
  const startTime = Date.now();
  let processed = 0;
  let graded = 0;
  let errors = 0;

  // ─── Process Videos ──────────────────────────────────────────────────────

  for (let i = 0; i < videos.length; i++) {
    const videoPath = videos[i];
    const name = basename(videoPath);
    const id = basename(videoPath, extname(videoPath));
    const relPath = relative(projectPath, videoPath);
    const clipFramesDir = join(FRAMES_DIR, id);

    console.log(`[${i + 1}/${videos.length}] ${name}`);

    // Detect camera + color from metadata (instant, no vision needed)
    const brand = getContainerBrand(videoPath);
    const camera = detectCamera(name, brand);
    const pixInfo = getPixFmt(videoPath);
    const colorProfile = detectColorProfile(camera, pixInfo);
    const duration = getDuration(videoPath);

    console.log(`  camera=${camera} profile=${colorProfile} duration=${duration.toFixed(1)}s`);

    if (DRY_RUN) {
      catalog[relPath] = { camera, colorProfile, duration, classification: null, pass2: null };
      continue;
    }

    // ── Pass 1: Low-res 5fps ──────────────────────────────────────────────
    console.log(`  Pass 1: extracting ${LM_STUDIO_FPS}fps @ ${LM_STUDIO_LOW_RES}px...`);
    const frames = await extractLowResFrames(videoPath, clipFramesDir);
    console.log(`  Pass 1: ${frames.length} frames → classifying...`);

    let classification;
    if (frames.length > 0) {
      const frameResults = await classifyFramesBatch(frames);
      classification = majorityVote(frameResults);
      console.log(`  Pass 1: ${classification.primary}/${classification.sub} (conf=${classification.confidence}, votes=${JSON.stringify(classification.vote_distribution)})`);
    } else {
      // Fallback: use folder name as hint
      const parentDir = basename(join(videoPath, '..'));
      const folderHint = parentDir.toLowerCase();
      classification = {
        primary: folderHint === 'drone' ? 'drone' : folderHint === 'agent' ? 'agent-on-camera' : 'wide',
        sub: folderHint === 'drone' ? 'aerial-wide' : folderHint === 'agent' ? 'walk-through' : 'establishing',
        location: 'unknown', room: 'unknown', lighting: 'unknown',
        confidence: 0.3, frame_count: 0, vote_distribution: {},
      };
      console.log(`  Pass 1: FALLBACK from folder name → ${classification.primary}`);
    }

    // ── Pass 2: Full-res single frame ─────────────────────────────────────
    const fullResPath = join(FRAMES_DIR, `${id}_fullres.jpg`);
    console.log(`  Pass 2: full-res screenshot...`);
    const extracted = await extractFullResFrame(videoPath, fullResPath);
    let pass2 = null;
    if (extracted && existsSync(fullResPath)) {
      try {
        const imgBuf = readFileSync(fullResPath);
        const b64 = imgBuf.toString('base64');
        const raw = await ollamaVision(PASS2_PROMPT, b64);
        pass2 = parseJSON(raw);
        if (pass2) {
          console.log(`  Pass 2: ${pass2.primary}/${pass2.sub} color="${pass2.color_notes?.slice(0, 60)}"`);
          // Override pass1 if pass2 confidence is higher
          if ((pass2.confidence || 0) > (classification.confidence || 0)) {
            classification.primary = pass2.primary || classification.primary;
            classification.sub = pass2.sub || classification.sub;
            console.log(`  Pass 2 override → ${classification.primary}/${classification.sub}`);
          }
        }
      } catch (e) {
        console.error(`  Pass 2: vision failed — ${e.message?.slice(0, 80)}`);
        errors++;
      }
    }

    // ── Sort to bin ───────────────────────────────────────────────────────
    const binName = classification.primary;
    sortToBin(videoPath, binName);
    console.log(`  Sorted → bins/${binName}/`);

    // ── Apply LUT ─────────────────────────────────────────────────────────
    const lutPath = findBestLut(colorProfile);
    if (lutPath) {
      const outName = `${id}_graded${extname(videoPath)}`;
      const outPath = join(GRADED_DIR, outName);
      console.log(`  Grading: ${basename(lutPath)} → graded/${outName}`);
      if (applyLut(videoPath, lutPath, outPath)) {
        graded++;
      } else {
        errors++;
      }
    } else {
      console.log(`  Grading: no LUT found for profile=${colorProfile}`);
    }

    // ── Store in catalog ──────────────────────────────────────────────────
    catalog[relPath] = {
      camera,
      colorProfile,
      duration,
      classification,
      pass2,
      bin: binName,
      lut: lutPath ? basename(lutPath) : null,
    };

    processed++;
    console.log('');
  }

  // ─── Process Photos ────────────────────────────────────────────────────

  for (let i = 0; i < photos.length; i++) {
    const photoPath = photos[i];
    const name = basename(photoPath);
    const relPath = relative(projectPath, photoPath);

    console.log(`[Photo ${i + 1}/${photos.length}] ${name}`);

    if (DRY_RUN) {
      catalog[relPath] = { type: 'photo', classification: null };
      continue;
    }

    // Classify photo directly (it IS the frame)
    try {
      const imgBuf = readFileSync(photoPath);
      const b64 = imgBuf.toString('base64');
      const raw = await ollamaVision(PASS1_PROMPT, b64);
      const parsed = parseJSON(raw) || { primary: 'detail', sub: 'architectural', confidence: 0.3 };

      // Dual sort: primary bin + photos bin
      sortToBin(photoPath, parsed.primary);
      sortToBin(photoPath, 'photos');
      console.log(`  ${parsed.primary}/${parsed.sub} → bins/${parsed.primary}/ + bins/photos/`);

      catalog[relPath] = { type: 'photo', classification: parsed, bins: [parsed.primary, 'photos'] };
      processed++;
    } catch (e) {
      console.error(`  [ERROR] ${e.message?.slice(0, 100)}`);
      sortToBin(photoPath, 'photos');
      catalog[relPath] = { type: 'photo', classification: null, bins: ['photos'] };
      errors++;
    }
  }

  // ─── Write Catalog ─────────────────────────────────────────────────────

  writeFileSync(CATALOG_PATH, JSON.stringify(catalog, null, 2));
  console.log(`\nCatalog written: ${CATALOG_PATH}`);

  // ─── Write Run Ledger ──────────────────────────────────────────────────

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const ledger = {
    project_id: brief?.project_id || basename(projectPath),
    property_address: brief?.property_address || basename(projectPath),
    current_stage: 'footage_intake',
    stages: {
      footage_intake: {
        status: 'done',
        started_at: new Date(startTime).toISOString(),
        completed_at: new Date().toISOString(),
        stats: {
          total_clips: videos.length,
          total_photos: photos.length,
          processed,
          graded,
          errors,
          elapsed_seconds: parseFloat(elapsed),
          model_used: MODEL,
          concurrency: CONCURRENCY,
        },
      },
    },
    created_at: new Date().toISOString(),
  };

  writeFileSync(LEDGER_PATH, JSON.stringify(ledger, null, 2));
  console.log(`Ledger written: ${LEDGER_PATH}`);

  // ─── Summary ───────────────────────────────────────────────────────────

  // Count bins
  const binSummary = {};
  if (existsSync(BINS_DIR)) {
    for (const d of readdirSync(BINS_DIR, { withFileTypes: true })) {
      if (d.isDirectory()) {
        binSummary[d.name] = readdirSync(join(BINS_DIR, d.name)).filter(f => !f.startsWith('.')).length;
      }
    }
  }

  console.log(`\n━━━ Pipeline Complete ━━━`);
  console.log(`Processed: ${processed}/${videos.length + photos.length} files`);
  console.log(`Graded:    ${graded} clips`);
  console.log(`Errors:    ${errors}`);
  console.log(`Elapsed:   ${elapsed}s`);
  console.log(`\nBins:`);
  for (const [bin, count] of Object.entries(binSummary).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${bin.padEnd(20)} ${count}`);
  }

  // macOS notification
  try {
    const msg = `${processed} clips sorted, ${graded} graded in ${elapsed}s`;
    exec(`osascript -e 'display notification "${msg}" with title "HyperEdit Pipeline" sound name "Glass"'`);
  } catch { /* silent */ }

  console.log('\nDone.\n');
}

main().catch(e => { console.error('Pipeline fatal:', e); process.exit(1); });
