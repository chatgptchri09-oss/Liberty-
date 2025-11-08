import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import database

LFD_ROLE_ID = 1415093546549248040
ARREST_CHANNEL_ID = 1436347936635097179

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

class ArrestModal(discord.ui.Modal, title="🚔 Arresto"):
    name_input = discord.ui.TextInput(
        label="Nome Arrestato",
        placeholder="Inserisci il nome",
        required=True
    )
    surname_input = discord.ui.TextInput(
        label="Cognome Arrestato",
        placeholder="Inserisci il cognome",
        required=True
    )
    age_input = discord.ui.TextInput(
        label="Età",
        placeholder="Inserisci l'età",
        required=True,
        max_length=3
    )
    residence_input = discord.ui.TextInput(
        label="Residenza",
        placeholder="Inserisci la residenza (se presente)",
        required=False
    )
    reason_input = discord.ui.TextInput(
        label="Motivo arresto",
        placeholder="Descrivi il motivo dell'arresto",
        style=discord.TextStyle.paragraph,
        required=True
    )
    penalty_input = discord.ui.TextInput(
        label="Pena",
        placeholder="Inserisci la pena",
        required=True
    )

    def __init__(self, bot, officer: discord.Member):
        super().__init__()
        self.bot = bot
        self.officer = officer

    async def on_submit(self, interaction: discord.Interaction):
        await database.create_arrest(
            str(self.officer.id),
            self.officer.display_name,
            self.name_input.value,
            self.surname_input.value,
            self.age_input.value,
            self.residence_input.value or "Non specificata",
            self.reason_input.value,
            self.penalty_input.value
        )
        
        embed = discord.Embed(
            title="🚔 ARRESTO EFFETTUATO",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="👮 Agente", value=self.officer.mention, inline=False)
        embed.add_field(name="👤 Nome", value=self.name_input.value, inline=True)
        embed.add_field(name="👤 Cognome", value=self.surname_input.value, inline=True)
        embed.add_field(name="🎂 Età", value=self.age_input.value, inline=True)
        
        if self.residence_input.value:
            embed.add_field(name="🏠 Residenza", value=self.residence_input.value, inline=False)
        
        embed.add_field(name="⚖️ Motivo arresto", value=self.reason_input.value, inline=False)
        embed.add_field(name="⏱️ Pena", value=self.penalty_input.value, inline=False)
        embed.timestamp = datetime.now()
        
        try:
            channel = self.bot.get_channel(ARREST_CHANNEL_ID)
            if channel and hasattr(channel, 'send'):
                await channel.send(embed=embed)
                await interaction.response.send_message(
                    f"<a:spunta:1431937738256552036> Arresto registrato con successo!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "<a:annulla:1431940396635652146> Errore: canale arresti non trovato!",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                f"<a:annulla:1431940396635652146> Errore durante l'invio dell'arresto: {str(e)}",
                ephemeral=True
            )

def setup_arrest_commands(bot: commands.Bot):
    
    @bot.tree.command(name="arresto", description="[LFD] Registra un arresto")
    async def arresto(interaction: discord.Interaction):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message(
                "<a:annulla:1431940396635652146> Solo i LFD possono usare questo comando!",
                ephemeral=True
            )
            return
        
        modal = ArrestModal(bot, interaction.user)
        await interaction.response.send_modal(modal)
