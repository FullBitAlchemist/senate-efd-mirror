# Senate eFD mirror

A tiny **public** repo that mirrors recent U.S. Senate electronic Periodic
Transaction Reports (PTRs) as JSON, so a datacenter-hosted agent can read them.

## Why this exists

`efdsearch.senate.gov` edge-blocks datacenter IPs (Akamai `Access Denied`), so the
trading agent's DigitalOcean droplet cannot scrape it directly. GitHub Actions
runners are **not** blocked, so this repo scrapes the site on a schedule and
publishes `data/senate_efd.json`, which the agent reads via
`raw.githubusercontent.com` (never blocked). Only public government data lives
here — the trading strategy stays in the private repo.

## Setup (one time)

1. Create a **new public GitHub repo**, e.g. `senate-efd-mirror`.
2. Copy the contents of this folder into it and push to `main`.
3. On GitHub: **Settings → Actions → General → Workflow permissions →** enable
   **Read and write permissions** (so the Action can commit the refreshed JSON).
4. **Actions** tab → run **"Senate eFD mirror"** once via *Run workflow*.
5. Confirm `data/senate_efd.json` updates, then give the agent this URL:
   `https://raw.githubusercontent.com/<you>/senate-efd-mirror/main/data/senate_efd.json`
   (it becomes `config.SENATE_EFD_MIRROR` on the droplet).

The workflow re-runs every 3 hours. `senate_efd_scrape.py` needs only `requests`.
