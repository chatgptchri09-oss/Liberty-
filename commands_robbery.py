import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from datetime import datetime

POLICE_ROLE_ID = 1415093546549248040

# Configurazione rapine
ROBBERIES = {
    "Market": {
        "emoji": "🏪",
        "robbers": "1/2",
        "hostages": "0",
        "cops": "2/3",
        "helmets": "No",
        "gap": "Solo polizia",
        "weapons": "Armi Bianche / Pistole",
        "reward": "30.000$",
        "lockpick_time": 4,  # minuti
        "color": discord.Color.orange()
    },
    "Negozio Vestiti": {
        "emoji": "👕",
        "robbers": "3/4",
        "hostages": "0",
        "cops": "5/6",
        "helmets": "No",
        "gap": "No",
        "weapons": "Pistole / Armi Automatiche",
        "reward": "150.000$",
        "lockpick_time": 5,
        "color": discord.Color.blue()
    },
    "Armeria": {
        "emoji": "🔫",
        "robbers": "3/4",
        "hostages": "0",
        "cops": "5/6",
        "helmets": "No",
        "gap": "No",
        "weapons": "Pistole / Mitra",
        "reward": "70.000$ + 2 Pistole + 1 Fucile a pompa",
        "lockpick_time": 7,
        "color": discord.Color.red()
    },
    "Pacific Standard": {
        "emoji": "🏦",
        "robbers": "4-7",
        "hostages": "4",
        "cops": "8",
        "helmets": "Si",
        "gap": "Si",
        "weapons": "TUTTE",
        "reward": "2.000.000$",
        "lockpick_time": 10,
        "color": discord.Color.gold()
    }
}


def setup_robbery_commands(bot: commands.Bot):
    
    async def robbery_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        choices = [
            app_commands.Choice(name="🏪 Rapina Market", value="Market"),
            app_commands.Choice(name="👕 Rapina Negozio Vestiti", value="Negozio Vestiti"),
            app_commands.Choice(name="🔫 Rapina Armeria", value="Armeria"),
            app_commands.Choice(name="🏦 Rapina Pacific Standard", value="Pacific Standard")
        ]
        
        if current:
            return [choice for choice in choices if current.lower() in choice.name.lower()]
        return choices
    
    @bot.tree.command(name="rapina", description="Avvia una rapina")
    @app_commands.describe(tipo="Seleziona il tipo di rapina")
    @app_commands.autocomplete(tipo=robbery_autocomplete)
    async def rapina(interaction: discord.Interaction, tipo: str):
        
        if tipo not in ROBBERIES:
            await interaction.response.send_message("❌ Tipo di rapina non valido!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        robbery_data = ROBBERIES[tipo]
        
        # Tag ruolo polizia
        police_role = interaction.guild.get_role(POLICE_ROLE_ID)
        police_mention = police_role.mention if police_role else f"<@&{POLICE_ROLE_ID}>"
        
        # PRIMO EMBED - Rapina Avviata
        now = datetime.now()
        timestamp = now.strftime("%d/%m/%y, %H:%M")
        
        start_embed = discord.Embed(
            title=f"🚨 Rapina {tipo} - Avviata",
            color=robbery_data["color"]
        )
        start_embed.add_field(
            name="👤 Rapinatore:",
            value=interaction.user.mention,
            inline=False
        )
        start_embed.add_field(
            name="**Dettagli**:",
            value=(
                f"• **Rapinatori**: {robbery_data['robbers']}\n"
                f"• **Ostaggi**: {robbery_data['hostages']}\n"
                f"• **Poliziotti**: {robbery_data['cops']}\n"
                f"• **Caschi**: {robbery_data['helmets']}\n"
                f"• **G.A.P**: {robbery_data['gap']}\n"
                f"• **Armi**: {robbery_data['weapons']}\n"
                f"• **Guadagno**: {robbery_data['reward']}"
            ),
            inline=False
        )
        start_embed.set_footer(text=timestamp)
        
        # Invia primo embed con tag polizia
        await interaction.followup.send(content=police_mention, embed=start_embed)
        
        # SECONDO EMBED - Scassinamento in corso
        lockpick_embed = discord.Embed(
            title="🔧 Scassinamento in corso...",
            color=discord.Color.yellow()
        )
        lockpick_embed.add_field(
            name="Durata stimata:",
            value=f"**{robbery_data['lockpick_time']} min**",
            inline=False
        )
        
        # Barra di caricamento
        progress_bar = "█" * 20
        lockpick_embed.add_field(
            name=f"{robbery_data['emoji']} Progress",
            value=f"{progress_bar} **100%**",
            inline=False
        )
        
        now2 = datetime.now()
        timestamp2 = now2.strftime("%d/%m/%y, %H:%M")
        lockpick_embed.set_footer(text=timestamp2)
        
        # Invia secondo embed
        await interaction.channel.send(embed=lockpick_embed)
        
        # Aspetta il tempo di scassinamento (in secondi)
        await asyncio.sleep(robbery_data['lockpick_time'] * 60)
        
        # TERZO EMBED - Rapina Completata
        complete_embed = discord.Embed(
            title="✅ Rapina completata",
            color=discord.Color.green()
        )
        complete_embed.add_field(
            name=f"**Rapina {tipo}** conclusa da {interaction.user.mention}.",
            value=f"💰 **Bottino da accreditare**: {robbery_data['reward']}",
            inline=False
        )
        complete_embed.add_field(
            name="Avviso:",
            value="utilizzo improprio o fuori regolamento comporta sanzioni.",
            inline=False
        )
        
        now3 = datetime.now()
        timestamp3 = now3.strftime("%d/%m/%y, %H:%M")
        complete_embed.set_footer(text=timestamp3)
        
        # Invia terzo embed
        await interaction.channel.send(embed=complete_embed)
