import discord
from discord import app_commands
import database
from constants import LOG_CHANNEL_ID, has_sceriffo

# ── Ruoli ─────────────────────────────────────────────────────────────────────
FDO_ROLE_ID       = 1404051916140449885
CRIMINALE_ROLE_ID = 1404052021539242036

def _has_fdo(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    return any(r.id == FDO_ROLE_ID for r in interaction.user.roles)

def _has_criminale(interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    return any(r.id == CRIMINALE_ROLE_ID for r in interaction.user.roles)

def _has_perquisizione(interaction) -> bool:
    return _has_fdo(interaction) or _has_criminale(interaction)


def setup_arrest_commands(bot):

    # ── /ammanetto ────────────────────────────────────────────────────────────
    @bot.tree.command(name="ammanetto", description="[FDO] Ammanetta un sospettato")
    @app_commands.describe(sospettato="Il sospettato", motivo="Motivo dell'arresto")
    async def ammanetto(interaction: discord.Interaction, sospettato: discord.Member, motivo: str):
        if not has_sceriffo(interaction):
            await interaction.response.send_message("❌ Solo lo Sceriffo può ammanettare.", ephemeral=True); return
        embed = discord.Embed(
            title="<a:manette:1431626831076921507> AMMANETTATO",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=sospettato.display_avatar.url)
        embed.add_field(name="🤠 Sospettato", value=sospettato.mention,       inline=True)
        embed.add_field(name="📋 Motivo",     value=motivo,                   inline=False)
        embed.add_field(name="⭐ Agente",     value=interaction.user.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sceriffo")
        await interaction.response.send_message(embed=embed)
        try:
            await sospettato.send(embed=discord.Embed(
                title="<a:manette:1431626831076921507> Sei stato ammanettato!",
                description=f"L'agente **{interaction.user.display_name}** ti ha fermato.\n**Motivo:** {motivo}",
                color=discord.Color.red()
            ))
        except Exception: pass
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ── /perquisizione ────────────────────────────────────────────────────────
    @bot.tree.command(name="perquisizione", description="[FDO/Criminali] Perquisisci un giocatore e vedi bisaccia e soldi")
    @app_commands.describe(bersaglio="Il giocatore da perquisire")
    async def perquisizione(interaction: discord.Interaction, bersaglio: discord.Member):
        if not _has_perquisizione(interaction):
            await interaction.response.send_message(
                "❌ Solo le **Forze dell'Ordine** o i **Criminali** possono perquisire.", ephemeral=True); return
        if bersaglio.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi perquisire te stesso.", ephemeral=True); return

        await interaction.response.defer(ephemeral=True)

        uid        = str(bersaglio.id)
        user_data  = await database.get_user(uid)
        inventario = await database.get_inventory(uid)

        if inventario:
            righe_inv = "\n".join(f"• {item['item_name']} x{item['quantity']}" for item in inventario)
        else:
            righe_inv = "*Bisaccia vuota*"

        if _has_fdo(interaction):
            titolo_ruolo = "⭐ Agente"
            colore       = discord.Color(0x8B4513)
            titolo       = "🔍 𝐏𝐄𝐑𝐐𝐔𝐈𝐒𝐈𝐙𝐈𝐎𝐍𝐄 𝐔𝐅𝐅𝐈𝐂𝐈𝐀𝐋𝐄"
        else:
            titolo_ruolo = "🦹 Criminale"
            colore       = discord.Color(0x2C2C2C)
            titolo       = "🔍 𝐏𝐄𝐑𝐐𝐔𝐈𝐒𝐈𝐙𝐈𝐎𝐍𝐄"

        embed = discord.Embed(title=titolo, color=colore, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=bersaglio.display_avatar.url)
        embed.add_field(name=titolo_ruolo,            value=interaction.user.mention,  inline=True)
        embed.add_field(name="🎯 Perquisito",         value=bersaglio.mention,         inline=True)
        embed.add_field(name="\u200b",                value="\u200b",                  inline=False)
        embed.add_field(name="💵 Contanti",           value=f"${user_data['cash']:,}", inline=True)
        embed.add_field(name="🏦 In Banca",           value=f"${user_data['bank']:,}", inline=True)
        embed.add_field(name="\u200b",                value="\u200b",                  inline=False)
        embed.add_field(name="🎒 Contenuto Bisaccia", value=righe_inv[:1024],          inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Perquisizione")
        await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            dm = discord.Embed(
                title="🔍 Sei stato perquisito!",
                description=(
                    f"**{interaction.user.display_name}** ha perquisito la tua bisaccia.\n\n"
                    f"💵 **Contanti visti:** ${user_data['cash']:,}\n"
                    f"🎒 **Inventario visto:** sì"
                ),
                color=colore, timestamp=discord.utils.utcnow()
            )
            dm.set_footer(text="🤠 Red Dead Redemption II — Perquisizione")
            await bersaglio.send(embed=dm)
        except Exception: pass

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="🔍 LOG — Perquisizione", color=colore, timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Eseguita da",  value=interaction.user.mention,  inline=True)
                log.add_field(name="🎯 Perquisito",   value=bersaglio.mention,         inline=True)
                log.add_field(name="💵 Contanti",     value=f"${user_data['cash']:,}", inline=True)
                log.add_field(name="🎒 Item trovati", value=str(len(inventario)),      inline=True)
                await ch.send(embed=log)
        except Exception: pass

    # ── /sequestra — autocomplete fuzzy sulla bisaccia del bersaglio ──────────
    # Nota: l'autocomplete di Discord non può conoscere il bersaglio in tempo reale
    # perché i parametri vengono risolti in ordine. La soluzione è usare
    # l'autocomplete sull'oggetto cercando tra TUTTI gli item del server,
    # e poi al momento dell'esecuzione verificare che il bersaglio ce l'abbia.
    # In alternativa usiamo un approccio più semplice e funzionale:
    # l'utente digita parte del nome e l'autocomplete mostra i match fuzzy
    # dall'inventario del bersaglio SE il bersaglio è già stato selezionato
    # (Discord passa i valori già inseriti nell'interaction dell'autocomplete).

    async def _ac_oggetto(interaction: discord.Interaction, current: str):
        # Prende il bersaglio dall'interaction se già selezionato
        try:
            bersaglio_id = interaction.namespace.bersaglio
            if not bersaglio_id:
                return []
            uid = str(bersaglio_id.id) if hasattr(bersaglio_id, "id") else str(bersaglio_id)
        except Exception:
            return []

        inventario = await database.get_inventory(uid)
        if not inventario:
            return []

        parole = current.lower().split()
        risultati = []
        for item in inventario:
            nome  = item["item_name"]
            nome_lower = nome.lower()
            # Fuzzy: tutte le parole digitate devono essere contenute nel nome
            if all(p in nome_lower for p in parole):
                label = f"{nome} (x{item['quantity']})"[:100]
                risultati.append(app_commands.Choice(name=label, value=nome))

        return risultati[:25]

    @bot.tree.command(name="sequestra", description="[FDO/Criminali] Sequestra un oggetto dalla bisaccia di un giocatore")
    @app_commands.describe(
        bersaglio="Il giocatore a cui sequestrare l'oggetto",
        oggetto="Cerca l'oggetto (scrivi parte del nome)",
        quantita="Quantità da sequestrare (default: 1)"
    )
    @app_commands.autocomplete(oggetto=_ac_oggetto)
    async def sequestra(interaction: discord.Interaction, bersaglio: discord.Member,
                        oggetto: str, quantita: int = 1):
        if not _has_perquisizione(interaction):
            await interaction.response.send_message(
                "❌ Solo le **Forze dell'Ordine** o i **Criminali** possono sequestrare oggetti.", ephemeral=True); return
        if bersaglio.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi sequestrare oggetti a te stesso.", ephemeral=True); return
        if quantita <= 0:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True); return

        await interaction.response.defer(ephemeral=True)

        uid_bersaglio = str(bersaglio.id)
        uid_esecutore = str(interaction.user.id)

        # Verifica disponibilità — supporta anche nome parziale cercando il match esatto prima,
        # poi il primo match fuzzy se non trovato esattamente
        qty_disponibile = await database.get_item_quantity(uid_bersaglio, oggetto)
        if qty_disponibile == 0:
            # Prova fuzzy fallback: cerca il primo item che contiene il testo digitato
            inventario = await database.get_inventory(uid_bersaglio)
            parole     = oggetto.lower().split()
            match      = next(
                (i for i in inventario if all(p in i["item_name"].lower() for p in parole)),
                None
            )
            if not match:
                await interaction.followup.send(
                    f"❌ **{bersaglio.display_name}** non ha nessun oggetto corrispondente a `{oggetto}` nella bisaccia.",
                    ephemeral=True
                ); return
            oggetto         = match["item_name"]
            qty_disponibile = match["quantity"]

        if qty_disponibile < quantita:
            await interaction.followup.send(
                f"❌ **{bersaglio.display_name}** ha solo **{qty_disponibile}x** `{oggetto}`.\n"
                f"Non puoi sequestrarne {quantita}.",
                ephemeral=True
            ); return

        if _has_fdo(interaction):
            colore = discord.Color(0x8B4513)
            label  = "⭐ Sequestro FDO"
        else:
            colore = discord.Color(0x2C2C2C)
            label  = "🦹 Rapina"

        embed_confirm = discord.Embed(
            title=f"⚠️ Conferma {label}",
            description=(
                f"Stai per sequestrare **{quantita}x {oggetto}** da {bersaglio.mention}.\n\n"
                f"L'oggetto verrà aggiunto alla **tua bisaccia**.\n"
                f"**Il giocatore riceverà un DM** con la notifica del sequestro.\n\n"
                f"Sei sicuro?"
            ),
            color=colore, timestamp=discord.utils.utcnow()
        )
        embed_confirm.set_footer(text="🤠 Red Dead Redemption II — Hai 60 secondi per confermare")

        class ConfermaView(discord.ui.View):
            def __init__(self_v):
                super().__init__(timeout=60)
                self_v.confermato = False

            @discord.ui.button(label="✅ Conferma Sequestro", style=discord.ButtonStyle.danger)
            async def conferma(self_v, itr: discord.Interaction, btn: discord.ui.Button):
                if itr.user.id != interaction.user.id:
                    await itr.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
                self_v.confermato = True
                self_v.stop()
                await itr.response.defer()

            @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.secondary)
            async def annulla(self_v, itr: discord.Interaction, btn: discord.ui.Button):
                if itr.user.id != interaction.user.id:
                    await itr.response.send_message("❌ Non è il tuo pannello.", ephemeral=True); return
                self_v.stop()
                await itr.response.edit_message(content="❌ Sequestro annullato.", embed=None, view=None)

        view = ConfermaView()
        await interaction.followup.send(embed=embed_confirm, view=view, ephemeral=True)
        await view.wait()

        if not view.confermato:
            return

        rimosso = await database.remove_item(uid_bersaglio, oggetto, quantita)
        if not rimosso:
            await interaction.followup.send("❌ Errore: oggetto non trovato o quantità insufficiente.", ephemeral=True); return

        await database.add_item(uid_esecutore, oggetto, quantita)

        embed_ok = discord.Embed(
            title=f"✅ {label} Completato",
            color=discord.Color.green(), timestamp=discord.utils.utcnow()
        )
        embed_ok.set_thumbnail(url=bersaglio.display_avatar.url)
        embed_ok.add_field(name="👤 Eseguito da", value=interaction.user.mention, inline=True)
        embed_ok.add_field(name="🎯 Bersaglio",   value=bersaglio.mention,        inline=True)
        embed_ok.add_field(name="\u200b",         value="\u200b",                 inline=False)
        embed_ok.add_field(name="📦 Oggetto",     value=oggetto,                  inline=True)
        embed_ok.add_field(name="🔢 Quantità",    value=str(quantita),            inline=True)
        embed_ok.set_footer(text="🤠 Red Dead Redemption II — Sequestro")
        await interaction.followup.send(embed=embed_ok, ephemeral=True)

        try:
            dm = discord.Embed(
                title="🚨 Ti è stato sequestrato un oggetto!",
                description=(
                    f"**{interaction.user.mention}** ti ha sequestrato:\n\n"
                    f"📦 **{quantita}x {oggetto}**\n\n"
                    f"*Se ritieni che questo sia un abuso, contatta lo Staff.*"
                ),
                color=discord.Color.red(), timestamp=discord.utils.utcnow()
            )
            dm.set_footer(text="🤠 Red Dead Redemption II — Sequestro")
            await bersaglio.send(embed=dm)
        except Exception: pass

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title=f"📦 LOG — {label}", color=colore, timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Eseguito da", value=interaction.user.mention, inline=True)
                log.add_field(name="🎯 Bersaglio",   value=bersaglio.mention,        inline=True)
                log.add_field(name="📦 Oggetto",     value=oggetto,                  inline=True)
                log.add_field(name="🔢 Quantità",    value=str(quantita),            inline=True)
                await ch.send(embed=log)
        except Exception: pass
