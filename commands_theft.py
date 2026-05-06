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

# ── Ruoli richiesti per tipo di droga ────────────────────────────────────────
DROGA_CONFIG = {
    "🍃 Tabacco":           1421166296850235602,
    "🍁 Canapa":            1421166461988114532,
    "🌿 Foglie di Cocaina": 1421166604447776780,
    "💉 Eroina":            1404052027570524181,
}

ITEM_FORBICI = "✂️ • Forbici per raccolta droga"

# Sessioni attive in memoria
_raccolte_attive:    dict = {}
_vendite_attive:     dict = {}
_creazioni_attive:   dict = {}   # /inizio-creazione-alcool
_distillazioni_attive: dict = {} # /inizio-distillazione
_vendite_moonshine_attive: dict = {}  # /inizio-vendita-moonshine


def _durata_str(secondi: float) -> str:
    h = int(secondi // 3600)
    m = int((secondi % 3600) // 60)
    s = int(secondi % 60)
    if h > 0:   return f"{h}h {m}min {s}s"
    elif m > 0: return f"{m}min {s}s"
    return f"{s}s"


# ── Tipi di alcool per la distilleria ────────────────────────────────────────
ALCOOL_CHOICES = [
    app_commands.Choice(name="🥃 Whisky",  value="🥃 Whisky"),
    app_commands.Choice(name="🍺 Birra",   value="🍺 Birra"),
    app_commands.Choice(name="🍶 Gin",     value="🍶 Gin"),
    app_commands.Choice(name="🍹 Brandy",  value="🍹 Brandy"),
    app_commands.Choice(name="🥃 Rum",     value="🥃 Rum"),
]


def setup_theft_commands(bot):

    # ══════════════════════════════════════════════════════════════════════════
    #  RACCOLTA DROGA
    # ══════════════════════════════════════════════════════════════════════════

    @bot.tree.command(name="inizio-raccolta", description="Inizia una sessione di raccolta droga")
    @app_commands.describe(
        droga="Tipo di droga da raccogliere",
        foto="Foto della sessione (OBBLIGATORIA)"
    )
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
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True)
            return

        if uid in _raccolte_attive:
            r = _raccolte_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una raccolta di **{r['droga']}** in corso! Usa `/fine-raccolta` prima.", ephemeral=True)
            return

        ruolo_id = DROGA_CONFIG.get(droga)
        if not ruolo_id or not isinstance(member, discord.Member) or \
           not any(r.id == ruolo_id for r in member.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per raccogliere **{droga}**.", ephemeral=True)
            return

        if await database.get_item_quantity(uid, ITEM_FORBICI) < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{ITEM_FORBICI}** nella bisaccia!", ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        _raccolte_attive[uid] = {"droga": droga, "inizio": now}

        embed = discord.Embed(
            title="🌱 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀",
            color=discord.Color(0x2E8B57),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="🤠 Raccoglitore", value=member.mention,                    inline=False)
        embed.add_field(name="🌿 Droga",        value=droga,                             inline=True)
        embed.add_field(name="🕐 Inizio",       value=f"<t:{int(now.timestamp())}:t>",  inline=True)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Raccolta • Usa /fine-raccolta per terminare")
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
                "❌ Non hai nessuna raccolta attiva. Usa `/inizio-raccolta` prima.", ephemeral=True)
            return
        sessione = _raccolte_attive[uid]
        if sessione["droga"] != droga:
            await interaction.response.send_message(
                f"❌ La tua raccolta attiva è di **{sessione['droga']}**, non di **{droga}**.", ephemeral=True)
            return

        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _raccolte_attive[uid]

        embed = discord.Embed(
            title="✅ 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐀",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Raccoglitore",  value=interaction.user.mention,            inline=False)
        embed.add_field(name="🌿 Droga",          value=droga,                               inline=True)
        embed.add_field(name="\u200b",             value="\u200b",                            inline=False)
        embed.add_field(name="🕐 Inizio",         value=f"<t:{int(inizio.timestamp())}:t>", inline=True)
        embed.add_field(name="🕑 Fine",           value=f"<t:{int(now.timestamp())}:t>",    inline=True)
        embed.add_field(name="\u200b",             value="\u200b",                            inline=False)
        embed.add_field(name="⏱️ Tempo raccolto", value=f"**{_durata_str(durata_s)}**",     inline=False)
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
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True)
            return
        if uid in _vendite_attive:
            v = _vendite_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una vendita di **{v['droga']}** in corso! Usa `/fine-vendita` prima.", ephemeral=True)
            return

        ruolo_id = DROGA_CONFIG.get(droga)
        if not ruolo_id or not isinstance(member, discord.Member) or \
           not any(r.id == ruolo_id for r in member.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per vendere **{droga}**.", ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        _vendite_attive[uid] = {"droga": droga, "inizio": now}

        embed = discord.Embed(
            title="💰 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="🤠 Venditore", value=member.mention,                   inline=False)
        embed.add_field(name="🌿 Droga",     value=droga,                            inline=True)
        embed.add_field(name="🕐 Inizio",    value=f"<t:{int(now.timestamp())}:t>",  inline=True)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Vendita • Usa /fine-vendita per terminare")
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
                "❌ Non hai nessuna vendita attiva. Usa `/inizio-vendita` prima.", ephemeral=True)
            return
        sessione = _vendite_attive[uid]
        if sessione["droga"] != droga:
            await interaction.response.send_message(
                f"❌ La tua vendita attiva è di **{sessione['droga']}**, non di **{droga}**.", ephemeral=True)
            return

        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _vendite_attive[uid]

        embed = discord.Embed(
            title="✅ 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐀",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Venditore",    value=interaction.user.mention,            inline=False)
        embed.add_field(name="🌿 Droga",         value=droga,                               inline=True)
        embed.add_field(name="\u200b",            value="\u200b",                            inline=False)
        embed.add_field(name="🕐 Inizio",        value=f"<t:{int(inizio.timestamp())}:t>", inline=True)
        embed.add_field(name="🕑 Fine",          value=f"<t:{int(now.timestamp())}:t>",    inline=True)
        embed.add_field(name="\u200b",            value="\u200b",                            inline=False)
        embed.add_field(name="⏱️ Tempo vendita", value=f"**{_durata_str(durata_s)}**",     inline=False)
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
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True)
            return

        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True)
            return

        if uid in _creazioni_attive:
            c = _creazioni_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una creazione di **{c['alcool']}** in corso!\nUsa `/fine-creazione-alcool` prima.",
                ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        _creazioni_attive[uid] = {"alcool": alcool, "inizio": now}

        embed = discord.Embed(
            title="🏭 𝐂𝐑𝐄𝐀𝐙𝐈𝐎𝐍𝐄 𝐀𝐋𝐂𝐎𝐎𝐋 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀",
            description="*Le botti fumano, il alambicco bolle...*",
            color=discord.Color(0xC8860A),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b", value="╔══════════════════╗", inline=False)
        embed.add_field(name="👨‍🏭 Distillatore",  value=member.mention,                   inline=True)
        embed.add_field(name="🥃 Prodotto",        value=f"**{alcool}**",                  inline=True)
        embed.add_field(name="\u200b",              value="╠══════════════════╣",           inline=False)
        embed.add_field(name="🕐 Inizio Produzione", value=f"<t:{int(now.timestamp())}:T>  (<t:{int(now.timestamp())}:R>)", inline=False)
        embed.add_field(name="\u200b",              value="╚══════════════════╝",           inline=False)
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
                "❌ Non hai nessuna creazione in corso. Usa `/inizio-creazione-alcool` prima.", ephemeral=True)
            return

        sessione = _creazioni_attive[uid]
        alcool   = sessione["alcool"]

        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _creazioni_attive[uid]

        embed = discord.Embed(
            title="✅ 𝐂𝐑𝐄𝐀𝐙𝐈𝐎𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀",
            description="*La partita è pronta. L'odore si diffonde per la distilleria.*",
            color=discord.Color(0x27AE60),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b",                value="╔══════════════════╗",                              inline=False)
        embed.add_field(name="👨‍🏭 Distillatore",       value=interaction.user.mention,                           inline=True)
        embed.add_field(name="🥃 Prodotto",            value=f"**{alcool}**",                                    inline=True)
        embed.add_field(name="\u200b",                 value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="🕐 Inizio",              value=f"<t:{int(inizio.timestamp())}:T>",                 inline=True)
        embed.add_field(name="🕑 Fine",                value=f"<t:{int(now.timestamp())}:T>",                    inline=True)
        embed.add_field(name="\u200b",                 value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="⏱️ Tempo di Produzione", value=f"```{_durata_str(durata_s)}```",                   inline=False)
        embed.add_field(name="\u200b",                 value="╚══════════════════╝",                             inline=False)
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
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True)
            return

        if not isinstance(member, discord.Member) or \
           not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True)
            return

        if uid in _distillazioni_attive:
            d = _distillazioni_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una distillazione di **{d['alcool']}** in corso!\nUsa `/fine-distillazione` prima.",
                ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        _distillazioni_attive[uid] = {"alcool": alcool, "inizio": now}

        embed = discord.Embed(
            title="🔥 𝐃𝐈𝐒𝐓𝐈𝐋𝐋𝐀𝐙𝐈𝐎𝐍𝐄 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀",
            description="*Il fuoco arde sotto l'alambicco. Il liquido scorre lentamente...*",
            color=discord.Color(0xE74C3C),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="\u200b",               value="╔══════════════════╗",                              inline=False)
        embed.add_field(name="👨‍🏭 Distillatore",     value=member.mention,                                      inline=True)
        embed.add_field(name="🔬 Distillato",         value=f"**{alcool}**",                                    inline=True)
        embed.add_field(name="\u200b",                value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="🕐 Inizio Distillazione", value=f"<t:{int(now.timestamp())}:T>  (<t:{int(now.timestamp())}:R>)", inline=False)
        embed.add_field(name="\u200b",                value="╚══════════════════╝",                             inline=False)
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
                "❌ Non hai nessuna distillazione in corso. Usa `/inizio-distillazione` prima.", ephemeral=True)
            return

        sessione = _distillazioni_attive[uid]
        alcool   = sessione["alcool"]

        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _distillazioni_attive[uid]

        embed = discord.Embed(
            title="✅ 𝐃𝐈𝐒𝐓𝐈𝐋𝐋𝐀𝐙𝐈𝐎𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀",
            description="*L'alambicco si raffredda. Il distillato è pronto per essere imbottigliato.*",
            color=discord.Color(0x8E44AD),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="\u200b",                  value="╔══════════════════╗",                              inline=False)
        embed.add_field(name="👨‍🏭 Distillatore",         value=interaction.user.mention,                           inline=True)
        embed.add_field(name="🔬 Distillato",            value=f"**{alcool}**",                                    inline=True)
        embed.add_field(name="\u200b",                   value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="🕐 Inizio",                value=f"<t:{int(inizio.timestamp())}:T>",                 inline=True)
        embed.add_field(name="🕑 Fine",                  value=f"<t:{int(now.timestamp())}:T>",                    inline=True)
        embed.add_field(name="\u200b",                   value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="⏱️ Durata Distillazione",  value=f"```{_durata_str(durata_s)}```",                   inline=False)
        embed.add_field(name="\u200b",                   value="╚══════════════════╝",                             inline=False)
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
            await interaction.response.send_message("❌ Allega un'immagine valida (jpg, png...).", ephemeral=True)
            return

        if not isinstance(member, discord.Member) or            not any(r.id == DISTILL_ROLE_ID for r in member.roles):
            await interaction.response.send_message(
                "❌ Solo i **Distillatori** possono usare questo comando.", ephemeral=True)
            return

        if uid in _vendite_moonshine_attive:
            await interaction.response.send_message(
                "❌ Hai già una vendita di **🌙 Moonshine** in corso!\nUsa `/fine-vendita-moonshine` prima.",
                ephemeral=True)
            return

        now = datetime.now(timezone.utc)
        _vendite_moonshine_attive[uid] = {"inizio": now}

        embed = discord.Embed(
            title="🌙 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐌𝐎𝐎𝐍𝐒𝐇𝐈𝐍𝐄 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀",
            description="*Il contrabbandiere carica i barili sul carro...*",
            color=discord.Color(0x4B0082),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="​",              value="╔══════════════════╗",                              inline=False)
        embed.add_field(name="👨‍🏭 Distillatore",    value=member.mention,                                      inline=True)
        embed.add_field(name="🌙 Prodotto",          value="**🌙 Moonshine**",                                  inline=True)
        embed.add_field(name="​",               value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="🕐 Inizio Vendita",    value=f"<t:{int(now.timestamp())}:T>  (<t:{int(now.timestamp())}:R>)", inline=False)
        embed.add_field(name="​",               value="╚══════════════════╝",                             inline=False)
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
                "❌ Non hai nessuna vendita Moonshine in corso. Usa `/inizio-vendita-moonshine` prima.", ephemeral=True)
            return

        sessione = _vendite_moonshine_attive[uid]
        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        del _vendite_moonshine_attive[uid]

        embed = discord.Embed(
            title="✅ 𝐕𝐄𝐍𝐃𝐈𝐓𝐀 𝐌𝐎𝐎𝐍𝐒𝐇𝐈𝐍𝐄 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀",
            description="*I barili sono stati consegnati. L'oro scorre nelle tasche...*",
            color=discord.Color(0x9B59B6),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="​",                value="╔══════════════════╗",                              inline=False)
        embed.add_field(name="👨‍🏭 Distillatore",       value=interaction.user.mention,                           inline=True)
        embed.add_field(name="🌙 Prodotto",             value="**🌙 Moonshine**",                                  inline=True)
        embed.add_field(name="​",                  value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="🕐 Inizio",               value=f"<t:{int(inizio.timestamp())}:T>",                 inline=True)
        embed.add_field(name="🕑 Fine",                 value=f"<t:{int(now.timestamp())}:T>",                    inline=True)
        embed.add_field(name="​",                  value="╠══════════════════╣",                             inline=False)
        embed.add_field(name="⏱️ Durata Vendita",       value=f"```{_durata_str(durata_s)}```",                   inline=False)
        embed.add_field(name="​",                  value="╚══════════════════╝",                             inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Distilleria | Vendita Completata")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass
