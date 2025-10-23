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

# ====================
# FUNZIONI DI INVENTARIO (Riutilizzabili)
# ====================

async def update_inventory(user_id: str, item_name: str, quantity: int, mode: str = 'add'):
    """
    Aggiorna l'inventario dell'utente.
    mode='add': Aggiunge la quantità.
    mode='set': Imposta la quantità. (Non usata qui, ma utile per futuri comandi)
    mode='remove': Rimuove la quantità.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if mode == 'add':
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + excluded.quantity",
                (user_id, item_name, quantity)
            )
        elif mode == 'remove':
            # Rimuove, assicurandosi che la quantità non sia inferiore a 0
            await db.execute(
                "UPDATE inventory SET quantity = MAX(0, quantity - ?) WHERE user_id = ? AND item_name = ?",
                (quantity, user_id, item_name)
            )
            # Elimina l'item se la quantità è 0
            await db.execute(
                "DELETE FROM inventory WHERE user_id = ? AND item_name = ? AND quantity <= 0",
                (user_id, item_name)
            )
        
        await db.commit()

# ====================
# CLASSI UI PER /give-item
# ====================

class ItemQuantityModal(discord.ui.Modal, title="Inserisci Quantità"):
    def __init__(self, bot: commands.Bot, target_user: discord.Member, item_name: str):
        super().__init__()
        self.bot = bot
        self.target_user = target_user
        self.item_name = item_name
        
        self.quantity_input = discord.ui.TextInput(
            label=f"Quantità di {item_name}", 
            placeholder="Solo numeri interi", 
            required=True
        )
        self.add_item(self.quantity_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            quantity = int(self.quantity_input.value)
            if quantity <= 0:
                await interaction.followup.send("❌ La quantità deve essere un numero intero positivo.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Quantità non valida. Inserisci solo numeri.", ephemeral=True)
            return

        # 1. Controllo Zaino (necessario per aggiungere item)
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (str(self.target_user.id),)) as cursor:
                user_data = await cursor.fetchone()

        if not user_data or user_data[0] == 0:
            await interaction.followup.send(f"❌ {self.target_user.mention} non ha uno zaino in cui mettere l'oggetto!", ephemeral=True)
            return
            
        # 2. Aggiorna Inventario
        await update_inventory(str(self.target_user.id), self.item_name, quantity, mode='add')
        
        # 3. Risposta e Log
        await interaction.followup.send(
            f"✅ Aggiunti **{quantity}**x **{self.item_name}** allo zaino di {self.target_user.mention}!",
            ephemeral=True
        )
        
        try:
            await self.target_user.send(
                f"🎁 Hai ricevuto **{quantity}**x **{self.item_name}** dallo staff ({interaction.user.mention})."
            )
        except:
            pass
        
        log_msg = f"➕ {interaction.user.mention} ha dato {quantity}x {self.item_name} a {self.target_user.mention}"
        await log_command(self.bot, LOG_CHANNEL_ID, log_msg)


class ItemSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, target_user: discord.Member, item_options: list):
        self.bot = bot
        self.target_user = target_user
        
        options = [
            discord.SelectOption(label=name, value=name) for name in item_options
        ]
        
        super().__init__(
            placeholder="Seleziona l'item da dare...", 
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_item = self.values[0]
        modal = ItemQuantityModal(self.bot, self.target_user, selected_item)
        await interaction.response.send_modal(modal)

# ====================
# FUNZIONE DI SETUP
# ====================

def setup_inventory_commands(bot: commands.Bot):
    
    # ====================
    # COMANDO: /give-item (Staff Interattivo)
    # ====================
    @bot.tree.command(name="give-item", description="[STAFF] Aggiungi un item all'inventario di un utente.")
    @app_commands.describe(utente="L'utente a cui dare l'item")
    async def give_item(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Solo lo staff può usare questo comando! (Richiesto: <@&{STAFF_ROLE_ID}>)", 
                ephemeral=True
            )
            return
        
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi dare item a un bot.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Carica gli item disponibili per il menu a tendina
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT name FROM items") as cursor:
                item_names = [row[0] for row in await cursor.fetchall()]

        if not item_names:
            await interaction.followup.send("❌ Nessun item disponibile nello shop. Creane uno con `/nuovoitem`.", ephemeral=True)
            return
            
        # Crea la view con il menu a tendina
        view = discord.ui.View(timeout=300)
        view.add_item(ItemSelect(bot, utente, item_names))

        await interaction.followup.send(
            f"🎁 Seleziona l'item da aggiungere allo zaino di **{utente.mention}**:",
            view=view,
            ephemeral=True
        )


    # ====================
    # COMANDO: /take-item (Staff Rapido)
    # ====================
    @bot.tree.command(name="take-item", description="[STAFF] Rimuovi un item dall'inventario di un utente.")
    @app_commands.describe(
        utente="L'utente a cui togliere l'item",
        item="Il nome esatto dell'item da rimuovere",
        quantita="La quantità da rimuovere"
    )
    async def take_item(interaction: discord.Interaction, utente: discord.Member, item: str, quantita: int):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Solo lo staff può usare questo comando! (Richiesto: <@&{STAFF_ROLE_ID}>)", 
                ephemeral=True
            )
            return
        
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi togliere item a un bot.", ephemeral=True)
            return
            
        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità deve essere maggiore di zero!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        
        user_id = str(utente.id)
        
        # 1. Controlla e aggiorna l'inventario (la funzione gestisce la rimozione)
        await update_inventory(user_id, item, quantita, mode='remove')
        
        # 2. Ottieni la quantità attuale (dopo la rimozione)
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", 
                (user_id, item)
            ) as cursor:
                current_quantity_data = await cursor.fetchone()
        
        # 3. Messaggi di risposta e Log
        current_quantity = current_quantity_data[0] if current_quantity_data else 0
        
        await interaction.followup.send(
            f"✅ Rimosse **{quantita}**x **{item}** dallo zaino di {utente.mention}.\n"
            f"(Quantità residua: **{current_quantity}**)",
            ephemeral=True
        )

        try:
            if current_quantity == 0:
                msg = f"💀 Lo staff ({interaction.user.mention}) ha rimosso tutte le tue **{item}** dallo zaino!"
            else:
                msg = f"⚠️ Lo staff ({interaction.user.mention}) ha rimosso **{quantita}**x **{item}** dal tuo zaino. Quantità residua: **{current_quantity}**."
            await utente.send(msg)
        except:
            pass

        log_msg = f"➖ {interaction.user.mention} ha tolto {quantita}x {item} a {utente.mention}"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)


    # ====================
    # COMANDI ESISTENTI
    # ====================
    
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

    # ====================
    # NUOVO COMANDO: /item-sell (Acquisto Item)
    # ====================
    @bot.tree.command(name="item-sell", description="Acquista un item dall'Item Shop.")
    @app_commands.describe(
        nome_item="Nome esatto dell'item da acquistare",
        quantita="Quantità da acquistare (default: 1)"
    )
    async def item_sell(interaction: discord.Interaction, nome_item: str, quantita: int = 1):
        user_id = str(interaction.user.id)
        member = interaction.user
        
        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            # 1. Controlla l'esistenza dell'item e il ruolo richiesto
            async with db.execute(
                "SELECT required_role_id FROM items WHERE name = ?", 
                (nome_item,)
            ) as cursor:
                item_data = await cursor.fetchone()

            if not item_data:
                await interaction.followup.send(f"❌ L'item **{nome_item}** non esiste nello shop!", ephemeral=True)
                return

            required_role_id = int(item_data[0])
            
            # 2. Controlla se l'utente ha il ruolo richiesto
            if not has_role(interaction, required_role_id):
                await interaction.followup.send(
                    f"❌ Non hai il ruolo richiesto per acquistare **{nome_item}**! (Richiesto: <@&{required_role_id}>)", 
                    ephemeral=True
                )
                return

            # 3. Controlla se l'utente ha uno zaino
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_backpack = await cursor.fetchone()
                
            if not user_backpack or user_backpack[0] == 0:
                await interaction.followup.send("❌ Non puoi acquistare item senza uno zaino! Comprane uno dal Market.", ephemeral=True)
                return

        # 4. Aggiungi l'item all'inventario (non c'è costo, solo requisito ruolo)
        await update_inventory(user_id, nome_item, quantita, mode='add')
        
        await interaction.followup.send(
            f"✅ Hai acquistato **{quantita}**x **{nome_item}**! Controlla il tuo zaino con `/invzaino`.",
            ephemeral=True
        )
        
        log_msg = f"🛒 {member.mention} ha acquistato {quantita}x {nome_item} (Ruolo: <@&{required_role_id}>)"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)

    # ====================
    # NUOVO COMANDO: /utilizza-item (Rimuovi Item dallo Zaino)
    # ====================
    @bot.tree.command(name="utilizza-item", description="Rimuovi item dal tuo zaino per 'utilizzarli'.")
    @app_commands.describe(
        nome_item="Nome esatto dell'item da utilizzare",
        quantita="Quantità da utilizzare (default: 1)"
    )
    async def utilizza_item(interaction: discord.Interaction, nome_item: str, quantita: int = 1):
        user_id = str(interaction.user.id)
        
        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità da utilizzare deve essere almeno 1.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            # 1. Controlla la quantità disponibile
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", 
                (user_id, nome_item)
            ) as cursor:
                current_quantity_data = await cursor.fetchone()

            if not current_quantity_data or current_quantity_data[0] < quantita:
                available = current_quantity_data[0] if current_quantity_data else 0
                await interaction.followup.send(
                    f"❌ Non hai abbastanza **{nome_item}**! (Disponibile: **{available}**)", 
                    ephemeral=True
                )
                return
            
            # 2. Rimuovi dall'inventario
            await update_inventory(user_id, nome_item, quantita, mode='remove')
            
            # 3. Ottieni la quantità residua dopo la rimozione
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", 
                (user_id, nome_item)
            ) as cursor:
                remaining_quantity_data = await cursor.fetchone()
                remaining = remaining_quantity_data[0] if remaining_quantity_data else 0
        
        # 4. Risposta e Log
        if remaining == 0:
            msg = f"✅ Hai utilizzato **{quantita}**x **{nome_item}**. L'item è stato rimosso completamente dal tuo zaino."
        else:
            msg = f"✅ Hai utilizzato **{quantita}**x **{nome_item}**. Quantità residua: **{remaining}**."
            
        await interaction.followup.send(msg, ephemeral=True)
        
        log_msg = f"🧪 {interaction.user.mention} ha utilizzato {quantita}x {nome_item}."
        await log_command(bot, LOG_CHANNEL_ID, log_msg)


    # ====================
    # NUOVO COMANDO: /dai-item (Trasferimento Item tra Utenti)
    # ====================
    @bot.tree.command(name="dai-item", description="Passa un item dal tuo zaino a un altro utente.")
    @app_commands.describe(
        utente="L'utente a cui dare l'item",
        nome_item="Nome esatto dell'item da passare",
        quantita="Quantità da trasferire (default: 1)"
    )
    async def dai_item(interaction: discord.Interaction, utente: discord.Member, nome_item: str, quantita: int = 1):
        sender_id = str(interaction.user.id)
        receiver_id = str(utente.id)
        
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi dare item a un bot.", ephemeral=True)
            return
            
        if utente.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi darti un item da solo! Usa `/utilizza-item` o `/invzaino`.", ephemeral=True)
            return
            
        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            # 1. Controlla lo zaino del mittente e la quantità
            async with db.execute(
                "SELECT has_backpack FROM users WHERE user_id = ?", 
                (sender_id,)
            ) as cursor:
                sender_backpack = await cursor.fetchone()
                
            if not sender_backpack or sender_backpack[0] == 0:
                await interaction.followup.send("❌ Non puoi dare item se non hai uno zaino.", ephemeral=True)
                return

            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", 
                (sender_id, nome_item)
            ) as cursor:
                sender_item_data = await cursor.fetchone()
            
            if not sender_item_data or sender_item_data[0] < quantita:
                available = sender_item_data[0] if sender_item_data else 0
                await interaction.followup.send(
                    f"❌ Non hai abbastanza **{nome_item}** da dare! (Disponibile: **{available}**)", 
                    ephemeral=True
                )
                return

            # 2. Controlla lo zaino del destinatario (DEVE averlo per riceverlo)
            async with db.execute(
                "SELECT has_backpack FROM users WHERE user_id = ?", 
                (receiver_id,)
            ) as cursor:
                receiver_backpack = await cursor.fetchone()
                
            if not receiver_backpack or receiver_backpack[0] == 0:
                await interaction.followup.send(
                    f"❌ {utente.mention} non ha uno zaino in cui ricevere l'item!", 
                    ephemeral=True
                )
                return
            
            # 3. Trasferimento: Rimuovi dal mittente
            await update_inventory(sender_id, nome_item, quantita, mode='remove')
            
            # 4. Trasferimento: Aggiungi al destinatario
            await update_inventory(receiver_id, nome_item, quantita, mode='add')
        
        # 5. Risposta e Log
        
        # Messaggio in DM al destinatario
        try:
            embed = discord.Embed(
                title="🎁 Oggetto Ricevuto!",
                description=f"Hai ricevuto **{quantita}**x **{nome_item}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="Donatore", value=interaction.user.mention, inline=False)
            embed.set_footer(text="Controlla il tuo zaino con /invzaino.")
            await utente.send(embed=embed)
        except:
            pass
            
        await interaction.followup.send(
            f"✅ Hai dato **{quantita}**x **{nome_item}** a {utente.mention} con successo!", 
            ephemeral=True
        )

        log_msg = f"➡️ {interaction.user.mention} ha dato {quantita}x {nome_item} a {utente.mention}"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)

