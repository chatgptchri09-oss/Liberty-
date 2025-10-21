import discord 
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
import database
from aiohttp import web
import asyncio

# Nota: discord.VoiceClient = None non è necessario, se l'errore audioop è stato risolto con Python 3.11.

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ====================
# COSTANTI
# ====================
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
    # Aggiungo la verifica per Member, come nei tuoi altri script
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass

@bot.event
async def on_ready():
    # Stampa di login
    print(f"✅ Logged in as {bot.user}")
    
    # Inizializza il database
    await database.init_db()
    
    # ====================
    # IMPORTAZIONE COMANDI (CORRETTA)
    # ====================
    from commands_invoice import setup_invoice_commands
    from commands_fines import setup_fine_commands
    from commands_documents import setup_document_commands
    from commands_wallet import setup_wallet_commands
    from commands_inventory import setup_inventory_commands
    from commands_rp import setup_rp_commands
    from commands_vehicle import setup_vehicle_commands
    from commands_salary import setup_salary_commands 
    from commands_bonifico import setup_bonifico_commands # ⬅️ NUOVO IMPORT AGGIUNTO QUI!
    
    # ====================
    # SETUP COMANDI 
    # ====================
    setup_invoice_commands(bot)
    setup_fine_commands(bot)
    setup_document_commands(bot)
    setup_wallet_commands(bot)
    setup_inventory_commands(bot)
    setup_rp_commands(bot)
    setup_vehicle_commands(bot)
    setup_salary_commands(bot) 
    setup_bonifico_commands(bot) # Questa riga ora funzionerà
    
    try:
        # Sincronizzazione dei comandi
        synced = await bot.tree.sync()
        print(f"✅ Bot online! Sincronizzati {len(synced)} comandi.")
    except Exception as e:
        print(f"❌ Errore nella sincronizzazione: {e}")


# ====================
# COMANDI BANCOMAT / SINCRONIZZAZIONE (da includere qui)
# ====================
@bot.tree.command(name="bancomat", description="Visualizza il saldo del tuo bancomat")
async def bancomat(interaction: discord.Interaction):
    user = await database.get_user(str(interaction.user.id))
    
    if not user:
        await database.create_user(str(interaction.user.id))
        user = await database.get_user(str(interaction.user.id))

    embed = discord.Embed(
        title="🏦 𝐁𝐀𝐍𝐂𝐎𝐌𝐀𝐓",
        color=discord.Color.blue()
    )
    embed.add_field(name="💵 𝐂𝐎𝐍𝐓𝐀𝐍𝐓𝐈", value=f"${user['cash']:,}", inline=False)
    embed.add_field(name="💳 𝐁𝐀𝐍𝐂𝐀", value=f"${user['bank']:,}", inline=False)
    embed.add_field(name="💰 𝐓𝐎𝐓𝐀𝐋𝐄", value=f"${user['cash'] + user['bank']:,}", inline=False)
    embed.set_thumbnail(url=BANCOMAT_IMAGE_URL)
    
    # La BancomatView non è definita qui, ma assumo che esista altrove.
    # In caso contrario, dovrai definirla o togliere 'view=BancomatView()'
    # await interaction.response.send_message(embed=embed, view=BancomatView(), ephemeral=True) 
    await interaction.response.send_message(embed=embed, ephemeral=True) # Uso temporaneo senza view
    await log_command(LOG_CHANNEL_ID, f"🏦 {interaction.user.mention} ha controllato il bancomat")


@bot.tree.command(name="sync", description="[STAFF] Sincronizza i comandi")
async def sync(interaction: discord.Interaction):
    if not has_role(interaction, STAFF_ROLE_ID):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    synced = await bot.tree.sync()
    await interaction.followup.send(f"✅ Sincronizzati {len(synced)} comandi!\\nPer vederli, ricarica Discord (Ctrl+R o Cmd+R).", ephemeral=True)


# ====================
# WEBSERVER H24
# ====================
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


# ====================
# ENTRY POINT PRINCIPALE
# ====================
async def main():
    # Inizia il web server in background
    await start_webserver()
    
    # Avvia il bot
    TOKEN = os.getenv("DISCORD_TOKEN") # Assumendo che il token sia in una variabile d'ambiente
    await bot.start(TOKEN)


if __name__ == "__main__":
    # Assicurati che il tuo token sia disponibile nell'ambiente
    from dotenv import load_dotenv
    load_dotenv() 
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot spento manualmente.")
    except Exception as e:
        print(f"Errore critico in main: {e}")
