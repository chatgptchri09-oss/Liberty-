import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_staff, COMPANY_ROLES

COMPANY_EMOJI = {
    "Sceriffo":     "🤠",
    "Dottore":      "🩺",
    "Armiere":      "🔫",
    "Stalla":       "🐎",
    "Saloon":       "🍻",
    "Emporio":      "🏪",
    "Contrabbando": "🚫",
    "Diligenza":    "🚂",
    "Stato":        "🏛️",
    "Banchiere":    "🏦",
    "Distilleria":  "🥃",
    "Macelleria":   "🥩",
    "FightClub":    "🥊",
}

# ── Ruoli extra con accesso al fondo cassa, oltre a quelli già in COMPANY_ROLES ──
# ⚠️ Chi ha questi ruoli può accedere, prelevare e depositare nel fondo cassa
# della compagnia indicata, IN AGGIUNTA a chi ha già il ruolo storico
# configurato in COMPANY_ROLES.
EXTRA_ACCESSO_BANCHIERE_ROLE_ID  = 1480217288933376130
EXTRA_ACCESSO_STATO_ROLE_ID      = 1480217343245287424
# ⚠️ Ruolo "Proprietario Fight Club" — placeholder, lo stesso usato in
# commands_fightclub.py. L'utente lo aggiornerà manualmente in entrambi i file
# quando avrà l'ID definitivo.
EXTRA_ACCESSO_FIGHTCLUB_ROLE_ID  = 1421169805968539699

_CHOICES = [
    app_commands.Choice(name="⭐ Sceriffo",     value="Sceriffo"),
    app_commands.Choice(name="🩺 Dottore",      value="Dottore"),
    app_commands.Choice(name="🔫 Armiere",      value="Armiere"),
    app_commands.Choice(name="🐴 Stalla",       value="Stalla"),
    app_commands.Choice(name="🍺 Saloon",       value="Saloon"),
    app_commands.Choice(name="🏪 Emporio",      value="Emporio"),
    app_commands.Choice(name="🚫 Contrabbando", value="Contrabbando"),
    app_commands.Choice(name="🚂 Diligenza",    value="Diligenza"),
    app_commands.Choice(name="🏛️ Stato",        value="Stato"),
    app_commands.Choice(name="🏦 Banca",        value="Banchiere"),
    app_commands.Choice(name="🥃 Distilleria",  value="Distilleria"),
    app_commands.Choice(name="🥩 Macelleria",   value="Macelleria"),
    app_commands.Choice(name="🥊 Fight Club",   value="FightClub"),
]


def _get_user_companies(member) -> list:
    result = []
    for company, role_id in COMPANY_ROLES.items():
        if isinstance(role_id, list):
            if any(r.id in role_id for r in member.roles):
                result.append(company)
        elif any(r.id == role_id for r in member.roles):
            result.append(company)

    # ⚠️ Ruoli extra: danno accesso anche a chi non ha già il ruolo storico
    # in COMPANY_ROLES (si sommano a quello che c'è già, non lo sostituiscono).
    member_role_ids = {r.id for r in member.roles}
    if EXTRA_ACCESSO_BANCHIERE_ROLE_ID in member_role_ids and "Banchiere" not in result:
        result.append("Banchiere")
    if EXTRA_ACCESSO_STATO_ROLE_ID in member_role_ids and "Stato" not in result:
        result.append("Stato")
    if EXTRA_ACCESSO_FIGHTCLUB_ROLE_ID and EXTRA_ACCESSO_FIGHTCLUB_ROLE_ID in member_role_ids and "FightClub" not in result:
        result.append("FightClub")

    return result


def _saldo_color(amount: int) -> discord.Color:
    if amount <= 0:
        return discord.Color.red()
    if amount < 500:
        return discord.Color.orange()
    return discord.Color(0xDAA520)


def _saldo_bar(amount: int, scala: int = 2000) -> str:
    """Barra visiva del saldo, scalata su 'scala' (puramente decorativa)."""
    f = max(0, min(10, round((amount / scala) * 10))) if scala else 0
    return "🟨" * f + "⬛" * (10 - f)


async def _build_fondocassa_embed(compagnia: str) -> discord.Embed:
    amount = await database.get_fondocassa(compagnia)
    emoji  = COMPANY_EMOJI.get(compagnia, "🏢")
    embed = discord.Embed(
        title=f"{emoji} 𝐅𝐎𝐍𝐃𝐎 𝐂𝐀𝐒𝐒𝐀 — {compagnia.upper()}",
        description="*Il forziere della compagnia, custodito sotto chiave.*",
        color=_saldo_color(amount),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="💰 Saldo attuale", value=f"## ${amount:,}", inline=False)
    embed.add_field(name="📊 Livello riserve", value=_saldo_bar(amount), inline=False)
    embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa | Usa i pulsanti qui sotto")
    return embed


# ══════════════════════════════════════════════════════════════════════════════
#  MODALI — Deposito / Prelievo
# ══════════════════════════════════════════════════════════════════════════════
class DepositoModal(discord.ui.Modal, title="💰 Deposita nel Fondo Cassa"):
    importo = discord.ui.TextInput(
        label="Importo da depositare ($)",
        placeholder="Es: 250",
        required=True,
        max_length=8
    )

    def __init__(self, compagnia: str, panel_view: "FondocassaPanelView"):
        super().__init__()
        self.compagnia  = compagnia
        self.panel_view = panel_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            importo = int(self.importo.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True); return

        user = await database.get_user(str(interaction.user.id))
        if user["cash"] < importo:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti. Disponibili: **${user['cash']:,}**", ephemeral=True); return

        await database.update_balance(str(interaction.user.id), cash=user["cash"] - importo)
        current = await database.get_fondocassa(self.compagnia)
        nuovo   = current + importo
        await database.update_fondocassa(self.compagnia, nuovo)

        emoji = COMPANY_EMOJI.get(self.compagnia, "🏢")
        log_embed = discord.Embed(
            title=f"💰 𝐃𝐞𝐩𝐨𝐬𝐢𝐭𝐨 — {self.compagnia}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        log_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        log_embed.add_field(name=f"{emoji} Compagnia", value=self.compagnia,      inline=True)
        log_embed.add_field(name="➕ Depositato",      value=f"${importo:,}",     inline=True)
        log_embed.add_field(name="💼 Nuovo saldo",     value=f"${nuovo:,}",       inline=True)
        log_embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")

        try:
            panel_embed = await _build_fondocassa_embed(self.compagnia)
            if self.panel_view.message:
                await self.panel_view.message.edit(embed=panel_embed, view=self.panel_view)
        except Exception:
            pass

        await interaction.response.send_message(embed=log_embed, ephemeral=True)
        try:
            ch = interaction.client.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=log_embed)
        except Exception:
            pass


class PrelievoModal(discord.ui.Modal, title="💸 Preleva dal Fondo Cassa"):
    importo = discord.ui.TextInput(
        label="Importo da prelevare ($)",
        placeholder="Es: 100",
        required=True,
        max_length=8
    )
    motivazione = discord.ui.TextInput(
        label="Motivazione (opzionale)",
        placeholder="Es: acquisto forniture",
        required=False,
        max_length=200
    )

    def __init__(self, compagnia: str, panel_view: "FondocassaPanelView"):
        super().__init__()
        self.compagnia  = compagnia
        self.panel_view = panel_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            importo = int(self.importo.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True); return

        current = await database.get_fondocassa(self.compagnia)
        if current < importo:
            await interaction.response.send_message(
                f"❌ Fondi insufficienti. Disponibili: **${current:,}**", ephemeral=True); return

        nuovo = current - importo
        await database.update_fondocassa(self.compagnia, nuovo)
        user = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(interaction.user.id), cash=user["cash"] + importo)

        emoji = COMPANY_EMOJI.get(self.compagnia, "🏢")
        log_embed = discord.Embed(
            title=f"💸 𝐏𝐫𝐞𝐥𝐢𝐞𝐯𝐨 — {self.compagnia}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        log_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        log_embed.add_field(name=f"{emoji} Compagnia",  value=self.compagnia, inline=True)
        log_embed.add_field(name="➖ Prelevato",        value=f"${importo:,}", inline=True)
        log_embed.add_field(name="💼 Saldo rimasto",    value=f"${nuovo:,}",   inline=True)
        if self.motivazione.value:
            log_embed.add_field(name="📋 Motivazione", value=self.motivazione.value, inline=False)
        log_embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")

        try:
            panel_embed = await _build_fondocassa_embed(self.compagnia)
            if self.panel_view.message:
                await self.panel_view.message.edit(embed=panel_embed, view=self.panel_view)
        except Exception:
            pass

        await interaction.response.send_message(embed=log_embed, ephemeral=True)
        try:
            ch = interaction.client.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=log_embed)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  VIEW — Pannello interattivo del Fondo Cassa
# ══════════════════════════════════════════════════════════════════════════════
class FondocassaPanelView(discord.ui.View):
    def __init__(self, compagnia: str, autorizzati_ids: set):
        super().__init__(timeout=180)
        self.compagnia       = compagnia
        self.autorizzati_ids = autorizzati_ids  # chi può usare i pulsanti (chi ha /fondocassa aperto)
        self.message: discord.Message | None = None

    async def _verifica(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in self.autorizzati_ids:
            await interaction.response.send_message(
                "❌ Non puoi interagire con il fondo cassa di un'altra compagnia.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Deposita", emoji="💰", style=discord.ButtonStyle.success)
    async def deposita_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._verifica(interaction):
            return
        await interaction.response.send_modal(DepositoModal(self.compagnia, self))

    @discord.ui.button(label="Preleva", emoji="💸", style=discord.ButtonStyle.danger)
    async def preleva_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._verifica(interaction):
            return
        await interaction.response.send_modal(PrelievoModal(self.compagnia, self))

    @discord.ui.button(label="Aggiorna", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def aggiorna_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._verifica(interaction):
            return
        embed = await _build_fondocassa_embed(self.compagnia)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


def setup_fondocassa_commands(bot):

    # ── /fondocassa ───────────────────────────────────────────────────────────
    @bot.tree.command(name="fondocassa", description="Apri il pannello del fondo cassa della tua compagnia")
    @app_commands.describe(compagnia="Seleziona la tua compagnia")
    @app_commands.choices(compagnia=_CHOICES)
    async def fondocassa(interaction: discord.Interaction, compagnia: str):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if compagnia not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte della compagnia **{compagnia}**.", ephemeral=True); return

        embed = await _build_fondocassa_embed(compagnia)
        view  = FondocassaPanelView(compagnia, {interaction.user.id})
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

    # ── /deposita-fondocassa (rapido, senza pannello) ────────────────────────
    @bot.tree.command(name="deposita-fondocassa", description="Deposita contanti nel fondo cassa della tua compagnia")
    @app_commands.describe(compagnia="La compagnia", importo="Importo da depositare")
    @app_commands.choices(compagnia=_CHOICES)
    async def deposita_fondocassa(interaction: discord.Interaction, compagnia: str, importo: int):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if compagnia not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte della compagnia **{compagnia}**.", ephemeral=True); return

        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return

        user = await database.get_user(str(interaction.user.id))
        if user["cash"] < importo:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti. Disponibili: **${user['cash']:,}**", ephemeral=True); return

        await database.update_balance(str(interaction.user.id), cash=user["cash"] - importo)
        current = await database.get_fondocassa(compagnia)
        nuovo   = current + importo
        await database.update_fondocassa(compagnia, nuovo)

        emoji = COMPANY_EMOJI.get(compagnia, "🏢")
        embed = discord.Embed(
            title=f"💰 𝐃𝐞𝐩𝐨𝐬𝐢𝐭𝐨 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {compagnia}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{emoji} Compagnia", value=compagnia,      inline=True)
        embed.add_field(name="💵 Depositato",      value=f"${importo:,}", inline=True)
        embed.add_field(name="💼 Nuovo saldo FC",  value=f"${nuovo:,}",   inline=True)
        embed.add_field(name="👤 Da",              value=interaction.user.mention, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── /preleva-fondocassa (rapido, senza pannello) ─────────────────────────
    @bot.tree.command(name="preleva-fondocassa", description="Preleva dal fondo cassa della tua compagnia")
    @app_commands.describe(compagnia="La compagnia", importo="Importo da prelevare", motivazione="Motivazione (opzionale)")
    @app_commands.choices(compagnia=_CHOICES)
    async def preleva_fondocassa(interaction: discord.Interaction, compagnia: str, importo: int, motivazione: str = ""):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True); return

        if compagnia not in _get_user_companies(interaction.user):
            await interaction.response.send_message(
                f"❌ Non fai parte della compagnia **{compagnia}**.", ephemeral=True); return

        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True); return

        current = await database.get_fondocassa(compagnia)
        if current < importo:
            await interaction.response.send_message(
                f"❌ Fondi insufficienti. Disponibili: **${current:,}**", ephemeral=True); return

        nuovo = current - importo
        await database.update_fondocassa(compagnia, nuovo)
        user = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(interaction.user.id), cash=user["cash"] + importo)

        emoji = COMPANY_EMOJI.get(compagnia, "🏢")
        embed = discord.Embed(
            title=f"💸 𝐏𝐫𝐞𝐥𝐢𝐞𝐯𝐨 𝐅𝐨𝐧𝐝𝐨 𝐂𝐚𝐬𝐬𝐚 — {compagnia}",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name=f"{emoji} Compagnia",  value=compagnia,      inline=True)
        embed.add_field(name="💵 Prelevato",        value=f"${importo:,}", inline=True)
        embed.add_field(name="💼 Saldo FC rimasto", value=f"${nuovo:,}",   inline=True)
        embed.add_field(name="👤 Da",               value=interaction.user.mention, inline=False)
        if motivazione:
            embed.add_field(name="📋 Motivazione",  value=motivazione, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── /saldo-fondocassa ─────────────────────────────────────────────────────
    @bot.tree.command(name="saldo-fondocassa", description="[Staff] Visualizza il saldo di tutti i fondi cassa")
    async def saldo_fondocassa(interaction: discord.Interaction):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Solo lo Staff può vedere tutti i fondi cassa.", ephemeral=True); return

        embed = discord.Embed(
            title="🏦 𝐑𝐄𝐆𝐈𝐒𝐓𝐑𝐎 𝐆𝐄𝐍𝐄𝐑𝐀𝐋𝐄 𝐃𝐄𝐈 𝐅𝐎𝐍𝐃𝐈 𝐂𝐀𝐒𝐒𝐀",
            description="*Il resoconto ufficiale dei forzieri di tutte le compagnie della contea.*",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        totale = 0
        for company, emoji in COMPANY_EMOJI.items():
            amount = await database.get_fondocassa(company)
            totale += amount
            embed.add_field(
                name=f"{emoji} {company}",
                value=f"**${amount:,}**\n{_saldo_bar(amount)}",
                inline=True
            )
        embed.add_field(name="​", value="​", inline=False)
        embed.add_field(name="💰 Totale Generale della Contea", value=f"## ${totale:,}", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed, ephemeral=True)
