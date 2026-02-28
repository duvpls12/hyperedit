#!/usr/bin/env node
/**
 * HyperEdit MCP Server entry point.
 * Claude Desktop config references this file; actual implementation is in
 * scripts/hyperedit-mcp-server.js.
 *
 * Claude Desktop MCP config:
 * {
 *   "hyperedit": {
 *     "command": "node",
 *     "args": ["/Users/davideby/hyperedit/mcp/server.js"]
 *   }
 * }
 */
import '../scripts/hyperedit-mcp-server.js';
