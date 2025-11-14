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
            title="<a:offline:1431606235354107914> ROLEPLAY OFF",
            description=(
                "<a:offline:1431606235354107914> La sessione di **roleplay è terminata**!\n\n"
                "📌 • Ricorda di eseguire il comando `/fineturno` per ricevere lo stipendio della giornata lavorativa.\n\n"
                "🙏 Grazie per aver giocato con noi su **Liberty City RP**!"
            ),
            color=discord.Color.red()
        )
        
        # Aggiungi immagine (sostituisci con il tuo URL)
        embed.set_image(url="https://cdn.discordapp.com/attachments/1235599658928308264/1250595400226963527/ServerOff.gif?ex=6918667a&is=691714fa&hm=be7932a6069a0f969d08a7d17d61584ba0a23c3ce21c6399e56355909bf56a1e&")
        embed.set_footer(text="Rewind RP")
        embed.timestamp = discord.utils.utcnow()
        
        # Invia l'embed
        await interaction.response.send_message(embed=embed)
        
        # Ottieni il canale
        channel = interaction.channel
        
        # Invia i messaggi successivi con delay
        await asyncio.sleep(1)
        await channel.send("<@&1414752091607535727> LA SESSIONE È STATA CHIUSA GRAZIE A TUTTI PER AVER GIOCATO")
        
        await asyncio.sleep(1)
        await channel.send("<@&1414752091607535727> TI ASPETTIAMO NELLA PROSSIMA SESSIONE!")
        
        await asyncio.sleep(1)
        await channel.send("<@&1414752091607535727> NON PERDETEVI IL TURNO! TERMINA IL TUO CON `/fineturno`")
        
        # Log dell'azione
        log_msg = f"🔴 {interaction.user.mention} ha terminato la sessione RP con `/rpoff`"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)
    
    print("✅ Comando /rpoff caricato")
