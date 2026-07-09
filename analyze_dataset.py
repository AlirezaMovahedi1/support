import json
import re
import sys
from collections import Counter

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')


# Load the dataset
with open('qa_dataset.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find unique keywords / apps / prices
android_apps = []
ios_apps = []
prices = []

for item in data:
    sup = item['support']
    cust = item['customer']
    
    # Check for iOS keywords
    if 'آیفون' in cust or 'ایفون' in cust or 'ios' in cust.lower():
        # Look at support replies to extract app names
        for word in ['وی تو باکس', 'v2box', 'streisand', 'fozzy', 'sing-box', 'شدوکراکت', 'shadowrocket', 'fair']:
            if word in sup.lower() or word in cust.lower():
                ios_apps.append(word)
                
    # Check for Android keywords
    if 'اندروید' in cust or 'android' in cust.lower() or 'سامسونگ' in cust or 'شیائومی' in cust:
        for word in ['v2rayng', 'v2ray', 'sing-box', 'نپستور', 'nepstur', 'anray']:
            if word in sup.lower() or word in cust.lower():
                android_apps.append(word)
                
    # Extract pricing lines
    for line in sup.split('\n'):
        if 'گیگ' in line or 'تومان' in line or 'هزار' in line:
            prices.append(line.strip())

print("iOS Apps mentioned:")
print(Counter(ios_apps))

print("\nAndroid Apps mentioned:")
print(Counter(android_apps))

print("\nSample Pricing/Plan lines in Support replies:")
price_lines = Counter(prices)
for line, count in price_lines.most_common(20):
    print(f"({count} times): {line}")
