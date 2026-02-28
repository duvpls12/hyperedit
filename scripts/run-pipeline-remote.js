#!/usr/bin/env node
/**
 * HyperEdit Remote GPU Pipeline
 *
 * Streams clips to Vast.ai server for classification, generates local proxies.
 * All heavy decoding + vision happens on the GPU. Mac only does lightweight work.
 *
 * Flow per clip:
 *   1. SCP clip to server /tmp/
 *   2. SSH run gpu-classify.py → returns JSON classification
 *   3. Delete clip from server
 *   4. Sort into bins (symlink)
 *   5. Generate 720p proxy locally (fast, small files)
 *
 * Usage:
 *   node scripts/run-pipeline-remote.js /Volumes/Charlie/hyperedit-studio/projects/20260227_Test_Pipeline
 *   node scripts/run-pipeline-remote.js <path> --concurrency 2 --skip-proxy --model qwen2.5vl:7b
 */

import { execSync, exec as execCb } from 'child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, symlinkSync, unlinkSync } from 'fs';
import { join, basename, extname, relative } from 'path';
import { promisify } from 'util';

const execAsync = promisify(execCb);

// ─── Config ──────────────────────────────────────────────────────────────────

const SSH_HOST = 'root@154.59.156.10';
const SSH_PORT = '29449';
const SSH_OPTS = `-p ${SSH_PORT} -o StrictHostKeyChecking=no -o ConnectTimeout=15`;
const REMOTE_SCRIPT = '/workspace/gpu-classify.py';
const REMOTE_TMP = '/tmp/hyperedit';
const PROXY_RES = 720;      // proxy longest edge
const PROXY_CRF = 23;       // proxy quality (higher = smaller/faster)

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

// ─── CLI Args ────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const projectPath = args.find(a => !a.startsWith('--'));
if (!projectPath) {
  console.error('Usage: node scripts/run-pipeline-remote.js <project-path> [--concurrency <n>] [--skip-proxy] [--model <id>]');
  process.exit(1);
}

const MODEL = args.includes('--model') ? args[args.indexOf('--model') + 1] : 'qwen2.5vl:7b';
const CONCURRENCY = args.includes('--concurrency') ? parseInt(args[args.indexOf('--concurrency') + 1]) : 1;
const SKIP_PROXY = args.includes('--skip-proxy');

const FOOTAGE_DIR = join(projectPath, 'footage');
const BINS_DIR = join(projectPath, 'bins');
const PROXY_DIR = join(projectPath, 'proxies');
const CATALOG_PATH = join(projectPath, 'shot-catalog.json');
const LEDGER_PATH = join(projectPath, 'run-ledger.json');
const LUT_ROOT = '/Volumes/Charlie/hyperedit-studio/assets/luts';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function isVideo(f) { return /\.(mp4|mov|mxf|avi|mkv|m4v|mts|m2ts)$/i.test(f); }

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

function ssh(cmd, timeout = 300_000) {
  return exec(`ssh ${SSH_OPTS} ${SSH_HOST} "${cmd.replace(/"/g, '\\"')}"`, timeout);
}

function scp(localPath, remotePath, timeout = 120_000) {
  return exec(`scp -P ${SSH_PORT} -o StrictHostKeyChecking=no "${localPath}" ${SSH_HOST}:${remotePath}`, timeout);
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
  if (brand === 'XAVC' || brand.startsWith('XAVC')) return 'sony';
  if (brand.startsWith('DJI') || brand.startsWith('DJMD')) return 'dji';
  return 'unknown';
}

function detectColorProfile(camera, pixInfo) {
  const { pix_fmt, color_transfer, color_range } = pixInfo;
  if (color_transfer.includes('slog') || color_transfer.includes('bt2020')) return 'slog3';
  if (color_transfer.includes('dlog')) return 'dlog';
  if (camera === 'sony' && pix_fmt.includes('10') && color_range === 'pc') return 'slog3';
  if (camera === 'sony' && pix_fmt.includes('10')) return 'slog3-cine';
  if (camera === 'sony') return 'rec709';
  if (camera === 'dji' && pix_fmt.includes('10')) return 'dlog';
  if (camera === 'dji') return 'dlogm';
  if (camera === 'gopro') return 'gopro-flat';
  return 'rec709';
}

const PROFILE_TO_LUT_DIR = {
  'slog3': 'sony-slog3', 'slog3-cine': 'sony-slog3-cine',
  'dlog': 'dji-dlog', 'dlogm': 'dji-dlogm',
  'gopro-flat': 'gopro-flat', 'rec709': 'rec709',
};

function findBestLut(profile) {
  const lutDir = join(LUT_ROOT, PROFILE_TO_LUT_DIR[profile] || 'generic');
  if (!existsSync(lutDir)) return null;
  const luts = readdirSync(lutDir).filter(f => /\.cube$/i.test(f)).sort();
  return luts.length ? join(lutDir, luts[0]) : null;
}

function sortToBin(filePath, binName) {
  const binDir = join(BINS_DIR, binName);
  mkdirSync(binDir, { recursive: true });
  const linkPath = join(binDir, basename(filePath));
  try { if (existsSync(linkPath)) unlinkSync(linkPath); symlinkSync(filePath, linkPath); } catch {}
}

function generateProxy(inputPath, outputPath) {
  const scale = `'if(gt(iw\\,ih)\\,${PROXY_RES}\\,-2)':'if(gt(iw\\,ih)\\,-2\\,${PROXY_RES})'`;
  const cmd = `ffmpeg -i "${inputPath}" -vf "scale=${scale}" -c:v libx264 -crf ${PROXY_CRF} -preset ultrafast -c:a aac -b:a 128k "${outputPath}" -y -loglevel error`;
  try { exec(cmd, 300_000); return true; } catch { return false; }
}

// ─── Process Single Clip on Remote GPU ───────────────────────────────────────

async function classifyRemote(videoPath) {
  const name = basename(videoPath);
  const remotePath = `${REMOTE_TMP}/${name}`;

  // Upload
  scp(videoPath, remotePath, 300_000);

  // Classify on GPU
  const result = ssh(`python3 ${REMOTE_SCRIPT} ${remotePath} --model ${MODEL}`, 600_000);

  // Cleanup remote
  try { ssh(`rm -f ${remotePath}`); } catch {}

  // Parse JSON from last line of stdout
  const lines = result.split('\n');
  for (let i = lines.length - 1; i >= 0; i--) {
    try { return JSON.parse(lines[i]); } catch { continue; }
  }
  throw new Error(`No JSON in remote output: ${result.slice(0, 200)}`);
}

// ─── Main Pipeline ───────────────────────────────────────────────────────────

async function main() {
  console.log(`\n━━━ HyperEdit Remote GPU Pipeline ━━━`);
  console.log(`Project:     ${projectPath}`);
  console.log(`GPU:         ${SSH_HOST}:${SSH_PORT}`);
  console.log(`Model:       ${MODEL}`);
  console.log(`Concurrency: ${CONCURRENCY}`);
  console.log(`Proxies:     ${SKIP_PROXY ? 'SKIP' : `${PROXY_RES}p`}\n`);

  if (!existsSync(FOOTAGE_DIR)) { console.error('No footage/ directory.'); process.exit(1); }

  // Read brief
  const briefPath = join(projectPath, 'brief.json');
  let brief = null;
  if (existsSync(briefPath)) {
    brief = JSON.parse(readFileSync(briefPath, 'utf-8'));
    console.log(`Brief:       ${brief.property_address || brief.project_id || 'loaded'}`);
  }

  // Verify GPU connection
  console.log('Connecting to GPU...');
  try {
    ssh('nvidia-smi --query-gpu=name,memory.free --format=csv,noheader');
    console.log('GPU: connected');
  } catch (e) {
    console.error('Cannot reach GPU server:', e.message?.slice(0, 100));
    process.exit(1);
  }

  // Deploy classify script if not present
  try {
    ssh(`test -f ${REMOTE_SCRIPT}`);
  } catch {
    console.log('Deploying classifier to GPU...');
    ssh(`mkdir -p /workspace && pip3 install requests -q`);
    scp('scripts/gpu-classify.py', REMOTE_SCRIPT);
  }
  ssh(`mkdir -p ${REMOTE_TMP}`);

  // Ensure Ollama is running with model
  try {
    ssh('curl -s http://localhost:11434/api/tags');
  } catch {
    console.log('Starting Ollama...');
    ssh('nohup ollama serve > /tmp/ollama.log 2>&1 &');
    exec('sleep 3');
  }

  const videos = findFiles(FOOTAGE_DIR, isVideo);
  console.log(`\nFound ${videos.length} clips\n`);

  mkdirSync(BINS_DIR, { recursive: true });
  if (!SKIP_PROXY) mkdirSync(PROXY_DIR, { recursive: true });

  const catalog = {};
  const startTime = Date.now();
  let processed = 0, errors = 0;

  for (let i = 0; i < videos.length; i++) {
    const videoPath = videos[i];
    const name = basename(videoPath);
    const id = basename(videoPath, extname(videoPath));
    const relPath = relative(projectPath, videoPath);

    // Local metadata (instant)
    const brand = getContainerBrand(videoPath);
    const camera = detectCamera(name, brand);
    const pixInfo = getPixFmt(videoPath);
    const colorProfile = detectColorProfile(camera, pixInfo);

    console.log(`[${i + 1}/${videos.length}] ${name} (${camera}/${colorProfile})`);

    // Remote classification
    try {
      const t0 = Date.now();
      const result = await classifyRemote(videoPath);
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);

      const cls = result.classification || {};
      console.log(`  → ${cls.primary}/${cls.sub} (conf=${cls.confidence}) [${elapsed}s]`);

      // Camera-aware drone override: only DJI files can be drone
      if (cls.primary === 'drone' && camera !== 'dji') {
        console.log(`  OVERRIDE: ${camera} clip "${name}" cannot be drone → wide`);
        cls.primary = 'wide';
        cls.sub = cls.sub?.startsWith('aerial') ? 'high-angle' : cls.sub || 'establishing';
      }

      // Sort
      const binName = cls.primary || 'unknown';
      sortToBin(videoPath, binName);

      // Generate proxy
      if (!SKIP_PROXY) {
        const proxyPath = join(PROXY_DIR, `${id}_proxy.mp4`);
        if (!existsSync(proxyPath)) {
          process.stdout.write(`  proxy: generating ${PROXY_RES}p...`);
          if (generateProxy(videoPath, proxyPath)) {
            console.log(' done');
          } else {
            console.log(' FAILED');
          }
        }
      }

      const lutPath = findBestLut(colorProfile);
      catalog[relPath] = {
        camera, colorProfile, duration: result.duration,
        classification: cls, pass2: result.pass2,
        bin: binName, lut: lutPath ? basename(lutPath) : null, lutPath,
      };
      processed++;
    } catch (e) {
      console.error(`  ERROR: ${e.message?.slice(0, 120)}`);
      errors++;
      catalog[relPath] = { camera, colorProfile, error: e.message?.slice(0, 200) };
    }
  }

  // Write catalog
  writeFileSync(CATALOG_PATH, JSON.stringify(catalog, null, 2));

  // Write ledger
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
        stats: { total_clips: videos.length, processed, errors, elapsed_seconds: parseFloat(elapsed), model_used: MODEL, mode: 'remote-gpu' },
      },
    },
    created_at: new Date().toISOString(),
  };
  writeFileSync(LEDGER_PATH, JSON.stringify(ledger, null, 2));

  // Bin summary
  const binSummary = {};
  if (existsSync(BINS_DIR)) {
    for (const d of readdirSync(BINS_DIR, { withFileTypes: true })) {
      if (d.isDirectory()) binSummary[d.name] = readdirSync(join(BINS_DIR, d.name)).filter(f => !f.startsWith('.')).length;
    }
  }

  console.log(`\n━━━ Pipeline Complete ━━━`);
  console.log(`Processed: ${processed}/${videos.length}`);
  console.log(`Errors:    ${errors}`);
  console.log(`Elapsed:   ${elapsed}s`);
  console.log(`\nBins:`);
  for (const [bin, count] of Object.entries(binSummary).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${bin.padEnd(20)} ${count}`);
  }

  // Notify
  try { exec(`osascript -e 'display notification "${processed} clips classified in ${elapsed}s" with title "HyperEdit Pipeline" sound name "Glass"'`); } catch {}

  console.log('\nDone. GPU instance can be stopped.\n');
}

main().catch(e => { console.error('Pipeline fatal:', e); process.exit(1); });
