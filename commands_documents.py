import discord
from discord import app_commands
import database
from datetime import datetime

LOG_CHANNEL_ID = 1479158931610931414
SCERIFFO_ROLES = 1404051912197931109

def has_sceriffo(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in SCERIFFO_ROLES for r in interaction.user.roles)

def setup_document_commands(bot):

    @bot.tree.command(name="documento", description="[MUNICIPIO] Crea il documento di identità per un cittadino")
    @app_commands.describe(
        cittadino="Il cittadino",
        nome="Nome", cognome="Cognome",
        eta="Età", sesso="Sesso",
        luogo_nascita="Luogo di nascita"
    )
    @app_commands.choices(sesso=[
        app_commands.Choice(name="🤠 Uomo",   value="Uomo"),
        app_commands.Choice(name="👩 Donna",  value="Donna"),
    ])
    async def documento(
        interaction: discord.Interaction,
        cittadino: discord.Member,
        nome: str, cognome: str,
        eta: int, sesso: str,
        luogo_nascita: str
    ):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può emettere documenti.", ephemeral=True)
            return

        await database.set_document(str(cittadino.id), nome, cognome, eta, sesso, luogo_nascita)

        embed = discord.Embed(
            title="📜 DOCUMENTO DI IDENTITÀ",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Nome",           value=nome,         inline=True)
        embed.add_field(name="👥 Cognome",         value=cognome,      inline=True)
        embed.add_field(name="🎂 Età",             value=str(eta),     inline=True)
        embed.add_field(name="⚧ Sesso",            value=sesso,        inline=True)
        embed.add_field(name="📍 Luogo di nascita", value=luogo_nascita, inline=True)
        embed.add_field(name="🔒 Emesso da",       value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

        try:
            await cittadino.send(embed=embed)
        except Exception:
            pass

    @bot.tree.command(name="rimuovi-documento", description="[Staff] Rimuovi il documento di identità di un cittadino")
    @app_commands.describe(cittadino="Il cittadino")
    async def rimuovi_documento(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return

        # Rimozione dal db
        import aiosqlite
        async with aiosqlite.connect("rdr2_bot.db") as db:
            await db.execute("DELETE FROM documents WHERE user_id = ?", (str(cittadino.id),))
            await db.commit()

        embed = discord.Embed(
            title="🗑️ Documento Rimosso",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Cittadino", value=cittadino.mention, inline=True)
        embed.add_field(name="👮 Rimosso da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="cercapersona", description="[Sceriffo] Cerca una persona nel registro")
    @app_commands.describe(cittadino="Il cittadino da cercare")
    async def cercapersona(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può consultare il registro.", ephemeral=True)
            return

        doc = await database.get_document(str(cittadino.id))
        fines = await database.get_fines(str(cittadino.id))
        records = await database.get_criminal_records(str(cittadino.id))

        embed = discord.Embed(
            title=f"🔍 Ricerca: {cittadino.display_name}",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)

        if doc:
            embed.add_field(name="📜 Identità", value=(
                f"**Nome:** {doc['nome']} {doc['cognome']}\n"
                f"**Età:** {doc['eta']} | **Sesso:** {doc['sesso']}\n"
                f"**Nato a:** {doc['luogo_nascita']}"
            ), inline=False)
        else:
            embed.add_field(name="📜 Identità", value="*Nessun documento registrato*", inline=False)

        embed.add_field(name="⭐ Taglie attive", value=f"{len(fines)} (${sum(f['amount'] for f in fines):,})", inline=True)
        embed.add_field(name="⚖️ Crimini", value=str(len(records)), inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Registro Sceriffo")
        await interaction.response.send_message(embed=embed, ephemeral=True)
