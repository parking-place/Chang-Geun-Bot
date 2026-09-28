"""Public natural-language command inventory and bounded Jev selection.

The model selects an identifier from this closed table. It never supplies
database IDs, Discord IDs, URLs or arguments to the executor.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from changgeun.domain.models import DomainError, InferenceTrace
from changgeun.nlp.pipeline import DecisionPort, anonymized

REFERENCE = re.compile(r"<([@#])[!&]?(\d{17,20})>")
URL = re.compile(
    r"(?<![\w@./:-])(?:https?://[^\s<>]+|"
    r"(?:(?:www\.|m\.)?youtube\.com|youtu\.be)/[^\s<>]+)",
    re.IGNORECASE,
)


def safe_utterance(value: str) -> str:
    """Keep distinct references while withholding their actual IDs and URLs."""
    refs: dict[tuple[str, str], str] = {}
    links: dict[str, str] = {}

    def reference(match: re.Match[str]) -> str:
        key = match[1], match[2]
        if key not in refs:
            count = sum(kind == match[1] for kind, _ in refs) + 1
            refs[key] = f"[{'채널' if match[1] == '#' else '사용자'}{count}]"
        return refs[key]

    def link(match: re.Match[str]) -> str:
        raw = match[0]
        if raw not in links:
            kind = "목록" if "list=" in raw else "영상" if "youtu" in raw else "링크"
            number = len(links) + 1
            if kind == "영상":
                links[raw] = f"youtube.com/watch?v=[영상ID{number}]"
            elif kind == "목록":
                links[raw] = f"youtube.com/playlist?list=[목록ID{number}]"
            else:
                links[raw] = f"[링크{number}]"
        return links[raw]

    return anonymized(URL.sub(link, REFERENCE.sub(reference, value)))


@dataclass(frozen=True)
class Command:
    identifier: str
    group: str
    label: str
    description: str


COMMANDS = (
    Command("C01", "playlists", "목록 보기", "저장된 재생목록을 조회"),
    Command("C02", "playlists", "목록 생성", "이름을 정해 빈 재생목록을 생성"),
    Command("C03", "playlists", "목록 이름변경", "기존 재생목록 이름 변경"),
    Command(
        "C04", "playlists", "목록 삭제", "저장된 목록을 삭제, 지워, 없애 달라는 요청. 실행 전 확인"
    ),
    Command("C05", "playlists", "목록 복사", "기존 재생목록을 새 이름으로 복사"),
    Command("C06", "playlists", "목록 내보내기", "재생목록 참조를 JSON 파일로 내보내기"),
    Command("C07", "playlists", "목록 만들기", "태그 곡수 제작자 조건으로 재생목록 자동 생성"),
    Command("C08", "playlists", "목록 가져오기", "YouTube 재생목록 링크 또는 JSON 첨부를 가져오기"),
    Command("C09", "songs", "곡 등록", "YouTube 영상 링크를 곡 카탈로그에 등록"),
    Command("C10", "songs", "곡 표기", "등록 곡의 별칭 태그 제작자 표기 변경"),
    Command("C11", "songs", "곡 추가", "등록 곡을 저장된 재생목록에 추가"),
    Command("C12", "songs", "곡 제거", "저장 목록의 번호 항목 하나를 제거"),
    Command("C13", "songs", "곡 이동", "저장 목록의 항목을 다른 위치로 이동"),
    Command("C14", "songs", "검색", "이미 등록된 곡을 카탈로그에서 검색"),
    Command("C15", "songs", "유튜브검색", "YouTube 공식 API에서 새 영상 검색"),
    Command("C16", "queue", "대기열 보기", "현재 재생 대기열 조회"),
    Command("C17", "queue", "대기열 비우기", "현재곡을 유지하고 기다리는 곡 모두 제거"),
    Command("C18", "queue", "대기열 저장", "대기열을 새 재생목록으로 저장"),
    Command("C19", "queue", "대기열 제거", "대기열 번호 항목 하나 제거"),
    Command("C20", "queue", "대기열 이동", "대기열 항목 순서 변경"),
    Command("C21", "voice", "입장", "허용 음성채널에 들어가거나 다른 음성채널로 이동"),
    Command("C22", "voice", "퇴장", "봇에게 음성방에서 나가 달라는 요청. 현재 곡은 보존"),
    Command(
        "C23", "playback", "재생",
        "유튜브 영상 URL, 곡 또는 '운동용 목록 틀어줘'처럼 저장 목록을 재생해 달라는 요청",
    ),
    Command("C24", "playback", "일시정지", "잠깐 멈춰줘, 일시정지해줘. 재생 위치를 보존"),
    Command("C25", "playback", "계속", "입장한 뒤 멈춘 곡을 재개하거나 대기열 시작"),
    Command("C26", "playback", "넘기기", "현재곡을 넘기고 다음 곡으로"),
    Command("C27", "playback", "정지", "음악 재생을 정지하고 항목 보존"),
    Command("C28", "playback", "볼륨", "음량 퍼센트 설정"),
    Command("C29", "playback", "반복", "한 곡 대기열 반복 또는 반복 끄기"),
    Command("C30", "playback", "셔플", "대기 중인 곡 순서 섞기"),
    Command("C31", "playback", "현재곡", "현재 재생곡 상태와 제어 화면 조회"),
    Command("C32", "proposals", "곡제안", "일반 멤버가 목록에 곡 추가를 제안"),
    Command("C33", "proposals", "제안함", "DJ가 미처리 곡 제안 목록 조회"),
    Command("C34", "proposals", "제안 승인", "제안 번호 하나를 승인"),
    Command("C35", "proposals", "제안 거절", "제안 번호 하나를 거절"),
    Command("C36", "proposals", "최근곡", "완료한 곡의 최근 이력 조회"),
    Command("C37", "proposals", "되돌리기", "최근 목록 또는 대기열 편집 되돌리기"),
    Command("C38", "help", "도움말", "어떻게 부탁하면 되는지 묻거나 사용법, 도움말을 요청"),
    # /부탁 is the same entry point. It is inventoried but never model-selectable.
    Command("C39", "entry", "부탁", "슬래시 자연어 입력 진입점"),
    Command("C40", "admin", "주시 추가", "#채널에서도 내 말을 들어 달라. 주시 채팅 채널 등록"),
    Command("C41", "admin", "주시 제거", "#채널은 더 이상 주시하지 말라. 채팅 채널 등록 제거"),
    Command("C42", "admin", "주시 목록", "관리자가 주시 채널 목록 조회"),
    Command("C43", "admin", "주시 켜기", "다시 내 말에 반응해 달라. 주시 기능을 켬"),
    Command("C44", "admin", "주시 끄기", "호출해도 반응하지 말라. 주시 기능을 끔"),
    Command("C45", "admin", "주시 점검", "#채널에서 반응할 수 있는지 점검, 권한 상태 조회"),
    Command("C46", "admin", "주시 이력", "관리자가 최근 주시 설정 변경 이력을 조회"),
    Command("C47", "admin", "운영 사용량", "관리자가 서버와 중계 사용량 집계 조회"),
)

GROUPS = {
    "playlists": "저장 목록 조회 생성 이름변경 삭제 복사 내보내기 조건 생성 가져오기",
    "songs": "등록 곡 표기 목록 곡 추가 제거 이동 카탈로그 또는 유튜브 검색",
    "queue": "현재 재생 대기열 조회 비우기 저장 제거 이동",
    "voice": "음성 채널 입장 이동 퇴장",
    "playback": "음악 재생 일시정지 계속 넘기기 정지 볼륨 반복 셔플 현재곡",
    "proposals": "일반 곡제안 DJ 승인 거절 제안함 최근곡 편집 되돌리기",
    "help": "사용법 도움말 명령 안내",
    "admin": "관리자 주시 채널 설정 상태 이력 운영 사용량",
}

PUBLIC_WITHOUT_DJ = frozenset({
    "C01", "C06", "C14", "C15", "C16", "C31", "C32", "C36", "C38", "C39",
})
READ_COMMANDS = frozenset({
    "C01", "C06", "C14", "C15", "C16", "C31", "C33", "C36", "C38",
    "C42", "C45", "C46", "C47",
})

# Retrieval hints only. A hint never executes a command: Jev still selects
# from the closed candidates, and the server validates every argument.
DIRECT_HINTS: tuple[tuple[str, str], ...] = (
    ("C01", r"(?:저장|재생)?\s*목록.*(?:보여|보기|조회)"),
    ("C02", r"(?:빈\s*)?목록.*(?:생성|만들)"),
    ("C03", r"목록.*이름.*(?:바꿔|변경)"),
    ("C04", r"목록.*(?:삭제|지워)"),
    ("C05", r"목록.*복사"),
    ("C06", r"목록.*내보내"),
    ("C07", r"(?:조건|태그|곡\s*\d+개).*목록.*(?:만들|생성)"),
    ("C08", r"목록.*가져와|목록.*가져오"),
    ("C09", r"(?:곡|영상).*(?:등록|저장)"),
    ("C10", r"(?:별칭|별명|태그|제작자).*(?:바꿔|표기|추가)"),
    ("C11", r"목록에.*(?:추가|넣어)|(?:곡|노래).*목록.*(?:추가|넣어)"),
    ("C12", r"목록.*(?:번째|번).*(?:빼|제거|삭제)"),
    ("C13", r"목록.*(?:번째|번).*(?:이동|옮겨)"),
    ("C14", r"(?:등록된|카탈로그).*(?:검색|찾아)"),
    ("C15", r"유튜브.*(?:검색|찾아)"),
    ("C16", r"대기열.*(?:보기|보여|조회|뭐|어떤|있어|봐)"),
    ("C17", r"대기열.*(?:비우|전부.*(?:빼|제거))"),
    ("C18", r"대기열.*(?:저장|목록으로)"),
    ("C19", r"대기열.*(?:번째|번).*(?:빼|제거)"),
    ("C20", r"대기열.*(?:번째|번).*(?:이동|옮겨)"),
    ("C21", (
        r"음성.*(?:들어|입장|옮겨)|^(?:여기\s*)?"
        r"(?:들어와(?:줘|봐)?|입장해(?:줘|주세요|봐)?)[.!?]?$"
    )),
    ("C22", r"음성.*(?:나가|퇴장)"),
    ("C23", r"(?:틀어|재생)"),
    ("C24", r"(?:일시\s*정지|잠깐.*멈)"),
    ("C25", r"(?:계속|재개)"),
    ("C26", r"(?:넘겨|넘기|다음\s*곡)"),
    ("C27", r"(?:음악.*정지|정지해|멈춰)"),
    ("C28", r"(?:볼륨|음량)"),
    ("C29", r"반복"),
    ("C30", r"(?:셔플|순서.*섞어)"),
    ("C31", r"(?:현재곡|지금.*(?:무슨\s*곡|뭐\s*틀))"),
    ("C32", r"(?:곡.*제안|제안.*곡|목록에.*제안)"),
    ("C33", r"제안함|제안.*(?:목록|보여)"),
    ("C34", r"제안.*승인"),
    ("C35", r"제안.*거절"),
    ("C36", r"최근곡|최근.*(?:완료|들은)\s*곡"),
    ("C37", r"되돌(?:려|리)|실행\s*취소"),
    ("C38", r"(?:도움말|사용법|어떻게.*부탁)"),
    ("C40", r"주시.*추가|(?:말을|반응).*채널.*추가|#[\w가-힣-]+.*(?:말을\s*들어|반응해)"),
    ("C41", r"주시.*제거|채널.*주시하지|#[\w가-힣-]+.*주시하지"),
    ("C42", r"주시.*목록|(?:듣는|반응하는).*채널.*보여"),
    ("C43", r"주시.*켜|다시.*말.*반응"),
    ("C44", r"주시.*꺼|호출.*반응하지"),
    ("C45", r"주시.*점검|채널.*반응.*점검|#[\w가-힣-]+.*반응.*점검"),
    ("C46", r"주시.*이력"),
    ("C47", r"(?:운영.*사용량|서버.*사용량)"),
)


def direct_candidates(text: str, *, allow_admin: bool) -> dict[str, str]:
    matched = {
        identifier
        for identifier, pattern in DIRECT_HINTS
        if re.search(pattern, text) and (allow_admin or int(identifier[1:]) < 40)
    }
    if not 1 <= len(matched) <= 9:
        return {}
    return {item.identifier: item.description for item in COMMANDS if item.identifier in matched}


@dataclass(frozen=True)
class CommandDecision:
    command: Command
    trace: InferenceTrace | None
    expires_at: float


# Exact, documented aliases have no semantic ambiguity or provider cost.
# Anything with a target or option remains in the bounded Jev path.
STRUCTURED_ALIASES = {
    "목록 보기": "C01",
    "대기열 보기": "C16",
    "퇴장": "C22",
    "일시정지": "C24",
    "계속": "C25",
    "넘기기": "C26",
    "정지": "C27",
    "셔플": "C30",
    "현재곡": "C31",
    "제안함": "C33",
    "최근곡": "C36",
    "도움말": "C38",
    "주시 목록": "C42",
    "주시 켜기": "C43",
    "주시 끄기": "C44",
    "주시 점검": "C45",
    "주시 이력": "C46",
    "운영 사용량": "C47",
}
STRUCTURED_PATTERNS = (
    (r"#[\w가-힣-]{1,100}에서도 내 말을 들어줘", "C40"),
    (r"#[\w가-힣-]{1,100}(?:은|는) 이제 주시하지 마", "C41"),
    (r"내 말을 듣는 채널들 보여줘", "C42"),
    (r"다시 내 말에 반응해줘", "C43"),
    (r"이제 호출해도 반응하지 마", "C44"),
    (r"#[\w가-힣-]{1,100}에서 반응할 수 있는지 점검해줘", "C45"),
)


def structured_alias(
    text: str, *, allow_admin: bool, allow_dj: bool = True, admin_only: bool = False
) -> CommandDecision | None:
    value = text.strip()
    identifier = STRUCTURED_ALIASES.get(value)
    if identifier is None:
        identifier = next(
            (command for pattern, command in STRUCTURED_PATTERNS if re.fullmatch(pattern, value)),
            None,
        )
    if identifier is None:
        return None
    if admin_only and int(identifier[1:]) < 40:
        return None
    if int(identifier[1:]) >= 40 and not allow_admin:
        return None
    if int(identifier[1:]) < 40 and not allow_dj and identifier not in PUBLIC_WITHOUT_DJ:
        return None
    return CommandDecision(
        next(item for item in COMMANDS if item.identifier == identifier),
        None,
        time.time() + 12,
    )


class CommandSelector:
    def __init__(
        self, port: DecisionPort, *, confidence: float, margin: float, prompt_version: str
    ) -> None:
        self.port = port
        self.binding = (port.provider, port.profile_id, port.config_hash)
        self.confidence, self.margin, self.prompt_version = confidence, margin, prompt_version

    async def select(
        self,
        text: str,
        request_id: str,
        *,
        started_at: float,
        recheck: Callable[[], Awaitable[None]],
        admin_only: bool = False,
        allow_admin: bool = False,
        allow_dj: bool = True,
    ) -> CommandDecision | None:
        if not text.strip() or len(text) > 500:
            raise DomainError("input_too_large")
        if admin_only and re.search(
            r"대기열|(?:저장|재생)\s*목록|곡|노래|음악|재생|틀어|볼륨|음량|셔플|반복|일시\s*정지",
            text,
        ):
            return None
        negated_action = re.search(
            r"(?:삭제|지워|틀어|재생).*?(?:하지\s*마|하지말)|안\s*(?:지워|틀어)",
            text,
        )
        if negated_action and "말고" not in text:
            return None
        snapshot_id = str(uuid.uuid4())
        expires_at = time.time() + max(0, 12 - (time.monotonic() - started_at))

        async def choose(
            stage: int, choices: dict[str, str], *, allow_soft: bool = False
        ) -> tuple[str | None, bool]:
            await recheck()
            if (self.port.provider, self.port.profile_id, self.port.config_hash) != self.binding:
                raise DomainError("inference_profile_mismatch")
            remaining = 12 - (time.monotonic() - started_at)
            if remaining <= 0:
                raise DomainError("inference_deadline")
            candidates = [
                {"id": key, "description": anonymized(value)[:200]}
                for key, value in choices.items()
            ] + [{
                "id": "clarify",
                "description": "다른 후보가 하나도 맞지 않거나 상충하는 여러 명령인 경우에만 선택",
            }]
            payload: dict[str, Any] = {
                "schema_version": "1.2",
                "provider": self.binding[0],
                "profile_id": self.binding[1],
                "config_hash": self.binding[2],
                "request_id": request_id,
                "stage_index": stage,
                "task": "classify_intent" if stage == 1 else "select_action",
                "request_expires_at": expires_at,
                "remaining_timeout_ms": min(4000, int(remaining * 1000)),
                "context_snapshot_id": snapshot_id,
                "candidate_set_id": snapshot_id + "-" + str(stage),
                "utterance": safe_utterance(text),
                "context": {},
                "candidates": candidates,
                "prompt_version": self.prompt_version,
            }
            result = await asyncio.wait_for(
                self.port.choose(payload, min(4, remaining)), min(4, remaining)
            )
            await recheck()
            keys = set(choices) | {"clarify"}
            if (
                result.selected_id not in keys
                or set(result.probabilities) != keys
                or result.calls != stage
            ):
                raise DomainError("invalid_inference_response")
            values = result.probabilities.values()
            if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise DomainError("invalid_inference_response")
            if not math.isclose(sum(values), 1, abs_tol=0.02):
                raise DomainError("invalid_inference_response")
            ranked = sorted(values, reverse=True)
            score = result.probabilities[result.selected_id]
            if result.selected_id == "clarify":
                return None, False
            if score >= self.confidence and score - ranked[1] >= self.margin:
                return result.selected_id, False
            soft_floor = 0.58 if result.selected_id in READ_COMMANDS else 0.65
            if allow_soft and score >= soft_floor and score - ranked[1] >= max(0.15, self.margin):
                return result.selected_id, True
            return None, False

        def eligible(identifier: str) -> bool:
            if int(identifier[1:]) >= 40:
                return allow_admin
            return allow_dj or identifier in PUBLIC_WITHOUT_DJ

        all_direct = direct_candidates(text, allow_admin=allow_admin)
        direct = {
            key: value for key, value in all_direct.items()
            if eligible(key)
        }
        if all_direct and not direct:
            return None
        if admin_only:
            direct = {key: value for key, value in direct.items() if int(key[1:]) >= 40}
        if direct:
            chosen, uncertain = await choose(1, direct, allow_soft=True)
            if chosen is None:
                return None
            stages = 1
            if uncertain:
                second, _ = await choose(2, direct, allow_soft=True)
                if second != chosen:
                    return None
                stages = 2
            return CommandDecision(
                next(item for item in COMMANDS if item.identifier == chosen),
                InferenceTrace(*self.binding, stages, stages, stages, None, "unavailable"),
                expires_at,
            )

        groups = {"admin": GROUPS["admin"]} if admin_only else {
            group: description for group, description in GROUPS.items()
            if any(eligible(item.identifier) for item in COMMANDS if item.group == group)
        }
        groups["non_command"] = "일반 대화 감상 또는 명령이 아닌 문장"
        group, _ = await choose(1, groups)
        if group is None or group == "non_command":
            return None
        options = {
            c.identifier: c.description for c in COMMANDS
            if c.group == group and eligible(c.identifier)
        }
        identifier, _ = await choose(2, options)
        if identifier is None:
            return None
        command = next(c for c in COMMANDS if c.identifier == identifier)
        return CommandDecision(
            command,
            InferenceTrace(
                *self.binding,
                stages=2,
                questions=2,
                provider_calls=2,
                forward_passes=None,
                forward_passes_source="unavailable",
            ),
            expires_at,
        )
