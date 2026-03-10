# TODO - Clean Departure & Strict Pre-Sweep Fix

- [ ] Add `min_departure_bars` input (default 5) in both strategy files
- [ ] Replace Demand validation logic with strict clean-departure + pre-sweep kill rules
- [ ] Replace Supply validation logic with strict clean-departure + pre-sweep kill rules
- [ ] Remove/replace any early-touch ignore behavior
- [ ] Mirror changes in `SND_Strategy_enter.pine`
- [ ] Run thorough static verification (grep for new reasons/input and absence of old ignore paths)
- [ ] Summarize testing coverage and results
