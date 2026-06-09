import discord
from discord import app_commands
import database
import aiosqlite
from constants import LOG_CHANNEL_ID, DATABASE_NAME, has_staff, CHIAVE_ROLE_ID

# ── ID Ruoli speciali ─────────────────────────────────────────────────────────
AGENZIA_ROLE_ID      = 1404051965364670545
WHITELISTER_ROLE_ID  = 1404051876592488562
CHIAVE_CMD_ROLE_ID   = 1404051860121456701
FOUNDER_ROLE_ID      = 1404051866962100286

# Ruoli assegnati dal whitelister
BG_POSITIVO_ROLE_ID  = 1480218025373208791
WL_POSITIVA_ROLES    = [
    1404052052530696243,
    1404052053877063680,
    1404052056028872775,
    1432490950277599313,
]
SESSO_UOMO_ROLE_ID   = 1404052058688065547
SESSO_DONNA_ROLE_ID  = 1404052059564675174

BACKGROUND_CHANNEL_ID = 1480221950105096355

# ── Helper log ────────────────────────────────────────────────────────────────
async def _log(bot, embed: discord.Embed):
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch: await ch.send(embed=embed)
    except Exception: pass

def _has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == role_id for r in interaction.user.roles)


# ── Logica background via DM ──────────────────────────────────────────────────
async def _avvia_background(bot, member: discord.Member):
    """Avvia il flusso background via DM. Chiamata dopo conferma dal Modal."""

    DOMANDE_OOC = [
        ("🆔 ID PSN",                                    "Scrivi il tuo ID PSN:"),
        ("💻 Tag Discord",                               "Scrivi il tuo tag Discord:"),
        ("🖋️ Nome (Reale)",                             "Scrivi il tuo nome reale:"),
        ("🔞 Età (Reale)",                               "Scrivi la tua età reale:"),
        ("👤 Da Quanto Tempo Fai Rp",                    "Da quanto tempo fai roleplay?"),
        ("🌵 Come Sei Venuto A Conoscenza Del Server",   "Come hai conosciuto il nostro server?"),
        ("🚨 In Quanti Altri Server Sei Stato",          "In quanti altri server sei stato?"),
        ("⚡ Perché Hai Scelto Questo Server",           "Perché hai scelto questo server?"),
        ("🐎 Sai che è un server RP di RDR2 Online",    "Sai che è un server RP di RDR2 Online? (Sì/No)"),
    ]
    DOMANDE_IC = [
        ("🖋️ Nome e Cognome",                           "Scrivi il nome e cognome del tuo personaggio:"),
        ("🔞 Età (Siamo nel 1899)",                      "Quanti anni ha il tuo personaggio? (Siamo nel 1899)"),
        ("📆 Data Di Nascita (Siamo nel 1899)",          "Data di nascita del personaggio (Siamo nel 1899):"),
        ("🧠 Carattere, Personalità e Paure",            "Descrivi carattere, personalità e paure del personaggio:"),
        ("👀 Obbiettivo",                                "Qual è l'obiettivo del tuo personaggio?"),
        ("📕 Storia Personaggio (Minimo 5 Righe)",       "Racconta la storia del tuo personaggio (minimo 5 righe):"),
    ]

    risposte_ooc: list = []
    risposte_ic:  list = []

    def check(m):
        return m.author.id == member.id and isinstance(m.channel, discord.DMChannel)

    async def chiedi(label: str, domanda: str):
        e = discord.Embed(
            description=f"**{domanda}**\n\n*Scrivi `annulla` per interrompere il background.*",
            color=discord.Color(0x8B4513)
        )
        await member.send(embed=e)
        try:
            msg = await bot.wait_for("message", check=check, timeout=900)
            if msg.content.strip().lower() == "annulla":
                return "ANNULLA"
            return msg.content
        except Exception:
            return None

    EMBED_TIMEOUT = discord.Embed(
        title="⏰ Tempo scaduto",
        description=(
            "Hai impiegato troppo tempo a rispondere.\n"
            "Il background è stato **annullato automaticamente**.\n\n"
            "Puoi ricominciare premendo il pulsante nel canale quando sei pronto. 🤠"
        ),
        color=discord.Color.red()
    )
    EMBED_ANNULLA = discord.Embed(
        title="❌ Background Annullato",
        description=(
            "Hai annullato il background.\n\n"
            "Puoi ricominciare premendo il pulsante nel canale quando sei pronto. 🤠"
        ),
        color=discord.Color.orange()
    )

    # ── OOC ──────────────────────────────────────────────────────────────────
    await member.send(embed=discord.Embed(
        description="╞═════𖠁**OOC**𖠁═════╡", color=discord.Color(0xDAA520)
    ))
    for label, domanda in DOMANDE_OOC:
        r = await chiedi(label, domanda)
        if r is None:
            await member.send(embed=EMBED_TIMEOUT); return
        if r == "ANNULLA":
            await member.send(embed=EMBED_ANNULLA); return
        risposte_ooc.append((label, r))

    # ── IC ────────────────────────────────────────────────────────────────────
    await member.send(embed=discord.Embed(
        description="╞═════𖠁**IC**𖠁═════╡", color=discord.Color(0xDAA520)
    ))
    for label, domanda in DOMANDE_IC:
        r = await chiedi(label, domanda)
        if r is None:
            await member.send(embed=EMBED_TIMEOUT); return
        if r == "ANNULLA":
            await member.send(embed=EMBED_ANNULLA); return
        risposte_ic.append((label, r))

    await member.send(embed=discord.Embed(
        description=(
            "Le tue risposte sono state registrate negli archivi della contea.\n\n"
            "La tua storia verrà ora esaminata dalle autorità.\n"
            "Riceverai notizie non appena la tua richiesta verrà valutata.\n\n"
            "Per ora, viandante... attendi il tuo destino. 🤠"
        ),
        color=discord.Color(0x8B4513)
    ))

    # ── Embed riepilogo nel canale background ─────────────────────────────────
    embed_bg = discord.Embed(
        title="📋 𝐍𝐔𝐎𝐕𝐎 𝐁𝐀𝐂𝐊𝐆𝐑𝐎𝐔𝐍𝐃",
        color=discord.Color(0x8B4513),
        timestamp=discord.utils.utcnow()
    )
    embed_bg.set_thumbnail(url=member.display_avatar.url)
    embed_bg.add_field(name="👤 Candidato", value=member.mention, inline=False)

    def _aggiungi_campo(embed, label, testo):
        testo  = testo or "—"
        chunks = [testo[i:i+1024] for i in range(0, len(testo), 1024)]
        embed.add_field(name=label, value=chunks[0], inline=False)
        for chunk in chunks[1:]:
            embed.add_field(name=f"↳ {label}", value=chunk, inline=False)

    embed_bg.add_field(name="\u200b", value="╞═════𖠁 **OOC** 𖠁═════╡", inline=False)
    for l, r in risposte_ooc:
        _aggiungi_campo(embed_bg, l, r)
    embed_bg.add_field(name="\u200b", value="\u200b", inline=False)
    embed_bg.add_field(name="\u200b", value="╞═════𖠁 **IC** 𖠁═════╡", inline=False)
    for l, r in risposte_ic:
        _aggiungi_campo(embed_bg, l, r)
    embed_bg.set_footer(text="🤠 Red Dead Redemption II — Background PG")

    try:
        bg_ch = bot.get_channel(BACKGROUND_CHANNEL_ID)
        if not bg_ch:
            bg_ch = await bot.fetch_channel(BACKGROUND_CHANNEL_ID)
        if bg_ch:
            await bg_ch.send(content=f"<@&{WHITELISTER_ROLE_ID}>", embed=embed_bg)
            print(f"[BG] Background inviato per {member.id}", flush=True)
    except Exception as e:
        print(f"[BG] Errore invio: {e}", flush=True)

    # ── Log staff ─────────────────────────────────────────────────────────────
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch:
            log_embed = discord.Embed(
                title="📋 LOG — Background PG Completato",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="👤 Candidato", value=member.mention,  inline=True)
            log_embed.add_field(name="🆔 User ID",   value=str(member.id),  inline=True)
            log_embed.set_footer(text="🤠 Red Dead Redemption II — Background PG")
            await ch.send(embed=log_embed)
    except Exception:
        pass


# ── Modal di conferma ─────────────────────────────────────────────────────────
class BackgroundConfermaModal(discord.ui.Modal, title="🤠 Conferma Background PG"):

    conferma = discord.ui.TextInput(
        label="Scrivi CONFERMO per iniziare",
        placeholder="CONFERMO",
        required=True,
        min_length=8,
        max_length=8,
        style=discord.TextStyle.short
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        if self.conferma.value.strip().upper() != "CONFERMO":
            await interaction.response.send_message(
                "❌ Devi scrivere esattamente **CONFERMO** per procedere.",
                ephemeral=True
            )
            return

        # Risposta immediata — questa è la parte chiave:
        # rispondiamo SUBITO a Discord prima di fare qualsiasi altra cosa
        await interaction.response.send_message(
            "✅ Perfetto! Controlla i tuoi **messaggi privati**, ti sto scrivendo ora. 🤠",
            ephemeral=True
        )

        # Proviamo ad aprire il DM
        try:
            embed_benvenuto = discord.Embed(
                description=(
                    "Saluti, viandante.\n"
                    "Per entrare in queste terre dovrai rispondere ad alcune domande sul tuo passato.\n\n"
                    "Rispondi con sincerità e iniziamo. 🤠"
                ),
                color=discord.Color.green()
            )
            await interaction.user.send(embed=embed_benvenuto)
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Non riesco a inviarti un DM!\n"
                "Vai in **Impostazioni → Privacy e sicurezza** e abilita\n"
                "**'Consenti messaggi privati dai membri del server'**.",
                ephemeral=True
            )
            return

        # Avvia il background in background (senza bloccare l'interaction)
        import asyncio
        asyncio.create_task(_avvia_background(self.bot, interaction.user))

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"[BackgroundModal] Errore: {error}", flush=True)
        try:
            await interaction.response.send_message(
                "❌ Errore imprevisto. Riprova tra qualche secondo.",
                ephemeral=True
            )
        except Exception:
            pass


# ── Bottone che apre il Modal ─────────────────────────────────────────────────
class BackgroundButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(
            label="🤠 Inizia Background PG",
            style=discord.ButtonStyle.success,
            custom_id="bg_apri_modal"   # custom_id fisso per persistenza
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        # Apre il Modal — questa risposta è ISTANTANEA per Discord
        await interaction.response.send_modal(BackgroundConfermaModal(self.bot))


# ── View persistente ──────────────────────────────────────────────────────────
class BackgroundView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(BackgroundButton(bot))


# ── Registra view persistente (chiamare in on_ready) ──────────────────────────
def register_persistent_views(bot):
    bot.add_view(BackgroundView(bot))


# ─────────────────────────────────────────────────────────────────────────────
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
        embed = discord.Embed(title="💰 𝐃𝐞𝐧𝐚𝐫𝐨 𝐀𝐠𝐠𝐢𝐮𝐧𝐭𝐨", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="💵 Importo",   value=f"${importo:,}",          inline=True)
        embed.add_field(name="📋 Dove",      value=label,                    inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /remove-money ─────────────────────────────────────────────────────────
    @bot.tree.command(name="remove-money", description="[Staff] Rimuovi denaro da un giocatore")
    @app_commands.describe(giocatore="Il giocatore", importo="Importo", dove="Contanti, banca, o automatico")
    @app_commands.choices(dove=[
        app_commands.Choice(name="🔄 Automatico (contanti → banca)", value="auto"),
        app_commands.Choice(name="💵 Solo Contanti",                  value="cash"),
        app_commands.Choice(name="🏦 Solo Banca",                     value="bank"),
    ])
    async def remove_money(interaction: discord.Interaction, giocatore: discord.Member, importo: int, dove: str = "auto"):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return
        user = await database.get_user(str(giocatore.id))
        if dove == "cash":
            rimosso_cash = min(importo, user["cash"])
            await database.update_balance(str(giocatore.id), cash=user["cash"] - rimosso_cash)
            label = f"💵 Contanti (rimossi ${rimosso_cash:,})"
        elif dove == "bank":
            rimosso_bank = min(importo, user["bank"])
            await database.update_balance(str(giocatore.id), bank=user["bank"] - rimosso_bank)
            label = f"🏦 Banca (rimossi ${rimosso_bank:,})"
        else:
            rimosso_cash = min(importo, user["cash"])
            resto        = importo - rimosso_cash
            rimosso_bank = min(resto, user["bank"])
            await database.update_balance(str(giocatore.id),
                                          cash=user["cash"] - rimosso_cash,
                                          bank=user["bank"] - rimosso_bank)
            if rimosso_cash > 0 and rimosso_bank > 0:
                label = f"🔄 Contanti **${rimosso_cash:,}** + Banca **${rimosso_bank:,}**"
            elif rimosso_cash > 0:
                label = f"💵 Contanti (${rimosso_cash:,})"
            else:
                label = f"🏦 Banca (${rimosso_bank:,})"
        embed = discord.Embed(title="💸 𝐃𝐞𝐧𝐚𝐫𝐨 𝐑𝐢𝐦𝐨𝐬𝐬𝐨", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="💵 Importo",   value=f"${importo:,}",          inline=True)
        embed.add_field(name="📋 Da",        value=label,                    inline=False)
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
        embed = discord.Embed(title="💼 𝐒𝐭𝐢𝐩𝐞𝐧𝐝𝐢𝐨 𝐏𝐚𝐠𝐚𝐭𝐨", color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="💵 Stipendio", value=f"${importo:,}",          inline=True)
        embed.add_field(name="🤠 Lavoro",    value=ruolo,                    inline=True)
        embed.add_field(name="👮 Pagato da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Stipendio")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)
        try:
            dm = discord.Embed(
                title="💵 𝐇𝐚𝐢 𝐫𝐢𝐜𝐞𝐯𝐮𝐭𝐨 𝐥𝐨 𝐬𝐭𝐢𝐩𝐞𝐧𝐝𝐢𝐨!",
                description=f"Hai ricevuto **${importo:,}** per il tuo lavoro da **{ruolo}**.",
                color=discord.Color.green()
            )
            await giocatore.send(embed=dm)
        except Exception: pass

    # ── /annuncio ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="annuncio", description="[Staff] Invia un annuncio con @everyone")
    @app_commands.describe(titolo="Titolo", messaggio="Testo dell'annuncio")
    async def annuncio(interaction: discord.Interaction, titolo: str, messaggio: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        embed = discord.Embed(
            title=f"📜 {titolo}", description=messaggio,
            color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow()
        )
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
        embed = discord.Embed(title="🗑️ 𝐖𝐢𝐩𝐞 𝐈𝐭𝐞𝐦 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐚𝐭𝐨", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👮 Eseguito da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /whitelister ──────────────────────────────────────────────────────────
    @bot.tree.command(name="whitelister", description="[Whitelister] Dai l'esito di background o whitelist")
    @app_commands.describe(
        giocatore="Il candidato", esito="Tipo di esito",
        sesso="Sesso del personaggio (solo per Whitelist Positiva)",
        motivazione="Motivazione (opzionale)",
        id_psn="ID PSN del giocatore (opzionale)"
    )
    @app_commands.choices(esito=[
        app_commands.Choice(name="✅ Background Positivo", value="bg_positivo"),
        app_commands.Choice(name="❌ Background Negativo", value="bg_negativo"),
        app_commands.Choice(name="✅ Whitelist Positiva",  value="wl_positiva"),
        app_commands.Choice(name="❌ Whitelist Negativa",  value="wl_negativa"),
    ])
    @app_commands.choices(sesso=[
        app_commands.Choice(name="👨 Uomo",  value="uomo"),
        app_commands.Choice(name="👩 Donna", value="donna"),
    ])
    async def whitelister(
        interaction: discord.Interaction, giocatore: discord.Member, esito: str,
        sesso: str = "", motivazione: str = "", id_psn: str = ""
    ):
        if not _has_role(interaction, WHITELISTER_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo il ruolo **Whitelister** può usare questo comando.", ephemeral=True
            ); return
        await interaction.response.defer()
        color = discord.Color.green() if esito in ("bg_positivo", "wl_positiva") else discord.Color.red()
        TITOLI = {
            "bg_positivo": "✅ 𝐁𝐚𝐜𝐤𝐠𝐫𝐨𝐮𝐧𝐝 𝐏𝐨𝐬𝐢𝐭𝐢𝐯𝐨",
            "bg_negativo": "❌ 𝐁𝐚𝐜𝐤𝐠𝐫𝐨𝐮𝐧𝐝 𝐍𝐞𝐠𝐚𝐭𝐢𝐯𝐨",
            "wl_positiva": "✅ 𝐖𝐡𝐢𝐭𝐞𝐥𝐢𝐬𝐭 𝐏𝐨𝐬𝐢𝐭𝐢𝐯𝐚",
            "wl_negativa": "❌ 𝐖𝐡𝐢𝐭𝐞𝐥𝐢𝐬𝐭 𝐍𝐞𝐠𝐚𝐭𝐢𝐯𝐚",
        }
        embed = discord.Embed(title=TITOLI[esito], color=color, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="👤 Giocatore",   value=giocatore.mention,        inline=True)
        embed.add_field(name="📋 Esito",       value=TITOLI[esito],            inline=True)
        if motivazione:
            embed.add_field(name="📝 Motivazione", value=motivazione, inline=False)
        embed.add_field(name="👮 Whitelister", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Whitelist")
        await interaction.followup.send(content=giocatore.mention, embed=embed)
        guild = interaction.guild
        if guild:
            try:
                NON_WL_ID   = 1404052057630965841
                non_wl_role = guild.get_role(NON_WL_ID)
                if esito == "bg_positivo":
                    r = guild.get_role(BG_POSITIVO_ROLE_ID)
                    if r: await giocatore.add_roles(r, reason="Background Positivo")
                    if non_wl_role: await giocatore.remove_roles(non_wl_role, reason="Background Positivo")
                elif esito == "wl_positiva":
                    for rid in WL_POSITIVA_ROLES:
                        r = guild.get_role(rid)
                        if r: await giocatore.add_roles(r, reason="Whitelist Positiva")
                    bg_role = guild.get_role(BG_POSITIVO_ROLE_ID)
                    if bg_role: await giocatore.remove_roles(bg_role, reason="Whitelist Positiva")
                    if non_wl_role: await giocatore.remove_roles(non_wl_role, reason="Whitelist Positiva")
                    if sesso == "uomo":
                        r = guild.get_role(SESSO_UOMO_ROLE_ID)
                        if r: await giocatore.add_roles(r, reason="Sesso: Uomo")
                    elif sesso == "donna":
                        r = guild.get_role(SESSO_DONNA_ROLE_ID)
                        if r: await giocatore.add_roles(r, reason="Sesso: Donna")
            except Exception: pass
        if id_psn:
            try:
                await giocatore.edit(nick=id_psn, reason=f"ID PSN da whitelister {interaction.user}")
            except Exception: pass
        try:
            await giocatore.send(embed=embed)
        except Exception: pass

    # ── /status-whitelist ─────────────────────────────────────────────────────
    @bot.tree.command(name="status-whitelist", description="[Staff] Stato servizi whitelist")
    @app_commands.describe(stato="Online o offline")
    @app_commands.choices(stato=[
        app_commands.Choice(name="🟢 Online",  value="online"),
        app_commands.Choice(name="🔴 Offline", value="offline"),
    ])
    async def status_whitelist(interaction: discord.Interaction, stato: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        color = discord.Color.green() if stato == "online" else discord.Color.red()
        emoji = "🟢" if stato == "online" else "🔴"
        embed = discord.Embed(
            title=f"{emoji} 𝐒𝐞𝐫𝐯𝐢𝐳𝐢 𝐖𝐡𝐢𝐭𝐞𝐥𝐢𝐬𝐭 — {stato.upper()}",
            color=color, timestamp=discord.utils.utcnow()
        )
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
        app_commands.Choice(name="🏦 Banca",        value="Banca"),
        app_commands.Choice(name="🥃 Distilleria",  value="Distilleria"),
    ])
    async def add_fondocassa(interaction: discord.Interaction, compagnia: str, importo: int):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        current = await database.get_fondocassa(compagnia)
        await database.update_fondocassa(compagnia, current + importo)
        embed = discord.Embed(title="💼 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 𝐀𝐠𝐠𝐢𝐨𝐫𝐧𝐚𝐭𝐨", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="🏢 Compagnia",    value=compagnia,                 inline=True)
        embed.add_field(name="💵 Aggiunto",     value=f"${importo:,}",           inline=True)
        embed.add_field(name="💰 Nuovo totale", value=f"${current+importo:,}",   inline=True)
        embed.add_field(name="👮 Staff",        value=interaction.user.mention,  inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)

    # ── /daiproprieta ─────────────────────────────────────────────────────────
    @bot.tree.command(name="daiproprieta", description="[Agenzia] Registra una proprietà per un cittadino")
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
        if not _has_role(interaction, AGENZIA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo l'**Agenzia Immobiliare** può registrare proprietà.", ephemeral=True
            ); return
        await database.add_property(str(cittadino.id), nome, tipo, luogo)
        embed = discord.Embed(title="🏡 𝐏𝐫𝐨𝐩𝐫𝐢𝐞𝐭à 𝐑𝐞𝐠𝐢𝐬𝐭𝐫𝐚𝐭𝐚", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Proprietario", value=cittadino.mention,        inline=True)
        embed.add_field(name="🏠 Nome",         value=nome,                     inline=True)
        embed.add_field(name="🏷️ Tipo",         value=tipo,                     inline=True)
        embed.add_field(name="📍 Ubicazione",   value=luogo,                    inline=False)
        embed.add_field(name="👮 Assegnato da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Proprietà")
        await interaction.response.send_message(embed=embed)
        await _log(bot, embed)
        try:
            dm = discord.Embed(
                title="🏡 𝐍𝐮𝐨𝐯𝐚 𝐏𝐫𝐨𝐩𝐫𝐢𝐞𝐭à!",
                description=f"Sei proprietario di **{nome}** ({tipo}) a **{luogo}**!",
                color=discord.Color(0x8B4513)
            )
            await cittadino.send(embed=dm)
        except Exception: pass

    # ── /setup-background ─────────────────────────────────────────────────────
    @bot.tree.command(name="setup-background", description="[Chiave] Invia il pannello Background PG nel canale")
    async def setup_background(interaction: discord.Interaction):
        if not _has_role(interaction, FOUNDER_ROLE_ID):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return

        embed = discord.Embed(
            title="𝐌𝐀𝐊𝐄 𝐘𝐎𝐔𝐑 𝐍𝐀𝐌𝐄 𝐈𝐍 𝐓𝐇𝐄 𝐖𝐄𝐒𝐓",
            description=(
                "Prima di mettere piede nelle terre selvagge e iniziare la tua nuova vita, "
                "ogni anima deve lasciare traccia della propria storia.\n\n"
                "Lo sceriffo della contea richiede che ogni nuovo arrivato racconti chi è, "
                "da dove viene e quale strada lo ha condotto fin qui.\n\n"
                "Premi il pulsante qui sotto per parlare con l'ufficio registri.\n"
                "Verrai contattato nei messaggi privati dopo la conferma.\n\n"
                "Ricorda... in queste terre un uomo vale tanto quanto la storia "
                "che porta con sé. 🤠"
            ),
            color=discord.Color(0x8B4513)
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio Registri")

        await interaction.channel.send(embed=embed, view=BackgroundView(bot))
        await interaction.response.send_message("✅ Pannello background inviato!", ephemeral=True)
