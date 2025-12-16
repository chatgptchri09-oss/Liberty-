import discord
from discord import app_commands
from discord.ext import commands

# ====================
# COSTANTI (DEVONO ESSERE LE STESSE DI bot.py)
# ====================
STAFF_ROLE_ID = 1414738761207517214
LOG_CHANNEL_ID = 1415297578022604850

# ====================
# FUNZIONI DI SUPPORTO
# ====================

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

# ====================
# CLASSE MODAL PER RIFIUTO BANDO
# ====================

class RifiutoMotivoModal(discord.ui.Modal, title="Motivo del Rifiuto Bando"):
    motivo_input = discord.ui.TextInput(
        label="Motivo del Rifiuto", 
        placeholder="Spiega brevemente perché il candidato è stato rifiutato.", 
        style=discord.TextStyle.long, 
        required=True, 
        max_length=500
    )

    def __init__(self, cittadino: discord.Member, lavoro: discord.Role, staff_id: int):
        super().__init__()
        self.cittadino = cittadino
        self.lavoro = lavoro
        self.staff_id = staff_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        staff_member = interaction.guild.get_member(self.staff_id)
        motivo = self.motivo_input.value

        embed = discord.Embed(
            title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐛𝐚𝐧𝐝𝐨 <a:annulla:1431940396635652146>",
            color=discord.Color.red()
        )
        
        description_content = (
            f"**𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼**<a:casomaiconflecia:1434244328448069642> {self.cittadino.mention}\n"
            f"**𝗘𝘀𝗶𝘁𝗼**<a:casomaiconflecia:1434244328448069642> Rifiutato \n"
            f"**𝗟𝗮𝘃𝗼𝗿𝗼**<a:casomaiconflecia:1434244328448069642> {self.lavoro.mention}\n"
            f"**𝗠𝗼𝘁𝗶𝘃𝗼**<a:casomaiconflecia:1434244328448069642> {motivo}\n\n"
            f"▬▬▬▬▬▬▬▬\n"
            f"Da <@&{STAFF_ROLE_ID}>\n"
            f"{staff_member.mention if staff_member else f'<@{self.staff_id}>'}" 
        )
        
        embed.description = description_content
        
        await interaction.channel.send(embed=embed)
        
        await interaction.followup.send(f"✅ Bando Rifiutato inviato con successo.", ephemeral=True)

# ====================
# SETUP COMANDI BANDO
# ====================

def setup_bando_commands(bot: commands.Bot):
    
    @bot.tree.command(name="bando", description="[STAFF] Annuncia l'apertura o chiusura di un bando")
    @app_commands.describe(stato="Seleziona lo stato del bando")
    @app_commands.choices(stato=[
        app_commands.Choice(name="Aperto", value="APERTO"),
        app_commands.Choice(name="Chiuso", value="CHIUSO"),
    ])
    async def bando(interaction: discord.Interaction, stato: app_commands.Choice[str]):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo Staff può usare questo comando.", ephemeral=True)
            return
        
        if stato.value == "APERTO":
            embed = discord.Embed(
                title="<a:Online:1431599470897922069> 𝐁𝐚𝐧𝐝𝐨 𝐀𝐩𝐞𝐫𝐭𝐨 <a:Online:1431599470897922069>",
                description="Lo staff annuncia che le candidature per questo bando sono ufficialmente aperte!",
                color=discord.Color.green()
            )
            embed.set_image(url="https://cdn.discordapp.com/attachments/1235599658928308264/1250595402474848417/BandoAperto.png")
            
            await interaction.response.send_message(embed=embed)
            
    
            
        elif stato.value == "CHIUSO":
            embed = discord.Embed(
                title="<a:offline:1431606235354107914> 𝐁𝐚𝐧𝐝𝐨 𝐂𝐡𝐢𝐮𝐬𝐨 <a:offline:1431606235354107914>",
                description="Lo staff annuncia che le candidature per questo bando sono ufficialmente chiuse.",
                color=discord.Color.red()
            )
            embed.set_image(url="https://cdn.discordapp.com/attachments/1235599658928308264/1250595402223452160/BandoChiuso.png")
            
            await interaction.response.send_message(embed=embed)
            
            
    
    @bot.tree.command(name="esito-bando", description="[STAFF] Gestisce l'esito di un bando lavorativo.")
    @app_commands.describe(
        esito="Seleziona l'esito del bando",
        cittadino="La persona che ha partecipato al bando",
        lavoro="Il ruolo del lavoro principale (Es. L.F.D.)",
        grado="[OPZIONALE] Il grado/rank lavorativo (Es. Cadetto, Agente Semplice)"
    )
    @app_commands.choices(esito=[
        app_commands.Choice(name="Assunto", value="ASSUNTO"),
        app_commands.Choice(name="Rifiutato", value="RIFIUTATO"),
    ])
    async def esito_bando(
        interaction: discord.Interaction, 
        esito: app_commands.Choice[str], 
        cittadino: discord.Member, 
        lavoro: discord.Role,
        grado: discord.Role = None
    ):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo Staff può usare questo comando.", ephemeral=True)
            return
        
        staff_id = interaction.user.id

        # --- Logica RIFIUTATO ---
        if esito.value == "RIFIUTATO":
            modal = RifiutoMotivoModal(cittadino, lavoro, staff_id) 
            await interaction.response.send_modal(modal)
            return 
        
        # --- Logica ASSUNTO ---
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        roles_to_add = []
        
        # 1. Aggiungi il Ruolo Lavoro Principale
        if lavoro not in cittadino.roles:
            roles_to_add.append(lavoro)
        
        # 2. Aggiungi il Ruolo Grado (se specificato)
        if grado and grado not in cittadino.roles:
            roles_to_add.append(grado)

        log_success = "Nessun ruolo aggiunto (Già posseduti)."
        
        # 3. Esegui l'aggiunta dei ruoli
        if roles_to_add:
            try:
                reason = f"Assunzione tramite bando da parte di {interaction.user.name}. Ruoli: {', '.join([r.name for r in roles_to_add])}"
                await cittadino.add_roles(*roles_to_add, reason=reason)
                log_success = f"Ruoli aggiunti: {', '.join([r.name for r in roles_to_add])}"
            except discord.Forbidden:
                await interaction.followup.send("❌ Non sono riuscito ad aggiungere il ruolo per problemi di permessi (Il bot non ha un ruolo abbastanza alto).", ephemeral=True)
                return
            except Exception as e:
                await interaction.followup.send(f"❌ Errore sconosciuto nell'aggiunta ruoli: {e}", ephemeral=True)
                return


        # 4. Creazione dell'Embed di Notifica (Pubblico)
        
        embed = discord.Embed(
            title="<a:megafono:1431932605984542720> 𝐄𝐬𝐢𝐭𝐨 𝐛𝐚𝐧𝐝𝐨 <a:si:1433573748891582566>",
            color=discord.Color.green()
        )
        
        description_content = (
            f"**𝗖𝗶𝘁𝘁𝗮𝗱𝗶𝗻𝗼**<a:casomaiconflecia:1434244328448069642> {cittadino.mention}\n"
            f"**𝗘𝘀𝗶𝘁𝗼**<a:casomaiconflecia:1434244328448069642> Assunto \n"
            f"**𝗟𝗮𝘃𝗼𝗿𝗼**<a:casomaiconflecia:1434244328448069642> {lavoro.mention}\n"
        )
        
        if grado:
            description_content += f"**𝗚𝗿𝗮𝗱𝗼**<a:casomaiconflecia:1434244328448069642> {grado.mention}\n"
            
        description_content += (
            f"\n▬▬▬▬▬▬▬▬\n"
            f"Da <@&{STAFF_ROLE_ID}>\n"
            f"{interaction.user.mention}" 
        )
        
        embed.description = description_content
        
        await interaction.channel.send(embed=embed)
        
        # 5. Risposta finale (Ephemera)
        await interaction.followup.send(f"✅ Bando Assunto inviato con successo e ruoli aggiunti a {cittadino.mention}.", ephemeral=True)
        
       
        )
