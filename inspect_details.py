import json
import sys

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

with open('qa_dataset.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("--- Starlink Mentions ---")
starlink_count = 0
for item in data:
    if 'استارلینک' in item['support'] or 'استارلینک' in item['customer']:
        print(f"Q: {item['customer']}")
        print(f"A: {item['support']}")
        print("-" * 50)
        starlink_count += 1
        if starlink_count >= 5:
            break

print("--- 45 هزار تومان Mentions ---")
count_45 = 0
for item in data:
    if '۴۵ هزار' in item['support'] or '45 هزار' in item['support']:
        print(f"Q: {item['customer']}")
        print(f"A: {item['support']}")
        print("-" * 50)
        count_45 += 1
        if count_45 >= 5:
            break
