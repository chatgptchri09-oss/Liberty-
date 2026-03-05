import discord
from discord import app_commands
import database
from datetime import datetime

LOG_CHANNEL_ID = 1415297578022604850
SCERIFFO_ROLES = [1415093546549248040]

def has_sceriffo(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in SCERIFFO_ROLES for r in interaction.user.roles)

def setup_arrest_commands(bot):

    @bot.tree.command(name="ammanetto", description="[Sceriffo] Ammanetta un sospettato")
    @app_commands.describe(sospettato="Il sospettato da ammanettare", motivo="Motivo dell'arresto")
    async def ammanetto(interaction: discord.Interaction, sospettato: discord.Member, motivo: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può ammanettare qualcuno.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⛓️ AMMANETTATO",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=sospettato.display_avatar.url)
        embed.add_field(name="🤠 Sospettato",  value=sospettato.mention,       inline=True)
        embed.add_field(name="📋 Motivo",      value=motivo,                   inline=False)
        embed.add_field(name="⭐ Sceriffo",    value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="⛓️ Sei stato ammanettato!",
                description=f"Lo Sceriffo **{interaction.user.display_name}** ti ha ammanettato.\n**Motivo:** {motivo}",
                color=discord.Color.red()
            )
            await sospettato.send(embed=dm)
        except Exception:
            pass

    @bot.tree.command(name="modulo-arresto", description="[Sceriffo] Compila un modulo di arresto ufficiale")
    @app_commands.describe(
        criminale="Il criminale arrestato",
        crimine="Il crimine commesso",
        pena="La pena (es: 30 min in prigione, $500 di taglia)"
    )
    async def modulo_arresto(interaction: discord.Interaction, criminale: discord.Member, crimine: str, pena: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può compilare moduli di arresto.", ephemeral=True)
            return

        await database.add_arrest(str(criminale.id), crimine, pena, interaction.user.display_name)
        await database.add_criminal_record(str(criminale.id), crimine, pena, interaction.user.display_name)

        embed = discord.Embed(
            title="📋 MODULO DI ARRESTO",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=criminale.display_avatar.url)
        embed.add_field(name="🤠 Criminale",   value=criminale.mention,        inline=True)
        embed.add_field(name="⚖️ Crimine",     value=crimine,                  inline=False)
        embed.add_field(name="🔒 Pena",        value=pena,                     inline=False)
        embed.add_field(name="⭐ Sceriffo",    value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    @bot.tree.command(name="denuncia", description="Compila una denuncia ufficiale contro un individuo")
    @app_commands.describe(
        accusato="La persona che stai denunciando",
        accusa="Descrivi cosa ha fatto",
    )
    async def denuncia(interaction: discord.Interaction, accusato: discord.Member, accusa: str):
        embed = discord.Embed(
            title="📜 DENUNCIA UFFICIALE",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Denunciante",  value=interaction.user.mention, inline=True)
        embed.add_field(name="😠 Accusato",     value=accusato.mention,         inline=True)
        embed.add_field(name="📋 Accusa",       value=accusa,                   inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass
