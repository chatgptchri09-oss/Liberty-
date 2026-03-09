import discord
from discord import app_commands
import database
import asyncio
import random

# ── Ruoli autorizzati ─────────────────────────────────────────────────────────
SINDACO_ROLE_ID   = 1404051939561574514
DIRETTORE_ROLE_ID = 1404051913150038117
CONTABILE_ROLE_ID = 1480217343245287424   # terzo ruolo che può usare il comando

# Canale banca per le notifiche di conferma
BANK_CHANNEL_ID = 1404052325609504798

# ── Helper ────────────────────────────────────────────────────────────────────
def _has_any(interaction: discord.Interaction, *role_ids: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    ids = {r.id for r in interaction.user.roles}
    return bool(ids & set(role_ids))

def _has_role(member: discord.Member, role_id: int) -> bool:
    return any(r.id == role_id for r in member.roles)


# ── View conferma nel canale banca ────────────────────────────────────────────
class ConfermaView(discord.ui.View):
    """
    Viene postata nel canale banca dopo una richiesta di prelievo/deposito.
    Serve la conferma del Direttore E del Sindaco per eseguire l'operazione.
    """
    def __init__(
        self,
        bot,
        operazione: str,          # "preleva" | "deposita"
        importo: int,
        mittente: discord.Member,  # chi usa il comando
        target: discord.Member,    # il cittadino
        guild: discord.Guild,
    ):
        super().__init__(timeout=3600)   # 1 ora di tempo per confermare
        self.bot         = bot
        self.operazione  = operazione
        self.importo     = importo
        self.mittente    = mittente
        self.target      = target
        self.guild       = guild
        self.ok_direttore = False
        self.ok_sindaco   = False
        self._lock        = asyncio.Lock()

    async def _esegui(self, interaction: discord.Interaction):
        """Esegue l'operazione quando entrambe le conferme sono arrivate."""
        mittente_data = await database.get_user(str(self.mittente.id))
        target_data   = await database.get_user(str(self.target.id))

        if self.operazione == "preleva":
            # Prende soldi dalla banca del target e li mette nei contanti del mittente
            if target_data["bank"] < self.importo:
                await interaction.followup.send(
                    f"❌ **{self.target.display_name}** non ha abbastanza fondi in banca "
                    f"(disponibili: **${target_data['bank']:,}**).",
                    ephemeral=False
                )
                self.stop()
                return
            await database.update_balance(str(self.target.id),   bank=target_data["bank"] - self.importo)
            await database.update_balance(str(self.mittente.id), cash=mittente_data["cash"] + self.importo)
            titolo = "💸 Prelievo Eseguito"
            desc   = (f"**${self.importo:,}** prelevati dal conto di {self.target.mention} "
                      f"e consegnati a {self.mittente.mention}.")
        else:
            # Prende soldi dai contanti del mittente e li mette in banca al target
            if mittente_data["cash"] < self.importo:
                await interaction.followup.send(
                    f"❌ {self.mittente.mention} non ha abbastanza contanti "
                    f"(disponibili: **${mittente_data['cash']:,}**).",
                    ephemeral=False
                )
                self.stop()
                return
            await database.update_balance(str(self.mittente.id), cash=mittente_data["cash"] - self.importo)
            await database.update_balance(str(self.target.id),   bank=target_data["bank"] + self.importo)
            titolo = "🏦 Deposito Eseguito"
            desc   = (f"**${self.importo:,}** depositati sul conto di {self.target.mention} "
                      f"da {self.mittente.mention}.")

        embed_ok = discord.Embed(
            title=f"✅ {titolo}",
            description=desc,
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed_ok.set_footer(text="🤠 Red Dead Redemption II — Banca")

        # Aggiorna il messaggio nel canale banca
        await interaction.message.edit(embed=embed_ok, view=None)
        self.stop()

        # DM al target
        try:
            await self.target.send(embed=embed_ok)
        except Exception:
            pass

    @discord.ui.button(
        label="✅ Conferma Direttore",
        style=discord.ButtonStyle.success,
        custom_id="banca_conferma_direttore_v2"
    )
    async def conferma_direttore(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _has_role(interaction.user, DIRETTORE_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo il **Direttore della Banca** può premere questo tasto.", ephemeral=True
            )
            return
        async with self._lock:
            if self.ok_direttore:
                await interaction.response.send_message("⚠️ Hai già confermato.", ephemeral=True)
                return
            self.ok_direttore = True
            await interaction.response.send_message("✅ Conferma Direttore registrata.", ephemeral=True)
            button.disabled = True
            button.label    = "✅ Direttore ✓"

            if self.ok_sindaco:
                await self._esegui(interaction)
            else:
                await interaction.message.edit(view=self)

    @discord.ui.button(
        label="✅ Conferma Sindaco",
        style=discord.ButtonStyle.primary,
        custom_id="banca_conferma_sindaco_v2"
    )
    async def conferma_sindaco(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _has_role(interaction.user, SINDACO_ROLE_ID):
            await interaction.response.send_message(
                "❌ Solo il **Sindaco** può premere questo tasto.", ephemeral=True
            )
            return
        async with self._lock:
            if self.ok_sindaco:
                await interaction.response.send_message("⚠️ Hai già confermato.", ephemeral=True)
                return
            self.ok_sindaco = True
            await interaction.response.send_message("✅ Conferma Sindaco registrata.", ephemeral=True)
            button.disabled = True
            button.label    = "✅ Sindaco ✓"

            if self.ok_direttore:
                await self._esegui(interaction)
            else:
                await interaction.message.edit(view=self)


# ── View pulsanti Preleva / Deposita (risposta al comando) ───────────────────
class SaldoView(discord.ui.View):
    def __init__(self, bot, mittente: discord.Member, target: discord.Member):
        super().__init__(timeout=300)
        self.bot      = bot
        self.mittente = mittente
        self.target   = target

    # ── Modal importo ─────────────────────────────────────────────────────────
    def _modal(self, operazione: str) -> discord.ui.Modal:
        view_self = self

        class ImportoModal(discord.ui.Modal, title=f"{'Preleva' if operazione == 'preleva' else 'Deposita'} Soldi"):
            importo_field = discord.ui.TextInput(
                label="Importo ($)",
                placeholder="Es: 500",
                min_length=1,
                max_length=10
            )

            async def on_submit(self_modal, interaction: discord.Interaction):
                try:
                    importo = int(self_modal.importo_field.value.replace(",", "").replace(".", ""))
                    if importo <= 0:
                        raise ValueError
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Importo non valido.", ephemeral=True
                    )
                    return

                await interaction.response.defer(ephemeral=True)

                # Costruisce embed di richiesta per il canale banca
                op_label = "PRELIEVO" if operazione == "preleva" else "DEPOSITO"
                op_emoji = "💸" if operazione == "preleva" else "🏦"
                color    = discord.Color.gold() if operazione == "preleva" else discord.Color.blue()

                target_data   = await database.get_user(str(view_self.target.id))
                mittente_data = await database.get_user(str(view_self.mittente.id))

                if operazione == "preleva":
                    desc = (f"**{view_self.mittente.display_name}** vuole prelevare "
                            f"**${importo:,}** dal conto di **{view_self.target.display_name}**.")
                else:
                    desc = (f"**{view_self.mittente.display_name}** vuole depositare "
                            f"**${importo:,}** sul conto di **{view_self.target.display_name}**.")

                embed_req = discord.Embed(
                    title=f"{op_emoji} Richiesta {op_label}",
                    description=desc,
                    color=color,
                    timestamp=discord.utils.utcnow()
                )
                embed_req.set_thumbnail(url=view_self.target.display_avatar.url)
                embed_req.add_field(name="👤 Operatore",     value=view_self.mittente.mention, inline=True)
                embed_req.add_field(name="🎯 Cittadino",     value=view_self.target.mention,   inline=True)
                embed_req.add_field(name="💰 Importo",       value=f"${importo:,}",            inline=True)
                embed_req.add_field(name="🏦 Saldo banca cittadino",
                                    value=f"${target_data['bank']:,}", inline=True)
                embed_req.add_field(name="💵 Contanti operatore",
                                    value=f"${mittente_data['cash']:,}", inline=True)
                embed_req.add_field(
                    name="⚠️ Stato",
                    value="In attesa di: **Direttore** e **Sindaco**",
                    inline=False
                )
                embed_req.set_footer(text="🤠 Red Dead Redemption II — Autorizzazione Banca")

                conferma_view = ConfermaView(
                    bot=view_self.bot,
                    operazione=operazione,
                    importo=importo,
                    mittente=view_self.mittente,
                    target=view_self.target,
                    guild=interaction.guild
                )

                bank_ch = view_self.bot.get_channel(BANK_CHANNEL_ID)
                if bank_ch:
                    await bank_ch.send(
                        content=f"<@&{DIRETTORE_ROLE_ID}> <@&{SINDACO_ROLE_ID}>",
                        embed=embed_req,
                        view=conferma_view
                    )

                await interaction.followup.send(
                    f"✅ Richiesta inviata nel canale banca. "
                    f"In attesa della conferma di **Direttore** e **Sindaco**.",
                    ephemeral=True
                )

        return ImportoModal()

    @discord.ui.button(label="💸 Preleva Soldi", style=discord.ButtonStyle.success)
    async def preleva(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self._modal("preleva"))

    @discord.ui.button(label="🏦 Deposita Soldi", style=discord.ButtonStyle.primary)
    async def deposita(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self._modal("deposita"))


# ─────────────────────────────────────────────────────────────────────────────
def setup_banca_commands(bot):

    # ── /controlla-saldo ──────────────────────────────────────────────────────
    @bot.tree.command(name="controlla-saldo", description="[Banca] Visualizza il saldo bancario di un cittadino")
    @app_commands.describe(cittadino="Il cittadino di cui controllare il saldo")
    async def controlla_saldo(interaction: discord.Interaction, cittadino: discord.Member):
        if not _has_any(interaction, SINDACO_ROLE_ID, DIRETTORE_ROLE_ID, CONTABILE_ROLE_ID):
            await interaction.response.send_message(
                "❌ Non hai i permessi per usare questo comando.", ephemeral=True
            )
            return

        user = await database.get_user(str(cittadino.id))

        embed = discord.Embed(
            title="🏦 𝐒𝐚𝐥𝐝𝐨 𝐁𝐚𝐧𝐜𝐚𝐫𝐢𝐨",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=cittadino.display_avatar.url)
        embed.add_field(name="👤 Titolare",  value=cittadino.mention,       inline=True)
        embed.add_field(name="🏦 In Banca",  value=f"${user['bank']:,}",    inline=True)
        embed.add_field(name="💵 Contanti",  value=f"${user['cash']:,}",    inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Banca")

        view = SaldoView(bot=bot, mittente=interaction.user, target=cittadino)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── /tiro-dadi ────────────────────────────────────────────────────────────
    @bot.tree.command(name="tiro-dadi", description="Lancia un dado da 1 a 10 con animazione")
    async def tiro_dadi(interaction: discord.Interaction):
        risultato = random.randint(1, 10)   # pura probabilità uniforme 10%

        FACCE = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        ANIMAZIONE = ["🎲", "🎰", "✨", "💫", "🌀"]

        # Primo embed — animazione lancio
        embed_anim = discord.Embed(
            title="🎲 𝐋𝐚𝐧𝐜𝐢𝐨 𝐝𝐞𝐥 𝐃𝐚𝐝𝐨",
            description="Il dado rotola sul tavolo...",
            color=discord.Color(0xDAA520)
        )
        embed_anim.set_footer(text="🤠 Red Dead Redemption II — Dadi")

        await interaction.response.send_message(embed=embed_anim)
        msg = await interaction.original_response()

        # Animazione: 5 frame da 0.6s
        for i, frame in enumerate(ANIMAZIONE):
            casuale = random.randint(1, 10)
            embed_frame = discord.Embed(
                title="🎲 𝐋𝐚𝐧𝐜𝐢𝐨 𝐝𝐞𝐥 𝐃𝐚𝐝𝐨",
                description=f"{frame}  **{casuale}**  {frame}",
                color=discord.Color(0xDAA520)
            )
            embed_frame.set_footer(text="🤠 Red Dead Redemption II — Dadi")
            await msg.edit(embed=embed_frame)
            await asyncio.sleep(0.6)

        # Embed risultato finale
        faccia = FACCE[risultato - 1]
        if risultato == 10:
            colore = discord.Color.gold()
            commento = "🌟 Numero massimo! Fortuna sfacciata!"
        elif risultato >= 7:
            colore = discord.Color.green()
            commento = "👍 Buon risultato!"
        elif risultato >= 4:
            colore = discord.Color(0xDAA520)
            commento = "😐 Nella media."
        else:
            colore = discord.Color.red()
            commento = "💀 Sfortuna!"

        embed_finale = discord.Embed(
            title="🎲 𝐑𝐢𝐬𝐮𝐥𝐭𝐚𝐭𝐨 𝐝𝐞𝐥 𝐃𝐚𝐝𝐨",
            description=f"## {faccia}  **{risultato}**  {faccia}\n\n{commento}",
            color=colore,
            timestamp=discord.utils.utcnow()
        )
        embed_finale.add_field(name="🎯 Numero uscito", value=str(risultato), inline=True)
        embed_finale.add_field(name="👤 Giocatore",     value=interaction.user.mention, inline=True)
        embed_finale.add_field(name="📊 Probabilità",   value="10% per ogni numero", inline=True)
        embed_finale.set_footer(text="🤠 Red Dead Redemption II — Dadi")

        await msg.edit(embed=embed_finale)
