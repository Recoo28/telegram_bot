import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerChannel
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import NetworkError, Forbidden
from your_bot_logic import setup_handlers, main
from telethon import TelegramClient
from telegram.ext import ApplicationBuilder

# Logging ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot bilgileri
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Grup ve kullanıcı bilgileri
TARGET_GROUP_ID = -1001647237066
ADMIN_ID = 981506247
TIKTOK_URL = "https://www.tiktok.com/@fakedostyoffical?_t=8o1qYxH3ThF&_r=1"
GROUP_ID = -1002156787755

# Veritabanı bağlantısı
conn = sqlite3.connect('user_data.db')
c = conn.cursor()

# Tablo oluşturma (eğer yoksa)
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, username TEXT, join_date TEXT, status TEXT, in_group BOOLEAN)''')
conn.commit()

# Kullanıcı medya sayılarını ve son tebrik zamanlarını saklamak için sözlükler
user_media_count = {}
last_congratulated = {}
last_congratulated_15 = {}
bulk_media_tracker = {}

# Telethon client
telethon_client = TelegramClient('bot_session', API_ID, API_HASH)

# python-telegram-bot uygulaması
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Telethon event handler'ları
@telethon_client.on(events.NewMessage(chats=TARGET_GROUP_ID))
@telethon_client.on(events.Album(chats=TARGET_GROUP_ID))
async def handle_new_message(event):
    if event.message.media:
        sender = await event.get_sender()
        user_id = sender.id
        
        if user_id not in bulk_media_tracker:
            bulk_media_tracker[user_id] = {'count': 1, 'last_message_id': event.message.id}
        else:
            bulk_media_tracker[user_id]['count'] += 1
            bulk_media_tracker[user_id]['last_message_id'] = event.message.id
        
        if user_id not in user_media_count:
            user_media_count[user_id] = 1
        else:
            user_media_count[user_id] += 1
        
        print(f"Kullanıcı {user_id} için medya sayısı: {user_media_count[user_id]}")
        
        sender_entity = await telethon_client.get_entity(user_id)
        mention = f"[{sender_entity.first_name}](tg://user?id={user_id})"
        
        if 7 <= user_media_count[user_id] < 15 and (user_id not in last_congratulated or 
                                                    datetime.now() - last_congratulated[user_id] > timedelta(days=1)):
            if event.message.id == bulk_media_tracker[user_id]['last_message_id']:
                print(f"Kullanıcı {user_id} 7 medya gönderdi, tebrik ediliyor...")
                congrats_message = f"Tebrikler {mention}, gün içinde 7 tane medya gönderdiniz. Grubumuza katkılarınız için teşekkür ederiz."
                await telethon_client.send_message(TARGET_GROUP_ID, congrats_message, reply_to=event.message.id)
                last_congratulated[user_id] = datetime.now()
        
        elif user_media_count[user_id] >= 15 and (user_id not in last_congratulated_15 or 
                                                  datetime.now() - last_congratulated_15[user_id] > timedelta(days=1)):
            if event.message.id == bulk_media_tracker[user_id]['last_message_id']:
                print(f"Kullanıcı {user_id} 15 medya gönderdi, ikinci kez tebrik ediliyor...")
                congrats_message_15 = f"Waow {mention}, sen şahanesin. Günde 15 medya gönderdin. Bu grubu seviyor olmasın. Bizde seni seviyoruz, teşekkür ederim."
                await telethon_client.send_message(TARGET_GROUP_ID, congrats_message_15, reply_to=event.message.id)
                last_congratulated_15[user_id] = datetime.now()
        
        await asyncio.sleep(1)
        bulk_media_tracker[user_id]['count'] = 0

# python-telegram-bot handler'ları
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    current_time = datetime.now()

    if update.effective_chat.type != "private":
        return

    logger.info(f"Start command received from user {user.id}")

    c.execute("SELECT status, in_group FROM users WHERE user_id = ?", (user.id,))
    result = c.fetchone()
    logger.info(f"Database result for user {user.id}: {result}")

    if not result:
        logger.info(f"User {user.id} not in database. Adding to database.")
        c.execute("INSERT INTO users (user_id, username, join_date, status, in_group) VALUES (?, ?, ?, ?, ?)",
                  (user.id, user.username, current_time.strftime("%Y-%m-%d %H:%M:%S"), "waiting_proof", True))
        conn.commit()
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Merhaba {user.first_name}, TikTok Takipleşme Grubuna hoşgeldin. "
                 f"Mesaj yazabilmek için lütfen TikTok hesabımızı takip edip bana ekran görüntüsünü at. {TIKTOK_URL}"
        )
    elif result[0] == "approved":
        logger.info(f"User {user.id} is already approved")
        await update.message.reply_text("Zaten grupta yazma izniniz var.")
    elif result[0] == "waiting_proof":
        logger.info(f"User {user.id} is waiting for proof")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Merhaba {user.first_name}, lütfen TikTok hesabımızı takip edip bana ekran görüntüsünü at. {TIKTOK_URL}"
        )
    else:
        logger.warning(f"Unexpected status for user {user.id}: {result[0]}")
        await update.message.reply_text("Bu botu kullanabilmek için belirtilen gruba üye olmanız gerekmektedir.")

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for new_member in update.message.new_chat_members:
        user_id = new_member.id
        username = new_member.username
        join_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logger.info(f"New member joined: {user_id} ({username})")
        
        try:
            result = await context.bot.restrict_chat_member(
                chat_id=GROUP_ID,
                user_id=user_id,
                permissions={"can_send_messages": False, "can_send_media_messages": False}
            )
            logger.info(f"Mute result for user {user_id}: {result}")
        except Exception as e:
            logger.error(f"Error muting user {user_id}: {e}", exc_info=True)
        
        try:
            c.execute("INSERT OR REPLACE INTO users (user_id, username, join_date, status, in_group) VALUES (?, ?, ?, ?, ?)",
                      (user_id, username, join_date, "waiting_proof", True))
            conn.commit()
            logger.info(f"User {user_id} added/updated in database")
        except Exception as e:
            logger.error(f"Error updating database for user {user_id}: {e}", exc_info=True)
        
        try:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=f"Selam, {new_member.mention_html()} sol taraftan profil fotoğrafıma tıklayıp beni başlatman gerekiyor ya da @fakedostyoffical_bot tıklayıp /start komutunu ver.",
                parse_mode='HTML'
            )
            logger.info(f"Welcome message sent for user {user_id}: {sent_message.message_id}")
        except Exception as e:
            logger.error(f"Error sending welcome message for user {user_id}: {e}", exc_info=True)

async def handle_member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    left_member = update.message.left_chat_member
    if left_member:
        user_id = left_member.id
        logger.info(f"Member left: {user_id}")
        
        c.execute("UPDATE users SET in_group = FALSE, status = 'left' WHERE user_id = ?", (user_id,))
        conn.commit()

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    user = update.effective_user
    photo = update.message.photo[-1]
    
    c.execute("SELECT status FROM users WHERE user_id = ?", (user.id,))
    result = c.fetchone()
    
    if not result or result[0] != "waiting_proof":
        if result and result[0] == "approved":
            await update.message.reply_text("Bu işlemi yapmanıza gerek yok. Zaten grupta yazma izniniz var.")
        else:
            await update.message.reply_text("Lütfen önce /start komutunu kullanın.")
        return
    
    keyboard = [
        [InlineKeyboardButton("Onayla✔", callback_data=f"approve_{user.id}"),
         InlineKeyboardButton("Reddet❌", callback_data=f"reject_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo.file_id,
        caption=f"Kullanıcı: {user.mention_html()}\nID: {user.id}",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    await update.message.reply_text("Ekran görüntünüz incelenmek üzere gönderildi. Lütfen bekleyin.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    
    logger.info(f"Button callback: action={action}, user_id={user_id}")
    
    if action == "approve":
        try:
            result = await context.bot.restrict_chat_member(
                chat_id=GROUP_ID,
                user_id=user_id,
                permissions={"can_send_messages": True, "can_send_media_messages": True}
            )
            logger.info(f"Unmute result for user {user_id}: {result}")

            c.execute("UPDATE users SET status = 'approved' WHERE user_id = ?", (user_id,))
            conn.commit()
            await context.bot.send_message(chat_id=user_id, text="Takibiniz onaylandı. Artık grupta mesaj yazabilirsiniz.")
            
            new_keyboard = [
                [InlineKeyboardButton("Onaylandı✅", callback_data=f"approved_{user_id}"),
                 InlineKeyboardButton("Reddet❌", callback_data=f"reject_{user_id}")]
            ]
            new_reply_markup = InlineKeyboardMarkup(new_keyboard)
            await query.edit_message_reply_markup(reply_markup=new_reply_markup)
            
        except Exception as e:
            logger.error(f"Error approving user {user_id}: {e}", exc_info=True)
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"Kullanıcı onaylanırken bir hata oluştu: {e}")
    elif action == "reject":
        await context.bot.send_message(
            chat_id=user_id,
            text="Lütfen, takip ettiğinizin ekran görüntüsünü atın."
        )
        
        new_keyboard = [
            [InlineKeyboardButton("Onayla✔", callback_data=f"approve_{user_id}"),
             InlineKeyboardButton("Reddedildi❌", callback_data=f"rejected_{user_id}")]
        ]
        new_reply_markup = InlineKeyboardMarkup(new_keyboard)
        await query.edit_message_reply_markup(reply_markup=new_reply_markup)
    
    elif action in ["approved", "rejected"]:
        pass
    
    await query.answer()

async def reset_daily_counters():
    while True:
        print("Günlük sayaç sıfırlama görevi çalışıyor...")
        now = datetime.now()
        next_day = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        await asyncio.sleep((next_day - now).total_seconds())
        
        # Sayaçları sıfırla
        user_media_count.clear()
        last_congratulated.clear()
        last_congratulated_15.clear()
        bulk_media_tracker.clear()
        print("Günlük sayaçlar sıfırlandı.")

# Telethon için ana fonksiyon
async def run_telethon():
    await telethon_client.start(bot_token=BOT_TOKEN)
    print("Telethon client başlatıldı.")
    
    # Sayaç sıfırlama görevini başlat
    asyncio.create_task(reset_daily_counters())
    print("Sayaç sıfırlama görevi başlatıldı.")
    
    await telethon_client.run_until_disconnected()

# python-telegram-bot için ana fonksiyon
async def run_ptb():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_member_left))
    
    await application.initialize()
    await application.start()
    print("python-telegram-bot uygulaması başlatıldı.")
    
    await application.updater.start_polling()

# Ana fonksiyon
async def main():
    try:
        # Her iki client'ı ayrı görevler olarak başlat
        telethon_task = asyncio.create_task(run_telethon())
        ptb_task = asyncio.create_task(run_ptb())
        
        # Her iki görevin de tamamlanmasını bekle
        await asyncio.gather(telethon_task, ptb_task)
    except Exception as e:
        logger.error(f"Ana döngüde bir hata oluştu: {e}", exc_info=True)
    finally:
        # Temizlik işlemleri
        await telethon_client.disconnect()
        await application.stop()
        conn.close()
if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        setup_handlers(application, telethon_client)
        loop.run_until_complete(main(telethon_client, application))
    except KeyboardInterrupt:
        print("Bot kapatılıyor...")
    except Exception as e:
        logger.error(f"Beklenmeyen bir hata oluştu: {e}", exc_info=True)
