import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1479158931610931414
LOG_CHANNEL_MONEY_ID = 1479158931610931414
CHIAVE_ROLE_ID = 1404051860121456701

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


def setup_bonifico_commands(bot: commands.Bot):
    
    @bot.tree.command(name="paga", description="Invia denaro tramite pagamento fisico")
    @app_commands.describe(
        utente="L'utente a cui dare il denaro",
        importo="La cifra da dare dal tuo conto bancario",
        motivo="Il motivo del pagamento"
    )
    async def bonifico(interaction: discord.Interaction, utente: discord.Member, importo: int, motivo: str):
        
        sender_id = str(interaction.user.id)
        receiver_id = str(utente.id)
        
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            return 

        try:
            if importo <= 0:
                await interaction.followup.send("❌ L'importo del bonifico deve essere maggiore di zero!", ephemeral=True)
                return
            
            if sender_id == receiver_id:
                await interaction.followup.send("❌ Non puoi effettuare un bonifico a te stesso!", ephemeral=True)
                return
            
            if utente.bot:
                await interaction.followup.send("❌ Non puoi effettuare un bonifico a un bot!", ephemeral=True)
                return
            
            sender_data = await database.get_user(sender_id)
            receiver_data = await database.get_user(receiver_id)
            
            sender_bank_balance = sender_data['bank']
            receiver_bank_balance = receiver_data['bank']

            if sender_bank_balance < importo:
                await interaction.followup.send(
                    f"❌ Non hai abbastanza fondi in banca! (Saldo: **${sender_bank_balance:,}**)", 
                    ephemeral=True
                )
                return
            
            new_sender_bank = sender_bank_balance - importo
            new_receiver_bank = receiver_bank_balance + importo

            await database.update_balance(sender_id, bank=new_sender_bank)
            await database.update_balance(receiver_id, bank=new_receiver_bank)

            try:
                embed_dm = discord.Embed(
                    title="💸 Bonifico Ricevuto!",
                    description=f"Hai ricevuto un bonifico di **${importo:,}** in banca da {interaction.user.mention}.",
                    color=discord.Color.green()
                )
                embed_dm.add_field(name="Motivo", value=f"_{motivo}_", inline=False)
                embed_dm.set_footer(text=f"Il tuo nuovo saldo bancario è: ${new_receiver_bank:,}")
                await utente.send(embed=embed_dm)
            except:
                pass 
            
            # Messaggio pubblico nel canale
            await interaction.channel.send(
                f"✅ {interaction.user.mention} ha inviato **${importo:,}** a {utente.mention} per: _{motivo}_"
            )
                
            await interaction.followup.send(
                f"<a:spunta:1431937738256552036> Bonifico completato! Hai inviato **${importo:,}** a {utente.mention}.\n"
                f"Il tuo nuovo saldo bancario è: **${new_sender_bank:,}**",
                ephemeral=True
            )

            # LOG CON EMBED
            log_embed = discord.Embed(
                title="💸 LOG BONIFICO",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Mittente", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Destinatario", value=utente.mention, inline=True)
            log_embed.add_field(name="Importo", value=f"${importo:,}", inline=True)
            log_embed.add_field(name="Motivo", value=motivo[:1024], inline=False)
            log_embed.add_field(name="Nuovo saldo mittente", value=f"${new_sender_bank:,}", inline=True)
            log_embed.add_field(name="Nuovo saldo destinatario", value=f"${new_receiver_bank:,}", inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_MONEY_ID, embed=log_embed)

        except Exception as e:
            print(f"ERRORE GRAVE DURANTE BONIFICO: {e}")
            
            # LOG ERRORE CON EMBED
            error_log_embed = discord.Embed(
                title="❌ LOG ERRORE BONIFICO",
                color=discord.Color.dark_red()
            )
            error_log_embed.add_field(name="Mittente", value=interaction.user.mention, inline=True)
            error_log_embed.add_field(name="Destinatario", value=utente.mention, inline=True)
            error_log_embed.add_field(name="Importo", value=f"${importo:,}", inline=True)
            error_log_embed.add_field(name="Errore", value=str(e)[:1000], inline=False)
            error_log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=error_log_embed)
            
            await interaction.followup.send(
                f"❌ Si è verificato un errore critico durante il bonifico. Controlla il log del bot per i dettagli.",
                ephemeral=True
            )

    @bot.tree.command(name="wipe-item", description="[CHIAVE] Elimina tutti gli item e zaini dal sistema")
    async def wipe_item(interaction: discord.Interaction):
        if not has_role(interaction, CHIAVE_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Solo i creatori del server possono usare questo comando! (Richiesto: <@&{CHIAVE_ROLE_ID}>)", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                # Conta quanti utenti hanno zaini e item prima di eliminarli
                async with db.execute("SELECT COUNT(*) FROM users WHERE has_backpack = 1") as cursor:
                    backpack_count = (await cursor.fetchone())[0]
                
                async with db.execute("SELECT COUNT(DISTINCT user_id) FROM inventory") as cursor:
                    users_with_items = (await cursor.fetchone())[0]
                
                async with db.execute("SELECT COUNT(*) FROM inventory") as cursor:
                    total_items = (await cursor.fetchone())[0]
                
                # Elimina tutti gli item dall'inventario
                await db.execute("DELETE FROM inventory")
                
                # Rimuove tutti gli zaini
                await db.execute("UPDATE users SET has_backpack = 0")
                
                await db.commit()
            
            await interaction.followup.send(
                f"✅ **WIPE COMPLETATO!**\n\n"
                f"📦 **{total_items}** item eliminati\n"
                f"👥 **{users_with_items}** utenti avevano item\n"
                f"🎒 **{backpack_count}** zaini rimossi\n\n"
                f"Tutti gli inventari sono stati azzerati!",
                ephemeral=True
            )
            
            # LOG
            log_embed = discord.Embed(
                title="🗑️ LOG WIPE ITEM GLOBALE",
                color=discord.Color.dark_red()
            )
            log_embed.add_field(name="👮 Eseguito da", value=interaction.user.mention, inline=False)
            log_embed.add_field(name="📦 Item eliminati", value=str(total_items), inline=True)
            log_embed.add_field(name="👥 Utenti coinvolti", value=str(users_with_items), inline=True)
            log_embed.add_field(name="🎒 Zaini rimossi", value=str(backpack_count), inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)
            
        except Exception as e:
            print(f"Errore in /wipe-item: {e}")
            await interaction.followup.send(f"❌ Errore durante il wipe: {e}", ephemeral=True)
