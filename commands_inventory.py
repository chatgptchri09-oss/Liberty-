import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import math
from datetime import datetime
from typing import Dict, List, Any

# ===================================================================================
# COSTANTI E FUNZIONI DI SUPPORTO
# ===================================================================================

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLE_ID = 1414738761207517214
MARKET_ROLE_ID = 1415242295153918123

# --- Costanti per Logica Crafting/Inventario (Ricette/Progetti) ---
RICETTE: Dict[str, Dict[str, int]] = {
    "Pistola": {"Ferro": 20, "Percussore Bilanciato": 1, "Otturatore": 1},
    "Pistola d'Ordinanza (F.D.O)": {"Ferro": 25, "Acciaio Lavorato": 15, "Kit Smussatura (Bordi)": 1},
    "Taser (F.D.O)": {"Ferro": 18, "Acciaio Lavorato": 1, "Pacco Celle 18650 Protette": 1, "Microchip": 1},
    "Pistola Da Combattimento": {"Ferro": 45, "Molla Rinforzata": 1, "Otturatore": 1},
    "Revolver Pesante": {"Ferro": 30, "Acciaio Lavorato": 1, "Molla Rinforzata": 1},
    "Pistola MK2 (F.D.O)": {"Ferro": 15, "Pistola": 1, "Otturatore": 1, "Molla Rinforzata": 1},
    "Pistola MK2 = 1": {"Ferro": 15, "Pistola": 1, "Otturatore": 1, "Molla Rinforzata": 1},
    "Fucile": {"Acciaio Lavorato": 50, "Canna Lunga": 1, "Calcio": 1}, 
}

PROGETTI_MAP: Dict[str, List[str]] = {
    "Progetto Pistole Legali": ["Pistola", "Pistola d'Ordinanza (F.D.O)", "Taser (F.D.O)", "Pistola Da Combattimento", "Revolver Pesante", "Pistola MK2 (F.D.O)", "Pistola MK2 = 1"],
    "Progetto Armi Lunghe Legali": ["Fucile"], 
    "Progetto Protezioni": ["Giubbotto Antiproiettile", "Elmetto"], 
    "Progetto Armi Lunghe Illegali": ["AK-47", "M4"], 
}

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

# ===================================================================================
# FUNZIONI DI INVENTARIO AGGIORNATE
# ===================================================================================

async def update_inventory(user_id: str, item_name: str, quantity: int, mode: str = 'add'):
    """
    Aggiorna l'inventario dell'utente.
    mode='add': Aggiunge la quantità. mode='remove': Rimuove la quantità.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if mode == 'add':
            await db.execute(
                "INSERT INTO user_inventory (user_id, item_name, quantity) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + excluded.quantity",
                (user_id, item_name, quantity)
            )
        elif mode == 'remove':
            # Rimuove la quantità
            await db.execute(
                "UPDATE user_inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                (quantity, user_id, item_name)
            )
            # Rimuove l'item se la quantità è <= 0
            await db.execute(
                "DELETE FROM user_inventory WHERE user_id = ? AND item_name = ? AND quantity <= 0",
                (user_id, item_name)
            )
        await db.commit()

async def get_backpack_size(user_id: str) -> int:
    """Recupera la dimensione dello zaino dell'utente dalla tabella users."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT has_backpack FROM users WHERE user_id = ?", 
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            # Assumiamo che 1 = Zaino 30Kg, 0 = 0Kg.
            return 30 if result and result[0] == 1 else 0

async def get_inventory_items_with_weight(user_id: str) -> List[Dict]:
    """Recupera gli item dell'utente, includendo il peso dalla tabella items."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            """
            SELECT ui.item_name, ui.quantity, i.weight 
            FROM user_inventory ui
            LEFT JOIN items i ON ui.item_name = i.name 
            WHERE ui.user_id = ? AND ui.quantity > 0
            ORDER BY ui.item_name
            """,
            (user_id,)
        ) as cursor:
            results = await cursor.fetchall()
            
            items_list = []
            for item_name, quantity, weight in results:
                items_list.append({
                    "item_name": item_name,
                    "quantity": quantity,
                    "weight": weight if weight is not None else 0.0 
                })
            return items_list

async def get_inventory_item(user_id: str, item_name: str) -> int:
    """Recupera la quantità di un item posseduta dall'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM user_inventory WHERE user_id = ? AND item_name = ?",
            (user_id, item_name)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

async def get_item_weight_db(item_name: str) -> float:
    """Recupera il peso di un item specifico dal database."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT weight FROM items WHERE name = ?", 
            (item_name,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0.0 # Ritorna 0.0 se non trovato o non definito

# ===================================================================================
# CLASSI VIEW
# ===================================================================================

class InventoryView(discord.ui.View):
    def __init__(self, bot: commands.Bot, items: List[Dict], max_weight: int, total_weight: float):
        super().__init__(timeout=60)
        self.bot = bot
        self.items = items
        self.max_weight = max_weight
        self.total_weight = total_weight
        self.items_per_page = 5
        self.current_page = 0
        self.max_pages = math.ceil(len(self.items) / self.items_per_page) if self.items else 1
        
        self.add_item(self.create_page_button("⬅️ Pagina", "prev_page", discord.ButtonStyle.secondary))
        self.add_item(self.create_page_button("Pagina ➡️", "next_page", discord.ButtonStyle.secondary))
        self.add_item(self.create_deposit_button())

    def create_page_button(self, label, custom_id, style):
        button = discord.ui.Button(label=label, style=style, custom_id=custom_id, disabled=(self.max_pages == 1))
        button.callback = self.page_callback
        return button

    def create_deposit_button(self):
        button = discord.ui.Button(label="Metti nel deposito", style=discord.ButtonStyle.danger, custom_id="deposit_button")
        button.callback = self.deposit_callback
        return button

    def get_page_content(self) -> str:
        start_index = self.current_page * self.items_per_page
        end_index = start_index + self.items_per_page
        page_items = self.items[start_index:end_index]
        
        content = []
        
        content.append(f"👑 **Zaino ({self.max_weight}Kg)**")
        # Peso totale formattato a 3 decimali
        content.append(f"Peso attuale: {self.total_weight:.3f}Kg / {self.max_weight}Kg") 
        
        for item in page_items:
            item_name = item['item_name']
            quantity = item['quantity']
            item_weight = item['weight'] 
            
            total_item_weight = quantity * item_weight
            
            content.append(
                f"* **-{quantity} | {item_name}** ({total_item_weight:.3f}Kg)")
            
        return "\n".join(content)

    async def update_message(self, interaction: discord.Interaction):
        if self.max_pages > 1:
            self.children[0].disabled = (self.current_page == 0)
            self.children[1].disabled = (self.current_page == self.max_pages - 1)

        embed = discord.Embed(
            title="Inventario Zaino", 
            description=self.get_page_content(), 
            color=discord.Color.dark_teal()
        )
        embed.set_footer(text=f"Pagina {self.current_page + 1} di {self.max_pages} | Richiesto da {interaction.user.display_name}")
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def page_callback(self, interaction: discord.Interaction):
        if interaction.custom_id == "prev_page" and self.current_page > 0:
            self.current_page -= 1
        elif interaction.custom_id == "next_page" and self.current_page < self.max_pages - 1:
            self.current_page += 1
            
        await self.update_message(interaction)

    async def deposit_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("⚙️ Comando /deposit in fase di sviluppo...", ephemeral=True)


class ProgettoView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.add_item(self.create_select_menu())

    def create_select_menu(self):
        options = []
        for progetto in PROGETTI_MAP.keys():
            options.append(discord.SelectOption(label=progetto, value=progetto))
            
        select = discord.ui.Select(
            placeholder="Scegli una categoria di progetto",
            options=options,
            custom_id="progetto_select"
        )
        select.callback = self.select_callback
        return select

    async def select_callback(self, interaction: discord.Interaction):
        selected_progetto = interaction.data['values'][0]
        ricette_lista = PROGETTI_MAP.get(selected_progetto, [])
        
        if await get_inventory_item(self.user_id, selected_progetto) == 0:
            await interaction.response.send_message(
                f"❌ Devi possedere l'item **{selected_progetto}** nello zaino per visualizzare le sue ricette!",
                ephemeral=True
            )
            return

        ricette_text = ""
        for item_name in ricette_lista:
            ricetta = RICETTE.get(item_name)
            if ricetta:
                materiali_list = [f"**{quantita}x** {materiale}" for materiale, quantita in ricetta.items()]
                ricette_text += f"**{item_name}** – {', '.join(materiali_list)}\n"

        embed = discord.Embed(
            title=f"Ricette – {selected_progetto}",
            description=ricette_text if ricette_text else "Nessuna ricetta definita per questo progetto.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Suggerimento: i materiali non vengono controllati qui.")
        
        await interaction.response.edit_message(embed=embed, view=None)


# ===================================================================================
# COMANDI PRINCIPALI
# ===================================================================================

def setup_inventory_commands(bot: commands.Bot):
    
    # -------------------------------------------------------------------------------
    # COMANDO /invzaino (VISUALIZZA INVENTARIO CON PESO)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="invzaino", description="Visualizza il contenuto del tuo zaino (inventory)")
    async def invzaino(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        max_weight = await get_backpack_size(user_id)
        
        if max_weight == 0:
            await interaction.followup.send("❌ Non possiedi uno zaino per visualizzare l'inventario!", ephemeral=True)
            return

        items = await get_inventory_items_with_weight(user_id) 
        total_weight = sum(item['quantity'] * item['weight'] for item in items)
        
        if not items:
            await interaction.followup.send(
                f"👑 **Zaino ({max_weight}Kg)**\nPeso attuale: 0.000Kg / {max_weight}Kg\n* Lo zaino è vuoto.",
                ephemeral=True
            )
            return
            
        view = InventoryView(bot, items, max_weight, total_weight)
        
        embed = discord.Embed(
            title="Inventario Zaino", 
            description=view.get_page_content(), 
            color=discord.Color.dark_teal()
        )
        embed.set_footer(text=f"Pagina 1 di {view.max_pages} | Richiesto da {interaction.user.display_name}")

        await interaction.followup.send(
            content=f"Rewind V2 **APP** {datetime.now().strftime('%H:%M')}\n**@{interaction.user.display_name}**",
            embed=embed, 
            view=view, 
            ephemeral=True
        )
        await log_command(bot, LOG_CHANNEL_ID, f"💼 {interaction.user.mention} ha visualizzato il suo zaino.")


    # -------------------------------------------------------------------------------
    # COMANDO /progetto (VISUALIZZA RICETTE)
    # -------------------------------------------------------------------------------
    
    @bot.tree.command(name="progetto", description="Visualizza le ricette disponibili per i tuoi progetti")
    async def progetto(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        view = ProgettoView(bot, str(interaction.user.id))
        
        embed = discord.Embed(
            title="Progetti disponibili",
            description="Seleziona dal menu la categoria di progetto che vuoi visualizzare. Per aprire una categoria devi possedere nello zaino il corrispondente item progetto.",
            color=discord.Color.blue()
        )
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"📝 {interaction.user.mention} ha visualizzato il menu Progetti.")


    # -------------------------------------------------------------------------------
    # COMANDO /dai (TRASFERIMENTO OGGETTI)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="dai-item", description="Dai un oggetto dal tuo zaino a un altro utente")
    @app_commands.describe(utente="L'utente a cui dare l'oggetto", nome_item="Il nome dell'oggetto da dare", quantita="La quantità da trasferire")
    async def dai(interaction: discord.Interaction, utente: discord.Member, nome_item: str, quantita: int):
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        sender_id = str(interaction.user.id)
        receiver_id = str(utente.id)
        
        if quantita <= 0:
            await interaction.followup.send("❌ La quantità deve essere almeno 1!", ephemeral=True)
            return
            
        if sender_id == receiver_id:
            await interaction.followup.send("❌ Non puoi dare un oggetto a te stesso!", ephemeral=True)
            return

        sender_quantity = await get_inventory_item(sender_id, nome_item)
        receiver_backpack = await get_backpack_size(receiver_id)
        
        if sender_quantity < quantita:
            await interaction.followup.send(f"❌ Non hai **{quantita}**x **{nome_item}** nel tuo zaino!", ephemeral=True)
            return
            
        if receiver_backpack == 0:
            await interaction.followup.send(
                f"❌ {utente.mention} non ha uno zaino in cui ricevere l'item!", 
                ephemeral=True
            )
            return
            
        # --- Controllo Peso (NUOVA LOGICA AGGIUNTA) ---
        
        # 1. Calcola il peso che si sposta
        item_weight = await get_item_weight_db(nome_item)
        transfer_weight = quantita * item_weight
        
        # 2. Calcola il peso attuale del destinatario (escluso l'item che riceverà)
        receiver_items = await get_inventory_items_with_weight(receiver_id)
        current_receiver_weight = sum(item['quantity'] * item['weight'] for item in receiver_items if item['item_name'] != nome_item)
        
        # 3. Verifica il limite
        new_receiver_weight = current_receiver_weight + transfer_weight
        if new_receiver_weight > receiver_backpack:
             await interaction.followup.send(
                f"❌ **{utente.mention} non può ricevere questo oggetto!** Il suo zaino è troppo pesante.\n"
                f"Peso attuale: {current_receiver_weight:.3f}Kg. Peso da ricevere: {transfer_weight:.3f}Kg. Limite: {receiver_backpack}Kg.",
                ephemeral=True
            )
             return

        # Trasferimento effettivo
        await update_inventory(sender_id, nome_item, quantita, mode='remove')
        await update_inventory(receiver_id, nome_item, quantita, mode='add')
    
        try:
            embed = discord.Embed(
                title="🎁 Oggetto Ricevuto!",
                description=f"Hai ricevuto **{quantita}**x **{nome_item}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="Donatore", value=interaction.user.mention, inline=False)
            embed.set_footer(text=f"Il tuo nuovo peso stimato: {new_receiver_weight:.3f}Kg. Controlla il tuo zaino con /invzaino.")
            await utente.send(embed=embed)
        except:
            pass
            
        await interaction.followup.send(
            f"✅ Hai dato **{quantita}**x **{nome_item}** a {utente.mention} con successo!", 
            ephemeral=True
        )

        log_msg = f"➡️ {interaction.user.mention} ha dato {quantita}x {nome_item} a {utente.mention}"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)


    # -------------------------------------------------------------------------------
    # COMANDO /additem (AGGIUNGI OGGETTO - STAFF)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="give-item", description="[STAFF] Aggiunge un oggetto all'inventario di un utente")
    @app_commands.describe(utente="L'utente a cui aggiungere l'oggetto", nome_item="Nome dell'oggetto da aggiungere", quantita="La quantità da aggiungere")
    async def additem(interaction: discord.Interaction, utente: discord.Member, nome_item: str, quantita: int):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = str(utente.id)
        
        # --- Controllo Peso per l'aggiunta (NUOVA LOGICA) ---
        max_weight = await get_backpack_size(user_id)
        if max_weight == 0:
             await interaction.followup.send(
                f"❌ **{utente.mention} non possiede uno zaino!** L'item non può essere aggiunto.", 
                ephemeral=True
            )
             return
             
        item_weight = await get_item_weight_db(nome_item)
        transfer_weight = quantita * item_weight
        
        receiver_items = await get_inventory_items_with_weight(user_id)
        current_receiver_weight = sum(item['quantity'] * item['weight'] for item in receiver_items if item['item_name'] != nome_item)
        new_receiver_weight = current_receiver_weight + transfer_weight
        
        if new_receiver_weight > max_weight:
             await interaction.followup.send(
                f"❌ **Impossibile aggiungere!** {utente.mention} non ha abbastanza spazio.\n"
                f"Peso attuale: {current_receiver_weight:.3f}Kg. Peso da aggiungere: {transfer_weight:.3f}Kg. Limite: {max_weight}Kg.",
                ephemeral=True
            )
             return
        
        # Esecuzione dell'aggiunta
        await update_inventory(user_id, nome_item, quantita, mode='add')
        
        await interaction.followup.send(
            f"✅ Aggiunti **{quantita}**x **{nome_item}** all'inventario di {utente.mention}!", 
            ephemeral=True
        )
        
        try:
            await utente.send(f"✅ Lo staff ha aggiunto **{quantita}**x **{nome_item}** al tuo zaino. Nuovo peso stimato: {new_receiver_weight:.3f}Kg.")
        except:
            pass
            
        await log_command(bot, LOG_CHANNEL_ID, f"➕ {interaction.user.mention} ha aggiunto {quantita}x {nome_item} a {utente.mention}")


    # -------------------------------------------------------------------------------
    # COMANDO /removeitem (RIMUOVI OGGETTO - STAFF)
    # -------------------------------------------------------------------------------

    @bot.tree.command(name="removeitem", description="[STAFF] Rimuove un oggetto dall'inventario di un utente")
    @app_commands.describe(utente="L'utente a cui rimuovere l'oggetto", nome_item="Nome dell'oggetto da rimuovere", quantita="La quantità da rimuovere")
    async def removeitem(interaction: discord.Interaction, utente: discord.Member, nome_item: str, quantita: int):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return

        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = str(utente.id)
        
        current_quantity = await get_inventory_item(user_id, nome_item)
        
        if current_quantity < quantita:
            await interaction.followup.send(
                f"❌ {utente.mention} possiede solo {current_quantity}x **{nome_item}**. Impossibile rimuovere {quantita}.", 
                ephemeral=True
            )
            return

        # Esecuzione della rimozione
        await update_inventory(user_id, nome_item, quantita, mode='remove')
        
        await interaction.followup.send(
            f"✅ Rimossi **{quantita}**x **{nome_item}** dall'inventario di {utente.mention}!", 
            ephemeral=True
        )
        
        try:
            new_quantity = current_quantity - quantita
            await utente.send(f"⚠️ Lo staff ha rimosso **{quantita}**x **{nome_item}** dal tuo zaino. Quantità rimanente: {new_quantity}.")
        except:
            pass
            
        await log_command(bot, LOG_CHANNEL_ID, f"➖ {interaction.user.mention} ha rimosso {quantita}x {nome_item} da {utente.mention}")
