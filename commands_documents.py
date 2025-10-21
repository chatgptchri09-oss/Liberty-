import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850

LFD_ROLE_ID = 1415093546549248040
EMS_ROLE_ID = 1415239481757536256
ARMERIA_ROLE_ID = 1415092383250382858
CONCESSIONARIO_ROLE_ID = 1415238213303406702
STAFF_ROLE_ID = 1414738761207517214

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            await channel.send(message)
    except:
        pass

def setup_document_commands(bot: commands.Bot):
    
    class DocumentoModal(discord.ui.Modal, title="📄 Documento"):
        nome = discord.ui.TextInput(label="Nome", required=True)
        cognome = discord.ui.TextInput(label="Cognome", required=True)
        data_nascita = discord.ui.TextInput(label="Data di nascita (GG/MM/AAAA)", placeholder="01/01/1990", required=True)
        luogo_nascita = discord.ui.TextInput(label="Luogo di nascita", required=True)
        nazionalita = discord.ui.TextInput(label="Nazionalità", required=True)

        def __init__(self, bot, user_id: str, photo_url: str):
            super().__init__()
            self.bot = bot
            self.user_id = user_id
            self.photo_url = photo_url

        async def on_submit(self, interaction: discord.Interaction):
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO documents (user_id, name, surname, birth_date, birth_place, nationality, photo_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (self.user_id, self.nome.value, self.cognome.value, self.data_nascita.value, self.luogo_nascita.value, self.nazionalita.value, self.photo_url)
                )
                await db.commit()
            
            await interaction.response.send_message(f"✅ Documento registrato per <@{self.user_id}>!", ephemeral=True)
            await log_command(self.bot, LOG_CHANNEL_ID, f"📄 {interaction.user.mention} ha registrato un documento per <@{self.user_id}>")
    
    @bot.tree.command(name="documento", description="[LFD] Crea un documento per un utente")
    @app_commands.describe(
        utente="L'utente per cui creare il documento",
        foto="Carica la foto da allegare"
    )
    async def documento(interaction: discord.Interaction, utente: discord.Member, foto: discord.Attachment):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        photo_url = foto.url
        modal = DocumentoModal(bot, str(utente.id), photo_url)
        await interaction.response.send_modal(modal)
    
    @bot.tree.command(name="rimuovi-documento", description="[STAFF] Rimuovi il documento di un utente")
    @app_commands.describe(utente="L'utente a cui rimuovere il documento")
    async def rimuovi_documento(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT * FROM documents WHERE user_id = ?", (str(utente.id),)) as cursor:
                doc = await cursor.fetchone()
            
            if not doc:
                await interaction.response.send_message(f"❌ {utente.mention} non possiede un documento!", ephemeral=True)
                return
            
            await db.execute("DELETE FROM documents WHERE user_id = ?", (str(utente.id),))
            await db.commit()
        
        await interaction.response.send_message(f"✅ Documento rimosso da {utente.mention}!", ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"🗑️ {interaction.user.mention} ha rimosso il documento di {utente.mention}")
        
        try:
            await utente.send("⚠️ Il tuo documento è stato rimosso da uno staff!")
        except:
            pass
    
    class PatenteModal(discord.ui.Modal, title="🚗 Patente"):
        nome = discord.ui.TextInput(label="Nome Cliente", required=True)
        cognome = discord.ui.TextInput(label="Cognome Cliente", required=True)
        tipo = discord.ui.TextInput(label="Tipo di Patente", placeholder="Es: B, A, C", required=True)

        def __init__(self, bot, user_id: str):
            super().__init__()
            self.bot = bot
            self.user_id = user_id

        async def on_submit(self, interaction: discord.Interaction):
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO licenses (user_id, name, surname, license_type) VALUES (?, ?, ?, ?)",
                    (self.user_id, self.nome.value, self.cognome.value, self.tipo.value)
                )
                await db.commit()
            
            await interaction.response.send_message(f"✅ Patente registrata per <@{self.user_id}>!", ephemeral=True)
            await log_command(self.bot, LOG_CHANNEL_ID, f"🚗 {interaction.user.mention} ha registrato una patente per <@{self.user_id}>")
    
    @bot.tree.command(name="daipatente", description="[CONCESSIONARIO] Registra una patente")
    @app_commands.describe(utente="L'utente per cui registrare la patente")
    async def daipatente(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, CONCESSIONARIO_ROLE_ID):
            await interaction.response.send_message("❌ Solo il Concessionario può usare questo comando!", ephemeral=True)
            return
        
        modal = PatenteModal(bot, str(utente.id))
        await interaction.response.send_modal(modal)
    
    class PortoDarmiModal(discord.ui.Modal, title="🔫 Porto d'Armi"):
        nome = discord.ui.TextInput(label="Nome Cittadino", required=True)
        cognome = discord.ui.TextInput(label="Cognome Cittadino", required=True)
        eta = discord.ui.TextInput(label="Età Cittadino", required=True, max_length=3)
        livello = discord.ui.TextInput(label="Livello porto d'armi", placeholder="Es: 1, 2, 3", required=True)

        def __init__(self, bot, user_id: str):
            super().__init__()
            self.bot = bot
            self.user_id = user_id

        async def on_submit(self, interaction: discord.Interaction):
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO gun_licenses (user_id, name, surname, age, level) VALUES (?, ?, ?, ?, ?)",
                    (self.user_id, self.nome.value, self.cognome.value, self.eta.value, self.livello.value)
                )
                await db.commit()
            
            await interaction.response.send_message(f"✅ Porto d'armi registrato per <@{self.user_id}>!", ephemeral=True)
            await log_command(self.bot, LOG_CHANNEL_ID, f"🔫 {interaction.user.mention} ha registrato un porto d'armi per <@{self.user_id}>")
    
    @bot.tree.command(name="daiportodarmi", description="[LFD] Registra un porto d'armi")
    @app_commands.describe(utente="L'utente per cui registrare il porto d'armi")
    async def daiportodarmi(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        modal = PortoDarmiModal(bot, str(utente.id))
        await interaction.response.send_modal(modal)
    
    class LibrettoModal(discord.ui.Modal, title="📋 Libretto"):
        nome = discord.ui.TextInput(label="Nome Cliente", required=True)
        cognome = discord.ui.TextInput(label="Cognome Cliente", required=True)
        modello = discord.ui.TextInput(label="Modello Del Veicolo", required=True)
        targa = discord.ui.TextInput(label="Targa", required=True)

        def __init__(self, bot, user_id: str):
            super().__init__()
            self.bot = bot
            self.user_id = user_id

        async def on_submit(self, interaction: discord.Interaction):
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO vehicle_registrations (user_id, client_name, client_surname, vehicle_model, plate, modifications) VALUES (?, ?, ?, ?, ?, ?)",
                    (self.user_id, self.nome.value, self.cognome.value, self.modello.value, self.targa.value, "/////")
                )
                await db.commit()
            
            await interaction.response.send_message(f"✅ Libretto registrato per <@{self.user_id}>!", ephemeral=True)
            await log_command(self.bot, LOG_CHANNEL_ID, f"📋 {interaction.user.mention} ha registrato un libretto per <@{self.user_id}>")
    
    @bot.tree.command(name="dailibretto", description="[CONCESSIONARIO] Registra un libretto")
    @app_commands.describe(cliente="Il cliente per cui registrare il libretto")
    async def dailibretto(interaction: discord.Interaction, cliente: discord.Member):
        if not has_role(interaction, CONCESSIONARIO_ROLE_ID):
            await interaction.response.send_message("❌ Solo il Concessionario può usare questo comando!", ephemeral=True)
            return
        
        modal = LibrettoModal(bot, str(cliente.id))
        await interaction.response.send_modal(modal)
    
    class CertificatoMedicoModal(discord.ui.Modal, title="🏥 Certificato Medico"):
        nome = discord.ui.TextInput(label="Nome Paziente", required=True)
        cognome = discord.ui.TextInput(label="Cognome Paziente", required=True)
        eta = discord.ui.TextInput(label="Età Paziente", required=True, max_length=3)
        esito = discord.ui.TextInput(label="Esito (positivo/negativo)", required=True)

        def __init__(self, bot, user_id: str):
            super().__init__()
            self.bot = bot
            self.user_id = user_id

        async def on_submit(self, interaction: discord.Interaction):
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO medical_certificates (user_id, patient_name, patient_surname, patient_age, result) VALUES (?, ?, ?, ?, ?)",
                    (self.user_id, self.nome.value, self.cognome.value, self.eta.value, self.esito.value)
                )
                await db.commit()
            
            await interaction.response.send_message(f"✅ Certificato medico registrato per <@{self.user_id}>!", ephemeral=True)
            await log_command(self.bot, LOG_CHANNEL_ID, f"🏥 {interaction.user.mention} ha registrato un certificato medico per <@{self.user_id}>")
    
    @bot.tree.command(name="daicertificatomedico", description="[EMS] Registra un certificato medico")
    @app_commands.describe(utente="L'utente per cui registrare il certificato")
    async def daicertificatomedico(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, EMS_ROLE_ID):
            await interaction.response.send_message("❌ Solo gli EMS possono usare questo comando!", ephemeral=True)
            return
        
        modal = CertificatoMedicoModal(bot, str(utente.id))
        await interaction.response.send_modal(modal)
    
    class CertificatoBalisticoModal(discord.ui.Modal, title="🎯 Certificato Balistico"):
        nome = discord.ui.TextInput(label="Nome Cliente", required=True)
        cognome = discord.ui.TextInput(label="Cognome Cliente", required=True)
        eta = discord.ui.TextInput(label="Età Cliente", required=True, max_length=3)
        esito = discord.ui.TextInput(label="Esito (positivo/negativo)", required=True)

        def __init__(self, bot, user_id: str):
            super().__init__()
            self.bot = bot
            self.user_id = user_id

        async def on_submit(self, interaction: discord.Interaction):
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await db.execute(
                    "INSERT INTO ballistic_certificates (user_id, client_name, client_surname, client_age, result) VALUES (?, ?, ?, ?, ?)",
                    (self.user_id, self.nome.value, self.cognome.value, self.eta.value, self.esito.value)
                )
                await db.commit()
            
            await interaction.response.send_message(f"✅ Certificato balistico registrato per <@{self.user_id}>!", ephemeral=True)
            await log_command(self.bot, LOG_CHANNEL_ID, f"🎯 {interaction.user.mention} ha registrato un certificato balistico per <@{self.user_id}>")
    
    @bot.tree.command(name="daicertificatobalistico", description="[ARMERIA] Registra un certificato balistico")
    @app_commands.describe(utente="L'utente per cui registrare il certificato")
    async def daicertificatobalistico(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, ARMERIA_ROLE_ID):
            await interaction.response.send_message("❌ Solo l'Armeria può usare questo comando!", ephemeral=True)
            return
        
        modal = CertificatoBalisticoModal(bot, str(utente.id))
        await interaction.response.send_modal(modal)
    
    @bot.tree.command(name="rimuovicertificatobalistico", description="[LFD] Rimuovi un certificato balistico da un utente")
    @app_commands.describe(utente="L'utente a cui rimuovere il certificato")
    async def rimuovicertificatobalistico(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT * FROM ballistic_certificates WHERE user_id = ?", (str(utente.id),)) as cursor:
                cert = await cursor.fetchone()
            
            if not cert:
                await interaction.response.send_message(f"❌ {utente.mention} non possiede un certificato balistico!", ephemeral=True)
                return
            
            await db.execute("DELETE FROM ballistic_certificates WHERE user_id = ?", (str(utente.id),))
            await db.commit()
        
        await interaction.response.send_message(f"✅ Certificato balistico rimosso da {utente.mention}!", ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"🗑️ {interaction.user.mention} ha rimosso il certificato balistico di {utente.mention}")
        
        try:
            await utente.send("⚠️ Il tuo certificato balistico è stato rimosso!")
        except:
            pass
    
    @bot.tree.command(name="rimuovicertificatomedico", description="[STAFF] Rimuovi un certificato medico da un utente")
    @app_commands.describe(utente="L'utente a cui rimuovere il certificato")
    async def rimuovicertificatomedico(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo staff può usare questo comando!", ephemeral=True)
            return
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT * FROM medical_certificates WHERE user_id = ?", (str(utente.id),)) as cursor:
                cert = await cursor.fetchone()
            
            if not cert:
                await interaction.response.send_message(f"❌ {utente.mention} non possiede un certificato medico!", ephemeral=True)
                return
            
            await db.execute("DELETE FROM medical_certificates WHERE user_id = ?", (str(utente.id),))
            await db.commit()
        
        await interaction.response.send_message(f"✅ Certificato medico rimosso da {utente.mention}!", ephemeral=True)
        await log_command(bot, LOG_CHANNEL_ID, f"🗑️ {interaction.user.mention} ha rimosso il certificato medico di {utente.mention}")
        
        try:
            await utente.send("⚠️ Il tuo certificato medico è stato rimosso!")
        except:
            pass
