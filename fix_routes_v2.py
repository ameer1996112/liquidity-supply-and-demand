import codecs
import sys

with codecs.open('src/api_portfolio_control.py', 'r', 'utf-8') as f:
    content = f.read()

start_marker = '@router.get("/accounts/allocation-suggest", response_model=AllocationPlanResponse)'
end_marker = '# ══════════════════════════════════════════════════════════════════\n# HEALTH CHECK & MONITORING'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)

if start_idx == -1 or end_idx == -1:
    print("Markers not found", start_idx, end_idx)
    sys.exit(1)

extracted_block = content[start_idx:end_idx]
content_without_block = content[:start_idx] + content[end_idx:]

insert_marker = '@router.get("/accounts/{account_name}")'
insert_idx = content_without_block.find(insert_marker)

if insert_idx == -1:
    print("Insert marker not found")
    sys.exit(1)

final_content = content_without_block[:insert_idx] + extracted_block + '\n' + content_without_block[insert_idx:]

with codecs.open('src/api_portfolio_control.py', 'w', 'utf-8') as f:
    f.write(final_content)

print("Swap successful")
