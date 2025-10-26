import discord
from discord import app_commands
from discord.ext import commands
import database
from datetime import datetime

LFD_ROLE_ID = 1415093546549248040
LOG_CHANNEL_ID = 1415297578022604850
LFD_LOG_CHANNEL_ID = 1424007218554208316

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

class FineModal(discord.ui.Modal, title="<a:sirena:1431792628332101723> Multa"):
    name_input = discord.ui.TextInput(label="Nome", placeholder="Nome dell'arrestato", required=True)
    surname_input = discord.ui.TextInput(label="Cognome", placeholder="Cognome dell'arrestato", required=True)
    age_input = discord.ui.TextInput(label="Età", placeholder="Età", required=True, max_length=3)
    infractions_input = discord.ui.TextInput(
        label="Infrazioni",
        placeholder="Descrivi le infrazioni",
        style=discord.TextStyle.paragraph,
        required=True
    )
    fine_amount_input = discord.ui.TextInput(
        label="Multa da pagare",
        placeholder="Importo in $",
        required=True,
        max_length=10
    )

    def __init__(self, bot, user_id: str):
        super().__init__()
        self.bot = bot
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            fine_amount = int(self.fine_amount_input.value)
            if fine_amount <= 0:
                await interaction.response.send_message("❌ L'importo deve essere maggiore di 0!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Importo non valido!", ephemeral=True)
            return
        
        await database.create_fine(
            self.user_id,
            self.name_input.value,
            self.surname_input.value,
            self.age_input.value,
            self.infractions_input.value,
            fine_amount
        )
        
        embed = discord.Embed(
            title="<a:sirena:1431792628332101723> MULTA RICEVUTA",
            color=discord.Color.red()
        )
        embed.add_field(name="👤 Nome", value=self.name_input.value, inline=True)
        embed.add_field(name="👤 Cognome", value=self.surname_input.value, inline=True)
        embed.add_field(name="🎂 Età", value=self.age_input.value, inline=True)
        embed.add_field(name="⚖️ Infrazioni", value=self.infractions_input.value, inline=False)
        embed.add_field(name="💰 Multa", value=f"${fine_amount:,}", inline=False)
        
        try:
            user = await self.bot.fetch_user(int(self.user_id))
            await user.send(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(f"✅ Multa inviata a <@{self.user_id}>!", ephemeral=True)
        await log_command(self.bot, LOG_CHANNEL_ID, f"🚨 {interaction.user.mention} ha multato <@{self.user_id}> per ${fine_amount:,}")

def setup_fine_commands(bot: commands.Bot):
    
    @bot.tree.command(name="multa", description="[LFD] Emetti una multa")
    @app_commands.describe(utente="L'utente da multare")
    async def multa(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        modal = FineModal(bot, str(utente.id))
        await interaction.response.send_modal(modal)
    
    class FineSelectMenu(discord.ui.Select):
        def __init__(self, fines, user_id):
            self.user_id = user_id
            self.fine_map = {}
            options = []
            
            for fine in fines:
                fine_id, name, surname, infractions, fine_amount = fine
                self.fine_map[str(fine_id)] = fine
                options.append(
                    discord.SelectOption(
                        label=f"{name} {surname} - ${fine_amount:,}",
                        description=infractions[:100],
                        value=str(fine_id)
                    )
                )
            
            super().__init__(placeholder="Seleziona una multa da pagare", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ Questo non è il tuo menu!", ephemeral=True)
                return
            
            fine_id = int(self.values[0])
            fine = await database.get_fine(fine_id)
            
            if not fine:
                await interaction.response.send_message("❌ Multa non trovata!", ephemeral=True)
                return
            
            _, user_id, name, surname, age, infractions, fine_amount, paid, _ = fine
            
            if paid:
                await interaction.response.send_message("❌ Questa multa è già stata pagata!", ephemeral=True)
                return
            
            user = await database.get_user(user_id)
            total = user["cash"] + user["bank"]
            
            if total < fine_amount:
                await interaction.response.send_message("❌ Non hai abbastanza soldi per pagare questa multa!", ephemeral=True)
                return
            
            new_cash = user["cash"]
            new_bank = user["bank"]
            remaining = fine_amount
            
            if new_bank >= remaining:
                new_bank -= remaining
            else:
                remaining -= new_bank
                new_bank = 0
                new_cash -= remaining
            
            await database.update_balance(user_id, cash=new_cash, bank=new_bank)
            await database.pay_fine(fine_id)
            
            log_embed = discord.Embed(
                title="💰 MULTA PAGATA",
                color=discord.Color.green()
            )
            log_embed.add_field(name="👤 Nome", value=name, inline=True)
            log_embed.add_field(name="👤 Cognome", value=surname, inline=True)
            log_embed.add_field(name="🎂 Età", value=age, inline=True)
            log_embed.add_field(name="⚖️ Infrazioni", value=infractions, inline=False)
            log_embed.add_field(name="💰 Multa", value=f"${fine_amount:,}", inline=False)
            log_embed.timestamp = datetime.now()
            
            await log_command(bot, LFD_LOG_CHANNEL_ID, embed=log_embed)
            await interaction.response.send_message(f"✅ Hai pagato la multa di **${fine_amount:,}**!", ephemeral=True)
            await log_command(bot, LOG_CHANNEL_ID, f"💳 {interaction.user.mention} ha pagato una multa di ${fine_amount:,}")
    
    @bot.tree.command(name="pagamulta", description="Paga una multa ricevuta")
    async def pagamulta(interaction: discord.Interaction):
        fines = await database.get_unpaid_fines(str(interaction.user.id))
        
        if not fines:
            await interaction.response.send_message(" Non hai multe da pagare!", ephemeral=True)
            return
        
        view = discord.ui.View()
        view.add_item(FineSelectMenu(fines, str(interaction.user.id)))
        
        await interaction.response.send_message("🚨 Seleziona una multa da pagare:", view=view, ephemeral=True)
    
    @bot.tree.command(name="controllomulta", description="[LFD] Controlla le multe di un utente")
    @app_commands.describe(utente="L'utente di cui controllare le multe")
    async def controllomulta(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        fines = await database.get_unpaid_fines(str(utente.id))
        
        if not fines:
            await interaction.response.send_message(f"✅ {utente.mention} non ha multe da pagare!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"🚨 MULTE DI {utente.display_name}",
            color=discord.Color.red()
        )
        
        total_fines = 0
        for fine_id, name, surname, infractions, fine_amount in fines:
            total_fines += fine_amount
            embed.add_field(
                name=f"Multa #{fine_id}",
                value=f"**Nome:** {name} {surname}\n**Infrazioni:** {infractions}\n**Importo:** ${fine_amount:,}",
                inline=False
            )
        
        embed.add_field(name="💰 TOTALE MULTE", value=f"${total_fines:,}", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"👁️ {interaction.user.mention} ha controllato le multe di {utente.mention}")
