import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput

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

# ====================
# MODAL PER MODULO ARRESTO
# ====================

class ArrestModal(Modal, title="⛓️ Modulo di Arresto"):
    nome = TextInput(
        label="Nome Arrestato",
        placeholder="Inserisci il nome dell'arrestato",
        required=True,
        max_length=50
    )
    
    cognome = TextInput(
        label="Cognome Arrestato",
        placeholder="Inserisci il cognome dell'arrestato",
        required=True,
        max_length=50
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

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # Defer per evitare timeout
        await interaction.response.defer(ephemeral=True)
        
        # Prepara i dati
        nome_completo = f"{self.nome.value} {self.cognome.value}"
        eta_value = self.eta.value
        residenza_value = self.residenza.value if self.residenza.value else "Non specificata"
        motivo_value = self.motivo.value
        pena_value = self.pena.value
        agente = interaction.user.mention
        
        # Creazione embed per il log
        embed = discord.Embed(
            title="⛓️‍💥 ARRESTO",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="👮 Agente", value=agente, inline=False)
        embed.add_field(name="👤 Nome Completo", value=nome_completo, inline=False)
        embed.add_field(name="🎂 Età", value=eta_value, inline=True)
        embed.add_field(name="🏠 Residenza", value=residenza_value, inline=True)
        embed.add_field(name="📋 Motivo Arresto", value=motivo_value, inline=False)
        embed.add_field(name="⚖️ Pena", value=pena_value, inline=False)
        
        embed.set_footer(text="L.F.D - Los Santos Police Department")
        
        # Invia il log nel canale
        await log_arrest(self.bot, ARREST_LOG_CHANNEL_ID, embed)
        
        # Conferma all'agente
        await interaction.followup.send(
            f"✅ Arresto registrato con successo!\n"
            f"**Arrestato:** {nome_completo}\n"
            f"**Pena:** {pena_value}",
            ephemeral=True
        )

# ====================
# COMANDO /MODULO-ARRESTO
# ====================

def setup_arrest_commands(bot: commands.Bot):
    """Registra il comando modulo-arresto."""
    
    @bot.tree.command(name="modulo-arresto", description="[L.F.D] Registra un arresto")
    async def modulo_arresto(interaction: discord.Interaction):
        # Controllo permessi
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo gli agenti del L.F.D possono usare questo comando!",
                ephemeral=True
            )
            return
        
        # Apri il modal
        modal = ArrestModal(bot)
        await interaction.response.send_modal(modal)
    
    print("✅ Comando /modulo-arresto caricato")
