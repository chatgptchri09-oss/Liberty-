import discord
from discord import app_commands
import database
import aiosqlite
import datetime
from constants import STATO_ROLE_ID, LOG_CHANNEL_ID, has_sceriffo, DATABASE_NAME

# ── UTILITY PERMESSI ─────────────────────────────────────────────────────────
def has_stato(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == STATO_ROLE_ID for r in interaction.user.roles)

# ── VIEW PER PUBBLICARE IL DOCUMENTO ─────────────────────────────────────────
class MostraDocumentoView(discord.ui.View):
    def __init__(self, embed: discord.Embed, richiedente: discord.Member):
        super().__init__(timeout=None)
        self.embed = embed
        self.richiedente = richiedente

    @discord.ui.button(label="📢 Mostra a tutti", style=discord.ButtonStyle.primary)
    async def mostra(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.send(
            content=f"📜 {self.richiedente.mention} ha mostrato il suo documento:",
            embed=self.embed
        )
        await interaction.response.send_message("Documento mostrato con successo!", ephemeral=True)

# ── COSTRUZIONE EMBED (Grafica Originale) ────────────────────────────────────
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
    embed.add_field(name="💇 Capelli",           value=data.get("capelli", "—"),       inline=True)
    embed.add_field(name="👁️ Occhi",             value=data.get("occhi", "—"),         inline=True)
    embed.add_field(name="🎨 Carnagione",        value=data.get("carnagione", "—"),    inline=True)
    embed.add_field(name="🔍 Segni Particolari", value=data.get("segni", "—"),         inline=True)
    if foto_url:
        embed.set_image(url=foto_url)
    embed.add_field(name="🔒 Emesso da",         value=emittente.mention,              inline=True)
    embed.set_footer(text="🤠 Red Dead Redemption II — Documento Ufficiale")
    return embed

# ── MODAL UNICO (Per evitare l'errore "Qualcosa è andato storto") ────────────
class DocumentoModal(discord.ui.Modal, title="📒 Creazione Documento"):
    linea1 = discord.ui.TextInput(label="PSN ID | Nome | Cognome", placeholder="Esempio: RedDead_99 | Arthur | Morgan", required=True)
    linea2 = discord.ui.TextInput(label="Data Nascita | Età", placeholder="Esempio: 15/05/1890 | 34", required=True)
    linea3 = discord.ui.TextInput(label="Residenza | Nazionalità | Sesso", placeholder="Esempio: Blackwater | Americana | Uomo", required=True)
    linea4 = discord.ui.TextInput(label="Capelli | Occhi | Carnagione", placeholder="Esempio: Neri | Verdi | Chiara", required=True)
    linea5 = discord.ui.TextInput(label="Segni Particolari", placeholder="Esempio: Cicatrice sulla guancia (o scrivi Nessuno)", required=False)

    def __init__(self, bot, cittadino, foto_url, emittente):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino
        self.foto_url = foto_url
        self.emittente = emittente

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Split dei dati inseriti (gestisce gli spazi dopo il simbolo '|')
        p1 = [x.strip() for x in self.linea1.value.split('|')]
        p2 = [x.strip() for x in self.linea2.value.split('|')]
        p3 = [x.strip() for x in self.linea3.value.split('|')]
        p4 = [x.strip() for x in self.linea4.value.split('|')]

        full_data = {
            "psn_id": p1[0] if len(p1)>0 else "—",
            "nome": p1[1] if len(p1)>1 else "—",
            "cognome": p1[2] if len(p1)>2 else "—",
            "data_nascita": p2[0] if len(p2)>0 else "—",
            "eta": p2[1] if len(p2)>1 else "0",
            "residenza": p3[0] if len(p3)>0 else "—",
            "nazionalita": p3[1] if len(p3)>1 else "—",
            "sesso": p3[2] if len(p3)>2 else "—",
            "capelli": p4[0] if len(p4)>0 else "—",
            "occhi": p4[1] if len(p4)>1 else "—",
            "carnagione": p4[2] if len(p4)>2 else "—",
            "segni": self.linea5.value or "Nessuno"
        }

        # Conversione età
        try: eta_int = int("".join(filter(str.isdigit, full_data["eta"])))
        except: eta_int = 0

        # Salvataggio Database
        await database.set_document(
            str(self.cittadino.id),
            full_data["nome"], full_data["cognome"], eta_int,
            full_data["sesso"], full_data["residenza"],
            self.foto_url,
            extra=full_data
        )

        embed = _build_doc_embed(self.cittadino, self.emittente, full_data, self.foto_url)
        view = MostraDocumentoView(embed, self.cittadino)

        await interaction.followup.send("✅ Documento creato con successo!", embed=embed, view=view)
        
        # DM e Log
        try: await self.cittadino.send("📜 Il tuo documento ufficiale è stato emesso!", embed=embed)
        except: pass
        ch = self.bot.get_channel(LOG_CHANNEL_ID)
        if ch: await ch.send(embed=embed)

# ── SETUP COMANDI ────────────────────────────────────────────────────────────
def setup_document_commands(bot):

    @bot.tree.command(name="documento", description="[Stato] Crea il documento per un cittadino")
    async def documento(interaction: discord.Interaction, cittadino: discord.Member, foto: discord.Attachment):
        if not has_stato(interaction):
            await interaction.response.send_message("❌ Solo lo Stato può emettere documenti.", ephemeral=True); return
        if not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Devi caricare una foto!", ephemeral=True); return
        
        await interaction.response.send_modal(DocumentoModal(bot, cittadino, foto.url, interaction.user))

    @bot.tree.command(name="rimuovi-documento", description="[Stato] Rimuovi un documento")
    async def rimuovi_documento(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_stato(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM documents WHERE user_id=?", (str(cittadino.id),))
            await db.commit()
        await interaction.response.send_message(f"🗑️ Documento di {cittadino.mention} eliminato.", ephemeral=False)

    @bot.tree.command(name="mostra-documento", description="Visualizza il tuo documento")
    async def mostra_documento(interaction: discord.Interaction):
        doc = await database.get_document(str(interaction.user.id))
        if not doc:
            await interaction.response.send_message("❌ Non hai un documento registrato.", ephemeral=True); return
        
        extra = doc.get("extra") or {}
        data = {
            "psn_id": extra.get("psn_id", "—"),
            "nome": doc.get("nome", "—"),
            "cognome": doc.get("cognome", "—"),
            "data_nascita": extra.get("data_nascita", "—"),
            "eta": str(doc.get("eta", "—")),
            "residenza": doc.get("luogo_nascita", "—"),
            "nazionalita": extra.get("nazionalita", "—"),
            "sesso": doc.get("sesso", "—"),
            "capelli": extra.get("capelli", "—"),
            "occhi": extra.get("occhi", "—"),
            "carnagione": extra.get("carnagione", "—"),
            "segni": extra.get("segni", "—"),
        }
        embed = _build_doc_embed(interaction.user, interaction.user, data, doc.get("foto_url"))
        await interaction.response.send_message(embed=embed, view=MostraDocumentoView(embed, interaction.user), ephemeral=True)

    @bot.tree.command(name="cercapersona", description="[FDO/Stato] Cerca nel registro civile")
    async def cercapersona(interaction: discord.Interaction, cittadino: discord.Member):
        if not (has_sceriffo(interaction) or has_stato(interaction)):
            await interaction.response.send_message("❌ Accesso negato.", ephemeral=True); return

        await interaction.response.defer(ephemeral=True)
        doc = await database.get_document(str(cittadino.id))
        fines = await database.get_fines(str(cittadino.id))
        records = await database.get_criminal_records(str(cittadino.id))

        embed = discord.Embed(title=f"🔍 Ricerca: {cittadino.display_name}", color=0x8B4513)
        if doc:
            embed.add_field(name="📜 Identità", value=f"**Nome:** {doc['nome']} {doc.get('cognome','')}\n**Residenza:** {doc['luogo_nascita']}", inline=False)
            embed.set_image(url=doc.get("foto_url"))
        else:
            embed.add_field(name="📜 Identità", value="Nessun documento trovato.", inline=False)
        
        embed.add_field(name="⚖️ Fedina", value=f"Multe: {len(fines)} | Reati: {len(records)}", inline=True)
        await interaction.followup.send(embed=embed)
