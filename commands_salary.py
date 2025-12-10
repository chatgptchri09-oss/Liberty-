import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

# ===================================================================================
# COSTANTI E FUNZIONI DI SUPPORTO
# Queste costanti e funzioni sono state dedotte dai tuoi altri file (es. commands_fines.py)
# ===================================================================================

# Definizione dei nomi usati nei tuoi altri script
DATABASE_NAME = "economy_bot.db" 
LOG_CHANNEL_ID = 1415297578022604850 # Esempio dal tuo codice. Assicurati sia corretto.
STAFF_ROLE_ID = 1414738761207517214  # Esempio dal tuo codice. Assicurati sia corretto.

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
    except Exception as e:
        # Puoi loggare l'errore se il logging fallisce, ma per ora lo ignoriamo come nel tuo codice
        pass

# ===================================================================================
# CLASSI E COMANDI PER LA RICHIESTA STIPENDIO
# ===================================================================================

class RichiestaStipendioModal(discord.ui.Modal, title="💰 Richiesta Stipendio"):
    busta_paga = discord.ui.TextInput(label="Busta Paga", placeholder="Importo in $", required=True)

    def __init__(self, bot: commands.Bot, lavoro: discord.Role, allegato: discord.Attachment = None):
        super().__init__()
        self.bot = bot
        self.lavoro = lavoro
        self.allegato = allegato

    async def on_submit(self, interaction: discord.Interaction):
    # Validazione importo
    try:
        # Rimuove le virgole (,) se l'utente le usa per migliaia
        amount_str = self.busta_paga.value.replace(',', '').replace('$', '').strip()
        amount = int(amount_str)
        
        if amount <= 0:
            await interaction.response.send_message("❌ L'importo deve essere maggiore di 0!", ephemeral=True)
            return
    except ValueError:
        await interaction.response.send_message("❌ Importo non valido! Inserisci solo numeri interi.", ephemeral=True)
        return

    embed = discord.Embed(
        title="💰 𝐑𝐈𝐂𝐇𝐈𝐄𝐒𝐓𝐀 𝐒𝐓𝐈𝐏𝐄𝐍𝐃𝐈𝐎",
        color=discord.Color.gold()
    )
    embed.add_field(name="👤 𝐔𝐓𝐄𝐍𝐓𝐄", value=interaction.user.mention, inline=False)
    embed.add_field(name="📆 𝐋𝐀𝐕𝐎𝐑𝐎 𝐒𝐕𝐎𝐋𝐓𝐎", value=self.lavoro.mention, inline=False)
    # Formatta l'importo con le virgole per chiarezza (es. 50,000)
    embed.add_field(name="📥 𝐁𝐔𝐒𝐓𝐀 𝐏𝐀𝐆𝐀", value=f"${amount:,.2f}" if amount % 1 != 0 else f"${amount:,}", inline=False)


    # Se c'è allegato immagine, la mostra nell'embed
    if self.allegato and self.allegato.content_type and self.allegato.content_type.startswith("image/"):
        embed.set_image(url=self.allegato.url)
    elif self.allegato:
         # Se l'allegato non è un'immagine, aggiunge un link
        embed.add_field(name="🔗 Allegato Prova", value=f"[Visualizza Allegato]({self.allegato.url})", inline=False)


    view = StipendioView(self.bot, str(interaction.user.id), amount)
    
    # Risposta ephemeral all'utente
    await interaction.response.send_message("✅ Richiesta stipendio inviata!", ephemeral=True)
    
    # Invia il messaggio NEL CANALE dove è stato usato il comando
    await interaction.channel.send(content="<@&1414738761207517214>", embed=embed, view=view)


class StipendioView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str, amount: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.amount = amount

    @discord.ui.button(label="✅ Accetta", style=discord.ButtonStyle.green)
    async def accetta(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica se l'utente che clicca è STAFF
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo gli staff possono accettare richieste!", ephemeral=True)
            return

        # Connessione al database e aggiornamento del conto bancario
        async with aiosqlite.connect(DATABASE_NAME) as db:
            # 1. Recupera il saldo attuale
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (self.user_id,)) as cursor:
                user = await cursor.fetchone()

            if user:
                # 2. Calcola il nuovo saldo
                new_bank = user[0] + self.amount
                # 3. Aggiorna il database
                await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_bank, self.user_id))
                await db.commit()
            else:
                 # Se l'utente non è nel DB, crealo con il saldo iniziale e lo stipendio
                await db.execute("INSERT OR IGNORE INTO users (user_id, bank) VALUES (?, ?)", (self.user_id, self.amount + 20000)) # Assumendo 20000 come saldo iniziale
                await db.commit()
        
        # Invia messaggio privato all'utente
        try:
            user = await self.bot.fetch_user(int(self.user_id))
            await user.send(f"✅ La tua richiesta stipendio di **${self.amount:,}** è stata accettata da {interaction.user.mention}!")
        except Exception:
            pass

        # Cancella il messaggio originale e invia la conferma
        await interaction.message.delete()
        await interaction.response.send_message(f"✅ Richiesta stipendio accettata e **${self.amount:,}** erogati per <@{self.user_id}>!", ephemeral=True)
        
        # Log
        await log_command(self.bot, LOG_CHANNEL_ID, f"💰 {interaction.user.mention} ha accettato stipendio di ${self.amount:,} per <@{self.user_id}>")

    @discord.ui.button(label="❌ Rifiuta", style=discord.ButtonStyle.red)
    async def rifiuta(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verifica se l'utente che clicca è STAFF
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo gli staff possono rifiutare richieste!", ephemeral=True)
            return

        # Invia messaggio privato all'utente (opzionale: potresti voler inviare anche qui un messaggio)
        try:
            user = await self.bot.fetch_user(int(self.user_id))
            await user.send(f"❌ La tua richiesta stipendio di **${self.amount:,}** è stata rifiutata da {interaction.user.mention}.")
        except Exception:
            pass

        # Cancella il messaggio originale e invia la conferma
        await interaction.message.delete()
        await interaction.response.send_message(f"❌ Richiesta stipendio rifiutata per <@{self.user_id}>!", ephemeral=True)
        
        # Log
        await log_command(self.bot, LOG_CHANNEL_ID, f"❌ {interaction.user.mention} ha rifiutato stipendio per <@{self.user_id}>")


def setup_salary_commands(bot: commands.Bot):
    """Registra i comandi al tree del bot e li rende disponibili."""
    
    @bot.tree.command(name="richiesta-stipendio", description="Richiedi uno stipendio")
    @app_commands.describe(
        lavoro_svolto="Il ruolo del lavoro svolto",
        allegato="Carica una prova (immagine, facoltativo)"
    )
    async def richiesta_stipendio(interaction: discord.Interaction, lavoro_svolto: discord.Role, allegato: discord.Attachment = None):
        # Controllo ruolo: verifica se l'utente possiede il ruolo per cui richiede lo stipendio
        if lavoro_svolto not in interaction.user.roles:
            await interaction.response.send_message(
                f"❌ Non puoi richiedere uno stipendio per **{lavoro_svolto.name}** perché non hai questo ruolo!",
                ephemeral=True
            )
            await log_command(bot, LOG_CHANNEL_ID, f"⚠️ {interaction.user.mention} ha tentato richiesta stipendio per {lavoro_svolto.name} senza avere il ruolo")
            return

        modal = RichiestaStipendioModal(bot, lavoro_svolto, allegato)
        await interaction.response.send_modal(modal)
