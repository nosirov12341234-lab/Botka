import telebot
import sqlite3
from datetime import datetime

# --- SOZLAMALAR ---
TOKEN = "8220266826:AAEdkHlhdJmi2HWMrANe9Ch-ky5vIDkkNxY"
ADMIN_ID = 8215108926
bot = telebot.TeleBot(TOKEN)

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect('bonus_bot.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, referrer_id INTEGER, balance INTEGER DEFAULT 0, status TEXT DEFAULT 'pending')''')
    cursor.execute('CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY)')
    cursor.execute('''CREATE TABLE IF NOT EXISTS prizes 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, cost INTEGER, photo TEXT, gender TEXT)''')
    conn.commit()
    return conn

db = init_db()

# Kanallarni tekshirish
def check_sub(user_id):
    cursor = db.cursor()
    cursor.execute("SELECT id FROM channels")
    channels = cursor.fetchall()
    if not channels: return True
    for ch in channels:
        try:
            status = bot.get_chat_member(ch[0], user_id).status
            if status in ['left', 'kicked']: return False
        except:
            bot.send_message(ADMIN_ID, f"⚠️ Diqqat: Bot {ch[0]} kanalida admin emas!")
            return False
    return True

# --- ASOSIY MENYU ---
def main_menu(user_id):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎁 Sovg'alar", "💰 Ballarim va ID")
    markup.add("🔗 Do'stlarni taklif qilish", "📸 Rasm orqali buyurtma")
    markup.add("📞 Admin bilan bog'lanish")
    if user_id == ADMIN_ID: markup.add("⚙️ Admin Panel")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    u_id = message.from_user.id
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (u_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, referrer_id, status) VALUES (?, ?, 'pending')", (u_id, ref_id))
        db.commit()

    if check_sub(u_id):
        bot.send_message(u_id, "Xush kelibsiz! Ballar to'plang va sovg'alarga ega bo'ling.", reply_markup=main_menu(u_id))
    else:
        show_sub_channels(u_id)

def show_sub_channels(user_id):
    cursor = db.cursor()
    cursor.execute("SELECT id FROM channels")
    markup = telebot.types.InlineKeyboardMarkup()
    for row in cursor.fetchall():
        markup.add(telebot.types.InlineKeyboardButton("Kanalga a'zo bo'lish", url=f"https://t.me/{row[0][1:]}"))
    markup.add(telebot.types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_sub_status"))
    bot.send_message(user_id, "Xarid qilish va sovg'alar yutish uchun kanallarga a'zo bo'ling:", reply_markup=markup)

# --- TASDIQLASH (REFERAL TIZIMI LOGIKASI) ---
@bot.callback_query_handler(func=lambda call: call.data == "check_sub_status")
def check_callback(call):
    u_id = call.from_user.id
    if check_sub(u_id):
        cursor = db.cursor()
        cursor.execute("SELECT referrer_id, status FROM users WHERE user_id=?", (u_id,))
        res = cursor.fetchone()
        
        if res and res[1] == 'pending':
            ref_id = res[0]
            if ref_id:
                cursor.execute("UPDATE users SET balance = balance + 5 WHERE user_id=?", (ref_id,))
                bot.send_message(ref_id, "✅ Yangi do'stingiz kanallarga qo'shildi! Sizga +5 ball berildi.")
            
            cursor.execute("UPDATE users SET status = 'active' WHERE user_id=?", (u_id,))
            db.commit()
        
        bot.delete_message(u_id, call.message.message_id)
        bot.send_message(u_id, "Tabriklaymiz! Endi botdan to'liq foydalanishingiz mumkin.", reply_markup=main_menu(u_id))
    else:
        bot.answer_callback_query(call.id, "Siz hali kanallarga a'zo emassiz!", show_alert=True)

# --- SOVG'ALAR (ERKAK/AYOL) ---
@bot.message_handler(func=lambda m: m.text == "🎁 Sovg'alar")
def gender_menu(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("👨 Erkaklar uchun", callback_data="p_Erkak"),
               telebot.types.InlineKeyboardButton("👩 Ayollar uchun", callback_data="p_Ayol"))
    bot.send_message(message.chat.id, "Kategoriyani tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("p_"))
def show_prizes(call):
    gender = call.data.split("_")[1]
    cursor = db.cursor()
    cursor.execute("SELECT * FROM prizes WHERE gender=?", (gender,))
    items = cursor.fetchall()
    if not items:
        bot.answer_callback_query(call.id, "Hozircha bu bo'limda sovg'alar yo'q.")
        return
    for item in items:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(f"🔄 Almashtirish ({item[2]} ball)", callback_data=f"exchange_{item[0]}"))
        bot.send_photo(call.message.chat.id, item[3], caption=f"🎁 {item[1]}\n💰 Narxi: {item[2]} ball", reply_markup=markup)

# --- AYIRBOSHLASH ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("exchange_"))
def exchange(call):
    p_id = call.data.split("_")[1]
    u_id = call.from_user.id
    cursor = db.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (u_id,))
    bal = cursor.fetchone()[0]
    cursor.execute("SELECT * FROM prizes WHERE id=?", (p_id,))
    prize = cursor.fetchone()

    if bal >= prize[2]:
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (prize[2], u_id))
        db.commit()
        bot.send_message(u_id, "✅ Ayirboshlash muvaffaqiyatli! Qo'shimcha ma'lumot uchun admin sizga bog'lanadi.")
        bot.send_photo(ADMIN_ID, prize[3], caption=f"📣 SOVRIN ALMASHTIRILDI!\n👤 Kim: @{call.from_user.username}\n🆔 ID: {u_id}\n🎁 Sovrin: {prize[1]}")
    else:
        bot.answer_callback_query(call.id, "Ballaringiz yetarli emas!", show_alert=True)

# --- RASM ORQALI BUYURTMA ---
@bot.message_handler(func=lambda m: m.text == "📸 Rasm orqali buyurtma")
def photo_order(message):
    msg = bot.send_message(message.chat.id, "Buyurtma qilmoqchi bo'lgan mahsulotingiz rasmini yuboring:")
    bot.register_next_step_handler(msg, forward_order)

def forward_order(message):
    if message.content_type == 'photo':
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        bot.send_message(ADMIN_ID, f"📸 YANGI BUYURTMA (RASM)\n👤 Kimdan: @{message.from_user.username}\n🆔 ID: `{message.from_user.id}`\n📅 Sana: {now}")
        bot.send_message(message.chat.id, "Rasmingiz adminga yuborildi. Tez orada bog'lanamiz!")
    else:
        bot.send_message(message.chat.id, "Iltimos, faqat rasm yuboring.")

# --- BALLAR VA TAKLIF ---
@bot.message_handler(func=lambda m: m.text == "💰 Ballarim va ID")
def balance(message):
    cursor = db.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
    bal = cursor.fetchone()[0]
    bot.send_message(message.chat.id, f"👤 Sizning ID: `{message.from_user.id}`\n💰 To'plangan ballar: {bal} ball", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔗 Do'stlarni taklif qilish")
def invite(message):
    link = f"https://t.me/{bot.get_me().username}?start={message.from_user.id}"
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📤 Havolani ulashish", url=f"https://t.me/share/url?url={link}&text=Zo'r bot ekan, do'stlar taklif qilib sovg'alar yutib ol!"))
    bot.send_message(message.chat.id, f"Do'stlaringizni taklif qiling va har biri uchun 5 ball oling!\n\nLink: {link}", reply_markup=markup)

# --- ADMIN PANEL ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="a_ch"),
               telebot.types.InlineKeyboardButton("🎁 Sovg'a qo'shish", callback_data="a_pr"))
    bot.send_message(ADMIN_ID, "Boshqaruv paneli:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "a_ch")
def add_ch(call):
    msg = bot.send_message(ADMIN_ID, "Kanal linkini yuboring (@kanal):")
    bot.register_next_step_handler(msg, save_ch)

def save_ch(message):
    db.cursor().execute("INSERT OR IGNORE INTO channels VALUES (?)", (message.text,))
    db.commit()
    bot.send_message(ADMIN_ID, "Kanal qo'shildi!")

@bot.callback_query_handler(func=lambda call: call.data == "a_pr")
def add_pr(call):
    msg = bot.send_message(ADMIN_ID, "Nomi, Narxi, Jinsi (Erkak/Ayol). Namuna: Soat, 100, Erkak")
    bot.register_next_step_handler(msg, get_pr)

def get_pr(message):
    data = message.text.split(", ")
    msg = bot.send_message(ADMIN_ID, "Rasmini yuboring:")
    bot.register_next_step_handler(msg, save_pr, data)

def save_pr(message, data):
    db.cursor().execute("INSERT INTO prizes (name, cost, photo, gender) VALUES (?, ?, ?, ?)", (data[0], int(data[1]), message.photo[-1].file_id, data[2]))
    db.commit()
    bot.send_message(ADMIN_ID, "Sovg'a saqlandi!")

bot.infinity_polling()
