import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_sceriffo

# Canale dove viene postato il manifesto della taglia
RICERCATI_CHANNEL_ID = 1418579324554055771
CITTADINI_ROLE_ID    = 1404052056028872775


def setup_fine_commands(bot):

    # ── /taglia ───────────────────────────────────────────────────────────────
    @bot.tree.command(name="taglia", description="[FDO] Emetti una taglia su un fuorilegge")
    @app_commands.describe(
        fuorilegge="Il fuorilegge",
        importo="Valore della taglia",
        motivo="Motivazione",
        foto="Foto del ricercato (opzionale)"
    )
    async def taglia(
        interaction: discord.Interaction,
        fuorilegge: discord.Member,
        importo: int,
        motivo: str,
        foto: discord.Attachment = None
    ):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può emettere taglie.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True)
            return

        await database.add_fine(str(fuorilegge.id), importo, motivo, interaction.user.display_name)

        # ── Embed principale (nel canale corrente) ────────────────────────────
        embed = discord.Embed(
            title="⭐ 𝐓𝐀𝐆𝐋𝐈𝐀 𝐄𝐌𝐄𝐒𝐒𝐀",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=fuorilegge.display_avatar.url)
        embed.add_field(name="🤠 Fuorilegge", value=fuorilegge.mention,       inline=True)
        embed.add_field(name="💰 Taglia",     value=f"${importo:,}",          inline=True)
        embed.add_field(name="📋 Motivo",     value=motivo,                   inline=False)
        embed.add_field(name="⭐ Sceriffo",   value=interaction.user.mention, inline=True)
        if foto and foto.content_type and foto.content_type.startswith("image/"):
            embed.set_image(url=foto.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
        await interaction.response.send_message(embed=embed)

        # ── Manifesto nel canale ricercati ────────────────────────────────────
        try:
            ricercati_ch = bot.get_channel(RICERCATI_CHANNEL_ID)
            if ricercati_ch:
                manifesto = discord.Embed(
                    title="🔴 𝐑𝐈𝐂𝐄𝐑𝐂𝐀𝐓𝐎 — 𝐓𝐀𝐆𝐋𝐈𝐀 𝐄𝐌𝐄𝐒𝐒𝐀",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                manifesto.set_thumbnail(url=fuorilegge.display_avatar.url)
                manifesto.add_field(name="🤠 Nome",    value=fuorilegge.mention,       inline=True)
                manifesto.add_field(name="💰 Taglia",  value=f"${importo:,}",          inline=True)
                manifesto.add_field(name="📋 Crimine", value=motivo,                   inline=False)
                manifesto.add_field(name="⭐ Emessa da", value=interaction.user.mention, inline=True)
                if foto and foto.content_type and foto.content_type.startswith("image/"):
                    manifesto.set_image(url=foto.url)
                manifesto.set_footer(text="🤠 Red Dead Redemption II — Ufficio dello Sceriffo")
                await ricercati_ch.send(
                    content=f"<@&{CITTADINI_ROLE_ID}>",
                    embed=manifesto
                )
        except Exception:
            pass

        # ── DM al fuorilegge ──────────────────────────────────────────────────
        try:
            await fuorilegge.send(embed=discord.Embed(
                title="⭐ 𝐇𝐚𝐢 𝐮𝐧𝐚 𝐭𝐚𝐠𝐥𝐢𝐚 𝐬𝐮𝐥𝐥𝐚 𝐭𝐞𝐬𝐭𝐚!",
                description=(
                    f"Lo Sceriffo **{interaction.user.display_name}** ha messo una taglia "
                    f"di **${importo:,}** su di te.\n**Motivo:** {motivo}"
                ),
                color=discord.Color.red()
            ))
        except Exception:
            pass

        # ── Log ───────────────────────────────────────────────────────────────
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ── /paga-taglia ──────────────────────────────────────────────────────────
    @bot.tree.command(name="paga-taglia", description="Paga le taglie sulla tua testa")
    async def paga_taglia(interaction: discord.Interaction):
        uid   = str(interaction.user.id)
        fines = await database.get_fines(uid)
        if not fines:
            await interaction.response.send_message("✅ Non hai taglie attive!", ephemeral=True)
            return
        totale = sum(f["amount"] for f in fines)
        user   = await database.get_user(uid)
        if user["cash"] < totale:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti.\nTotale taglie: **${totale:,}** — Tuoi: **${user['cash']:,}**",
                ephemeral=True
            )
            return
        await database.update_balance(uid, cash=user["cash"] - totale)
        for f in fines:
            await database.pay_fine(f["id"])
        embed = discord.Embed(
            title="✅ 𝐓𝐚𝐠𝐥𝐢𝐞 𝐒𝐚𝐥𝐝𝐚𝐭𝐞",
            description=f"Hai pagato **${totale:,}**. Sei tornato un uomo libero.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /controlla-taglia ─────────────────────────────────────────────────────
    @bot.tree.command(name="controlla-taglia", description="[FDO] Verifica le taglie di un giocatore")
    @app_commands.describe(giocatore="Il giocatore")
    async def controlla_taglia(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        fines = await database.get_fines(str(giocatore.id))
        embed = discord.Embed(
            title=f"⭐ 𝐓𝐚𝐠𝐥𝐢𝐞 𝐝𝐢 {giocatore.display_name}",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        if not fines:
            embed.description = "✅ Nessuna taglia attiva."
        else:
            for f in fines:
                embed.add_field(
                    name=f"Taglia #{f['id']} — ${f['amount']:,}",
                    value=f"📋 {f['reason']}\n👮 {f['issued_by']}\n📅 {f['created_at']}",
                    inline=False
                )
            embed.add_field(name="💰 Totale", value=f"${sum(f['amount'] for f in fines):,}", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /assegno ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="assegno", description="Emetti un assegno bancario a un altro giocatore")
    @app_commands.describe(
        destinatario="Il giocatore che riceverà i soldi",
        importo="Importo dell'assegno (prelevato dalla tua banca)",
        motivazione="Motivo dell'assegno"
    )
    async def assegno(
        interaction: discord.Interaction,
        destinatario: discord.Member,
        importo: int,
        motivazione: str
    ):
        if destinatario.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi fare un assegno a te stesso.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        uid      = str(interaction.user.id)
        mittente = await database.get_user(uid)

        # I soldi DEVONO essere in banca
        if mittente["bank"] < importo:
            await interaction.response.send_message(
                f"❌ Fondi bancari insufficienti!\n"
                f"Importo assegno: **${importo:,}** — Tua banca: **${mittente['bank']:,}**\n"
                f"*(I soldi dell'assegno devono essere in banca, non in contanti.)*",
                ephemeral=True
            )
            return

        dest = await database.get_user(str(destinatario.id))

        # Scala dalla banca del mittente
        await database.update_balance(uid, bank=mittente["bank"] - importo)
        # Aggiunge alla banca del destinatario
        await database.update_balance(str(destinatario.id), bank=dest["bank"] + importo)

        embed = discord.Embed(
            title="🏦 𝐀𝐬𝐬𝐞𝐠𝐧𝐨 𝐄𝐦𝐞𝐬𝐬𝐨",
            color=discord.Color(0x4682B4),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="👤 Mittente",    value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 Destinatario", value=destinatario.mention,    inline=True)
        embed.add_field(name="\u200b",          value="\u200b",                inline=False)
        embed.add_field(name="💵 Importo",      value=f"${importo:,}",         inline=True)
        embed.add_field(name="📋 Motivazione",  value=motivazione,             inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Assegno Bancario")
        await interaction.response.send_message(embed=embed)

        # ── DM al destinatario ────────────────────────────────────────────────
        try:
            dm = discord.Embed(
                title="🏦 Hai ricevuto un assegno!",
                description=(
                    f"**{interaction.user.display_name}** ti ha inviato **${importo:,}** in banca.\n\n"
                    f"**Motivazione:** {motivazione}"
                ),
                color=discord.Color(0x4682B4)
            )
            await destinatario.send(embed=dm)
        except Exception:
            pass

        # ── Log ───────────────────────────────────────────────────────────────
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass
