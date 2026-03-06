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

    # ── /itemshop ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="itemshop", description="Visualizza il negozio degli item disponibili")
    async def itemshop(interaction: discord.Interaction):
        items = await database.get_shop_items()

        embed = discord.Embed(
            title="🏪 𝐄𝐦𝐩𝐨𝐫𝐢𝐨 𝐝𝐞𝐥 𝐅𝐚𝐫 𝐖𝐞𝐬𝐭",
            description="Benvenuto, cowboy! Acquista con `/item-sell`.",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )

        if not items:
            embed.description = "*L'emporio è vuoto per ora...*"
        else:
            for item in items:
                ruolo_line = ""
                if item.get("required_role"):
                    ruolo_line = f"\n🔑 **Ruolo Richiesto:** <@&{item['required_role']}>"
                embed.add_field(
                    name=item["item_name"],
                    value=f"💵 **${item['price']:,}**\n_{item['description']}_{ruolo_line}",
                    inline=True
                )
        embed.set_footer(text="🤠 Red Dead Redemption II — Emporio")
        await interaction.response.send_message(embed=embed)

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
        prezzo="Prezzo in $",
        descrizione="Descrizione breve",
        ruolo_richiesto="Ruolo Discord richiesto per acquistare (lascia vuoto = tutti)"
    )
    async def crea_item(
        interaction: discord.Interaction,
        nome: str,
        prezzo: int,
        descrizione: str,
        ruolo_richiesto: discord.Role = None
    ):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return
        if prezzo <= 0:
            await interaction.response.send_message("❌ Il prezzo deve essere positivo.", ephemeral=True)
            return

        role_id = ruolo_richiesto.id if ruolo_richiesto else None
        await database.upsert_shop_item(nome, prezzo, descrizione, role_id)

        embed = discord.Embed(title="✅ 𝐈𝐭𝐞𝐦 𝐂𝐫𝐞𝐚𝐭𝐨/𝐀𝐠𝐠𝐢𝐨𝐫𝐧𝐚𝐭𝐨", color=discord.Color.green(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="📦 Nome",        value=nome,           inline=True)
        embed.add_field(name="💵 Prezzo",      value=f"${prezzo:,}", inline=True)
        embed.add_field(name="📝 Descrizione", value=descrizione,    inline=False)
        if role_id:
            embed.add_field(name="🔑 Ruolo Richiesto", value=f"<@&{role_id}>", inline=True)
        else:
            embed.add_field(name="🔑 Ruolo Richiesto", value="Nessuno (tutti possono acquistare)", inline=True)
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
