import discord
from discord import app_commands
import database
from constants import (
    BANKER_ROLE_ID, BANK_CHANNEL_ID, LOG_CHANNEL_ID,
    STAFF_ROLES, has_staff
)


# ══════════════════════════════════════════════════════════════════════════════
#  PORTAFOGLIO — Select Menu con Documento, Bisaccia, Proprietà (NO SOLDI)
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
        ]
        super().__init__(placeholder="Seleziona una sezione...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        # Solo il proprietario può usare i propri bottoni
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("❌ Questo portafoglio non è tuo!", ephemeral=True)
            return

        val = self.values[0]
        user_id = str(self.target.id)

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
            await interaction.response.edit_message(embed=embed, view=self.view)

        elif val == "bisaccia":
            items = await database.get_inventory(user_id)
            user  = await database.get_user(user_id)
            embed = discord.Embed(
                title="🎒 𝐋𝐚 𝐭𝐮𝐚 𝐁𝐢𝐬𝐚𝐜𝐜𝐢𝐚",
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
            await interaction.response.edit_message(embed=embed, view=self.view)

        elif val == "proprieta":
            props = await database.get_properties(user_id)
            embed = discord.Embed(
                title="🏡 𝐋𝐞 𝐭𝐮𝐞 𝐏𝐫𝐨𝐩𝐫𝐢𝐞𝐭à",
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
            await interaction.response.edit_message(embed=embed, view=self.view)

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
            await interaction.response.edit_message(embed=embed, view=self.view)


class PortafoglioView(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=120)
        self.add_item(PortafoglioSelect(target))


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
            title=f"🏦 𝐑𝐢𝐜𝐡𝐢𝐞𝐬𝐭𝐚 𝐝𝐢 {label}",  # ✅ CORRETTO
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
            title=f"<a:Portafoglio:1462442004569919629> 𝐏𝐨𝐫𝐭𝐚𝐟𝐨𝐠𝐥𝐢𝐨 𝐝𝐢 {interaction.user.mention}",
            description=(
                "Seleziona una sezione dal menu qui sotto per visualizzare\n"
                "le tue informazioni personali nel Far West."
            ),
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Portafoglio")
        view = PortafoglioView(interaction.user)
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
