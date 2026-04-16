"""
src/pipeline/__init__.py

Lightweight package marker for pipeline helpers.

Keep this file import-safe: worker startup imports submodules such as
``src.pipeline.account_guards``, which causes Python to execute this
package ``__init__`` first.
"""

__all__: list[str] = []
