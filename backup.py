import asyncio
import os
import base64
import shutil
import aiohttp
import discord
import sys
from datetime import datetime

sys.stdout.reconfigure(line_buffering=True)

DATABASE_NAME    = "rdr2_bot.db"
BACKUP_INTERVAL  = 6 * 3600
OWNER_ID         = 492778659093716993
OWNER_ROLE_ID    = 1404051866962100286
NOTIFY_CHANNEL   = 1407293728103727197


# ── Helper permessi ───────────────────────────────────────────────────────────
def _can_use(interaction) -> bool:
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        return any(r.id == OWNER_ROLE_ID for r in interaction.user.roles)
    return False


# ── Funzione core: push backup su GitHub ─────────────────────────────────────
async def _push_backup() -> tuple[bool, str]:
    """Esegue il backup. Ritorna (successo, messaggio)."""
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo  = os.getenv("GITHUB_REPO")

    if not github_token or not github_repo:
        msg = "⚠️ GITHUB_TOKEN o GITHUB_REPO non configurati."
        print(msg, flush=True)
        return False, msg

    if not os.path.exists(DATABASE_NAME):
        msg = f"⚠️ File '{DATABASE_NAME}' non trovato."
        print(msg, flush=True)
        return False, msg

    size_bytes  = os.path.getsize(DATABASE_NAME)
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
                msg = f"❌ Errore recupero SHA ({resp.status})"
                print(f"{msg}: {text}", flush=True)
                return False, msg

        payload = {
            "message": f"🔄 Backup automatico database — {timestamp}",
            "content": content_b64,
            "branch":  "main"
        }
        if sha:
            payload["sha"] = sha

        async with session.put(api_url, headers=headers, json=payload) as resp:
            if resp.status in (200, 201):
                print(f"✅ Backup completato su GitHub ({timestamp})", flush=True)
                await _cleanup_old_backups(session, headers, backup_dir)
                return True, timestamp
            else:
                text = await resp.text()
                msg = f"❌ Backup fallito ({resp.status})"
                print(f"{msg}: {text}", flush=True)
                return False, msg


async def _cleanup_old_backups(session, headers, backup_dir_url):
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
                "message": f"🗑️ Pulizia automatica: {name}",
                "sha":     sha,
                "branch":  "main"
            }
            async with session.delete(del_url, headers=headers, json=payload) as del_resp:
                if del_resp.status == 200:
                    deleted += 1

    if deleted:
        print(f"🗑️ Eliminati {deleted} vecchi file di backup", flush=True)


# ── Loop automatico ogni 6 ore ────────────────────────────────────────────────
async def backup_database(bot=None):
    print("🔄 Sistema di backup avviato (ogni 6 ore)", flush=True)
    while True:
        await asyncio.sleep(BACKUP_INTERVAL)
        ok, result = await _push_backup()

        # Notifica nel canale Discord
        if bot:
            try:
                ch = bot.get_channel(NOTIFY_CHANNEL)
                if ch:
                    if ok:
                        embed = discord.Embed(
                            title="✅ Backup Automatico Completato",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.add_field(name="🕐 Data/Ora UTC", value=result, inline=True)
                        embed.add_field(name="📦 File",         value=DATABASE_NAME, inline=True)
                        embed.add_field(name="🔁 Prossimo",     value="tra 6 ore",   inline=True)
                    else:
                        embed = discord.Embed(
                            title="❌ Backup Automatico Fallito",
                            description=result,
                            color=discord.Color.red(),
                            timestamp=discord.utils.utcnow()
                        )
                    embed.set_footer(text="🤠 Red Dead Redemption II — Backup")
                    await ch.send(embed=embed)
            except Exception as e:
                print(f"⚠️ Notifica backup fallita: {e}", flush=True)


# ── Comandi Discord ───────────────────────────────────────────────────────────
def setup_backup_commands(bot):

    # ── /backup-create ────────────────────────────────────────────────────────
    @bot.tree.command(
        name="backup-create",
        description="[Owner] Crea subito un backup del database su GitHub"
    )
    async def backup_create(interaction: discord.Interaction):
        if not _can_use(interaction):
            await interaction.response.send_message(
                "❌ Non hai i permessi per usare questo comando.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        ok, result = await _push_backup()

        if ok:
            embed = discord.Embed(
                title="✅ 𝐁𝐚𝐜𝐤𝐮𝐩 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐚𝐭𝐨",
                description="Il database è stato salvato su GitHub con successo.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="🕐 Data/Ora UTC", value=result,       inline=True)
            embed.add_field(name="📦 File",         value=DATABASE_NAME, inline=True)
            embed.add_field(name="👤 Avviato da",   value=interaction.user.mention, inline=True)
        else:
            embed = discord.Embed(
                title="❌ 𝐁𝐚𝐜𝐤𝐮𝐩 𝐅𝐚𝐥𝐥𝐢𝐭𝐨",
                description=result,
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )

        embed.set_footer(text="🤠 Red Dead Redemption II — Backup")
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Notifica pubblica nel canale
        try:
            ch = bot.get_channel(NOTIFY_CHANNEL)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ── /backup-load ──────────────────────────────────────────────────────────
    @bot.tree.command(
        name="backup-load",
        description="[Owner] Ripristina il database dall'ultimo backup su GitHub"
    )
    async def backup_load(interaction: discord.Interaction):
        if not _can_use(interaction):
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
        embed.add_field(name="📦 File",        value=DATABASE_NAME,              inline=True)
        embed.add_field(name="💾 Dimensione",  value=f"{len(db_bytes):,} bytes", inline=True)
        embed.add_field(name="👤 Eseguito da", value=interaction.user.mention,   inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ripristino Backup")
        await interaction.followup.send(embed=embed, ephemeral=True)

        # Notifica pubblica nel canale
        try:
            ch = bot.get_channel(NOTIFY_CHANNEL)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

        print(f"✅ Database ripristinato da {interaction.user} ({interaction.user.id})", flush=True)
