import discord
from discord import app_commands
import database
import aiosqlite
from constants import STATO_ROLE_ID, LOG_CHANNEL_ID, has_sceriffo, DATABASE_NAME

# ID ruoli Staff che possono usare /vedi-documento
STAFF_VEDI_DOC = {1404051875426467902, 1404051873698418791}

def has_stato(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == STATO_ROLE_ID for r in interaction.user.roles)

def has_staff_doc(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in STAFF_VEDI_DOC for r in interaction.user.roles)


# ── View con tasto "Mostra" ──────────────────────────────────────────────────
class MostraDocumentoView(discord.ui.View):
    def __init__(self, embed: discord.Embed, richiedente: discord.Member):
        super().__init__(timeout=300)
        self.embed       = embed
        self.richiedente = richiedente

    @discord.ui.button(label="📢 Mostra", style=discord.ButtonStyle.primary)
    async def mostra(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            content=f"📜 Questo documento è stato mostrato da {self.richiedente.mention}",
            embed=self.embed
        )


# ── Costruisce l'embed del documento ─────────────────────────────────────────
def _build_doc_embed(cittadino, emittente, data: dict, foto_url):
    embed = discord.Embed(
        title="<a:documento:1458563773546893541> 𝐃𝐎𝐂𝐔𝐌𝐄𝐍𝐓𝐎 𝐃'𝐈𝐃𝐄𝐍𝐓𝐈𝐓À 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄",
        color=discord.Color(0x8B4513),
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=cittadino.display_avatar.url)
    embed.add_field(name="👤 ID PSN",           value=data.get("psn_id", "—"),       inline=True)
    embed.add_field(name="🔖 ID Discord",        value=cittadino.mention,              inline=True)
    embed.add_field(name="\u200b",               value="\u200b",                       inline=False)
    embed.add_field(name="👤 Nome",              value=data.get("nome", "—"),          inline=True)
    embed.add_field(name="👥 Cognome",           value=data.get("cognome", "—"),       inline=True)
    embed.add_field(name="📅 Data di Nascita",   value=data.get("data_nascita", "—"),  inline=True)
    embed.add_field(name="🎂 Età",               value=str(data.get("eta", "—")),      inline=True)
    embed.add_field(name="📍 Residenza",         value=data.get("residenza", "—"),     inline=True)
    embed.add_field(name="🌍 Nazionalità",       value=data.get("nazionalita", "—"),   inline=True)
    embed.add_field(name="⚧ Sesso",              value=data.get("sesso", "—"),         inline=True)
    embed.add_field(name="\u200b",               value="\u200b",                       inline=False)
    embed.add_field(name="💇 Colore Capelli",    value=data.get("capelli", "—"),       inline=True)
    embed.add_field(name="👁️ Colore Occhi",      value=data.get("occhi", "—"),         inline=True)
    embed.add_field(name="🎨 Carnagione",        value=data.get("carnagione", "—"),    inline=True)
    embed.add_field(name="🔍 Segni Particolari", value=data.get("segni", "—"),         inline=True)
    if foto_url:
        embed.set_image(url=foto_url)
    embed.add_field(name="🔒 Emesso da",         value=emittente.mention,              inline=True)
    embed.set_footer(text="🤠 Red Dead Redemption II — Documento Ufficiale")
    return embed


# ─────────────────────────────────────────────────────────────────────────────
#  View STEP 2
# ─────────────────────────────────────────────────────────────────────────────
class Step2View(discord.ui.View):
    def __init__(self, bot, cittadino, foto_url, emittente, data1):
        super().__init__(timeout=300)
        self.bot        = bot
        self.cittadino  = cittadino
        self.foto_url   = foto_url
        self.emittente  = emittente
        self.data1      = data1

    @discord.ui.button(label="➡️ Continua — Parte 2", style=discord.ButtonStyle.primary)
    async def apri_step2(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        bot        = self.bot
        cittadino  = self.cittadino
        foto_url   = self.foto_url
        emittente  = self.emittente
        data1      = self.data1

        class Modal2(discord.ui.Modal, title="📒 Modulo Documenti — Parte 2"):
            residenza   = discord.ui.TextInput(label="Residenza",      style=discord.TextStyle.short, required=True,  max_length=80)
            nazionalita = discord.ui.TextInput(label="Nazionalità",    style=discord.TextStyle.short, required=True,  max_length=50)
            sesso       = discord.ui.TextInput(label="Sesso",          style=discord.TextStyle.short, required=True,  max_length=10, placeholder="Uomo / Donna")
            capelli     = discord.ui.TextInput(label="Colore Capelli", style=discord.TextStyle.short, required=True,  max_length=30)
            occhi       = discord.ui.TextInput(label="Colore Occhi",   style=discord.TextStyle.short, required=True,  max_length=30)

            async def on_submit(self2, inter: discord.Interaction):
                data2 = {
                    "residenza":   self2.residenza.value,
                    "nazionalita": self2.nazionalita.value,
                    "sesso":       self2.sesso.value,
                    "capelli":     self2.capelli.value,
                    "occhi":       self2.occhi.value,
                }
                view3 = Step3View(bot, cittadino, foto_url, emittente, {**data1, **data2})
                await inter.response.send_message(
                    "✅ **Parte 2 completata!** Premi il bottone per l'ultimo step.",
                    view=view3, ephemeral=True
                )

        await interaction.response.send_modal(Modal2())


# ─────────────────────────────────────────────────────────────────────────────
#  View STEP 3
# ─────────────────────────────────────────────────────────────────────────────
class Step3View(discord.ui.View):
    def __init__(self, bot, cittadino, foto_url, emittente, data12):
        super().__init__(timeout=300)
        self.bot       = bot
        self.cittadino = cittadino
        self.foto_url  = foto_url
        self.emittente = emittente
        self.data12    = data12

    @discord.ui.button(label="➡️ Continua — Parte 3", style=discord.ButtonStyle.primary)
    async def apri_step3(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        bot        = self.bot
        cittadino  = self.cittadino
        foto_url   = self.foto_url
        emittente  = self.emittente
        data12     = self.data12

        class Modal3(discord.ui.Modal, title="📒 Modulo Documenti — Parte 3"):
            carnagione = discord.ui.TextInput(label="Colore Carnagione", style=discord.TextStyle.short, required=True,  max_length=30)
            segni      = discord.ui.TextInput(label="Segni Particolari", style=discord.TextStyle.short, required=False, max_length=100, placeholder="Lascia vuoto se nessuno")

            async def on_submit(self3, inter: discord.Interaction):
                full = {
                    **data12,
                    "carnagione": self3.carnagione.value,
                    "segni":      self3.segni.value or "Nessuno",
                }
                try:
                    eta_int = int(full["eta"])
                except (ValueError, KeyError):
                    await inter.response.send_message("❌ Età non valida.", ephemeral=True)
                    return

                await database.set_document(
                    str(cittadino.id),
                    full["nome"], full["cognome"], eta_int,
                    full["sesso"], full["residenza"],
                    foto_url,
                    extra={
                        "psn_id":       full.get("psn_id", "—"),
                        "data_nascita": full.get("data_nascita", "—"),
                        "nazionalita":  full.get("nazionalita", "—"),
                        "capelli":      full.get("capelli", "—"),
                        "occhi":        full.get("occhi", "—"),
                        "carnagione":   full.get("carnagione", "—"),
                        "segni":        full.get("segni", "—"),
                    }
                )

                embed = _build_doc_embed(cittadino, emittente, full, foto_url)
                view  = MostraDocumentoView(embed, inter.user)
                await inter.response.send_message(
                    content="✅ **Documento registrato con successo!**",
                    embed=embed, view=view, ephemeral=True
                )
                try:
                    await cittadino.send(
                        content="📜 **Il tuo documento d'identità è stato registrato!**",
                        embed=embed
                    )
                except Exception:
                    pass
                try:
                    ch = bot.get_channel(LOG_CHANNEL_ID)
                    if ch:
                        await ch.send(embed=embed)
                except Exception:
                    pass

        await interaction.response.send_modal(Modal3())


# ─────────────────────────────────────────────────────────────────────────────
#  COMANDI
# ─────────────────────────────────────────────────────────────────────────────
def setup_document_commands(bot):

    # ── /documento ───────────────────────────────────────────────────────────
    @bot.tree.command(name="documento", description="[Stato] Crea il documento d'identità ufficiale per un cittadino")
    @app_commands.describe(
        cittadino="Il cittadino",
        foto="Foto del personaggio (OBBLIGATORIA — carica un'immagine)"
    )
    async def documento(
        interaction: discord.Interaction,
        cittadino: discord.Member,
        foto: discord.Attachment
    ):
        if not has_stato(interaction):
            await interaction.response.send_message(
                "❌ Solo il ruolo **Stato** può emettere documenti d'identità.", ephemeral=True); return

        if not foto.content_type or not foto.content_type.startswith("image/"):
            await interaction.response.send_message(
                "❌ Il file caricato non è un'immagine valida. Carica un'immagine (jpg, png...).", ephemeral=True); return

        foto_url   = foto.url
        emittente  = interaction.user

        class Modal1(discord.ui.Modal, title="📒 Modulo Documenti — Parte 1"):
            psn_id       = discord.ui.TextInput(label="ID PSN",         style=discord.TextStyle.short, required=True, max_length=50)
            nome         = discord.ui.TextInput(label="Nome",            style=discord.TextStyle.short, required=True, max_length=50)
            cognome      = discord.ui.TextInput(label="Cognome",         style=discord.TextStyle.short, required=True, max_length=50)
            data_nascita = discord.ui.TextInput(label="Data di Nascita", style=discord.TextStyle.short, required=True, max_length=20, placeholder="es: 12/03/1885")
            eta          = discord.ui.TextInput(label="Età",             style=discord.TextStyle.short, required=True, max_length=3)

            async def on_submit(self, inter: discord.Interaction):
                data1 = {
                    "psn_id":       self.psn_id.value,
                    "nome":         self.nome.value,
                    "cognome":      self.cognome.value,
                    "data_nascita": self.data_nascita.value,
                    "eta":          self.eta.value,
                }
                view2 = Step2View(bot, cittadino, foto_url, emittente, data1)
                await inter.response.send_message(
                    "✅ **Parte 1 completata!** Premi il bottone per continuare.",
                    view=view2, ephemeral=True
                )

        await interaction.response.send_modal(Modal1())

    # ── /rimuovi-documento ───────────────────────────────────────────────────
    @bot.tree.command(name="rimuovi-documento", description="[Stato] Rimuovi il documento d'identità di un cittadino")
    @app_commands.describe(cittadino="Il cittadino")
    async def rimuovi_documento(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_stato(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM documents WHERE user_id=?", (str(cittadino.id),))
            await db.commit()

        embed = discord.Embed(
            title="🗑️ 𝐃𝐨𝐜𝐮𝐦𝐞𝐧𝐭𝐨 𝐑𝐢𝐦𝐨𝐬𝐬𝐨",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Cittadino",  value=cittadino.mention,        inline=True)
        embed.add_field(name="🔒 Rimosso da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Stato")
        await interaction.response.send_message(embed=embed)

    # ── /mostra-documento ────────────────────────────────────────────────────
    @bot.tree.command(name="mostra-documento", description="Mostra il tuo documento d'identità con tasto per renderlo pubblico")
    async def mostra_documento(interaction: discord.Interaction):
        doc = await database.get_document(str(interaction.user.id))
        if not doc:
            await interaction.response.send_message("❌ Non hai un documento registrato.", ephemeral=True); return

        extra = doc.get("extra") or {}
        data  = {
            "psn_id":       extra.get("psn_id", "—"),
            "nome":         doc.get("nome", "—"),
            "cognome":      doc.get("cognome", "—"),
            "data_nascita": extra.get("data_nascita", "—"),
            "eta":          str(doc.get("eta", "—")),
            "residenza":    doc.get("luogo_nascita", "—"),
            "nazionalita":  extra.get("nazionalita", "—"),
            "sesso":        doc.get("sesso", "—"),
            "capelli":      extra.get("capelli", "—"),
            "occhi":        extra.get("occhi", "—"),
            "carnagione":   extra.get("carnagione", "—"),
            "segni":        extra.get("segni", "—"),
        }
        embed = _build_doc_embed(interaction.user, interaction.user, data, doc.get("foto_url"))
        view  = MostraDocumentoView(embed, interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── /cercapersona ────────────────────────────────────────────────────────
    @bot.tree.command(name="cercapersona", description="[FDO] Cerca una persona nel registro")
    @app_commands.describe(cittadino="Il cittadino da cercare")
    async def cercapersona(interaction: discord.Interaction, cittadino: discord.Member):
        if not (has_sceriffo(interaction) or has_stato(interaction)):
            await interaction.response.send_message(
                "❌ Solo lo Sceriffo o lo Stato possono consultare il registro.", ephemeral=True); return

        await interaction.response.defer(ephemeral=True)

        doc     = await database.get_document(str(cittadino.id))
        fines   = await database.get_fines(str(cittadino.id))
        records = await database.get_criminal_records(str(cittadino.id))

        embed = discord.Embed(
            title=f"🔍 𝐑𝐢𝐜𝐞𝐫𝐜𝐚: {cittadino.display_name}",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)

        if doc:
            embed.add_field(name="📜 Identità", value=(
                f"**Nome:** {doc.get('nome','—')} {doc.get('cognome','—')}\n"
                f"**Età:** {doc.get('eta','—')} | **Sesso:** {doc.get('sesso','—')}\n"
                f"**Residenza:** {doc.get('luogo_nascita','—')}"
            ), inline=False)
            if doc.get("foto_url"):
                embed.set_image(url=doc["foto_url"])
        else:
            embed.add_field(name="📜 Identità", value="*Nessun documento registrato*", inline=False)

        embed.add_field(
            name="⭐ Taglie attive",
            value=f"{len(fines)} (${sum(f['amount'] for f in fines):,})",
            inline=True
        )
        embed.add_field(name="⚖️ Crimini registrati", value=str(len(records)), inline=True)
        embed.set_footer(text=f"🤠 Consultato da: {interaction.user.display_name}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /vedi-documento ──────────────────────────────────────────────────────
    @bot.tree.command(name="vedi-documento", description="[Staff] Visualizza il documento di un cittadino")
    @app_commands.describe(cittadino="Il cittadino di cui vedere il documento")
    async def vedi_documento(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_staff_doc(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        doc = await database.get_document(str(cittadino.id))
        if not doc:
            await interaction.followup.send(
                f"❌ {cittadino.mention} non ha un documento registrato.", ephemeral=True
            )
            return

        extra = doc.get("extra") or {}
        data  = {
            "psn_id":       extra.get("psn_id", "—"),
            "nome":         doc.get("nome", "—"),
            "cognome":      doc.get("cognome", "—"),
            "data_nascita": extra.get("data_nascita", "—"),
            "eta":          str(doc.get("eta", "—")),
            "residenza":    doc.get("luogo_nascita", "—"),
            "nazionalita":  extra.get("nazionalita", "—"),
            "sesso":        doc.get("sesso", "—"),
            "capelli":      extra.get("capelli", "—"),
            "occhi":        extra.get("occhi", "—"),
            "carnagione":   extra.get("carnagione", "—"),
            "segni":        extra.get("segni", "—"),
        }
        embed = _build_doc_embed(cittadino, interaction.user, data, doc.get("foto_url"))
        await interaction.followup.send(embed=embed, ephemeral=True)

        # DM al cittadino
        try:
            dm = discord.Embed(
                title="👁️ Il tuo documento è stato consultato",
                description=f"Lo staff {interaction.user.mention} ha visualizzato il tuo documento d'identità.",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            dm.set_footer(text="🤠 Red Dead Redemption II — Documento Ufficiale")
            await cittadino.send(embed=dm)
        except Exception:
            pass

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(
                    title="👁️ LOG — Documento Consultato da Staff",
                    color=discord.Color(0x8B4513),
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
                log.add_field(name="👤 Cittadino", value=cittadino.mention,        inline=True)
                await ch.send(embed=log)
        except Exception:
            pass
