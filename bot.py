import discord
from discord import app_commands
from discord.ext import commands
import os
from datetime import datetime
import database
import backup
from aiohttp import web
import asyncio
import aiosqlite
from discord.ui import Modal, TextInput, View, Button
import sys
import time

sys.stdout.reconfigure(line_buffering=True)
print("✅ Import base completati", flush=True)

# ====================
# CONFIGURAZIONE
# ====================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
print("✅ Bot inizializzato", flush=True)

# ====================
# VARIABILI GLOBALI
# ====================
last_sync_time = 0


# ====================
# COSTANTI RDR2
# ====================
STAFF_ROLE_ID       = 1414738761207517214
SCERIFFO_ROLE_ID    = 1415093546549248040
DOTTORE_ROLE_ID     = 1415239481757536256
ARMIERE_ROLE_ID     = 1415092383250382858
STALLA_ROLE_ID      = 1415238213303406702
SALOON_ROLE_ID      = 1415243266777157643
EMPORIO_ROLE_ID     = 1415242295153918123
OFFICINA_ROLE_ID    = 1415240071216500746
CONTRABBANDO_ID     = 1424004700608401428
STATO_ROLE_ID       = 1424005156558606466
DILIGENZA_ROLE_ID   = 1415262517407645828
CHIAVE_ROLE_ID      = 1414735564632231988
BANKER_ROLE_ID      = 1404051937438994493

LOG_CHANNEL_ID      = 1415297578022604850
BANK_CHANNEL_ID     = 1404052325609504798
DATABASE_NAME       = "rdr2_bot.db"

COMPANY_LOG_CHANNELS = {
    "Sceriffo":     1424007218554208316,
    "Dottore":      1424111086537281567,
    "Armiere":      1424111403228205147,
    "Stalla":       1424111522107490405,
    "Emporio":      1424111628374511729,
    "Officina":     1424111759559495760,
    "Contrabbando": 1424111925360463882,
    "Diligenza":    1424112194139984003,
}

COMPANY_ROLES = {
    "Sceriffo":     SCERIFFO_ROLE_ID,
    "Dottore":      DOTTORE_ROLE_ID,
    "Armiere":      ARMIERE_ROLE_ID,
    "Stalla":       STALLA_ROLE_ID,
    "Saloon":       SALOON_ROLE_ID,
    "Emporio":      EMPORIO_ROLE_ID,
    "Contrabbando": CONTRABBANDO_ID,
    "Diligenza":    DILIGENZA_ROLE_ID,
}

print("✅ Costanti definite", flush=True)

# ====================
# SUPPORTO
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

print("✅ Funzioni di supporto definite", flush=True)

# ====================
# EVENT HANDLERS
# ====================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}", flush=True)
    print(f"✅ Bot ID: {bot.user.id}", flush=True)
    print(f"✅ Presente in {len(bot.guilds)} server", flush=True)
    await database.init_db()
    print("✅ Bot RDR2 pronto! 🤠", flush=True)

print("✅ Event handler registrato", flush=True)

# ====================
# IMPORT COMANDI
# ====================

_imports = [
    ("commands_invoice",         "setup_invoice_commands"),
    ("commands_fines",           "setup_fine_commands"),
    ("commands_documents",       "setup_document_commands"),
    ("commands_wallet",          "setup_wallet_commands"),
    ("commands_inventory",       "setup_inventory_commands"),
    ("commands_rp",              "setup_rp_commands"),
    ("commands_admin",           "setup_admin_commands"),
    ("commands_bando",           "setup_bando_commands"),
    ("commands_rp_status",       "setup_rpoff_commands"),
    ("commands_arrests",         "setup_arrest_commands"),
    ("commands_criminal_record", "setup_criminal_record_commands"),
    ("commands_properties",      "setup_property_commands"),
    ("commands_wipepg",          "setup_wipepg_commands"),
    ("commands_robbery",         "setup_robbery_commands"),
    ("commands_theft",           "setup_theft_commands"),
    ("commands_scoop",           "setup_scoop_commands"),
    ("commands_fondocassa",      "setup_fondocassa_commands"),
    ("commands_bonifico",        "setup_bonifico_commands"),
    ("commands_deposits",        "setup_deposit_commands"),
]

_loaded_setups = {}

for _module_name, _func_name in _imports:
    try:
        print(f"📦 Import {_module_name}...", flush=True)
        _mod = __import__(_module_name)
        _loaded_setups[_func_name] = getattr(_mod, _func_name)
        print(f"✅ {_module_name} OK", flush=True)
    except Exception as e:
        print(f"❌ ERRORE in {_module_name}: {e}", flush=True)

try:
    print("📦 Import commands_marijuana...", flush=True)
    from commands_marijuana import setup_marijuana_commands, setup_marijuana_database
    _loaded_setups["setup_marijuana_commands"] = setup_marijuana_commands
    print("✅ commands_marijuana OK", flush=True)
except Exception as e:
    print(f"❌ ERRORE in commands_marijuana: {e}", flush=True)
    async def setup_marijuana_database(): pass

print("✅ Import completati!", flush=True)

# ====================
# SETUP COMANDI
# ====================

print("🔧 Setup comandi...", flush=True)
for _func_name, _func in _loaded_setups.items():
    try:
        _func(bot)
        print(f"✅ {_func_name}", flush=True)
    except Exception as e:
        print(f"❌ {_func_name}: {e}", flush=True)
print("✅ Setup completato!", flush=True)

# ====================
# COMANDO SYNC
# ====================

@bot.tree.command(name="sync", description="[Staff] Sincronizza i comandi slash")
async def sync(interaction: discord.Interaction):
    global last_sync_time
    if not has_role(interaction, CHIAVE_ROLE_ID):
        await interaction.response.send_message("❌ Solo i creatori del server possono usare questo comando.", ephemeral=True)
        return

    
    await interaction.response.defer(ephemeral=True)
    try:
        synced = await bot.tree.sync()
        last_sync_time = time.time()
        await interaction.followup.send(
            f"✅ **{len(synced)} comandi sincronizzati!**\n🔄 Ricarica Discord per vederli.\n⏰ Prossima sync disponibile tra **1 ora**.",
            ephemeral=True
        )
        print(f"✅ Sync: {len(synced)} comandi — da {interaction.user}", flush=True)
    except discord.HTTPException as e:
        if e.status == 429:
            await interaction.followup.send("❌ **Rate limited da Discord.** Aspetta 2-3 ore.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)

# ====================
# LISTA COMANDI
# ====================

class CommandCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⭐ Comandi Staff",    description="Comandi riservati allo staff",       value="staff"),
            discord.SelectOption(label="🔫 Comandi Sceriffo", description="Comandi dello Sceriffo e dei lawman", value="sceriffo"),
            discord.SelectOption(label="💰 Comandi Economia", description="Banca, fatture, fondo cassa",         value="economia"),
            discord.SelectOption(label="🤠 Comandi Roleplay", description="Azioni, caccia, pesca, crafting",     value="roleplay"),
        ]
        super().__init__(placeholder="Seleziona una categoria...", options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]

        if category == "staff":
            embed = discord.Embed(title="⭐ COMANDI STAFF", color=discord.Color.red())
            cmds = [
                "`/crea-item` — Crea un item nell'emporio",
                "`/eliminaitem` — Elimina un item dall'emporio",
                "`/give-item` — Dai un item a un giocatore",
                "`/take-item` — Rimuovi un item da un giocatore",
                "`/add-money` — Aggiungi denaro a un giocatore",
                "`/remove-money` — Rimuovi denaro da un giocatore",
                "`/paga-stipendio` — Paga lo stipendio",
                "`/annuncio` — Invia un annuncio pubblico",
                "`/bando` — Apri/chiudi un bando lavorativo",
                "`/esito-bando` — Comunica l'esito di un bando",
                "`/rpon` — Attiva il Roleplay",
                "`/rpoff` — Disattiva il Roleplay",
                "`/sondaggiorp` — Crea un sondaggio RP",
                "`/rimuovibisaccia` — Rimuovi la bisaccia di un giocatore",
                "`/wipe-pg` — Resetta completamente un personaggio",
                "`/wipe-item` — Svuota tutte le bisacce",
                "`/whitelister` — Dai l'esito di una whitelist",
                "`/status-whitelist` — Stato servizi whitelist",
                "`/add-fondocassa` — Aggiungi al fondo cassa",
                "`/daiproprieta` — Registra una proprietà",
            ]
        elif category == "sceriffo":
            embed = discord.Embed(title="🔫 COMANDI SCERIFFO", color=discord.Color.blue())
            cmds = [
                "`/documento` — Emetti un documento di identità",
                "`/rimuovi-documento` — Rimuovi un documento",
                "`/cercapersona` — Cerca una persona nel registro",
                "`/ammanetto` — Ammanetta un sospettato",
                "`/taglia` — Emetti una taglia su un fuorilegge",
                "`/controlla-taglia` — Verifica le taglie di un giocatore",
                "`/modulo-arresto` — Compila un modulo di arresto",
                "`/denuncia` — Compila una denuncia ufficiale",
                "`/puliziafedinapenale` — Pulisci la fedina penale",
            ]
        elif category == "economia":
            embed = discord.Embed(title="💰 COMANDI ECONOMIA", color=discord.Color.green())
            cmds = [
                "`/banca` — Accedi al tuo conto bancario",
                "`/portafoglio` — Visualizza i tuoi averi",
                "`/controlla-conto` — Controlla il conto di un altro giocatore",
                "`/fattura` — Emetti una fattura",
                "`/pagafattura` — Paga una fattura ricevuta",
                "`/paga-taglia` — Paga le taglie sulla tua testa",
                "`/fondocassa` — Visualizza il fondo cassa della tua compagnia",
            ]
        elif category == "roleplay":
            embed = discord.Embed(title="🤠 COMANDI ROLEPLAY", color=discord.Color.purple())
            cmds = [
                "`/me` — Esegui un'azione RP (Fame & Sete calano!)",
                "`/mangia` — Mangia dalla tua bisaccia",
                "`/bevi` — Bevi dalla tua bisaccia",
                "`/bisaccia` — Visualizza la tua bisaccia",
                "`/dai-item` — Dai un item a un altro giocatore",
                "`/utilizza-item` — Utilizza un item",
                "`/itemshop` — Visualizza l'emporio",
                "`/item-sell` — Acquista dall'emporio",
                "`/anonimo` — Invia un messaggio anonimo",
                "`/sondaggiorp` — Crea un sondaggio RP",
                "`/nascondo` — Nascondi un oggetto",
                "`/campeggio` — Monta/smonta il tuo accampamento",
                "`/caccia` — Descrivi una battuta di caccia",
                "`/pesca` — Descrivi una sessione di pesca",
                "`/rapina` — Tenta una rapina (illegale)",
                "`/furto` — Tenta un furto (illegale)",
                "`/raccolta-marijuana` — Raccogli erba selvatica (illegale)",
                "`/raccolta-cocaina` — Raccogli piante rare (illegale)",
                "`/scoop` — Pubblica sul giornale",
                "`/miafedinapenale` — Visualizza la tua fedina penale",
                "`/mie-proprieta` — Visualizza le tue proprietà",
            ]
        else:
            return

        embed.description = "**Comandi disponibili:**\n\n" + "\n".join(cmds)
        embed.set_footer(text="🤠 Red Dead Redemption II — Lista Comandi")
        view = CommandCategoryView()
        await interaction.response.edit_message(embed=embed, view=view)


class CommandCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CommandCategorySelect())


@bot.tree.command(name="lista-comandi", description="Visualizza tutti i comandi disponibili")
async def lista_comandi(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📜 LISTA COMANDI — RED DEAD REDEMPTION II",
        description=(
            "Benvenuto, cowboy! Seleziona una categoria dal menu qui sotto\n"
            "per visualizzare i comandi disponibili."
        ),
        color=discord.Color(0xDAA520),
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text="🤠 Red Dead Redemption II RP")
    view = CommandCategoryView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

print("✅ Comandi app registrati", flush=True)

# ====================
# WEBSERVER H24
# ====================

async def handle(request):
    return web.Response(text="🤠 Red Dead Redemption II Bot — Online!")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Webserver avviato su porta {port}", flush=True)

# ====================
# ENTRY POINT
# ====================

async def main():
    try:
        print("🌐 Avvio webserver...", flush=True)
        await start_webserver()

        TOKEN = os.getenv("DISCORD_TOKEN")
        if not TOKEN:
            print("❌ DISCORD_TOKEN non trovato!", flush=True)
            return

        print("🔄 Connessione a Discord...", flush=True)
        asyncio.create_task(backup.backup_database())
        print("✅ Backup automatico attivato (ogni 6 ore)", flush=True)

        await bot.start(TOKEN)

    except discord.LoginFailure:
        print("❌ Token Discord non valido!", flush=True)
    except discord.HTTPException as e:
        print(f"❌ ERRORE HTTP Discord: {e}", flush=True)
        if e.status == 429:
            print("⚠️ Rate limited. Riprova tra 30 minuti.", flush=True)
    except Exception as e:
        print(f"❌ ERRORE FATALE: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("🚀 Avvio Red Dead Redemption II Bot...", flush=True)
    print(f"🐍 Python: {sys.version}", flush=True)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Bot spento manualmente.", flush=True)
    except Exception as e:
        print(f"❌ Errore avvio: {e}", flush=True)
        import traceback
        traceback.print_exc()
