from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime

client = None
db = None

async def init_db():
    global client, db
    mongodb_url = os.getenv("MONGODB_URL")
    if not mongodb_url:
        print("❌ MONGODB_URL non trovato!", flush=True)
        return
    
    client = AsyncIOMotorClient(mongodb_url)
    db = client.liberty_bot
    print("✅ MongoDB connesso!", flush=True)

async def get_user(user_id: str):
    user = await db.users.find_one({"user_id": user_id})
    if user:
        return {
            "user_id": user["user_id"],
            "cash": user.get("cash", 0),
            "bank": user.get("bank", 20000),
            "has_backpack": user.get("has_backpack", 0)
        }
    else:
        await db.users.insert_one({
            "user_id": user_id,
            "cash": 0,
            "bank": 20000,
            "has_backpack": 0
        })
        return {"user_id": user_id, "cash": 0, "bank": 20000, "has_backpack": 0}

async def update_balance(user_id: str, cash: int = None, bank: int = None):
    update_data = {}
    if cash is not None:
        update_data["cash"] = cash
    if bank is not None:
        update_data["bank"] = bank
    
    if update_data:
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data},
            upsert=True
        )

async def create_invoice(client_id: str, sender_id: str, description: str, price: int, company: str):
    await db.invoices.insert_one({
        "client_id": client_id,
        "sender_id": sender_id,
        "description": description,
        "price": price,
        "company": company,
        "paid": 0,
        "created_at": datetime.utcnow().isoformat()
    })

async def get_unpaid_invoices(user_id: str):
    invoices = await db.invoices.find({"client_id": user_id, "paid": 0}).to_list(100)
    return [(inv["_id"], inv["sender_id"], inv["description"], inv["price"], inv["company"]) for inv in invoices]

async def pay_invoice(invoice_id):
    await db.invoices.update_one({"_id": invoice_id}, {"$set": {"paid": 1}})

async def get_invoice(invoice_id):
    return await db.invoices.find_one({"_id": invoice_id})

async def create_fine(user_id: str, name: str, surname: str, age: str, infractions: str, fine_amount: int):
    await db.fines.insert_one({
        "user_id": user_id,
        "name": name,
        "surname": surname,
        "age": age,
        "infractions": infractions,
        "fine_amount": fine_amount,
        "paid": 0,
        "created_at": datetime.utcnow().isoformat()
    })

async def get_unpaid_fines(user_id: str):
    fines = await db.fines.find({"user_id": user_id, "paid": 0}).to_list(100)
    return [(f["_id"], f["name"], f["surname"], f["infractions"], f["fine_amount"]) for f in fines]

async def pay_fine(fine_id):
    await db.fines.update_one({"_id": fine_id}, {"$set": {"paid": 1}})

async def get_fine(fine_id):
    return await db.fines.find_one({"_id": fine_id})
