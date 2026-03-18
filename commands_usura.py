import discord
from discord import app_commands
import aiosqlite
import asyncio
from datetime import datetime, timezone
from constants import LOG_CHANNEL_ID, DATABASE_NAME

# ── Costanti ──────────────────────────────────────────────────────────────────
OLIO_ITEM   = "<:OlioArmi:1483872658574544988> • Olio per Armi"
COTE_ITEM   = "<:Cote:1483873630986174484> • Cote"

AVVISI_USURA = {75, 50, 25, 10, 5, 0}

# ── Armi da FUOCO (calo 5%/24h, 2% per passaggio) ────────────────────────────
ARMI_FUOCO = {
    # Revolver
    "<:Revolver:1457468114575822918> • Revolver d'Azzardo",
    "<:Revolver:1457468114575822918> • Revolver d'Azzardo (M.N.)",
    "<:Revolver:1457468114575822918> • Revolver Cattleman",
    "<:Revolver:1457468114575822918> • Revolver Cattleman (M.N.)",
    "<:Revolver:1457468114575822918> • Revolver a Doppia Azione",
    "<:Revolver:1457468114575822918> • Revolver a Doppia Azione (M.N.)",
    "<:Revolver:1457468114575822918> • Revolver Schofield",
    "<:Revolver:1457468114575822918> • Revolver Schofield (M.N.)",
    "<:Revolver:1457468114575822918> • Revolver Navy",
    "<:Revolver:1457468114575822918> • Revolver Navy (M.N.)",
    # Pistole
    "<:Volcanic:1457650683837677653> • Pistola Volcanic",
    "<:Volcanic:1457650683837677653> • Pistola Volcanic (M.N.)",
    # Fucili a canne mozze
    "<:DoppiettaaCanneMozze:1457657137533550685> • Fucile a Canne Mozze Lisce",
    "<:DoppiettaaCanneMozze:1457657137533550685> • Fucile a Canne Mozze Lisce (M.N.)",
    # Doppiette
    "<:Doppietta:1457655998562041947> • Doppietta a Canne Lisce",
    "<:Doppietta:1457655998562041947> • Doppietta a Canne Lisce (M.N.)",
    # Fucili a pompa
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia a Pompa",
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia a Pompa (M.N.)",
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia Semiautomatico",
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia Semiautomatico (M.N.)",
    # Carabine e ripetizioni
    "<:Litchfield:1457518211716087961> • Carabina a Ripetizione",
    "<:Litchfield:1457518211716087961> • Carabina a Ripetizione (M.N.)",
    "<:Litchfield:1457518211716087961> • Lancaster a Ripetizione",
    "<:Litchfield:1457518211716087961> • Lancaster a Ripetizione (M.N.)",
    # Fucili a canna rigata
    "<:Springfield:1457642354717622362> • Varmint a Canna Rigata",
    "<:Springfield:1457642354717622362> • Varmint a Canna Rigata (M.N.)",
    "<:Springfield:1457642354717622362> • Springfield a Canna Rigata",
    "<:Springfield:1457642354717622362> • Springfield a Canna Rigata (M.N.)",
    "<:Springfield:1457642354717622362> • Bolt-Action a Canna Rigata",
    "<:Springfield:1457642354717622362> • Bolt-Action a Canna Rigata (M.N.)",
}

# ── Armi da MISCHIA (calo 2%/24h, 1% per passaggio) — escluso lazo ───────────
ARMI_MISCHIA = {
    "🪓 • Accetta",
    "🪓 • Accetta da Caccia",
    "🪓 • Mannaia",
    "🔨 • Martello",
    "🪓 • Tomahawk",
    "<:Coltello:1457696753892720760> • Coltello",
    "<:Coltello:1457696753892720760> • Coltello a Lancia",
    "<:Coltello:1457696753892720760> • Coltello Mandibola",
    "<:Coltello:1457696753892720760> • Coltello da Lancio",
    "<:Machete:1457700008244674593> • Machete",
    "<:FaretraConFreccie:1457707105078214879> • Faretra con Frecce",
    "<:Arco:1457700407282241671> • Arco",
    "<:ArcoMigliorato:1457701357342687335> • Arco Migliorato",
    "📿 • Bolas",
    # Lazo e Lazo Rinforzato ESCLUSI
}

ALL_ARMI = ARMI_FUOCO | ARMI_MISCHIA

# ── Helper: tipo arma ─────────────────────────────────────────────────────────
def _tipo_arma(nome: str) -> str | None:
    if nome in ARMI_FUOCO:   return "fuoco"
    if nome in ARMI_MISCHIA: return "mischia"
    return None

def _calo_24h(tipo: str) -> int:
    return 5 if tipo == "fuoco" else 2

def _calo_passaggio(tipo: str) -> int:
    return 2 if tipo == "fuoco" else 1

def _item_pulizia(tipo: str) -> str:
    return OLIO_ITEM if tipo == "fuoco" else COTE_ITEM

# ── DB helpers ────────────────────────────────────────────────────────────────
async def init_usura_table():
    """Crea la tabella usura se non esiste (chiamare da on_ready o init_db)."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weapon_durability (
                user_id   TEXT NOT NULL,
                item_name TEXT NOT NULL,
                usura     INTEGER DEFAULT 100,
                PRIMARY KEY (user_id, item_name)
            )
        """)
        await db.commit()

async def get_usura(user_id: str, item_name: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT usura FROM weapon_durability WHERE user_id=? AND item_name=?",
            (user_id, item_name)
        ) as c:
            row = await c.fetchone()
            return row[0] if row else 100

async def set_usura(user_id: str, item_name: str, valore: int):
    v = max(0, min(100, valore))
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO weapon_durability (user_id, item_name, usura)
            VALUES (?,?,?)
            ON CONFLICT(user_id, item_name) DO UPDATE SET usura=excluded.usura
        """, (user_id, item_name, v))
        await db.commit()

async def delete_usura(user_id: str, item_name: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "DELETE FROM weapon_durability WHERE user_id=? AND item_name=?",
            (user_id, item_name)
        )
        await db.commit()

async def get_tutte_usure_utente(user_id: str) -> list[dict]:
    """Ritorna lista {item_name, usura} per le armi dell'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_name, usura FROM weapon_durability WHERE user_id=?",
            (user_id,)
        ) as c:
            rows = await c.fetchall()
    return [{"item_name": r["item_name"], "usura": r["usura"]} for r in rows]

async def get_armi_inventario(user_id: str) -> list[str]:
    """Ritorna i nomi delle armi (fra ALL_ARMI) presenti nell'inventario dell'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_name FROM inventory WHERE user_id=? AND quantity>0",
            (user_id,)
        ) as c:
            rows = await c.fetchall()
    return [r["item_name"] for r in rows if r["item_name"] in ALL_ARMI]

# ── Helper: barra usura ───────────────────────────────────────────────────────
def _barra(v: int) -> str:
    piena = round(v / 10)
    if v >= 75:   colore = "🟩"
    elif v >= 50: colore = "🟨"
    elif v >= 25: colore = "🟧"
    else:         colore = "🟥"
    return colore * piena + "⬛" * (10 - piena) + f"  **{v}%**"

def _colore_usura(v: int) -> discord.Color:
    if v >= 75:   return discord.Color.green()
    if v >= 50:   return discord.Color.yellow()
    if v >= 25:   return discord.Color.orange()
    return discord.Color.red()

# ── Notifica usura ────────────────────────────────────────────────────────────
async def _notifica_usura(bot, user_id: str, item_name: str, usura: int):
    """Manda DM + log quando usura raggiunge una soglia."""
    if usura not in AVVISI_USURA:
        return

    tipo = _tipo_arma(item_name)
    if usura == 0:
        titolo = "💀 Arma Distrutta!"
        desc   = f"La tua arma **{item_name}** è completamente consumata ed è stata **rimossa** dalla bisaccia."
        color  = discord.Color.red()
    else:
        titolo = f"⚠️ Usura Arma — {usura}%"
        item_p = _item_pulizia(tipo)
        desc   = (
            f"La tua arma **{item_name}** ha raggiunto il **{usura}%** di usura.\n"
            f"Usa `/pulisci-arma` con **{item_p}** per ripristinarla."
        )
        color = _colore_usura(usura)

    embed = discord.Embed(title=titolo, description=desc, color=color, timestamp=discord.utils.utcnow())
    embed.add_field(name="🔫 Arma",  value=item_name,   inline=True)
    embed.add_field(name="⚙️ Usura", value=_barra(usura), inline=True)
    embed.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura")

    # DM
    try:
        user = await bot.fetch_user(int(user_id))
        if user:
            await user.send(embed=embed)
    except Exception:
        pass

    # Log
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch:
            log = discord.Embed(
                title=f"🔧 LOG USURA — {usura}%",
                color=color,
                timestamp=discord.utils.utcnow()
            )
            log.add_field(name="👤 Utente",  value=f"<@{user_id}>", inline=True)
            log.add_field(name="🔫 Arma",    value=item_name,        inline=True)
            log.add_field(name="⚙️ Usura",   value=f"{usura}%",      inline=True)
            await ch.send(embed=log)
    except Exception:
        pass

# ── Applica calo usura (usato da /dai-item) ───────────────────────────────────
async def applica_calo_passaggio(bot, user_id: str, item_name: str):
    """Riduce l'usura al passaggio. Se scende a 0 rimuove l'arma."""
    tipo = _tipo_arma(item_name)
    if not tipo:
        return
    usura_attuale = await get_usura(user_id, item_name)
    nuova         = max(0, usura_attuale - _calo_passaggio(tipo))
    await set_usura(user_id, item_name, nuova)
    await _notifica_usura(bot, user_id, item_name, nuova)
    if nuova == 0:
        await _rimuovi_arma_db(user_id, item_name)

async def _rimuovi_arma_db(user_id: str, item_name: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "DELETE FROM inventory WHERE user_id=? AND item_name=?",
            (user_id, item_name)
        )
        await db.commit()
    await delete_usura(user_id, item_name)

# ── Task 24h ──────────────────────────────────────────────────────────────────
async def task_usura_giornaliera(bot):
    """Loop ogni 24h: cala l'usura di tutte le armi di tutti gli utenti."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(86400)  # 24 ore
        print("🔧 Avvio calo usura giornaliero...", flush=True)
        try:
            # Prendo tutti gli utenti con armi in inventario
            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT DISTINCT user_id, item_name FROM inventory WHERE quantity>0"
                ) as c:
                    rows = await c.fetchall()

            for row in rows:
                uid   = row["user_id"]
                item  = row["item_name"]
                tipo  = _tipo_arma(item)
                if not tipo:
                    continue
                usura_attuale = await get_usura(uid, item)
                if usura_attuale <= 0:
                    continue
                nuova = max(0, usura_attuale - _calo_24h(tipo))
                await set_usura(uid, item, nuova)
                await _notifica_usura(bot, uid, item, nuova)
                if nuova == 0:
                    await _rimuovi_arma_db(uid, item)

            print("✅ Calo usura giornaliero completato.", flush=True)
        except Exception as e:
            print(f"❌ Errore task usura: {e}", flush=True)


# ── Setup comandi ─────────────────────────────────────────────────────────────
def setup_usura_commands(bot):

    # ── /pulisci-arma ─────────────────────────────────────────────────────────
    async def _ac_pulisci(interaction: discord.Interaction, current: str):
        uid   = str(interaction.user.id)
        armi  = await get_armi_inventario(uid)
        scelte = []
        for arma in armi:
            usura = await get_usura(uid, arma)
            if usura < 100:
                label = f"{arma} ({usura}%)"[:100]
                scelte.append(app_commands.Choice(name=label, value=arma))
        return [c for c in scelte if current.lower() in c.name.lower()][:25]

    @bot.tree.command(name="pulisci-arma", description="Pulisci un'arma dalla bisaccia per ripristinare l'usura")
    @app_commands.describe(arma="L'arma da pulire (solo quelle sotto 100%)")
    @app_commands.autocomplete(arma=_ac_pulisci)
    async def pulisci_arma(interaction: discord.Interaction, arma: str):
        uid  = str(interaction.user.id)
        tipo = _tipo_arma(arma)
        if not tipo:
            await interaction.response.send_message("❌ Quest'arma non è nel sistema usura.", ephemeral=True)
            return

        # Verifica che abbia l'arma
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?",
                (uid, arma)
            ) as c:
                row = await c.fetchone()
        if not row or row[0] < 1:
            await interaction.response.send_message(f"❌ Non hai **{arma}** nella bisaccia.", ephemeral=True)
            return

        # Verifica item pulizia
        item_p = _item_pulizia(tipo)
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?",
                (uid, item_p)
            ) as c:
                row_p = await c.fetchone()
        if not row_p or row_p[0] < 1:
            nome_item = "Olio per Armi" if tipo == "fuoco" else "Cote"
            await interaction.response.send_message(
                f"❌ Hai bisogno di **{item_p}** per pulire quest'arma.\n"
                f"Acquistalo dall'emporio.",
                ephemeral=True
            )
            return

        usura_vecchia = await get_usura(uid, arma)
        if usura_vecchia >= 100:
            await interaction.response.send_message(f"✅ **{arma}** è già al 100% di usura.", ephemeral=True)
            return

        # Consuma item pulizia
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute(
                "UPDATE inventory SET quantity=quantity-1 WHERE user_id=? AND item_name=?",
                (uid, item_p)
            )
            await db.commit()

        # Ripristina usura
        await set_usura(uid, arma, 100)

        embed = discord.Embed(
            title="🔧 𝐀𝐫𝐦𝐚 𝐏𝐮𝐥𝐢𝐭𝐚",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🔫 Arma",         value=arma,              inline=False)
        embed.add_field(name="⚙️ Usura prima",  value=_barra(usura_vecchia), inline=True)
        embed.add_field(name="✅ Usura dopo",   value=_barra(100),       inline=True)
        embed.add_field(name="🧴 Usato",        value=item_p,            inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura")
        await interaction.response.send_message(embed=embed)

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="🔧 LOG — Arma Pulita", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Utente", value=interaction.user.mention, inline=True)
                log.add_field(name="🔫 Arma",   value=arma,                     inline=True)
                log.add_field(name="📈 Usura",  value=f"{usura_vecchia}% → 100%", inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /visualizza-stato-arma ────────────────────────────────────────────────
    @bot.tree.command(name="visualizza-stato-arma", description="Visualizza l'usura delle tue armi")
    async def visualizza_stato_arma(interaction: discord.Interaction):
        uid  = str(interaction.user.id)
        armi = await get_armi_inventario(uid)

        if not armi:
            await interaction.response.send_message(
                "❌ Non hai armi nella bisaccia.", ephemeral=True
            )
            return

        # Costruisce le opzioni del menu
        options = []
        for arma in armi[:25]:
            usura = await get_usura(uid, arma)
            label = f"{arma} — {usura}%"[:100]
            options.append(discord.SelectOption(label=label, value=arma))

        class ArmaSelect(discord.ui.Select):
            def __init__(self_s):
                super().__init__(
                    placeholder="Seleziona un'arma...",
                    options=options,
                    min_values=1,
                    max_values=1
                )

            async def callback(self_s, itr: discord.Interaction):
                arma_sel = self_s.values[0]
                tipo_sel = _tipo_arma(arma_sel)
                usura    = await get_usura(uid, arma_sel)
                item_p   = _item_pulizia(tipo_sel) if tipo_sel else "—"
                calo_g   = _calo_24h(tipo_sel) if tipo_sel else 0
                calo_p   = _calo_passaggio(tipo_sel) if tipo_sel else 0

                embed = discord.Embed(
                    title="🔫 𝐒𝐭𝐚𝐭𝐨 𝐀𝐫𝐦𝐚",
                    color=_colore_usura(usura),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_author(name=itr.user.display_name, icon_url=itr.user.display_avatar.url)
                embed.add_field(name="🔫 Arma",           value=arma_sel,          inline=False)
                embed.add_field(name="⚙️ Usura",          value=_barra(usura),     inline=False)
                embed.add_field(name="📉 Calo ogni 24h",  value=f"-{calo_g}%",     inline=True)
                embed.add_field(name="🤝 Calo passaggio", value=f"-{calo_p}%",     inline=True)
                embed.add_field(name="🧴 Per pulire",     value=item_p,            inline=True)
                if usura <= 25:
                    embed.add_field(
                        name="⚠️ Avviso",
                        value="Questa arma è in cattive condizioni! Puliscila presto.",
                        inline=False
                    )
                embed.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura")
                await itr.response.edit_message(embed=embed, view=ArmaView())

        class ArmaView(discord.ui.View):
            def __init__(self_v):
                super().__init__(timeout=120)
                self_v.add_item(ArmaSelect())

        embed_ini = discord.Embed(
            title="🔫 𝐒𝐭𝐚𝐭𝐨 𝐀𝐫𝐦𝐢",
            description="Seleziona un'arma dal menu per vedere l'usura dettagliata.",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed_ini.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        # Anteprima rapida di tutte le armi
        righe = []
        for arma in armi[:25]:
            usura = await get_usura(uid, arma)
            righe.append(f"{arma} — {_barra(usura)}")
        embed_ini.add_field(name="📋 Le tue armi", value="\n".join(righe), inline=False)
        embed_ini.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura")

        await interaction.response.send_message(embed=embed_ini, view=ArmaView(), ephemeral=True)
