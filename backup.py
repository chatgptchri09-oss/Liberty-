import asyncio
import os
import base64
import aiohttp
import sys
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

DATABASE_NAME = "rdr2_bot.db"
BACKUP_INTERVAL = 6 * 3600  # 6 ore in secondi


async def backup_database():
    """Loop infinito che esegue il backup del database su GitHub ogni 6 ore."""
    print("🔄 Sistema di backup avviato (ogni 6 ore)", flush=True)
    while True:
        await asyncio.sleep(BACKUP_INTERVAL)
        await _push_backup()


async def _push_backup():
    """Esegue il backup del file .db su GitHub tramite API."""
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")  # formato: "utente/nome-repo"

    if not github_token or not github_repo:
        print("⚠️ Backup saltato: GITHUB_TOKEN o GITHUB_REPO non configurati.", flush=True)
        return

    if not os.path.exists(DATABASE_NAME):
        print(f"⚠️ Backup saltato: file '{DATABASE_NAME}' non trovato.", flush=True)
        return

    with open(DATABASE_NAME, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    timestamp   = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    remote_path = f"backups/{DATABASE_NAME}"
    api_url     = f"https://api.github.com/repos/{github_repo}/contents/{remote_path}"

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json"
    }

    async with aiohttp.ClientSession() as session:
        sha = None
        async with session.get(api_url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                sha = data.get("sha")
            elif resp.status not in (404,):
                text = await resp.text()
                print(f"❌ Backup: errore nel recupero SHA ({resp.status}): {text}", flush=True)
                return

        payload = {
            "message": f"🔄 Backup automatico database — {timestamp}",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        async with session.put(api_url, headers=headers, json=payload) as resp:
            if resp.status in (200, 201):
                print(f"✅ Backup completato su GitHub ({timestamp})", flush=True)
            else:
                text = await resp.text()
                print(f"❌ Backup fallito ({resp.status}): {text}", flush=True)
