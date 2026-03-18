### Grey Area 1/4: Firm Auto-Detection Strategy
| # | Question | ✅ Recommended | Alternative(s) |
|---|----------|---------------|-----------------|
| 1 | Matching strategy for server names? | **Prefix matching** (`FTMO-Server` matches `FTMO-Server3`) — robust to new servers | Exact mapping for every string |
| 2 | Case sensitivity? | **Case-insensitive** — avoids capitalization bugs | Strict case matching |

### Grey Area 2/4: Rules Database Architecture
| # | Question | ✅ Recommended | Alternative(s) |
|---|----------|---------------|-----------------|
| 1 | Rule storage format? | **Flat columns** — easier to query and update | JSONB blob |
| 2 | Timezone handling for daily reset (NY midnight)? | **Store standard timezone string** (`America/New_York`) — handles DST automatically | Store static UTC offset |

### Grey Area 3/4: Challenge Account Differentiation
| # | Question | ✅ Recommended | Alternative(s) |
|---|----------|---------------|-----------------|
| 1 | Initial challenge type state for new accounts? | `null` / unconfigured — forces explicit user selection via API | Default to Phase 1 |
| 2 | Drawdown denominator basis for Phase 1/2? | **Initial balance** — required by FTMO rules | Trailing high-water-mark (incorrect for Phase 1) |

### Grey Area 4/4: API Design
| # | Question | ✅ Recommended | Alternative(s) |
|---|----------|---------------|-----------------|
| 1 | Unrecognized server response? | **200 OK with `firm_detected: false`** — allows graceful UI fallback ("Unknown firm") | 404 Not Found error |
