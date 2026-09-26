import discord
from discord import app_commands
import database
import aiosqlite
from datetime import datetime, timezone
from constants import LOG_CHANNEL_ID, DATABASE_NAME

# ⚠️ ID ruolo "Proprietario Fight Club" da confermare — al momento placeholder.
# L'utente lo inserirà manualmente in seguito.
FIGHT_CLUB_OWNER_ROLE_ID = 1421169805968539699

SCOMMESSA_MIN = 10
SCOMMESSA_MAX = 500

COLOR_FC       = 0x8B4513
COLOR_FC_CLOSE = 0xDAA520
COLOR_FC_WIN   = 0x228B22
COLOR_FC_VOID  = 0xB22222


def _has_fightclub_owner(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(r.id == FIGHT_CLUB_OWNER_ROLE_ID for r in interaction.user.roles)


async def _ensure_tables(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS fight_matches (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lottatore_a   TEXT NOT NULL,
            lottatore_b   TEXT NOT NULL,
            stato         TEXT DEFAULT 'aperta',
            vincitore     TEXT,
            message_id    TEXT,
            channel_id    TEXT,
            created_by    TEXT,
            created_at    TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS fight_bets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id   INTEGER NOT NULL,
            user_id    TEXT NOT NULL,
            lato       TEXT NOT NULL,
            importo    INTEGER NOT NULL,
            created_at TEXT
        )
    """)


async def _create_match(lottatore_a: str, lottatore_b: str, created_by: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        c = await db.execute(
            "INSERT INTO fight_matches (lottatore_a,lottatore_b,stato,created_by,created_at) VALUES (?,?,'aperta',?,?)",
            (lottatore_a, lottatore_b, created_by, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()
        return c.lastrowid


async def _set_match_message(match_id: int, message_id: str, channel_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        await db.execute(
            "UPDATE fight_matches SET message_id=?, channel_id=? WHERE id=?",
            (message_id, channel_id, match_id)
        )
        await db.commit()


async def _get_match(match_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fight_matches WHERE id=?", (match_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def _set_match_stato(match_id: int, stato: str, vincitore: str = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        await db.execute(
            "UPDATE fight_matches SET stato=?, vincitore=? WHERE id=?",
            (stato, vincitore, match_id)
        )
        await db.commit()


async def _add_bet(match_id: int, user_id: str, lato: str, importo: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        await db.execute(
            "INSERT INTO fight_bets (match_id,user_id,lato,importo,created_at) VALUES (?,?,?,?,?)",
            (match_id, user_id, lato, importo, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()


async def _get_bets(match_id: int) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fight_bets WHERE match_id=?", (match_id,)) as c:
            return [dict(r) for r in await c.fetchall()]


async def _get_user_bet(match_id: int, user_id: str) -> dict | None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await _ensure_tables(db)
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM fight_bets WHERE match_id=? AND user_id=?", (match_id, user_id)
        ) as c:
            row = await c.fetchone()
            return dict(row) if row else None


class ScommessaModal(discord.ui.Modal):
    def __init__(self, view: "FightBettingView", lato: str, nome_lottatore: str):
        super().__init__(title=f"🥊 Scommetti su {nome_lottatore}")
        self.view_ref = view
        self.lato = lato
        self.nome_lottatore = nome_lottatore
        self.importo = discord.ui.TextInput(
            label=f"Importo (min ${SCOMMESSA_MIN}, max ${SCOMMESSA_MAX})",
            placeholder="Es: 100",
            required=True,
            max_length=6
        )
        self.add_item(self.importo)

    async def on_submit(self, interaction: discord.Interaction):
        match = await _get_match(self.view_ref.match_id)
        if not match or match["stato"] != "aperta":
            await interaction.response.send_message("❌ Le scommesse per questo incontro sono chiuse.", ephemeral=True)
            return

        try:
            importo = int(self.importo.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Importo non valido.", ephemeral=True)
            return

        if importo < SCOMMESSA_MIN or importo > SCOMMESSA_MAX:
            await interaction.response.send_message(
                f"❌ L'importo deve essere tra **${SCOMMESSA_MIN}** e **${SCOMMESSA_MAX}**.", ephemeral=True
            )
            return

        uid = str(interaction.user.id)
        esistente = await _get_user_bet(self.view_ref.match_id, uid)
        if esistente:
            await interaction.response.send_message(
                "❌ Hai già scommesso su questo incontro (una sola scommessa a testa).", ephemeral=True
            )
            return

        user = await database.get_user(uid)
        if user["cash"] < importo:
            await interaction.response.send_message(
                f"❌ Contanti insufficienti. Disponibili: **${user['cash']:,}**", ephemeral=True
            )
            return

        await database.update_balance(uid, cash=user["cash"] - importo)
        await _add_bet(self.view_ref.match_id, uid, self.lato, importo)

        await interaction.response.send_message(
            f"✅ Hai scommesso **${importo:,}** su **{self.nome_lottatore}**! In bocca al lupo, cowboy.",
            ephemeral=True
        )

        try:
            embed = await self.view_ref.build_embed()
            if self.view_ref.message:
                await self.view_ref.message.edit(embed=embed, view=self.view_ref)
        except Exception as e:
            print(f"[fightclub] errore aggiornamento pannello: {e}", flush=True)


class FightBettingView(discord.ui.View):
    def __init__(self, match_id: int, lottatore_a: str, lottatore_b: str):
        super().__init__(timeout=None)
        self.match_id    = match_id
        self.lottatore_a = lottatore_a
        self.lottatore_b = lottatore_b
        self.message: discord.Message | None = None

        self.bet_a.label = f"🥊 Scommetti su {lottatore_a}"[:80]
        self.bet_b.label = f"🥊 Scommetti su {lottatore_b}"[:80]

    async def build_embed(self) -> discord.Embed:
        match = await _get_match(self.match_id)
        bets  = await _get_bets(self.match_id)

        pool_a = sum(b["importo"] for b in bets if b["lato"] == "A")
        pool_b = sum(b["importo"] for b in bets if b["lato"] == "B")
        cnt_a  = sum(1 for b in bets if b["lato"] == "A")
        cnt_b  = sum(1 for b in bets if b["lato"] == "B")
        totale = pool_a + pool_b

        stato = match["stato"] if match else "aperta"

        if stato == "aperta":
            titolo = "🥊 SCOMMESSE APERTE — FIGHT CLUB"
            colore = COLOR_FC
        elif stato == "chiusa":
            titolo = "🥊 SCOMMESSE CHIUSE — IN ATTESA DEL VERDETTO"
            colore = COLOR_FC_CLOSE
        elif stato == "annullata":
            titolo = "🥊 SCOMMESSE ANNULLATE — RIMBORSO EFFETTUATO"
            colore = COLOR_FC_VOID
        else:
            vincitore_nome = self.lottatore_a if match["vincitore"] == "A" else self.lottatore_b
            titolo = f"🥊 VINCE {vincitore_nome.upper()} — SCOMMESSE PAGATE"
            colore = COLOR_FC_WIN

        embed = discord.Embed(title=titolo, color=colore, timestamp=discord.utils.utcnow())
        embed.add_field(name=f"🥊 {self.lottatore_a}", value=f"**${pool_a:,}**\n{cnt_a} scommettitori", inline=True)
        embed.add_field(name="⚔️", value="vs", inline=True)
        embed.add_field(name=f"🥊 {self.lottatore_b}", value=f"**${pool_b:,}**\n{cnt_b} scommettitori", inline=True)

        quota_a = f"x{(totale/pool_a):.2f}" if pool_a > 0 else "—"
        quota_b = f"x{(totale/pool_b):.2f}" if pool_b > 0 else "—"
        embed.add_field(name="💰 Monte premi totale", value=f"**${totale:,}**", inline=False)
        embed.add_field(name=f"📊 Quota {self.lottatore_a}", value=quota_a, inline=True)
        embed.add_field(name=f"📊 Quota {self.lottatore_b}", value=quota_b, inline=True)

        if stato == "risolta" and match["vincitore"]:
            vincitore = match["vincitore"]
            pool_vincente = pool_a if vincitore == "A" else pool_b
            righe = []
            for b in bets:
                if b["lato"] == vincitore and pool_vincente > 0:
                    vincita = round(b["importo"] / pool_vincente * totale)
                    righe.append(f"<@{b['user_id']}> — puntati ${b['importo']:,} → vinti **${vincita:,}**")
            if righe:
                embed.add_field(name="🏆 Vincitori", value="\n".join(righe)[:1024], inline=False)

        embed.add_field(
            name="ℹ️ Regole",
            value=(
                f"Scommessa minima **${SCOMMESSA_MIN}**, massima **${SCOMMESSA_MAX}**.\n"
                "Servono almeno **2 scommettitori** — sotto il minimo, rimborso automatico.\n"
                "Il montepremi totale viene ridistribuito ai vincitori in proporzione alla puntata."
            ),
            inline=False
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Fight Club")
        return embed

    async def _rifiuta_se_non_proprietario(self, interaction: discord.Interaction) -> bool:
        if not _has_fightclub_owner(interaction):
            await interaction.response.send_message(
                "❌ Solo il proprietario del Fight Club può gestire questo incontro.", ephemeral=True
            )
            return True
        return False

    @discord.ui.button(label="🥊 Scommetti su A", style=discord.ButtonStyle.danger, row=0)
    async def bet_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        match = await _get_match(self.match_id)
        if not match or match["stato"] != "aperta":
            await interaction.response.send_message("❌ Le scommesse sono chiuse.", ephemeral=True); return
        await interaction.response.send_modal(ScommessaModal(self, "A", self.lottatore_a))

    @discord.ui.button(label="🥊 Scommetti su B", style=discord.ButtonStyle.primary, row=0)
    async def bet_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        match = await _get_match(self.match_id)
        if not match or match["stato"] != "aperta":
            await interaction.response.send_message("❌ Le scommesse sono chiuse.", ephemeral=True); return
        await interaction.response.send_modal(ScommessaModal(self, "B", self.lottatore_b))

    @discord.ui.button(label="🔒 Chiudi Scommesse", style=discord.ButtonStyle.secondary, row=1)
    async def chiudi(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._rifiuta_se_non_proprietario(interaction):
            return
        match = await _get_match(self.match_id)
        if not match or match["stato"] != "aperta":
            await interaction.response.send_message("❌ Non ci sono scommesse aperte da chiudere.", ephemeral=True); return

        await _set_match_stato(self.match_id, "chiusa")
        self.bet_a.disabled = True
        self.bet_b.disabled = True
        self.chiudi.disabled = True
        self.vince_a.disabled = False
        self.vince_b.disabled = False

        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏆 Vince A", style=discord.ButtonStyle.success, row=2, disabled=True)
    async def vince_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._rifiuta_se_non_proprietario(interaction):
            return
        await self._risolvi(interaction, "A")

    @discord.ui.button(label="🏆 Vince B", style=discord.ButtonStyle.success, row=2, disabled=True)
    async def vince_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._rifiuta_se_non_proprietario(interaction):
            return
        await self._risolvi(interaction, "B")

    async def _risolvi(self, interaction: discord.Interaction, vincitore: str):
        match = await _get_match(self.match_id)
        if not match or match["stato"] not in ("chiusa",):
            await interaction.response.send_message("❌ L'incontro non è pronto per la risoluzione.", ephemeral=True)
            return

        bets = await _get_bets(self.match_id)
        for c in self.children:
            c.disabled = True

        if len(bets) < 2:
            for b in bets:
                user = await database.get_user(b["user_id"])
                await database.update_balance(b["user_id"], cash=user["cash"] + b["importo"])
                try:
                    fetched = await interaction.client.fetch_user(int(b["user_id"]))
                    await fetched.send(
                        f"🥊 L'incontro **{self.lottatore_a} vs {self.lottatore_b}** è stato annullato "
                        f"(meno di 2 scommettitori). Rimborsati **${b['importo']:,}**."
                    )
                except Exception:
                    pass
            await _set_match_stato(self.match_id, "annullata")
            embed = await self.build_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            return

        pool_a = sum(b["importo"] for b in bets if b["lato"] == "A")
        pool_b = sum(b["importo"] for b in bets if b["lato"] == "B")
        totale = pool_a + pool_b
        pool_vincente = pool_a if vincitore == "A" else pool_b

        if pool_vincente == 0:
            for b in bets:
                user = await database.get_user(b["user_id"])
                await database.update_balance(b["user_id"], cash=user["cash"] + b["importo"])
                try:
                    fetched = await interaction.client.fetch_user(int(b["user_id"]))
                    await fetched.send(
                        f"🥊 Nessuno aveva scommesso sul vincitore dell'incontro "
                        f"**{self.lottatore_a} vs {self.lottatore_b}**. Rimborsati **${b['importo']:,}**."
                    )
                except Exception:
                    pass
            await _set_match_stato(self.match_id, "annullata")
            embed = await self.build_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            return

        for b in bets:
            if b["lato"] == vincitore:
                vincita = round(b["importo"] / pool_vincente * totale)
                user = await database.get_user(b["user_id"])
                await database.update_balance(b["user_id"], cash=user["cash"] + vincita)
                try:
                    fetched = await interaction.client.fetch_user(int(b["user_id"]))
                    nome_vinc = self.lottatore_a if vincitore == "A" else self.lottatore_b
                    await fetched.send(
                        f"🏆 Hai vinto la scommessa su **{nome_vinc}**!\n"
                        f"Puntati: **${b['importo']:,}** → Vinti: **${vincita:,}**"
                    )
                except Exception:
                    pass
            else:
                try:
                    fetched = await interaction.client.fetch_user(int(b["user_id"]))
                    nome_perso = self.lottatore_a if b["lato"] == "A" else self.lottatore_b
                    await fetched.send(
                        f"😔 Hai perso la scommessa su **{nome_perso}** (${b['importo']:,})."
                    )
                except Exception:
                    pass

        await _set_match_stato(self.match_id, "risolta", vincitore)
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

        try:
            ch = interaction.client.get_channel(LOG_CHANNEL_ID)
            if ch:
                nome_vinc = self.lottatore_a if vincitore == "A" else self.lottatore_b
                log = discord.Embed(
                    title="🥊 LOG — Fight Club: Incontro Risolto",
                    color=COLOR_FC_WIN,
                    timestamp=discord.utils.utcnow()
                )
                log.add_field(name="⚔️ Incontro", value=f"{self.lottatore_a} vs {self.lottatore_b}", inline=True)
                log.add_field(name="🏆 Vincitore", value=nome_vinc, inline=True)
                log.add_field(name="💰 Monte premi", value=f"${totale:,}", inline=True)
                log.add_field(name="👮 Dichiarato da", value=interaction.user.mention, inline=True)
                await ch.send(embed=log)
        except Exception:
            pass


def setup_fightclub_commands(bot):

    @bot.tree.command(name="scommessa-apri", description="[Fight Club] Apri le scommesse per un incontro")
    @app_commands.describe(lottatore_a="Nome del primo lottatore", lottatore_b="Nome del secondo lottatore")
    async def scommessa_apri(interaction: discord.Interaction, lottatore_a: str, lottatore_b: str):
        if not _has_fightclub_owner(interaction):
            await interaction.response.send_message(
                f"❌ Solo chi ha il ruolo <@&{FIGHT_CLUB_OWNER_ROLE_ID}> può aprire scommesse.", ephemeral=True
            )
            return

        match_id = await _create_match(lottatore_a, lottatore_b, str(interaction.user.id))
        view = FightBettingView(match_id, lottatore_a, lottatore_b)
        embed = await view.build_embed()

        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        view.message = msg
        await _set_match_message(match_id, str(msg.id), str(msg.channel.id))

    @bot.tree.command(name="scommessa-stato", description="[Fight Club] Mostra lo stato di un incontro (per ID)")
    @app_commands.describe(match_id="ID dell'incontro (visibile nel log)")
    async def scommessa_stato(interaction: discord.Interaction, match_id: int):
        match = await _get_match(match_id)
        if not match:
            await interaction.response.send_message("❌ Incontro non trovato.", ephemeral=True); return
        view = FightBettingView(match_id, match["lottatore_a"], match["lottatore_b"])
        embed = await view.build_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
