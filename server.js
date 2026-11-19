#!/usr/bin/env node
/*
 * 入党积极分子刷题库 · 本地局域网服务器（Node.js 版，作为 Python 的备用方案）
 * 用法：node server.js [--port 8080] [--open]
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { exec } = require("child_process");

const ROOT = __dirname;
const args = process.argv.slice(2);
const getArg = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const PORT = parseInt(getArg("--port", "8080"), 10);

function detectLan() {
  const nets = os.networkInterfaces();
  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      const fam = net.family;
      if ((fam === "IPv4" || fam === 4) && !net.internal) return net.address;
    }
  }
  return "127.0.0.1";
}

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
};

const server = http.createServer((req, res) => {
  const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
  if (urlPath === "/api/info") {
    const body = JSON.stringify({ lan: LAN_IP, port: PORT });
    res.writeHead(200, {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    });
    res.end(body);
    return;
  }

  let rel = urlPath === "/" ? "/index.html" : urlPath;
  const filePath = path.join(ROOT, path.normalize(rel));
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }
  fs.readFile(filePath, (err, data) => {
    if (err) {
      res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("404 Not Found");
      return;
    }
    const type = MIME[path.extname(filePath).toLowerCase()] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": type, "Cache-Control": "no-cache" });
    res.end(data);
  });
});

const LAN_IP = detectLan();
server.listen(PORT, "0.0.0.0", () => {
  const local = `http://localhost:${PORT}/`;
  const lan = `http://${LAN_IP}:${PORT}/`;
  console.log("=".repeat(52));
  console.log("  入党积极分子刷题库 · 本地服务已启动 (Node)");
  console.log("=".repeat(52));
  console.log(`  电脑访问： ${local}`);
  console.log(`  手机访问： ${lan}`);
  console.log("  （手机需和电脑连在同一个 WiFi/局域网）");
  console.log("  按 Ctrl+C 停止服务。");
  console.log("=".repeat(52));
  if (args.includes("--open")) {
    const cmd =
      process.platform === "win32"
        ? `start "" "${local}"`
        : process.platform === "darwin"
        ? `open "${local}"`
        : `xdg-open "${local}"`;
    exec(cmd, () => {});
  }
});
