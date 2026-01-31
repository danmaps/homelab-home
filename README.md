# homelab-home

A tiny local homepage/dashboard for your home lab apps.

It:
- detects your Tailscale IP + LAN IP
- probes whether key service ports are open
- shows a simple dashboard with links (mobile-friendly)

## Run

```bash
npm install
npm run dev
```

### Run "for real" (Windows, detached)

This keeps the process running even if the terminal (or OpenClaw exec session) ends:

```powershell
Start-Process -FilePath cmd.exe -WorkingDirectory "$PWD" -ArgumentList '/c','npm start' -WindowStyle Hidden
```

Default URL:
- http://localhost:3499

## Configure services

Edit `SERVICES` in `server.js`.

## Notes

- This does not expose anything to the internet.
- If a service shows DOWN, it may not be running or a firewall is blocking that port.
