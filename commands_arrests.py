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

# --- FUNZIONE DI SETUP DEI COMANDI ---
def setup_arrest_commands(bot: commands.Bot):
    
    @bot.tree.command(name="arresto", description="[LFD] Registra un arresto tramite parametri.")
    @app_commands.describe(
        cittadino="L'utente Discord che deve essere arrestato (Tag obbligatorio)",
        nome="Nome del cittadino (Usato per il DB/Log)",
        cognome="Cognome del cittadino (Usato per il DB/Log)",
        eta="Età del cittadino",
        motivo="Motivo dell'arresto (Dettagliato)",
        pena="Pena o durata della detenzione",
        residenza="Residenza del cittadino (Opzionale)"
    )
    async def arresto(
        interaction: discord.Interaction, 
        cittadino: discord.Member,
        nome: str,
        cognome: str,
        eta: int,
        motivo: str,
        pena: str,
        residenza: str = "Non specificata" # Parametro opzionale
    ):
        
        # 1. Controllo Permessi
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message(
                "<a:annulla:1431940396635652146> Solo i LFD possono usare questo comando!",
                ephemeral=True
            )
            return

        # 2. Risposta Immediata (Defer) per handling DB/Log
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # 3. Preparazione Dati
        officer = interaction.user
        
        # 4. Operazione Database
        try:
            await database.create_arrest(
                str(officer.id),
                officer.display_name,
                nome,
                cognome,
                str(eta),
                residenza,
                motivo,
                pena
            )
            
            # 5. Creazione Embed di Log
            embed = discord.Embed(
                title="🚔 ARRESTO EFFETTUATO",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="👮 Agente", value=officer.mention, inline=False)
            embed.add_field(name="👤 Cittadino Arrestato", value=cittadino.mention, inline=False) # Tag utente
            
            embed.add_field(name="Nome e Cognome", value=f"{nome} {cognome}", inline=True)
            embed.add_field(name="🎂 Età", value=str(eta), inline=True)
            embed.add_field(name="🏠 Residenza", value=residenza, inline=True)
            
            embed.add_field(name="⚖️ Motivo arresto", value=motivo, inline=False)
            embed.add_field(name="⏱️ Pena", value=pena, inline=False)
            embed.timestamp = datetime.now()
            
            # 6. Invio Log e Risposta
            channel = bot.get_channel(ARREST_CHANNEL_ID)
            
            if channel and hasattr(channel, 'send'):
                await channel.send(embed=embed)
                
                # Risposta finale all'utente (Followup)
                await interaction.followup.send(
                    f"<a:spunta:1431937738256552036> Arresto di **{nome} {cognome}** ({cittadino.mention}) registrato con successo!",
                    ephemeral=True
                )
            else:
                # Fallback in caso di canale non trovato
                await interaction.followup.send(
                    f"<a:annulla:1431940396635652146> Arresto di {nome} {cognome} registrato nel DB, ma il canale log non è stato trovato!",
                    ephemeral=True
                )

        except Exception as e:
            # Gestione errore in caso di fallimento DB o altro
            print(f"Errore critico in /arresto: {e}")
            await interaction.followup.send(
                f"<a:annulla:1431940396635652146> Errore critico: Impossibile registrare l'arresto. Controlla il log del bot.",
                ephemeral=True
            )
