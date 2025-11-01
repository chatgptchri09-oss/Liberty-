import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
# Importiamo le costanti e le utility dal modulo commands_inventory per coerenza
from commands_inventory import DATABASE_NAME, LOG_CHANNEL_ID, RICETTE, PROGETTI_MAP, update_inventory 

# ===================================================================================
# FUNZIONI DATABASE UTILITY
# ===================================================================================

async def get_item_quantity_db(user_id: str, item_name: str) -> int:
    """Recupera la quantità di un item posseduta dall'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM user_inventory WHERE user_id = ? AND item_name = ?",
            (user_id, item_name)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    """Funzione di logging standard usata in tutti i tuoi comandi."""
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass

# ===================================================================================
# CLASSE VIEW PER LA SCELTA DEL PROGETTO (Menu di /crafting)
# ===================================================================================

class CraftingView(discord.ui.View):
    def __init__(self, bot: commands.Bot, nome_progetto: str, ricette_disponibili: List[str]):
        super().__init__(timeout=60)
        self.bot = bot
        self.nome_progetto = nome_progetto
        self.ricette_disponibili = ricette_disponibili
        self.add_item(self.create_select_menu())

    def create_select_menu(self):
        options = [
            discord.SelectOption(label=ricetta, value=ricetta)
            for ricetta in self.ricette_disponibili
        ]
        
        select = discord.ui.Select(
            placeholder="Scegli la ricetta da craftare...",
            options=options,
            custom_id="crafting_select"
        )
        select.callback = self.select_callback
        return select

    async def select_callback(self, interaction: discord.Interaction):
        item_da_craftare = interaction.data['values'][0]
        
        # 1. DEFER CRITICO: Risponde immediatamente
        await interaction.response.defer(ephemeral=True)

        # 2. LOGICA DI CRAFTING
        await self.execute_crafting(interaction, item_da_craftare)
        self.stop() # Ferma la View

    async def execute_crafting(self, interaction: discord.Interaction, item_da_craftare: str):
        user_id = str(interaction.user.id)
        ricetta = RICETTE.get(item_da_craftare)
        
        # 2.1 Verifica Materiali
        materiali_mancanti = {}
        for materiale, quantita_richiesta in ricetta.items():
            quantita_posseduta = await get_item_quantity_db(user_id, materiale)
            if quantita_posseduta < quantita_richiesta:
                materiali_mancanti[materiale] = quantita_richiesta - quantita_posseduta

        if materiali_mancanti:
            mancanze = [f"{q}x {m}" for m, q in materiali_mancanti.items()]
            await interaction.followup.send(
                f"❌ **Crafting fallito!** Ti mancano i seguenti componenti: {', '.join(mancanze)}.", 
                ephemeral=True
            )
            return

        # 2.2 Sottrazione Materiali (usa update_inventory importata)
        componenti_consumati = ricetta
        for materiale, quantita in componenti_consumati.items():
            await update_inventory(user_id, materiale, quantita, mode='remove')

        # 2.3 Simulazione del processo con barra di progresso
        embed_in_progress = discord.Embed(
            title="🛠️ **Crafting in corso**",
            description=f"{item_da_craftare}\n\nPreparazione banco **\[Progress bar - 8%\]**",
            color=discord.Color.orange()
        )
        message = await interaction.edit_original_response(embed=embed_in_progress, view=None)

        await asyncio.sleep(1.0) 
        embed_in_progress.description = f"{item_da_craftare}\n\nTaratura & finitura **\[Progress bar - 58%\]**"
        await message.edit(embed=embed_in_progress)

        await asyncio.sleep(1.0)
        embed_in_progress.description = f"{item_da_craftare}\n\nVerifica qualità **\[Progress bar - 100%\]**"
        await message.edit(embed=embed_in_progress)
        
        await asyncio.sleep(0.5)

        # 2.4 Aggiunta Item Craftato
        await update_inventory(user_id, item_da_craftare, 1, mode='add')

        # 2.5 Risposta Finale
        consumati_list = [f"*-{q}x {m}*" for m, q in componenti_consumati.items()]
        final_embed = discord.Embed(
            title="✅ **Craft completato**",
            description=f"Hai craftato **1x** 🔫 **{item_da_craftare}.**",
            color=discord.Color.green()
        )
        final_embed.add_field(name="Componenti consumati:", value="\n".join(consumati_list), inline=False)
        final_embed.set_footer(text=f"Oggi alle {datetime.now().strftime('%H:%M')}")
        
        await message.edit(embed=final_embed)
        
        await log_command(
            self.bot, 
            LOG_CHANNEL_ID, 
            f"🛠️ {interaction.user.mention} ha craftato 1x {item_da_craftare} ({self.nome_progetto})"
        )

# ===================================================================================
# COMANDO PRINCIPALE: /crafting
# ===================================================================================

def setup_crafting_commands(bot: commands.Bot):
    
    @bot.tree.command(name="crafting", description="Apri il menu di crafting per creare oggetti")
    @app_commands.describe(progetto_scelto="Scegli il progetto che vuoi usare")
    @app_commands.choices(progetto_scelto=[
        app_commands.Choice(name="Pistole Legali (FDO/FFA)", value="Progetto Pistole Legali"),
        app_commands.Choice(name="Armi Lunghe Legali", value="Progetto Armi Lunghe Legali"),
        app_commands.Choice(name="Progetto Protezioni", value="Progetto Protezioni"),
        app_commands.Choice(name="Armi Lunghe Illegali", value="Progetto Armi Lunghe Illegali"),
    ])
    async def crafting(interaction: discord.Interaction, progetto_scelto: app_commands.Choice):
        user_id = str(interaction.user.id)
        nome_progetto = progetto_scelto.value

        # 1. Controllo possesso del progetto
        quantita_progetto = await get_item_quantity_db(user_id, nome_progetto)
        if quantita_progetto == 0:
            await interaction.response.send_message(
                f"❌ Non puoi usare il progetto **{nome_progetto}** perché non lo possiedi nello zaino!",
                ephemeral=True
            )
            return

        # 2. Identificazione ricette disponibili
        ricette_disponibili = PROGETTI_MAP.get(nome_progetto, [])
        if not ricette_disponibili:
             await interaction.response.send_message(
                f"❌ Le ricette per **{nome_progetto}** non sono state definite nel codice del bot.",
                ephemeral=True
            )
             return
        
        # 3. Invio del menu di selezione
        view = CraftingView(bot, nome_progetto, ricette_disponibili)

        embed = discord.Embed(
            title=f"🔫 {nome_progetto} – Scegli la ricetta",
            description="Seleziona la ricetta che vuoi fabbricare dal menu a tendina. Hai **60 secondi** per scegliere.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"🛠️ {interaction.user.mention} ha aperto il menu crafting ({nome_progetto})")
