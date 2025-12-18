import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import math

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLE_ID = 1414738761207517214
MARKET_ROLE_ID = 1415242295153918123
ITEMS_PER_PAGE = 5

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, "send"):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass

async def update_inventory(user_id: str, item_name: str, quantity: int, mode: str = 'add'):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if mode == 'add':
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + excluded.quantity",
                (user_id, item_name, quantity)
            )
        elif mode == 'remove':
            await db.execute(
                "UPDATE inventory SET quantity = MAX(0, quantity - ?) WHERE user_id = ? AND item_name = ?",
                (quantity, user_id, item_name)
            )
            await db.execute(
                "DELETE FROM inventory WHERE user_id = ? AND item_name = ? AND quantity <= 0",
                (user_id, item_name)
            )
        
        await db.commit()

async def fuzzy_search_item(search_term: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT name, required_role_id FROM items") as cursor:
            all_items = await cursor.fetchall()
    
    if not all_items:
        return None
    
    search_lower = search_term.lower()
    matches = []
    
    for item_name, role_id in all_items:
        if search_lower in item_name.lower():
            matches.append((item_name, role_id))
    
    if len(matches) == 0:
        return None
    elif len(matches) == 1:
        return {"exact_match": True, "item_name": matches[0][0], "required_role_id": matches[0][1]}
    else:
        return {"exact_match": False, "matches": matches}

class ItemShopPaginationView(discord.ui.View):
    def __init__(self, bot: commands.Bot, items: list, guild: discord.Guild):
        super().__init__(timeout=180)
        self.bot = bot
        self.items = items
        self.guild = guild
        self.current_page = 0
        self.total_pages = math.ceil(len(items) / ITEMS_PER_PAGE)
        
        self.update_buttons()
    
    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
    
    def get_embed(self):
        start_idx = self.current_page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_items = self.items[start_idx:end_idx]
        
        embed = discord.Embed(
            title="🛒 Shop - Lista degli Item",
            color=discord.Color.blue()
        )
        
        description_lines = []
        for name, required_role_id in page_items:
            role = self.guild.get_role(int(required_role_id))
            role_mention = role.mention if role else f"<@&{required_role_id}>"
            
            description_lines.append(f"• **{name}**")
            description_lines.append(f"🔑 Ruolo richiesto: {role_mention}\n")
        
        embed.description = "\n".join(description_lines) if description_lines else "Nessun item disponibile"
        embed.set_footer(text=f"Pagina {self.current_page + 1} di {self.total_pages}")
        
        return embed
    
    @discord.ui.button(label="◀️ Pagina", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Pagina ▶️", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

class BackpackPaginationView(discord.ui.View):
    def __init__(self, items: list, target_user: discord.Member, requester: discord.Member):
        super().__init__(timeout=180)
        self.items = items
        self.target_user = target_user
        self.requester = requester
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = math.ceil(len(items) / self.items_per_page) if items else 1
        
        self.update_buttons()
    
    def update_buttons(self):
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
    
    def get_embed(self):
        embed = discord.Embed(
            title=f"🎒 Zaino",
            color=discord.Color.blue()
        )
        
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.items[start_idx:end_idx]
        
        if page_items:
            for item_name, quantity in page_items:
                embed.add_field(
                    name=f"{item_name}",
                    value=f"Quantità: **{quantity}**",
                    inline=False
                )
        else:
            embed.description = "Lo zaino è vuoto!"
        
        embed.set_footer(text=f"👤 Pagina {self.current_page + 1} di {self.total_pages} | Richiesto da {self.requester.display_name}")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message("❌ Non puoi usare questi bottoni!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="◀️ Pagina", style=discord.ButtonStyle.primary, custom_id="prev_page_backpack")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="Pagina ▶️", style=discord.ButtonStyle.primary, custom_id="next_page_backpack")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

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

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (str(self.target_user.id),)) as cursor:
                user_data = await cursor.fetchone()

        if not user_data or user_data[0] == 0:
            await interaction.followup.send(f"❌ {self.target_user.mention} non ha uno zaino in cui mettere l'oggetto!", ephemeral=True)
            return
            
        await update_inventory(str(self.target_user.id), self.item_name, quantity, mode='add')
        
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
        
        # LOG CON EMBED
        log_embed = discord.Embed(
            title="➕ LOG ITEM DATO",
            color=discord.Color.green()
        )
        log_embed.add_field(name="👮 Staff", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Ricevente", value=self.target_user.mention, inline=True)
        log_embed.add_field(name="📦 Item", value=self.item_name, inline=False)
        log_embed.add_field(name="🔢 Quantità", value=str(quantity), inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)

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

class FuzzyItemSelect(discord.ui.Select):
    def __init__(self, matches: list, callback_function):
        self.callback_function = callback_function
        
        options = [
            discord.SelectOption(label=name, description=f"Ruolo: {role_id}", value=name) 
            for name, role_id in matches[:25]
        ]
        
        super().__init__(
            placeholder="Seleziona l'item corretto...", 
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        selected_item = self.values[0]
        await self.callback_function(interaction, selected_item)

def setup_inventory_commands(bot: commands.Bot):
    
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

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT name FROM items") as cursor:
                item_names = [row[0] for row in await cursor.fetchall()]

        if not item_names:
            await interaction.followup.send("❌ Nessun item disponibile nello shop. Creane uno con `/crea-item`.", ephemeral=True)
            return
            
        view = discord.ui.View(timeout=300)
        view.add_item(ItemSelect(bot, utente, item_names))

        await interaction.followup.send(
            f"🎁 Seleziona l'item da aggiungere allo zaino di **{utente.mention}**:",
            view=view,
            ephemeral=True
        )

    # CONTINUA... (per limiti di caratteri suddivido in due parti)
    # PARTE 2 DI commands_inventory.py - Aggiungi questi comandi dopo give-item

    @bot.tree.command(name="take-item", description="[STAFF] Rimuovi un item dall'inventario di un utente.")
    @app_commands.describe(
        utente="L'utente a cui togliere l'item",
        item="Il nome dell'item da rimuovere (anche parziale)",
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
        
        search_result = await fuzzy_search_item(item)
        
        if search_result is None:
            await interaction.followup.send(f"❌ Nessun item trovato con il nome '{item}'!", ephemeral=True)
            return
        
        if not search_result["exact_match"]:
            matches = search_result["matches"]
            
            async def handle_selection(select_interaction: discord.Interaction, selected_item: str):
                await select_interaction.response.defer(ephemeral=True)
                
                user_id = str(utente.id)
                await update_inventory(user_id, selected_item, quantita, mode='remove')
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute(
                        "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", 
                        (user_id, selected_item)
                    ) as cursor:
                        current_quantity_data = await cursor.fetchone()
                
                current_quantity = current_quantity_data[0] if current_quantity_data else 0
                
                await select_interaction.followup.send(
                    f"✅ Rimosse **{quantita}**x **{selected_item}** dallo zaino di {utente.mention}.\n"
                    f"(Quantità residua: **{current_quantity}**)",
                    ephemeral=True
                )

                try:
                    if current_quantity == 0:
                        msg = f"💀 Lo staff ({interaction.user.mention}) ha rimosso tutte le tue **{selected_item}** dallo zaino!"
                    else:
                        msg = f"⚠️ Lo staff ({interaction.user.mention}) ha rimosso **{quantita}**x **{selected_item}** dal tuo zaino. Quantità residua: **{current_quantity}**."
                    await utente.send(msg)
                except:
                    pass

                log_embed = discord.Embed(title="➖ LOG ITEM RIMOSSO", color=discord.Color.red())
                log_embed.add_field(name="👮 Staff", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="👤 Utente", value=utente.mention, inline=True)
                log_embed.add_field(name="📦 Item", value=selected_item, inline=False)
                log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=True)
                log_embed.add_field(name="📊 Residuo", value=str(current_quantity), inline=True)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            
            view = discord.ui.View(timeout=300)
            view.add_item(FuzzyItemSelect(matches, handle_selection))
            await interaction.followup.send(
                f"🔍 Trovati **{len(matches)}** item che contengono '{item}'. Seleziona quello corretto:",
                view=view,
                ephemeral=True
            )
            return
        
        item_name = search_result["item_name"]
        user_id = str(utente.id)
        
        await update_inventory(user_id, item_name, quantita, mode='remove')
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", 
                (user_id, item_name)
            ) as cursor:
                current_quantity_data = await cursor.fetchone()
        
        current_quantity = current_quantity_data[0] if current_quantity_data else 0
        
        await interaction.followup.send(
            f"✅ Rimosse **{quantita}**x **{item_name}** dallo zaino di {utente.mention}.\n"
            f"(Quantità residua: **{current_quantity}**)",
            ephemeral=True
        )

        try:
            if current_quantity == 0:
                msg = f"💀 Lo staff ({interaction.user.mention}) ha rimosso tutte le tue **{item_name}** dallo zaino!"
            else:
                msg = f"⚠️ Lo staff ({interaction.user.mention}) ha rimosso **{quantita}**x **{item_name}** dal tuo zaino. Quantità residua: **{current_quantity}**."
            await utente.send(msg)
        except:
            pass

        log_embed = discord.Embed(title="➖ LOG ITEM RIMOSSO", color=discord.Color.red())
        log_embed.add_field(name="👮 Staff", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Utente", value=utente.mention, inline=True)
        log_embed.add_field(name="📦 Item", value=item_name, inline=False)
        log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=True)
        log_embed.add_field(name="📊 Residuo", value=str(current_quantity), inline=True)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

    @bot.tree.command(name="crea-item", description="[STAFF] Crea un nuovo item")
    @app_commands.describe(nome_item="Nome dell'item", ruolo_richiesto="Ruolo richiesto per acquistare l'item")
    async def nuovoitem(interaction: discord.Interaction, nome_item: str, ruolo_richiesto: discord.Role):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            try:
                await db.execute("INSERT INTO items (name, required_role_id) VALUES (?, ?)", (nome_item, str(ruolo_richiesto.id)))
                await db.commit()
                await interaction.response.send_message(f"✅ Item **{nome_item}** creato con successo!\n🔒 Ruolo richiesto: {ruolo_richiesto.mention}", ephemeral=True)
                
                log_embed = discord.Embed(title="➕ LOG ITEM CREATO", color=discord.Color.green())
                log_embed.add_field(name="👮 Creato da", value=interaction.user.mention, inline=False)
                log_embed.add_field(name="📦 Nome Item", value=nome_item, inline=True)
                log_embed.add_field(name="🔒 Ruolo Richiesto", value=ruolo_richiesto.mention, inline=True)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            except aiosqlite.IntegrityError:
                await interaction.response.send_message(f"❌ L'item **{nome_item}** esiste già!", ephemeral=True)

    @bot.tree.command(name="eliminaitem", description="[STAFF] Elimina un item")
    @app_commands.describe(nome="Nome dell'item da eliminare")
    async def eliminaitem(interaction: discord.Interaction, nome: str):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        
        search_result = await fuzzy_search_item(nome)
        
        if search_result is None:
            await interaction.followup.send(f"❌ Nessun item trovato con il nome '{nome}'!", ephemeral=True)
            return
        
        if not search_result["exact_match"]:
            matches = search_result["matches"]
            
            async def handle_deletion(select_interaction: discord.Interaction, selected_item: str):
                await select_interaction.response.defer(ephemeral=True)
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    await db.execute("DELETE FROM items WHERE name = ?", (selected_item,))
                    await db.commit()
                
                await select_interaction.followup.send(f"✅ Item **{selected_item}** eliminato!", ephemeral=True)
                
                log_embed = discord.Embed(title="➖ LOG ITEM ELIMINATO", color=discord.Color.red())
                log_embed.add_field(name="👮 Eliminato da", value=interaction.user.mention, inline=False)
                log_embed.add_field(name="📦 Item Eliminato", value=selected_item, inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            
            view = discord.ui.View(timeout=300)
            view.add_item(FuzzyItemSelect(matches, handle_deletion))
            await interaction.followup.send(f"🔍 Trovati **{len(matches)}** item che contengono '{nome}'. Seleziona quello da eliminare:", view=view, ephemeral=True)
            return
        
        item_name = search_result["item_name"]
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            cursor = await db.execute("DELETE FROM items WHERE name = ?", (item_name,))
            await db.commit()

            if cursor.rowcount > 0:
                await interaction.followup.send(f"✅ Item **{item_name}** eliminato!", ephemeral=True)
                
                log_embed = discord.Embed(title="➖ LOG ITEM ELIMINATO", color=discord.Color.red())
                log_embed.add_field(name="👮 Eliminato da", value=interaction.user.mention, inline=False)
                log_embed.add_field(name="📦 Item Eliminato", value=item_name, inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            else:
                await interaction.followup.send(f"❌ L'item **{item_name}** non esiste!", ephemeral=True)
    
    @bot.tree.command(name="itemshop", description="Visualizza tutti gli item disponibili")
    async def itemshop(interaction: discord.Interaction):
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT name, required_role_id FROM items") as cursor:
                items = await cursor.fetchall()

        if not items:
            await interaction.response.send_message("❌ Non ci sono item nello shop!", ephemeral=True)
            return

        view = ItemShopPaginationView(bot, items, interaction.guild)
        embed = view.get_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        

    
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
                await db.execute("INSERT INTO users (user_id, cash, bank, has_backpack) VALUES (?, 0, 0, ?)", (str(utente.id), 1))
            else:
                await db.execute("UPDATE users SET has_backpack = 1 WHERE user_id = ?", (str(utente.id),))

            await db.commit()

        await interaction.response.send_message(f"✅ Zaino venduto a {utente.mention}!", ephemeral=True)

        try:
            await utente.send("🎒 Ti è stato venduto uno zaino dal Market! Ora puoi vedere e usare il tuo zaino con `/invzaino`.")
        except:
            pass

        log_embed = discord.Embed(title="🎒 LOG ZAINO VENDUTO", color=discord.Color.green())
        log_embed.add_field(name="👮 Venditore", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Acquirente", value=utente.mention, inline=True)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
    
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
        
        log_embed = discord.Embed(title="🗑️ LOG ZAINO RIMOSSO", color=discord.Color.red())
        log_embed.add_field(name="👮 Rimosso da", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Utente", value=utente.mention, inline=True)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

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

        view = BackpackPaginationView(items, target_user, interaction.user)
        embed = view.get_embed()
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        if utente and utente.id != interaction.user.id:
            try:
                await utente.send(f"👀 ATTENZIONE‼️ {interaction.user.mention} ha appena guardato il tuo zaino. STAI ATTENTO‼️🚨")
            except:
                pass
            
            log_embed = discord.Embed(title="👁️ LOG ZAINO CONTROLLATO", color=discord.Color.gold())
            log_embed.add_field(name="👮 Controllato da", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="👤 Zaino di", value=utente.mention, inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
        
    # CONTINUA NEL PROSSIMO MESSAGGIO CON item-sell, utilizza-item e dai-item
    # PARTE 3 DI commands_inventory.py - ULTIMI COMANDI (item-sell, utilizza-item, dai-item)
# Aggiungi questi comandi dopo invzaino

    @bot.tree.command(name="item-sell", description="Acquista un item dall'Item Shop.")
    @app_commands.describe(
        nome_item="Nome dell'item da acquistare (anche parziale)",
        quantita="Quantità da acquistare (default: 1)"
    )
    async def item_sell(interaction: discord.Interaction, nome_item: str, quantita: int = 1):
        user_id = str(interaction.user.id)
        member = interaction.user
        
        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        search_result = await fuzzy_search_item(nome_item)
        
        if search_result is None:
            await interaction.followup.send(f"❌ Nessun item trovato con il nome '{nome_item}'!", ephemeral=True)
            return
        
        if not search_result["exact_match"]:
            matches = search_result["matches"]
            
            async def handle_purchase(select_interaction: discord.Interaction, selected_item: str):
                await select_interaction.response.defer(ephemeral=True)
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT required_role_id FROM items WHERE name = ?", (selected_item,)) as cursor:
                        item_data = await cursor.fetchone()
                
                if not item_data:
                    await select_interaction.followup.send(f"❌ Errore nel recupero dell'item!", ephemeral=True)
                    return
                
                required_role_id = int(item_data[0])
                
                if not has_role(select_interaction, required_role_id):
                    await select_interaction.followup.send(f"❌ Non hai il ruolo richiesto per acquistare **{selected_item}**! (Richiesto: <@&{required_role_id}>)", ephemeral=True)
                    return
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (user_id,)) as cursor:
                        user_backpack = await cursor.fetchone()
                        
                if not user_backpack or user_backpack[0] == 0:
                    await select_interaction.followup.send("❌ Non puoi acquistare item senza uno zaino! Comprane uno dal Market.", ephemeral=True)
                    return
                
                await update_inventory(user_id, selected_item, quantita, mode='add')
                
                await select_interaction.followup.send(f"✅ Hai acquistato **{quantita}**x **{selected_item}**! Controlla il tuo zaino con `/invzaino`.", ephemeral=True)
                
                log_embed = discord.Embed(title="🛒 LOG ITEM ACQUISTATO", color=discord.Color.green())
                log_embed.add_field(name="👤 Acquirente", value=member.mention, inline=True)
                log_embed.add_field(name="📦 Item", value=selected_item, inline=True)
                log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=False)
                log_embed.add_field(name="🔒 Ruolo", value=f"<@&{required_role_id}>", inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            
            view = discord.ui.View(timeout=300)
            view.add_item(FuzzyItemSelect(matches, handle_purchase))
            await interaction.followup.send(f"🔍 Trovati **{len(matches)}** item che contengono '{nome_item}'. Seleziona quello da acquistare:", view=view, ephemeral=True)
            return
        
        item_name = search_result["item_name"]
        required_role_id = int(search_result["required_role_id"])
        
        if not has_role(interaction, required_role_id):
            await interaction.followup.send(f"❌ Non hai il ruolo richiesto per acquistare **{item_name}**! (Richiesto: <@&{required_role_id}>)", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (user_id,)) as cursor:
                user_backpack = await cursor.fetchone()
                
        if not user_backpack or user_backpack[0] == 0:
            await interaction.followup.send("❌ Non puoi acquistare item senza uno zaino! Comprane uno dal Market.", ephemeral=True)
            return

        await update_inventory(user_id, item_name, quantita, mode='add')
        
        await interaction.followup.send(f"✅ Hai acquistato **{quantita}**x **{item_name}**! Controlla il tuo zaino con `/invzaino`.", ephemeral=True)
        
        log_embed = discord.Embed(title="🛒 LOG ITEM ACQUISTATO", color=discord.Color.green())
        log_embed.add_field(name="👤 Acquirente", value=member.mention, inline=True)
        log_embed.add_field(name="📦 Item", value=item_name, inline=True)
        log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=False)
        log_embed.add_field(name="🔒 Ruolo", value=f"<@&{required_role_id}>", inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

    @bot.tree.command(name="utilizza-item", description="Rimuovi item dal tuo zaino per 'utilizzarli'.")
    @app_commands.describe(nome_item="Nome dell'item da utilizzare (anche parziale)", quantita="Quantità da utilizzare (default: 1)")
    async def utilizza_item(interaction: discord.Interaction, nome_item: str, quantita: int = 1):
        user_id = str(interaction.user.id)
        
        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità da utilizzare deve essere almeno 1.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT item_name FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
                user_items = [row[0] for row in await cursor.fetchall()]
        
        if not user_items:
            await interaction.followup.send("❌ Il tuo zaino è vuoto!", ephemeral=True)
            return
        
        nome_item_lower = nome_item.lower()
        matches = [item for item in user_items if nome_item_lower in item.lower()]
        
        if len(matches) == 0:
            await interaction.followup.send(f"❌ Non hai nessun item che contiene '{nome_item}' nel tuo zaino!", ephemeral=True)
            return
        
        if len(matches) > 1:
            async def handle_use(select_interaction: discord.Interaction, selected_item: str):
                await select_interaction.response.defer(ephemeral=True)
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, selected_item)) as cursor:
                        current_quantity_data = await cursor.fetchone()

                if not current_quantity_data or current_quantity_data[0] < quantita:
                    available = current_quantity_data[0] if current_quantity_data else 0
                    await select_interaction.followup.send(f"❌ Non hai abbastanza **{selected_item}**! (Disponibile: **{available}**)", ephemeral=True)
                    return
                
                await update_inventory(user_id, selected_item, quantita, mode='remove')
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, selected_item)) as cursor:
                        remaining_quantity_data = await cursor.fetchone()
                        remaining = remaining_quantity_data[0] if remaining_quantity_data else 0
                
                if remaining == 0:
                    msg = f"✅ Hai utilizzato **{quantita}**x **{selected_item}**. L'item è stato rimosso completamente dal tuo zaino."
                else:
                    msg = f"✅ Hai utilizzato **{quantita}**x **{selected_item}**. Quantità residua: **{remaining}**."
                    
                await select_interaction.followup.send(msg, ephemeral=True)
                
                log_embed = discord.Embed(title="🧪 LOG ITEM UTILIZZATO", color=discord.Color.purple())
                log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=False)
                log_embed.add_field(name="📦 Item", value=selected_item, inline=True)
                log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=True)
                log_embed.add_field(name="📊 Residuo", value=str(remaining), inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            
            matches_with_role = [(item, "N/A") for item in matches]
            view = discord.ui.View(timeout=300)
            view.add_item(FuzzyItemSelect(matches_with_role, handle_use))
            await interaction.followup.send(f"🔍 Trovati **{len(matches)}** item che contengono '{nome_item}'. Seleziona quello da utilizzare:", view=view, ephemeral=True)
            return
        
        selected_item = matches[0]

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, selected_item)) as cursor:
                current_quantity_data = await cursor.fetchone()

            if not current_quantity_data or current_quantity_data[0] < quantita:
                available = current_quantity_data[0] if current_quantity_data else 0
                await interaction.followup.send(f"❌ Non hai abbastanza **{selected_item}**! (Disponibile: **{available}**)", ephemeral=True)
                return
            
            await update_inventory(user_id, selected_item, quantita, mode='remove')
            
            async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, selected_item)) as cursor:
                remaining_quantity_data = await cursor.fetchone()
                remaining = remaining_quantity_data[0] if remaining_quantity_data else 0
        
        if remaining == 0:
            msg = f"✅ Hai utilizzato **{quantita}**x **{selected_item}**. L'item è stato rimosso completamente dal tuo zaino."
        else:
            msg = f"✅ Hai utilizzato **{quantita}**x **{selected_item}**. Quantità residua: **{remaining}**."
            
        await interaction.followup.send(msg, ephemeral=True)
        
        log_embed = discord.Embed(title="🧪 LOG ITEM UTILIZZATO", color=discord.Color.purple())
        log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=False)
        log_embed.add_field(name="📦 Item", value=selected_item, inline=True)
        log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=True)
        log_embed.add_field(name="📊 Residuo", value=str(remaining), inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

    @bot.tree.command(name="dai-item", description="Passa un item dal tuo zaino a un altro utente.")
    @app_commands.describe(utente="L'utente a cui dare l'item", nome_item="Nome dell'item da passare (anche parziale)", quantita="Quantità da trasferire (default: 1)")
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
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (sender_id,)) as cursor:
                sender_backpack = await cursor.fetchone()
                
        if not sender_backpack or sender_backpack[0] == 0:
            await interaction.followup.send("❌ Non puoi dare item se non hai uno zaino.", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT item_name FROM inventory WHERE user_id = ?", (sender_id,)) as cursor:
                user_items = [row[0] for row in await cursor.fetchall()]
        
        if not user_items:
            await interaction.followup.send("❌ Il tuo zaino è vuoto!", ephemeral=True)
            return
        
        nome_item_lower = nome_item.lower()
        matches = [item for item in user_items if nome_item_lower in item.lower()]
        
        if len(matches) == 0:
            await interaction.followup.send(f"❌ Non hai nessun item che contiene '{nome_item}' nel tuo zaino!", ephemeral=True)
            return
        
        if len(matches) > 1:
            async def handle_transfer(select_interaction: discord.Interaction, selected_item: str):
                await select_interaction.response.defer(ephemeral=True)
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (sender_id, selected_item)) as cursor:
                        sender_item_data = await cursor.fetchone()
                
                if not sender_item_data or sender_item_data[0] < quantita:
                    available = sender_item_data[0] if sender_item_data else 0
                    await select_interaction.followup.send(f"❌ Non hai abbastanza **{selected_item}** da dare! (Disponibile: **{available}**)", ephemeral=True)
                    return

                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (receiver_id,)) as cursor:
                        receiver_backpack = await cursor.fetchone()
                        
                if not receiver_backpack or receiver_backpack[0] == 0:
                    await select_interaction.followup.send(f"❌ {utente.mention} non ha uno zaino in cui ricevere l'item!", ephemeral=True)
                    return
                
                await update_inventory(sender_id, selected_item, quantita, mode='remove')
                await update_inventory(receiver_id, selected_item, quantita, mode='add')
                
                try:
                    embed = discord.Embed(title="🎁 Oggetto Ricevuto!", description=f"Hai ricevuto **{quantita}**x **{selected_item}**.", color=discord.Color.green())
                    embed.add_field(name="Donatore", value=interaction.user.mention, inline=False)
                    embed.set_footer(text="Controlla il tuo zaino con /invzaino.")
                    await utente.send(embed=embed)
                except:
                    pass
                    
                await select_interaction.followup.send(f"✅ Hai dato **{quantita}**x **{selected_item}** a {utente.mention} con successo!", ephemeral=True)

                log_embed = discord.Embed(title="➡️ LOG ITEM TRASFERITO", color=discord.Color.blue())
                log_embed.add_field(name="👤 Da", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="👤 A", value=utente.mention, inline=True)
                log_embed.add_field(name="📦 Item", value=selected_item, inline=False)
                log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            
            matches_with_role = [(item, "N/A") for item in matches]
            view = discord.ui.View(timeout=300)
            view.add_item(FuzzyItemSelect(matches_with_role, handle_transfer))
            await interaction.followup.send(f"🔍 Trovati **{len(matches)}** item che contengono '{nome_item}'. Seleziona quello da trasferire:", view=view, ephemeral=True)
            return
        
        selected_item = matches[0]

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (sender_id, selected_item)) as cursor:
                sender_item_data = await cursor.fetchone()
        
        if not sender_item_data or sender_item_data[0] < quantita:
            available = sender_item_data[0] if sender_item_data else 0
            await interaction.followup.send(f"❌ Non hai abbastanza **{selected_item}** da dare! (Disponibile: **{available}**)", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT has_backpack FROM users WHERE user_id = ?", (receiver_id,)) as cursor:
                receiver_backpack = await cursor.fetchone()
                
        if not receiver_backpack or receiver_backpack[0] == 0:
            await interaction.followup.send(f"❌ {utente.mention} non ha uno zaino in cui ricevere l'item!", ephemeral=True)
            return
        
        await update_inventory(sender_id, selected_item, quantita, mode='remove')
        await update_inventory(receiver_id, selected_item, quantita, mode='add')
        
        try:
            embed = discord.Embed(title="🎁 Oggetto Ricevuto!", description=f"Hai ricevuto **{quantita}**x **{selected_item}**.", color=discord.Color.green())
            embed.add_field(name="Donatore", value=interaction.user.mention, inline=False)
            embed.set_footer(text="Controlla il tuo zaino con /invzaino.")
            await utente.send(embed=embed)
        except:
            pass
            
        await interaction.followup.send(f"✅ Hai dato **{quantita}**x **{selected_item}** a {utente.mention} con successo!", ephemeral=True)

        log_embed = discord.Embed(title="➡️ LOG ITEM TRASFERITO", color=discord.Color.blue())
        log_embed.add_field(name="👤 Da", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 A", value=utente.mention, inline=True)
        log_embed.add_field(name="📦 Item", value=selected_item, inline=False)
        log_embed.add_field(name="🔢 Quantità", value=str(quantita), inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
