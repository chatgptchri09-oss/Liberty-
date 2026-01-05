import asyncpg
import json
import os
from datetime import datetime

# Pool di connessioni globale
_pool = None

async def get_pool():
    """Ottieni il pool di connessioni PostgreSQL"""
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("❌ DATABASE_URL non trovato nelle variabili d'ambiente!")
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10)
    return _pool

async def init_db():
    """Inizializza tutte le tabelle del database"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # TABELLA DEPOSITI FAZIONI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deposit_inventory (
                id SERIAL PRIMARY KEY,
                deposit_name TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                UNIQUE(deposit_name, item_name)
            )
        """)
        
        # TABELLA PROPRIETÀ
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                owner_name TEXT NOT NULL,
                owner_surname TEXT NOT NULL,
                owner_age TEXT NOT NULL,
                property_name TEXT NOT NULL,
                property_type TEXT NOT NULL,
                assigned_by TEXT NOT NULL,
                assigned_at TEXT NOT NULL
            )
        """)
        
        # TABELLA UTENTI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 20000,
                has_backpack INTEGER DEFAULT 0
            )
        """)
        
        # TABELLA FATTURE
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                client_id TEXT,
                sender_id TEXT,
                description TEXT,
                price INTEGER,
                company TEXT,
                paid INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        
        # TABELLA MULTE
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fines (
                id SERIAL PRIMARY KEY,
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
        
        # TABELLA ARRESTI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS arrests (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                nome_completo TEXT,
                eta TEXT,
                residenza TEXT,
                motivo TEXT,
                pena TEXT,
                created_at TEXT
            )
        """)
        
        # TABELLA DOCUMENTI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                surname TEXT,
                birth_date TEXT,
                birth_place TEXT,
                nationality TEXT,
                photo_url TEXT
            )
        """)
        
        # TABELLA PATENTI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                name TEXT,
                surname TEXT,
                license_type TEXT
            )
        """)
        
        # TABELLA PORTO D'ARMI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS gun_licenses (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                name TEXT,
                surname TEXT,
                age TEXT,
                level TEXT
            )
        """)
        
        # TABELLA VEICOLI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_registrations (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                client_name TEXT,
                client_surname TEXT,
                vehicle_model TEXT,
                plate TEXT,
                insurance INTEGER DEFAULT 0,
                modifications TEXT,
                seized INTEGER DEFAULT 0
            )
        """)
        
        # TABELLA CERTIFICATI MEDICI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS medical_certificates (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                patient_name TEXT,
                patient_surname TEXT,
                patient_age TEXT,
                result TEXT
            )
        """)
        
        # TABELLA CERTIFICATI BALISTICI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ballistic_certificates (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                client_name TEXT,
                client_surname TEXT,
                client_age TEXT,
                result TEXT
            )
        """)
        
        # TABELLA OGGETTI
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE,
                required_role_id TEXT
            )
        """)
        
        # TABELLA INVENTARIO
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id TEXT,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, item_name)
            )
        """)
        
        # TABELLA TURNI LAVORO
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS work_shifts (
                user_id TEXT,
                role_id TEXT,
                start_time TEXT,
                hourly_salary INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, role_id)
            )
        """)
        
    print("✅ Database PostgreSQL inizializzato con successo!", flush=True)

async def get_user(user_id: str):
    """Ottieni i dati di un utente"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if row:
            return {
                "user_id": row['user_id'],
                "cash": row['cash'],
                "bank": row['bank'],
                "has_backpack": row['has_backpack']
            }
        else:
            await conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
            return {"user_id": user_id, "cash": 0, "bank": 20000, "has_backpack": 0}

async def update_balance(user_id: str, cash: int = None, bank: int = None):
    """Aggiorna il saldo di un utente"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if cash is not None and bank is not None:
            await conn.execute("UPDATE users SET cash = $1, bank = $2 WHERE user_id = $3", cash, bank, user_id)
        elif cash is not None:
            await conn.execute("UPDATE users SET cash = $1 WHERE user_id = $2", cash, user_id)
        elif bank is not None:
            await conn.execute("UPDATE users SET bank = $1 WHERE user_id = $2", bank, user_id)

async def create_invoice(client_id: str, sender_id: str, description: str, price: int, company: str):
    """Crea una nuova fattura"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO invoices (client_id, sender_id, description, price, company, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
            client_id, sender_id, description, price, company, datetime.now().isoformat()
        )

async def get_unpaid_invoices(user_id: str):
    """Ottieni le fatture non pagate di un utente"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, sender_id, description, price, company FROM invoices WHERE client_id = $1 AND paid = 0",
            user_id
        )
        return [(row['id'], row['sender_id'], row['description'], row['price'], row['company']) for row in rows]

async def pay_invoice(invoice_id: int):
    """Marca una fattura come pagata"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE invoices SET paid = 1 WHERE id = $1", invoice_id)

async def get_invoice(invoice_id: int):
    """Ottieni i dati di una fattura"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM invoices WHERE id = $1", invoice_id)
        if row:
            return tuple(row.values())
        return None

async def create_fine(user_id: str, name: str, surname: str, age: str, infractions: str, fine_amount: int):
    """Crea una nuova multa"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO fines (user_id, name, surname, age, infractions, fine_amount, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            user_id, name, surname, age, infractions, fine_amount, datetime.now().isoformat()
        )

async def get_unpaid_fines(user_id: str):
    """Ottieni le multe non pagate di un utente"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, surname, infractions, fine_amount FROM fines WHERE user_id = $1 AND paid = 0",
            user_id
        )
        return [(row['id'], row['name'], row['surname'], row['infractions'], row['fine_amount']) for row in rows]

async def pay_fine(fine_id: int):
    """Marca una multa come pagata"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE fines SET paid = 1 WHERE id = $1", fine_id)

async def get_fine(fine_id: int):
    """Ottieni i dati di una multa"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM fines WHERE id = $1", fine_id)
        if row:
            return tuple(row.values())
        return None
