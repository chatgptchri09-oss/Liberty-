import discord
from discord import app_commands
import aiosqlite
import asyncio
import time
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

# ── Armi da MISCHIA (-2%/24h, -1% per passaggio) ─────────────────────────────
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


# ── Helper ────────────────────────────────────────────────────────────────────
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
async def _ensure_tables():
    """Crea le tabelle se non esistono, inclusa last_decay_ts."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weapon_durability (
                user_id   TEXT NOT NULL,
                item_name TEXT NOT NULL,
                usura     INTEGER DEFAULT 100,
                last_decay_ts REAL DEFAULT 0,
                PRIMARY KEY (user_id, item_name)
            )
        """)
        # Upgrade sicuro: aggiunge last_decay_ts se la tabella esisteva già
        try:
            await db.execute("ALTER TABLE weapon_durability ADD COLUMN last_decay_ts REAL DEFAULT 0")
        except Exception:
            pass
        await db.commit()

async def get_usura(user_id: str, item_name: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT usura FROM weapon_durability WHERE user_id=? AND item_name=?",
            (user_id, item_name)
        ) as c:
            row = await c.fetchone()
            return row[0] if row else 100

async def set_usura(user_id: str, item_name: str, valore: int, update_ts: bool = False):
    """Salva l'usura. Se update_ts=True aggiorna anche last_decay_ts al momento attuale."""
    v  = max(0, min(100, valore))
    ts = time.time() if update_ts else None
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if ts is not None:
            await db.execute("""
                INSERT INTO weapon_durability (user_id, item_name, usura, last_decay_ts)
                VALUES (?,?,?,?)
                ON CONFLICT(user_id, item_name) DO UPDATE SET usura=excluded.usura, last_decay_ts=excluded.last_decay_ts
            """, (user_id, item_name, v, ts))
        else:
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

async def get_armi_inventario(user_id: str) -> list[dict]:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT item_name, quantity FROM inventory WHERE user_id=? AND quantity>0",
            (user_id,)
        ) as c:
            rows = await c.fetchall()
    return [{"item_name": r["item_name"], "quantity": r["quantity"]}
            for r in rows if r["item_name"] in ALL_ARMI]

async def get_armi_con_usura(user_id: str) -> list[dict]:
    armi_inv = await get_armi_inventario(user_id)
    if not armi_inv:
        return []
    nomi = [a["item_name"] for a in armi_inv]
    ph   = ",".join("?" for _ in nomi)
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT item_name, usura FROM weapon_durability WHERE user_id=? AND item_name IN ({ph})",
            (user_id, *nomi)
        ) as c:
            rows = await c.fetchall()
    usura_map = {r["item_name"]: r["usura"] for r in rows}
    result = []
    for a in armi_inv:
        nome = a["item_name"]
        qty  = a["quantity"]
        usura_base = usura_map.get(nome, 100)
        if qty == 1:
            result.append({"item_name": nome, "usura": usura_base, "slot": None})
        else:
            for i in range(qty):
                result.append({"item_name": nome, "usura": usura_base, "slot": i + 1})
    return result


# ── Notifica DM usura — GARANTITA ────────────────────────────────────────────
async def _notifica_usura(bot, user_id: str, item_name: str, usura: int):
    """Invia sempre il DM all'utente. Logga l'esito nel canale log."""
    if usura not in AVVISI_USURA:
        return

    tipo = _tipo_arma(item_name)

    if usura == 0:
        titolo = "💀 Arma Distrutta!"
        desc   = (
            f"La tua arma **{item_name}** è completamente consumata ed è stata "
            f"**rimossa automaticamente** dalla tua bisaccia.\n\n"
            f"Acquistane una nuova dall'emporio."
        )
        color = discord.Color.red()
    else:
        titolo = f"⚠️ Usura Arma — {usura}%"
        desc   = (
            f"La tua arma **{item_name}** ha raggiunto il **{usura}%** di usura.\n\n"
            f"Usa `/pulisci-arma` con **{_item_pulizia(tipo)}** per ripristinarla prima che si rompa!"
        )
        color = _colore_usura(usura)

    embed_dm = discord.Embed(
        title=titolo,
        description=desc,
        color=color,
        timestamp=discord.utils.utcnow()
    )
    embed_dm.add_field(name="🔫 Arma",  value=item_name,     inline=True)
    embed_dm.add_field(name="⚙️ Usura", value=_barra(usura), inline=True)
    if usura <= 25 and usura > 0:
        embed_dm.add_field(
            name="🚨 Attenzione",
            value="L'arma è in condizioni critiche! Puliscila subito.",
            inline=False
        )
    embed_dm.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura Armi")

    # ── DM all'utente — tentiamo più volte ───────────────────────────────────
    dm_inviato = False
    for tentativo in range(3):
        try:
            user = await bot.fetch_user(int(user_id))
            if user:
                await user.send(embed=embed_dm)
                dm_inviato = True
                break
        except discord.Forbidden:
            # L'utente ha i DM chiusi — non possiamo fare nulla
            break
        except Exception:
            await asyncio.sleep(1)

    # ── Log nel canale ────────────────────────────────────────────────────────
    try:
        ch = bot.get_channel(LOG_CHANNEL_ID)
        if ch:
            log = discord.Embed(
                title=f"🔧 LOG USURA — {usura}%",
                color=color,
                timestamp=discord.utils.utcnow()
            )
            log.add_field(name="👤 Utente",   value=f"<@{user_id}>",                       inline=True)
            log.add_field(name="🔫 Arma",     value=item_name,                              inline=True)
            log.add_field(name="⚙️ Usura",    value=f"{usura}%",                            inline=True)
            log.add_field(name="📨 DM",       value="✅ Inviato" if dm_inviato else "❌ Fallito (DM chiusi)", inline=True)
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


# ── Task 24h — resistente ai riavvii ─────────────────────────────────────────
async def task_usura_giornaliera(bot):
    """
    Ogni ora controlla tutte le armi nel database.
    Per ogni arma calcola quante giornate (24h) sono passate dall'ultimo decay
    e applica i cali arretrati. Così funziona anche dopo riavvii di Render.
    """
    await _ensure_tables()
    await bot.wait_until_ready()
    print("🔧 Task usura avviato (controllo ogni ora)", flush=True)

    while not bot.is_closed():
        await asyncio.sleep(3600)  # controlla ogni ora
        now_ts = time.time()
        print("🔧 Controllo usura armi...", flush=True)

        try:
            # Leggi tutte le righe usura con il loro timestamp
            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT user_id, item_name, usura, last_decay_ts FROM weapon_durability WHERE usura > 0"
                ) as c:
                    rows = await c.fetchall()

            for row in rows:
                uid       = row["user_id"]
                item      = row["item_name"]
                usura_cur = row["usura"]
                last_ts   = row["last_decay_ts"] or 0

                tipo = _tipo_arma(item)
                if not tipo:
                    continue

                # Verifica che l'arma sia ancora nell'inventario
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    async with db.execute(
                        "SELECT quantity FROM inventory WHERE user_id=? AND item_name=? AND quantity>0",
                        (uid, item)
                    ) as c:
                        inv_row = await c.fetchone()
                if not inv_row:
                    continue

                # Quante giornate complete sono passate dall'ultimo decay?
                secondi_passati = now_ts - last_ts
                giorni_passati  = int(secondi_passati // 86400)

                if giorni_passati < 1:
                    continue  # Non è ancora passato un giorno

                calo_totale = _calo_24h(tipo) * giorni_passati
                nuova_usura = max(0, usura_cur - calo_totale)

                await set_usura(uid, item, nuova_usura, update_ts=True)

                # Notifica per ogni soglia attraversata
                for soglia in sorted(AVVISI_USURA, reverse=True):
                    if usura_cur > soglia >= nuova_usura:
                        await _notifica_usura(bot, uid, item, soglia)

                if nuova_usura == 0:
                    await _rimuovi_arma_db(uid, item)

            print("✅ Controllo usura completato.", flush=True)
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
                slot_label = f" #{a['slot']}" if a.get("slot") else ""
                label = f"{a['item_name']}{slot_label} ({a['usura']}%)"[:100]
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
            await interaction.followup.send("❌ Quest'arma non è nel sistema usura.", ephemeral=True); return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?", (uid, arma)
            ) as c:
                row = await c.fetchone()
        if not row or row[0] < 1:
            await interaction.followup.send(f"❌ Non hai **{arma}** nella bisaccia.", ephemeral=True); return

        usura_attuale = await get_usura(uid, arma)
        if usura_attuale >= 100:
            await interaction.followup.send(f"✅ **{arma}** è già al 100% di usura.", ephemeral=True); return

        item_p = _item_pulizia(tipo)
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(
                "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?", (uid, item_p)
            ) as c:
                row_p = await c.fetchone()
        if not row_p or row_p[0] < 1:
            await interaction.followup.send(
                f"❌ Hai bisogno di **{item_p}** per pulire quest'arma.\nAcquistalo dall'emporio.",
                ephemeral=True
            ); return

        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute(
                "UPDATE inventory SET quantity=quantity-1 WHERE user_id=? AND item_name=?", (uid, item_p)
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
        embed.add_field(name="✅ Dopo",        value=_barra(100),           inline=True)
        embed.add_field(name="🧴 Utilizzato", value=item_p,                inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sistema Usura")
        await interaction.followup.send(embed=embed, ephemeral=True)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="🔧 LOG — Arma Pulita", color=discord.Color.green(), timestamp=discord.utils.utcnow())
                log.add_field(name="👤 Utente", value=interaction.user.mention,   inline=True)
                log.add_field(name="🔫 Arma",   value=arma,                       inline=True)
                log.add_field(name="📈 Usura",  value=f"{usura_attuale}% → 100%", inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /visualizza-stato-arma ────────────────────────────────────────────────
    @bot.tree.command(name="visualizza-stato-arma", description="Visualizza l'usura delle tue armi")
    async def visualizza_stato_arma(interaction: discord.Interaction):
        uid = str(interaction.user.id)

        try:
            await _ensure_tables()
            async with aiosqlite.connect(DATABASE_NAME) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT item_name FROM inventory WHERE user_id=? AND quantity>0", (uid,)
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
        except Exception as e:
            print(f"[vis-arma] ERRORE: {e}", flush=True)
            await interaction.response.send_message("❌ Errore interno. Riprova.", ephemeral=True); return

        if not armi_nomi:
            await interaction.response.send_message("❌ Non hai armi nella bisaccia.", ephemeral=True); return

        armi_usura = []
        for nome in armi_nomi:
            async with aiosqlite.connect(DATABASE_NAME) as db2:
                db2.row_factory = aiosqlite.Row
                async with db2.execute(
                    "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?", (uid, nome)
                ) as c3:
                    row_q = await c3.fetchone()
            qty       = row_q["quantity"] if row_q else 1
            usura_val = usura_map.get(nome, 100)
            if qty == 1:
                armi_usura.append({"item_name": nome, "usura": usura_val, "slot": None})
            else:
                for i in range(qty):
                    armi_usura.append({"item_name": nome, "usura": usura_val, "slot": i + 1})

        PER_PAG = 5
        tot_pag = max(1, -(-len(armi_usura) // PER_PAG))

        def _build_embed(pagina: int) -> discord.Embed:
            embed = discord.Embed(
                title="🔫 𝐒𝐭𝐚𝐭𝐨 𝐀𝐫𝐦𝐢",
                color=discord.Color(0x8B4513),
                timestamp=discord.utils.utcnow()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            for a in armi_usura[pagina * PER_PAG:(pagina + 1) * PER_PAG]:
                tipo   = _tipo_arma(a["item_name"])
                calo_g = _calo_24h(tipo) if tipo else 0
                calo_p = _calo_passaggio(tipo) if tipo else 0
                puliz  = _item_pulizia(tipo) if tipo else "—"
                avviso = " ⚠️" if a["usura"] <= 25 else ""
                slot_label = f" #{a['slot']}" if a.get("slot") else ""
                embed.add_field(
                    name=f"{a['item_name']}{slot_label}{avviso}",
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
                self_v.p -= 1; self_v._aggiorna()
                await itr.response.edit_message(embed=_build_embed(self_v.p), view=self_v)

            @discord.ui.button(label="➡️", style=discord.ButtonStyle.primary)
            async def next_btn(self_v, itr: discord.Interaction, btn):
                self_v.p += 1; self_v._aggiorna()
                await itr.response.edit_message(embed=_build_embed(self_v.p), view=self_v)

        view = UsuraView(0) if tot_pag > 1 else discord.ui.View(timeout=120)
        await interaction.response.send_message(embed=_build_embed(0), view=view, ephemeral=True)
