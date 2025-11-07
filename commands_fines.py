import discord
from discord import app_commands
from discord.ext import commands
import database # Assumo che tu abbia un modulo 'database'
from datetime import datetime
import aiohttp # NECESSARIO per inviare messaggi a Webhook esterni

# --- COSTANTI AGGIORNATE ---
LFD_ROLE_ID = 1415093546549248040
LOG_CHANNEL_ID = 1415297578022604850
LFD_LOG_CHANNEL_ID = 1424007218554208316
# NUOVA COSTANTE: L'URL del Webhook per i log di arresto
# ATTENZIONE: Questo Webhook è esposto pubblicamente. Gestiscilo con cura!
ARRESTO_WEBHOOK_URL = "https://discord.com/api/webhooks/1436348492376445000/oHUsctv4kcRwePtWcVcMfaFaxz7E8V8fXZUNWc2G2_GQARjsMTbV9HfbuYf5G8i2Zreq"
# ----------------------------


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
        # Gestione silenziosa degli errori di logging
        pass

# --- NUOVA FUNZIONE PER IL LOG TRAMITE WEBHOOK ESTERNO ---
async def log_arresto_webhook(embed: discord.Embed):
    """
    Invia l'embed di log all'URL del Webhook esterno utilizzando aiohttp.
    """
    if not ARRESTO_WEBHOOK_URL:
        return
        
    # Discord Webhook necessita di un formato JSON specifico
    payload = {
        "embeds": [embed.to_dict()]
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # Invio della richiesta POST al Webhook
            await session.post(ARRESTO_WEBHOOK_URL, json=payload)
        except Exception:
            # Fallimento nell'invio del log, gestito silenziosamente
            pass
# ---------------------------------------------------------


class FineModal(discord.ui.Modal, title="<a:sirena:1431792628332101723> Multa"):
    name_input = discord.ui.TextInput(label="Nome", placeholder="Nome dell'arrestato", required=True)
    surname_input = discord.ui.TextInput(label="Cognome", placeholder="Cognome dell'arrestato", required=True)
    age_input = discord.ui.TextInput(label="Età", placeholder="Età", required=True, max_length=3)
    infractions_input = discord.ui.TextInput(
        label="Infrazioni",
        placeholder="Descrivi le infrazioni",
        style=discord.TextStyle.paragraph,
        required=True
    )
    fine_amount_input = discord.ui.TextInput(
        label="Multa da pagare",
        placeholder="Importo in $",
        required=True,
        max_length=10
    )

    def __init__(self, bot, user_id: str):
        super().__init__()
        self.bot = bot
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            fine_amount = int(self.fine_amount_input.value)
            if fine_amount <= 0:
                await interaction.response.send_message("<a:annulla:1431940396635652146> L'importo deve essere maggiore di 0!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("<a:annulla:1431940396635652146> Importo non valido!", ephemeral=True)
            return
        
        await database.create_fine(
            self.user_id,
            self.name_input.value,
            self.surname_input.value,
            self.age_input.value,
            self.infractions_input.value,
            fine_amount
        )
        
        embed = discord.Embed(
            title="<a:sirena:1431792628332101723> MULTA RICEVUTA",
            color=discord.Color.red()
        )
        embed.add_field(name="👤 Nome", value=self.name_input.value, inline=True)
        embed.add_field(name="👤 Cognome", value=self.surname_input.value, inline=True)
        embed.add_field(name="🎂 Età", value=self.age_input.value, inline=True)
        embed.add_field(name="⚖️ Infrazioni", value=self.infractions_input.value, inline=False)
        embed.add_field(name="💰 Multa", value=f"${fine_amount:,}", inline=False)
        
        try:
            user = await self.bot.fetch_user(int(self.user_id))
            await user.send(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(f"<a:spunta:1431937738256552036> Multa inviata a <@{self.user_id}>!", ephemeral=True)
        await log_command(self.bot, LOG_CHANNEL_ID, f"<a:sirena:1431792628332101723> {interaction.user.mention} ha multato <@{self.user_id}> per ${fine_amount:,}")


# --- NUOVO MODAL PER L'ARRESTO ---
class ArrestoModal(discord.ui.Modal, title="<a:sirena:1431792628332101723> Modulo di Arresto"):
    name_input = discord.ui.TextInput(label="Nome arrestato", placeholder="Nome della persona arrestata", required=True)
    surname_input = discord.ui.TextInput(label="Cognome arrestato", placeholder="Cognome della persona arrestata", required=True)
    age_input = discord.ui.TextInput(label="Età", placeholder="Età", required=True, max_length=3)
    residenza_input = discord.ui.TextInput(label="Residenza (se presente)", placeholder="Residenza", required=False)
    motivo_input = discord.ui.TextInput(
        label="Motivo arresto",
        placeholder="Descrivi il motivo dell'arresto",
        style=discord.TextStyle.paragraph,
        required=True
    )
    pena_input = discord.ui.TextInput(label="Pena", placeholder="Esempio: 20 minuti in prigione", required=True)

    def __init__(self, arrested_user: discord.Member):
        super().__init__(timeout=300) # Aggiungo un timeout, buona pratica
        self.arrested_user = arrested_user

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Creazione dell'Embed Blu (come richiesto)
        embed = discord.Embed(
            title="<a:sirena:1431792628332101723> CITTADINO ARRESTATO",
            color=discord.Color.blue() # Colore blu richiesto
        )
        
        # Aggiunta delle informazioni dell'arrestato
        arrestato_tag = self.arrested_user.mention
        esecutore_tag = interaction.user.mention
        
        embed.add_field(name="👤 Dati Arrestato", value=f"**Nome:** {self.name_input.value}\n**Cognome:** {self.surname_input.value}\n**Età:** {self.age_input.value}\n**Tag Discord:** {arrestato_tag}", inline=False) # Tag arrestato
        embed.add_field(name="🏠 Residenza", value=self.residenza_input.value if self.residenza_input.value else "N/D", inline=True)
        embed.add_field(name="👮 Esecutore", value=esecutore_tag, inline=True) # Tag esecutore
        embed.add_field(name="⚖️ Motivo", value=self.motivo_input.value, inline=False)
        embed.add_field(name="🚨 Pena", value=self.pena_input.value, inline=False)
        
        embed.timestamp = datetime.now()

        # 2. Invio del log al Webhook esterno
        await log_arresto_webhook(embed)
        
        # 3. Risposta all'interazione (conferma)
        await interaction.response.send_message(
            f"<a:spunta:1431937738256552036> Modulo di arresto inviato per **{self.arrested_user.display_name}**! Log registrato nel canale Webhook.", 
            ephemeral=True
        )
        
        # Log di backup nel canale di log interno (opzionale)
        await log_command(interaction.client, LOG_CHANNEL_ID, f"🚓 {interaction.user.mention} ha compilato un modulo di arresto per {self.arrested_user.mention}.")
# ---------------------------------


def setup_fine_commands(bot: commands.Bot):
    
    @bot.tree.command(name="multa", description="[LFD] Emetti una multa")
    @app_commands.describe(utente="L'utente da multare")
    async def multa(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("<a:annulla:1431940396635652146> Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        modal = FineModal(bot, str(utente.id))
        await interaction.response.send_modal(modal)

    # --- NUOVO COMANDO: /modulo-arresto ---
    @bot.tree.command(name="modulo-arresto", description="[LFD] Compila un modulo di arresto e logga con Webhook.")
    @app_commands.describe(cittadino="La persona da arrestare (tag)")
    async def modulo_arresto(interaction: discord.Interaction, cittadino: discord.Member):
        # Controllo del ruolo LFD
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("<a:annulla:1431940396635652146> Solo i LFD (<@&1415093546549248040>) possono usare questo comando!", ephemeral=True)
            return
        
        # Apre il Modal all'utente
        modal = ArrestoModal(cittadino)
        await interaction.response.send_modal(modal)
    # ---------------------------------------
    
    class FineSelectMenu(discord.ui.Select):
        def __init__(self, fines, user_id):
            self.user_id = user_id
            self.fine_map = {}
            options = []
            
            for fine in fines:
                fine_id, name, surname, infractions, fine_amount = fine
                self.fine_map[str(fine_id)] = fine
                options.append(
                    discord.SelectOption(
                        label=f"{name} {surname} - ${fine_amount:,}",
                        description=infractions[:100],
                        value=str(fine_id)
                    )
                )
            
            super().__init__(placeholder="Seleziona una multa da pagare", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Questo non è il tuo menu!", ephemeral=True)
                return
            
            fine_id = int(self.values[0])
            fine = await database.get_fine(fine_id)
            
            if not fine:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Multa non trovata!", ephemeral=True)
                return
            
            _, user_id, name, surname, age, infractions, fine_amount, paid, _ = fine
            
            if paid:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Questa multa è già stata pagata!", ephemeral=True)
                return
            
            user = await database.get_user(user_id)
            total = user["cash"] + user["bank"]
            
            if total < fine_amount:
                await interaction.response.send_message("<a:annulla:1431940396635652146> Non hai abbastanza soldi per pagare questa multa!", ephemeral=True)
                return
            
            new_cash = user["cash"]
            new_bank = user["bank"]
            remaining = fine_amount
            
            if new_bank >= remaining:
                new_bank -= remaining
            else:
                remaining -= new_bank
                new_bank = 0
                new_cash -= remaining
            
            await database.update_balance(user_id, cash=new_cash, bank=new_bank)
            await database.pay_fine(fine_id)
            
            log_embed = discord.Embed(
                title="<a:saccodisoldi:1433965141145161770> MULTA PAGATA",
                color=discord.Color.green()
            )
            log_embed.add_field(name="👤 Nome", value=name, inline=True)
            log_embed.add_field(name="👤 Cognome", value=surname, inline=True)
            log_embed.add_field(name="🎂 Età", value=age, inline=True)
            log_embed.add_field(name="⚖️ Infrazioni", value=infractions, inline=False)
            log_embed.add_field(name="💰 Multa", value=f"${fine_amount:,}", inline=False)
            log_embed.timestamp = datetime.now()
            
            await log_command(bot, LFD_LOG_CHANNEL_ID, embed=log_embed)
            await interaction.response.send_message(f"<a:spunta:1431937738256552036> Hai pagato la multa di **${fine_amount:,}**!", ephemeral=True)
            await log_command(bot, LOG_CHANNEL_ID, f"💳 {interaction.user.mention} ha pagato una multa di ${fine_amount:,}")
    
    @bot.tree.command(name="pagamulta", description="Paga una multa ricevuta")
    async def pagamulta(interaction: discord.Interaction):
        fines = await database.get_unpaid_fines(str(interaction.user.id))
        
        if not fines:
            await interaction.response.send_message(" Non hai multe da pagare!", ephemeral=True)
            return
        
        view = discord.ui.View()
        view.add_item(FineSelectMenu(fines, str(interaction.user.id)))
        
        await interaction.response.send_message("<a:sirena:1431792628332101723> Seleziona una multa da pagare:", view=view, ephemeral=True)
    
    @bot.tree.command(name="controllomulta", description="[LFD] Controlla le multe di un utente")
    @app_commands.describe(utente="L'utente di cui controllare le multe")
    async def controllomulta(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("<a:annulla:1431940396635652146> Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        fines = await database.get_unpaid_fines(str(utente.id))
        
        if not fines:
            await interaction.response.send_message(f"<a:spunta:1431937738256552036> {utente.mention} non ha multe da pagare!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"<a:sirena:1431792628332101723> MULTE DI {utente.display_name}",
            color=discord.Color.red()
        )
        
        total_fines = 0
        for fine_id, name, surname, infractions, fine_amount in fines:
            total_fines += fine_amount
            embed.add_field(
                name=f"Multa #{fine_id}",
                value=f"**Nome:** {name} {surname}\n**Infrazioni:** {infractions}\n**Importo:** ${fine_amount:,}",
                inline=False
            )
        
        embed.add_field(name="💰 TOTALE MULTE", value=f"${total_fines:,}", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"👁️ {interaction.user.mention} ha controllato le multe di {utente.mention}")

# Fine dello script completo
