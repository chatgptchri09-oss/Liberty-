import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import math

# ===================================================================================
# COSTANTI E FUNZIONI DI SUPPORTO
# ===================================================================================

DATABASE_NAME = "economy_bot.db"
# STAFF_ROLE_ID è usato per /add-money e /remove-money (1414738761207517214)
STAFF_ROLE_ID = 1414738761207517214  
# RESET_ROLE_ID è usato per /reset (1414735564632231988)
RESET_ROLE_ID = 1414735564632231988 
LOG_CHANNEL_ID = 1415297578022604850 

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
    except Exception:
        pass


def setup_admin_commands(bot: commands.Bot):
    """Registra i comandi amministrativi al tree del bot."""
    
    # ====================
    # COMANDO: /add-money
    # ====================
    @bot.tree.command(name="add-money", description="[STAFF] Aggiunge soldi al conto bancario di un utente.")
    @app_commands.describe(
        utente="L'utente a cui aggiungere i soldi",
        importo="La cifra da aggiungere (va in Banca)"
    )
    async def add_money(interaction: discord.Interaction, utente: discord.Member, importo: int):
        # 1. Controllo Ruolo (Permesso)
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per usare questo comando. (Richiesto: <@&{STAFF_ROLE_ID}>)", 
                ephemeral=True
            )
            return

        # 2. Validazione
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo da aggiungere deve essere maggiore di zero!", ephemeral=True)
            return
            
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi aggiungere soldi a un bot.", ephemeral=True)
            return
            
        # 3. Aggiornamento Database
        user_id = str(utente.id)
        
        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_data = await cursor.fetchone()

            if user_data:
                # L'utente esiste: aggiorna il saldo in banca
                new_bank = user_data[0] + importo
                await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_bank, user_id))
            else:
                # L'utente non esiste: crea il record
                # Assumo che il saldo iniziale in banca sia 20000 come nel database.py
                initial_bank = 20000
                new_bank = initial_bank + importo
                await db.execute("INSERT OR IGNORE INTO users (user_id, cash, bank, has_backpack) VALUES (?, 0, ?, 0)", (user_id, new_bank))
                
            await db.commit()

        # 4. Risposta e Log
        try:
            await utente.send(f"💸 Lo staff ({interaction.user.mention}) ha accreditato **${importo:,}** sul tuo conto bancario.")
        except:
            pass

        await interaction.followup.send(
            f"✅ Aggiunto **${importo:,}** al conto bancario di **{utente.mention}**.",
        )
        await log_command(bot, LOG_CHANNEL_ID, f"💵 {interaction.user.mention} ha aggiunto ${importo:,} al conto bancario di {utente.mention}")


# All'interno della funzione def setup_admin_commands(bot: commands.Bot):

    # =========================================
    # COMANDO: /annuncio (VERSIONE DEFER/FOLLOWUP)
    # =========================================
    @bot.tree.command(name="annuncio", description="[STAFF] Invia un annuncio nel canale desiderato.")
    @app_commands.describe(
        canale="Canale dove inviare l'annuncio",
        titolo="Titolo dell'annuncio",
        descrizione="Contenuto dell'annuncio",
        colore="Colore dell'annuncio (rosso, verde, blu, giallo, viola, arancione)"
    )
    async def annuncio(
        interaction: discord.Interaction,
        canale: discord.TextChannel,
        titolo: str,
        descrizione: str,
        colore: str
    ):
        STAFF_ROLE_ID = 1414738761207517214
        MENTION_ROLE_ID = 1414752091607535727

        # 1. Controllo permessi
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Non hai i permessi per usare questo comando!", ephemeral=True)
            return

        # 2. RINVIO: Avvisa Discord che stiamo lavorando
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 3. Mappa colori disponibili
        color_map = {
            "rosso": discord.Color.red(),
            "verde": discord.Color.green(),
            "blu": discord.Color.blue(),
            "giallo": discord.Color.gold(),
            "viola": discord.Color.purple(),
            "arancione": discord.Color.orange()
        }

        embed_color = color_map.get(colore.lower(), discord.Color.blurple())

        # 4. Creazione Embed
        embed = discord.Embed(
            title=f"<a:megafono:1431932605984542720> {titolo} <a:megafono:1431932605984542720>",
            description=descrizione,
            color=embed_color
        )

        # Footer con tag dell'autore e la sua immagine
        embed.set_footer(
            text=f"Annuncio inviato da {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        # Thumbnail del server se presente
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        # 5. Invia annuncio nel canale scelto (Operazione I/O che DEVE essere veloce)
        await canale.send(f"<@&{MENTION_ROLE_ID}>", embed=embed)

        # 6. Risposta privata all'autore (Risolve l'interazione)
        await interaction.followup.send(f"✅ Annuncio inviato correttamente in {canale.mention}!", ephemeral=True)

        # 7. Log nel canale di log
        await log_command(bot, LOG_CHANNEL_ID, f"📢 {interaction.user.mention} ha inviato un annuncio in {canale.mention}: **{titolo}**")


    
    # ====================
    # COMANDO: /remove-money
    # ====================
    @bot.tree.command(name="remove-money", description="[STAFF] Rimuovi soldi dal conto bancario di un utente.")
    @app_commands.describe(
        utente="L'utente a cui rimuovere i soldi",
        importo="La cifra da rimuovere (dalla Banca)"
    )
    async def remove_money(interaction: discord.Interaction, utente: discord.Member, importo: int):
        # 1. Controllo Ruolo (Permesso)
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per usare questo comando. (Richiesto: <@&{STAFF_ROLE_ID}>)", 
                ephemeral=True
            )
            return

        # 2. Validazione
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo da rimuovere deve essere maggiore di zero!", ephemeral=True)
            return
            
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi rimuovere soldi a un bot.", ephemeral=True)
            return
            
        # 3. Aggiornamento Database
        user_id = str(utente.id)
        
        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_data = await cursor.fetchone()

            if not user_data:
                # Se l'utente non esiste, lo inseriamo con 0 e terminiamo
                await db.execute("INSERT OR IGNORE INTO users (user_id, cash, bank, has_backpack) VALUES (?, 0, 0, 0)", (user_id,))
                await db.commit()
                await interaction.followup.send(f"❌ {utente.mention} non aveva un saldo in banca, quindi non è stato rimosso nulla.", ephemeral=True)
                return

            current_bank = user_data[0]
            
            # Calcola il nuovo saldo, assicurandosi che non scenda sotto zero
            new_bank = max(0, current_bank - importo)
            
            # Aggiorna il database
            await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_bank, user_id))
            await db.commit()
            
            removed_amount = current_bank - new_bank # Quantità effettivamente rimossa

        # 4. Risposta e Log
        try:
            await utente.send(f"⚠️ Lo staff ({interaction.user.mention}) ha rimosso **${removed_amount:,}** dal tuo conto bancario.")
        except:
            pass
        
        await interaction.followup.send(
            f"✅ Rimosso **${removed_amount:,}** dal conto bancario di **{utente.mention}**."
        )

        await log_command(bot, LOG_CHANNEL_ID, f"➖ {interaction.user.mention} ha rimosso ${removed_amount:,} dal conto bancario di {utente.mention}")

    
    # ====================
    # COMANDO: /reset
    # ====================
    @bot.tree.command(name="reset", description="[STAFF] Rimuovi tutti i soldi (cash e banca) di un utente.")
    @app_commands.describe(utente="L'utente a cui azzerare i soldi")
    async def reset(interaction: discord.Interaction, utente: discord.Member):
        # 1. Controllo Ruolo (Permesso)
        if not has_role(interaction, RESET_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per usare questo comando. (Richiesto: <@&{RESET_ROLE_ID}>)", 
                ephemeral=True
            )
            return

        # 2. Controllo Self-Reset
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi azzerare i soldi di un bot.", ephemeral=True)
            return
            
        # 3. Aggiornamento Database
        user_id = str(utente.id)
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            # Azzeramento di 'cash' e 'bank'
            await db.execute(
                "UPDATE users SET cash = 0, bank = 0 WHERE user_id = ?",
                (user_id,)
            )
            # Se l'utente non esisteva, lo inseriamo con saldo zero
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, cash, bank) VALUES (?, 0, 0)",
                (user_id,)
            )
            await db.commit()
        
        # 4. Risposta e Log
        try:
            await utente.send(f"⚠️ Il tuo saldo (cash e banca) è stato azzerato dallo staff ({interaction.user.mention}).")
        except:
            pass

        await interaction.response.send_message(
            f"✅ Saldo (cash e banca) di **{utente.mention}** azzerato con successo!",
            ephemeral=True
        )

        await log_command(bot, LOG_CHANNEL_ID, f"🔄 {interaction.user.mention} ha azzerato il saldo (cash e banca) di {utente.mention}")
        
    pass


# ===================================================
# MODAL PER IL MOTIVO DI RIFIUTO
# ===================================================
class RifiutoMotivoModal(discord.ui.Modal, title="Motivo del Rifiuto"):
    def __init__(self, citizen: discord.Member, role: discord.Role, staff_id: int, bot: commands.Bot):
        super().__init__()
        self.citizen = citizen
        self.role = role
        self.staff_id = staff_id
        self.bot = bot # Passa il bot al modal per il logging
        
    motivo_input = discord.ui.TextInput(
        label="Motivo del rifiuto del bando",
        style=discord.TextStyle.paragraph,
        placeholder="Specifica il motivo dettagliato per cui il bando è stato rifiutato.",
        required=True,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        motivo = self.motivo_input.value
        
        # 1. Crea l'Embed di Rifiuto
        embed = discord.Embed(
            title="𝐄𝐬𝐢𝐭𝐨 𝐛𝐚𝐧𝐝𝐨",
            color=discord.Color.red()
        )
        
        # 2. Costruisci la descrizione ESATTA (Non è un footer, è descrizione)
        description_content = (
            f"**𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼**: {self.citizen.mention}\n"
            f"**𝗘𝘀𝗶𝘁𝗼**: Rifiutato ❌\n"
            f"**𝗟𝗮𝘃𝗼𝗿𝗼**: {self.role.mention}\n"
            f"**𝗠𝗼𝘁𝗶𝘃𝗼**: {motivo}\n\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬\n"
            # TAG STAFF ROLE ESATTO
            f"Da <@&{STAFF_ROLE_ID}>\n"
            # TAG STAFF UTENTE ESATTO
            f"<@{self.staff_id}>" 
        )
        
        embed.description = description_content
        
        # 3. Risposta di conferma effimera allo staff (RISOLVE L'INTERAZIONE)
        await interaction.response.send_message(f"✅ Esito Rifiutato inviato per {self.citizen.mention}.", ephemeral=True)
        
        # 4. Invio Pubblico nel canale dell'interazione
        await interaction.channel.send(embed=embed)
        
        # 5. Log
        await log_command(
            self.bot, # Usa il bot passato
            LOG_CHANNEL_ID, 
            f"🚫 {interaction.user.mention} ha rifiutato il bando di {self.citizen.mention} per {self.role.name}. Motivo: {motivo[:50]}..."
        )


# =========================================
# COMANDO: /esito-bando
# =========================================
@bot.tree.command(name="esito-bando", description="[STAFF] Gestisce l'esito di un bando lavorativo.")
@app_commands.describe(
    esito="Seleziona l'esito del bando",
    cittadino="La persona che ha partecipato al bando",
    lavoro="Il ruolo del lavoro per cui è stato fatto il bando"
)
@app_commands.choices(esito=[
    app_commands.Choice(name="Assunto", value="ASSUNTO"),
    app_commands.Choice(name="Rifiutato", value="RIFIUTATO"),
])
async def esito_bando(
    interaction: discord.Interaction, 
    esito: app_commands.Choice[str], 
    cittadino: discord.Member, 
    lavoro: discord.Role
):
    # Controllo permessi
    if not has_role(interaction, STAFF_ROLE_ID):
        await interaction.response.send_message("❌ Solo lo Staff può usare questo comando.", ephemeral=True)
        return
    
    # Se l'esito è RIFIUTATO, apri il Modal e termina la funzione qui
    if esito.value == "RIFIUTATO":
        modal = RifiutoMotivoModal(cittadino, lavoro, interaction.user.id, bot) # Passa 'bot'
        await interaction.response.send_modal(modal)
        return 
    
    # --- Logica ASSUNTO (Risposta diretta senza defer) ---
    
    # 1. RISPOSTA RAPIDA: Previene il timeout e conferma subito allo staff
    await interaction.response.send_message(f"✅ Bando Assunto in fase di invio per {cittadino.mention}.", ephemeral=True)

    success = False
    
    # 2. Tenta di aggiungere il ruolo (operazione che può fallire/essere lenta)
    if lavoro not in cittadino.roles:
        try:
            await cittadino.add_roles(lavoro, reason=f"Assunzione tramite bando da parte di {interaction.user.name}")
            success = True
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Non sono riuscito ad aggiungere il ruolo per problemi di permessi.", ephemeral=True)
        except Exception:
            pass
    else:
        success = True
        
    # 3. Crea l'Embed di Assunzione
    embed = discord.Embed(
        title="𝐄𝐬𝐢𝐭𝐨 𝐛𝐚𝐧𝐝𝐨",
        color=discord.Color.green()
    )
    
    # 4. Costruisci la descrizione ESATTA
    description_content = (
        f"**𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼**: {cittadino.mention}\n"
        f"**𝗘𝘀𝗶𝘁𝗼**: Assunto ✅\n"
        f"**𝗟𝗮𝘃𝗼𝗿𝗼**: {lavoro.mention}\n\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"Da <@&{STAFF_ROLE_ID}>\n"
        f"{interaction.user.mention}" 
    )
    
    embed.description = description_content
    
    # 5. Invio Pubblico nel canale dell'interazione
    await interaction.channel.send(embed=embed)
    
    # 6. Log
    await log_command(
        bot, 
        LOG_CHANNEL_ID, 
        f"🟢 {interaction.user.mention} ha assunto {cittadino.mention} per {lavoro.name}. Ruolo aggiunto: {success}"
    )
