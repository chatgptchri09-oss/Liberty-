import discord 
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
import database
from aiohttp import web
import asyncio
import aiosqlite # Necessario per admin commands, meglio averlo qui.
from discord.ui import Modal, TextInput, View, Button # Importiamo le classi UI

# ====================
# CONFIGURAZIONE INIZIALE
# ====================

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
LOG_CHANNEL_ID = 1415297578022604850

# ====================
# EVENTI DI BASE DEL BOT
# ====================

@bot.event
async def on_ready():
    print(f'🤖 Logged in as {bot.user} (ID: {bot.user.id})')
    
    # Inizializza il database
    await database.init_db()
    print("💾 Database inizializzato.")
    
    # Sincronizza i comandi slash
    try:
        synced = await bot.tree.sync()
        print(f"✅ Sincronizzati {len(synced)} comandi slash globali.")
    except Exception as e:
        print(f"❌ Errore durante la sincronizzazione: {e}")

# ====================
# COMANDI AGGIUNTIVI (Esempio /sync)
# ====================

@bot.tree.command(name="sync", description="[STAFF] Sincronizza i comandi slash con Discord.")
async def sync_command(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("❌ Non hai i permessi per eseguire questo comando.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        await interaction.followup.send(f"✅ Sincronizzazione completata! Sincronizzati **{len(synced)}** comandi.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Errore durante la sincronizzazione: {e}", ephemeral=True)


@bot.tree.command(name="help", description="Visualizza la lista dei comandi disponibili.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="<:IconaGuida:1431695431666878484> 𝐆𝐔𝐈𝐃𝐀 𝐂𝐎𝐌𝐀𝐍𝐃𝐈",
        description="Ecco la lista di tutti i comandi disponibili suddivisi per categoria.",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="💰 ECONOMIA",
        value=(
            "**/portafoglio** – Visualizza i tuoi saldi e documenti.\n"
            "**/bonifico** – Invia denaro in banca ad un altro utente.\n"
            "**/pagafattura** – Visualizza e paga le tue fatture.\n"
            "**/pagamulta** – Visualizza e paga le tue multe.\n"
            "**/deposito** – Deposita denaro in banca.\n"
            "**/preleva** – Preleva denaro dalla banca."
        ),
        inline=False
    )

    embed.add_field(
        name="💼 INVENTARIO & CRAFTING",
        value=(
            "**/invzaino** – Controlla gli oggetti nel tuo zaino (con peso).\n"
            "**/dai** – Trasferisci un oggetto a un altro utente.\n"
            "**/progetto** – Visualizza le ricette che possiedi.\n"
            "**/crafta** – Prova a creare un oggetto usando una ricetta."
        ),
        inline=False
    )
    
    embed.add_field(
        name="🚨 L.F.D. / E.M.S.",
        value=(
            "**/documento** – Compila il tuo documento d'identità (una tantum).\n"
            "**/controlladoc** – Controlla il documento di un cittadino (LFD/EMS).\n"
            "**/controllatarga** – Controlla la targa di un veicolo (LFD/Officina).\n"
            "**/multa** – Emetti una multa a un cittadino (LFD).\n"
            "**/fattura** – Emetti una fattura a un cittadino (Aziende).\n"
            "**/certificatomedico** – Rilascia un certificato medico (EMS)."
        ),
        inline=False
    )
    
    embed.add_field(
        name="🗣️ COMANDI SOCIAL / RP",
        value=(
            "**/me** – Descrivi un’azione RP.\n"
            "**/anonimo** – Invia un messaggio anonimo.\n"
            "**/nascondo** – Nasconditi per evitare di essere localizzato.\n"
            "**/turno** – Inizia o termina il turno lavorativo."
        ),
        inline=False
    )

    embed.set_footer(text="📌 Usa /help per consultare la lista dei comandi in qualsiasi momento.")

    await interaction.response.send_message(embed=embed, ephemeral=True)

# ====================
# 1. IMPORTAZIONE COMANDI (COMPLETA)
# ====================
from commands_invoice import setup_invoice_commands
from commands_fines import setup_fine_commands
from commands_documents import setup_document_commands
from commands_wallet import setup_wallet_commands
from commands_inventory import setup_inventory_commands
from commands_rp import setup_rp_commands
from commands_vehicle import setup_vehicle_commands
from commands_salary import setup_salary_commands 
from commands_bonifico import setup_bonifico_commands
from commands_admin import setup_admin_commands
from commands_crafting import setup_crafting_commands # <--- NUOVA

# ====================
# 2. SETUP COMANDI (COMPLETO)
# ====================
setup_invoice_commands(bot)
setup_fines_commands(bot) # <-- Ripristinato l'uso del file corretto
setup_document_commands(bot)
setup_wallet_commands(bot)
setup_inventory_commands(bot)
setup_rp_commands(bot)
setup_vehicle_commands(bot)
setup_salary_commands(bot) 
setup_bonifico_commands(bot)
setup_admin_commands(bot)
setup_crafting_commands(bot) # <--- NUOVA


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
    TOKEN = os.getenv("DISCORD_TOKEN")
    await bot.start(TOKEN)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot spento manualmente.")
    except Exception as e:
        print(f"Errore critico all'avvio: {e}")
