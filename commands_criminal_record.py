import discord
from discord import app_commands
import database
from constants import has_sceriffo

def setup_criminal_record_commands(bot):

    @bot.tree.command(name="miafedinapenale", description="Visualizza la tua fedina penale")
    async def mia_fedina(interaction: discord.Interaction):
        records = await database.get_criminal_records(str(interaction.user.id))
        embed = discord.Embed(title=f"⚖️ 𝐅𝐞𝐝𝐢𝐧𝐚 𝐏𝐞𝐧𝐚𝐥𝐞 𝐝𝐢 {interaction.user.mention}",
                              color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if not records:
            embed.description = "✅ *Nessun crimine registrato. Sei un uomo onesto, cowboy.*"
        else:
            for r in records[:8]:
                embed.add_field(name=f"⚖️ {r['crime']}",
                                value=f"🔒 {r['sentence']}\n👮 {r['officer']}\n📅 {r['created_at']}", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fedina Penale")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="puliziafedinapenale", description="[FDO] Pulisci la fedina penale di un cittadino")
    @app_commands.describe(cittadino="Il cittadino")
    async def pulisci_fedina(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo.", ephemeral=True); return
        await database.clear_criminal_record(str(cittadino.id))
        embed = discord.Embed(title="✅ 𝐅𝐞𝐝𝐢𝐧𝐚 𝐏𝐞𝐧𝐚𝐥𝐞 𝐏𝐮𝐥𝐢𝐭𝐚", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Cittadino", value=cittadino.mention,        inline=True)
        embed.add_field(name="⭐ Sceriffo",  value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed)
        try: await cittadino.send(embed=discord.Embed(
            title="✅ 𝐅𝐞𝐝𝐢𝐧𝐚 𝐏𝐞𝐧𝐚𝐥𝐞 𝐏𝐮𝐥𝐢𝐭𝐚",
            description="La tua fedina penale è stata pulita. Sei libero da ogni accusa.",
            color=discord.Color.green()))
        except Exception: pass
