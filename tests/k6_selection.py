"""k6_selection.py — K6 변조행 판정을 「이번 변경이 닿은 행」으로 좁히는 선택 코어.

tests/run.sh 의 T37-15(K6)가 부르는 **순수 로직**이다 — 입력 파일을 읽어 stdout 에 레코드를
낸다. git · 미러 · 하위 프로세스 · 파일 쓰기를 쓰지 않으므로 합성 fixture 만으로 전 기능을
시험할 수 있다(T37-21~T37-23). 규칙의 정본은 docs/prps/t37-incremental-k6.md §3 이고 이
파일이 그 구현이다 — 규칙(R1~R5)과 전체 재확인 트리거를 바꾸려면 그 문서를 먼저 고친다.

선택의 안전 방향은 **넓은 쪽**이다. 이 코어가 틀려서 행이 조용히 빠지면 K6 가 공허하게
통과하므로, 판단이 애매한 자리는 더 많이 고르는 쪽으로 기울인다(과선택은 시간만 쓴다).

전체 재확인(FULL) 트리거 — tests/run.sh 의 변경 줄 중 주석·빈 줄이 아닌 줄이 아래에 있을 때:
  1. 등록 그룹 함수가 아닌 함수(헬퍼·러너·사전 점검·하네스 함수)
  2. 하네스 그룹 함수(T37 자신)
  3. 함수 밖 최상위 코드 중 단일 줄 `readonly 이름=값` 상수가 아닌 것(배열·트랩·main 호출 …)
  4. 이 파일(tests/k6_selection.py)의 모든 변경 — 호출자가 변경 파일 목록으로 알려 준다
행 선택 규칙(변조행마다 하나라도 맞으면 고른다):
  R1 ledger  원장 diff 의 추가·변경된 데이터 줄
  R2 target  target_path 가 바뀐 파일 목록에 든 행(파일 단위)
  R3 block   변경 줄(주석 포함)이 그 행의 가드 블록 안에 있다
  R4 name    바뀐 정의(상수·그룹 함수 지역 변수)의 이름을 가드 블록이 참조한다
  R5 later   같은 그룹 함수에서 보고 줄보다 앞선 조기 종료 줄·공용 줄이 바뀌었다
  -  unresolved  토큰 보고 줄이 정확히 1건이 아니어서 블록을 정할 수 없다(행 단위 fail-close)

한계(비망라) — 블록 정의는 이 저장소의 머리 주석 관례(첫 낱말이 서브체크 ID)에 기댄다. 관례를
벗어난 가드는 앞뒤 여유(margin)와 R5 가 덮는 범위까지만 덮인다. 여러 줄 따옴표 문자열 안의
`#` 줄은 주석으로 보고, 여러 열린 heredoc 이 한 줄에 겹치는 형태는 첫 것만 본다. 전수 증명이
아니다.
"""

from __future__ import annotations

import argparse
import bisect
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

# tests/run.sh 의 FAILURE_REPORT_LINE_PATTERN 과 같은 정의 — T37-13 의 판별자 자격(보고 줄
# 정확히 1건)과 같은 분모를 봐야 하므로 두 곳이 어긋나면 안 된다.
FAILURE_REPORT_LINE_PATTERN = re.compile(
    r"^\s*(note_failure|record_failure|log_error|echo)\s", re.ASCII
)
NOTE_OR_RECORD_FAILURE_PATTERN = re.compile(r"^\s*(?:note_failure|record_failure)\s", re.ASCII)
FUNCTION_DEFINITION_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(\) \{")
CLOSING_BRACE_PATTERN = re.compile(r"^\}")
HEREDOC_OPEN_PATTERN = re.compile(r"(?<!<)<<(?!<)(-?)\s*(['\"]?)([A-Za-z_]\w*)\2", re.ASCII)
COMMENT_OR_BLANK_PATTERN = re.compile(r"^\s*(#|$)", re.ASCII)
TOP_LEVEL_CONSTANT_PATTERN = re.compile(r"^readonly ([A-Z_][A-Z0-9_]*)=(.*)$")
ASSIGNMENT_PATTERN = re.compile(r"^\s*(local\s+)?([A-Za-z_]\w*)=", re.ASCII)
LOCAL_DECLARATION_PATTERN = re.compile(r"^\s*local\s+([A-Za-z_][\w ]*)$", re.ASCII)
LOCAL_ASSIGNMENT_NAME_PATTERN = re.compile(r"(?:^|\s)([A-Za-z_]\w*)=", re.ASCII)
EARLY_EXIT_PATTERN = re.compile(r"\b(return|exit|record_failure)\b", re.ASCII)
GUARD_COMMENT_HEAD_PATTERN = re.compile(
    r"^\s*#\s*(?:-+\s*)?(T[0-9]+-[0-9a-z]+)(?![0-9a-z])", re.ASCII
)
GUARD_REPORT_ID_PATTERN = re.compile(r"\"(T[0-9]+-[0-9a-z]+)[: (]", re.ASCII)
HUNK_HEADER_PATTERN = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

TOP_LEVEL_LABEL = "top-level"
CORE_FILE_LABEL = "k6_selection.py"
ROW_FIELD_COUNT = 8
EXIT_USAGE_ERROR = 2

REASON_ORDER = ("ledger", "target", "block", "name", "later", "unresolved")


@dataclass(frozen=True)
class MutationRow:
    """원장 변조행 한 줄 — 선택에 쓰는 열만 담는다."""

    guard_id: str
    target_path: str
    expect_token: str


@dataclass(frozen=True)
class SourceChange:
    """diff 의 변경 줄 하나(새 쪽 좌표). `-` 줄의 위치는 hunk 의 새 쪽 시작이다(순수 삭제는 앞 줄)."""

    position: int
    sign: str
    text: str


@dataclass(frozen=True)
class FunctionSpan:
    """최상위 함수 정의 하나 — start 는 `이름() {` 줄, end 는 마지막 열 0 `}` 줄."""

    start: int
    end: int
    name: str


@dataclass(frozen=True)
class GuardBlock:
    """한 변조행의 가드 블록 — [low, high] 는 앞뒤 여유를 붙이고 함수 구간으로 자른 줄 범위."""

    guard_id: str
    low: int
    high: int
    function: str | None
    report_line: int


@dataclass(frozen=True)
class SourceClassification:
    """run.sh 변경 줄의 분류 결과 — 전체 재확인 사유와 R3·R4·R5 의 재료."""

    full_reasons: tuple[str, ...]
    changed_positions: tuple[int, ...]
    defined_names: frozenset[str]
    later_points: tuple[tuple[str, int], ...]


def split_lines(text: str) -> list[str]:
    """텍스트를 줄 목록으로 나눈다 — 끝의 개행이 만드는 빈 마지막 원소는 뺀다(줄 번호가 grep 과 같다)."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _read_hunk_body(
    lines: Sequence[str],
    index: int,
    counts: tuple[int, int, int],
    changes: list[SourceChange],
) -> int:
    """hunk 본문에서 `-` 줄 old_count 개와 `+` 줄 new_count 개를 읽고 다음 줄 번호를 낸다."""
    removed_left, new_start, added_left = counts
    anchor = max(new_start, 1) if added_left == 0 else new_start
    position = new_start
    while index < len(lines) and (removed_left > 0 or added_left > 0):
        line = lines[index]
        if line.startswith("\\"):
            index += 1
            continue
        if line.startswith("-") and removed_left > 0:
            changes.append(SourceChange(anchor, "-", line[1:]))
            removed_left -= 1
        elif line.startswith("+") and added_left > 0:
            changes.append(SourceChange(position, "+", line[1:]))
            position += 1
            added_left -= 1
        else:
            break
        index += 1
    return index


def parse_zero_context_diff(text: str) -> tuple[SourceChange, ...]:
    """`git diff -U0` 원문에서 변경 줄을 새 쪽 좌표로 뽑는다(헤더·hunk 밖 줄은 무시한다)."""
    lines = text.split("\n")
    changes: list[SourceChange] = []
    index = 0
    while index < len(lines):
        header = HUNK_HEADER_PATTERN.match(lines[index])
        index += 1
        if header is None:
            continue
        old_count = 1 if header.group(2) is None else int(header.group(2))
        new_count = 1 if header.group(4) is None else int(header.group(4))
        counts = (old_count, int(header.group(3)), new_count)
        index = _read_hunk_body(lines, index, counts, changes)
    return tuple(changes)


def _find_heredoc_close(lines: Sequence[str], start: int, word: str, strip_tabs: bool) -> int | None:
    """start(0 기준) 이후에서 heredoc 을 닫는 줄의 0 기준 번호를 낸다. 없으면 None."""
    for index in range(start, len(lines)):
        candidate = lines[index].lstrip("\t") if strip_tabs else lines[index]
        if candidate == word:
            return index
    return None


def heredoc_line_numbers(lines: Sequence[str]) -> frozenset[int]:
    """heredoc 본문과 닫는 줄의 1 기준 줄 번호 집합. 여는 줄 자신은 코드라서 넣지 않는다."""
    inside: set[int] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        opened = None if COMMENT_OR_BLANK_PATTERN.match(line) else HEREDOC_OPEN_PATTERN.search(line)
        close_index = None
        if opened is not None:
            close_index = _find_heredoc_close(lines, index + 1, opened.group(3), opened.group(1) == "-")
        if close_index is None:
            index += 1
            continue
        inside.update(range(index + 2, close_index + 2))
        index = close_index + 1
    return frozenset(inside)


def function_spans(
    lines: Sequence[str], heredoc: frozenset[int] = frozenset()
) -> tuple[FunctionSpan, ...]:
    """최상위 함수 구간 목록. 끝은 다음 정의 직전까지에서 마지막 열 0 `}` 줄이다(heredoc 안의 `}` 는 뺀다)."""
    starts = [
        (number, match.group(1))
        for number, line in enumerate(lines, 1)
        if number not in heredoc and (match := FUNCTION_DEFINITION_PATTERN.match(line))
    ]
    spans = []
    for order, (start, name) in enumerate(starts):
        limit = starts[order + 1][0] - 1 if order + 1 < len(starts) else len(lines)
        end = start
        for number in range(limit, start, -1):
            if number not in heredoc and CLOSING_BRACE_PATTERN.match(lines[number - 1]):
                end = number
                break
        spans.append(FunctionSpan(start, end, name))
    return tuple(spans)


class SpanLocator:
    """줄 번호가 어느 함수 구간에 드는지 찾는다(구간 밖이면 None = 최상위)."""

    def __init__(self, spans: Sequence[FunctionSpan]) -> None:
        self._spans = list(spans)
        self._starts = [span.start for span in self._spans]

    def locate(self, position: int) -> FunctionSpan | None:
        """position 을 감싼 함수 구간. 없으면 None."""
        index = bisect.bisect_right(self._starts, position) - 1
        if index >= 0 and position <= self._spans[index].end:
            return self._spans[index]
        return None


def _mention_index(lines: Sequence[str]) -> dict[str, list[int]]:
    """서브체크 ID → 그 ID 를 머리에 두는 줄 번호들 — 주석 머리줄 또는 note_failure/record_failure 첫 메시지."""
    index: dict[str, list[int]] = {}
    for number, line in enumerate(lines, 1):
        head = GUARD_COMMENT_HEAD_PATTERN.match(line)
        if head is not None:
            index.setdefault(head.group(1), []).append(number)
        if NOTE_OR_RECORD_FAILURE_PATTERN.match(line):
            for guard_id in dict.fromkeys(GUARD_REPORT_ID_PATTERN.findall(line)):
                index.setdefault(guard_id, []).append(number)
    return index


def _clip_block(
    positions: Sequence[int], margin: int, span: FunctionSpan | None, line_count: int
) -> tuple[int, int]:
    """언급·보고 줄 위치에 앞뒤 여유를 붙이고 함수 구간(없으면 파일 전체)으로 자른다."""
    floor = span.start if span is not None else 1
    ceiling = span.end if span is not None else line_count
    return max(min(positions) - margin, floor), min(max(positions) + margin, ceiling)


def guard_blocks(
    rows: Sequence[MutationRow],
    lines: Sequence[str],
    spans: Sequence[FunctionSpan],
    margin: int,
) -> Mapping[str, GuardBlock | None]:
    """변조행마다 가드 블록을 낸다. 토큰 보고 줄이 정확히 1건이 아니면 None(블록 미상)."""
    locator = SpanLocator(spans)
    mentions = _mention_index(lines)
    report_numbers = [
        number for number, line in enumerate(lines, 1) if FAILURE_REPORT_LINE_PATTERN.match(line)
    ]
    blocks: dict[str, GuardBlock | None] = {}
    for row in rows:
        hits = [number for number in report_numbers if row.expect_token in lines[number - 1]]
        if len(hits) != 1:
            blocks[row.guard_id] = None
            continue
        span = locator.locate(hits[0])
        same_container = [
            number for number in mentions.get(row.guard_id, ()) if locator.locate(number) == span
        ]
        low, high = _clip_block([hits[0], *same_container], margin, span, len(lines))
        blocks[row.guard_id] = GuardBlock(
            row.guard_id, low, high, span.name if span is not None else None, hits[0]
        )
    return blocks


def _covered_lines_of_function(
    span: FunctionSpan, mentions: Mapping[str, Sequence[int]], margin: int, locator: SpanLocator
) -> bytearray:
    """함수 안에서 언급되는 모든 서브체크 ID(면제행·미등록 포함)의 블록이 덮는 줄 표시(1 이면 덮임)."""
    covered = bytearray(span.end - span.start + 1)
    for positions in mentions.values():
        inside = [position for position in positions if locator.locate(position) == span]
        if not inside:
            continue
        low, high = _clip_block(inside, margin, span, span.end)
        for number in range(low, high + 1):
            covered[number - span.start] = 1
    return covered


def defined_names(text: str) -> tuple[str, ...]:
    """한 줄이 정의하는 변수 이름들(그룹 함수 안 `local 이름=`·`이름=`·`local 이름…`). 정의가 아니면 빈 튜플."""
    declaration = LOCAL_DECLARATION_PATTERN.match(text)
    if declaration is not None:
        return tuple(declaration.group(1).split())
    assignment = ASSIGNMENT_PATTERN.match(text)
    if assignment is None:
        return ()
    if assignment.group(1) is not None:
        names = LOCAL_ASSIGNMENT_NAME_PATTERN.findall(text[text.index("local") + len("local"):])
        return tuple(names) or (assignment.group(2),)
    return (assignment.group(2),)


def _top_level_constant_name(text: str) -> str | None:
    """단일 줄 `readonly 이름=값` 상수면 이름을 낸다. 값이 `(` 로 시작하는 배열이면 None."""
    match = TOP_LEVEL_CONSTANT_PATTERN.match(text)
    if match is None or match.group(2).startswith("("):
        return None
    return match.group(1)


class _ChangeClassifier:
    """변경 줄을 하나씩 분류해 SourceClassification 의 재료를 모은다."""

    def __init__(
        self,
        lines: Sequence[str],
        spans: Sequence[FunctionSpan],
        heredoc: frozenset[int],
        group_functions: frozenset[str],
        harness_function: str,
        margin: int,
    ) -> None:
        self._lines = lines
        self._locator = SpanLocator(spans)
        self._spans = {span.name: span for span in spans}
        self._heredoc = heredoc
        self._group_functions = group_functions
        self._harness_function = harness_function
        self._margin = margin
        self._mentions = _mention_index(lines)
        self._covered: dict[str, bytearray] = {}
        self.full_reasons: list[str] = []
        self.names: set[str] = set()
        self.later_points: list[tuple[str, int]] = []

    def _is_covered_by_guard_block(self, function: str, position: int) -> bool:
        """그 함수 안에서 언급되는 어떤 서브체크 ID 의 블록이든 position 을 덮는지."""
        if function not in self._covered:
            self._covered[function] = _covered_lines_of_function(
                self._spans[function], self._mentions, self._margin, self._locator
            )
        span = self._spans[function]
        return bool(self._covered[function][position - span.start])

    def _classify_group_function_line(self, function: str, change: SourceChange) -> None:
        names = defined_names(change.text)
        self.names.update(names)
        position = min(max(change.position, 1), len(self._lines))
        if EARLY_EXIT_PATTERN.search(change.text) or (
            not names and not self._is_covered_by_guard_block(function, position)
        ):
            self.later_points.append((function, position))

    def classify(self, change: SourceChange) -> None:
        """변경 줄 하나를 분류한다(주석·빈 줄은 R3 위치만 쓰이므로 여기서는 무시한다)."""
        position = min(max(change.position, 1), len(self._lines))
        in_heredoc = position in self._heredoc
        if COMMENT_OR_BLANK_PATTERN.match(change.text) and not in_heredoc:
            return
        removed_definition = (
            change.sign == "-" and FUNCTION_DEFINITION_PATTERN.match(change.text)
        )
        if removed_definition:
            self.full_reasons.append(removed_definition.group(1))
            return
        constant = None if in_heredoc else _top_level_constant_name(change.text)
        if constant is not None:
            self.names.add(constant)
            return
        span = self._locator.locate(position)
        if span is None:
            self.full_reasons.append(TOP_LEVEL_LABEL)
        elif span.name not in self._group_functions or span.name == self._harness_function:
            self.full_reasons.append(span.name)
        elif not in_heredoc:
            self._classify_group_function_line(span.name, change)


def classify_source_changes(
    changes: Sequence[SourceChange],
    lines: Sequence[str],
    spans: Sequence[FunctionSpan],
    heredoc: frozenset[int],
    group_functions: frozenset[str],
    harness_function: str,
    margin: int,
) -> SourceClassification:
    """run.sh 의 변경 줄을 분류한다 — 전체 재확인 사유(공용 부분)와 R3·R4·R5 의 재료를 낸다."""
    classifier = _ChangeClassifier(lines, spans, heredoc, group_functions, harness_function, margin)
    for change in changes:
        classifier.classify(change)
    return SourceClassification(
        full_reasons=tuple(dict.fromkeys(classifier.full_reasons)),
        changed_positions=tuple(min(max(change.position, 1), len(lines)) for change in changes),
        defined_names=frozenset(classifier.names),
        later_points=tuple(classifier.later_points),
    )


def _name_reference_pattern(names: frozenset[str]) -> re.Pattern[str] | None:
    """바뀐 정의 이름 중 하나라도 참조하는 줄을 찾는 정규식(`$이름`·`${이름}`, 대문자 이름은 맨 낱말도)."""
    if not names:
        return None
    alternatives = []
    for name in sorted(names):
        escaped = re.escape(name)
        alternatives.append(r"\$\{?[#!]?" + escaped + r"\b")
        if name.isupper():
            alternatives.append(r"\b" + escaped + r"\b")
    return re.compile("|".join(alternatives), re.ASCII)


def _block_references(block: GuardBlock, lines: Sequence[str], pattern: re.Pattern[str] | None) -> bool:
    """가드 블록의 줄 중 하나라도 바뀐 정의의 이름을 참조하는지(R4)."""
    if pattern is None:
        return False
    return any(pattern.search(lines[number - 1]) for number in range(block.low, block.high + 1))


def _later_point_precedes_report(block: GuardBlock, later_points: Sequence[tuple[str, int]]) -> bool:
    """같은 그룹 함수에서 보고 줄보다 앞선 변경 줄(조기 종료·공용 줄)이 있는지(R5)."""
    if block.function is None:
        return False
    return any(
        function == block.function and position < block.report_line
        for function, position in later_points
    )


def select_rows(
    rows: Sequence[MutationRow],
    changed_files: frozenset[str],
    ledger_changed_ids: frozenset[str],
    classification: SourceClassification,
    blocks: Mapping[str, GuardBlock | None],
    lines: Sequence[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """변조행마다 근거(R1~R5·unresolved)를 모아, 근거가 하나라도 있는 행만 원장 순서로 낸다."""
    reference_pattern = _name_reference_pattern(classification.defined_names)
    selected = []
    for row in rows:
        reasons = set()
        if row.guard_id in ledger_changed_ids:
            reasons.add("ledger")
        if row.target_path in changed_files:
            reasons.add("target")
        block = blocks.get(row.guard_id)
        if block is None:
            reasons.add("unresolved")
        else:
            if any(block.low <= position <= block.high for position in classification.changed_positions):
                reasons.add("block")
            if _block_references(block, lines, reference_pattern):
                reasons.add("name")
            if _later_point_precedes_report(block, classification.later_points):
                reasons.add("later")
        if reasons:
            selected.append((row.guard_id, tuple(reason for reason in REASON_ORDER if reason in reasons)))
    return tuple(selected)


def parse_mutation_rows(text: str) -> tuple[MutationRow, ...]:
    """파싱된 원장(탭 구분 8열) 텍스트에서 변조행(3열이 `-` 가 아닌 행)만 원장 순서로 낸다."""
    rows = []
    for number, line in enumerate(split_lines(text), 1):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != ROW_FIELD_COUNT:
            raise ValueError(f"ledger row {number}: expected {ROW_FIELD_COUNT} columns, got {len(fields)}")
        if fields[2] != "-":
            rows.append(MutationRow(fields[0], fields[1], fields[4]))
    return tuple(rows)


def ledger_changed_guard_ids(changes: Sequence[SourceChange]) -> frozenset[str]:
    """원장 diff 에서 추가·변경된 데이터 줄(`+`, 주석·빈 줄 제외)의 guard_id 집합."""
    return frozenset(
        change.text.split("\t")[0]
        for change in changes
        if change.sign == "+" and not COMMENT_OR_BLANK_PATTERN.match(change.text)
    )


def parse_group_functions(text: str) -> dict[str, str]:
    """`<그룹ID>\\t<함수명>` 줄들을 그룹 ID → 함수명 사전으로 읽는다."""
    mapping = {}
    for line in split_lines(text):
        fields = line.split("\t")
        if len(fields) != 2 or not all(fields):
            raise ValueError(f"group function line is malformed: {line!r}")
        mapping[fields[0]] = fields[1]
    return mapping


def _read(path: str) -> str:
    """UTF-8 텍스트 파일 하나를 읽는다(읽기 실패는 호출자 main 이 입력 이상으로 처리한다)."""
    return Path(path).read_text(encoding="utf-8")


def format_parse_diff_records(changes: Sequence[SourceChange]) -> list[str]:
    """parse-diff 출력 — `<위치>\\t<부호>\\t<code|comment>` (종류는 줄 텍스트만으로 정한다)."""
    return [
        f"{change.position}\t{change.sign}\t"
        f"{'comment' if COMMENT_OR_BLANK_PATTERN.match(change.text) else 'code'}"
        for change in changes
    ]


def run_select(arguments: argparse.Namespace) -> list[str]:
    """select 명령 — 입력 파일을 읽어 FULL·ROW·EXAMINED·RUNSH_CHANGES·LEDGER_CHANGES 레코드를 낸다."""
    lines = split_lines(_read(arguments.source))
    rows = parse_mutation_rows(_read(arguments.mutation_rows))
    changed_files = frozenset(split_lines(_read(arguments.changed_files)))
    run_sh_changes = parse_zero_context_diff(_read(arguments.run_sh_diff))
    ledger_changes = parse_zero_context_diff(_read(arguments.ledger_diff))
    group_functions = parse_group_functions(_read(arguments.group_functions))
    if arguments.harness_group not in group_functions:
        raise ValueError(f"harness group {arguments.harness_group!r} is not registered")
    if arguments.margin < 0:
        raise ValueError(f"margin must not be negative: {arguments.margin}")
    heredoc = heredoc_line_numbers(lines)
    spans = function_spans(lines, heredoc)
    classification = classify_source_changes(
        run_sh_changes, lines, spans, heredoc, frozenset(group_functions.values()),
        group_functions[arguments.harness_group], arguments.margin,
    )
    blocks = guard_blocks(rows, lines, spans, arguments.margin)
    selected = select_rows(
        rows, changed_files, ledger_changed_guard_ids(ledger_changes), classification, blocks, lines
    )
    full_reasons = list(classification.full_reasons)
    if arguments.core_repo_path in changed_files:
        full_reasons.append(CORE_FILE_LABEL)
    records = [f"FULL\t{reason}" for reason in full_reasons]
    records += [f"ROW\t{guard_id}\t{','.join(reasons)}" for guard_id, reasons in selected]
    records += [
        f"EXAMINED\t{len(rows)}",
        f"RUNSH_CHANGES\t{len(run_sh_changes)}",
        f"LEDGER_CHANGES\t{len(ledger_changes)}",
    ]
    return records


def build_argument_parser() -> argparse.ArgumentParser:
    """명령행 인자 정의 — parse-diff 와 select 두 하위 명령. 도움말은 로케일과 무관하게 ASCII 로 쓴다."""
    parser = argparse.ArgumentParser(
        prog="k6_selection.py",
        description="K6 mutation row selection core (see docs/prps/t37-incremental-k6.md).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    parse_diff = commands.add_parser("parse-diff", help="print changed lines of a -U0 diff file")
    parse_diff.add_argument("diff_file")
    select = commands.add_parser("select", help="print full-recheck reasons and selected rows")
    for name in ("source", "mutation-rows", "changed-files", "run-sh-diff", "ledger-diff",
                 "group-functions", "harness-group", "core-repo-path"):
        select.add_argument(f"--{name}", required=True)
    select.add_argument("--margin", type=int, required=True)
    return parser


def main(argv: Sequence[str]) -> int:
    """진입점 — 입력 이상(읽기 실패·열 수 불일치 등)은 사유를 stderr 에 내고 2 를 반환한다."""
    arguments = build_argument_parser().parse_args(argv)
    try:
        if arguments.command == "parse-diff":
            records = format_parse_diff_records(parse_zero_context_diff(_read(arguments.diff_file)))
        else:
            records = run_select(arguments)
    except (OSError, ValueError) as error:
        print(f"k6_selection: input error: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    for record in records:
        print(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
