#!/usr/bin/env python
# -*- coding: utf-8 -*-

with open('controller_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace send_interval with send_intervals
old_interval = 'send_interval = self.autokey_coords.get("autokey_send_interval", 100) / 1000.0  # Convert ms to seconds'
new_intervals = '''send_intervals = self.autokey_coords.get("autokey_send_intervals", [100, 100, 100])
        
        # Ensure intervals list has correct length
        while len(send_intervals) < send_count:
            send_intervals.append(100)  # Default to 100ms if missing
        send_intervals = send_intervals[:send_count]  # Trim if too many'''

if old_interval in content:
    content = content.replace(old_interval, new_intervals)
    print("✓ Replaced send_interval definition")
else:
    print("✗ send_interval definition not found")

# Replace time.sleep(send_interval) with variable intervals
old_time_sleep = 'time.sleep(send_interval)'
new_time_sleep = '''send_interval_ms = send_intervals[i] if i < len(send_intervals) else 100
                time.sleep(send_interval_ms / 1000.0)  # Convert ms to seconds'''

if old_time_sleep in content:
    content = content.replace(old_time_sleep, new_time_sleep)
    print("✓ Replaced time.sleep call")
else:
    print("✗ time.sleep call not found")

with open('controller_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✓ All replacements done!")
