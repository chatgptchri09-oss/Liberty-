import discord
from discord import app_commands
import database
import random
from datetime import datetime

# ─────────────────────────────────────────────
# COSTANTI
# ─────────────────────────────────────────────
LOG_CHANNEL_ID = 1415297578022604850

# Formato item: "{emoji} • nome"
# ─────────────────────────────────────────────
# CIBI e ripristino fame (%)
# ─────────────────────────────────────────────
FOOD_ITEMS = {
    # Carni selvatiche
    "🦌 • Carne di cervo":         30,
    "🦌 • Carne di cervo grande":  35,
    "🫎 • Carne di alce":          40,
    "🐃 • Carne di bisonte":       45,
    "🐗 • Carne di cinghiale":     35,
    "🐻 • Carne di orso":          50,
    "🐑 • Carne di pecora":        25,
    "🐐 • Carne di capra":         25,
    "🐄 • Carne di mucca":         30,
    "🐂 • Carne di toro":          35,
    "🐔 • Carne di pollo":         20,
    "🦃 • Carne di tacchino":      25,
    "🦆 • Carne di anatra":        20,
    "🪿 • Carne di oca":           22,
    "🐇 • Carne di coniglio":      15,
    "🐿️ • Carne di scoiattolo":   10,
    "🦝 • Carne di procione":      12,
    "🐾 • Carne di opossum":       10,
    "🐍 • Carne di serpente":       8,
    "🐸 • Carne di rana":           6,
    "🦀 • Carne di granchio":      12,
    "🐟 • Carne di pesce":         18,
    # Varianti cucinate
    "🍖 • Carne arrostita semplice": 28,
    "🌿 • Carne con menta":          32,
    "🌱 • Carne con timo":           32,
    "🍃 • Carne con origano":        32,
    # Cibo in scatola
    "🥫 • Fagioli in scatola":      20,
    "🥫 • Pesce in scatola":        18,
    "🥫 • Mais in scatola":         15,
    "🥫 • Fragole in scatola":      12,
    "🥫 • Pesche in scatola":       14,
    "🥫 • Ananas in scatola":       14,
    "🥫 • Salmone in scatola":      20,
    "🍪 • Biscotti":                10,
    "🫙 • Biscotti salati":          8,
    "🍞 • Pane":                    15,
    "🧀 • Formaggio":               18,
    "🍫 • Cioccolato":              12,
    "🍬 • Caramelle":                6,
    "🍬 • Zolletta di zucchero":     4,
    # Frutta e verdura
    "🍎 • Mela":                    10,
    "🍐 • Pera":                    10,
    "🍑 • Pesca":                   10,
    "🍑 • Albicocca":                8,
    "🍌 • Banana":                  12,
    "🫐 • Mora":                     8,
    "🍇 • Lampone":                  7,
    "🍓 • Fragola":                  7,
    "🥬 • Sedano":                   5,
    "🫚 • Barbabietola":             6,
    "🥕 • Carota":                   8,
    # Pesci
    "🐟 • Persico":                 18,
    "🐟 • Salmone rosso":           22,
    "🐟 • Trota iridea":            20,
    "🐟 • Pesce gatto":             18,
    "🐟 • Bluegill":                14,
    "🐟 • Pickerel":                16,
    "🐟 • Rock Bass":               16,
    "🐟 • Muskellunge":             25,
    "🐟 • Storione":                30,
}

# ─────────────────────────────────────────────
# BEVANDE e ripristino sete (%)
# Alcolici ripristinano meno e danno lieve penalità fame
# ─────────────────────────────────────────────
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
# Bevande alcoliche (ripristinano sete ma danno piccola penalità fame)
ALCOHOLIC = {
    "🥃 • Whisky", "🥃 • Bourbon", "🥃 • Brandy",
    "🥃 • Rum guatemalteco", "🍸 • Gin", "🍺 • Birra",
    "🍺 • Birra artigianale", "🍷 • Vino pregiato",
    "🥂 • Champagne", "🍑 • Liquore alla pesca", "🫐 • Liquore al lampone"
}

def hunger_bar(value: int) -> str:
    filled = round(value / 10)
    return "█" * filled + "░" * (10 - filled) + f"  **{value}%**"

def thirst_bar(value: int) -> str:
    filled = round(value / 10)
    return "█" * filled + "░" * (10 - filled) + f"  **{value}%**"

def hunger_color(hunger: int, thirst: int) -> discord.Color:
    if hunger < 20 or thirst < 20:
        return discord.Color.red()
    if hunger < 50 or thirst < 50:
        return discord.Color.orange()
    return discord.Color(0x8B4513)  # Saddle Brown - stile western

def setup_rp_commands(bot):

    # ─── /me ───────────────────────────────────────
    @bot.tree.command(name="me", description="Esegui un'azione roleplay nel Far West")
    @app_commands.describe(azione="Descrivi cosa fa il tuo personaggio")
    async def me(interaction: discord.Interaction, azione: str):
        user = await database.get_user(str(interaction.user.id))

        # Calo randomico fame e sete (4-10%)
        fame_calo  = random.randint(4, 10)
        sete_calo  = random.randint(4, 10)
        new_hunger = max(0, user["hunger"] - fame_calo)
        new_thirst = max(0, user["thirst"] - thirst_calo := sete_calo)

        await database.update_hunger_thirst(
            str(interaction.user.id),
            hunger=new_hunger,
            thirst=new_thirst
        )

        embed = discord.Embed(
            description=f"*{interaction.user.display_name} {azione}*",
            color=hunger_color(new_hunger, new_thirst),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(
            name="🍔 Fame",
            value=hunger_bar(new_hunger),
            inline=True
        )
        embed.add_field(
            name="💦 Sete",
            value=thirst_bar(new_thirst),
            inline=True
        )

        warnings = []
        if new_hunger < 20:
            warnings.append("⚠️ **Sei affamato!** Mangia qualcosa prima di svenire.")
        if new_thirst < 20:
            warnings.append("⚠️ **Sei assetato!** Bevi qualcosa subito.")
        if warnings:
            embed.add_field(name="⚡ Avviso", value="\n".join(warnings), inline=False)

        embed.set_footer(text="🤠 Red Dead Redemption II — Azione RP")
        await interaction.response.send_message(embed=embed)

    # ─── /mangia ───────────────────────────────────
    @bot.tree.command(name="mangia", description="Mangia un cibo dalla tua bisaccia per ripristinare la fame")
    @app_commands.describe(cibo="Il cibo da mangiare (deve essere nella tua bisaccia)")
    @app_commands.autocomplete(cibo=lambda i, c: [
        app_commands.Choice(name=k, value=k)
        for k in FOOD_ITEMS if c.lower() in k.lower()
    ][:25])
    async def mangia(interaction: discord.Interaction, cibo: str):
        if cibo not in FOOD_ITEMS:
            await interaction.response.send_message(
                "❌ Questo cibo non è riconosciuto. Usa l'autocompletamento per scegliere.",
                ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        qty = await database.get_item_quantity(user_id, cibo)
        if qty < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{cibo}** nella tua bisaccia!", ephemeral=True
            )
            return

        user = await database.get_user(user_id)
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
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="🥘 Cibo", value=cibo, inline=False)
        embed.add_field(
            name="🍔 Fame",
            value=f"{hunger_bar(old_hunger)}  →  {hunger_bar(new_hunger)}",
            inline=False
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ─── /bevi ─────────────────────────────────────
    @bot.tree.command(name="bevi", description="Bevi qualcosa dalla tua bisaccia per ripristinare la sete")
    @app_commands.describe(bevanda="La bevanda da bere (deve essere nella tua bisaccia)")
    @app_commands.autocomplete(bevanda=lambda i, c: [
        app_commands.Choice(name=k, value=k)
        for k in DRINK_ITEMS if c.lower() in k.lower()
    ][:25])
    async def bevi(interaction: discord.Interaction, bevanda: str):
        if bevanda not in DRINK_ITEMS:
            await interaction.response.send_message(
                "❌ Questa bevanda non è riconosciuta. Usa l'autocompletamento per scegliere.",
                ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        qty = await database.get_item_quantity(user_id, bevanda)
        if qty < 1:
            await interaction.response.send_message(
                f"❌ Non hai **{bevanda}** nella tua bisaccia!", ephemeral=True
            )
            return

        user = await database.get_user(user_id)
        ripristino = DRINK_ITEMS[bevanda]
        old_thirst = user["thirst"]
        new_thirst = min(100, old_thirst + ripristino)
        await database.update_hunger_thirst(user_id, thirst=new_thirst)
        await database.remove_item(user_id, bevanda, 1)

        # Se alcolico: piccola penalità fame (-5)
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
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="🥃 Bevanda", value=bevanda, inline=False)
        embed.add_field(
            name="💦 Sete",
            value=f"{thirst_bar(old_thirst)}  →  {thirst_bar(new_thirst)}" + hunger_note,
            inline=False
        )
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed)

    # ─── /bisaccia ─────────────────────────────────
    @bot.tree.command(name="bisaccia", description="Visualizza il contenuto della tua bisaccia")
    async def bisaccia(interaction: discord.Interaction):
        items = await database.get_inventory(str(interaction.user.id))
        embed = discord.Embed(
            title="🎒 Bisaccia di " + interaction.user.display_name,
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if not items:
            embed.description = "*La tua bisaccia è vuota, cowboy...*"
        else:
            desc = ""
            for item in items:
                desc += f"**{item['item_name']}** — x{item['quantity']}\n"
            embed.description = desc
        embed.set_footer(text="🤠 Red Dead Redemption II — Bisaccia")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── /dai-item ──────────────────────────────────
    @bot.tree.command(name="dai-item", description="Dai un item della tua bisaccia a un altro giocatore")
    @app_commands.describe(giocatore="Il giocatore a cui dare l'item", item="L'item da dare", quantita="Quantità da dare")
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
                f"❌ Non hai abbastanza **{item}** nella tua bisaccia.", ephemeral=True
            )
            return

        await database.add_item(str(giocatore.id), item, quantita)

        embed = discord.Embed(
            title="🤝 Scambio avvenuto",
            color=discord.Color(0x8B4513),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📦 Item", value=item, inline=True)
        embed.add_field(name="🔢 Quantità", value=str(quantita), inline=True)
        embed.add_field(name="👤 Dato da", value=interaction.user.mention, inline=True)
        embed.add_field(name="🎯 Ricevuto da", value=giocatore.mention, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Scambio")
        await interaction.response.send_message(embed=embed)

    # ─── /anonimo ───────────────────────────────────
    @bot.tree.command(name="anonimo", description="Invia un messaggio anonimo nel canale corrente")
    @app_commands.describe(messaggio="Il messaggio anonimo da inviare")
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

    # ─── /sondaggiorp ───────────────────────────────
    @bot.tree.command(name="sondaggiorp", description="[STAFF] Crea un sondaggio roleplay")
    @app_commands.describe(domanda="La domanda del sondaggio", opzione1="Prima opzione", opzione2="Seconda opzione")
    async def sondaggiorp(interaction: discord.Interaction, domanda: str, opzione1: str, opzione2: str):
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

    # ─── /nascondo ──────────────────────────────────
    @bot.tree.command(name="nascondo", description="Nascondi un oggetto in un luogo segreto")
    @app_commands.describe(oggetto="L'oggetto da nascondere", luogo="Il luogo dove lo nascondi")
    async def nascondo(interaction: discord.Interaction, oggetto: str, luogo: str):
        embed = discord.Embed(
            title="🙈 Oggetto Nascosto",
            color=discord.Color(0x556B2F),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="📦 Oggetto", value=oggetto, inline=True)
        embed.add_field(name="📍 Luogo", value=luogo, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Oggetto nascosto")
        await interaction.response.send_message(embed=embed)

    # ─── /campeggio ─────────────────────────────────
    @bot.tree.command(name="campeggio", description="Monta o smonta il tuo accampamento nel Far West")
    @app_commands.describe(azione="Monta o smonta", luogo="Dove monti l'accampamento")
    @app_commands.choices(azione=[
        app_commands.Choice(name="⛺ Monta accampamento", value="monta"),
        app_commands.Choice(name="🏕️ Smonta accampamento", value="smonta"),
    ])
    async def campeggio(interaction: discord.Interaction, azione: str, luogo: str = ""):
        if azione == "monta":
            desc = f"*{interaction.user.display_name} monta il proprio accampamento" + (f" a **{luogo}**." if luogo else ".*")
            title = "⛺ Accampamento Montato"
        else:
            desc = f"*{interaction.user.display_name} smonta il proprio accampamento" + (f" da **{luogo}**." if luogo else ".*")
            title = "🏕️ Accampamento Smontato"

        embed = discord.Embed(title=title, description=desc, color=discord.Color(0x8B4513), timestamp=discord.utils.utcnow())
        embed.set_footer(text="🤠 Red Dead Redemption II — Accampamento")
        await interaction.response.send_message(embed=embed)

    # ─── /caccia ────────────────────────────────────
    @bot.tree.command(name="caccia", description="Descrivi una sessione di caccia nel Far West")
    @app_commands.describe(preda="L'animale cacciato", luogo="Dove hai cacciato")
    async def caccia(interaction: discord.Interaction, preda: str, luogo: str):
        embed = discord.Embed(
            title="🎯 Battuta di Caccia",
            color=discord.Color(0x556B2F),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="🦌 Preda", value=preda, inline=True)
        embed.add_field(name="📍 Zona", value=luogo, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Caccia")
        await interaction.response.send_message(embed=embed)

    # ─── /pesca ─────────────────────────────────────
    @bot.tree.command(name="pesca", description="Descrivi una sessione di pesca")
    @app_commands.describe(pesce="Il pesce catturato", luogo="Dove hai pescato")
    async def pesca(interaction: discord.Interaction, pesce: str, luogo: str):
        embed = discord.Embed(
            title="🎣 Sessione di Pesca",
            color=discord.Color(0x4682B4),
            timestamp=discord.utils.utcnow()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        embed.add_field(name="🐟 Pesce", value=pesce, inline=True)
        embed.add_field(name="📍 Zona", value=luogo, inline=True)
        embed.set_footer(text="🤠 Red Dead Redemption II — Pesca")
        await interaction.response.send_message(embed=embed)
