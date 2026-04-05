import discord
from discord import app_commands
from constants import has_staff, LOG_CHANNEL_ID


def setup_bando_commands(bot):

    @bot.tree.command(name="bando", description="[Staff] Apri o chiudi un bando lavorativo")
    @app_commands.describe(stato="Aperto o chiuso")
    @app_commands.choices(
        stato=[
            app_commands.Choice(name="🟢 Aperto", value="aperto"),
            app_commands.Choice(name="🔴 Chiuso", value="chiuso"),
        ]
    )
    async def bando(interaction: discord.Interaction, stato: str):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return

        if stato == "aperto":
            color    = discord.Color.green()
            titolo   = "<a:online:1459627385702973572> 𝐁𝐀𝐍𝐃𝐎 𝐀𝐏𝐄𝐑𝐓𝐎 <a:online:1459627385702973572>"
            immagine = "https://i.postimg.cc/htny3bsk/585ED73F-B062-4585-8652-DA2F28167758.png"
        else:
            color    = discord.Color.red()
            titolo   = "<a:offline:1459628872197738641> 𝐁𝐀𝐍𝐃𝐎 𝐂𝐇𝐈𝐔𝐒𝐎 <a:offline:1459628872197738641>"
            immagine = "https://i.postimg.cc/9FhYWX9F/055FF80F-60C4-4353-A87D-7D52C9FE7D9D.png"

        embed = discord.Embed(title=titolo, color=color, timestamp=discord.utils.utcnow())
        embed.set_image(url=immagine)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bando Lavorativo")

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Bando pubblicato!", ephemeral=True)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ------------------------------------------------------------------ #

    @bot.tree.command(name="esito-bando", description="[Staff] Comunica l'esito di un bando lavorativo")
    @app_commands.describe(
        giocatore="Il candidato",
        lavoro="Il ruolo lavorativo da assegnare (tag del ruolo)",
        grado="Il grado/rango del lavoro da assegnare (tag del ruolo)",
        esito="Esito del bando",
        motivazione="Motivazione (opzionale)"
    )
    @app_commands.choices(
        esito=[
            app_commands.Choice(name="✅ Assunto",   value="assunto"),
            app_commands.Choice(name="❌ Rifiutato", value="rifiutato"),
        ]
    )
    async def esito_bando(
        interaction: discord.Interaction,
        giocatore: discord.Member,
        lavoro: discord.Role,
        grado: discord.Role,
        esito: str,
        motivazione: str = ""
    ):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return

        # Assegna i 2 ruoli solo se assunto
        if esito == "assunto":
            try:
                await giocatore.add_roles(lavoro, reason=f"Bando lavorativo — assunto da {interaction.user}")
                await giocatore.add_roles(grado,  reason=f"Bando lavorativo — grado assegnato da {interaction.user}")
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ Non ho i permessi per assegnare quei ruoli.", ephemeral=True
                )
                return

        color = discord.Color.green() if esito == "assunto" else discord.Color.red()
        emoji = "✅" if esito == "assunto" else "❌"

        embed = discord.Embed(
            title=f"{emoji} 𝐄𝐬𝐢𝐭𝐨 𝐁𝐚𝐧𝐝𝐨 — {esito.capitalize()}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="👤 Candidato",   value=giocatore.mention,        inline=True)
        embed.add_field(name="🤠 Lavoro",      value=lavoro.mention,           inline=True)
        embed.add_field(name="🎖️ Grado",      value=grado.mention,            inline=True)
        embed.add_field(name="📋 Esito",       value=esito.capitalize(),       inline=True)
        if motivazione:
            embed.add_field(name="📝 Motivazione", value=motivazione, inline=False)
        embed.add_field(name="👮 Valutato da", value=interaction.user.mention, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bando Lavorativo")

        # Risposta nel canale
        await interaction.response.send_message(embed=embed)

        # DM al giocatore
        try:
            dm_embed = discord.Embed(
                title=f"{emoji} Esito del tuo Bando — {esito.capitalize()}",
                color=color,
                timestamp=discord.utils.utcnow()
            )
            dm_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            dm_embed.add_field(name="🤠 Lavoro",  value=lavoro.name,        inline=True)
            dm_embed.add_field(name="🎖️ Grado",  value=grado.name,         inline=True)
            dm_embed.add_field(name="📋 Esito",   value=esito.capitalize(),  inline=True)
            if esito == "assunto":
                dm_embed.add_field(
                    name="🎉 Congratulazioni!",
                    value=f"Sei stato assunto come **{lavoro.name}** con il grado **{grado.name}**! I ruoli ti sono stati assegnati automaticamente.",
                    inline=False
                )
            else:
                dm_embed.add_field(
                    name="😔 Purtroppo...",
                    value="La tua candidatura non è stata accettata questa volta. Non arrenderti!",
                    inline=False
                )
            if motivazione:
                dm_embed.add_field(name="📝 Motivazione", value=motivazione, inline=False)
            dm_embed.add_field(name="👮 Valutato da", value=str(interaction.user), inline=False)
            dm_embed.set_footer(text="🤠 Red Dead Redemption II — Bando Lavorativo")
            await giocatore.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass
