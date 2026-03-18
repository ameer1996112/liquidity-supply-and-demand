import sys
from unittest.mock import MagicMock
from src.services.prop_firm_detector import PropFirmDetector

def run_tests():
    detector = PropFirmDetector(MagicMock())
    
    cases = [
        # Server contains LIVE/SERVER -> funded
        ("FTMO-Server3", "My Account", "funded"),
        ("Live-MetaAPI", "Test", "funded"),
        # Server is Demo, parsing account names:
        ("FTMO-Demo", "Ameer Funded", "funded"),
        ("FundedEngineer-Demo", "100k Master", "funded"),
        ("FTMO-Demo", "P2 100k", "phase_2"),
        ("Meta-Demo", "Verification 50k", "phase_2"),
        ("MyForexFunds-Demo", "Evaluation P1", "phase_1"),
        ("FTMO-Demo", "Fresh Start Step 1", "phase_1"),
        # Fallback empty string
        ("FTMO-Demo", "", "phase_1"),
    ]
    
    passed = 0
    for server, account, expected in cases:
        result = detector.auto_detect_challenge_type(server, account)
        if result == expected:
            print(f"PASS: '{server}' / '{account}' -> {result}")
            passed += 1
        else:
            print(f"FAIL: '{server}' / '{account}'. Expected {expected}, got {result}")
            
    if passed == len(cases):
        print("All tests passed.")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
