from datetime import datetime
import dateutil.parser

trade_created_at = "2026-02-20T14:05:06.646601+00:00"
dt = dateutil.parser.isoparse(trade_created_at)

now = datetime.fromisoformat("2026-02-22T15:55:23+02:00")
diff = now - dt

print(f"Trade created: {dt}")
print(f"Current UTC: {now}")
print(f"Age: {diff.total_seconds() / 3600:.1f} hours")
