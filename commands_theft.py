import discord
from discord import app_commands
from datetime import datetime, timezone
import database
from constants import LOG_CHANNEL_ID, DISTILL_ROLE_ID

def _criminali_attivi() -> bool:
    try:
        import commands_invoice as _ci
        return _ci._azioni_criminali_attive
    except Exception:
        return True

_MSG_OFFLINE = "❌ Le **azioni criminali** sono attualmente **offline**.\nAttendi che lo Staff le riattivi."

# ── Emoji animate ─────────────────────────────────────────────────────────────
EMOJI_FUOCO       = "<a:fuoco:1502969683551453234>"
EMOJI_CONFERMA    = "<a:conferma:1451983464764014733>"
EMOJI_CARICAMENTO = "<a:Caricamento:1432417274983219276>"

# ── Ruoli ─────────────────────────────────────────────────────────────────────
DROGA_CONFIG = {
    "🍃 Tabacco":           1421166296850235602,
    "🍁 Canapa":            1421166461988114532,
    "🌿 Foglie di Cocaina": 1421166604447776780,
    "💉 Eroina":            1404052027570524181,
}

FALSARIO_ROLE_ID = 1404052043424989194  # Unico ruolo per creazione armi
ITEM_FORBICI     = "✂️ • Forbici per raccolta droga"

# Sessioni attive in memoria
_raccolte_attive:          dict = {}
_vendite_attive:           dict = {}
_creazioni_attive:         dict = {}
_distillazioni_attive:     dict = {}
_vendite_moonshine_attive: dict = {}
_creazioni_armi_attive:    dict = {}


def _durata_str(secondi: float) -> str:
    h = int(secondi // 3600)
    m = int((secondi % 3600) // 60)
    s = int(secondi % 60)
    if h > 0:   return f"{h}h {m}min {s}s"
    elif m > 0: return f"{m}min {s}s"
    return f"{s}s"

def _barra(secondi: float, max_s: int = 3600, lunghezza: int = 12) -> str:
    riempita = min(int((secondi / max_s) * lunghezza), lunghezza)
    return "█" * riempita + "░" * (lunghezza - riempita)


ARMI_CHOICES = [
    app_commands.Choice(name="🔫 Revolver",       value="🔫 Revolver"),
    app_commands.Choice(name="🔫 Fucile a Pompa", value="🔫 Fucile a Pompa"),
    app_commands.Choice(name="🔫 Carabina",       value="🔫 Carabina"),
    app_commands.Choice(name="🗡️ Coltello",       value="🗡️ Coltello"),
    app_commands.Choice(name="💣 Dinamite",        value="💣 Dinamite"),
]


def setup_theft_commands(bot):

    # ══════════════════════════════════════════════════════════════════════════
    #  RACCOLTA DROGA
    # ══════════════════════════════════════════════════════════════════════════

    @bot.tree.command(name="inizio-raccolta", description="Inizia una sessione di raccolta droga")
    @app_commands.describe(droga="Tipo di droga da raccogliere", foto="Foto della sessione (OBBLIGATORIA)")
    @app_commands.choices(droga=[
        app_commands.Choice(name="🍃 Tabacco",           value="🍃 Tabacco"),
        app_commands.Choice(name="🍁 Canapa",             value="🍁 Canapa"),
        app_commands.Choice(name="🌿 Foglie di Cocaina",  value="🌿 Foglie di Cocaina"),
        app_commands.Choice(name="💉 Eroina",             value="💉 Eroina"),
    ])
    async def inizio_raccolta(interaction: discord.Interaction, droga: str, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if uid in _raccolte_attive:
            r = _raccolte_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una raccolta di **{r['droga']}** in corso! Usa `/fine-raccolta` prima.", ephemeral=True); return
        ruolo_id = DROGA_CONFIG.get(droga)
        if not ruolo_id or not isinstance(member, discord.Member) or \
           not any(r.id == ruolo_id for r in member.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per raccogliere **{droga}**.", ephemeral=True); return
        if await database.get_item_quantity(uid, ITEM_FORBICI) < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{ITEM_FORBICI}** nella bisaccia!", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _raccolte_attive[uid] = {"droga": droga, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_CARICAMENTO} 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_CARICAMENTO}",
            description=(
                "*Le mani si sporcano di terra. La raccolta ha inizio...*\n"
                "*Muoviti in silenzio, viandante. Le autorità potrebbero essere vicine.*\n\u200b"
            ),
            color=discord.Color(0x2E8B57),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🤠 Raccoglitore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🌿 Tipo Droga",   value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Sessione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;32m● RACCOLTA IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Raccolta | Usa /fine-raccolta per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="fine-raccolta", description="Termina la sessione di raccolta droga")
    @app_commands.describe(droga="Tipo di droga che stavi raccogliendo")
    @app_commands.choices(droga=[
        app_commands.Choice(name="🍃 Tabacco",           value="🍃 Tabacco"),
        app_commands.Choice(name="🍁 Canapa",             value="🍁 Canapa"),
        app_commands.Choice(name="🌿 Foglie di Cocaina",  value="🌿 Foglie di Cocaina"),
        app_commands.Choice(name="💉 Eroina",             value="💉 Eroina"),
    ])
    async def fine_raccolta(interaction: discord.Interaction, droga: str):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _raccolte_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna raccolta attiva. Usa `/inizio-raccolta` prima.", ephemeral=True); return
        sessione = _raccolte_attive[uid]
        if sessione["droga"] != droga:
            await interaction.response.send_message(
                f"❌ La tua raccolta attiva è di **{sessione['droga']}**, non di **{droga}**.", ephemeral=True); return
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _raccolte_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description=(
                "*La bisaccia è piena. Ora sparisci prima che qualcuno ti veda.*\n\u200b"
            ),
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🤠 Raccoglitore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🌿 Droga",        value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="⏱️ Durata Totale",
            value=f"```\n  {_durata_str(durata_s)}\n```",
            inline=True
        )
        embed.add_field(
            name="📊 Progresso",
            value=f"```\n  [{_barra(durata_s)}]\n```",
            inline=True
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Raccolta Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  VENDITA DROGA
    # ══════════════════════════════════════════════════════════════════════════

    @bot.tree.command(name="inizio-vendita", description="Inizia una sessione di vendita droga")
    @app_commands.describe(droga="Tipo di droga da vendere", foto="Foto della sessione (OBBLIGATORIA)")
    @app_commands.choices(droga=[
        app_commands.Choice(name="🍃 Tabacco",           value="🍃 Tabacco"),
        app_commands.Choice(name="🍁 Canapa",             value="🍁 Canapa"),
        app_commands.Choice(name="🌿 Foglie di Cocaina",  value="🌿 Foglie di Cocaina"),
        app_commands.Choice(name="💉 Eroina",             value="💉 Eroina"),
    ])
    async def inizio_vendita(interaction: discord.Interaction, droga: str, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if uid in _vendite_attive:
            v = _vendite_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una vendita di **{v['droga']}** in corso! Usa `/fine-vendita` prima.", ephemeral=True); return
        ruolo_id = DROGA_CONFIG.get(droga)
        if not ruolo_id or not isinstance(member, discord.Member) or \
           not any(r.id == ruolo_id for r in member.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per vendere **{droga}**.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _vendite_attive[uid] = {"droga": droga, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_CARICAMENTO} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_CARICAMENTO}",
            description=(
                "*La merce cambia mani nell'ombra. L'affare ha inizio...*\n"
                "*Occhi aperti, la legge potrebbe essere in agguato.*\n\u200b"
            ),
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🤠 Venditore",  value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🌿 Tipo Droga", value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Sessione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;33m● VENDITA IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Vendita | Usa /fine-vendita per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="fine-vendita", description="Termina la sessione di vendita droga")
    @app_commands.describe(droga="Tipo di droga che stavi vendendo")
    @app_commands.choices(droga=[
        app_commands.Choice(name="🍃 Tabacco",           value="🍃 Tabacco"),
        app_commands.Choice(name="🍁 Canapa",             value="🍁 Canapa"),
        app_commands.Choice(name="🌿 Foglie di Cocaina",  value="🌿 Foglie di Cocaina"),
        app_commands.Choice(name="💉 Eroina",             value="💉 Eroina"),
    ])
    async def fine_vendita(interaction: discord.Interaction, droga: str):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _vendite_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna vendita attiva. Usa `/inizio-vendita` prima.", ephemeral=True); return
        sessione = _vendite_attive[uid]
        if sessione["droga"] != droga:
            await interaction.response.send_message(
                f"❌ La tua vendita attiva è di **{sessione['droga']}**, non di **{droga}**.", ephemeral=True); return
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _vendite_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description=(
                "*L'oro è nelle tasche. L'affare è concluso.*\n\u200b"
            ),
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🤠 Venditore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🌿 Droga",     value=f"**{droga}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Vendita Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  DISTILLERIA — CREAZIONE ALCOOL
    # ══════════════════════════════════════════════════════════════════════════

    @bot.tree.command(name="inizio-creazione-alcool", description="[Distilleria] Inizia la creazione di una partita di Moonshine")
    @app_commands.describe(foto="Foto della sessione (OBBLIGATORIA)")
    async def inizio_creazione_alcool(interaction: discord.Interaction, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        alcool = "🌙 Moonshine"
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True); return
        if uid in _creazioni_attive:
            await interaction.response.send_message(
                f"❌ Hai già una creazione di **{_creazioni_attive[uid]['alcool']}** in corso!\nUsa `/fine-creazione-alcool` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _creazioni_attive[uid] = {"alcool": alcool, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_FUOCO} 𝐂𝐑𝐄𝐀𝐙𝐈𝐎𝐍𝐄 𝐀𝐋𝐂𝐎𝐎𝐋 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_FUOCO}",
            description=(
                "*Le botti fumano, l'alambicco bolle...*\n"
                "*Il profumo del Moonshine riempie la stanza.*\n\u200b"
            ),
            color=discord.Color(0xC8860A),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="👨‍🏭 Distillatore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🥃 Prodotto",      value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Produzione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;33m● PRODUZIONE IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Distilleria | /fine-creazione-alcool per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="fine-creazione-alcool", description="[Distilleria] Termina la creazione di una partita di Moonshine")
    async def fine_creazione_alcool(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _creazioni_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna creazione in corso. Usa `/inizio-creazione-alcool` prima.", ephemeral=True); return
        sessione = _creazioni_attive[uid]
        alcool   = sessione["alcool"]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _creazioni_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐂𝐑𝐄𝐀𝐙𝐈𝐎𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description=(
                "*La partita è pronta. L'odore si diffonde per la distilleria.*\n\u200b"
            ),
            color=discord.Color(0x27AE60),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="👨‍🏭 Distillatore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🥃 Prodotto",      value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;32m★ PARTITA PRONTA PER LA CONSEGNA ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Distilleria | Produzione Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  DISTILLERIA — DISTILLAZIONE
    # ══════════════════════════════════════════════════════════════════════════

    @bot.tree.command(name="inizio-distillazione", description="[Distilleria] Inizia una sessione di distillazione Moonshine")
    @app_commands.describe(foto="Foto della sessione (OBBLIGATORIA)")
    async def inizio_distillazione(interaction: discord.Interaction, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        alcool = "🌙 Moonshine"
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True); return
        if uid in _distillazioni_attive:
            await interaction.response.send_message(
                f"❌ Hai già una distillazione in corso!\nUsa `/fine-distillazione` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _distillazioni_attive[uid] = {"alcool": alcool, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_FUOCO} 𝐃𝐈𝐒𝐓𝐈𝐋𝐋𝐀𝐙𝐈𝐎𝐍𝐄 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_FUOCO}",
            description=(
                "*Il fuoco arde sotto l'alambicco. Il liquido scorre lentamente...*\n"
                "*Ogni goccia è preziosa. Non sprecare nulla.*\n\u200b"
            ),
            color=discord.Color(0xE74C3C),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="👨‍🏭 Distillatore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🔬 Distillato",    value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Distillazione",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;31m🔥 DISTILLAZIONE IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Distilleria | /fine-distillazione per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="fine-distillazione", description="[Distilleria] Termina la sessione di distillazione Moonshine")
    async def fine_distillazione(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _distillazioni_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna distillazione in corso. Usa `/inizio-distillazione` prima.", ephemeral=True); return
        sessione = _distillazioni_attive[uid]
        alcool   = sessione["alcool"]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _distillazioni_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐃𝐈𝐒𝐓𝐈𝐋𝐋𝐀𝐙𝐈𝐎𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description=(
                "*L'alambicco si raffredda. Il distillato è pronto per essere imbottigliato.*\n\u200b"
            ),
            color=discord.Color(0x8E44AD),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="👨‍🏭 Distillatore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🔬 Distillato",    value=f"**{alcool}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;35m★ DISTILLATO PRONTO PER L'IMBOTTIGLIAMENTO ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Distilleria | Distillazione Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  DISTILLERIA — VENDITA MOONSHINE
    # ══════════════════════════════════════════════════════════════════════════

    @bot.tree.command(name="inizio-vendita-moonshine", description="[Distilleria] Inizia una sessione di vendita Moonshine")
    @app_commands.describe(foto="Foto della sessione (OBBLIGATORIA)")
    async def inizio_vendita_moonshine(interaction: discord.Interaction, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True); return
        if uid in _vendite_moonshine_attive:
            await interaction.response.send_message(
                "❌ Hai già una vendita di **🌙 Moonshine** in corso!\nUsa `/fine-vendita-moonshine` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _vendite_moonshine_attive[uid] = {"inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_CARICAMENTO} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐌𝐎𝐎𝐍𝐒𝐇𝐈𝐍𝐄 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_CARICAMENTO}",
            description=(
                "*Il contrabbandiere carica i barili sul carro...*\n"
                "*La notte è il momento migliore per i traffici oscuri.*\n\u200b"
            ),
            color=discord.Color(0x4B0082),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="👨‍🏭 Distillatore", value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🌙 Prodotto",      value="**🌙 Moonshine**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Vendita",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;34m● CONSEGNA IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Distilleria | /fine-vendita-moonshine per terminare")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="fine-vendita-moonshine", description="[Distilleria] Termina la sessione di vendita Moonshine")
    async def fine_vendita_moonshine(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _vendite_moonshine_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna vendita Moonshine in corso. Usa `/inizio-vendita-moonshine` prima.", ephemeral=True); return
        sessione = _vendite_moonshine_attive[uid]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _vendite_moonshine_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐌𝐎𝐎𝐍𝐒𝐇𝐈𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description=(
                "*I barili sono stati consegnati. L'oro scorre nelle tasche...*\n\u200b"
            ),
            color=discord.Color(0x9B59B6),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="👨‍🏭 Distillatore", value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🌙 Prodotto",      value="**🌙 Moonshine**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso", value=f"```\n  [{_barra(durata_s)}]\n```", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;32m★ CONSEGNA COMPLETATA CON SUCCESSO ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Distilleria | Vendita Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  ARMERIA — CREAZIONE ARMI  🔫
    # ══════════════════════════════════════════════════════════════════════════

    @bot.tree.command(name="inizio-creazione-armi", description="[Armeria] Inizia una sessione di forgiatura armi")
    @app_commands.describe(
        arma="Tipo di arma da forgiare",
        foto="Foto della sessione di lavoro (OBBLIGATORIA)"
    )
    @app_commands.choices(arma=ARMI_CHOICES)
    async def inizio_creazione_armi(interaction: discord.Interaction, arma: str, foto: discord.Attachment):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid    = str(interaction.user.id)
        member = interaction.user
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True); return
        if not isinstance(member, discord.Member) or \
           not any(r.id == FALSARIO_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Non hai i permessi per forgiare armi.", ephemeral=True); return
        if uid in _creazioni_armi_attive:
            await interaction.response.send_message(
                f"❌ Hai già una forgiatura di **{_creazioni_armi_attive[uid]['arma']}** in corso!\n"
                f"Usa `/fine-creazione-armi` prima.", ephemeral=True); return
        now = datetime.now(timezone.utc)
        _creazioni_armi_attive[uid] = {"arma": arma, "inizio": now}

        embed = discord.Embed(
            title=f"{EMOJI_FUOCO} 𝐅𝐎𝐑𝐆𝐈𝐀𝐓𝐔𝐑𝐀 𝐀𝐑𝐌𝐈 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀 {EMOJI_FUOCO}",
            description=(
                "```\n"
                "  ██╗      █████╗ ██████╗  ██████╗ \n"
                "  ██║     ██╔══██╗██╔══██╗██╔═══██╗\n"
                "  ██║     ███████║██████╔╝██║   ██║\n"
                "  ██║     ██╔══██║██╔══██╗██║   ██║\n"
                "  ███████╗██║  ██║██████╔╝╚██████╔╝\n"
                "  ╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ \n"
                "```\n"
                "*Il metallo arroventa la fucina. Le scintille volano nell'aria...*\n"
                "*Il martello risuona. Un'altra leggenda sta per nascere.*\n\u200b"
            ),
            color=discord.Color(0xFF4500),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🔨 Armiere",         value=f"{member.mention}\n`{member.display_name}`", inline=True)
        embed.add_field(name="🔫 Arma in Forgiatura", value=f"**{arma}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="🕐 Inizio Forgiatura",
            value=(
                f"> 🗓️ {discord.utils.format_dt(now, style='D')}\n"
                f"> ⏰ {discord.utils.format_dt(now, style='T')}\n"
                f"> ⏳ {discord.utils.format_dt(now, style='R')}"
            ),
            inline=False
        )
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="📊 Stato",
            value="```ansi\n\u001b[1;31m🔥 FORGIATURA IN CORSO\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_image(url=foto.url)
        embed.set_footer(
            text="🤠 Red Dead Redemption II — Armeria | Usa /fine-creazione-armi per completare",
            icon_url=member.display_avatar.url
        )
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="fine-creazione-armi", description="[Armeria] Termina la sessione di forgiatura armi")
    async def fine_creazione_armi(interaction: discord.Interaction):
        if not _criminali_attivi():
            await interaction.response.send_message(_MSG_OFFLINE, ephemeral=True); return
        uid = str(interaction.user.id)
        if uid not in _creazioni_armi_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna forgiatura in corso.\nUsa `/inizio-creazione-armi` prima.", ephemeral=True); return
        sessione = _creazioni_armi_attive[uid]
        arma     = sessione["arma"]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _creazioni_armi_attive[uid]

        embed = discord.Embed(
            title=f"{EMOJI_CONFERMA} 𝐅𝐎𝐑𝐆𝐈𝐀𝐓𝐔𝐑𝐀 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀 {EMOJI_CONFERMA}",
            description=(
                "*Il metallo si è raffreddato. L'arma è pronta.*\n"
                "*Una creazione degna del Far West è nata tra le mani dell'armiere.*\n\u200b"
            ),
            color=discord.Color(0xFFD700),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════════════╗", inline=False)
        embed.add_field(name="🔨 Armiere",    value=f"{interaction.user.mention}\n`{interaction.user.display_name}`", inline=True)
        embed.add_field(name="🔫 Arma Forgiata", value=f"**{arma}**", inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="🕐 Inizio", value=f"> ⏰ {discord.utils.format_dt(inizio, style='T')}", inline=True)
        embed.add_field(name="🕑 Fine",   value=f"> ⏰ {discord.utils.format_dt(now, style='T')}",   inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(name="⏱️ Durata Forgiatura", value=f"```\n  {_durata_str(durata_s)}\n```", inline=True)
        embed.add_field(name="📊 Progresso",          value=f"```\n  [{_barra(durata_s)}]\n```",    inline=True)
        embed.add_field(name="\u200b", value="╠══════════════════════════╣", inline=False)
        embed.add_field(
            name="✅ Stato Finale",
            value="```ansi\n\u001b[1;33m★ ARMA CONSEGNATA CON SUCCESSO ★\u001b[0m\n```",
            inline=False
        )
        embed.add_field(name="\u200b", value="╚══════════════════════════╝", inline=False)
        embed.set_footer(
            text="🤠 Red Dead Redemption II | Forgiatura Completata",
            icon_url=interaction.user.display_avatar.url
        )
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass
