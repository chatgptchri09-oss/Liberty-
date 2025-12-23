import aiosqlite
import asyncio

DATABASE_NAME = "economy_bot.db"

async def fix_work_shifts_table():
    """Sistema la tabella work_shifts aggiungendo la colonna hourly_salary"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            # Prova ad aggiungere la colonna
            await db.execute("ALTER TABLE work_shifts ADD COLUMN hourly_salary INTEGER DEFAULT 0")
            await db.commit()
            print("✅ Colonna 'hourly_salary' aggiunta con successo!")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("⚠️ La colonna 'hourly_salary' esiste già!")
            else:
                print(f"❌ Errore: {e}")
                print("\n🔧 Provo a ricreare la tabella...")
                
                # Backup dei dati esistenti
                async with db.execute("SELECT user_id, role_id, start_time FROM work_shifts") as cursor:
                    old_data = await cursor.fetchall()
                
                # Elimina la vecchia tabella
                await db.execute("DROP TABLE IF EXISTS work_shifts")
                
                # Crea la nuova tabella con la colonna corretta
                await db.execute("""
                    CREATE TABLE work_shifts (
                        user_id TEXT,
                        role_id TEXT,
                        start_time TEXT,
                        hourly_salary INTEGER DEFAULT 0,
                        PRIMARY KEY (user_id, role_id)
                    )
                """)
                
                # Ripristina i dati (con hourly_salary = 0 per i vecchi turni)
                for user_id, role_id, start_time in old_data:
                    await db.execute(
                        "INSERT INTO work_shifts (user_id, role_id, start_time, hourly_salary) VALUES (?, ?, ?, ?)",
                        (user_id, role_id, start_time, 0)
                    )
                
                await db.commit()
                print("✅ Tabella work_shifts ricreata con successo!")
                print(f"✅ {len(old_data)} turni attivi ripristinati")

# Esegui lo script
asyncio.run(fix_work_shifts_table())
