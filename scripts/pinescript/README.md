# Pine Script – Modular S&D Strategy

Modular layout to stay under TradingView token limits and avoid timeouts.

## Layout

| Path                             | Role                                                                                                                         |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **libraries/SND_Utils.pine**     | Generic helpers: `to_json_num`, `is_bullish`, `is_bearish`, `get_auto_pip_size`, `build_webhook_payload`, etc. All `export`. |
| **libraries/SND_Core.pine**      | `type Zone`, `calculate_zone_score`, `is_makuchaku_pvt_low`/`_high`, AI scoring. Accepts `series float` where needed.        |
| **strategies/SND_Strategy.pine** | Main strategy: imports the two libraries, holds `input()` and `strategy.entry` calls.                                        |

Publish **SND_Utils** and **SND_Core** as TradingView libraries (e.g. `ameer_1996112/SND_Utils/1`, `ameer_1996112/SND_Core/1`), then in **SND_Strategy.pine** use:

```pine
import ameer_1996112/SND_Utils/1 as Utils
import ameer_1996112/SND_Core/1 as Core
```

Legacy single-file (reference only): `supply_and_demand_optimized.pine`.
