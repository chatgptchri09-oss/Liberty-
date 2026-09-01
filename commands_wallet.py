import discord
from discord import app_commands
import database
from constants import (
    BANKER_ROLE_ID, BANK_CHANNEL_ID, LOG_CHANNEL_ID,
    STAFF_ROLES, has_staff
)

# ── Ruoli per dare armi/cavalli ────────────────────────────────────────────────
ARMAIOLO_ROLE_ID = 1404051953188733002   # può usare /dai-arma
STALLIERE_ROLE_ID = 1404051942698913792  # può usare /dai-cavallo


def _has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == role_id for r in interaction.user.roles)


# ── Scelte armi/cavalli ─────────────────────────────────────────────────────────
TIPO_ARMA_CHOICES = [
    app_commands.Choice(name="🔫 Pistola",                 value="Pistola"),
    app_commands.Choice(name="🔫 Revolver",                value="Revolver"),
    app_commands.Choice(name="🔫 Fucile a Pompa",          value="Fucile a Pompa"),
    app_commands.Choice(name="🔫 Fucile a Ripetizione",    value="Fucile a Ripetizione"),
    app_commands.Choice(name="🎯 Fucile di Precisione",    value="Fucile di Precisione"),
    app_commands.Choice(name="🏹 Arco",                    value="Arco"),
    app_commands.Choice(name="🗡️ Coltello / Ascia da lancio", value="Coltello / Ascia da lancio"),
    app_commands.Choice(name="💣 Esplosivo (Dinamite/Molotov)", value="Esplosivo"),
    app_commands.Choice(name="🪢 Lazo",                    value="Lazo"),
]

SESSO_CAVALLO_CHOICES = [
    app_commands.Choice(name="♂️ Stallone", value="Stallone"),
    app_commands.Choice(name="♀️ Giumenta", value="Giumenta"),
    app_commands.Choice(name="✂️ Castrato", value="Castrato"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  PORTAFOGLIO — Select Menu con Documento, Bisaccia, Proprietà, Fedina,
#  Armi, Cavalli (NO SOLDI) + tasto "📢 Mostra" per condividere in chat
# ══════════════════════════════════════════════════════════════════════════════

def _hunger_bar(v: int) -> str:
    f = round(v / 10)
    return "█" * f + "░" * (10 - f) + f"  **{v}%**"


class PortafoglioSelect(discord.ui.Select):
    def __init__(self, target: discord.Member):
        self.target = target
        options = [
            discord.SelectOption(label="📜 Documento d'identità", value="documento",
                                 description="Visualizza il tuo documento ufficiale"),
            discord.SelectOption(label="🎒 Bisaccia", value="bisaccia",
                                 description="Contenuto della tua bisaccia e stato fisico"),
            discord.SelectOption(label="🏡 Proprietà", value="proprieta",
                                 description="Le tue proprietà nel Far West"),
            discord.SelectOption(label="⚖️ Fedina Penale", value="fedina",
                                 description="I tuoi precedenti con la legge"),
            discord.SelectOption(label="🔫 Armi", value="armi",
                                 description="Le armi in tuo possesso"),
            discord.SelectOption(label="🐴 Cavalli", value="cavalli",
                                 description="I cavalli in tuo possesso"),
        ]
        super().__init__(placeholder="Seleziona una sezione...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        user_id = str(self.target.id)
        view: "PortafoglioView" = self.view

        if val == "documento":
            doc = await database.get_document(user_id)
            embed = discord.Embed(
                title="📜 𝐃𝐨𝐜𝐮𝐦𝐞𝐧𝐭𝐨 𝐝'𝐈𝐝𝐞𝐧𝐭𝐢𝐭à",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            if not doc:
                embed.description = "*Nessun documento registrato. Contatta le autorità.*"
            else:
                embed.add_field(name="👤 Nome",            value=doc["nome"],          inline=True)
                embed.add_field(name="👥 Cognome",         value=doc["cognome"],        inline=True)
                embed.add_field(name="🎂 Età",             value=str(doc["eta"]),       inline=True)
                embed.add_field(name="⚧ Sesso",            value=doc["sesso"],          inline=True)
                embed.add_field(name="📍 Luogo di nascita",value=doc["luogo_nascita"],  inline=True)
                embed.add_field(name="📅 Emesso il",       value=doc["created_at"],     inline=True)
                if doc.get("foto_url"):
                    embed.set_image(url=doc["foto_url"])
            embed.set_footer(text="🤠 Red Dead Redemption II — Documento")
            label = "📜 Documento d'identità"

        elif val == "bisaccia":
            items = await database.get_inventory(user_id)
            user  = await database.get_user(user_id)
            embed = discord.Embed(
                title="🎒 𝐁𝐢𝐬𝐚𝐜𝐜𝐢𝐚",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="🍔 Fame", value=_hunger_bar(user["hunger"]), inline=True)
            embed.add_field(name="💦 Sete", value=_hunger_bar(user["thirst"]), inline=True)
            if not items:
                embed.add_field(name="📦 Contenuto", value="*Bisaccia vuota.*", inline=False)
            else:
                desc = "\n".join(f"**{i['item_name']}** — x{i['quantity']}" for i in items)
                embed.add_field(name="📦 Contenuto", value=desc, inline=False)
            embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
            label = "🎒 Bisaccia"

        elif val == "proprieta":
            props = await database.get_properties(user_id)
            embed = discord.Embed(
                title="🏡 𝐏𝐫𝐨𝐩𝐫𝐢𝐞𝐭à",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            if not props:
                embed.description = "*Non possiedi ancora nessuna proprietà nel Far West.*"
            else:
                for p in props:
                    embed.add_field(
                        name=f"{p['property_type']} — {p['property_name']}",
                        value=f"📍 {p['location']}\n📅 {p['created_at']}",
                        inline=False
                    )
            embed.set_footer(text="🤠 Red Dead Redemption II — Proprietà")
            label = "🏡 Proprietà"

        elif val == "fedina":
            records = await database.get_criminal_records(user_id)
            embed = discord.Embed(
                title="⚖️ 𝐅𝐞𝐝𝐢𝐧𝐚 𝐏𝐞𝐧𝐚𝐥𝐞",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            if not records:
                embed.description = "✅ *Nessun crimine registrato. Sei un uomo onesto, cowboy.*"
            else:
                for r in records[:8]:
                    embed.add_field(
                        name=f"⚖️ {r['crime']}",
                        value=f"🔒 {r['sentence']}\n👮 {r['officer']}\n📅 {r['created_at']}",
                        inline=False
                    )
            embed.set_footer(text="🤠 Red Dead Redemption II — Fedina Penale")
            label = "⚖️ Fedina Penale"

        elif val == "armi":
            armi = await database.get_weapons(user_id)
            embed = discord.Embed(
                title="🔫 𝐀𝐫𝐦𝐢",
                color=discord.Color(0x2C2C2C),
                timestamp=discord.utils.utcnow()
            )
            if not armi:
                embed.description = "*Non possiedi nessuna arma registrata.*"
            else:
                for a in armi[:10]:
                    dettagli_line = f"\n📝 {a['dettagli']}" if a.get("dettagli") else ""
                    embed.add_field(
                        name=f"🔫 {a['nome_arma']}",
                        value=f"🏷️ Tipo: {a['tipo']}{dettagli_line}\n📅 {a['created_at']}",
                        inline=False
                    )
            embed.set_footer(text="🤠 Red Dead Redemption II — Armi")
            label = "🔫 Armi"

        elif val == "cavalli":
            cavalli = await database.get_horses(user_id)
            embed = discord.Embed(
                title="🐴 𝐂𝐚𝐯𝐚𝐥𝐥𝐢",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            if not cavalli:
                embed.description = "*Non possiedi nessun cavallo registrato.*"
            else:
                for cv in cavalli[:10]:
                    eta_line = f"\n🎂 Età: {cv['eta']}" if cv.get("eta") else ""
                    embed.add_field(
                        name=f"🐴 {cv['nome']}",
                        value=(
                            f"🏇 Razza: {cv['razza']}\n"
                            f"🎨 Colore: {cv['colore']}\n"
                            f"⚧ Sesso: {cv['sesso']}{eta_line}\n"
                            f"💵 Prezzo: ${cv['prezzo']:,}\n"
                            f"📅 {cv['created_at']}"
                        ),
                        inline=False
                    )
            embed.set_footer(text="🤠 Red Dead Redemption II — Cavalli")
            label = "🐴 Cavalli"

        else:
            return

        # Salva l'embed corrente nella view per il tasto "📢 Mostra"
        view.current_embed = embed
        view.current_label = label
        await interaction.response.edit_message(embed=embed, view=view)


class PortafoglioView(discord.ui.View):
    def __init__(self, target: discord.Member, extra_viewer_id: str = None):
        super().__init__(timeout=180)
        self.target          = target
        self.extra_viewer_id = extra_viewer_id  # es. uno staff che usa /visualizza-portafoglio
        self.current_embed: discord.Embed | None = None
        self.current_label: str | None = None
        self.add_item(PortafoglioSelect(target))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.target.id:
            return True
        if self.extra_viewer_id and str(interaction.user.id) == self.extra_viewer_id:
            return True
        await interaction.response.send_message("❌ Questo portafoglio non è tuo!", ephemeral=True)
        return False

    @discord.ui.button(label="📢 Mostra", style=discord.ButtonStyle.blurple, row=1)
    async def mostra(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_embed is None:
            await interaction.response.send_message(
                "❌ Seleziona prima una sezione dal menu.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            content=f"{interaction.user.mention} ha mostrato **{self.current_label}** di {self.target.mention}:",
            embed=self.current_embed
        )


# ══════════════════════════════════════════════════════════════════════════════
#  BANCA — Preleva/Deposita con approvazione banchiere
# ══════════════════════════════════════════════════════════════════════════════

class BancaModal(discord.ui.Modal):
    importo_field = discord.ui.TextInput(
        label="Importo ($)",
        placeholder="Es: 500",
        required=True,
        max_length=10
    )

    def __init__(self, action: str):
        self.action = action
        title = "💸 Richiesta Prelievo" if action == "preleva" else "🏦 Richiesta Deposito"
        super().__init__(title=title)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.importo_field.value.replace(",","").replace("$","").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Importo non valido. Inserisci un numero intero positivo.", ephemeral=True)
            return

        user = await database.get_user(str(interaction.user.id))

        if self.action == "preleva" and amount > user["bank"]:
            await interaction.response.send_message(
                f"❌ Saldo banca insufficiente. Disponibile: **${user['bank']:,}**", ephemeral=True
            )
            return
        if self.action == "deposita" and amount > user["cash"]:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti. Disponibile: **${user['cash']:,}**", ephemeral=True
            )
            return

        bank_ch = interaction.guild.get_channel(BANK_CHANNEL_ID)
        if bank_ch is None:
            await interaction.response.send_message("❌ Canale banca non trovato.", ephemeral=True)
            return

        label = "Prelievo" if self.action == "preleva" else "Deposito"
        embed = discord.Embed(
            title=f"🏦 𝐑𝐢𝐜𝐡𝐢𝐞𝐬𝐭𝐚 𝐝𝐢 {label}",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 Cliente",        value=interaction.user.mention,  inline=True)
        embed.add_field(name="💰 Importo",         value=f"${amount:,}",            inline=True)
        embed.add_field(name="📋 Operazione",      value=label,                     inline=True)
        embed.add_field(name="💵 Contanti att.",   value=f"${user['cash']:,}",      inline=True)
        embed.add_field(name="🏦 Banca att.",      value=f"${user['bank']:,}",      inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Banca | Solo il Banchiere può approvare")

        view = ConfermaOperazioneView(str(interaction.user.id), amount, self.action)
        await bank_ch.send(
            content=f"<@&{BANKER_ROLE_ID}> — Nuova richiesta da {interaction.user.mention}",
            embed=embed,
            view=view
        )
        await interaction.response.send_message(
            f"✅ Richiesta di **{label.lower()}** di **${amount:,}** inviata al Banchiere. Riceverai una notifica in DM.",
            ephemeral=True
        )


class ConfermaOperazioneView(discord.ui.View):
    def __init__(self, user_id: str, amount: int, action: str):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.amount  = amount
        self.action  = action

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        if not any(r.id == BANKER_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ Solo il **Banchiere** può gestire questa richiesta.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Conferma", style=discord.ButtonStyle.green)
    async def conferma(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await database.get_user(self.user_id)
        if self.action == "preleva":
            if self.amount > user["bank"]:
                await interaction.response.edit_message(content="❌ Fondi insufficienti — operazione annullata.", view=None)
                return
            await database.update_balance(self.user_id, cash=user["cash"]+self.amount, bank=user["bank"]-self.amount)
            esito = f"💵 Hai prelevato **${self.amount:,}**. I contanti sono stati aggiunti al tuo portafoglio."
        else:
            if self.amount > user["cash"]:
                await interaction.response.edit_message(content="❌ Contanti insufficienti — operazione annullata.", view=None)
                return
            await database.update_balance(self.user_id, cash=user["cash"]-self.amount, bank=user["bank"]+self.amount)
            esito = f"🏦 Hai depositato **${self.amount:,}** in banca."

        for c in self.children: c.disabled = True
        await interaction.response.edit_message(
            content=f"✅ **Operazione approvata da {interaction.user.display_name}**", view=self
        )
        guild  = interaction.guild
        member = guild.get_member(int(self.user_id))
        if member:
            try:
                dm = discord.Embed(title="🏦 𝐎𝐩𝐞𝐫𝐚𝐳𝐢𝐨𝐧𝐞 𝐁𝐚𝐧𝐜𝐚𝐫𝐢𝐚 𝐀𝐩𝐩𝐫𝐨𝐯𝐚𝐭𝐚", description=esito,
                                   color=discord.Color.green(), timestamp=discord.utils.utcnow())
                dm.set_footer(text="🤠 Red Dead Redemption II — Banca")
                await member.send(embed=dm)
            except Exception:
                pass

    @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.red)
    async def annulla(self, interaction: discord.Interaction, button: discord.ui.Button):
        for c in self.children: c.disabled = True
        await interaction.response.edit_message(
            content=f"❌ **Operazione annullata da {interaction.user.display_name}**", view=self
        )
        guild  = interaction.guild
        member = guild.get_member(int(self.user_id))
        if member:
            try:
                label = "prelievo" if self.action == "preleva" else "deposito"
                dm = discord.Embed(
                    title="🏦 𝐎𝐩𝐞𝐫𝐚𝐳𝐢𝐨𝐧𝐞 𝐁𝐚𝐧𝐜𝐚𝐫𝐢𝐚 𝐑𝐢𝐟𝐢𝐮𝐭𝐚𝐭𝐚",
                    description=f"La tua richiesta di **{label}** di **${self.amount:,}** è stata **rifiutata** dal Banchiere.",
                    color=discord.Color.red(), timestamp=discord.utils.utcnow()
                )
                dm.set_footer(text="🤠 Red Dead Redemption II — Banca")
                await member.send(embed=dm)
            except Exception:
                pass


class BancaView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Questo non è il tuo conto!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Preleva", style=discord.ButtonStyle.green, emoji="💸")
    async def preleva(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BancaModal("preleva"))

    @discord.ui.button(label="Deposita", style=discord.ButtonStyle.blurple, emoji="🏦")
    async def deposita(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BancaModal("deposita"))


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════════════════════════════════════

def setup_wallet_commands(bot):

    # ── /portafoglio ─────────────────────────────────────────────────────────
    @bot.tree.command(name="portafoglio", description="Apri il tuo portafoglio personale")
    async def portafoglio(interaction: discord.Interaction):
        embed = discord.Embed(
            # ⚠️ FIX: le menzioni (@utente) non vengono renderizzate nei TITOLI
            # degli embed su Discord — mostrano solo il testo grezzo "<@123..>".
            # Per questo si vedevano numeri e una @. Ora uso il display_name.
            title=f"<a:Portafoglio:1462442004569919629> 𝐏𝐨𝐫𝐭𝐚𝐟𝐨𝐠𝐥𝐢𝐨 𝐝𝐢 {interaction.user.display_name}",
            description=(
                "Seleziona una sezione dal menu qui sotto per visualizzare\n"
                "le tue informazioni personali nel Far West.\n\n"
                "📢 Premi **Mostra** per condividerla pubblicamente in chat."
            ),
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Portafoglio")
        view = PortafoglioView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── /visualizza-portafoglio [Staff] ─────────────────────────────────────
    @bot.tree.command(name="visualizza-portafoglio", description="[Staff] Visualizza il portafoglio di un giocatore")
    @app_commands.describe(giocatore="Il giocatore di cui vedere il portafoglio")
    async def visualizza_portafoglio(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"<a:Portafoglio:1462442004569919629> 𝐏𝐨𝐫𝐭𝐚𝐟𝐨𝐠𝐥𝐢𝐨 𝐝𝐢 {giocatore.display_name}",
            description=(
                "Seleziona una sezione dal menu qui sotto per visualizzare\n"
                f"le informazioni di **{giocatore.display_name}** nel Far West.\n\n"
                "📢 Premi **Mostra** per condividerla pubblicamente in chat."
            ),
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.set_footer(text=f"🤠 Red Dead Redemption II — Portafoglio (visualizzato da {interaction.user.display_name})")
        view = PortafoglioView(giocatore, extra_viewer_id=str(interaction.user.id))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── /banca ───────────────────────────────────────────────────────────────
    @bot.tree.command(name="banca", description="Accedi al tuo conto bancario")
    async def banca(interaction: discord.Interaction):
        user = await database.get_user(str(interaction.user.id))
        embed = discord.Embed(
            title="🏦 𝐁𝐚𝐧𝐜𝐚 𝐝𝐞𝐥 𝐅𝐚𝐫 𝐖𝐞𝐬𝐭",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 Correntista", value=interaction.user.mention,        inline=False)
        embed.add_field(name="💵 Contanti",    value=f"${user['cash']:,}",            inline=True)
        embed.add_field(name="🏦 In banca",    value=f"${user['bank']:,}",            inline=True)
        embed.add_field(name="💰 Totale",      value=f"${user['cash']+user['bank']:,}", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Le operazioni richiedono l'approvazione del Banchiere")
        await interaction.response.send_message(embed=embed, view=BancaView(str(interaction.user.id)), ephemeral=True)

    # ── /paga (ex /bonifico) ─────────────────────────────────────────────────
    @bot.tree.command(name="paga", description="Paga un altro giocatore in contanti (trasferimento diretto)")
    @app_commands.describe(
        giocatore="Il giocatore a cui pagare",
        importo="Importo in $ da pagare",
        causale="Motivo del pagamento (opzionale)"
    )
    async def paga(interaction: discord.Interaction, giocatore: discord.Member, importo: int, causale: str = ""):
        if giocatore.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi pagare te stesso.", ephemeral=True)
            return
        if giocatore.bot:
            await interaction.response.send_message("❌ Non puoi pagare un bot.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        mittente = await database.get_user(str(interaction.user.id))
        if mittente["cash"] < importo:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti. Disponibile: **${mittente['cash']:,}**", ephemeral=True
            )
            return

        destinatario = await database.get_user(str(giocatore.id))

        # Trasferisce in CONTANTI (non banca)
        await database.update_balance(str(interaction.user.id), cash=mittente["cash"] - importo)
        await database.update_balance(str(giocatore.id),        cash=destinatario["cash"] + importo)

        embed = discord.Embed(
            title="💸 𝐏𝐚𝐠𝐚𝐦𝐞𝐧𝐭𝐨 𝐄𝐟𝐟𝐞𝐭𝐭𝐮𝐚𝐭𝐨",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Da",        value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 A",         value=giocatore.mention,        inline=True)
        embed.add_field(name="💵 Importo",   value=f"${importo:,}",          inline=True)
        if causale:
            embed.add_field(name="📋 Causale", value=causale, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Pagamento in Contanti")
        await interaction.response.send_message(embed=embed)

        # DM al destinatario
        try:
            dm = discord.Embed(
                title="💵 𝐇𝐚𝐢 𝐫𝐢𝐜𝐞𝐯𝐮𝐭𝐨 𝐮𝐧 𝐩𝐚𝐠𝐚𝐦𝐞𝐧𝐭𝐨!",
                description=(
                    f"**{interaction.user.display_name}** ti ha pagato **${importo:,}** in contanti."
                    + (f"\n📋 **Causale:** {causale}" if causale else "")
                ),
                color=discord.Color.green()
            )
            dm.set_footer(text="🤠 Red Dead Redemption II")
            await giocatore.send(embed=dm)
        except Exception:
            pass

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  ARMI — /dai-arma [Armaiolo] e /rimuovi-arma [Staff]
    # ══════════════════════════════════════════════════════════════════════

    async def _weapon_autocomplete(interaction: discord.Interaction, current: str):
        try:
            giocatore_id = interaction.namespace.giocatore
            if not giocatore_id:
                return []
            armi = await database.get_weapons(str(giocatore_id))
            current = (current or "").lower()
            return [
                app_commands.Choice(name=a["nome_arma"], value=a["nome_arma"])
                for a in armi if current in a["nome_arma"].lower()
            ][:25]
        except Exception:
            return []

    @bot.tree.command(name="dai-arma", description="[Armaiolo] Assegna un'arma a un giocatore")
    @app_commands.describe(
        giocatore="Il giocatore a cui dare l'arma",
        nome="Nome dell'arma (es: Revolver Cattleman)",
        tipo="Tipologia dell'arma",
        dettagli="Dettagli aggiuntivi (incisioni, munizioni, ecc. — opzionale)"
    )
    @app_commands.choices(tipo=TIPO_ARMA_CHOICES)
    async def dai_arma(interaction: discord.Interaction, giocatore: discord.Member,
                       nome: str, tipo: str, dettagli: str = ""):
        if not _has_role(interaction, ARMAIOLO_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Solo chi ha il ruolo <@&{ARMAIOLO_ROLE_ID}> può dare armi.", ephemeral=True
            )
            return
        await database.add_weapon(str(giocatore.id), nome, tipo, dettagli, str(interaction.user.id))

        embed = discord.Embed(title="🔫 𝐀𝐫𝐦𝐚 𝐀𝐬𝐬𝐞𝐠𝐧𝐚𝐭𝐚", color=discord.Color(0x2C2C2C), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="🔫 Arma",      value=nome,                     inline=True)
        embed.add_field(name="🏷️ Tipo",      value=tipo,                     inline=True)
        if dettagli:
            embed.add_field(name="📝 Dettagli", value=dettagli, inline=False)
        embed.add_field(name="👮 Assegnata da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Armeria")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="🔫 𝐇𝐚𝐢 𝐫𝐢𝐜𝐞𝐯𝐮𝐭𝐨 𝐮𝐧'𝐚𝐫𝐦𝐚!",
                description=f"Hai ricevuto **{nome}** ({tipo}). Usa `/portafoglio` per vederla.",
                color=discord.Color(0x2C2C2C)
            )
            await giocatore.send(embed=dm)
        except Exception:
            pass

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    @bot.tree.command(name="rimuovi-arma", description="[Staff] Rimuovi un'arma dal portafoglio di un giocatore")
    @app_commands.describe(giocatore="Il giocatore", arma="Nome dell'arma da rimuovere")
    @app_commands.autocomplete(arma=_weapon_autocomplete)
    async def rimuovi_arma(interaction: discord.Interaction, giocatore: discord.Member, arma: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return
        ok = await database.remove_weapon_by_name(str(giocatore.id), arma)
        if not ok:
            await interaction.response.send_message(
                f"❌ **{giocatore.display_name}** non possiede nessuna arma chiamata **{arma}**.", ephemeral=True
            )
            return
        embed = discord.Embed(title="🗑️ 𝐀𝐫𝐦𝐚 𝐑𝐢𝐦𝐨𝐬𝐬𝐚", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="🔫 Arma",      value=arma,                     inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Armeria")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════
    #  CAVALLI — /dai-cavallo [Stalliere] e /rimuovi-cavallo [Staff]
    # ══════════════════════════════════════════════════════════════════════

    async def _horse_autocomplete(interaction: discord.Interaction, current: str):
        try:
            giocatore_id = interaction.namespace.giocatore
            if not giocatore_id:
                return []
            cavalli = await database.get_horses(str(giocatore_id))
            current = (current or "").lower()
            return [
                app_commands.Choice(name=cv["nome"], value=cv["nome"])
                for cv in cavalli if current in cv["nome"].lower()
            ][:25]
        except Exception:
            return []

    @bot.tree.command(name="dai-cavallo", description="[Stalliere] Assegna un cavallo a un giocatore")
    @app_commands.describe(
        giocatore="Il giocatore a cui dare il cavallo",
        nome="Nome del cavallo",
        razza="Razza del cavallo (scrivila liberamente, es: Arabo, Paint Horse americano, Purosangue...)",
        colore="Colore/mantello del cavallo",
        sesso="Sesso del cavallo",
        prezzo="Prezzo del cavallo (solo per la fattura — non scala i contanti)",
        eta="Età del cavallo (opzionale)"
    )
    @app_commands.choices(sesso=SESSO_CAVALLO_CHOICES)
    async def dai_cavallo(interaction: discord.Interaction, giocatore: discord.Member,
                          nome: str, razza: str, colore: str, sesso: str,
                          prezzo: int, eta: str = ""):
        if not _has_role(interaction, STALLIERE_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Solo chi ha il ruolo <@&{STALLIERE_ROLE_ID}> può dare cavalli.", ephemeral=True
            )
            return
        await database.add_horse(str(giocatore.id), nome, razza, colore, sesso, eta, prezzo, str(interaction.user.id))

        embed = discord.Embed(title="🐴 𝐂𝐚𝐯𝐚𝐥𝐥𝐨 𝐀𝐬𝐬𝐞𝐠𝐧𝐚𝐭𝐨", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
        embed.add_field(name="🐴 Nome",      value=nome,              inline=True)
        embed.add_field(name="🏇 Razza",     value=razza,             inline=True)
        embed.add_field(name="🎨 Colore",    value=colore,            inline=True)
        embed.add_field(name="⚧ Sesso",      value=sesso,             inline=True)
        if eta:
            embed.add_field(name="🎂 Età", value=eta, inline=True)
        embed.add_field(name="💵 Prezzo (fattura)", value=f"${prezzo:,}", inline=True)
        embed.add_field(name="👮 Assegnato da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Stalla")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="🐴 𝐇𝐚𝐢 𝐫𝐢𝐜𝐞𝐯𝐮𝐭𝐨 𝐮𝐧 𝐜𝐚𝐯𝐚𝐥𝐥𝐨!",
                description=f"Hai ricevuto **{nome}** ({razza}, {colore}). Usa `/portafoglio` per vederlo.",
                color=discord.Color(0x8B4513)
            )
            await giocatore.send(embed=dm)
        except Exception:
            pass

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    @bot.tree.command(name="rimuovi-cavallo", description="[Staff] Rimuovi un cavallo dal portafoglio di un giocatore")
    @app_commands.describe(giocatore="Il giocatore", cavallo="Nome del cavallo da rimuovere")
    @app_commands.autocomplete(cavallo=_horse_autocomplete)
    async def rimuovi_cavallo(interaction: discord.Interaction, giocatore: discord.Member, cavallo: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return
        ok = await database.remove_horse_by_name(str(giocatore.id), cavallo)
        if not ok:
            await interaction.response.send_message(
                f"❌ **{giocatore.display_name}** non possiede nessun cavallo chiamato **{cavallo}**.", ephemeral=True
            )
            return
        embed = discord.Embed(title="🗑️ 𝐂𝐚𝐯𝐚𝐥𝐥𝐨 𝐑𝐢𝐦𝐨𝐬𝐬𝐨", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="🐴 Cavallo",   value=cavallo,                  inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Stalla")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass
