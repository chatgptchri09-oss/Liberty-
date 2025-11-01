import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

# ===================================================================================
# COSTANTI
# ===================================================================================

DATABASE_NAME = "economy_bot.db"
LOG_CHANNEL_ID = 1415297578022604850
STAFF_ROLE_ID = 1414738761207517214
MARKET_ROLE_ID = 1415242295153918123
BACKPACK_PRICE = 5000 # Prezzo per l'acquisto dello zaino

# ===================================================================================
# FUNZIONI DI SUPPORTO
# ===================================================================================

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

async def get_user_economy(user_id: str):
    """Recupera denaro e stato zaino dell'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Assicurati che 'has_backpack' sia presente nella tabella users
        async with db.execute("SELECT cash, bank, has_backpack FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_user_economy(user_id: str, bank_change: int = 0, backpack_status: int = None):
    """Aggiorna bank e/o stato zaino dell'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        query = "UPDATE users SET bank = bank + ?"
        params = [bank_change]
        
        if backpack_status is not None:
            query += ", has_backpack = ?"
            params.append(backpack_status)
        
        query += " WHERE user_id = ?"
        params.append(user_id)
        
        # Inizializza l'utente se non esiste (necessario per evitare errori UPDATE)
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        
        await db.execute(query, tuple(params))
        await db.commit()

async def update_inventory(user_id: str, item_name: str, quantity: int, mode: str = 'add'):
    """Aggiorna l'inventario dell'utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if mode == 'add':
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = quantity + excluded.quantity",
                (user_id, item_name, quantity)
            )
        elif mode == 'remove':
            await db.execute(
                "UPDATE inventory SET quantity = quantity - ? WHERE user_id = ? AND item_name = ?",
                (quantity, user_id, item_name)
            )
            await db.execute("DELETE FROM inventory WHERE user_id = ? AND quantity <= 0", (user_id,))
        elif mode == 'set': # Utile per i comandi staff
            await db.execute(
                "INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, item_name) DO UPDATE SET quantity = ?",
                (user_id, item_name, quantity, quantity)
            )
            await db.execute("DELETE FROM inventory WHERE user_id = ? AND quantity <= 0", (user_id,))

        await db.commit()

async def add_item_to_shop(name: str, price: int, required_role_id: int):
    """Aggiunge un item al database 'items' per l'item shop."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO items (name, price, required_role_id) VALUES (?, ?, ?)",
            (name, price, str(required_role_id))
        )
        await db.commit()

async def remove_item_from_shop(name: str):
    """Rimuove un item dal database 'items'."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("DELETE FROM items WHERE name = ?", (name,))
        await db.commit()
        return cursor.rowcount > 0 # Ritorna True se un item è stato rimosso

async def get_shop_items():
    """Recupera tutti gli item disponibili per la vendita."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT name, price, required_role_id FROM items ORDER BY price ASC") as cursor:
            return await cursor.fetchall()
            
# ===================================================================================
# FUNZIONE DI SETUP
# ===================================================================================

def setup_inventory_commands(bot: commands.Bot):
    
    # ===================================================
    # COMANDO: /vendi-zaino (MARKET)
    # ===================================================
    @bot.tree.command(name="vendi-zaino", description=f"[Market] Acquista uno zaino per ${BACKPACK_PRICE:,}")
    async def vendizaino(interaction: discord.Interaction):
        # 1. Controllo Ruolo Market
        if not has_role(interaction, MARKET_ROLE_ID):
            await interaction.response.send_message("❌ Questo comando può essere usato solo dal **Market**.", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        user_data = await get_user_economy(user_id)
        # Se l'utente non esiste nel DB, lo inizializziamo (update_user_economy lo fa in automatico)
        if not user_data:
             user_data = [0, 20000, 0] # Dati di default per continuare

        cash, bank, has_backpack = user_data
        
        # 2. Controllo Zaino Esistente
        if has_backpack == 1:
            await interaction.followup.send("❌ Hai già uno zaino! Non puoi acquistarne un altro.", ephemeral=True)
            return

        # 3. Controllo Denaro (Usiamo la Banca per gli acquisti importanti)
        if bank < BACKPACK_PRICE:
            await interaction.followup.send(f"❌ Non hai abbastanza soldi in banca! Hai solo ${bank:,} ma ne servono ${BACKPACK_PRICE:,}.", ephemeral=True)
            return

        # 4. Transazione
        try:
            # Rimuovi i soldi e imposta has_backpack a 1
            await update_user_economy(user_id, bank_change=-BACKPACK_PRICE, backpack_status=1)
            
            new_bank = bank - BACKPACK_PRICE
            
            # 5. Risposta e Log
            await interaction.followup.send(
                f"✅ Hai acquistato uno zaino per **${BACKPACK_PRICE:,}**! Il tuo nuovo saldo bancario è: **${new_bank:,}**",
                ephemeral=True
            )
            
            # 6. Notifica DM all'utente
            try:
                dm_embed = discord.Embed(
                    title="🎒 Zaino Acquistato!",
                    description=(
                        f"Congratulazioni! Hai acquistato uno zaino per **${BACKPACK_PRICE:,}**.\n"
                        f"Ora puoi usarlo per gestire i tuoi item con il comando: **/invzaino**."
                    ),
                    color=discord.Color.blue()
                )
                await interaction.user.send(embed=dm_embed)
            except discord.Forbidden:
                pass # L'utente ha i DM chiusi
            
            await log_command(bot, LOG_CHANNEL_ID, f"🛍️ {interaction.user.mention} ha acquistato uno zaino per ${BACKPACK_PRICE:,}")

        except Exception as e:
            print(f"Errore durante /vendi-zaino: {e}")
            await interaction.followup.send("❌ Si è verificato un errore durante la transazione. Contatta lo staff.", ephemeral=True)


    # ===================================================
    # COMANDO: /rimuovi-zaino (STAFF)
    # ===================================================
    @bot.tree.command(name="rimuovi-zaino", description="[Staff] Rimuovi lo zaino a un utente")
    @app_commands.describe(utente="L'utente a cui rimuovere lo zaino")
    async def rimuovizaino(interaction: discord.Interaction, utente: discord.Member):
        # 1. Controllo Ruolo Staff
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo **staff** può usare questo comando!", ephemeral=True)
            return

        target_id = str(utente.id)
        
        await interaction.response.defer(ephemeral=True)
        
        user_data = await get_user_economy(target_id)
        if not user_data:
            await interaction.followup.send(f"❌ Errore: Dati utente ({utente.mention}) non trovati.", ephemeral=True)
            return
            
        has_backpack = user_data[2]

        # 2. Controllo Zaino Esistente
        if has_backpack == 0:
            await interaction.followup.send(f"❌ {utente.mention} non ha uno zaino da rimuovere.", ephemeral=True)
            return

        # 3. Rimozione Zaino
        try:
            # Imposta has_backpack a 0 
            await update_user_economy(target_id, backpack_status=0)
            
            # 4. Risposta e Log
            await interaction.followup.send(
                f"✅ Zaino rimosso con successo da **{utente.mention}**.",
                ephemeral=True
            )
            
            # 5. Notifica DM all'utente
            try:
                dm_embed = discord.Embed(
                    title="⚠️ Zaino Rimosso!",
                    description="Il tuo zaino è stato rimosso dallo staff. Non potrai più usare i comandi di inventario finché non ne acquisti uno nuovo.",
                    color=discord.Color.red()
                )
                await utente.send(embed=dm_embed)
            except discord.Forbidden:
                pass # L'utente ha i DM chiusi
                
            await log_command(bot, LOG_CHANNEL_ID, f"🗑️ {interaction.user.mention} ha rimosso lo zaino a {utente.mention}")

        except Exception as e:
            print(f"Errore durante /rimuovi-zaino: {e}")
            await interaction.followup.send("❌ Si è verificato un errore durante la rimozione dello zaino.", ephemeral=True)


    # ===================================================
    # COMANDO: /crea-item (STAFF)
    # Crea un item e lo aggiunge allo shop (tabella items)
    # ===================================================
    @bot.tree.command(name="crea-item", description="[Staff] Aggiunge un item all'Item Shop")
    @app_commands.describe(
        nome_item="Nome dell'item (es: Pistola Legale)",
        prezzo="Prezzo di vendita dell'item",
        ruolo_necessario="Ruolo richiesto per l'acquisto (es: @Armeria) (default: Nessuno)"
    )
    async def creaitem(interaction: discord.Interaction, nome_item: str, prezzo: int, ruolo_necessario: discord.Role = None):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo **staff** può usare questo comando!", ephemeral=True)
            return
        
        if prezzo <= 0:
            await interaction.response.send_message("❌ Il prezzo deve essere un numero positivo.", ephemeral=True)
            return

        role_id = ruolo_necessario.id if ruolo_necessario else 0 # 0 = Nessun Ruolo

        try:
            await add_item_to_shop(nome_item, prezzo, role_id)
            
            role_text = ruolo_necessario.mention if ruolo_necessario else "Nessuno"
            
            embed = discord.Embed(
                title="✅ Item Aggiunto all'Item Shop",
                color=discord.Color.green()
            )
            embed.add_field(name="Nome Item", value=nome_item, inline=False)
            embed.add_field(name="Prezzo", value=f"${prezzo:,}", inline=True)
            embed.add_field(name="Ruolo Necessario", value=role_text, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await log_command(bot, LOG_CHANNEL_ID, f"🆕 {interaction.user.mention} ha creato l'item '{nome_item}' per lo shop.")

        except aiosqlite.IntegrityError:
            await interaction.response.send_message(f"❌ L'item **{nome_item}** esiste già nell'Item Shop.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Errore durante la creazione dell'item: {e}", ephemeral=True)


    # ===================================================
    # COMANDO: /elimina-item (STAFF)
    # Rimuove un item dallo shop (tabella items)
    # ===================================================
    @bot.tree.command(name="elimina-item", description="[Staff] Rimuove un item dall'Item Shop")
    @app_commands.describe(nome_item="Nome dell'item da rimuovere (deve essere esatto)")
    async def eliminaitem(interaction: discord.Interaction, nome_item: str):
        if not has_role(interaction, STAFF_ROLE_ID):
            await interaction.response.send_message("❌ Solo lo **staff** può usare questo comando!", ephemeral=True)
            return
            
        try:
            removed = await remove_item_from_shop(nome_item)
            
            if removed:
                await interaction.response.send_message(f"✅ Item **{nome_item}** rimosso con successo dall'Item Shop.", ephemeral=True)
                await log_command(bot, LOG_CHANNEL_ID, f"🗑️ {interaction.user.mention} ha rimosso l'item '{nome_item}' dallo shop.")
            else:
                await interaction.response.send_message(f"❌ L'item **{nome_item}** non è stato trovato nell'Item Shop.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Errore durante l'eliminazione dell'item: {e}", ephemeral=True)


    # ===================================================
    # COMANDO: /item-shop (PUBBLICO)
    # Mostra gli item disponibili
    # ===================================================
    @bot.tree.command(name="item-shop", description="Visualizza gli item disponibili per l'acquisto")
    async def itemshop(interaction: discord.Interaction):
        
        await interaction.response.defer(ephemeral=False, thinking=True)
        
        shop_items = await get_shop_items()
        
        if not shop_items:
            await interaction.followup.send("❌ L'Item Shop è attualmente vuoto. Riprova più tardi.", ephemeral=False)
            return
            
        embed = discord.Embed(
            title="🛒 Item Shop",
            description="Ecco gli item disponibili per l'acquisto (da Market/Armerie, ecc.).",
            color=discord.Color.blue()
        )
        
        for name, price, role_id_str in shop_items:
            role_id = int(role_id_str)
            role_text = f"Necessario: <@&{role_id}>" if role_id != 0 else "Nessun requisito di ruolo"
            
            embed.add_field(
                name=f"**{name}**",
                value=f"**Prezzo:** ${price:,}\n{role_text}",
                inline=True
            )
        
        # Puoi aggiungere una nota su come acquistare, ad esempio:
        embed.set_footer(text="Per acquistare, recati al Market o al venditore appropriato e usa il comando /vendi-item.")
        
        await interaction.followup.send(embed=embed, ephemeral=False)


    # ===================================================
    # COMANDO: /trasferisci (Mantenuto per la logica di base)
    # ===================================================
    @bot.tree.command(name="trasferisci", description="Trasferisci un item del tuo zaino a un altro utente")
    @app_commands.describe(
        utente="L'utente a cui trasferire l'item",
        nome_item="Il nome dell'item da trasferire",
        quantita="La quantità da trasferire (default 1)"
    )
    async def trasferisci(interaction: discord.Interaction, utente: discord.Member, nome_item: str, quantita: int = 1):
        
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        sender_id = str(interaction.user.id)
        receiver_id = str(utente.id)
        
        # 1. Controllo quantità e utente
        if quantita <= 0:
            await interaction.followup.send("❌ La quantità deve essere positiva.", ephemeral=True)
            return
        if utente.bot:
            await interaction.followup.send("❌ Non puoi trasferire item a un bot.", ephemeral=True)
            return

        # 2. Logica Zaino e Quantità Disponibile (da completare con la tua logica inventory)
        # Esempio di logica (Dovrebbe essere più robusta, ma è un placeholder)
        
        sender_inventory = None # Dovresti implementare una funzione get_user_inventory(sender_id)
        
        # Simuliamo il controllo dello zaino (Assumi che get_user_economy sia già implementato)
        sender_economy = await get_user_economy(sender_id)
        receiver_economy = await get_user_economy(receiver_id)
        
        sender_backpack = sender_economy[2] if sender_economy else 0
        receiver_backpack = receiver_economy[2] if receiver_economy else 0
        
        if sender_backpack == 0:
            await interaction.followup.send("❌ Non hai uno zaino! Non puoi trasferire item.", ephemeral=True)
            return
            
        if receiver_backpack == 0:
            await interaction.followup.send(f"❌ {utente.mention} non ha uno zaino in cui ricevere l'item!", ephemeral=True)
            return

        # *** Questa parte necessita di una funzione `get_item_quantity(user_id, item_name)` ***
        # Per ora, si assume che se l'utente ha uno zaino, possa trasferire.
        # Devi implementare la logica per verificare che l'utente abbia l'item e la quantità richiesta.
        
        try:
            # 3. Trasferimento: Rimuovi dal mittente
            # Implementare un controllo per assicurarsi che la quantità sia disponibile prima di rimuovere
            await update_inventory(sender_id, nome_item, quantita, mode='remove')
            
            # 4. Trasferimento: Aggiungi al destinatario
            await update_inventory(receiver_id, nome_item, quantita, mode='add')
        
        except Exception as e:
            # Questo catcher intercetta, ad esempio, errori se la quantità da rimuovere è maggiore di quella posseduta
            await interaction.followup.send(f"❌ Errore: non hai abbastanza **{nome_item}** per il trasferimento (o errore DB).", ephemeral=True)
            print(f"Errore trasferimento: {e}")
            return
        
        # 5. Risposta e Log
        
        # Messaggio in DM al destinatario
        try:
            embed = discord.Embed(
                title="🎁 Oggetto Ricevuto!",
                description=f"Hai ricevuto **{quantita}**x **{nome_item}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="Donatore", value=interaction.user.mention, inline=False)
            embed.set_footer(text="Controlla il tuo zaino con /invzaino.")
            await utente.send(embed=embed)
        except:
            pass
            
        await interaction.followup.send(
            f"✅ Hai dato **{quantita}**x **{nome_item}** a {utente.mention} con successo!", 
            ephemeral=True
        )

        log_msg = f"➡️ {interaction.user.mention} ha dato {quantita}x {nome_item} a {utente.mention}"
        await log_command(bot, LOG_CHANNEL_ID, log_msg)


    # ===================================================
    # COMANDO: /invzaino (Placeholder)
    # ===================================================
    @bot.tree.command(name="invzaino", description="Visualizza il tuo zaino e gli item al suo interno")
    async def invzaino(interaction: discord.Interaction):
        await interaction.response.send_message("🎒 Comando /invzaino in fase di implementazione. Mostrerà il tuo inventario.", ephemeral=True)

