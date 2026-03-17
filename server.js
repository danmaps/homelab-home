import express from 'express';
import net from 'node:net';
import { execFile } from 'node:child_process';
import { readFileSync, existsSync, statSync } from 'node:fs';

const app = express();
const PORT = Number(process.env.PORT || 3499);
const HOST = process.env.HOST || '127.0.0.1';
const DEFAULT_CONFIG = {
  repoUrl: '',
  telegramUsername: 'danmaps_clawd_bot',
  services: [],
};

function readConfigFile(path) {
  if (!existsSync(path)) return null;
  try {
    const stat = statSync(path);
    if (!stat.isFile()) {
      console.warn(`Ignoring ${path}: path exists but is not a file`);
      return null;
    }
    const raw = readFileSync(path, 'utf-8');
    return JSON.parse(raw);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.warn(`Ignoring ${path}: could not read/parse JSON (${message})`);
    return null;
  }
}

function loadConfig() {
  const candidates = ['config.local.json', 'config.json'];
  for (const path of candidates) {
    const cfg = readConfigFile(path);
    if (cfg && typeof cfg === 'object') {
      return {
        source: path,
        config: { ...DEFAULT_CONFIG, ...cfg },
      };
    }
  }
  return {
    source: 'defaults',
    config: { ...DEFAULT_CONFIG },
  };
}

const { source: CONFIG_SOURCE, config: CONFIG } = loadConfig();

function normalizeServices(services) {
  const out = [];
  for (const s of services || []) {
    if (!s || !s.key || !s.name) continue;
    const port = (s.port === 'self' || s.port === 'PORT') ? PORT : Number(s.port);
    if (!Number.isFinite(port) || port <= 0) continue;
    out.push({
      key: String(s.key),
      name: String(s.name),
      port,
      path: String(s.path || '/'),
      repoUrl: s.repoUrl ? String(s.repoUrl) : '',
      source: 'config',
    });
  }
  return out;
}

const CONFIG_SERVICES = normalizeServices(Array.isArray(CONFIG.services) ? CONFIG.services : []);

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

  let lan = '';
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

function parsePublishedPorts(raw) {
  const text = String(raw || '').trim();
  if (!text) return [];
  const parts = text.split(',').map((s) => s.trim()).filter(Boolean);
  const out = [];
  for (const part of parts) {
    const m = part.match(/(?:(\d+\.\d+\.\d+\.\d+):)?(\d+)->(\d+)\/tcp/);
    if (!m) continue;
    out.push({
      hostIp: m[1] || '',
      hostPort: Number(m[2]),
      containerPort: Number(m[3]),
      protocol: 'tcp',
    });
  }
  return out;
}

async function getDockerServices() {
  const raw = await run('docker', ['ps', '--format', '{{.Names}}|{{.Ports}}']);
  if (!raw) return [];
  const rows = raw.split(/\r?\n/).filter(Boolean);
  const services = [];
  for (const row of rows) {
    const [name, portsRaw = ''] = row.split('|');
    const ports = parsePublishedPorts(portsRaw);
    const primary = ports.find((p) => p.hostPort && p.protocol === 'tcp') || null;
    services.push({
      key: name,
      name,
      containerName: name,
      port: primary ? primary.hostPort : null,
      hostIp: primary?.hostIp || '',
      containerPort: primary?.containerPort || null,
      path: '/',
      repoUrl: '',
      source: 'docker',
      reachable: Boolean(primary),
      ports,
    });
  }
  return services;
}

function mergeServices(configServices, dockerServices) {
  const map = new Map();

  for (const svc of dockerServices) {
    map.set(svc.key, svc);
  }

  for (const svc of configServices) {
    const existing = map.get(svc.key);
    if (existing) {
      map.set(svc.key, {
        ...existing,
        ...svc,
        port: existing.port ?? svc.port,
        host: svc.host || existing.host || '',
        publicUrl: svc.publicUrl || existing.publicUrl || '',
        source: existing.source === 'docker' ? 'docker+config' : svc.source,
      });
    } else {
      map.set(svc.key, svc);
    }
  }

  return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
}

app.get('/api/status', async (_req, res) => {
  const ips = await getIps();
  const dockerServices = await getDockerServices();
  const services = mergeServices(CONFIG_SERVICES, dockerServices);

  const tailscaleHost = ips.tailscale || '100.87.16.33';
  const results = {};
  for (const s of services) {
    if (!s.port || !Number.isFinite(Number(s.port))) {
      results[s.key] = { ok: false, reason: 'no-published-port' };
      continue;
    }
    const displayHost = s.hostIp || tailscaleHost;
    const probeHost = (!displayHost || displayHost === '0.0.0.0') ? 'host.docker.internal' : displayHost;
    const ok = await probePort(probeHost, Number(s.port));
    results[s.key] = { ok, host: displayHost, port: Number(s.port) };
  }

  res.json({
    success: true,
    updatedAt: new Date().toISOString(),
    ips,
    services,
    results,
    meta: {
      repoUrl: CONFIG.repoUrl || '',
      telegramUsername: CONFIG.telegramUsername || 'danmaps_clawd_bot',
      configSource: CONFIG_SOURCE,
    },
  });
});

app.use(express.static('web'));

app.listen(PORT, HOST, () => {
  console.log(`homelab-home running on http://${HOST}:${PORT}`);
  console.log(`config source: ${CONFIG_SOURCE} (${CONFIG_SERVICES.length} configured service${CONFIG_SERVICES.length === 1 ? '' : 's'})`);
});
