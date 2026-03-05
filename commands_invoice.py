import discord
from discord import app_commands
import database
from datetime import datetime

LOG_CHANNEL_ID = 1415297578022604850

def setup_invoice_commands(bot):

    @bot.tree.command(name="fattura", description="Emetti una fattura per un servizio nel Far West")
    @app_commands.describe(
        destinatario="Il giocatore a cui mandare la fattura",
        importo="Importo in dollari",
        descrizione="Servizio o bene fornito"
    )
    async def fattura(interaction: discord.Interaction, destinatario: discord.Member, importo: int, descrizione: str):
        if destinatario.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi emettere una fattura a te stesso.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        invoice_id = await database.add_invoice(
            str(interaction.user.id), str(destinatario.id), importo, descrizione
        )

        embed = discord.Embed(
            title="📜 FATTURA EMESSA",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🧾 N° Fattura",   value=f"#{invoice_id}",          inline=True)
        embed.add_field(name="💵 Importo",       value=f"${importo:,}",           inline=True)
        embed.add_field(name="📋 Servizio",      value=descrizione,               inline=False)
        embed.add_field(name="👤 Emessa da",     value=interaction.user.mention,  inline=True)
        embed.add_field(name="🎯 Destinatario",  value=destinatario.mention,      inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fattura | Usa /pagafattura per pagare")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="📜 Hai ricevuto una fattura!",
                description=(
                    f"**{interaction.user.display_name}** ti ha inviato una fattura di **${importo:,}**.\n\n"
                    f"**Servizio:** {descrizione}\n"
                    f"Usa `/pagafattura` con il numero **#{invoice_id}** per pagare."
                ),
                color=discord.Color(0xDAA520)
            )
            await destinatario.send(embed=dm)
        except Exception:
            pass

    @bot.tree.command(name="pagafattura", description="Paga una fattura ricevuta")
    @app_commands.describe(numero_fattura="Il numero della fattura da pagare")
    async def paga_fattura(interaction: discord.Interaction, numero_fattura: int):
        invoice = await database.get_invoice(numero_fattura)

        if not invoice:
            await interaction.response.send_message("❌ Fattura non trovata.", ephemeral=True)
            return
        if invoice["to_user"] != str(interaction.user.id):
            await interaction.response.send_message("❌ Questa fattura non è intestata a te.", ephemeral=True)
            return
        if invoice["paid"]:
            await interaction.response.send_message("❌ Questa fattura è già stata pagata.", ephemeral=True)
            return

        user = await database.get_user(str(interaction.user.id))
        if user["cash"] < invoice["amount"]:
            await interaction.response.send_message(
                f"❌ Non hai abbastanza contanti. (Necessari: ${invoice['amount']:,} — Tuoi: ${user['cash']:,})",
                ephemeral=True
            )
            return

        await database.update_balance(str(interaction.user.id), cash=user["cash"] - invoice["amount"])
        emitter = await database.get_user(invoice["from_user"])
        await database.update_balance(invoice["from_user"], cash=emitter["cash"] + invoice["amount"])
        await database.pay_invoice(numero_fattura)

        embed = discord.Embed(
            title="✅ Fattura Pagata",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🧾 N° Fattura",  value=f"#{numero_fattura}",           inline=True)
        embed.add_field(name="💵 Importo",      value=f"${invoice['amount']:,}",      inline=True)
        embed.add_field(name="📋 Servizio",     value=invoice["description"],         inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fattura")
        await interaction.response.send_message(embed=embed)
