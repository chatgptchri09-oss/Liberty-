import discord
from discord import app_commands
import database
from datetime import datetime

LOG_CHANNEL_ID = 1415297578022604850

# ID ruolo Banchiere e canale banca
BANKER_ROLE_ID  = 1404051937438994493
BANK_CHANNEL_ID = 1404052325609504798

def setup_wallet_commands(bot):

    # ─── Vista portafoglio ───────────────────────────────────────────────────
    def create_portafoglio_embed(user: dict, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(
            title="👜 Portafoglio di " + member.display_name,
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💵 Contanti",   value=f"${user['cash']:,}",  inline=True)
        embed.add_field(name="🏦 In banca",   value=f"${user['bank']:,}",  inline=True)
        embed.add_field(name="💰 Totale",     value=f"${user['cash'] + user['bank']:,}", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Portafoglio")
        return embed

    @bot.tree.command(name="portafoglio", description="Visualizza il tuo portafoglio con i tuoi averi")
    async def portafoglio(interaction: discord.Interaction):
        user = await database.get_user(str(interaction.user.id))
        embed = create_portafoglio_embed(user, interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ─── Banca con approvazione banchiere ───────────────────────────────────

    class ConfermaOperazioneView(discord.ui.View):
        """Vista nell'embed del canale banchieri — solo il banchiere può interagire."""
        def __init__(self, user_id: str, amount: int, action: str):
            super().__init__(timeout=300)
            self.user_id = user_id
            self.amount  = amount
            self.action  = action  # 'preleva' o 'deposita'

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if not isinstance(interaction.user, discord.Member):
                return False
            has_banker = any(r.id == BANKER_ROLE_ID for r in interaction.user.roles)
            if not has_banker:
                await interaction.response.send_message(
                    "❌ Solo un **Banchiere** può approvare o rifiutare questa operazione.",
                    ephemeral=True
                )
                return False
            return True

        @discord.ui.button(label="✅ Conferma", style=discord.ButtonStyle.green)
        async def conferma(self, interaction: discord.Interaction, button: discord.ui.Button):
            user = await database.get_user(self.user_id)

            if self.action == "preleva":
                if self.amount > user["bank"]:
                    await interaction.response.edit_message(
                        content="❌ **Operazione annullata automaticamente:** l'utente non ha fondi sufficienti in banca.",
                        view=None
                    )
                    return
                new_cash = user["cash"] + self.amount
                new_bank = user["bank"] - self.amount
                esito_msg = f"💵 Hai prelevato **${self.amount:,}** dalla banca. Operazione approvata dal banchiere."
            else:  # deposita
                if self.amount > user["cash"]:
                    await interaction.response.edit_message(
                        content="❌ **Operazione annullata automaticamente:** l'utente non ha abbastanza contanti.",
                        view=None
                    )
                    return
                new_cash = user["cash"] - self.amount
                new_bank = user["bank"] + self.amount
                esito_msg = f"🏦 Hai depositato **${self.amount:,}** in banca. Operazione approvata dal banchiere."

            await database.update_balance(self.user_id, cash=new_cash, bank=new_bank)

            # Disabilita bottoni
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"✅ **Operazione confermata da {interaction.user.display_name}**",
                view=self
            )

            # DM all'utente
            guild = interaction.guild
            member = guild.get_member(int(self.user_id))
            if member:
                try:
                    dm_embed = discord.Embed(
                        title="🏦 Operazione Bancaria Approvata",
                        description=esito_msg,
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow()
                    )
                    dm_embed.add_field(name="💵 Nuovo saldo contanti", value=f"${new_cash:,}", inline=True)
                    dm_embed.add_field(name="🏦 Nuovo saldo banca",    value=f"${new_bank:,}", inline=True)
                    dm_embed.set_footer(text="🤠 Red Dead Redemption II — Banca")
                    await member.send(embed=dm_embed)
                except Exception:
                    pass

        @discord.ui.button(label="❌ Annulla", style=discord.ButtonStyle.red)
        async def annulla(self, interaction: discord.Interaction, button: discord.ui.Button):
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"❌ **Operazione annullata da {interaction.user.display_name}**",
                view=self
            )

            # DM all'utente
            guild  = interaction.guild
            member = guild.get_member(int(self.user_id))
            if member:
                try:
                    dm_embed = discord.Embed(
                        title="🏦 Operazione Bancaria Rifiutata",
                        description=(
                            f"La tua richiesta di **{'prelievo' if self.action == 'preleva' else 'deposito'}** "
                            f"di **${self.amount:,}** è stata **rifiutata** dal banchiere."
                        ),
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    dm_embed.set_footer(text="🤠 Red Dead Redemption II — Banca")
                    await member.send(embed=dm_embed)
                except Exception:
                    pass

    class BancaModal(discord.ui.Modal):
        importo_input = discord.ui.TextInput(
            label="Importo",
            placeholder="Inserisci la cifra (solo numeri)",
            required=True
        )

        def __init__(self, action: str):
            self.action = action
            title = "💸 Richiesta di Prelievo" if action == "preleva" else "🏦 Richiesta di Deposito"
            super().__init__(title=title)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                amount = int(self.importo_input.value.replace(",", "").replace("$", "").strip())
                if amount <= 0:
                    await interaction.response.send_message("❌ L'importo deve essere maggiore di zero.", ephemeral=True)
                    return
            except ValueError:
                await interaction.response.send_message("❌ Importo non valido. Solo numeri interi.", ephemeral=True)
                return

            user = await database.get_user(str(interaction.user.id))
            if self.action == "preleva" and amount > user["bank"]:
                await interaction.response.send_message(
                    f"❌ Non hai abbastanza fondi in banca. (Disponibile: ${user['bank']:,})", ephemeral=True
                )
                return
            if self.action == "deposita" and amount > user["cash"]:
                await interaction.response.send_message(
                    f"❌ Non hai abbastanza contanti. (Disponibile: ${user['cash']:,})", ephemeral=True
                )
                return

            # Embed nel canale banchieri
            action_label = "prelievo" if self.action == "preleva" else "deposito"
            bank_channel = interaction.guild.get_channel(BANK_CHANNEL_ID)
            if bank_channel is None:
                await interaction.response.send_message("❌ Canale banca non trovato.", ephemeral=True)
                return

            banker_embed = discord.Embed(
                title=f"🏦 Richiesta di {action_label.capitalize()}",
                color=discord.Color(0xDAA520),
                timestamp=discord.utils.utcnow()
            )
            banker_embed.set_thumbnail(url=interaction.user.display_avatar.url)
            banker_embed.add_field(name="👤 Cliente",      value=interaction.user.mention,  inline=True)
            banker_embed.add_field(name="💰 Importo",      value=f"${amount:,}",            inline=True)
            banker_embed.add_field(name="📋 Operazione",   value=action_label.capitalize(),  inline=True)
            banker_embed.add_field(name="💵 Contanti att.", value=f"${user['cash']:,}",      inline=True)
            banker_embed.add_field(name="🏦 Banca att.",   value=f"${user['bank']:,}",      inline=True)
            banker_embed.set_footer(text="🤠 Red Dead Redemption II — Richiesta Bancaria")

            view = ConfermaOperazioneView(str(interaction.user.id), amount, self.action)
            await bank_channel.send(
                content=f"<@&{BANKER_ROLE_ID}> — Nuova richiesta da {interaction.user.mention}",
                embed=banker_embed,
                view=view
            )

            await interaction.response.send_message(
                f"✅ La tua richiesta di **{action_label}** di **${amount:,}** è stata inviata al banchiere. "
                f"Riceverai una notifica in DM quando verrà elaborata.",
                ephemeral=True
            )

    class BancaView(discord.ui.View):
        def __init__(self, user_id: str):
            super().__init__(timeout=None)
            self.user_id = user_id

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("❌ Questo non è il tuo conto!", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="Preleva", style=discord.ButtonStyle.green, emoji="💸")
        async def preleva(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(BancaModal(action="preleva"))

        @discord.ui.button(label="Deposita", style=discord.ButtonStyle.blurple, emoji="🏦")
        async def deposita(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(BancaModal(action="deposita"))

    def create_banca_embed(user: dict, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(
            title="🏦 Banca del Far West",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 Correntista",  value=member.mention,         inline=False)
        embed.add_field(name="💵 Contanti",     value=f"${user['cash']:,}",   inline=True)
        embed.add_field(name="🏦 In banca",     value=f"${user['bank']:,}",   inline=True)
        embed.add_field(name="💰 Totale",       value=f"${user['cash'] + user['bank']:,}", inline=False)
        embed.set_footer(text="🤠 Red Dead Redemption II — Banca | Le operazioni richiedono l'approvazione del banchiere")
        return embed

    @bot.tree.command(name="banca", description="Accedi al tuo conto bancario")
    async def banca(interaction: discord.Interaction):
        user    = await database.get_user(str(interaction.user.id))
        embed   = create_banca_embed(user, interaction.user)
        view    = BancaView(str(interaction.user.id))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @bot.tree.command(name="controlla-conto", description="Controlla il conto bancario di un altro giocatore")
    @app_commands.describe(giocatore="Il giocatore di cui controllare il conto")
    async def controlla_conto(interaction: discord.Interaction, giocatore: discord.Member):
        if giocatore.bot:
            await interaction.response.send_message("❌ Non puoi controllare il conto di un bot.", ephemeral=True)
            return
        if giocatore.id == interaction.user.id:
            await interaction.response.send_message("❌ Usa `/banca` per vedere il tuo conto.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        user_data = await database.get_user(str(giocatore.id))

        embed = discord.Embed(
            title=f"🔍 Conto di {giocatore.display_name}",
            color=discord.Color(0xDAA520),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=giocatore.display_avatar.url)
        embed.add_field(name="💵 Contanti", value=f"${user_data['cash']:,}", inline=True)
        embed.add_field(name="🏦 In banca", value=f"${user_data['bank']:,}", inline=True)
        embed.set_footer(text=f"Visualizzato da: {interaction.user.display_name}")

        try:
            notif = discord.Embed(
                title="🚨 Attenzione, cowboy!",
                description=f"{interaction.user.mention} ha sbirciato il tuo conto bancario!",
                color=discord.Color.red()
            )
            await giocatore.send(embed=notif)
            dm_status = "Notifica DM inviata."
        except Exception:
            dm_status = "DM bloccati."

        await interaction.followup.send(
            content=f"✅ Visualizzazione completata. ({dm_status})",
            embed=embed,
            ephemeral=True
        )
