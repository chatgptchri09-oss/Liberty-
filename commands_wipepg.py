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

    async def safe_delete(self, db, table_name: str, user_id: str) -> int:
        """Elimina dati da una tabella in modo sicuro, anche se la tabella non esiste"""
        try:
            cursor = await db.execute(f"DELETE FROM {table_name} WHERE user_id = ?", (user_id,))
            return cursor.rowcount
        except:
            return 0

    async def safe_delete_double(self, db, table_name: str, user_id: str, column1: str, column2: str) -> int:
        """Elimina dati da una tabella con due colonne possibili (es. fatture)"""
        try:
            cursor = await db.execute(
                f"DELETE FROM {table_name} WHERE {column1} = ? OR {column2} = ?",
                (user_id, user_id)
            )
            return cursor.rowcount
        except:
            return 0

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
                # 1. RESET SOLDI (a $20,000 iniziali) - Sempre eseguito
                try:
                    # Prima controlla se l'utente esiste nella tabella users
                    cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                    exists = await cursor.fetchone()
                    
                    if exists:
                        # Utente esiste, aggiorna
                        await db.execute(
                            "UPDATE users SET cash = 0, bank = 20000, has_backpack = 0 WHERE user_id = ?",
                            (user_id,)
                        )
                    else:
                        # Utente non esiste, crealo con saldo iniziale
                        await db.execute(
                            "INSERT INTO users (user_id, cash, bank, has_backpack) VALUES (?, 0, 20000, 0)",
                            (user_id,)
                        )
                    deleted_data["soldi"] = "Reset a $20,000"
                except Exception as e:
                    deleted_data["soldi"] = f"Errore: {str(e)}"

                # 2. ELIMINA INVENTARIO
                deleted_data["inventory"] = await self.safe_delete(db, "inventory", user_id)

                # 3. ELIMINA PROPRIETÀ
                deleted_data["properties"] = await self.safe_delete(db, "properties", user_id)

                # 4. ELIMINA DOCUMENTI
                deleted_data["documents"] = await self.safe_delete(db, "documents", user_id)

                # 5. ELIMINA PATENTI
                deleted_data["licenses"] = await self.safe_delete(db, "licenses", user_id)

                # 6. ELIMINA PORTO D'ARMI
                deleted_data["gun_licenses"] = await self.safe_delete(db, "gun_licenses", user_id)

                # 7. ELIMINA LIBRETTI VEICOLI
                deleted_data["vehicle_registrations"] = await self.safe_delete(db, "vehicle_registrations", user_id)

                # 8. ELIMINA CERTIFICATI MEDICI
                deleted_data["medical_certificates"] = await self.safe_delete(db, "medical_certificates", user_id)

                # 9. ELIMINA CERTIFICATI BALISTICI
                deleted_data["ballistic_certificates"] = await self.safe_delete(db, "ballistic_certificates", user_id)

                # 10. ELIMINA MULTE
                deleted_data["fines"] = await self.safe_delete(db, "fines", user_id)

                # 11. ELIMINA FATTURE (sia come cliente che come sender)
                deleted_data["invoices"] = await self.safe_delete_double(db, "invoices", user_id, "client_id", "sender_id")

                # 12. ELIMINA ARRESTI
                deleted_data["arrests"] = await self.safe_delete(db, "arrests", user_id)

                # 13. ELIMINA FEDINA PENALE
                deleted_data["criminal_records"] = await self.safe_delete(db, "criminal_records", user_id)

                # 14. ELIMINA TURNI DI LAVORO
                deleted_data["work_shifts"] = await self.safe_delete(db, "work_shifts", user_id)

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
                title="❌ ERRORE CRITICO",
                description=f"Si è verificato un errore imprevisto durante il wipe:\n```{str(e)}```",
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
