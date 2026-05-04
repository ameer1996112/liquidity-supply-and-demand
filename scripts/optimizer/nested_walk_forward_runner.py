from __future__ import annotations

from scripts.optimizer.walk_forward_runner import cli, evaluate_walk_forward, is_catastrophic_fold, write_outputs

__all__ = ["cli", "evaluate_walk_forward", "is_catastrophic_fold", "write_outputs"]


if __name__ == "__main__":
    cli()
