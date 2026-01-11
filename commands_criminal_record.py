import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database
from datetime import datetime

LFD_ROLE_ID = 1415093546549248040
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
    except Exception as e:
        print(f"Errore nel log: {e}", flush=True)

async def get_user_arrests(user_id: str):
    try:
        async with aiosqlite.connect(database.DATABASE_NAME) as db:
            cursor = await db.execute(
                "SELECT id, nome_completo, eta, residenza, motivo, pena, created_at FROM arrests WHERE user_id = ?",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        print(f"Errore get_user_arrests: {e}", flush=True)
        return []

async def get_arrests_by_name(nome: str, cognome: str):
    nome_completo_ricerca = f"{nome} {cognome}".lower()
    try:
        async with aiosqlite.connect(database.DATABASE_NAME) as db:
            cursor = await db.execute(
                "SELECT id, user_id, nome_completo, eta, residenza, motivo, pena, created_at FROM arrests"
            )
            rows = await cursor.fetchall()
            matching_arrests = [
                row for row in rows if row[2].lower() == nome_completo_ricerca
            ]
            return matching_arrests
    except Exception as e:
        print(f"Errore get_arrests_by_name: {e}", flush=True)
        return []

async def clear_criminal_record(user_id: str):
    try:
        async with aiosqlite.connect(database.DATABASE_NAME) as db:
            await db.execute("DELETE FROM fines WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM arrests WHERE user_id = ?", (user_id,))
            await db.commit()
    except Exception as e:
        print(f"Errore clear_criminal_record: {e}", flush=True)

async def get_unpaid_fines(user_id: str):
    try:
        async with aiosqlite.connect(database.DATABASE_NAME) as db:
            cursor = await db.execute(
                "SELECT id, name, surname, infractions, fine_amount FROM fines WHERE user_id = ? AND paid = 0",
                (user_id,)
            )
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        print(f"Errore get_unpaid_fines: {e}", flush=True)
        return []

async def get_fines_by_name(nome: str, cognome: str):
    try:
        async with aiosqlite.connect(database.DATABASE_NAME) as db:
            cursor = await db.execute(
                "SELECT id, user_id, name, surname, infractions, fine_amount, paid FROM fines WHERE LOWER(name) = ? AND LOWER(surname) = ?",
                (nome.lower(), cognome.lower())
            )
            rows = await cursor.fetchall()
            return rows
    except Exception as e:
        print(f"Errore get_fines_by_name: {e}", flush=True)
        return []

def setup_criminal_record_commands(bot: commands.Bot):
    
    @bot.tree.command(name="miafedinapenale", description="Visualizza la tua fedina penale")
    async def miafedinapenale(interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            user_id = str(interaction.user.id)
            
            fines = await get_unpaid_fines(user_id)
            arrests = await get_user_arrests(user_id)
            
            embed = discord.Embed(
                title="📂 La Tua Fedina Penale",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            
            if fines:
                multe_text = ""
                for fine_id, name, surname, infractions, fine_amount in fines:
                    infractions_short = infractions[:80] + "..." if len(infractions) > 80 else infractions
                    multe_text += f"🚫 **Multa #{fine_id}** - ${fine_amount:,}\n   *{infractions_short}*\n"
                embed.add_field(name="💸 Multe", value=multe_text.strip(), inline=False)
            else:
                embed.add_field(name="💸 Multe", value="✅ Nessuna multa", inline=False)
            
            if arrests:
                arresti_text = ""
                for arrest_id, nome, eta, residenza, motivo, pena, created_at in arrests:
                    motivo_short = motivo[:80] + "..." if len(motivo) > 80 else motivo
                    arresti_text += f"🚫 **Arresto #{arrest_id}** - Pena: {pena}\n   *{motivo_short}*\n"
                embed.add_field(name="🔒 Arresti", value=arresti_text.strip(), inline=False)
            else:
                embed.add_field(name="🔒 Arresti", value="✅ Nessun arresto", inline=False)
            
            embed.set_footer(text="L.F.D - Los Santos Police Department")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Errore in miafedinapenale: {e}", flush=True)
            try:
                await interaction.followup.send("❌ Si è verificato un errore nel recupero della fedina penale.", ephemeral=True)
            except:
                pass
        
        
    @bot.tree.command(name="cercapersona", description="[L.F.D] Cerca una persona nel database criminale")
    @app_commands.describe(
        nome="Nome della persona da cercare",
        cognome="Cognome della persona da cercare"
    )
    async def cercapersona(interaction: discord.Interaction, nome: str, cognome: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo gli agenti del L.F.D possono usare questo comando!",
                ephemeral=True
            )
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            nome_completo = f"{nome} {cognome}"
            
            fines = await get_fines_by_name(nome, cognome)
            arrests = await get_arrests_by_name(nome, cognome)
            
            if not fines and not arrests:
                await interaction.followup.send(
                    f"🔍 Nessun record trovato per **{nome_completo}** nel database criminale.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🔍 Ricerca: {nome_completo}",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            
            if fines:
                multe_text = ""
                for fine_id, user_id, name, surname, infractions, fine_amount, paid in fines:
                    status = "✅ Pagata" if paid else "❌ Non pagata"
                    infractions_short = infractions[:70] + "..." if len(infractions) > 70 else infractions
                    multe_text += f"🚫 **Multa #{fine_id}** - ${fine_amount:,} ({status})\n   Discord: <@{user_id}>\n   *{infractions_short}*\n\n"
                embed.add_field(name="💸 Multe Trovate", value=multe_text.strip(), inline=False)
            else:
                embed.add_field(name="💸 Multe Trovate", value="✅ Nessuna multa registrata", inline=False)
            
            if arrests:
                arresti_text = ""
                for arrest_id, user_id, nome_comp, eta, residenza, motivo, pena, created_at in arrests:
                    motivo_short = motivo[:70] + "..." if len(motivo) > 70 else motivo
                    arresti_text += f"🚫 **Arresto #{arrest_id}** - Pena: {pena}\n   Discord: <@{user_id}>\n   *{motivo_short}*\n\n"
                embed.add_field(name="🔒 Arresti Trovati", value=arresti_text.strip(), inline=False)
            else:
                embed.add_field(name="🔒 Arresti Trovati", value="✅ Nessun arresto registrato", inline=False)
            
            embed.set_footer(text=f"Ricerca effettuata da {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Errore in cercapersona: {e}", flush=True)
            try:
                await interaction.followup.send("❌ Si è verificato un errore nella ricerca.", ephemeral=True)
            except:
                pass
        
        
    @bot.tree.command(name="puliziafedinapenale", description="[L.F.D] Pulisce la fedina penale di un utente")
    @app_commands.describe(utente="L'utente a cui pulire la fedina penale")
    async def puliziafedinapenale(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo gli agenti del L.F.D possono usare questo comando!",
                ephemeral=True
            )
            return
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            user_id = str(utente.id)
            
            fines = await get_unpaid_fines(user_id)
            arrests = await get_user_arrests(user_id)
            
            if not fines and not arrests:
                await interaction.followup.send(
                    f"ℹ️ {utente.mention} ha già la fedina penale pulita!",
                    ephemeral=True
                )
                return
            
            await clear_criminal_record(user_id)
            
            try:
                dm_embed = discord.Embed(
                    title="✨ FEDINA PENALE PULITA",
                    description=(
                        f"La tua fedina penale è stata **pulita** da {interaction.user.mention}!\n\n"
                        "Tutte le tue multe e arresti sono stati rimossi dal sistema."
                    ),
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.set_footer(text="L.F.D - Los Santos Police Department")
                await utente.send(embed=dm_embed)
                dm_status = "✅ Notifica DM inviata"
            except:
                dm_status = "⚠️ Impossibile inviare DM (bloccati)"
            
            await interaction.followup.send(
                f"✅ Fedina penale di {utente.mention} pulita con successo!\n{dm_status}",
                ephemeral=True
            )
        except Exception as e:
            print(f"Errore in puliziafedinapenale: {e}", flush=True)
            try:
                await interaction.followup.send("❌ Si è verificato un errore nella pulizia della fedina penale.", ephemeral=True)
            except:
                pass
