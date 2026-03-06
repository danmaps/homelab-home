# homelab-home

A tiny local homepage/dashboard for your home lab apps.

It:
- detects your Tailscale IP + LAN IP
- probes whether key service ports are open
- shows a simple dashboard with links (mobile-friendly)

## Run

```bash
npm install
npm start
``` 

Default URL:
- http://localhost:3499

## Configure services

Create `config.local.json` (recommended) or edit `config.json`.

Load order:
- `config.local.json` (if present and valid JSON file)
- `config.json`
- built-in defaults (empty services list)

Use [`config.example.json`](/home/openclaw/.openclaw/workspace/homelab-home/config.example.json) as the template.

## Notes

- This does not expose anything to the internet.
- If a service shows DOWN, it may not be running or a firewall is blocking that port.
