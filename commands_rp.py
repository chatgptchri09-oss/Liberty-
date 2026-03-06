import discord
from discord import app_commands
import database
import random
import aiosqlite
from datetime import datetime, timezone
import math
from constants import (
    LOG_CHANNEL_ID, DATABASE_NAME, STAFF_ROLES, STAFF_ROLE_ID,
    SCERIFFO_ROLE_ID, DOTTORE_ROLE_ID, ARMIERE_ROLE_ID,
    STALLA_ROLE_ID, SALOON_ROLE_ID, EMPORIO_ROLE_ID,
    CONTRABBANDO_ID, DILIGENZA_ROLE_ID, STATO_ROLE_ID
)

# Canale dove va la notifica stipendio per lo staff
STIPENDIO_CHANNEL_ID = 1422986030650228766

# Turni attivi in memoria: user_id → {role, stipendio, inizio}
_turni_attivi: dict = {}

# ── Cibi ──────────────────────────────────────────────────────────────────────
FOOD_ITEMS = {
    "🦌 • Carne di cervo":           30,
    "🦌 • Carne di cervo grande":    35,
    "🫎 • Carne di alce":            40,
    "🐃 • Carne di bisonte":         45,
    "🐗 • Carne di cinghiale":       35,
    "🐻 • Carne di orso":            50,
    "🐑 • Carne di pecora":          25,
    "🐐 • Carne di capra":           25,
    "🐄 • Carne di mucca":           30,
    "🐂 • Carne di toro":            35,
    "🐔 • Carne di pollo":           20,
    "🦃 • Carne di tacchino":        25,
    "🦆 • Carne di anatra":          20,
    "🪿 • Carne di oca":             22,
    "🐇 • Carne di coniglio":        15,
    "🐿️ • Carne di scoiattolo":      10,
    "🦝 • Carne di procione":        12,
    "🐾 • Carne di opossum":         10,
    "🐍 • Carne di serpente":         8,
    "🐸 • Carne di rana":             6,
    "🦀 • Carne di granchio":        12,
    "🐟 • Carne di pesce":           18,
    "🍖 • Carne arrostita semplice": 28,
    "🌿 • Carne con menta":          32,
    "🌱 • Carne con timo":           32,
    "🍃 • Carne con origano":        32,
    "🥫 • Fagioli in scatola":       20,
    "🥫 • Pesce in scatola":         18,
    "🥫 • Mais in scatola":          15,
    "🥫 • Fragole in scatola":       12,
    "🥫 • Pesche in scatola":        14,
    "🥫 • Ananas in scatola":        14,
    "🥫 • Salmone in scatola":       20,
    "🍪 • Biscotti":                 10,
    "🫙 • Biscotti salati":           8,
    "🍞 • Pane":                     15,
    "🧀 • Formaggio":                18,
    "🍫 • Cioccolato":               12,
    "🍬 • Caramelle":                 6,
    "🍬 • Zolletta di zucchero":      4,
    "🍎 • Mela":                     10,
    "🍐 • Pera":                     10,
    "🍑 • Pesca":                    10,
    "🍑 • Albicocca":                 8,
    "🍌 • Banana":                   12,
    "🫐 • Mora":                      8,
    "🍇 • Lampone":                   7,
    "🍓 • Fragola":                   7,
    "🥬 • Sedano":                    5,
    "🫚 • Barbabietola":              6,
    "🥕 • Carota":                    8,
    "🐟 • Persico":                  18,
    "🐟 • Salmone rosso":            22,
    "🐟 • Trota iridea":             20,
    "🐟 • Pesce gatto":              18,
    "🐟 • Bluegill":                 14,
    "🐟 • Pickerel":                 16,
    "🐟 • Rock Bass":                16,
    "🐟 • Muskellunge":              25,
    "🐟 • Storione":                 30,
}

DRINK_ITEMS = {
    "🥃 • Whisky":             15,
    "🥃 • Bourbon":            15,
    "🥃 • Brandy":             12,
    "🥃 • Rum guatemalteco":   12,
    "🍸 • Gin":                10,
    "🍺 • Birra":              20,
    "🍺 • Birra artigianale":  22,
    "🍷 • Vino pregiato":      18,
    "🥂 • Champagne":          16,
    "🍑 • Liquore alla pesca": 14,
    "🫐 • Liquore al lampone": 14,
    "☕ • Caffè":              25,
}
ALCOHOLIC = {
    "🥃 • Whisky", "🥃 • Bourbon", "🥃 • Brandy", "🥃 • Rum guatemalteco",
    "🍸 • Gin", "🍺 • Birra", "🍺 • Birra artigianale",
    "🍷 • Vino pregiato", "🥂 • Champagne",
    "🍑 • Liquore alla pesca", "🫐 • Liquore al lampone"
}

# ── Helper ────────────────────────────────────────────────────────────────────
def _bar(v: int) -> str:
    f = round(v / 10)
    return "█" * f + "░" * (10 - f) + f"  **{v}%**"

def _color(h: int, t: int) -> discord.Color:
    if h < 20 or t < 20: return discord.Color.red()
    if h < 50 or t < 50: return discord.Color.orange()
    return discord.Color(0x8B4513)

def _sp() -> tuple:
    """Ritorna una coppia (nome, valore) per un campo vuoto separatore."""
    return "\u200b", "\u200b"

def _fuzzy(query: str, candidates: list) -> list:
    q = query.lower().strip()
    if not q: return candidates
    words = q.split()
    r = [c for c in candidates if all(w in c.lower() for w in words)]
    return r or [c for c in candidates if any(w in c.lower() for w in words)]


def setup_rp_commands(bot):

    # ── /me ──────────────────────────────────────────────────────────────────
    @bot.tree.command(name="me", description="Esegui un'azione roleplay nel Far West")
    @app_commands.describe(azione="Descrivi cosa fa il tuo personaggio")
    async def me(interaction: discord.Interaction, azione: str):
        uid  = str(interaction.user.id)
        user = await database.get_user(uid)
        h_drop = random.randint(4, 10)
        t_drop = random.randint(4, 10)
        new_h  = max(0, user["hunger"] - h_drop)
        new_t  = max(0, user["thirst"] - t_drop)
        await database.update_hunger_thirst(uid, hunger=new_h, thirst=new_t)
        embed = discord.Embed(
            description=f"*{interaction.user.display_name} {azione}*",
            color=_color(new_h, new_t),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🍔 Fame", value=_bar(new_h), inline=True)
        embed.add_field(name="💦 Sete", value=_bar(new_t), inline=True)
        warns = []
        if new_h < 20: warns.append("⚠️ **Sei affamato!** Mangia qualcosa.")
        if new_t < 20: warns.append("⚠️ **Sei assetato!** Bevi qualcosa.")
        if warns:
            embed.add_field(name="\u200b", value="\u200b", inline=False)
            embed.add_field(name="⚡ Avviso", value="\n".join(warns), inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Azione RP")
        await interaction.response.send_message(embed=embed)

    # ── /mangia ──────────────────────────────────────────────────────────────
    async def _food_ac(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, list(FOOD_ITEMS.keys()))[:25]]

    @bot.tree.command(name="mangia", description="Mangia un cibo dalla bisaccia per ripristinare la fame")
    @app_commands.describe(cibo="Il cibo da mangiare")
    @app_commands.autocomplete(cibo=_food_ac)
    async def mangia(interaction: discord.Interaction, cibo: str):
        if cibo not in FOOD_ITEMS:
            m = _fuzzy(cibo, list(FOOD_ITEMS.keys()))
            cibo = m[0] if m else cibo
        if cibo not in FOOD_ITEMS:
            await interaction.response.send_message("❌ Cibo non riconosciuto.", ephemeral=True); return
        uid = str(interaction.user.id)
        if await database.get_item_quantity(uid, cibo) < 1:
            await interaction.response.send_message(f"❌ Non hai **{cibo}** nella bisaccia!", ephemeral=True); return
        user  = await database.get_user(uid)
        rip   = FOOD_ITEMS[cibo]
        old_h = user["hunger"]
        new_h = min(100, old_h + rip)
        await database.update_hunger_thirst(uid, hunger=new_h)
        await database.remove_item(uid, cibo, 1)
        embed = discord.Embed(title="🍖 Pasto consumato", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🥘 Cibo",     value=cibo,                               inline=False)
        embed.add_field(name=*_sp(),        inline=False)
        embed.add_field(name="🍔 Fame",     value=f"{_bar(old_h)}  →  {_bar(new_h)}", inline=False)
        embed.add_field(name=*_sp(),        inline=False)
        embed.add_field(name="➕ Recupero", value=f"+{rip}%",                          inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ── /bevi ────────────────────────────────────────────────────────────────
    async def _drink_ac(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=m, value=m) for m in _fuzzy(current, list(DRINK_ITEMS.keys()))[:25]]

    @bot.tree.command(name="bevi", description="Bevi qualcosa dalla bisaccia per ripristinare la sete")
    @app_commands.describe(bevanda="La bevanda da bere")
    @app_commands.autocomplete(bevanda=_drink_ac)
    async def bevi(interaction: discord.Interaction, bevanda: str):
        if bevanda not in DRINK_ITEMS:
            m = _fuzzy(bevanda, list(DRINK_ITEMS.keys()))
            bevanda = m[0] if m else bevanda
        if bevanda not in DRINK_ITEMS:
            await interaction.response.send_message("❌ Bevanda non riconosciuta.", ephemeral=True); return
        uid = str(interaction.user.id)
        if await database.get_item_quantity(uid, bevanda) < 1:
            await interaction.response.send_message(f"❌ Non hai **{bevanda}** nella bisaccia!", ephemeral=True); return
        user  = await database.get_user(uid)
        rip   = DRINK_ITEMS[bevanda]
        old_t = user["thirst"]
        new_t = min(100, old_t + rip)
        await database.update_hunger_thirst(uid, thirst=new_t)
        await database.remove_item(uid, bevanda, 1)
        note = ""
        if bevanda in ALCOHOLIC:
            new_h = max(0, user["hunger"] - 5)
            await database.update_hunger_thirst(uid, hunger=new_h)
            note = "\n⚠️ *L'alcol ti ha tolto un po' di appetito...*"
        embed = discord.Embed(title="💧 Bevanda consumata", color=discord.Color(0x4682B4), timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🥃 Bevanda", value=bevanda,                                    inline=False)
        embed.add_field(name=*_sp(),       inline=False)
        embed.add_field(name="💦 Sete",    value=f"{_bar(old_t)}  →  {_bar(new_t)}" + note, inline=False)
        embed.add_field(name=*_sp(),       inline=False)
        embed.add_field(name="➕ Recupero",value=f"+{rip}%",                                 inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ── /bisaccia ────────────────────────────────────────────────────────────
    @bot.tree.command(name="bisaccia", description="Visualizza il contenuto della bisaccia")
    @app_commands.describe(utente="Tag di un altro giocatore (opzionale)")
    async def bisaccia(interaction: discord.Interaction, utente: discord.Member = None):
        ALLOWED = [STAFF_ROLE_ID, 1404051860121456701, SCERIFFO_ROLE_ID, STATO_ROLE_ID]
        target = utente or interaction.user
        if utente and utente.id != interaction.user.id:
            if not isinstance(interaction.user, discord.Member) or \
               not any(r.id in ALLOWED for r in interaction.user.roles):
                await interaction.response.send_message("❌ Solo Staff e Sceriffo possono vedere la bisaccia altrui.", ephemeral=True); return
        items = await database.get_inventory(str(target.id))
        user  = await database.get_user(str(target.id))
        titolo = f"🎒 Bisaccia di {target.display_name}" if utente else "🎒 La tua Bisaccia"
        embed = discord.Embed(title=titolo, color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🍔 Fame", value=_bar(user["hunger"]), inline=True)
        embed.add_field(name="💦 Sete", value=_bar(user["thirst"]), inline=True)
        embed.add_field(name=*_sp(),    inline=False)
        if not items:
            embed.add_field(name="📦 Contenuto", value="*Bisaccia vuota.*", inline=False)
        else:
            desc = "\n".join(f"**{i['item_name']}** — x{i['quantity']}" for i in items)
            embed.add_field(name="📦 Contenuto", value=desc, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        if utente and utente.id != interaction.user.id:
            try:
                ch = bot.get_channel(LOG_CHANNEL_ID)
                if ch:
                    log = discord.Embed(title="👁️ LOG — Bisaccia Controllata", color=discord.Color(0x8B4513))
                    log.add_field(name="👮 Chi ha guardato", value=interaction.user.mention, inline=True)
                    log.add_field(name="👤 Bisaccia di",     value=target.mention,           inline=True)
                    await ch.send(embed=log)
            except Exception: pass

    # ── /vendibisaccia ───────────────────────────────────────────────────────
    @bot.tree.command(name="vendibisaccia", description="Vendi l'intera tua bisaccia a un altro giocatore")
    @app_commands.describe(acquirente="Il giocatore che compra", prezzo="Prezzo in $ concordato")
    async def vendi_bisaccia(interaction: discord.Interaction, acquirente: discord.Member, prezzo: int):
        if acquirente.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi venderla a te stesso.", ephemeral=True); return
        if prezzo <= 0:
            await interaction.response.send_message("❌ Il prezzo deve essere positivo.", ephemeral=True); return
        items = await database.get_inventory(str(interaction.user.id))
        if not items:
            await interaction.response.send_message("❌ La tua bisaccia è vuota!", ephemeral=True); return
        buyer = await database.get_user(str(acquirente.id))
        if buyer["cash"] < prezzo:
            await interaction.response.send_message(f"❌ {acquirente.display_name} non ha abbastanza contanti.", ephemeral=True); return
        seller = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(acquirente.id),       cash=buyer["cash"] - prezzo)
        await database.update_balance(str(interaction.user.id), cash=seller["cash"] + prezzo)
        for it in items:
            await database.add_item(str(acquirente.id), it["item_name"], it["quantity"])
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM inventory WHERE user_id=?", (str(interaction.user.id),))
            await db.commit()
        contenuto = "\n".join(f"• {i['item_name']} x{i['quantity']}" for i in items)
        embed = discord.Embed(title="🤝 Bisaccia Venduta", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.add_field(name="💰 Prezzo",    value=f"${prezzo:,}",           inline=True)
        embed.add_field(name="👤 Venditore", value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 Acquirente",value=acquirente.mention,        inline=True)
        embed.add_field(name=*_sp(),         inline=False)
        embed.add_field(name="📦 Contenuto", value=contenuto or "—",         inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Scambio")
        await interaction.response.send_message(embed=embed)

    # ── /dai-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="dai-item", description="Dai un item dalla tua bisaccia a un altro giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="L'item da dare", quantita="Quantità")
    async def dai_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if giocatore.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi darti item da solo!", ephemeral=True); return
        if quantita < 1:
            await interaction.response.send_message("❌ Quantità minima: 1.", ephemeral=True); return
        if not await database.remove_item(str(interaction.user.id), item, quantita):
            await interaction.response.send_message(f"❌ Non hai abbastanza **{item}**.", ephemeral=True); return
        await database.add_item(str(giocatore.id), item, quantita)
        embed = discord.Embed(title="🤝 Item Consegnato", color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.add_field(name="📦 Item",     value=item,                     inline=True)
        embed.add_field(name="🔢 Quantità", value=str(quantita),            inline=True)
        embed.add_field(name=*_sp(),        inline=False)
        embed.add_field(name="👤 Da",       value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 A",        value=giocatore.mention,        inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Scambio")
        await interaction.response.send_message(embed=embed)

    # ── /utilizza-item ───────────────────────────────────────────────────────
    @bot.tree.command(name="utilizza-item", description="Utilizza un item dalla tua bisaccia")
    @app_commands.describe(item="L'item da utilizzare")
    async def utilizza_item(interaction: discord.Interaction, item: str):
        if not await database.remove_item(str(interaction.user.id), item, 1):
            await interaction.response.send_message(f"❌ Non hai **{item}** nella bisaccia.", ephemeral=True); return
        embed = discord.Embed(
            title="✅ Item Utilizzato",
            description=f"*{interaction.user.display_name} utilizza **{item}**.*",
            color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    #  /inizio-turno
    # ══════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="inizio-turno", description="Inizia il tuo turno di lavoro")
    @app_commands.describe(
        lavoro="Tag del ruolo lavorativo (@Sceriffo, @Dottore…)",
        stipendio="Il tuo stipendio orario in $"
    )
    async def inizio_turno(interaction: discord.Interaction, lavoro: discord.Role, stipendio: int):
        uid = str(interaction.user.id)

        # Blocco doppio turno
        if uid in _turni_attivi:
            t = _turni_attivi[uid]
            await interaction.response.send_message(
                f"❌ Hai già un turno attivo come **{t['role'].name}** iniziato alle "
                f"**{t['inizio'].strftime('%H:%M')} UTC**.\n"
                f"Usa `/fine-turno` prima di iniziarne un altro.",
                ephemeral=True
            )
            return

        # Controllo: l'utente possiede il ruolo indicato
        if not isinstance(interaction.user, discord.Member) or \
           not any(r.id == lavoro.id for r in interaction.user.roles):
            await interaction.response.send_message(
                f"❌ Non hai il ruolo {lavoro.mention} per iniziare questo turno.",
                ephemeral=True
            )
            return

        if stipendio <= 0:
            await interaction.response.send_message("❌ Lo stipendio orario deve essere positivo.", ephemeral=True); return

        now = datetime.now(timezone.utc)
        _turni_attivi[uid] = {
            "role":      lavoro,
            "stipendio": stipendio,
            "inizio":    now,
        }

        embed = discord.Embed(
            title="🟢 TURNO INIZIATO",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Dipendente",    value=interaction.user.mention, inline=False)
        embed.add_field(name=*_sp(),             inline=False)
        embed.add_field(name="💼 Lavoro",        value=lavoro.mention,           inline=False)
        embed.add_field(name=*_sp(),             inline=False)
        embed.add_field(name="💵 Stipendio/ora", value=f"${stipendio:,}",        inline=False)
        embed.add_field(name=*_sp(),             inline=False)
        embed.add_field(name="🕐 Inizio turno",  value=now.strftime("%H:%M UTC"), inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Turno di Lavoro")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed)
        except Exception: pass

    # ══════════════════════════════════════════════════════════════════════════
    #  /fine-turno
    # ══════════════════════════════════════════════════════════════════════════
    @bot.tree.command(name="fine-turno", description="Termina il tuo turno di lavoro")
    @app_commands.describe(lavoro="Tag del ruolo lavorativo con cui hai iniziato il turno")
    async def fine_turno(interaction: discord.Interaction, lavoro: discord.Role):
        uid = str(interaction.user.id)

        if uid not in _turni_attivi:
            await interaction.response.send_message(
                "❌ Non hai nessun turno attivo. Usa `/inizio-turno` prima.", ephemeral=True
            )
            return

        turno = _turni_attivi[uid]
        if turno["role"].id != lavoro.id:
            await interaction.response.send_message(
                f"❌ Il tuo turno attivo è per **{turno['role'].name}**, non per {lavoro.mention}.",
                ephemeral=True
            )
            return

        now          = datetime.now(timezone.utc)
        inizio       = turno["inizio"]
        durata_s     = (now - inizio).total_seconds()
        ore_esatte   = durata_s / 3600
        ore_fatturate = max(1, math.ceil(ore_esatte))   # minimo 1 ora, arrotonda per eccesso

        stipendio_totale = turno["stipendio"] * ore_fatturate

        h_display  = int(durata_s // 3600)
        m_display  = int((durata_s % 3600) // 60)
        durata_str = f"{h_display}h {m_display}min" if h_display > 0 else f"{m_display}min"

        del _turni_attivi[uid]

        # ── Embed fine turno (nel canale corrente) ───────────────────────────
        embed_fine = discord.Embed(
            title="🔴 TURNO TERMINATO",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed_fine.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed_fine.add_field(name="🤠 Dipendente",       value=interaction.user.mention,               inline=False)
        embed_fine.add_field(name=*_sp(),                inline=False)
        embed_fine.add_field(name="💼 Lavoro",           value=lavoro.mention,                         inline=False)
        embed_fine.add_field(name=*_sp(),                inline=False)
        embed_fine.add_field(name="🕐 Inizio",           value=inizio.strftime("%H:%M UTC"),           inline=True)
        embed_fine.add_field(name="🕑 Fine",             value=now.strftime("%H:%M UTC"),              inline=True)
        embed_fine.add_field(name=*_sp(),                inline=False)
        embed_fine.add_field(name="⏱️ Durata reale",     value=durata_str,                             inline=True)
        embed_fine.add_field(name="📋 Ore fatturate",    value=f"{ore_fatturate}h (arrot. eccesso)",   inline=True)
        embed_fine.add_field(name=*_sp(),                inline=False)
        embed_fine.add_field(name="💵 Stipendio/ora",    value=f"${turno['stipendio']:,}",             inline=True)
        embed_fine.add_field(name="💰 Totale da pagare", value=f"**${stipendio_totale:,}**",           inline=True)
        embed_fine.set_footer(text="🤠 Red Dead Redemption II — Turno di Lavoro")

        await interaction.response.send_message(embed=embed_fine)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch: await ch.send(embed=embed_fine)
        except Exception: pass

        # ── Embed notifica staff (canale stipendi) ───────────────────────────
        embed_staff = discord.Embed(
            title="💼 RICHIESTA PAGAMENTO STIPENDIO",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed_staff.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed_staff.add_field(name="🤠 Dipendente",       value=interaction.user.mention,               inline=False)
        embed_staff.add_field(name=*_sp(),                inline=False)
        embed_staff.add_field(name="💼 Ruolo",            value=lavoro.mention,                         inline=False)
        embed_staff.add_field(name=*_sp(),                inline=False)
        embed_staff.add_field(name="🕐 Inizio turno",     value=inizio.strftime("%H:%M UTC"),           inline=True)
        embed_staff.add_field(name="🕑 Fine turno",       value=now.strftime("%H:%M UTC"),              inline=True)
        embed_staff.add_field(name=*_sp(),                inline=False)
        embed_staff.add_field(name="⏱️ Durata",           value=durata_str,                             inline=True)
        embed_staff.add_field(name="📋 Ore fatturate",    value=f"{ore_fatturate}h",                    inline=True)
        embed_staff.add_field(name=*_sp(),                inline=False)
        embed_staff.add_field(name="💵 Stipendio/ora",    value=f"${turno['stipendio']:,}",             inline=True)
        embed_staff.add_field(name="💰 Da pagare",        value=f"**${stipendio_totale:,}**",           inline=True)
        embed_staff.set_footer(text="🤠 Red Dead Redemption II — Usa /paga-stipendio per pagare")

        try:
            stipendio_ch = bot.get_channel(STIPENDIO_CHANNEL_ID)
            if stipendio_ch:
                await stipendio_ch.send(
                    content=f"<@&{STAFF_ROLE_ID}> Paga lo stipendio!",
                    embed=embed_staff
                )
        except Exception: pass

    # ── /campeggio ───────────────────────────────────────────────────────────
    @bot.tree.command(name="campeggio", description="Monta o smonta il tuo accampamento")
    @app_commands.describe(azione="Monta o smonta", luogo="Dove (opzionale)")
    @app_commands.choices(azione=[
        app_commands.Choice(name="⛺ Monta accampamento",  value="monta"),
        app_commands.Choice(name="🏕️ Smonta accampamento", value="smonta"),
    ])
    async def campeggio(interaction: discord.Interaction, azione: str, luogo: str = ""):
        if azione == "monta":
            title = "⛺ Accampamento Montato"
            desc  = f"*{interaction.user.display_name} monta il proprio accampamento" + (f" a **{luogo}**.*" if luogo else ".*")
        else:
            title = "🏕️ Accampamento Smontato"
            desc  = f"*{interaction.user.display_name} smonta il proprio accampamento" + (f" da **{luogo}**.*" if luogo else ".*")
        embed = discord.Embed(title=title, description=desc, color=discord.Color(0x556B2F), timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Accampamento")
        await interaction.response.send_message(embed=embed)

    # ── /caccia ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="caccia", description="Descrivi una sessione di caccia")
    @app_commands.describe(preda="L'animale cacciato", luogo="Zona di caccia", qualita="Qualità della preda")
    @app_commands.choices(qualita=[
        app_commands.Choice(name="⭐ Scadente",     value="Scadente ⭐"),
        app_commands.Choice(name="⭐⭐ Buona",      value="Buona ⭐⭐"),
        app_commands.Choice(name="⭐⭐⭐ Perfetta", value="Perfetta ⭐⭐⭐"),
    ])
    async def caccia(interaction: discord.Interaction, preda: str, luogo: str, qualita: str = "Buona ⭐⭐"):
        embed = discord.Embed(title="🎯 Battuta di Caccia", color=discord.Color(0x556B2F), timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Cacciatore", value=interaction.user.mention, inline=False)
        embed.add_field(name=*_sp(),          inline=False)
        embed.add_field(name="🦌 Preda",      value=preda,                    inline=False)
        embed.add_field(name=*_sp(),          inline=False)
        embed.add_field(name="📍 Zona",       value=luogo,                    inline=False)
        embed.add_field(name=*_sp(),          inline=False)
        embed.add_field(name="⭐ Qualità",    value=qualita,                  inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Caccia")
        await interaction.response.send_message(embed=embed)

    # ── /pesca ───────────────────────────────────────────────────────────────
    @bot.tree.command(name="pesca", description="Descrivi una sessione di pesca")
    @app_commands.describe(pesce="Il pesce catturato", luogo="Dove hai pescato", peso="Peso (es: 2.5 kg, opzionale)")
    async def pesca(interaction: discord.Interaction, pesce: str, luogo: str, peso: str = ""):
        embed = discord.Embed(title="🎣 Sessione di Pesca", color=discord.Color(0x4682B4), timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Pescatore", value=interaction.user.mention, inline=False)
        embed.add_field(name=*_sp(),         inline=False)
        embed.add_field(name="🐟 Pesce",     value=pesce,                    inline=False)
        embed.add_field(name=*_sp(),         inline=False)
        embed.add_field(name="📍 Zona",      value=luogo,                    inline=False)
        if peso:
            embed.add_field(name=*_sp(),     inline=False)
            embed.add_field(name="⚖️ Peso",  value=peso,                     inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Pesca")
        await interaction.response.send_message(embed=embed)

    # ── /anonimo ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="anonimo", description="Invia un messaggio anonimo nel canale")
    @app_commands.describe(messaggio="Il messaggio anonimo")
    async def anonimo(interaction: discord.Interaction, messaggio: str):
        embed = discord.Embed(description=f"*\"{messaggio}\"*", color=discord.Color(0x2C2C2C), timestamp=discord.utils.utcnow())
        embed.set_author(name="🎭 Messaggio Anonimo")
        embed.set_footer(text="🤠 Red Dead Redemption II — Anonimo")
        await interaction.response.send_message("✅ Messaggio inviato anonimamente.", ephemeral=True)
        await interaction.channel.send(embed=embed)

    # ── /nascondo ────────────────────────────────────────────────────────────
    @bot.tree.command(name="nascondo", description="Nascondi un oggetto in un luogo segreto")
    @app_commands.describe(oggetto="L'oggetto", luogo="Il luogo segreto")
    async def nascondo(interaction: discord.Interaction, oggetto: str, luogo: str):
        embed = discord.Embed(title="🙈 Oggetto Nascosto", color=discord.Color(0x556B2F), timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="📦 Oggetto", value=oggetto, inline=False)
        embed.add_field(name=*_sp(),       inline=False)
        embed.add_field(name="📍 Luogo",   value=luogo,   inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Nascosto")
        await interaction.response.send_message(embed=embed)

    # ── /sondaggiorp ─────────────────────────────────────────────────────────
    @bot.tree.command(name="sondaggiorp", description="[Staff] Crea un sondaggio roleplay")
    @app_commands.describe(domanda="La domanda", opzione1="Prima opzione", opzione2="Seconda opzione")
    async def sondaggiorp(interaction: discord.Interaction, domanda: str, opzione1: str, opzione2: str):
        if not isinstance(interaction.user, discord.Member) or \
           not any(r.id in STAFF_ROLES for r in interaction.user.roles):
            await interaction.response.send_message("❌ Non hai i permessi.", ephemeral=True); return
        embed = discord.Embed(title="📜 Sondaggio Roleplay", description=f"**{domanda}**",
                              color=discord.Color(0xDAA520), timestamp=discord.utils.utcnow())
        embed.add_field(name="1️⃣ Opzione A", value=opzione1, inline=False)
        embed.add_field(name=*_sp(),          inline=False)
        embed.add_field(name="2️⃣ Opzione B", value=opzione2, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sondaggio RP")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("1️⃣")
        await msg.add_reaction("2️⃣")
        await interaction.response.send_message("✅ Sondaggio creato!", ephemeral=True)

    # ── /lettera ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="lettera", description="Invia una lettera privata a un altro giocatore")
    @app_commands.describe(
        destinatario="Il giocatore a cui inviare la lettera",
        contenuto_lettera="Il contenuto della lettera",
        mittente="Il tuo nome e cognome RP (es: Arthur Morgan)"
    )
    async def lettera(
        interaction: discord.Interaction,
        destinatario: discord.Member,
        contenuto_lettera: str,
        mittente: str
    ):
        if destinatario.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi inviare una lettera a te stesso.", ephemeral=True); return
        if destinatario.bot:
            await interaction.response.send_message("❌ Non puoi inviare una lettera a un bot.", ephemeral=True); return

        COLOR_AVORIO = 0xF5F0DC

        embed_dm = discord.Embed(
            title="✉️ Hai ricevuto una lettera",
            color=COLOR_AVORIO,
            timestamp=discord.utils.utcnow()
        )
        embed_dm.add_field(name="📤 Mittente",          value=interaction.user.mention, inline=False)
        embed_dm.add_field(name=*_sp(),                 inline=False)
        embed_dm.add_field(name="📬 Destinatario",      value=destinatario.mention,     inline=False)
        embed_dm.add_field(name=*_sp(),                 inline=False)
        embed_dm.add_field(name="📜 Contenuto lettera", value=contenuto_lettera,        inline=False)
        embed_dm.add_field(name=*_sp(),                 inline=False)
        embed_dm.add_field(name="🖊️ Firma mittente",   value=f"__{mittente}__",        inline=False)
        embed_dm.set_footer(text="🤠 Red Dead Redemption II — Posta del Far West")

        inviata = False
        try:
            await destinatario.send(embed=embed_dm)
            inviata = True
        except discord.Forbidden:
            pass

        if inviata:
            await interaction.response.send_message(
                f"✅ Lettera inviata a {destinatario.mention} via DM.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ Non è stato possibile consegnare la lettera: {destinatario.mention} ha i DM disabilitati.",
                ephemeral=True
            )

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                embed_log = discord.Embed(title="✉️ LOG — Lettera Inviata", color=COLOR_AVORIO, timestamp=discord.utils.utcnow())
                embed_log.add_field(name="📤 Mittente",          value=interaction.user.mention, inline=False)
                embed_log.add_field(name=*_sp(),                 inline=False)
                embed_log.add_field(name="📬 Destinatario",      value=destinatario.mention,     inline=False)
                embed_log.add_field(name=*_sp(),                 inline=False)
                embed_log.add_field(name="📜 Contenuto lettera", value=contenuto_lettera,        inline=False)
                embed_log.add_field(name=*_sp(),                 inline=False)
                embed_log.add_field(name="🖊️ Firma mittente",   value=f"__{mittente}__",        inline=False)
                await ch.send(embed=embed_log)
        except Exception: pass
