import discord
from discord import app_commands
from discord.ext import commands
import database
from datetime import datetime
import random

LFD_ROLE_ID = 1415093546549248040
LOG_CHANNEL_ID = 1415297578022604850
LFD_LOG_CHANNEL_ID = 1424007218554208316
ARRESTO_LOG_CHANNEL_ID = 1436347936635097179
LOG_CHANNEL_MULTE_ID = 1424007218554208316

SLOT_SYMBOLS = ["🐺", "⭐", "🍋", "💎", "🎰"]

def has_role(interaction: discord.Interaction, role_id: int) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    return any(role.id == role_id for role in interaction.user.roles)

async def log_command(bot, channel_id: int, message: str = None, embed: discord.Embed = None):
    try:
        channel = bot.get_channel(channel_id)
        if channel and hasattr(channel, 'send'):
            if embed:
                await channel.send(embed=embed)
            elif message:
                await channel.send(message)
    except:
        pass


class FineModal(discord.ui.Modal, title="<a:sirena:1431792628332101723> Multa"):
    name_input = discord.ui.TextInput(label="Nome", placeholder="Nome dell'arrestato", required=True)
    surname_input = discord.ui.TextInput(label="Cognome", placeholder="Cognome dell'arrestato", required=True)
    age_input = discord.ui.TextInput(label="Età", placeholder="Età", required=True, max_length=3)
    infractions_input = discord.ui.TextInput(
        label="Infrazioni",
        placeholder="Descrivi le infrazioni",
        style=discord.TextStyle.paragraph,
        required=True
    )
    fine_amount_input = discord.ui.TextInput(
        label="Multa da pagare",
        placeholder="Importo in $",
        required=True,
        max_length=10
    )

    def __init__(self, bot, user_id: str):
        super().__init__()
        self.bot = bot
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            fine_amount = int(self.fine_amount_input.value)
            if fine_amount <= 0:
                await interaction.response.send_message("<a:annulla:1431940396635652146> L'importo deve essere maggiore di 0!", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("<a:annulla:1431940396635652146> Importo non valido!", ephemeral=True)
            return
        
        await database.create_fine(
            self.user_id,
            self.name_input.value,
            self.surname_input.value,
            self.age_input.value,
            self.infractions_input.value,
            fine_amount
        )
        
        embed = discord.Embed(
            title="<a:sirena:1431792628332101723> MULTA RICEVUTA",
            color=discord.Color.red()
        )
        embed.add_field(name="👤 Nome", value=self.name_input.value, inline=True)
        embed.add_field(name="👤 Cognome", value=self.surname_input.value, inline=True)
        embed.add_field(name="🎂 Età", value=self.age_input.value, inline=True)
        embed.add_field(name="⚖️ Infrazioni", value=self.infractions_input.value, inline=False)
        embed.add_field(name="💰 Multa", value=f"${fine_amount:,}", inline=False)
        
        try:
            user = await self.bot.fetch_user(int(self.user_id))
            await user.send(embed=embed)
        except:
            pass
        
        await interaction.response.send_message(f"<a:spunta:1431937738256552036> Multa inviata a <@{self.user_id}>!", ephemeral=True)
        
        # LOG CON EMBED
        log_embed = discord.Embed(
            title="<a:sirena:1431792628332101723> LOG MULTA EMESSA",
            color=discord.Color.red()
        )
        log_embed.add_field(name="Agente", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Multato", value=f"<@{self.user_id}>", inline=True)
        log_embed.add_field(name="Importo", value=f"${fine_amount:,}", inline=True)
        log_embed.add_field(name="Infrazioni", value=self.infractions_input.value[:1000], inline=False)
        log_embed.timestamp = discord.utils.utcnow()
        await log_command(self.bot, LOG_CHANNEL_MULTE_ID, embed=log_embed)


def setup_fine_commands(bot: commands.Bot):
    
    @bot.tree.command(name="multa", description="[LFD] Emetti una multa")
    @app_commands.describe(utente="L'utente da multare")
    async def multa(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("<a:annulla:1431940396635652146> Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        modal = FineModal(bot, str(utente.id))
        await interaction.response.send_modal(modal)

    
    class FineSelectMenu(discord.ui.Select):
        def __init__(self, fines, user_id):
            self.user_id = user_id
            self.fine_map = {}
            options = []
            
            for fine in fines:
                fine_id, name, surname, infractions, fine_amount = fine
                self.fine_map[str(fine_id)] = fine
                options.append(
                    discord.SelectOption(
                        label=f"{name} {surname} - ${fine_amount:,}",
                        description=infractions[:100],
                        value=str(fine_id)
                    )
                )
            
            super().__init__(placeholder="Seleziona una multa da pagare", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True, thinking=True)

            if str(interaction.user.id) != self.user_id:
                await interaction.followup.send("<a:annulla:1431940396635652146> Questo non è il tuo menu!", ephemeral=True)
                return
            
            fine_id = int(self.values[0])
            fine = await database.get_fine(fine_id)
            
            if not fine:
                await interaction.followup.send("<a:annulla:1431940396635652146> Multa non trovata!", ephemeral=True)
                return
            
            _, user_id, name, surname, age, infractions, fine_amount, paid, _ = fine
            
            if paid:
                await interaction.followup.send("<a:annulla:1431940396635652146> Questa multa è già stata pagata!", ephemeral=True)
                return
            
            user = await database.get_user(user_id)
            total = user["cash"] + user["bank"]
            
            if total < fine_amount:
                await interaction.followup.send("<a:annulla:1431940396635652146> Non hai abbastanza soldi per pagare questa multa!", ephemeral=True)
                return
            
            new_cash = user["cash"]
            new_bank = user["bank"]
            remaining = fine_amount
            
            if new_bank >= remaining:
                new_bank -= remaining
            else:
                remaining -= new_bank
                new_bank = 0
                new_cash -= remaining
            
            await database.update_balance(user_id, cash=new_cash, bank=new_bank)
            await database.pay_fine(fine_id)
            
            log_embed = discord.Embed(
                title="<a:saccodisoldi:1433965141145161770> MULTA PAGATA",
                color=discord.Color.green()
            )
            log_embed.add_field(name="👤 Nome", value=name, inline=True)
            log_embed.add_field(name="👤 Cognome", value=surname, inline=True)
            log_embed.add_field(name="🎂 Età", value=age, inline=True)
            log_embed.add_field(name="⚖️ Infrazioni", value=infractions, inline=False)
            log_embed.add_field(name="💰 Multa", value=f"${fine_amount:,}", inline=False)
            log_embed.timestamp = datetime.now()
            
            await log_command(bot, LFD_LOG_CHANNEL_ID, embed=log_embed)
            await interaction.followup.send(f"<a:spunta:1431937738256552036> Hai pagato la multa di **${fine_amount:,}**!", ephemeral=True)
            
            # LOG CON EMBED
            payment_log_embed = discord.Embed(
                title="💳 LOG PAGAMENTO MULTA",
                color=discord.Color.green()
            )
            payment_log_embed.add_field(name="Pagato da", value=interaction.user.mention, inline=True)
            payment_log_embed.add_field(name="Importo", value=f"${fine_amount:,}", inline=True)
            payment_log_embed.timestamp = discord.utils.utcnow()
            await log_command(bot, LOG_CHANNEL_ID, embed=payment_log_embed)
    
    @bot.tree.command(name="pagamulta", description="Paga una multa ricevuta")
    async def pagamulta(interaction: discord.Interaction):
        fines = await database.get_unpaid_fines(str(interaction.user.id))
        
        if not fines:
            await interaction.response.send_message("✅ Non hai multe da pagare!", ephemeral=True)
            return
        
        view = discord.ui.View()
        view.add_item(FineSelectMenu(fines, str(interaction.user.id)))
        
        await interaction.response.send_message("<a:sirena:1431792628332101723> Seleziona una multa da pagare:", view=view, ephemeral=True)
    
    @bot.tree.command(name="controllomulta", description="[LFD] Controlla le multe di un utente")
    @app_commands.describe(utente="L'utente di cui controllare le multe")
    async def controllomulta(interaction: discord.Interaction, utente: discord.Member):
        if not has_role(interaction, LFD_ROLE_ID):
            await interaction.response.send_message("<a:annulla:1431940396635652146> Solo i LFD possono usare questo comando!", ephemeral=True)
            return
        
        fines = await database.get_unpaid_fines(str(utente.id))
        
        if not fines:
            await interaction.response.send_message(f"<a:spunta:1431937738256552036> {utente.mention} non ha multe da pagare!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"<a:sirena:1431792628332101723> MULTE DI {utente.display_name}",
            color=discord.Color.red()
        )
        
        total_fines = 0
        for fine_id, name, surname, infractions, fine_amount in fines:
            total_fines += fine_amount
            embed.add_field(
                name=f"Multa #{fine_id}",
                value=f"**Nome:** {name} {surname}\n**Infrazioni:** {infractions}\n**Importo:** ${fine_amount:,}",
                inline=False
            )
        
        embed.add_field(name="💰 TOTALE MULTE", value=f"${total_fines:,}", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        
    
    @bot.tree.command(name="slotmachine", description="Gioca alla slot machine")
    @app_commands.describe(puntata="Importo da puntare (max $10,000)")
    async def slotmachine(interaction: discord.Interaction, puntata: int):
        if puntata <= 0:
            await interaction.response.send_message("<a:annulla:1431940396635652146> La puntata deve essere maggiore di 0!", ephemeral=True)
            return
        
        if puntata > 10000:
            await interaction.response.send_message("<a:annulla:1431940396635652146> La puntata massima è di $10,000!", ephemeral=True)
            return
        
        user = await database.get_user(str(interaction.user.id))
        total_balance = user["cash"] + user["bank"]
        
        if total_balance < puntata:
            await interaction.response.send_message("<a:annulla:1431940396635652146> Non hai abbastanza soldi per questa puntata!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        new_cash = user["cash"]
        new_bank = user["bank"]
        remaining = puntata
        
        if new_bank >= remaining:
            new_bank -= remaining
        else:
            remaining -= new_bank
            new_bank = 0
            new_cash -= remaining
        
        rand = random.random()
        
        # Nuove probabilità: 10% jackpot, 30% vincita normale, 60% perdita
        if rand < 0.10:  # 10% di probabilità (1 su 10)
            symbol = random.choice(SLOT_SYMBOLS)
            symbols = [symbol, symbol, symbol]
            winnings = int(puntata * 2.2)
            result_type = "jackpot"
        elif rand < 0.40:  # 30% di probabilità (3 su 10)
            symbol = random.choice(SLOT_SYMBOLS)
            other = random.choice([s for s in SLOT_SYMBOLS if s != symbol])
            symbols = [symbol, symbol, other]
            random.shuffle(symbols)
            winnings = int(puntata * 1.4)
            result_type = "win"
        else:  # 60% di probabilità (6 su 10)
            symbols = random.choices(SLOT_SYMBOLS, k=3)
            while symbols[0] == symbols[1] or symbols[1] == symbols[2] or symbols[0] == symbols[2]:
                symbols = random.choices(SLOT_SYMBOLS, k=3)
            winnings = 0
            result_type = "loss"
        
        import asyncio
        
        embed1 = discord.Embed(
            title="🎰 Slot Machine",
            description="| 🎲 | ❔ | ❔ |",
            color=discord.Color.red()
        )
        embed1.set_footer(text="Liberty RP - Slot Machine")
        message = await interaction.followup.send(embed=embed1)
        await asyncio.sleep(1)
        
        embed2 = discord.Embed(
            title="🎰 Slot Machine",
            description="| ❔ | 🎲 | ❔ |",
            color=discord.Color.orange()
        )
        embed2.set_footer(text="Liberty RP - Slot Machine")
        await message.edit(embed=embed2)
        await asyncio.sleep(1)
        
        embed3 = discord.Embed(
            title="🎰 Slot Machine",
            description="| ❔ | ❔ | 🎲 |",
            color=discord.Color.red()
        )
        embed3.set_footer(text="Liberty RP - Slot Machine")
        await message.edit(embed=embed3)
        await asyncio.sleep(1)
        
        embed4 = discord.Embed(
            title="🎰 Slot Machine",
            description="| 🎲 | 🎲 | ❔ |",
            color=discord.Color.red()
        )
        embed4.set_footer(text="Liberty RP - Slot Machine")
        await message.edit(embed=embed4)
        await asyncio.sleep(1)
        
        embed5 = discord.Embed(
            title="🎰 Slot Machine",
            description="| 🎲 | 🎲 | 🎲 |",
            color=0xc59dff
        )
        embed5.set_footer(text="Liberty RP - Slot Machine")
        await message.edit(embed=embed5)
        await asyncio.sleep(1)
        
        if result_type != "loss":
            new_cash += winnings
        
        await database.update_balance(str(interaction.user.id), cash=new_cash, bank=new_bank)
        
        if result_type == "jackpot":
            final_embed = discord.Embed(
                title="🎰 Risultato",
                description=f"| {symbols[0]} | {symbols[1]} | {symbols[2]} |",
                color=discord.Color.gold()
            )
            final_embed.add_field(
                name="",
                value=f"🎉 **JACKPOT!** Hai vinto **${winnings:,}**!",
                inline=False
            )
        elif result_type == "win":
            final_embed = discord.Embed(
                title="🎰 Risultato",
                description=f"| {symbols[0]} | {symbols[1]} | {symbols[2]} |",
                color=discord.Color.purple()
            )
            final_embed.add_field(
                name="",
                value=f"✨ Due simboli uguali! Hai vinto **${winnings:,}**!",
                inline=False
            )
        else:
            final_embed = discord.Embed(
                title="🎰 Risultato",
                description=f"| {symbols[0]} | {symbols[1]} | {symbols[2]} |",
                color=discord.Color.red()
            )
            final_embed.add_field(
                name="",
                value=f"❌ Nessuna vincita. Hai perso **${puntata:,}**!",
                inline=False
            )
        
        final_embed.set_footer(text="Liberty RP - Slot Machine")
        final_embed.set_thumbnail(url="https://i.postimg.cc/Qt136VrF/IMG-4279.gif")
        await message.edit(embed=final_embed)
