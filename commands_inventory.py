import discord
from discord import app_commands
import database
import aiosqlite
from constants import DATABASE_NAME, has_staff, LOG_CHANNEL_ID


# ── Fuzzy match ───────────────────────────────────────────────────────────────
def _fuzzy(query: str, candidates: list) -> list:
    q = query.lower().strip()
    if not q:
        return candidates
    words = q.split()
    all_match = [c for c in candidates if all(w in c.lower() for w in words)]
    if all_match:
        return all_match
    return [c for c in candidates if any(w in c.lower() for w in words)]


# ── Costanti paginazione ──────────────────────────────────────────────────────
ITEMS_PER_PAGE = 5


# ── Helper embed emporio ──────────────────────────────────────────────────────
def _build_shop_embed(page_items: list, page: int, tot: int) -> discord.Embed:
    embed = discord.Embed(
        title="🏪 𝐍𝐞𝐠𝐨𝐳𝐢𝐨 𝐝𝐞𝐥 𝐅𝐚𝐫 𝐖𝐞𝐬𝐭",
        description="Benvenuto, cowboy! Acquista con `/item-sell`." if page_items else "*L'emporio è vuoto per ora...*",
        color=discord.Color(0xDAA520),
        timestamp=discord.utils.utcnow()
    )
    for item in page_items:
        ruolo_line = f"\n🔑 **Ruolo:** <@&{item['required_role']}>" if item.get("required_role") else ""
        desc_line  = f"\n_{item['description']}_" if item.get("description") else ""
        embed.add_field(name=item["item_name"], value=f"{desc_line}{ruolo_line}" or "—", inline=True)
    embed.set_footer(text=f"🤠 Red Dead Redemption II — Emporio | Pagina {page+1}/{tot}")
    return embed


# ── View paginazione emporio (a livello modulo per persistenza callback) ───────
class ShopView(discord.ui.View):
    def __init__(self, all_items: list, page: int = 0):
        super().__init__(timeout=120)
        self._all  = all_items
        self.page  = page
        self._tot  = max(1, -(-len(all_items) // ITEMS_PER_PAGE))
        self._update_buttons()

    def _get_page(self, p: int) -> list:
        return self._all[p * ITEMS_PER_PAGE:(p + 1) * ITEMS_PER_PAGE]

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self._tot - 1

    @discord.ui.button(label="⬅️ Pagina", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=_build_shop_embed(self._get_page(self.page), self.page, self._tot),
            view=self
        )

    @discord.ui.button(label="➡️ Pagina", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(
            embed=_build_shop_embed(self._get_page(self.page), self.page, self._tot),
            view=self
        )


# ── View paginazione bisaccia (a livello modulo per persistenza callback) ──────
class BisacciaPageView(discord.ui.View):
    def __init__(self, all_items: list, titolo: str, hunger: int, thirst: int,
                 avatar_url: str, page: int = 0):
        super().__init__(timeout=120)
        self._all      = all_items
        self._titolo   = titolo
        self._hunger   = hunger
        self._thirst   = thirst
        self._avatar   = avatar_url
        self.page      = page
        self._tot      = max(1, -(-len(all_items) // ITEMS_PER_PAGE))
        self._update_buttons()

    def _bar(self, v: int) -> str:
        f = round(v / 10)
        return "█" * f + "░" * (10 - f) + f"  **{v}%**"

    def _get_page(self, p: int) -> list:
        return self._all[p * ITEMS_PER_PAGE:(p + 1) * ITEMS_PER_PAGE]

    def _build_embed(self, p: int) -> discord.Embed:
        embed = discord.Embed(title=self._titolo, color=discord.Color(0x8B4513),
                              timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=self._avatar)
        embed.add_field(name="🍔 Fame", value=self._bar(self._hunger), inline=True)
        embed.add_field(name="💦 Sete", value=self._bar(self._thirst), inline=True)
        page_items = self._get_page(p)
        if not self._all:
            embed.add_field(name="📦 Contenuto", value="*Bisaccia vuota.*", inline=False)
        else:
            desc = "\n".join(f"**{i['item_name']}** — x{i['quantity']}" for i in page_items)
            embed.add_field(name="📦 Contenuto", value=desc, inline=False)
        embed.set_footer(text=f"🤠 Red Dead Redemption II — Bisaccia | Pagina {p+1}/{self._tot}")
        return embed

    def _update_buttons(self):
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self._tot - 1

    @discord.ui.button(label="⬅️ Pagina", style=discord.ButtonStyle.primary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(self.page), view=self)

    @discord.ui.button(label="➡️ Pagina", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(self.page), view=self)


def setup_inventory_commands(bot):

    # ── Autocomplete item shop ────────────────────────────────────────────────
    async def _shop_autocomplete(interaction: discord.Interaction, current: str):
        items = await database.get_shop_items()
        names = [i["item_name"] for i in items]
        matches = _fuzzy(current, names)
        return [app_commands.Choice(name=m, value=m) for m in matches[:25]]

    # ── /listino-emporio ──────────────────────────────────────────────────────
    @bot.tree.command(name="negozio", description="Visualizza il negozio degli item disponibili")
    async def itemshop(interaction: discord.Interaction):
        all_items = await database.get_shop_items()
        tot = max(1, -(-len(all_items) // ITEMS_PER_PAGE))
        embed = _build_shop_embed(all_items[:ITEMS_PER_PAGE], 0, tot)
        if tot > 1:
            await interaction.response.send_message(embed=embed, view=ShopView(all_items, 0))
        else:
            await interaction.response.send_message(embed=embed)

    # ── /item-sell ────────────────────────────────────────────────────────────
    @bot.tree.command(name="item-sell", description="Acquista uno o più item dall'emporio")
    @app_commands.describe(item="L'item da acquistare", quantita="Quantità")
    @app_commands.autocomplete(item=_shop_autocomplete)
    async def item_sell(interaction: discord.Interaction, item: str, quantita: int = 1):
        print(f"[item-sell] START uid={interaction.user.id} item={item!r} q={quantita}", flush=True)
        uid = str(interaction.user.id)

        if quantita < 1:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True)
            return

        print(f"[item-sell] get_shop_item...", flush=True)
        shop_item = await database.get_shop_item(item)
        if not shop_item:
            print(f"[item-sell] non trovato diretto, fuzzy...", flush=True)
            all_items = await database.get_shop_items()
            matches = _fuzzy(item, [i["item_name"] for i in all_items])
            if matches:
                shop_item = await database.get_shop_item(matches[0])
        if not shop_item:
            print(f"[item-sell] item non trovato", flush=True)
            await interaction.response.send_message(
                "❌ Item non trovato. Usa l'autocomplete per scegliere.", ephemeral=True
            )
            return

        print(f"[item-sell] trovato: {shop_item['item_name']}", flush=True)
        role_id = shop_item.get("required_role")
        if role_id:
            if not isinstance(interaction.user, discord.Member) or \
               not any(r.id == role_id for r in interaction.user.roles):
                await interaction.response.send_message(
                    f"❌ Per acquistare **{shop_item['item_name']}** devi avere il ruolo <@&{role_id}>.",
                    ephemeral=True
                )
                return

        print(f"[item-sell] check saldo...", flush=True)
        totale    = shop_item["price"] * quantita
        nome_item = shop_item["item_name"]
        user_data = await database.get_user(uid)
        print(f"[item-sell] saldo={user_data['cash']} totale={totale}", flush=True)

        if user_data["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti! Hai **${user_data['cash']:,}** ma servono **${totale:,}**.",
                ephemeral=True
            )
            return

        print(f"[item-sell] acquisto...", flush=True)
        await database.update_balance(uid, cash=user_data["cash"] - totale)
        await database.add_item(uid, nome_item, quantita)
        try:
            import commands_usura as _cu
            if _cu._tipo_arma(nome_item):
                print(f"[item-sell] set_usura arma...", flush=True)
                await _cu.set_usura(uid, nome_item, 100)
        except Exception as e:
            print(f"[item-sell] usura skip (non critico): {e}", flush=True)

        print(f"[item-sell] OK, invio embed", flush=True)
        embed = discord.Embed(
            title="✅ 𝐀𝐜𝐪𝐮𝐢𝐬𝐭𝐨 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐚𝐭𝐨",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📦 Item",     value=nome_item,                       inline=True)
        embed.add_field(name="🔢 Quantità", value=str(quantita),                   inline=True)
        embed.add_field(name="💵 Pagato",   value=f"${totale:,}",                  inline=True)
        embed.add_field(name="💰 Rimasto",  value=f"${user_data['cash']-totale:,}", inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Emporio")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"[item-sell] DONE", flush=True)

    # ── /crea-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="crea-item", description="[Staff] Crea un nuovo item nell'emporio")
    @app_commands.describe(
        nome="Nome item (es: 🥃 • Whisky)",
        ruolo_richiesto="Ruolo Discord richiesto per ottenere l'item",
        descrizione="Descrizione breve (facoltativa)"
    )
    async def crea_item(
        interaction: discord.Interaction,
        nome: str,
        ruolo_richiesto: discord.Role,
        descrizione: str = ""
    ):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        role_id = ruolo_richiesto.id
        await database.upsert_shop_item(nome, 0, descrizione, role_id)

        embed = discord.Embed(title="✅ 𝐈𝐭𝐞𝐦 𝐂𝐫𝐞𝐚𝐭𝐨/𝐀𝐠𝐠𝐢𝐨𝐫𝐧𝐚𝐭𝐨", color=discord.Color.green(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="📦 Nome",            value=nome,              inline=True)
        embed.add_field(name="🔑 Ruolo Richiesto", value=f"<@&{role_id}>", inline=True)
        if descrizione:
            embed.add_field(name="📝 Descrizione", value=descrizione, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)

    # ── /eliminaitem ─────────────────────────────────────────────────────────
    @bot.tree.command(name="eliminaitem", description="[Staff] Elimina un item dall'emporio")
    @app_commands.describe(nome="Nome dell'item da eliminare")
    @app_commands.autocomplete(nome=_shop_autocomplete)
    async def elimina_item(interaction: discord.Interaction, nome: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return
        await database.delete_shop_item(nome)
        await interaction.response.send_message(f"✅ Item **{nome}** rimosso dall'emporio.", ephemeral=True)

    # ── Autocomplete per give/take ────────────────────────────────────────────
    async def _shop_items_autocomplete(interaction: discord.Interaction, current: str):
        items = await database.get_shop_items()
        names = [i["item_name"] for i in items]
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, names)[:25]]

    async def _bisaccia_autocomplete(interaction: discord.Interaction, current: str):
        try:
            giocatore_id = interaction.namespace.giocatore
            if not giocatore_id:
                return []
            items = await database.get_inventory(str(giocatore_id))
            names = [i["item_name"] for i in items]
            return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, names)[:25]]
        except Exception:
            return []

    # ── /give-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="give-item", description="[Staff] Dai un item a un giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="Nome item", quantita="Quantità")
    @app_commands.autocomplete(item=_shop_items_autocomplete)
    async def give_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        shop_items = await database.get_shop_items()
        names = [i["item_name"] for i in shop_items]
        exact = next((n for n in names if n.lower() == item.lower()), None)
        matches = [exact] if exact else _fuzzy(item, names)

        if len(matches) == 0:
            item_finale = item
        elif len(matches) == 1:
            item_finale = matches[0]
        else:
            embed = discord.Embed(
                title="🔍 Trovati più item con questo nome:",
                description="Seleziona l'item da consegnare dal menu qui sotto.",
                color=discord.Color(0xDAA520),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="🤠 Red Dead Redemption II — Admin")

            class GiveSelect(discord.ui.Select):
                def __init__(self_s):
                    options = [discord.SelectOption(label=m[:100], value=m) for m in matches[:25]]
                    super().__init__(placeholder="Scegli l'item...", options=options)

                async def callback(self_s, itr: discord.Interaction):
                    chosen = self_s.values[0]
                    await database.add_item(str(giocatore.id), chosen, quantita)
                    done = discord.Embed(title="🎁 𝐈𝐭𝐞𝐦 𝐂𝐨𝐧𝐬𝐞𝐠𝐧𝐚𝐭𝐨", color=discord.Color.green(),
                                        timestamp=discord.utils.utcnow())
                    done.add_field(name="👤 Ricevuto da", value=giocatore.mention, inline=True)
                    done.add_field(name="📦 Item",        value=chosen,            inline=True)
                    done.add_field(name="🔢 Quantità",    value=str(quantita),     inline=True)
                    done.add_field(name="👮 Staff",       value=itr.user.mention,  inline=True)
                    done.set_footer(text="🤠 Red Dead Redemption II — Admin")
                    await itr.response.edit_message(embed=done, view=None)

            view = discord.ui.View(timeout=60)
            view.add_item(GiveSelect())
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        await database.add_item(str(giocatore.id), item_finale, quantita)
        embed = discord.Embed(title="🎁 𝐈𝐭𝐞𝐦 𝐂𝐨𝐧𝐬𝐞𝐠𝐧𝐚𝐭𝐨", color=discord.Color.green(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Ricevuto da", value=giocatore.mention,        inline=True)
        embed.add_field(name="📦 Item",        value=item_finale,              inline=True)
        embed.add_field(name="🔢 Quantità",    value=str(quantita),            inline=True)
        embed.add_field(name="👮 Staff",       value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)

    # ── /take-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="take-item", description="[Staff] Rimuovi un item dalla bisaccia di un giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="Nome item (fuzzy search nella bisaccia)", quantita="Quantità")
    @app_commands.autocomplete(item=_bisaccia_autocomplete)
    async def take_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        inventory = await database.get_inventory(str(giocatore.id))
        names = [i["item_name"] for i in inventory]
        exact = next((n for n in names if n.lower() == item.lower()), None)
        matches = [exact] if exact else _fuzzy(item, names)

        if len(matches) == 0:
            await interaction.response.send_message(
                f"❌ **{giocatore.display_name}** non ha nessun item corrispondente a **{item}**.",
                ephemeral=True
            )
            return
        elif len(matches) == 1:
            item_finale = matches[0]
        else:
            embed = discord.Embed(
                title="🔍 Trovati più item con questo nome:",
                description=f"Seleziona l'item da rimuovere dalla bisaccia di **{giocatore.display_name}**.",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text="🤠 Red Dead Redemption II — Admin")

            class TakeSelect(discord.ui.Select):
                def __init__(self_s):
                    options = [discord.SelectOption(label=m[:100], value=m) for m in matches[:25]]
                    super().__init__(placeholder="Scegli l'item da rimuovere...", options=options)

                async def callback(self_s, itr: discord.Interaction):
                    chosen = self_s.values[0]
                    if not await database.remove_item(str(giocatore.id), chosen, quantita):
                        await itr.response.edit_message(
                            embed=discord.Embed(
                                title="❌ Quantità insufficiente",
                                description=f"**{giocatore.display_name}** non ha abbastanza **{chosen}**.",
                                color=discord.Color.red()
                            ), view=None
                        )
                        return
                    done = discord.Embed(title="📦 𝐈𝐭𝐞𝐦 𝐑𝐢𝐦𝐨𝐬𝐬𝐨", color=discord.Color.orange(),
                                        timestamp=discord.utils.utcnow())
                    done.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
                    done.add_field(name="📦 Item",      value=chosen,            inline=True)
                    done.add_field(name="🔢 Quantità",  value=str(quantita),     inline=True)
                    done.add_field(name="👮 Staff",     value=itr.user.mention,  inline=True)
                    done.set_footer(text="🤠 Red Dead Redemption II — Admin")
                    await itr.response.edit_message(embed=done, view=None)

            view = discord.ui.View(timeout=60)
            view.add_item(TakeSelect())
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        if not await database.remove_item(str(giocatore.id), item_finale, quantita):
            await interaction.response.send_message(
                f"❌ **{giocatore.display_name}** non ha abbastanza **{item_finale}**.", ephemeral=True
            )
            return
        embed = discord.Embed(title="📦 𝐈𝐭𝐞𝐦 𝐑𝐢𝐦𝐨𝐬𝐬𝐨", color=discord.Color.orange(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="📦 Item",      value=item_finale,              inline=True)
        embed.add_field(name="🔢 Quantità",  value=str(quantita),            inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)

    # ── /rimuovibisaccia ──────────────────────────────────────────────────────
    @bot.tree.command(name="rimuovibisaccia", description="[Staff] Rimuovi la bisaccia di un giocatore")
    @app_commands.describe(giocatore="Il giocatore")
    async def rimuovi_bisaccia(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM inventory WHERE user_id=?", (str(giocatore.id),))
            await db.commit()
        embed = discord.Embed(title="🗑️ 𝐁𝐢𝐬𝐚𝐜𝐜𝐢𝐚 𝐑𝐢𝐦𝐨𝐬𝐬𝐚", color=discord.Color.red(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,        inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
