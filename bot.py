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
LOG_CHANNEL_ID = 1415297578022604850

# ===================================================================================
# FUNZIONE DI LOG GLOBALE (ESSENZIALE)
# ===================================================================================
async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    """Funzione centralizzata di logging per tutti i comandi."""
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except Exception:
        # Silenzia l'errore se il log fallisce
        pass

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

# ====================
# CLASSI UI PER /BANCOMAT (AGGIORNATE)
# ====================

def create_bancomat_embed(user: dict, user_mention: str) -> discord.Embed:
    """Crea l'embed del bancomat."""
    embed = discord.Embed(
        title="<a:Bancomat:1431618497489666198> 𝐁𝐀𝐍𝐂𝐎𝐌𝐀𝐓",
        color=discord.Color.blue()
    )
    # Ho corretto le emoji che usavano caratteri non standard
    embed.add_field(name="👤 Cliente", value=user_mention, inline=False)
    embed.add_field(name="💵 Contanti", value=f"${user['cash']:,}", inline=False)
    embed.add_field(name="💳 Banca", value=f"${user['bank']:,}", inline=False)
    embed.add_field(name="💲 Totale", value=f"${user['cash'] + user['bank']:,}", inline=False)
    return embed


class MoneyTransferModal(Modal, title="Trasferimento di Denaro"):
    amount_input = TextInput(label="Importo", placeholder="La cifra da trasferire (solo numeri)", required=True)

    # **PASSAGGIO BOT AGGIUNTO**
    def __init__(self, bot: commands.Bot, action: str):
        super().__init__()
        self.bot = bot
        self.action = action 
        self.title = "Preleva Contanti" if action == 'preleva' else "Deposita Denaro"
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
        updated_user = await database.get_user(user_id) 
        updated_embed = create_bancomat_embed(updated_user, interaction.user.mention)
        action_text = "prelevati" if self.action == 'preleva' else "depositati"
        
        # **PASSAGGIO BOT AGGIUNTO**
        view = BancomatView(self.bot, user_id) 
        
        await interaction.followup.send(
            content=f"✅ Hai **{action_text}** **${amount:,}** con successo! Ecco il tuo nuovo saldo:",
            embed=updated_embed,
            view=view,
            ephemeral=True
        )
        
        # 6. Log (CHIAMATA CORRETTA)
        log_msg = f"💸 {interaction.user.mention} ha {self.action} ${amount:,}"
        await log_command(self.bot, LOG_CHANNEL_ID, log_msg)


class BancomatView(View):
    # **PASSAGGIO BOT AGGIUNTO**
    def __init__(self, bot: commands.Bot, user_id: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Questo non è il tuo bancomat!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Preleva", style=discord.ButtonStyle.green, emoji="💸")
    async def preleva_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # **PASSAGGIO BOT AGGIUNTO**
        modal = MoneyTransferModal(self.bot, action='preleva')
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Deposita", style=discord.ButtonStyle.blurple, emoji="🏦")
    async def deposita_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # **PASSAGGIO BOT AGGIUNTO**
        modal = MoneyTransferModal(self.bot, action='deposita')
        await interaction.response.send_modal(modal)

# ====================
# COMANDI APP
# ====================

@bot.tree.command(name="bancomat", description="Visualizza il saldo del tuo bancomat")
async def bancomat(interaction: discord.Interaction):
    
    # 1. DEFER CRITICO: Risponde immediatamente per evitare il timeout (NUOVA AGGIUNTA)
    await interaction.response.defer(ephemeral=True, thinking=True) 
    
    # La funzione get_user crea l'utente se non esiste
    # Questa operazione (database) può impiegare più di 3 secondi
    user = await database.get_user(str(interaction.user.id))
    user_id = str(interaction.user.id)
    user_mention = interaction.user.mention
    
    # Creazione dell'embed
    embed = create_bancomat_embed(user, user_mention)
    
    # Creazione della View con i bottoni
    view = BancomatView(bot, user_id)
    
    # 2. FOLLOWUP: Invia il messaggio finale DOPO il defer (SOSTITUISCE interaction.response.send_message)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    # 3. Log
    await log_command(bot, LOG_CHANNEL_ID, f"💸 {interaction.user.mention} ha controllato il bancomat")


# Il comando /controlla-bancomat aveva già il defer, non è necessaria alcuna modifica lì.

@bot.tree.command(name="controlla-bancomat", description="Visualizza il saldo del bancomat di un altro utente e invia una notifica.")
@app_commands.describe(utente="L'utente di cui controllare il bancomat")
async def controlla_bancomat(interaction: discord.Interaction, utente: discord.Member):
    checker_member = interaction.user
    
    if utente.bot:
        await interaction.response.send_message("❌ Non puoi controllare il bancomat di un bot.", ephemeral=True)
        return

    if utente.id == checker_member.id:
        await interaction.response.send_message("❌ Usa il comando `/bancomat` per vedere il tuo saldo.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    
    try:
        # 2. Recupera i dati dell'utente Controllato
        user_data = await database.get_user(str(utente.id))
        
        # 3. Creazione dell'embed
        embed = create_bancomat_embed(user_data, utente.mention)
        embed.title = f"🔎 SALDO VISTO: {utente.display_name}"
        embed.color = discord.Color.gold()
        embed.set_footer(text=f"Visualizzato da: {checker_member.display_name}")
        
        # 4. Invia la notifica DM all'utente controllato
        try:
            notification_embed = discord.Embed(
                title="⚠️ ATTENZIONE ❗",
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
            ephemeral=True
        )
        
        # 6. Log (CHIAMATA CORRETTA)
        log_msg = f"👀 {checker_member.mention} ha controllato il bancomat di {utente.mention}."
        await log_command(bot, LOG_CHANNEL_ID, log_msg)

    except Exception as e:
        print(f"Errore in /controlla-bancomat: {e}")
        await interaction.followup.send("❌ Si è verificato un errore nel controllo del bancomat.", ephemeral=True)


@bot.tree.command(name="help", description="Visualizza la lista dei comandi disponibili.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="<:IconaGuida:1431695497034203256> 𝐆𝐔𝐈𝐃𝐀 𝐂𝐎𝐌𝐀𝐍𝐃𝐈",
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
            "**/bancomat** – Accedi al tuo conto per depositare o prelevare denaro." # CORRETTO
        ),
        inline=False
    )

    embed.add_field(
        name="💼 INVENTARIO & CRAFTING",
        value=(
            "**/invzaino** – Controlla gli oggetti nel tuo zaino (con peso).\n"
            "**/trasferisci** – Trasferisci un oggetto a un altro utente.\n"
            "**/crafting** – Prova a creare un oggetto usando una ricetta."
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
from commands_crafting import setup_crafting_commands 

# ====================
# 2. SETUP COMANDI (COMPLETO)
# ====================
setup_invoice_commands(bot)
setup_fine_commands(bot) 
setup_document_commands(bot)
setup_wallet_commands(bot)
setup_inventory_commands(bot)
setup_rp_commands(bot)
setup_vehicle_commands(bot)
setup_salary_commands(bot) 
setup_bonifico_commands(bot)
setup_admin_commands(bot)
setup_crafting_commands(bot) 


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
    await start_webserver()
    
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
