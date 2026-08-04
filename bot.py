import os
import sys
import re
import sqlite3
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Reconfigure stdout to use utf-8 for Windows console
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Verify and configure Gemini API Key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ Error: GEMINI_API_KEY is not defined in the environment or .env file.")
    sys.exit(1)

genai.configure(api_key=api_key)

KB_DIR = "knowledge_base"
DB_PATH = "chat_memory.db"

class ChatMemoryManager:
    """Manages persistent chat history per user using SQLite database."""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_user_history(self, user_id, limit=10):
        """Retrieves recent conversation history for a given user_id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM message_history
                WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
            """, (str(user_id), limit))
            rows = cursor.fetchall()
            
        history = []
        for role, content in reversed(rows):
            history.append({
                "role": role,
                "parts": [content]
            })
        return history

    def add_message(self, user_id, role, content):
        """Appends a user or model message to history."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO message_history (user_id, role, content)
                VALUES (?, ?, ?)
            """, (str(user_id), role, content))
            conn.commit()

    def clear_user_history(self, user_id):
        """Clears memory for a specific user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM message_history WHERE user_id = ?", (str(user_id),))
            conn.commit()

# Initialize Global Memory Manager
memory_manager = ChatMemoryManager()

def parse_md_file(path, filename):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    yaml_meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_str = parts[1]
            body = parts[2]
            for line in yaml_str.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    yaml_meta[k.strip()] = v.strip()
    
    return {
        "filename": filename,
        "meta": yaml_meta,
        "body": body
    }

def load_knowledge_base():
    kb_data = []
    if not os.path.exists(KB_DIR):
        print(f"⚠️ Knowledge base directory '{KB_DIR}' not found.")
        return kb_data
        
    for filename in os.listdir(KB_DIR):
        if filename.endswith(".md"):
            path = os.path.join(KB_DIR, filename)
            kb_data.append(parse_md_file(path, filename))
    return kb_data

def get_relevant_context(query, kb_data):
    query = query.lower()
    matches_scores = []
    
    for doc in kb_data:
        meta_str = " ".join(doc["meta"].values()).lower()
        tags_str = doc["meta"].get("tags", "").replace("[", "").replace("]", "").replace("'", "").lower()
        body_str = doc["body"].lower()
        full_text = f"{meta_str} {tags_str} {body_str}"
        
        score = 0
        tags_list = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        for tag in tags_list:
            if tag in query:
                score += 5
                
        query_terms = [t for t in re.findall(r'\w+', query) if len(t) > 2]
        for term in query_terms:
            if term in full_text:
                score += 1
            for tag in tags_list:
                if term in tag or tag in term:
                    score += 2
                    
        if score > 0:
            matches_scores.append((doc, score))
            
    matches_scores.sort(key=lambda x: x[1], reverse=True)
    return [item[0] for item in matches_scores[:2]]

def detect_user_intent(query, has_image=False):
    """Classifies user intent into distinct categories for targeted handling."""
    if has_image:
        return "TROUBLESHOOTING_VISUAL"
        
    query_clean = query.lower().strip()
    
    # Intent 1: Price Request
    if any(k in query_clean for k in ["چنده", "چند", "قیمت", "هزینه", "پلن", "تعرفه", "چقدر میشه", "قیمتش"]):
        return "PRICE_REQUEST"
        
    # Intent 2: Order / Purchase Request
    if any(k in query_clean for k in ["بفرست", "خرید", "میخوام", "می‌خوام", "ثبت کن", "اکانت میخوام", "اشتراک میخوام", "تست بده", "تست برام", "یک ماهه"]):
        return "ORDER_REQUEST"
        
    # Intent 3: Payment / Card Info
    if any(k in query_clean for k in ["کارت", "شماره کارت", "واریز", "فیش", "پرداخت", "حساب"]):
        return "PAYMENT_INFO"

    # Intent 4: Connection / Troubleshooting
    if any(k in query_clean for k in ["قطعه", "قطع", "کار نمیکنه", "وصل نمیشه", "پینگ نمیده", "ارور", "خرابه", "کند"]):
        return "TROUBLESHOOTING"

    # Intent 5: Setup Tutorial / Download
    if any(k in query_clean for k in ["آموزش", "برنامه", "دانلود", "نصب", "چجوری وصل شم", "چطور"]):
        return "TUTORIAL"

    return "GENERAL"

def generate_response(query, image_path=None, user_id="default_user"):
    """Generates response taking user's intent and conversation history into account."""
    kb_data = load_knowledge_base()
    
    # Classify User Intent
    intent = detect_user_intent(query, has_image=bool(image_path))
    
    # Retrieve user's previous history from SQLite memory
    history = memory_manager.get_user_history(user_id=user_id, limit=10)
    
    # Combine query + user history for context search if query is brief
    history_text = " ".join([h["parts"][0] for h in history if isinstance(h["parts"][0], str)])
    search_query = f"{query} {history_text}".strip() if query else "خرابی اتصال اسکرین شات ارور"
    
    matched_docs = get_relevant_context(search_query, kb_data)
    
    if image_path:
        visual_doc = next((d for d in kb_data if d['filename'] == 'troubleshooting_visual.md'), None)
        if visual_doc and visual_doc not in matched_docs:
            matched_docs.append(visual_doc)
            
    context_blocks = []
    for doc in matched_docs:
        context_blocks.append(f"Document ({doc['meta'].get('title', doc['filename'])}):\n{doc['body'].strip()}")
        
    context = "\n\n---\n\n".join(context_blocks) if context_blocks else "هیچ فایل راهنمای مستقیمی در پایگاه دانش یافت نشد."
    
    # Intent-specific behavioral instruction
    intent_guidance = ""
    if intent == "PRICE_REQUEST":
        intent_guidance = "قصد مشتری: قیمت می‌خواهد. لیست پکیج‌های قیمت را خیلی کوتاه با ایموجی بفرست و آخرش بپرس کدام حجم مد نظرش است."
    elif intent == "ORDER_REQUEST":
        intent_guidance = "قصد مشتری: قصد خرید یا سفارش دارد. او را تشویق کن، مشخصات سیستم‌عاملش را بپرس یا راهنمایی و شماره کارت پرداخت ارائه بده."
    elif intent == "PAYMENT_INFO":
        intent_guidance = "قصد مشتری: اطلاعات کارت یا واریز می‌خواهد. راهنمایی پرداخت و شماره کارت را بده و بگو فیش را بفرستد."
    elif intent == "TROUBLESHOOTING_VISUAL" or intent == "TROUBLESHOOTING":
        intent_guidance = "قصد مشتری: مشکل اتصال دارد. با دقت راه‌حل رفع مشکل یا درخواست اسکرین‌شات از برنامه را بده."
    elif intent == "TUTORIAL":
        intent_guidance = "قصد مشتری: آموزش راه‌اندازی می‌خواهد. اسم برنامه مناسب سیستم‌عاملش را ساده و گام‌به‌گام بگو."
    else:
        intent_guidance = "قصد مشتری: گفتگو عمومی یا سوال عادی پشتیبانی است."

    system_instruction = (
        "تو ادمین واقعی و پشتیبان فنی انسان در تلگرام برای فروشگاه X2Ray VPN هستی.\n"
        "مشتری نباید تحت هیچ شرایطی متوجه شود که با هوش مصنوعی صحبت می‌کند.\n\n"
        f"🎯 [تحلیل قصد مشتری در این پیام]: {intent} -> {intent_guidance}\n\n"
        "دستورالعمل لحن و فرمت پاسخ‌دهی:\n"
        "۱. لحن کاملاً صمیمی، دوستانه، عامیانه و تلگرامی داشته باش (مثل یک ادمین جوان و خوش‌برخورد).\n"
        "۲. به هیچ عنوان از کلمات کتابی، رسمی و اداری استفاده نکن (مثلاً به جای «جهت»، «فرآیند»، «ملاحظه فرمایید»، «ارسال نمایید» از «واسه»، «ببین»، «بفرست»، «بررسی کن» استفاده کن).\n"
        "۳. سلام و احوال‌پرسی‌های تکراری و اداری نده. با کلماتی مثل «سلام عزیزم»، «سلام داداش وقتت بخیر»، «سلام جانم» یا «سلام وقت بخیر ❤️» شروع کن.\n"
        "۴. پاسخ‌ها را کوتاه، روان و ساده بنویس. از شماره‌گذاری‌های رسمی زیاد یا بولت‌پوینت‌های خیلی طولانی کتابی پرهیز کن.\n"
        "۵. سابقه چت قبلی مشتری را حتماً مد نظر قرار بده. اگر قبلاً مدل گوشی، اپراتور یا مشکلی را گفته، نیاز به پرسش دوباره نیست و بر همان اساس پاسخ بده.\n"
        "۶. در صورت ارسال اسکرین‌شات، مانند یک ادمین باتجربه عیب برنامه (v2rayNG یا V2Box) را روی عکس ببین و خیلی ساده و عامیانه راهنمایی‌اش کن.\n"
        "۷. اگر شماره کارت یا تلفن خواسته شد، مقادیر حساس را سانسور کن.\n\n"
        "نمونه پاسخ‌های واقعی ادمین تلگرام:\n"
        "- مشتری: قیمت چند؟\n"
        "  ادمین: سلام عزیزم وقتت بخیر ❤️\n"
        "  پکیج ۴۰ گیگ: ۱۲۰ تمن (یکماهه)\n"
        "  پکیج ۸۰ گیگ: ۲۲۰ تمن (دوکاربره)\n"
        "  کدوم مد نظرت هست برات ثبت کنم؟\n\n"
        "- مشتری: وصلم ولی اینترنت ندارم\n"
        "  ادمین: سلام جانم، یه اسکرین‌شات از داخل برنامه‌ت میفرستی ببینم سروری که انتخابی داری پینگ میده یا نه؟\n\n"
        f"پایگاه دانش (اطلاعات مرجع):\n{context}"
    )
    
    contents = []
    if query:
        contents.append(query)
    else:
        contents.append("لطفا این اسکرین‌شات از برنامه فیلترشکن را بررسی کرده و راهنمایی کنید.")
        
    if image_path:
        try:
            import PIL.Image
            img = PIL.Image.open(image_path)
            contents.append(img)
        except Exception as e:
            print(f"Error loading image: {e}")
            
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        # Start chat with loaded history
        chat = model.start_chat(history=history)
        response = chat.send_message(contents)
        
        # Save new user query and model reply to SQLite memory
        user_msg = query if query else "[ارسال تصویر اسکرین‌شات]"
        memory_manager.add_message(user_id=user_id, role="user", content=user_msg)
        memory_manager.add_message(user_id=user_id, role="model", content=response.text)
        
        return {
            "intent": intent,
            "response": response.text
        }
    except Exception as e:
        return {
            "intent": intent,
            "response": f"❌ Error generating response: {e}"
        }

if __name__ == "__main__":
    print("🤖 X2Ray Support Chatbot (with Intent Classifier & Memory) is running!")
    print("Type your message and press Enter (type 'exit' to quit).\n")
    
    current_user = "cli_demo_user"
    
    while True:
        try:
            user_input = input("Customer: ")
            if user_input.strip().lower() == 'exit':
                print("Goodbye!")
                break
                
            if not user_input.strip():
                continue
                
            result = generate_response(user_input, user_id=current_user)
            print(f"🎯 Detected Intent: {result['intent']}")
            print(f"AI Bot: {result['response']}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
