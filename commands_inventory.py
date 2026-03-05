import discord
from discord import app_commands
import database
import aiosqlite
from datetime import datetime

LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLES    = [1414738761207517214, 1414735564632231988]

DATABASE_NAME  = "rdr2_bot.db"

def has_staff(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in STAFF_ROLES for r in interaction.user.roles)

async def init_shop_table():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                item_name TEXT PRIMARY KEY,
                price INTEGER,
                description TEXT,
                emoji TEXT DEFAULT '📦'
            )
        """)
        await db.commit()

async def get_shop_items() -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM shop_items ORDER BY price ASC") as cursor:
            return [dict(r) for r in await cursor.fetchall()]

async def get_shop_item(name: str) -> dict | None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM shop_items WHERE item_name = ?", (name,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def add_shop_item(name: str, price: int, description: str, emoji: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO shop_items (item_name, price, description, emoji)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(item_name) DO UPDATE SET price=?, description=?, emoji=?
        """, (name, price, description, emoji, price, description, emoji))
        await db.commit()

async def remove_shop_item(name: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM shop_items WHERE item_name = ?", (name,))
        await db.commit()

def setup_inventory_commands(bot):

    @bot.tree.command(name="itemshop", description="Visualizza il negozio degli item disponibili")
    async def itemshop(interaction: discord.Interaction):
        items = await get_shop_items()

        embed = discord.Embed(
            title="🏪 Emporio del Far West",
            description="Benvenuto, cowboy! Scegli cosa acquistare.",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url="https://i.imgur.com/placeholder.gif")

        if not items:
            embed.description = "*L'emporio è vuoto per ora...*"
        else:
            for item in items:
                embed.add_field(
                    name=f"{item['emoji']} {item['item_name']}",
                    value=f"💵 **${item['price']:,}**\n_{item['description']}_",
                    inline=True
                )
        embed.set_footer(text="🤠 Red Dead Redemption II — Emporio | Usa /item-sell per acquistare")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="item-sell", description="Acquista uno o più item dall'emporio")
    @app_commands.describe(item="L'item da acquistare", quantita="Quantità")
    async def item_sell(interaction: discord.Interaction, item: str, quantita: int = 1):
        if quantita < 1:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True)
            return

        shop_item = await get_shop_item(item)
        if not shop_item:
            await interaction.response.send_message(
                "❌ Questo item non è disponibile nell'emporio.", ephemeral=True
            )
            return

        totale = shop_item["price"] * quantita
        user   = await database.get_user(str(interaction.user.id))

        if user["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Non hai abbastanza contanti!\n"
                f"Costo totale: **${totale:,}** — Tuoi contanti: **${user['cash']:,}**",
                ephemeral=True
            )
            return

        await database.update_balance(str(interaction.user.id), cash=user["cash"] - totale)
        await database.add_item(str(interaction.user.id), item, quantita)

        embed = discord.Embed(
            title="🛒 Acquisto Completato",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📦 Item",      value=item,          inline=True)
        embed.add_field(name="🔢 Quantità",  value=str(quantita), inline=True)
        embed.add_field(name="💵 Pagato",    value=f"${totale:,}", inline=True)
        embed.add_field(name="💰 Rimasto",   value=f"${user['cash'] - totale:,}", inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Emporio")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="crea-item", description="[Staff] Crea un nuovo item nell'emporio")
    @app_commands.describe(nome="Nome dell'item", prezzo="Prezzo in $", descrizione="Descrizione breve", emoji="Emoji dell'item")
    async def crea_item(interaction: discord.Interaction, nome: str, prezzo: int, descrizione: str, emoji: str = "📦"):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        await init_shop_table()
        await add_shop_item(nome, prezzo, descrizione, emoji)

        embed = discord.Embed(title="✅ Item Creato", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="📦 Nome",       value=nome,         inline=True)
        embed.add_field(name="💵 Prezzo",     value=f"${prezzo:,}", inline=True)
        embed.add_field(name="📝 Descrizione",value=descrizione,   inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="eliminaitem", description="[Staff] Elimina un item dall'emporio")
    @app_commands.describe(nome="Nome dell'item da eliminare")
    async def elimina_item(interaction: discord.Interaction, nome: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        await remove_shop_item(nome)
        await interaction.response.send_message(f"✅ Item **{nome}** rimosso dall'emporio.", ephemeral=True)

    @bot.tree.command(name="rimuovibisaccia", description="[Staff] Rimuovi la bisaccia di un giocatore")
    @app_commands.describe(giocatore="Il giocatore")
    async def rimuovi_bisaccia(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM inventory WHERE user_id = ?", (str(giocatore.id),))
            await db.commit()

        embed = discord.Embed(
            title="🗑️ Bisaccia Rimossa",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Giocatore",  value=giocatore.mention,       inline=True)
        embed.add_field(name="👮 Staff",      value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="utilizza-item", description="Utilizza un item dalla tua bisaccia")
    @app_commands.describe(item="L'item da utilizzare")
    async def utilizza_item(interaction: discord.Interaction, item: str):
        rimosso = await database.remove_item(str(interaction.user.id), item, 1)
        if not rimosso:
            await interaction.response.send_message(
                f"❌ Non hai **{item}** nella tua bisaccia.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="✅ Item Utilizzato",
            description=f"*{interaction.user.display_name} utilizza **{item}**.*",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)
