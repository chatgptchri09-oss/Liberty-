import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, time
import asyncio

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
MARIJUANA_ROLE_ID = 1431629412339548320

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
        await db.commit()

async def get_today_collection(user_id: str):
    """Ottieni il numero di raccolte odierne per un utente"""
    today = datetime.now().date().isoformat()
    
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT collected_today, last_collection_date FROM marijuana_collection WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
        
        if not result:
            # Prima raccolta in assoluto
            await db.execute(
                "INSERT INTO marijuana_collection (user_id, collected_today, last_collection_date) VALUES (?, ?, ?)",
                (user_id, 0, today)
            )
            await db.commit()
            return 0
        
        collected, last_date = result
        
        # Se la data è diversa da oggi, resetta il contatore
        if last_date != today:
            await db.execute(
                "UPDATE marijuana_collection SET collected_today = 0, last_collection_date = ? WHERE user_id = ?",
                (today, user_id)
            )
            await db.commit()
            return 0
        
        return collected

async def increment_collection(user_id: str):
    """Incrementa il contatore di raccolta giornaliera"""
    today = datetime.now().date().isoformat()
    
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE marijuana_collection SET collected_today = collected_today + 1, last_collection_date = ? WHERE user_id = ?",
            (today, user_id)
        )
        await db.commit()

async def add_marijuana_to_inventory(user_id: str):
    """Aggiungi 1gr di marijuana all'inventario dell'utente"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Controlla se l'utente ha già marijuana nell'inventario
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?",
            (user_id, "🌿 | Marijuana")
        ) as cursor:
            result = await cursor.fetchone()
        
        if result:
            # Incrementa la quantità
            new_quantity = result[0] + 1
            await db.execute(
                "UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?",
                (new_quantity, user_id, "🌿 | Marijuana")
            )
        else:
            # Crea nuovo item nell'inventario
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)",
                (user_id, "🌿 | Marijuana", 1)
            )
        
        await db.commit()

class CollectButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="🌿 Raccogli",
            custom_id="collect_marijuana"
        )
    
    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        # Controlla se l'utente ha il ruolo
        if not has_role(interaction, MARIJUANA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai il ruolo necessario per raccogliere marijuana!",
                ephemeral=True
            )
            return
        
        # Controlla il limite giornaliero
        collected_today = await get_today_collection(user_id)
        
        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere altra marijuana.",
                ephemeral=True
            )
            return
        
        # Incrementa il contatore
        await increment_collection(user_id)
        
        # Aggiungi marijuana all'inventario
        await add_marijuana_to_inventory(user_id)
        
        # Nuovo totale
        new_total = collected_today + 1
        
        # Aggiorna l'embed
        success_embed = discord.Embed(
            title="✅ Raccolta completata",
            description=f"Hai raccolto 1gr di marijuana, in totale oggi ne hai raccolti **{new_total}/{DAILY_LIMIT}**.\n\nL'item è stato aggiunto al tuo zaino.",
            color=0x2ecc71
        )
        success_embed.set_footer(text="Usa /invzaino per vedere il tuo inventario")
        
        # Disabilita il pulsante
        for item in self.view.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=success_embed, view=self.view)
        
        # LOG
        
class CollectView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=300)  # 5 minuti di timeout
        self.bot = bot
        self.add_item(CollectButton())

def setup_marijuana_commands(bot: commands.Bot):
    
    @bot.tree.command(name="raccogli-marijuana", description="Raccogli marijuana")
    async def raccolta(interaction: discord.Interaction):
        # Controlla se l'utente ha il ruolo
        if not has_role(interaction, MARIJUANA_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai il ruolo necessario per raccogliere marijuana!",
                ephemeral=True
            )
            return
        
        user_id = str(interaction.user.id)
        
        # Controlla il limite giornaliero
        collected_today = await get_today_collection(user_id)
        
        if collected_today >= DAILY_LIMIT:
            await interaction.response.send_message(
                f"❌ Hai raggiunto il limite giornaliero di raccolta! ({DAILY_LIMIT}/{DAILY_LIMIT})\n"
                "Torna domani per raccogliere altra marijuana.",
                ephemeral=True
            )
            return
        
        # Crea l'embed iniziale
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
        
        # Crea la view con il pulsante
        view = CollectView(bot)
        
        await interaction.response.send_message(embed=embed, view=view)

# Funzione da chiamare all'avvio del bot per inizializzare il database
async def setup_marijuana_database():
    await init_marijuana_db()
