import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from datetime import datetime, timezone, timedelta
from constants import LOG_CHANNEL_ID

# ── Configurazione ────────────────────────────────────────────────────────────
GAZZETTA_CHANNEL_ID   = 1404052251982565447   # Canale dove appare la gazzetta
GIORNALISTA_ROLE_ID   = 1404052056028872775   # Ruolo abilitato al comando
NOTIFICA_ROLE_ID      = 1404052056028872775   # Ruolo che riceve la notifica (@&)
DATABASE_NAME         = "rdr2.db"             # Stesso DB del bot

# ── Timezone Italia ───────────────────────────────────────────────────────────
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Rome")
    def _ora_it(dt: datetime) -> str:
        return dt.astimezone(_TZ).strftime("%d/%m/%Y alle %H:%M")
except ImportError:
    def _ora_it(dt: datetime) -> str:
        return (dt + timedelta(hours=2)).strftime("%d/%m/%Y alle %H:%M")


# ── DB helpers ────────────────────────────────────────────────────────────────
async def _init_gazzetta_table():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gazzetta_eventi (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo        TEXT    NOT NULL,
                titolo      TEXT    NOT NULL,
                descrizione TEXT    NOT NULL,
                autore_id   TEXT    NOT NULL,
                autore_tag  TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            )
        """)
        await db.commit()


async def _save_evento(tipo: str, titolo: str, descrizione: str,
                       autore_id: str, autore_tag: str, created_at: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        c = await db.execute(
            """INSERT INTO gazzetta_eventi
               (tipo, titolo, descrizione, autore_id, autore_tag, created_at)
               VALUES (?,?,?,?,?,?)""",
            (tipo, titolo, descrizione, autore_id, autore_tag, created_at)
        )
        await db.commit()
        return c.lastrowid


async def _get_autori_evento(tipo: str, titolo: str) -> list:
    """
    Restituisce i tag di TUTTI gli autori che hanno registrato
    eventi con lo stesso tipo+titolo (utile per eventi co-registrati).
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT DISTINCT autore_tag FROM gazzetta_eventi WHERE tipo=? AND titolo=?",
            (tipo, titolo)
        ) as c:
            rows = await c.fetchall()
            return [r[0] for r in rows]


# ── Tipi evento predefiniti (autocomplete) ────────────────────────────────────
_TIPI = [
    "🔫 Rapina",
    "🏪 Apertura Locale",
    "🎪 Evento Pubblico",
    "⚖️ Processo",
    "🚔 Arresto",
    "💀 Omicidio",
    "🐎 Gara Equestre",
    "🃏 Torneo di Poker",
    "🤠 Duello",
    "📜 Annuncio Ufficiale",
    "🌵 Spedizione",
    "🏕️ Accampamento",
    "🎯 Caccia",
    "💣 Attentato",
    "🤝 Accordo / Patto",
]


async def _tipo_ac(interaction: discord.Interaction, current: str):
    filtrati = [t for t in _TIPI if current.lower() in t.lower()] if current else _TIPI
    return [app_commands.Choice(name=t, value=t) for t in filtrati[:25]]


# ── Setup ─────────────────────────────────────────────────────────────────────
def setup_gazzetta_commands(bot: commands.Bot):

    # ── /registra-evento ──────────────────────────────────────────────────────
    @bot.tree.command(
        name="registra-evento",
        description="[Giornalista] Registra un evento sulla Gazzetta del West"
    )
    @app_commands.describe(
        tipo="Categoria dell'evento (es. Rapina, Apertura Locale…)",
        titolo="Titolo dell'articolo",
        descrizione="Descrizione completa dell'evento"
    )
    @app_commands.autocomplete(tipo=_tipo_ac)
    async def registra_evento(
        interaction: discord.Interaction,
        tipo: str,
        titolo: str,
        descrizione: str
    ):
        # ── Controllo ruolo ───────────────────────────────────────────────────
        if not isinstance(interaction.user, discord.Member) or \
           not any(r.id == GIORNALISTA_ROLE_ID for r in interaction.user.roles):
            await interaction.response.send_message(
                "❌ Solo i **Giornalisti** possono registrare eventi sulla Gazzetta.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # ── Inizializza tabella (safe) ────────────────────────────────────────
        await _init_gazzetta_table()

        # ── Salva nel DB ──────────────────────────────────────────────────────
        now_utc    = datetime.now(timezone.utc)
        now_str    = _ora_it(now_utc)
        autore_tag = str(interaction.user)
        autore_id  = str(interaction.user.id)

        evento_id = await _save_evento(
            tipo, titolo, descrizione, autore_id, autore_tag, now_str
        )

        # ── Recupera tutti gli autori co-registrati per questo titolo+tipo ────
        tutti_autori = await _get_autori_evento(tipo, titolo)
        autori_mention = []
        if interaction.guild:
            for tag in tutti_autori:
                member = discord.utils.find(
                    lambda m, t=tag: str(m) == t,
                    interaction.guild.members
                )
                autori_mention.append(member.mention if member else f"`{tag}`")
        else:
            autori_mention = [f"`{t}`" for t in tutti_autori]

        autori_str = "\n".join(f"✒️ {m}" for m in autori_mention)

        # ── Costruisce l'embed ────────────────────────────────────────────────
        embed = discord.Embed(
            color=discord.Color(0xC8A951),
            timestamp=now_utc
        )

        embed.set_author(name="GAZZETTA DEL WEST  •  Colorado Full RP")

        embed.title = "📰  𝑮𝑨𝒁𝒁𝑬𝑻𝑻𝑨  𝑫𝑬𝑳  𝑵𝑬𝑾 𝑨𝑼𝑺𝑻𝑰𝑵   <a:megafono:1431932605984542720>"

        embed.description = (
            "```\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  𝑵𝑶𝑻𝑰𝒁𝑰𝑬  𝑫𝑨𝑳  𝑵𝑬𝑾 𝑨𝑼𝑺𝑻𝑰𝑵\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "```"
        )

        embed.add_field(
            name="📌  Categoria",
            value=f"```{tipo}```",
            inline=True
        )
        embed.add_field(
            name="🗞️  Titolo",
            value=f"```{titolo}```",
            inline=True
        )
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        embed.add_field(
            name="📖  Resoconto",
            value=descrizione,
            inline=False
        )

        embed.add_field(name="\u200b", value="\u200b", inline=False)

        embed.add_field(
            name="✒️  Redatto da",
            value=autori_str or interaction.user.mention,
            inline=True
        )
        embed.add_field(
            name="🕒  Data & Ora",
            value=f"*{now_str}*",
            inline=True
        )
        embed.add_field(
            name="🔖  ID Articolo",
            value=f"`#{evento_id:04d}`",
            inline=True
        )

        embed.set_footer(
            text="🤠  𝑮𝑨𝒁𝒁𝑬𝑻𝑻𝑨  𝑫𝑬𝑳  𝑵𝑬𝑾 𝑨𝑼𝑺𝑻𝑰𝑵  🤠  —  Colorado Full RP"
        )

        # ── Invia nel canale gazzetta ─────────────────────────────────────────
        try:
            gazzetta_ch = bot.get_channel(GAZZETTA_CHANNEL_ID)
            if not gazzetta_ch:
                gazzetta_ch = await bot.fetch_channel(GAZZETTA_CHANNEL_ID)

            if gazzetta_ch:
                await gazzetta_ch.send(
                    content=f"<@&{NOTIFICA_ROLE_ID}>",
                    embed=embed
                )
            else:
                await interaction.followup.send(
                    "⚠️ Evento salvato nel DB ma canale gazzetta non trovato!",
                    ephemeral=True
                )
                return
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Evento salvato (ID `#{evento_id:04d}`) ma errore nell'invio: `{e}`",
                ephemeral=True
            )
            return

        # ── Conferma all'autore ───────────────────────────────────────────────
        confirm = discord.Embed(
            title="✅ Articolo pubblicato!",
            description=(
                f"L'evento **{titolo}** è stato registrato e pubblicato\n"
                f"sulla Gazzetta del West con ID `#{evento_id:04d}`."
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=confirm, ephemeral=True)

  
