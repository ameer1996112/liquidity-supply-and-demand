# RD 5-Minute Evidence Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing research-only RD Concepts pipeline with a reproducible six-channel YouTube inventory, local timestamped transcript ingestion, evidence-span extraction, a versioned rule catalog, and benchmark-case validation for the new five-minute detector.

**Architecture:** Keep all network downloads and full transcripts under ignored `data/rd_concepts`, while committing only source metadata, derived rule records, benchmark contracts, and tests. Use the `yt-dlp` CLI behind an injected command runner so production collection is robust and unit tests remain offline. Treat automatically extracted spans as research candidates; only validated catalog records can become executable strategy rules.

**Tech Stack:** Python 3, dataclasses, enums, JSON/JSONL, `yt-dlp`, pytest, existing `scripts.rd_concepts_pipeline` helpers.

---

## Scope Boundary

This plan implements Phase 0A of the approved design. It does not create the new Pine indicator, modify legacy Pine strategy logic, send TradingView alerts, or access broker execution code. A later plan will use the validated catalog and benchmark contracts to build `SND_RD_5M_V1_LAB.pine`.

## File Map

Create:

- `scripts/rd_concepts_pipeline/models.py`: typed source, video, transcript, evidence, and rule contracts.
- `scripts/rd_concepts_pipeline/sources.py`: six-channel registry and deterministic title classification.
- `scripts/rd_concepts_pipeline/youtube_inventory.py`: `yt-dlp` inventory adapter and normalized JSONL output.
- `scripts/rd_concepts_pipeline/youtube_transcripts.py`: transcript command builder and JSON3 parser.
- `scripts/rd_concepts_pipeline/evidence_extractor.py`: timestamped candidate-span extraction.
- `scripts/rd_concepts_pipeline/rule_catalog.py`: catalog loading, validation, precedence, conflicts, and coverage.
- `scripts/rd_concepts_pipeline/benchmark_cases.py`: benchmark-case contracts and validation.
- `scripts/rd_concepts_pipeline/youtube_sync.py`: resumable research-only orchestration CLI.
- `scripts/rd_concepts_pipeline/reference/rd_5m_rules.jsonl`: initial evidence-backed zone rules.
- `scripts/rd_concepts_pipeline/reference/rd_5m_cases.jsonl`: initial manually identified provisional case.
- `scripts/rd_concepts_pipeline/reference/source_snapshot.json`: six-channel inventory snapshot metadata.
- Focused tests and compact JSON fixtures under `tests/rd_concepts_pipeline/`.

Modify:

- `scripts/rd_concepts_pipeline/common.py`: atomic JSON/JSONL writes.
- `scripts/rd_concepts_pipeline/requirements.txt`: declare the `yt-dlp` CLI dependency.
- `scripts/rd_concepts_pipeline/README.md`: document YouTube workflow, outputs, and safety boundary.
- `scripts/rd_concepts_pipeline/run_all.sh`: add an opt-in YouTube sync; preserve Discord-only default behavior.

Do not modify:

- `src/logic.py`
- `src/worker.py`
- Broker adapters or execution services
- Any existing Pine strategy or indicator in this plan

### Task 1: Add Typed Evidence Contracts

**Files:**
- Create: `scripts/rd_concepts_pipeline/models.py`
- Create: `tests/rd_concepts_pipeline/test_models.py`

- [ ] **Step 1: Write failing model validation tests**

```python
from scripts.rd_concepts_pipeline.models import (
    ChannelSource,
    EvidenceClass,
    EvidenceSpan,
    RuleRecord,
    RuleStatus,
    SourceKind,
    SourceRef,
    TranscriptCue,
    VideoRecord,
)


def test_channel_source_builds_videos_url() -> None:
    source = ChannelSource("rd_forex", "RD Forex", "https://www.youtube.com/@RD_Forex", 2, "canonical")
    assert source.videos_url == "https://www.youtube.com/@RD_Forex/videos"


def test_video_record_round_trips_to_mapping() -> None:
    record = VideoRecord(
        source_id="rd_forex",
        video_id="abc123",
        title="Five minute full course",
        url="https://www.youtube.com/watch?v=abc123",
        evidence_class=EvidenceClass.RULE_SOURCE,
        published_at="2026-01-02",
    )
    assert VideoRecord.from_mapping(record.to_mapping()) == record


def test_rule_record_requires_evidence_for_executable_rule() -> None:
    record = RuleRecord(
        rule_id="RD5M-ZONE-001",
        decision_key="zone.origin.demand",
        concept="zone_origin",
        statement="Demand begins from the final bearish origin candle.",
        timeframe="5m",
        market_scope=("all",),
        status=RuleStatus.CONFIRMED,
        executable=True,
        sources=(),
    )
    assert record.validation_errors() == ("executable rule has no evidence source",)


def test_rule_record_round_trips_nested_sources() -> None:
    record = RuleRecord(
        rule_id="RD5M-ZONE-001",
        decision_key="zone.origin.demand",
        concept="zone_origin",
        statement="Demand begins from the final bearish origin candle.",
        timeframe="5m",
        market_scope=("all",),
        status=RuleStatus.CONFIRMED,
        executable=True,
        sources=(
            SourceRef(
                kind=SourceKind.VIDEO,
                source_id="rd_forex",
                evidence_id="abc123:1000-2000",
                url="https://www.youtube.com/watch?v=abc123",
                start_ms=1000,
                end_ms=2000,
            ),
        ),
    )
    assert RuleRecord.from_mapping(record.to_mapping()) == record


def test_evidence_span_requires_normative_and_concept_hits() -> None:
    try:
        EvidenceSpan("abc:0-1000", "abc", 0, 1000, "Never tap it.", (), ("never",))
    except ValueError as exc:
        assert str(exc) == "evidence span must contain a concept hit"
    else:
        raise AssertionError("span without a concept must fail")


def test_transcript_cue_rejects_negative_start() -> None:
    try:
        TranscriptCue(start_ms=-1, duration_ms=1000, text="rule")
    except ValueError as exc:
        assert str(exc) == "start_ms must be non-negative"
    else:
        raise AssertionError("negative start must fail")
```

- [ ] **Step 2: Run the tests and verify the import fails**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_models.py
```

Expected: collection fails with `ModuleNotFoundError: scripts.rd_concepts_pipeline.models`.

- [ ] **Step 3: Implement the model contracts**

Create enums `EvidenceClass`, `RuleStatus`, and `SourceKind` as `str, Enum` classes with these values:

```python
class EvidenceClass(str, Enum):
    RULE_SOURCE = "RULE_SOURCE"
    EDGE_EVIDENCE = "EDGE_EVIDENCE"
    OPERATIONS_EVIDENCE = "OPERATIONS_EVIDENCE"
    NON_RULE = "NON_RULE"


class RuleStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CORROBORATED = "CORROBORATED"
    CONFLICTING = "CONFLICTING"
    UNVERIFIED = "UNVERIFIED"
    SUPERSEDED = "SUPERSEDED"


class SourceKind(str, Enum):
    VIDEO = "VIDEO"
    MANUAL = "MANUAL"
    PROTECTED_INDICATOR = "PROTECTED_INDICATOR"
```

Implement these frozen dataclasses exactly so every later task uses one stable schema:

```python
@dataclass(frozen=True)
class ChannelSource:
    source_id: str
    name: str
    channel_url: str
    priority: int
    role: str

    @property
    def videos_url(self) -> str:
        return f"{self.channel_url.rstrip('/')}/videos"


@dataclass(frozen=True)
class VideoRecord:
    source_id: str
    video_id: str
    title: str
    url: str
    evidence_class: EvidenceClass
    published_at: str | None = None


@dataclass(frozen=True)
class TranscriptCue:
    start_ms: int
    duration_ms: int
    text: str


@dataclass(frozen=True)
class SourceRef:
    kind: SourceKind
    source_id: str
    evidence_id: str
    url: str
    start_ms: int | None = None
    end_ms: int | None = None
    note: str = ""


@dataclass(frozen=True)
class EvidenceSpan:
    span_id: str
    video_id: str
    start_ms: int
    end_ms: int
    text: str
    concepts: tuple[str, ...]
    normative_hits: tuple[str, ...]


@dataclass(frozen=True)
class RuleRecord:
    rule_id: str
    decision_key: str
    concept: str
    statement: str
    timeframe: str
    market_scope: tuple[str, ...]
    status: RuleStatus
    executable: bool
    sources: tuple[SourceRef, ...]
    supersedes: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()
```

Add `to_mapping()` and `from_mapping()` to `VideoRecord`, `SourceRef`, and `RuleRecord`. Serialize enums by `.value` and tuples as JSON arrays; deserialize arrays back to tuples. `RuleRecord.validation_errors()` must enforce:

```python
errors: list[str] = []
if self.executable and self.status not in {RuleStatus.CONFIRMED, RuleStatus.CORROBORATED}:
    errors.append("executable rule is not confirmed")
if self.executable and not self.sources:
    errors.append("executable rule has no evidence source")
if self.timeframe != "5m":
    errors.append("rule timeframe must be 5m")
if not self.market_scope:
    errors.append("rule market_scope is empty")
return tuple(errors)
```

`TranscriptCue.__post_init__()` must reject negative starts, negative durations, and blank text. `EvidenceSpan.__post_init__()` must require `end_ms > start_ms`, nonblank text, at least one concept, and at least one normative hit. `SourceRef.__post_init__()` must require `end_ms > start_ms` when both timestamps are supplied.

- [ ] **Step 4: Run the focused tests**

Run the Task 1 pytest command again.

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/rd_concepts_pipeline/models.py tests/rd_concepts_pipeline/test_models.py
git commit -m "DEV-845: add RD evidence contracts"
```

### Task 2: Register and Classify the Six Sources

**Files:**
- Create: `scripts/rd_concepts_pipeline/sources.py`
- Create: `tests/rd_concepts_pipeline/test_sources.py`

- [ ] **Step 1: Write failing source-registry tests**

```python
from scripts.rd_concepts_pipeline.models import EvidenceClass
from scripts.rd_concepts_pipeline.sources import CHANNEL_SOURCES, classify_video_title


def test_registry_contains_the_six_approved_channels() -> None:
    assert [source.source_id for source in CHANNEL_SOURCES] == [
        "rd_forex",
        "arger_fx",
        "mangoe",
        "rt_futures",
        "charney_fx",
        "trirex",
    ]
    assert [source.priority for source in CHANNEL_SOURCES] == [2, 3, 3, 3, 4, 5]


def test_title_classifier_separates_rules_edges_and_operations() -> None:
    assert classify_video_title("FULL course for LIQUIDITY supply and demand") is EvidenceClass.RULE_SOURCE
    assert classify_video_title("Why I Skipped These 2 Trades") is EvidenceClass.EDGE_EVIDENCE
    assert classify_video_title("Supply & Demand Liquidity Bot: Fully Automated") is EvidenceClass.OPERATIONS_EVIDENCE
    assert classify_video_title("A Year From Now You'll Wish You Started") is EvidenceClass.NON_RULE
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_sources.py
```

Expected: import fails because `sources.py` does not exist.

- [ ] **Step 3: Implement registry and classification**

Define `CHANNEL_SOURCES` with the exact six channel URLs and roles approved in the design. Use compiled, case-insensitive regex groups in this order:

```python
OPERATIONS_PATTERN = re.compile(r"\b(bot|ea|automated|automation|portfolio|drawdown)\b", re.I)
RULE_PATTERN = re.compile(
    r"full (course|guide)|blueprint|checklist|how to (draw|enter|identify)|"
    r"entry confirmation|only trading strategy|5.?minute.*strategy",
    re.I,
)
EDGE_PATTERN = re.compile(
    r"backtest|breakdown|skipp?ed|loss|live trad|perfect setup|week(ly)? recap|"
    r"trade taken|trades? missed",
    re.I,
)
```

Return operations first, then rule source, then edge evidence, then non-rule. This prevents Trirex bot-result titles from being treated as strategy definitions.

- [ ] **Step 4: Run the focused tests**

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/rd_concepts_pipeline/sources.py tests/rd_concepts_pipeline/test_sources.py
git commit -m "DEV-845: register RD video sources"
```

### Task 3: Add Atomic Research Writes and YouTube Inventory

**Files:**
- Modify: `scripts/rd_concepts_pipeline/common.py`
- Create: `scripts/rd_concepts_pipeline/youtube_inventory.py`
- Create: `tests/rd_concepts_pipeline/test_youtube_inventory.py`
- Create: `tests/rd_concepts_pipeline/fixtures/youtube_playlist.json`

- [ ] **Step 1: Add a compact playlist fixture and failing tests**

Use this fixture shape:

```json
{
  "id": "uploads",
  "title": "RD Forex - Videos",
  "entries": [
    {"id": "course1", "title": "FULL course for LIQUIDITY supply and demand", "url": "https://www.youtube.com/watch?v=course1", "upload_date": "20260102"},
    {"id": "mindset1", "title": "A Year From Now You'll Wish You Started", "url": "https://www.youtube.com/watch?v=mindset1", "upload_date": "20260101"}
  ]
}
```

Test that `parse_playlist_json()` returns two `VideoRecord` objects, classifies the first as `RULE_SOURCE`, converts `20260102` to `2026-01-02`, and constructs a watch URL when a flat entry exposes only an ID. Test `sync_inventory()` with an injected runner and assert records are sorted by `source_id`, then `video_id`.

- [ ] **Step 2: Run the focused tests and verify failure**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_youtube_inventory.py
```

Expected: import fails for `youtube_inventory`.

- [ ] **Step 3: Implement atomic JSONL writing**

Add to `common.py`:

```python
def atomic_write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        write_jsonl(temporary, rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
```

- [ ] **Step 4: Implement inventory collection**

In `youtube_inventory.py`, define:

```python
CommandRunner = Callable[[list[str]], str]


def run_command(argv: list[str]) -> str:
    completed = subprocess.run(
        argv,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return completed.stdout


def inventory_command(source: ChannelSource) -> list[str]:
    return ["yt-dlp", "--flat-playlist", "--dump-single-json", source.videos_url]
```

`sync_inventory()` must reject an empty channel response, normalize entries through `parse_playlist_json()`, and atomically write `data_dir / "youtube" / "inventory.jsonl"`. It must not download video media.

- [ ] **Step 5: Run Task 3 tests and the existing common tests**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_youtube_inventory.py tests/rd_concepts_pipeline/test_common.py
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add scripts/rd_concepts_pipeline/common.py scripts/rd_concepts_pipeline/youtube_inventory.py tests/rd_concepts_pipeline/test_youtube_inventory.py tests/rd_concepts_pipeline/fixtures/youtube_playlist.json
git commit -m "DEV-845: add YouTube inventory sync"
```

### Task 4: Parse and Cache Timestamped Transcripts

**Files:**
- Create: `scripts/rd_concepts_pipeline/youtube_transcripts.py`
- Create: `tests/rd_concepts_pipeline/test_youtube_transcripts.py`
- Create: `tests/rd_concepts_pipeline/fixtures/youtube_transcript.json3`
- Modify: `scripts/rd_concepts_pipeline/requirements.txt`

- [ ] **Step 1: Write a JSON3 fixture and failing parser tests**

```json
{
  "events": [
    {"tStartMs": 223000, "dDurationMs": 2000, "segs": [{"utf8": "Never close in the zone."}]},
    {"tStartMs": 225000, "dDurationMs": 2500, "segs": [{"utf8": " Liquidity must take out its own high."}]},
    {"tStartMs": 227500, "dDurationMs": 1000, "segs": [{"utf8": "\n"}]}
  ]
}
```

Tests must assert that `parse_json3_transcript()` returns two cues with preserved millisecond timestamps, trimmed text, and no blank cue. Test `transcript_command()` contains `--skip-download`, both `--write-subs` and `--write-auto-subs`, `--sub-format json3`, and the exact video URL.

- [ ] **Step 2: Verify tests fail**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_youtube_transcripts.py
```

Expected: missing module failure.

- [ ] **Step 3: Implement transcript parsing and command construction**

Implement:

```python
def parse_json3_transcript(payload: Mapping[str, Any]) -> list[TranscriptCue]:
    cues: list[TranscriptCue] = []
    for event in payload.get("events") or []:
        text = "".join(str(segment.get("utf8", "")) for segment in event.get("segs") or []).strip()
        if not text:
            continue
        cues.append(
            TranscriptCue(
                start_ms=int(event.get("tStartMs", 0)),
                duration_ms=max(0, int(event.get("dDurationMs", 0))),
                text=text,
            )
        )
    return cues
```

`cache_transcript()` must write only under `settings.data_dir / "youtube" / "transcripts"`, return `NO_TRANSCRIPT` when no English JSON3 file is produced, and never write transcript text under `scripts/` or `docs/`.

- [ ] **Step 4: Declare the CLI dependency**

Add:

```text
yt-dlp>=2026.3.17
```

Do not add a video-processing dependency; transcript collection is metadata/subtitle-only.

- [ ] **Step 5: Run the focused tests**

Expected: all tests pass without network access.

- [ ] **Step 6: Commit Task 4**

```bash
git add scripts/rd_concepts_pipeline/youtube_transcripts.py scripts/rd_concepts_pipeline/requirements.txt tests/rd_concepts_pipeline/test_youtube_transcripts.py tests/rd_concepts_pipeline/fixtures/youtube_transcript.json3
git commit -m "DEV-845: add timestamped transcript cache"
```

### Task 5: Extract Rule-Bearing Evidence Spans

**Files:**
- Create: `scripts/rd_concepts_pipeline/evidence_extractor.py`
- Create: `tests/rd_concepts_pipeline/test_evidence_extractor.py`

- [ ] **Step 1: Write failing evidence-span tests**

Build cues at 223s, 225s, and 240s. Assert that normative phrases within 15 seconds merge into one span, while a later unrelated cue remains separate. Assert that each span contains concept tags and a stable ID such as `course1:223000-227500`.

```python
def test_extract_evidence_spans_merges_nearby_rule_cues() -> None:
    cues = [
        TranscriptCue(223000, 2000, "Never close in the zone."),
        TranscriptCue(225000, 2500, "Liquidity must take out its own high."),
        TranscriptCue(260000, 1000, "Welcome back to the chart."),
    ]
    spans = extract_evidence_spans("course1", cues, context_ms=15000)
    assert [span.span_id for span in spans] == ["course1:223000-227500"]
    assert {"zone", "liquidity"} <= set(spans[0].concepts)
```

- [ ] **Step 2: Run and verify missing module failure**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_evidence_extractor.py
```

- [ ] **Step 3: Implement cue matching and span merging**

Use compiled normative patterns for `must`, `always`, `never`, `only`, `valid`, `invalid`, `wait`, `do not`, `don't`, and `rule`. Use concept patterns for `zone`, `origin`, `base`, `wick`, `candle`, `departure`, `liquidity`, `sweep`, `entry`, `stop`, `target`, `time`, and `risk`.

An evidence span must contain at least one normative hit and one concept hit. Merge matching cues whose time ranges are separated by at most `context_ms`. Extracted text is written only to ignored local candidate files; committed rule records use paraphrases and source timestamps.

- [ ] **Step 4: Run focused tests**

Expected: all tests pass.

- [ ] **Step 5: Commit Task 5**

```bash
git add scripts/rd_concepts_pipeline/evidence_extractor.py tests/rd_concepts_pipeline/test_evidence_extractor.py
git commit -m "DEV-845: extract RD rule evidence spans"
```

### Task 6: Validate Rule Authority, Conflicts, and Coverage

**Files:**
- Create: `scripts/rd_concepts_pipeline/rule_catalog.py`
- Create: `tests/rd_concepts_pipeline/test_rule_catalog.py`

- [ ] **Step 1: Write failing catalog tests**

Tests must prove:

- Duplicate `rule_id` values fail.
- Two executable rules with the same `decision_key` and contradictory statements fail unless one explicitly supersedes the other.
- A manual source outranks RD Forex, and RD Forex outranks Arger/Mangoe/RT Futures.
- `CONFLICTING`, `UNVERIFIED`, and `SUPERSEDED` rules cannot be executable.
- Coverage reports executable rule IDs missing positive and negative approved cases separately.

Use this precedence fixture:

```python
SOURCE_PRIORITY = {
    SourceKind.MANUAL: 1,
    "rd_forex": 2,
    "arger_fx": 3,
    "mangoe": 3,
    "rt_futures": 3,
    "charney_fx": 4,
    "trirex": 5,
    SourceKind.PROTECTED_INDICATOR: 6,
}
```

- [ ] **Step 2: Run and verify missing module failure**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_rule_catalog.py
```

- [ ] **Step 3: Implement catalog loading and validation**

Implement the module with these deterministic operations:

```python
SOURCE_PRIORITY: Mapping[SourceKind | str, int] = {
    SourceKind.MANUAL: 1,
    "rd_forex": 2,
    "arger_fx": 3,
    "mangoe": 3,
    "rt_futures": 3,
    "charney_fx": 4,
    "trirex": 5,
    SourceKind.PROTECTED_INDICATOR: 6,
}


def load_rule_catalog(path: Path) -> list[RuleRecord]:
    return [RuleRecord.from_mapping(row) for row in read_jsonl(path)]


def source_priority(ref: SourceRef) -> int:
    if ref.kind in {SourceKind.MANUAL, SourceKind.PROTECTED_INDICATOR}:
        return SOURCE_PRIORITY[ref.kind]
    return SOURCE_PRIORITY.get(ref.source_id, 99)


def rule_priority(record: RuleRecord) -> int:
    return min((source_priority(ref) for ref in record.sources), default=99)


def resolve_rule(
    records: Sequence[RuleRecord], decision_key: str
) -> RuleRecord | None:
    superseded_ids = {
        rule_id for record in records for rule_id in record.supersedes
    }
    candidates = [
        record
        for record in records
        if record.decision_key == decision_key
        and record.executable
        and record.status in {RuleStatus.CONFIRMED, RuleStatus.CORROBORATED}
        and record.rule_id not in superseded_ids
    ]
    if not candidates:
        return None
    best_priority = min(rule_priority(record) for record in candidates)
    best = [record for record in candidates if rule_priority(record) == best_priority]
    statements = {record.statement.strip().casefold() for record in best}
    if len(statements) != 1:
        return None
    return min(best, key=lambda record: record.rule_id)


def validate_rule_catalog(records: Sequence[RuleRecord]) -> list[str]:
    errors: list[str] = []
    by_id: dict[str, RuleRecord] = {}
    for record in records:
        if record.rule_id in by_id:
            errors.append(f"duplicate rule_id: {record.rule_id}")
        else:
            by_id[record.rule_id] = record
        errors.extend(
            f"{record.rule_id}: {error}" for error in record.validation_errors()
        )

    known_ids = set(by_id)
    for record in records:
        for related_id in (*record.supersedes, *record.conflicts_with):
            if related_id not in known_ids:
                errors.append(f"{record.rule_id}: unknown related rule {related_id}")

    executable = [record for record in records if record.executable]
    for index, left in enumerate(executable):
        for right in executable[index + 1 :]:
            if left.decision_key != right.decision_key:
                continue
            if left.statement.strip().casefold() == right.statement.strip().casefold():
                continue
            explicitly_resolved = (
                right.rule_id in left.supersedes or left.rule_id in right.supersedes
            )
            if not explicitly_resolved:
                errors.append(
                    f"unresolved executable conflict: {left.rule_id} vs {right.rule_id}"
                )

    for decision_key in {record.decision_key for record in executable}:
        if resolve_rule(records, decision_key) is None:
            errors.append(f"no deterministic executable rule: {decision_key}")
    return sorted(set(errors))


def rule_coverage(
    records: Sequence[RuleRecord], cases: Sequence[Mapping[str, Any]]
) -> dict[str, list[str]]:
    approved = [case for case in cases if case.get("label_status") == "APPROVED"]
    active_rule_ids = sorted(
        record.rule_id
        for record in records
        if record.executable and record.status != RuleStatus.SUPERSEDED
    )
    return {
        "missing_positive": [
            rule_id
            for rule_id in active_rule_ids
            if not any(
                rule_id in case.get("rules", ()) and case.get("expected_zones")
                for case in approved
            )
        ],
        "missing_negative": [
            rule_id
            for rule_id in active_rule_ids
            if not any(
                rule_id in case.get("rules", ()) and case.get("expected_rejections")
                for case in approved
            )
        ],
    }
```

`resolve_rule()` returns `None` when the highest-priority applicable rules still conflict. It must never resolve a conflict by file order. `validate_rule_catalog()` also rejects unknown relation IDs and contradictory executable records without explicit supersession, even when source priority would otherwise select one.

- [ ] **Step 4: Run focused tests**

Expected: all tests pass.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/rd_concepts_pipeline/rule_catalog.py tests/rd_concepts_pipeline/test_rule_catalog.py
git commit -m "DEV-845: validate RD rule authority"
```

### Task 7: Add Benchmark-Case Contracts

**Files:**
- Create: `scripts/rd_concepts_pipeline/benchmark_cases.py`
- Create: `tests/rd_concepts_pipeline/test_benchmark_cases.py`
- Create: `tests/rd_concepts_pipeline/fixtures/rd_5m_case.json`

- [ ] **Step 1: Write a complete benchmark fixture and failing tests**

The fixture must contain:

```json
{
  "case_id": "USDJPY-5M-FORMATION-WICK-001",
  "symbol": "USDJPY",
  "feed": "VANTAGE",
  "timeframe": "5m",
  "label_status": "APPROVED",
  "rules": ["RD5M-ZONE-FORMATION-WICK-DEMAND"],
  "bars": [
    {"time": "2026-07-19T08:00:00Z", "open": 162.290, "high": 162.296, "low": 162.270, "close": 162.275},
    {"time": "2026-07-19T08:05:00Z", "open": 162.274, "high": 162.310, "low": 162.264, "close": 162.305}
  ],
  "expected_zones": [
    {"direction": "DEMAND", "formation": "CONTINUATION", "geometry": "STANDARD", "origin_time": "2026-07-19T08:00:00Z", "confirmation_time": "2026-07-19T08:05:00Z", "top": 162.296, "bottom": 162.264}
  ],
  "expected_rejections": []
}
```

The numbers are a deterministic contract fixture, not a claim that they reproduce the screenshot's exact broker candles. Tests must reject non-5m cases, non-monotonic bar times, `top <= bottom`, expected times absent from bars, and approved cases without rule IDs. Add a second test proving a `PROVISIONAL` case may omit bars and prices only when it contains nonblank `evidence_note` and `expected_behavior` fields.

- [ ] **Step 2: Run and verify missing module failure**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_benchmark_cases.py
```

- [ ] **Step 3: Implement benchmark validation**

Expose `load_benchmark_cases(path)` and `validate_benchmark_case(mapping)`. Return a list of explicit errors rather than raising on the first data issue. Normalize prices with `Decimal(str(value))`; do not use binary float equality in fixture validation.

Validation must branch on `label_status`:

- `APPROVED` requires nonempty `bars`, nonempty `rules`, at least one expected zone or rejection, and every expected origin/confirmation/rejection time must match a fixture bar exactly.
- `PROVISIONAL` is excluded from release coverage and may omit `bars`, numeric geometry, and exact times, but requires nonblank `evidence_note`, nonblank `expected_behavior`, and nonempty `rules`.
- Any other label status is invalid.

- [ ] **Step 4: Run focused tests**

Expected: all tests pass.

- [ ] **Step 5: Commit Task 7**

```bash
git add scripts/rd_concepts_pipeline/benchmark_cases.py tests/rd_concepts_pipeline/test_benchmark_cases.py tests/rd_concepts_pipeline/fixtures/rd_5m_case.json
git commit -m "DEV-845: add RD benchmark contracts"
```

### Task 8: Build the Resumable YouTube Research CLI

**Files:**
- Create: `scripts/rd_concepts_pipeline/youtube_sync.py`
- Create: `tests/rd_concepts_pipeline/test_youtube_sync.py`

- [ ] **Step 1: Write failing CLI orchestration tests**

Test injected inventory and transcript functions rather than invoking network access. Verify:

- `inventory` calls all six sources.
- `transcripts` defaults to `RULE_SOURCE` and `EDGE_EVIDENCE` only.
- Existing successful transcript cache entries are skipped unless `--refresh` is set.
- Per-video transcript failure is recorded and processing continues.
- A channel inventory failure makes the run fail closed.
- Manifest totals equal successes plus failures plus skipped items.

- [ ] **Step 2: Run and verify missing module failure**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_youtube_sync.py
```

- [ ] **Step 3: Implement subcommands and manifest**

Support:

```text
python scripts/rd_concepts_pipeline/youtube_sync.py inventory
python scripts/rd_concepts_pipeline/youtube_sync.py transcripts
python scripts/rd_concepts_pipeline/youtube_sync.py evidence
python scripts/rd_concepts_pipeline/youtube_sync.py all
```

Add `--source`, `--refresh`, and `--include-operations`. Write `data/rd_concepts/youtube/manifest.json` atomically with `started_at`, `completed_at`, selected source IDs, selected classes, counts, and redacted failures. Do not require Discord authorization.

- [ ] **Step 4: Run focused tests**

Expected: all tests pass.

- [ ] **Step 5: Commit Task 8**

```bash
git add scripts/rd_concepts_pipeline/youtube_sync.py tests/rd_concepts_pipeline/test_youtube_sync.py
git commit -m "DEV-845: orchestrate RD YouTube evidence sync"
```

### Task 9: Seed Versioned Sources, Rules, and the First Manual Case

**Files:**
- Create: `scripts/rd_concepts_pipeline/reference/source_snapshot.json`
- Create: `scripts/rd_concepts_pipeline/reference/rd_5m_rules.jsonl`
- Create: `scripts/rd_concepts_pipeline/reference/rd_5m_cases.jsonl`
- Create: `tests/rd_concepts_pipeline/test_reference_catalog.py`

- [ ] **Step 1: Write failing reference-catalog tests**

Assert the source snapshot contains exactly these counts from 2026-07-19:

```python
{
    "rd_forex": 55,
    "arger_fx": 33,
    "mangoe": 123,
    "rt_futures": 21,
    "charney_fx": 79,
    "trirex": 81,
}
```

Assert initial rule IDs are unique and include:

```text
RD5M-ZONE-ORIGIN-DEMAND
RD5M-ZONE-ORIGIN-SUPPLY
RD5M-ZONE-STANDARD-BOUNDS
RD5M-ZONE-ACCURACY-DEMAND
RD5M-ZONE-ACCURACY-SUPPLY
RD5M-ZONE-UNTAPPED
RD5M-ZONE-DEPARTURE-WICK-EXCEPTION
RD5M-ZONE-FORMATION-WICK-DEMAND
```

Assert the first versioned case is `PROVISIONAL`, references `RD5M-ZONE-FORMATION-WICK-DEMAND`, and is not counted as release coverage until exact TradingView OHLC and timestamps replace the screenshot-derived observation.

- [ ] **Step 2: Run and verify missing files fail**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_reference_catalog.py
```

- [ ] **Step 3: Add the source snapshot**

Store `captured_at`, all six channel URLs, counts, and `total_videos: 392`. Mark the snapshot immutable; future refreshes create a new dated snapshot rather than changing historical counts silently.

- [ ] **Step 4: Add initial rule records with exact evidence**

Use RD Forex video `kxh_3__oAqg` and these millisecond ranges:

```text
Untapped/fresh rule:                 238000-299000
Departure-wick tap exception:       264000-288000
Standard supply bounds:             509000-516000
Accuracy supply condition/bounds:   527000-549000 and 659000-679000
Standard demand bounds:             596000-611000
Accuracy demand condition/bounds:   617000-631000
```

Use a `MANUAL` source dated 2026-07-19 for `RD5M-ZONE-FORMATION-WICK-DEMAND`: a same-direction bullish formation candle can extend the demand distal boundary below the bearish origin low before confirmation. Mark all rules executable only when their status is `CONFIRMED` or `CORROBORATED` and their catalog validation passes.

- [ ] **Step 5: Add the provisional USDJPY case record**

Record symbol `USDJPY`, feed `VANTAGE`, timeframe `5m`, observed date `2026-07-19`, direction `DEMAND`, and the expected formation-envelope behavior. Keep it `PROVISIONAL` until exact OHLC is exported; do not fabricate approved prices in the versioned case file.

- [ ] **Step 6: Run the reference tests and catalog validation**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline/test_reference_catalog.py tests/rd_concepts_pipeline/test_rule_catalog.py tests/rd_concepts_pipeline/test_benchmark_cases.py
```

Expected: all tests pass; release coverage reports the provisional case as missing approved coverage.

- [ ] **Step 7: Commit Task 9**

```bash
git add scripts/rd_concepts_pipeline/reference tests/rd_concepts_pipeline/test_reference_catalog.py
git commit -m "DEV-845: seed RD 5m evidence catalog"
```

### Task 10: Document and Verify the Phase 0A Pipeline

**Files:**
- Modify: `scripts/rd_concepts_pipeline/README.md`
- Modify: `scripts/rd_concepts_pipeline/run_all.sh`
- Test: `tests/rd_concepts_pipeline/`

- [ ] **Step 1: Add a failing documentation contract test**

Add to `tests/rd_concepts_pipeline/test_reference_catalog.py`:

```python
def test_readme_documents_youtube_safety_and_commands() -> None:
    text = Path("scripts/rd_concepts_pipeline/README.md").read_text()
    assert "youtube_sync.py inventory" in text
    assert "youtube_sync.py transcripts" in text
    assert "Full transcripts remain under ignored data/rd_concepts" in text
    assert "does not execute trades" in text
```

- [ ] **Step 2: Run the test and verify it fails on missing documentation**

Run the focused reference test.

Expected: assertion failure for the YouTube commands.

- [ ] **Step 3: Update README and opt-in orchestration**

Document installation, inventory, transcript, evidence, and all commands; the four evidence classes; source precedence; ignored outputs; rule catalog validation; and the boundary between research and execution.

Update `run_all.sh` so Discord behavior remains unchanged unless the caller sets `RD_INCLUDE_YOUTUBE=1`:

```bash
if [[ "${RD_INCLUDE_YOUTUBE:-0}" == "1" ]]; then
    python scripts/rd_concepts_pipeline/youtube_sync.py all
fi
```

- [ ] **Step 4: Run Phase 0A verification**

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/rd_concepts_pipeline
```

Expected: all RD Concepts pipeline tests pass.

```bash
source ./venv/bin/activate && PYTHONPATH=. python -m compileall -q scripts/rd_concepts_pipeline
```

Expected: exit code 0 with no output.

```bash
git diff --check
```

Expected: exit code 0.

- [ ] **Step 5: Run one explicit live inventory smoke test**

```bash
source ./venv/bin/activate && PYTHONPATH=. python scripts/rd_concepts_pipeline/youtube_sync.py inventory
```

Expected: six successful channel manifests, 392 videos for the dated baseline snapshot, no video media downloads, and output only under ignored `data/rd_concepts/youtube`. If counts have legitimately changed since 2026-07-19, preserve the historical snapshot and write the new count to the runtime manifest.

- [ ] **Step 6: Commit Task 10**

```bash
git add scripts/rd_concepts_pipeline/README.md scripts/rd_concepts_pipeline/run_all.sh tests/rd_concepts_pipeline/test_reference_catalog.py
git commit -m "DEV-845: document RD evidence workflow"
```

## Phase 0A Done Means

- All six approved channels are represented by typed, versioned source metadata.
- The pipeline can inventory channels and cache English transcript data without downloading video media.
- Full transcripts remain ignored local research data.
- Candidate evidence spans retain exact timestamps and concept tags.
- Rule catalog validation fails closed on duplicate IDs, unresolved conflicts, invalid executable status, or missing evidence.
- Benchmark contracts distinguish provisional observations from approved release fixtures.
- The initial zone rules and USDJPY formation-wick observation are versioned.
- All `tests/rd_concepts_pipeline` tests and compile checks pass.
- No Pine, backend execution, worker, or broker file changes are included.

## Next Plan

After Phase 0A passes, create a separate Phase 0B corpus-curation plan. It will process every `RULE_SOURCE` and relevant `EDGE_EVIDENCE` transcript, attach visual timestamps, resolve rule supersession, and build approved positive/negative cases before the Pine detector implementation plan begins.
