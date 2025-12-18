import discord
from discord import app_commands
from discord.ext import commands
import database
from datetime import datetime

COMPANY_ROLES = {
    "EMS": 1415239481757536256,
    "Armeria": 1415092383250382858,
    "Concessionario": 1415238213303406702,
    "Market": 1415242295153918123,
    "Officina": 1415240071216500746,
    "Import/Export": 1424004700608401428,
    "L.F.D": 1415093546549248040,
    "Pegasus Airlines": 1415262517407645828,
    "Dinasty 8": 1424381004944244828,
}

COMPANY_LOG_CHANNELS = {
    "EMS": 1424111086537281567,
    "Armeria": 1424111403228205147,
    "Concessionario": 1424111522107490405,
    "Market": 1424111628374511729,
    "Officina": 1424111759559495760,
    "Import/Export": 1424111925360463882,
    "Pegasus Airlines": 1424112194139984003,
    "L.F.D": 1424007218554208316,
    "Dinasty 8": 1451256740950573127,
}

LOG_CHANNEL_ID = 1415297578022604850

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass

def setup_invoice_commands(bot: commands.Bot):
    
    @bot.tree.command(name="fattura", description="[DIPENDENTI] Invia una fattura a un cliente")
    @app_commands.describe(
        cliente="Il cliente a cui inviare la fattura",
        descrizione="Descrizione della fattura",
        prezzo="Prezzo della fattura",
        azienda="Seleziona l'azienda"
    )
    @app_commands.choices(azienda=[
        app_commands.Choice(name="EMS", value="EMS"),
        app_commands.Choice(name="Armeria", value="Armeria"),
        app_commands.Choice(name="Concessionario", value="Concessionario"),
        app_commands.Choice(name="Market", value="Market"),
        app_commands.Choice(name="Officina", value="Officina"),
        app_commands.Choice(name="Import/Export", value="Import/Export"),
        app_commands.Choice(name="L.F.D", value="L.F.D"),
        app_commands.Choice(name="Pegasus Airlines", value="Pegasus Airlines"),
        app_commands.Choice(name="Dinasty 8", value="Dinasty 8"),
    ])
    async def fattura(interaction: discord.Interaction, cliente: discord.Member, descrizione: str, prezzo: int, azienda: str):
        if not has_role(interaction, COMPANY_ROLES[azienda]):
            await interaction.response.send_message("<a:annulla:1431940396635652146> Non hai il permesso di creare fatture per questa azienda!", ephemeral=True)
            return
        
        if prezzo <= 0:
            await interaction.response.send_message("<a:annulla:1431940396635652146> Il prezzo deve essere maggiore di 0!", ephemeral=True)
            return
        
        await database.create_invoice(str(cliente.id), str(interaction.user.id), descrizione, prezzo, azienda)
        
        embed = discord.Embed(
            title="<a:fattura:1432112195004796937> FATTURA RICEVUTA",
            color=discord.Color.orange()
        )
        embed.add_field(name="👤 Da", value=interaction.user.mention, inline=False)
        embed.add_field(name="📝 Descrizione", value=descrizione, inline=False)
        embed.add_field(name="💰 Prezzo", value=f"${prezzo:,}", inline=False)
        embed.add_field(name="🏢 Azienda", value=azienda, inline=False)
        
        try:
            await cliente.send(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(f"<a:spunta:1431937738256552036> Fattura inviata a {cliente.mention}!", ephemeral=True)
        
        # LOG CON EMBED
        log_embed = discord.Embed(
            title="📄 LOG FATTURA EMESSA",
            color=discord.Color.orange()
        )
        log_embed.add_field(name="👨‍💼 Dipendente", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Cliente", value=cliente.mention, inline=True)
        log_embed.add_field(name="🏢 Azienda", value=azienda, inline=False)
        log_embed.add_field(name="📝 Descrizione", value=descrizione[:1024], inline=False)
        log_embed.add_field(name="💰 Importo", value=f"${prezzo:,}", inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
    
    class InvoiceSelectMenu(discord.ui.Select):
        def __init__(self, invoices, user_id):
            self.user_id = user_id
            self.invoice_map = {}
            options = []
            
            for invoice in invoices:
                invoice_id, sender_id, description, price, company = invoice
                self.invoice_map[str(invoice_id)] = invoice
                options.append(
                    discord.SelectOption(
                        label=f"{company} - ${price:,}",
                        description=description[:100],
                        value=str(invoice_id)
                    )
                )
            
            super().__init__(placeholder="Seleziona una fattura da pagare", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Questo non è il tuo menu!", ephemeral=True)
                return
            
            invoice_id = int(self.values[0])
            invoice = await database.get_invoice(invoice_id)
            
            if not invoice:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Fattura non trovata!", ephemeral=True)
                return
            
            _, client_id, sender_id, description, price, company, paid, _ = invoice
            
            if paid:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Questa fattura è già stata pagata!", ephemeral=True)
                return
            
            user = await database.get_user(client_id)
            total = user["cash"] + user["bank"]
            
            if total < price:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Non hai abbastanza soldi per pagare questa fattura!", ephemeral=True)
                return
            
            new_cash = user["cash"]
            new_bank = user["bank"]
            remaining = price
            
            if new_bank >= remaining:
                new_bank -= remaining
            else:
                remaining -= new_bank
                new_bank = 0
                new_cash -= remaining
            
            await database.update_balance(client_id, cash=new_cash, bank=new_bank)
            await database.pay_invoice(invoice_id)
            
            employee_cut = int(price * 0.25)
            sender = await database.get_user(sender_id)
            await database.update_balance(sender_id, bank=sender["bank"] + employee_cut)
            
            try:
                sender_user = await bot.fetch_user(int(sender_id))
                await sender_user.send(f"<a:spunta:1431937738256552036> Hai ricevuto il 25% della fattura: **${employee_cut:,}**")
            except:
                pass
            
            log_channel_id = COMPANY_LOG_CHANNELS.get(company)
            if log_channel_id:
                log_embed = discord.Embed(
                    title="💰 FATTURA PAGATA",
                    color=discord.Color.green()
                )
                log_embed.add_field(name="👤 Cliente", value=f"<@{client_id}>", inline=False)
                log_embed.add_field(name="👨‍💼 Dipendente", value=f"<@{sender_id}>", inline=False)
                log_embed.add_field(name="📝 Descrizione", value=description, inline=False)
                log_embed.add_field(name="💰 Prezzo", value=f"${price:,}", inline=False)
                log_embed.add_field(name="💵 Guadagno Dipendente (25%)", value=f"${employee_cut:,}", inline=False)
                log_embed.timestamp = datetime.now()
                
                await log_command(bot, log_channel_id, embed=log_embed)
            
            await interaction.response.send_message(f"<a:spunta:1431937738256552036> Hai pagato la fattura di **${price:,}**!", ephemeral=True)
            
            # LOG GENERALE CON EMBED
            log_embed_general = discord.Embed(
                title="💳 LOG FATTURA PAGATA",
                color=discord.Color.green()
            )
            log_embed_general.add_field(name="👤 Pagata da", value=f"<@{client_id}>", inline=True)
            log_embed_general.add_field(name="👨‍💼 Dipendente", value=f"<@{sender_id}>", inline=True)
            log_embed_general.add_field(name="🏢 Azienda", value=company, inline=False)
            log_embed_general.add_field(name="💰 Importo Totale", value=f"${price:,}", inline=True)
            log_embed_general.add_field(name="💵 Guadagno Dipendente", value=f"${employee_cut:,}", inline=True)
            log_embed_general.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=log_embed_general)
    
    @bot.tree.command(name="pagafattura", description="Paga una fattura ricevuta")
    async def pagafattura(interaction: discord.Interaction):
        invoices = await database.get_unpaid_invoices(str(interaction.user.id))
        
        if not invoices:
            await interaction.response.send_message("<a:annulla:1431940396635652146> Non hai fatture da pagare!", ephemeral=True)
            return
        
        view = discord.ui.View()
        view.add_item(InvoiceSelectMenu(invoices, str(interaction.user.id)))
        
        await interaction.response.send_message("📄 Seleziona una fattura da pagare:", view=view, ephemeral=True)
