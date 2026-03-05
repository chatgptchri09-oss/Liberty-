import discord
from discord import app_commands
import database
from datetime import datetime

LOG_CHANNEL_ID  = 1415297578022604850
STAFF_ROLE_ID   = 1414738761207517214
CHIAVE_ROLE_ID  = 1414735564632231988

COMPANY_LOG_CHANNELS = {
    "Dottore": 1424111086537281567,
    "Armeria": 1424111403228205147,
    "Stalla":  1424111522107490405,
    "Saloon":  1424111628374511729,
    "Officina":1424111759559495760,
    "Contrabbando": 1424111925360463882,
    "Diligenza": 1424112194139984003,
    "Sceriffo": 1424007218554208316,
}

def has_staff(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in (STAFF_ROLE_ID, CHIAVE_ROLE_ID) for r in interaction.user.roles)

async def log_embed(bot, channel_id: int, embed: discord.Embed):
    try:
        ch = bot.get_channel(channel_id)
        if ch:
            await ch.send(embed=embed)
    except Exception:
        pass

def setup_admin_commands(bot):

    @bot.tree.command(name="add-money", description="[STAFF] Aggiungi denaro a un giocatore")
    @app_commands.describe(giocatore="Il giocatore", importo="Importo da aggiungere", dove="Contanti o banca")
    @app_commands.choices(dove=[
        app_commands.Choice(name="💵 Contanti", value="cash"),
        app_commands.Choice(name="🏦 Banca",    value="bank"),
    ])
    async def add_money(interaction: discord.Interaction, giocatore: discord.Member, importo: int, dove: str = "cash"):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        user = await database.get_user(str(giocatore.id))
        if dove == "cash":
            await database.update_balance(str(giocatore.id), cash=user["cash"] + importo)
        else:
            await database.update_balance(str(giocatore.id), bank=user["bank"] + importo)

        embed = discord.Embed(title="💰 Denaro Aggiunto", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
        embed.add_field(name="💵 Importo",   value=f"${importo:,}",   inline=True)
        embed.add_field(name="📋 Dove",      value="Contanti" if dove == "cash" else "Banca", inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await log_embed(bot, LOG_CHANNEL_ID, embed)

    @bot.tree.command(name="remove-money", description="[STAFF] Rimuovi denaro da un giocatore")
    @app_commands.describe(giocatore="Il giocatore", importo="Importo da rimuovere", dove="Contanti o banca")
    @app_commands.choices(dove=[
        app_commands.Choice(name="💵 Contanti", value="cash"),
        app_commands.Choice(name="🏦 Banca",    value="bank"),
    ])
    async def remove_money(interaction: discord.Interaction, giocatore: discord.Member, importo: int, dove: str = "cash"):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        user = await database.get_user(str(giocatore.id))
        if dove == "cash":
            new_val = max(0, user["cash"] - importo)
            await database.update_balance(str(giocatore.id), cash=new_val)
        else:
            new_val = max(0, user["bank"] - importo)
            await database.update_balance(str(giocatore.id), bank=new_val)

        embed = discord.Embed(title="💸 Denaro Rimosso", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
        embed.add_field(name="💵 Importo",   value=f"${importo:,}",   inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await log_embed(bot, LOG_CHANNEL_ID, embed)

    @bot.tree.command(name="give-item", description="[STAFF] Dai un item a un giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="Nome dell'item", quantita="Quantità")
    async def give_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        await database.add_item(str(giocatore.id), item, quantita)
        embed = discord.Embed(title="🎁 Item Consegnato", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Ricevuto da", value=giocatore.mention, inline=True)
        embed.add_field(name="📦 Item",        value=item,              inline=True)
        embed.add_field(name="🔢 Quantità",    value=str(quantita),     inline=True)
        embed.add_field(name="👮 Staff",       value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await log_embed(bot, LOG_CHANNEL_ID, embed)

    @bot.tree.command(name="take-item", description="[STAFF] Rimuovi un item da un giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="Nome dell'item", quantita="Quantità")
    async def take_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        rimosso = await database.remove_item(str(giocatore.id), item, quantita)
        if not rimosso:
            await interaction.response.send_message(f"❌ Il giocatore non ha abbastanza **{item}**.", ephemeral=True)
            return

        embed = discord.Embed(title="📦 Item Rimosso", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
        embed.add_field(name="📦 Item",      value=item,              inline=True)
        embed.add_field(name="🔢 Quantità",  value=str(quantita),     inline=True)
        embed.add_field(name="👮 Staff",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)
        await log_embed(bot, LOG_CHANNEL_ID, embed)

    @bot.tree.command(name="paga-stipendio", description="[STAFF] Paga lo stipendio a un giocatore")
    @app_commands.describe(giocatore="Il giocatore", importo="Importo stipendio", ruolo="Ruolo/Lavoro del giocatore")
    async def paga_stipendio(interaction: discord.Interaction, giocatore: discord.Member, importo: int, ruolo: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        user = await database.get_user(str(giocatore.id))
        await database.update_balance(str(giocatore.id), cash=user["cash"] + importo)

        embed = discord.Embed(
            title="💼 Stipendio Pagato",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Giocatore", value=giocatore.mention,  inline=True)
        embed.add_field(name="💵 Stipendio", value=f"${importo:,}",    inline=True)
        embed.add_field(name="🤠 Lavoro",    value=ruolo,              inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Stipendio")
        await interaction.response.send_message(embed=embed)
        await log_embed(bot, LOG_CHANNEL_ID, embed)

        try:
            dm = discord.Embed(
                title="💵 Hai ricevuto il tuo stipendio!",
                description=f"Hai ricevuto **${importo:,}** come stipendio per il tuo lavoro da **{ruolo}**.",
                color=discord.Color.green()
            )
            await giocatore.send(embed=dm)
        except Exception:
            pass

    @bot.tree.command(name="annuncio", description="[STAFF] Invia un annuncio pubblico nel server")
    @app_commands.describe(titolo="Titolo dell'annuncio", messaggio="Testo dell'annuncio")
    async def annuncio(interaction: discord.Interaction, titolo: str, messaggio: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 {titolo}",
            description=messaggio,
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Annuncio di {interaction.user.display_name} • 🤠 Red Dead Redemption II")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Annuncio inviato!", ephemeral=True)

    @bot.tree.command(name="whitelister", description="[STAFF] Comunica l'esito di una whitelist o background PG")
    @app_commands.describe(giocatore="Il giocatore", esito="Approvato o rifiutato", motivazione="Motivazione (opzionale)")
    @app_commands.choices(esito=[
        app_commands.Choice(name="✅ Approvato",  value="approvato"),
        app_commands.Choice(name="❌ Rifiutato",  value="rifiutato"),
    ])
    async def whitelister(interaction: discord.Interaction, giocatore: discord.Member, esito: str, motivazione: str = ""):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        color = discord.Color.green() if esito == "approvato" else discord.Color.red()
        emoji = "✅" if esito == "approvato" else "❌"

        embed = discord.Embed(
            title=f"{emoji} Whitelist / Background PG — {esito.capitalize()}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Giocatore",   value=giocatore.mention, inline=True)
        embed.add_field(name="📋 Esito",       value=esito.capitalize(), inline=True)
        if motivazione:
            embed.add_field(name="📝 Motivazione", value=motivazione, inline=False)
        embed.add_field(name="👮 Staff",       value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Whitelist")
        await interaction.response.send_message(embed=embed)

        try:
            await giocatore.send(embed=embed)
        except Exception:
            pass

    @bot.tree.command(name="status-whitelist", description="[STAFF] Indica se i servizi whitelist sono online/offline")
    @app_commands.choices(stato=[
        app_commands.Choice(name="🟢 Online",  value="online"),
        app_commands.Choice(name="🔴 Offline", value="offline"),
    ])
    async def status_whitelist(interaction: discord.Interaction, stato: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        color = discord.Color.green() if stato == "online" else discord.Color.red()
        emoji = "🟢" if stato == "online" else "🔴"
        embed = discord.Embed(
            title=f"{emoji} Servizi Whitelist — {stato.upper()}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Whitelist")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Stato aggiornato!", ephemeral=True)
