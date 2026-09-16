# Deploy MediBridge for FREE on Oracle Cloud (Always-Free tier)

Everything was prepared for you already:

- `docker-compose.yml` — two containers (frontend nginx on port 80, backend
  Uvicorn:8000 behind it, OCR + TTS inside the backend image).
- Data now persists: SQLite lives in the `backend-data` Docker volume, so
  accounts/history survive container restarts and rebuilds.
- `deploy/setup.sh` — installs Docker and starts everything with one command.

## Step 1 — Create the free Oracle Cloud account
1. Go to https://www.oracle.com/cloud/free/ and click **Start for free**.
2. Region: pick the one closest to you (e.g. Mumbai / Hyderabad for India).
3. Verify with email + phone, then add a card for ID verification.
   **You will not be charged** — this is Only used to confirm you exist.
4. After signup, open the console (cloud.oracle.com) — it may take a few minutes
   for your tenancy to be ready.

## Step 2 — Create the Always-Free VM
1. Console → **Compute → Instances → Create instance**.
2. Image: **Canonical Ubuntu 24.04** (or 22.04).
3. Shape: **Ampere A1** (Arm) — Always Free. Pick e.g. 2 OCPU / 8 GB RAM.
4. Networking: accept defaults (public IP + internet gateway auto-created).
5. Add your SSH public key — on this Windows PC we will generate one if you
   do not have it.
6. Click **Create**. Note the **public IP** shown on the instance page.
7. Zero-risk check: on the instance detail page the tag "Always Free" must
   appear next to the shape — if you pick a paid shape you'll be billed.

## Step 3 — Open port 80 (and 443 later)
Networking → Virtual Cloud Networks → your VCN → **Security Lists** →
default list → **Add Ingress Rules**:
- Source: `0.0.0.0/0`, IP Protocol: TCP, Destination Port: `80`
  (add `443` too if you later do HTTPS)

## Step 4 — Get the project onto the server and run it
On this PC (or in PowerShell), copy the project up. `<>` = your server IP:

```
scp -r C:\Users\dplav\MEDIBRIDGE ubuntu@<IP>:~/medibridge
```

Then SSH in and deploy (one command):

```
ssh ubuntu@<IP>
cd medibridge
bash deploy/setup.sh
```

Open `http://<IP>/` — MediBridge is live.

> Note: the docker-compose `frontend` container maps host port 80, so no extra
> port mapping is needed.

## Step 5 (optional) — Real domain + free HTTPS later
When you own a domain:
1. Point an A record `@` and `www` to the server IP.
2. On the server run `sudo apt install -y certbot` then
   `sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com`.
3. Add a `:443 ssl` server block in `frontend/nginx.conf` referencing
   `/etc/letsencrypt/live/yourdomain.com/{fullchain,privkey}.pem` and mount
   `/etc/letsencrypt:/etc/letsencrypt:ro` in the frontend service.

## Checks after deploy
- `curl http://<IP>/health` → `{"status":"ok", ..., "ai_provider":"mock"}`
- Upload the sample `clean_report.png` → cards + exactly 3 questions + audio.
- Sign up → upload twice → **Previous Records** shows the trend table.