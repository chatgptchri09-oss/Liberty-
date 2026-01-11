import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850

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


def setup_wallet_commands(bot: commands.Bot):
    
    class ShowDocumentView(discord.ui.View):
        def __init__(self, bot: commands.Bot, embed: discord.Embed, message: str):
            super().__init__(timeout=300)
            self.bot = bot
            self.embed = embed
            self.message = message
        
        @discord.ui.button(label="📢 Mostra", style=discord.ButtonStyle.secondary)
        async def show_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message(self.message, embed=self.embed)
            
            

    class WalletSelect(discord.ui.Select):
        def __init__(self, bot: commands.Bot, user_id: str):
            self.bot = bot
            self.user_id = user_id
            options = [
                discord.SelectOption(label="Documento", value="documento", emoji="📄"),
                discord.SelectOption(label="Patente", value="patente", emoji="🚗"),
                discord.SelectOption(label="Porto D'armi", value="portodarmi", emoji="🔫"),
                discord.SelectOption(label="Certificati", value="certificati", emoji="📋"),
                discord.SelectOption(label="Libretti", value="libretti", emoji="📒"),
            ]
            super().__init__(placeholder="Seleziona il documento da visualizzare", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ Questo non è il tuo portafoglio!", ephemeral=True)
                return
            
            selection = self.values[0]
            
            if selection == "documento":
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT * FROM documents WHERE user_id = ?", (self.user_id,)) as cursor:
                        doc = await cursor.fetchone()
                
                if not doc:
                    await interaction.response.send_message("❌ Non hai un documento registrato!", ephemeral=True)
                    return
                
                _, name, surname, birth_date, birth_place, nationality, photo_url = doc
                
                embed = discord.Embed(
                    title="<a:documento:1458563773546893541> DOCUMENTO D'IDENTITÀ <a:documento:1458563773546893541>",
                    color=discord.Color.blue()
                )
                embed.add_field(name="👤 Nome", value=name, inline=True)
                embed.add_field(name="👤 Cognome", value=surname, inline=True)
                embed.add_field(name="📅 Data di nascita", value=birth_date, inline=False)
                embed.add_field(name="🏙️ Luogo di nascita", value=birth_place, inline=False)
                embed.add_field(name="🌍 Nazionalità", value=nationality, inline=False)
                if photo_url:
                    embed.set_image(url=photo_url)
                
                view = ShowDocumentView(self.bot, embed, f"Questo è il documento di {interaction.user.mention}") 
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            elif selection == "patente":
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT * FROM licenses WHERE user_id = ?", (self.user_id,)) as cursor:
                        licenses = await cursor.fetchall()
                
                if not licenses:
                    await interaction.response.send_message("❌ Non hai patenti registrate!", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="🚗 PATENTI",
                    color=discord.Color.green()
                )
                
                for license in licenses:
                    _, user_id, name, surname, license_type = license
                    embed.add_field(
                        name=f"Patente Tipo {license_type}",
                        value=f"**Nome:** {name} {surname}",
                        inline=False
                    )
                
                view = ShowDocumentView(self.bot, embed, f"Queste sono le patenti di {interaction.user.mention}") 
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            elif selection == "portodarmi":
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT * FROM gun_licenses WHERE user_id = ?", (self.user_id,)) as cursor:
                        gun_licenses = await cursor.fetchall()
                
                if not gun_licenses:
                    await interaction.response.send_message("❌ Non hai porti d'armi registrati!", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="🔫 PORTI D'ARMI",
                    color=discord.Color.dark_red()
                )
                
                for gun_license in gun_licenses:
                    _, user_id, name, surname, age, level = gun_license
                    embed.add_field(
                        name=f"Porto d'Armi Livello {level}",
                        value=f"**Nome:** {name} {surname}\n**Età:** {age}",
                        inline=False
                    )
                
                view = ShowDocumentView(self.bot, embed, f"Questi sono i porti d'armi di {interaction.user.mention}")
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            elif selection == "certificati":
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT * FROM medical_certificates WHERE user_id = ?", (self.user_id,)) as cursor:
                        medical_certs = await cursor.fetchall()
                    async with db.execute("SELECT * FROM ballistic_certificates WHERE user_id = ?", (self.user_id,)) as cursor:
                        ballistic_certs = await cursor.fetchall()
                
                if not medical_certs and not ballistic_certs:
                    await interaction.response.send_message("❌ Non hai certificati registrati!", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="📋 CERTIFICATI",
                    color=discord.Color.purple()
                )
                
                for cert in medical_certs:
                    _, user_id, patient_name, patient_surname, patient_age, result = cert
                    embed.add_field(
                        name="🏥 Certificato Medico",
                        value=f"**Nome:** {patient_name} {patient_surname}\n**Età:** {patient_age}\n**Esito:** {result}",
                        inline=False
                    )
                
                for cert in ballistic_certs:
                    _, user_id, client_name, client_surname, client_age, result = cert
                    embed.add_field(
                        name="🎯 Certificato Balistico",
                        value=f"**Nome:** {client_name} {client_surname}\n**Età:** {client_age}\n**Esito:** {result}",
                        inline=False
                    )
                
                view = ShowDocumentView(self.bot, embed, f"Questi sono i certificati di {interaction.user.mention}")
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            elif selection == "libretti":
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute("SELECT * FROM vehicle_registrations WHERE user_id = ? AND seized = 0", (self.user_id,)) as cursor:
                        vehicles = await cursor.fetchall()
                
                if not vehicles:
                    await interaction.response.send_message("❌ Non hai libretti registrati!", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="📒 LIBRETTI",
                    color=discord.Color.orange()
                )
                
                for vehicle in vehicles:
                    # Gestisci sia veicoli con 9 colonne (con illegal) che con 8 (senza illegal)
                    if len(vehicle) == 10:
                        _, user_id, client_name, client_surname, vehicle_model, plate, insurance, modifications, seized, illegal = vehicle
                    else:
                        _, user_id, client_name, client_surname, vehicle_model, plate, insurance, modifications, seized = vehicle
                        illegal = 0  # Default a 0 se la colonna non esiste
                    
                    insurance_text = "✅ Assicurazione" if insurance else "❌ Assicurazione"
                    modifications_text = modifications if modifications and modifications != "/////" else "/////"
                    illegal_text = " (illegale)" if illegal else ""
                    
                    embed.add_field(
                        name=f"🚗 {vehicle_model}{illegal_text}",
                        value=f"**Proprietario:** {client_name} {client_surname}\n**Targa:** {plate}\n**{insurance_text}**\n**Modifiche:** {modifications_text}",
                        inline=False
                    )
                
                view = ShowDocumentView(self.bot, embed, f"Questi sono i libretti di {interaction.user.mention}")
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @bot.tree.command(name="portafoglio", description="Visualizza il tuo portafoglio")
    async def portafoglio(interaction: discord.Interaction):
        embed = discord.Embed(
            title="<a:portafoglio:1454794842302316594> 𝐏𝐎𝐑𝐓𝐀𝐅𝐎𝐆𝐋𝐈𝐎",
            description="Seleziona il documento che vuoi visualizzare dal menu a tendina qui sotto",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url="https://i.postimg.cc/tCSrLbHx/IMG-4544.gif")

        view = discord.ui.View()
        view.add_item(WalletSelect(bot, str(interaction.user.id)))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
