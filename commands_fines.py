import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_sceriffo

def setup_fine_commands(bot):

    @bot.tree.command(name="taglia", description="[Sceriffo] Emetti una taglia su un fuorilegge")
    @app_commands.describe(fuorilegge="Il fuorilegge", importo="Valore della taglia", motivo="Motivazione")
    async def taglia(interaction: discord.Interaction, fuorilegge: discord.Member, importo: int, motivo: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può emettere taglie.", ephemeral=True); return
        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return
        await database.add_fine(str(fuorilegge.id), importo, motivo, interaction.user.display_name)
        embed = discord.Embed(title="⭐ TAGLIA EMESSA", color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=fuorilegge.display_avatar.url)
        embed.add_field(name="🤠 Fuorilegge", value=fuorilegge.mention,        inline=True)
        embed.add_field(name="💰 Taglia",     value=f"${importo:,}",           inline=True)
        embed.add_field(name="📋 Motivo",     value=motivo,                    inline=False)
        embed.add_field(name="⭐ Sceriffo",   value=interaction.user.mention,  inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)
        try: await fuorilegge.send(embed=discord.Embed(
            title="⭐ Hai una taglia sulla testa!",
            description=f"Lo Sceriffo **{interaction.user.display_name}** ha messo una taglia di **${importo:,}** su di te.\n**Motivo:** {motivo}",
            color=discord.Color.red()))
        except Exception: pass
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    @bot.tree.command(name="paga-taglia", description="Paga le taglie sulla tua testa")
    async def paga_taglia(interaction: discord.Interaction):
        uid   = str(interaction.user.id)
        fines = await database.get_fines(uid)
        if not fines:
            await interaction.response.send_message("✅ Non hai taglie attive!", ephemeral=True); return
        totale = sum(f["amount"] for f in fines)
        user   = await database.get_user(uid)
        if user["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti.\nTotale taglie: **${totale:,}** — Tuoi: **${user['cash']:,}**", ephemeral=True); return
        await database.update_balance(uid, cash=user["cash"] - totale)
        for f in fines: await database.pay_fine(f["id"])
        embed = discord.Embed(title="✅ Taglie Saldate",
                              description=f"Hai pagato **${totale:,}**. Sei tornato un uomo libero.",
                              color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="controlla-taglia", description="[Sceriffo] Verifica le taglie di un giocatore")
    @app_commands.describe(giocatore="Il giocatore")
    async def controlla_taglia(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        fines = await database.get_fines(str(giocatore.id))
        embed = discord.Embed(title=f"⭐ Taglie di {giocatore.display_name}",
                              color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        if not fines:
            embed.description = "✅ Nessuna taglia attiva."
        else:
            for f in fines:
                embed.add_field(name=f"Taglia #{f['id']} — ${f['amount']:,}",
                                value=f"📋 {f['reason']}\n👮 {f['issued_by']}\n📅 {f['created_at']}", inline=False)
            embed.add_field(name="💰 Totale", value=f"${sum(f['amount'] for f in fines):,}", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed, ephemeral=True)
