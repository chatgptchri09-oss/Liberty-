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


class DepositMainView(discord.ui.View):
    """View principale per il deposito con bottone preleva"""
    def __init__(self, bot: commands.Bot, user: discord.Member, deposit_name: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.deposit_name = deposit_name
    
    @discord.ui.button(label="🎒 Metti nello zaino", style=discord.ButtonStyle.primary)
    async def withdraw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo bottone!", ephemeral=True)
            return
        
        await interaction.response.send_message(
            f"✏️ Scrivi la quantità e il nome dell'item da mettere nello zaino (esempio: 1 matita)",
            ephemeral=True
        )
        
        def check(m):
            return m.author.id == self.user.id and m.channel.id == interaction.channel.id
        
        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            
            try:
                parts = msg.content.split(maxsplit=1)
                if len(parts) != 2:
                    await interaction.followup.send("❌ Formato non valido! Usa: quantità nome_item", ephemeral=True)
                    return
                
                quantity = int(parts[0])
                item_name = parts[1]
                
                if quantity <= 0:
                    await interaction.followup.send("❌ La quantità deve essere maggiore di 0!", ephemeral=True)
                    return
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute(
                        "SELECT quantity FROM deposit_inventory WHERE deposit_name = ? AND item_name = ?",
                        (self.deposit_name, item_name)
                    ) as cursor:
                        result = await cursor.fetchone()
                
                if not result:
                    await interaction.followup.send(f"❌ L'item **{item_name}** non esiste nel deposito!", ephemeral=True)
                    return
                
                if result[0] < quantity:
                    await interaction.followup.send(
                        f"❌ Quantità insufficiente! Nel deposito ci sono solo **{result[0]}x {item_name}**",
                        ephemeral=True
                    )
                    return
                
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute(
                        "SELECT has_backpack FROM users WHERE user_id = ?",
                        (str(self.user.id),)
                    ) as cursor:
                        user_result = await cursor.fetchone()
                
                if not user_result or user_result[0] == 0:
                    await interaction.followup.send("❌ Non hai uno zaino!", ephemeral=True)
                    return
                
                try:
                    await msg.delete()
                except:
                    pass
                
                await move_item_from_deposit(
                    str(self.user.id),
                    self.deposit_name,
                    item_name,
                    quantity
                )
                
                emoji = DEPOSITS[self.deposit_name]["emoji"]
                
                public_embed = discord.Embed(
                    title=f"{emoji} Prelievo Effettuato",
                    description=f"{self.user.mention} ha prelevato degli item dal deposito **{self.deposit_name}**",
                    color=discord.Color.orange()
                )
                public_embed.add_field(name="📦 Item", value=item_name, inline=True)
                public_embed.add_field(name="🔢 Quantità", value=str(quantity), inline=True)
                
                await interaction.channel.send(embed=public_embed)
                
                log_embed = discord.Embed(
                    title="📤 LOG PRELIEVO ITEM",
                    color=discord.Color.orange()
                )
                log_embed.add_field(name="👤 Utente", value=self.user.mention, inline=True)
                log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
                log_embed.add_field(name="📦 Item", value=item_name, inline=False)
                log_embed.add_field(name="🔢 Quantità", value=str(quantity), inline=False)
                log_embed.timestamp = discord.utils.utcnow()
                
                await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
                
                await interaction.followup.send(
                    f"✅ Hai prelevato **{quantity}x {item_name}** dal deposito **{self.deposit_name}**!",
                    ephemeral=True
                )
                
            except ValueError:
                await interaction.followup.send("❌ Quantità non valida! La quantità deve essere un numero.", ephemeral=True)
        
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Tempo scaduto!", ephemeral=True)


class ItemSelectView(discord.ui.View):
    """View per selezionare l'item da depositare"""
    def __init__(self, bot: commands.Bot, user: discord.Member, deposit_name: str, user_items: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.deposit_name = deposit_name
        self.user_items = {item[0]: item[1] for item in user_items}
        
        options = []
        for item_name, quantity in list(self.user_items.items())[:25]:
            options.append(
                discord.SelectOption(
                    label=item_name,
                    value=item_name,
                    description=f"Ne possiedi: {quantity}"
                )
            )
        
        select = discord.ui.Select(
            placeholder="Seleziona un item da depositare...",
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ Non puoi usare questo menu!", ephemeral=True)
                return
            
            selected_item = interaction.values[0]
            quantity_owned = self.user_items[selected_item]
            
            embed = discord.Embed(
                title="📦 Scegli quantità da depositare",
                color=discord.Color.blue()
            )
            embed.add_field(name="Item:", value=selected_item, inline=False)
            embed.add_field(name="Ne possiedi:", value=str(quantity_owned), inline=False)
            
            view = QuantitySelectView(
                self.bot,
                self.user,
                self.deposit_name,
                selected_item,
                quantity_owned,
                self.user_items
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            print(f"Errore in select_callback: {e}")
            try:
                await interaction.response.send_message(f"❌ Errore: {e}", ephemeral=True)
            except:
                pass


class QuantitySelectView(discord.ui.View):
    """View per selezionare la quantità da depositare"""
    def __init__(self, bot: commands.Bot, user: discord.Member, deposit_name: str, 
                 item_name: str, quantity_owned: int, all_items: dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.deposit_name = deposit_name
        self.item_name = item_name
        self.quantity_owned = quantity_owned
        self.all_items = all_items
        
        options = []
        max_display = min(quantity_owned, 25)
        
        for i in range(1, max_display + 1):
            options.append(
                discord.SelectOption(
                    label=str(i),
                    value=str(i)
                )
            )
        
        if options:
            select = discord.ui.Select(
                placeholder="Seleziona la quantità...",
                options=options
            )
            select.callback = self.select_callback
            self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ Non puoi usare questo menu!", ephemeral=True)
                return
            
            quantity = int(interaction.values[0])
            await interaction.response.defer()
            await self.process_deposit(interaction, quantity)
        except Exception as e:
            print(f"Errore in quantity select: {e}")
    
    @discord.ui.button(label="🔢 Quantità Personalizzata", style=discord.ButtonStyle.primary, row=1)
    async def custom_quantity_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo bottone!", ephemeral=True)
            return
        
        await interaction.response.send_message(
            f"✏️ Scrivi qui la quantità di **{self.item_name}** da depositare in **{self.deposit_name}**\n"
            f"(Ne possiedi: **{self.quantity_owned}**)",
            ephemeral=True
        )
        
        def check(m):
            return m.author.id == self.user.id and m.channel.id == interaction.channel.id
        
        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=check)
            
            try:
                quantity = int(msg.content)
                
                if quantity <= 0:
                    await interaction.followup.send("❌ La quantità deve essere maggiore di 0!", ephemeral=True)
                    return
                
                if quantity > self.quantity_owned:
                    await interaction.followup.send(
                        f"❌ Non hai abbastanza **{self.item_name}**! (Possiedi: {self.quantity_owned})",
                        ephemeral=True
                    )
                    return
                
                try:
                    await msg.delete()
                except:
                    pass
                
                await self.process_deposit(interaction, quantity)
                
            except ValueError:
                await interaction.followup.send("❌ Quantità non valida! Inserisci solo numeri.", ephemeral=True)
        
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Tempo scaduto!", ephemeral=True)
    
    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo bottone!", ephemeral=True)
            return
        
        emoji = DEPOSITS[self.deposit_name]["emoji"]
        
        embed = discord.Embed(
            title="🏢 Deposito Fazione",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📖 Come funziona:",
            value=(
                f"• **{emoji} {self.deposit_name}**\n\n"
                "1️⃣ Selezionare l'oggetto da depositare dal menu in basso\n"
                "2️⃣ Scegli quante unità depositare\n"
                "3️⃣ Se va a buon fine: messaggio pubblico e log staff\n"
                "♻️ Puoi depositare più item finché il pannello resta aperto"
            ),
            inline=False
        )
        
        user_items_list = await get_user_inventory(str(self.user.id))
        
        if not user_items_list:
            await interaction.response.edit_message(
                content="❌ Il tuo zaino è ora vuoto!",
                embed=None,
                view=None
            )
            return
        
        view = ItemSelectView(self.bot, self.user, self.deposit_name, user_items_list)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def process_deposit(self, interaction: discord.Interaction, quantity: int):
        """Processa il deposito dell'item"""
        try:
            await move_item_to_deposit(
                str(self.user.id),
                self.deposit_name,
                self.item_name,
                quantity
            )
            
            emoji = DEPOSITS[self.deposit_name]["emoji"]
            
            public_embed = discord.Embed(
                title=f"{emoji} Deposito Effettuato",
                description=f"{self.user.mention} ha depositato degli item nel deposito **{self.deposit_name}**",
                color=discord.Color.green()
            )
            public_embed.add_field(name="📦 Item", value=self.item_name, inline=True)
            public_embed.add_field(name="🔢 Quantità", value=str(quantity), inline=True)
            
            await interaction.channel.send(embed=public_embed)
            
            log_embed = discord.Embed(
                title="📥 LOG DEPOSITO ITEM",
                color=discord.Color.green()
            )
            log_embed.add_field(name="👤 Utente", value=self.user.mention, inline=True)
            log_embed.add_field(name="🏢 Deposito", value=f"{emoji} {self.deposit_name}", inline=True)
            log_embed.add_field(name="📦 Item", value=self.item_name, inline=False)
            log_embed.add_field(name="🔢 Quantità", value=str(quantity), inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            
            await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)
            
            await interaction.followup.send(
                f"✅ Hai depositato **{quantity}x {self.item_name}** nel deposito **{self.deposit_name}**!",
                ephemeral=True
            )
            
            user_items_list = await get_user_inventory(str(self.user.id))
            
            if user_items_list:
                embed = discord.Embed(
                    title="🏢 Deposito Fazione",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📖 Come funziona:",
                    value=(
                        f"• **{emoji} {self.deposit_name}**\n\n"
                        "1️⃣ Selezionare l'oggetto da depositare dal menu in basso\n"
                        "2️⃣ Scegli quante unità depositare\n"
                        "3️⃣ Se va a buon fine: messaggio pubblico e log staff\n"
                        "♻️ Puoi depositare più item finché il pannello resta aperto"
                    ),
                    inline=False
                )
                
                view = ItemSelectView(self.bot, self.user, self.deposit_name, user_items_list)
                await interaction.message.edit(embed=embed, view=view)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Errore durante il deposito: {str(e)}", ephemeral=True)


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
    
    @bot.tree.command(name="depositi", description="Visualizza l'inventario di un deposito fazione")
    @app_commands.describe(deposito="Seleziona il deposito da visualizzare")
    @app_commands.autocomplete(deposito=deposit_autocomplete)
    async def depositi(interaction: discord.Interaction, deposito: str):
        if deposito not in DEPOSITS:
            await interaction.response.send_message("❌ Deposito non valido!", ephemeral=True)
            return
        
        if not has_role(interaction, DEPOSITS[deposito]["role_id"]):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per accedere a questo deposito",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        items = await get_deposit_inventory(deposito)
        
        emoji = DEPOSITS[deposito]["emoji"]
        
        embed = discord.Embed(
            title=f"{emoji} Deposito {deposito}",
            description=f"Inventario del deposito della fazione:",
            color=discord.Color.blue()
        )
        
        if items:
            for item_name, quantity in items:
                embed.add_field(
                    name=f"📦 {item_name}",
                    value=f"Quantità: **{quantity}**",
                    inline=False
                )
        else:
            embed.description = "Il deposito è vuoto!"
        
        embed.set_footer(text=f"Visualizzato da {interaction.user.display_name}")
        
        view = DepositMainView(bot, interaction.user, deposito)
        
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
                f"❌ Non hai i permessi per accedere a questo deposito",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT has_backpack FROM users WHERE user_id = ?",
                (str(interaction.user.id),)
            ) as cursor:
                result = await cursor.fetchone()
        
        if not result or result[0] == 0:
            await interaction.followup.send("❌ Non hai uno zaino!", ephemeral=True)
            return
        
        user_items = await get_user_inventory(str(interaction.user.id))
        
        if not user_items:
            await interaction.followup.send("❌ Il tuo zaino è vuoto!", ephemeral=True)
            return
        
        emoji = DEPOSITS[deposito]["emoji"]
        
        embed = discord.Embed(
            title="🏢 Deposito Fazione",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📖 Come funziona:",
            value=(
                f"• **{emoji} {deposito}**\n\n"
                "1️⃣ Selezionare l'oggetto da depositare dal menu in basso\n"
                "2️⃣ Scegli quante unità depositare\n"
                "3️⃣ Se va a buon fine: messaggio pubblico e log staff\n"
                "♻️ Puoi depositare più item finché il pannello resta aperto"
            ),
            inline=False
        )
        
        view = ItemSelectView(bot, interaction.user, deposito, user_items)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
