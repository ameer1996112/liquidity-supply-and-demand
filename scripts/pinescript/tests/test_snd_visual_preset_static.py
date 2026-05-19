from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STRATEGIES = [
    ROOT / "scripts/pinescript/strategies/SND_Strategy.pine",
    ROOT / "scripts/pinescript/strategies/SND_Strategey_refactor.pine",
]


def main() -> None:
    for path in STRATEGIES:
        strategy = path.read_text(encoding="utf-8")
        required = [
            'plotLiq    = input.bool(false, "plotLiq"',
            'show_fractals = input.bool(false, "show_fractals"',
            "showChartFractals = show_fractals",
            "showRawLiquidityLevels = plotLiq",
            "const int LIQ_LEVEL_EXTENSION_BARS = 1",
            "color liq_inducement_level_color = color.new(#7A6A4D, 20)",
            "col_demand_bg     = color.new(#8FA6A0, 93)",
            "col_demand_border = color.new(#54756E, 42)",
            "col_supply_bg     = color.new(#A88F95, 93)",
            "col_supply_border = color.new(#7A5860, 42)",
            "col_acc_demand_bg     = color.new(#8FA6A0, 91)",
            "col_acc_demand_border = color.new(#3F6860, 24)",
            "col_acc_supply_bg     = color.new(#A88F95, 91)",
            "col_acc_supply_border = color.new(#6E4852, 24)",
            "col_label_demand      = color.new(#23292C, 8)",
            "col_label_supply      = color.new(#23292C, 8)",
            "col_label_acc_demand  = color.new(#303332, 6)",
            "col_label_acc_supply  = color.new(#303332, 6)",
            "col_label_text        = color.new(#E6EAEC, 0)",
            "col_status_good       = color.new(#6F9388, 0)",
            "col_status_warn       = color.new(#7A6A4D, 0)",
            "col_status_bad        = color.new(#8C5C64, 0)",
            "col_status_info       = color.new(#5F789D, 0)",
            'plot(show_ema_context_line ? feature_ema_context : na, "EMA Context", color = color.new(#5F789D, 12), linewidth = 2)',
            'plot(strategy.position_size != 0 ? trade_tp1_price : na, "Trade TP Level", color = color.new(col_status_good, 50)',
            'plot(strategy.position_size != 0 ? trade_current_sl : na, "Trade SL Level", color = color.new(col_status_bad, 50)',
            'plot(strategy.position_size != 0 ? trade_entry_price : na, "Trade Entry", color = color.new(col_status_info, 50)',
            "liquidity_level_end_bar(Core.Zone z)",
            "extend_bars          = 6",
            "plotshape(showChartFractals",
            "z.inducementHLine := line.new(x1 = z.liqLowBar",
            "z.inducementHLine := line.new(x1 = z.liqHighBar",
            "color = liq_inducement_level_color, style = line.style_solid, width = 1)",
            "if isPvtLow and showRawLiquidityLevels",
            "if isPvtHigh and showRawLiquidityLevels",
            "if showRawLiquidityLevels and barstate.isconfirmed",
        ]
        missing = [needle for needle in required if needle not in strategy]
        if missing:
            raise AssertionError(f"{path.name} missing clean visual defaults:\n" + "\n".join(missing))
        forbidden = [
            "visual_detail_mode",
            'options = ["Clean", "Liquidity", "Full"]',
            "show_liquidity_connectors",
            "showChartLiquidityConnectors",
            "liq_connector_pending",
            "liq_connector_swept",
            "color liq_target_level_color",
            "z.connectorLine := line.new",
            "z.targetLine := line.new",
            "z.targetHLine := line.new",
            "line.new(x1 = z.createdBarIndex, y1 = z.liqLowPrice",
            "line.new(x1 = z.createdBarIndex, y1 = z.liqHighPrice",
            "liquidity_level_end_bar(z.liquiditySwept",
            "liquidity_level_end_bar(z.targetSwept",
            "extend_bars          = 50",
            "color.new(#f59e0b",
            "color.new(#facc15",
            "color.new(#D4AF37",
            "color.new(#C8A96A",
            "color.new(#6FA89A",
            "color.new(#2F8F7B",
            "color.new(#B76E79",
            "color.new(#A94D5D",
            "color.new(#7FAEA3",
            "color.new(#C08A92",
            "color.new(#3E7F73",
            "color.new(#8F4652",
            "color.new(#5277B8",
            "color.new(#2dd4bf",
            "color.new(#14b8a6",
            "color.new(#fb7185",
            "color.new(#f43f5e",
            "color.new(#38bdf8",
            "color.new(#0ea5e9",
            "color.new(#c084fc",
            "color.new(#a855f7",
            "color.new(#2196F3",
            "color.new(#AB47BC",
            "color.new(#26a69a",
            "color.new(#ef5350",
            'plot(show_ema_context_line ? feature_ema_context : na, "EMA Context", color = color.new(color.blue, 0)',
            "color.new(color.purple",
            "color.new(color.orange",
            "color.yellow",
            "color.lime",
            "color.rgb(100, 200, 255)",
            "color.rgb(0, 200, 100)",
            "color.rgb(255, 180, 0)",
            "color.rgb(255, 180, 80)",
            "color.rgb(255, 80, 80)",
        ]
        present = [needle for needle in forbidden if needle in strategy]
        if present:
            raise AssertionError(f"{path.name} must not expose visual modes:\n" + "\n".join(present))

    print("SND clean visual defaults static contract passed")


if __name__ == "__main__":
    main()
