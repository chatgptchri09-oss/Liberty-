import discord
from discord import app_commands
from constants import has_staff, LOG_CHANNEL_ID

LAVORI_RDR2 = [
    app_commands.Choice(name="⭐ Sceriffo",           value="Sceriffo"),
    app_commands.Choice(name="🩺 Dottore",            value="Dottore"),
    app_commands.Choice(name="🔫 Armiere",            value="Armiere"),
    app_commands.Choice(name="🐴 Stalliere",          value="Stalliere"),
    app_commands.Choice(name="🍺 Barista del Saloon", value="Barista del Saloon"),
    app_commands.Choice(name="⛏️ Minatore",           value="Minatore"),
    app_commands.Choice(name="🚂 Capotreno",          value="Capotreno"),
    app_commands.Choice(name="🌾 Fattore",            value="Fattore"),
    app_commands.Choice(name="📰 Giornalista",        value="Giornalista"),
    app_commands.Choice(name="🏪 Commerciante",       value="Commerciante"),
]

def setup_bando_commands(bot):

    @bot.tree.command(name="bando", description="[Staff] Apri o chiudi un bando lavorativo")
    @app_commands.describe(lavoro="Il lavoro", stato="Aperto o chiuso", dettagli="Dettagli aggiuntivi (opzionale)")
    @app_commands.choices(
        lavoro=LAVORI_RDR2,
        stato=[
            app_commands.Choice(name="🟢 Aperto", value="aperto"),
            app_commands.Choice(name="🔴 Chiuso", value="chiuso"),
        ]
    )
    async def bando(interaction: discord.Interaction, lavoro: str, stato: str, dettagli: str = ""):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        color = discord.Color.green() if stato == "aperto" else discord.Color.red()
        if stato == "aperto":
            emoji_anim = "<a:online:1459627385702973572>"
            titolo     = f"{emoji_anim} BANDO {lavoro.upper()} APERTO"
        else:
            emoji_anim = "<a:offline:1459628872197738641>"
            titolo     = f"{emoji_anim} BANDO {lavoro.upper()} CHIUSO"
        embed = discord.Embed(title=titolo, color=color, timestamp=discord.utils.utcnow())
        embed.set_image(url="https://i.postimg.cc/qqfVKM9B/IMG-7648.gif")
        if dettagli:
            embed.add_field(name="📝 Dettagli", value=dettagli, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bando Lavorativo")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Bando pubblicato!", ephemeral=True)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="esito-bando", description="[Staff] Comunica l'esito di un bando lavorativo")
    @app_commands.describe(giocatore="Il candidato", lavoro="Il lavoro", esito="Esito", motivazione="Motivazione (opzionale)")
    @app_commands.choices(
        lavoro=LAVORI_RDR2,
        esito=[
            app_commands.Choice(name="✅ Assunto",   value="assunto"),
            app_commands.Choice(name="❌ Rifiutato", value="rifiutato"),
        ]
    )
    async def esito_bando(interaction: discord.Interaction, giocatore: discord.Member,
                          lavoro: str, esito: str, motivazione: str = ""):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        color = discord.Color.green() if esito == "assunto" else discord.Color.red()
        emoji = "✅" if esito == "assunto" else "❌"
        embed = discord.Embed(title=f"{𝐞𝐦𝐨𝐣𝐢} 𝐄𝐬𝐢𝐭𝐨 𝐁𝐚𝐧𝐝𝐨 — {𝐞𝐬𝐢𝐭𝐨.𝐜𝐚𝐩𝐢𝐭𝐚𝐥𝐢𝐳𝐞()}",
                              color=color, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="👤 Candidato",   value=giocatore.mention,        inline=True)
        embed.add_field(name="🤠 Lavoro",      value=lavoro,                   inline=True)
        embed.add_field(name="📋 Esito",       value=esito.capitalize(),       inline=True)
        if motivazione: embed.add_field(name="📝 Motivazione", value=motivazione, inline=False)
        embed.add_field(name="👮 Valutato da", value=interaction.user.mention, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bando Lavorativo")
        await interaction.response.send_message(embed=embed)
        try: await giocatore.send(embed=embed)
        except Exception: pass
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass
