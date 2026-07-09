import os
import sys
from bs4 import BeautifulSoup
from datetime import datetime

# Reconfigure stdout to use utf-8 for Windows console
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')


def parse_chat_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    
    messages = []
    current_date_str = ""
    last_sender = None
    
    # We find all message divs
    # They can be "message default clearfix" or "message default clearfix joined"
    # Also "message service" contains date headers
    history_div = soup.find('div', class_='history')
    if not history_div:
        return []
        
    for child in history_div.find_all('div', recursive=False):
        classes = child.get('class', [])
        
        # Check if it's a date header
        if 'service' in classes:
            # Service message with date
            body_details = child.find('div', class_='body')
            if body_details and 'details' in body_details.get('class', []):
                current_date_str = body_details.get_text(strip=True)
            continue
            
        if 'default' in classes:
            # Standard message
            body_div = child.find('div', class_='body')
            if not body_div:
                continue
                
            # Date/Time
            date_div = body_div.find('div', class_='date')
            time_str = ""
            full_datetime_str = ""
            if date_div:
                time_str = date_div.get_text(strip=True)
                full_datetime_str = date_div.get('title', '')
                
            # Sender
            from_name_div = body_div.find('div', class_='from_name')
            if from_name_div:
                sender = from_name_div.get_text(strip=True)
                last_sender = sender
            else:
                # "joined" message inherits sender
                sender = last_sender
                
            # Text content
            text_div = body_div.find('div', class_='text')
            text_content = ""
            if text_div:
                text_content = text_div.get_text(separator="\n", strip=True)
                
            # Parse datetime
            dt = None
            if full_datetime_str:
                # Format is usually: "07.04.2023 14:41:59 UTC+03:30" or similar
                # Let's clean and parse it if possible
                try:
                    # Strip UTC offset for easier parsing
                    clean_dt_str = full_datetime_str.split(' UTC')[0]
                    dt = datetime.strptime(clean_dt_str, "%d.%m.%Y %H:%M:%S")
                except Exception as e:
                    pass
            
            messages.append({
                'sender': sender,
                'text': text_content,
                'time': time_str,
                'datetime': dt,
                'raw_datetime': full_datetime_str
            })
            
    return messages

# Let's test on chat_0001 and chat_0002
for chat_name in ['chat_0001', 'chat_0002', 'chat_0003']:
    test_file = f"c:\\Users\\mojan\\Desktop\\support\\DataExport_2026-07-05\\chats\\{chat_name}\\messages.html"
    if os.path.exists(test_file):
        with open(test_file, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'lxml')
        title_div = soup.find('div', class_='page_header')
        title = title_div.get_text(strip=True) if title_div else "Unknown"
        
        msgs = parse_chat_file(test_file)
        senders = set(m['sender'] for m in msgs if m['sender'])
        print(f"\n--- {chat_name} ---")
        print(f"Chat Title: {title}")
        print(f"Total messages: {len(msgs)}")
        print(f"Unique senders: {senders}")
        if len(msgs) > 0:
            print("First 3 messages:")
            for m in msgs[:3]:
                print(f"  [{m['sender']}]: {m['text'][:80]}...")
    else:
        print(f"{chat_name} not found")

