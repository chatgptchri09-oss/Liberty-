import discord
from discord import app_commands
import database
import aiosqlite
from constants import LOG_CHANNEL_ID, DATABASE_NAME

# ID virtuale conto Stato
STATO_USER_ID = "STATO"

# Percentuale che va all'emittente (il resto va allo Stato)
PERCENTUALE_EMITTENTE = 0.25


async def _aggiungi_stato(importo: int):
    """Aggiunge importo al conto banca virtuale dello Stato."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, cash, bank, hunger, thirst)
            VALUES (?, 0, ?, 100, 100)
            ON CONFLICT(user_id) DO UPDATE SET bank = bank + ?
        """, (STATO_USER_ID, importo, importo))
        await db.commit()


def setup_invoice_commands(bot):

    # ── /fattura ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="fattura", description="Emetti una fattura per un servizio nel Far West")
    @app_commands.describe(
        destinatario="Il giocatore a cui mandare la fattura",
        importo="Importo in dollari",
        descrizione="Servizio o bene fornito"
    )
    async def fattura(interaction: discord.Interaction, destinatario: discord.Member, importo: int, descrizione: str):
        if destinatario.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi emettere una fattura a te stesso.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        invoice_id = await database.add_invoice(
            str(interaction.user.id), str(destinatario.id), importo, descrizione
        )

        quota_emittente = round(importo * PERCENTUALE_EMITTENTE)
        quota_stato     = importo - quota_emittente

        embed = discord.Embed(
            title="📜 𝐅𝐀𝐓𝐓𝐔𝐑𝐀 𝐄𝐌𝐄𝐒𝐒𝐀",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="🧾 N° Fattura",      value=f"#{invoice_id}",         inline=True)
        embed.add_field(name="💵 Importo totale",  value=f"${importo:,}",           inline=True)
        embed.add_field(name="\u200b",             value="\u200b",                  inline=False)
        embed.add_field(name="📋 Servizio",        value=descrizione,               inline=False)
        embed.add_field(name="\u200b",             value="\u200b",                  inline=False)
        embed.add_field(name="👤 Emessa da",       value=interaction.user.mention,  inline=True)
        embed.add_field(name="🎯 Destinatario",    value=destinatario.mention,      inline=True)
        embed.add_field(name="\u200b",             value="\u200b",                  inline=False)
        embed.add_field(name="💰 Vai all'emittente (25%)", value=f"${quota_emittente:,}", inline=True)
        embed.add_field(name="🏛️ Vai allo Stato (75%)",   value=f"${quota_stato:,}",     inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fattura | Usa /pagafattura per pagare")
        await interaction.response.send_message(embed=embed)

        try:
            dm = discord.Embed(
                title="📜 Hai ricevuto una fattura!",
                description=(
                    f"**{interaction.user.display_name}** ti ha inviato una fattura di **${importo:,}**.\n\n"
                    f"**Servizio:** {descrizione}\n\n"
                    f"Usa `/pagafattura` per pagare — vedrai tutte le tue fatture in sospeso."
                ),
                color=discord.Color(0xDAA520)
            )
            await destinatario.send(embed=dm)
        except Exception:
            pass

    # ── /pagafattura ──────────────────────────────────────────────────────────
    @bot.tree.command(name="pagafattura", description="Paga una fattura ricevuta")
    async def paga_fattura(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid      = str(interaction.user.id)
        fatture  = await database.get_invoices_by_user(uid)

        if not fatture:
            await interaction.followup.send("✅ Non hai fatture in sospeso.", ephemeral=True)
            return

        # ── Costruisce le opzioni del menu ────────────────────────────────────
        options = []
        for inv in fatture[:25]:
            label = f"#{inv['id']} — ${inv['amount']:,} — {inv['description'][:40]}"[:100]
            options.append(discord.SelectOption(label=label, value=str(inv["id"])))

        class FatturaSelect(discord.ui.Select):
            def __init__(self_s):
                super().__init__(
                    placeholder="Seleziona la fattura da pagare...",
                    options=options
                )

            async def callback(self_s, itr: discord.Interaction):
                await itr.response.defer(ephemeral=True)
                invoice_id = int(self_s.values[0])
                invoice    = await database.get_invoice(invoice_id)

                if not invoice or invoice["paid"]:
                    await itr.followup.send("❌ Fattura non trovata o già pagata.", ephemeral=True)
                    return

                user_data = await database.get_user(uid)
                if user_data["cash"] < invoice["amount"]:
                    await itr.followup.send(
                        f"❌ Non hai abbastanza contanti.\n"
                        f"Necessari: **${invoice['amount']:,}** — Hai: **${user_data['cash']:,}**",
                        ephemeral=True
                    )
                    return

                importo         = invoice["amount"]
                quota_emittente = round(importo * PERCENTUALE_EMITTENTE)
                quota_stato     = importo - quota_emittente

                # Scala i soldi dal pagante
                await database.update_balance(uid, cash=user_data["cash"] - importo)
                # Paga l'emittente (25% in contanti)
                emitter = await database.get_user(invoice["from_user"])
                await database.update_balance(invoice["from_user"], cash=emitter["cash"] + quota_emittente)
                # Paga lo Stato (75% in banca virtuale)
                await _aggiungi_stato(quota_stato)
                # Segna come pagata
                await database.pay_invoice(invoice_id)

                embed = discord.Embed(
                    title="✅ 𝐅𝐚𝐭𝐭𝐮𝐫𝐚 𝐏𝐚𝐠𝐚𝐭𝐚",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="🧾 N° Fattura",             value=f"#{invoice_id}",         inline=True)
                embed.add_field(name="💵 Importo totale",         value=f"${importo:,}",           inline=True)
                embed.add_field(name="\u200b",                    value="\u200b",                  inline=False)
                embed.add_field(name="📋 Servizio",               value=invoice["description"],    inline=False)
                embed.add_field(name="\u200b",                    value="\u200b",                  inline=False)
                embed.add_field(name="💰 All'emittente (25%)",    value=f"${quota_emittente:,}",   inline=True)
                embed.add_field(name="🏛️ Allo Stato (75%)",      value=f"${quota_stato:,}",       inline=True)
                embed.set_footer(text="🤠 Red Dead Redemption II — Fattura")
                await itr.followup.send(embed=embed, ephemeral=True)

                # Log
                try:
                    ch = bot.get_channel(LOG_CHANNEL_ID)
                    if ch:
                        log = discord.Embed(
                            title="📜 LOG — Fattura Pagata",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        log.add_field(name="🧾 Fattura",  value=f"#{invoice_id}",       inline=True)
                        log.add_field(name="👤 Pagante",  value=f"<@{uid}>",             inline=True)
                        log.add_field(name="💵 Totale",   value=f"${importo:,}",         inline=True)
                        log.add_field(name="💰 Emittente",value=f"${quota_emittente:,}", inline=True)
                        log.add_field(name="🏛️ Stato",   value=f"${quota_stato:,}",     inline=True)
                        await ch.send(embed=log)
                except Exception:
                    pass

        class FatturaView(discord.ui.View):
            def __init__(self_v):
                super().__init__(timeout=120)
                self_v.add_item(FatturaSelect())

        embed_lista = discord.Embed(
            title="📜 𝐋𝐞 𝐭𝐮𝐞 𝐟𝐚𝐭𝐭𝐮𝐫𝐞 𝐢𝐧 𝐬𝐨𝐬𝐩𝐞𝐬𝐨",
            description="Seleziona la fattura che vuoi pagare dal menu qui sotto.",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        for inv in fatture[:25]:
            embed_lista.add_field(
                name=f"#{inv['id']} — ${inv['amount']:,}",
                value=f"📋 {inv['description']}\n👤 Da: <@{inv['from_user']}>",
                inline=False
            )
        embed_lista.set_footer(text="🤠 Red Dead Redemption II — Fatture")
        await interaction.followup.send(embed=embed_lista, view=FatturaView(), ephemeral=True)

    # ── /leaderboard ──────────────────────────────────────────────────────────
    @bot.tree.command(name="leaderboard", description="Classifica dei giocatori più ricchi del server")
    async def leaderboard(interaction: discord.Interaction):
        await interaction.response.defer()
        utenti = await database.get_all_users_sorted()

        if not utenti:
            await interaction.followup.send("❌ Nessun giocatore registrato.", ephemeral=True)
            return

        # Recupera i display name dalla guild
        guild    = interaction.guild
        PER_PAG  = 10
        tot_pag  = max(1, -(-len(utenti) // PER_PAG))

        def _build_embed(pagina: int) -> discord.Embed:
            embed = discord.Embed(
                title="🏆 𝐋𝐞𝐚𝐝𝐞𝐫𝐛𝐨𝐚𝐫𝐝 — 𝐈 𝐏𝐢ù 𝐑𝐢𝐜𝐜𝐡𝐢 𝐝𝐞𝐥 𝐅𝐚𝐫 𝐖𝐞𝐬𝐭",
                color=discord.Color(0xDAA520),
                timestamp=discord.utils.utcnow()
            )
            slice_ = utenti[pagina * PER_PAG:(pagina + 1) * PER_PAG]
            righe  = []
            for i, u in enumerate(slice_, start=pagina * PER_PAG + 1):
                member = guild.get_member(int(u["user_id"])) if guild else None
                nome   = member.display_name if member else f"<@{u['user_id']}>"
                totale = u["cash"] + u["bank"]
                if i == 1:   medaglia = "🥇"
                elif i == 2: medaglia = "🥈"
                elif i == 3: medaglia = "🥉"
                else:         medaglia = f"**#{i}**"
                righe.append(
                    f"{medaglia} {nome}\n"
                    f"┣ 💵 Contanti: **${u['cash']:,}**\n"
                    f"┗ 🏦 Banca: **${u['bank']:,}**  —  Totale: **${totale:,}**"
                )
            embed.description = "\n\n".join(righe)
            embed.set_footer(text=f"🤠 Red Dead Redemption II — Pagina {pagina+1}/{tot_pag}")
            return embed

        class LeaderView(discord.ui.View):
            def __init__(self_v, p: int = 0):
                super().__init__(timeout=120)
                self_v.p = p
                self_v._aggiorna()

            def _aggiorna(self_v):
                self_v.prev_btn.disabled = self_v.p == 0
                self_v.next_btn.disabled = self_v.p >= tot_pag - 1

            @discord.ui.button(label="⬅️ Pagina", style=discord.ButtonStyle.primary)
            async def prev_btn(self_v, itr: discord.Interaction, btn):
                self_v.p -= 1
                self_v._aggiorna()
                await itr.response.edit_message(embed=_build_embed(self_v.p), view=self_v)

            @discord.ui.button(label="➡️ Pagina", style=discord.ButtonStyle.primary)
            async def next_btn(self_v, itr: discord.Interaction, btn):
                self_v.p += 1
                self_v._aggiorna()
                await itr.response.edit_message(embed=_build_embed(self_v.p), view=self_v)

        view = LeaderView(0) if tot_pag > 1 else discord.ui.View(timeout=120)
        await interaction.followup.send(embed=_build_embed(0), view=view)
