import os
import sys
import re

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

KB_DIR = "knowledge_base"

def load_knowledge_base():
    kb_data = []
    if not os.path.exists(KB_DIR):
        return kb_data
        
    for filename in os.listdir(KB_DIR):
        if filename.endswith(".md"):
            path = os.path.join(KB_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Simple YAML frontmatter parser
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

def find_context(query, kb_data):
    # Simple keyword matching for demo/prototype
    query_words = set(re.findall(r'\w+', query.lower()))
    best_doc = None
    max_matches = 0
    
    for doc in kb_data:
        meta_str = " ".join(doc["meta"].values()).lower()
        tags_str = doc["meta"].get("tags", "").lower()
        body_str = doc["body"].lower()
        
        full_text = f"{meta_str} {tags_str} {body_str}"
        matches = sum(1 for word in query_words if word in full_text)
        
        if matches > max_matches:
            max_matches = matches
            best_doc = doc
            
    return best_doc, max_matches

def mock_bot_respond(query):
    kb_data = load_knowledge_base()
    best_doc, score = find_context(query, kb_data)
    
    print(f"\n==========================================")
    print(f"Customer: {query}")
    print(f"==========================================")
    
    if best_doc and score > 0:
        print(f"ℹ️ Found relevant knowledge document: [{best_doc['filename']}] (Score: {score})")
        print("\n--- Document metadata ---")
        for k, v in best_doc["meta"].items():
            print(f"{k}: {v}")
            
        print("\n--- System Prompt constructed for LLM ---")
        prompt = (
            f"You are a helpful customer support AI agent for X2Ray VPN.\n"
            f"Use the following knowledge base content to answer the customer's query.\n"
            f"If the answer is not in the context, guide them politely.\n\n"
            f"Context:\n{best_doc['body']}\n\n"
            f"Customer Query: {query}\n\n"
            f"Response:"
        )
        print(prompt[:600] + "...\n[Truncated for console]")
    else:
        print("⚠️ No direct match in knowledge base. The bot would fallback to generic support greeting.")

if __name__ == "__main__":
    # Test queries
    mock_bot_respond("سلام قیمت پلن ها چنده؟")
    mock_bot_respond("من گوشیم ایفونه چجوری وصل بشم؟")
    mock_bot_respond("رو همراه اول کار نمیکنه قطعه")
    mock_bot_respond("شماره کارت میدی برای تمدید؟")
