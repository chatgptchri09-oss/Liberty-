import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime
import math

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
LFD_ROLE_ID = 1415093546549248040
STAFF_ROLE_ID = 1414738761207517214
SALARY_CHANNEL_ID = 1452975451587870793

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

def setup_rp_commands(bot: commands.Bot):

    @bot.tree.command(name="ammanetto", description="[LFD] Ammanetta un utente")
    @app_commands.describe(utente="L'utente da ammanettare")
    async def ammanetto(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return

        embed = discord.Embed(
            title="<a:manette:1431626831076921507> 𝐀𝐌𝐌𝐀𝐍𝐄𝐓𝐓𝐀𝐌𝐄𝐍𝐓𝐎",
            description=f"{interaction.user.mention} ha ammanettato {utente.mention}\n\n <a:sirena:1431792628332101723><a:attenzione:1431795789205733467> Ha il diritto di rimanere in silenzio, qualsiasi cosa dirà potrà essere utilizzata contro di lei in tribunale. Ha diritto ad un avvocato, se non ne possiede uno gliene verrà fornito uno d'ufficio <a:attenzione:1431795789205733467><a:sirena:1431792628332101723> ",
            color=discord.Color.dark_red()
        )

        await interaction.response.send_message(embed=embed)
        
        log_embed = discord.Embed(
            title="⛓️ LOG AMMANETTAMENTO",
            color=discord.Color.dark_red()
        )
        log_embed.add_field(name="👮 Agente", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Ammanettato", value=utente.mention, inline=True)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

    @bot.tree.command(name="inizio-turno", description="Inizia un turno lavorativo")
    @app_commands.describe(
        lavoro="Il ruolo del lavoro",
        stipendio="Stipendio orario (es. 3800)"
    )
    async def inizio_turno(interaction: discord.Interaction, lavoro: discord.Role, stipendio: int):
        member = interaction.user

        if lavoro not in member.roles:
            await interaction.response.send_message(
                f"❌ Non puoi iniziare un turno come {lavoro.mention} perché non hai quel ruolo!",
                ephemeral=True
            )
            return
        
        if stipendio <= 0:
            await interaction.response.send_message(
                "❌ Lo stipendio orario deve essere maggiore di 0!",
                ephemeral=True
            )
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
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

            await db.execute(
                "INSERT INTO work_shifts (user_id, role_id, start_time, hourly_salary) VALUES (?, ?, ?, ?)",
                (str(interaction.user.id), str(lavoro.id), datetime.now().isoformat(), stipendio)
            )
            await db.commit()

        embed = discord.Embed(
            title="<a:Online:1431599470897922069> 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 <a:broom:1431606606763921408>",
            description=f"{interaction.user.mention} ha **INIZIATO** il proprio turno di {lavoro.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Stipendio Orario", value=f"${stipendio:,}", inline=False)

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="fine-turno", description="Termina un turno lavorativo")
    @app_commands.describe(lavoro="Il ruolo del lavoro da terminare")
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

            total_seconds = duration.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            
            # Calcola ore arrotondate: se minuti >= 31, arrotonda per eccesso
            if minutes >= 31:
                rounded_hours = hours + 1
            else:
                rounded_hours = hours
            
            # Calcola stipendio totale
            total_salary = rounded_hours * hourly_salary

            await db.execute(
                "DELETE FROM work_shifts WHERE user_id = ? AND role_id = ?",
                (str(interaction.user.id), str(lavoro.id))
            )
            await db.commit()

        # Embed nel canale corrente
        embed = discord.Embed(
            title=" <a:offline:1431606235354107914> 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 <a:cigarette:1431607423256494161>",
            description=(
                f"{interaction.user.mention} ha **TERMINATO** il proprio turno di {lavoro.mention}\n\n"
                f"**Tempo Lavorativo:** {hours}h e {minutes}min\n"
                f"**Ore Arrotondate:** {rounded_hours}h\n"
                f"**Stipendio Guadagnato:** ${total_salary:,}"
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)
        
        # Embed nel canale stipendi per lo staff
        salary_channel = bot.get_channel(SALARY_CHANNEL_ID)
        if salary_channel:
            salary_embed = discord.Embed(
                title="💰 Richiesta Pagamento Stipendio",
                color=discord.Color.gold()
            )
            salary_embed.add_field(name="👤 Dipendente", value=interaction.user.mention, inline=False)
            salary_embed.add_field(name="💼 Lavoro", value=lavoro.mention, inline=False)
            salary_embed.add_field(name="⏱️ Ore Lavorate", value=f"{rounded_hours}h", inline=True)
            salary_embed.add_field(name="💵 Stipendio Orario", value=f"${hourly_salary:,}", inline=True)
            salary_embed.add_field(name="💰 Totale da Pagare", value=f"**${total_salary:,}**", inline=False)
            salary_embed.set_footer(text=f"ID Utente: {interaction.user.id}")
            salary_embed.timestamp = discord.utils.utcnow()
            
            await salary_channel.send(
                content=f"<@&{STAFF_ROLE_ID}>\n{lavoro.mention} paga lo stipendio",
                embed=salary_embed
            )

    @bot.tree.command(name="paga-stipendio", description="[STAFF] Paga lo stipendio a un dipendente")
    @app_commands.describe(
        utente="L'utente a cui pagare lo stipendio",
        lavoro="Il lavoro svolto",
        stipendio="L'importo da pagare"
    )
    async def paga_stipendio(interaction: discord.Interaction, utente: discord.Member, lavoro: discord.Role, stipendio: int):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        if stipendio <= 0:
            await interaction.response.send_message("❌ Lo stipendio deve essere maggiore di 0!", ephemeral=True)
            return
        
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi pagare uno stipendio a un bot!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        user_id = str(utente.id)
        
        # Aggiungi soldi al database
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_data = await cursor.fetchone()

            if user_data:
                new_bank = user_data[0] + stipendio
                await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_bank, user_id))
            else:
                await db.execute(
                    "INSERT INTO users (user_id, cash, bank) VALUES (?, ?, ?)",
                    (user_id, 0, 20000 + stipendio)
                )
            await db.commit()
        
        # Invia DM all'utente
        try:
            dm_embed = discord.Embed(
                title="💰 Stipendio Ricevuto!",
                description=f"Hai ricevuto il tuo stipendio da {interaction.user.mention}",
                color=discord.Color.green()
            )
            dm_embed.add_field(name="💼 Lavoro", value=lavoro.mention, inline=False)
            dm_embed.add_field(name="💵 Importo", value=f"**${stipendio:,}**", inline=False)
            dm_embed.add_field(name="👮 Pagato da", value=interaction.user.mention, inline=False)
            dm_embed.set_footer(text="Controlla il tuo saldo con /bancomat")
            await utente.send(embed=dm_embed)
            dm_status = "DM inviato."
        except:
            dm_status = "DM non inviabile."

        await interaction.followup.send(
            f"✅ Stipendio di **${stipendio:,}** pagato a {utente.mention} per {lavoro.mention}! ({dm_status})",
            ephemeral=True
        )
        
        # LOG
        log_embed = discord.Embed(
            title="💰 LOG STIPENDIO PAGATO",
            color=discord.Color.green()
        )
        log_embed.add_field(name="👮 Pagato da", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Dipendente", value=utente.mention, inline=True)
        log_embed.add_field(name="💼 Lavoro", value=lavoro.mention, inline=False)
        log_embed.add_field(name="💵 Importo", value=f"${stipendio:,}", inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

    @bot.tree.command(name="anonimo", description="Invia un messaggio anonimo")
    @app_commands.describe(messaggio="Il messaggio da inviare anonimamente")
    async def anonimo(interaction: discord.Interaction, messaggio: str):
        embed = discord.Embed(
            title="<a:Hacked:1431683990443786240> 𝝰𝛈𝞂𝛈𝖏𝒎𝞂 <a:Skullhack:1431684263056638154>",
            description=messaggio,
            color=discord.Color.dark_gray()
        )

        await interaction.response.send_message("✅ Messaggio anonimo inviato!", ephemeral=True)
        await interaction.channel.send(embed=embed)
        
        log_embed = discord.Embed(
            title="💀 LOG MESSAGGIO ANONIMO",
            color=discord.Color.dark_gray()
        )
        log_embed.add_field(name="👤 Scritto da", value=interaction.user.mention, inline=False)
        log_embed.add_field(name="📝 Messaggio", value=messaggio[:1024], inline=False)
        log_embed.add_field(name="📍 Canale", value=interaction.channel.mention, inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
    
    @bot.tree.command(name="nascondo", description="Nascondi un oggetto in una posizione specifica")
    @app_commands.describe(
        oggetto="L'oggetto da nascondere",
        posizione="La posizione dove nasconderlo",
        foto="Foto del luogo nel quale si nasconde l'oggetto"
    )
    async def nascondo(
        interaction: discord.Interaction,
        oggetto: str,
        posizione: str,
        foto: discord.Attachment
    ):
        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Devi allegare un'immagine valida!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔍 Oggetto Nascosto",
            color=discord.Color.blue()
        )
        embed.add_field(name="📦 Oggetto", value=oggetto, inline=False)
        embed.add_field(name="📍 Posizione", value=posizione, inline=False)
        embed.set_image(url=foto.url)

        await interaction.response.send_message(embed=embed)
        
        log_embed = discord.Embed(
            title="🔍 LOG OGGETTO NASCOSTO",
            color=discord.Color.blue()
        )
        log_embed.add_field(name="👤 Nascosto da", value=interaction.user.mention, inline=False)
        log_embed.add_field(name="📦 Oggetto", value=oggetto, inline=True)
        log_embed.add_field(name="📍 Posizione", value=posizione, inline=True)
        log_embed.set_thumbnail(url=foto.url)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

    @bot.tree.command(name="me", description="Esegui un'azione RP visibile a tutti.")
    @app_commands.describe(azione="L'azione che vuoi eseguire")
    async def me(interaction: discord.Interaction, azione: str):
        
        embed = discord.Embed(
            title="<a:Ciak:1431629051545653369> 𝐀𝐳𝐢𝐨𝐧𝐞 <a:Progress:1431681998250049686> ",
            description=f"{interaction.user.mention}: *{azione}*",
            color=discord.Color.from_rgb(44, 47, 51)
        )

        await interaction.response.send_message("✅ Azione RP inviata!", ephemeral=True)
        await interaction.channel.send(embed=embed)
    
    @bot.tree.command(name="revoca-patente", description="[LFD] Rimuovi la licenza di guida a un utente.")
    @app_commands.describe(utente="L'utente a cui revocare la patente")
    async def revoca_patente(interaction: discord.Interaction, utente: discord.Member):
        user_id = str(utente.id)
        
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True, thinking=True)

        rows_deleted = 0
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                cursor = await db.execute(
                    "DELETE FROM licenses WHERE user_id = ?",
                    (user_id,)
                )
                rows_deleted = cursor.rowcount
                await db.commit()
                
            if rows_deleted == 0:
                await interaction.followup.send(
                    f"❌ {utente.mention} non possiede **alcuna licenza (licenses)** nel database da revocare.", 
                    ephemeral=True
                )
                return

            try:
                embed_dm = discord.Embed(
                    title="🚨 Patente Revocata",
                    description=f"La tua patente di guida e altre licenze generiche sono state revocate da {interaction.user.mention} (LFD).",
                    color=discord.Color.red()
                )
                embed_dm.add_field(name="Numero di licenze rimosse", value=f"**{rows_deleted}**")
                embed_dm.set_footer(text="Contatta un membro LFD per chiarimenti.")
                await utente.send(embed=embed_dm)
                dm_status = "Notifica DM inviata."
            except:
                dm_status = "Notifica DM non inviabile (DM bloccati)."

            await interaction.followup.send(
                f"✅ **{rows_deleted}** licenza/e rimosse a {utente.mention} con successo. ({dm_status})", 
                ephemeral=True
            )

            log_embed = discord.Embed(
                title="🚫 LOG REVOCA PATENTE",
                color=discord.Color.red()
            )
            log_embed.add_field(name="👮 Revocata da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="👤 Utente", value=utente.mention, inline=True)
            log_embed.add_field(name="📊 Licenze Rimosse", value=f"**{rows_deleted}**", inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

        except Exception as e:
            print(f"ERRORE CRITICO DURANTE REVOCA-PATENTE: {e}")
            await interaction.followup.send(
                f"❌ Si è verificato un errore critico nel database durante la revoca.",
                ephemeral=True
            )

    @bot.tree.command(name="cura", description="Cura un cittadino per una ferita specifica.")
    @app_commands.describe(
        cittadino="La persona da curare",
        tramite="Il metodo di cura utilizzato",
        ferita="La ferita che stai curando (es. 'gamba rotta')"
    )
    @app_commands.choices(tramite=[
        app_commands.Choice(name="Medikit", value="Medikit"),
        app_commands.Choice(name="Ospedale", value="Ospedale"),
        app_commands.Choice(name="Ambulanza", value="Ambulanza"),
    ])
    async def cura(interaction: discord.Interaction, cittadino: discord.Member, tramite: app_commands.Choice[str], ferita: str):
        
        descrizione = (
            f"{interaction.user.mention} ha curato **__{ferita}__** "
            f"a {cittadino.mention} tramite **{tramite.name}**"
        )
        
        embed = discord.Embed(
            title="<a:Ambulanza:1431690856280232058> 𝐂𝐮𝐫𝐚 <a:Cuore:1431691069703065640>",
            description=descrizione,
            color=discord.Color.from_rgb(0xE9, 0x1E, 0x63)
        )

        await interaction.response.send_message("✅ Azione Cura inviata!", ephemeral=True)
        await interaction.channel.send(embed=embed)
        
        log_embed = discord.Embed(
            title="🩹 LOG CURA",
            color=discord.Color.from_rgb(0xE9, 0x1E, 0x63)
        )
        log_embed.add_field(name="👨‍⚕️ Medico", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Paziente", value=cittadino.mention, inline=True)
        log_embed.add_field(name="🩺 Ferita", value=ferita, inline=False)
        log_embed.add_field(name="🚑 Metodo", value=tramite.name, inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
