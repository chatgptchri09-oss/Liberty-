import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime
import database

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
LFD_ROLE_ID = 1415093546549248040
STAFF_ROLE_ID = 1414738761207517214
POLL_ROLE_ID = 1414753824463126611
MENTION_ROLE_ID = 1414752091607535727

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
            title="⛓️‍💥 𝐀𝐌𝐌𝐀𝐍𝐄𝐓𝐓𝐀𝐌𝐄𝐍𝐓𝐎",
            description=f"{interaction.user.mention} ha ammanettato {utente.mention}\n\n🚨⚠️ Ha il diritto di rimanere in silenzio, qualsiasi cosa dirà potrà essere utilizzata contro di lei in tribunale. Ha diritto ad un avvocato, se non ne possiede uno gliene verrà fornito uno d'ufficio⚠️🚨",
            color=discord.Color.dark_red()
        )

        await interaction.response.send_message(embed=embed)
        await log_command(bot, LOG_CHANNEL_ID, f"⛓️ {interaction.user.mention} ha ammanettato {utente.mention}")
    
    @bot.tree.command(name="turno", description="Inizia o termina un turno lavorativo")
    @app_commands.describe(
        stato="Inizio o Fine turno",
        lavoro="Il ruolo del lavoro"
    )
    @app_commands.choices(stato=[
        app_commands.Choice(name="Inizio", value="inizio"),
        app_commands.Choice(name="Fine", value="fine"),
    ])
    async def turno(interaction: discord.Interaction, stato: str, lavoro: discord.Role):
        member = interaction.user

        if stato == "inizio":
            if lavoro not in member.roles:
                await interaction.response.send_message(
                    f"❌ Non puoi iniziare un turno come {lavoro.mention} perché non hai quel ruolo!",
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
                    "INSERT INTO work_shifts (user_id, role_id, start_time) VALUES (?, ?, ?)",
                    (str(interaction.user.id), str(lavoro.id), datetime.now().isoformat())
                )
                await db.commit()

            embed = discord.Embed(
                title="🟢 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 🧹",
                description=f"{interaction.user.mention} ha **INIZIATO** il proprio turno di {lavoro.mention}",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed)
            await log_command(bot, LOG_CHANNEL_ID, f"🟢 {interaction.user.mention} ha iniziato turno come {lavoro.name}")

        elif stato == "fine":
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT start_time FROM work_shifts WHERE user_id = ? AND role_id = ?",
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
                end_time = datetime.now()
                duration = end_time - start_time

                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)

                await db.execute(
                    "DELETE FROM work_shifts WHERE user_id = ? AND role_id = ?",
                    (str(interaction.user.id), str(lavoro.id))
                )
                await db.commit()

            embed = discord.Embed(
                title="🔴 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 🚬",
                description=(
                    f"{interaction.user.mention} ha **TERMINATO** il proprio turno di {lavoro.mention}\n\n"
                    f"**Tempo Lavorativo:** {hours}h e {minutes}min"
                ),
                color=discord.Color.red()
            )

            await interaction.response.send_message(embed=embed)
            await log_command(
                bot,
                LOG_CHANNEL_ID,
                f"🔴 {interaction.user.mention} ha terminato turno come {lavoro.name} ({hours}h {minutes}min)"
            )
    
    @bot.tree.command(name="anonimo", description="Invia un messaggio anonimo")
    @app_commands.describe(messaggio="Il messaggio da inviare anonimamente")
    async def anonimo(interaction: discord.Interaction, messaggio: str):
        embed = discord.Embed(
            title="☠️ 𝐌𝐄𝐒𝐒𝐀𝐆𝐆𝐈𝐎 𝐀𝐍𝐎𝐍𝐈𝐌𝐎 ☠️",
            description=messaggio,
            color=discord.Color.dark_gray()
        )

        await interaction.response.send_message("✅ Messaggio anonimo inviato!", ephemeral=True)
        await interaction.channel.send(embed=embed)
        await log_command(bot, LOG_CHANNEL_ID, f"☠️ {interaction.user.mention} ha inviato un messaggio anonimo")
    
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
        await log_command(bot, LOG_CHANNEL_ID, f"🔍 {interaction.user.mention} ha nascosto un oggetto")

    # ====================
    # NUOVO COMANDO: /me (Azione RP Visibile a Tutti)
    # ====================
    @bot.tree.command(name="me", description="Esegui un'azione RP visibile a tutti.")
    @app_commands.describe(azione="L'azione che vuoi eseguire")
    async def me(interaction: discord.Interaction, azione: str):
        
        # Non è necessario il defer perché non ci sono operazioni lente.
        
        embed = discord.Embed(
            title="🎬 𝐀𝐳𝐢𝐨𝐧𝐞...",
            description=f"{interaction.user.mention}: *{azione}*",
            color=discord.Color.from_rgb(44, 47, 51) # Colore neutro (Grigio Scura Discord)
        )

        # Risposta di conferma effimera e invio del messaggio visibile a tutti
        await interaction.response.send_message("✅ Azione RP inviata!", ephemeral=True)
        await interaction.channel.send(embed=embed)
        
        await log_command(bot, LOG_CHANNEL_ID, f"🎬 {interaction.user.mention} ha eseguito l'azione: {azione}")

    # ====================
    # COMANDO: /revoca-patente (Rimozione Licenza da LFD) - CORRETTO
    # ====================
    @bot.tree.command(name="revoca-patente", description="[LFD] Rimuovi la licenza di guida a un utente.")
    @app_commands.describe(utente="L'utente a cui revocare la patente")
    async def revoca_patente(interaction: discord.Interaction, utente: discord.Member):
        user_id = str(utente.id)
        
        # 1. Controllo Ruolo LFD
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True, thinking=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            
            # 2. Verifica l'esistenza di QUALSIASI patente (licenses)
            # Rimuoviamo il filtro sul 'license_type' per trovarla se c'è
            async with db.execute(
                "SELECT id, license_type FROM licenses WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                licenses = await cursor.fetchall()

            if not licenses:
                await interaction.followup.send(
                    f"❌ {utente.mention} non possiede **alcuna patente (licenses)** nel database.", 
                    ephemeral=True
                )
                return

            # 3. Rimuove TUTTE le patenti di tipo generico per l'utente.
            # Se vuoi lasciare altre licenze (ad esempio porto d'armi), dovrai specificare il 'license_type' esatto.
            # Assumo che 'licenses' sia per la patente di guida. Se hai un'altra tabella per Porto d'Armi (gun_licenses), va bene così.
            await db.execute(
                "DELETE FROM licenses WHERE user_id = ?",
                (user_id,)
            )
            rows_deleted = db.cursor.rowcount
            await db.commit()
            
        # 4. Notifica l'utente revocato in DM
        try:
            embed_dm = discord.Embed(
                title="🚨 Patente Revocata",
                description=f"La tua patente di guida (e qualsiasi altra licenza generica) è stata revocata da {interaction.user.mention} (LFD).",
                color=discord.Color.red()
            )
            embed_dm.add_field(name="Numero di licenze rimosse", value=f"**{rows_deleted}**")
            embed_dm.set_footer(text="Contatta un membro LFD per chiarimenti.")
            await utente.send(embed=embed_dm)
            dm_status = "Notifica DM inviata."
        except:
            dm_status = "Notifica DM non inviabile (DM bloccati)."

        # 5. Risposta LFD e Log
        await interaction.followup.send(
            f"✅ **{rows_deleted}** patente/licenze rimosse a {utente.mention} con successo. ({dm_status})", 
            ephemeral=True
        )

        log_msg = f"🚫 {interaction.user.mention} (LFD) ha revocato {rows_deleted} patenti a {utente.mention}"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)
