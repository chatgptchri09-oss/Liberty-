import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput
import aiosqlite
import asyncio
import math
import database

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
ITEMS_PER_PAGE = 10
LOG_CHANNEL_ITEM_ID = 1458565566070788146
ADMIN_ROLE_ID = 1414923114185490595
LOG_CHANNEL_MONEY_ID = 1459209240450433094


# Configurazione Fondi Cassa
CASH_FUNDS = {
    "Fondo Cassa L.F.D": {
        "role_id": 1415093546549248040,
        "color": 0x3498db,
        "table_name": "fund_lfd"
    },
    "Fondo Cassa Import Export": {
        "role_id": 1424004700608401428,
        "color": 0x992d22,
        "table_name": "fund_import"
    },
    "Fondo Cassa Armeria": {
        "role_id": 1415092383250382858,
        "color": 0xff6e00,
        "table_name": "fund_armeria"
    },
    "Fondo Cassa Market": {
        "role_id": 1415242295153918123,
        "color": 0xe67e22,
        "table_name": "fund_market"
    },
    "Fondo Cassa Diamond Casinò": {
        "role_id": 1449432810573140151,
        "color": 0x3498db,
        "table_name": "fund_casino"
    },
    "Fondo Cassa Vanilla Unicorn": {
        "role_id": 1415243266777157643,
        "color": 0x9b59b6,
        "table_name": "fund_vanilla"
    },
    "Fondo Cassa The Music Looker": {
        "role_id": 1460290945118638160,
        "color": 0xe91e63,
        "table_name": "fund_music"
    }
}

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

async def get_fund_balance(fund_name: str) -> int:
    """Recupera il saldo del fondo cassa"""
    table_name = CASH_FUNDS[fund_name]["table_name"]
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(f"SELECT balance FROM cash_funds WHERE fund_name = ?", (table_name,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

async def update_fund_balance(fund_name: str, amount: int):
    """Aggiorna il saldo del fondo cassa"""
    table_name = CASH_FUNDS[fund_name]["table_name"]
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO cash_funds (fund_name, balance) VALUES (?, ?) ON CONFLICT(fund_name) DO UPDATE SET balance = balance + ?",
            (table_name, amount, amount)
        )
        await db.commit()

class DepositFundModal(Modal, title="🏦 Deposita nel Fondo Cassa"):
    amount = TextInput(label="Importo da Depositare", placeholder="Inserisci l'importo...", required=True, max_length=15)

    def __init__(self, bot, fund_name: str):
        super().__init__()
        self.bot = bot
        self.fund_name = fund_name

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value.replace(",", "").replace("$", "").strip())
            
            if amount <= 0:
                await interaction.response.send_message("❌ L'importo deve essere maggiore di zero!", ephemeral=True)
                return
            
            user_data = await database.get_user(str(interaction.user.id))
            
            if user_data['cash'] < amount:
                await interaction.response.send_message(
                    f"❌ Non hai abbastanza contanti! (Possiedi: ${user_data['cash']:,})",
                    ephemeral=True
                )
                return
            
            # Sottrai dal bancomat dell'utente
            new_cash = user_data['cash'] - amount
            await database.update_balance(str(interaction.user.id), cash=new_cash)
            
            # Aggiungi al fondo cassa
            await update_fund_balance(self.fund_name, amount)
            
            new_balance = await get_fund_balance(self.fund_name)
            
            embed = discord.Embed(
                title=f"💼 DEPOSITO EFFETTUATO",
                description=f"{interaction.user.mention} ha depositato nel **{self.fund_name}**",
                color=CASH_FUNDS[self.fund_name]["color"]
            )
            embed.add_field(name="💸 Importo Depositato", value=f"${amount:,}", inline=True)
            embed.add_field(name="💰 Nuovo Saldo Fondo", value=f"${new_balance:,}", inline=True)
            embed.set_footer(text="Sistema Finanziario Aziendale Liberty City • 2026")
            embed.timestamp = discord.utils.utcnow()
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Log
            log_embed = discord.Embed(
                title="📥 LOG DEPOSITO FONDO CASSA",
                color=discord.Color.green()
            )
            log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🏢 Fondo", value=self.fund_name, inline=True)
            log_embed.add_field(name="💰 Importo", value=f"${amount:,}", inline=False)
            log_embed.add_field(name="💼 Nuovo Saldo", value=f"${new_balance:,}", inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(self.bot, LOG_CHANNEL_MONEY_ID, embed=log_embed)
            
        except ValueError:
            await interaction.response.send_message("❌ Importo non valido! Inserisci solo numeri.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Errore: {str(e)}", ephemeral=True)


class WithdrawFundModal(Modal, title="💸 Preleva dal Fondo Cassa"):
    amount = TextInput(label="Importo da Prelevare", placeholder="Inserisci l'importo...", required=True, max_length=15)

    def __init__(self, bot, fund_name: str):
        super().__init__()
        self.bot = bot
        self.fund_name = fund_name

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value.replace(",", "").replace("$", "").strip())
            
            if amount <= 0:
                await interaction.response.send_message("❌ L'importo deve essere maggiore di zero!", ephemeral=True)
                return
            
            current_balance = await get_fund_balance(self.fund_name)
            
            if current_balance < amount:
                await interaction.response.send_message(
                    f"❌ Fondi insufficienti! (Disponibile: ${current_balance:,})",
                    ephemeral=True
                )
                return
            
            # Sottrai dal fondo cassa
            await update_fund_balance(self.fund_name, -amount)
            
            # Aggiungi al bancomat dell'utente
            user_data = await database.get_user(str(interaction.user.id))
            new_cash = user_data['cash'] + amount
            await database.update_balance(str(interaction.user.id), cash=new_cash)
            
            new_balance = await get_fund_balance(self.fund_name)
            
            embed = discord.Embed(
                title=f"💼 PRELIEVO EFFETTUATO",
                description=f"{interaction.user.mention} ha prelevato dal **{self.fund_name}**",
                color=CASH_FUNDS[self.fund_name]["color"]
            )
            embed.add_field(name="💸 Importo Prelevato", value=f"${amount:,}", inline=True)
            embed.add_field(name="💰 Nuovo Saldo Fondo", value=f"${new_balance:,}", inline=True)
            embed.set_footer(text="Sistema Finanziario Aziendale Liberty City • 2026")
            embed.timestamp = discord.utils.utcnow()
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Log
            log_embed = discord.Embed(
                title="📤 LOG PRELIEVO FONDO CASSA",
                color=discord.Color.orange()
            )
            log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🏢 Fondo", value=self.fund_name, inline=True)
            log_embed.add_field(name="💰 Importo", value=f"${amount:,}", inline=False)
            log_embed.add_field(name="💼 Nuovo Saldo", value=f"${new_balance:,}", inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(self.bot, LOG_CHANNEL_MONEY_ID, embed=log_embed)
            
        except ValueError:
            await interaction.response.send_message("❌ Importo non valido! Inserisci solo numeri.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Errore: {str(e)}", ephemeral=True)


class FundView(discord.ui.View):
    """View per gestire il fondo cassa"""
    def __init__(self, bot, fund_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.fund_name = fund_name
    
    @discord.ui.button(label="💸 Preleva", style=discord.ButtonStyle.green)
    async def withdraw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WithdrawFundModal(self.bot, self.fund_name)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🏦 Deposita", style=discord.ButtonStyle.primary)
    async def deposit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DepositFundModal(self.bot, self.fund_name)
        await interaction.response.send_modal(modal)


def setup_fondocassa_commands(bot: commands.Bot):
    
    async def fund_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        choices = []
        for name in CASH_FUNDS.keys():
            choices.append(app_commands.Choice(name=name, value=name))
        
        if current:
            return [
                choice for choice in choices
                if current.lower() in choice.name.lower()
            ]
        return choices
    
    @bot.tree.command(name="fondocassa", description="Visualizza e gestisci il fondo cassa aziendale")
    @app_commands.describe(scelta="Seleziona il fondo cassa da gestire")
    @app_commands.autocomplete(scelta=fund_autocomplete)
    async def fondocassa(interaction: discord.Interaction, scelta: str):
        if scelta not in CASH_FUNDS:
            await interaction.response.send_message("❌ Fondo cassa non valido!", ephemeral=True)
            return
        
        if not has_role(interaction, CASH_FUNDS[scelta]["role_id"]):
            await interaction.response.send_message(
                "❌ Non hai i permessi per accedere a questo fondo cassa!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        balance = await get_fund_balance(scelta)
        nome_azienda = scelta.replace("Fondo Cassa ", "")
        
        embed = discord.Embed(
            title=f"💼 GESTIONE FONDO CASSA - {nome_azienda}",
            description=f"💰 **Saldo Disponibile:** ${balance:,}",
            color=CASH_FUNDS[scelta]["color"]
        )
        embed.set_footer(text="Sistema Finanziario Aziendale Liberty City • 2026")
        
        view = FundView(bot, scelta)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @bot.tree.command(name="add-fondocassa", description="[ADMIN] Aggiungi denaro a un fondo cassa")
    @app_commands.describe(
        scelta="Seleziona il fondo cassa",
        importo="Importo da aggiungere"
    )
    @app_commands.autocomplete(scelta=fund_autocomplete)
    async def add_fondocassa(interaction: discord.Interaction, scelta: str, importo: int):
        if not has_role(interaction, ADMIN_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo gli amministratori possono usare questo comando!",
                ephemeral=True
            )
            return
        
        if scelta not in CASH_FUNDS:
            await interaction.response.send_message("❌ Fondo cassa non valido!", ephemeral=True)
            return
        
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere maggiore di zero!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        await update_fund_balance(scelta, importo)
        new_balance = await get_fund_balance(scelta)
        
        nome_azienda = scelta.replace("Fondo Cassa ", "")
        
        embed = discord.Embed(
            title=f"✅ FONDI AGGIUNTI",
            description=f"Hai aggiunto **${importo:,}** al **{scelta}**",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Nuovo Saldo", value=f"${new_balance:,}", inline=False)
        embed.set_footer(text="Sistema Finanziario Aziendale Liberty City • 2026")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Log
        log_embed = discord.Embed(
            title="➕ LOG AGGIUNTA FONDO CASSA",
            color=discord.Color.gold()
        )
        log_embed.add_field(name="👤 Admin", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="🏢 Fondo", value=scelta, inline=True)
        log_embed.add_field(name="💰 Importo Aggiunto", value=f"${importo:,}", inline=False)
        log_embed.add_field(name="💼 Nuovo Saldo", value=f"${new_balance:,}", inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_MONEY_ID, embed=log_embed)
    
    print("✅ Comandi fondo cassa caricati")
