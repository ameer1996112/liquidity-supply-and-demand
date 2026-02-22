import sys

file_path = 'src/api_portfolio_control.py'
with open(file_path, 'r') as f:
    lines = f.readlines()

target_block_start = -1
for i, line in enumerate(lines):
    if line.startswith('@router.get("/accounts/allocation-suggest"'):
        target_block_start = i - 2
        break

target_block_end = -1
for i, line in enumerate(lines[target_block_start:]):
    if '# HEALTH CHECK & MONITORING' in line:
        target_block_end = target_block_start + i - 4
        break
        
insert_index = -1
for i, line in enumerate(lines):
    if line.startswith('@router.get("/accounts/{account_name}")'):
        insert_index = i - 2
        break

if target_block_start == -1 or insert_index == -1:
    print('Indices not found', target_block_start, target_block_end, insert_index)
    sys.exit(1)

block = lines[target_block_start:target_block_end]
del lines[target_block_start:target_block_end]

# re-insert at correct spot
new_lines = lines[:insert_index] + block + ['\n\n'] + lines[insert_index:]

with open(file_path, 'w') as f:
    f.writelines(new_lines)

print('File updated successfully')
