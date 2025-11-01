import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os
import json
import asyncio

# ===================================================================================
# COSTANTI E FUNZIONI DI SUPPORTO (Derivate da altri tuoi file)
# ===================================================================================

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850 
STAFF_ROLE_ID = 1414738761207517214 
CRAFTING_CHANNEL_ID = 123456789012345678 # ID placeholder, sostituisci con il canale crafting

# Funzioni di supporto (necessarie per i comandi)
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
    except Exception:
        pass

async def get_user_inventory(user_id: str):
    """Recupera l'inventario dell'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT item_name, quantity FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()

# Assumiamo che questa funzione sia definita nel tuo database.py o altrove
async def update_inventory(user_id: str, item_name: str, quantity: int, mode: str = 'add'):
    """Aggiorna l'inventario dell'utente. (Placeholder)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if mode == 'add':
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + excluded.quantity",
                (user_id, item_name, quantity)
            )
        elif mode == 'remove':
            # Logica complessa, qui usiamo un semplice UPDATE che fallirà se la quantità è < 0
            await db.execute(
                "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                (quantity, user_id, item_name)
            )
            # Pulizia degli item a zero
            await db.execute("DELETE FROM inventory WHERE user_id = ? AND quantity <= 0", (user_id,))

        await db.commit()


# ===================================================================================
# 🚨 FUNZIONE DI SETUP (TUTTO QUI SOTTO È STATO INDENTATO) 🚨
# ===================================================================================

def setup_crafting_commands(bot: commands.Bot):
    """Registra i comandi di crafting al tree del bot."""

    # ===================================================
    # COMANDO: /crafting (CORRETTO PER TYPERROR E INDENTAZIONE)
    # ===================================================
    @bot.tree.command(name="crafting", description="Apri il menu di crafting per creare oggetti")
    @app_commands.describe(progetto_scelto="Scegli il progetto che vuoi usare")
    @app_commands.choices(progetto_scelto=[
        app_commands.Choice(name="Pistole Legali (FDO/FFA)", value="Progetto Pistole Legali"),
        app_commands.Choice(name="Armi Lunghe Legali", value="Progetto Armi Lunghe Legali"),
        app_commands.Choice(name="Progetto Protezioni", value="Progetto Protezioni"),
        app_commands.Choice(name="Armi Lunghe Illegali", value="Progetto Armi Lunghe Illegali"),
    ])
    async def crafting(interaction: discord.Interaction, progetto_scelto: str): # <--- CORREZIONE: str anziché app_commands.Choice
        
        # 1. Controllo Canale (Aggiunto per sicurezza logica)
        if interaction.channel_id != CRAFTING_CHANNEL_ID:
            await interaction.response.send_message(
                f"❌ Questo comando può essere usato solo nel canale di <#{CRAFTING_CHANNEL_ID}>.", 
                ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        nome_progetto = progetto_scelto # Non serve .value perché è già str
        
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Logica di Esempio (DA COMPLETARE CON LE TUE RICETTE REALI)
        
        # 2. Recupero Inventario
        inventory_items = await get_user_inventory(user_id)
        inventory_dict = {item_name: quantity for item_name, quantity in inventory_items}
        
        # 3. Logica per la Ricetta (ESEMPIO!)
        if nome_progetto == "Progetto Pistole Legali":
            # Requisiti Esempio: 5x Ferro, 2x Kit Assemblaggio
            required_items = {"Ferro": 5, "Kit Assemblaggio": 2}
            output_item = "Pistola Legale"
            output_quantity = 1
        elif nome_progetto == "Progetto Protezioni":
            # Requisiti Esempio: 10x Tessuto, 3x Piastre
            required_items = {"Tessuto": 10, "Piastre": 3}
            output_item = "Giubbotto Antiproiettile"
            output_quantity = 1
        else:
            await interaction.followup.send("❌ Progetto non riconosciuto o non implementato.", ephemeral=True)
            return
            
        # 4. Controllo Requisiti
        can_craft = True
        missing_list = []
        for item, required_q in required_items.items():
            if inventory_dict.get(item, 0) < required_q:
                can_craft = False
                missing_list.append(f"{required_q}x {item} (hai {inventory_dict.get(item, 0)})")
                
        if not can_craft:
            missing_text = "\n".join(missing_list)
            await interaction.followup.send(
                f"❌ Non hai tutti i materiali necessari per craftare **{output_item}**!\n"
                f"Ti mancano:\n{missing_text}",
                ephemeral=True
            )
            return
            
        # 5. Esecuzione Crafting: Rimozione Materiali e Aggiunta Oggetto
        try:
            for item, required_q in required_items.items():
                await update_inventory(user_id, item, required_q, mode='remove')
                
            await update_inventory(user_id, output_item, output_quantity, mode='add')
            
            # 6. Risposta Successo
            await interaction.followup.send(
                f"✅ Hai craftato **{output_quantity}x {output_item}** usando il progetto **{nome_progetto}**!", 
                ephemeral=True
            )
            
            await log_command(
                bot, 
                LOG_CHANNEL_ID, 
                f"🛠️ {interaction.user.mention} ha craftato {output_quantity}x {output_item} (Progetto: {nome_progetto})"
            )
            
        except Exception as e:
            print(f"Errore durante il crafting: {e}")
            await interaction.followup.send("❌ Si è verificato un errore durante il crafting. Contatta lo staff.", ephemeral=True)
            await log_command(bot, LOG_CHANNEL_ID, f"❌ Errore critico nel crafting di {interaction.user.mention}: {e}")
