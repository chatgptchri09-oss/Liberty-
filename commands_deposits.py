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
        # Rimuovi dallo zaino utente
        await db.execute(
            "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
            (quantity, user_id, item_name)
        )
        await db.execute(
            "DELETE FROM inventory WHERE user_id = ? AND item_name = ? AND quantity <= 0",
            (user_id, item_name)
        )
        
        # Aggiungi al deposito
        await db.execute(
            """INSERT INTO deposit_inventory (deposit_name, item_name, quantity) 
               VALUES (?, ?, ?) 
               ON CONFLICT(deposit_name, item_name) 
               DO UPDATE SET quantity = quantity + excluded.quantity""",
            (deposit_name, item_name, quantity)
        )
        
        await db.commit()


class DepositSelectView(discord.ui.View):
    """View per selezionare il deposito"""
    def __init__(self, bot: commands.Bot, user: discord.Member, command_type: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.user = user
        self.command_type = command_type  # "view" o "deposit"
        
        # Crea il select menu
        options = []
        for name, data in DEPOSITS.items():
            # Verifica se l'utente ha il ruolo
            if has_role(type('obj', (object,), {'user': user})(), data["role_id"]):
                options.append(
                    discord.SelectOption(
                        label=f"Deposito {name}",
                        value=name,
                        emoji=data["emoji"]
                    )
                )
        
        if not options:
            options.append(
                discord.SelectOption(
                    label="Nessun deposito disponibile",
                    value="none",
                    description="Non hai accesso a nessun deposito"
                )
            )
        
        select = discord.ui.Select(
            placeholder="Seleziona un deposito...",
            options=options,
            custom_id="deposit_select"
        )
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo menu!", ephemeral=True)
            return
        
        deposit_name = interaction.values[0]
        
        if deposit_name == "none":
            await interaction.response.send_message("❌ Non hai accesso a nessun deposito!", ephemeral=True)
            return
        
        # Verifica ancora il ruolo
        if not has_role(interaction, DEPOSITS[deposit_name]["role_id"]):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo richiesto per accedere al deposito {deposit_name}!",
                ephemeral=True
            )
            return
        
        if self.command_type == "view":
            # Mostra inventario deposito
            await self.show_deposit_inventory(interaction, deposit_name)
        elif self.command_type == "deposit":
            # Avvia processo di deposito
            await self.start_deposit_process(interaction, deposit_name)
    
    async def show_deposit_inventory(self, interaction: discord.Interaction, deposit_name: str):
        """Mostra l'inventario del deposito"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        items = await get_deposit_inventory(deposit_name)
        
        emoji = DEPOSITS[deposit_name]["emoji"]
        
        embed = discord.Embed(
            title=f"{emoji} Deposito {deposit_name}",
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
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def start_deposit_process(self, interaction: discord.Interaction, deposit_name: str):
        """Avvia il processo di deposito item"""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # Verifica zaino
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT has_backpack FROM users WHERE user_id = ?",
                (str(self.user.id),)
            ) as cursor:
                result = await cursor.fetchone()
        
        if not result or result[0] == 0:
            await interaction.followup.send("❌ Non hai uno zaino!", ephemeral=True)
            return
        
        # Recupera inventario utente
        user_items = await get_user_inventory(str(self.user.id))
        
        if not user_items:
            await interaction.followup.send("❌ Il tuo zaino è vuoto!", ephemeral=True)
            return
        
        # Mostra embed iniziale con istruzioni
        emoji = DEPOSITS[deposit_name]["emoji"]
        
        embed = discord.Embed(
            title="🏢 Deposito Fazione",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📖 Come funziona:",
            value=(
                f"• **{emoji} {deposit_name}**\n\n"
                "1️⃣ Selezionare l'oggetto da depositare dal menu in basso\n"
                "2️⃣ Scegli quante unità depositare\n"
                "3️⃣ Se va a buon fine: messaggio pubblico e log staff\n"
                "♻️ Puoi depositare più item finché il pannello resta aperto"
            ),
            inline=False
        )
        
        # View con select per scegliere item
        view = ItemSelectView(self.bot, self.user, deposit_name, user_items)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ItemSelectView(discord.ui.View):
    """View per selezionare l'item da depositare"""
    def __init__(self, bot: commands.Bot, user: discord.Member, deposit_name: str, user_items: list):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.deposit_name = deposit_name
        self.user_items = {item[0]: item[1] for item in user_items}  # dict {item_name: quantity}
        
        # Crea select per items
        options = []
        for item_name, quantity in list(self.user_items.items())[:25]:  # Max 25 opzioni
            options.append(
                discord.SelectOption(
                    label=item_name,
                    value=item_name,
                    description=f"Ne possiedi: {quantity}"
                )
            )
        
        select = discord.ui.Select(
            placeholder="Seleziona un item da depositare...",
            options=options,
            custom_id="item_select"
        )
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo menu!", ephemeral=True)
            return
        
        selected_item = interaction.values[0]
        quantity_owned = self.user_items[selected_item]
        
        # Mostra view per scegliere quantità
        await self.show_quantity_selection(interaction, selected_item, quantity_owned)
    
    async def show_quantity_selection(self, interaction: discord.Interaction, item_name: str, quantity_owned: int):
        """Mostra la selezione della quantità"""
        embed = discord.Embed(
            title="📦 Scegli quantità da depositare",
            color=discord.Color.blue()
        )
        embed.add_field(name="Item:", value=item_name, inline=False)
        embed.add_field(name="Ne possiedi:", value=str(quantity_owned), inline=False)
        
        view = QuantitySelectView(
            self.bot,
            self.user,
            self.deposit_name,
            item_name,
            quantity_owned,
            self.user_items
        )
        
        await interaction.response.edit_message(embed=embed, view=view)


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
        
        # Crea select per quantità (max 25 opzioni)
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
                options=options,
                custom_id="quantity_select"
            )
            select.callback = self.select_callback
            self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo menu!", ephemeral=True)
            return
        
        quantity = int(interaction.values[0])
        await self.process_deposit(interaction, quantity)
    
    @discord.ui.button(label="🔢 Quantità Personalizzata", style=discord.ButtonStyle.primary, row=1)
    async def custom_quantity_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo bottone!", ephemeral=True)
            return
        
        # Invia messaggio per chiedere quantità
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
                
                # Elimina il messaggio dell'utente
                try:
                    await msg.delete()
                except:
                    pass
                
                # Processa il deposito
                await self.process_deposit(interaction, quantity, followup=True)
                
            except ValueError:
                await interaction.followup.send("❌ Quantità non valida! Inserisci solo numeri.", ephemeral=True)
        
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Tempo scaduto!", ephemeral=True)
    
    @discord.ui.button(label="⬅️ Indietro", style=discord.ButtonStyle.secondary, row=1)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi usare questo bottone!", ephemeral=True)
            return
        
        # Ritorna alla selezione item
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
        
        # Ricarica items aggiornati
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
    
    async def process_deposit(self, interaction: discord.Interaction, quantity: int, followup: bool = False):
        """Processa il deposito dell'item"""
        try:
            # Sposta item al deposito
            await move_item_to_deposit(
                str(self.user.id),
                self.deposit_name,
                self.item_name,
                quantity
            )
            
            emoji = DEPOSITS[self.deposit_name]["emoji"]
            
            # Messaggio pubblico in canale
            public_embed = discord.Embed(
                title=f"{emoji} Deposito Effettuato",
                description=f"{self.user.mention} ha depositato degli item nel deposito **{self.deposit_name}**",
                color=discord.Color.green()
            )
            public_embed.add_field(name="📦 Item", value=self.item_name, inline=True)
            public_embed.add_field(name="🔢 Quantità", value=str(quantity), inline=True)
            
            await interaction.channel.send(embed=public_embed)
            
            # LOG
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
            
            # Conferma privata
            if followup:
                await interaction.followup.send(
                    f"✅ Hai depositato **{quantity}x {self.item_name}** nel deposito **{self.deposit_name}**!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"✅ Hai depositato **{quantity}x {self.item_name}** nel deposito **{self.deposit_name}**!",
                    ephemeral=True
                )
            
            # Aggiorna la view per continuare
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
            error_msg = f"❌ Errore durante il deposito: {str(e)}"
            if followup:
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)


def setup_deposit_commands(bot: commands.Bot):
    
    @bot.tree.command(name="depositi", description="Visualizza l'inventario di un deposito fazione")
    async def depositi(interaction: discord.Interaction):
        # Verifica che l'utente abbia accesso ad almeno un deposito
        has_access = False
        for deposit_data in DEPOSITS.values():
            if has_role(interaction, deposit_data["role_id"]):
                has_access = True
                break
        
        if not has_access:
            await interaction.response.send_message(
                "❌ Non hai accesso a nessun deposito!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🏢 Seleziona un Deposito",
            description="Scegli il deposito di cui vuoi visualizzare l'inventario:",
            color=discord.Color.blue()
        )
        
        view = DepositSelectView(bot, interaction.user, "view")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @bot.tree.command(name="mettidep", description="Deposita item dal tuo zaino in un deposito fazione")
    async def mettidep(interaction: discord.Interaction):
        # Verifica che l'utente abbia accesso ad almeno un deposito
        has_access = False
        for deposit_data in DEPOSITS.values():
            if has_role(interaction, deposit_data["role_id"]):
                has_access = True
                break
        
        if not has_access:
            await interaction.response.send_message(
                "❌ Non hai accesso a nessun deposito!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🏢 Seleziona un Deposito",
            description="Scegli in quale deposito vuoi depositare i tuoi item:",
            color=discord.Color.green()
        )
        
        view = DepositSelectView(bot, interaction.user, "deposit")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
