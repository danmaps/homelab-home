# Power recovery runbook

## Decision

The Conductor host is a Dell OptiPlex 9020. It must start automatically when
utility power is restored after an outage so that the reverse proxy, containers,
and user-managed web services recover without an interactive login.

Set the Dell BIOS **AC Power Recovery Mode** to **On** (not `Last`, which leaves
the machine off when it was off at the time of the outage).

The firmware token table identifies the setting as:

| Option | Token | Desired state |
| --- | --- | --- |
| AC Power Recovery Mode | `0x00a3` | `On` |

`Off` is token `0x00a1`; `Last` is `0x00a2`.

## Configuration procedure

Use Dell's SMBIOS utility. Do not write raw values to the kernel's Dell SMBIOS
sysfs files.

```bash
sudo add-apt-repository --yes universe
sudo apt-get update
sudo apt-get install --yes smbios-utils

# Inspect the available firmware tokens and save an auditable export.
sudo smbios-token-ctl --dump-tokens-csv > /home/danny/dell-bios-tokens.csv

# Enable automatic power-on after AC power is restored.
sudo smbios-token-ctl --activate --token-id=0x00a3

# Verify the result. The AC Power Recovery Mode / On row must be true.
sudo smbios-token-ctl --dump-tokens-csv > /home/danny/dell-bios-tokens.csv
rg 'AC Power Recovery Mode' /home/danny/dell-bios-tokens.csv
```

Expected verification output:

```text
0x00a1,bool,false,AC Power Recovery Mode,Off
0x00a2,bool,false,AC Power Recovery Mode,Last
0x00a3,bool,true,AC Power Recovery Mode,On
```

If the BIOS has an administrator password, enter it through the normal `sudo`
prompt and pass it to `smbios-token-ctl` only when required. Do not store that
password in this repository or in scripts.

## OS boot prerequisites

Firmware power recovery only turns the machine on. The following services must
also be enabled so applications return after the operating system boots:

- system services: Caddy, Docker, Tailscale, and OpenClaw Gateway
- user services: the web applications (including Maps, Tracker, Apps, and
  Spatial Workbench)
- systemd user lingering for `danny`, allowing user services to start without
  an interactive login

Verify after maintenance or a reboot:

```bash
systemctl is-enabled caddy docker tailscaled openclaw-gateway
loginctl show-user danny -p Linger
systemctl --user --failed
docker ps
```

## Optional controlled test

After confirming backups and remote access, shut down the host, remove AC power
briefly, then restore it. Confirm that the host boots, Caddy is active, and the
public sites respond. Do not use a switched power strip that prevents AC from
being restored to the computer.
