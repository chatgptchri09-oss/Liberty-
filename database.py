import aiosqlite
import json
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

DATABASE_NAME = "economy_bot.db"

# ===================================================================================
# INIZIALIZZAZIONE DEL DATABASE
# ===================================================================================

async def init_db():
    """
    Inizializza tutte le tabelle del database.
    Questa è la funzione critica dove viene aggiunta la colonna 'weight'.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        
        # Tabella USERS (per denaro, banca, zaino)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 20000,
                has_backpack INTEGER DEFAULT 0
            )
        """)
        
        # Tabella INVOICES (fatture)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                sender_id TEXT,
                description TEXT,
                price INTEGER,
                company TEXT,
                paid INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        
        # Tabella FINES (multe)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                name TEXT,
                surname TEXT,
                age TEXT,
                infractions TEXT,
                fine_amount INTEGER,
                paid INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        
        # Tabella DOCUMENTS (documenti base)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                surname TEXT,
                birth_date TEXT,
                citizen_card_id TEXT UNIQUE
            )
        """)
        
        # Tabella VEHICLE_REGISTRATIONS (libretti auto)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_registrations (
                plate TEXT PRIMARY KEY,
                owner_id TEXT,
                model TEXT,
                color TEXT,
                insurance INTEGER DEFAULT 0,
                modifications TEXT DEFAULT '[]',
                seized INTEGER DEFAULT 0
            )
        """)
        
        # Tabella MEDICAL_CERTIFICATES (certificati medici)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS medical_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                client_name TEXT,
                client_surname TEXT,
                client_age TEXT,
                result TEXT
            )
        """)
        
        # Tabella BALLISTIC_CERTIFICATES (certificati balistici)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ballistic_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                client_name TEXT,
                client_surname TEXT,
                client_age TEXT,
                result TEXT
            )
        """)
        
        # Tabella WORK_SHIFTS (turni di lavoro)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS work_shifts (
                user_id TEXT,
                role_id TEXT,
                start_time TEXT,
                PRIMARY KEY (user_id, role_id)
            )
        """)
        
        # Tabella ITEMS (oggetti craftabili/acquistabili)
        # 🚨 LA MODIFICA CRITICA: AGGIUNTA DI 'weight REAL DEFAULT 0.0' 🚨
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                required_role_id TEXT,
                weight REAL DEFAULT 0.0
            )
        """)
        
        # Tabella USER_INVENTORY (inventario)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_inventory (
                user_id TEXT,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, item_name)
            )
        """)
        
        # Assicura che la colonna weight esista nella tabella ITEMS se il db è già popolato
        try:
            await db.execute("ALTER TABLE items ADD COLUMN weight REAL DEFAULT 0.0")
        except aiosqlite.OperationalError as e:
            # Ignora l'errore se la colonna esiste già (che è il comportamento atteso)
            if "duplicate column name: weight" not in str(e):
                raise e

        await db.commit()

# ===================================================================================
# FUNZIONI UTILITY UTENTE/DENARO
# ===================================================================================

async def ensure_user_exists(user_id: str):
    """Assicura che l'utente esista nella tabella users."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", 
            (user_id,)
        )
        await db.commit()

async def get_user_balance(user_id: str) -> Tuple[int, int]:
    """Recupera il saldo cash e bank dell'utente."""
    await ensure_user_exists(user_id)
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT cash, bank FROM users WHERE user_id = ?", 
            (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            return result if result else (0, 0)

async def update_user_balance(user_id: str, cash_change: int = 0, bank_change: int = 0) -> Tuple[int, int]:
    """Aggiorna il saldo cash e/o bank dell'utente."""
    await ensure_user_exists(user_id)
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if cash_change != 0:
            await db.execute(
                "UPDATE users SET cash = cash + ? WHERE user_id = ?", 
                (cash_change, user_id)
            )
        if bank_change != 0:
            await db.execute(
                "UPDATE users SET bank = bank + ? WHERE user_id = ?", 
                (bank_change, user_id)
            )
        await db.commit()
        return await get_user_balance(user_id)

# ===================================================================================
# FUNZIONI FATTURE (INVOICES)
# ===================================================================================

async def create_invoice(client_id: str, sender_id: str, description: str, price: int, company: str):
    """Crea una nuova fattura non pagata."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO invoices (client_id, sender_id, description, price, company, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (client_id, sender_id, description, price, company, datetime.now().isoformat())
        )
        await db.commit()

async def get_unpaid_invoices(client_id: str) -> List[Tuple]:
    """Recupera tutte le fatture non pagate per un cliente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, description, price, company, sender_id FROM invoices WHERE client_id = ? AND paid = 0",
            (client_id,)
        ) as cursor:
            return await cursor.fetchall()

async def pay_invoice(invoice_id: int):
    """Marca una fattura come pagata."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("UPDATE invoices SET paid = 1 WHERE id = ?", (invoice_id,))
        await db.commit()

async def get_invoice(invoice_id: int) -> Optional[Tuple]:
    """Recupera una fattura per ID."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)) as cursor:
            return await cursor.fetchone()

# ===================================================================================
# FUNZIONI MULTE (FINES)
# ===================================================================================

async def create_fine(user_id: str, name: str, surname: str, age: str, infractions: str, fine_amount: int):
    """Crea una nuova multa non pagata."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO fines (user_id, name, surname, age, infractions, fine_amount, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, surname, age, infractions, fine_amount, datetime.now().isoformat())
        )
        await db.commit()

async def get_unpaid_fines(user_id: str) -> List[Tuple]:
    """Recupera tutte le multe non pagate per un utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, name, surname, infractions, fine_amount FROM fines WHERE user_id = ? AND paid = 0",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def pay_fine(fine_id: int):
    """Marca una multa come pagata."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("UPDATE fines SET paid = 1 WHERE id = ?", (fine_id,))
        await db.commit()

async def get_fine(fine_id: int) -> Optional[Tuple]:
    """Recupera una multa per ID."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM fines WHERE id = ? AND paid = 0", (fine_id,)) as cursor:
            return await cursor.fetchone()

# ===================================================================================
# FUNZIONI DOCUMENTI
# ===================================================================================

async def create_document(user_id: str, name: str, surname: str, birth_date: str, citizen_card_id: str):
    """Crea o aggiorna un documento di identità."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO documents (user_id, name, surname, birth_date, citizen_card_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, surname, birth_date, citizen_card_id)
        )
        await db.commit()

async def get_document(user_id: str) -> Optional[Tuple]:
    """Recupera il documento di identità per user_id."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM documents WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def search_document_by_name(name: str, surname: str) -> List[Tuple]:
    """Cerca documenti per nome e cognome."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT * FROM documents WHERE name LIKE ? AND surname LIKE ?",
            (name, surname)
        ) as cursor:
            return await cursor.fetchall()

async def create_vehicle_registration(plate: str, owner_id: str, model: str, color: str):
    """Crea un nuovo libretto di circolazione."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO vehicle_registrations (plate, owner_id, model, color) VALUES (?, ?, ?, ?)",
            (plate, owner_id, model, color)
        )
        await db.commit()

async def get_vehicle_registrations_by_owner(owner_id: str) -> List[Tuple]:
    """Recupera tutti i libretti posseduti da un utente."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM vehicle_registrations WHERE owner_id = ?", (owner_id,)) as cursor:
            return await cursor.fetchall()

async def get_vehicle_registration(plate: str) -> Optional[Tuple]:
    """Recupera un libretto di circolazione per targa."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM vehicle_registrations WHERE plate = ?", (plate,)) as cursor:
            return await cursor.fetchone()

async def update_vehicle_insurance(plate: str, insured: int):
    """Aggiorna lo stato di assicurazione di un veicolo."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "UPDATE vehicle_registrations SET insurance = ? WHERE plate = ?",
            (insured, plate)
        )
        await db.commit()

async def create_medical_certificate(user_id: str, client_name: str, client_surname: str, client_age: str, result: str):
    """Crea o aggiorna un certificato medico."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO medical_certificates (user_id, client_name, client_surname, client_age, result) VALUES (?, ?, ?, ?, ?)",
            (user_id, client_name, client_surname, client_age, result)
        )
        await db.commit()

async def get_medical_certificate(user_id: str) -> Optional[Tuple]:
    """Recupera il certificato medico per user_id."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM medical_certificates WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

# ===================================================================================
# FUNZIONI TURNI DI LAVORO
# ===================================================================================

async def start_work_shift(user_id: str, role_id: str):
    """Avvia un turno di lavoro."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO work_shifts (user_id, role_id, start_time) VALUES (?, ?, ?)",
            (user_id, role_id, datetime.now().isoformat())
        )
        await db.commit()

async def get_active_work_shift(user_id: str, role_id: str) -> Optional[str]:
    """Controlla se un turno di lavoro è attivo e restituisce l'orario di inizio."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT start_time FROM work_shifts WHERE user_id = ? AND role_id = ?",
            (user_id, role_id)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

async def end_work_shift(user_id: str, role_id: str):
    """Termina un turno di lavoro."""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "DELETE FROM work_shifts WHERE user_id = ? AND role_id = ?",
            (user_id, role_id)
        )
        await db.commit()

# ... (Qui possono essere aggiunte altre funzioni per la gestione dell'inventario, 
# ma quelle per l'inventario sono più specifiche e le hai in commands_inventory.py)
