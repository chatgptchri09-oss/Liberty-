import discord
from discord import app_commands
from discord.ext import commands
import asyncio

# ====================
# COSTANTI
# ====================
AUTHORIZED_ROLE_ID = 1414753824463126611  # Ruolo autorizzato per /rpoff
LOG_CHANNEL_ID = 1415297578022604850  # Canale di log

# ====================
# FUNZIONI DI SUPPORTO
# ====================

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    """Verifica se l'utente ha un determinato ruolo."""
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    """Invia un log nel canale specificato."""
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except Exception as e:
        print(f"Errore nel log: {e}")

# ====================
# COMANDO /RPOFF
# ====================

def setup_rpoff_commands(bot: commands.Bot):
    """Registra i comandi RP Off."""
    
    @bot.tree.command(name="rpoff", description=" Termina la sessione di roleplay")
    async def rpoff(interaction: discord.Interaction):
        # Controllo permessi
        if not has_role(interaction, AUTHORIZED_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai i permessi per utilizzare questo comando!",
                ephemeral=True
            )
            return
        
        # Creazione embed principale
        embed = discord.Embed(
            title="🔴 ROLEPLAY OFF",
            description=(
                "🔴 La sessione di **roleplay è terminata**!\n\n"
                "📌 • Ricorda di eseguire il comando `/fineturno` per ricevere lo stipendio della giornata lavorativa.\n\n"
                "🙏 Grazie per aver giocato con noi su **Liberty City RP**!"
            ),
            color=discord.Color.red()
        )
        
        # Aggiungi immagine (sostituisci con il tuo URL)
        embed.set_image(url="https://cdn.discordapp.com/attachments/1415383066440106096/1438860643636744202/CB9CD8E0-50BC-4878-BF4D-1B63A8DC2F96.png?ex=69186ae6&is=69171966&hm=f890090b7fa98b89ba942518ee46ea028cb62823d92d9284fb9aef299d46ea12&")
        embed.set_footer(text="Rewind RP")
        embed.timestamp = discord.utils.utcnow()
        
        # Invia l'embed
        await interaction.response.send_message(embed=embed)
        
        # Ottieni il canale
        channel = interaction.channel
        
        # Invia i messaggi successivi con delay
        await asyncio.sleep(1)
        await channel.send("@🚶 | Cittadino Di chicago LA SESSIONE È STATA CHIUSA GRAZIE A TUTTI PER AVER GIOCATO")
        
        await asyncio.sleep(1)
        await channel.send("@🚶 | Cittadino Di chicago TI ASPETTIAMO NELLA PROSSIMA SESSIONE!")
        
        await asyncio.sleep(1)
        await channel.send("@🚶 | Cittadino Di chicago NON PERDETEVI IL TURNO! INIZIA IL TUO CON `/fineturno`")
        
        # Log dell'azione
        log_msg = f"🔴 {interaction.user.mention} ha terminato la sessione RP con `/rpoff`"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)
    
    print("✅ Comando /rpoff caricato")
