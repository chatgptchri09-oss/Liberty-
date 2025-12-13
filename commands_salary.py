import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime
import database

# ===================================================================================
# COSTANTI
# ===================================================================================
DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLE_ID = 1414738761207517214
SALARY_REQUEST_CHANNEL_ID = 1449436170160308457
ADMIN_ROLE_ID = 1414735564632231988

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

# ===================================================================================
# SETUP COMANDI
# ===================================================================================
def setup_salary_commands(bot: commands.Bot):
    
    @bot.tree.command(name="inizio-turno", description="Inizia un turno lavorativo")
    @app_commands.describe(
        lavoro="Il ruolo del lavoro",
        stipendio_orario="Stipendio orario in $"
    )
    async def inizio_turno(interaction: discord.Interaction, lavoro: discord.Role, stipendio_orario: int):
        member = interaction.user

        if lavoro not in member.roles:
            await interaction.response.send_message(
                f"❌ Non puoi iniziare un turno come {lavoro.mention} perché non hai quel ruolo!",
                ephemeral=True
            )
            return

        # Validazione stipendio
        if stipendio_orario <= 0:
            await interaction.response.send_message("❌ Lo stipendio deve essere maggiore di 0!", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            # Controlla se esiste già un turno attivo
            async with db.execute(
                "SELECT * FROM work_shifts WHERE user_id = ? AND role_id = ?",
                (str(interaction.user.id), str(lavoro.id))
            ) as cursor:
                existing_shift = await cursor.fetchone()

            if existing_shift:
                await interaction.response.send_message(
                    f"❌ Hai già un turno attivo per {lavoro.mention}!",
                    ephemeral=True
                )
                return

            # Inserisci il nuovo turno con lo stipendio orario
            await db.execute(
                "INSERT INTO work_shifts (user_id, role_id, start_time, hourly_salary) VALUES (?, ?, ?, ?)",
                (str(interaction.user.id), str(lavoro.id), datetime.now().isoformat(), stipendio_orario)
            )
            await db.commit()

        embed = discord.Embed(
            title="<a:Online:1431599470897922069> 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 <a:broom:1431606606763921408>",
            description=f"{interaction.user.mention} ha **INIZIATO** il proprio turno di {lavoro.mention}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)
        await log_command(bot, LOG_CHANNEL_ID, f"🟢 {interaction.user.mention} ha iniziato turno come {lavoro.name} (${stipendio_orario:,}/ora)")

    @bot.tree.command(name="fine-turno", description="Termina un turno lavorativo")
    @app_commands.describe(lavoro="Il ruolo del lavoro")
    async def fine_turno(interaction: discord.Interaction, lavoro: discord.Role):
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT start_time, hourly_salary FROM work_shifts WHERE user_id = ? AND role_id = ?",
                (str(interaction.user.id), str(lavoro.id))
            ) as cursor:
                shift = await cursor.fetchone()

            if not shift:
                await interaction.response.send_message(
                    f"❌ Non hai un turno attivo per {lavoro.mention}!",
                    ephemeral=True
                )
                return

            start_time = datetime.fromisoformat(shift[0])
            hourly_salary = shift[1]
            end_time = datetime.now()
            duration = end_time - start_time

            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            
            # Calcola lo stipendio totale (ore lavorate * stipendio orario)
            total_hours = duration.total_seconds() / 3600
            total_salary = int(total_hours * hourly_salary)

            await db.execute(
                "DELETE FROM work_shifts WHERE user_id = ? AND role_id = ?",
                (str(interaction.user.id), str(lavoro.id))
            )
            await db.commit()

        # Embed di fine turno
        embed = discord.Embed(
            title=" <a:offline:1431606235354107914> 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 <a:cigarette:1431607423256494161>",
            description=(
                f"{interaction.user.mention} ha **TERMINATO** il proprio turno di {lavoro.mention}\n\n"
                f"**Tempo Lavorativo:** {hours}h e {minutes}min\n\n"
                f"💼 **Lo staff è stato avvisato per il pagamento!**"
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)
        await log_command(
            bot,
            LOG_CHANNEL_ID,
            f"🔴 {interaction.user.mention} ha terminato turno come {lavoro.name} ({hours}h {minutes}min)"
        )

        # Embed richiesta stipendio nel canale dedicato
        salary_embed = discord.Embed(
            title="💰 RICHIESTA STIPENDIO",
            color=discord.Color.orange()
        )
        salary_embed.add_field(name="👤 Lavoratore", value=interaction.user.mention, inline=False)
        salary_embed.add_field(name="💼 Lavoro svolto", value=lavoro.mention, inline=False)
        salary_embed.add_field(name="💵 Stipendio da dare", value=f"${total_salary:,}", inline=False)
        salary_embed.add_field(name="⏱️ Ore lavorate", value=f"{hours}h e {minutes}min", inline=False)
        salary_embed.set_footer(text=f"User ID: {interaction.user.id} | Role ID: {lavoro.id}")

        await log_command(bot, SALARY_REQUEST_CHANNEL_ID, message=f"<@&{STAFF_ROLE_ID}>", embed=salary_embed)

    @bot.tree.command(name="cancella-turno", description="[ADMIN] Cancella un turno attivo bloccato")
    @app_commands.describe(
        utente="L'utente di cui cancellare il turno",
        lavoro="Il ruolo del lavoro da cancellare"
    )
    async def cancella_turno(interaction: discord.Interaction, utente: discord.Member, lavoro: discord.Role):
        # Controllo permessi
        if not has_role(interaction, ADMIN_ROLE_ID):
            await interaction.response.send_message("❌ Solo gli admin possono usare questo comando!", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT * FROM work_shifts WHERE user_id = ? AND role_id = ?",
                (str(utente.id), str(lavoro.id))
            ) as cursor:
                shift = await cursor.fetchone()
            
            if not shift:
                await interaction.response.send_message(
                    f"❌ {utente.mention} non ha un turno attivo per {lavoro.mention}!",
                    ephemeral=True
                )
                return
            
            await db.execute(
                "DELETE FROM work_shifts WHERE user_id = ? AND role_id = ?",
                (str(utente.id), str(lavoro.id))
            )
            await db.commit()
        
        await interaction.response.send_message(
            f"✅ Turno cancellato per {utente.mention} - {lavoro.mention}!",
            ephemeral=True
        )
        
        # Log
        await log_command(
            bot,
            LOG_CHANNEL_ID,
            f"🗑️ {interaction.user.mention} ha cancellato il turno di {utente.mention} per {lavoro.name}"
        )

    @bot.tree.command(name="pagastipendio", description="[STAFF] Paga lo stipendio a un utente")
    @app_commands.describe(
        utente="L'utente da pagare",
        somma="L'importo da pagare",
        lavoro="Il ruolo del lavoro"
    )
    async def pagastipendio(interaction: discord.Interaction, utente: discord.Member, somma: int, lavoro: discord.Role):
        # Controllo permessi
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        # Validazione somma
        if somma <= 0:
            await interaction.response.send_message("❌ La somma deve essere maggiore di 0!", ephemeral=True)
            return

        # Aggiorna il saldo dell'utente (aggiungi alla banca)
        user_data = await database.get_user(str(utente.id))
        new_bank = user_data["bank"] + somma
        await database.update_balance(str(utente.id), bank=new_bank)

        # Invia messaggio privato all'utente
        try:
            await utente.send(f"💰 Hai ricevuto il tuo stipendio di **${somma:,}** per il lavoro di {lavoro.mention}!")
        except:
            pass

        # Conferma
        await interaction.response.send_message(
            f"✅ Hai pagato **${somma:,}** a {utente.mention} per {lavoro.mention}!",
            ephemeral=True
        )

        # Log
        await log_command(
            bot,
            LOG_CHANNEL_ID,
            f"💰 {interaction.user.mention} ha pagato ${somma:,} a {utente.mention} per {lavoro.name}"
        )
