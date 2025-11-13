import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

# ====================
# COSTANTI (DEVONO CORRISPONDERE A QUELLE DI bot.py)
# ====================
DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLE_ID = 1414738761207517214 # Assicurati che l'ID sia corretto

# ====================
# FUNZIONI DI SUPPORTO (Devono essere definite nel tuo file principale)
# ====================

# Funzione per controllare i ruoli (ipotizziamo che sia accessibile)
def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

# Funzione per il logging (ipotizziamo che sia accessibile)
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

# Funzione per recuperare i dati dell'utente (generalmente definita in database.py)
async def get_user_data(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT cash, bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user_data = await cursor.fetchone()
            if user_data:
                return {"cash": user_data[0], "bank": user_data[1]}
            # Se l'utente non esiste, restituisci i saldi iniziali (0, 0)
            return {"cash": 0, "bank": 0}

# ====================
# SETUP DEI COMANDI
# ====================

def setup_admin_commands(bot: commands.Bot):
    
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
            # Recupera i dati correnti
            current_data = await get_user_data(user_id)
            new_bank = current_data['bank'] + importo
            
            # Aggiorna il database
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO users (user_id, cash, bank) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET bank = ?",
                    (user_id, current_data['cash'], new_bank, new_bank)
                )
                await db.commit()
            
            # Invia notifica DM all'utente
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
            
            # Log nel canale generale
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"💵 {interaction.user.mention} ha aggiunto **${importo:,}** a {utente.mention} (Motivo: {motivo})."
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante l'aggiunta di denaro: {e}", ephemeral=True)

    # =========================================
    # COMANDO: /remove-money
    # =========================================
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
            # Recupera i dati correnti
            current_data = await get_user_data(user_id)
            
            # La banca non può andare sotto zero
            new_bank = max(0, current_data['bank'] - importo)
            removed_amount = current_data['bank'] - new_bank
            
            if removed_amount == 0 and current_data['bank'] > 0:
                 await interaction.followup.send(f"❌ Impossibile rimuovere **${importo:,}**: l'utente ha solo **${current_data['bank']:,}** in banca. Nessuna operazione eseguita.", ephemeral=True)
                 return
            
            # Aggiorna il database
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO users (user_id, cash, bank) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET bank = ?",
                    (user_id, current_data['cash'], new_bank, new_bank)
                )
                await db.commit()
            
            # Invia notifica DM all'utente
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
            
            # Log nel canale generale
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"🚫 {interaction.user.mention} ha rimosso **${removed_amount:,}** a {utente.mention} (Motivo: {motivo})."
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante la rimozione di denaro: {e}", ephemeral=True)

    # =========================================
    # COMANDO: /set-balance
    # =========================================
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
            else: # bank
                sql_column = "bank"
                old_balance = current_data['bank']
                new_balance = nuovo_saldo

            # Aggiorna il database
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    f"UPDATE users SET {sql_column} = ? WHERE user_id = ?",
                    (new_balance, user_id)
                )
                # Assicurati che l'utente esista nel DB
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, cash, bank) VALUES (?, ?, ?)",
                    (user_id, current_data['cash'] if tipo_saldo.value == 'bank' else new_balance, current_data['bank'] if tipo_saldo.value == 'cash' else new_balance)
                )
                await db.commit()
            
            
            # Notifica
            await interaction.followup.send(
                f"✅ Saldo **{tipo_saldo.name}** di {utente.mention} impostato su **${new_balance:,}** (Precedente: ${old_balance:,}).",
                ephemeral=True
            )
            
            # Log
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"🛠️ {interaction.user.mention} ha impostato il saldo **{tipo_saldo.name}** di {utente.mention} su **${new_balance:,}**."
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante l'impostazione del saldo: {e}", ephemeral=True)

    # =========================================
    # COMANDO: /init-user
    # =========================================
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
                # Inserisce o aggiorna i saldi a zero
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
            
            
