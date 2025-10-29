# ---------------- Callback Query ----------------

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    chat_id = query.message.chat_id
    subs = load_subscribers()
    if query.data == 'stop':
        if chat_id in subs:
            subs.remove(chat_id)
            save_subscribers(subs)
        query.answer(text="Bildirimler kapatıldı ✅")
        query.edit_message_reply_markup(reply_markup=None)

# ---------------- /start komutu ----------------

def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    subs = load_subscribers()
    if chat_id not in subs:
        subs.append(chat_id)
        save_subscribers(subs)
    update.message.reply_text("✅ Abonelik aktif edildi. Eğitim bildirimleri gönderilecektir.")

# ---------------- Main ----------------

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))

    updater.start_polling()

    bot = updater.bot
    egitimler = egitimleri_cek()
    subs = load_subscribers()
    for s in subs:
        gonder_egitimler(bot, s, egitimler)

    updater.idle()

if name == "__main__":
    main()
