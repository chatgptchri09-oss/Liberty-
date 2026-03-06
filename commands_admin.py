import discord
from discord import app_commands
import database
import aiosqlite
from constants import LOG_CHANNEL_ID, DATABASE_NAME, has_staff, CHIAVE_ROLE_ID

async def _log(bot, embed: discord.Embed):
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch: await ch.send(embed=embed)
    except Exception: pass

def setup_admin_commands(bot):

    # ── /add-money ────────────────────────────────────────────────────────────
    @bot.tree.command(name="add-money", description="[Staff] Aggiungi denaro a un giocatore")
    @app_commands.describe(giocatore="Il giocatore", importo="Importo", dove="Contanti o banca")
    @app_commands.choices(dove=[
        app_commands.Choice(name="💵 Contanti", value="cash"),
        app_commands.Choice(name="🏦 Banca",    value="bank"),
    ])
    async def add_money(interaction: discord.Interaction, giocatore: discord.Member, importo: int, dove: str = "cash"):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return
        user = await database.get_user(str(giocatore.id))
        if dove == "cash":
            await database.update_balance(str(giocatore.id), cash=user["cash"] + importo)
        else:
            await database.update_balance(str(giocatore.id), bank=user["bank"] + importo)
        label = "Contanti" if dove == "cash" else "Banca"
        embed = discord.Embed(title="💰 Denaro Aggiunto", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
        embed.add_field(name="💵 Importo",   value=f"${importo:,}",   inline=True)
        embed.add_field(name="📋 Dove",      value=label,              inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /remove-money ─────────────────────────────────────────────────────────
    @bot.tree.command(name="remove-money", description="[Staff] Rimuovi denaro da un giocatore")
    @app_commands.describe(giocatore="Il giocatore", importo="Importo", dove="Contanti o banca")
    @app_commands.choices(dove=[
        app_commands.Choice(name="💵 Contanti", value="cash"),
        app_commands.Choice(name="🏦 Banca",    value="bank"),
    ])
    async def remove_money(interaction: discord.Interaction, giocatore: discord.Member, importo: int, dove: str = "cash"):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        user = await database.get_user(str(giocatore.id))
        if dove == "cash":
            await database.update_balance(str(giocatore.id), cash=max(0, user["cash"] - importo))
        else:
            await database.update_balance(str(giocatore.id), bank=max(0, user["bank"] - importo))
        label = "Contanti" if dove == "cash" else "Banca"
        embed = discord.Embed(title="💸 Denaro Rimosso", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
        embed.add_field(name="💵 Importo",   value=f"${importo:,}",   inline=True)
        embed.add_field(name="📋 Da",        value=label,              inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /give-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="give-item", description="[Staff] Dai un item a un giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="Nome item", quantita="Quantità")
    async def give_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        await database.add_item(str(giocatore.id), item, quantita)
        embed = discord.Embed(title="🎁 Item Consegnato", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Ricevuto da", value=giocatore.mention, inline=True)
        embed.add_field(name="📦 Item",        value=item,              inline=True)
        embed.add_field(name="🔢 Quantità",    value=str(quantita),     inline=True)
        embed.add_field(name="👮 Staff",       value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /take-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="take-item", description="[Staff] Rimuovi un item da un giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="Nome item", quantita="Quantità")
    async def take_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        if not await database.remove_item(str(giocatore.id), item, quantita):
            await interaction.response.send_message(f"❌ Il giocatore non ha abbastanza **{item}**.", ephemeral=True); return
        embed = discord.Embed(title="📦 Item Rimosso", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
        embed.add_field(name="📦 Item",      value=item,              inline=True)
        embed.add_field(name="🔢 Quantità",  value=str(quantita),     inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /paga-stipendio ───────────────────────────────────────────────────────
    @bot.tree.command(name="paga-stipendio", description="[Staff] Paga lo stipendio a un giocatore")
    @app_commands.describe(giocatore="Il giocatore", importo="Importo stipendio", ruolo="Lavoro del giocatore")
    async def paga_stipendio(interaction: discord.Interaction, giocatore: discord.Member, importo: int, ruolo: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        user = await database.get_user(str(giocatore.id))
        await database.update_balance(str(giocatore.id), cash=user["cash"] + importo)
        embed = discord.Embed(title="💼 Stipendio Pagato", color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,  inline=True)
        embed.add_field(name="💵 Stipendio", value=f"${importo:,}",    inline=True)
        embed.add_field(name="🤠 Lavoro",    value=ruolo,              inline=True)
        embed.add_field(name="👮 Pagato da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Stipendio")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)
        try:
            dm = discord.Embed(title="💵 Hai ricevuto lo stipendio!",
                               description=f"Hai ricevuto **${importo:,}** per il tuo lavoro da **{ruolo}**.",
                               color=discord.Color.green())
            await giocatore.send(embed=dm)
        except Exception: pass

    # ── /annuncio ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="annuncio", description="[Staff] Invia un annuncio con @everyone")
    @app_commands.describe(titolo="Titolo", messaggio="Testo dell'annuncio")
    async def annuncio(interaction: discord.Interaction, titolo: str, messaggio: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        embed = discord.Embed(title=f"📜 {titolo}", description=messaggio,
                              color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"Annuncio di {interaction.user.display_name} • 🤠 Red Dead Redemption II")
        await interaction.channel.send(content="@everyone", embed=embed)
        await interaction.response.send_message("✅ Annuncio inviato!", ephemeral=True)

    # ── /wipe-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="wipe-item", description="[Staff] Svuota le bisacce di tutti i giocatori")
    async def wipe_item(interaction: discord.Interaction):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM inventory")
            await db.commit()
        embed = discord.Embed(title="🗑️ Wipe Item Completato", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👮 Eseguito da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /whitelister ──────────────────────────────────────────────────────────
    @bot.tree.command(name="whitelister", description="[Staff] Dai l'esito di una whitelist")
    @app_commands.describe(giocatore="Il candidato", esito="Approvato o rifiutato", motivazione="Motivazione (opzionale)")
    @app_commands.choices(esito=[
        app_commands.Choice(name="✅ Approvato",  value="approvato"),
        app_commands.Choice(name="❌ Rifiutato",  value="rifiutato"),
    ])
    async def whitelister(interaction: discord.Interaction, giocatore: discord.Member, esito: str, motivazione: str = ""):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        color = discord.Color.green() if esito == "approvato" else discord.Color.red()
        emoji = "✅" if esito == "approvato" else "❌"
        embed = discord.Embed(title=f"{emoji} Whitelist — {esito.capitalize()}", color=color, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,       inline=True)
        embed.add_field(name="📋 Esito",     value=esito.capitalize(),       inline=True)
        if motivazione: embed.add_field(name="📝 Motivazione", value=motivazione, inline=False)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Whitelist")
        await interaction.response.send_message(embed=embed)
        try: await giocatore.send(embed=embed)
        except Exception: pass

    # ── /status-whitelist ─────────────────────────────────────────────────────
    @bot.tree.command(name="status-whitelist", description="[Staff] Stato servizi whitelist")
    @app_commands.choices(stato=[
        app_commands.Choice(name="🟢 Online",  value="online"),
        app_commands.Choice(name="🔴 Offline", value="offline"),
    ])
    async def status_whitelist(interaction: discord.Interaction, stato: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        color = discord.Color.green() if stato == "online" else discord.Color.red()
        emoji = "<a:online:1459627385702973572>" if stato == "online" else "<a:offline:1459628872197738641>"
        embed = discord.Embed(title=f"{emoji} Servizi Whitelist — {stato.upper()}", color=color, timestamp=discord.utils.utcnow())
        embed.set_footer(text="🤠 Red Dead Redemption II")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Stato aggiornato!", ephemeral=True)

    # ── /add-fondocassa ───────────────────────────────────────────────────────
    @bot.tree.command(name="add-fondocassa", description="[Staff] Aggiungi al fondo cassa di una compagnia")
    @app_commands.describe(compagnia="La compagnia", importo="Importo da aggiungere")
    @app_commands.choices(compagnia=[
        app_commands.Choice(name="⭐ Sceriffo",     value="Sceriffo"),
        app_commands.Choice(name="🩺 Dottore",      value="Dottore"),
        app_commands.Choice(name="🔫 Armiere",      value="Armiere"),
        app_commands.Choice(name="🐴 Stalla",       value="Stalla"),
        app_commands.Choice(name="🍺 Saloon",       value="Saloon"),
        app_commands.Choice(name="🏪 Emporio",      value="Emporio"),
        app_commands.Choice(name="🚫 Contrabbando", value="Contrabbando"),
        app_commands.Choice(name="🚂 Diligenza",    value="Diligenza"),
    ])
    async def add_fondocassa(interaction: discord.Interaction, compagnia: str, importo: int):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        current = await database.get_fondocassa(compagnia)
        await database.update_fondocassa(compagnia, current + importo)
        embed = discord.Embed(title="💼 Fondo Cassa Aggiornato", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="🏢 Compagnia",    value=compagnia,                  inline=True)
        embed.add_field(name="💵 Aggiunto",     value=f"${importo:,}",            inline=True)
        embed.add_field(name="💰 Nuovo totale", value=f"${current+importo:,}",   inline=True)
        embed.add_field(name="👮 Staff",        value=interaction.user.mention,   inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /daiproprieta ─────────────────────────────────────────────────────────
    @bot.tree.command(name="daiproprieta", description="[Staff] Registra una proprietà per un cittadino")
    @app_commands.describe(cittadino="Il proprietario", nome="Nome proprietà", tipo="Tipo", luogo="Ubicazione")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="🏡 Ranch",        value="Ranch"),
        app_commands.Choice(name="⛏️ Miniera",      value="Miniera"),
        app_commands.Choice(name="🍺 Saloon",       value="Saloon"),
        app_commands.Choice(name="🐴 Stalla",       value="Stalla"),
        app_commands.Choice(name="🏚️ Casolare",     value="Casolare"),
        app_commands.Choice(name="🌾 Fattoria",     value="Fattoria"),
        app_commands.Choice(name="🏪 Emporio",      value="Emporio"),
        app_commands.Choice(name="🏕️ Accampamento", value="Accampamento"),
    ])
    async def dai_proprieta(interaction: discord.Interaction, cittadino: discord.Member,
                            nome: str, tipo: str, luogo: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        await database.add_property(str(cittadino.id), nome, tipo, luogo)
        embed = discord.Embed(title="🏡 Proprietà Registrata", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Proprietario", value=cittadino.mention, inline=True)
        embed.add_field(name="🏠 Nome",         value=nome,              inline=True)
        embed.add_field(name="🏷️ Tipo",         value=tipo,              inline=True)
        embed.add_field(name="📍 Ubicazione",   value=luogo,             inline=False)
        embed.add_field(name="👮 Assegnato da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Proprietà")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)
        try:
            dm = discord.Embed(title="🏡 Nuova Proprietà!",
                               description=f"Sei proprietario di **{nome}** ({tipo}) a **{luogo}**!",
                               color=discord.Color(0x8B4513))
            await cittadino.send(embed=dm)
        except Exception: pass
