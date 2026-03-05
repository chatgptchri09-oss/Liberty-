import discord
from discord import app_commands
import database
import random

LOG_CHANNEL_ID = 1415297578022604850

def setup_theft_commands(bot):

    @bot.tree.command(name="furto", description="Tenta un furto furtivo nel Far West (azione illegale)")
    @app_commands.describe(bersaglio="Cosa vuoi rubare", luogo="Dove")
    async def furto(interaction: discord.Interaction, bersaglio: str, luogo: str):
        successo = random.random() < 0.65
        bottino  = random.randint(20, 200) if successo else 0

        if successo:
            user = await database.get_user(str(interaction.user.id))
            await database.update_balance(str(interaction.user.id), cash=user["cash"] + bottino)
            color = discord.Color(0x556B2F)
            titolo = "🤫 Furto Riuscito"
            desc = (
                f"*{interaction.user.display_name} ruba furtivamente **{bersaglio}** a **{luogo}**.*\n\n"
                f"**Guadagno: ${bottino:,}**"
            )
        else:
            color = discord.Color.red()
            titolo = "❌ Furto Fallito"
            desc = (
                f"*{interaction.user.display_name} tenta di rubare **{bersaglio}** a **{luogo}**...*\n\n"
                f"*Qualcuno ti vede. Ti dileguhi nel nulla senza nulla.*"
            )

        embed = discord.Embed(title=titolo, description=desc, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Crimine")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="raccolta-marijuana", description="Raccogli erba selvatica nel Far West (azione illegale)")
    @app_commands.describe(luogo="Dove raccogli")
    async def raccolta_marijuana(interaction: discord.Interaction, luogo: str):
        quantita = random.randint(1, 5)
        user = await database.get_user(str(interaction.user.id))

        # Calo fame/sete per la fatica
        new_h = max(0, user["hunger"] - random.randint(4, 8))
        new_t = max(0, user["thirst"] - random.randint(4, 8))
        await database.update_hunger_thirst(str(interaction.user.id), hunger=new_h, thirst=new_t)
        await database.add_item(str(interaction.user.id), "🌿 • Erba Selvatica", quantita)

        embed = discord.Embed(
            title="🌿 Raccolta Completata",
            description=f"*{interaction.user.display_name} raccoglie erba selvatica a **{luogo}**.*",
            color=discord.Color(0x556B2F),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📦 Raccolto", value=f"🌿 • Erba Selvatica x{quantita}", inline=True)
        embed.add_field(name="🍔 Fame",     value=f"**{new_h}%**",                     inline=True)
        embed.add_field(name="💦 Sete",     value=f"**{new_t}%**",                     inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Raccolta")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="raccolta-cocaina", description="Raccogli piante rare nel Far West (azione illegale)")
    @app_commands.describe(luogo="Dove raccogli")
    async def raccolta_cocaina(interaction: discord.Interaction, luogo: str):
        quantita = random.randint(1, 3)
        user = await database.get_user(str(interaction.user.id))

        new_h = max(0, user["hunger"] - random.randint(5, 10))
        new_t = max(0, user["thirst"] - random.randint(5, 10))
        await database.update_hunger_thirst(str(interaction.user.id), hunger=new_h, thirst=new_t)
        await database.add_item(str(interaction.user.id), "🪴 • Pianta Rara", quantita)

        embed = discord.Embed(
            title="🪴 Raccolta Completata",
            description=f"*{interaction.user.display_name} raccoglie piante rare a **{luogo}**.*",
            color=discord.Color(0x556B2F),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📦 Raccolto", value=f"🪴 • Pianta Rara x{quantita}", inline=True)
        embed.add_field(name="🍔 Fame",     value=f"**{new_h}%**",                  inline=True)
        embed.add_field(name="💦 Sete",     value=f"**{new_t}%**",                  inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Raccolta")
        await interaction.response.send_message(embed=embed)
