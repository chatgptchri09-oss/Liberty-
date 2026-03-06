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
        embed.add_field(name="🍔 Fame",     value=f"{_bar(old_h)}  →  {_bar(new_h)}", inline=False)
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
        embed.add_field(name="💦 Sete",    value=f"{_bar(old_t)}  →  {_bar(new_t)}" + note, inline=False)
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
        if not items:
            embed.add_field(name="📦 Contenuto", value="*Bisaccia vuota.*", inline=False)
        else:
            desc = "\n".join(f"**{i['item_name']}** — x{i['quantity']}" for i in items)
            embed.add_field(name="📦 Contenuto", value=desc, inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    # ── /inizio-turno ────────────────────────────────────────────────────────
    @bot.tree.command(name="inizio-turno", description="Inizia il tuo turno di lavoro")
    @app_commands.describe(lavoro="Tag del ruolo lavorativo", stipendio="Lo stipendio orario")
    async def inizio_turno(interaction: discord.Interaction, lavoro: discord.Role, stipendio: int):
        uid = str(interaction.user.id)
        if uid in _turni_attivi:
            await interaction.response.send_message("❌ Hai già un turno attivo.", ephemeral=True); return
        
        now = datetime.now(timezone.utc)
        _turni_attivi[uid] = {"role": lavoro, "stipendio": stipendio, "inizio": now}

        embed = discord.Embed(title="🟢 TURNO INIZIATO", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Dipendente", value=interaction.user.mention, inline=True)
        embed.add_field(name="Lavoro", value=lavoro.mention, inline=True)
        embed.add_field(name="Inizio", value=now.strftime("%H:%M UTC"), inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /fine-turno ──────────────────────────────────────────────────────────
    @bot.tree.command(name="fine-turno", description="Termina il tuo turno di lavoro")
    @app_commands.describe(lavoro="Tag del ruolo lavorativo")
    async def fine_turno(interaction: discord.Interaction, lavoro: discord.Role):
        uid = str(interaction.user.id)
        if uid not in _turni_attivi:
            await interaction.response.send_message("❌ Non hai turni attivi.", ephemeral=True); return
        
        turno = _turni_attivi.pop(uid)
        now = datetime.now(timezone.utc)
        durata = (now - turno["inizio"]).total_seconds()
        ore = max(1, math.ceil(durata / 3600))
        totale = turno["stipendio"] * ore

        embed = discord.Embed(title="🔴 TURNO TERMINATO", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Dipendente", value=interaction.user.mention, inline=True)
        embed.add_field(name="Ore", value=str(ore), inline=True)
        embed.add_field(name="Totale", value=f"${totale}", inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /campeggio ───────────────────────────────────────────────────────────
    @bot.tree.command(name="campeggio", description="Monta o smonta il tuo accampamento")
    @app_commands.choices(azione=[
        app_commands.Choice(name="⛺ Monta accampamento",  value="monta"),
        app_commands.Choice(name="🏕️ Smonta accampamento", value="smonta"),
    ])
    async def campeggio(interaction: discord.Interaction, azione: str, luogo: str = ""):
        desc = f"*{interaction.user.display_name} {azione} l'accampamento" + (f" a **{luogo}**.*" if luogo else ".*")
        embed = discord.Embed(title="🏕️ Campeggio", description=desc, color=discord.Color(0x556B2F))
        await interaction.response.send_message(embed=embed)

    # ── /caccia ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="caccia", description="Descrivi una sessione di caccia")
    async def caccia(interaction: discord.Interaction, preda: str, luogo: str, qualita: str = "Buona ⭐⭐"):
        embed = discord.Embed(title="🎯 Caccia", color=discord.Color(0x556B2F))
        embed.add_field(name="Preda", value=preda, inline=True)
        embed.add_field(name="Qualità", value=qualita, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /pesca ───────────────────────────────────────────────────────────────
    @bot.tree.command(name="pesca", description="Descrivi una sessione di pesca")
    async def pesca(interaction: discord.Interaction, pesce: str, luogo: str, peso: str = ""):
        embed = discord.Embed(title="🎣 Pesca", color=discord.Color(0x4682B4))
        embed.add_field(name="Pesce", value=pesce, inline=True)
        await interaction.response.send_message(embed=embed)

    # ── /anonimo ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="anonimo", description="Invia un messaggio anonimo")
    async def anonimo(interaction: discord.Interaction, messaggio: str):
        embed = discord.Embed(description=f"*\"{messaggio}\"*", color=discord.Color(0x2C2C2C))
        await interaction.response.send_message("✅ Inviato.", ephemeral=True)
        await interaction.channel.send(embed=embed)

    # ── /nascondo ────────────────────────────────────────────────────────────
    @bot.tree.command(name="nascondo", description="Nascondi un oggetto")
    async def nascondo(interaction: discord.Interaction, oggetto: str, luogo: str):
        embed = discord.Embed(title="🙈 Nascondiglio", description=f"Hai nascosto **{oggetto}** a **{luogo}**.", color=discord.Color(0x556B2F))
        await interaction.response.send_message(embed=embed)

    # ── /sondaggiorp ─────────────────────────────────────────────────────────
    @bot.tree.command(name="sondaggiorp", description="[Staff] Crea un sondaggio")
    async def sondaggiorp(interaction: discord.Interaction, domanda: str, opzione1: str, opzione2: str):
        embed = discord.Embed(title="📜 Sondaggio", description=domanda, color=discord.Color(0xDAA520))
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await interaction.response.send_message("✅ Creato.", ephemeral=True)

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
            await interaction.response.send_message("❌ Non puoi inviare una lettera a te stesso.", ephemeral=True)
            return
        if destinatario.bot:
            await interaction.response.send_message("❌ Non puoi inviare una lettera a un bot.", ephemeral=True)
            return

        COLOR_AVORIO = 0xF5F0DC

        embed_dm = discord.Embed(
            title="✉️ Hai ricevuto una lettera",
            color=COLOR_AVORIO,
            timestamp=discord.utils.utcnow()
        )
        embed_dm.add_field(name="📤 Mittente",          value=interaction.user.mention, inline=False)
        embed_dm.add_field(name="📬 Destinatario",      value=destinatario.mention,     inline=False)
        embed_dm.add_field(name="📜 Contenuto lettera", value=contenuto_lettera,        inline=False)
        embed_dm.add_field(name="🖊️ Firma mittente",   value=f"__{mittente}__",        inline=False)
        embed_dm.set_footer(text="🤠 Red Dead Redemption II — Posta del Far West")

        try:
            await destinatario.send(embed=embed_dm)
            await interaction.response.send_message(
                f"✅ Lettera inviata a {destinatario.mention} via DM.", ephemeral=True
            )
            
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                embed_log = discord.Embed(title="✉️ LOG — Lettera Inviata", color=COLOR_AVORIO, timestamp=discord.utils.utcnow())
                embed_log.add_field(name="📤 Mittente Discord", value=interaction.user.mention, inline=True)
                embed_log.add_field(name="📬 Destinatario",      value=destinatario.mention,     inline=True)
                embed_log.add_field(name="🖊️ Firma RP",         value=mittente,                 inline=False)
                embed_log.add_field(name="📜 Contenuto",         value=contenuto_lettera,        inline=False)
                await ch.send(embed=embed_log)

        except discord.Forbidden:
            await interaction.response.send_message(
                f"⚠️ Non è stato possibile consegnare la lettera: {destinatario.mention} ha i DM disabilitati.",
                ephemeral=True
            )
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Errore imprevisto.", ephemeral=True)
