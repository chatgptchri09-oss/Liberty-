import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput
import aiosqlite
from datetime import datetime
import database

# ====================
# COSTANTI
# ====================
LFD_ROLE_ID = 1415093546549248040  # Ruolo L.F.D autorizzato
ARREST_LOG_CHANNEL_ID = 1436347936635097179  # Canale log arresti

# ====================
# FUNZIONI DI SUPPORTO
# ====================

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    """Verifica se l'utente ha un determinato ruolo."""
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_arrest(bot, channel_id: int, embed: discord.Embed):
    """Invia il log dell'arresto nel canale specificato."""
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            await channel.send(embed=embed)
    except Exception as e:
        print(f"Errore nel log arresto: {e}")

async def save_arrest_to_db(user_id: str, nome_completo: str, eta: str, residenza: str, motivo: str, pena: str):
    """Salva l'arresto nel database."""
    try:
        async with aiosqlite.connect(database.DATABASE_NAME) as db:
            await db.execute(
                "INSERT INTO arrests (user_id, nome_completo, eta, residenza, motivo, pena, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, nome_completo, eta, residenza, motivo, pena, datetime.utcnow().isoformat())
            )
            await db.commit()
        print(f"[DEBUG] Arresto salvato nel database per user_id: {user_id}")
    except Exception as e:
        print(f"[ERRORE] Impossibile salvare arresto nel DB: {e}")

# ====================
# MODAL PER MODULO ARRESTO
# ====================

class ArrestModal(Modal, title="⛓️ Modulo di Arresto"):
    nome_completo = TextInput(
        label="Nome e Cognome",
        placeholder="Es: Mario Rossi",
        required=True,
        max_length=100
    )
    
    eta = TextInput(
        label="Età",
        placeholder="Inserisci l'età dell'arrestato",
        required=True,
        max_length=3
    )
    
    residenza = TextInput(
        label="Residenza (se presente)",
        placeholder="Inserisci la residenza o lascia vuoto",
        required=False,
        max_length=100
    )
    
    motivo = TextInput(
        label="Motivo Arresto",
        placeholder="Descrivi il motivo dell'arresto",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )
    
    pena = TextInput(
        label="Pena",
        placeholder="Inserisci la pena (es. 5 anni, multa $10,000)",
        required=True,
        max_length=100
    )

    def __init__(self, bot, cittadino: discord.Member):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino

    async def on_submit(self, interaction: discord.Interaction):
        print(f"[DEBUG] Modal submit ricevuto da {interaction.user}")
        
        # Defer per evitare timeout
        try:
            await interaction.response.defer(ephemeral=True)
            print(f"[DEBUG] Defer completato")
        except Exception as e:
            print(f"[ERRORE] Errore nel defer: {e}")
            return
        
        # Prepara i dati
        nome_completo = self.nome_completo.value
        eta_value = self.eta.value
        residenza_value = self.residenza.value if self.residenza.value else "Non specificata"
        motivo_value = self.motivo.value
        pena_value = self.pena.value
        agente = interaction.user.mention
        
        print(f"[DEBUG] Dati raccolti: {nome_completo}, {eta_value}, {residenza_value}")
        
        # Salva l'arresto nel database
        await save_arrest_to_db(
            str(self.cittadino.id),
            nome_completo,
            eta_value,
            residenza_value,
            motivo_value,
            pena_value
        )
        
        # Creazione embed per il log
        embed = discord.Embed(
            title="⛓️‍💥 ARRESTO",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="👮 Agente", value=agente, inline=False)
        embed.add_field(name="🚨 Cittadino Arrestato", value=self.cittadino.mention, inline=False)
        embed.add_field(name="👤 Nome Completo", value=nome_completo, inline=False)
        embed.add_field(name="🎂 Età", value=eta_value, inline=True)
        embed.add_field(name="🏠 Residenza", value=residenza_value, inline=True)
        embed.add_field(name="📋 Motivo Arresto", value=motivo_value, inline=False)
        embed.add_field(name="⚖️ Pena", value=pena_value, inline=False)
        
        embed.set_footer(text="L.F.D - Los Santos Police Department")
        
        print(f"[DEBUG] Embed creato, invio al canale log...")
        
        # Invia il log nel canale
        try:
            await log_arrest(self.bot, ARREST_LOG_CHANNEL_ID, embed)
            print(f"[DEBUG] Log inviato con successo")
        except Exception as e:
            print(f"[ERRORE] Errore nell'invio del log: {e}")
        
        # Conferma all'agente
        try:
            await interaction.followup.send(
                f"✅ Arresto registrato con successo!\n"
                f"**Arrestato:** {nome_completo}\n"
                f"**Pena:** {pena_value}",
                ephemeral=True
            )
            print(f"[DEBUG] Conferma inviata all'agente")
        except Exception as e:
            print(f"[ERRORE] Errore nell'invio della conferma: {e}")

# ====================
# COMANDO /MODULO-ARRESTO
# ====================

def setup_arrest_commands(bot: commands.Bot):
    """Registra il comando modulo-arresto."""
    
    @bot.tree.command(name="modulo-arresto", description="[L.F.D] Registra un arresto")
    @app_commands.describe(cittadino="Il cittadino da arrestare")
    async def modulo_arresto(interaction: discord.Interaction, cittadino: discord.Member):
        print(f"[DEBUG] Comando /modulo-arresto chiamato da {interaction.user}")
        
        # Controllo permessi
        if not has_role(interaction, LFD_ROLE_ID):
            print(f"[DEBUG] {interaction.user} non ha i permessi")
            await interaction.response.send_message(
                "❌ Solo gli agenti del L.F.D possono usare questo comando!",
                ephemeral=True
            )
            return
        
        print(f"[DEBUG] Permessi OK, cittadino selezionato: {cittadino}")
        
        # Controlla se è un bot
        if cittadino.bot:
            print(f"[DEBUG] Tentativo di arrestare un bot")
            await interaction.response.send_message(
                "❌ Non puoi arrestare un bot!",
                ephemeral=True
            )
            return
        
        # Apri il modal
        try:
            print(f"[DEBUG] Apertura modal...")
            modal = ArrestModal(bot, cittadino)
            await interaction.response.send_modal(modal)
            print(f"[DEBUG] Modal inviato con successo")
        except Exception as e:
            print(f"[ERRORE] Errore nell'apertura del modal: {e}")
            await interaction.response.send_message(
                f"❌ Errore nell'apertura del modulo: {e}",
                ephemeral=True
            )
    
    print("✅ Comando /modulo-arresto caricato")
