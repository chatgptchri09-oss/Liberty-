import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
from constants import LOG_CHANNEL_ID, DATABASE_NAME, has_staff

# ID ruolo autorizzato a usare /wipe-totale
WIPE_TOTALE_ROLE_ID = 1404051860121456701

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

    # ══════════════════════════════════════════════════════════════════════════
    #  /wipe-totale
    # ══════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="wipe-totale", description="[OWNER] Resetta TUTTI gli utenti del server")
    async def wipe_totale(interaction: discord.Interaction):
        # Controllo ruolo
        has_role = (
            isinstance(interaction.user, discord.Member) and
            any(r.id == WIPE_TOTALE_ROLE_ID for r in interaction.user.roles)
        )

        if not has_role:
            # Log del tentativo
            try:
                ch = bot.get_channel(LOG_CHANNEL_ID)
                if ch:
                    log = discord.Embed(
                        title="⚠️ LOG — Tentativo /wipe-totale NON AUTORIZZATO",
                        color=discord.Color.dark_red(),
                        timestamp=discord.utils.utcnow()
                    )
                    log.add_field(name="👤 Utente",  value=interaction.user.mention, inline=True)
                    log.add_field(name="🆔 User ID", value=str(interaction.user.id), inline=True)
                    log.add_field(name="📢 Canale",  value=interaction.channel.mention, inline=True)
                    await ch.send(embed=log)
            except Exception:
                pass

            await interaction.response.send_message(
                "❌ Perché provi a griffare il server?",
                ephemeral=True
            )
            return

        # Embed di conferma
        confirm_embed = discord.Embed(
            title="☠️ ATTENZIONE — WIPE TOTALE SERVER",
            description=(
                "Stai per **CANCELLARE COMPLETAMENTE** i dati di **TUTTI GLI UTENTI** del server!\n\n"
                "⚠️ Questa operazione è **IRREVERSIBILE** e non può essere annullata una volta avviata."
            ),
            color=discord.Color.dark_red()
        )
        confirm_embed.add_field(
            name="📋 Cosa verrà eliminato per OGNI utente:",
            value=(
                "• 💰 **Soldi** (reset a $50 in contanti)\n"
                "• 🎒 **Inventario/Bisaccia** (tutto)\n"
                "• 📄 **Documenti** (tutti)\n"
                "• 🏠 **Proprietà** (tutte)\n"
                "• 🚨 **Taglie/Multe** (tutte)\n"
                "• 📜 **Fedina penale** (tutta)\n"
                "• ⛓️ **Arresti** (tutti)\n"
                "• 📄 **Fatture** (tutte)\n"
                "• 💼 **Turni attivi** (rimossi)\n"
                "• 🙈 **Oggetti nascosti** (tutti)\n"
                "• 🔫 **Usura armi** (tutta)\n"
                "• 🍔 **Fame e Sete** (reset a 100)\n"
            ),
            inline=False
        )
        confirm_embed.add_field(
            name="✅ Cosa NON verrà toccato:",
            value="• 🏪 **Negozio** (shop_items rimane intatto)\n• 🏦 **Fondo cassa** (fondocassa rimane intatto)",
            inline=False
        )
        confirm_embed.add_field(
            name="‼️ ULTIMA POSSIBILITÀ",
            value="Premi **✅ CONFERMO IL WIPE TOTALE** per procedere oppure **❌ Annulla** per fermarti.",
            inline=False
        )
        confirm_embed.set_footer(text="🤠 Red Dead Redemption II — Solo il proprietario può eseguire questa azione")

        view = WipeTotaleConfirmView(bot, interaction.user)
        await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  View conferma /wipe-pg
# ══════════════════════════════════════════════════════════════════════════════
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
                await db.execute("""
                    INSERT INTO users (user_id, cash, bank, hunger, thirst)
                    VALUES (?, 50, 0, 100, 100)
                    ON CONFLICT(user_id) DO UPDATE SET
                        cash=50, bank=0, hunger=100, thirst=100
                """, (uid,))
                stats["soldi"] = "Reset a $50 contanti"

                c = await db.execute("DELETE FROM inventory WHERE user_id=?", (uid,))
                stats["inventario"] = c.rowcount

                stats["documenti"] = await self._safe_del(db, "documents", uid)
                stats["proprieta"] = await self._safe_del(db, "properties", uid)
                stats["taglie"]    = await self._safe_del(db, "fines", uid)
                stats["fedina"]    = await self._safe_del(db, "criminal_records", uid)
                stats["arresti"]   = await self._safe_del(db, "arrests", uid)

                try:
                    c2 = await db.execute(
                        "DELETE FROM invoices WHERE from_user=? OR to_user=?", (uid, uid)
                    )
                    stats["fatture"] = c2.rowcount
                except Exception:
                    stats["fatture"] = 0

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

                try:
                    c4 = await db.execute("DELETE FROM weapon_durability WHERE user_id=?", (uid,))
                    stats["usura_armi"] = c4.rowcount
                except Exception:
                    stats["usura_armi"] = 0

                await db.commit()

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
            success_embed.add_field(name="👤 Utente",      value=self.target_user.mention, inline=True)

            await interaction.followup.send(embed=success_embed, ephemeral=True)

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


# ══════════════════════════════════════════════════════════════════════════════
#  View conferma /wipe-totale
# ══════════════════════════════════════════════════════════════════════════════
class WipeTotaleConfirmView(discord.ui.View):
    def __init__(self, bot, admin_user: discord.Member):
        super().__init__(timeout=60)
        self.bot        = bot
        self.admin_user = admin_user

    @discord.ui.button(label="✅ CONFERMO IL WIPE TOTALE", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message(
                "❌ Solo chi ha eseguito il comando può confermare!", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        totals = {
            "utenti":    0,
            "inventory": 0,
            "documenti": 0,
            "proprieta": 0,
            "taglie":    0,
            "fedina":    0,
            "arresti":   0,
            "fatture":   0,
            "turni":     0,
            "nascosti":  0,
            "usura":     0,
        }

        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                # Recupera tutti gli user_id esistenti
                async with db.execute("SELECT user_id FROM users") as c:
                    all_users = [row[0] for row in await c.fetchall()]

                # Reset tabella users (tutti a $50 contanti, banca 0, fame/sete 100)
                # NON tocchiamo shop_items né fondocassa
                r = await db.execute(
                    "UPDATE users SET cash=50, bank=0, hunger=100, thirst=100"
                )
                totals["utenti"] = r.rowcount

                # Svuota tabelle per ogni utente
                for table, key in [
                    ("inventory",        "inventory"),
                    ("documents",        "documenti"),
                    ("properties",       "proprieta"),
                    ("fines",            "taglie"),
                    ("criminal_records", "fedina"),
                    ("arrests",          "arresti"),
                ]:
                    try:
                        r2 = await db.execute(f"DELETE FROM {table}")
                        totals[key] = r2.rowcount
                    except Exception:
                        pass

                # Fatture
                try:
                    r3 = await db.execute("DELETE FROM invoices")
                    totals["fatture"] = r3.rowcount
                except Exception:
                    pass

                # Turni attivi
                try:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS turni_attivi (
                            user_id TEXT PRIMARY KEY, role_id INTEGER,
                            role_name TEXT, stipendio INTEGER, inizio_ts REAL
                        )
                    """)
                    r4 = await db.execute("DELETE FROM turni_attivi")
                    totals["turni"] = r4.rowcount
                except Exception:
                    pass

                # Oggetti nascosti
                try:
                    await db.execute("""
                        CREATE TABLE IF NOT EXISTS hidden_items (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL, item_name TEXT NOT NULL,
                            quantity INTEGER DEFAULT 1, luogo TEXT, created_at TEXT
                        )
                    """)
                    r5 = await db.execute("DELETE FROM hidden_items")
                    totals["nascosti"] = r5.rowcount
                except Exception:
                    pass

                # Usura armi
                try:
                    r6 = await db.execute("DELETE FROM weapon_durability")
                    totals["usura"] = r6.rowcount
                except Exception:
                    pass

                # Documenti falsi
                try:
                    await db.execute("DELETE FROM fake_documents")
                except Exception:
                    pass

                await db.commit()

            # ── Embed successo ───────────────────────────────────────────────
            success_embed = discord.Embed(
                title="☠️ WIPE TOTALE COMPLETATO",
                description=f"Tutti i dati di **{totals['utenti']} utenti** sono stati azzerati.",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            success_embed.add_field(name="📊 Dettaglio operazione:", value=(
                f"• 💰 Utenti resettati: **{totals['utenti']}** (→ $50 contanti)\n"
                f"• 🎒 Item inventario rimossi: **{totals['inventory']}**\n"
                f"• 📄 Documenti rimossi: **{totals['documenti']}**\n"
                f"• 🏠 Proprietà rimosse: **{totals['proprieta']}**\n"
                f"• 🚨 Taglie/Multe rimosse: **{totals['taglie']}**\n"
                f"• 📜 Record fedina rimossi: **{totals['fedina']}**\n"
                f"• ⛓️ Arresti rimossi: **{totals['arresti']}**\n"
                f"• 📄 Fatture rimosse: **{totals['fatture']}**\n"
                f"• 💼 Turni rimossi: **{totals['turni']}**\n"
                f"• 🙈 Oggetti nascosti rimossi: **{totals['nascosti']}**\n"
                f"• 🔫 Record usura armi rimossi: **{totals['usura']}**\n"
            ), inline=False)
            success_embed.add_field(
                name="✅ Intatto",
                value="🏪 Negozio (shop_items) • 🏦 Fondo cassa",
                inline=False
            )
            success_embed.add_field(name="👮 Eseguito da", value=self.admin_user.mention, inline=True)
            success_embed.set_footer(text="🤠 Red Dead Redemption II — Wipe Totale")

            await interaction.followup.send(embed=success_embed, ephemeral=True)

            # ── Log ──────────────────────────────────────────────────────────
            try:
                ch = self.bot.get_channel(LOG_CHANNEL_ID)
                if ch:
                    log = discord.Embed(
                        title="☠️ LOG — WIPE TOTALE SERVER",
                        color=discord.Color.dark_red(),
                        timestamp=discord.utils.utcnow()
                    )
                    log.add_field(name="👮 Eseguito da",    value=self.admin_user.mention,    inline=True)
                    log.add_field(name="👥 Utenti azzerati", value=str(totals['utenti']),     inline=True)
                    log.add_field(name="📊 Dettaglio", value=(
                        f"Inventory: {totals['inventory']} | Documenti: {totals['documenti']} | "
                        f"Proprietà: {totals['proprieta']} | Taglie: {totals['taglie']} | "
                        f"Fedina: {totals['fedina']} | Arresti: {totals['arresti']} | "
                        f"Fatture: {totals['fatture']} | Turni: {totals['turni']} | "
                        f"Nascosti: {totals['nascosti']} | Usura: {totals['usura']}"
                    ), inline=False)
                    await ch.send(embed=log)
            except Exception:
                pass

            # Disabilita bottoni
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Errore durante il wipe totale: ```{e}```", ephemeral=True
            )
            print(f"[wipe-totale] Errore: {e}", flush=True)

    @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.admin_user.id:
            await interaction.response.send_message(
                "❌ Solo chi ha eseguito il comando può annullare!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="❌ Wipe Totale annullato",
            description="Nessun dato è stato eliminato. Il server è al sicuro.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
