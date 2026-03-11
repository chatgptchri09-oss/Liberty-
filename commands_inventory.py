import discord
from discord import app_commands
import database
import aiosqlite
from constants import DATABASE_NAME, has_staff, LOG_CHANNEL_ID


# ── Fuzzy match ───────────────────────────────────────────────────────────────
def _fuzzy(query: str, candidates: list) -> list:
    """Restituisce candidati che contengono ogni parola del query (tutte, poi almeno una)."""
    q = query.lower().strip()
    if not q:
        return candidates
    words = q.split()
    # Prima prova: tutte le parole presenti
    all_match = [c for c in candidates if all(w in c.lower() for w in words)]
    if all_match:
        return all_match
    # Seconda prova: almeno una parola
    return [c for c in candidates if any(w in c.lower() for w in words)]


def setup_inventory_commands(bot):

    # ── Helper paginazione emporio ───────────────────────────────────────────
    ITEMS_PER_PAGE = 5

    def _build_shop_embed(page_items: list, page: int, tot: int) -> discord.Embed:
        embed = discord.Embed(
            title="🏪 𝐄𝐦𝐩𝐨𝐫𝐢𝐨 𝐝𝐞𝐥 𝐅𝐚𝐫 𝐖𝐞𝐬𝐭",
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

    # ── /listino-emporio ──────────────────────────────────────────────────────
    @bot.tree.command(name="listino-emporio", description="Visualizza il negozio degli item disponibili")
    async def itemshop(interaction: discord.Interaction):
        all_items = await database.get_shop_items()
        tot = max(1, -(-len(all_items) // ITEMS_PER_PAGE))

        def get_page(p):
            return all_items[p * ITEMS_PER_PAGE:(p + 1) * ITEMS_PER_PAGE]

        class ShopView(discord.ui.View):
            def __init__(self_v, p=0):
                super().__init__(timeout=120)
                self_v.p = p
                self_v._refresh()

            def _refresh(self_v):
                self_v.prev_btn.disabled = self_v.p == 0
                self_v.next_btn.disabled = self_v.p >= tot - 1

            @discord.ui.button(label="⬅️ Pagina", style=discord.ButtonStyle.primary)
            async def prev_btn(self_v, itr: discord.Interaction, btn):
                self_v.p -= 1
                self_v._refresh()
                await itr.response.edit_message(embed=_build_shop_embed(get_page(self_v.p), self_v.p, tot), view=self_v)

            @discord.ui.button(label="➡️ Pagina", style=discord.ButtonStyle.primary)
            async def next_btn(self_v, itr: discord.Interaction, btn):
                self_v.p += 1
                self_v._refresh()
                await itr.response.edit_message(embed=_build_shop_embed(get_page(self_v.p), self_v.p, tot), view=self_v)

        if tot > 1:
            await interaction.response.send_message(embed=_build_shop_embed(get_page(0), 0, tot), view=ShopView())
        else:
            await interaction.response.send_message(embed=_build_shop_embed(get_page(0), 0, tot))

    # ── Autocomplete item shop ────────────────────────────────────────────────
    async def _shop_autocomplete(interaction: discord.Interaction, current: str):
        items = await database.get_shop_items()
        names = [i["item_name"] for i in items]
        matches = _fuzzy(current, names)
        return [app_commands.Choice(name=m, value=m) for m in matches[:25]]

    # ── /item-sell ────────────────────────────────────────────────────────────
    @bot.tree.command(name="item-sell", description="Acquista uno o più item dall'emporio")
    @app_commands.describe(item="L'item da acquistare", quantita="Quantità")
    @app_commands.autocomplete(item=_shop_autocomplete)
    async def item_sell(interaction: discord.Interaction, item: str, quantita: int = 1):
        if quantita < 1:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True)
            return

        shop_item = await database.get_shop_item(item)
        # Fuzzy fallback se non trovato esatto
        if not shop_item:
            all_items = await database.get_shop_items()
            matches = _fuzzy(item, [i["item_name"] for i in all_items])
            if matches:
                shop_item = await database.get_shop_item(matches[0])
        if not shop_item:
            await interaction.response.send_message(
                "❌ Item non trovato nell'emporio. Controlla `/itemshop`.", ephemeral=True
            )
            return

        # Controllo ruolo richiesto
        role_id = shop_item.get("required_role")
        if role_id:
            if not isinstance(interaction.user, discord.Member) or \
               not any(r.id == role_id for r in interaction.user.roles):
                await interaction.response.send_message(
                    f"❌ Per acquistare **{shop_item['item_name']}** devi avere il ruolo <@&{role_id}>.",
                    ephemeral=True
                )
                return

        totale = shop_item["price"] * quantita
        user   = await database.get_user(str(interaction.user.id))
        if user["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti!\nCosto: **${totale:,}** — Tuoi: **${user['cash']:,}**",
                ephemeral=True
            )
            return

        await database.update_balance(str(interaction.user.id), cash=user["cash"] - totale)
        await database.add_item(str(interaction.user.id), shop_item["item_name"], quantita)

        embed = discord.Embed(title="🛒 𝐀𝐜𝐪𝐮𝐢𝐬𝐭𝐨 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐚𝐭𝐨", color=discord.Color(0x8B4513),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="📦 Item",     value=shop_item["item_name"], inline=True)
        embed.add_field(name="🔢 Quantità", value=str(quantita),          inline=True)
        embed.add_field(name="💵 Pagato",   value=f"${totale:,}",         inline=True)
        embed.add_field(name="💰 Rimasto",  value=f"${user['cash']-totale:,}", inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Emporio")
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
        embed.add_field(name="📦 Nome",              value=nome,              inline=True)
        embed.add_field(name="🔑 Ruolo Richiesto",   value=f"<@&{role_id}>", inline=True)
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

    # ── /give-item ────────────────────────────────────────────────────────────
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
            item_finale = item  # usa testo così com'è se non trovato nel negozio
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
                    done = discord.Embed(title="🎁 𝐈𝐭𝐞𝐦 𝐂𝐨𝐧𝐬𝐞𝐠𝐧𝐚𝐭𝐨", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                    done.add_field(name="👤 Ricevuto da", value=giocatore.mention,   inline=True)
                    done.add_field(name="📦 Item",        value=chosen,              inline=True)
                    done.add_field(name="🔢 Quantità",    value=str(quantita),       inline=True)
                    done.add_field(name="👮 Staff",       value=itr.user.mention,    inline=True)
                    done.set_footer(text="🤠 Red Dead Redemption II — Admin")
                    await itr.response.edit_message(embed=done, view=None)

            view = discord.ui.View(timeout=60)
            view.add_item(GiveSelect())
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        await database.add_item(str(giocatore.id), item_finale, quantita)
        embed = discord.Embed(title="🎁 𝐈𝐭𝐞𝐦 𝐂𝐨𝐧𝐬𝐞𝐠𝐧𝐚𝐭𝐨", color=discord.Color.green(), timestamp=discord.utils.utcnow())
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
                    done = discord.Embed(title="📦 𝐈𝐭𝐞𝐦 𝐑𝐢𝐦𝐨𝐬𝐬𝐨", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
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
        embed = discord.Embed(title="📦 𝐈𝐭𝐞𝐦 𝐑𝐢𝐦𝐨𝐬𝐬𝐨", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
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
