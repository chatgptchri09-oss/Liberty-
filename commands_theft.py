import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from datetime import datetime
import random

POLICE_ROLE_ID = 1415093546549248040

# Lista di auto GTA V
GTA_CARS = [
    "Torero XO",
    "Zentorno",
    "Adder",
    "Entity XXR",
    "T20",
    "Osiris",
    "Reaper",
    "Turismo R",
    "Infernus",
    "Vacca",
    "Bullet",
    "Banshee 900R",
    "Itali GTO",
    "Krieger",
    "Emerus",
    "Vagner",
    "XA-21",
    "Tempesta",
    "Nero Custom",
    "Tyrus",
    "GP1",
    "811",
    "Pfister Neon",
    "Autarch",
    "Visione",
    "Taipan",
    "Tezeract",
    "Thrax",
    "Deveste Eight",
    "S80RR"
]

# Configurazione furti
THEFTS = {
    "Auto": {
        "emoji": "🚗",
        "title": "Furto Auto",
        "actions": [
            "Scasso",
            "Ingresso",
            "Collega i fili",
            "Fuga"
        ],
        "action_emoji": "🔧",
        "color": discord.Color.blue()
    },
    "Appartamento": {
        "emoji": "🏠",
        "title": "Furto Appartamento",
        "actions": [
            "Scasso",
            "Ingresso",
            "Perlustrazione",
            "Raccolta",
            "Fuga"
        ],
        "loot": [
            "💻 | Laptop Da Gaming",
            "🍺 | Vaso Di Cristallo Di Murano (Illegale)",
            "💍 | Collana D'oro (Illegale)"
        ],
        "action_emoji": "🔧",
        "color": discord.Color.orange()
    },
    "Villa": {
        "emoji": "🏡",
        "title": "Furto Villa",
        "actions": [
            "Scasso",
            "Ingresso",
            "Perlustrazione",
            "Raccolta",
            "Fuga"
        ],
        "loot": [
            "🖼️ | Quadro D'autore",
            "💎 | Diamanti",
            "⌚ | Rolex",
            "💰 | Cassaforte con 50.000$"
        ],
        "action_emoji": "🔧",
        "color": discord.Color.purple()
    }
}


def setup_theft_commands(bot: commands.Bot):
    
    async def theft_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        choices = [
            app_commands.Choice(name="🚗 Furto Auto", value="Auto"),
            app_commands.Choice(name="🏠 Furto Appartamento", value="Appartamento"),
            app_commands.Choice(name="🏡 Furto Villa", value="Villa")
        ]
        
        if current:
            return [choice for choice in choices if current.lower() in choice.name.lower()]
        return choices
    
    @bot.tree.command(name="furto", description="Esegui un furto")
    @app_commands.describe(tipo="Seleziona il tipo di furto")
    @app_commands.autocomplete(tipo=theft_autocomplete)
    async def furto(interaction: discord.Interaction, tipo: str):
        
        if tipo not in THEFTS:
            await interaction.response.send_message("❌ Tipo di furto non valido!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        theft_data = THEFTS[tipo]
        
        # Tag ruolo polizia
        police_role = interaction.guild.get_role(POLICE_ROLE_ID)
        police_mention = police_role.mention if police_role else f"<@&{POLICE_ROLE_ID}>"
        
        # Invia tag polizia
        await interaction.followup.send(content=police_mention)
        
        # Per ogni azione, crea un embed
        total_actions = len(theft_data["actions"])
        
        for idx, action in enumerate(theft_data["actions"], 1):
            now = datetime.now()
            timestamp = now.strftime("%d/%m/%y, %H:%M")
            
            action_embed = discord.Embed(
                title="🛠️ Sistema Furti Liberty",
                color=theft_data["color"]
            )
            action_embed.add_field(
                name=f"{theft_data['action_emoji']} {interaction.user.mention} esegue: **{action}...** ({idx}/{total_actions})",
                value="\u200b",
                inline=False
            )
            action_embed.set_footer(text=timestamp)
            
            await interaction.channel.send(embed=action_embed)
            
            # Aspetta 1 minuto tra ogni azione
            if idx < total_actions:
                await asyncio.sleep(60)
        
        # Aspetta 1 minuto prima dell'embed finale
        await asyncio.sleep(60)
        
        # EMBED FINALE - Furto Completato
        now = datetime.now()
        timestamp = now.strftime("%d/%m/%y, %H:%M")
        
        complete_embed = discord.Embed(
            color=discord.Color.green()
        )
        
        # Diversifica in base al tipo di furto
        if tipo == "Auto":
            # Scegli una macchina casuale
            stolen_car = random.choice(GTA_CARS)
            complete_embed.title = "🚗 Furto Auto Completato"
            complete_embed.add_field(
                name="Hai rubato:",
                value=f"• 🚗 | {stolen_car}",
                inline=False
            )
        
        elif tipo == "Appartamento":
            complete_embed.title = "🏠 Furto Appartamento Completato"
            loot_text = "\n".join([f"• {item}" for item in theft_data["loot"]])
            complete_embed.add_field(
                name="Hai rubato:",
                value=loot_text,
                inline=False
            )
        
        elif tipo == "Villa":
            complete_embed.title = "🏡 Furto Villa Completato"
            loot_text = "\n".join([f"• {item}" for item in theft_data["loot"]])
            complete_embed.add_field(
                name="Hai rubato:",
                value=loot_text,
                inline=False
            )
        
        complete_embed.set_footer(text=timestamp)
        
        # Tag utente sopra l'embed finale
        await interaction.channel.send(content=interaction.user.mention, embed=complete_embed)
