import aiosqlite
import json
from datetime import datetime

DATABASE_NAME = "economy_bot.db"

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        
        # ... tutte le tue tabelle esistenti ...
        
        # TABELLA PROPRIETÀ (NUOVA)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        
        await db.commit()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 20000,
                has_backpack INTEGER DEFAULT 0
            )
        """)
        
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS arrests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                nome_completo TEXT,
                eta TEXT,
                residenza TEXT,
                motivo TEXT,
                pena TEXT,
                created_at TEXT
            )
        """)
        
        await db.execute("""
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                name TEXT,
                surname TEXT,
                license_type TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gun_licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                name TEXT,
                surname TEXT,
                age TEXT,
                level TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS medical_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                patient_name TEXT,
                patient_surname TEXT,
                patient_age TEXT,
                result TEXT
            )
        """)
        
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                required_role_id TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id TEXT,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, item_name)
            )
        """)
        
        await db.execute("""
    CREATE TABLE IF NOT EXISTS work_shifts (
        user_id TEXT,
        role_id TEXT,
        start_time TEXT,
        PRIMARY KEY (user_id, role_id)
    )
""")
        
        await db.commit()

async def get_user(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"user_id": row[0], "cash": row[1], "bank": row[2], "has_backpack": row[3]}
            else:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return {"user_id": user_id, "cash": 0, "bank": 20000, "has_backpack": 0}

async def update_balance(user_id: str, cash: int = None, bank: int = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if cash is not None and bank is not None:
            await db.execute("UPDATE users SET cash = ?, bank = ? WHERE user_id = ?", (cash, bank, user_id))
        elif cash is not None:
            await db.execute("UPDATE users SET cash = ? WHERE user_id = ?", (cash, user_id))
        elif bank is not None:
            await db.execute("UPDATE users SET bank = ? WHERE user_id = ?", (bank, user_id))
        await db.commit()

async def create_invoice(client_id: str, sender_id: str, description: str, price: int, company: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO invoices (client_id, sender_id, description, price, company, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (client_id, sender_id, description, price, company, datetime.now().isoformat())
        )
        await db.commit()

async def get_unpaid_invoices(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, sender_id, description, price, company FROM invoices WHERE client_id = ? AND paid = 0",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def pay_invoice(invoice_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("UPDATE invoices SET paid = 1 WHERE id = ?", (invoice_id,))
        await db.commit()

async def get_invoice(invoice_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)) as cursor:
            return await cursor.fetchone()

async def create_fine(user_id: str, name: str, surname: str, age: str, infractions: str, fine_amount: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO fines (user_id, name, surname, age, infractions, fine_amount, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, name, surname, age, infractions, fine_amount, datetime.now().isoformat())
        )
        await db.commit()

async def get_unpaid_fines(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT id, name, surname, infractions, fine_amount FROM fines WHERE user_id = ? AND paid = 0",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

async def pay_fine(fine_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("UPDATE fines SET paid = 1 WHERE id = ?", (fine_id,))
        await db.commit()

async def get_fine(fine_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT * FROM fines WHERE id = ?", (fine_id,)) as cursor:
            return await cursor.fetchone()
