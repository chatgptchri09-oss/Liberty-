import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput
import aiosqlite
from datetime import datetime
import database

LFD_ROLE_ID = 1415093546549248040
ARREST_LOG_CHANNEL_ID = 1436347936635097179
REPORT_LOG_CHANNEL_ID = 1459208033879195648  # Cambia questo ID con il canale per le denunce

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_arrest(bot, channel_id: int, embed: discord.Embed):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            await channel.send(embed=embed)
    except Exception as e:
        print(f"Errore nel log arresto: {e}")

async def log_report(bot, channel_id: int, embed: discord.Embed):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            await channel.send(embed=embed)
    except Exception as e:
        print(f"Errore nel log denuncia: {e}")

async def save_arrest_to_db(user_id: str, nome_completo: str, eta: str, residenza: str, motivo: str, pena: str):
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

async def save_report_to_db(user_id: str, utente: str, titolo: str, accusato: str, motivo: str, facoltativo: str = ""):
    try:
        async with aiosqlite.connect(database.DATABASE_NAME) as db:
            await db.execute(
                "INSERT INTO reports (user_id, utente, titolo, accusato, motivo, facoltativo, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, utente, titolo, accusato, motivo, facoltativo, datetime.utcnow().isoformat())
            )
            await db.commit()
        print(f"[DEBUG] Denuncia salvata nel database per user_id: {user_id}")
    except Exception as e:
        print(f"[ERRORE] Impossibile salvare denuncia nel DB: {e}")

class ArrestModal(Modal, title="⛓️ Modulo di Arresto"):
    nome_completo = TextInput(label="Nome e Cognome", placeholder="Es: Mario Rossi", required=True, max_length=100)
    eta = TextInput(label="Età", placeholder="Inserisci l'età dell'arrestato", required=True, max_length=3)
    residenza = TextInput(label="Residenza (se presente)", placeholder="Inserisci la residenza o lascia vuoto", required=False, max_length=100)
    motivo = TextInput(label="Motivo Arresto", placeholder="Descrivi il motivo dell'arresto", required=True, style=discord.TextStyle.paragraph, max_length=500)
    pena = TextInput(label="Pena", placeholder="Inserisci la pena (es. 5 anni, multa $10,000)", required=True, max_length=100)

    def __init__(self, bot, cittadino: discord.Member):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino

    async def on_submit(self, interaction: discord.Interaction):
        print(f"[DEBUG] Modal submit ricevuto da {interaction.user}")
        
        try:
            await interaction.response.defer(ephemeral=True)
            print(f"[DEBUG] Defer completato")
        except Exception as e:
            print(f"[ERRORE] Errore nel defer: {e}")
            return
        
        nome_completo = self.nome_completo.value
        eta_value = self.eta.value
        residenza_value = self.residenza.value if self.residenza.value else "Non specificata"
        motivo_value = self.motivo.value
        pena_value = self.pena.value
        agente = interaction.user.mention
        
        print(f"[DEBUG] Dati raccolti: {nome_completo}, {eta_value}, {residenza_value}")
        
        await save_arrest_to_db(
            str(self.cittadino.id),
            nome_completo,
            eta_value,
            residenza_value,
            motivo_value,
            pena_value
        )
        
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
        
        try:
            await log_arrest(self.bot, ARREST_LOG_CHANNEL_ID, embed)
            print(f"[DEBUG] Log inviato con successo")
        except Exception as e:
            print(f"[ERRORE] Errore nell'invio del log: {e}")
        
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

def setup_arrest_commands(bot: commands.Bot):
    
    @bot.tree.command(name="modulo-arresto", description="[L.F.D] Registra un arresto")
    @app_commands.describe(cittadino="Il cittadino da arrestare")
    async def modulo_arresto(interaction: discord.Interaction, cittadino: discord.Member):
        print(f"[DEBUG] Comando /modulo-arresto chiamato da {interaction.user}")
        
        if not has_role(interaction, LFD_ROLE_ID):
            print(f"[DEBUG] {interaction.user} non ha i permessi")
            await interaction.response.send_message(
                "❌ Solo gli agenti del L.F.D possono usare questo comando!",
                ephemeral=True
            )
            return
        
        print(f"[DEBUG] Permessi OK, cittadino selezionato: {cittadino}")
        
        if cittadino.bot:
            print(f"[DEBUG] Tentativo di arrestare un bot")
            await interaction.response.send_message(
                "❌ Non puoi arrestare un bot!",
                ephemeral=True
            )
            return
        
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
    
    @bot.tree.command(name="denuncia", description="[L.F.D] Presenta una denuncia")
    @app_commands.describe(
        utente="Utente che sta facendo la denuncia",
        titolo="Titolo della denuncia",
        accusato="Nome e cognome dell'accusato",
        motivo="Motivo della denuncia",
        facoltativo="Informazioni aggiuntive (opzionale)"
    )
    async def denuncia(
        interaction: discord.Interaction,
        utente: discord.Member,
        titolo: str,
        accusato: str,
        motivo: str,
        facoltativo: str = ""
    ):
        print(f"[DEBUG] Comando /denuncia chiamato da {interaction.user}")
        
        if not has_role(interaction, LFD_ROLE_ID):
            print(f"[DEBUG] {interaction.user} non ha i permessi")
            await interaction.response.send_message(
                "❌ Solo gli agenti del L.F.D possono usare questo comando!",
                ephemeral=True
            )
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            print(f"[DEBUG] Defer completato")
        except Exception as e:
            print(f"[ERRORE] Errore nel defer: {e}")
            return
        
        facoltativo_value = facoltativo if facoltativo else "Nessuna informazione aggiuntiva"
        
        print(f"[DEBUG] Dati denuncia raccolti: {titolo}, {accusato}")
        
        await save_report_to_db(
            str(utente.id),
            utente.mention,
            titolo,
            accusato,
            motivo,
            facoltativo_value
        )
        
        embed = discord.Embed(
            title="📋 DENUNCIA",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="👮 Poliziotto che esegue la denuncia", value=interaction.user.mention, inline=False)
        embed.add_field(name="👤 Utente che ha fatto la denuncia", value=utente.mention, inline=False)
        embed.add_field(name="📌 Titolo", value=titolo, inline=False)
        embed.add_field(name="🎯 Accusato", value=accusato, inline=False)
        embed.add_field(name="📝 Motivo", value=motivo, inline=False)
        embed.add_field(name="ℹ️ Facoltativo", value=facoltativo_value, inline=False)
        
        embed.set_footer(text="L.F.D - Los Santos Police Department")
        
        print(f"[DEBUG] Embed denuncia creato, invio al canale log...")
        
        try:
            await log_report(bot, REPORT_LOG_CHANNEL_ID, embed)
            print(f"[DEBUG] Log denuncia inviato con successo")
        except Exception as e:
            print(f"[ERRORE] Errore nell'invio del log denuncia: {e}")
        
        try:
            await interaction.followup.send(
                f"✅ Denuncia registrata con successo!\n"
                f"**Utente denunciante:** {utente.mention}\n"
                f"**Titolo:** {titolo}\n"
                f"**Accusato:** {accusato}",
                ephemeral=True
            )
            print(f"[DEBUG] Conferma denuncia inviata all'agente")
        except Exception as e:
            print(f"[ERRORE] Errore nell'invio della conferma denuncia: {e}")
    
    print("✅ Comandi /modulo-arresto e /denuncia caricati")
