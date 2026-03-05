import discord
from discord import app_commands
import database
import random
import aiosqlite
from datetime import datetime

LOG_CHANNEL_ID = 1415297578022604850
DATABASE_NAME  = "rdr2_bot.db"

# ─────────────────────────────────────────────────────────────────────────────
# CIBI — formato "{emoji} • nome" : ripristino fame %
# ─────────────────────────────────────────────────────────────────────────────
FOOD_ITEMS = {
    # Carni selvatiche
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
    # Varianti cucinate
    "🍖 • Carne arrostita semplice": 28,
    "🌿 • Carne con menta":          32,
    "🌱 • Carne con timo":           32,
    "🍃 • Carne con origano":        32,
    # Cibo in scatola
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
    # Frutta e verdura
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
    # Pesci
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

# ─────────────────────────────────────────────────────────────────────────────
# BEVANDE — formato "{emoji} • nome" : ripristino sete %
# ─────────────────────────────────────────────────────────────────────────────
DRINK_ITEMS = {
    "🥃 • Whisky":              15,
    "🥃 • Bourbon":             15,
    "🥃 • Brandy":              12,
    "🥃 • Rum guatemalteco":    12,
    "🍸 • Gin":                 10,
    "🍺 • Birra":               20,
    "🍺 • Birra artigianale":   22,
    "🍷 • Vino pregiato":       18,
    "🥂 • Champagne":           16,
    "🍑 • Liquore alla pesca":  14,
    "🫐 • Liquore al lampone":  14,
    "☕ • Caffè":               25,
}

ALCOHOLIC = {
    "🥃 • Whisky", "🥃 • Bourbon", "🥃 • Brandy",
    "🥃 • Rum guatemalteco", "🍸 • Gin", "🍺 • Birra",
    "🍺 • Birra artigianale", "🍷 • Vino pregiato",
    "🥂 • Champagne", "🍑 • Liquore alla pesca", "🫐 • Liquore al lampone"
}

# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────
def _bar(value: int) -> str:
    filled = round(value / 10)
    return "█" * filled + "░" * (10 - filled) + f"  **{value}%**"

def _color(hunger: int, thirst: int) -> discord.Color:
    if hunger < 20 or thirst < 20:
        return discord.Color.red()
    if hunger < 50 or thirst < 50:
        return discord.Color.orange()
    return discord.Color(0x8B4513)

# ─────────────────────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────────────────────
def setup_rp_commands(bot):

    # ── /me ──────────────────────────────────────────────────────────────────
    @bot.tree.command(name="me", description="Esegui un'azione roleplay nel Far West")
    @app_commands.describe(azione="Descrivi cosa fa il tuo personaggio")
    async def me(interaction: discord.Interaction, azione: str):
        user_id = str(interaction.user.id)
        user    = await database.get_user(user_id)

        fame_calo  = random.randint(4, 10)
        sete_calo  = random.randint(4, 10)
        new_hunger = max(0, user["hunger"] - fame_calo)
        new_thirst = max(0, user["thirst"] - sete_calo)

        await database.update_hunger_thirst(user_id, hunger=new_hunger, thirst=new_thirst)

        embed = discord.Embed(
            description=f"*{interaction.user.display_name} {azione}*",
            color=_color(new_hunger, new_thirst),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="🍔 Fame", value=_bar(new_hunger), inline=True)
        embed.add_field(name="💦 Sete", value=_bar(new_thirst), inline=True)

        warnings = []
        if new_hunger < 20:
            warnings.append("⚠️ **Sei affamato!** Mangia qualcosa prima di svenire.")
        if new_thirst < 20:
            warnings.append("⚠️ **Sei assetato!** Bevi qualcosa subito.")
        if warnings:
            embed.add_field(name="⚡ Avviso", value="\n".join(warnings), inline=False)

        embed.set_footer(text="🤠 Red Dead Redemption II — Azione RP")
        await interaction.response.send_message(embed=embed)

    # ── /mangia ──────────────────────────────────────────────────────────────
    async def food_autocomplete(interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=k, value=k)
            for k in FOOD_ITEMS if current.lower() in k.lower()
        ][:25]

    @bot.tree.command(name="mangia", description="Mangia un cibo dalla tua bisaccia per ripristinare la fame")
    @app_commands.describe(cibo="Il cibo da mangiare (deve essere nella tua bisaccia)")
    @app_commands.autocomplete(cibo=food_autocomplete)
    async def mangia(interaction: discord.Interaction, cibo: str):
        if cibo not in FOOD_ITEMS:
            await interaction.response.send_message(
                "❌ Cibo non riconosciuto. Usa l'autocompletamento per scegliere.", ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        qty = await database.get_item_quantity(user_id, cibo)
        if qty < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{cibo}** nella tua bisaccia!", ephemeral=True
            )
            return

        user       = await database.get_user(user_id)
        ripristino = FOOD_ITEMS[cibo]
        old_hunger = user["hunger"]
        new_hunger = min(100, old_hunger + ripristino)

        await database.update_hunger_thirst(user_id, hunger=new_hunger)
        await database.remove_item(user_id, cibo, 1)

        embed = discord.Embed(
            title="🍖 Pasto consumato",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🥘 Cibo",   value=cibo,                                            inline=False)
        embed.add_field(name="🍔 Fame",   value=f"{_bar(old_hunger)}  →  {_bar(new_hunger)}",   inline=False)
        embed.add_field(name="➕ Recupero", value=f"+{ripristino}%",                             inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ── /bevi ────────────────────────────────────────────────────────────────
    async def drink_autocomplete(interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=k, value=k)
            for k in DRINK_ITEMS if current.lower() in k.lower()
        ][:25]

    @bot.tree.command(name="bevi", description="Bevi qualcosa dalla tua bisaccia per ripristinare la sete")
    @app_commands.describe(bevanda="La bevanda da bere (deve essere nella tua bisaccia)")
    @app_commands.autocomplete(bevanda=drink_autocomplete)
    async def bevi(interaction: discord.Interaction, bevanda: str):
        if bevanda not in DRINK_ITEMS:
            await interaction.response.send_message(
                "❌ Bevanda non riconosciuta. Usa l'autocompletamento per scegliere.", ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        qty = await database.get_item_quantity(user_id, bevanda)
        if qty < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{bevanda}** nella tua bisaccia!", ephemeral=True
            )
            return

        user       = await database.get_user(user_id)
        ripristino = DRINK_ITEMS[bevanda]
        old_thirst = user["thirst"]
        new_thirst = min(100, old_thirst + ripristino)

        await database.update_hunger_thirst(user_id, thirst=new_thirst)
        await database.remove_item(user_id, bevanda, 1)

        hunger_note = ""
        if bevanda in ALCOHOLIC:
            new_hunger = max(0, user["hunger"] - 5)
            await database.update_hunger_thirst(user_id, hunger=new_hunger)
            hunger_note = "\n⚠️ *L'alcol ti ha tolto un po' di appetito...*"

        embed = discord.Embed(
            title="💧 Bevanda consumata",
            color=discord.Color(0x4682B4),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🥃 Bevanda", value=bevanda,                                         inline=False)
        embed.add_field(name="💦 Sete",    value=f"{_bar(old_thirst)}  →  {_bar(new_thirst)}" + hunger_note, inline=False)
        embed.add_field(name="➕ Recupero", value=f"+{ripristino}%",                              inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ── /bisaccia (propria) ──────────────────────────────────────────────────
    @bot.tree.command(name="bisaccia", description="Visualizza il contenuto della tua bisaccia")
    async def bisaccia(interaction: discord.Interaction):
        items = await database.get_inventory(str(interaction.user.id))
        user  = await database.get_user(str(interaction.user.id))

        embed = discord.Embed(
            title=f"🎒 Bisaccia di {interaction.user.display_name}",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🍔 Fame", value=_bar(user["hunger"]), inline=True)
        embed.add_field(name="💦 Sete", value=_bar(user["thirst"]), inline=True)

        if not items:
            embed.add_field(name="📦 Contenuto", value="*La tua bisaccia è vuota, cowboy...*", inline=False)
        else:
            desc = ""
            for item in items:
                desc += f"**{item['item_name']}** — x{item['quantity']}\n"
            embed.add_field(name="📦 Contenuto", value=desc, inline=False)

        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /controllabisaccia (altrui, solo staff/sceriffo) ─────────────────────
    @bot.tree.command(name="controllabisaccia", description="[Staff/Sceriffo] Controlla la bisaccia di un altro giocatore")
    @app_commands.describe(giocatore="Il giocatore di cui controllare la bisaccia")
    async def controlla_bisaccia(interaction: discord.Interaction, giocatore: discord.Member):
        ALLOWED = [1414738761207517214, 1414735564632231988, 1415093546549248040]
        if not isinstance(interaction.user, discord.Member) or not any(r.id in ALLOWED for r in interaction.user.roles):
            await interaction.response.send_message("❌ Non hai i permessi per controllare la bisaccia altrui.", ephemeral=True)
            return

        items = await database.get_inventory(str(giocatore.id))
        user  = await database.get_user(str(giocatore.id))

        embed = discord.Embed(
            title=f"🔍 Bisaccia di {giocatore.display_name}",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="🍔 Fame", value=_bar(user["hunger"]), inline=True)
        embed.add_field(name="💦 Sete", value=_bar(user["thirst"]), inline=True)

        if not items:
            embed.add_field(name="📦 Contenuto", value="*Bisaccia vuota.*", inline=False)
        else:
            desc = ""
            for item in items:
                desc += f"**{item['item_name']}** — x{item['quantity']}\n"
            embed.add_field(name="📦 Contenuto", value=desc, inline=False)

        embed.set_footer(text=f"🤠 Controllato da: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Log
        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                log = discord.Embed(title="👁️ LOG CONTROLLO BISACCIA", color=discord.Color(0x8B4513))
                log.add_field(name="👮 Staff", value=interaction.user.mention, inline=True)
                log.add_field(name="👤 Giocatore", value=giocatore.mention, inline=True)
                await ch.send(embed=log)
        except Exception:
            pass

    # ── /vendibisaccia ───────────────────────────────────────────────────────
    @bot.tree.command(name="vendibisaccia", description="Vendi l'intera tua bisaccia a un altro giocatore per una cifra concordata")
    @app_commands.describe(acquirente="Il giocatore che acquista la tua bisaccia", prezzo="Prezzo concordato in $")
    async def vendi_bisaccia(interaction: discord.Interaction, acquirente: discord.Member, prezzo: int):
        if acquirente.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi vendere la bisaccia a te stesso.", ephemeral=True)
            return
        if prezzo <= 0:
            await interaction.response.send_message("❌ Il prezzo deve essere positivo.", ephemeral=True)
            return

        items = await database.get_inventory(str(interaction.user.id))
        if not items:
            await interaction.response.send_message("❌ La tua bisaccia è vuota, non c'è nulla da vendere!", ephemeral=True)
            return

        buyer = await database.get_user(str(acquirente.id))
        if buyer["cash"] < prezzo:
            await interaction.response.send_message(
                f"❌ {acquirente.display_name} non ha abbastanza contanti. (Richiesti: ${prezzo:,})", ephemeral=True
            )
            return

        # Trasferisce denaro
        seller = await database.get_user(str(interaction.user.id))
        await database.update_balance(str(acquirente.id),      cash=buyer["cash"] - prezzo)
        await database.update_balance(str(interaction.user.id), cash=seller["cash"] + prezzo)

        # Trasferisce item
        for item in items:
            await database.add_item(str(acquirente.id), item["item_name"], item["quantity"])
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM inventory WHERE user_id = ?", (str(interaction.user.id),))
            await db.commit()

        desc = "\n".join(f"• {i['item_name']} x{i['quantity']}" for i in items)
        embed = discord.Embed(
            title="🤝 Bisaccia Venduta",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="💰 Prezzo",    value=f"${prezzo:,}",             inline=True)
        embed.add_field(name="👤 Venditore", value=interaction.user.mention,   inline=True)
        embed.add_field(name="🎯 Acquirente",value=acquirente.mention,          inline=True)
        embed.add_field(name="📦 Contenuto", value=desc or "—",               inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Scambio Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ── /dai-item ────────────────────────────────────────────────────────────
    @bot.tree.command(name="dai-item", description="Dai un item dalla tua bisaccia a un altro giocatore")
    @app_commands.describe(giocatore="Il giocatore", item="L'item da dare", quantita="Quantità")
    async def dai_item(interaction: discord.Interaction, giocatore: discord.Member, item: str, quantita: int = 1):
        if giocatore.id == interaction.user.id:
            await interaction.response.send_message("❌ Non puoi darti un item da solo!", ephemeral=True)
            return
        if quantita < 1:
            await interaction.response.send_message("❌ La quantità deve essere almeno 1.", ephemeral=True)
            return

        rimosso = await database.remove_item(str(interaction.user.id), item, quantita)
        if not rimosso:
            await interaction.response.send_message(
                f"❌ Non hai abbastanza **{item}** nella bisaccia.", ephemeral=True
            )
            return

        await database.add_item(str(giocatore.id), item, quantita)

        embed = discord.Embed(
            title="🤝 Scambio Avvenuto",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📦 Item",       value=item,                     inline=True)
        embed.add_field(name="🔢 Quantità",   value=str(quantita),            inline=True)
        embed.add_field(name="👤 Da",         value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 A",          value=giocatore.mention,        inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Scambio")
        await interaction.response.send_message(embed=embed)

    # ── /utilizza-item ───────────────────────────────────────────────────────
    @bot.tree.command(name="utilizza-item", description="Utilizza un item dalla tua bisaccia")
    @app_commands.describe(item="L'item da utilizzare")
    async def utilizza_item(interaction: discord.Interaction, item: str):
        rimosso = await database.remove_item(str(interaction.user.id), item, 1)
        if not rimosso:
            await interaction.response.send_message(
                f"❌ Non hai **{item}** nella tua bisaccia.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="✅ Item Utilizzato",
            description=f"*{interaction.user.display_name} utilizza **{item}**.*",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ── /inizio-turno ────────────────────────────────────────────────────────
    @bot.tree.command(name="inizio-turno", description="Inizia il tuo turno di lavoro nel Far West")
    @app_commands.describe(lavoro="Il tuo lavoro/ruolo")
    async def inizio_turno(interaction: discord.Interaction, lavoro: str):
        embed = discord.Embed(
            title="🟢 TURNO INIZIATO",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Giocatore", value=interaction.user.mention, inline=True)
        embed.add_field(name="💼 Lavoro",    value=lavoro,                   inline=True)
        embed.add_field(name="🕐 Inizio",    value=discord.utils.utcnow().strftime("%H:%M UTC"), inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Turno di Lavoro")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ── /fine-turno ──────────────────────────────────────────────────────────
    @bot.tree.command(name="fine-turno", description="Termina il tuo turno di lavoro nel Far West")
    @app_commands.describe(lavoro="Il tuo lavoro/ruolo", note="Note sul turno (opzionale)")
    async def fine_turno(interaction: discord.Interaction, lavoro: str, note: str = ""):
        embed = discord.Embed(
            title="🔴 TURNO TERMINATO",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🤠 Giocatore", value=interaction.user.mention, inline=True)
        embed.add_field(name="💼 Lavoro",    value=lavoro,                   inline=True)
        embed.add_field(name="🕐 Fine",      value=discord.utils.utcnow().strftime("%H:%M UTC"), inline=True)
        if note:
            embed.add_field(name="📝 Note",  value=note,                     inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Turno di Lavoro")
        await interaction.response.send_message(embed=embed)

        try:
            ch = bot.get_channel(LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
        except Exception:
            pass

    # ── /campeggio ───────────────────────────────────────────────────────────
    @bot.tree.command(name="campeggio", description="Monta o smonta il tuo accampamento nel Far West")
    @app_commands.describe(azione="Monta o smonta", luogo="Dove monti/smonti l'accampamento")
    @app_commands.choices(azione=[
        app_commands.Choice(name="⛺ Monta accampamento", value="monta"),
        app_commands.Choice(name="🏕️ Smonta accampamento", value="smonta"),
    ])
    async def campeggio(interaction: discord.Interaction, azione: str, luogo: str = ""):
        if azione == "monta":
            desc   = f"*{interaction.user.display_name} monta il proprio accampamento" + (f" a **{luogo}**.*" if luogo else ".*")
            title  = "⛺ Accampamento Montato"
            color  = discord.Color(0x556B2F)
        else:
            desc   = f"*{interaction.user.display_name} smonta il proprio accampamento" + (f" da **{luogo}**.*" if luogo else ".*")
            title  = "🏕️ Accampamento Smontato"
            color  = discord.Color(0x8B4513)

        embed = discord.Embed(title=title, description=desc, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="🤠 Red Dead Redemption II — Accampamento")
        await interaction.response.send_message(embed=embed)

    # ── /caccia ──────────────────────────────────────────────────────────────
    @bot.tree.command(name="caccia", description="Descrivi una sessione di caccia e aggiungi la preda alla bisaccia")
    @app_commands.describe(preda="L'animale cacciato", luogo="Dove hai cacciato", qualita="Qualità della preda")
    @app_commands.choices(qualita=[
        app_commands.Choice(name="⭐ Scadente",  value="Scadente"),
        app_commands.Choice(name="⭐⭐ Buona",   value="Buona"),
        app_commands.Choice(name="⭐⭐⭐ Perfetta", value="Perfetta"),
    ])
    async def caccia(interaction: discord.Interaction, preda: str, luogo: str, qualita: str = "Buona"):
        embed = discord.Embed(
            title="🎯 Battuta di Caccia",
            color=discord.Color(0x556B2F),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🦌 Preda",    value=preda,   inline=True)
        embed.add_field(name="📍 Zona",     value=luogo,   inline=True)
        embed.add_field(name="⭐ Qualità",  value=qualita, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Caccia")
        await interaction.response.send_message(embed=embed)

    # ── /pesca ───────────────────────────────────────────────────────────────
    @bot.tree.command(name="pesca", description="Descrivi una sessione di pesca nel Far West")
    @app_commands.describe(pesce="Il pesce catturato", luogo="Dove hai pescato", peso="Peso approssimativo (es: 2.5 kg)")
    async def pesca(interaction: discord.Interaction, pesce: str, luogo: str, peso: str = ""):
        embed = discord.Embed(
            title="🎣 Sessione di Pesca",
            color=discord.Color(0x4682B4),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="🐟 Pesce", value=pesce, inline=True)
        embed.add_field(name="📍 Zona",  value=luogo, inline=True)
        if peso:
            embed.add_field(name="⚖️ Peso", value=peso, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Pesca")
        await interaction.response.send_message(embed=embed)

    # ── /anonimo ─────────────────────────────────────────────────────────────
    @bot.tree.command(name="anonimo", description="Invia un messaggio anonimo nel canale corrente")
    @app_commands.describe(messaggio="Il messaggio anonimo")
    async def anonimo(interaction: discord.Interaction, messaggio: str):
        embed = discord.Embed(
            description=f"*\"{messaggio}\"*",
            color=discord.Color(0x2C2C2C),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name="🎭 Messaggio Anonimo")
        embed.set_footer(text="🤠 Red Dead Redemption II — Anonimo")
        await interaction.response.send_message("✅ Messaggio inviato in modo anonimo.", ephemeral=True)
        await interaction.channel.send(embed=embed)

    # ── /sondaggiorp ─────────────────────────────────────────────────────────
    @bot.tree.command(name="sondaggiorp", description="[Staff] Crea un sondaggio roleplay")
    @app_commands.describe(domanda="La domanda", opzione1="Prima opzione", opzione2="Seconda opzione")
    async def sondaggiorp(interaction: discord.Interaction, domanda: str, opzione1: str, opzione2: str):
        STAFF_ROLES = [1414738761207517214, 1414735564632231988]
        if not isinstance(interaction.user, discord.Member) or not any(r.id in STAFF_ROLES for r in interaction.user.roles):
            await interaction.response.send_message("❌ Non hai i permessi necessari.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📜 Sondaggio Roleplay",
            description=f"**{domanda}**",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="1️⃣ Opzione A", value=opzione1, inline=True)
        embed.add_field(name="2️⃣ Opzione B", value=opzione2, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Sondaggio RP")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("1️⃣")
        await msg.add_reaction("2️⃣")
        await interaction.response.send_message("✅ Sondaggio creato!", ephemeral=True)

    # ── /nascondo ────────────────────────────────────────────────────────────
    @bot.tree.command(name="nascondo", description="Nascondi un oggetto in un luogo segreto")
    @app_commands.describe(oggetto="L'oggetto da nascondere", luogo="Il luogo dove lo nascondi")
    async def nascondo(interaction: discord.Interaction, oggetto: str, luogo: str):
        embed = discord.Embed(
            title="🙈 Oggetto Nascosto",
            color=discord.Color(0x556B2F),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="📦 Oggetto", value=oggetto, inline=True)
        embed.add_field(name="📍 Luogo",   value=luogo,   inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Nascosto")
        await interaction.response.send_message(embed=embed)

    # ── /scoop ───────────────────────────────────────────────────────────────
    @bot.tree.command(name="scoop", description="Pubblica uno scoop sulla Gazzetta del Far West")
    @app_commands.describe(titolo="Titolo dell'articolo", notizia="Testo della notizia")
    async def scoop(interaction: discord.Interaction, titolo: str, notizia: str):
        embed = discord.Embed(
            title=f"📰 {titolo}",
            description=notizia,
            color=discord.Color(0xF5DEB3),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=f"Giornalista: {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Gazzetta del Far West")
        await interaction.response.send_message(embed=embed)

    # ── /mie-proprieta ───────────────────────────────────────────────────────
    @bot.tree.command(name="mie-proprieta", description="Visualizza le tue proprietà nel Far West")
    async def mie_proprieta(interaction: discord.Interaction):
        props = await database.get_properties(str(interaction.user.id))
        embed = discord.Embed(
            title=f"🏡 Proprietà di {interaction.user.display_name}",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if not props:
            embed.description = "*Non possiedi ancora nessuna proprietà nel Far West.*"
        else:
            for p in props:
                embed.add_field(
                    name=f"{p['property_type']} — {p['property_name']}",
                    value=f"📍 {p['location']}\n📅 {p['created_at']}",
                    inline=False
                )
        embed.set_footer(text="🤠 Red Dead Redemption II — Proprietà")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /miafedinapenale ─────────────────────────────────────────────────────
    @bot.tree.command(name="miafedinapenale", description="Visualizza la tua fedina penale")
    async def mia_fedina(interaction: discord.Interaction):
        records = await database.get_criminal_records(str(interaction.user.id))
        embed = discord.Embed(
            title=f"⚖️ Fedina Penale di {interaction.user.display_name}",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if not records:
            embed.description = "✅ *Nessun crimine registrato. Sei un uomo onesto, cowboy.*"
        else:
            for r in records[-10:]:
                embed.add_field(
                    name=f"⚖️ {r['crime']}",
                    value=f"🔒 Pena: {r['sentence']}\n👮 Sceriffo: {r['officer']}\n📅 {r['created_at']}",
                    inline=False
                )
        embed.set_footer(text="🤠 Red Dead Redemption II — Fedina Penale")
        await interaction.response.send_message(embed=embed, ephemeral=True)
