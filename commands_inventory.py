import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLE_ID = 1414738761207517214
MARKET_ROLE_ID = 1415242295153918123

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, "send"):
            await channel.send(message)
    except:
        pass

def setup_inventory_commands(bot: commands.Bot):
    
    @bot.tree.command(name="nuovoitem", description="[STAFF] Crea un nuovo item")
    @app_commands.describe(
        nome_item="Nome dell'item",
        ruolo_richiesto="Ruolo richiesto per acquistare l'item"
    )
    async def nuovoitem(interaction: discord.Interaction, nome_item: str, ruolo_richiesto: discord.Role):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            try:
                await db.execute(
                    "INSERT INTO items (name, required_role_id) VALUES (?, ?)",
                    (nome_item, str(ruolo_richiesto.id))
                )
                await db.commit()
                await interaction.response.send_message(
                    f"✅ Item **{nome_item}** creato con successo!\n🔒 Ruolo richiesto: {ruolo_richiesto.mention}",
                    ephemeral=True
                )
                await log_command(bot, LOG_CHANNEL_ID, f"➕ {interaction.user.mention} ha creato l'item {nome_item} (Ruolo: {ruolo_richiesto.mention})")
            except aiosqlite.IntegrityError:
                await interaction.response.send_message(f"❌ L'item **{nome_item}** esiste già!", ephemeral=True)
    
    @bot.tree.command(name="eliminaitem", description="[STAFF] Elimina un item")
    @app_commands.describe(nome="Nome dell'item da eliminare")
    async def eliminaitem(interaction: discord.Interaction, nome: str):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            cursor = await db.execute("DELETE FROM items WHERE name = ?", (nome,))
            await db.commit()

            if cursor.rowcount > 0:
                await interaction.response.send_message(f"✅ Item **{nome}** eliminato!", ephemeral=True)
                await log_command(bot, LOG_CHANNEL_ID, f"➖ {interaction.user.mention} ha eliminato l'item {nome}")
            else:
                await interaction.response.send_message(f"❌ L'item **{nome}** non esiste!", ephemeral=True)
    
    @bot.tree.command(name="itemshop", description="Visualizza tutti gli item disponibili")
    async def itemshop(interaction: discord.Interaction):
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT name, required_role_id FROM items") as cursor:
                items = await cursor.fetchall()

        if not items:
            await interaction.response.send_message("❌ Non ci sono item nello shop!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛒 ITEM SHOP",
            description="Ecco tutti gli item disponibili:",
            color=discord.Color.blue()
        )

        for name, required_role_id in items:
            embed.add_field(
                name=f"📦 {name}",
                value=f"Ruolo richiesto: <@&{required_role_id}>",
                inline=False
            )

        await interaction.response.send_message(embed=embed)
        await log_command(bot, LOG_CHANNEL_ID, f"🛒 {interaction.user.mention} ha visualizzato l'item shop")
    
    @bot.tree.command(name="vendizaino", description="[MARKET] Vendi uno zaino a un utente")
    @app_commands.describe(utente="L'utente a cui vendere lo zaino")
    async def vendizaino(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, MARKET_ROLE_ID):
            await interaction.response.send_message("❌ Solo il Market può usare questo comando!", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (str(utente.id),)) as cursor:
                user_data = await cursor.fetchone()

            if user_data and user_data[0] == 1:
                await interaction.response.send_message(f"❌ {utente.mention} ha già uno zaino!", ephemeral=True)
                return

            if user_data is None:
                await db.execute("INSERT INTO users (user_id, has_backpack) VALUES (?, ?)", (str(utente.id), 1))
            else:
                await db.execute("UPDATE users SET has_backpack = 1 WHERE user_id = ?", (str(utente.id),))

            await db.commit()

        await interaction.response.send_message(f"✅ Zaino venduto a {utente.mention}!", ephemeral=True)

        try:
            await utente.send("🎒 Ti è stato venduto uno zaino dal Market! Ora puoi vedere e usare il tuo zaino con `/invzaino`.")
        except:
            pass

        await log_command(bot, LOG_CHANNEL_ID, f"🎒 {interaction.user.mention} ha venduto uno zaino a {utente.mention}")
    
    @bot.tree.command(name="rimuovizaino", description="[STAFF] Rimuovi lo zaino da un utente")
    @app_commands.describe(utente="L'utente a cui rimuovere lo zaino")
    async def rimuovizaino(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (str(utente.id),)) as cursor:
                user_data = await cursor.fetchone()

            if not user_data or user_data[0] == 0:
                await interaction.response.send_message(f"❌ {utente.mention} non ha uno zaino!", ephemeral=True)
                return

            await db.execute("UPDATE users SET has_backpack = 0 WHERE user_id = ?", (str(utente.id),))
            await db.execute("DELETE FROM inventory WHERE user_id = ?", (str(utente.id),))
            await db.commit()

        await interaction.response.send_message(f"✅ Hai rimosso lo zaino di {utente.mention}!", ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"🗑️ {interaction.user.mention} ha rimosso lo zaino di {utente.mention}")

        try:
            await utente.send("⚠️ Ti è stato rimosso lo zaino da uno staff!")
        except:
            pass
    
    @bot.tree.command(name="invzaino", description="Visualizza lo zaino tuo o di un altro utente")
    @app_commands.describe(utente="L'utente di cui visualizzare lo zaino (opzionale)")
    async def invzaino(interaction: discord.Interaction, utente: discord.Member = None):
        target_user = utente if utente else interaction.user

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (str(target_user.id),)) as cursor:
                user_data = await cursor.fetchone()

            if not user_data or user_data[0] == 0:
                if target_user.id == interaction.user.id:
                    await interaction.response.send_message("❌ Non hai uno zaino! Compralo dal Market.", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ {target_user.mention} non ha uno zaino!", ephemeral=True)
                return

            async with db.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (str(target_user.id),)) as cursor:
                items = await cursor.fetchall()

        embed = discord.Embed(
            title=f"🎒 ZAINO DI {target_user.display_name}",
            color=discord.Color.dark_green()
        )

        if items:
            for item_name, quantity in items:
                embed.add_field(name=f"📦 {item_name}", value=f"Quantità: **{quantity}**", inline=True)
        else:
            embed.description = "Lo zaino è vuoto!"

        await interaction.response.send_message(embed=embed, ephemeral=True)

        if utente and utente.id != interaction.user.id:
            try:
                await utente.send(f"👀 ATTENZIONE‼️ {interaction.user.mention} ha appena guardato il tuo zaino. STAI ATTENTO‼️🚨")
            except:
                pass
            await log_command(bot, LOG_CHANNEL_ID, f"👁️ {interaction.user.mention} ha guardato lo zaino di {utente.mention}")
        else:
            await log_command(bot, LOG_CHANNEL_ID, f"🎒 {interaction.user.mention} ha aperto il proprio zaino")
