import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
GIORNALISTA_ROLE_ID = 1431390528725061794

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass

def setup_scoop_command(bot: commands.Bot):
    
    @bot.tree.command(name="scoop", description="[GIORNALISTA] Pubblica uno scoop giornalistico")
    @app_commands.describe(
        titolo="Il titolo dello scoop",
        descrizione="La descrizione dettagliata dello scoop",
        fascia="La fascia di importanza dello scoop",
        giornalista="Il nome del giornalista",
        foto="Foto allegata allo scoop (facoltativa)",
        immagine_link="Link dell'immagine principale (facoltativo)",
        thumbnail_link="Link della thumbnail (facoltativo)"
    )
    @app_commands.choices(fascia=[
        app_commands.Choice(name="Fascia Alta", value="alta"),
        app_commands.Choice(name="Fascia Media", value="media"),
        app_commands.Choice(name="Fascia Bassa", value="bassa"),
    ])
    async def scoop(
        interaction: discord.Interaction,
        titolo: str,
        descrizione: str,
        fascia: app_commands.Choice[str],
        giornalista: str,
        foto: discord.Attachment = None,
        immagine_link: str = None,
        thumbnail_link: str = None
    ):
        # Verifica che l'utente abbia il ruolo giornalista
        if not has_role(interaction, GIORNALISTA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo i giornalisti possono usare questo comando!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Calcola il guadagno in base alla fascia
        parole = len(descrizione.split())
        
        if fascia.value == "bassa":
            guadagno_base = parole * 10
            fascia_nome = "Fascia Bassa"
        elif fascia.value == "media":
            guadagno_base = parole * 20
            fascia_nome = "Fascia Media"
        else:  # alta
            guadagno_base = parole * 30
            fascia_nome = "Fascia Alta"
        
        # Aggiungi bonus foto se presente
        bonus_foto = 400 if foto else 0
        guadagno_totale = guadagno_base + bonus_foto
        
        # Aggiungi il guadagno al database dell'utente
        user_id = str(interaction.user.id)
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_data = await cursor.fetchone()

            if user_data:
                new_bank = user_data[0] + guadagno_totale
                await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_bank, user_id))
            else:
                await db.execute(
                    "INSERT INTO users (user_id, cash, bank) VALUES (?, ?, ?)",
                    (user_id, 0, 20000 + guadagno_totale)
                )
            await db.commit()
        
        # Crea l'embed dello scoop
        embed = discord.Embed(
            title=f"<a:annuncio:1449799366218088508> Nuovo Scoop: {titolo}",
            color=0xff0000
        )
        
        embed.add_field(
            name="**👤 Giornalista**",
            value=f"**{giornalista}**",
            inline=False
        )
        
        embed.add_field(
            name="**📝 Descrizione**",
            value=descrizione,
            inline=False
        )
        
        embed.add_field(
            name="**📊 Fascia**",
            value=f"**{fascia_nome}**",
            inline=True
        )
        
        # Dettagli del guadagno
        guadagno_text = f"**${guadagno_totale:,}**\n"
        guadagno_text += f"└ Parole: {parole} × ${guadagno_base // parole if parole > 0 else 0} = ${guadagno_base:,}"
        if bonus_foto:
            guadagno_text += f"\n└ Bonus Foto: +${bonus_foto:,}"
        
        embed.add_field(
            name="**💰 Guadagno Ricevuto**",
            value=guadagno_text,
            inline=True
        )
        
        # Aggiungi la foto - priorità: foto allegata > link immagine > nessuna
        if foto:
            if foto.content_type and foto.content_type.startswith("image/"):
                embed.set_image(url=foto.url)
            else:
                await interaction.followup.send(
                    "⚠️ L'allegato non è un'immagine valida, continuo senza foto.",
                    ephemeral=True
                )
        elif immagine_link:
            # Se non c'è foto allegata, usa il link fornito
            embed.set_image(url="https://i.postimg.cc/fLQN0GRy/Intro-Weazel-News1.gif")
        
        # Aggiungi thumbnail dal link se fornito
        if thumbnail_link:
            embed.set_thumbnail(url="https://i.postimg.cc/rFVqj2Cs/IMG-4453.gif")
        
        embed.set_footer(text=f"Pubblicato da {interaction.user.display_name}")
        embed.timestamp = discord.utils.utcnow()
        
        # Invia il messaggio con @everyone
        await interaction.followup.send(content="@everyone", embed=embed)
        
        # Invia DM al giornalista
        try:
            dm_embed = discord.Embed(
                title="✅ Scoop Pubblicato!",
                description=f"Il tuo scoop **{titolo}** è stato pubblicato con successo!",
                color=discord.Color.green()
            )
            dm_embed.add_field(
                name="**💰 Guadagno**",
                value=f"Hai guadagnato **${guadagno_totale:,}**!",
                inline=False
            )
            await interaction.user.send(embed=dm_embed)
        except:
            pass
        
        # Log dello scoop
        log_embed = discord.Embed(
            title="📰 LOG SCOOP PUBBLICATO",
            color=0xff0000
        )
        log_embed.add_field(name="👤 Pubblicato da", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="📰 Giornalista", value=giornalista, inline=True)
        log_embed.add_field(name="📝 Titolo", value=titolo, inline=False)
        log_embed.add_field(name="📊 Fascia", value=fascia_nome, inline=True)
        log_embed.add_field(name="💰 Guadagno", value=f"${guadagno_totale:,}", inline=True)
        log_embed.add_field(name="📸 Foto", value="Sì" if foto else "No", inline=True)
        log_embed.add_field(name="📍 Canale", value=interaction.channel.mention, inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
