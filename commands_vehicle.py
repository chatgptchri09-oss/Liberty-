import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
VEHICLE_LOG_CHANNEL_ID = 1414759489998946396 
LFD_ROLE_ID = 1415093546549248040
OFFICINA_ROLE_ID = 1415240071216500746
LOG_CHANNEL_MODIFICHE_ID = 1457772963867922554

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, content=None, embed=None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            await channel.send(content=content, embed=embed)
    except Exception as e:
        print(f"Errore nell'invio del log al canale {channel_id}: {e}")

def setup_vehicle_commands(bot: commands.Bot):
    
    @bot.tree.command(name="controllatarga", description="[LFD] Controlla la targa di un veicolo")
    @app_commands.describe(targa="La targa del veicolo da controllare")
    async def controllatarga(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT * FROM vehicle_registrations WHERE plate = ?",
                    (targa,)
                ) as cursor:
                    vehicle = await cursor.fetchone()
            
            if not vehicle:
                await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                return
            
            # Gestisci sia veicoli vecchi (9 colonne) che nuovi (10 colonne con illegal)
            if len(vehicle) == 10:
                _, user_id, client_name, client_surname, vehicle_model, plate, insurance, modifications, seized, illegal = vehicle
            else:
                _, user_id, client_name, client_surname, vehicle_model, plate, insurance, modifications, seized = vehicle
                illegal = 0
            
            embed = discord.Embed(
                title=f"🚗 CONTROLLO TARGA: {targa}",
                color=discord.Color.blue()
            )
            embed.add_field(name="👤 Proprietario", value=f"{client_name} {client_surname} (<@{user_id}>)", inline=False)
            embed.add_field(name="🚙 Modello", value=vehicle_model, inline=True)
            embed.add_field(name="🔖 Targa", value=plate, inline=True)
            embed.add_field(name="📋 Assicurazione", value="✅ Presente" if insurance else "❌ Assente", inline=False)
            embed.add_field(name="🔧 Modifiche", value=modifications if modifications and modifications != "/////" else "Nessuna", inline=False)
            
            stato_text = "⚠️ SEQUESTRATO" if seized else "✅ Regolare"
            if illegal:
                stato_text += " 🏴‍☠️ (ILLEGALE)"
            embed.add_field(name="🚨 Stato", value=stato_text, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # LOG CON EMBED
            log_embed = discord.Embed(
                title="🚗 LOG CONTROLLO TARGA",
                color=discord.Color.blue()
            )
            log_embed.add_field(name="👮 Controllato da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🔖 Targa", value=targa, inline=True)
            log_embed.add_field(name="👤 Proprietario", value=f"{client_name} {client_surname} (<@{user_id}>)", inline=False)
            log_embed.add_field(name="🚙 Modello", value=vehicle_model, inline=True)
            log_embed.add_field(name="📋 Assicurazione", value="✅ Presente" if insurance else "❌ Assente", inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in controllatarga: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)
    
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
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT * FROM vehicle_registrations WHERE plate = ?",
                    (targa,)
                ) as cursor:
                    vehicle = await cursor.fetchone()
                
                if not vehicle:
                    await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                    return
                
                new_insurance_status = 1 if stato == "aggiungi" else 0
                
                await db.execute(
                    "UPDATE vehicle_registrations SET insurance = ? WHERE plate = ?",
                    (new_insurance_status, targa)
                )
                await db.commit()
            
            action = "aggiunta" if stato == "aggiungi" else "rimossa"
            await interaction.followup.send(f"✅ Assicurazione {action} per il veicolo con targa **{targa}**!", ephemeral=True)
            
            # LOG CON EMBED
            log_embed = discord.Embed(
                title=f"📋 ASSICURAZIONE {'AGGIUNTA' if stato == 'aggiungi' else 'RIMOSSA'}",
                color=discord.Color.green() if stato == "aggiungi" else discord.Color.red()
            )
            log_embed.add_field(name="👨‍🔧 Eseguito da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🔖 Targa", value=targa, inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_MODIFICHE_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in assicurazione: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)
    
    @bot.tree.command(name="modificaveicolo", description="[OFFICINA] Modifica un veicolo")
    @app_commands.describe(
        targa="La targa del veicolo",
        modifiche="Le modifiche applicate al veicolo"
    )
    async def modificaveicolo(interaction: discord.Interaction, targa: str, modifiche: str):
        if not has_role(interaction, OFFICINA_ROLE_ID):
            await interaction.response.send_message("❌ Solo l'Officina può usare questo comando!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT * FROM vehicle_registrations WHERE plate = ?",
                    (targa,)
                ) as cursor:
                    vehicle = await cursor.fetchone()
                
                if not vehicle:
                    await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                    return
                
                await db.execute(
                    "UPDATE vehicle_registrations SET modifications = ? WHERE plate = ?",
                    (modifiche, targa)
                )
                await db.commit()
            
            await interaction.followup.send(f"✅ Modifiche registrate per il veicolo con targa **{targa}**!", ephemeral=True)
            
            # LOG CON EMBED
            log_embed = discord.Embed(
                title="🔧 MODIFICA VEICOLO",
                color=discord.Color.blue()
            )
            log_embed.add_field(name="👨‍🔧 Eseguito da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🔖 Targa", value=targa, inline=True)
            log_embed.add_field(name="🔧 Modifiche", value=modifiche[:1024], inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_MODIFICHE_ID, embed=log_embed)
        except Exception as e:
            print(f"Errore in modificaveicolo: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)
    
    @bot.tree.command(name="sequestraveicolo", description="[LFD] Sequestra un veicolo")
    @app_commands.describe(targa="La targa del veicolo da sequestrare")
    async def sequestraveicolo(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT * FROM vehicle_registrations WHERE plate = ?",
                    (targa,)
                ) as cursor:
                    vehicle = await cursor.fetchone()
                
                if not vehicle:
                    await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                    return
                
                # Gestisci sia 9 che 10 colonne
                if len(vehicle) >= 9:
                    _, user_id, client_name, client_surname = vehicle[0:4]
                else:
                    await interaction.followup.send("❌ Errore nel formato del veicolo!", ephemeral=True)
                    return
                
                await db.execute(
                    "UPDATE vehicle_registrations SET seized = 1 WHERE plate = ?",
                    (targa,)
                )
                await db.commit()
            
            embed = discord.Embed(
                title="<a:sirena:1431792628332101723> VEICOLO SEQUESTRATO",
                description=f"Il veicolo con targa **{targa}** è stato contrassegnato come sequestrato.",
                color=discord.Color.red()
            )
            embed.add_field(name="👮 Esecutore", value=interaction.user.mention, inline=True)
            embed.add_field(name="👤 Proprietario Registrato", value=f"{client_name} {client_surname} (<@{user_id}>)", inline=True)
            embed.set_footer(text=f"ID Utente: {interaction.user.id}")
            
            await interaction.followup.send(f"✅ Veicolo con targa **{targa}** sequestrato!", ephemeral=True)
            await log_command(bot, VEHICLE_LOG_CHANNEL_ID, embed=embed)
        except Exception as e:
            print(f"Errore in sequestraveicolo: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)
    
    @bot.tree.command(name="dissequestraveicolo", description="[LFD] Rimuovi il sequestro da un veicolo")
    @app_commands.describe(targa="La targa del veicolo da dissequestrare")
    async def dissequestraveicolo(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT * FROM vehicle_registrations WHERE plate = ?",
                    (targa,)
                ) as cursor:
                    vehicle = await cursor.fetchone()
                
                if not vehicle:
                    await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
                    return
                
                # Gestisci sia 9 che 10 colonne
                if len(vehicle) >= 9:
                    _, user_id, client_name, client_surname = vehicle[0:4]
                else:
                    await interaction.followup.send("❌ Errore nel formato del veicolo!", ephemeral=True)
                    return
                
                await db.execute(
                    "UPDATE vehicle_registrations SET seized = 0 WHERE plate = ?",
                    (targa,)
                )
                await db.commit()
            
            embed = discord.Embed(
                title="<a:si:1433573748891582566> SEQUESTRO RIMOSSO",
                description=f"Il sequestro è stato rimosso dal veicolo con targa **{targa}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="👮 Esecutore", value=interaction.user.mention, inline=True)
            embed.add_field(name="👤 Proprietario Registrato", value=f"{client_name} {client_surname} (<@{user_id}>)", inline=True)
            embed.set_footer(text=f"ID Utente: {interaction.user.id}")
            
            await interaction.followup.send(f"✅ Sequestro rimosso dal veicolo con targa **{targa}**!", ephemeral=True)
            await log_command(bot, VEHICLE_LOG_CHANNEL_ID, embed=embed)
        except Exception as e:
            print(f"Errore in dissequestraveicolo: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)
    
    @bot.tree.command(name="rimuovilibretto", description="[LFD] Rimuovi un libretto di circolazione")
    @app_commands.describe(targa="La targa del veicolo")
    async def rimuovilibretto(interaction: discord.Interaction, targa: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                cursor = await db.execute(
                    "DELETE FROM vehicle_registrations WHERE plate = ?",
                    (targa,)
                )
                await db.commit()
                
                if cursor.rowcount > 0:
                    await interaction.followup.send(f"✅ Libretto per il veicolo con targa **{targa}** rimosso!", ephemeral=True)
                    
                    # LOG CON EMBED
                    log_embed = discord.Embed(
                        title="🗑️ LOG LIBRETTO RIMOSSO",
                        color=discord.Color.red()
                    )
                    log_embed.add_field(name="👮 Rimosso da", value=interaction.user.mention, inline=True)
                    log_embed.add_field(name="🔖 Targa", value=targa, inline=True)
                    log_embed.timestamp = discord.utils.utcnow()
                    await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
                else:
                    await interaction.followup.send(f"❌ Nessun veicolo trovato con la targa **{targa}**!", ephemeral=True)
        except Exception as e:
            print(f"Errore in rimuovilibretto: {e}")
            await interaction.followup.send("❌ Si è verificato un errore!", ephemeral=True)
