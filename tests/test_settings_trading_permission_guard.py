from config.settings import Settings


def test_trading_permission_guard_defaults_to_legacy_entry_mode() -> None:
    settings = Settings(
        supabase_url="https://example.supabase.co",
        redis_url="redis://localhost:6379/0",
        _env_file=None,
    )

    assert settings.enable_trading_permission_guard is False
