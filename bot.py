import discord 
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
import database
from aiohttp import web
import asyncio
import aiosqlite 
from discord.ui import Modal, TextInput, View, Button 

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
AGENZIA_ROLE_ID = 1424381004944244828
IMPORT_EXPORT_ROLE_ID = 1424004700608401428
STATO_ROLE_ID = 1424005156558606466
PEGASUS_ROLE_ID = 1415262517407645828
CHIAVE_ROLE_ID = 1414735564632231988

LOG_CHANNEL_ID = 1415297578022604850
DATABASE_NAME = "economy_bot.db" 

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

PORTAFOGLIO_IMAGE_URL = "https://i.imgur.com/placeholder.gif"

# ====================
# FUNZIONI DI SUPPORTO
# ====================

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

# Funzione di log che usa la variabile globale 'bot'
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


# ====================
# CLASSI UI PER /BANCOMAT
# ====================

def create_bancomat_embed(user: dict, user_mention: str) -> discord.Embed:
    """Crea l'embed del bancomat."""
    embed = discord.Embed(
        # Utilizzo dei caratteri Unicode Math Sans Bold per il titolo 
        title="<a:Bancomat:1431618497489666198> 𝐁𝐀𝐍𝐂𝐎𝐌𝐀𝐓 <a:cartadicreditoMacerto:1454052506962235560>",
        color=discord.Color.blue()
    )
    # Nomi dei campi in Math Sans Bold
    embed.add_field(name="👤 𝐂𝐋𝐈𝐄𝐍𝐓𝐄", value=user_mention, inline=False)
    embed.add_field(name="💸 𝐂𝐎𝐍𝐓𝐀𝐍𝐓𝐈", value=f"${user['cash']:,}", inline=False)
    embed.add_field(name="💳 𝐁𝐀𝐍𝐂𝐀", value=f"${user['bank']:,}", inline=False)
    embed.add_field(name="💰 𝐓𝐎𝐓𝐀𝐋𝐄", value=f"${user['cash'] + user['bank']:,}", inline=False)
    return embed


class MoneyTransferModal(Modal, title="Trasferimento di Denaro"):
    amount_input = TextInput(label="Importo", placeholder="La cifra da trasferire (solo numeri)", required=True)

    def __init__(self, action: str):
        super().__init__()
        self.action = action # 'preleva' o 'deposita'
        self.title = "💸 Preleva Contanti" if action == 'preleva' else "🏦 Deposita Denaro"
        self.amount_input.label = f"Importo da {action.capitalize()}"


    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        # 1. Validazione input
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            amount_str = self.amount_input.value.replace(',', '').replace('$', '').strip()
            amount = int(amount_str)
            
            if amount <= 0:
                await interaction.followup.send("❌ L'importo deve essere maggiore di zero!", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Importo non valido! Inserisci solo numeri interi.", ephemeral=True)
            return

        # 2. Recupera i saldi
        user = await database.get_user(user_id)
        current_cash = user['cash']
        current_bank = user['bank']
        
        new_cash = current_cash
        new_bank = current_bank
        
        error_message = None

        # 3. Esegue il trasferimento
        if self.action == 'preleva':
            if amount > current_bank:
                error_message = f"❌ Non hai abbastanza soldi in banca per prelevare **${amount:,}**! (Disponibile: ${current_bank:,})"
            else:
                new_cash = current_cash + amount
                new_bank = current_bank - amount
                
        elif self.action == 'deposita':
            if amount > current_cash:
                error_message = f"❌ Non hai abbastanza contanti per depositare **${amount:,}**! (Disponibile: ${current_cash:,})"
            else:
                new_cash = current_cash - amount
                new_bank = current_bank + amount

        if error_message:
            await interaction.followup.send(error_message, ephemeral=True)
            return

        # 4. Aggiorna il database
        await database.update_balance(user_id, cash=new_cash, bank=new_bank)

        # 5. Risposta e aggiornamento embed
        
        # Crea il nuovo embed
        updated_user = await database.get_user(user_id) # Riprendi i dati aggiornati
        updated_embed = create_bancomat_embed(updated_user, interaction.user.mention)
        
        action_text = "prelevati" if self.action == 'preleva' else "depositati"
        
        view = BancomatView(user_id) # La view deve essere ricreata per coerenza
        
        await interaction.followup.send(
            content=f"✅ Hai **{action_text}** **${amount:,}** con successo! Ecco il tuo nuovo saldo:",
            embed=updated_embed,
            view=view,
            ephemeral=True
        )
        
        

class BancomatView(View):
    def __init__(self, user_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Questo non è il tuo bancomat!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Preleva", style=discord.ButtonStyle.green, emoji="💸")
    async def preleva_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MoneyTransferModal(action='preleva')
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Deposita", style=discord.ButtonStyle.blurple, emoji="🏦")
    async def deposita_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MoneyTransferModal(action='deposita')
        await interaction.response.send_modal(modal)


# ====================
# EVENT HANDLERS
# ====================

@bot.event
async def on_ready():
    # Stampa di login
    print(f"✅ Logged in as {bot.user}")
    
    # Inizializza il database
    await database.init_db()
    await setup_marijuana_database()

# ====================
# IMPORTAZIONE COMANDI (Assicurati che questi file esistano)
# ====================
from commands_invoice import setup_invoice_commands
from commands_fines import setup_fine_commands
from commands_documents import setup_document_commands
from commands_wallet import setup_wallet_commands
from commands_inventory import setup_inventory_commands
from commands_rp import setup_rp_commands
from commands_vehicle import setup_vehicle_commands
from commands_bonifico import setup_bonifico_commands
from commands_admin import setup_admin_commands
from commands_bando import setup_bando_commands
from commands_rp_status import setup_rpoff_commands 
from commands_arrests import setup_arrest_commands
from commands_criminal_record import setup_criminal_record_commands
from commands_properties import setup_property_commands
from commands_wipepg import setup_wipepg_commands
from commands_deposits import setup_deposit_commands
from commands_robbery import setup_robbery_commands
from commands_theft import setup_theft_commands
from commands_scoop import setup_scoop_commands
from commands_marijuana import setup_marijuana_commands, setup_marijuana_database

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
setup_bonifico_commands(bot)
setup_admin_commands(bot)
setup_bando_commands(bot)
setup_rpoff_commands(bot)
setup_arrest_commands(bot)
setup_criminal_record_commands(bot)
setup_property_commands(bot)
setup_wipepg_commands(bot)
setup_deposit_commands(bot)
setup_robbery_commands(bot)
setup_theft_commands(bot)
setup_scoop_commands(bot)
setup_marijuana_commands(bot)


# ====================
# COMANDI APP (MANTENUTI QUI)
# ====================

@bot.tree.command(name="bancomat", description="Visualizza il saldo del tuo bancomat")
async def bancomat(interaction: discord.Interaction):
    # La funzione get_user crea l'utente se non esiste
    user = await database.get_user(str(interaction.user.id))
    user_id = str(interaction.user.id)
    user_mention = interaction.user.mention
    
    # Creazione dell'embed
    embed = create_bancomat_embed(user, user_mention)
    
    # Creazione della View con i bottoni
    view = BancomatView(user_id)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



@bot.tree.command(name="sync", description="[STAFF] Sincronizza i comandi")
async def sync(interaction: discord.Interaction):
    if not has_role(interaction, CHIAVE_ROLE_ID):
        await interaction.response.send_message("❌ Solo i due creatori del server possono usare questo comando!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    synced = await bot.tree.sync()
    await interaction.followup.send(f"✅ Sincronizzati {len(synced)} comandi!\nPer vederli, ricarica Discord (Ctrl+R o Cmd+R).", ephemeral=True)

@bot.tree.command(name="controlla-bancomat", description="Visualizza il saldo del bancomat di un altro utente e invia una notifica.")
@app_commands.describe(utente="L'utente di cui controllare il bancomat")
async def controlla_bancomat(interaction: discord.Interaction, utente: discord.Member):
    checker_member = interaction.user
    
    if utente.bot:
        await interaction.response.send_message("❌ Non puoi controllare il bancomat di un bot.", ephemeral=True)
        return

    # Non puoi controllare te stesso, devi usare /bancomat
    if utente.id == checker_member.id:
        await interaction.response.send_message("❌ Usa il comando `/bancomat` per vedere il tuo saldo.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    
    try:
        # 2. Recupera i dati dell'utente Controllato
        user_data = await database.get_user(str(utente.id))
        
        # 3. Creazione dell'embed (usa la funzione esistente)
        embed = create_bancomat_embed(user_data, utente.mention)
        embed.title = f"🔍 SALDO VISTO: {utente.display_name}" # Titolo aggiornato per RP
        embed.color = discord.Color.gold()
        embed.set_footer(text=f"Visualizzato da: {checker_member.display_name}")
        
        # 4. Invia la notifica DM all'utente controllato
        try:
            notification_embed = discord.Embed(
                title="🚨 ATTENZIONE ❗",
                description=f"{checker_member.mention} ha visualizzato il tuo conto bancario❗",
                color=discord.Color.red()
            )
            await utente.send(embed=notification_embed)
            dm_status = "Notifica DM inviata all'utente."
        except:
            dm_status = "Notifica DM non inviabile (DM bloccati)."

        # 5. Risposta a chi ha eseguito il comando
        await interaction.followup.send(
            content=f"✅ Visualizzazione completata. ({dm_status})",
            embed=embed,
            ephemeral=True # Solo l'esecutore vede l'embed
        )
        
        # 6. Log
        log_embed = discord.Embed(
            title="👁️ LOG CONTROLLO BANCOMAT",
            color=discord.Color.gold()
        )
        log_embed.add_field(name="👮 Controllato da", value=checker_member.mention, inline=True)
        log_embed.add_field(name="👤 Utente Controllato", value=utente.mention, inline=True)
        log_embed.add_field(name="💵 Contanti", value=f"${user_data['cash']:,}", inline=False)
        log_embed.add_field(name="🏦 Banca", value=f"${user_data['bank']:,}", inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(LOG_CHANNEL_ID, embed=log_embed)

    except Exception as e:
        print(f"Errore in /controlla-bancomat: {e}")
        await interaction.followup.send("❌ Si è verificato un errore nel controllo del bancomat.", ephemeral=True)

# ====================
# WEBSERVER H24
# ====================
async def handle(request):
    return web.Response(text="✅ Il bot è attivo e funzionante!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup() 

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Server web avviato su porta {port}")

# ====================
# ENTRY POINT PRINCIPALE - CON ERROR HANDLING
# ====================
async def main():
    try:
        # Inizia il web server in background
        await start_webserver()
        
        TOKEN = os.getenv("DISCORD_TOKEN")
        
        if not TOKEN:
            print("❌ ERRORE: DISCORD_TOKEN non trovato nelle variabili d'ambiente!")
            while True:
                await asyncio.sleep(3600)
        
        # Piccolo delay iniziale
        await asyncio.sleep(3)
        
        print("🔄 Connessione a Discord in corso...")
        async with bot:
            await bot.start(TOKEN)
            
    except discord.HTTPException as e:
        if e.status == 429:
            print(f"⚠️ Rate limited da Discord.")
            print(f"🌐 Webserver attivo. Aspetta 30-60 minuti.")
            while True:
                await asyncio.sleep(3600)
        else:
            print(f"❌ Errore HTTP ({e.status}): {e}")
            while True:
                await asyncio.sleep(3600)
    except discord.LoginFailure:
        print(f"❌ Token non valido! Controlla DISCORD_TOKEN.")
        while True:
            await asyncio.sleep(3600)
    except Exception as e:
        print(f"❌ ERRORE CRITICO ALL'AVVIO: {e}")
        import traceback
        traceback.print_exc()  # Stampa lo stack trace completo
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() 
    
    try:
        print("🚀 Avvio bot in corso...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot spento manualmente.")
    except Exception as e:
        print(f"❌ Errore fatale: {e}")
        import traceback
        traceback.print_exc()
