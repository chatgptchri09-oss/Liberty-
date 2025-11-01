import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import math

# ===================================================================================
# COSTANTI E FUNZIONI DI SUPPORTO (Devono stare fuori dalla funzione di setup)
# ===================================================================================

DATABASE_NAME = "economy_bot.db"
STAFF_ROLE_ID = 1414738761207517214
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


# ===================================================================================
# 🚨 FUNZIONE DI SETUP (TUTTI I COMANDI DEVONO STARE QUI DENTRO) 🚨
# ===================================================================================

def setup_admin_commands(bot: commands.Bot):
    """Registra i comandi amministrativi al tree del bot."""

    # ===================================================
    # MODAL PER IL MOTIVO DI RIFIUTO (Deve stare qui dentro)
    # ===================================================
    class RifiutoMotivoModal(discord.ui.Modal, title="Motivo del Rifiuto"):
        # Il bot non serve come parametro del Modal se usiamo la funzione di setup
        def __init__(self, citizen: discord.Member, role: discord.Role, staff_id: int): 
            super().__init__()
            self.citizen = citizen
            self.role = role
            self.staff_id = staff_id
            
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
                title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐛𝐚𝐧𝐝𝐨 <a:annulla:1431940396635652146> ",
                color=discord.Color.red()
            )
            
            # 2. Costruisci la descrizione ESATTA
            description_content = (
                f"**𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼**<a:casomaiconflecia:1434244328448069642> {self.citizen.mention}\n"
                f"**𝗘𝘀𝗶𝘁𝗼**<a:casomaiconflecia:1434244328448069642> Rifiutato ❌\n"
                f"**𝗟𝗮𝘃𝗼𝗿𝗼**<a:casomaiconflecia:1434244328448069642> {self.role.mention}\n"
                f"**𝗠𝗼𝘁𝗶𝘃𝗼**<a:casomaiconflecia:1434244328448069642> {motivo}\n\n"
                f"▬▬▬▬▬▬▬▬▬▬▬▬\n"
                f"Da <@&{STAFF_ROLE_ID}>\n"
                f"<@{self.staff_id}>" 
            )
            
            embed.description = description_content
            
            # 3. Risposta di conferma effimera allo staff (RISOLVE L'INTERAZIONE)
            await interaction.response.send_message(f"✅ Esito Rifiutato inviato per {self.citizen.mention}.", ephemeral=True)
            
            # 4. Invio Pubblico nel canale dell'interazione
            await interaction.channel.send(embed=embed)
            
            # 5. Log (Ora usa 'bot' che è accessibile nello scope di setup_admin_commands)
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"🚫 {interaction.user.mention} ha rifiutato il bando di {self.citizen.mention} per {self.role.name}. Motivo: {motivo[:50]}..."
            )
            
    # ==============================================================================
    # ⚠️ PROBLEMA RIGA 96: DEVI INSERIRE QUI IL TUO COMANDO /dai-rimuovi_zaino
    # ⚠️ E assicurati che il parametro con app_commands.choices sia di tipo 'str'.
    # ⚠️ Esempio corretto: async def dai_rimuovi_zaino(..., azione: str, ...)
    # ==============================================================================
    
    # ESEMPIO DELLA CORREZIONE CHE DEVI APPLICARE AL TUO COMANDO /dai-rimuovi_zaino:
    """
    @bot.tree.command(name="dai-rimuovi_zaino", description="[STAFF] Dai o togli lo zaino ad un utente")
    @app_commands.describe(azione="Seleziona l'azione (dai/rimuovi)")
    @app_commands.choices(azione=[
        app_commands.Choice(name="Dai", value="DAI"),
        app_commands.Choice(name="Rimuovi", value="RIMUOVI"),
    ])
    async def dai_rimuovi_zaino(interaction: discord.Interaction, utente: discord.Member, azione: str): # <-- DEVE ESSERE 'str' QUI!
        # Usa 'azione' direttamente, non 'azione.value'
        # ...
    """
    
    # ====================
    # COMANDO: /add-money
    # ====================
    @bot.tree.command(name="add-money", description="[STAFF] Aggiunge soldi al conto bancario di un utente.")
    @app_commands.describe(
        utente="L'utente a cui aggiungere i soldi",
        importo="La cifra da aggiungere (va in Banca)"
    )
    async def add_money(interaction: discord.Interaction, utente: discord.Member, importo: int):
        # ... (Logica di add-money) ...
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per usare questo comando. (Richiesto: <@&{STAFF_ROLE_ID}>)", 
                ephemeral=True
            )
            return

        if importo <= 0:
            await interaction.response.send_message("❌ L'importo da aggiungere deve essere maggiore di zero!", ephemeral=True)
            return
            
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi aggiungere soldi a un bot.", ephemeral=True)
            return
            
        user_id = str(utente.id)
        
        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_data = await cursor.fetchone()

            if user_data:
                new_bank = user_data[0] + importo
                await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_bank, user_id))
            else:
                initial_bank = 20000
                new_bank = initial_bank + importo
                await db.execute("INSERT OR IGNORE INTO users (user_id, cash, bank, has_backpack) VALUES (?, 0, ?, 0)", (user_id, new_bank))
                
            await db.commit()

        try:
            await utente.send(f"💸 Lo staff ({interaction.user.mention}) ha accreditato **${importo:,}** sul tuo conto bancario.")
        except:
            pass

        await interaction.followup.send(
            f"✅ Aggiunto **${importo:,}** al conto bancario di **{utente.mention}**.",
        )
        await log_command(bot, LOG_CHANNEL_ID, f"💵 {interaction.user.mention} ha aggiunto ${importo:,} al conto bancario di {utente.mention}")


    # =========================================
    # COMANDO: /annuncio
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

        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Non hai i permessi per usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        color_map = {
            "rosso": discord.Color.red(),
            "verde": discord.Color.green(),
            "blu": discord.Color.blue(),
            "giallo": discord.Color.gold(),
            "viola": discord.Color.purple(),
            "arancione": discord.Color.orange()
        }

        embed_color = color_map.get(colore.lower(), discord.Color.blurple())

        embed = discord.Embed(
            title=f"<a:megafono:1431932605984542720> {titolo} <a:megafono:1431932605984542720>",
            description=descrizione,
            color=embed_color
        )

        embed.set_footer(
            text=f"Annuncio inviato da {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await canale.send(f"<@&{MENTION_ROLE_ID}>", embed=embed)

        await interaction.followup.send(f"✅ Annuncio inviato correttamente in {canale.mention}!", ephemeral=True)

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
        # ... (Logica di remove-money) ...
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per usare questo comando. (Richiesto: <@&{STAFF_ROLE_ID}>)", 
                ephemeral=True
            )
            return

        if importo <= 0:
            await interaction.response.send_message("❌ L'importo da rimuovere deve essere maggiore di zero!", ephemeral=True)
            return
            
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi rimuovere soldi a un bot.", ephemeral=True)
            return
            
        user_id = str(utente.id)
        
        await interaction.response.defer(ephemeral=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_data = await cursor.fetchone()

            if not user_data:
                await db.execute("INSERT OR IGNORE INTO users (user_id, cash, bank, has_backpack) VALUES (?, 0, 0, 0)", (user_id,))
                await db.commit()
                await interaction.followup.send(f"❌ {utente.mention} non aveva un saldo in banca, quindi non è stato rimosso nulla.", ephemeral=True)
                return

            current_bank = user_data[0]
            new_bank = max(0, current_bank - importo)
            
            await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_bank, user_id))
            await db.commit()
            
            removed_amount = current_bank - new_bank

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
        # ... (Logica di reset) ...
        if not has_role(interaction, RESET_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per usare questo comando. (Richiesto: <@&{RESET_ROLE_ID}>)", 
                ephemeral=True
            )
            return

        if utente.bot:
            await interaction.response.send_message("❌ Non puoi azzerare i soldi di un bot.", ephemeral=True)
            return
            
        user_id = str(utente.id)
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute(
                "UPDATE users SET cash = 0, bank = 0 WHERE user_id = ?",
                (user_id,)
            )
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, cash, bank) VALUES (?, 0, 0)",
                (user_id,)
            )
            await db.commit()
        
        try:
            await utente.send(f"⚠️ Il tuo saldo (cash e banca) è stato azzerato dallo staff ({interaction.user.mention}).")
        except:
            pass

        await interaction.response.send_message(
            f"✅ Saldo (cash e banca) di **{utente.mention}** azzerato con successo!",
            ephemeral=True
        )

        await log_command(bot, LOG_CHANNEL_ID, f"🔄 {interaction.user.mention} ha azzerato il saldo (cash e banca) di {utente.mention}")
        
    
    # =========================================
    # COMANDO: /esito-bando (CORRETTO)
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
        esito: str, # <--- CORREZIONE: DEVE ESSERE 'str'
        cittadino: discord.Member, 
        lavoro: discord.Role
    ):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo Staff può usare questo comando.", ephemeral=True)
            return
        
        # Passiamo il bot al modal per il logging
        if esito == "RIFIUTATO": # <--- CORREZIONE: usiamo 'esito' direttamente
            modal = RifiutoMotivoModal(cittadino, lavoro, interaction.user.id) 
            await interaction.response.send_modal(modal)
            return 
        
        # --- Logica ASSUNTO (Stabile) ---
        
        await interaction.response.send_message(f"✅ Bando Assunto in fase di invio per {cittadino.mention}.", ephemeral=True)

        success = False
        
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
            
        embed = discord.Embed(
            title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐛𝐚𝐧𝐝𝐨 <a:si:1433573748891582566>",
            color=discord.Color.green()
        )
        
        description_content = (
            f"**𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼**<a:casomaiconflecia:1434244328448069642> {cittadino.mention}\n"
            f"**𝗘𝘀𝗶𝘁𝗼**<a:casomaiconflecia:1434244328448069642> Assunto \n"
            f"**𝗟𝗮𝘃𝗼𝗿𝗼**<a:casomaiconflecia:1434244328448069642> {lavoro.mention}\n\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"Da <@&{STAFF_ROLE_ID}>\n"
            f"{interaction.user.mention}" 
        )
        
        embed.description = description_content
        
        await interaction.channel.send(embed=embed)
        
        await log_command(
            bot, 
            LOG_CHANNEL_ID, 
            f"🟢 {interaction.user.mention} ha assunto {cittadino.mention} per {lavoro.name}. Ruolo aggiunto: {success}"
        )
