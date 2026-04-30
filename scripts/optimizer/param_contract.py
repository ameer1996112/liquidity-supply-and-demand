from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from . import config as optimizer_config

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PINE_SOURCE = PROJECT_ROOT / "scripts" / "pinescript" / "strategies" / "SND_Strategy.pine"


@dataclass(frozen=True)
class PineInput:
    variable: str
    title: str


def _paren_depth(text: str) -> int:
    depth = 0
    quote = None
    escaped = False
    for char in text:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
    return depth


def _split_args(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote = None
    escaped = False
    for index, char in enumerate(args):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:index].strip())
            start = index + 1
    parts.append(args[start:].strip())
    return parts


def _string_literal_value(value: str) -> str | None:
    match = re.match(r'"([^"]*)"', value.strip())
    if not match:
        return None
    return match.group(1)


def _input_title(args: str) -> str:
    positional: list[str] = []
    for arg in _split_args(args):
        if arg.startswith("title"):
            match = re.search(r'title\s*=\s*"([^"]*)"', arg)
            if match:
                return match.group(1)
        if "=" not in arg:
            positional.append(arg)
    title_arg = positional[1] if len(positional) > 1 else positional[0]
    title = _string_literal_value(title_arg)
    if title is None:
        raise ValueError(f"Could not parse Pine input title from: {args[:120]}")
    return title


def extract_pine_inputs(pine_source: Path = DEFAULT_PINE_SOURCE) -> dict[str, PineInput]:
    source = pine_source.read_text()
    inputs: dict[str, PineInput] = {}
    lines = source.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if "= input." not in line:
            index += 1
            continue
        block = line
        depth = _paren_depth(line[line.find("input.") :])
        while depth > 0:
            index += 1
            if index >= len(lines):
                raise ValueError(f"Unclosed Pine input call near: {line.strip()}")
            block += "\n" + lines[index]
            depth += _paren_depth(lines[index])
        match = re.match(r"\s*(?P<name>\w+)\s*=\s*input\.\w+\((?P<body>.*)\)\s*$", block, re.S)
        if match:
            variable = match.group("name")
            inputs[variable] = PineInput(variable=variable, title=_input_title(match.group("body")))
        index += 1
    return inputs


def optimizer_search_param_names() -> set[str]:
    synthetic = set(getattr(optimizer_config, "OPTIMIZER_SYNTHETIC_PARAMS", ()))
    names = set(optimizer_config.OPTUNA_SEARCH_SPACE) - synthetic - {"liq_distance"}
    names.update(item["param"] for item in optimizer_config.LIQ_DISTANCE_RANGES.values())
    return names


def optimizer_applied_pine_param_names() -> set[str]:
    synthetic_inputs = {
        input_name
        for input_names in getattr(optimizer_config, "OPTIMIZER_SYNTHETIC_PARAM_INPUTS", {}).values()
        for input_name in input_names
    }
    return (
        optimizer_search_param_names()
        | set(getattr(optimizer_config, "OPTIMIZER_CONTEXT_PARAM_DEFAULTS", ()))
        | set(getattr(optimizer_config, "OPTIMIZER_METADATA_PARAMS", ()))
        | synthetic_inputs
    )


def pine_title_match_rows() -> list[tuple[str, str, str]]:
    inputs = extract_pine_inputs()
    applied = optimizer_applied_pine_param_names()
    ui_only = set(getattr(optimizer_config, "OPTIMIZER_UI_ONLY_PARAMS", ()))
    rows: list[tuple[str, str, str]] = []
    for variable in sorted(inputs):
        title = inputs[variable].title
        if title in applied:
            status = "applied"
        elif title in ui_only:
            status = "ui_only"
        else:
            status = "untracked"
        rows.append((variable, title, status))
    return rows


def validate_optimizer_pine_contract(*, logger: logging.Logger | None = None) -> None:
    contract_logger = logger or log
    inputs = extract_pine_inputs()
    pine_titles = {item.title for item in inputs.values()}
    pine_variables = set(inputs)
    applied = optimizer_applied_pine_param_names()
    ui_only = set(getattr(optimizer_config, "OPTIMIZER_UI_ONLY_PARAMS", ()))

    title_mismatches = sorted(
        f"{item.variable} has title {item.title!r}" for item in inputs.values() if item.variable != item.title
    )
    missing_optimizer_titles = sorted(applied - pine_titles)
    untracked_pine_inputs = sorted(pine_variables - applied - ui_only)

    contract_logger.info("Pine input titles: %s", sorted(pine_titles))
    contract_logger.info("Optimizer param names: %s", sorted(applied))

    errors: list[str] = []
    if title_mismatches:
        errors.append(f"Pine input title(s) must equal variable names: {title_mismatches}")
    if missing_optimizer_titles:
        errors.append(f"Optimizer param(s) missing Pine input title(s): {missing_optimizer_titles}")
    if untracked_pine_inputs:
        errors.append(f"Pine input(s) not searched, recorded, or UI-only: {untracked_pine_inputs}")

    if errors:
        contract_logger.error("Match: ❌ mismatches: %s", errors)
        raise KeyError("; ".join(errors))

    contract_logger.info("Match: ✅ all matched")
