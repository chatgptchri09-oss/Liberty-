import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import database # Per riutilizzare le funzioni come get_user e create_user

# Nomi delle costanti e funzioni dedotti dai tuoi altri script
DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850

# Funzione log_command duplicata per rendere lo script indipendente
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
        
        # 1. Validazione base dell'importo
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo del bonifico deve essere maggiore di zero!", ephemeral=True)
            return
        
        # 2. Controllo bonifico verso sé stessi
        if sender_id == receiver_id:
            await interaction.response.send_message("❌ Non puoi effettuare un bonifico a te stesso!", ephemeral=True)
            return
            
        # 3. Controllo Utente nel DB e saldo
        async with aiosqlite.connect(DATABASE_NAME) as db:
            # Recupera saldo del mittente (solo bank)
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (sender_id,)) as cursor:
                sender_data = await cursor.fetchone()
            
            # Recupera saldo del ricevente
            async with db.execute("SELECT bank FROM users WHERE user_id = ?", (receiver_id,)) as cursor:
                receiver_data = await cursor.fetchone()
            
            # Se il mittente non ha un record (dovrebbe averlo dal /bancomat)
            if not sender_data:
                await interaction.response.send_message("❌ Non hai un conto in banca! Usa /bancomat per crearlo.", ephemeral=True)
                return
            
            sender_bank_balance = sender_data[0]
            
            # 4. Verifica se il mittente ha abbastanza soldi in banca
            if sender_bank_balance < importo:
                await interaction.response.send_message(
                    f"❌ Non hai abbastanza fondi in banca! (Saldo: ${sender_bank_balance:,})", 
                    ephemeral=True
                )
                return
            
            # 5. Esegue il trasferimento
            
            # Deduca l'importo dal mittente
            new_sender_bank = sender_bank_balance - importo
            await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_sender_bank, sender_id))
            
            # Aggiunge l'importo al ricevente
            if receiver_data:
                new_receiver_bank = receiver_data[0] + importo
                await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (new_receiver_bank, receiver_id))
            else:
                # Se il ricevente non ha un record, lo crea con il bonifico come saldo iniziale in banca
                await db.execute("INSERT INTO users (user_id, bank, cash, has_backpack) VALUES (?, ?, 0, 0)", (receiver_id, importo))
                
            await db.commit()

        # 6. Risposta all'utente e notifica
        
        # Invia la notifica in DM all'utente che ha ricevuto il bonifico
        try:
            await utente.send(
                f"💸 **BONIFICO RICEVUTO!**\n"
                f"Hai ricevuto un bonifico di **${importo:,}** da {interaction.user.mention}."
            )
        except discord.Forbidden:
            # Se i DM sono bloccati, non fa nulla
            pass
            
        # Risposta sul canale Discord
        await interaction.response.send_message(
            f"✅ Bonifico completato! Hai inviato **${importo:,}** a {utente.mention} dal tuo conto bancario.", 
            ephemeral=True
        )

        # 7. Log
        await log_command(bot, LOG_CHANNEL_ID, f"💸 {interaction.user.mention} ha inviato bonifico di ${importo:,} a {utente.mention}")

    # Registra il comando al tree
    bot.tree.add_command(bonifico)
