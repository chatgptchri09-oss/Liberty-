import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
import database # ASSICURATI CHE QUESTO FILE ESISTA E CONTENGA LE FUNZIONI DB
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

LOG_CHANNEL_ID = 1415297578022604850
DATABASE_NAME = "economy_bot.db"
PORTAFOGLIO_IMAGE_URL = "https://i.imgur.com/placeholder.gif" 

# Le costanti COMPANY_LOG_CHANNELS, COMPANY_ROLES, ALL_COMPANY_ROLES sono corrette.

# ====================
# FUNZIONI DI SUPPORTO
# ====================

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
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
    except Exception:
        pass


def create_bancomat_embed(user: dict, user_mention: str) -> discord.Embed:
    """Crea l'embed del bancomat."""
    embed = discord.Embed(
        # TITOLO MODIFICATO QUI
        title="<a:Bancomat:1431618497489666198> 𝐁𝐀𝐍𝐂𝐎𝐌𝐀𝐓",
        color=discord.Color.blue()
    )
    embed.add_field(name="👤 𝐂𝐋𝐈𝐄𝐍𝐓𝐄", value=user_mention, inline=False)
    embed.add_field(name="💰 𝐂𝐎𝐍𝐓𝐀𝐍𝐓𝐈", value=f"${user['cash']:,}", inline=False)
    embed.add_field(name="💳 𝐁𝐀𝐍𝐂𝐀", value=f"${user['bank']:,}", inline=False)
    embed.add_field(name="💵 𝐓𝐎𝐓𝐀𝐋𝐄", value=f"${user['cash'] + user['bank']:,}", inline=False)
    return embed

# ====================
# CLASSI UI PER /BANCOMAT
# ====================

# Dichiarazione anticipata per l'uso nel Modal
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

    @discord.ui.button(label="Deposita", style=discord.ButtonStyle.blurple, emoji="🏠")
    async def deposita_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MoneyTransferModal(action='deposita')
        await interaction.response.send_modal(modal)


class MoneyTransferModal(Modal):
    amount_input = TextInput(label="Importo", placeholder="La cifra da trasferire (solo numeri)", required=True)

    def __init__(self, action: str):
        # Il titolo va passato direttamente a super().__init__()
        modal_title = "💸 Preleva Contanti" if action == 'preleva' else "🏠 Deposita Denaro"
        super().__init__(title=modal_title)
        self.action = action 
        self.amount_input.label = f"Importo da {action.capitalize()}"


    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        # 1. Validazione input
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            # Rimuovi i separatori per permettere all'utente di scrivere 10.000 o $10,000
            amount_str = self.amount_input.value.replace(',', '').replace('$', '').replace('.', '').strip()
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
        
        # Recupera i dati aggiornati e crea il nuovo embed
        updated_user = await database.get_user(user_id)
        updated_embed = create_bancomat_embed(updated_user, interaction.user.mention)
        
        action_text = "prelevati" if self.action == 'preleva' else "depositati"
        
        # Edit del messaggio originale per mostrare il nuovo saldo
        await interaction.edit_original_response(
            content=f"✅ Hai **{action_text}** **${amount:,}** con successo! Ecco il tuo nuovo saldo:",
            embed=updated_embed,
            view=BancomatView(user_id) # La view deve essere ricreata per coerenza
        )
        
        # 6. Log
        log_msg = f"🏠 {interaction.user.mention} ha {self.action} ${amount:,}"
        await log_command(LOG_CHANNEL_ID, log_msg)


# ====================
# EVENT HANDLERS
# ====================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    
    # Inizializza il database
    await database.init_db()


    # ====================
    # SETUP COMANDI (Spostato qui per risolvere l'errore di importazione ciclica)
    # ====================
    try:
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
        from commands_arrests import setup_arrest_commands

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
        setup_arrest_commands(bot)
        print("✅ Tutti i moduli dei comandi sono stati caricati correttamente.")

    except ImportError as e:
        print(f"❌ Errore di importazione di un modulo comandi: {e}")
    except Exception as e:
        print(f"❌ Errore durante il setup dei comandi: {e}")


# ====================
# COMANDI APP (MANTENUTI QUI)
# ====================

@bot.tree.command(name="bancomat", description="Visualizza il saldo del tuo bancomat")
async def bancomat(interaction: discord.Interaction):
    user = await database.get_user(str(interaction.user.id))
    user_id = str(interaction.user.id)
    user_mention = interaction.user.mention
    
    embed = create_bancomat_embed(user, user_mention)
    view = BancomatView(user_id)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    await log_command(LOG_CHANNEL_ID, f"🏠 {interaction.user.mention} ha controllato il bancomat")


@bot.tree.command(name="sync", description="[STAFF] Sincronizza i comandi")
async def sync(interaction: discord.Interaction):
    if not has_role(interaction, STAFF_ROLE_ID):
        await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
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

    if utente.id == checker_member.id:
        await interaction.response.send_message("❌ Usa il comando `/bancomat` per vedere il tuo saldo.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    
    try:
        user_data = await database.get_user(str(utente.id))
        
        embed = create_bancomat_embed(user_data, utente.mention)
        
        # TITOLO MODIFICATO QUI
        embed.title = f"🔎 𝐂𝐎𝐍𝐓𝐑𝐎𝐋𝐋𝐎 𝐒𝐀𝐋𝐃𝐎: {utente.display_name}"
        embed.color = discord.Color.gold()
        embed.set_footer(text=f"Visualizzato da: {checker_member.display_name}")
        
        try:
            notification_embed = discord.Embed(
                title="🚨 𝐀𝐓𝐓𝐄𝐍𝐙𝐈𝐎𝐍𝐄 ❗",
                description=f"{checker_member.mention} ha visualizzato il tuo conto bancario❗",
                color=discord.Color.red()
            )
            await utente.send(embed=notification_embed)
            dm_status = "Notifica DM inviata all'utente."
        except:
            dm_status = "Notifica DM non inviabile (DM bloccati)."

        await interaction.followup.send(
            content=f"✅ Visualizzazione completata. ({dm_status})",
            embed=embed,
            ephemeral=True 
        )
        
        log_msg = f"👀 {checker_member.mention} ha controllato il bancomat di {utente.mention} (Visibile a tutti)."
        await log_command(LOG_CHANNEL_ID, log_msg)

    except Exception as e:
        print(f"Errore in /controlla-bancomat: {e}")
        await interaction.followup.send("❌ Si è verificato un errore nel controllo del bancomat.", ephemeral=True)

@bot.tree.command(name="help", description="Mostra la lista aggiornata dei comandi del bot")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📚 𝐋𝐈𝐒𝐓𝐀 𝐂𝐎𝐌𝐀𝐍𝐃𝐈 𝐃𝐄𝐋 𝐁𝐎𝐓",
        description="Ecco tutti i comandi disponibili nel server, suddivisi per categoria. Usa quelli del tuo lavoro!",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👮‍♂️ 𝐂𝐎𝐌𝐀𝐍𝐃𝐈 𝐃𝐈 𝐏𝐎𝐋𝐈𝐙𝐈𝐀",
        value=(
            "**/ammanetto** – Ammanetta un cittadino.\n"
            "**/controllatarga** – Controlla la targa di un veicolo.\n"
            "**/controllomulta** – Mostra le multe di un cittadino.\n"
            "**/dissequestraveicolo** – Rimuove un sequestro da un veicolo.\n"
            "**/modificaveicolo** – Modifica i dati di un veicolo.\n"
            "**/multa** – Emetti una multa.\n"
            "**/revoca-patente** – Revoca la patente di un cittadino.\n"
            "**/sequestraveicolo** – Sequestra un veicolo."
        ),
        inline=False
    )

    embed.add_field(
        name="🛠️ 𝐂𝐎𝐌𝐀𝐍𝐃𝐈 𝐎𝐅𝐅𝐈𝐂𝐈𝐍𝐀",
        value=(
            "**/assicurazione** – Gestisci o verifica un’assicurazione.\n"
            "**/modificaveicolo** – Modifica i dati di un veicolo (solo officina)."
        ),
        inline=False
    )

    embed.add_field(
        name="📜 𝐂𝐎𝐌𝐀𝐍𝐃𝐈 𝐃𝐎𝐂𝐔𝐌𝐄𝐍𝐓𝐈",
        value=(
            "**/documento** – Mostra il tuo documento d’identità.\n"
            "**/dailibretto** – Rilascia un libretto di circolazione.\n"
            "**/daipatente** – Rilascia una patente.\n"
            "**/daiportodarmi** – Consegna un porto d’armi.\n"
            "**/daicertificatobalistico** – Rilascia un certificato balistico.\n"
            "**/daicertificatomedico** – Rilascia un certificato medico.\n"
            "**/rimuovilibretto** – Rimuove un libretto di circolazione.\n"
            "**/rimuovicertificatobalistico** – Revoca un certificato balistico.\n"
            "**/rimuovicertificatomedico** – Revoca un certificato medico."
        ),
        inline=False
    )

    embed.add_field(
        name="💵 𝐂𝐎𝐌𝐀𝐍𝐃𝐈 𝐄𝐂𝐎𝐍𝐎𝐌𝐈𝐂𝐈",
        value=(
            "**/bancomat** – Accedi al tuo conto bancario.\n"
            "**/bonifico** – Invia un bonifico a un altro cittadino.\n"
            "**/portafoglio** – Mostra i tuoi contanti.\n"
            "**/controlla-bancomat** – Controlla il conto di un altro utente.\n"
            "**/fattura** – Emetti una fattura lavorativa.\n"
            "**/pagafattura** – Paga una fattura ricevuta.\n"
            "**/pagamulta** – Paga una multa.\n"
            "**/richiesta-stipendio** – Richiedi il tuo stipendio lavorativo."
        ),
        inline=False
    )

    embed.add_field(
        name="🎒 𝐂𝐎𝐌𝐀𝐍𝐃𝐈 𝐈𝐍𝐕𝐄𝐍𝐓𝐀𝐑𝐈𝐎 𝐄 𝐌𝐄𝐑𝐂𝐀𝐓𝐎",
        value=(
            "**/invzaino** – Mostra il contenuto del tuo zaino.\n"
            "**/itemshop** – Mostra gli oggetti acquistabili.\n"
            "**/dai-item** – Dai un oggetto a un altro cittadino.\n"
            "**/utilizza-item** – Usa un oggetto dal tuo zaino.\n"
            "**/vendizaino** – Vendi un oggetto dal tuo zaino.\n"
            "**/item-sell** – Vendi un oggetto del negozio."
        ),
        inline=False
    )

    embed.add_field(
        name="💬 𝐂𝐎𝐌𝐀𝐍𝐃𝐈 𝐒𝐎𝐂𝐈𝐀𝐋 / 𝐑𝐏",
        value=(
            "**/me** – Descrivi un’azione RP.\n"
            "**/anonimo** – Invia un messaggio anonimo.\n"
            "**/nascondo** – Nasconditi per evitare di essere localizzato.\n"
            "**/turno** – Inizia o termina il turno lavorativo."
        ),
        inline=False
    )

    embed.set_footer(text="📄 Usa /help per consultare la lista dei comandi in qualsiasi momento.")

    await interaction.response.send_message(embed=embed, ephemeral=True)

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
        print(f"Errore critico in main: {e}")
