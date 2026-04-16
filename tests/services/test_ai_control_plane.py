from src.services.ai_control_plane import (
    ModuleState,
    ResolvedModuleState,
    resolve_module_state,
    resolve_panic_mode,
)


def test_strategy_scope_overrides_higher_scopes() -> None:
    resolved = resolve_module_state(
        module_name="chart_context",
        panic_mode=False,
        global_state=ModuleState.ENABLED,
        user_state=ModuleState.ENABLED,
        account_state=ModuleState.DISABLED,
        strategy_state=ModuleState.ENABLED,
        admin_override=None,
    )

    assert resolved == ResolvedModuleState(enabled=True, source="strategy", forced=False)


def test_admin_forced_off_beats_all_other_states() -> None:
    resolved = resolve_module_state(
        module_name="debate_review",
        panic_mode=False,
        global_state=ModuleState.ENABLED,
        user_state=ModuleState.ENABLED,
        account_state=ModuleState.ENABLED,
        strategy_state=ModuleState.ENABLED,
        admin_override="forced-off",
    )

    assert resolved == ResolvedModuleState(enabled=False, source="admin", forced=True)


def test_panic_mode_disables_non_core_modules() -> None:
    assert resolve_panic_mode(module_name="chart_context", panic_mode=True) is False
    assert resolve_panic_mode(module_name="debate_review", panic_mode=True) is False
