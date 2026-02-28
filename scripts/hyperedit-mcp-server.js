#!/usr/bin/env node
/**
 * HyperEdit MCP Server
 * 10 tools for AI-driven video editing pipeline
 * Runs via stdio transport (Claude Desktop / Claude Code)
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { promises as fs } from 'fs';
import { execSync, exec } from 'child_process';
import path from 'path';
import { promisify } from 'util';

const execAsync = promisify(exec);

// ─── Constants ───────────────────────────────────────────────────────────────

const LUTS_ROOT = '/Volumes/Charlie/hyperedit-studio/assets/luts';
const MANIFEST_FILE = 'hyperedit-classifications.json';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function detectCameraFromFilename(filename) {
  const base = path.basename(filename, path.extname(filename)).toUpperCase();
  if (/^C0\d{3}/.test(base) || /^C\d{4}/.test(base)) return 'Sony (Alpha/FX series)';
  if (/^DJI_/.test(base)) return 'DJI (drone)';
  if (/^GOPR|^GX|^GH/.test(base)) return 'GoPro';
  if (/^IMG_\d+/.test(base)) return 'iPhone / generic';
  if (/^MVI_/.test(base)) return 'Canon';
  if (/^DSC_/.test(base)) return 'Nikon';
  if (/^P1[A-Z0-9]{6}/.test(base)) return 'Panasonic';
  if (/^_MG_|^_1A_/.test(base)) return 'Canon EOS';
  if (/^R0[A-Z0-9]{6}/.test(base)) return 'Ricoh';
  if (/^DSCF/.test(base)) return 'Fujifilm';
  return 'Unknown';
}

async function detectCameraWithFallback(filePath) {
  const filenameResult = detectCameraFromFilename(filePath);
  if (filenameResult !== 'Unknown') return filenameResult;

  // Fallback: probe container brand + exiftool for camera make
  if (isVideoFile(filePath)) {
    try {
      const probe = await runFfprobe(filePath);
      const brand = (probe.format?.tags?.major_brand || '').toUpperCase();
      if (brand === 'XAVC' || brand.startsWith('XAVC')) return 'Sony (Alpha/FX series)';
      if (brand.startsWith('DJMD') || brand.startsWith('DJI')) return 'DJI (drone)';

      // Check encoder tag
      const videoStream = probe.streams?.find(s => s.codec_type === 'video');
      const encoder = (videoStream?.tags?.encoder || '').toLowerCase();
      if (encoder.includes('sony') || encoder.includes('xavc')) return 'Sony (Alpha/FX series)';
    } catch { /* continue */ }
  }

  // Try exiftool for camera make
  try {
    const { stdout } = await execAsync(`exiftool -Make -Model -j "${filePath}"`);
    const exif = JSON.parse(stdout)?.[0];
    const make = (exif?.Make || '').toLowerCase();
    if (make.includes('sony')) return 'Sony (Alpha/FX series)';
    if (make.includes('dji')) return 'DJI (drone)';
    if (make.includes('gopro')) return 'GoPro';
    if (make.includes('apple')) return 'iPhone / generic';
    if (make.includes('canon')) return 'Canon';
    if (make.includes('nikon')) return 'Nikon';
    if (make.includes('panasonic') || make.includes('lumix')) return 'Panasonic';
    if (make.includes('fujifilm')) return 'Fujifilm';
    if (make.includes('ricoh')) return 'Ricoh';
    if (make) return make;
  } catch { /* exiftool not available */ }

  return 'Unknown';
}

function isVideoFile(filePath) {
  return /\.(mp4|mov|mxf|avi|mkv|r3d|braw|m2ts|mts|m4v|webm)$/i.test(filePath);
}

function isImageFile(filePath) {
  return /\.(jpg|jpeg|png|tiff|tif|dng|cr2|cr3|arw|nef|raf|gpr|bmp|heic)$/i.test(filePath);
}

async function runFfprobe(filePath, args = '-v quiet -print_format json -show_format -show_streams') {
  const cmd = `ffprobe ${args} "${filePath}"`;
  const { stdout } = await execAsync(cmd);
  return JSON.parse(stdout);
}

// ─── MCP Server ───────────────────────────────────────────────────────────────

const server = new McpServer({
  name: 'hyperedit',
  version: '1.0.0',
}, {
  capabilities: { tools: {} },
});

// ─── Tool 1: list_project_footage ────────────────────────────────────────────

server.tool(
  'list_project_footage',
  'List all clips/photos in a project folder with names, sizes, and types.',
  {
    projectPath: z.string().describe('Absolute path to the project folder'),
  },
  async ({ projectPath }) => {
    let entries;
    try {
      entries = await fs.readdir(projectPath, { withFileTypes: true });
    } catch (err) {
      return { content: [{ type: 'text', text: `Error reading directory: ${err.message}` }], isError: true };
    }

    const files = [];
    for (const entry of entries) {
      if (!entry.isFile()) continue;
      const filePath = path.join(projectPath, entry.name);
      const stat = await fs.stat(filePath);
      const ext = path.extname(entry.name).toLowerCase();
      let type = 'other';
      if (isVideoFile(entry.name)) type = 'video';
      else if (isImageFile(entry.name)) type = 'image';
      else if (/\.(mp3|wav|aac|aiff|flac|m4a|ogg)$/i.test(entry.name)) type = 'audio';
      else if (/\.(cube|3dl|lut)$/i.test(entry.name)) type = 'lut';

      files.push({
        name: entry.name,
        path: filePath,
        type,
        extension: ext,
        sizeBytes: stat.size,
        sizeMB: (stat.size / 1024 / 1024).toFixed(2),
        modified: stat.mtime.toISOString(),
      });
    }

    const summary = `Found ${files.length} files in ${projectPath}`;
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({ summary, files }, null, 2),
      }],
    };
  }
);

// ─── Tool 2: extract_frame ────────────────────────────────────────────────────

server.tool(
  'extract_frame',
  'Extract the middle frame from a video clip via FFmpeg.',
  {
    videoPath: z.string().describe('Absolute path to the video file'),
    outputPath: z.string().optional().describe('Where to save the frame jpg (defaults to same dir as video)'),
  },
  async ({ videoPath, outputPath }) => {
    try {
      // Get duration via ffprobe
      const probe = await runFfprobe(videoPath, '-v quiet -print_format json -show_format');
      const duration = parseFloat(probe.format?.duration ?? '0');
      if (!duration) throw new Error('Could not determine video duration');

      const midpoint = duration / 2;
      const outFile = outputPath ?? videoPath.replace(/\.[^.]+$/, '_frame_mid.jpg');

      execSync(
        `ffmpeg -y -ss ${midpoint} -i "${videoPath}" -frames:v 1 -q:v 2 "${outFile}"`,
        { stdio: 'pipe' }
      );

      const stat = await fs.stat(outFile);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            success: true,
            midpoint: `${midpoint.toFixed(3)}s of ${duration.toFixed(3)}s total`,
            outputPath: outFile,
            fileSizeBytes: stat.size,
          }, null, 2),
        }],
      };
    } catch (err) {
      return { content: [{ type: 'text', text: `Error extracting frame: ${err.message}` }], isError: true };
    }
  }
);

// ─── Tool 3: get_file_metadata ────────────────────────────────────────────────

server.tool(
  'get_file_metadata',
  'Read EXIF/file metadata and parse filename to detect camera model.',
  {
    filePath: z.string().describe('Absolute path to the file'),
  },
  async ({ filePath }) => {
    try {
      const stat = await fs.stat(filePath);
      const camera = await detectCameraWithFallback(filePath);
      const result = {
        filePath,
        fileName: path.basename(filePath),
        sizeBytes: stat.size,
        sizeMB: (stat.size / 1024 / 1024).toFixed(2),
        created: stat.birthtime.toISOString(),
        modified: stat.mtime.toISOString(),
        detectedCamera: camera,
        metadata: {},
      };

      // Try ffprobe for video/audio
      if (isVideoFile(filePath)) {
        try {
          const probe = await runFfprobe(filePath);
          result.metadata.ffprobe = {
            duration: probe.format?.duration,
            bitRate: probe.format?.bit_rate,
            formatName: probe.format?.format_name,
            streams: probe.streams?.map(s => ({
              codec_type: s.codec_type,
              codec_name: s.codec_name,
              width: s.width,
              height: s.height,
              r_frame_rate: s.r_frame_rate,
              color_space: s.color_space,
              color_transfer: s.color_transfer,
              color_primaries: s.color_primaries,
              pix_fmt: s.pix_fmt,
            })).filter(Boolean),
          };
        } catch {
          result.metadata.ffprobeError = 'ffprobe failed or not installed';
        }
      }

      // Try exiftool if available
      try {
        const { stdout } = await execAsync(`exiftool -j "${filePath}"`);
        const exif = JSON.parse(stdout)?.[0];
        if (exif) result.metadata.exiftool = exif;
      } catch {
        result.metadata.exiftoolNote = 'exiftool not available';
      }

      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
    } catch (err) {
      return { content: [{ type: 'text', text: `Error reading metadata: ${err.message}` }], isError: true };
    }
  }
);

// ─── Tool 4: classify_shot ────────────────────────────────────────────────────

server.tool(
  'classify_shot',
  'Store shot classification for a clip into a JSON manifest in the project folder.',
  {
    filePath: z.string().describe('Absolute path to the clip'),
    primary: z.enum(['wide', 'tight', 'detail', 'drone', 'agent-on-camera']).describe('Primary shot type'),
    sub: z.string().describe('Sub-classification (e.g. establishing, low-angle, over-shoulder)'),
    tags: z.array(z.string()).describe('Tags such as interior/exterior, room name, lighting condition'),
  },
  async ({ filePath, primary, sub, tags }) => {
    try {
      const projectPath = path.dirname(filePath);
      const manifestPath = path.join(projectPath, MANIFEST_FILE);

      // Camera-aware drone override: only DJI-named files can be drone
      const fnameUpper = path.basename(filePath).toUpperCase();
      const isDji = fnameUpper.startsWith('DJI_') || fnameUpper.startsWith('DJI ');
      let finalPrimary = primary;
      let finalSub = sub;
      if (primary === 'drone' && !isDji) {
        finalPrimary = 'wide';
        finalSub = sub.startsWith('aerial') ? 'high-angle' : sub || 'establishing';
      }

      let manifest = {};
      try {
        const raw = await fs.readFile(manifestPath, 'utf-8');
        manifest = JSON.parse(raw);
      } catch {
        // No existing manifest, start fresh
      }

      manifest[filePath] = {
        filePath,
        fileName: path.basename(filePath),
        classification: { primary: finalPrimary, sub: finalSub, tags },
        classifiedAt: new Date().toISOString(),
      };

      await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2));
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            success: true,
            manifestPath,
            entry: manifest[filePath],
          }, null, 2),
        }],
      };
    } catch (err) {
      return { content: [{ type: 'text', text: `Error classifying shot: ${err.message}` }], isError: true };
    }
  }
);

// ─── Tool 5: detect_color_profile ────────────────────────────────────────────

server.tool(
  'detect_color_profile',
  'Determine the color profile from metadata and camera model heuristics.',
  {
    filePath: z.string().describe('Absolute path to the video file'),
    cameraModel: z.string().optional().describe('Camera model string (overrides auto-detection)'),
  },
  async ({ filePath, cameraModel }) => {
    try {
      const detectedCamera = cameraModel ?? await detectCameraWithFallback(filePath);
      let profile = 'Rec.709';
      let confidence = 'heuristic';

      // Try ffprobe first for color metadata
      let colorTransfer = '';
      let colorSpace = '';
      if (isVideoFile(filePath)) {
        try {
          const probe = await runFfprobe(filePath);
          const videoStream = probe.streams?.find(s => s.codec_type === 'video');
          colorTransfer = videoStream?.color_transfer ?? '';
          colorSpace = videoStream?.color_space ?? '';

          if (colorTransfer.includes('slog3') || colorTransfer.includes('s-log3')) {
            profile = 'S-Log3';
            confidence = 'metadata';
          } else if (colorTransfer.includes('dlog') || colorTransfer.includes('d-log')) {
            profile = 'D-Log';
            confidence = 'metadata';
          } else if (colorTransfer.includes('flat') || colorTransfer.includes('gopro')) {
            profile = 'GoPro Flat';
            confidence = 'metadata';
          }
        } catch {
          // No ffprobe, fall through to heuristics
        }
      }

      // Camera-based heuristics if no metadata hit
      if (confidence === 'heuristic') {
        const cam = detectedCamera.toLowerCase();
        if (cam.includes('sony')) {
          profile = cam.includes('fx') ? 'S-Log3 Cine' : 'S-Log3';
        } else if (cam.includes('dji')) {
          profile = 'D-Log M';
        } else if (cam.includes('gopro')) {
          profile = 'GoPro Flat';
        } else if (cam.includes('canon') || cam.includes('nikon') || cam.includes('iphone')) {
          profile = 'Rec.709';
        } else if (cam.includes('panasonic')) {
          profile = 'D-Log';
        }
      }

      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            filePath,
            detectedCamera,
            colorProfile: profile,
            confidence,
            rawMetadata: { colorTransfer, colorSpace },
          }, null, 2),
        }],
      };
    } catch (err) {
      return { content: [{ type: 'text', text: `Error detecting color profile: ${err.message}` }], isError: true };
    }
  }
);

// ─── Tool 6: sort_to_bin ─────────────────────────────────────────────────────

server.tool(
  'sort_to_bin',
  'Symlink an asset into the appropriate bin folder within a project.',
  {
    filePath: z.string().describe('Absolute path to the source asset'),
    binName: z.string().describe('Name of the bin folder (e.g. "wide-shots", "drone", "broll")'),
    projectPath: z.string().describe('Absolute path to the project folder'),
  },
  async ({ filePath, binName, projectPath }) => {
    try {
      const binDir = path.join(projectPath, 'bins', binName);
      await fs.mkdir(binDir, { recursive: true });

      const linkPath = path.join(binDir, path.basename(filePath));
      try {
        await fs.unlink(linkPath);
      } catch {
        // No existing link, fine
      }

      await fs.symlink(filePath, linkPath);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            success: true,
            symlink: linkPath,
            target: filePath,
            bin: binName,
          }, null, 2),
        }],
      };
    } catch (err) {
      return { content: [{ type: 'text', text: `Error creating symlink: ${err.message}` }], isError: true };
    }
  }
);

// ─── Tool 7: list_available_luts ─────────────────────────────────────────────

server.tool(
  'list_available_luts',
  'List LUT files from the Charlie drive, optionally filtered by camera or profile.',
  {
    camera: z.string().optional().describe('Filter by camera name (e.g. "sony", "dji", "gopro")'),
    profile: z.string().optional().describe('Filter by profile subdirectory (e.g. "sony-slog3", "dji-dlog")'),
  },
  async ({ camera, profile }) => {
    try {
      await fs.access(LUTS_ROOT);
    } catch {
      return {
        content: [{
          type: 'text',
          text: `LUT directory not accessible: ${LUTS_ROOT}. Is Charlie drive mounted?`,
        }],
        isError: true,
      };
    }

    const subdirs = await fs.readdir(LUTS_ROOT, { withFileTypes: true });
    const results = [];

    for (const entry of subdirs) {
      if (!entry.isDirectory()) continue;
      const dirName = entry.name;

      // Apply filters
      if (profile && !dirName.toLowerCase().includes(profile.toLowerCase())) continue;
      if (camera && !dirName.toLowerCase().includes(camera.toLowerCase())) continue;

      const subPath = path.join(LUTS_ROOT, dirName);
      let files;
      try {
        files = await fs.readdir(subPath);
      } catch {
        continue;
      }

      const luts = files.filter(f => /\.(cube|3dl|lut)$/i.test(f));
      results.push({
        directory: dirName,
        path: subPath,
        lutCount: luts.length,
        luts: luts.map(f => ({ name: f, path: path.join(subPath, f) })),
      });
    }

    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          lutsRoot: LUTS_ROOT,
          filters: { camera: camera ?? 'none', profile: profile ?? 'none' },
          directories: results,
          totalLuts: results.reduce((acc, d) => acc + d.lutCount, 0),
        }, null, 2),
      }],
    };
  }
);

// ─── Tool 8: apply_lut ───────────────────────────────────────────────────────

server.tool(
  'apply_lut',
  'Apply a .cube LUT to footage via FFmpeg lut3d filter.',
  {
    inputPath: z.string().describe('Absolute path to the input video'),
    lutPath: z.string().describe('Absolute path to the .cube LUT file'),
    outputPath: z.string().describe('Absolute path for the output video'),
  },
  async ({ inputPath, lutPath, outputPath }) => {
    try {
      // Validate LUT file exists
      await fs.access(lutPath);

      const cmd = `ffmpeg -y -i "${inputPath}" -vf "lut3d='${lutPath.replace(/'/g, "'\\''")}'" -c:a copy "${outputPath}"`;
      execSync(cmd, { stdio: 'pipe' });

      const stat = await fs.stat(outputPath);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            success: true,
            inputPath,
            lutPath,
            outputPath,
            outputSizeMB: (stat.size / 1024 / 1024).toFixed(2),
          }, null, 2),
        }],
      };
    } catch (err) {
      return { content: [{ type: 'text', text: `Error applying LUT: ${err.message}` }], isError: true };
    }
  }
);

// ─── Tool 9: get_project_brief ───────────────────────────────────────────────

server.tool(
  'get_project_brief',
  'Read brief.json from the project folder.',
  {
    projectPath: z.string().describe('Absolute path to the project folder'),
  },
  async ({ projectPath }) => {
    const briefPath = path.join(projectPath, 'brief.json');
    try {
      const raw = await fs.readFile(briefPath, 'utf-8');
      const brief = JSON.parse(raw);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({ briefPath, brief }, null, 2),
        }],
      };
    } catch (err) {
      return {
        content: [{
          type: 'text',
          text: `brief.json not found at ${briefPath}: ${err.message}`,
        }],
        isError: true,
      };
    }
  }
);

// ─── Tool 10: notify ─────────────────────────────────────────────────────────

server.tool(
  'notify',
  'Send a macOS notification and log a Slack-ready message.',
  {
    title: z.string().describe('Notification title'),
    message: z.string().describe('Notification body'),
    channel: z.string().optional().describe('Slack channel (informational — actual Slack via Slack MCP)'),
  },
  async ({ title, message, channel }) => {
    const results = { macOS: false, slack: false, channel: channel ?? '#general' };

    // macOS notification
    try {
      execSync(
        `osascript -e 'display notification "${message.replace(/"/g, '\\"')}" with title "${title.replace(/"/g, '\\"')}"'`,
        { stdio: 'pipe' }
      );
      results.macOS = true;
    } catch (err) {
      results.macOSError = err.message;
    }

    // Slack: log to stdout (actual delivery via Slack MCP when connected in Claude Desktop)
    const slackPayload = {
      channel: channel ?? '#general',
      text: `*${title}*\n${message}`,
      timestamp: new Date().toISOString(),
    };
    console.error(`[SLACK_NOTIFY] ${JSON.stringify(slackPayload)}`);
    results.slack = true;
    results.slackNote = 'Message logged — actual delivery requires Slack MCP server connection';

    return {
      content: [{
        type: 'text',
        text: JSON.stringify(results, null, 2),
      }],
    };
  }
);

// ─── Start ────────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
