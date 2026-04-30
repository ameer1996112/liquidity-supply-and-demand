from pathlib import Path
import re

from scripts.optimizer import config as optimizer_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PINE_SOURCE = PROJECT_ROOT / "scripts" / "pinescript" / "strategies" / "SND_Strategy.pine"


def _extract_pine_inputs() -> dict[str, str]:
    source = PINE_SOURCE.read_text()
    inputs: dict[str, str] = {}
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
            block += "\n" + lines[index]
            depth += _paren_depth(lines[index])
        match = re.match(r"\s*(?P<name>\w+)\s*=\s*input\.\w+\((?P<body>.*)\)\s*$", block, re.S)
        if match:
            inputs[match.group("name")] = _input_title(match.group("body"))
        index += 1
    return inputs


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
    parts = []
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


def _input_title(args: str) -> str:
    positional = []
    for arg in _split_args(args):
        if arg.startswith("title"):
            match = re.search(r'title\s*=\s*"([^"]*)"', arg)
            if match:
                return match.group(1)
        if "=" not in arg:
            positional.append(arg)
    title_arg = positional[1] if len(positional) > 1 else positional[0]
    match = re.match(r'"([^"]*)"', title_arg)
    assert match is not None
    return match.group(1)


def _searched_param_names() -> set[str]:
    synthetic = set(getattr(optimizer_config, "OPTIMIZER_SYNTHETIC_PARAMS", ()))
    names = set(optimizer_config.OPTUNA_SEARCH_SPACE) - synthetic - {"liq_distance"}
    names.update(item["param"] for item in optimizer_config.LIQ_DISTANCE_RANGES.values())
    return names


def test_optimizer_params_are_backed_by_canonical_pine_input_titles() -> None:
    pine_inputs = _extract_pine_inputs()
    pine_titles = set(pine_inputs.values())

    searched = _searched_param_names()
    assert searched <= pine_titles

    metadata = set(getattr(optimizer_config, "OPTIMIZER_METADATA_PARAMS", ()))
    assert metadata <= pine_titles
    synthetic_inputs = {
        input_name
        for input_names in getattr(
            optimizer_config, "OPTIMIZER_SYNTHETIC_PARAM_INPUTS", {}
        ).values()
        for input_name in input_names
    }
    ui_only = set(getattr(optimizer_config, "OPTIMIZER_UI_ONLY_PARAMS", ()))
    assert set(pine_inputs) <= searched | metadata | synthetic_inputs | ui_only

    for name, title in pine_inputs.items():
        assert title == name
