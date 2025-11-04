import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
# VECCHIO LOG GENERALE (Usato per ControllaTarga, Assicurazione, etc.)
LOG_CHANNEL_ID = 1415297578022604850
# NUOVO LOG DEDICATO (Usato solo per Sequestra/Dissequestra)
VEHICLE_LOG_CHANNEL_ID = 1414759489998946396 
LFD_ROLE_ID = 1415093546549248040
OFFICINA_ROLE_ID = 1415240071216500746

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, content=None, embed=None):
    """Funzione per inviare un messaggio di log (stringa o Embed) a un canale specifico."""
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            # Invia il messaggio. Usa content o embed.
            await channel.send(content=content, embed=embed)
    except Exception as e:
        print(f"Errore nell'invio del log al canale {channel_id}: {e}")
        pass

def setup_vehicle_commands(bot: commands.Bot):
    
    # =================================================================
    # COMANDO: CONTROLLATARGA (LOG GENERALE)
    # =================================================================
    @bot.tree.command(name="controllatarga", description="[LFD] Controlla la targa di un veicolo")
    @app_commands.describe(targa="La targa del veicolo da controllare")
    async def controllatarga(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT * FROM vehicle_registrations WHERE plate = ?",
                (targa,)
            ) as cursor:
                vehicle = await cursor.fetchone()
        
        if not vehicle:
            await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
            return
        
        _, user_id, client_name, client_surname, vehicle_model, plate, insurance, modifications, seized = vehicle
        
        embed = discord.Embed(
            title=f"🚗 CONTROLLO TARGA: {targa}",
            color=discord.Color.blue()
        )
        embed.add_field(name="👤 Proprietario", value=f"{client_name} {client_surname} (<@{user_id}>)", inline=False)
        embed.add_field(name="🚙 Modello", value=vehicle_model, inline=True)
        embed.add_field(name="🔖 Targa", value=plate, inline=True)
        embed.add_field(name="📋 Assicurazione", value="✅ Presente" if insurance else "❌ Assente", inline=False)
        embed.add_field(name="🔧 Modifiche", value=modifications if modifications and modifications != "/////" else "Nessuna", inline=False)
        embed.add_field(name="🚨 Stato", value="⚠️ SEQUESTRATO" if seized else "✅ Regolare", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, content=f"🚗 {interaction.user.mention} ha controllato la targa {targa}")
    
    # =================================================================
    # COMANDO: ASSICURAZIONE (LOG GENERALE)
    # =================================================================
    @bot.tree.command(name="assicurazione", description="[OFFICINA] Gestisci l'assicurazione di un veicolo")
    @app_commands.describe(
        targa="La targa del veicolo",
        stato="Aggiungi o rimuovi l'assicurazione"
    )
    @app_commands.choices(stato=[
        app_commands.Choice(name="Aggiungi", value="aggiungi"),
        app_commands.Choice(name="Rimuovi", value="rimuovi"),
    ])
    async def assicurazione(interaction: discord.Interaction, targa: str, stato: str):
        if not has_role(interaction, OFFICINA_ROLE_ID):
            await interaction.response.send_message("❌ Solo l'Officina può usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT * FROM vehicle_registrations WHERE plate = ?",
                (targa,)
            ) as cursor:
                vehicle = await cursor.fetchone()
            
            if not vehicle:
                await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return
            
            new_insurance_status = 1 if stato == "aggiungi" else 0
            
            await db.execute(
                "UPDATE vehicle_registrations SET insurance = ? WHERE plate = ?",
                (new_insurance_status, targa)
            )
            await db.commit()
        
        action = "aggiunta" if stato == "aggiungi" else "rimossa"
        await interaction.response.send_message(f"✅ Assicurazione {action} per il veicolo con targa **{targa}**!", ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, content=f"📋 {interaction.user.mention} ha {action} l'assicurazione per {targa}")
    
    # =================================================================
    # COMANDO: MODIFICAVEICOLO (LOG GENERALE)
    # =================================================================
    @bot.tree.command(name="modificaveicolo", description="[OFFICINA] Modifica un veicolo")
    @app_commands.describe(
        targa="La targa del veicolo",
        modifiche="Le modifiche applicate al veicolo"
    )
    async def modificaveicolo(interaction: discord.Interaction, targa: str, modifiche: str):
        if not has_role(interaction, OFFICINA_ROLE_ID):
            await interaction.response.send_message("❌ Solo l'Officina può usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT * FROM vehicle_registrations WHERE plate = ?",
                (targa,)
            ) as cursor:
                vehicle = await cursor.fetchone()
            
            if not vehicle:
                await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return
            
            await db.execute(
                "UPDATE vehicle_registrations SET modifications = ? WHERE plate = ?",
                (modifiche, targa)
            )
            await db.commit()
        
        await interaction.response.send_message(f"✅ Modifiche registrate per il veicolo con targa **{targa}**!", ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, content=f"🔧 {interaction.user.mention} ha modificato il veicolo {targa}")
    
    # =================================================================
    # COMANDO: SEQUESTRAVEICOLO (LOG DEDICATO CON EMBED)
    # =================================================================
    @bot.tree.command(name="sequestraveicolo", description="[LFD] Sequestra un veicolo")
    @app_commands.describe(targa="La targa del veicolo da sequestrare")
    async def sequestraveicolo(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT * FROM vehicle_registrations WHERE plate = ?",
                (targa,)
            ) as cursor:
                vehicle = await cursor.fetchone()
            
            if not vehicle:
                await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return
            
            # Recupera le info del proprietario per l'Embed
            _, user_id, client_name, client_surname, _, _, _, _, _ = vehicle
            
            await db.execute(
                "UPDATE vehicle_registrations SET seized = 1 WHERE plate = ?",
                (targa,)
            )
            await db.commit()
        
        # --- CREAZIONE EMBED PER IL LOG SEPARATO ---
        embed = discord.Embed(
            title="🚨 VEICOLO SEQUESTRATO",
            description=f"Il veicolo con targa **{targa}** è stato contrassegnato come sequestrato.",
            color=discord.Color.red() # Colore Rosso
        )
        embed.add_field(name="👮 Esecutore", value=interaction.user.mention, inline=True)
        embed.add_field(name="👤 Proprietario Registrato", value=f"{client_name} {client_surname} (<@{user_id}>)", inline=True)
        embed.set_footer(text=f"ID Utente: {interaction.user.id}")
        
        await interaction.response.send_message(f"✅ Veicolo con targa **{targa}** sequestrato!", ephemeral=True)
        # USA IL LOG SEPARATO ED INVIA L'EMBED
        await log_command(bot, VEHICLE_LOG_CHANNEL_ID, embed=embed)
    
    # =================================================================
    # COMANDO: DISSEQUESTRAVEICOLO (LOG DEDICATO CON EMBED)
    # =================================================================
    @bot.tree.command(name="dissequestraveicolo", description="[LFD] Rimuovi il sequestro da un veicolo")
    @app_commands.describe(targa="La targa del veicolo da dissequestrare")
    async def dissequestraveicolo(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT * FROM vehicle_registrations WHERE plate = ?",
                (targa,)
            ) as cursor:
                vehicle = await cursor.fetchone()
            
            if not vehicle:
                await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return
            
            # Recupera le info del proprietario per l'Embed
            _, user_id, client_name, client_surname, _, _, _, _, _ = vehicle
            
            await db.execute(
                "UPDATE vehicle_registrations SET seized = 0 WHERE plate = ?",
                (targa,)
            )
            await db.commit()
        
        # --- CREAZIONE EMBED PER IL LOG SEPARATO ---
        embed = discord.Embed(
            title="✅ SEQUESTRO RIMOSSO",
            description=f"Il sequestro è stato rimosso dal veicolo con targa **{targa}**.",
            color=discord.Color.green() # Colore Verde
        )
        embed.add_field(name="👮 Esecutore", value=interaction.user.mention, inline=True)
        embed.add_field(name="👤 Proprietario Registrato", value=f"{client_name} {client_surname} (<@{user_id}>)", inline=True)
        embed.set_footer(text=f"ID Utente: {interaction.user.id}")
        
        await interaction.response.send_message(f"✅ Sequestro rimosso dal veicolo con targa **{targa}**!", ephemeral=True)
        # USA IL LOG SEPARATO ED INVIA L'EMBED
        await log_command(bot, VEHICLE_LOG_CHANNEL_ID, embed=embed)
    
    # =================================================================
    # COMANDO: RIMUOVILIBRETTO (LOG GENERALE)
    # =================================================================
    @bot.tree.command(name="rimuovilibretto", description="[LFD] Rimuovi un libretto di circolazione")
    @app_commands.describe(targa="La targa del veicolo")
    async def rimuovilibretto(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            cursor = await db.execute(
                "DELETE FROM vehicle_registrations WHERE plate = ?",
                (targa,)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                await interaction.response.send_message(f"✅ Libretto per il veicolo con targa **{targa}** rimosso!", ephemeral=True)
                await log_command(bot, LOG_CHANNEL_ID, content=f"🗑️ {interaction.user.mention} ha rimosso il libretto del veicolo {targa}")
            else:
                await interaction.response.send_message(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
