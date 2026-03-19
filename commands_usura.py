import discord
from discord import app_commands
import aiosqlite
import asyncio
from constants import LOG_CHANNEL_ID, DATABASE_NAME

# ── Costanti ──────────────────────────────────────────────────────────────────
OLIO_ITEM    = "<:OlioArmi:1483872658574544988> • Olio per Armi"
COTE_ITEM    = "<:Cote:1483873630986174484> • Cote"
AVVISI_USURA = {75, 50, 25, 10, 5, 0}

# ── Armi da FUOCO (-5%/24h, -2% per passaggio) ───────────────────────────────
ARMI_FUOCO = {
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
    "<:Volcanic:1457650683837677653> • Pistola Volcanic",
    "<:Volcanic:1457650683837677653> • Pistola Volcanic (M.N.)",
    "<:DoppiettaaCanneMozze:1457657137533550685> • Fucile a Canne Mozze Lisce",
    "<:DoppiettaaCanneMozze:1457657137533550685> • Fucile a Canne Mozze Lisce (M.N.)",
    "<:Doppietta:1457655998562041947> • Doppietta a Canne Lisce",
    "<:Doppietta:1457655998562041947> • Doppietta a Canne Lisce (M.N.)",
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia a Pompa",
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia a Pompa (M.N.)",
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia Semiautomatico",
    "<:Doppietta:1457655998562041947> • Fucile a Canna Liscia Semiautomatico (M.N.)",
    "<:Litchfield:1457518211716087961> • Carabina a Ripetizione",
    "<:Litchfield:1457518211716087961> • Carabina a Ripetizione (M.N.)",
    "<:Litchfield:1457518211716087961> • Lancaster a Ripetizione",
    "<:Litchfield:1457518211716087961> • Lancaster a Ripetizione (M.N.)",
    "<:Springfield:1457642354717622362> • Varmint a Canna Rigata",
    "<:Springfield:1457642354717622362> • Varmint a Canna Rigata (M.N.)",
    "<:Springfield:1457642354717622362> • Springfield a Canna Rigata",
    "<:Springfield:1457642354717622362> • Springfield a Canna Rigata (M.N.)",
    "<:Springfield:1457642354717622362> • Bolt-Action a Canna Rigata",
    "<:Springfield:1457642354717622362> • Bolt-Action a Canna Rigata (M.N.)",
}

# ── Armi da MISCHIA (-2%/24h, -1% per passaggio) — lazo ESCLUSO ──────────────
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
}

ALL_ARMI = ARMI_FUOCO | ARMI_MISCHIA

# ── Helper tipo/calo ──────────────────────────────────────────────────────────
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

def _barra(v: int) -> str:
    piena = round(v / 10)
    if v >= 75:   blocco = "🟩"
    elif v >= 50: blocco = "🟨"
    elif v >= 25: blocco = "🟧"
    else:         blocco = "🟥"
    return blocco * piena + "⬛" * (10 - piena) + f"  **{v}%**"

def _colore_usura(v: int) -> discord.Color:
    if v >= 75:   return discord.Color.green()
    if v >= 50:   return discord.Color.yellow()
    if v >= 25:   return discord.Color.orange()
    return discord.Color.red()

# ── DB helpers ────────────────────────────────────────────────────────────────
async def init_usura_table():
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

async def get_armi_inventario(user_id: str) -> list[str]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_name FROM inventory WHERE user_id=? AND quantity>0",
            (user_id,)
        ) as c:
            rows = await c.fetchall()
    return [r["item_name"] for r in rows if r["item_name"] in ALL_ARMI]

async def get_armi_con_usura(user_id: str) -> list[dict]:
    """Carica armi + usura in una sola passata per evitare N query separate."""
    armi = await get_armi_inventario(user_id)
    if not armi:
        return []
    placeholders = ",".join("?" for _ in armi)
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT item_name, usura FROM weapon_durability WHERE user_id=? AND item_name IN ({placeholders})",
            (user_id, *armi)
        ) as c:
            rows = await c.fetchall()
    usura_map = {r["item_name"]: r["usura"] for r in rows}
    return [{"item_name": a, "usura": usura_map.get(a, 100)} for a in armi]

# ── Notifica usura ────────────────────────────────────────────────────────────
async def _notifica_usura(bot, user_id: str, item_name: str, usura: int):
    if usura not in AVVISI_USURA:
        return
    tipo = _tipo_arma(item_name)
    if usura == 0:
        titolo = "💀 Arma Distrutta!"
        desc   = f"La tua arma **{item_name}** è completamente consumata ed è stata **rimossa** dalla bisaccia."
        color  = discord.Color.red()
    else:
        titolo = f"⚠️ Usura Arma — {usura}%"
        desc   = (
            f"La tua arma **{item_name}** ha raggiunto il **{usura}%** di usura.\n"
            f"Usa `/pulisci-arma` con **{_item_pulizia(tipo)}** per ripristinarla."
        )
        color = _colore_usura(usura)

    embed = discord.Embed(title=titolo, description=desc, color=color, timestamp=discord.utils.utcnow())
    embed.add_field(name="🔫 Arma",  value=item_name,     inline=True)
    embed.add_field(name="⚙️ Usura", value=_barra(usura), inline=True)
    embed.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura")

    try:
        user = await bot.fetch_user(int(user_id))
        if user:
            await user.send(embed=embed)
    except Exception:
        pass
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch:
            log = discord.Embed(title=f"🔧 LOG USURA — {usura}%", color=color, timestamp=discord.utils.utcnow())
            log.add_field(name="👤 Utente", value=f"<@{user_id}>", inline=True)
            log.add_field(name="🔫 Arma",   value=item_name,        inline=True)
            log.add_field(name="⚙️ Usura",  value=f"{usura}%",      inline=True)
            await ch.send(embed=log)
    except Exception:
        pass

async def _rimuovi_arma_db(user_id: str, item_name: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "DELETE FROM inventory WHERE user_id=? AND item_name=?",
            (user_id, item_name)
        )
        await db.commit()
    await delete_usura(user_id, item_name)

# ── Calo al passaggio (chiamato da /dai-item) ─────────────────────────────────
async def applica_calo_passaggio(bot, user_id: str, item_name: str):
    tipo = _tipo_arma(item_name)
    if not tipo:
        return
    usura_attuale = await get_usura(user_id, item_name)
    nuova         = max(0, usura_attuale - _calo_passaggio(tipo))
    await set_usura(user_id, item_name, nuova)
    await _notifica_usura(bot, user_id, item_name, nuova)
    if nuova == 0:
        await _rimuovi_arma_db(user_id, item_name)

# ── Task 24h ──────────────────────────────────────────────────────────────────
async def task_usura_giornaliera(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(86400)
        print("🔧 Avvio calo usura giornaliero...", flush=True)
        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT DISTINCT user_id, item_name FROM inventory WHERE quantity>0"
                ) as c:
                    rows = await c.fetchall()

            for row in rows:
                uid  = row["user_id"]
                item = row["item_name"]
                tipo = _tipo_arma(item)
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
        uid  = str(interaction.user.id)
        armi = await get_armi_con_usura(uid)
        scelte = []
        for a in armi:
            if a["usura"] < 100:
                label = f"{a['item_name']} ({a['usura']}%)"[:100]
                scelte.append(app_commands.Choice(name=label, value=a["item_name"]))
        return [c for c in scelte if current.lower() in c.name.lower()][:25]

    @bot.tree.command(name="pulisci-arma", description="Pulisci un'arma dalla bisaccia per ripristinare l'usura")
    @app_commands.describe(arma="L'arma da pulire")
    @app_commands.autocomplete(arma=_ac_pulisci)
    async def pulisci_arma(interaction: discord.Interaction, arma: str):
        await interaction.response.defer(ephemeral=True)
        uid  = str(interaction.user.id)
        tipo = _tipo_arma(arma)

        if not tipo:
            await interaction.followup.send("❌ Quest'arma non è nel sistema usura.", ephemeral=True)
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?",
                (uid, arma)
            ) as c:
                row = await c.fetchone()
        if not row or row[0] < 1:
            await interaction.followup.send(f"❌ Non hai **{arma}** nella bisaccia.", ephemeral=True)
            return

        usura_attuale = await get_usura(uid, arma)
        if usura_attuale >= 100:
            await interaction.followup.send(f"✅ **{arma}** è già al 100% di usura.", ephemeral=True)
            return

        item_p = _item_pulizia(tipo)
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?",
                (uid, item_p)
            ) as c:
                row_p = await c.fetchone()
        if not row_p or row_p[0] < 1:
            await interaction.followup.send(
                f"❌ Hai bisogno di **{item_p}** per pulire quest'arma.\nAcquistalo dall'emporio.",
                ephemeral=True
            )
            return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute(
                "UPDATE inventory SET quantity=quantity-1 WHERE user_id=? AND item_name=?",
                (uid, item_p)
            )
            await db.commit()
        await set_usura(uid, arma, 100)

        embed = discord.Embed(
            title="🔧 𝐀𝐫𝐦𝐚 𝐏𝐮𝐥𝐢𝐭𝐚",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🔫 Arma",       value=arma,                  inline=False)
        embed.add_field(name="⚙️ Prima",      value=_barra(usura_attuale), inline=True)
        embed.add_field(name="✅ Dopo",       value=_barra(100),            inline=True)
        embed.add_field(name="🧴 Utilizzato", value=item_p,                inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura")
        await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="🔧 LOG — Arma Pulita", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Utente", value=interaction.user.mention,    inline=True)
                log.add_field(name="🔫 Arma",   value=arma,                        inline=True)
                log.add_field(name="📈 Usura",  value=f"{usura_attuale}% → 100%",  inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /visualizza-stato-arma ────────────────────────────────────────────────
    @bot.tree.command(name="visualizza-stato-arma", description="Visualizza l'usura delle tue armi")
    async def visualizza_stato_arma(interaction: discord.Interaction):
        print(f"[vis-arma] START uid={interaction.user.id}", flush=True)
        uid = str(interaction.user.id)

        try:
            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS weapon_durability (
                        user_id TEXT NOT NULL, item_name TEXT NOT NULL,
                        usura INTEGER DEFAULT 100, PRIMARY KEY (user_id, item_name)
                    )
                """)
                await db.commit()
                async with db.execute(
                    "SELECT item_name FROM inventory WHERE user_id=? AND quantity>0",
                    (uid,)
                ) as c:
                    inv_rows = await c.fetchall()
                armi_nomi = [r["item_name"] for r in inv_rows if r["item_name"] in ALL_ARMI]
                usura_map = {}
                if armi_nomi:
                    ph = ",".join("?" for _ in armi_nomi)
                    async with db.execute(
                        f"SELECT item_name, usura FROM weapon_durability WHERE user_id=? AND item_name IN ({ph})",
                        (uid, *armi_nomi)
                    ) as c2:
                        for r in await c2.fetchall():
                            usura_map[r["item_name"]] = r["usura"]
            print(f"[vis-arma] query ok, armi={len(armi_nomi)}", flush=True)
        except Exception as e:
            print(f"[vis-arma] ERRORE query: {e}", flush=True)
            await interaction.response.send_message("❌ Errore interno. Riprova.", ephemeral=True)
            return

        armi_usura = [
            {"item_name": a, "usura": usura_map.get(a, 100)}
            for a in armi_nomi
        ]
        print(f"[vis-arma] armi trovate={len(armi_usura)}", flush=True)

        if not armi_usura:
            await interaction.response.send_message(
                "❌ Non hai armi nella bisaccia.", ephemeral=True
            )
            return

        # Tutto pronto — risposta immediata con pulsanti
        PER_PAG = 5
        tot_pag = max(1, -(-len(armi_usura) // PER_PAG))

        def _build_embed(pagina: int) -> discord.Embed:
            embed = discord.Embed(
                title="🔫 𝐒𝐭𝐚𝐭𝐨 𝐀𝐫𝐦𝐢",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            slice_ = armi_usura[pagina * PER_PAG:(pagina + 1) * PER_PAG]
            for a in slice_:
                tipo = _tipo_arma(a["item_name"])
                calo_g = _calo_24h(tipo) if tipo else 0
                calo_p = _calo_passaggio(tipo) if tipo else 0
                puliz  = _item_pulizia(tipo) if tipo else "—"
                avviso = " ⚠️" if a["usura"] <= 25 else ""
                embed.add_field(
                    name=f"{a['item_name']}{avviso}",
                    value=(
                        f"{_barra(a['usura'])}\n"
                        f"📉 -{calo_g}%/giorno  🤝 -{calo_p}% passaggio  🧴 {puliz}"
                    ),
                    inline=False
                )
            embed.set_footer(text=f"🤠 Red Dead Redemption II — Usura | Pagina {pagina+1}/{tot_pag}")
            return embed

        class UsuraView(discord.ui.View):
            def __init__(self_v, p: int = 0):
                super().__init__(timeout=120)
                self_v.p = p
                self_v._aggiorna()

            def _aggiorna(self_v):
                self_v.prev_btn.disabled = self_v.p == 0
                self_v.next_btn.disabled = self_v.p >= tot_pag - 1

            @discord.ui.button(label="⬅️", style=discord.ButtonStyle.primary)
            async def prev_btn(self_v, itr: discord.Interaction, btn):
                self_v.p -= 1
                self_v._aggiorna()
                await itr.response.edit_message(embed=_build_embed(self_v.p), view=self_v)

            @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary)
            async def next_btn(self_v, itr: discord.Interaction, btn):
                self_v.p += 1
                self_v._aggiorna()
                await itr.response.edit_message(embed=_build_embed(self_v.p), view=self_v)

        view = UsuraView(0) if tot_pag > 1 else discord.ui.View(timeout=120)
        print(f"[vis-arma] invio risposta pag 1/{tot_pag}", flush=True)
        await interaction.response.send_message(
            embed=_build_embed(0),
            view=view,
            ephemeral=True
        )
        print(f"[vis-arma] DONE", flush=True)
