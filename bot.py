import discord 
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
import database
from aiohttp import web
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

STAFF_ROLE_ID = 1414738761207517214
LFD_ROLE_ID = 1415093546549248040
EMS_ROLE_ID = 1415239481757536256
ARMERIA_ROLE_ID = 1415092383250382858
CONCESSIONARIO_ROLE_ID = 1415238213303406702
VANILLA_ROLE_ID = 1415243266777157643
MARKET_ROLE_ID = 1415242295153918123
OFFICINA_ROLE_ID = 1415240071216500746
AGENZIA_ROLE_ID = 1424381004944244828
IMPORT_EXPORT_ROLE_ID = 1424004700608401428
STATO_ROLE_ID = 1424005156558606466
PEGASUS_ROLE_ID = 1415262517407645828

LOG_CHANNEL_ID = 1415297578022604850

COMPANY_LOG_CHANNELS = {
    "EMS": 1424111086537281567,
    "Armeria": 1424111403228205147,
    "Concessionario": 1424111522107490405,
    "Market": 1424111628374511729,
    "Officina": 1424111759559495760,
    "Import/Export": 1424111925360463882,
    "Pegasus Airlines": 1424112194139984003,
    "L.F.D": 1424007218554208316
}

COMPANY_ROLES = {
    "EMS": EMS_ROLE_ID,
    "Armeria": ARMERIA_ROLE_ID,
    "Concessionario": CONCESSIONARIO_ROLE_ID,
    "Market": MARKET_ROLE_ID,
    "Officina": OFFICINA_ROLE_ID,
    "Import/Export": IMPORT_EXPORT_ROLE_ID,
    "L.F.D": LFD_ROLE_ID,
    "Pegasus Airlines": PEGASUS_ROLE_ID
}

ALL_COMPANY_ROLES = {
    "EMS": EMS_ROLE_ID,
    "Armeria": ARMERIA_ROLE_ID,
    "Concessionario": CONCESSIONARIO_ROLE_ID,
    "Vanilla Unicorn": VANILLA_ROLE_ID,
    "Market": MARKET_ROLE_ID,
    "Officina": OFFICINA_ROLE_ID,
    "Agenzia Immobiliare": AGENZIA_ROLE_ID,
    "Import/Export": IMPORT_EXPORT_ROLE_ID,
    "Stato": STATO_ROLE_ID,
    "L.F.D": LFD_ROLE_ID,
    "Pegasus Airlines": PEGASUS_ROLE_ID
}

BANCOMAT_IMAGE_URL = "https://i.imgur.com/placeholder.gif"
PORTAFOGLIO_IMAGE_URL = "https://i.imgur.com/placeholder.gif"

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(channel_id: int, message: str):
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)
    except:
        pass


@bot.event
async def on_ready():
    await database.init_db()
    
    from commands_invoice import setup_invoice_commands
    from commands_fines import setup_fine_commands
    from commands_documents import setup_document_commands
    from commands_wallet import setup_wallet_commands
    from commands_inventory import setup_inventory_commands
    from commands_rp import setup_rp_commands
    from commands_vehicle import setup_vehicle_commands
    
    setup_invoice_commands(bot)
    setup_fine_commands(bot)
    setup_document_commands(bot)
    setup_wallet_commands(bot)
    setup_inventory_commands(bot)
    setup_rp_commands(bot)
    setup_vehicle_commands(bot)
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot online! Sincronizzati {len(synced)} comandi.")
    except Exception as e:
        print(f"❌ Errore nella sincronizzazione: {e}")


class WithdrawModal(discord.ui.Modal, title="💸 Preleva Contanti"):
    amount = discord.ui.TextInput(
        label="Importo da prelevare",
        placeholder="Inserisci l'importo in $",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount_value = int(self.amount.value)
            if amount_value <= 0:
                await interaction.response.send_message("❌ L'importo deve essere maggiore di 0!", ephemeral=True)
                return

            user = await database.get_user(str(interaction.user.id))
            
            if user["bank"] < amount_value:
                await interaction.response.send_message("❌ Non hai abbastanza soldi in banca!", ephemeral=True)
                return
            
            new_bank = user["bank"] - amount_value
            new_cash = user["cash"] + amount_value
            await database.update_balance(str(interaction.user.id), cash=new_cash, bank=new_bank)
            
            await interaction.response.send_message(f"✅ Hai prelevato **${amount_value:,}** dalla banca!", ephemeral=True)
            await log_command(LOG_CHANNEL_ID, f"💸 {interaction.user.mention} ha prelevato ${amount_value:,}")
        except ValueError:
            await interaction.response.send_message("❌ Inserisci un importo valido!", ephemeral=True)

class DepositModal(discord.ui.Modal, title="💰 Deposita Contanti"):
    amount = discord.ui.TextInput(
        label="Importo da depositare",
        placeholder="Inserisci l'importo in $",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount_value = int(self.amount.value)
            if amount_value <= 0:
                await interaction.response.send_message("❌ L'importo deve essere maggiore di 0!", ephemeral=True)
                return

            user = await database.get_user(str(interaction.user.id))
            
            if user["cash"] < amount_value:
                await interaction.response.send_message("❌ Non hai abbastanza contanti!", ephemeral=True)
                return
            
            new_cash = user["cash"] - amount_value
            new_bank = user["bank"] + amount_value
            await database.update_balance(str(interaction.user.id), cash=new_cash, bank=new_bank)
            
            await interaction.response.send_message(f"✅ Hai depositato **${amount_value:,}** in banca!", ephemeral=True)
            await log_command(LOG_CHANNEL_ID, f"💰 {interaction.user.mention} ha depositato ${amount_value:,}")
        except ValueError:
            await interaction.response.send_message("❌ Inserisci un importo valido!", ephemeral=True)


class BancomatView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💸 Preleva", style=discord.ButtonStyle.green)
    async def withdraw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WithdrawModal())

    @discord.ui.button(label="💰 Deposita", style=discord.ButtonStyle.primary)
    async def deposit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DepositModal())


@bot.tree.command(name="bancomat", description="Visualizza il tuo bancomat")
async def bancomat(interaction: discord.Interaction):
    user = await database.get_user(str(interaction.user.id))
    
    embed = discord.Embed(
        title="🏦 𝐁𝐀𝐍𝐂𝐎𝐌𝐀𝐓",
        color=discord.Color.blue()
    )
    embed.add_field(name="👤 𝐂𝐋𝐈𝐄𝐍𝐓𝐄", value=interaction.user.mention, inline=False)
    embed.add_field(name="💵 𝐂𝐎𝐍𝐓𝐀𝐍𝐓𝐈", value=f"${user['cash']:,}", inline=False)
    embed.add_field(name="🏦 𝐁𝐀𝐍𝐂𝐀", value=f"${user['bank']:,}", inline=False)
    embed.add_field(name="💰 𝐓𝐎𝐓𝐀𝐋𝐄", value=f"${user['cash'] + user['bank']:,}", inline=False)
    embed.set_thumbnail(url=BANCOMAT_IMAGE_URL)
    
    await interaction.response.send_message(embed=embed, view=BancomatView(), ephemeral=True)
    await log_command(LOG_CHANNEL_ID, f"🏦 {interaction.user.mention} ha controllato il bancomat")


@bot.tree.command(name="sync", description="[STAFF] Sincronizza i comandi")
async def sync(interaction: discord.Interaction):
    if not has_role(interaction, STAFF_ROLE_ID):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    synced = await bot.tree.sync()
    await interaction.followup.send(f"✅ Sincronizzati {len(synced)} comandi!", ephemeral=True)


async def handle(request):
    return web.Response(text="✅ Il bot è attivo e funzionante!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Server web avviato su porta {port}")


async def main():
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ ERRORE: variabile DISCORD_TOKEN non trovata.")
        return

    webserver = asyncio.create_task(start_webserver())
    await bot.start(TOKEN)
    await webserver


if __name__ == "__main__":
    asyncio.run(main())
