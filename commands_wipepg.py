import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
ADMIN_ROLE_ID = 1414923114185490595

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

def setup_wipepg_commands(bot: commands.Bot):
    
    @bot.tree.command(name="wipe-pg", description="[ADMIN] Resetta completamente tutti i dati di un utente dal database")
    @app_commands.describe(utente="L'utente da resettare completamente")
    async def wipe_pg(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, ADMIN_ROLE_ID):
            await interaction.response.send_message(
                f"❌ Solo gli Admin possono usare questo comando! (Richiesto: <@&{ADMIN_ROLE_ID}>)",
                ephemeral=True
            )
            return

        if utente.bot:
            await interaction.response.send_message("❌ Non puoi resettare un bot.", ephemeral=True)
            return

        # Conferma con embed di warning
        confirm_embed = discord.Embed(
            title="⚠️ ATTENZIONE - WIPE PERSONAGGIO",
            description=f"Stai per **CANCELLARE COMPLETAMENTE** tutti i dati di {utente.mention}!",
            color=discord.Color.red()
        )
        confirm_embed.add_field(
            name="📋 Cosa verrà eliminato:",
            value=(
                "• 💰 **Soldi** (reset a $20,000)\n"
                "• 🏠 **Proprietà** (tutte)\n"
                "• 🎒 **Zaino** e **Inventario** (tutto)\n"
                "• 📄 **Documenti** (tutti)\n"
                "• 🚗 **Patenti** (tutte)\n"
                "• 🔫 **Porto d'armi** (tutti)\n"
                "• 📋 **Libretti veicoli** (tutti)\n"
                "• 🏥 **Certificati medici** (tutti)\n"
                "• 🎯 **Certificati balistici** (tutti)\n"
                "• 🚨 **Multe** (tutte)\n"
                "• 📄 **Fatture** (tutte)\n"
                "• ⛓️ **Arresti** (tutti)\n"
                "• 📜 **Fedina penale** (tutta)\n"
                "• 💼 **Turni di lavoro** (tutti)\n"
            ),
            inline=False
        )
        confirm_embed.add_field(
            name="⚠️ QUESTA AZIONE È IRREVERSIBILE!",
            value="Clicca **✅ Conferma** per procedere o **❌ Annulla** per fermarti.",
            inline=False
        )

        # View con bottoni di conferma
        view = WipeConfirmView(bot, utente, interaction.user)
        
        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)


class WipeConfirmView(discord.ui.View):
    def __init__(self, bot: commands.Bot, target_user: discord.Member, admin_user: discord.Member):
        super().__init__(timeout=60)
        self.bot = bot
        self.target_user = target_user
        self.admin_user = admin_user

    @discord.ui.button(label="✅ Conferma", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message("❌ Solo chi ha eseguito il comando può confermare!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        user_id = str(self.target_user.id)
        deleted_data = {}

        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                # 1. RESET SOLDI (a $20,000 iniziali)
                await db.execute(
                    "UPDATE users SET cash = 0, bank = 20000, has_backpack = 0 WHERE user_id = ?",
                    (user_id,)
                )
                deleted_data["soldi"] = "Reset a $20,000"

                # 2. ELIMINA INVENTARIO
                cursor = await db.execute("DELETE FROM inventory WHERE user_id = ?", (user_id,))
                deleted_data["inventory"] = cursor.rowcount

                # 3. ELIMINA PROPRIETÀ
                cursor = await db.execute("DELETE FROM properties WHERE user_id = ?", (user_id,))
                deleted_data["properties"] = cursor.rowcount

                # 4. ELIMINA DOCUMENTI
                cursor = await db.execute("DELETE FROM documents WHERE user_id = ?", (user_id,))
                deleted_data["documents"] = cursor.rowcount

                # 5. ELIMINA PATENTI
                cursor = await db.execute("DELETE FROM licenses WHERE user_id = ?", (user_id,))
                deleted_data["licenses"] = cursor.rowcount

                # 6. ELIMINA PORTO D'ARMI
                cursor = await db.execute("DELETE FROM gun_licenses WHERE user_id = ?", (user_id,))
                deleted_data["gun_licenses"] = cursor.rowcount

                # 7. ELIMINA LIBRETTI VEICOLI
                cursor = await db.execute("DELETE FROM vehicle_registrations WHERE user_id = ?", (user_id,))
                deleted_data["vehicle_registrations"] = cursor.rowcount

                # 8. ELIMINA CERTIFICATI MEDICI
                cursor = await db.execute("DELETE FROM medical_certificates WHERE user_id = ?", (user_id,))
                deleted_data["medical_certificates"] = cursor.rowcount

                # 9. ELIMINA CERTIFICATI BALISTICI
                cursor = await db.execute("DELETE FROM ballistic_certificates WHERE user_id = ?", (user_id,))
                deleted_data["ballistic_certificates"] = cursor.rowcount

                # 10. ELIMINA MULTE
                cursor = await db.execute("DELETE FROM fines WHERE user_id = ?", (user_id,))
                deleted_data["fines"] = cursor.rowcount

                # 11. ELIMINA FATTURE (sia come cliente che come sender)
                cursor = await db.execute(
                    "DELETE FROM invoices WHERE client_id = ? OR sender_id = ?",
                    (user_id, user_id)
                )
                deleted_data["invoices"] = cursor.rowcount

                # 12. ELIMINA ARRESTI
                cursor = await db.execute("DELETE FROM arrests WHERE user_id = ?", (user_id,))
                deleted_data["arrests"] = cursor.rowcount

                # 13. ELIMINA FEDINA PENALE
                cursor = await db.execute("DELETE FROM criminal_records WHERE user_id = ?", (user_id,))
                deleted_data["criminal_records"] = cursor.rowcount

                # 14. ELIMINA TURNI DI LAVORO
                cursor = await db.execute("DELETE FROM work_shifts WHERE user_id = ?", (user_id,))
                deleted_data["work_shifts"] = cursor.rowcount

                await db.commit()

            # Messaggio di conferma all'admin
            success_embed = discord.Embed(
                title="✅ WIPE COMPLETATO",
                description=f"Tutti i dati di {self.target_user.mention} sono stati cancellati con successo!",
                color=discord.Color.green()
            )
            
            details = "\n".join([
                f"• 💰 **Soldi:** {deleted_data.get('soldi', 'N/A')}",
                f"• 🎒 **Item Inventario:** {deleted_data.get('inventory', 0)} rimossi",
                f"• 🏠 **Proprietà:** {deleted_data.get('properties', 0)} rimosse",
                f"• 📄 **Documenti:** {deleted_data.get('documents', 0)} rimossi",
                f"• 🚗 **Patenti:** {deleted_data.get('licenses', 0)} rimosse",
                f"• 🔫 **Porto d'armi:** {deleted_data.get('gun_licenses', 0)} rimossi",
                f"• 📋 **Libretti:** {deleted_data.get('vehicle_registrations', 0)} rimossi",
                f"• 🏥 **Cert. Medici:** {deleted_data.get('medical_certificates', 0)} rimossi",
                f"• 🎯 **Cert. Balistici:** {deleted_data.get('ballistic_certificates', 0)} rimossi",
                f"• 🚨 **Multe:** {deleted_data.get('fines', 0)} rimosse",
                f"• 📄 **Fatture:** {deleted_data.get('invoices', 0)} rimosse",
                f"• ⛓️ **Arresti:** {deleted_data.get('arrests', 0)} rimossi",
                f"• 📜 **Fedina Penale:** {deleted_data.get('criminal_records', 0)} record rimossi",
                f"• 💼 **Turni Lavoro:** {deleted_data.get('work_shifts', 0)} rimossi"
            ])
            
            success_embed.add_field(name="📊 Dettaglio Eliminazioni:", value=details, inline=False)

            await interaction.followup.send(embed=success_embed, ephemeral=True)

            # Notifica DM all'utente
            try:
                dm_embed = discord.Embed(
                    title="🔄 RESET PERSONAGGIO",
                    description="Il tuo personaggio è stato completamente resettato da un Admin.",
                    color=discord.Color.orange()
                )
                dm_embed.add_field(
                    name="💰 Nuovo Saldo",
                    value="$20,000 in banca",
                    inline=False
                )
                dm_embed.add_field(
                    name="📋 Informazioni",
                    value="Tutti i tuoi dati precedenti sono stati cancellati. Puoi ricominciare da zero!",
                    inline=False
                )
                dm_embed.set_footer(text="Liberty RP - Amministrazione")
                await self.target_user.send(embed=dm_embed)
            except:
                pass

            # LOG CON EMBED
            log_embed = discord.Embed(
                title="🗑️ LOG WIPE PERSONAGGIO",
                description=f"**RESET COMPLETO** eseguito su {self.target_user.mention}",
                color=discord.Color.dark_red()
            )
            log_embed.add_field(name="👮 Eseguito da", value=self.admin_user.mention, inline=True)
            log_embed.add_field(name="👤 Utente Resettato", value=self.target_user.mention, inline=True)
            log_embed.add_field(name="📊 Dettagli", value=details, inline=False)
            log_embed.timestamp = discord.utils.utcnow()
            
            await log_command(self.bot, LOG_CHANNEL_ID, embed=log_embed)

            # Disabilita i bottoni
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ ERRORE",
                description=f"Si è verificato un errore durante il wipe:\n```{str(e)}```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            print(f"Errore wipe-pg: {e}")

    @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message("❌ Solo chi ha eseguito il comando può annullare!", ephemeral=True)
            return

        cancel_embed = discord.Embed(
            title="❌ OPERAZIONE ANNULLATA",
            description=f"Il wipe di {self.target_user.mention} è stato annullato.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=cancel_embed, ephemeral=True)

        # Disabilita i bottoni
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
