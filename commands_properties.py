import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
AGENZIA_ROLE_ID = 1424381004944244828  # Ruolo Agenzia Immobiliare

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass

class ProprietaModal(discord.ui.Modal, title="🏠 Registra Proprietà"):
    nome = discord.ui.TextInput(
        label="Nome",
        placeholder="Nome del proprietario",
        required=True,
        max_length=50
    )
    cognome = discord.ui.TextInput(
        label="Cognome",
        placeholder="Cognome del proprietario",
        required=True,
        max_length=50
    )
    eta = discord.ui.TextInput(
        label="Età",
        placeholder="Età del proprietario",
        required=True,
        max_length=3
    )
    nome_proprieta = discord.ui.TextInput(
        label="Nome Proprietà",
        placeholder="Es: Villa sul Lago, Appartamento Centro",
        required=True,
        max_length=100
    )
    tipo_proprieta = discord.ui.TextInput(
        label="Tipo di Proprietà",
        placeholder="Es: garage, attico, appartamento, villa",
        required=True,
        max_length=50
    )

    def __init__(self, bot: commands.Bot, utente: discord.Member):
        super().__init__()
        self.bot = bot
        self.utente = utente

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            eta_int = int(self.eta.value)
            if eta_int <= 0 or eta_int > 150:
                await interaction.followup.send("❌ Età non valida! Inserisci un numero tra 1 e 150.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ Età non valida! Inserisci solo numeri.", ephemeral=True)
            return

        # Salva nel database
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute(
                """INSERT INTO properties 
                   (user_id, owner_name, owner_surname, owner_age, property_name, property_type, assigned_by, assigned_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    str(self.utente.id),
                    self.nome.value,
                    self.cognome.value,
                    self.eta.value,
                    self.nome_proprieta.value,
                    self.tipo_proprieta.value,
                    str(interaction.user.id)
                )
            )
            await db.commit()

        # Notifica DM all'utente
        try:
            embed_dm = discord.Embed(
                title="🏠 Nuova Proprietà Assegnata!",
                description=f"Ti è stata assegnata una nuova proprietà dall'Agenzia Immobiliare!",
                color=discord.Color.green()
            )
            embed_dm.add_field(name="🏘️ Nome Proprietà", value=self.nome_proprieta.value, inline=False)
            embed_dm.add_field(name="🏢 Tipo", value=self.tipo_proprieta.value, inline=True)
            embed_dm.add_field(name="👤 Intestatario", value=f"{self.nome.value} {self.cognome.value}", inline=True)
            embed_dm.add_field(name="📋 Info", value="Usa `/mie-proprieta` per visualizzare tutte le tue proprietà.", inline=False)
            embed_dm.set_footer(text="Liberty RP - Agenzia Immobiliare")
            await self.utente.send(embed=embed_dm)
            dm_status = "Notifica DM inviata."
        except:
            dm_status = "Notifica DM non inviabile (DM bloccati)."

        # Conferma all'operatore
        await interaction.followup.send(
            f"✅ Proprietà **{self.nome_proprieta.value}** registrata con successo per {self.utente.mention}!\n({dm_status})",
            ephemeral=True
        )

        # LOG CON EMBED
        log_embed = discord.Embed(
            title="🏠 LOG PROPRIETÀ ASSEGNATA",
            color=discord.Color.green()
        )
        log_embed.add_field(name="👨‍💼 Assegnata da", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="👤 Proprietario", value=self.utente.mention, inline=True)
        log_embed.add_field(name="📝 Intestatario", value=f"{self.nome.value} {self.cognome.value}", inline=False)
        log_embed.add_field(name="🎂 Età", value=self.eta.value, inline=True)
        log_embed.add_field(name="🏘️ Nome Proprietà", value=self.nome_proprieta.value, inline=False)
        log_embed.add_field(name="🏢 Tipo Proprietà", value=self.tipo_proprieta.value, inline=True)
        log_embed.timestamp = discord.utils.utcnow()
        
        await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)


class MostraProprietaView(discord.ui.View):
    def __init__(self, user: discord.Member, properties: list):
        super().__init__(timeout=None)
        self.user = user
        self.properties = properties

    @discord.ui.button(label="Mostra", style=discord.ButtonStyle.primary, emoji="📢")
    async def mostra_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Crea l'embed pubblico
        embed = discord.Embed(
            title=f"🏠 Proprietà di {self.user.display_name}",
            description=f"{self.user.mention} possiede **{len(self.properties)}** proprietà:",
            color=discord.Color.blue()
        )

        for prop in self.properties:
            property_id, owner_name, owner_surname, owner_age, property_name, property_type, assigned_at = prop
            
            # Formatta la data
            date_str = assigned_at.split()[0] if assigned_at else "N/A"
            
            field_value = (
                f"📝 **Intestatario:** {owner_name} {owner_surname}\n"
                f"🎂 **Età:** {owner_age}\n"
                f"🏢 **Tipo:** {property_type}\n"
                f"📅 **Assegnata il:** {date_str}"
            )
            
            embed.add_field(
                name=f"🏘️ {property_name}",
                value=field_value,
                inline=False
            )

        embed.set_footer(text=f"👤 Mostrato da {interaction.user.display_name}")
        embed.set_thumbnail(url=self.user.display_avatar.url if self.user.display_avatar else None)

        # Invia il messaggio pubblico
        await interaction.response.send_message(
            content=f"Queste sono le proprietà di {self.user.mention}",
            embed=embed
        )


def setup_property_commands(bot: commands.Bot):
    
    @bot.tree.command(name="daiproprieta", description="[AGENZIA] Assegna una proprietà a un cittadino")
    @app_commands.describe(utente="Il cittadino a cui assegnare la proprietà")
    async def daiproprieta(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, AGENZIA_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Solo l'Agenzia Immobiliare può usare questo comando! (Richiesto: <@&{AGENZIA_ROLE_ID}>)",
                ephemeral=True
            )
            return

        if utente.bot:
            await interaction.response.send_message("❌ Non puoi assegnare proprietà a un bot.", ephemeral=True)
            return

        # Apri il modal
        modal = ProprietaModal(bot, utente)
        await interaction.response.send_modal(modal)

    @bot.tree.command(name="mie-proprieta", description="Visualizza le tue proprietà")
    async def mie_proprieta(interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Recupera le proprietà dell'utente
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                """SELECT id, owner_name, owner_surname, owner_age, property_name, property_type, assigned_at 
                   FROM properties 
                   WHERE user_id = ? 
                   ORDER BY assigned_at DESC""",
                (user_id,)
            ) as cursor:
                properties = await cursor.fetchall()

        if not properties:
            await interaction.followup.send(
                "❌ Non possiedi alcuna proprietà registrata.\n💡 Contatta l'Agenzia Immobiliare per acquistarne una!",
                ephemeral=True
            )
            return

        # Crea l'embed privato con le proprietà
        embed = discord.Embed(
            title=f"🏠 Le Tue Proprietà",
            description=f"Hai **{len(properties)}** proprietà registrate:",
            color=discord.Color.blue()
        )

        for prop in properties:
            property_id, owner_name, owner_surname, owner_age, property_name, property_type, assigned_at = prop
            
            # Formatta la data
            date_str = assigned_at.split()[0] if assigned_at else "N/A"
            
            field_value = (
                f"📝 **Intestatario:** {owner_name} {owner_surname}\n"
                f"🎂 **Età:** {owner_age}\n"
                f"🏢 **Tipo:** {property_type}\n"
                f"📅 **Assegnata il:** {date_str}"
            )
            
            embed.add_field(
                name=f"🏘️ {property_name}",
                value=field_value,
                inline=False
            )

        embed.set_footer(text=f"👤 Proprietà di {interaction.user.display_name}")
        embed.set_thumbnail(url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)

        # Crea la view con il bottone "Mostra"
        view = MostraProprietaView(interaction.user, properties)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        # NESSUN LOG per questo comando come richiesto
