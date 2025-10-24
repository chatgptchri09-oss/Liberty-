import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database # <--- Importazione Essenziale per usare le tue funzioni!

# Nomi delle costanti come definite nei tuoi altri script
DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850

# Funzione log_command (essenziale per tutti i tuoi file di comando)
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
        importo="La cifra da trasferire dal tuo conto bancario"
    )
    async def bonifico(interaction: discord.Interaction, utente: discord.Member, importo: int):
        
        sender_id = str(interaction.user.id)
        receiver_id = str(utente.id)
        
        # 1. DEFER CRITICO: Risponde immediatamente per evitare il timeout
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            return 

        try:
            # 2. Validazione base e controllo
            if importo <= 0:
                await interaction.followup.send("❌ L'importo del bonifico deve essere maggiore di zero!", ephemeral=True)
                return
            
            if sender_id == receiver_id:
                await interaction.followup.send("❌ Non puoi effettuare un bonifico a te stesso!", ephemeral=True)
                return
            
            if utente.bot:
                await interaction.followup.send("❌ Non puoi effettuare un bonifico a un bot!", ephemeral=True)
                return
            
            # 3. Recupera i dati (Usa la funzione get_user dal tuo database.py)
            sender_data = await database.get_user(sender_id)
            receiver_data = await database.get_user(receiver_id) # Crea l'utente se non esiste
            
            sender_bank_balance = sender_data['bank']
            receiver_bank_balance = receiver_data['bank']

            # 4. Controllo del saldo del mittente
            if sender_bank_balance < importo:
                await interaction.followup.send(
                    f"❌ Non hai abbastanza fondi in banca! (Saldo: **${sender_bank_balance:,}**)", 
                    ephemeral=True
                )
                return
            
            # 5. Esegue il trasferimento (Calcolo e aggiornamento)
            
            new_sender_bank = sender_bank_balance - importo
            new_receiver_bank = receiver_bank_balance + importo

            # Aggiorna il mittente (Usa la funzione update_balance dal tuo database.py)
            await database.update_balance(sender_id, bank=new_sender_bank)
            
            # Aggiorna il ricevente (Usa la funzione update_balance dal tuo database.py)
            await database.update_balance(receiver_id, bank=new_receiver_bank)

            # 6. Risposta e notifica
            
            # Notifica in DM al ricevente
            try:
                embed_dm = discord.Embed(
                    title="💸 Bonifico Ricevuto!",
                    description=f"Hai ricevuto un bonifico di **${importo:,}** in banca da {interaction.user.mention}.",
                    color=discord.Color.green()
                )
                embed_dm.set_footer(text=f"Il tuo nuovo saldo bancario è: ${new_receiver_bank:,}")
                await utente.send(embed=embed_dm)
            except:
                pass 
                
            # Risposta finale di successo
            await interaction.followup.send(
                f"✅ Bonifico completato! Hai inviato **${importo:,}** a {utente.mention}.\n"
                f"Il tuo nuovo saldo bancario è: **${new_sender_bank:,}**",
                ephemeral=True
            )

            # 7. Log
            await log_command(bot, LOG_CHANNEL_ID, f"💸 {interaction.user.mention} ha inviato bonifico di ${importo:,} a {utente.mention}")

        except Exception as e:
            # Gestisce qualsiasi altro errore imprevisto
            print(f"ERRORE GRAVE DURANTE BONIFICO: {e}")
            await log_command(bot, LOG_CHANNEL_ID, f"❌ ERRORE CRITICO BONIFICO: {interaction.user.mention} ha fallito a inviare {importo} a {utente.mention}. Errore: {e}")
            # Risposta di errore finale 
            await interaction.followup.send(
                f"❌ Si è verificato un errore critico durante il bonifico. Controlla il log del bot per i dettagli.",
                ephemeral=True
            )
