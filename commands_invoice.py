import discord
from discord import app_commands
import database
import aiosqlite
from constants import LOG_CHANNEL_ID, DATABASE_NAME

# Percentuale che va all'emittente (il resto va al fondo cassa azienda)
PERCENTUALE_EMITTENTE = 0.25

# ── Aziende per /fattura ───────────────────────────────────────────────────────
ARMIERE_ROLE_ID   = 1404051953188733002
STALLA_ROLE_ID    = 1404051942698913792
AGENZIA_ROLE_ID   = 1404051965364670545
STAFF_ROLE_ID     = 1404051875426467902
CHIAVE_ROLE_ID    = 1404051860121456701

LOG_ARMERIA_CH    = 1501575429461639249
LOG_STALLA_CH     = 1501575466925166785
LOG_AGENZIA_CH    = 1501575481172951162

AZIENDE_CONFIG = {
    "Armeria":             {"ruolo": ARMIERE_ROLE_ID, "log_ch": LOG_ARMERIA_CH,  "emoji": "🔫", "fondocassa": "Armiere"},
    "Stalla":              {"ruolo": STALLA_ROLE_ID,  "log_ch": LOG_STALLA_CH,   "emoji": "🐴", "fondocassa": "Stalla"},
    "Agenzia Immobiliare": {"ruolo": AGENZIA_ROLE_ID, "log_ch": LOG_AGENZIA_CH,  "emoji": "🏡", "fondocassa": "Agenzia"},
}

# ── Stato azioni criminali (in memoria — si resetta al riavvio) ────────────────
_azioni_criminali_attive: bool = True


def _azienda_da_desc(description: str) -> tuple[str, dict] | tuple[None, None]:
    """Estrae il nome azienda dal separatore ' | ' in fondo alla descrizione."""
    if " | " in description:
        az_nome = description.rsplit(" | ", 1)[-1].strip()
        if az_nome in AZIENDE_CONFIG:
            return az_nome, AZIENDE_CONFIG[az_nome]
    return None, None


def setup_invoice_commands(bot):

    # ── /fattura ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="fattura", description="Emetti una fattura per un servizio nel Far West")
    @app_commands.describe(
        destinatario="Il giocatore a cui mandare la fattura",
        importo="Importo in dollari",
        descrizione="Servizio o bene fornito",
        azienda="L'azienda che emette la fattura"
    )
    @app_commands.choices(azienda=[
        app_commands.Choice(name="🔫 Armeria",             value="Armeria"),
        app_commands.Choice(name="🐴 Stalla",              value="Stalla"),
        app_commands.Choice(name="🏡 Agenzia Immobiliare", value="Agenzia Immobiliare"),
    ])
    async def fattura(interaction: discord.Interaction, destinatario: discord.Member,
                      importo: int, descrizione: str, azienda: str):
        if destinatario.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi emettere una fattura a te stesso.", ephemeral=True)
            return
        if importo <= 0:
            await interaction.response.send_message("❌ L'importo deve essere positivo.", ephemeral=True)
            return

        # Verifica ruolo azienda
        az = AZIENDE_CONFIG[azienda]
        if not isinstance(interaction.user, discord.Member) or \
                not any(r.id == az["ruolo"] for r in interaction.user.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo **{azienda}** per emettere fatture a suo nome.", ephemeral=True)
            return

        # Salva l'azienda nella descrizione come " | NomeAzienda" in fondo
        desc_con_az = f"{descrizione} | {azienda}"
        invoice_id = await database.add_invoice(
            str(interaction.user.id), str(destinatario.id), importo, desc_con_az
        )

        quota_emittente = round(importo * PERCENTUALE_EMITTENTE)
        quota_fc        = importo - quota_emittente

        embed = discord.Embed(
            title=f"📜 𝐅𝐀𝐓𝐓𝐔𝐑𝐀 𝐄𝐌𝐄𝐒𝐒𝐀 — {az['emoji']} {azienda.upper()}",
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
        embed.add_field(name=f"{az['emoji']} Azienda", value=azienda,               inline=True)
        embed.add_field(name="\u200b",             value="\u200b",                  inline=False)
        embed.add_field(name="💰 All'emittente (25%)",        value=f"${quota_emittente:,}", inline=True)
        embed.add_field(name=f"{az['emoji']} Fondo Cassa (75%)", value=f"${quota_fc:,}",     inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Fattura | Usa /pagafattura per pagare")
        await interaction.response.send_message(embed=embed)

        # DM al destinatario
        try:
            dm = discord.Embed(
                title="📜 Hai ricevuto una fattura!",
                description=(
                    f"**{interaction.user.display_name}** ti ha inviato una fattura di **${importo:,}**.\n\n"
                    f"**Servizio:** {descrizione}\n"
                    f"**Azienda:** {az['emoji']} {azienda}\n\n"
                    f"Usa `/pagafattura` per pagare."
                ),
                color=discord.Color(0xDAA520)
            )
            await destinatario.send(embed=dm)
        except Exception:
            pass

        # ── Log canale azienda — FATTURA EMESSA ──────────────────────────────
        try:
            log_ch = bot.get_channel(az["log_ch"])
            if log_ch:
                log = discord.Embed(
                    title=f"📜 LOG — Fattura Emessa | {az['emoji']} {azienda}",
                    color=discord.Color(0xDAA520),
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="🧾 N° Fattura",                  value=f"#{invoice_id}",              inline=True)
                log.add_field(name="💵 Importo",                     value=f"${importo:,}",               inline=True)
                log.add_field(name="📋 Servizio",                    value=descrizione,                   inline=False)
                log.add_field(name="👤 Emessa da",                   value=interaction.user.mention,      inline=True)
                log.add_field(name="🎯 Destinatario",                value=destinatario.mention,          inline=True)
                log.add_field(name="💰 All'emittente (25%)",         value=f"${quota_emittente:,}",       inline=True)
                log.add_field(name=f"{az['emoji']} Fondo Cassa (75%)", value=f"${quota_fc:,}",           inline=True)
                await log_ch.send(content=interaction.user.mention, embed=log)
        except Exception:
            pass

    # ── /pagafattura ──────────────────────────────────────────────────────────
    @bot.tree.command(name="pagafattura", description="Paga una fattura ricevuta")
    async def paga_fattura(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid     = str(interaction.user.id)
        fatture = await database.get_invoices_by_user(uid)

        if not fatture:
            await interaction.followup.send("✅ Non hai fatture in sospeso.", ephemeral=True)
            return

        options = []
        for inv in fatture[:25]:
            # Mostra la descrizione pulita (senza " | Azienda" in fondo)
            desc_pulita = inv["description"].rsplit(" | ", 1)[0] if " | " in inv["description"] else inv["description"]
            label = f"#{inv['id']} — ${inv['amount']:,} — {desc_pulita[:40]}"[:100]
            options.append(discord.SelectOption(label=label, value=str(inv["id"])))

        class FatturaSelect(discord.ui.Select):
            def __init__(self_s):
                super().__init__(placeholder="Seleziona la fattura da pagare...", options=options)

            async def callback(self_s, itr: discord.Interaction):
                await itr.response.defer(ephemeral=True)
                invoice_id = int(self_s.values[0])
                invoice    = await database.get_invoice(invoice_id)

                if not invoice or invoice["paid"]:
                    await itr.followup.send("❌ Fattura non trovata o già pagata.", ephemeral=True)
                    return

                user_data = await database.get_user(uid)
                importo   = invoice["amount"]
                cash_disp = user_data["cash"]
                bank_disp = user_data["bank"]

                if cash_disp + bank_disp < importo:
                    await itr.followup.send(
                        f"❌ Fondi insufficienti.\n"
                        f"Necessari: **${importo:,}** — Hai: **${cash_disp:,}** in contanti e **${bank_disp:,}** in banca",
                        ephemeral=True
                    )
                    return

                # Scala prima dai contanti, poi dalla banca per il resto
                if cash_disp >= importo:
                    nuovo_cash = cash_disp - importo
                    nuovo_bank = bank_disp
                else:
                    nuovo_cash = 0
                    nuovo_bank = bank_disp - (importo - cash_disp)

                quota_emittente = round(importo * PERCENTUALE_EMITTENTE)
                quota_fc        = importo - quota_emittente

                # Aggiorna saldo pagante
                await database.update_balance(uid, cash=nuovo_cash, bank=nuovo_bank)
                # Paga l'emittente (25% in contanti)
                emitter = await database.get_user(invoice["from_user"])
                await database.update_balance(invoice["from_user"], cash=emitter["cash"] + quota_emittente)
                # Paga il 75% al fondo cassa dell'azienda
                az_nome, az_cfg = _azienda_da_desc(invoice["description"])
                if az_nome:
                    fc_attuale = await database.get_fondocassa(az_cfg["fondocassa"])
                    await database.update_fondocassa(az_cfg["fondocassa"], fc_attuale + quota_fc)

                # Segna come pagata
                await database.pay_invoice(invoice_id)

                # Descrizione pulita per gli embed
                desc_pulita = invoice["description"].rsplit(" | ", 1)[0] if " | " in invoice["description"] else invoice["description"]

                embed = discord.Embed(
                    title="✅ 𝐅𝐚𝐭𝐭𝐮𝐫𝐚 𝐏𝐚𝐠𝐚𝐭𝐚",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="🧾 N° Fattura",    value=f"#{invoice_id}",       inline=True)
                embed.add_field(name="💵 Importo totale", value=f"${importo:,}",        inline=True)
                embed.add_field(name="\u200b",            value="\u200b",               inline=False)
                embed.add_field(name="📋 Servizio",       value=desc_pulita,            inline=False)
                embed.add_field(name="\u200b",            value="\u200b",               inline=False)
                embed.add_field(name="💰 All'emittente (25%)", value=f"${quota_emittente:,}", inline=True)
                if az_nome:
                    embed.add_field(
                        name=f"{az_cfg['emoji']} Fondo Cassa {az_nome} (75%)",
                        value=f"${quota_fc:,}", inline=True
                    )
                embed.set_footer(text="🤠 Red Dead Redemption II — Fattura")
                await itr.followup.send(embed=embed, ephemeral=True)

                # ── Log canale generale ───────────────────────────────────────
                try:
                    ch = bot.get_channel(LOG_CHANNEL_ID)
                    if ch:
                        log = discord.Embed(
                            title="📜 LOG — Fattura Pagata",
                            color=discord.Color.green(),
                            timestamp=discord.utils.utcnow()
                        )
                        log.add_field(name="🧾 Fattura",    value=f"#{invoice_id}",              inline=True)
                        log.add_field(name="👤 Pagante",    value=f"<@{uid}>",                   inline=True)
                        log.add_field(name="🧑‍💼 Emesso da", value=f"<@{invoice['from_user']}>",  inline=True)
                        log.add_field(name="💵 Totale",     value=f"${importo:,}",               inline=True)
                        log.add_field(name="💰 Emittente",  value=f"${quota_emittente:,}",       inline=True)
                        if az_nome:
                            log.add_field(name=f"{az_cfg['emoji']} Fondo Cassa", value=f"${quota_fc:,}", inline=True)
                        await ch.send(embed=log)
                except Exception:
                    pass

                # ── Log canale azienda — FATTURA PAGATA ──────────────────────
                try:
                    if az_nome and az_cfg:
                        log_az_ch = bot.get_channel(az_cfg["log_ch"])
                        if log_az_ch:
                            log_az = discord.Embed(
                                title=f"✅ LOG — Fattura Pagata | {az_cfg['emoji']} {az_nome}",
                                color=discord.Color.green(),
                                timestamp=discord.utils.utcnow()
                            )
                            log_az.add_field(name="🧾 N° Fattura",   value=f"#{invoice_id}",              inline=True)
                            log_az.add_field(name="💵 Totale",       value=f"${importo:,}",               inline=True)
                            log_az.add_field(name="📋 Servizio",     value=desc_pulita,                   inline=False)
                            log_az.add_field(name="👤 Pagato da",    value=f"<@{uid}>",                   inline=True)
                            log_az.add_field(name="🧑‍💼 Emittente",   value=f"<@{invoice['from_user']}>",  inline=True)
                            log_az.add_field(name="💰 All'emittente (25%)",              value=f"${quota_emittente:,}", inline=True)
                            log_az.add_field(name=f"{az_cfg['emoji']} Fondo Cassa (75%)", value=f"${quota_fc:,}",      inline=True)
                            await log_az_ch.send(content=f"<@{invoice['from_user']}>", embed=log_az)
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
            desc_pulita = inv["description"].rsplit(" | ", 1)[0] if " | " in inv["description"] else inv["description"]
            embed_lista.add_field(
                name=f"#{inv['id']} — ${inv['amount']:,}",
                value=f"📋 {desc_pulita}\n👤 Da: <@{inv['from_user']}>",
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

        guild   = interaction.guild
        PER_PAG = 10
        tot_pag = max(1, -(-len(utenti) // PER_PAG))

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
                else:        medaglia = f"**#{i}**"
                righe.append(f"{medaglia} {nome}\n┗ 🏦 Totale Soldi: **${totale:,}**")
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

    # ── /azioni-criminali-on ──────────────────────────────────────────────────
    @bot.tree.command(name="azioni-criminali-on", description="[Staff] Attiva le azioni criminali nel server")
    async def azioni_criminali_on(interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or \
                not any(r.id in (STAFF_ROLE_ID, CHIAVE_ROLE_ID) for r in interaction.user.roles):
            await interaction.response.send_message("❌ Solo lo Staff può usare questo comando.", ephemeral=True)
            return

        global _azioni_criminali_attive
        _azioni_criminali_attive = True

        embed = discord.Embed(
            title="<a:online:1459627385702973572> 𝐀𝐙𝐈𝐎𝐍𝐈 𝐂𝐑𝐈𝐌𝐈𝐍𝐀𝐋𝐈 𝐎𝐍𝐋𝐈𝐍𝐄 <a:online:1459627385702973572>",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url="https://i.postimg.cc/PfPSxmzZ/2b2664d3-4692-4371-8ddc-d59881a795dc.png")
        embed.set_footer(text=f"🤠 Attivate da {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    # ── /azioni-criminali-off ─────────────────────────────────────────────────
    @bot.tree.command(name="azioni-criminali-off", description="[Staff] Disattiva le azioni criminali nel server")
    async def azioni_criminali_off(interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or \
                not any(r.id in (STAFF_ROLE_ID, CHIAVE_ROLE_ID) for r in interaction.user.roles):
            await interaction.response.send_message("❌ Solo lo Staff può usare questo comando.", ephemeral=True)
            return

        global _azioni_criminali_attive
        _azioni_criminali_attive = False

        embed = discord.Embed(
            title="<a:offline:1459628872197738641> 𝐀𝐙𝐈𝐎𝐍𝐈 𝐂𝐑𝐈𝐌𝐈𝐍𝐀𝐋𝐈 𝐎𝐅𝐅𝐋𝐈𝐍𝐄 <a:offline:1459628872197738641>",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_image(url="https://i.postimg.cc/PfPSxmzZ/2b2664d3-4692-4371-8ddc-d59881a795dc.png")
        embed.set_footer(text=f"🤠 Disattivate da {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
