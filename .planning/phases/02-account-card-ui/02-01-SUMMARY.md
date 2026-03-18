---
status: "complete"
---

# Plan 02-01: Hooks & Wrapper - Summary

## Built
- **src/hooks/usePropFirmChallenge.ts**: Exported the `usePropFirmChallenge` hook powered by `@tanstack/react-query` calling our `apiFetch` on `10s` polling.
- **src/components/accounts/PropFirmSection.tsx**: Built the base skeleton and loaded state data parser, extracting server names safely and displaying errors/loading gracefully.
- **src/components/accounts/EnhancedAccountCard.tsx**: Added `<PropFirmSection />` appropriately wrapped.

## Review Notes
React Query usage aligns properly with the rest of the application ecosystem. Tested gracefully.

## Self-Check: PASSED
- [x] SWR/React Query 10s fetch active
- [x] Embedded properly inside the account card
