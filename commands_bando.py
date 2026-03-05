import discord
from discord import app_commands
import database
import aiosqlite
import random
from datetime import datetime

STAFF_ROLES = [1414738761207517214, 1414735564632231988]

def has_staff(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id in STAFF_ROLES for r in interaction.user.roles)

# ─── commands_bando ──────────────────────────────────────────────────────────

def setup_bando_commands(bot):

    LAVORI_RDR2 = [
        app_commands.Choice(name="⭐ Sceriffo",           value="Sceriffo"),
        app_commands.Choice(name="🩺 Dottore",            value="Dottore"),
        app_commands.Choice(name="🔫 Armiere",            value="Armiere"),
        app_commands.Choice(name="🐴 Stalliere",          value="Stalliere"),
        app_commands.Choice(name="🍺 Barista del Saloon", value="Barista del Saloon"),
        app_commands.Choice(name="⛏️ Minatore",           value="Minatore"),
        app_commands.Choice(name="🚂 Capotreno",          value="Capotreno"),
        app_commands.Choice(name="🌾 Fattore",            value="Fattore"),
        app_commands.Choice(name="📰 Giornalista",        value="Giornalista"),
        app_commands.Choice(name="🏪 Commerciante",       value="Commerciante"),
    ]

    @bot.tree.command(name="bando", description="[Staff] Comunica apertura/chiusura di un bando lavorativo")
    @app_commands.describe(lavoro="Il lavoro", stato="Aperto o chiuso", dettagli="Ulteriori informazioni")
    @app_commands.choices(
        lavoro=LAVORI_RDR2,
        stato=[
            app_commands.Choice(name="🟢 Aperto", value="aperto"),
            app_commands.Choice(name="🔴 Chiuso", value="chiuso"),
        ]
    )
    async def bando(interaction: discord.Interaction, lavoro: str, stato: str, dettagli: str = ""):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        color = discord.Color.green() if stato == "aperto" else discord.Color.red()
        emoji = "🟢" if stato == "aperto" else "🔴"

        embed = discord.Embed(
            title=f"📜 BANDO LAVORATIVO — {emoji} {stato.upper()}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🤠 Lavoro",    value=lavoro, inline=True)
        embed.add_field(name="📋 Stato",     value=stato.capitalize(), inline=True)
        if dettagli:
            embed.add_field(name="📝 Dettagli", value=dettagli, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bando Lavorativo")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Bando pubblicato!", ephemeral=True)

    @bot.tree.command(name="esito-bando", description="[Staff] Comunica l'esito di un bando lavorativo")
    @app_commands.describe(giocatore="Il candidato", lavoro="Il lavoro", esito="Approvato o rifiutato", motivazione="Motivazione")
    @app_commands.choices(esito=[
        app_commands.Choice(name="✅ Assunto",  value="assunto"),
        app_commands.Choice(name="❌ Rifiutato", value="rifiutato"),
    ])
    async def esito_bando(interaction: discord.Interaction, giocatore: discord.Member, lavoro: str, esito: str, motivazione: str = ""):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        color = discord.Color.green() if esito == "assunto" else discord.Color.red()
        emoji = "✅" if esito == "assunto" else "❌"

        embed = discord.Embed(
            title=f"{emoji} Esito Bando — {esito.capitalize()}",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Candidato",  value=giocatore.mention,       inline=True)
        embed.add_field(name="🤠 Lavoro",     value=lavoro,                  inline=True)
        embed.add_field(name="📋 Esito",      value=esito.capitalize(),      inline=True)
        if motivazione:
            embed.add_field(name="📝 Motivazione", value=motivazione, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bando Lavorativo")
        await interaction.response.send_message(embed=embed)

        try:
            await giocatore.send(embed=embed)
        except Exception:
            pass


# ─── commands_rp_status ──────────────────────────────────────────────────────

def setup_rpoff_commands(bot):

    @bot.tree.command(name="rpon", description="[Staff] Attiva la modalità Roleplay")
    async def rpon(interaction: discord.Interaction):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🟢 ROLEPLAY ATTIVO",
            description="Il Far West è aperto! Buon gioco a tutti, cowboy! 🤠",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ RP attivato!", ephemeral=True)

    @bot.tree.command(name="rpoff", description="[Staff] Disattiva la modalità Roleplay")
    async def rpoff(interaction: discord.Interaction):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🔴 ROLEPLAY OFFLINE",
            description="Il Far West chiude i battenti. A presto, cowboy! 🤠",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II")
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ RP disattivato!", ephemeral=True)


# ─── commands_wipepg ─────────────────────────────────────────────────────────

def setup_wipepg_commands(bot):

    class ConfermaWipeView(discord.ui.View):
        def __init__(self, target_id: str, staff_id: str):
            super().__init__(timeout=60)
            self.target_id = target_id
            self.staff_id  = staff_id

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if str(interaction.user.id) != self.staff_id:
                await interaction.response.send_message("❌ Non sei lo staff che ha avviato questa operazione.", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="✅ Conferma WIPE", style=discord.ButtonStyle.danger)
        async def conferma(self, interaction: discord.Interaction, button: discord.ui.Button):
            await database.wipe_user(self.target_id)
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content="✅ **WIPE completato.**", view=self)

        @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.secondary)
        async def annulla(self, interaction: discord.Interaction, button: discord.ui.Button):
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content="❌ **WIPE annullato.**", view=self)

    @bot.tree.command(name="wipe-pg", description="[Staff] Resetta completamente il personaggio di un giocatore")
    @app_commands.describe(giocatore="Il giocatore da wippare")
    async def wipe_pg(interaction: discord.Interaction, giocatore: discord.Member):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚠️ CONFERMA WIPE PG",
            description=(
                f"Stai per resettare **completamente** il personaggio di {giocatore.mention}.\n\n"
                f"Verranno eliminati: contanti, banca, bisaccia, documenti, taglie, fedina penale, proprietà.\n\n"
                f"**Sei sicuro?**"
            ),
            color=discord.Color.orange()
        )
        view = ConfermaWipeView(str(giocatore.id), str(interaction.user.id))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @bot.tree.command(name="wipe-item", description="[Staff] Rimuovi tutti gli item e bisacce di tutti i giocatori")
    async def wipe_item(interaction: discord.Interaction):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        async with aiosqlite.connect("rdr2_bot.db") as db:
            await db.execute("DELETE FROM inventory")
            await db.commit()

        await interaction.response.send_message("✅ Tutte le bisacce sono state svuotate.", ephemeral=True)


# ─── commands_scoop ──────────────────────────────────────────────────────────

def setup_scoop_commands(bot):

    @bot.tree.command(name="scoop", description="Pubblica uno scoop sul giornale del Far West")
    @app_commands.describe(titolo="Titolo dell'articolo", notizia="Testo della notizia")
    async def scoop(interaction: discord.Interaction, titolo: str, notizia: str):
        embed = discord.Embed(
            title=f"📰 {titolo}",
            description=notizia,
            color=discord.Color(0xF5DEB3),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=f"Giornalista: {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Gazzetta del Far West")
        await interaction.response.send_message(embed=embed)


# ─── commands_fondocassa ─────────────────────────────────────────────────────

COMPANY_ROLES_RDR2 = {
    "Sceriffo":       1415093546549248040,
    "Dottore":        1415239481757536256,
    "Armeria":        1415092383250382858,
    "Stalla":         1415238213303406702,
    "Saloon":         1415243266777157643,
    "Emporio":        1415242295153918123,
    "Officina":       1415240071216500746,
    "Contrabbando":   1424004700608401428,
    "Diligenza":      1415262517407645828,
}

def setup_fondocassa_commands(bot):

    @bot.tree.command(name="fondocassa", description="Visualizza il fondo cassa della tua compagnia")
    async def fondocassa(interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Errore.", ephemeral=True)
            return

        user_companies = []
        for company, role_id in COMPANY_ROLES_RDR2.items():
            if any(r.id == role_id for r in interaction.user.roles):
                user_companies.append(company)

        if not user_companies:
            await interaction.response.send_message(
                "❌ Non fai parte di nessuna compagnia.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💼 Fondo Cassa Compagnia",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        for company in user_companies:
            amount = await database.get_fondocassa(company)
            embed.add_field(name=f"🏢 {company}", value=f"${amount:,}", inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fondo Cassa")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="add-fondocassa", description="[Staff] Aggiungi soldi al fondocassa di una compagnia")
    @app_commands.describe(compagnia="La compagnia", importo="Importo da aggiungere")
    @app_commands.choices(compagnia=[
        app_commands.Choice(name=c, value=c) for c in COMPANY_ROLES_RDR2
    ])
    async def add_fondocassa(interaction: discord.Interaction, compagnia: str, importo: int):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        current = await database.get_fondocassa(compagnia)
        await database.update_fondocassa(compagnia, current + importo)

        embed = discord.Embed(
            title="💼 Fondo Cassa Aggiornato",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🏢 Compagnia",     value=compagnia,           inline=True)
        embed.add_field(name="💵 Aggiunto",       value=f"${importo:,}",    inline=True)
        embed.add_field(name="💰 Nuovo totale",   value=f"${current + importo:,}", inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Admin")
        await interaction.response.send_message(embed=embed)


# ─── commands_marijuana (raccolta erba, gestita in commands_theft) ────────────

async def setup_marijuana_database():
    """Placeholder — la raccolta erba è in commands_theft."""
    pass

def setup_marijuana_commands(bot):
    """Placeholder — la raccolta erba è gestita in commands_theft."""
    pass


# ─── commands_bonifico ────────────────────────────────────────────────────────

def setup_bonifico_commands(bot):
    """Rimosso per RDR2 — i trasferimenti avvengono tramite la banca con banchiere."""
    pass


# ─── commands_deposits (rimosso per RDR2) ─────────────────────────────────────

def setup_deposit_commands(bot):
    """Rimosso per RDR2."""
    pass
