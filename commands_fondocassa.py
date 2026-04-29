import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_staff, COMPANY_ROLES

COMPANY_EMOJI = {
    "Sceriffo":     "🤠",
    "Dottore":      "🩺",
    "Armiere":      "🔫",
    "Stalla":       "🐎",
    "Saloon":       "🍻",
    "Emporio":      "🏪",
    "Contrabbando": "🚫",
    "Diligenza":    "🚂",
    "Stato":        "🏛️",
    "Banchiere":    "🏦",
    "Distilleria":  "🥃",
    "Macelleria":   "🥩",
    "Fight Club":   "🥊",
}

_CHOICES = [
    app_commands.Choice(name="⭐ Sceriffo",     value="Sceriffo"),
    app_commands.Choice(name="🩺 Dottore",      value="Dottore"),
    app_commands.Choice(name="🔫 Armiere",      value="Armiere"),
    app_commands.Choice(name="🐴 Stalla",       value="Stalla"),
    app_commands.Choice(name="🍺 Saloon",       value="Saloon"),
    app_commands.Choice(name="🏪 Emporio",      value="Emporio"),
    app_commands.Choice(name="🚫 Contrabbando", value="Contrabbando"),
    app_commands.Choice(name="🚂 Diligenza",    value="Diligenza"),
    app_commands.Choice(name="🏛️ Stato",        value="Stato"),
    app_commands.Choice(name="🏦 Banca",        value="Banchiere"),
    app_commands.Choice(name="🥃 Distilleria",  value="Distilleria"),
    app_commands.Choice(name="🥩 Macelleria",   value="Macelleria"),
    app_commands.Choice(name="🥊 Fight Club",   value="FightClub"),
]


def _get_user_companies(member) -> list:
    result = []
    for company, role_id in COMPANY_ROLES.items():
        if isinstance(role_id, list):
            if any(r.id in role_id for r in member.roles):
                result.append(company)
        elif any(r.id == role_id for r in member.roles):
            result.append(company)
    return result


def setup_fondocassa_commands(bot):

    # ── /fondocassa ───────────────────────────────────────────────────────────
    @bot.tree.command(name="fondocassa", description="Visualizza il fondo cassa della tua compagnia")
    @app_commands.describe(compagnia="Seleziona la tua compagnia")
    @app_commands.choices(compagnia=_CHOICES)
    async def fondocassa(interaction: discord.Interaction, compagnia: str):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if compagnia not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte della compagnia **{compagnia}**.", ephemeral=True); return

        amount = await database.get_fondocassa(compagnia)
        emoji  = COMPANY_EMOJI.get(compagnia, "🏢")
        embed  = discord.Embed(
            title=f"💶 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {compagnia}",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name=f"{emoji} Saldo attuale", value=f"**${amount:,}**", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /deposita-fondocassa ──────────────────────────────────────────────────
    @bot.tree.command(name="deposita-fondocassa", description="Deposita contanti nel fondo cassa della tua compagnia")
    @app_commands.describe(compagnia="La compagnia", importo="Importo da depositare")
    @app_commands.choices(compagnia=_CHOICES)
    async def deposita_fondocassa(interaction: discord.Interaction, compagnia: str, importo: int):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if compagnia not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte della compagnia **{compagnia}**.", ephemeral=True); return

        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return

        user = await database.get_user(str(interaction.user.id))
        if user["cash"] < importo:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti. Disponibili: **${user['cash']:,}**", ephemeral=True); return

        await database.update_balance(str(interaction.user.id), cash=user["cash"] - importo)
        current = await database.get_fondocassa(compagnia)
        await database.update_fondocassa(compagnia, current + importo)

        emoji = COMPANY_EMOJI.get(compagnia, "🏢")
        embed = discord.Embed(
            title=f"💰 𝐃𝐞𝐩𝐨𝐬𝐢𝐭𝐨 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {compagnia}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{emoji} Compagnia", value=compagnia,               inline=True)
        embed.add_field(name="💵 Depositato",      value=f"${importo:,}",         inline=True)
        embed.add_field(name="💼 Nuovo saldo FC",  value=f"${current+importo:,}", inline=True)
        embed.add_field(name="👤 Da",              value=interaction.user.mention, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── /preleva-fondocassa ───────────────────────────────────────────────────
    @bot.tree.command(name="preleva-fondocassa", description="Preleva dal fondo cassa della tua compagnia")
    @app_commands.describe(compagnia="La compagnia", importo="Importo da prelevare", motivazione="Motivazione (opzionale)")
    @app_commands.choices(compagnia=_CHOICES)
    async def preleva_fondocassa(interaction: discord.Interaction, compagnia: str, importo: int, motivazione: str = ""):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if compagnia not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte della compagnia **{compagnia}**.", ephemeral=True); return

        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return

        current = await database.get_fondocassa(compagnia)
        if current < importo:
            await interaction.response.send_message(
                f"❌ Fondi insufficienti. Disponibili: **${current:,}**", ephemeral=True); return

        await database.update_fondocassa(compagnia, current - importo)
        user = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(interaction.user.id), cash=user["cash"] + importo)

        emoji = COMPANY_EMOJI.get(compagnia, "🏢")
        embed = discord.Embed(
            title=f"💸 𝐏𝐫𝐞𝐥𝐢𝐞𝐯𝐨 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {compagnia}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{emoji} Compagnia",  value=compagnia,               inline=True)
        embed.add_field(name="💵 Prelevato",        value=f"${importo:,}",         inline=True)
        embed.add_field(name="💼 Saldo FC rimasto", value=f"${current-importo:,}", inline=True)
        embed.add_field(name="👤 Da",               value=interaction.user.mention, inline=False)
        if motivazione:
            embed.add_field(name="📋 Motivazione",  value=motivazione,              inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── /saldo-fondocassa ─────────────────────────────────────────────────────
    @bot.tree.command(name="saldo-fondocassa", description="[Staff] Visualizza il saldo di tutti i fondi cassa")
    async def saldo_fondocassa(interaction: discord.Interaction):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Solo lo Staff può vedere tutti i fondi cassa.", ephemeral=True); return
        embed = discord.Embed(
            title="💼 𝐒𝐚𝐥𝐝𝐨 𝐅𝐨𝐧𝐝𝐢 𝐂𝐚𝐬𝐬𝐚 — 𝐓𝐮𝐭𝐭𝐞 𝐥𝐞 𝐂𝐨𝐦𝐩𝐚𝐠𝐧𝐢𝐞",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        totale = 0
        for company, emoji in COMPANY_EMOJI.items():
            amount = await database.get_fondocassa(company)
            totale += amount
            embed.add_field(name=f"{emoji} {company}", value=f"**${amount:,}**", inline=True)
        embed.add_field(name="💰 Totale Generale", value=f"**${totale:,}**", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed, ephemeral=True)
