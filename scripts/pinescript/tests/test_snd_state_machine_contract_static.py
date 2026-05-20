from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGY = ROOT / "scripts/pinescript/strategies/SND_Strategy.pine"


def main() -> None:
    strategy = STRATEGY.read_text(encoding="utf-8")

    required = [
        'const string ZSTATE_CANDIDATE = "Candidate"',
        'const string ZSTATE_ACTIVE = "Active"',
        'const string ZSTATE_LEFT_ZONE = "LeftZone"',
        'const string ZSTATE_LIQ_FOUND = "LiquidityFound"',
        'const string ZSTATE_LIQ_VALID = "LiquidityValid"',
        'const string ZSTATE_LIQ_SWEPT = "LiquiditySwept"',
        'const string ZSTATE_TARGET_BOS = "TargetBOSSwept"',
        'const string ZSTATE_READY = "ReadyForMitigation"',
        'const string ZSTATE_USED = "MitigatedUsed"',
        'const string ZSTATE_INVALID = "Invalid"',
        'const string ZSTATE_EXPIRED = "Expired"',
        'const string REASON_CREATED = "CREATED"',
        'const string REASON_REJECTED_NO_DISPLACEMENT = "REJECTED_NO_DISPLACEMENT"',
        'const string REASON_REJECTED_CHOPPY_BASE = "REJECTED_CHOPPY_BASE"',
        'const string REASON_REJECTED_CONTAMINATED_ORIGIN = "REJECTED_CONTAMINATED_ORIGIN"',
        'const string REASON_REJECTED_DUPLICATE = "REJECTED_DUPLICATE"',
        'const string REASON_LIQ_FOUND = "LIQ_FOUND"',
        'const string REASON_LIQ_VALID = "LIQ_VALID"',
        'const string REASON_LIQ_INVALID_INSIDE_ZONE = "LIQ_INVALID_INSIDE_ZONE"',
        'const string REASON_LIQ_INVALID_TOO_FAR = "LIQ_INVALID_TOO_FAR"',
        'const string REASON_LIQ_INVALID_NOT_STRONG = "LIQ_INVALID_NOT_STRONG"',
        'const string REASON_INDUCEMENT_SWEPT = "INDUCEMENT_SWEPT"',
        'const string REASON_TARGET_BOS_SWEPT = "TARGET_BOS_SWEPT"',
        'const string REASON_READY_FOR_MITIGATION = "READY_FOR_MITIGATION"',
        'const string REASON_INVALID_RETURN_BEFORE_PROOF = "INVALID_RETURN_BEFORE_PROOF"',
        'const string REASON_INVALID_CLOSE_INSIDE_ZONE = "INVALID_CLOSE_INSIDE_ZONE"',
        'const string REASON_INVALID_DISTAL_CLOSE = "INVALID_DISTAL_CLOSE"',
        'const string REASON_INVALID_EARLY_RETURN = "INVALID_EARLY_RETURN"',
        'const string REASON_MITIGATED_USED_FOR_ENTRY = "MITIGATED_USED_FOR_ENTRY"',
        'const string REASON_EXPIRED = "EXPIRED"',
        'const string REASON_PRUNED = "PRUNED"',
        "zone_state(Core.Zone z) =>",
        "if z.mitigated or not na(z.lastEntryBar)",
        "ZSTATE_USED",
        "else if not z.active and zone_inactive_reason(z) == REASON_EXPIRED",
        "ZSTATE_EXPIRED",
        "else if z.targetSwept",
        "ZSTATE_READY",
        "else if z.liquiditySwept",
        "ZSTATE_LIQ_SWEPT",
        "else if z.liquidityValid",
        "ZSTATE_LIQ_VALID",
        "else if not na(z.liquidityPrice) or not na(z.liqLowPrice) or not na(z.liqHighPrice)",
        "ZSTATE_LIQ_FOUND",
        "else if z.leftZone",
        "ZSTATE_LEFT_ZONE",
        "else",
        "ZSTATE_ACTIVE",
        "mark_zone_rejected(string reason) =>",
        "string candidateRejectReason = REASON_CREATED",
        "candidateRejectReason := mark_zone_rejected(REASON_REJECTED_DUPLICATE)",
        "candidateRejectReason := mark_zone_rejected(REASON_REJECTED_NO_DISPLACEMENT)",
        "candidateRejectReason := mark_zone_rejected(REASON_REJECTED_CHOPPY_BASE)",
        "candidateRejectReason := mark_zone_rejected(REASON_REJECTED_CONTAMINATED_ORIGIN)",
        "bool baseTooLarge =",
        "bool contaminatedOrigin = false",
        "if skipDuplicateZone",
        "mark_zone_rejected(REASON_REJECTED_DUPLICATE)",
    ]

    missing = [item for item in required if item not in strategy]
    if missing:
        raise AssertionError("Missing state machine contract markers:\n" + "\n".join(missing))

    print("SND state machine static contract passed")


if __name__ == "__main__":
    main()
