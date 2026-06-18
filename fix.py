import sys

with open("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine", "r") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
target_idx = -1

for i, line in enumerate(lines):
    if line.startswith("resolveStandardZoneCandidateAt(int eventStartIdx, int candidateBaseIdx, bool demand, int startOffset) =>"):
        start_idx = i
    if line.startswith("isContinuationZoneModel(string model) =>"):
        end_idx = i
    if line.startswith("if barstate.isconfirmed and isPrimaryFiveMinute"):
        target_idx = i

if start_idx != -1 and end_idx != -1 and target_idx != -1:
    block = lines[start_idx:end_idx]
    
    # delete the block
    new_lines = lines[:start_idx] + lines[end_idx:]
    
    # find the new target_idx
    new_target_idx = -1
    for i, line in enumerate(new_lines):
        if line.startswith("if barstate.isconfirmed and isPrimaryFiveMinute"):
            new_target_idx = i
            break
            
    # insert the block
    final_lines = new_lines[:new_target_idx] + block + new_lines[new_target_idx:]
    
    with open("scripts/pinescript/indicators/SND_Raw_RD_Forex.pine", "w") as f:
        f.writelines(final_lines)
    print("Fixed!")
else:
    print(f"Failed to find indices: start={start_idx}, end={end_idx}, target={target_idx}")

