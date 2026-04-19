import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from constants import LOG_CHANNEL_ID, DATABASE_NAME, has_staff

def setup_wipepg_commands(bot: commands.Bot):

    @bot.tree.command(name="wipe-pg", description="[Staff] Resetta completamente tutti i dati di un utente")
    @app_commands.describe(utente="L'utente da resettare completamente")
    async def wipe_pg(interaction: discord.Interaction, utente: discord.Member):
        if not has_staff(interaction):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True)
            return
        if utente.bot:
            await interaction.response.send_message("❌ Non puoi resettare un bot.", ephemeral=True)
            return

        confirm_embed = discord.Embed(
            title="⚠️ ATTENZIONE — WIPE PERSONAGGIO",
            description=f"Stai per **CANCELLARE COMPLETAMENTE** tutti i dati di {utente.mention}!",
            color=discord.Color.red()
        )
        confirm_embed.add_field(
            name="📋 Cosa verrà eliminato:",
            value=(
                "• 💰 **Soldi** (reset a $50 in contanti)\n"
                "• 🎒 **Inventario/Bisaccia** (tutto)\n"
                "• 📄 **Documenti** (tutti)\n"
                "• 🏠 **Proprietà** (tutte)\n"
                "• 🚨 **Taglie/Multe** (tutte)\n"
                "• 📜 **Fedina penale** (tutta)\n"
                "• ⛓️ **Arresti** (tutti)\n"
                "• 📄 **Fatture** (tutte)\n"
                "• 💼 **Turno attivo** (rimosso)\n"
                "• 🙈 **Oggetti nascosti** (tutti)\n"
                "• 🔫 **Usura armi** (tutta)\n"
                "• 🍔 **Fame e Sete** (reset a 100)\n"
            ),
            inline=False
        )
        confirm_embed.add_field(
            name="⚠️ QUESTA AZIONE È IRREVERSIBILE!",
            value="Clicca **✅ Conferma** per procedere o **❌ Annulla** per fermarti.",
            inline=False
        )

        view = WipeConfirmView(bot, utente, interaction.user)
        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)


class WipeConfirmView(discord.ui.View):
    def __init__(self, bot, target_user: discord.Member, admin_user: discord.Member):
        super().__init__(timeout=60)
        self.bot         = bot
        self.target_user = target_user
        self.admin_user  = admin_user

    async def _safe_del(self, db, table: str, uid: str) -> int:
        try:
            c = await db.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))
            return c.rowcount
        except Exception:
            return 0

    @discord.ui.button(label="✅ Conferma", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message("❌ Solo chi ha eseguito il comando può confermare!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        uid = str(self.target_user.id)
        stats = {}

        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                # Reset utente a $50 contanti, banca 0, fame/sete 100
                await db.execute("""
                    INSERT INTO users (user_id, cash, bank, hunger, thirst)
                    VALUES (?, 50, 0, 100, 100)
                    ON CONFLICT(user_id) DO UPDATE SET
                        cash=50, bank=0, hunger=100, thirst=100
                """, (uid,))
                stats["soldi"] = "Reset a $50 contanti"

                # Inventario
                c = await db.execute("DELETE FROM inventory WHERE user_id=?", (uid,))
                stats["inventario"] = c.rowcount

                # Documenti
                stats["documenti"] = await self._safe_del(db, "documents", uid)

                # Proprietà
                stats["proprieta"] = await self._safe_del(db, "properties", uid)

                # Taglie/Multe
                stats["taglie"] = await self._safe_del(db, "fines", uid)

                # Fedina penale
                stats["fedina"] = await self._safe_del(db, "criminal_records", uid)

                # Arresti
                stats["arresti"] = await self._safe_del(db, "arrests", uid)

                # Fatture (come mittente e destinatario)
                try:
                    c2 = await db.execute(
                        "DELETE FROM invoices WHERE from_user=? OR to_user=?", (uid, uid)
                    )
                    stats["fatture"] = c2.rowcount
                except Exception:
                    stats["fatture"] = 0

                # Turno attivo
                try:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS turni_attivi (
                            user_id TEXT PRIMARY KEY, role_id INTEGER,
                            role_name TEXT, stipendio INTEGER, inizio_ts REAL
                        )
                    """)
                    await db.execute("DELETE FROM turni_attivi WHERE user_id=?", (uid,))
                    stats["turno"] = "rimosso"
                except Exception:
                    stats["turno"] = "N/A"

                # Oggetti nascosti
                try:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS hidden_items (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL, item_name TEXT NOT NULL,
                            quantity INTEGER DEFAULT 1, luogo TEXT, created_at TEXT
                        )
                    """)
                    c3 = await db.execute("DELETE FROM hidden_items WHERE user_id=?", (uid,))
                    stats["nascosti"] = c3.rowcount
                except Exception:
                    stats["nascosti"] = 0

                # Usura armi
                try:
                    c4 = await db.execute("DELETE FROM weapon_durability WHERE user_id=?", (uid,))
                    stats["usura_armi"] = c4.rowcount
                except Exception:
                    stats["usura_armi"] = 0

                await db.commit()

            # Embed successo
            success_embed = discord.Embed(
                title="✅ WIPE COMPLETATO",
                description=f"Tutti i dati di {self.target_user.mention} sono stati cancellati!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            success_embed.add_field(name="📊 Dettaglio:", value=(
                f"• 💰 Soldi: {stats['soldi']}\n"
                f"• 🎒 Inventario: {stats['inventario']} item rimossi\n"
                f"• 📄 Documenti: {stats['documenti']} rimossi\n"
                f"• 🏠 Proprietà: {stats['proprieta']} rimosse\n"
                f"• 🚨 Taglie: {stats['taglie']} rimosse\n"
                f"• 📜 Fedina penale: {stats['fedina']} record rimossi\n"
                f"• ⛓️ Arresti: {stats['arresti']} rimossi\n"
                f"• 📄 Fatture: {stats['fatture']} rimosse\n"
                f"• 💼 Turno: {stats['turno']}\n"
                f"• 🙈 Oggetti nascosti: {stats['nascosti']} rimossi\n"
                f"• 🔫 Usura armi: {stats['usura_armi']} record rimossi\n"
            ), inline=False)
            success_embed.add_field(name="👮 Eseguito da", value=self.admin_user.mention, inline=True)
            success_embed.add_field(name="👤 Utente", value=self.target_user.mention, inline=True)

            await interaction.followup.send(embed=success_embed, ephemeral=True)

            # DM all'utente
            try:
                dm = discord.Embed(
                    title="🔄 Il tuo personaggio è stato resettato",
                    description="Un amministratore ha resettato completamente il tuo personaggio.",
                    color=discord.Color.orange()
                )
                dm.add_field(name="💰 Nuovo saldo", value="$50 in contanti", inline=False)
                dm.set_footer(text="🤠 Red Dead Redemption II — Colorado Full RP")
                await self.target_user.send(embed=dm)
            except Exception:
                pass

            # Log
            try:
                ch = self.bot.get_channel(LOG_CHANNEL_ID)
                if ch:
                    log = discord.Embed(
                        title="🗑️ LOG — Wipe Personaggio",
                        color=discord.Color.dark_red(),
                        timestamp=discord.utils.utcnow()
                    )
                    log.add_field(name="👮 Staff",  value=self.admin_user.mention,  inline=True)
                    log.add_field(name="👤 Utente", value=self.target_user.mention, inline=True)
                    await ch.send(embed=log)
            except Exception:
                pass

            # Disabilita bottoni
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Errore durante il wipe: ```{e}```", ephemeral=True
            )
            print(f"[wipe-pg] Errore: {e}", flush=True)

    @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message("❌ Solo chi ha eseguito il comando può annullare!", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Operazione annullata",
            description=f"Il wipe di {self.target_user.mention} è stato annullato.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
