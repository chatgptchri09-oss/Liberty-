import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import database # Modulo necessario per le operazioni DB

# --- COSTANTI ---
LFD_ROLE_ID = 1415093546549248040
ARREST_CHANNEL_ID = 1436347936635097179 # Canale dove verrà inviato l'Embed di arresto
# ----------------

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    """Controlla se l'utente che interagisce ha un determinato ruolo."""
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

# --- CLASSE MODAL CORRETTA CON DEFER/FOLLOWUP ---
class ArrestModal(discord.ui.Modal, title="🚔 Arresto"):
    name_input = discord.ui.TextInput(
        label="Nome Arrestato",
        placeholder="Inserisci il nome",
        required=True
    )
    surname_input = discord.ui.TextInput(
        label="Cognome Arrestato",
        placeholder="Inserisci il cognome",
        required=True
    )
    age_input = discord.ui.TextInput(
        label="Età",
        placeholder="Inserisci l'età",
        required=True,
        max_length=3
    )
    residence_input = discord.ui.TextInput(
        label="Residenza",
        placeholder="Inserisci la residenza (se presente)",
        required=False
    )
    reason_input = discord.ui.TextInput(
        label="Motivo arresto",
        placeholder="Descrivi il motivo dell'arresto",
        style=discord.TextStyle.paragraph,
        required=True
    )
    penalty_input = discord.ui.TextInput(
        label="Pena",
        placeholder="Inserisci la pena",
        required=True
    )

    def __init__(self, bot, officer: discord.Member):
        # Aggiunto timeout esplicito per robustezza
        super().__init__(timeout=300) 
        self.bot = bot
        self.officer = officer

    async def on_submit(self, interaction: discord.Interaction):
        # 1. RISPOSTA IMMEDIATA (DEFER) per evitare il timeout di 3 secondi
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # Estrazione dei dati (più pulita)
        name_value = self.name_input.value
        surname_value = self.surname_input.value
        age_value = self.age_input.value
        residence_value = self.residence_input.value or "Non specificata"
        reason_value = self.reason_input.value
        penalty_value = self.penalty_input.value

        try:
            # 2. Operazione Database
            await database.create_arrest(
                str(self.officer.id),
                self.officer.display_name,
                name_value,
                surname_value,
                age_value,
                residence_value,
                reason_value,
                penalty_value
            )
            
            # 3. Creazione Embed di Log
            embed = discord.Embed(
                title="🚔 ARRESTO EFFETTUATO",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="👮 Agente", value=self.officer.mention, inline=False)
            embed.add_field(name="👤 Nome", value=name_value, inline=True)
            embed.add_field(name="👤 Cognome", value=surname_value, inline=True)
            embed.add_field(name="🎂 Età", value=age_value, inline=True)
            
            if residence_value != "Non specificata":
                embed.add_field(name="🏠 Residenza", value=residence_value, inline=False)
            
            embed.add_field(name="⚖️ Motivo arresto", value=reason_value, inline=False)
            embed.add_field(name="⏱️ Pena", value=penalty_value, inline=False)
            
            
            # 4. Invio Log
            channel = self.bot.get_channel(ARREST_CHANNEL_ID)
            
            if channel and hasattr(channel, 'send'):
                await channel.send(embed=embed)
                
                # 5. Risposta finale all'utente (Followup)
                await interaction.followup.send(
                    f"<a:spunta:1431937738256552036> Arresto registrato con successo!",
                    ephemeral=True
                )
            else:
                # 5. Fallback in caso di canale non trovato
                await interaction.followup.send(
                    "<a:annulla:1431940396635652146> Arresto registrato nel DB, ma il canale log non è stato trovato!",
                    ephemeral=True
                )

        except Exception as e:
            # Gestione errore in caso di fallimento DB o altro
            await interaction.followup.send(
                f"<a:annulla:1431940396635652146> Errore critico: Impossibile registrare l'arresto. (Dettagli: {str(e)[:50]}...)",
                ephemeral=True
            )

# --- FUNZIONE DI SETUP DEI COMANDI ---
def setup_arrest_commands(bot: commands.Bot):
    
    @bot.tree.command(name="arresto", description="[LFD] Registra un arresto")
    async def arresto(interaction: discord.Interaction):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message(
                "<a:annulla:1431940396635652146> Solo i LFD possono usare questo comando!",
                ephemeral=True
            )
            return
        
        # Apre il Modal (la risposta al Modal è gestita all'interno di ArrestModal)
        modal = ArrestModal(bot, interaction.user)
        await interaction.response.send_modal(modal)
