import json
import os
import sys

# Ensure UTF-8 output on Windows terminal
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

KB_DIR = "knowledge_base"

def test_kb_consistency():
    """Verifies that all .md files in the knowledge base have valid YAML frontmatter and titles."""
    print("📋 Checking Knowledge Base Files consistency...")
    if not os.path.exists(KB_DIR):
        print(f"❌ Error: {KB_DIR} directory does not exist.")
        sys.exit(1)
        
    md_files = [f for f in os.listdir(KB_DIR) if f.endswith(".md")]
    if not md_files:
        print(f"⚠️ Warning: No .md files found in {KB_DIR}")
        return

    all_passed = True
    for filename in md_files:
        path = os.path.join(KB_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Verify basic structure
            if not content.startswith("---"):
                print(f"❌ {filename}: Missing frontmatter start ('---')")
                all_passed = False
                continue
                
            parts = content.split("---", 2)
            if len(parts) < 3:
                print(f"❌ {filename}: Malformed frontmatter block. Needs matching '---'")
                all_passed = False
                continue
                
            yaml_str = parts[1]
            yaml_meta = {}
            for line in yaml_str.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    yaml_meta[k.strip()] = v.strip()
                    
            # Check required fields
            title = yaml_meta.get("title")
            tags = yaml_meta.get("tags")
            
            if not title:
                print(f"❌ {filename}: Missing 'title' in frontmatter")
                all_passed = False
            if not tags:
                print(f"❌ {filename}: Missing 'tags' in frontmatter")
                all_passed = False
                
            if title and tags:
                print(f"✅ {filename}: Format looks good. Title: '{title}'")
                
        except Exception as e:
            print(f"❌ {filename}: Read error - {e}")
            all_passed = False
            
    if all_passed:
        print("\n✨ All knowledge base documents passed integrity checks successfully!")
    else:
        print("\n⚠️ Some documentation integrity errors were found.")
        sys.exit(1)

if __name__ == "__main__":
    test_kb_consistency()
