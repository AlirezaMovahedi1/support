import os
import sys
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Reconfigure stdout to use utf-8 for Windows console
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# Regex to redact sensitive information
CARD_REGEX = re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b')
PHONE_REGEX = re.compile(r'\b(?:09|\+98|0098)\d{9}\b')

def redact_sensitive_info(text):
    if not text:
        return ""
    text = CARD_REGEX.sub("[شماره کارت]", text)
    text = PHONE_REGEX.sub("[شماره تلفن]", text)
    return text

def parse_chat_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    
    # Extract chat title
    title_div = soup.find('div', class_='page_header')
    chat_title = title_div.get_text(strip=True) if title_div else ""
    
    history_div = soup.find('div', class_='history')
    if not history_div:
        return chat_title, []
        
    messages = []
    last_sender = None
    
    for child in history_div.find_all('div', recursive=False):
        classes = child.get('class', [])
        
        # Date indicator (service messages)
        if 'service' in classes:
            continue
            
        if 'default' in classes:
            body_div = child.find('div', class_='body')
            if not body_div:
                continue
                
            # Date/Time
            date_div = body_div.find('div', class_='date')
            full_datetime_str = date_div.get('title', '') if date_div else ""
                
            # Sender
            from_name_div = body_div.find('div', class_='from_name')
            if from_name_div:
                sender = from_name_div.get_text(strip=True)
                last_sender = sender
            else:
                sender = last_sender
                
            # Text content
            text_div = body_div.find('div', class_='text')
            text_content = ""
            if text_div:
                text_content = text_div.get_text(separator="\n", strip=True)
                
            # Parse datetime
            dt = None
            if full_datetime_str:
                try:
                    clean_dt_str = full_datetime_str.split(' UTC')[0]
                    dt = datetime.strptime(clean_dt_str, "%d.%m.%Y %H:%M:%S")
                except Exception:
                    pass
            
            # Only add messages that actually contain text
            if text_content:
                messages.append({
                    'sender': sender,
                    'text': text_content,
                    'datetime': dt
                })
            
    return chat_title, messages

def process_chats(chats_dir):
    qa_pairs = []
    chat_folders = [f for f in os.listdir(chats_dir) if f.startswith('chat_')]
    chat_folders.sort()
    
    print(f"Starting parsing for {len(chat_folders)} chats...")
    
    for idx, folder in enumerate(chat_folders):
        file_path = os.path.join(chats_dir, folder, 'messages.html')
        if not os.path.exists(file_path):
            continue
            
        try:
            chat_title, messages = parse_chat_file(file_path)
            
            # Check unique senders in this chat
            unique_senders = set(m['sender'] for m in messages if m['sender'])
            
            # Filter: we only want 1-on-1 support chats
            # Normally it contains "Support" and the Customer (which is not Support)
            # If there are more than 2 senders, it's likely a group or channel, so skip.
            if len(unique_senders) > 2 or len(unique_senders) < 2:
                continue
                
            # Identify which sender is Support
            # Usually the account owner is "Support"
            support_sender_name = "Support"
            if support_sender_name not in unique_senders:
                # If "Support" is not one of them, skip (could be two other people in a group)
                continue
                
            # Group consecutive messages from the same sender (conversational turns)
            grouped_messages = []
            for msg in messages:
                if not msg['sender']:
                    continue
                    
                role = "support" if msg['sender'] == support_sender_name else "customer"
                
                if not grouped_messages:
                    grouped_messages.append({
                        'role': role,
                        'text': msg['text']
                    })
                else:
                    last_msg = grouped_messages[-1]
                    if last_msg['role'] == role:
                        # Append to the current group
                        last_msg['text'] += "\n" + msg['text']
                    else:
                        # Create a new group
                        grouped_messages.append({
                            'role': role,
                            'text': msg['text']
                        })
            
            # Build Q&A pairs
            # We look for a "customer" group followed immediately by a "support" group
            i = 0
            while i < len(grouped_messages) - 1:
                curr = grouped_messages[i]
                nxt = grouped_messages[i+1]
                
                if curr['role'] == 'customer' and nxt['role'] == 'support':
                    # Clean and redact
                    customer_q = redact_sensitive_info(curr['text'])
                    support_a = redact_sensitive_info(nxt['text'])
                    
                    # Basic filters to ensure we don't save empty/trivial QA
                    if len(customer_q.strip()) > 3 and len(support_a.strip()) > 3:
                        qa_pairs.append({
                            'chat_id': folder,
                            'customer': customer_q,
                            'support': support_a
                        })
                    i += 2  # Skip to the next pair
                else:
                    i += 1
                    
        except Exception as e:
            print(f"Error processing {folder}: {e}")
            
    return qa_pairs

if __name__ == "__main__":
    chats_directory = r"c:\Users\mojan\Desktop\support\DataExport_2026-07-05\chats"
    qa_dataset = process_chats(chats_directory)
    
    # Save the cleaned dataset
    output_path = r"c:\Users\mojan\Desktop\support\qa_dataset.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(qa_dataset, f, ensure_ascii=False, indent=4)
        
    print(f"\nParsing completed successfully!")
    print(f"Extracted {len(qa_dataset)} clean Q&A pairs.")
    print(f"Dataset saved to: {output_path}")
