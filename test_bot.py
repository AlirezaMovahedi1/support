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
    query = query.lower()
    matches_scores = []
    
    for doc in kb_data:
        meta_str = " ".join(doc["meta"].values()).lower()
        tags_str = doc["meta"].get("tags", "").replace("[", "").replace("]", "").replace("'", "").lower()
        body_str = doc["body"].lower()
        full_text = f"{meta_str} {tags_str} {body_str}"
        
        score = 0
        tags_list = [tag.strip() for tag in tags_str.split(",") if tag.strip()]
        
        # 1. Substring matching of tags in the query
        for tag in tags_list:
            if tag in query:
                score += 5
                
        # 2. General term matching
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
    if matches_scores:
        return matches_scores[0][0], matches_scores[0][1]
    return None, 0

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

def run_automated_tests():
    print("🧪 Starting Automated Test Suite for Support Bot...")
    test_queries = [
        ("سلام قیمت پلن ها چنده؟", "pricing.md"),
        ("من گوشیم ایفونه چجوری وصل بشم؟", "ios_setup.md"),
        ("رو همراه اول کار نمیکنه قطعه", "troubleshooting.md"),
        ("شماره کارت میدی برای تمدید؟", "payment.md"),
        ("برای ویندوز برنامه نکو ری رو چطور نصب کنم؟", "windows_setup.md"),
    ]
    
    kb_data = load_knowledge_base()
    passed = 0
    
    for query, expected_doc in test_queries:
        best_doc, score = find_context(query, kb_data)
        doc_name = best_doc['filename'] if best_doc else None
        
        if doc_name == expected_doc:
            print(f"✅ Pass: Query '{query}' matched expected '{expected_doc}' (Score: {score})")
            passed += 1
        else:
            print(f"❌ Fail: Query '{query}' matched '{doc_name}' instead of expected '{expected_doc}'")
            
    print(f"\n📊 Summary: {passed}/{len(test_queries)} tests passed.")

if __name__ == "__main__":
    run_automated_tests()
