import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database
from datetime import datetime, timezone
from constants import (
    LOG_CHANNEL_ID, DATABASE_NAME, has_staff,
    SCERIFFO_ROLE_ID, ARMIERE_ROLE_ID, STALLA_ROLE_ID,
    EMPORIO_ROLE_ID, SALOON_ROLE_ID, DOTTORE_ROLE_ID,
    STAFF_ROLE_ID, CHIAVE_ROLE_ID
)

# ── ID Ruoli depositi speciali ─────────────────────────────────────────────────
PINKERTON_ROLE_ID   = 1420267736319266906
PEAKY_ROLE_ID       = 1494988697127485513
SILENT_ROLE_ID      = 1495036199096811570
BLACKWOOD_ROLE_ID   = 1496603144551923905

# ── Configurazione depositi ───────────────────────────────────────────────────
DEPOSITI = {
    "pinkerton":  {"label": "🕵️ | Deposito Pinkerton",       "ruoli": [PINKERTON_ROLE_ID]},
    "sceriffato": {"label": "🤠 | Deposito Sceriffato",       "ruoli": [SCERIFFO_ROLE_ID]},
    "armeria":    {"label": "🔫 | Deposito Armeria",          "ruoli": [ARMIERE_ROLE_ID]},
    "stalla":     {"label": "🐎 | Deposito Stalla",           "ruoli": [STALLA_ROLE_ID]},
    "emporio":    {"label": "🏪 | Deposito Emporio",          "ruoli": [EMPORIO_ROLE_ID]},
    "saloon":     {"label": "🍻 | Deposito Saloon",           "ruoli": [SALOON_ROLE_ID]},
    "medico":     {"label": "🩺 | Deposito Studio Medico",    "ruoli": [DOTTORE_ROLE_ID]},
    "peaky":      {"label": "🐦‍⬛ | Deposito Peaky Blinders",  "ruoli": [PEAKY_ROLE_ID]},
    "silent":     {"label": "🃏 | Deposito Silent Syndacate", "ruoli": [SILENT_ROLE_ID]},
    "blackwood":  {"label": "☠️ | Deposito Famiglia Blackwood","ruoli": [BLACKWOOD_ROLE_ID]},
}

DEPOSITI_CHOICES = [
    app_commands.Choice(name=v["label"], value=k)
    for k, v in DEPOSITI.items()
]

def _ha_accesso(interaction: discord.Interaction, deposito_key: str) -> bool:
    """Ritorna True se l'utente ha il ruolo del deposito O è staff."""
    if has_staff(interaction):
        return True
    if not isinstance(interaction.user, discord.Member):
        return False
    ruoli_richiesti = DEPOSITI[deposito_key]["ruoli"]
    return any(r.id in ruoli_richiesti for r in interaction.user.roles)

# ── DB helpers depositi ───────────────────────────────────────────────────────
async def _init_dep_table():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                deposito  TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity  INTEGER DEFAULT 0,
                PRIMARY KEY (deposito, item_name)
            )
        """)
        await db.commit()

async def _get_dep_items(deposito: str) -> list[dict]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_name, quantity FROM deposits WHERE deposito=? AND quantity>0 ORDER BY item_name ASC",
            (deposito,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def _get_dep_qty(deposito: str, item_name: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM deposits WHERE deposito=? AND item_name=?",
            (deposito, item_name)
        ) as c:
            row = await c.fetchone()
            return row[0] if row else 0

async def _add_dep_item(deposito: str, item_name: str, qty: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO deposits (deposito, item_name, quantity)
            VALUES (?,?,?)
            ON CONFLICT(deposito, item_name) DO UPDATE SET quantity=quantity+excluded.quantity
        """, (deposito, item_name, qty))
        await db.commit()

async def _remove_dep_item(deposito: str, item_name: str, qty: int) -> bool:
    cur_qty = await _get_dep_qty(deposito, item_name)
    if cur_qty < qty:
        return False
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE deposits SET quantity=quantity-? WHERE deposito=? AND item_name=?",
            (qty, deposito, item_name)
        )
        await db.commit()
    return True

def _fuzzy(query: str, candidates: list) -> list:
    q = query.lower().strip()
    if not q: return candidates
    words = q.split()
    r = [c for c in candidates if all(w in c.lower() for w in words)]
    return r or [c for c in candidates if any(w in c.lower() for w in words)]

# ── VIEW PRELIEVO ─────────────────────────────────────────────────────────────
class DepositoPrelievoView(discord.ui.View):
    def __init__(self, bot, user: discord.Member, deposito_key: str, items: list[dict], pagina: int = 0):
        super().__init__(timeout=300)
        self.bot          = bot
        self.user         = user
        self.dep_key      = deposito_key
        self.dep_label    = DEPOSITI[deposito_key]["label"]
        self.items        = items
        self.pagina       = pagina
        self.PER_PAG      = 25
        self.tot_pag      = max(1, -(-len(items) // self.PER_PAG))
        self._aggiorna_pulsanti()
        self._aggiorna_select()

    def _pagina_items(self):
        s = self.pagina * self.PER_PAG
        return self.items[s:s + self.PER_PAG]

    def _aggiorna_pulsanti(self):
        self.prev_btn.disabled = self.pagina == 0
        self.next_btn.disabled = self.pagina >= self.tot_pag - 1

    def _aggiorna_select(self):
        # Rimuovi vecchio select se presente
        self.clear_items()
        page_items = self._pagina_items()
        options = [
            discord.SelectOption(
                label=f"{i['item_name'][:90]} (x{i['quantity']})",
                value=i["item_name"]
            )
            for i in page_items
        ]
        select = discord.ui.Select(
            placeholder="Seleziona un item da mettere nella bisaccia",
            options=options if options else [discord.SelectOption(label="Nessun item", value="__vuoto__")]
        )
        select.callback = self._select_callback
        self.add_item(select)
        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)
        self.add_item(self.chiudi_btn)

    def _build_embed(self) -> discord.Embed:
        s = self.pagina * self.PER_PAG
        e = min(s + self.PER_PAG, len(self.items))
        embed = discord.Embed(
            title="🏢 Deposito Fazione — Prelievo",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.description = (
            f"📖 **Come funziona:**\n"
            f"• Deposito: **{self.dep_label}**\n"
            f"• Seleziona un item e la quantità da mettere nello zaino.\n\n"
            f"Mostrati **{s+1}-{e}** di **{len(self.items)}**\n"
            f"**Pagina {self.pagina+1} di {self.tot_pag}**"
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
        return embed

    async def _select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo pannello.", ephemeral=True)
            return
        item_sel = interaction.data["values"][0]
        if item_sel == "__vuoto__":
            await interaction.response.send_message("❌ Nessun item disponibile.", ephemeral=True)
            return
        qty_dep = await _get_dep_qty(self.dep_key, item_sel)
        view2 = QuantitaPrelievoView(
            self.bot, self.user, self.dep_key, self.dep_label,
            item_sel, qty_dep, self
        )
        await interaction.response.edit_message(embed=view2._build_embed(), view=view2)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        self.pagina -= 1
        self._aggiorna_pulsanti()
        self._aggiorna_select()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        self.pagina += 1
        self._aggiorna_pulsanti()
        self._aggiorna_select()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="❌ Chiudi Pannello", style=discord.ButtonStyle.danger, row=1)
    async def chiudi_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        await interaction.response.edit_message(
            content="✅ Pannello chiuso.", embed=None, view=None
        )


# ── VIEW QUANTITÀ ─────────────────────────────────────────────────────────────
class QuantitaPrelievoView(discord.ui.View):
    def __init__(self, bot, user, dep_key, dep_label, item_name, qty_dep, parent_view):
        super().__init__(timeout=300)
        self.bot        = bot
        self.user       = user
        self.dep_key    = dep_key
        self.dep_label  = dep_label
        self.item_name  = item_name
        self.qty_dep    = qty_dep
        self.parent     = parent_view

        # Select quantità 1-25 (o meno se disponibile meno)
        max_q = min(qty_dep, 25)
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, max_q + 1)]
        if not options:
            options = [discord.SelectOption(label="0", value="0")]
        sel = discord.ui.Select(
            placeholder=f"Seleziona la quantità (1-{max_q})",
            options=options
        )
        sel.callback = self._qty_callback
        self.add_item(sel)
        self.add_item(self.qty_custom_btn)
        self.add_item(self.indietro_btn)

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎒 Scegli quantità da prelevare",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.description = (
            f"Item: **{self.item_name}**\n"
            f"Nel deposito: **{self.qty_dep}**\n"
            f"Massimo Prelevabile ora: **{self.qty_dep}**"
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
        return embed

    async def _esegui_prelievo(self, interaction: discord.Interaction, qty: int):
        if qty <= 0:
            await interaction.response.send_message("❌ Quantità non valida.", ephemeral=True)
            return
        ok = await _remove_dep_item(self.dep_key, self.item_name, qty)
        if not ok:
            await interaction.response.send_message(
                f"❌ Non ci sono abbastanza **{self.item_name}** nel deposito.", ephemeral=True)
            return
        await database.add_item(str(self.user.id), self.item_name, qty)

        # Embed pubblico
        ora = datetime.now(timezone.utc).strftime("%H:%M")
        embed_pub = discord.Embed(
            title="🎒 Prelievo Deposito Fazione",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed_pub.description = (
            f"✅ Prelievo completato.\n\n"
            f"**🏢 Deposito:** {self.dep_label}\n"
            f"**📦 Item: {qty}x** {self.item_name}"
        )
        embed_pub.set_footer(text=f"🤠 Oggi alle {ora}")

        await interaction.response.edit_message(
            content="✅ Prelievo completato! Pannello chiuso.", embed=None, view=None
        )
        await interaction.channel.send(content=self.user.mention, embed=embed_pub)

        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="📦 LOG — Prelievo Deposito", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Utente",   value=self.user.mention,   inline=True)
                log.add_field(name="🏢 Deposito", value=self.dep_label,      inline=True)
                log.add_field(name="📦 Item",     value=f"{self.item_name} x{qty}", inline=True)
                await ch.send(embed=log)
        except Exception: pass

    async def _qty_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        qty = int(interaction.data["values"][0])
        await self._esegui_prelievo(interaction, qty)

    @discord.ui.button(label="🔢 Quantità Personalizzata", style=discord.ButtonStyle.primary, row=1)
    async def qty_custom_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return

        dep_key    = self.dep_key
        dep_label  = self.dep_label
        item_name  = self.item_name
        qty_dep    = self.qty_dep
        bot        = self.bot
        user       = self.user

        class QtyModal(discord.ui.Modal, title="🔢 Quantità personalizzata"):
            quantita = discord.ui.TextInput(
                label=f"Quanti {item_name[:40]} vuoi prelevare?",
                style=discord.TextStyle.short,
                placeholder=f"Max: {qty_dep}",
                required=True, max_length=6
            )
            async def on_submit(self2, itr: discord.Interaction):
                try:
                    qty = int(self2.quantita.value)
                except ValueError:
                    await itr.response.send_message("❌ Inserisci un numero valido.", ephemeral=True)
                    return
                if qty <= 0 or qty > qty_dep:
                    await itr.response.send_message(f"❌ Quantità non valida (max: {qty_dep}).", ephemeral=True)
                    return
                ok = await _remove_dep_item(dep_key, item_name, qty)
                if not ok:
                    await itr.response.send_message("❌ Quantità non disponibile nel deposito.", ephemeral=True)
                    return
                await database.add_item(str(user.id), item_name, qty)

                ora = datetime.now(timezone.utc).strftime("%H:%M")
                embed_pub = discord.Embed(
                    title="🎒 Prelievo Deposito Fazione",
                    color=discord.Color(0x8B4513),
                    timestamp=discord.utils.utcnow()
                )
                embed_pub.description = (
                    f"✅ Prelievo completato.\n\n"
                    f"**🏢 Deposito:** {dep_label}\n"
                    f"**📦 Item: {qty}x** {item_name}"
                )
                embed_pub.set_footer(text=f"🤠 Oggi alle {ora}")
                await itr.response.send_message("✅ Prelievo completato!", ephemeral=True)
                await itr.channel.send(content=user.mention, embed=embed_pub)

                try:
                    ch = bot.get_channel(LOG_CHANNEL_ID)
                    if ch:
                        log = discord.Embed(title="📦 LOG — Prelievo Deposito", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                        log.add_field(name="👤 Utente",   value=user.mention,      inline=True)
                        log.add_field(name="🏢 Deposito", value=dep_label,         inline=True)
                        log.add_field(name="📦 Item",     value=f"{item_name} x{qty}", inline=True)
                        await ch.send(embed=log)
                except Exception: pass

        await interaction.response.send_modal(QtyModal())

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def indietro_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        self.parent._aggiorna_select()
        await interaction.response.edit_message(embed=self.parent._build_embed(), view=self.parent)


# ── VIEW DEPOSITO ─────────────────────────────────────────────────────────────
class DepositoMettiView(discord.ui.View):
    def __init__(self, bot, user: discord.Member, deposito_key: str, inv_items: list[dict], pagina: int = 0):
        super().__init__(timeout=300)
        self.bot       = bot
        self.user      = user
        self.dep_key   = deposito_key
        self.dep_label = DEPOSITI[deposito_key]["label"]
        self.items     = inv_items
        self.pagina    = pagina
        self.PER_PAG   = 25
        self.tot_pag   = max(1, -(-len(inv_items) // self.PER_PAG))
        self._aggiorna()

    def _pagina_items(self):
        s = self.pagina * self.PER_PAG
        return self.items[s:s + self.PER_PAG]

    def _aggiorna(self):
        self.clear_items()
        page_items = self._pagina_items()
        options = [
            discord.SelectOption(
                label=f"{i['item_name'][:90]} (x{i['quantity']})",
                value=i["item_name"]
            )
            for i in page_items
        ]
        sel = discord.ui.Select(
            placeholder="Seleziona l'item da depositare",
            options=options if options else [discord.SelectOption(label="Bisaccia vuota", value="__vuoto__")]
        )
        sel.callback = self._select_callback
        self.add_item(sel)

    def _build_embed(self) -> discord.Embed:
        s = self.pagina * self.PER_PAG
        e = min(s + self.PER_PAG, len(self.items))
        embed = discord.Embed(
            title="🏢 Deposito Fazione",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.description = (
            f"📖 **Come funziona:**\n"
            f"• Deposito: **{self.dep_label}**\n"
            f"1️⃣ Seleziona l'oggetto da **depositare**.\n"
            f"2️⃣ Scegli **quante unità** depositare.\n"
            f"♻️ Puoi depositare più item finché il pannello resta aperto.\n\n"
            f"Mostrati **{s+1}-{e}** di **{len(self.items)}**\n"
            f"**Pagina {self.pagina+1} di {self.tot_pag}**"
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
        return embed

    async def _select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        item_sel = interaction.data["values"][0]
        if item_sel == "__vuoto__":
            await interaction.response.send_message("❌ Bisaccia vuota.", ephemeral=True); return

        qty_inv = await database.get_item_quantity(str(self.user.id), item_sel)
        view2 = QuantitaDepositoView(self.bot, self.user, self.dep_key, self.dep_label, item_sel, qty_inv, self)
        await interaction.response.edit_message(embed=view2._build_embed(), view=view2)


class QuantitaDepositoView(discord.ui.View):
    def __init__(self, bot, user, dep_key, dep_label, item_name, qty_inv, parent_view):
        super().__init__(timeout=300)
        self.bot       = bot
        self.user      = user
        self.dep_key   = dep_key
        self.dep_label = dep_label
        self.item_name = item_name
        self.qty_inv   = qty_inv
        self.parent    = parent_view

        max_q = min(qty_inv, 25)
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, max_q + 1)]
        if not options:
            options = [discord.SelectOption(label="0", value="0")]
        sel = discord.ui.Select(
            placeholder=f"Seleziona la quantità (1-{max_q})",
            options=options
        )
        sel.callback = self._qty_callback
        self.add_item(sel)
        self.add_item(self.qty_custom_btn)
        self.add_item(self.indietro_btn)

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="📦 Scegli quantità da depositare",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.description = (
            f"Item: **{self.item_name}**\n"
            f"Ne possiedi: **{self.qty_inv}**\n"
            f"Peso unitario: **—**"
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
        return embed

    async def _esegui_deposito(self, interaction: discord.Interaction, qty: int):
        if qty <= 0:
            await interaction.response.send_message("❌ Quantità non valida.", ephemeral=True); return
        rimosso = await database.remove_item(str(self.user.id), self.item_name, qty)
        if not rimosso:
            await interaction.response.send_message("❌ Non hai abbastanza item.", ephemeral=True); return
        await _add_dep_item(self.dep_key, self.item_name, qty)

        ora = datetime.now(timezone.utc).strftime("%H:%M")
        embed_pub = discord.Embed(
            title="🏢 Deposito Fazione",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed_pub.description = (
            f"✅ Deposito effettuato con successo.\n\n"
            f"**🏢 Deposito:** {self.dep_label}\n"
            f"**📦 Item: {qty}x** {self.item_name}"
        )
        embed_pub.set_footer(text=f"🤠 Oggi alle {ora}")
        await interaction.channel.send(content=self.user.mention, embed=embed_pub)

        # Aggiorna inventario nella view parent
        inv_aggiornato = await database.get_inventory(str(self.user.id))
        self.parent.items = [i for i in inv_aggiornato]
        self.parent.tot_pag = max(1, -(-len(self.parent.items) // self.parent.PER_PAG))
        self.parent._aggiorna()
        await interaction.response.edit_message(embed=self.parent._build_embed(), view=self.parent)

        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="📦 LOG — Deposito Fazione", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Utente",   value=self.user.mention,           inline=True)
                log.add_field(name="🏢 Deposito", value=self.dep_label,              inline=True)
                log.add_field(name="📦 Item",     value=f"{self.item_name} x{qty}", inline=True)
                await ch.send(embed=log)
        except Exception: pass

    async def _qty_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        qty = int(interaction.data["values"][0])
        await self._esegui_deposito(interaction, qty)

    @discord.ui.button(label="🔢 Quantità Personalizzata", style=discord.ButtonStyle.primary, row=1)
    async def qty_custom_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return

        item_name  = self.item_name
        qty_inv    = self.qty_inv
        dep_key    = self.dep_key
        dep_label  = self.dep_label
        bot        = self.bot
        user       = self.user
        parent     = self.parent

        class QtyModal(discord.ui.Modal, title="🔢 Quantità personalizzata"):
            quantita = discord.ui.TextInput(
                label=f"Quanti {item_name[:40]} vuoi depositare?",
                style=discord.TextStyle.short,
                placeholder=f"Max: {qty_inv}",
                required=True, max_length=6
            )
            async def on_submit(self2, itr: discord.Interaction):
                try:
                    qty = int(self2.quantita.value)
                except ValueError:
                    await itr.response.send_message("❌ Inserisci un numero valido.", ephemeral=True); return
                if qty <= 0 or qty > qty_inv:
                    await itr.response.send_message(f"❌ Quantità non valida (max: {qty_inv}).", ephemeral=True); return
                rimosso = await database.remove_item(str(user.id), item_name, qty)
                if not rimosso:
                    await itr.response.send_message("❌ Non hai abbastanza item.", ephemeral=True); return
                await _add_dep_item(dep_key, item_name, qty)

                ora = datetime.now(timezone.utc).strftime("%H:%M")
                embed_pub = discord.Embed(title="🏢 Deposito Fazione", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                embed_pub.description = (
                    f"✅ Deposito effettuato con successo.\n\n"
                    f"**🏢 Deposito:** {dep_label}\n"
                    f"**📦 Item: {qty}x** {item_name}"
                )
                embed_pub.set_footer(text=f"🤠 Oggi alle {ora}")
                await itr.channel.send(content=user.mention, embed=embed_pub)
                inv_aggiornato = await database.get_inventory(str(user.id))
                parent.items = list(inv_aggiornato)
                parent.tot_pag = max(1, -(-len(parent.items) // parent.PER_PAG))
                parent._aggiorna()
                await itr.response.send_message("✅ Depositato!", ephemeral=True)

        await interaction.response.send_modal(QtyModal())

    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def indietro_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌", ephemeral=True); return
        self.parent._aggiorna()
        await interaction.response.edit_message(embed=self.parent._build_embed(), view=self.parent)


# ── SETUP COMANDI ─────────────────────────────────────────────────────────────
def setup_deposits_commands(bot: commands.Bot):

    @bot.event
    async def on_ready_dep():
        await _init_dep_table()

    # ── /depgenerici ──────────────────────────────────────────────────────────
    @bot.tree.command(name="depgenerici", description="Preleva item da un deposito fazione")
    @app_commands.describe(deposito="Seleziona il deposito fazione")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    async def depgenerici(interaction: discord.Interaction, deposito: str):
        await _init_dep_table()
        if not _ha_accesso(interaction, deposito):
            await interaction.response.send_message(
                f"❌ Non hai accesso al **{DEPOSITI[deposito]['label']}**.", ephemeral=True)
            return

        items = await _get_dep_items(deposito)
        if not items:
            await interaction.response.send_message(
                f"❌ Il **{DEPOSITI[deposito]['label']}** è vuoto.", ephemeral=True)
            return

        view = DepositoPrelievoView(bot, interaction.user, deposito, items)
        await interaction.response.send_message(embed=view._build_embed(), view=view, ephemeral=True)

    # ── /mettidepfazione ──────────────────────────────────────────────────────
    @bot.tree.command(name="mettidepfazione", description="Deposita item dalla tua bisaccia in un deposito fazione")
    @app_commands.describe(deposito="Seleziona il deposito fazione")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    async def mettidepfazione(interaction: discord.Interaction, deposito: str):
        await _init_dep_table()
        if not _ha_accesso(interaction, deposito):
            await interaction.response.send_message(
                f"❌ Non hai accesso al **{DEPOSITI[deposito]['label']}**.", ephemeral=True)
            return

        inv = await database.get_inventory(str(interaction.user.id))
        if not inv:
            await interaction.response.send_message("❌ La tua bisaccia è vuota.", ephemeral=True)
            return

        view = DepositoMettiView(bot, interaction.user, deposito, inv)
        await interaction.response.send_message(embed=view._build_embed(), view=view, ephemeral=True)

    # ── /give-item-deposito ───────────────────────────────────────────────────
    async def _dep_item_ac(interaction: discord.Interaction, current: str):
        dep_key = None
        for opt in interaction.data.get("options", []):
            if opt["name"] == "deposito":
                dep_key = opt["value"]
                break
        if not dep_key:
            return []
        items = await _get_dep_items(dep_key)
        nomi  = [i["item_name"] for i in items]
        matches = _fuzzy(current, nomi) if current else nomi
        return [app_commands.Choice(name=m[:100], value=m) for m in matches[:25]]

    @bot.tree.command(name="give-item-deposito", description="[Staff] Aggiungi item in un deposito fazione")
    @app_commands.describe(
        deposito="Il deposito",
        nome="Nome dell'item da aggiungere",
        quantita="Quantità da aggiungere"
    )
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    @app_commands.autocomplete(nome=_dep_item_ac)
    async def give_item_deposito(interaction: discord.Interaction, deposito: str, nome: str, quantita: int):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Solo lo Staff può usare questo comando.", ephemeral=True)
            return
        if quantita <= 0:
            await interaction.response.send_message("❌ Quantità non valida.", ephemeral=True)
            return

        await _init_dep_table()
        await _add_dep_item(deposito, nome, quantita)
        dep_label = DEPOSITI[deposito]["label"]

        embed = discord.Embed(
            title="📦 Item Aggiunto al Deposito",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🏢 Deposito", value=dep_label,                 inline=True)
        embed.add_field(name="📦 Item",     value=f"{nome} x{quantita}",     inline=True)
        embed.add_field(name="👮 Staff",    value=interaction.user.mention,  inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass
