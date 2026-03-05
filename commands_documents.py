import discord
from discord import app_commands
import database
from constants import STATO_ROLE_ID, LOG_CHANNEL_ID, has_sceriffo

# Il ruolo che può emettere documenti è STATO_ROLE_ID (non più Sceriffo)
def has_stato(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == STATO_ROLE_ID for r in interaction.user.roles)

def setup_document_commands(bot):

    # ── /documento ───────────────────────────────────────────────────────────
    # La foto viene caricata come allegato Discord direttamente nel comando
    @bot.tree.command(name="documento", description="[Stato] Crea il documento d'identità ufficiale per un cittadino")
    @app_commands.describe(
        cittadino="Il cittadino",
        nome="Nome",
        cognome="Cognome",
        eta="Età",
        sesso="Sesso",
        luogo_nascita="Luogo di nascita",
        foto="Foto del personaggio (carica un'immagine direttamente)"
    )
    @app_commands.choices(sesso=[
        app_commands.Choice(name="🤠 Uomo",  value="Uomo"),
        app_commands.Choice(name="👩 Donna", value="Donna"),
    ])
    async def documento(
        interaction: discord.Interaction,
        cittadino: discord.Member,
        nome: str,
        cognome: str,
        eta: int,
        sesso: str,
        luogo_nascita: str,
        foto: discord.Attachment = None
    ):
        if not has_stato(interaction):
            await interaction.response.send_message(
                "❌ Solo il ruolo **Stato** può emettere documenti d'identità.", ephemeral=True
            )
            return
        if eta < 0 or eta > 120:
            await interaction.response.send_message("❌ Età non valida.", ephemeral=True)
            return

        # Verifica che la foto sia un'immagine
        foto_url = None
        if foto:
            if not foto.content_type or not foto.content_type.startswith("image/"):
                await interaction.response.send_message(
                    "❌ Il file caricato non è un'immagine valida. Carica un'immagine (jpg, png, gif...).", ephemeral=True
                )
                return
            foto_url = foto.url

        await database.set_document(
            str(cittadino.id), nome, cognome, eta, sesso, luogo_nascita, foto_url
        )

        embed = discord.Embed(
            title="📜 DOCUMENTO D'IDENTITÀ UFFICIALE",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Nome",            value=nome,          inline=True)
        embed.add_field(name="👥 Cognome",          value=cognome,       inline=True)
        embed.add_field(name="🎂 Età",              value=str(eta),      inline=True)
        embed.add_field(name="⚧ Sesso",             value=sesso,         inline=True)
        embed.add_field(name="📍 Luogo di nascita", value=luogo_nascita, inline=True)
        embed.add_field(name="🔒 Emesso da",        value=interaction.user.mention, inline=True)

        if foto_url:
            embed.set_image(url=foto_url)
        else:
            embed.add_field(name="🖼️ Foto", value="*Nessuna foto allegata*", inline=False)

        embed.set_footer(text="🤠 Red Dead Redemption II — Documento Ufficiale")
        await interaction.response.send_message(embed=embed)

        # DM al cittadino
        try:
            await cittadino.send(
                content="📜 **Il tuo documento d'identità è stato registrato!**",
                embed=embed
            )
        except Exception:
            pass

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ── /rimuovi-documento ───────────────────────────────────────────────────
    @bot.tree.command(name="rimuovi-documento", description="[Stato] Rimuovi il documento d'identità di un cittadino")
    @app_commands.describe(cittadino="Il cittadino")
    async def rimuovi_documento(interaction: discord.Interaction, cittadino: discord.Member):
        if not has_stato(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return

        import aiosqlite
        from constants import DATABASE_NAME
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM documents WHERE user_id=?", (str(cittadino.id),))
            await db.commit()

        embed = discord.Embed(
            title="🗑️ Documento Rimosso",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Cittadino",  value=cittadino.mention,        inline=True)
        embed.add_field(name="🔒 Rimosso da", value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Stato")
        await interaction.response.send_message(embed=embed)

    # ── /cercapersona ────────────────────────────────────────────────────────
    @bot.tree.command(name="cercapersona", description="[Sceriffo/Stato] Cerca una persona nel registro")
    @app_commands.describe(cittadino="Il cittadino da cercare")
    async def cercapersona(interaction: discord.Interaction, cittadino: discord.Member):
        if not (has_sceriffo(interaction) or has_stato(interaction)):
            await interaction.response.send_message(
                "❌ Solo lo Sceriffo o lo Stato possono consultare il registro.", ephemeral=True
            )
            return

        doc     = await database.get_document(str(cittadino.id))
        fines   = await database.get_fines(str(cittadino.id))
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
            if doc.get("foto_url"):
                embed.set_image(url=doc["foto_url"])
        else:
            embed.add_field(name="📜 Identità", value="*Nessun documento registrato*", inline=False)

        embed.add_field(name="⭐ Taglie attive",
                        value=f"{len(fines)} (${sum(f['amount'] for f in fines):,})", inline=True)
        embed.add_field(name="⚖️ Crimini registrati", value=str(len(records)), inline=True)
        embed.set_footer(text=f"🤠 Consultato da: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
