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
)

PINKERTON_ROLE_ID = 1420267736319266906
PEAKY_ROLE_ID     = 1494988697127485513
SILENT_ROLE_ID    = 1495036199096811570
BLACKWOOD_ROLE_ID = 1496603144551923905
SONS_ROLE_ID      = 1501323223411855583

DEPOSITI = {
    "pinkerton":  {"label": "🕵️ | Deposito Pinkerton",        "ruoli": [PINKERTON_ROLE_ID]},
    "sceriffato": {"label": "🤠 | Deposito Sceriffato",        "ruoli": [SCERIFFO_ROLE_ID]},
    "armeria":    {"label": "🔫 | Deposito Armeria",           "ruoli": [ARMIERE_ROLE_ID]},
    "stalla":     {"label": "🐎 | Deposito Stalla",            "ruoli": [STALLA_ROLE_ID]},
    "emporio":    {"label": "🏪 | Deposito Emporio",           "ruoli": [EMPORIO_ROLE_ID]},
    "saloon":     {"label": "🍻 | Deposito Saloon",            "ruoli": [SALOON_ROLE_ID]},
    "medico":     {"label": "🩺 | Deposito Studio Medico",     "ruoli": [DOTTORE_ROLE_ID]},
    "peaky":      {"label": "🐦‍⬛ | Deposito Peaky Blinders",   "ruoli": [PEAKY_ROLE_ID]},
    "sons":       {"label": "👻 | Deposito Sons Of Shadows",  "ruoli": [SONS_ROLE_ID]},
}

DEPOSITI_CHOICES = [app_commands.Choice(name=v["label"], value=k) for k, v in DEPOSITI.items()]

def _ha_accesso(interaction: discord.Interaction, dep: str) -> bool:
    if has_staff(interaction): return True
    if not isinstance(interaction.user, discord.Member): return False
    return any(r.id in DEPOSITI[dep]["ruoli"] for r in interaction.user.roles)

def _fuzzy(q: str, candidates: list) -> list:
    q = q.lower().strip()
    if not q: return candidates
    words = q.split()
    r = [c for c in candidates if all(w in c.lower() for w in words)]
    return r or [c for c in candidates if any(w in c.lower() for w in words)]

# ── DB ────────────────────────────────────────────────────────────────────────
async def _init():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                deposito TEXT NOT NULL, item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 0, PRIMARY KEY (deposito, item_name)
            )
        """)
        await db.commit()

async def _get_items(dep: str) -> list[dict]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_name, quantity FROM deposits WHERE deposito=? AND quantity>0 ORDER BY item_name",
            (dep,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def _get_qty(dep: str, item: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM deposits WHERE deposito=? AND item_name=?", (dep, item)
        ) as c:
            r = await c.fetchone()
            return r[0] if r else 0

async def _add(dep: str, item: str, qty: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO deposits (deposito, item_name, quantity) VALUES (?,?,?)
            ON CONFLICT(deposito, item_name) DO UPDATE SET quantity=quantity+excluded.quantity
        """, (dep, item, qty))
        await db.commit()

async def _remove(dep: str, item: str, qty: int) -> bool:
    cur = await _get_qty(dep, item)
    if cur < qty: return False
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE deposits SET quantity=quantity-? WHERE deposito=? AND item_name=?",
            (qty, dep, item)
        )
        await db.commit()
    return True

# ── HELPER EMBED ──────────────────────────────────────────────────────────────
def _embed_lista(dep: str, items: list, pagina: int, tot_pag: int, per_pag: int, modo: str) -> discord.Embed:
    dep_label = DEPOSITI[dep]["label"]
    s = pagina * per_pag
    e = min(s + per_pag, len(items))
    if modo == "preleva":
        titolo = "🏢 Deposito Fazione — Prelievo"
        desc = (
            f"📖 **Come funziona:**\n"
            f"• Deposito: **{dep_label}**\n"
            f"• Seleziona un item e la quantità da mettere nello zaino.\n\n"
            f"Mostrati **{s+1}–{e}** di **{len(items)}**\n**Pagina {pagina+1} di {tot_pag}**"
        )
    else:
        titolo = "🏢 Deposito Fazione"
        desc = (
            f"📖 **Come funziona:**\n"
            f"• Deposito: **{dep_label}**\n"
            f"1️⃣ Seleziona l'oggetto da **depositare**.\n"
            f"2️⃣ Scegli **quante unità** depositare.\n"
            f"♻️ Puoi depositare più item finché il pannello resta aperto.\n\n"
            f"Mostrati **{s+1}–{e}** di **{len(items)}**\n**Pagina {pagina+1} di {tot_pag}**"
        )
    embed = discord.Embed(title=titolo, description=desc,
                          color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
    embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
    return embed

def _embed_qty_preleva(item: str, qty_dep: int) -> discord.Embed:
    embed = discord.Embed(title="🎒 Scegli quantità da prelevare",
                          color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
    embed.description = (
        f"Item: **{item}**\n"
        f"Nel deposito: **{qty_dep}**\n"
        f"Massimo Prelevabile ora: **{qty_dep}**"
    )
    embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
    return embed

def _embed_qty_deposita(item: str, qty_inv: int) -> discord.Embed:
    embed = discord.Embed(title="📦 Scegli quantità da depositare",
                          color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
    embed.description = f"Item: **{item}**\nNe possiedi: **{qty_inv}**"
    embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
    return embed

def _embed_pub_preleva(dep: str, item: str, qty: int) -> discord.Embed:
    ora = datetime.now(timezone.utc).strftime("%H:%M")
    embed = discord.Embed(title="🎒 Prelievo Deposito Fazione",
                          color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
    embed.description = (
        f"✅ Prelievo completato.\n\n"
        f"**🏢 Deposito:** {DEPOSITI[dep]['label']}\n"
        f"**📦 Item: {qty}x** {item}"
    )
    embed.set_footer(text=f"🤠 Oggi alle {ora}")
    return embed

def _embed_pub_deposita(dep: str, item: str, qty: int) -> discord.Embed:
    ora = datetime.now(timezone.utc).strftime("%H:%M")
    embed = discord.Embed(title="🏢 Deposito Fazione",
                          color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
    embed.description = (
        f"✅ Deposito effettuato con successo.\n\n"
        f"**🏢 Deposito:** {DEPOSITI[dep]['label']}\n"
        f"**📦 Item: {qty}x** {item}"
    )
    embed.set_footer(text=f"🤠 Oggi alle {ora}")
    return embed


# ═════════════════════════════════════════════════════════════════════════════
#  MODAL QUANTITÀ PERSONALIZZATA
# ═════════════════════════════════════════════════════════════════════════════
class QtyModalPreleva(discord.ui.Modal, title="🔢 Quantità personalizzata"):
    q = discord.ui.TextInput(
        label="Quantità da prelevare",
        placeholder="Inserisci un numero...",
        required=True, max_length=6
    )

    def __init__(self, bot, uid: int, dep: str, item: str, qty_dep: int):
        super().__init__()
        self.bot     = bot
        self.uid     = uid
        self.dep     = dep
        self.item    = item
        self.qty_dep = qty_dep
        self.q.label       = f"Quanti {item[:40]} vuoi prelevare?"
        self.q.placeholder = f"Max: {qty_dep}"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.q.value)
        except ValueError:
            await interaction.response.send_message("❌ Inserisci un numero valido.", ephemeral=True); return
        if qty <= 0 or qty > self.qty_dep:
            await interaction.response.send_message(f"❌ Max: {self.qty_dep}", ephemeral=True); return
        ok = await _remove(self.dep, self.item, qty)
        if not ok:
            await interaction.response.send_message("❌ Quantità non disponibile.", ephemeral=True); return
        await database.add_item(str(self.uid), self.item, qty)
        await interaction.response.send_message("✅ Prelievo completato!", ephemeral=True)
        await interaction.channel.send(content=f"<@{self.uid}>",
                                       embed=_embed_pub_preleva(self.dep, self.item, qty))
        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="📦 LOG — Prelievo Deposito",
                                    color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                log.add_field(name="👤", value=f"<@{self.uid}>", inline=True)
                log.add_field(name="🏢", value=DEPOSITI[self.dep]["label"], inline=True)
                log.add_field(name="📦", value=f"{self.item} x{qty}", inline=True)
                await ch.send(embed=log)
        except Exception: pass


class QtyModalDeposita(discord.ui.Modal, title="🔢 Quantità personalizzata"):
    q = discord.ui.TextInput(
        label="Quantità da depositare",
        placeholder="Inserisci un numero...",
        required=True, max_length=6
    )

    def __init__(self, bot, uid: int, dep: str, item: str, qty_inv: int):
        super().__init__()
        self.bot     = bot
        self.uid     = uid
        self.dep     = dep
        self.item    = item
        self.qty_inv = qty_inv
        self.q.label       = f"Quanti {item[:40]} vuoi depositare?"
        self.q.placeholder = f"Max: {qty_inv}"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qty = int(self.q.value)
        except ValueError:
            await interaction.response.send_message("❌ Inserisci un numero valido.", ephemeral=True); return
        if qty <= 0 or qty > self.qty_inv:
            await interaction.response.send_message(f"❌ Max: {self.qty_inv}", ephemeral=True); return
        ok = await database.remove_item(str(self.uid), self.item, qty)
        if not ok:
            await interaction.response.send_message("❌ Non hai abbastanza item.", ephemeral=True); return
        await _add(self.dep, self.item, qty)
        await interaction.response.send_message("✅ Depositato!", ephemeral=True)
        await interaction.channel.send(content=f"<@{self.uid}>",
                                       embed=_embed_pub_deposita(self.dep, self.item, qty))
        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="📦 LOG — Deposito Fazione",
                                    color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                log.add_field(name="👤", value=f"<@{self.uid}>", inline=True)
                log.add_field(name="🏢", value=DEPOSITI[self.dep]["label"], inline=True)
                log.add_field(name="📦", value=f"{self.item} x{qty}", inline=True)
                await ch.send(embed=log)
        except Exception: pass

# ═════════════════════════════════════════════════════════════════════════════
#  VIEW PRELIEVO — lista item
# ═════════════════════════════════════════════════════════════════════════════
class PrelievoListaView(discord.ui.View):
    PER_PAG = 25

    def __init__(self, bot, uid: int, dep: str, items: list, pagina: int = 0):
        super().__init__(timeout=300)
        self.bot    = bot
        self.uid    = uid
        self.dep    = dep
        self.items  = items
        self.pagina = pagina
        self.tot    = max(1, -(-len(items) // self.PER_PAG))
        self._build()

    def _build(self):
        self.clear_items()
        s     = self.pagina * self.PER_PAG
        chunk = self.items[s:s + self.PER_PAG]
        opts  = [discord.SelectOption(label=f"{i['item_name'][:80]} (x{i['quantity']})", value=i["item_name"])
                 for i in chunk] or [discord.SelectOption(label="Deposito vuoto", value="__vuoto__")]

        sel = discord.ui.Select(placeholder="Seleziona un item da mettere nello zaino", options=opts)

        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
            v = interaction.data["values"][0]
            if v == "__vuoto__":
                await interaction.response.send_message("❌ Deposito vuoto.", ephemeral=True); return
            qty_dep = await _get_qty(self.dep, v)
            view2   = PrelievoQtyView(self.bot, self.uid, self.dep, v, qty_dep, self)
            await interaction.response.edit_message(embed=_embed_qty_preleva(v, qty_dep), view=view2)

        sel.callback = _cb
        self.add_item(sel)

        btn_prev = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary,
                                     disabled=self.pagina == 0, row=1)
        btn_next = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary,
                                     disabled=self.pagina >= self.tot - 1, row=1)
        btn_close = discord.ui.Button(label="❌ Chiudi Pannello", style=discord.ButtonStyle.danger, row=1)

        async def _prev(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            self.pagina -= 1
            self._build()
            await interaction.response.edit_message(
                embed=_embed_lista(self.dep, self.items, self.pagina, self.tot, self.PER_PAG, "preleva"),
                view=self)

        async def _next(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            self.pagina += 1
            self._build()
            await interaction.response.edit_message(
                embed=_embed_lista(self.dep, self.items, self.pagina, self.tot, self.PER_PAG, "preleva"),
                view=self)

        async def _close(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            await interaction.response.edit_message(content="✅ Pannello chiuso.", embed=None, view=None)

        btn_prev.callback  = _prev
        btn_next.callback  = _next
        btn_close.callback = _close
        self.add_item(btn_prev)
        self.add_item(btn_next)
        self.add_item(btn_close)


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW PRELIEVO — quantità
# ═════════════════════════════════════════════════════════════════════════════
class PrelievoQtyView(discord.ui.View):
    def __init__(self, bot, uid: int, dep: str, item: str, qty_dep: int, parent):
        super().__init__(timeout=300)
        self.bot     = bot
        self.uid     = uid
        self.dep     = dep
        self.item    = item
        self.qty_dep = qty_dep
        self.parent  = parent
        self._build()

    def _build(self):
        self.clear_items()
        max_q = min(self.qty_dep, 25)
        opts  = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, max_q + 1)] \
                or [discord.SelectOption(label="0", value="0")]

        sel = discord.ui.Select(placeholder=f"Seleziona la quantità (1–{max_q})", options=opts)

        async def _sel_cb(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            await self._preleva(interaction, int(interaction.data["values"][0]))

        sel.callback = _sel_cb
        self.add_item(sel)

        btn_custom = discord.ui.Button(label="🔢 Quantità Personalizzata",
                                       style=discord.ButtonStyle.primary, row=1)
        btn_back   = discord.ui.Button(label="⬅️ Indietro",
                                       style=discord.ButtonStyle.secondary, row=1)

        async def _custom(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            dep    = self.dep
            item   = self.item
            qty_dep= self.qty_dep
            bot    = self.bot
            uid    = self.uid
            parent = self.parent

            await interaction.response.send_modal(
                    QtyModalPreleva(bot, uid, dep, item, qty_dep))

        async def _back(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            self.parent._build()
            await interaction.response.edit_message(
                embed=_embed_lista(self.dep, self.parent.items, self.parent.pagina,
                                   self.parent.tot, self.parent.PER_PAG, "preleva"),
                view=self.parent)

        btn_custom.callback = _custom
        btn_back.callback   = _back
        self.add_item(btn_custom)
        self.add_item(btn_back)

    async def _preleva(self, interaction: discord.Interaction, qty: int):
        ok = await _remove(self.dep, self.item, qty)
        if not ok:
            await interaction.response.send_message("❌ Quantità non disponibile.", ephemeral=True); return
        await database.add_item(str(self.uid), self.item, qty)
        await interaction.response.edit_message(content="✅ Prelievo completato! Pannello chiuso.",
                                                embed=None, view=None)
        await interaction.channel.send(content=f"<@{self.uid}>",
                                       embed=_embed_pub_preleva(self.dep, self.item, qty))
        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="📦 LOG — Prelievo Deposito",
                                    color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                log.add_field(name="👤", value=f"<@{self.uid}>", inline=True)
                log.add_field(name="🏢", value=DEPOSITI[self.dep]["label"], inline=True)
                log.add_field(name="📦", value=f"{self.item} x{qty}", inline=True)
                await ch.send(embed=log)
        except Exception: pass


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW DEPOSITO — lista item
# ═════════════════════════════════════════════════════════════════════════════
class DepositaListaView(discord.ui.View):
    PER_PAG = 25

    def __init__(self, bot, uid: int, dep: str, items: list, pagina: int = 0):
        super().__init__(timeout=300)
        self.bot    = bot
        self.uid    = uid
        self.dep    = dep
        self.items  = items
        self.pagina = pagina
        self.tot    = max(1, -(-len(items) // self.PER_PAG))
        self._build()

    def _build(self):
        self.clear_items()
        s     = self.pagina * self.PER_PAG
        chunk = self.items[s:s + self.PER_PAG]
        opts  = [discord.SelectOption(label=f"{i['item_name'][:80]} (x{i['quantity']})", value=i["item_name"])
                 for i in chunk] or [discord.SelectOption(label="Bisaccia vuota", value="__vuoto__")]

        sel = discord.ui.Select(placeholder="Seleziona l'item da depositare", options=opts)

        async def _cb(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            v = interaction.data["values"][0]
            if v == "__vuoto__":
                await interaction.response.send_message("❌ Bisaccia vuota.", ephemeral=True); return
            qty_inv = await database.get_item_quantity(str(self.uid), v)
            view2   = DepositaQtyView(self.bot, self.uid, self.dep, v, qty_inv, self)
            await interaction.response.edit_message(embed=_embed_qty_deposita(v, qty_inv), view=view2)

        sel.callback = _cb
        self.add_item(sel)

        btn_prev  = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary,
                                      disabled=self.pagina == 0, row=1)
        btn_next  = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary,
                                      disabled=self.pagina >= self.tot - 1, row=1)

        async def _prev(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            self.pagina -= 1; self._build()
            await interaction.response.edit_message(
                embed=_embed_lista(self.dep, self.items, self.pagina, self.tot, self.PER_PAG, "deposita"),
                view=self)

        async def _next(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            self.pagina += 1; self._build()
            await interaction.response.edit_message(
                embed=_embed_lista(self.dep, self.items, self.pagina, self.tot, self.PER_PAG, "deposita"),
                view=self)

        btn_prev.callback = _prev
        btn_next.callback = _next
        self.add_item(btn_prev)
        self.add_item(btn_next)


# ═════════════════════════════════════════════════════════════════════════════
#  VIEW DEPOSITO — quantità
# ═════════════════════════════════════════════════════════════════════════════
class DepositaQtyView(discord.ui.View):
    def __init__(self, bot, uid: int, dep: str, item: str, qty_inv: int, parent):
        super().__init__(timeout=300)
        self.bot     = bot
        self.uid     = uid
        self.dep     = dep
        self.item    = item
        self.qty_inv = qty_inv
        self.parent  = parent
        self._build()

    def _build(self):
        self.clear_items()
        max_q = min(self.qty_inv, 25)
        opts  = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, max_q + 1)] \
                or [discord.SelectOption(label="0", value="0")]

        sel = discord.ui.Select(placeholder=f"Seleziona la quantità (1–{max_q})", options=opts)

        async def _sel_cb(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            await self._deposita(interaction, int(interaction.data["values"][0]))

        sel.callback = _sel_cb
        self.add_item(sel)

        btn_custom = discord.ui.Button(label="🔢 Quantità Personalizzata",
                                       style=discord.ButtonStyle.primary, row=1)
        btn_back   = discord.ui.Button(label="⬅️ Indietro",
                                       style=discord.ButtonStyle.secondary, row=1)

        async def _custom(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            dep    = self.dep; item = self.item; qty_inv = self.qty_inv
            bot    = self.bot; uid  = self.uid;  parent  = self.parent

            await interaction.response.send_modal(
                    QtyModalDeposita(bot, uid, dep, item, qty_inv))

        async def _back(interaction: discord.Interaction):
            if interaction.user.id != self.uid:
                await interaction.response.send_message("❌", ephemeral=True); return
            inv = await database.get_inventory(str(self.uid))
            self.parent.items = inv
            self.parent.tot   = max(1, -(-len(inv) // self.parent.PER_PAG))
            self.parent._build()
            await interaction.response.edit_message(
                embed=_embed_lista(self.dep, inv, self.parent.pagina,
                                   self.parent.tot, self.parent.PER_PAG, "deposita"),
                view=self.parent)

        btn_custom.callback = _custom
        btn_back.callback   = _back
        self.add_item(btn_custom)
        self.add_item(btn_back)

    async def _deposita(self, interaction: discord.Interaction, qty: int):
        ok = await database.remove_item(str(self.uid), self.item, qty)
        if not ok:
            await interaction.response.send_message("❌ Non hai abbastanza item.", ephemeral=True); return
        await _add(self.dep, self.item, qty)
        inv = await database.get_inventory(str(self.uid))
        self.parent.items = inv
        self.parent.tot   = max(1, -(-len(inv) // self.parent.PER_PAG))
        self.parent._build()
        await interaction.response.edit_message(
            embed=_embed_lista(self.dep, inv, self.parent.pagina,
                               self.parent.tot, self.parent.PER_PAG, "deposita"),
            view=self.parent)
        await interaction.channel.send(content=f"<@{self.uid}>",
                                       embed=_embed_pub_deposita(self.dep, self.item, qty))
        try:
            ch = self.bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="📦 LOG — Deposito Fazione",
                                    color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
                log.add_field(name="👤", value=f"<@{self.uid}>", inline=True)
                log.add_field(name="🏢", value=DEPOSITI[self.dep]["label"], inline=True)
                log.add_field(name="📦", value=f"{self.item} x{qty}", inline=True)
                await ch.send(embed=log)
        except Exception: pass


# ═════════════════════════════════════════════════════════════════════════════
#  SETUP COMANDI
# ═════════════════════════════════════════════════════════════════════════════
def setup_deposits_commands(bot: commands.Bot):

    @bot.tree.command(name="depgenerici", description="Preleva item da un deposito fazione")
    @app_commands.describe(deposito="Seleziona il deposito fazione")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    async def depgenerici(interaction: discord.Interaction, deposito: str):
        await _init()
        if not _ha_accesso(interaction, deposito):
            await interaction.response.send_message(
                f"❌ Non hai accesso al **{DEPOSITI[deposito]['label']}**.", ephemeral=True); return
        items = await _get_items(deposito)
        if not items:
            await interaction.response.send_message(
                f"❌ Il **{DEPOSITI[deposito]['label']}** è vuoto.", ephemeral=True); return
        view = PrelievoListaView(bot, interaction.user.id, deposito, items)
        await interaction.response.send_message(
            embed=_embed_lista(deposito, items, 0, view.tot, view.PER_PAG, "preleva"),
            view=view, ephemeral=True)

    @bot.tree.command(name="mettidepfazione", description="Deposita item dalla tua bisaccia in un deposito fazione")
    @app_commands.describe(deposito="Seleziona il deposito fazione")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    async def mettidepfazione(interaction: discord.Interaction, deposito: str):
        await _init()
        if not _ha_accesso(interaction, deposito):
            await interaction.response.send_message(
                f"❌ Non hai accesso al **{DEPOSITI[deposito]['label']}**.", ephemeral=True); return
        inv = await database.get_inventory(str(interaction.user.id))
        if not inv:
            await interaction.response.send_message("❌ La tua bisaccia è vuota.", ephemeral=True); return
        view = DepositaListaView(bot, interaction.user.id, deposito, inv)
        await interaction.response.send_message(
            embed=_embed_lista(deposito, inv, 0, view.tot, view.PER_PAG, "deposita"),
            view=view, ephemeral=True)

    async def _ac_give(interaction: discord.Interaction, current: str):
        dep = next((o["value"] for o in interaction.data.get("options", []) if o["name"] == "deposito"), None)
        if not dep: return []
        items = await _get_items(dep)
        nomi  = [i["item_name"] for i in items]
        return [app_commands.Choice(name=m[:100], value=m)
                for m in (_fuzzy(current, nomi) if current else nomi)[:25]]

    @bot.tree.command(name="give-item-deposito", description="[Staff] Aggiungi item in un deposito fazione")
    @app_commands.describe(deposito="Il deposito", nome="Nome item", quantita="Quantità")
    @app_commands.choices(deposito=DEPOSITI_CHOICES)
    @app_commands.autocomplete(nome=_ac_give)
    async def give_item_deposito(interaction: discord.Interaction, deposito: str, nome: str, quantita: int):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Solo lo Staff.", ephemeral=True); return
        if quantita <= 0:
            await interaction.response.send_message("❌ Quantità non valida.", ephemeral=True); return
        await _init()
        await _add(deposito, nome, quantita)
        embed = discord.Embed(title="📦 Item Aggiunto al Deposito",
                              color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="🏢 Deposito", value=DEPOSITI[deposito]["label"], inline=True)
        embed.add_field(name="📦 Item",     value=f"{nome} x{quantita}",      inline=True)
        embed.add_field(name="👮 Staff",    value=interaction.user.mention,    inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Depositi Fazione")
        await interaction.response.send_message(embed=embed)
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass
