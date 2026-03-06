import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_sceriffo

def setup_arrest_commands(bot):

    @bot.tree.command(name="ammanetto", description="[Sceriffo] Ammanetta un sospettato")
    @app_commands.describe(sospettato="Il sospettato", motivo="Motivo dell'arresto")
    async def ammanetto(interaction: discord.Interaction, sospettato: discord.Member, motivo: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può ammanettare.", ephemeral=True); return
        embed = discord.Embed(title="<a:manette:1431626831076921507> 𝐀𝐌𝐌𝐀𝐍𝐄𝐓𝐓𝐀𝐓𝐎", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=sospettato.display_avatar.url)
        embed.add_field(name="🤠 Sospettato", value=sospettato.mention,        inline=True)
        embed.add_field(name="📋 Motivo",     value=motivo,                    inline=False)
        embed.add_field(name="⭐ Sceriffo",   value=interaction.user.mention,  inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed)
        try: await sospettato.send(embed=discord.Embed(
            title="<a:manette:1431626831076921507> 𝐒𝐞𝐢 𝐬𝐭𝐚𝐭𝐨 𝐚𝐦𝐦𝐚𝐧𝐞𝐭𝐭𝐚𝐭𝐨!",
            description=f"Lo Sceriffo **{interaction.user.display_name}** ti ha fermato.\n**Motivo:** {motivo}",
            color=discord.Color.red()))
        except Exception: pass

    @bot.tree.command(name="modulo-arresto", description="[Sceriffo] Compila un modulo di arresto ufficiale")
    @app_commands.describe(criminale="Il criminale", crimine="Il crimine", pena="La pena")
    async def modulo_arresto(interaction: discord.Interaction, criminale: discord.Member, crimine: str, pena: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo.", ephemeral=True); return
        await database.add_arrest(str(criminale.id), crimine, pena, interaction.user.display_name)
        await database.add_criminal_record(str(criminale.id), crimine, pena, interaction.user.display_name)
        embed = discord.Embed(title="📋 𝐌𝐎𝐃𝐔𝐋𝐎 𝐃𝐈 𝐀𝐑𝐑𝐄𝐒𝐓𝐎", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=criminale.display_avatar.url)
        embed.add_field(name="🤠 Criminale", value=criminale.mention,         inline=True)
        embed.add_field(name="⚖️ Crimine",   value=crimine,                   inline=False)
        embed.add_field(name="🔒 Pena",      value=pena,                      inline=False)
        embed.add_field(name="⭐ Sceriffo",  value=interaction.user.mention,  inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="denuncia", description="Compila una denuncia contro un individuo")
    @app_commands.describe(accusato="La persona accusata", accusa="Descrizione dell'accusa")
    async def denuncia(interaction: discord.Interaction, accusato: discord.Member, accusa: str):
        embed = discord.Embed(title="📜 𝐃𝐄𝐍𝐔𝐍𝐂𝐈𝐀 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄", color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Denunciante", value=interaction.user.mention, inline=True)
        embed.add_field(name="😠 Accusato",    value=accusato.mention,         inline=True)
        embed.add_field(name="📋 Accusa",      value=accusa,                   inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass
