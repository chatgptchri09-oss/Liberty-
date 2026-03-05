import discord
from discord import app_commands
import database
import random
from datetime import datetime

LOG_CHANNEL_ID = 1415297578022604850

def setup_robbery_commands(bot):

    @bot.tree.command(name="rapina", description="Tenta una rapina rischiosa nel Far West (azione illegale)")
    @app_commands.describe(bersaglio="Cosa o chi vuoi rapinare", luogo="Dove avviene la rapina")
    async def rapina(interaction: discord.Interaction, bersaglio: str, luogo: str):
        successo = random.random() < 0.55  # 55% di successo
        bottino  = random.randint(50, 500) if successo else 0

        if successo:
            user = await database.get_user(str(interaction.user.id))
            await database.update_balance(str(interaction.user.id), cash=user["cash"] + bottino)
            color = discord.Color(0x8B4513)
            titolo = "💰 Rapina Riuscita!"
            desc = (
                f"*{interaction.user.display_name} riesce a rapinare **{bersaglio}** a **{luogo}**!*\n\n"
                f"**Bottino ottenuto: ${bottino:,}**"
            )
        else:
            color = discord.Color.red()
            titolo = "❌ Rapina Fallita"
            desc = (
                f"*{interaction.user.display_name} tenta di rapinare **{bersaglio}** a **{luogo}**...*\n\n"
                f"*Qualcosa va storto. Ti dai alla fuga a mani vuote.*"
            )

        embed = discord.Embed(title=titolo, description=desc, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Crimine")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(
                    title="🚨 LOG RAPINA",
                    color=discord.Color.green() if successo else discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="👤 Giocatore", value=interaction.user.mention, inline=True)
                log.add_field(name="🎯 Bersaglio",  value=bersaglio,               inline=True)
                log.add_field(name="📍 Luogo",       value=luogo,                   inline=True)
                log.add_field(name="💰 Bottino",     value=f"${bottino:,}",         inline=True)
                log.add_field(name="✅ Esito",       value="Riuscita" if successo else "Fallita", inline=True)
                await ch.send(embed=log)
        except Exception:
            pass
