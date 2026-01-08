import asyncio
import os
from datetime import datetime
import base64
import aiohttp

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = "chatgptchri09-oss/liberty-bot-backups"  # ⚠️ CAMBIA CON IL TUO USERNAME!
DATABASE_NAME = "economy_bot.db"

async def backup_database():
    """Esegue backup automatico ogni 6 ore"""
    
    if not GITHUB_TOKEN:
        print("⚠️ GITHUB_TOKEN non trovato! Backup disabilitato.", flush=True)
        return
    
    while True:
        try:
            print(f"📦 Avvio backup del database...", flush=True)
            
            # Verifica che il file esista
            if not os.path.exists(DATABASE_NAME):
                print(f"⚠️ Database {DATABASE_NAME} non trovato. Riprovo tra 1 ora.", flush=True)
                await asyncio.sleep(60 * 60)
                continue
            
            # Leggi il database
            with open(DATABASE_NAME, 'rb') as f:
                db_data = f.read()
            
            # Converti in base64 (formato richiesto da GitHub)
            db_b64 = base64.b64encode(db_data).decode('utf-8')
            
            # Crea nome file con timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"backups/backup_{timestamp}.db"
            
            # Upload su GitHub
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            data = {
                "message": f"Backup automatico {timestamp}",
                "content": db_b64
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.put(url, json=data, headers=headers) as resp:
                    if resp.status == 201:
                        print(f"✅ Backup salvato con successo: {filename}", flush=True)
                    elif resp.status == 422:
                        print(f"⚠️ Backup già esistente o errore formato", flush=True)
                    else:
                        error_text = await resp.text()
                        print(f"❌ Errore backup (status {resp.status}): {error_text[:200]}", flush=True)
            
            # Attendi 6 ore prima del prossimo backup
            print(f"⏰ Prossimo backup tra 6 ore", flush=True)
            await asyncio.sleep(6 * 60 * 60)
            
        except FileNotFoundError:
            print(f"⚠️ File {DATABASE_NAME} non trovato. Riprovo tra 1 ora.", flush=True)
            await asyncio.sleep(60 * 60)
        except Exception as e:
            print(f"❌ Errore durante il backup: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # In caso di errore, riprova tra 1 ora
            await asyncio.sleep(60 * 60)
