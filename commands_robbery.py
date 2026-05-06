import discord
from discord import app_commands
from constants import LOG_CHANNEL_ID

def _criminali_attivi() -> bool:
    try:
        import commands_invoice as _ci
        return _ci._azioni_criminali_attive
    except Exception:
        return True

# Ruoli da menzionare sopra l'embed
SCERIFFO_PING  = 1404051916140449885
CRIMINALI_PING = 1420468587998478376

# Dati rapine dalla tabella ufficiale
RAPINE = {
    "Persona": {
        "emoji": "🤠",
        "immagine": "https://i.postimg.cc/BZT2mN2W/IMG-7555.webp",
        "criminali": "1",
        "fdo": "Da 1 a 2",
        "bottino": "Variabile",
        "armi": "Bianche e Pistole",
        "ostaggi": "1",
        "scassinamento": "0 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Stalla": {
        "emoji": "🐴",
        "immagine": "https://i.postimg.cc/tgd9K1kY/IMG-7556.jpg",
        "criminali": "Da 1 a 2",
        "fdo": "Da 2 a 3",
        "bottino": "100$ + 1 Cavallo + Capitali",
        "armi": "Pistole",
        "ostaggi": "1",
        "scassinamento": "3 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Emporio": {
        "emoji": "🏪",
        "immagine": "https://i.postimg.cc/7LPxyHWf/IMG-7557.jpg",
        "criminali": "Da 1 a 3",
        "fdo": "Da 2 a 4",
        "bottino": "150$ + 2 Capitali + Binocolo",
        "armi": "Pistole e Fucili",
        "ostaggi": "1",
        "scassinamento": "5 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Saloon": {
        "emoji": "🍺",
        "immagine": "https://i.postimg.cc/ydSy6HJs/IMG-7554.webp",
        "criminali": "Da 1 a 4",
        "fdo": "Da 2 a 5",
        "bottino": "220$ + 3 Capitali",
        "armi": "Pistole e Fucili",
        "ostaggi": "Da 1 a 2",
        "scassinamento": "7 Minuti",
        "tetti": "NO",
        "fdo_speciali": "NO",
    },
    "Armeria": {
        "emoji": "🔫",
        "immagine": "https://i.postimg.cc/15pPnVxw/IMG-7558.jpg",
        "criminali": "Da 2 a 4",
        "fdo": "Da 3 a 5",
        "bottino": "300$ + 5 Capitali + 2 Revolver + 1 Fucile",
        "armi": "Tutte",
        "ostaggi": "Da 1 a 2",
        "scassinamento": "10 Minuti",
        "tetti": "SÌ",
        "fdo_speciali": "SÌ",
    },
    "Diligenza": {
        "emoji": "🚂",
        "immagine": "https://i.postimg.cc/sfWCqG2y/IMG-7559.jpg",
        "criminali": "Da 1 a 6",
        "fdo": "Da 2 a 7",
        "bottino": "Variabile + 5 Capitali",
        "armi": "Tutte",
        "ostaggi": "Da 1 a 10",
        "scassinamento": "0 Minuti",
        "tetti": "NO",
        "fdo_speciali": "SÌ",
    },
    "Treno": {
        "emoji": "🚃",
        "immagine": "https://i.postimg.cc/Pq70Fdst/IMG-7560.webp",
        "criminali": "Da 4 a 7",
        "fdo": "Da 5 a 8",
        "bottino": "800$ + 10 Capitali + Merce",
        "armi": "Tutte",
        "ostaggi": "Da 1 a 12",
        "scassinamento": "12 Minuti",
        "tetti": "SÌ",
        "fdo_speciali": "SÌ",
    },
}


def setup_robbery_commands(bot):

    @bot.tree.command(name="rapina", description="Avvia una rapina nel Far West (azione illegale)")
    @app_commands.describe(bersaglio="Scegli il tipo di rapina")
    @app_commands.choices(bersaglio=[
        app_commands.Choice(name="🤠 Persona",   value="Persona"),
        app_commands.Choice(name="🐴 Stalla",    value="Stalla"),
        app_commands.Choice(name="🏪 Emporio",   value="Emporio"),
        app_commands.Choice(name="🍺 Saloon",    value="Saloon"),
        app_commands.Choice(name="🔫 Armeria",   value="Armeria"),
        app_commands.Choice(name="🚂 Diligenza", value="Diligenza"),
        app_commands.Choice(name="🚃 Treno",     value="Treno"),
    ])
    async def rapina(interaction: discord.Interaction, bersaglio: str):
        if not _criminali_attivi():
            await interaction.response.send_message(
                "❌ Le **azioni criminali** sono attualmente **offline**.\nAttendi che lo Staff le riattivi.",
                ephemeral=True)
            return
        r = RAPINE[bersaglio]

        embed = discord.Embed(
            title=f"{r['emoji']} 𝐑𝐀𝐏𝐈𝐍𝐀 — {bersaglio.upper()}",
            color=discord.Color(0x8B0000),
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url=r["immagine"])
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="👥 Criminali richiesti", value=r["criminali"],     inline=True)
        embed.add_field(name="🚔 FDO richieste",       value=r["fdo"],           inline=True)
        embed.add_field(name="💰 Bottino",             value=r["bottino"],       inline=False)
        embed.add_field(name="🔫 Armi consentite",     value=r["armi"],          inline=True)
        embed.add_field(name="🙋 Ostaggi",             value=r["ostaggi"],       inline=True)
        embed.add_field(name="⏱️ Tempo scassinamento", value=r["scassinamento"], inline=True)
        embed.add_field(name="🏠 Accesso tetti",       value=r["tetti"],         inline=True)
        embed.add_field(name="⭐ FDO speciali",        value=r["fdo_speciali"],  inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Rapina")

        ping_content = f"<@&{SCERIFFO_PING}> <@&{CRIMINALI_PING}>"
        await interaction.response.send_message(content=ping_content, embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(
                    title="🚨 𝐋𝐎𝐆 𝐑𝐀𝐏𝐈𝐍𝐀",
                    color=discord.Color(0x8B0000),
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="👤 Avviata da", value=interaction.user.mention, inline=True)
                log.add_field(name="🎯 Tipo",        value=bersaglio,               inline=True)
                await ch.send(embed=log)
        except Exception:
            pass
