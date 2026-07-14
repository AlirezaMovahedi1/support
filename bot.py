import os
import sys
import re
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

def load_knowledge_base():
    kb_data = []
    if not os.path.exists(KB_DIR):
        print(f"⚠️ Knowledge base directory '{KB_DIR}' not found.")
        return kb_data
        
    for filename in os.listdir(KB_DIR):
        if filename.endswith(".md"):
            path = os.path.join(KB_DIR, filename)
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
            
            kb_data.append({
                "filename": filename,
                "meta": yaml_meta,
                "body": body
            })
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
        
        # 1. Substring matching of tags in the query
        # This solves "آیفونه" matching "آیفون" because "آیفون" is in "آیفونه"
        tags_list = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        for tag in tags_list:
            if tag in query:
                score += 5  # High weight for tag matches
                
        # 2. General term matching
        query_terms = [t for t in re.findall(r'\w+', query) if len(t) > 2]
        for term in query_terms:
            if term in full_text:
                score += 1
            # Check if doc tags contain the query term as a substring
            for tag in tags_list:
                if term in tag or tag in term:
                    score += 2
                    
        if score > 0:
            matches_scores.append((doc, score))
            
    # Sort by score descending
    matches_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Return top 2 matching documents
    return [item[0] for item in matches_scores[:2]]

def generate_response(query, image_path=None):
    kb_data = load_knowledge_base()
    
    # Get standard textual context
    # If query is empty but we have an image, search for general troubleshooting context
    search_query = query if query else "خرابی اتصال اسکرین شات ارور"
    matched_docs = get_relevant_context(search_query, kb_data)
    
    # If we have an image, ensure troubleshooting_visual.md is in context
    if image_path:
        visual_doc = next((d for d in kb_data if d['filename'] == 'troubleshooting_visual.md'), None)
        if visual_doc and visual_doc not in matched_docs:
            matched_docs.append(visual_doc)
            
    # Construct context block
    context_blocks = []
    for doc in matched_docs:
        context_blocks.append(f"Document ({doc['meta'].get('title', doc['filename'])}):\n{doc['body'].strip()}")
        
    context = "\n\n---\n\n".join(context_blocks) if context_blocks else "هیچ فایل راهنمای مستقیمی در پایگاه دانش یافت نشد."
    
    system_instruction = (
        "You are a professional customer support AI agent for X2Ray VPN. "
        "Your goal is to answer the customer's query accurately and politely using ONLY the provided Context.\n"
        "You may be provided with a text query, a screenshot image, or both.\n"
        "If they send an image, use the visual troubleshooting guide (troubleshooting_visual.md) to inspect the screenshot. "
        "Analyze what app they are using (v2rayNG or V2Box), identify the visual error (e.g. no config selected, switch off, expired), "
        "and provide step-by-step guidance in Persian.\n"
        "If the customer is asking for prices, show the pricing table from the pricing document.\n"
        "If they ask for support, payment details, or tutorials, use the respective documents.\n"
        "If the query or visual error cannot be answered by the context, "
        "politely guide them and say that a human support agent will review their request soon.\n\n"
        "Guidelines:\n"
        "- Reply in Persian (Farsi).\n"
        "- Use a friendly, polite, and helpful tone.\n"
        "- Redact card numbers or telephone numbers if they ask (always show '[شماره کارت]' or '[شماره تلفن]').\n"
        "- Keep responses concise and structured (use bullet points or lists if appropriate).\n\n"
        f"Context:\n{context}"
    )
    
    contents = []
    if query:
        contents.append(query)
    else:
        # Default text query if only image is provided
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
        response = model.generate_content(contents=contents)
        return response.text
    except Exception as e:
        return f"❌ Error generating response: {e}"

if __name__ == "__main__":
    print("🤖 X2Ray Support Chatbot is running!")
    print("Type your message and press Enter (type 'exit' to quit).\n")
    
    while True:
        try:
            user_input = input("Customer: ")
            if user_input.strip().lower() == 'exit':
                print("Goodbye!")
                break
                
            if not user_input.strip():
                continue
                
            response = generate_response(user_input)
            print(f"AI Bot: {response}\n")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
