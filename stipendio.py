import discord
from discord import app_commands
from discord.ext import commands

LOG_CHANNEL_ID = 1415297578022604850

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

def setup_salary_commands(bot: commands.Bot):

    class StipendioView(discord.ui.View):
        """Puoi aggiungere bottoni per approvazione se vuoi."""
        def __init__(self, bot, user_id: str, amount: int):
            super().__init__(timeout=None)
            self.bot = bot
            self.user_id = user_id
            self.amount = amount

    class RichiestaStipendioModal(discord.ui.Modal, title="💰 Richiesta Stipendio"):
        busta_paga = discord.ui.TextInput(label="Busta Paga", placeholder="Importo in $", required=True)

        def __init__(self, bot, lavoro: discord.Role, allegato: discord.Attachment = None):
            super().__init__()
            self.bot = bot
            self.lavoro = lavoro
            self.allegato = allegato  # Discord Attachment opzionale

        async def on_submit(self, interaction: discord.Interaction):
            # ✅ Validazione importo
            try:
                amount = int(self.busta_paga.value)
                if amount <= 0:
                    await interaction.response.send_message("❌ L'importo deve essere maggiore di 0!", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ Importo non valido!", ephemeral=True)
                return

            embed = discord.Embed(
                title="💰 𝐑𝐈𝐂𝐇𝐈𝐄𝐒𝐓𝐀 𝐒𝐓𝐈𝐏𝐄𝐍𝐃𝐈𝐎",
                color=discord.Color.gold()
            )
            embed.add_field(name="👤 𝐔𝐓𝐄𝐍𝐓𝐄", value=interaction.user.mention, inline=False)
            embed.add_field(name="📆 𝐋𝐀𝐕𝐎𝐑𝐎 𝐒𝐕𝐎𝐋𝐓𝐎", value=self.lavoro.mention, inline=False)
            embed.add_field(name="📥 𝐁𝐔𝐒𝐓𝐀 𝐏𝐀𝐆𝐀", value=f"${amount:,}", inline=False)

            # ✅ Se c'è allegato e immagine, mostra nell'embed
            if self.allegato and self.allegato.content_type and self.allegato.content_type.startswith("image/"):
                embed.set_image(url=self.allegato.url)

            view = StipendioView(self.bot, str(interaction.user.id), amount)
            await interaction.response.send_message(embed=embed, view=view)

    @bot.tree.command(name="richiesta-stipendio", description="Richiedi uno stipendio")
    @app_commands.describe(
        lavoro_svolto="Il ruolo del lavoro svolto",
        allegato="Carica una prova (immagine, facoltativo)"
    )
    async def richiesta_stipendio(interaction: discord.Interaction, lavoro_svolto: discord.Role, allegato: discord.Attachment = None):
        # Controllo che l’utente abbia il ruolo per cui richiede lo stipendio
        if lavoro_svolto not in interaction.user.roles:
            await interaction.response.send_message(
                f"❌ Non puoi richiedere uno stipendio per **{lavoro_svolto.name}** perché non hai questo ruolo!",
                ephemeral=True
            )
            await log_command(bot, LOG_CHANNEL_ID, f"⚠️ {interaction.user.mention} ha tentato richiesta stipendio per {lavoro_svolto.name} senza avere il ruolo")
            return

        modal = RichiestaStipendioModal(bot, lavoro_svolto, allegato)
        await interaction.response.send_modal(modal)

async def log_command(bot, channel_id: int, message: str):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            await channel.send(message)
    except:
        pass
