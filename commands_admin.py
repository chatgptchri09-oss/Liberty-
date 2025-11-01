import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import math
import database # Importa il modulo database se ne hai bisogno per le funzioni di gestione denaro

# ===================================================================================
# COSTANTI E FUNZIONI DI SUPPORTO
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

# --- NUOVE FUNZIONI DATABASE PER GESTIONE ITEMS ---

async def create_item_db(name: str, required_role_id: str, weight: float):
    """Crea un nuovo item nella tabella 'items' con il peso."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO items (name, required_role_id, weight) VALUES (?, ?, ?)",
            (name, required_role_id, weight)
        )
        await db.commit()

# ===================================================================================
# 🚨 FUNZIONE DI SETUP (TUTTI I COMANDI DEVONO STARE QUI DENTRO) 🚨
# ===================================================================================

def setup_admin_commands(bot: commands.Bot):
    
    # -------------------------------------------------------------------------------
    # NUOVO COMANDO: /nuovo-item (con gestione peso)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="nuovo-item", description="[STAFF] Crea un nuovo oggetto nel database (con peso)")
    @app_commands.describe(
        nome="Nome dell'oggetto (es. Ferro)",
        peso_kg="Peso dell'oggetto in kg (es. 0.010)",
        ruolo_necessario="Il ruolo necessario per craftare/comprare (se presente)"
    )
    async def nuovo_item(interaction: discord.Interaction, nome: str, peso_kg: float, ruolo_necessario: discord.Role = None):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        if peso_kg < 0:
            await interaction.followup.send("❌ Il peso non può essere negativo!", ephemeral=True)
            return

        try:
            role_id = str(ruolo_necessario.id) if ruolo_necessario else "None"
            await create_item_db(nome, role_id, peso_kg)
            
            embed = discord.Embed(
                title="✅ Oggetto creato con successo",
                description=f"L'oggetto **{nome}** è stato aggiunto al database.",
                color=discord.Color.green()
            )
            embed.add_field(name="Peso", value=f"{peso_kg} Kg", inline=True)
            embed.add_field(name="Ruolo richiesto", value=ruolo_necessario.name if ruolo_necessario else "Nessuno", inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            await log_command(bot, LOG_CHANNEL_ID, f"🛠️ {interaction.user.mention} ha creato l'item: {nome} ({peso_kg} Kg)")

        except aiosqlite.IntegrityError:
            await interaction.followup.send(f"❌ Errore: Un oggetto con il nome **{nome}** esiste già!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Si è verificato un errore: {e}", ephemeral=True)

    # -------------------------------------------------------------------------------
    # COMANDO: /grantbackpack (ESEMPIO DI COMANDO PREESISTENTE)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="dai/rimuovi-zaino", description="[STAFF] Dai o togli lo zaino ad un utente")
    @app_commands.describe(utente="L'utente a cui dare/togliere lo zaino", azione="Scegli se dare o togliere")
    @app_commands.choices(azione=[
        app_commands.Choice(name="Dai Zaino (30Kg)", value="grant"),
        app_commands.Choice(name="Togli Zaino (0Kg)", value="revoke"),
    ])
    async def grantbackpack(interaction: discord.Interaction, utente: discord.Member, azione: app_commands.Choice):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        user_id = str(utente.id)
        
        new_status = 1 if azione.value == "grant" else 0
        
        try:
            # Aggiornamento diretto nella tabella users
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO users (user_id, has_backpack) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET has_backpack = excluded.has_backpack",
                    (user_id, new_status)
                )
                await db.commit()
            
            
            action_text = "ha ricevuto lo Zaino (30Kg)" if new_status == 1 else "ha perso lo Zaino (0Kg)"
            
            await interaction.followup.send(f"✅ {utente.mention} {action_text}!", ephemeral=True)
            await log_command(bot, LOG_CHANNEL_ID, f"💼 {interaction.user.mention} ha modificato lo zaino di {utente.mention} ({azione.name})")

        except Exception as e:
            await interaction.followup.send(f"❌ Si è verificato un errore nel database: {e}", ephemeral=True)

    # -------------------------------------------------------------------------------
    # COMANDO: /bando (DAL TUO SNIPPET ORIGINALE)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="bando", description="[STAFF] Gestione Esito Bando Lavorativo")
    @app_commands.describe(cittadino="Il cittadino per cui stabilire l'esito", lavoro="Il ruolo lavorativo")
    @app_commands.choices(esito=[
        app_commands.Choice(name="Assunto", value="assunto"),
        app_commands.Choice(name="Rifiutato", value="rifiutato")
    ])
    async def bando(interaction: discord.Interaction, cittadino: discord.Member, lavoro: discord.Role, esito: app_commands.Choice):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
            
        await interaction.response.defer() 

        if esito.value == "rifiutato":
            embed = discord.Embed(
                title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐛𝐚𝐧𝐝𝐨 <a:annulla:1431940396635652146>",
                description=f"**𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼**<a:casomaiconflecia:1434244328448069642> {cittadino.mention}\n**𝗘𝘀𝗶𝘁𝗼**<a:casomaiconflecia:1434244328448069642> Rifiutato\n**𝗟𝗮𝘃𝗼𝗿𝗼**<a:casomaiconflecia:1434244328448069642> {lavoro.mention}\n\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
                color=discord.Color.red()
            )
            try:
                await cittadino.send(embed=embed)
                await interaction.followup.send(f"✅ Esito di rifiuto inviato per {cittadino.mention}.", ephemeral=True)
            except:
                await interaction.followup.send(f"✅ Esito di rifiuto inviato, ma non sono riuscito a inviare per {cittadino.mention}.", ephemeral=True)
            
            await log_command(bot, LOG_CHANNEL_ID, f"📄 {interaction.user.mention} ha rifiutato il bando di {cittadino.mention} per {lavoro.name}")
            return

        # Logica per assunzione
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
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
        )
        embed.description = description_content

        if success:
            try:
                await cittadino.send(embed=embed)
                await interaction.followup.send(f"✅ Esito di assunzione inviato per {cittadino.mention}.", ephemeral=True)
            except:
                await interaction.followup.send(f"✅ Esito di assunzione inviato, ma non sono riuscito ad aggiungere il ruolo e inviare per {cittadino.mention}.", ephemeral=True)

            await log_command(bot, LOG_CHANNEL_ID, f"📄 {interaction.user.mention} ha assunto {cittadino.mention} per {lavoro.name}")
        else:
            await interaction.followup.send(f"❌ Si è verificato un errore durante l'assunzione di {cittadino.mention}.", ephemeral=True)

    # -------------------------------------------------------------------------------
    # COMANDO: /addcash (ESEMPIO DI COMANDO PREESISTENTE)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="add-money", description="[STAFF] Aggiungi denaro in contanti a un utente")
    @app_commands.describe(utente="L'utente a cui aggiungere denaro", importo="L'importo da aggiungere")
    async def addcash(interaction: discord.Interaction, utente: discord.Member, importo: int):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO users (user_id, cash) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET cash = cash + excluded.cash",
                    (str(utente.id), importo)
                )
                await db.commit()
                
                new_data = await db.execute("SELECT cash FROM users WHERE user_id = ?", (str(utente.id),)).fetchone()
                new_cash = new_data[0] if new_data else importo
            
            await interaction.followup.send(f"✅ Aggiunti **${importo:,}** in contanti a {utente.mention}.", ephemeral=True)
            try:
                await utente.send(f"💵 Lo staff ha aggiunto **${importo:,}** al tuo portafoglio. Nuovo saldo contanti: ${new_cash:,}")
            except:
                pass
            await log_command(bot, LOG_CHANNEL_ID, f"💰 {interaction.user.mention} ha aggiunto ${importo:,} a {utente.mention} (CASH)")

        except Exception as e:
            await interaction.followup.send(f"❌ Si è verificato un errore: {e}", ephemeral=True)
            
    # Includi qui gli altri comandi di gestione denaro o admin (es. /removecash, /addbank, /setbank, ecc.)

    # -------------------------------------------------------------------------------
    # PLACEHOLDER PER ALTRI COMANDI ADMIN
    # -------------------------------------------------------------------------------
    # @bot.tree.command(name="removecash", description="[STAFF] Rimuovi contanti...")
    # ...
    # @bot.tree.command(name="addbank", description="[STAFF] Aggiungi banca...")
    # ...
    
    pass
