import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = "8158476912:AAFGaToEfn9YnyzPgKNg3S95Qvt3CxQSBXE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# O'yin holatlarini saqlash uchun lug'at
games = {}

BASE_ROLES = ["Mafiya", "Komissar", "Doktor", "Fuqaro", "Fuqaro", "Mafiya"]

# --- YORDAMCHI FUNKSIYALAR ---

def get_alive_players_keyboard(chat_id, action_type):
    """Tirik o'yinchilar ro'yxatidan inline tugmalar yasash"""
    keyboard = []
    players = games[chat_id]["players"]
    
    for p_id, p_info in players.items():
        if p_info["alive"]:
            # Callback ma'lumot formati: harakat:guruh_id:nishon_id
            callback_data = f"{action_type}:{chat_id}:{p_id}"
            keyboard.append([InlineKeyboardButton(text=p_info["name"], callback_data=callback_data)])
            
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def check_victory(chat_id):
    """G'alaba shartlarini tekshirish"""
    players = games[chat_id]["players"]
    mafia_count = sum(1 for p in players.values() if p["alive"] and p["role"] == "Mafiya")
    citizen_count = sum(1 for p in players.values() if p["alive"] and p["role"] != "Mafiya")
    
    if mafia_count == 0:
        await bot.send_message(chat_id, "🏆 **FUQAROLAR G'ALABA QOZONDI!**\nBarcha mafiyalar yo'q qilindi.")
        games[chat_id]["status"] = "finished"
        return True
    elif mafia_count >= citizen_count:
        await bot.send_message(chat_id, "🏆 **MAFIYA G'ALABA QOZONDI!**\nShahar butunlay mafiya qo'liga o'tdi.")
        games[chat_id]["status"] = "finished"
        return True
    return False

# --- ASOSIY BUYRUQLAR ---

@dp.message(Command("newgame"))
async def cmd_newgame(message: Message):
    chat_id = message.chat.id
    games[chat_id] = {
        "status": "waiting",
        "players": {},
        "night_actions": {"mafia": None, "doctor": None, "commissar": None},
        "votes": {}
    }
    await message.answer("🎮 **Yangi Mafia o'yini ochildi!**\nQo'shilish uchun /join buyrug'ini yuboring.")

@dp.message(Command("join"))
async def cmd_join(message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if chat_id not in games or games[chat_id]["status"] != "waiting":
        return await message.answer("❌ O'yin kutilmayapti.")

    if user.id in games[chat_id]["players"]:
        return await message.answer("Siz allaqachon qo'shilgansiz.")

    games[chat_id]["players"][user.id] = {"name": user.first_name, "role": None, "alive": True}
    await message.answer(f"👤 **{user.first_name}** qo'shildi! Jami: {len(games[chat_id]['players'])} ta.")

@dp.message(Command("startgame"))
async def cmd_startgame(message: Message):
    chat_id = message.chat.id
    if chat_id not in games or len(games[chat_id]["players"]) < 4:
        return await message.answer("❌ O'yin boshlash uchun kamida 4 kishi kerak!")

    await message.answer("🎲 Rollar tarqatilmoqda...")
    player_ids = list(games[chat_id]["players"].keys())
    random.shuffle(player_ids)
    
    game_roles = BASE_ROLES[:len(player_ids)]
    while len(game_roles) < len(player_ids):
        game_roles.append("Fuqaro")

    for i, p_id in enumerate(player_ids):
        games[chat_id]["players"][p_id]["role"] = game_roles[i]
        try:
            await bot.send_message(p_id, f"🎭 Sizning rolingiz: **{game_roles[i]}**")
        except Exception:
            await message.answer(f"⚠️ {games[chat_id]['players'][p_id]['name']} botga /start bosmagan!")

    await start_night(chat_id)

# --- BOSQICHLAR: KECHA ---

async def start_night(chat_id):
    games[chat_id]["status"] = "night"
    games[chat_id]["night_actions"] = {"mafia": None, "doctor": None, "commissar": None}
    
    await bot.send_message(chat_id, "🌙 **Kecha tushdi. Shahar uyquga ketdi...**")

    # Rollarga shaxsiy xabarda tugma yuborish
    players = games[chat_id]["players"]
    for p_id, p_info in players.items():
        if not p_info["alive"]:
            continue
            
        if p_info["role"] == "Mafiya":
            await bot.send_message(p_id, "🔪 Kimni o'ldirmoqchisiz?", reply_markup=get_alive_players_keyboard(chat_id, "mafia_kill"))
        elif p_info["role"] == "Doktor":
            await bot.send_message(p_id, "❤️ Kimni davolamoqchisiz?", reply_markup=get_alive_players_keyboard(chat_id, "doc_heal"))
        elif p_info["role"] == "Komissar":
            await bot.send_message(p_id, "👮 Kimni tekshirmoqchisiz?", reply_markup=get_alive_players_keyboard(chat_id, "com_check"))

    # Kechasi amallarni bajarish uchun 40 soniya vaqt (test uchun qisqartirish mumkin)
    await asyncio.sleep(40)
    if games[chat_id]["status"] == "night":
        await end_night(chat_id)

# --- KECHASI TUGMALARNI QABUL QILISH ---

@dp.callback_query(F.data.startswith("mafia_kill:"))
async def process_mafia(callback: CallbackQuery):
    _, chat_id, target_id = callback.data.split(":")
    games[int(chat_id)]["night_actions"]["mafia"] = int(target_id)
    await callback.message.edit_text("🎯 Tanlov qabul qilindi. Sheriklaringiz ovozini kuting (agar bo'lsa).")

@dp.callback_query(F.data.startswith("doc_heal:"))
async def process_doctor(callback: CallbackQuery):
    _, chat_id, target_id = callback.data.split(":")
    games[int(chat_id)]["night_actions"]["doctor"] = int(target_id)
    await callback.message.edit_text("🏥 Davolash obyekti aniqlandi.")

@dp.callback_query(F.data.startswith("com_check:"))
async def process_commissar(callback: CallbackQuery):
    _, chat_id, target_id = callback.data.split(":")
    chat_id = int(chat_id)
    target_id = int(target_id)
    
    role = games[chat_id]["players"][target_id]["role"]
    result = "🔴 Mafiya!" if role == "Mafiya" else "🟢 Oddiy fuqaro/Tinch aholi."
    
    games[chat_id]["night_actions"]["commissar"] = target_id
    await callback.message.edit_text(f"🔍 Tekshiruv natijasi: {games[chat_id]['players'][target_id]['name']} — {result}")

# --- BOSQICHLAR: KUNDUZ VA OVOZ BERISH ---

async def end_night(chat_id):
    actions = games[chat_id]["night_actions"]
    players = games[chat_id]["players"]
    
    killed_id = actions["mafia"]
    healed_id = actions["doctor"]
    
    await bot.send_message(chat_id, "☀️ **Tong otdi! Shahar uyg'ondi.**")
    
    if killed_id and killed_id != healed_id:
        players[killed_id]["alive"] = False
        victim_name = players[killed_id]["name"]
        await bot.send_message(chat_id, f"💀 Kechasi mudhish qotillik yuz berdi. **{victim_name}** o'ldirildi!")
    else:
        await bot.send_message(chat_id, "🛡 Kechasi tinch o'tdi. Doktor kimnidir qutqarib qoldi!")

    if await check_victory(chat_id):
        return

    # Kunduzgi muhokama va ovoz berish
    games[chat_id]["status"] = "voting"
    games[chat_id]["votes"] = {}
    
    await bot.send_message(chat_id, "🗣 **Muhokama boshlandi (60 soniya).**\nSo'ng ovoz berish boshlanadi. Kimdan shubhalanasiz?", 
                           reply_markup=get_alive_players_keyboard(chat_id, "vote_player"))
    
    await asyncio.sleep(60)
    if games[chat_id]["status"] == "voting":
        await calculate_votes(chat_id)

@dp.callback_query(F.data.startswith("vote_player:"))
async def process_vote(callback: CallbackQuery):
    _, chat_id, target_id = callback.data.split(":")
    chat_id = int(chat_id)
    voter_id = callback.from_user.id
    
    # O'liklar ovoz bera olmaydi
    if not games[chat_id]["players"][voter_id]["alive"]:
        return await callback.answer("Siz o'lgansiz, ovoz bera olmaysiz!", show_alert=True)
        
    games[chat_id]["votes"][voter_id] = int(target_id)
    await callback.answer("Ovozingiz qabul qilindi!")

async def calculate_votes(chat_id):
    votes = games[chat_id]["votes"]
    players = games[chat_id]["players"]
    
    if not votes:
        await bot.send_message(chat_id, "💤 Hech kim ovoz bermadi. O'yin kecha bosqichiga qaytadi.")
        await start_night(chat_id)
        return

    # Ovozlarni hisoblash
    vote_counts = {}
    for target in votes.values():
        vote_counts[target] = vote_counts.get(target, 0) + 1
        
    # Eng ko'p ovoz olgan odamni topish
    sorted_votes = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
    expelled_id, max_votes = sorted_votes[0]
    
    expelled_name = players[expelled_id]["name"]
    expelled_role = players[expelled_id]["role"]
    
    players[expelled_id]["alive"] = False
    await bot.send_message(chat_id, f"⚖️ Ovoz berish yakunlandi.\nShahar qaroriga ko'ra **{expelled_name}** ({expelled_role}) quvildi!")
    
    if await check_victory(chat_id):
        return
        
    # Agar o'yin tugamasa, yana kechaga qaytiladi
    await start_night(chat_id)

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
