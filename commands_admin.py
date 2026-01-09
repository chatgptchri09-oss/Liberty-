import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

# ====================
# COSTANTI (DEVONO CORRISPONDERE A QUELLE DI bot.py)
# ====================
DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLE_ID = 1414738761207517214
WHITELISTER_ROLE_ID = 1415090850253246534
BACKGROUND_CHANNEL_ID = 1415100952796725268
BACKGROUND_APPROVED_ROLE_ID = 1415102727746490522
LOG_CHANNEL_MONEY_ID = 1459209240450433094

# Ruoli da aggiungere se la whitelist è passata
WL_ROLES = [
    1415375541069942785,
    1414752091607535727,
    1414752276404502730,
    1415375715737538661,
    1415123550624419924
]

# ====================
# FUNZIONI DI SUPPORTO
# ====================

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

async def get_user_data(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT cash, bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user_data = await cursor.fetchone()
            if user_data:
                return {"cash": user_data[0], "bank": user_data[1]}
            return {"cash": 0, "bank": 0}

# ====================
# MODAL PER BACKGROUND
# ====================

class BackgroundModal(discord.ui.Modal, title="Background Personaggio"):
    id_psn = discord.ui.TextInput(
        label="ID PSN",
        placeholder="Inserisci il tuo ID PSN",
        required=True,
        max_length=100
    )
    
    nome_ic = discord.ui.TextInput(
        label="Nome IC",
        placeholder="Inserisci il nome del personaggio",
        required=True,
        max_length=100
    )
    
    cognome_ic = discord.ui.TextInput(
        label="Cognome IC",
        placeholder="Inserisci il cognome del personaggio",
        required=True,
        max_length=100
    )
    
    eta_ic = discord.ui.TextInput(
        label="Età IC",
        placeholder="Inserisci l'età del personaggio",
        required=True,
        max_length=3
    )
    
    storia_pg = discord.ui.TextInput(
        label="Storia del Personaggio",
        placeholder="Racconta la storia del tuo personaggio...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Crea embed con le informazioni
            embed = discord.Embed(
                title="📝 Nuovo Background Inviato",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="👤 Utente Discord", value=interaction.user.mention, inline=False)
            embed.add_field(name="🎮 ID PSN", value=self.id_psn.value, inline=True)
            embed.add_field(name="📛 Nome IC", value=self.nome_ic.value, inline=True)
            embed.add_field(name="📛 Cognome IC", value=self.cognome_ic.value, inline=True)
            embed.add_field(name="🎂 Età IC", value=self.eta_ic.value, inline=True)
            embed.add_field(name="📖 Storia del Personaggio", value=self.storia_pg.value, inline=False)
            embed.set_footer(text=f"ID Utente: {interaction.user.id}")
            embed.timestamp = discord.utils.utcnow()
            
            # Invia nel canale background con tag staff e whitelister
            background_channel = self.bot.get_channel(BACKGROUND_CHANNEL_ID)
            if background_channel:
                await background_channel.send(
                    content=f"<@&{STAFF_ROLE_ID}> <@&{WHITELISTER_ROLE_ID}>",
                    embed=embed
                )
                await interaction.followup.send("✅ Background inviato con successo! Attendi la valutazione.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Errore: canale background non trovato!", ephemeral=True)
        except Exception as e:
            print(f"Errore in BackgroundModal: {e}")
            try:
                await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)
            except:
                pass

# ====================
# MODAL PER BACKGROUND RIFIUTATO
# ====================

class BackgroundRifiutatoModal(discord.ui.Modal, title="Background Rifiutato"):
    motivo_input = discord.ui.TextInput(
        label="Motivo del Rifiuto",
        placeholder="Spiega perché il background è stato rifiutato",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, bot, cittadino: discord.Member):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            motivo = self.motivo_input.value
            
            # Crea embed rosso
            embed = discord.Embed(
                title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐁𝐚𝐜𝐤𝐠𝐫𝐨𝐮𝐧𝐝 <a:annulla:1431940396635652146>",
                description=f"Il background di {self.cittadino.mention} è stato rifiutato.",
                color=discord.Color.red()
            )
            embed.add_field(name="Valutato da <a:casomaiconflecia:1434244328448069642>", value=interaction.user.mention, inline=True)
            embed.add_field(name="Motivo <a:casomaiconflecia:1434244328448069642>", value=motivo, inline=False)
            embed.set_image(url="https://i.postimg.cc/hPHXNnFp/2BB43855-B9BD-4D5B-B755-0902034D9B45.png")
            embed.timestamp = discord.utils.utcnow()
            
            await interaction.channel.send(content=self.cittadino.mention, embed=embed)
            
            # Invia DM all'utente
            try:
                dm_embed = discord.Embed(
                    title="❌ Background Rifiutato",
                    description=f"Il tuo background è stato rifiutato da {interaction.user.mention}.",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Motivo", value=motivo, inline=False)
                dm_embed.add_field(
                    name="Cosa fare ora",
                    value="Rivedi il tuo background seguendo le indicazioni e invialo nuovamente.",
                    inline=False
                )
                await self.cittadino.send(embed=dm_embed)
            except:
                pass
            
            await interaction.followup.send(f"❌ Background rifiutato per {self.cittadino.mention}!", ephemeral=True)
            
            # LOG
            log_embed = discord.Embed(
                title="❌ LOG BACKGROUND RIFIUTATO",
                color=discord.Color.red()
            )
            log_embed.add_field(name="Staff/Whitelister", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Cittadino", value=self.cittadino.mention, inline=True)
            log_embed.add_field(name="Motivo", value=motivo[:200], inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in BackgroundRifiutatoModal: {e}")
            try:
                await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)
            except:
                pass

# ====================
# MODAL PER WHITELIST PASSATA
# ====================

class WhitelistPassataModal(discord.ui.Modal, title="Whitelist Passata"):
    errori_input = discord.ui.TextInput(
        label="Errori",
        placeholder="Descrivi gli errori commessi (se presenti)",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, bot, cittadino: discord.Member):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            errori = self.errori_input.value
            
            # Crea embed verde
            embed = discord.Embed(
                title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐰𝐡𝐢𝐭𝐞𝐥𝐢𝐬𝐭 <a:conferma:1451983464764014733>",
                color=discord.Color.green()
            )
            
            embed.add_field(name="𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼<a:casomaiconflecia:1434244328448069642>", value=self.cittadino.mention, inline=True)
            embed.add_field(name="𝗘𝘀𝗶𝘁𝗼<a:casomaiconflecia:1434244328448069642>", value="Whitelist Passata", inline=True)
            embed.add_field(name="𝗘𝗿𝗿𝗼𝗿𝗶<a:casomaiconflecia:1434244328448069642>", value=errori, inline=True)
            embed.add_field(name="𝗩𝗮𝗹𝘂𝘁𝗮𝘁𝗼 𝗱𝗮<a:casomaiconflecia:1434244328448069642>", value=interaction.user.mention, inline=True)
            
            embed.set_image(url="https://i.postimg.cc/L5jj6kFR/IMG-4265.jpg")
            
            await interaction.channel.send(content=self.cittadino.mention, embed=embed)
            
            try:
                roles_to_remove = [role for role in self.cittadino.roles if role.name != "@everyone"]
                if roles_to_remove:
                    await self.cittadino.remove_roles(*roles_to_remove, reason=f"Pulizia ruoli per whitelist passata - valutata da {interaction.user.name}")
            except Exception as e:
                print(f"Errore rimozione ruoli: {e}")
            
            roles_to_add = []
            for role_id in WL_ROLES:
                role = interaction.guild.get_role(role_id)
                if role:
                    roles_to_add.append(role)
            
            if roles_to_add:
                try:
                    await self.cittadino.add_roles(*roles_to_add, reason=f"Whitelist passata - valutata da {interaction.user.name}")
                except Exception as e:
                    print(f"Errore aggiunta ruoli: {e}")
            
            try:
                dm_embed = discord.Embed(
                    title="✅ Whitelist Passata!",
                    description=f"Congratulazioni! Hai superato la whitelist valutata da {interaction.user.mention}.",
                    color=discord.Color.green()
                )
                dm_embed.add_field(name="Errori riscontrati", value=errori, inline=False)
                await self.cittadino.send(embed=dm_embed)
            except:
                pass
            
            await interaction.followup.send(f"✅ Whitelist passata inviata per {self.cittadino.mention}! Ruoli aggiornati.", ephemeral=True)
            
            # LOG CON EMBED
            log_embed = discord.Embed(
                title="✅ LOG WHITELIST PASSATA",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Valutatore", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Cittadino", value=self.cittadino.mention, inline=True)
            log_embed.add_field(name="Azione", value="Ruoli resettati e aggiornati", inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in WhitelistPassataModal: {e}")
            try:
                await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)
            except:
                pass

# ====================
# MODAL PER WHITELIST RIMANDATA
# ====================

class WhitelistRimandataModal(discord.ui.Modal, title="Whitelist Rimandata"):
    errori_input = discord.ui.TextInput(
        label="Errori",
        placeholder="Descrivi gli errori commessi",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    motivo_input = discord.ui.TextInput(
        label="Motivo",
        placeholder="Spiega il motivo della rimandazione",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self, bot, cittadino: discord.Member):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            errori = self.errori_input.value
            motivo = self.motivo_input.value
            
            embed = discord.Embed(
                title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐰𝐡𝐢𝐭𝐞𝐥𝐢𝐬𝐭 <a:annulla:1431940396635652146>",
                color=discord.Color.red()
            )
            
            embed.add_field(name="𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼<a:casomaiconflecia:1434244328448069642>", value=self.cittadino.mention, inline=True)
            embed.add_field(name="𝗘𝘀𝗶𝘁𝗼<a:casomaiconflecia:1434244328448069642>", value="Whitelist Rimandata", inline=True)
            embed.add_field(name="𝗘𝗿𝗿𝗼𝗿𝗶<a:casomaiconflecia:1434244328448069642>", value=errori, inline=True)
            embed.add_field(name="𝗠𝗼𝘁𝗶𝘃𝗼<a:casomaiconflecia:1434244328448069642>", value=motivo, inline=True)
            embed.add_field(name="𝗩𝗮𝗹𝘂𝘁𝗮𝘁𝗼 𝗱𝗮<a:casomaiconflecia:1434244328448069642>", value=interaction.user.mention, inline=True)
            
            embed.set_image(url="https://i.postimg.cc/G3vDDjVJ/IMG-4266.jpg")
            
            await interaction.channel.send(content=self.cittadino.mention, embed=embed)
            
            try:
                dm_embed = discord.Embed(
                    title="❌ Whitelist Rimandata",
                    description=f"La tua whitelist è stata rimandata da {interaction.user.mention}. Ripassa lo studio e riprova!",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Errori riscontrati", value=errori, inline=False)
                dm_embed.add_field(name="Motivo", value=motivo, inline=False)
                await self.cittadino.send(embed=dm_embed)
            except:
                pass
            
            await interaction.followup.send(f"❌ Whitelist rimandata inviata per {self.cittadino.mention}!", ephemeral=True)
            
            # LOG CON EMBED
            log_embed = discord.Embed(
                title="❌ LOG WHITELIST RIMANDATA",
                color=discord.Color.red()
            )
            log_embed.add_field(name="Valutatore", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Cittadino", value=self.cittadino.mention, inline=True)
            log_embed.add_field(name="Motivo", value=motivo[:100], inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in WhitelistRimandataModal: {e}")
            try:
                await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)
            except:
                pass

# ====================
# SETUP DEI COMANDI
# ====================

def setup_admin_commands(bot: commands.Bot):
    
    @bot.tree.command(name="background", description="Invia il tuo background per la valutazione")
    async def background(interaction: discord.Interaction):
        modal = BackgroundModal(bot)
        await interaction.response.send_modal(modal)
    
    @bot.tree.command(name="whitelister", description="[WHITELISTER] Valuta l'esito di una whitelist o background")
    @app_commands.describe(
        esito="Seleziona l'esito della valutazione",
        cittadino="Il cittadino da valutare"
    )
    @app_commands.choices(esito=[
        app_commands.Choice(name="Whitelist passata", value="PASSATA"),
        app_commands.Choice(name="Whitelist rimandata", value="RIMANDATA"),
        app_commands.Choice(name="Background Positivo", value="BG_POSITIVO"),
        app_commands.Choice(name="Background Rifiutato", value="BG_RIFIUTATO"),
    ])
    async def whitelister(interaction: discord.Interaction, esito: app_commands.Choice[str], cittadino: discord.Member):
        if not has_role(interaction, WHITELISTER_ROLE_ID):
            await interaction.response.send_message("❌ Solo i Whitelister possono usare questo comando!", ephemeral=True)
            return
        
        if cittadino.bot:
            await interaction.response.send_message("❌ Non puoi valutare un bot!", ephemeral=True)
            return
        
        try:
            if esito.value == "PASSATA":
                modal = WhitelistPassataModal(bot, cittadino)
                await interaction.response.send_modal(modal)
            elif esito.value == "RIMANDATA":
                modal = WhitelistRimandataModal(bot, cittadino)
                await interaction.response.send_modal(modal)
            elif esito.value == "BG_POSITIVO":
                # Background positivo NON richiede modal, processa direttamente
                await interaction.response.defer(ephemeral=True)
                
                # Crea embed verde
                embed = discord.Embed(
                    title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐁𝐚𝐜𝐤𝐠𝐫𝐨𝐮𝐧𝐝 <a:conferma:1451983464764014733>",
                    description=f"Il background di {cittadino.mention} è stato approvato!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Valutato da <a:casomaiconflecia:1434244328448069642>", value=interaction.user.mention, inline=True)
                embed.set_image(url="https://i.postimg.cc/JndgKPyX/IMG-4390.png")
                embed.set_footer(text="Preparati per la Whitelist Orale")
                embed.timestamp = discord.utils.utcnow()
                
                await interaction.channel.send(content=cittadino.mention, embed=embed)
                
                # Rimuovi tutti i ruoli
                try:
                    roles_to_remove = [role for role in cittadino.roles if role.name != "@everyone"]
                    if roles_to_remove:
                        await cittadino.remove_roles(*roles_to_remove, reason=f"Background approvato - valutato da {interaction.user.name}")
                except Exception as e:
                    print(f"Errore rimozione ruoli: {e}")
                
                # Aggiungi ruolo background approvato
                approved_role = interaction.guild.get_role(BACKGROUND_APPROVED_ROLE_ID)
                if approved_role:
                    try:
                        await cittadino.add_roles(approved_role, reason=f"Background approvato - valutato da {interaction.user.name}")
                    except Exception as e:
                        print(f"Errore aggiunta ruolo: {e}")
                
                # Invia DM all'utente
                try:
                    dm_embed = discord.Embed(
                        title="✅ Background Approvato!",
                        description=f"Congratulazioni! Il tuo background è stato approvato da {interaction.user.mention}.",
                        color=discord.Color.green()
                    )
                    dm_embed.add_field(
                        name="Prossimo Step",
                        value="Preparati per la **Whitelist Orale**. Verrai contattato a breve!",
                        inline=False
                    )
                    await cittadino.send(embed=dm_embed)
                except:
                    pass
                
                await interaction.followup.send(f"✅ Background approvato per {cittadino.mention}! Ruolo aggiornato.", ephemeral=True)
                
                # LOG
                log_embed = discord.Embed(
                    title="✅ LOG BACKGROUND APPROVATO",
                    color=discord.Color.green()
                )
                log_embed.add_field(name="Valutatore", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Cittadino", value=cittadino.mention, inline=True)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
                
            elif esito.value == "BG_RIFIUTATO":
                modal = BackgroundRifiutatoModal(bot, cittadino)
                await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Errore in whitelister command: {e}")
            try:
                await interaction.response.send_message(f"❌ Errore: {e}", ephemeral=True)
            except:
                try:
                    await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)
                except:
                    pass
    
    @bot.tree.command(name="annuncio", description="[STAFF] Invia un annuncio a tutti i membri del server")
    @app_commands.describe(testo="Il testo dell'annuncio")
    async def annuncio(interaction: discord.Interaction, testo: str):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="<a:annuncio:1449799366218088508> 𝐀𝐍𝐍𝐔𝐍𝐂𝐈𝐎 <a:annuncio:1449799366218088508>",
            description=testo,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Annuncio inviato da {interaction.user.display_name}")
        
        await interaction.channel.send(content="@everyone", embed=embed)
        
        await interaction.followup.send("✅ Annuncio inviato con successo!", ephemeral=True)
        
        # LOG CON EMBED
        
    
    @bot.tree.command(name="add-money", description="[STAFF] Aggiungi soldi al conto bancario di un utente.")
    @app_commands.describe(
        utente="L'utente a cui aggiungere i soldi",
        importo="L'importo da aggiungere",
        motivo="Il motivo per cui si aggiungono i soldi"
    )
    async def add_money(interaction: discord.Interaction, utente: discord.Member, importo: int, motivo: str):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere maggiore di zero!", ephemeral=True)
            return

        if utente.bot:
            await interaction.response.send_message("❌ Non puoi aggiungere soldi ad un bot.", ephemeral=True)
            return
        
        user_id = str(utente.id)
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            current_data = await get_user_data(user_id)
            new_bank = current_data['bank'] + importo
            
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO users (user_id, cash, bank) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET bank = ?",
                    (user_id, current_data['cash'], new_bank, new_bank)
                )
                await db.commit()
            
            try:
                await utente.send(
                    f"💰 Lo staff ha aggiunto **${importo:,}** al tuo conto bancario.\n"
                    f"**Motivo:** {motivo}\n"
                    f"Nuovo saldo in banca: **${new_bank:,}**"
                )
                dm_status = "DM inviato."
            except:
                dm_status = "DM non inviabile."

            await interaction.followup.send(
                f"✅ Aggiunti **${importo:,}** al conto bancario di {utente.mention}. ({dm_status})",
                ephemeral=True
            )
            
            # LOG CON EMBED
            log_embed = discord.Embed(
                title="💵 LOG AGGIUNTA DENARO",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Staff", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Utente", value=utente.mention, inline=True)
            log_embed.add_field(name="Importo", value=f"${importo:,}", inline=True)
            log_embed.add_field(name="Motivo", value=motivo, inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_MONEY_ID, embed=log_embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante l'aggiunta di denaro: {e}", ephemeral=True)

    @bot.tree.command(name="remove-money", description="[STAFF] Rimuovi soldi dal conto bancario di un utente.")
    @app_commands.describe(
        utente="L'utente a cui rimuovere i soldi",
        importo="L'importo da rimuovere",
        motivo="Il motivo della rimozione (es. Multa, Tassa)"
    )
    async def remove_money(interaction: discord.Interaction, utente: discord.Member, importo: int, motivo: str):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere maggiore di zero!", ephemeral=True)
            return

        user_id = str(utente.id)
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            current_data = await get_user_data(user_id)
            new_bank = max(0, current_data['bank'] - importo)
            removed_amount = current_data['bank'] - new_bank
            
            if removed_amount == 0 and current_data['bank'] > 0:
                 await interaction.followup.send(f"❌ Impossibile rimuovere **${importo:,}**: l'utente ha solo **${current_data['bank']:,}** in banca. Nessuna operazione eseguita.", ephemeral=True)
                 return
            
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO users (user_id, cash, bank) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET bank = ?",
                    (user_id, current_data['cash'], new_bank, new_bank)
                )
                await db.commit()
            
            try:
                await utente.send(
                    f"⚠️ Lo staff ha rimosso **${removed_amount:,}** dal tuo conto bancario.\n"
                    f"**Motivo:** {motivo}\n"
                    f"Nuovo saldo in banca: **${new_bank:,}**"
                )
                dm_status = "DM inviato."
            except:
                dm_status = "DM non inviabile."

            await interaction.followup.send(
                f"✅ Rimossi **${removed_amount:,}** dal conto bancario di {utente.mention}. (Nuovo saldo: ${new_bank:,}). ({dm_status})",
                ephemeral=True
            )
            
            # LOG CON EMBED
            log_embed = discord.Embed(
                title="🚫 LOG RIMOZIONE DENARO",
                color=discord.Color.red()
            )
            log_embed.add_field(name="Staff", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Utente", value=utente.mention, inline=True)
            log_embed.add_field(name="Importo", value=f"${removed_amount:,}", inline=True)
            log_embed.add_field(name="Motivo", value=motivo, inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_MONEY_ID, embed=log_embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante la rimozione di denaro: {e}", ephemeral=True)
