import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime
import database
import asyncio # Aggiungi questo all'inizio del file, se non c'è


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
            title="<a:manette:1431626831076921507> 𝐀𝐌𝐌𝐀𝐍𝐄𝐓𝐓𝐀𝐌𝐄𝐍𝐓𝐎",
            description=f"{interaction.user.mention} ha ammanettato {utente.mention}\n\n <a:sirena:1431792628332101723><a:attenzione:1431795789205733467> Ha il diritto di rimanere in silenzio, qualsiasi cosa dirà potrà essere utilizzata contro di lei in tribunale. Ha diritto ad un avvocato, se non ne possiede uno gliene verrà fornito uno d'ufficio <a:attenzione:1431795789205733467><a:sirena:1431792628332101723> ",
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
                title="<a:Online:1431599470897922069> 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 <a:broom:1431606606763921408>",
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
                title=" <a:offline:1431606235354107914> 𝐓𝐮𝐫𝐧𝐨 𝐥𝐚𝐯𝐨𝐫𝐚𝐭𝐢𝐯𝐨 <a:cigarette:1431607423256494161>",
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
            title="<a:Hacked:1431683990443786240> 𝝰𝛈𝞂𝛈𝖏𝒎𝞂 <a:Skullhack:1431684263056638154>",
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
            title="<a:Ciak:1431629051545653369> 𝐀𝐳𝐢𝐨𝐧𝐞 <a:Progress:1431681998250049686> ",
            description=f"{interaction.user.mention}: *{azione}*",
            color=discord.Color.from_rgb(44, 47, 51) # Colore neutro (Grigio Scura Discord)
        )

        # Risposta di conferma effimera e invio del messaggio visibile a tutti
        await interaction.response.send_message("✅ Azione RP inviata!", ephemeral=True)
        await interaction.channel.send(embed=embed)
        
        await log_command(bot, LOG_CHANNEL_ID, f"🎬 {interaction.user.mention} ha eseguito l'azione: {azione}")

    # ====================
    # COMANDO: /revoca-patente (Rimozione Licenza da LFD) - MASSIMA VELOCITÀ
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

        rows_deleted = 0
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                
                # 2. Rimuove TUTTE le licenze generiche (licenses) per l'utente in un'unica operazione
                cursor = await db.execute(
                    "DELETE FROM licenses WHERE user_id = ?",
                    (user_id,)
                )
                rows_deleted = cursor.rowcount
                await db.commit()
                
            # 3. Gestione del risultato e Notifica
            if rows_deleted == 0:
                await interaction.followup.send(
                    f"❌ {utente.mention} non possiede **alcuna licenza (licenses)** nel database da revocare.", 
                    ephemeral=True
                )
                return

            # Notifica l'utente revocato in DM
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

            # 4. Risposta LFD e Log
            await interaction.followup.send(
                f"✅ **{rows_deleted}** licenza/e rimosse a {utente.mention} con successo. ({dm_status})", 
                ephemeral=True
            )

            log_msg = f"🚫 {interaction.user.mention} (LFD) ha revocato {rows_deleted} licenze a {utente.mention}"
            await log_command(bot, LOG_CHANNEL_ID, log_msg)

        except Exception as e:
            # Cattura qualsiasi errore di blocco o SQL
            print(f"ERRORE CRITICO DURANTE REVOCA-PATENTE: {e}")
            await log_command(bot, LOG_CHANNEL_ID, f"❌ ERRORE REVOCA-PATENTE: {interaction.user.mention} ha fallito a revocare {utente.mention}. Errore: {e}")
            await interaction.followup.send(
                f"❌ Si è verificato un errore critico nel database durante la revoca.",
                ephemeral=True
            )

# ====================
    # NUOVO COMANDO: /cura (Azione Curativa Visibile a Tutti)
    # ====================
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
        
        # Prepara la descrizione con il testo sottolineato per la ferita
        # Usa il markup Markdown "__testo__" per sottolineare
        descrizione = (
            f"{interaction.user.mention} ha curato **__{ferita}__** "
            f"a {cittadino.mention} tramite **{tramite.name}**"
        )
        
        # Crea l'Embed
        embed = discord.Embed(
            title="<a:Ambulanza:1431690856280232058> 𝐂𝐮𝐫𝐚 <a:Cuore:1431691069703065640>",
            description=descrizione,
            color=discord.Color.from_rgb(0xE9, 0x1E, 0x63) # #e91e63 in RGB
        )

        # Risposta di conferma effimera e invio del messaggio visibile a tutti
        await interaction.response.send_message("✅ Azione Cura inviata!", ephemeral=True)
        await interaction.channel.send(embed=embed)
        
        await log_command(bot, LOG_CHANNEL_ID, f"🩹 {interaction.user.mention} ha curato {cittadino.mention} per '{ferita}' tramite {tramite.name}")

    # =========================================
    # NUOVO COMANDO: /sondaggio (Poll)
    # =========================================
    @bot.tree.command(name="sondaggio", description="Crea un sondaggio rapido con opzioni SI/NO/PIÙ TARDI.")
    @app_commands.describe(
        domanda="La domanda o l'oggetto del sondaggio"
    )
    async def sondaggio(interaction: discord.Interaction, domanda: str):
        # 1. Verifica dei permessi (Ruolo POLL_ROLE_ID)
        POLL_ROLE_ID = 1414753824463126611 # ID del ruolo per il sondaggio (come da contesto)
        if not has_role(interaction, POLL_ROLE_ID):
            await interaction.response.send_message("❌ Non hai i permessi per creare sondaggi (Ruolo Poll richiesto).", ephemeral=True)
            return

        # 2. Costruzione della descrizione dell'Embed
        # Uso le triple virgolette e i blocchi di citazione (>) per la formattazione richiesta
        description_content = f"""
> **{domanda}**

 <a:spunta:1431937738256552036> SI CI SARÒ 
 <a:annulla:1431940396635652146> NO NON CI SARÒ 
 <a:Orologio:1431937656744448060> VENGO PIÙ TARDI
"""
        
        # 3. Creazione dell'Embed
        embed = discord.Embed(
            title="<a:megafono:1431932605984542720> Sondaggio <a:megafono:1431932605984542720>",
            description=description_content,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Sondaggio creato da {interaction.user.display_name}")

        # 4. Risposta effimera di conferma
        await interaction.response.send_message("✅ Sondaggio inviato!", ephemeral=True)

        # 5. Invio del messaggio pubblico e acquisizione dell'oggetto messaggio
        # Acquisiamo l'oggetto messaggio per poter aggiungere le reazioni
        poll_message = await interaction.channel.send(embed=embed)

        # 6. Aggiunta delle reazioni
        try:
            await poll_message.add_reaction("<a:spunta:1431937738256552036>")
            await poll_message.add_reaction("<a:annulla:1431940396635652146>")
            await poll_message.add_reaction("<a:Orologio:1431937656744448060>")
        except Exception as e:
            # Logging in caso di fallimento nell'aggiungere le reazioni
            await log_command(bot, LOG_CHANNEL_ID, f"🚨 Errore nell'aggiungere reazioni al sondaggio: {e}")

        # 7. Logging
        await log_command(bot, LOG_CHANNEL_ID, f"🗳️ {interaction.user.mention} ha avviato un sondaggio: '{domanda}'")


    # =========================================
    # COMANDO: /stato-rp (On/Off) - OTTIMIZZATO
    # =========================================
    @bot.tree.command(name="stato-rp", description=" Gestisce lo stato ON o OFF del RolePlay.")
    @app_commands.describe(
        on_off="Seleziona lo stato attuale del RolePlay"
    )
    @app_commands.choices(on_off=[
        app_commands.Choice(name="On", value="ON"),
        app_commands.Choice(name="Off", value="OFF"),
    ])
    async def stato_rp(interaction: discord.Interaction, on_off: app_commands.Choice[str]):
        # Verifica dei permessi (Ruolo POLL_ROLE_ID)
        POLL_ROLE_ID = 1414753824463126611
        MENTION_ROLE_ID = 1414752091607535727
        
        if not has_role(interaction, POLL_ROLE_ID):
            await interaction.response.send_message("❌ Non hai i permessi per cambiare lo stato del RolePlay (Ruolo Poll richiesto).", ephemeral=True)
            return

        # 1. RINVIO IMMEDIATO: Avvisa Discord che stiamo lavorando
        # Lo mettiamo effimero per nascondere il "ci sta lavorando" all'utente.
        await interaction.response.defer(ephemeral=True, thinking=True) 

        # Inizializzazione
        content_message = f"{interaction.user.mention} ha usato </stato-rp:{interaction.command.id}>"
        embed = None
        log_status = "" 
        
        # --- Logica ON ---
        if on_off.value == "ON":
            
            embed = discord.Embed(
                title="<a:Online:1431599470897922069> 𝐑𝐨𝐥𝐞𝐏𝐥𝐚𝐲 𝐎𝐧 <a:Online:1431599470897922069>",
                color=discord.Color.from_rgb(144, 238, 144) # Verde chiaro
            )
            embed.description = (
                f"**𝗛𝗼𝘀𝘁:** {interaction.user.mention}\n"
                f"<@&{MENTION_ROLE_ID}>\n"
                f"**𝐓𝐢 𝐚𝐮𝐠𝐮𝐫𝐢𝐚𝐦𝐨 𝐮𝐧 𝐛𝐮𝐨𝐧 𝐫𝐨𝐥𝐞𝐩𝐥𝐚𝐲**"
            )
            embed.set_image(url="https://cdn.discordapp.com/attachments/1235599658928308264/1250595400616771614/ServerOn.gif?ex=6900ab7a&is=68ff59fa&hm=fa91c25322c407b4fdd88d3cfbbc6f8db86c62e1fa8e74b0733cb0930c3285f3&")
            log_status = "attivato il RolePlay (ON)"

        # --- Logica OFF ---
        elif on_off.value == "OFF":
            
            embed = discord.Embed(
                title="<a:Caricamento:1432417274983219276> 𝐑𝐨𝐥𝐞𝐏𝐥𝐚𝐲 𝐎𝐟𝐟 <a:Caricamento:1432417274983219276>",
                color=discord.Color.red()
            )
            embed.description = (
                f"<@&{MENTION_ROLE_ID}>\n"
                f"**𝐒𝐩𝐞𝐫𝐢𝐚𝐦𝐨 𝐭𝐢 𝐬𝐢𝐚 𝐝𝐢𝐯𝐞𝐫𝐭𝐢𝐭𝐨**\n"
                f"_ricordati di chiudere il turno lavorativo_"
            )
            embed.set_image(url="https://cdn.discordapp.com/attachments/1235599658928308264/1250595400226963527/ServerOff.gif?ex=6900ab7a&is=68ff59fa&hm=b846c818c8e0180e4d5ad0230f5f123ec9b18cec632acf888d0675fe9a593bbd&")
            log_status = "disattivato il RolePlay (OFF)"

        # --- Aggiungi la foto profilo del server (Thumbnail) ---
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        # 4. RISOLUZIONE RAPIDA (per eliminare "ci sta lavorando")
        # Sostituisce il messaggio "pensando" con una conferma effimera per l'utente.
        await interaction.edit_original_response(
            content=f"✅ Stato RolePlay aggiornato su {on_off.value}!"
        )

        # 5. INVIO PUBBLICO: Invia il messaggio finale come operazione separata
        await interaction.response.send_message(embed=embed)
        )

        # 6. Logging
        await log_command(bot, LOG_CHANNEL_ID, f"🎲 {interaction.user.mention} ha {log_status}")
