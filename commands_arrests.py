import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_sceriffo


def setup_arrest_commands(bot):

    @bot.tree.command(name="ammanetto", description="[FDO] Ammanetta un sospettato")
    @app_commands.describe(sospettato="Il sospettato", motivo="Motivo dell'arresto")
    async def ammanetto(interaction: discord.Interaction, sospettato: discord.Member, motivo: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può ammanettare.", ephemeral=True)
            return

        embed = discord.Embed(
            title="<a:manette:1431626831076921507> 𝐀𝐌𝐌𝐀𝐍𝐄𝐓𝐓𝐀𝐓𝐎",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=sospettato.display_avatar.url)
        embed.add_field(name="🤠 Sospettato", value=sospettato.mention,       inline=True)
        embed.add_field(name="📋 Motivo",     value=motivo,                   inline=False)
        embed.add_field(name="⭐ Agente",   value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")

        await interaction.response.send_message(embed=embed)

        # DM al sospettato
        try:
            await sospettato.send(embed=discord.Embed(
                title="<a:manette:1431626831076921507> 𝐒𝐞𝐢 𝐬𝐭𝐚𝐭𝐨 𝐚𝐦𝐦𝐚𝐧𝐞𝐭𝐭𝐚𝐭𝐨!",
                description=f"L'agente **{interaction.user.mention}** ti ha fermato.\n**Motivo:** {motivo}",
                color=discord.Color.red()
            ))
        except Exception:
            pass

        # Log nel canale
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass
