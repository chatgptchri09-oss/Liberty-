import aiosqlite
from constants import DATABASE_NAME

async def init_db():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                cash    INTEGER DEFAULT 0,
                bank    INTEGER DEFAULT 0,
                hunger  INTEGER DEFAULT 100,
                thirst  INTEGER DEFAULT 100
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                user_id   TEXT,
                item_name TEXT,
                quantity  INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, item_name)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                user_id       TEXT PRIMARY KEY,
                nome          TEXT,
                cognome       TEXT,
                eta           INTEGER,
                sesso         TEXT,
                luogo_nascita TEXT,
                foto_url      TEXT DEFAULT NULL,
                extra         TEXT DEFAULT NULL,
                created_at    TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fines (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT,
                amount     INTEGER,
                reason     TEXT,
                issued_by  TEXT,
                paid       INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS criminal_records (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT,
                crime      TEXT,
                sentence   TEXT,
                officer    TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       TEXT,
                property_name TEXT,
                property_type TEXT,
                location      TEXT,
                created_at    TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user   TEXT,
                to_user     TEXT,
                amount      INTEGER,
                description TEXT,
                paid        INTEGER DEFAULT 0,
                created_at  TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fondocassa (
                company TEXT PRIMARY KEY,
                amount  INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS arrests (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT,
                reason     TEXT,
                duration   TEXT,
                officer    TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shop_items (
                item_name     TEXT PRIMARY KEY,
                price         INTEGER,
                description   TEXT,
                required_role INTEGER DEFAULT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS weapon_durability (
                user_id       TEXT NOT NULL,
                item_name     TEXT NOT NULL,
                usura         INTEGER DEFAULT 100,
                last_decay_ts REAL DEFAULT 0,
                PRIMARY KEY (user_id, item_name)
            )
        """)

        # Upgrade sicuro su db già esistenti
        for stmt in [
            "ALTER TABLE users ADD COLUMN hunger INTEGER DEFAULT 100",
            "ALTER TABLE users ADD COLUMN thirst INTEGER DEFAULT 100",
            "ALTER TABLE documents ADD COLUMN foto_url TEXT DEFAULT NULL",
            "ALTER TABLE documents ADD COLUMN extra TEXT DEFAULT NULL",
            "ALTER TABLE shop_items ADD COLUMN required_role INTEGER DEFAULT NULL",
            "ALTER TABLE weapon_durability ADD COLUMN last_decay_ts REAL DEFAULT 0",
        ]:
            try:
                await db.execute(stmt)
            except Exception:
                pass

        await db.commit()
    print("✅ Database RDR2 inizializzato", flush=True)


# ── UTENTI ────────────────────────────────────────────────────────────────────

async def get_user(user_id: str) -> dict:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO users (user_id,cash,bank,hunger,thirst) VALUES (?,50,0,100,100)",
                    (user_id,)
                )
                await db.commit()
                return {"user_id": user_id, "cash": 50, "bank": 0, "hunger": 100, "thirst": 100}
            return dict(row)

async def update_balance(user_id: str, cash: int = None, bank: int = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if cash is not None and bank is not None:
            await db.execute("UPDATE users SET cash=?,bank=? WHERE user_id=?", (cash, bank, user_id))
        elif cash is not None:
            await db.execute("UPDATE users SET cash=? WHERE user_id=?", (cash, user_id))
        elif bank is not None:
            await db.execute("UPDATE users SET bank=? WHERE user_id=?", (bank, user_id))
        await db.commit()

async def update_hunger_thirst(user_id: str, hunger: int = None, thirst: int = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if hunger is not None and thirst is not None:
            await db.execute(
                "UPDATE users SET hunger=?,thirst=? WHERE user_id=?",
                (max(0,min(100,hunger)), max(0,min(100,thirst)), user_id)
            )
        elif hunger is not None:
            await db.execute("UPDATE users SET hunger=? WHERE user_id=?", (max(0,min(100,hunger)), user_id))
        elif thirst is not None:
            await db.execute("UPDATE users SET thirst=? WHERE user_id=?", (max(0,min(100,thirst)), user_id))
        await db.commit()


# ── INVENTARIO ────────────────────────────────────────────────────────────────

async def get_inventory(user_id: str) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM inventory WHERE user_id=? AND quantity>0", (user_id,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def add_item(user_id: str, item_name: str, quantity: int = 1):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO inventory (user_id,item_name,quantity) VALUES (?,?,?)
            ON CONFLICT(user_id,item_name) DO UPDATE SET quantity=quantity+?
        """, (user_id, item_name, quantity, quantity))
        await db.commit()

async def remove_item(user_id: str, item_name: str, quantity: int = 1) -> bool:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?", (user_id, item_name)
        ) as c:
            row = await c.fetchone()
            if not row or row["quantity"] < quantity:
                return False
        await db.execute(
            "UPDATE inventory SET quantity=quantity-? WHERE user_id=? AND item_name=?",
            (quantity, user_id, item_name)
        )
        await db.commit()
        return True

async def get_item_quantity(user_id: str, item_name: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT quantity FROM inventory WHERE user_id=? AND item_name=?", (user_id, item_name)
        ) as c:
            row = await c.fetchone()
            return row[0] if row else 0


# ── SHOP ──────────────────────────────────────────────────────────────────────

async def get_shop_items() -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM shop_items ORDER BY price ASC") as c:
            return [dict(r) for r in await c.fetchall()]

async def get_shop_item(name: str) -> dict | None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM shop_items WHERE item_name=?", (name,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None

async def upsert_shop_item(name: str, price: int, description: str, required_role: int = None):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO shop_items (item_name,price,description,required_role) VALUES (?,?,?,?)
            ON CONFLICT(item_name) DO UPDATE SET price=?,description=?,required_role=?
        """, (name, price, description, required_role, price, description, required_role))
        await db.commit()

async def delete_shop_item(name: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM shop_items WHERE item_name=?", (name,))
        await db.commit()


# ── TAGLIE / MULTE ────────────────────────────────────────────────────────────

async def add_fine(user_id: str, amount: int, reason: str, issued_by: str):
    from datetime import datetime
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO fines (user_id,amount,reason,issued_by,paid,created_at) VALUES (?,?,?,?,0,?)",
            (user_id, amount, reason, issued_by, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()

async def get_fines(user_id: str) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fines WHERE user_id=? AND paid=0", (user_id,)) as c:
            return [dict(r) for r in await c.fetchall()]

async def pay_fine(fine_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("UPDATE fines SET paid=1 WHERE id=?", (fine_id,))
        await db.commit()


# ── FEDINA PENALE ─────────────────────────────────────────────────────────────

async def add_criminal_record(user_id: str, crime: str, sentence: str, officer: str):
    from datetime import datetime
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO criminal_records (user_id,crime,sentence,officer,created_at) VALUES (?,?,?,?,?)",
            (user_id, crime, sentence, officer, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()

async def get_criminal_records(user_id: str) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM criminal_records WHERE user_id=? ORDER BY id DESC", (user_id,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def clear_criminal_record(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM criminal_records WHERE user_id=?", (user_id,))
        await db.commit()


# ── DOCUMENTI ─────────────────────────────────────────────────────────────────

async def set_document(user_id: str, nome: str, cognome: str, eta: int,
                       sesso: str, luogo_nascita: str, foto_url: str = None,
                       extra: dict = None):
    import json
    from datetime import datetime
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO documents
                (user_id,nome,cognome,eta,sesso,luogo_nascita,foto_url,extra,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                nome=excluded.nome, cognome=excluded.cognome, eta=excluded.eta,
                sesso=excluded.sesso, luogo_nascita=excluded.luogo_nascita,
                foto_url=excluded.foto_url, extra=excluded.extra,
                created_at=excluded.created_at
        """, (user_id, nome, cognome, eta, sesso, luogo_nascita, foto_url, extra_json,
              datetime.utcnow().strftime("%d/%m/%Y %H:%M")))
        await db.commit()

async def get_document(user_id: str) -> dict | None:
    import json
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM documents WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("extra") and isinstance(d["extra"], str):
                try:
                    d["extra"] = json.loads(d["extra"])
                except Exception:
                    d["extra"] = {}
            return d


# ── PROPRIETÀ ─────────────────────────────────────────────────────────────────

async def add_property(user_id: str, property_name: str, property_type: str, location: str):
    from datetime import datetime
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO properties (user_id,property_name,property_type,location,created_at) VALUES (?,?,?,?,?)",
            (user_id, property_name, property_type, location, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()

async def get_properties(user_id: str) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM properties WHERE user_id=?", (user_id,)) as c:
            return [dict(r) for r in await c.fetchall()]


# ── FATTURE ───────────────────────────────────────────────────────────────────

async def add_invoice(from_user: str, to_user: str, amount: int, description: str) -> int:
    from datetime import datetime
    async with aiosqlite.connect(DATABASE_NAME) as db:
        c = await db.execute(
            "INSERT INTO invoices (from_user,to_user,amount,description,paid,created_at) VALUES (?,?,?,?,0,?)",
            (from_user, to_user, amount, description, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()
        return c.lastrowid

async def get_invoice(invoice_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None

async def get_invoices_by_user(user_id: str) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM invoices WHERE to_user=? AND paid=0 ORDER BY id ASC", (user_id,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def pay_invoice(invoice_id: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("UPDATE invoices SET paid=1 WHERE id=?", (invoice_id,))
        await db.commit()

async def get_all_users_sorted() -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, cash, bank FROM users WHERE user_id != 'STATO' ORDER BY (cash+bank) DESC"
        ) as c:
            return [dict(r) for r in await c.fetchall()]


# ── FONDO CASSA ───────────────────────────────────────────────────────────────

async def get_fondocassa(company: str) -> int:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT amount FROM fondocassa WHERE company=?", (company,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0

async def update_fondocassa(company: str, amount: int):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            INSERT INTO fondocassa (company,amount) VALUES (?,?)
            ON CONFLICT(company) DO UPDATE SET amount=?
        """, (company, amount, amount))
        await db.commit()


# ── ARRESTI ───────────────────────────────────────────────────────────────────

async def add_arrest(user_id: str, reason: str, duration: str, officer: str):
    from datetime import datetime
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            "INSERT INTO arrests (user_id,reason,duration,officer,created_at) VALUES (?,?,?,?,?)",
            (user_id, reason, duration, officer, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()


# ── TURNI ATTIVI ──────────────────────────────────────────────────────────────

async def save_turno(user_id: str, role_id: int, role_name: str, stipendio: int, inizio_ts: float):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS turni_attivi (
                user_id   TEXT PRIMARY KEY,
                role_id   INTEGER,
                role_name TEXT,
                stipendio INTEGER,
                inizio_ts REAL
            )
        """)
        await db.execute("""
            INSERT INTO turni_attivi (user_id, role_id, role_name, stipendio, inizio_ts)
            VALUES (?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                role_id=excluded.role_id, role_name=excluded.role_name,
                stipendio=excluded.stipendio, inizio_ts=excluded.inizio_ts
        """, (user_id, role_id, role_name, stipendio, inizio_ts))
        await db.commit()

async def delete_turno(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS turni_attivi (
                user_id TEXT PRIMARY KEY, role_id INTEGER,
                role_name TEXT, stipendio INTEGER, inizio_ts REAL
            )
        """)
        await db.execute("DELETE FROM turni_attivi WHERE user_id=?", (user_id,))
        await db.commit()

async def get_all_turni() -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS turni_attivi (
                user_id   TEXT PRIMARY KEY,
                role_id   INTEGER,
                role_name TEXT,
                stipendio INTEGER,
                inizio_ts REAL
            )
        """)
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM turni_attivi") as c:
            return [dict(r) for r in await c.fetchall()]

async def get_turno(user_id: str) -> dict | None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS turni_attivi (
                user_id TEXT PRIMARY KEY, role_id INTEGER,
                role_name TEXT, stipendio INTEGER, inizio_ts REAL
            )
        """)
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM turni_attivi WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


# ── OGGETTI NASCOSTI ──────────────────────────────────────────────────────────

async def init_hidden_items_table():
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hidden_items (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL,
                item_name  TEXT NOT NULL,
                quantity   INTEGER DEFAULT 1,
                luogo      TEXT,
                created_at TEXT
            )
        """)
        await db.commit()

async def hide_item(user_id: str, item_name: str, quantity: int, luogo: str) -> int:
    from datetime import datetime
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hidden_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL, item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1, luogo TEXT, created_at TEXT
            )
        """)
        c = await db.execute(
            "INSERT INTO hidden_items (user_id, item_name, quantity, luogo, created_at) VALUES (?,?,?,?,?)",
            (user_id, item_name, quantity, luogo, datetime.utcnow().strftime("%d/%m/%Y %H:%M"))
        )
        await db.commit()
        return c.lastrowid

async def get_hidden_items(user_id: str) -> list:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hidden_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL, item_name TEXT NOT NULL,
                quantity INTEGER DEFAULT 1, luogo TEXT, created_at TEXT
            )
        """)
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM hidden_items WHERE user_id=? ORDER BY id ASC", (user_id,)
        ) as c:
            return [dict(r) for r in await c.fetchall()]

async def recover_hidden_item(hide_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM hidden_items WHERE id=?", (hide_id,)) as c:
            row = await c.fetchone()
            if not row:
                return None
            item = dict(row)
        await db.execute("DELETE FROM hidden_items WHERE id=?", (hide_id,))
        await db.commit()
        return item


# ── WIPE ──────────────────────────────────────────────────────────────────────

async def wipe_user(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        for t in ("users","inventory","documents","fines","criminal_records","properties","arrests"):
            await db.execute(f"DELETE FROM {t} WHERE user_id=?", (user_id,))
        await db.execute(
            "INSERT INTO users (user_id,cash,bank,hunger,thirst) VALUES (?,50,0,100,100)", (user_id,)
        )
        await db.commit()


# ── DOCUMENTI FALSI ───────────────────────────────────────────────────────────

async def set_fake_document(user_id: str, nome: str, cognome: str, eta: int,
                            sesso: str, luogo_nascita: str, foto_url: str = None,
                            extra: dict = None):
    import json
    from datetime import datetime
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fake_documents (
                user_id       TEXT PRIMARY KEY,
                nome          TEXT,
                cognome       TEXT,
                eta           INTEGER,
                sesso         TEXT,
                luogo_nascita TEXT,
                foto_url      TEXT,
                extra         TEXT DEFAULT NULL,
                created_at    TEXT
            )
        """)
        await db.execute("""
            INSERT INTO fake_documents
                (user_id,nome,cognome,eta,sesso,luogo_nascita,foto_url,extra,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                nome=excluded.nome, cognome=excluded.cognome, eta=excluded.eta,
                sesso=excluded.sesso, luogo_nascita=excluded.luogo_nascita,
                foto_url=excluded.foto_url, extra=excluded.extra,
                created_at=excluded.created_at
        """, (user_id, nome, cognome, eta, sesso, luogo_nascita, foto_url, extra_json,
              datetime.utcnow().strftime("%d/%m/%Y %H:%M")))
        await db.commit()

async def get_fake_document(user_id: str) -> dict | None:
    import json
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fake_documents (
                user_id TEXT PRIMARY KEY, nome TEXT, cognome TEXT, eta INTEGER,
                sesso TEXT, luogo_nascita TEXT, foto_url TEXT,
                extra TEXT DEFAULT NULL, created_at TEXT
            )
        """)
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM fake_documents WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get("extra") and isinstance(d["extra"], str):
                try:
                    d["extra"] = json.loads(d["extra"])
                except Exception:
                    d["extra"] = {}
            return d

async def delete_fake_document(user_id: str):
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM fake_documents WHERE user_id=?", (user_id,))
        await db.commit()
