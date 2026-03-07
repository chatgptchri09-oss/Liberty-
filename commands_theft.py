import discord
from discord import app_commands
from datetime import datetime, timezone
import database
from constants import LOG_CHANNEL_ID

# ── Ruoli richiesti per tipo di droga ────────────────────────────────────────
DROGA_CONFIG = {
    "🍃 Tabacco":             1421166296850235602,
    "🍁 Canapa":              1421166461988114532,
    "🌿 Foglie di Cocaina":   1421166604447776780,
    "💉 Eroina":              1404052027570524181,
}

ITEM_FORBICI = "✂️ • Forbici per raccolta droga"

# Sessioni attive in memoria: user_id → {droga, inizio}
_raccolte_attive: dict = {}


def _durata_str(secondi: float) -> str:
    h = int(secondi // 3600)
    m = int((secondi % 3600) // 60)
    s = int(secondi % 60)
    if h > 0:
        return f"{h}h {m}min {s}s"
    elif m > 0:
        return f"{m}min {s}s"
    return f"{s}s"


def setup_theft_commands(bot):

    # ── /inizio-raccolta ─────────────────────────────────────────────────────
    @bot.tree.command(name="inizio-raccolta", description="Inizia una sessione di raccolta droga")
    @app_commands.describe(
        droga="Tipo di droga da raccogliere",
        foto="Foto della sessione (OBBLIGATORIA — allega un'immagine)"
    )
    @app_commands.choices(droga=[
        app_commands.Choice(name="🍃 Tabacco",           value="🍃 Tabacco"),
        app_commands.Choice(name="🍁 Canapa",             value="🍁 Canapa"),
        app_commands.Choice(name="🌿 Foglie di Cocaina",  value="🌿 Foglie di Cocaina"),
        app_commands.Choice(name="💉 Eroina",             value="💉 Eroina"),
    ])
    async def inizio_raccolta(
        interaction: discord.Interaction,
        droga: str,
        foto: discord.Attachment
    ):
        uid    = str(interaction.user.id)
        member = interaction.user

        # Controlla immagine
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message(
                "❌ Il file allegato non è un'immagine valida. Allega una foto (jpg, png...).",
                ephemeral=True
            )
            return

        # Controlla se ha già una raccolta attiva
        if uid in _raccolte_attive:
            r = _raccolte_attive[uid]
            await interaction.response.send_message(
                f"❌ Hai già una raccolta di **{r['droga']}** in corso! Usa `/fine-raccolta` prima.",
                ephemeral=True
            )
            return

        # Controlla ruolo richiesto
        ruolo_id = DROGA_CONFIG.get(droga)
        if ruolo_id is None:
            await interaction.response.send_message("❌ Tipo di droga non valido.", ephemeral=True)
            return

        if not isinstance(member, discord.Member) or \
           not any(r.id == ruolo_id for r in member.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per raccogliere **{droga}**.",
                ephemeral=True
            )
            return

        # Controlla forbici in bisaccia
        quantita_forbici = await database.get_item_quantity(uid, ITEM_FORBICI)
        if quantita_forbici < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{ITEM_FORBICI}** nella bisaccia! Non puoi raccogliere senza attrezzatura.",
                ephemeral=True
            )
            return

        # Registra inizio raccolta
        now = datetime.now(timezone.utc)
        _raccolte_attive[uid] = {
            "droga":  droga,
            "inizio": now,
        }

        embed = discord.Embed(
            title="🌱 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐈𝐍𝐈𝐙𝐈𝐀𝐓𝐀",
            color=discord.Color(0x2E8B57),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        embed.add_field(name="🤠 Raccoglitore", value=member.mention,                         inline=False)
        embed.add_field(name="🌿 Droga",         value=droga,                                  inline=True)
        embed.add_field(name="🕐 Inizio",        value=f"<t:{int(now.timestamp())}:t>",        inline=True)
        embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Raccolta • Usa /fine-raccolta per terminare")

        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ── /fine-raccolta ───────────────────────────────────────────────────────
    @bot.tree.command(name="fine-raccolta", description="Termina la sessione di raccolta droga e calcola il tempo")
    @app_commands.describe(droga="Tipo di droga che stavi raccogliendo")
    @app_commands.choices(droga=[
        app_commands.Choice(name="🍃 Tabacco",           value="🍃 Tabacco"),
        app_commands.Choice(name="🍁 Canapa",             value="🍁 Canapa"),
        app_commands.Choice(name="🌿 Foglie di Cocaina",  value="🌿 Foglie di Cocaina"),
        app_commands.Choice(name="💉 Eroina",             value="💉 Eroina"),
    ])
    async def fine_raccolta(
        interaction: discord.Interaction,
        droga: str
    ):
        uid = str(interaction.user.id)

        if uid not in _raccolte_attive:
            await interaction.response.send_message(
                "❌ Non hai nessuna raccolta attiva. Usa `/inizio-raccolta` prima.",
                ephemeral=True
            )
            return

        sessione = _raccolte_attive[uid]
        if sessione["droga"] != droga:
            await interaction.response.send_message(
                f"❌ La tua raccolta attiva è di **{sessione['droga']}**, non di **{droga}**.",
                ephemeral=True
            )
            return

        now      = datetime.now(timezone.utc)
        inizio   = sessione["inizio"]
        durata_s = (now - inizio).total_seconds()
        durata   = _durata_str(durata_s)

        del _raccolte_attive[uid]

        embed = discord.Embed(
            title="✅ 𝐑𝐀𝐂𝐂𝐎𝐋𝐓𝐀 𝐓𝐄𝐑𝐌𝐈𝐍𝐀𝐓𝐀",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Raccoglitore", value=interaction.user.mention,               inline=False)
        embed.add_field(name="🌿 Droga",         value=droga,                                  inline=True)
        embed.add_field(name="\u200b",            value="\u200b",                               inline=False)
        embed.add_field(name="🕐 Inizio",        value=f"<t:{int(inizio.timestamp())}:t>",    inline=True)
        embed.add_field(name="🕑 Fine",          value=f"<t:{int(now.timestamp())}:t>",       inline=True)
        embed.add_field(name="\u200b",            value="\u200b",                               inline=False)
        embed.add_field(name="⏱️ Tempo raccolto", value=f"**{durata}**",                       inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Raccolta Completata")

        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass
