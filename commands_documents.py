import discord
from discord import app_commands
import database
import aiosqlite
from constants import STATO_ROLE_ID, LOG_CHANNEL_ID, has_sceriffo, DATABASE_NAME

def has_stato(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == STATO_ROLE_ID for r in interaction.user.roles)

# --- View per mostrare il documento in pubblico ---
class MostraDocumentoView(discord.ui.View):
    def __init__(self, embed: discord.Embed, richiedente: discord.Member):
        super().__init__(timeout=300)
        self.embed = embed
        self.richiedente = richiedente

    @discord.ui.button(label="📢 Mostra", style=discord.ButtonStyle.primary)
    async def mostra(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(
            content=f"📜 Questo documento è stato mostrato da {self.richiedente.mention}",
            embed=self.embed
        )

def _build_doc_embed(cittadino, emittente, data: dict, foto_url):
    embed = discord.Embed(
        title="<a:documento:1458563773546893541> 𝐃𝐎𝐂𝐔𝐌𝐄𝐍𝐓𝐎 𝐃'𝐈𝐃𝐄𝐍𝐓𝐈𝐓À 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄",
        color=discord.Color(0x8B4513),
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=cittadino.display_avatar.url)
    embed.add_field(name="👤 ID PSN", value=data.get("psn_id", "—"), inline=True)
    embed.add_field(name="🔖 ID Discord", value=cittadino.mention, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="👤 Nome", value=data.get("nome", "—"), inline=True)
    embed.add_field(name="👥 Cognome", value=data.get("cognome", "—"), inline=True)
    embed.add_field(name="📅 Data di Nascita", value=data.get("data_nascita", "—"), inline=True)
    embed.add_field(name="🎂 Età", value=str(data.get("eta", "—")), inline=True)
    embed.add_field(name="📍 Residenza", value=data.get("residenza", "—"), inline=True)
    embed.add_field(name="🌍 Nazionalità", value=data.get("nazionalita", "—"), inline=True)
    embed.add_field(name="⚧ Sesso", value=data.get("sesso", "—"), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="💇 Capelli", value=data.get("capelli", "—"), inline=True)
    embed.add_field(name="👁️ Occhi", value=data.get("occhi", "—"), inline=True)
    embed.add_field(name="🎨 Carnagione", value=data.get("carnagione", "—"), inline=True)
    embed.add_field(name="🔍 Segni", value=data.get("segni", "—"), inline=True)
    if foto_url:
        embed.set_image(url=foto_url)
    embed.add_field(name="🔒 Emesso da", value=emittente.mention, inline=True)
    embed.set_footer(text="🤠 Red Dead Redemption II — Documento Ufficiale")
    return embed

# --- STEP FINALE: Raccolta dati rimanenti tramite Modal finale ---
class FinalStepModal(discord.ui.Modal, title="Dettagli Finali Documento"):
    residenza = discord.ui.TextInput(label="Residenza", placeholder="Es: Saint Denis", required=True)
    nazionalita = discord.ui.TextInput(label="Nazionalità", placeholder="Es: Americana", required=True)
    tratti_fisici = discord.ui.TextInput(
        label="Capelli, Occhi, Carnagione", 
        placeholder="Es: Neri, Verdi, Chiara", 
        style=discord.TextStyle.long,
        required=True
    )
    sesso = discord.ui.TextInput(label="Sesso", placeholder="Uomo / Donna", max_length=10, required=True)
    segni = discord.ui.TextInput(label="Segni Particolari", placeholder="Nessuno", required=False)

    def __init__(self, bot, cittadino, foto_url, emittente, data_precedente):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino
        self.foto_url = foto_url
        self.emittente = emittente
        self.data_precedente = data_precedente

    async def on_submit(self, interaction: discord.Interaction):
        # Splittiamo i tratti fisici per semplicità o li teniamo come stringa
        tratti = self.tratti_fisici.value.split(',')
        capelli = tratti[0].strip() if len(tratti) > 0 else "—"
        occhi = tratti[1].strip() if len(tratti) > 1 else "—"
        carnagione = tratti[2].strip() if len(tratti) > 2 else "—"

        full_data = {
            **self.data_precedente,
            "residenza": self.residenza.value,
            "nazionalita": self.nazionalita.value,
            "sesso": self.sesso.value,
            "capelli": capelli,
            "occhi": occhi,
            "carnagione": carnagione,
            "segni": self.segni.value or "Nessuno"
        }

        # Salvataggio Database
        try:
            eta_int = int(full_data["eta"])
        except: eta_int = 0

        await database.set_document(
            str(self.cittadino.id),
            full_data["nome"], full_data["cognome"], eta_int,
            full_data["sesso"], full_data["residenza"],
            self.foto_url,
            extra=full_data
        )

        embed = _build_doc_embed(self.cittadino, self.emittente, full_data, self.foto_url)
        view = MostraDocumentoView(embed, interaction.user)
        
        await interaction.response.send_message(
            content="✅ **Documento creato con successo!**",
            embed=embed, view=view, ephemeral=True
        )

        # Log e DM
        try:
            await self.cittadino.send(content="📜 Il tuo documento è pronto!", embed=embed)
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except: pass

# --- STEP 1: Modal Iniziale ---
class InizioDocumentoModal(discord.ui.Modal, title="Modulo Documenti - Parte 1"):
    psn_id = discord.ui.TextInput(label="ID PSN", required=True)
    nome = discord.ui.TextInput(label="Nome", required=True)
    cognome = discord.ui.TextInput(label="Cognome", required=True)
    data_nascita = discord.ui.TextInput(label="Data di Nascita", placeholder="GG/MM/AAAA", required=True)
    eta = discord.ui.TextInput(label="Età", max_length=3, required=True)

    def __init__(self, bot, cittadino, foto_url, emittente):
        super().__init__()
        self.bot = bot
        self.cittadino = cittadino
        self.foto_url = foto_url
        self.emittente = emittente

    async def on_submit(self, interaction: discord.Interaction):
        data1 = {
            "psn_id": self.psn_id.value,
            "nome": self.nome.value,
            "cognome": self.cognome.value,
            "data_nascita": self.data_nascita.value,
            "eta": self.eta.value,
        }
        
        # Invece di mandare un'altra View con bottone, apriamo subito il secondo modal tramite una "scusa" tecnica
        # o inviamo un bottone che non scade mai.
        class ContinueView(discord.ui.View):
            def __init__(self, bot, cittadino, foto_url, emittente, data1):
                super().__init__(timeout=None)
                self.bot, self.cit, self.foto, self.emi, self.d1 = bot, cittadino, foto_url, emittente, data1

            @discord.ui.button(label="Ultimo Step: Dettagli Fisici", style=discord.ButtonStyle.green)
            async def next_step(self, inter: discord.Interaction, button: discord.ui.Button):
                await inter.response.send_modal(FinalStepModal(self.bot, self.cit, self.foto, self.emi, self.d1))

        await interaction.response.send_message(
            "Dati anagrafici salvati. Clicca qui sotto per inserire i dati fisici e completare.",
            view=ContinueView(self.bot, self.cittadino, self.foto_url, self.emittente, data1),
            ephemeral=True
        )

def setup_document_commands(bot):
    @bot.tree.command(name="documento", description="Crea il documento d'identità")
    @app_commands.describe(cittadino="Il cittadino", foto="Carica la foto")
    async def documento(interaction: discord.Interaction, cittadino: discord.Member, foto: discord.Attachment):
        if not has_stato(interaction):
            await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True); return
        
        if not foto.content_type.startswith("image/"):
            await interaction.response.send_message("❌ Carica un'immagine valida.", ephemeral=True); return

        await interaction.response.send_modal(InizioDocumentoModal(bot, cittadino, foto.url, interaction.user))

    # --- Comandi Rimuovi e Mostra rimangono invariati ---
    @bot.tree.command(name="rimuovi-documento", description="Rimuovi documento")
    async def rimuovi_documento(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_stato(interaction): return
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM documents WHERE user_id=?", (str(cittadino.id),))
            await db.commit()
        await interaction.response.send_message(f"✅ Documento di {cittadino.mention} rimosso.")

    @bot.tree.command(name="mostra-documento", description="Mostra il tuo documento")
    async def mostra_documento(interaction: discord.Interaction):
        doc = await database.get_document(str(interaction.user.id))
        if not doc:
            await interaction.response.send_message("❌ Non hai un documento.", ephemeral=True); return
        
        extra = doc.get("extra") or {}
        # Mappatura dati per l'embed
        data = {**extra, "nome": doc['nome'], "cognome": doc['cognome'], "eta": doc['eta'], "residenza": doc['luogo_nascita'], "sesso": doc['sesso']}
        embed = _build_doc_embed(interaction.user, interaction.user, data, doc.get("foto_url"))
        await interaction.response.send_message(embed=embed, view=MostraDocumentoView(embed, interaction.user), ephemeral=True)
