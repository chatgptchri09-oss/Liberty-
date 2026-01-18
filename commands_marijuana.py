import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, time
import asyncio

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
MARIJUANA_ROLE_ID = 1431629412339548320
COCAINA_ROLE_ID = 1431628821634744474
SMANTELLATORE_ROLE_ID = 1456965485382991902

# Limite giornaliero di raccolta
DAILY_LIMIT = 300

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

async def init_marijuana_db():
    """Inizializza la tabella per la raccolta marijuana"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS marijuana_collection (
                user_id TEXT PRIMARY KEY,
                collected_today INTEGER DEFAULT 0,
                last_collection_date TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cocaina_collection (
                user_id TEXT PRIMARY KEY,
                collected_today INTEGER DEFAULT 0,
                last_collection_date TEXT
            )
        """)
        await db.commit()

async def get_today_collection(user_id: str, table_name: str):
    """Ottieni il numero di raccolte odierne per un utente"""
    today = datetime.now().date().isoformat()
    
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            f"SELECT collected_today, last_collection_date FROM {table_name} WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
        
        if not result:
            await db.execute(
                f"INSERT INTO {table_name} (user_id, collected_today, last_collection_date) VALUES (?, ?, ?)",
                (user_id, 0, today)
            )
            await db.commit()
            return 0
        
        collected, last_date = result
        
        if last_date != today:
            await db.execute(
                f"UPDATE {table_name} SET collected_today = 0, last_collection_date = ? WHERE user_id = ?",
                (today, user_id)
            )
            await db.commit()
            return 0
        
        return collected

async def increment_collection(user_id: str, table_name: str):
    """Incrementa il contatore di raccolta giornaliera"""
    today = datetime.now().date().isoformat()
    
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            f"UPDATE {table_name} SET collected_today = collected_today + 1, last_collection_date = ? WHERE user_id = ?",
            (today, user_id)
        )
        await db.commit()

async def add_item_to_inventory(user_id: str, item_name: str):
    """Aggiungi 1 item all'inventario dell'utente"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
            (user_id, item_name)
        ) as cursor:
            result = await cursor.fetchone()
        
        if result:
            new_quantity = result[0] + 1
            await db.execute(
                "UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?",
                (new_quantity, user_id, item_name)
            )
        else:
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)",
                (user_id, item_name, 1)
            )
        
        await db.commit()

async def has_item_in_inventory(user_id: str, item_name: str) -> bool:
    """Controlla se l'utente ha un item nell'inventario"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
            (user_id, item_name)
        ) as cursor:
            result = await cursor.fetchone()
            return result is not None and result[0] > 0

class CollectMarijuanaButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="🌿 Raccogli",
            custom_id="collect_marijuana"
        )
    
    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        if not has_role(interaction, MARIJUANA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai il ruolo necessario per raccogliere marijuana!",
                ephemeral=True
            )
            return
        
        if not await has_item_in_inventory(user_id, "✂️ | Forbici Raccolta Marijuana"):
            await interaction.response.send_message(
                "❌ Ti servono le **✂️ | Forbici Raccolta Marijuana** per raccogliere",
                ephemeral=True
            )
            return
        
        collected_today = await get_today_collection(user_id, "marijuana_collection")
        
        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere altra marijuana.",
                ephemeral=True
            )
            return
        
        for item in self.view.children:
            item.disabled = True
        
        processing_embed = discord.Embed(
            title="🌿 Raccolta Marijuana",
            description="⏳ Raccolta in corso... Attendi 10 secondi.",
            color=0x2ecc71
        )
        processing_embed.set_footer(text="Non chiudere questo messaggio")
        
        await interaction.response.edit_message(embed=processing_embed, view=self.view)
        
        await asyncio.sleep(10)
        
        await increment_collection(user_id, "marijuana_collection")
        await add_item_to_inventory(user_id, "🌿 | Marijuana")
        
        new_total = collected_today + 1
        
        success_embed = discord.Embed(
            title="✅ Raccolta completata",
            description=f"Hai raccolto 1gr di marijuana, in totale oggi ne hai raccolti **{new_total}/{DAILY_LIMIT}**.\n\nL'item è stato aggiunto al tuo zaino.",
            color=0x2ecc71
        )
        success_embed.set_footer(text="Usa /invzaino per vedere il tuo inventario")
        
        await interaction.edit_original_response(embed=success_embed, view=self.view)

class CollectCocainaButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="🥥 Raccogli",
            custom_id="collect_cocaina"
        )
    
    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        if not has_role(interaction, COCAINA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai il ruolo necessario per raccogliere cocaina!",
                ephemeral=True
            )
            return
        
        if not await has_item_in_inventory(user_id, "⛏️ | Falce Raccolta Cocaina"):
            await interaction.response.send_message(
                "❌ Ti servono la **⛏️ | Falce Raccolta Cocaina** per raccogliere",
                ephemeral=True
            )
            return
        
        collected_today = await get_today_collection(user_id, "cocaina_collection")
        
        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere altra cocaina.",
                ephemeral=True
            )
            return
        
        for item in self.view.children:
            item.disabled = True
        
        processing_embed = discord.Embed(
            title="🥥 Raccolta Cocaina",
            description="⏳ Raccolta in corso... Attendi 10 secondi.",
            color=discord.Color.light_grey()
        )
        processing_embed.set_footer(text="Non chiudere questo messaggio")
        
        await interaction.response.edit_message(embed=processing_embed, view=self.view)
        
        await asyncio.sleep(10)
        
        await increment_collection(user_id, "cocaina_collection")
        await add_item_to_inventory(user_id, "❄️ | Cocaina Grezza")
        
        new_total = collected_today + 1
        
        success_embed = discord.Embed(
            title="✅ Raccolta completata",
            description=f"Hai raccolto 1gr di cocaina grezza, in totale oggi ne hai raccolti **{new_total}/{DAILY_LIMIT}**.\n\nL'item è stato aggiunto al tuo zaino.",
            color=discord.Color.light_grey()
        )
        success_embed.set_footer(text="Usa /invzaino per vedere il tuo inventario")
        
        await interaction.edit_original_response(embed=success_embed, view=self.view)

class CollectMarijuanaView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
        self.add_item(CollectMarijuanaButton())

class CollectCocainaView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot
        self.add_item(CollectCocainaButton())

def setup_marijuana_commands(bot: commands.Bot):
    
    @bot.tree.command(name="raccolta-marijuana", description="Raccogli marijuana")
    async def raccolta_marijuana(interaction: discord.Interaction):
        if not has_role(interaction, MARIJUANA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai il ruolo necessario per raccogliere marijuana!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if not await has_item_in_inventory(user_id, "✂️ | Forbici Raccolta Marijuana"):
            await interaction.response.send_message(
                "❌ Ti servono le **✂️ | Forbici Raccolta Marijuana** per raccogliere",
                ephemeral=True
            )
            return
        
        collected_today = await get_today_collection(user_id, "marijuana_collection")
        
        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere altra marijuana.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🌿 Raccolta Marijuana",
            description="Premi il pulsante sottostante per raccogliere 1gr di marijuana.",
            color=0x2ecc71
        )
        embed.add_field(
            name="📊 Progresso giornaliero",
            value=f"**{collected_today}/{DAILY_LIMIT}** raccolti oggi",
            inline=False
        )
        embed.set_footer(text="Limite giornaliero: 300gr")
        
        view = CollectMarijuanaView(bot)
        await interaction.response.send_message(embed=embed, view=view)

    @bot.tree.command(name="raccolta-cocaina", description="Raccogli cocaina grezza")
    async def raccolta_cocaina(interaction: discord.Interaction):
        if not has_role(interaction, COCAINA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai il ruolo necessario per raccogliere cocaina!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        if not await has_item_in_inventory(user_id, "⛏️ | Falce Raccolta Cocaina"):
            await interaction.response.send_message(
                "❌ Ti servono la **⛏️ | Falce Raccolta Cocaina** per raccogliere",
                ephemeral=True
            )
            return
        
        collected_today = await get_today_collection(user_id, "cocaina_collection")
        
        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere altra cocaina.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🥥 Raccolta Cocaina",
            description="Premi il pulsante sottostante per raccogliere 1gr di cocaina grezza.",
            color=discord.Color.light_grey()
        )
        embed.add_field(
            name="📊 Progresso giornaliero",
            value=f"**{collected_today}/{DAILY_LIMIT}** raccolti oggi",
            inline=False
        )
        embed.set_footer(text="Limite giornaliero: 300gr")
        
        view = CollectCocainaView(bot)
        await interaction.response.send_message(embed=embed, view=view)

    @bot.tree.command(name="smantellaauto", description="[SMANTELLATORE] Smantella un veicolo")
    @app_commands.describe(utente="L'utente che sta smantellando il veicolo")
    async def smantellaauto(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, SMANTELLATORE_ROLE_ID):
            await interaction.response.send_message(
                "❌ Devi avere il ruolo per smantellare le auto che ti darà il cartello!",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message("⏳ Smantellamento avviato, attendi 15 secondi...", ephemeral=True)
        
        embed_in_progress = discord.Embed(
            title="🔧 Smantellamento in corso...",
            description=f"**{interaction.user.name}** Sta smantellando un veicolo... 🔧",
            color=discord.Color.orange()
        )
        embed_in_progress.add_field(
            name="⏳ Tempo rimanente",
            value="Attendi **15 secondi** per completare l'operazione.",
            inline=False
        )
        embed_in_progress.set_footer(text=f"Oggi alle {datetime.now().strftime('%H:%M')}")
        
        message = await interaction.channel.send(embed=embed_in_progress)
        
        await asyncio.sleep(15)
        
        embed_completed = discord.Embed(
            title="✅ Smantellamento completato!",
            description=f"{utente.mention} ha terminato lo smantellamento del veicolo 🚗💥",
            color=discord.Color.green()
        )
        embed_completed.add_field(
            name="📦 Hai ottenuto i seguenti componenti che sono già stati aggiunti al tuo zaino 🎒:",
            value=(
                "• <:paraurti:1459842286052446416> **2x Paraurti**\n"
                "• <:cerchione:1459842536112918662> **4x Cerchioni**\n"
                "• 📻 **1x Autoradio**"
            ),
            inline=False
        )
        embed_completed.add_field(
            name="💰 Valore totale",
            value="Puoi rivendere questi pezzi al cartello",
            inline=False
        )
        embed_completed.set_footer(text=f"Oggi alle {datetime.now().strftime('%H:%M')}")
        
        await message.edit(embed=embed_completed)
        
        # AGGIUNGI GLI ITEM ALL'INVENTARIO - QUESTA ERA LA PARTE MANCANTE!
        await add_item_to_inventory(str(utente.id), "<:paraurti:1459842286052446416> | Paraurti")
        await add_item_to_inventory(str(utente.id), "<:paraurti:1459842286052446416> | Paraurti")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "<:cerchione:1459842536112918662> | Cerchioni")
        await add_item_to_inventory(str(utente.id), "📻 | Autoradio")
        
        # LOG
        

async def setup_marijuana_database():
    await init_marijuana_db()
