import express from 'express';
import net from 'node:net';
import { execFile } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';

const app = express();
const PORT = Number(process.env.PORT || 3499);
const HOST = process.env.HOST || '127.0.0.1';

function loadConfig(){
  const localPath = 'config.local.json';
  const path = existsSync(localPath) ? localPath : 'config.json';
  try {
    const raw = readFileSync(path, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { repoUrl: '', telegramUsername: 'danmaps_clawd_bot' };
  }
}

const CONFIG = loadConfig();

function normalizeServices(services){
  const out = [];
  for(const s of (services || [])){
    if(!s || !s.key || !s.name) continue;
    const port = (s.port === 'self' || s.port === 'PORT') ? PORT : Number(s.port);
    if(!Number.isFinite(port) || port <= 0) continue;
    out.push({
      key: String(s.key),
      name: String(s.name),
      port,
      path: String(s.path || '/'),
      repoUrl: s.repoUrl ? String(s.repoUrl) : '',
    });
  }
  return out;
}

const SERVICES = normalizeServices(CONFIG.services);


function probePort(host, port, timeoutMs = 500) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let done = false;

    const finish = (ok) => {
      if (done) return;
      done = true;
      try { socket.destroy(); } catch {}
      resolve(ok);
    };

    socket.setTimeout(timeoutMs);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));

    socket.connect(port, host);
  });
}

function run(cmd, args) {
  return new Promise((resolve) => {
    execFile(cmd, args, { windowsHide: true }, (err, stdout) => {
      if (err) return resolve('');
      resolve(String(stdout || '').trim());
    });
  });
}

async function getIps() {
  const ts = (await run('tailscale', ['ip', '-4'])).split(/\r?\n/).filter(Boolean)[0] || '';

  // Best-effort LAN IP detection (Windows + Linux)
  let lan = '';

  // Windows: ipconfig
  const ipconfig = await run('ipconfig', []);
  if (ipconfig) {
    const blocks = ipconfig.split(/\r?\n\r?\n/);
    for (const b of blocks) {
      if (!b.includes('Wi-Fi') || !b.includes('IPv4 Address')) continue;
      const m = b.match(/IPv4 Address[.\s]*:\s*([0-9.]+)/);
      if (m && (m[1].startsWith('192.168.') || m[1].startsWith('10.'))) {
        lan = m[1];
        break;
      }
    }
    if (!lan) {
      const all = Array.from(ipconfig.matchAll(/IPv4 Address[.\s]*:\s*([0-9.]+)/g)).map((m) => m[1]);
      lan = all.find((ip) => ip.startsWith('192.168.') || ip.startsWith('10.')) || '';
    }
  }

  // Linux/macOS: hostname -I / ip -4 addr
  if (!lan) {
    const hostIps = (await run('hostname', ['-I'])) || '';
    const all = hostIps.split(/\s+/).filter(Boolean);
    lan = all.find((ip) => ip.startsWith('192.168.') || ip.startsWith('10.')) || '';
  }
  if (!lan) {
    const ipAddr = await run('ip', ['-4', 'addr']);
    const all = Array.from(ipAddr.matchAll(/inet\s+([0-9.]+)\//g)).map((m) => m[1]);
    lan = all.find((ip) => ip.startsWith('192.168.') || ip.startsWith('10.')) || '';
  }

  return { tailscale: ts, lan };
}

app.get('/api/status', async (_req, res) => {
  const ips = await getIps();

  const hosts = [
    { key: 'tailscale', label: 'Tailscale', host: ips.tailscale },
    { key: 'lan', label: 'LAN', host: ips.lan },
    { key: 'localhost', label: 'Localhost', host: '127.0.0.1' },
  ].filter((h) => h.host);

  const results = {};
  for (const h of hosts) {
    results[h.key] = {};
    for (const s of SERVICES) {
      const ok = await probePort(h.host, s.port);
      results[h.key][s.key] = { ok };
    }
  }

  res.json({
    success: true,
    updatedAt: new Date().toISOString(),
    ips,
    services: SERVICES,
    results,
    meta: {
      repoUrl: CONFIG.repoUrl || '',
      telegramUsername: CONFIG.telegramUsername || 'danmaps_clawd_bot',
    },
  });
});

app.use(express.static('web'));

app.listen(PORT, HOST, () => {
  console.log(`homelab-home running on http://${HOST}:${PORT}`);
});
