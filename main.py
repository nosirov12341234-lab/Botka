import telebot
import sqlite3

# --- ASOSIY SOZLAMALAR ---
TOKEN = "8220266826:AAEdkHlhdJmi2HWMrANe9Ch-ky5vIDkkNxY"
ADMIN_ID = 8215108926
bot = telebot.TeleBot(TOKEN)

# --- BAZANI SOZLASH ---
def init_db():
    conn = sqlite3.connect('mega_bot.db')
    cursor = conn.cursor()
    # Foydalanuvchilar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, referrer_id INTEGER, ref_count INTEGER DEFAULT 0)''')
    # Kanallar jadvali
    cursor.execute('CREATE TABLE IF NOT EXISTS channels (channel_id TEXT PRIMARY KEY)')
    # Darajalar jadvali (AUTOINCREMENT xatosi tuzatildi)
    cursor.execute('''CREATE TABLE IF NOT EXISTS levels 
                      (level_id INTEGER PRIMARY KEY AUTOINCREMENT, req_count INTEGER, photo_id TEXT, description TEXT)''')
    conn.commit()
    conn.close()

# Kanallarni olish
def get_channels():
    conn = sqlite3.connect('mega_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM channels")
    ch = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ch

# Obunani tekshirish
def check_sub(user_id):
    channels = get_channels()
    if not channels: return True # Kanal yo'q bo'lsa o'tkazib yuboradi
    for ch in channels:
        try:
            status = bot.get_chat_member(ch, user_id).status
            if status in ['left', 'kicked']: return False
        except: continue
    return True

# --- ASOSIY START ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    conn = sqlite3.connect('mega_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        referrer = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        cursor.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer))
        conn.commit()
    conn.close()

    if check_sub(user_id):
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🎁 Sovrinli o'yin", "🛍 Xaridni boshlash")
        markup.add("👨‍💻 Admin bilan bog'lanish", "📊 Statistika")
        if user_id == ADMIN_ID: markup.add("⚙️ Admin Panel")
        bot.send_message(user_id, "Xaridni boshlang tugmasini bosib xarid qilishingiz mumkin. Shuningdek, sovrinli o'yinimizda qatnashishingizni istardik!", reply_markup=markup)
    else:
        show_sub_channels(user_id)

def show_sub_channels(user_id):
    channels = get_channels()
    markup = telebot.types.InlineKeyboardMarkup()
    for ch in channels:
        markup.add(telebot.types.InlineKeyboardButton("Kanalga a'zo bo'lish", url=f"https://t.me/{ch[1:]}"))
    markup.add(telebot.types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    bot.send_message(user_id, "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", reply_markup=markup)

# --- ADMIN PANEL ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"))
    markup.add(telebot.types.InlineKeyboardButton("🏆 Daraja qo'shish", callback_data="add_level"))
    bot.send_message(ADMIN_ID, "Boshqaruv paneli:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "add_channel")
def add_ch_prompt(call):
    msg = bot.send_message(ADMIN_ID, "Kanal linkini yuboring (Masalan: @kanal_nomi):")
    bot.register_next_step_handler(msg, save_channel)

def save_channel(message):
    conn = sqlite3.connect('mega_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO channels (channel_id) VALUES (?)", (message.text,))
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, "Kanal saqlandi!")

@bot.callback_query_handler(func=lambda call: call.data == "add_level")
def add_lvl_prompt(call):
    msg = bot.send_message(ADMIN_ID, "Necha referal kerak? (Masalan: 5):")
    bot.register_next_step_handler(msg, get_lvl_count)

def get_lvl_count(message):
    count = message.text
    msg = bot.send_message(ADMIN_ID, "Sovrin rasmini yuboring:")
    bot.register_next_step_handler(msg, get_lvl_photo, count)

def get_lvl_photo(message, count):
    if message.content_type == 'photo':
        photo_id = message.photo[-1].file_id
        msg = bot.send_message(ADMIN_ID, "Sovrin haqida izoh yozing:")
        bot.register_next_step_handler(msg, save_level, count, photo_id)
    else:
        bot.send_message(ADMIN_ID, "Rasm yubormadingiz!")

def save_level(message, count, photo_id):
    conn = sqlite3.connect('mega_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO levels (req_count, photo_id, description) VALUES (?, ?, ?)", (int(count), photo_id, message.text))
    conn.commit()
    conn.close()
    bot.send_message(ADMIN_ID, "Daraja qo'shildi!")

@bot.message_handler(func=lambda m: m.text == "🎁 Sovrinli o'yin")
def show_levels(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('mega_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT req_count, photo_id, description FROM levels ORDER BY req_count ASC")
    levels = cursor.fetchall()
    cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (user_id,))
    my_refs = cursor.fetchone()[0]
    conn.close()

    link = f"https://t.me/{(bot.get_me()).username}?start={user_id}"
    bot.send_message(user_id, f"📊 Referallaringiz: {my_refs}\n🔗 Link: {link}")

    for lvl in levels:
        bot.send_photo(user_id, lvl[1], caption=f"🎯 Maqsad: {lvl[0]} ta do'st\n📝 {lvl[2]}")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_callback(call):
    user_id = call.from_user.id
    if check_sub(user_id):
        conn = sqlite3.connect('mega_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        if res and res[0]:
            ref_id = res[0]
            cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE user_id=?", (ref_id,))
            conn.commit()
            
            cursor.execute("SELECT ref_count FROM users WHERE user_id=?", (ref_id,))
            new_count = cursor.fetchone()[0]
            cursor.execute("SELECT req_count FROM levels WHERE req_count=?", (new_count,))
            if cursor.fetchone():
                bot.send_message(ADMIN_ID, f"🔔 Sovrin! @{bot.get_chat(ref_id).username} ({ref_id}) {new_count} taga yetdi!")
        conn.close()
        bot.delete_message(user_id, call.message.message_id)
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "Kanalga a'zo bo'ling!", show_alert=True)

if __name__ == "__main__":
    init_db()
    print("Bot ishlamoqda...")
    bot.infinity_polling()
  
