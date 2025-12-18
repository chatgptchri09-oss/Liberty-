import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850

# Configurazione depositi
DEPOSITS = {
    "Red Vipers": {
        "emoji": "🐍",
        "role_id": 1424383006151413881
    },
    "Grim Shadows": {
        "emoji": "🥷",
        "role_id": 1424383242194255944
    },
    "Iron Fangs": {
        "emoji": "🧲",
        "role_id": 1424383496104710196
    },
    "Families": {
        "emoji": "🈯️",
        "role_id": 1450899985662218461
    },
    "Ballas": {
        "emoji": "♈️",
        "role_id": 1450900306190794853
    },
    "LFD": {
        "emoji": "👮‍♂️",
        "role_id": 1415093546549248040
    },
    "Armeria": {
        "emoji": "🔫",
        "role_id": 1415092383250382858
    },
    "Import": {
        "emoji": "🚚",
        "role_id": 1424004700608401428
    },
    "Cartello": {
        "emoji": "💀",
        "role_id": 1415361876136820858
    },
    "Figli del Cartello": {
        "emoji": "🐲",
        "role_id": 1415868723339722762
    },
    "Ndrangheta": {
        "emoji": "♟️",
        "role_id": 1424384006505631784
    },
    "Gomorra": {
        "emoji": "🎱",
        "role_id": 1424384198889705472
    }
}

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass

async def get_user_inventory(user_id: str):
    """Recupera l'inventario dell'utente"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT item_name, quantity FROM inventory WHERE user_id = ? ORDER BY item_name",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def get_deposit_inventory(deposit_name: str):
    """Recupera l'inventario del deposito"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT item_name, quantity FROM deposit_inventory WHERE deposit_name = ? ORDER BY item_name",
            (deposit_name,)
        ) as cursor:
            return await cursor.fetchall()

async def move_item_to_deposit(user_id: str, deposit_name: str, item_name: str, quantity: int):
    """Sposta item dallo zaino al deposito"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
            (quantity, user_id, item_name)
        )
        await db.execute(
            "DELETE FROM inventory WHERE user_id = ? AND item_name = ? AND quantity <= 0",
            (user_id, item_name)
        )
        
        await db.execute(
            """INSERT INTO deposit_inventory (deposit_name, item_name, quantity) 
               VALUES (?, ?, ?) 
               ON CONFLICT(deposit_name, item_name) 
               DO UPDATE SET quantity = quantity + excluded.quantity""",
            (deposit_name, item_name, quantity)
        )
        
        await db.commit()

async def move_item_from_deposit(user_id: str, deposit_name: str, item_name: str, quantity: int):
    """Sposta item dal deposito allo zaino"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE deposit_inventory SET quantity = quantity - ? WHERE deposit_name = ? AND item_name = ?",
            (quantity, deposit_name, item_name)
        )
        await db.execute(
            "DELETE FROM deposit_inventory WHERE deposit_name = ? AND item_name = ? AND quantity <= 0",
            (deposit_name, item_name)
        )
        
        await db.execute(
            """INSERT INTO inventory (user_id, item_name, quantity) 
               VALUES (?, ?, ?) 
               ON CONFLICT(user_id, item_name) 
               DO UPDATE SET quantity = quantity + excluded.quantity""",
            (user_id, item_name, quantity)
        )
        
        await db.commit()


class ItemConfirmView(discord.ui.View):
    """View per confermare la selezione dell'item"""
    def __init__(self, bot: commands.Bot, user_id: int, deposit_name: str, matched_items: list, quantity: int, is_withdraw: bool = False):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.deposit_name = deposit_name
        self.quantity = quantity
        self.is_withdraw = is_withdraw
        self.selected_item = None
        
        # Crea un bottone per ogni item trovato (max 5)
        for item_name in matched_items[:5]:
            button = discord.ui.Button(label=item_name, style=discord.ButtonStyle.primary)
            button.callback = self.create_callback(item_name)
            self.add_item(button)
        
        # Aggiungi bottone annulla
        cancel_button = discord.ui.Button(label="❌ Annulla", style=discord.ButtonStyle.danger)
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
    
    def create_callback(self, item_name: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ Non puoi usare questo bottone!", ephemeral=True)
                return
            
            self.selected_item = item_name
            
            if self.is_withdraw:
                await self.process_withdraw(interaction)
            else:
                await self.process_deposit(interaction)
        
        return callback
    
    async def cancel_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Non puoi usare questo bottone!", ephemeral=True)
            return
        
        await interaction.response.edit_message(content="❌ Operazione annullata!", embed=None, view=None)
    
    async def process_deposit(self, interaction: discord.Interaction):
        try:
            await move_item_to_deposit(
                str(self.user_id),
                self.deposit_name,
                self.selected_item,
                self.quantity
            )
            
            emoji = DEPOSITS[self.deposit_name]["emoji"]
            
            public_embed = discord.Embed(
                title=f"{emoji} Deposito Effettuato",
                description=f"{interaction.user.mention} ha depositato degli item nel deposito **{self.deposit_name}**",
                color=discord.Color.green()
            )
            public_embed.add_field(name="📦 Item", value=self.selected_item, inline=True)
            public_embed.add_field(name="🔢 Quantità", value=str(self.quantity), inline=True)
            
            await interaction.channel.send(embed=public_embed)
            
            log_embed = discord.Embed(
                title="📥 LOG DEPOSITO ITEM",
                color=discord.Color.green()
            )
            log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
            log_embed.add_field(name="📦 Item", value=self.selected_item, inline=False)
            log_embed.add_field(name="🔢 Quantità", value=str(self.quantity), inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            
            await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
            
            await interaction.response.edit_message(
                content=f"✅ Hai depositato **{self.quantity}x {self.selected_item}** nel deposito **{self.deposit_name}**!",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ Errore: {str(e)}", embed=None, view=None)
    
    async def process_withdraw(self, interaction: discord.Interaction):
        try:
            await move_item_from_deposit(
                str(self.user_id),
                self.deposit_name,
                self.selected_item,
                self.quantity
            )
            
            emoji = DEPOSITS[self.deposit_name]["emoji"]
            
            public_embed = discord.Embed(
                title=f"{emoji} Prelievo Effettuato",
                description=f"{interaction.user.mention} ha prelevato degli item dal deposito **{self.deposit_name}**",
                color=discord.Color.orange()
            )
            public_embed.add_field(name="📦 Item", value=self.selected_item, inline=True)
            public_embed.add_field(name="🔢 Quantità", value=str(self.quantity), inline=True)
            
            await interaction.channel.send(embed=public_embed)
            
            log_embed = discord.Embed(
                title="📤 LOG PRELIEVO ITEM",
                color=discord.Color.orange()
            )
            log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
            log_embed.add_field(name="📦 Item", value=self.selected_item, inline=False)
            log_embed.add_field(name="🔢 Quantità", value=str(self.quantity), inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            
            await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
            
            await interaction.response.edit_message(
                content=f"✅ Hai prelevato **{self.quantity}x {self.selected_item}** dal deposito **{self.deposit_name}**!",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.edit_message(content=f"❌ Errore: {str(e)}", embed=None, view=None)


class DepositModal(discord.ui.Modal, title="Deposita Item"):
    """Modal per depositare item nel deposito"""
    
    item_name = discord.ui.TextInput(
        label="Nome Item (anche parziale)",
        placeholder="Scrivi il nome dell'item...",
        required=True,
        max_length=100
    )
    
    quantity = discord.ui.TextInput(
        label="Quantità",
        placeholder="Scrivi la quantità da depositare...",
        required=True,
        max_length=10
    )
    
    def __init__(self, bot: commands.Bot, deposit_name: str):
        super().__init__()
        self.bot = bot
        self.deposit_name = deposit_name
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            item_search = self.item_name.value.strip().lower()
            qty = int(self.quantity.value.strip())
            
            if qty <= 0:
                await interaction.response.send_message("❌ La quantità deve essere maggiore di 0!", ephemeral=True)
                return
            
            # Verifica che l'utente abbia lo zaino
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT has_backpack FROM users WHERE user_id = ?",
                    (str(interaction.user.id),)
                ) as cursor:
                    user_result = await cursor.fetchone()
            
            if not user_result or user_result[0] == 0:
                await interaction.response.send_message("❌ Non hai uno zaino!", ephemeral=True)
                return
            
            # Cerca item che contengono il testo cercato
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT item_name, quantity FROM inventory WHERE user_id = ?",
                    (str(interaction.user.id),)
                ) as cursor:
                    all_items = await cursor.fetchall()
            
            # Filtra item che contengono il testo cercato (case insensitive)
            matched_items = []
            exact_match = None
            
            for item_name, item_qty in all_items:
                if item_search == item_name.lower():
                    exact_match = (item_name, item_qty)
                    break
                elif item_search in item_name.lower():
                    matched_items.append((item_name, item_qty))
            
            # Se c'è un match esatto, usalo
            if exact_match:
                item_name, item_qty = exact_match
                
                if item_qty < qty:
                    await interaction.response.send_message(
                        f"❌ Non hai abbastanza **{item_name}**! (Possiedi: {item_qty})",
                        ephemeral=True
                    )
                    return
                
                # Deposita direttamente
                await move_item_to_deposit(
                    str(interaction.user.id),
                    self.deposit_name,
                    item_name,
                    qty
                )
                
                emoji = DEPOSITS[self.deposit_name]["emoji"]
                
                public_embed = discord.Embed(
                    title=f"{emoji} Deposito Effettuato",
                    description=f"{interaction.user.mention} ha depositato degli item nel deposito **{self.deposit_name}**",
                    color=discord.Color.green()
                )
                public_embed.add_field(name="📦 Item", value=item_name, inline=True)
                public_embed.add_field(name="🔢 Quantità", value=str(qty), inline=True)
                
                await interaction.channel.send(embed=public_embed)
                
                log_embed = discord.Embed(
                    title="📥 LOG DEPOSITO ITEM",
                    color=discord.Color.green()
                )
                log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
                log_embed.add_field(name="📦 Item", value=item_name, inline=False)
                log_embed.add_field(name="🔢 Quantità", value=str(qty), inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                
                await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
                
                await interaction.response.send_message(
                    f"✅ Hai depositato **{qty}x {item_name}** nel deposito **{self.deposit_name}**!",
                    ephemeral=True
                )
                return
            
            # Se non c'è match esatto ma ci sono match parziali
            if matched_items:
                # Verifica che tutti gli item abbiano quantità sufficiente
                valid_items = [(name, q) for name, q in matched_items if q >= qty]
                
                if not valid_items:
                    await interaction.response.send_message(
                        f"❌ Nessun item con **'{item_search}'** ha quantità sufficiente!",
                        ephemeral=True
                    )
                    return
                
                if len(valid_items) == 1:
                    # Solo un match, deposita direttamente
                    item_name, item_qty = valid_items[0]
                    
                    await move_item_to_deposit(
                        str(interaction.user.id),
                        self.deposit_name,
                        item_name,
                        qty
                    )
                    
                    emoji = DEPOSITS[self.deposit_name]["emoji"]
                    
                    public_embed = discord.Embed(
                        title=f"{emoji} Deposito Effettuato",
                        description=f"{interaction.user.mention} ha depositato degli item nel deposito **{self.deposit_name}**",
                        color=discord.Color.green()
                    )
                    public_embed.add_field(name="📦 Item", value=item_name, inline=True)
                    public_embed.add_field(name="🔢 Quantità", value=str(qty), inline=True)
                    
                    await interaction.channel.send(embed=public_embed)
                    
                    log_embed = discord.Embed(
                        title="📥 LOG DEPOSITO ITEM",
                        color=discord.Color.green()
                    )
                    log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
                    log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
                    log_embed.add_field(name="📦 Item", value=item_name, inline=False)
                    log_embed.add_field(name="🔢 Quantità", value=str(qty), inline=False)
                    log_embed.timestamp = discord.utils.utcnow()
                    
                    await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
                    
                    await interaction.response.send_message(
                        f"✅ Hai depositato **{qty}x {item_name}** nel deposito **{self.deposit_name}**!",
                        ephemeral=True
                    )
                    return
                
                # Più match, chiedi conferma
                embed = discord.Embed(
                    title="🔍 Item trovati",
                    description=f"Ho trovato **{len(valid_items)}** item che contengono **'{item_search}'**. Quale vuoi depositare?",
                    color=discord.Color.blue()
                )
                
                items_text = ""
                for item_name, item_qty in valid_items[:5]:
                    items_text += f"📦 **{item_name}** (Possiedi: {item_qty})\n"
                
                embed.add_field(name="Seleziona un item:", value=items_text, inline=False)
                
                view = ItemConfirmView(
                    self.bot,
                    interaction.user.id,
                    self.deposit_name,
                    [name for name, _ in valid_items],
                    qty,
                    is_withdraw=False
                )
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
            
            # Nessun match trovato
            await interaction.response.send_message(
                f"❌ Non ho trovato nessun item con **'{item_search}'** nel tuo zaino!",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message("❌ La quantità deve essere un numero valido!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Errore: {str(e)}", ephemeral=True)


class WithdrawModal(discord.ui.Modal, title="Preleva Item"):
    """Modal per prelevare item dal deposito"""
    
    item_name = discord.ui.TextInput(
        label="Nome Item (anche parziale)",
        placeholder="Scrivi il nome dell'item...",
        required=True,
        max_length=100
    )
    
    quantity = discord.ui.TextInput(
        label="Quantità",
        placeholder="Scrivi la quantità da prelevare...",
        required=True,
        max_length=10
    )
    
    def __init__(self, bot: commands.Bot, deposit_name: str):
        super().__init__()
        self.bot = bot
        self.deposit_name = deposit_name
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            item_search = self.item_name.value.strip().lower()
            qty = int(self.quantity.value.strip())
            
            if qty <= 0:
                await interaction.response.send_message("❌ La quantità deve essere maggiore di 0!", ephemeral=True)
                return
            
            # Verifica che l'utente abbia lo zaino
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT has_backpack FROM users WHERE user_id = ?",
                    (str(interaction.user.id),)
                ) as cursor:
                    user_result = await cursor.fetchone()
            
            if not user_result or user_result[0] == 0:
                await interaction.response.send_message("❌ Non hai uno zaino!", ephemeral=True)
                return
            
            # Cerca item nel deposito che contengono il testo cercato
            async with aiosqlite.connect(DATABASE_NAME) as db:
                async with db.execute(
                    "SELECT item_name, quantity FROM deposit_inventory WHERE deposit_name = ?",
                    (self.deposit_name,)
                ) as cursor:
                    all_items = await cursor.fetchall()
            
            # Filtra item che contengono il testo cercato (case insensitive)
            matched_items = []
            exact_match = None
            
            for item_name, item_qty in all_items:
                if item_search == item_name.lower():
                    exact_match = (item_name, item_qty)
                    break
                elif item_search in item_name.lower():
                    matched_items.append((item_name, item_qty))
            
            # Se c'è un match esatto, usalo
            if exact_match:
                item_name, item_qty = exact_match
                
                if item_qty < qty:
                    await interaction.response.send_message(
                        f"❌ Quantità insufficiente! Nel deposito ci sono solo **{item_qty}x {item_name}**",
                        ephemeral=True
                    )
                    return
                
                # Preleva direttamente
                await move_item_from_deposit(
                    str(interaction.user.id),
                    self.deposit_name,
                    item_name,
                    qty
                )
                
                emoji = DEPOSITS[self.deposit_name]["emoji"]
                
                public_embed = discord.Embed(
                    title=f"{emoji} Prelievo Effettuato",
                    description=f"{interaction.user.mention} ha prelevato degli item dal deposito **{self.deposit_name}**",
                    color=discord.Color.orange()
                )
                public_embed.add_field(name="📦 Item", value=item_name, inline=True)
                public_embed.add_field(name="🔢 Quantità", value=str(qty), inline=True)
                
                await interaction.channel.send(embed=public_embed)
                
                log_embed = discord.Embed(
                    title="📤 LOG PRELIEVO ITEM",
                    color=discord.Color.orange()
                )
                log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
                log_embed.add_field(name="📦 Item", value=item_name, inline=False)
                log_embed.add_field(name="🔢 Quantità", value=str(qty), inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                
                await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
                
                await interaction.response.send_message(
                    f"✅ Hai prelevato **{qty}x {item_name}** dal deposito **{self.deposit_name}**!",
                    ephemeral=True
                )
                return
            
            # Se non c'è match esatto ma ci sono match parziali
            if matched_items:
                # Verifica che tutti gli item abbiano quantità sufficiente
                valid_items = [(name, q) for name, q in matched_items if q >= qty]
                
                if not valid_items:
                    await interaction.response.send_message(
                        f"❌ Nessun item con **'{item_search}'** ha quantità sufficiente nel deposito!",
                        ephemeral=True
                    )
                    return
                
                if len(valid_items) == 1:
                    # Solo un match, preleva direttamente
                    item_name, item_qty = valid_items[0]
                    
                    await move_item_from_deposit(
                        str(interaction.user.id),
                        self.deposit_name,
                        item_name,
                        qty
                    )
                    
                    emoji = DEPOSITS[self.deposit_name]["emoji"]
                    
                    public_embed = discord.Embed(
                        title=f"{emoji} Prelievo Effettuato",
                        description=f"{interaction.user.mention} ha prelevato degli item dal deposito **{self.deposit_name}**",
                        color=discord.Color.orange()
                    )
                    public_embed.add_field(name="📦 Item", value=item_name, inline=True)
                    public_embed.add_field(name="🔢 Quantità", value=str(qty), inline=True)
                    
                    await interaction.channel.send(embed=public_embed)
                    
                    log_embed = discord.Embed(
                        title="📤 LOG PRELIEVO ITEM",
                        color=discord.Color.orange()
                    )
                    log_embed.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
                    log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
                    log_embed.add_field(name="📦 Item", value=item_name, inline=False)
                    log_embed.add_field(name="🔢 Quantità", value=str(qty), inline=False)
                    log_embed.timestamp = discord.utils.utcnow()
                    
                    await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
                    
                    await interaction.response.send_message(
                        f"✅ Hai prelevato **{qty}x {item_name}** dal deposito **{self.deposit_name}**!",
                        ephemeral=True
                    )
                    return
                
                # Più match, chiedi conferma
                embed = discord.Embed(
                    title="🔍 Item trovati",
                    description=f"Ho trovato **{len(valid_items)}** item che contengono **'{item_search}'**. Quale vuoi prelevare?",
                    color=discord.Color.blue()
                )
                
                items_text = ""
                for item_name, item_qty in valid_items[:5]:
                    items_text += f"📦 **{item_name}** (Disponibili: {item_qty})\n"
                
                embed.add_field(name="Seleziona un item:", value=items_text, inline=False)
                
                view = ItemConfirmView(
                    self.bot,
                    interaction.user.id,
                    self.deposit_name,
                    [name for name, _ in valid_items],
                    qty,
                    is_withdraw=True
                )
                
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                return
            
            # Nessun match trovato
            await interaction.response.send_message(
                f"❌ Non ho trovato nessun item con **'{item_search}'** nel deposito!",
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message("❌ La quantità deve essere un numero valido!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Errore: {str(e)}", ephemeral=True)


class DepositView(discord.ui.View):
    """View con bottoni per depositare e prelevare"""
    def __init__(self, bot: commands.Bot, deposit_name: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.deposit_name = deposit_name
    
    @discord.ui.button(label="📥 Deposita Item", style=discord.ButtonStyle.green)
    async def deposit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DepositModal(self.bot, self.deposit_name)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🎒 Preleva Item", style=discord.ButtonStyle.primary)
    async def withdraw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WithdrawModal(self.bot, self.deposit_name)
        await interaction.response.send_modal(modal)


def setup_deposit_commands(bot: commands.Bot):
    
    async def deposit_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        choices = []
        for name, data in DEPOSITS.items():
            emoji = data["emoji"]
            choices.append(
                app_commands.Choice(
                    name=f"{emoji} | Deposito {name}",
                    value=name
                )
            )
        
        if current:
            return [
                choice for choice in choices
                if current.lower() in choice.name.lower()
            ]
        return choices
    
    @bot.tree.command(name="depositi", description="Visualizza e gestisci l'inventario di un deposito fazione")
    @app_commands.describe(deposito="Seleziona il deposito da visualizzare")
    @app_commands.autocomplete(deposito=deposit_autocomplete)
    async def depositi(interaction: discord.Interaction, deposito: str):
        if deposito not in DEPOSITS:
            await interaction.response.send_message("❌ Deposito non valido!", ephemeral=True)
            return
        
        if not has_role(interaction, DEPOSITS[deposito]["role_id"]):
            await interaction.response.send_message(
                "❌ Non hai i permessi per accedere a questo deposito",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        items = await get_deposit_inventory(deposito)
        
        emoji = DEPOSITS[deposito]["emoji"]
        
        embed = discord.Embed(
            title=f"{emoji} Deposito {deposito}",
            description="Inventario del deposito della fazione:",
            color=discord.Color.blue()
        )
        
        if items:
            items_text = ""
            for item_name, quantity in items:
                items_text += f"📦 **{item_name}** - Quantità: **{quantity}**\n"
            embed.add_field(name="Items disponibili:", value=items_text, inline=False)
        else:
            embed.description = "Il deposito è vuoto!"
        
        embed.add_field(
            name="📖 Come funziona:",
            value=(
                "• **📥 Deposita Item** - Metti item dal tuo zaino nel deposito\n"
                "• **🎒 Preleva Item** - Prendi item dal deposito al tuo zaino\n\n"
                "Clicca sui bottoni qui sotto per iniziare!"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Visualizzato da {interaction.user.display_name}")
        
        view = DepositView(bot, deposito)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @bot.tree.command(name="mettidep", description="Deposita item dal tuo zaino in un deposito fazione")
    @app_commands.describe(deposito="Seleziona in quale deposito depositare")
    @app_commands.autocomplete(deposito=deposit_autocomplete)
    async def mettidep(interaction: discord.Interaction, deposito: str):
        if deposito not in DEPOSITS:
            await interaction.response.send_message("❌ Deposito non valido!", ephemeral=True)
            return
        
        if not has_role(interaction, DEPOSITS[deposito]["role_id"]):
            await interaction.response.send_message(
                "❌ Non hai i permessi per accedere a questo deposito",
                ephemeral=True
            )
            return
        
        # Verifica zaino
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT has_backpack FROM users WHERE user_id = ?",
                (str(interaction.user.id),)
            ) as cursor:
                result = await cursor.fetchone()
        
        if not result or result[0] == 0:
            await interaction.response.send_message("❌ Non hai uno zaino!", ephemeral=True)
            return
        
        # Apri modal direttamente
        modal = DepositModal(bot, deposito)
        await interaction.response.send_modal(modal)
