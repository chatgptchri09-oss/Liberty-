import discord
from discord import app_commands
import database
from datetime import datetime

SCERIFFO_ROLES = 1404051916140449885

def has_sceriffo(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in SCERIFFO_ROLES for r in interaction.user.roles)

def setup_criminal_record_commands(bot):

    @bot.tree.command(name="miafedinapenale", description="Visualizza la tua fedina penale")
    async def mia_fedina(interaction: discord.Interaction):
        records = await database.get_criminal_records(str(interaction.user.id))
        embed = discord.Embed(
            title=f"⚖️ Fedina Penale di {interaction.user.mention}",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if not records:
            embed.description = "✅ *Nessun crimine registrato. Sei pulito, cowboy.*"
        else:
            for r in records[-10:]:  # mostra ultimi 10
                embed.add_field(
                    name=f"⚖️ {r['crime']}",
                    value=f"🔒 Pena: {r['sentence']}\n👮 Sceriffo: {r['officer']}\n📅 {r['created_at']}",
                    inline=False
                )
        embed.set_footer(text="🤠 Red Dead Redemption II — Fedina Penale")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="puliziafedinapenale", description="[Sceriffo] Pulisci la fedina penale di un cittadino")
    @app_commands.describe(cittadino="Il cittadino")
    async def pulisci_fedina(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può pulire la fedina penale.", ephemeral=True)
            return

        await database.clear_criminal_record(str(cittadino.id))

        embed = discord.Embed(
            title="✅ Fedina Penale Pulita",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Cittadino", value=cittadino.mention,       inline=True)
        embed.add_field(name="⭐ Sceriffo",  value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="✅ Fedina Penale Pulita",
                description="La tua fedina penale è stata pulita dallo Sceriffo. Sei libero da ogni accusa.",
                color=discord.Color.green()
            )
            await cittadino.send(embed=dm)
        except Exception:
            pass
