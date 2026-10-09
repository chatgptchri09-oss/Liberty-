import discord
from discord import app_commands
import asyncio
import random
import time
import aiosqlite
import database
from constants import LOG_CHANNEL_ID, DATABASE_NAME, STAFF_ROLE_ID

# ══════════════════════════════════════════════════════════════════════════════
#  CERCATORE D'ORO — /cerca-oro  e  /fondi-pepite
# ══════════════════════════════════════════════════════════════════════════════

# ⚠️ ID del ruolo "Cercatore d'Oro" — placeholder, da inserire.
# Finché è 0 i comandi sono utilizzabili SOLO dallo Staff (per poter testare).
ORO_ROLE_ID = 1558078970602455190

# ⚠️ Nomi esatti degli item in bisaccia. Se nell'emporio/DB esistono già item
# con nomi diversi per pepite e lingotti, cambia queste due costanti.
PEPITA_NAME   = "🪙 • Pepita d'Oro"
LINGOTTO_NAME = "🥇 • Lingotto d'Oro"

# ── Regole /cerca-oro ─────────────────────────────────────────────────────────
COOLDOWN_CERCA_S = 120      # 1 ricerca ogni 2 minuti
ROLL_MIN         = 0        # pepite per ricerca: da 0 ...
ROLL_MAX         = 10       # ... a 10
LIMITE_PEPITE    = 100      # limite di raccolta (100 pepite = 100 gr)
BLOCCO_S         = 3600     # 1 ora di blocco, parte da quando si raggiungono le 100

# ── Regole /fondi-pepite ──────────────────────────────────────────────────────
PEPITE_PER_LINGOTTO    = 100   # minimo e costo di 1 lingotto
FUSIONE_S_PER_LINGOTTO = 600   # 10 minuti a lingotto
LINGOTTO_VALORE        = 200   # $ — SOLO informativo, non usato dal codice

COLOR_ATTESA = 0x8B6B3D
COLOR_STOP   = 0xB22222
COLOR_FORNACE = 0xE25822
COLOR_FUSO   = 0xFFD700

_locks: dict = {}
def _lock(uid: str) -> asyncio.Lock:
    return _locks.setdefault(uid, asyncio.Lock())


# ══════════════════════════════════════════════════════════════════════════════
#  Permessi
# ══════════════════════════════════════════════════════════════════════════════
def _autorizzato(member) -> bool:
    if not isinstance(member, discord.Member):
        return False
    ids = {r.id for r in member.roles}
    if STAFF_ROLE_ID in ids:
        return True
    return ORO_ROLE_ID != 0 and ORO_ROLE_ID in ids


def _msg_non_autorizzato() -> str:
    if ORO_ROLE_ID == 0:
        return "⚠️ Il ruolo **Cercatore d'Oro** non è ancora stato configurato. Per ora il comando è riservato allo Staff."
    return f"❌ Solo chi ha il ruolo <@&{ORO_ROLE_ID}> può usare questo comando."


# ══════════════════════════════════════════════════════════════════════════════
#  DB
# ══════════════════════════════════════════════════════════════════════════════
async def _ensure_tables(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS oro_ricerche (
            user_id     TEXT PRIMARY KEY,
            raccolte    INTEGER DEFAULT 0,
            ultimo_ts   REAL DEFAULT 0,
            blocco_fino REAL DEFAULT 0
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS oro_fusioni (
            user_id    TEXT PRIMARY KEY,
            lingotti   INTEGER,
            inizio_ts  REAL,
            fine_ts    REAL,
            channel_id TEXT
        )
    """)


async def _get_fusione(uid: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM oro_fusioni WHERE user_id=?", (uid,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
#  Helper grafici
# ══════════════════════════════════════════════════════════════════════════════
def _bar(v: int, tot: int, n: int = 10) -> str:
    f = round(max(0, min(tot, v)) / tot * n) if tot else 0
    return "▰" * f + "▱" * (n - f)


def _fuoco_bar(prog: float, n: int = 12) -> str:
    f = round(max(0.0, min(1.0, prog)) * n)
    return "🟧" * f + "⬛" * (n - f)


def _tier(tirato: int):
    if tirato == 0:
        return ("🪨 𝐍𝐞𝐬𝐬𝐮𝐧𝐚 𝐏𝐞𝐩𝐢𝐭𝐚", 0x6B4F3A, [
            "Il setaccio resta vuoto: solo sabbia, fango e un po' di delusione.",
            "Niente da fare, il fiume oggi non ti regala nulla.",
            "Hai setacciato per niente... solo sassi e acqua gelida.",
        ])
    if tirato <= 3:
        return ("✨ 𝐐𝐮𝐚𝐥𝐜𝐡𝐞 𝐏𝐞𝐩𝐢𝐭𝐚", 0xCD853F, [
            "Un luccichio tra la ghiaia: qualche pepita finisce nel setaccio.",
            "Il fiume è generoso quel tanto che basta: poche pepite, ma sono tue.",
        ])
    if tirato <= 7:
        return ("💰 𝐁𝐞𝐥 𝐁𝐨𝐭𝐭𝐢𝐧𝐨", 0xDAA520, [
            "Il setaccio brilla al sole! Una bella manciata di pepite!",
            "Il fiume stavolta ti sorride: un bel bottino luccicante.",
        ])
    return ("🌟 𝐅𝐈𝐋𝐎𝐍𝐄 𝐃'𝐎𝐑𝐎!", 0xFFD700, [
        "FILONE! Il setaccio è carico d'oro, non credi ai tuoi occhi!",
        "Il tuo setaccio trabocca: pepite ovunque, è il tuo giorno fortunato!",
    ])


# ══════════════════════════════════════════════════════════════════════════════
#  /cerca-oro — logica
# ══════════════════════════════════════════════════════════════════════════════
async def _tenta_ricerca(uid: str) -> dict:
    async with _lock(uid):
        now = time.time()
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await _ensure_tables(db)
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM oro_ricerche WHERE user_id=?", (uid,)) as c:
                row = await c.fetchone()
            raccolte    = row["raccolte"] if row else 0
            ultimo_ts   = row["ultimo_ts"] if row else 0
            blocco_fino = row["blocco_fino"] if row else 0

            # Blocco orario ancora attivo
            if blocco_fino > now:
                return {"ok": False, "motivo": "limite", "until": blocco_fino}

            # Blocco scaduto → nuovo ciclo di raccolta
            if blocco_fino > 0:
                raccolte, blocco_fino = 0, 0

            # Cooldown di 2 minuti
            if now - ultimo_ts < COOLDOWN_CERCA_S:
                return {"ok": False, "motivo": "cooldown", "until": ultimo_ts + COOLDOWN_CERCA_S}

            tirato  = random.randint(ROLL_MIN, ROLL_MAX)
            trovate = min(tirato, LIMITE_PEPITE - raccolte)
            raccolte += trovate
            limite_raggiunto = raccolte >= LIMITE_PEPITE
            if limite_raggiunto:
                blocco_fino = now + BLOCCO_S

            await db.execute("""
                INSERT INTO oro_ricerche (user_id, raccolte, ultimo_ts, blocco_fino)
                VALUES (?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    raccolte=excluded.raccolte, ultimo_ts=excluded.ultimo_ts,
                    blocco_fino=excluded.blocco_fino
            """, (uid, raccolte, now, blocco_fino))
            await db.commit()

        if trovate > 0:
            await database.add_item(uid, PEPITA_NAME, trovate)
        totale = await database.get_item_quantity(uid, PEPITA_NAME)

        return {
            "ok": True, "tirato": tirato, "trovate": trovate, "ciclo": raccolte,
            "limite_raggiunto": limite_raggiunto, "sblocco": blocco_fino,
            "next": now + COOLDOWN_CERCA_S, "totale": totale,
        }


def _embed_attesa(user) -> discord.Embed:
    e = discord.Embed(
        title="⛏️ 𝐒𝐞𝐭𝐚𝐜𝐜𝐢𝐚𝐧𝐝𝐨 𝐢𝐥 𝐟𝐢𝐮𝐦𝐞...",
        description=f"*{user.display_name} immerge il setaccio nell'acqua gelida e lo scuote piano...*",
        color=COLOR_ATTESA, timestamp=discord.utils.utcnow()
    )
    e.set_footer(text="🤠 Red Dead Redemption II — Cercatore d'Oro")
    return e


def _embed_blocco(res: dict) -> discord.Embed:
    until = int(res["until"])
    if res["motivo"] == "cooldown":
        e = discord.Embed(
            title="⏳ 𝐀𝐥𝐥𝐚 𝐥𝐞𝐧𝐭𝐚, 𝐜𝐨𝐰𝐛𝐨𝐲",
            description=f"Il setaccio è ancora bagnato. Potrai cercare di nuovo <t:{until}:R>.",
            color=COLOR_ATTESA
        )
    else:
        e = discord.Embed(
            title="⛔ 𝐋𝐢𝐦𝐢𝐭𝐞 𝐫𝐚𝐠𝐠𝐢𝐮𝐧𝐭𝐨",
            description=(f"Hai già raccolto **{LIMITE_PEPITE} pepite**: il fiume è esausto.\n"
                         f"Potrai riprendere <t:{until}:R>."),
            color=COLOR_STOP
        )
    e.set_footer(text="🤠 Red Dead Redemption II — Cercatore d'Oro")
    return e


def _embed_ricerca(user, res: dict) -> discord.Embed:
    titolo, colore, testi = _tier(res["tirato"])
    e = discord.Embed(title=titolo, description=f"*{random.choice(testi)}*",
                      color=colore, timestamp=discord.utils.utcnow())
    e.set_author(name=user.display_name, icon_url=user.display_avatar.url)

    t = res["trovate"]
    valore = (("🪙" * t + " ") if t else "") + f"**+{t}**"
    if t < res["tirato"]:
        valore += f"\n*(il limite ti ha fermato: ne avresti trovate {res['tirato']})*"
    e.add_field(name="🪙 Pepite trovate", value=valore, inline=True)
    e.add_field(name="🎒 In bisaccia", value=f"**{res['totale']}** pepite", inline=True)
    e.add_field(
        name="⛏️ Raccolta oraria",
        value=f"{_bar(res['ciclo'], LIMITE_PEPITE)}  **{res['ciclo']}/{LIMITE_PEPITE}**",
        inline=False
    )
    if res["limite_raggiunto"]:
        e.add_field(name="⛔ Limite raggiunto",
                    value=f"Il fiume riposa: riprendi <t:{int(res['sblocco'])}:R>", inline=False)
    else:
        e.add_field(name="⏳ Prossima ricerca", value=f"<t:{int(res['next'])}:R>", inline=False)

    foot = "🤠 Red Dead Redemption II — Cercatore d'Oro"
    if res["totale"] >= PEPITE_PER_LINGOTTO:
        foot += " | Hai pepite per /fondi-pepite!"
    e.set_footer(text=foot)
    return e


class RicercaView(discord.ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=300)
        self.uid = uid
        self.message = None

    @discord.ui.button(label="Cerca di nuovo", emoji="⛏️", style=discord.ButtonStyle.success)
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            await interaction.response.send_message("❌ Questo setaccio non è il tuo.", ephemeral=True)
            return
        if not _autorizzato(interaction.user):
            await interaction.response.send_message(_msg_non_autorizzato(), ephemeral=True)
            return
        res = await _tenta_ricerca(str(interaction.user.id))
        if not res["ok"]:
            await interaction.response.send_message(embed=_embed_blocco(res), ephemeral=True)
            return
        self.stop()
        await interaction.response.edit_message(embed=_embed_attesa(interaction.user), view=None)
        await asyncio.sleep(1.5)
        nuova = RicercaView(self.uid)
        nuova.message = interaction.message
        await interaction.edit_original_response(embed=_embed_ricerca(interaction.user, res), view=nuova)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  /fondi-pepite — grafica
# ══════════════════════════════════════════════════════════════════════════════
def _embed_fusione(row: dict) -> discord.Embed:
    now   = time.time()
    tot   = max(1.0, row["fine_ts"] - row["inizio_ts"])
    prog  = (now - row["inizio_ts"]) / tot
    pct   = int(max(0.0, min(1.0, prog)) * 100)
    fine  = int(row["fine_ts"])
    n     = row["lingotti"]

    e = discord.Embed(
        title="🔥 𝐅𝐎𝐍𝐃𝐈𝐓𝐔𝐑𝐀 𝐈𝐍 𝐂𝐎𝐑𝐒𝐎",
        description="*Le pepite ardono nella fornace della miniera, l'oro cola nelle forme di ferro...*",
        color=COLOR_FORNACE, timestamp=discord.utils.utcnow()
    )
    e.add_field(name="🥇 Lingotti", value=f"**{n}**", inline=True)
    e.add_field(name="🪙 Pepite fuse", value=f"**{n * PEPITE_PER_LINGOTTO}**", inline=True)
    e.add_field(name="⏱️ Termine", value=f"<t:{fine}:R>\n(<t:{fine}:t>)", inline=True)
    e.add_field(name="🔥 Avanzamento", value=f"{_fuoco_bar(prog)}  **{pct}%**", inline=False)
    e.set_footer(text="🤠 Red Dead Redemption II — Miniera | I lingotti arrivano da soli in bisaccia")
    return e


class FusioneView(discord.ui.View):
    def __init__(self, uid: int):
        super().__init__(timeout=900)
        self.uid = uid
        self.message = None

    @discord.ui.button(label="Aggiorna", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.uid:
            await interaction.response.send_message("❌ Questa fusione non è tua.", ephemeral=True)
            return
        row = await _get_fusione(str(self.uid))
        if not row:
            e = discord.Embed(
                title="✅ 𝐅𝐮𝐬𝐢𝐨𝐧𝐞 𝐜𝐨𝐦𝐩𝐥𝐞𝐭𝐚𝐭𝐚",
                description="I lingotti sono pronti: controlla la tua bisaccia con `/bisaccia`.",
                color=COLOR_FUSO
            )
            e.set_footer(text="🤠 Red Dead Redemption II — Miniera")
            self.stop()
            await interaction.response.edit_message(embed=e, view=None)
            return
        await interaction.response.edit_message(embed=_embed_fusione(row), view=self)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  Consegna automatica dei lingotti (task in background)
# ══════════════════════════════════════════════════════════════════════════════
async def _notifica_fusione(bot, row: dict):
    uid = int(row["user_id"])
    n   = row["lingotti"]
    totale = await database.get_item_quantity(row["user_id"], LINGOTTO_NAME)
    e = discord.Embed(
        title="🥇 𝐅𝐎𝐍𝐃𝐈𝐓𝐔𝐑𝐀 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐀𝐓𝐀",
        description="*L'oro si è raffreddato nelle forme: i lingotti sono pronti e splendenti.*",
        color=COLOR_FUSO, timestamp=discord.utils.utcnow()
    )
    e.add_field(name="🥇 Lingotti ricevuti", value=f"**+{n}**", inline=True)
    e.add_field(name="🎒 Totale in bisaccia", value=f"**{totale}** lingotti", inline=True)
    e.set_footer(text="🤠 Red Dead Redemption II — Miniera")

    inviato = False
    try:
        ch = bot.get_channel(int(row["channel_id"])) if row.get("channel_id") else None
        if ch:
            await ch.send(content=f"<@{uid}>", embed=e)
            inviato = True
    except Exception:
        pass
    if not inviato:
        try:
            u = await bot.fetch_user(uid)
            await u.send(embed=e)
        except Exception:
            pass

    try:
        log_ch = bot.get_channel(LOG_CHANNEL_ID)
        if log_ch:
            log = discord.Embed(title="🥇 LOG — Fusione Completata", color=COLOR_FUSO,
                                timestamp=discord.utils.utcnow())
            log.add_field(name="👤 Utente", value=f"<@{uid}>", inline=True)
            log.add_field(name="🥇 Lingotti", value=str(n), inline=True)
            await log_ch.send(embed=log)
    except Exception:
        pass


async def _consegna_fusioni(bot):
    now = time.time()
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM oro_fusioni WHERE fine_ts<=?", (now,)) as c:
            rows = [dict(r) for r in await c.fetchall()]

    for r in rows:
        async with _lock(r["user_id"]):
            async with aiosqlite.connect(DATABASE_NAME) as db:
                cur = await db.execute(
                    "DELETE FROM oro_fusioni WHERE user_id=? AND fine_ts=?",
                    (r["user_id"], r["fine_ts"])
                )
                await db.commit()
                claimed = cur.rowcount > 0
            if not claimed:
                continue
            try:
                await database.add_item(r["user_id"], LINGOTTO_NAME, r["lingotti"])
            except Exception as ex:
                print(f"❌ [oro] consegna lingotti fallita per {r['user_id']}: {ex}", flush=True)
                async with aiosqlite.connect(DATABASE_NAME) as db:
                    await db.execute(
                        "INSERT OR REPLACE INTO oro_fusioni (user_id,lingotti,inizio_ts,fine_ts,channel_id) VALUES (?,?,?,?,?)",
                        (r["user_id"], r["lingotti"], r["inizio_ts"], r["fine_ts"], r["channel_id"])
                    )
                    await db.commit()
                continue
            await _notifica_fusione(bot, r)


async def _fusion_loop(bot):
    await bot.wait_until_ready()
    print("🥇 Task consegna lingotti avviato (controllo ogni 20s)", flush=True)
    while not bot.is_closed():
        try:
            await _consegna_fusioni(bot)
        except Exception as ex:
            print(f"❌ [oro] errore task fusioni: {ex}", flush=True)
        await asyncio.sleep(20)


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════════════════════════════════════
def setup_oro_commands(bot):

    # Avvia il task di consegna al primo on_ready, senza toccare bot.py
    _state = {"started": False}

    async def _avvia_task_oro():
        if _state["started"]:
            return
        _state["started"] = True
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await _ensure_tables(db)
            await db.commit()
        asyncio.create_task(_fusion_loop(bot))

    bot.add_listener(_avvia_task_oro, "on_ready")

    # ── /cerca-oro ───────────────────────────────────────────────────────────
    @bot.tree.command(name="cerca-oro", description="Setaccia il fiume in cerca di pepite d'oro")
    async def cerca_oro(interaction: discord.Interaction):
        if not _autorizzato(interaction.user):
            await interaction.response.send_message(_msg_non_autorizzato(), ephemeral=True)
            return

        res = await _tenta_ricerca(str(interaction.user.id))
        if not res["ok"]:
            await interaction.response.send_message(embed=_embed_blocco(res), ephemeral=True)
            return

        await interaction.response.send_message(embed=_embed_attesa(interaction.user))
        await asyncio.sleep(1.5)
        view = RicercaView(interaction.user.id)
        msg = await interaction.edit_original_response(
            embed=_embed_ricerca(interaction.user, res), view=view
        )
        view.message = msg

    # ── /fondi-pepite ────────────────────────────────────────────────────────
    @bot.tree.command(
        name="fondi-pepite",
        description="Fondi le pepite in lingotti alla miniera (100 pepite = 1 lingotto, 10 min l'uno)"
    )
    @app_commands.describe(lingotti="Quanti lingotti produrre (servono 100 pepite per ciascuno)")
    async def fondi_pepite(interaction: discord.Interaction, lingotti: int):
        if not _autorizzato(interaction.user):
            await interaction.response.send_message(_msg_non_autorizzato(), ephemeral=True)
            return
        if lingotti < 1:
            await interaction.response.send_message("❌ Devi fondere almeno **1 lingotto**.", ephemeral=True)
            return

        uid = str(interaction.user.id)
        async with _lock(uid):
            esistente = await _get_fusione(uid)
            if esistente:
                await interaction.response.send_message(
                    content="⚠️ Hai già una fusione in corso, attendi che finisca:",
                    embed=_embed_fusione(esistente), ephemeral=True
                )
                return

            servono = lingotti * PEPITE_PER_LINGOTTO
            hai = await database.get_item_quantity(uid, PEPITA_NAME)
            if hai < servono:
                e = discord.Embed(
                    title="❌ 𝐏𝐞𝐩𝐢𝐭𝐞 𝐢𝐧𝐬𝐮𝐟𝐟𝐢𝐜𝐢𝐞𝐧𝐭𝐢",
                    description=(f"Per **{lingotti}** lingott{'o' if lingotti == 1 else 'i'} servono "
                                 f"**{servono}** pepite (minimo {PEPITE_PER_LINGOTTO}).\n"
                                 f"Ne hai **{hai}**."),
                    color=COLOR_STOP
                )
                e.set_footer(text="🤠 Red Dead Redemption II — Miniera")
                await interaction.response.send_message(embed=e, ephemeral=True)
                return

            if not await database.remove_item(uid, PEPITA_NAME, servono):
                await interaction.response.send_message("❌ Errore nel prelievo delle pepite.", ephemeral=True)
                return

            now = time.time()
            fine = now + lingotti * FUSIONE_S_PER_LINGOTTO
            async with aiosqlite.connect(DATABASE_NAME) as db:
                await _ensure_tables(db)
                await db.execute(
                    "INSERT OR REPLACE INTO oro_fusioni (user_id,lingotti,inizio_ts,fine_ts,channel_id) VALUES (?,?,?,?,?)",
                    (uid, lingotti, now, fine, str(interaction.channel_id) if interaction.channel_id else None)
                )
                await db.commit()
            row = {"user_id": uid, "lingotti": lingotti, "inizio_ts": now, "fine_ts": fine}

        view = FusioneView(interaction.user.id)
        await interaction.response.send_message(embed=_embed_fusione(row), view=view)
        view.message = await interaction.original_response()
