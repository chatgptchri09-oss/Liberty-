import discord
from discord import app_commands
import database
from datetime import datetime

LOG_CHANNEL_ID = 1415297578022604850

SCERIFFO_ROLES = [1415093546549248040]  # ruoli polizia/sceriffo

def has_sceriffo(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in SCERIFFO_ROLES for r in interaction.user.roles)

def setup_fine_commands(bot):

    @bot.tree.command(name="taglia", description="[Sceriffo] Emetti una taglia su un fuorilegge")
    @app_commands.describe(
        fuorilegge="Il fuorilegge su cui emettere la taglia",
        importo="Valore della taglia in dollari",
        motivo="Motivazione della taglia"
    )
    async def taglia(interaction: discord.Interaction, fuorilegge: discord.Member, importo: int, motivo: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può emettere taglie.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        await database.add_fine(str(fuorilegge.id), importo, motivo, interaction.user.display_name)

        embed = discord.Embed(
            title="⭐ TAGLIA EMESSA",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=fuorilegge.display_avatar.url)
        embed.add_field(name="🤠 Fuorilegge",  value=fuorilegge.mention,         inline=True)
        embed.add_field(name="💰 Taglia",      value=f"${importo:,}",            inline=True)
        embed.add_field(name="📋 Motivazione", value=motivo,                     inline=False)
        embed.add_field(name="⭐ Sceriffo",    value=interaction.user.mention,   inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

        # Notifica al fuorilegge
        try:
            dm = discord.Embed(
                title="⭐ Hai una taglia sulla testa!",
                description=f"Lo Sceriffo **{interaction.user.display_name}** ha emesso una taglia di **${importo:,}** su di te.\n\n**Motivazione:** {motivo}",
                color=discord.Color.red()
            )
            await fuorilegge.send(embed=dm)
        except Exception:
            pass

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    @bot.tree.command(name="paga-taglia", description="Paga una taglia per liberarti dalla legge")
    async def paga_taglia(interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        fines   = await database.get_fines(user_id)

        if not fines:
            await interaction.response.send_message("✅ Non hai taglie attive, sei libero come il vento!", ephemeral=True)
            return

        totale = sum(f["amount"] for f in fines)
        user   = await database.get_user(user_id)

        if user["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Non hai abbastanza contanti per pagare tutte le taglie.\n"
                f"Totale: **${totale:,}** — Tuoi contanti: **${user['cash']:,}**",
                ephemeral=True
            )
            return

        await database.update_balance(user_id, cash=user["cash"] - totale)
        for f in fines:
            await database.pay_fine(f["id"])

        embed = discord.Embed(
            title="✅ Taglie Saldate",
            description=f"Hai pagato **${totale:,}** e sei tornato un uomo libero.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="controlla-taglia", description="[Sceriffo] Verifica le taglie di un fuorilegge")
    @app_commands.describe(giocatore="Il giocatore da controllare")
    async def controlla_taglia(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può controllare le taglie.", ephemeral=True)
            return

        fines = await database.get_fines(str(giocatore.id))
        embed = discord.Embed(
            title=f"⭐ Taglie di {giocatore.display_name}",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=giocatore.display_avatar.url)

        if not fines:
            embed.description = "✅ Nessuna taglia attiva."
        else:
            for f in fines:
                embed.add_field(
                    name=f"Taglia #{f['id']} — ${f['amount']:,}",
                    value=f"📋 {f['reason']}\n👮 Emessa da: {f['issued_by']}\n📅 {f['created_at']}",
                    inline=False
                )
            embed.add_field(name="💰 Totale", value=f"${sum(f['amount'] for f in fines):,}", inline=False)

        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed, ephemeral=True)
