import asyncio
import os
import base64
import shutil
import aiohttp
import discord
import sys
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

DATABASE_NAME = "rdr2_bot.db"
BACKUP_INTERVAL = 6 * 3600  # 6 ore in secondi

OWNER_ID      = 492778659093716993   # @fucckku
OWNER_ROLE_ID = 1404051866962100286  # ruolo fallback


# ── Helper permessi ───────────────────────────────────────────────────────────
def _can_restore(interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        return any(r.id == OWNER_ROLE_ID for r in interaction.user.roles)
    return False


# ── Backup automatico ─────────────────────────────────────────────────────────
async def backup_database():
    print("🔄 Sistema di backup avviato (ogni 6 ore)", flush=True)
    while True:
        await asyncio.sleep(BACKUP_INTERVAL)
        await _push_backup()


async def _push_backup():
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")

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
    backup_dir  = f"https://api.github.com/repos/{github_repo}/contents/backups"

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
                await _cleanup_old_backups(session, headers, backup_dir)
            else:
                text = await resp.text()
                print(f"❌ Backup fallito ({resp.status}): {text}", flush=True)


async def _cleanup_old_backups(session: aiohttp.ClientSession, headers: dict, backup_dir_url: str):
    async with session.get(backup_dir_url, headers=headers) as resp:
        if resp.status != 200:
            return
        files = await resp.json()

    deleted = 0
    for f in files:
        name = f.get("name", "")
        if name.startswith("backup_") and name != DATABASE_NAME:
            del_url = f.get("url")
            sha     = f.get("sha")
            if not del_url or not sha:
                continue
            payload = {
                "message": f"🗑️ Pulizia automatica backup vecchio: {name}",
                "sha": sha,
                "branch": "main"
            }
            async with session.delete(del_url, headers=headers, json=payload) as del_resp:
                if del_resp.status == 200:
                    deleted += 1

    if deleted:
        print(f"🗑️ Eliminati {deleted} vecchi file di backup da GitHub", flush=True)


# ── Comando /ripristina-backup ────────────────────────────────────────────────
def setup_backup_commands(bot):

    @bot.tree.command(
        name="ripristina-backup",
        description="[Owner] Ripristina il database dall'ultimo backup su GitHub"
    )
    async def ripristina_backup(interaction: discord.Interaction):
        if not _can_restore(interaction):
            await interaction.response.send_message(
                "❌ Non hai i permessi per usare questo comando.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        github_token = os.getenv("GITHUB_TOKEN")
        github_repo  = os.getenv("GITHUB_REPO")

        if not github_token or not github_repo:
            await interaction.followup.send(
                "❌ GITHUB_TOKEN o GITHUB_REPO non configurati.", ephemeral=True
            )
            return

        api_url = f"https://api.github.com/repos/{github_repo}/contents/backups/{DATABASE_NAME}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as resp:
                if resp.status != 200:
                    await interaction.followup.send(
                        f"❌ Impossibile scaricare il backup (errore {resp.status}).",
                        ephemeral=True
                    )
                    return
                data = await resp.json()

        content_b64 = data.get("content", "").replace("\n", "")
        if not content_b64:
            await interaction.followup.send("❌ Il file di backup è vuoto.", ephemeral=True)
            return

        db_bytes = base64.b64decode(content_b64)

        # Salva copia locale prima di sovrascrivere
        if os.path.exists(DATABASE_NAME):
            shutil.copy(DATABASE_NAME, DATABASE_NAME + ".pre_restore")

        with open(DATABASE_NAME, "wb") as f:
            f.write(db_bytes)

        embed = discord.Embed(
            title="✅ 𝐑𝐢𝐩𝐫𝐢𝐬𝐭𝐢𝐧𝐨 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐚𝐭𝐨",
            description="Il database è stato ripristinato dall'ultimo backup su GitHub.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📦 File",        value=DATABASE_NAME,               inline=True)
        embed.add_field(name="💾 Dimensione",  value=f"{len(db_bytes):,} bytes",  inline=True)
        embed.add_field(name="👤 Eseguito da", value=interaction.user.mention,    inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ripristino Backup")
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"✅ Database ripristinato da {interaction.user} ({interaction.user.id})", flush=True)
