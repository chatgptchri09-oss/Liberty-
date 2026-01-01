import discord
from discord import app_commands
from discord.ext import commands
import asyncio

# ====================
# COSTANTI
# ====================
AUTHORIZED_ROLE_ID = 1414753824463126611  # Ruolo autorizzato per /rpoff e /rpon
CITIZEN_ROLE_ID = 1414752091607535727  # Ruolo cittadino da menzionare
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
# COMANDI RP STATUS
# ====================

def setup_rpoff_commands(bot: commands.Bot):
    """Registra i comandi RP Status."""
    
    @bot.tree.command(name="rpoff", description="Termina la sessione di roleplay")
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
                "📌 • Ricorda di eseguire il comando `/fine-turno` per ricevere lo stipendio della giornata lavorativa.\n\n"
                "🙏 Grazie per aver giocato con noi su **Liberty RP**!"
            ),
            color=discord.Color.red()
        )
        
        # Aggiungi immagine (sostituisci con il tuo URL)
        embed.set_image(url="https://cdn.discordapp.com/attachments/1235599658928308264/1250595400226963527/ServerOff.gif?ex=6918667a&is=691714fa&hm=be7932a6069a0f969d08a7d17d61584ba0a23c3ce21c6399e56355909bf56a1e&")
        embed.set_footer(text="Liberty RP")
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
        await channel.send("<@&1414752091607535727> NON PERDETEVI IL TURNO! TERMINA IL TUO CON `/fine-turno`")
        

    @bot.tree.command(name="rpon", description="[STAFF] Avvia la sessione di roleplay")
    @app_commands.describe(idps4="L'ID PS4 dell'utente che avvia la sessione")
    async def rpon(interaction: discord.Interaction, idps4: str):
        # Controllo permessi
        if not has_role(interaction, AUTHORIZED_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai i permessi per utilizzare questo comando!",
                ephemeral=True
            )
            return
        
        # Creazione embed principale
        embed = discord.Embed(
            title="<a:Online:1431599470897922069> ROLEPLAY ON",
            description=(
                "💬 La roleplay è **UFFICIALMENTE ON!**\n\n"
                "💃🕺 **DIAMO IL VIA ALLE DANZE!**\n\n"
                "💊 Unisciti alla nostra crew:\n"
                "[Social Club Liberty RP](https://socialclub.rockstargames.com/crew/liberty_full_rp_ps4/hierarchy)\n\n"
                "<a:Online:1431599470897922069> ⏱️ *Avvia il tuo turno con* `/inizio-turno`"
            ),
            color=discord.Color.green()
        )
        
        # Aggiungi immagine ROLEPLAY ON (sostituisci con il tuo URL)
        embed.set_image(url="https://cdn.discordapp.com/attachments/1235599658928308264/1250595400616771614/ServerOn.gif?ex=6918667a&is=691714fa&hm=040de693ddd56f45ef5ee93116185cad03061f91bf9a02b04b5eda504779cd22&")
        embed.set_footer(text="Liberty RP")
        embed.timestamp = discord.utils.utcnow()
        
        # Invia l'embed
        await interaction.response.send_message(embed=embed)
        
        # Ottieni il canale
        channel = interaction.channel
        
        # Primo messaggio: unisciti alla sessione con ID PS4
        await asyncio.sleep(1)
        await channel.send(f"<@&{CITIZEN_ROLE_ID}> Unisciti alla sessione di Roleplay! ID PS4: **{idps4}**")
        
        # Secondo messaggio: segui il link e unisciti
        await asyncio.sleep(1)
        await channel.send(
            f"<@&{CITIZEN_ROLE_ID}> SEGUI IL LINK E UNISCITI A NOI: "
            "https://socialclub.rockstargames.com/crew/liberty_full_rp_ps4/hierarchy"
        )
        
        
        
        # Terzo messaggio: non perdetevi la sessione
        await asyncio.sleep(1)
        await channel.send(f"<@&{CITIZEN_ROLE_ID}> NON PERDETEVI LA SESSIONE! INIZIA IL TUO TURNO CON `/inizio-turno`")

    @bot.tree.command(name="sondaggiorp", description=" Crea un sondaggio per la disponibilità al roleplay")
    @app_commands.describe(orario="L'orario della sessione di roleplay (es. 21:30)")
    async def sondaggiorp(interaction: discord.Interaction, orario: str):
        # Controllo permessi
        if not has_role(interaction, AUTHORIZED_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai i permessi per utilizzare questo comando!",
                ephemeral=True
            )
            return
        
        # Creazione embed del sondaggio
        embed = discord.Embed(
            title=f"🎭 Roleplay attivo alle ore {orario}?",
            description=(
                "Rispondi con una delle seguenti reazioni:\n\n"
                "✅ **Sì**\n"
                "Pronto per il roleplay!\n\n"
                "❌ **No**\n"
                "Non disponibile.\n\n"
                "⏳ **Forse più tardi**\n"
                "Potrei unirmi più tardi.\n\n"
                
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Reagisci con l'emoji corrispondente per indicare la tua disponibilità.")
        embed.timestamp = discord.utils.utcnow()
        
        
        
        
        # Recupera il messaggio per aggiungere le reazioni
        message = await interaction.original_response()
        
        # Aggiungi le reazioni automaticamente
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        await message.add_reaction("⏳")
        
        
