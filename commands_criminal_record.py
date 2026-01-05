import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import database

LFD_ROLE_ID = 1415093546549248040
LOG_CHANNEL_ID = 1415297578022604850

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def get_user_arrests(user_id: str):
    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(
                "SELECT id, nome_completo, eta, residenza, motivo, pena, created_at FROM arrests WHERE user_id = $1",
                user_id
            )
    except Exception as e:
        print(f"[ERRORE] get_user_arrests: {e}", flush=True)
        return []

async def get_arrests_by_name(nome: str, cognome: str):
    try:
        nome_completo_ricerca = f"{nome} {cognome}".lower()
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            # Cerchiamo direttamente nel DB con LOWER per efficienza
            return await conn.fetch(
                "SELECT id, user_id, nome_completo, eta, residenza, motivo, pena, created_at FROM arrests WHERE LOWER(nome_completo) = $1",
                nome_completo_ricerca
            )
    except Exception as e:
        print(f"[ERRORE] get_arrests_by_name: {e}", flush=True)
        return []

async def clear_criminal_record(user_id: str):
    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM fines WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM arrests WHERE user_id = $1", user_id)
        print(f"[DEBUG] Fedina penale pulita per user_id: {user_id}", flush=True)
    except Exception as e:
        print(f"[ERRORE] clear_criminal_record: {e}", flush=True)

def setup_criminal_record_commands(bot: commands.Bot):
    
    @bot.tree.command(name="miafedinapenale", description="Visualizza la tua fedina penale")
    async def miafedinapenale(interaction: discord.Interaction):
        print(f"[DEBUG] /miafedinapenale usato da {interaction.user}", flush=True)
        await interaction.response.defer(ephemeral=True)
        
        user_id = str(interaction.user.id)
        
        # Nota: Assicurati che database.get_unpaid_fines sia aggiornato allo stile pool
        fines = await database.get_unpaid_fines(user_id)
        arrests = await get_user_arrests(user_id)
        
        embed = discord.Embed(
            title="📂 La Tua Fedina Penale",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        if fines:
            multe_text = ""
            for record in fines:
                # record: id, name, surname, infractions, fine_amount
                multe_text += f"🚫 **Multa #{record[0]}** - ${record[4]:,}\n   *{record[3][:80]}...*\n"
            embed.add_field(name="💸 Multe", value=multe_text.strip(), inline=False)
        else:
            embed.add_field(name="💸 Multe", value="✅ Nessuna multa", inline=False)
        
        if arrests:
            arresti_text = ""
            for record in arrests:
                # record: id, nome, eta, residenza, motivo, pena, created_at
                arresti_text += f"🚫 **Arresto #{record[0]}** - Pena: {record[5]}\n   *{record[4][:80]}...*\n"
            embed.add_field(name="🔒 Arresti", value=arresti_text.strip(), inline=False)
        else:
            embed.add_field(name="🔒 Arresti", value="✅ Nessun arresto", inline=False)
        
        embed.set_footer(text="L.F.D - Los Santos Police Department")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="cercapersona", description="[L.F.D] Cerca una persona nel database criminale")
    @app_commands.describe(nome="Nome della persona", cognome="Cognome della persona")
    async def cercapersona(interaction: discord.Interaction, nome: str, cognome: str):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Permessi insufficienti!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        nome_completo = f"{nome} {cognome}"
        
        try:
            pool = await database.get_pool()
            async with pool.acquire() as conn:
                fines = await conn.fetch(
                    "SELECT id, user_id, name, surname, infractions, fine_amount, paid FROM fines WHERE LOWER(name) = $1 AND LOWER(surname) = $2",
                    nome.lower(), cognome.lower()
                )
            
            arrests = await get_arrests_by_name(nome, cognome)
            
            if not fines and not arrests:
                await interaction.followup.send(f"🔍 Nessun record per **{nome_completo}**.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"🔍 Ricerca: {nome_completo}",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            
            if fines:
                multe_text = ""
                for r in fines:
                    status = "✅ Pagata" if r[6] else "❌ Non pagata"
                    multe_text += f"🚫 **Multa #{r[0]}** - ${r[5]:,} ({status})\n   Discord: <@{r[1]}>\n   *{r[4][:70]}...*\n\n"
                embed.add_field(name="💸 Multe Trovate", value=multe_text.strip(), inline=False)
            
            if arrests:
                arresti_text = ""
                for r in arrests:
                    arresti_text += f"🚫 **Arresto #{r[0]}** - Pena: {r[6]}\n   Discord: <@{r[1]}>\n   *{r[5][:70]}...*\n\n"
                embed.add_field(name="🔒 Arresti Trovati", value=arresti_text.strip(), inline=False)
            
            embed.set_footer(text=f"Ricerca di {interaction.user.display_name}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"[ERRORE] cercapersona: {e}", flush=True)
            await interaction.followup.send("❌ Errore durante la ricerca.", ephemeral=True)

    @bot.tree.command(name="puliziafedinapenale", description="[L.F.D] Pulisce la fedina penale di un utente")
    @app_commands.describe(utente="L'utente a cui pulire la fedina penale")
    async def puliziafedinapenale(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("❌ Permessi insufficienti!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        user_id = str(utente.id)
        
        await clear_criminal_record(user_id)
        
        try:
            dm_embed = discord.Embed(
                title="✨ FEDINA PENALE PULITA",
                description=f"La tua fedina penale è stata **pulita** da {interaction.user.mention}!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            dm_embed.set_footer(text="L.F.D - Los Santos Police Department")
            await utente.send(embed=dm_embed)
            dm_status = "✅ Notifica DM inviata"
        except:
            dm_status = "⚠️ Impossibile inviare DM"
        
        await interaction.followup.send(f"✅ Fedina penale di {utente.mention} pulita!\n{dm_status}", ephemeral=True)

    print("✅ Comandi Fedina Penale caricati", flush=True)
