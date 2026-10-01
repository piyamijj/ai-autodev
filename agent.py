import os
import sys
import subprocess
import logging
import chromadb
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Logging Ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Hafıza (Vector DB) Başlatma
chroma_client = chromadb.PersistentClient(path="./agent_memory")
collection = chroma_client.get_or_create_collection(name="devops_memory")

# Telegram Bot Token
TOKEN = "8825570649:AAFf2646w9GPjGblbCFZKCKXCyd2_HIS8-U"

# MeinGPT API Ayarları (Doğrulanmış Adres)
MEINGPT_URL = "https://app.meingpt.com/api/openai/v1/chat/completions"
MEINGPT_KEY = "sk_meingpt_a8f0910844585dfc992348b647dacaf2c44b1ce027c945c20da8775f0483c725"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Akıllı AI Auto-Dev Agent Aktif!\n\nBana bir görev ver (Örn: 'Faktöriyel hesaplayan bir Python fonksiyonu yaz').")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    await update.message.reply_text(f"⚙️ Görev alındı: '{user_prompt}'\nMeinGPT (GPT-5-Nano) kod yazıyor...")

    headers = {
        "Authorization": f"Bearer {MEINGPT_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = "Sen sadece temiz ve çalışan Python kodları yazan bir yazılım ajanısın. Yanıtında asla açıklama, markdown blokları (```python gibi) veya ekstra metin olmasın. Sadece doğrudan çalıştırılabilir kodu döndür."
    
    data = {
        "model": "gpt-5-nano",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Şu işi yapan bir Python scripti yaz: {user_prompt}"}
        ]
    }

    try:
        response = requests.post(MEINGPT_URL, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            res_json = response.json()
            generated_code = res_json['choices'][0]['message']['content'].strip()
            
            # Markdown temizliği
            if generated_code.startswith("```"):
                lines = generated_code.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                generated_code = "\n".join(lines).strip()
        else:
            await update.message.reply_text(f"❌ MeinGPT API hatası verdi (Kod: {response.status_code}). Response: {response.text}")
            return
    except Exception as e:
        await update.message.reply_text(f"⚠️ MeinGPT bağlantı hatası: {str(e)}")
        return

    # Dosyaya Yazma İşlemi
    filename = "generated_script.py"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(generated_code)

    # Syntax (Yazım Hatası) Testi
    try:
        subprocess.run([sys.executable, "-m", "py_compile", filename], check=True)
    except subprocess.CalledProcessError:
        await update.message.reply_text("❌ Model kod yazdı fakat syntax hatası verdi, işlem iptal ediliyor.")
        return

    # Hafızaya Kaydetme (RAG)
    collection.add(
        documents=[f"Task: {user_prompt} -> Created: {filename}"],
        ids=[str(collection.count() + 1)]
    )

    # Git Commit & Push İşlemi
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"feat: {user_prompt}"], check=True)
        subprocess.run(["git", "push"], check=True)
        
        repo_url = "https://github.com/piyamijj/ai-autodev"
        await update.message.reply_text(f"✅ Kod başarıyla test edildi ve GitHub'a pushlandı!\n🔗 Repo: {repo_url}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Kod yerelde başarıyla üretildi ama Git push sırasında hata oluştu: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Akıllı AI Agent çalışıyor...")
    app.run_polling()
