import telebot
from telebot import types
import ccxt
import numpy as np

# --- BOT AYARLARI ---
TOKEN = "8644028444:AAEaC1NAAZXkQ-S2PZR2yMnS_k2pFABwXD8"
bot = telebot.TeleBot(TOKEN)

# Borsayı Tanımla
exchange = ccxt.binance({'enableRateLimit': True})
SYMBOL = "BTC/USDT"

def get_market_data(symbol, timeframe):
    """Piyasa mum verilerini ve göstergelerini hesaplar."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=100)
        closes = np.array([x[4] for x in ohlcv])
        highs = np.array([x[2] for x in ohlcv])
        lows = np.array([x[1] for x in ohlcv])

        current_price = closes[-1]

        # 1. EMA Hesaplama (20 ve 50 periyot)
        def calculate_ema(data, window):
            weights = np.exp(np.linspace(-1., 0., window))
            weights /= weights.sum()
            a = np.convolve(data, weights, mode='full')[:len(data)]
            a[:window] = a[window]
            return a

        ema_fast = calculate_ema(closes, 20)[-1]
        ema_slow = calculate_ema(closes, 50)[-1]

        # 2. RSI Hesaplama (14 periyot)
        deltas = np.diff(closes)
        seed = deltas[:14]
        up = seed[seed >= 0].sum()/14
        down = -seed[seed < 0].sum()/14
        rs = up/down if down != 0 else 0
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # 3. ATR (Volatillik & Hassas SL/TP Hesaplama)
        tr = np.maximum(highs[1:] - lows[1:], 
                        np.maximum(abs(highs[1:] - closes[:-1]), 
                                   abs(lows[1:] - closes[:-1])))
        atr = np.mean(tr[-14:])

        # --- FİLTRELENMİŞ KESİN SİNYAL MANTIĞI ---
        # Trend yönü, RSI bölgesel onayı ile filtrelenir
        if current_price > ema_fast and ema_fast > ema_slow and rsi > 50 and rsi < 70:
            signal = "BUY 🟢 (YÜKSELİŞ TRENDİ)"
            entry = current_price
            sl = round(entry - (atr * 1.8), 2)
            tp = round(entry + (atr * 3.6), 2)  # 1:2 Risk-Ödül Oranı
            confidence = "Yüksek (EMA + RSI Onaylı)"

        elif current_price < ema_fast and ema_fast < ema_slow and rsi < 50 and rsi > 30:
            signal = "SELL 🔴 (DÜŞÜŞ TRENDİ)"
            entry = current_price
            sl = round(entry + (atr * 1.8), 2)
            tp = round(entry - (atr * 3.6), 2)  # 1:2 Risk-Ödül Oranı
            confidence = "Yüksek (EMA + RSI Onaylı)"

        else:
            # Belirsiz, yatay veya aşırı alım/satım bölgesindeki tehlikeli piyasa
            signal = "NÖTR ⚪ (RİSKLİ BÖLGE)"
            entry = current_price
            sl = round(entry - (atr * 1.0), 2)
            tp = round(entry + (atr * 1.0), 2)
            confidence = "Düşük (Piyasa Kararsız/Yatay)"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "price": current_price,
            "signal": signal,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rsi": round(rsi, 2),
            "confidence": confidence
        }

    except Exception as e:
        return None

@bot.message_handler(commands=['start', 'analiz'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    # Zaman Dilimi Butonları
    btn1 = types.InlineKeyboardButton("1m ⚡", callback_data="tf_1m")
    btn2 = types.InlineKeyboardButton("5m ⏱️", callback_data="tf_5m")
    btn3 = types.InlineKeyboardButton("15m 📊", callback_data="tf_15m")
    btn4 = types.InlineKeyboardButton("1h ⏳", callback_data="tf_1h")
    btn5 = types.InlineKeyboardButton("4h 📈", callback_data="tf_4h")
    btn6 = types.InlineKeyboardButton("1d 📅", callback_data="tf_1d")
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    bot.send_message(
        message.chat.id, 
        "🤖 **GainzAlgo Precision V2 Bot**\n\nAnaliz yapmak istediğiniz **zaman dilimini** seçin:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('tf_'))
def handle_analysis(call):
    timeframe = call.data.split('_')[1]
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"🔄 **{SYMBOL}** için `{timeframe}` mumları taranıyor..."
    )
    
    res = get_market_data(SYMBOL, timeframe)
    
    if res:
        response_text = (
            f"🎯 **HASSAS ANALİZ SONUCU ({res['symbol']})**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ **Zaman Dilimi:** `{res['timeframe']}`\n"
            f"📍 **Anlık Fiyat:** `${res['price']}`\n"
            f"📊 **RSI Değeri:** `{res['rsi']}`\n\n"
            f"🚨 **Sinyal:** **{res['signal']}**\n"
            f"🎯 **Giriş (Entry):** `${res['entry']}`\n"
            f"🛑 **Stop-Loss (SL):** `${res['sl']}`\n"
            f"✅ **Take-Profit (TP):** `${res['tp']}`\n\n"
            f"🛡️ **Güvenilirlik:** `{res['confidence']}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *Not: Nötr sinyallerde işleme girmeyiniz.*"
        )
    else:
        response_text = "❌ Bağlantı hatası oluştu. Lütfen tekrar deneyin."

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Farklı Zaman Dilimi Seç", callback_data="reset"))

    bot.send_message(call.message.chat.id, response_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == 'reset')
def reset_callback(call):
    send_welcome(call.message)

print("Bot sorunsuz çalışıyor...")
bot.infinity_polling()
