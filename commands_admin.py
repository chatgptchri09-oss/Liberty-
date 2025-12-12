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
WHITELISTER_ROLE_ID = 1415090850253246534  # Ruolo Whitelister

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
        await interaction.response.defer(ephemeral=True)
        
        errori = self.errori_input.value
        
        # Crea embed verde
        embed = discord.Embed(
            title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐰𝐡𝐢𝐭𝐞𝐥𝐢𝐬𝐭 <a:si:1433573748891582566>",
            color=discord.Color.green()
        )
        
        embed.add_field(name="𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼<a:casomaiconflecia:1434244328448069642>", value=self.cittadino.mention, inline=True)
        embed.add_field(name="𝗘𝘀𝗶𝘁𝗼<a:casomaiconflecia:1434244328448069642>", value="Whitelist Passata", inline=True)
        embed.add_field(name="𝗘𝗿𝗿𝗼𝗿𝗶<a:casomaiconflecia:1434244328448069642>", value=errori, inline=True)
        embed.add_field(name="𝗩𝗮𝗹𝘂𝘁𝗮𝘁𝗼 𝗱𝗮<a:casomaiconflecia:1434244328448069642>", value=interaction.user.mention, inline=True)
        
        # Immagine whitelist passata SOTTO l'embed
        embed.set_image(url="https://cdn.discordapp.com/attachments/1415106856245923941/1448725386211885199/5DFE5104-36EC-4F82-89F8-99409A912B17.png")
        
        # Invia nel canale con menzione
        await interaction.channel.send(content=self.cittadino.mention, embed=embed)
        
        # RIMUOVI TUTTI I RUOLI (tranne @everyone che non può essere rimosso)
        try:
            # Ottieni tutti i ruoli dell'utente tranne @everyone
            roles_to_remove = [role for role in self.cittadino.roles if role.name != "@everyone"]
            if roles_to_remove:
                await self.cittadino.remove_roles(*roles_to_remove, reason=f"Pulizia ruoli per whitelist passata - valutata da {interaction.user.name}")
        except Exception as e:
            print(f"Errore rimozione ruoli: {e}")
        
        # Aggiungi i nuovi ruoli
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
        
        # Invia DM
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
        
        # Log
        await log_command(self.bot, LOG_CHANNEL_ID, f"✅ {interaction.user.mention} ha fatto passare la whitelist a {self.cittadino.mention} (Ruoli resettati e aggiornati)")

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
        await interaction.response.defer(ephemeral=True)
        
        errori = self.errori_input.value
        motivo = self.motivo_input.value
        
        # Crea embed rosso
        embed = discord.Embed(
            title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐰𝐡𝐢𝐭𝐞𝐥𝐢𝐬𝐭 <a:annulla:1431940396635652146>",
            color=discord.Color.red()
        )
        
        embed.add_field(name="𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼<a:casomaiconflecia:1434244328448069642>", value=self.cittadino.mention, inline=True)
        embed.add_field(name="𝗘𝘀𝗶𝘁𝗼<a:casomaiconflecia:1434244328448069642>", value="Whitelist Rimandata", inline=True)
        embed.add_field(name="𝗘𝗿𝗿𝗼𝗿𝗶<a:casomaiconflecia:1434244328448069642>", value=errori, inline=True)
        embed.add_field(name="𝗠𝗼𝘁𝗶𝘃𝗼<a:casomaiconflecia:1434244328448069642>", value=motivo, inline=True)
        embed.add_field(name="𝗩𝗮𝗹𝘂𝘁𝗮𝘁𝗼 𝗱𝗮<a:casomaiconflecia:1434244328448069642>", value=interaction.user.mention, inline=True)
        
        # Immagine whitelist rimandata SOTTO l'embed
        embed.set_image(url="https://cdn.discordapp.com/attachments/1415106856245923941/1448725897392685148/F518A845-EB0B-4704-894A-A8794FD99E24.png")
        
        # Invia nel canale con menzione
        await interaction.channel.send(content=self.cittadino.mention, embed=embed)
        
        # Invia DM
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
        
        # Log
        await log_command(self.bot, LOG_CHANNEL_ID, f"❌ {interaction.user.mention} ha rimandato la whitelist a {self.cittadino.mention}")

# ====================
# SETUP DEI COMANDI
# ====================

def setup_admin_commands(bot: commands.Bot):
    
    @bot.tree.command(name="whitelister", description="[WHITELISTER] Valuta l'esito di una whitelist")
    @app_commands.describe(
        esito="Seleziona l'esito della whitelist",
        cittadino="Il cittadino da valutare"
    )
    @app_commands.choices(esito=[
        app_commands.Choice(name="Whitelist passata", value="PASSATA"),
        app_commands.Choice(name="Whitelist rimandata", value="RIMANDATA"),
    ])
    async def whitelister(interaction: discord.Interaction, esito: app_commands.Choice[str], cittadino: discord.Member):
        if not has_role(interaction, WHITELISTER_ROLE_ID):
            await interaction.response.send_message("❌ Solo i Whitelister possono usare questo comando!", ephemeral=True)
            return
        
        if cittadino.bot:
            await interaction.response.send_message("❌ Non puoi valutare un bot!", ephemeral=True)
            return
        
        if esito.value == "PASSATA":
            modal = WhitelistPassataModal(bot, cittadino)
        else:  # RIMANDATA
            modal = WhitelistRimandataModal(bot, cittadino)
        
        await interaction.response.send_modal(modal)
    
    # =========================================
    # COMANDO: /add-money
    # =========================================
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
            
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"💵 {interaction.user.mention} ha aggiunto **${importo:,}** a {utente.mention} (Motivo: {motivo})."
            )

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
            
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"🚫 {interaction.user.mention} ha rimosso **${removed_amount:,}** a {utente.mention} (Motivo: {motivo})."
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante la rimozione di denaro: {e}", ephemeral=True)

    @bot.tree.command(name="set-balance", description="[STAFF] Imposta il saldo Cash o Bank di un utente.")
    @app_commands.describe(
        utente="L'utente di cui cambiare il saldo",
        tipo_saldo="Il tipo di saldo da impostare (cash o bank)",
        nuovo_saldo="Il valore numerico da impostare (non negativo)"
    )
    @app_commands.choices(tipo_saldo=[
        app_commands.Choice(name="Contanti (cash)", value="cash"),
        app_commands.Choice(name="Banca (bank)", value="bank"),
    ])
    async def set_balance(interaction: discord.Interaction, utente: discord.Member, tipo_saldo: app_commands.Choice[str], nuovo_saldo: int):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        if nuovo_saldo < 0:
            await interaction.response.send_message("❌ Il saldo non può essere negativo!", ephemeral=True)
            return

        user_id = str(utente.id)
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            current_data = await get_user_data(user_id)
            
            if tipo_saldo.value == "cash":
                sql_column = "cash"
                old_balance = current_data['cash']
                new_balance = nuovo_saldo
            else:
                sql_column = "bank"
                old_balance = current_data['bank']
                new_balance = nuovo_saldo

            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    f"UPDATE users SET {sql_column} = ? WHERE user_id = ?",
                    (new_balance, user_id)
                )
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, cash, bank) VALUES (?, ?, ?)",
                    (user_id, current_data['cash'] if tipo_saldo.value == 'bank' else new_balance, current_data['bank'] if tipo_saldo.value == 'cash' else new_balance)
                )
                await db.commit()
            
            await interaction.followup.send(
                f"✅ Saldo **{tipo_saldo.name}** di {utente.mention} impostato su **${new_balance:,}** (Precedente: ${old_balance:,}).",
                ephemeral=True
            )
            
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"🛠️ {interaction.user.mention} ha impostato il saldo **{tipo_saldo.name}** di {utente.mention} su **${new_balance:,}**."
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante l'impostazione del saldo: {e}", ephemeral=True)

    @bot.tree.command(name="init-user", description="[STAFF] Inizializza un utente (resetta o crea con $0).")
    @app_commands.describe(
        utente="L'utente da inizializzare nel database economico"
    )
    async def init_user(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        user_id = str(utente.id)
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO users (user_id, cash, bank) VALUES (?, 0, 0) ON CONFLICT(user_id) DO UPDATE SET cash = 0, bank = 0",
                    (user_id,)
                )
                await db.commit()
            
            await interaction.followup.send(
                f"✅ Utente {utente.mention} inizializzato/resettato. Saldo Cash: $0, Saldo Bank: $0.",
                ephemeral=True
            )
            
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"🆕 {interaction.user.mention} ha inizializzato/resettato {utente.mention} nel database."
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante l'inizializzazione dell'utente: {e}", ephemeral=True)
