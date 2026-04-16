from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ModuleState(str, Enum):
    INHERIT = "inherit"
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass(frozen=True)
class ResolvedModuleState:
    enabled: bool
    source: str
    forced: bool


def resolve_panic_mode(module_name: str, panic_mode: bool) -> bool:
    if not panic_mode:
        return True
    return False


def resolve_module_state(
    module_name: str,
    panic_mode: bool,
    global_state: ModuleState,
    user_state: ModuleState,
    account_state: ModuleState,
    strategy_state: ModuleState,
    admin_override: Optional[str],
) -> ResolvedModuleState:
    if admin_override == "forced-off":
        return ResolvedModuleState(enabled=False, source="admin", forced=True)
    if admin_override == "forced-on":
        return ResolvedModuleState(enabled=True, source="admin", forced=True)
    if not resolve_panic_mode(module_name, panic_mode):
        return ResolvedModuleState(enabled=False, source="panic", forced=True)

    for source, value in (
        ("strategy", strategy_state),
        ("account", account_state),
        ("user", user_state),
        ("global", global_state),
    ):
        if value == ModuleState.ENABLED:
            return ResolvedModuleState(enabled=True, source=source, forced=False)
        if value == ModuleState.DISABLED:
            return ResolvedModuleState(enabled=False, source=source, forced=False)

    return ResolvedModuleState(enabled=False, source="default", forced=False)
