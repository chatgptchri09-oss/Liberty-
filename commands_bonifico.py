import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database

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


def setup_bonifico_commands(bot: commands.Bot):
    
    @bot.tree.command(name="bonifico", description="Invia denaro tramite bonifico bancario")
    @app_commands.describe(
        utente="L'utente a cui inviare il denaro",
        importo="La cifra da trasferire dal tuo conto bancario",
        motivo="Il motivo del bonifico"
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
            
            # Messaggio pubblico nel canale visibile a tutti (esattamente come nella foto)
            await interaction.channel.send(
                f"✅ Hai inviato **${importo:,}** a {utente.mention} per: *{motivo}*"
            )
            
            # Conferma privata al mittente
            await interaction.followup.send(
                f"<a:spunta:1431937738256552036> Bonifico completato! Il tuo nuovo saldo bancario è: **${new_sender_bank:,}**",
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
            await log_command(bot, LOG_CHANNEL_ID, embed=log_embed)

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
