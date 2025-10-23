import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

# ===================================================================================
# COSTANTI E FUNZIONI DI SUPPORTO
# Assicurati che questi ID siano corretti e allineati con i tuoi altri file.
# ===================================================================================

DATABASE_NAME = "economy_bot.db"
# Ruolo fornito dall'utente per usare il comando /reset
RESET_ROLE_ID = 1414735564632231988 
LOG_CHANNEL_ID = 1415297578022604850 # Assunto dal tuo contesto

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
    except Exception:
        pass


def setup_admin_commands(bot: commands.Bot):
    """Registra i comandi amministrativi al tree del bot."""
    
    @bot.tree.command(name="reset", description="[STAFF] Rimuovi tutti i soldi (cash e banca) di un utente.")
    @app_commands.describe(utente="L'utente a cui azzerare i soldi")
    async def reset(interaction: discord.Interaction, utente: discord.Member):
        # 1. Controllo Ruolo (Permesso)
        if not has_role(interaction, RESET_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Non hai i permessi per usare questo comando. (Richiesto: <@&{RESET_ROLE_ID}>)", 
                ephemeral=True
            )
            return

        # 2. Controllo Self-Reset
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi azzerare i soldi di un bot.", ephemeral=True)
            return
            
        # 3. Aggiornamento Database
        user_id = str(utente.id)
        
        async with aiosqlite.connect(DATABASE_NAME) as db:
            # Azzeramento di 'cash' e 'bank'
            await db.execute(
                "UPDATE users SET cash = 0, bank = 0 WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
            
            # Se l'utente non era nel DB (e non è stato aggiornato), 
            # lo inseriamo con saldo zero per coerenza.
            # Questo previene un errore se lo si guarda subito dopo con /bancomat
            async with db.execute("SELECT changes()",) as cursor:
                changes = (await cursor.fetchone())[0]
            
            if changes == 0:
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, cash, bank) VALUES (?, 0, 0)",
                    (user_id,)
                )
                await db.commit()
        
        # 4. Risposta e Log
        
        # Notifica l'utente target (se possibile)
        try:
            await utente.send(f"⚠️ Il tuo saldo (cash e banca) è stato azzerato dallo staff ({interaction.user.mention}).")
        except:
            pass

        # Risposta all'interazione
        await interaction.response.send_message(
            f"✅ Saldo (cash e banca) di **{utente.mention}** azzerato con successo!",
            ephemeral=True
        )

        # Log nel canale di log
        await log_command(bot, LOG_CHANNEL_ID, f"🔄 {interaction.user.mention} ha azzerato il saldo (cash e banca) di {utente.mention}")
        
    # Non è necessario bot.tree.add_command(reset) perché usiamo il decoratore
    pass 
