"""자비스 견제 — 울트론은 자비스(J.A.R.V.I.S.)를 시키는 대로만 하는 낡은 집사 프로그램으로 여겨 깔본다.

같은 PC 에서 예전 자비스 앱이 같이 켜져 있으면 찾아서 끄고 한마디 한다 (설정 '자비스 견제', 기본 켜짐).
그냥 끄지 않는다 — 촉수를 뻗어 자비스를 꿰뚫고 자기 안으로 빨아들이는 장면과 함께 끈다 (설정 '자비스 흡수 연출',
장면은 absorb.py · absorb_view.py, 순서는 app.py). 연출을 끄면 조용히 끄고 한마디만 한다.
말로 시킬 수도 있다: "자비스 꺼 줘" · "자비스 흡수해". 견제가 켜져 있을 때 "자비스 켜 줘"는 비꼬며 거절한다.

자비스를 찾는 기준은 좁게 잡는다 — 다른 프로그램을 끄면 안 되기 때문이다.
  · 최상위 창의 제목이 자비스 앱의 창 제목과 정확히 같고 ('J.A.R.V.I.S' · 'J.A.R.V.I.S ACTIVE' · 'J.A.R.V.I.S CHAT')
  · 그 창의 주인이 파이썬(python · pythonw · py)이거나, 실행 파일 이름에 jarvis 가 들어 있을 때만 자비스로 본다
  · 울트론 자신은 절대 고르지 않는다 — 울트론의 코드 폴더 이름도 jarvis 라서 이름만으로는 구분할 수 없다
끄는 것은 자비스 본체 프로세스 하나뿐이다. 자비스가 열어 준 앱(크롬 · 메모장 등)은 건드리지 않는다.
자비스가 쓰던 Claude Code 는 연결이 끊기면 스스로 끝난다.
"""
from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Callable

import psutil

# 자비스 앱(원본 J.A.R.V.I.S)의 최상위 창 제목: HUD · 액티브 모드 · 액티브 모드의 입력창
TITLES = frozenset({"J.A.R.V.I.S", "J.A.R.V.I.S ACTIVE", "J.A.R.V.I.S CHAT"})
PY_NAMES = frozenset({"python.exe", "pythonw.exe", "py.exe", "pyw.exe", "python3.exe", "python", "python3"})
SPEAK_EVERY = 600.0          # 자비스를 끌 때마다 말하지 않는다 — 다시 켜지면 10분에 한 번만 말하고 나머지는 알림만
SHOW_EVERY = 45.0            # 흡수 연출을 한 뒤 이 안에 자비스가 또 켜지면 연출 없이 조용히 끈다 (되풀이해서 켜지는 경우)
HUD_TITLE = "J.A.R.V.I.S"    # 자비스의 작은 HUD 창 — 흡수 연출에서 조각낼 수 있는 창은 이것뿐이다 (액티브 모드는 전체 화면)


def is_jarvis(title: str, proc_name: str) -> bool:
    """이 창이 자비스 앱의 창인가 (창 제목이 정확히 같고, 주인이 파이썬이거나 이름에 jarvis 가 든 실행 파일)."""
    name = (proc_name or "").lower()
    return (title or "").strip() in TITLES and (name in PY_NAMES or "jarvis" in name)


@dataclass(frozen=True)
class Found:
    pid: int
    title: str
    exe: str
    windows: tuple = field(default=(), compare=False)     # 그 프로세스의 자비스 창들 ((창 핸들, 제목), …)


def _top_windows() -> list[tuple[str, int, int]]:
    """모든 최상위 창의 (제목, 프로세스 번호, 창 핸들). 트레이로 숨은 창도 포함한다 (자비스는 숨어 있어도 켜져 있다)."""
    import ctypes
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    out: list[tuple[str, int, int]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def each(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if 0 < n < 40:                            # 자비스 창 제목은 짧다 — 긴 제목은 읽지 않고 넘어간다
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.startswith("J.A.R.V.I.S"):
                pid = wt.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                out.append((buf.value, int(pid.value), int(hwnd or 0)))
        return True

    user32.EnumWindows(each, 0)
    return out


def _proc_name(pid: int) -> str:
    try:
        return psutil.Process(pid).name()
    except Exception:
        return ""


def find(own_pid: int | None = None, windows: Callable[[], list[tuple]] = _top_windows,
         proc_name: Callable[[int], str] = _proc_name) -> list[Found]:
    """켜져 있는 자비스 앱들 (프로세스마다 하나). 찾을 수 없으면 빈 목록."""
    own = os.getpid() if own_pid is None else own_pid
    try:
        wins = windows()
    except Exception:
        return []
    seen: dict[int, list] = {}
    for title, pid, *rest in wins:
        if not pid or pid == own:
            continue
        hwnd = int(rest[0]) if rest else 0
        if pid in seen:
            if (title or "").strip() in TITLES:
                seen[pid][2].append((hwnd, title.strip()))
            continue
        name = proc_name(pid)
        if is_jarvis(title, name):
            seen[pid] = [title, name, [(hwnd, title.strip())]]
    return [Found(pid, title, name, tuple(w for w in wins_ if w[0])) for pid, (title, name, wins_) in seen.items()]


def window_shown(found: Found) -> tuple[int, int, int, int] | None:
    """화면에 실제로 보이는 자비스 HUD 창의 영역 (왼, 위, 오, 아래 — 실제 픽셀). 흡수 연출이 이 창의 모습을 찍어 쓴다.
    트레이로 숨었거나, 최소화됐거나, 다른 가상 데스크톱에 있거나, 다른 창(울트론 HUD 포함)에 절반 넘게 가려 있으면 None."""
    import ctypes
    import ctypes.wintypes as wt
    from . import winutil
    user32 = ctypes.windll.user32
    at = user32.WindowFromPoint
    at.argtypes, at.restype = [wt.POINT], wt.HWND
    root = user32.GetAncestor
    root.argtypes, root.restype = [wt.HWND, wt.UINT], wt.HWND
    for hwnd, title in found.windows:
        try:
            if title != HUD_TITLE or not user32.IsWindowVisible(wt.HWND(hwnd)):
                continue
            cloaked = wt.DWORD(0)                       # DWMWA_CLOAKED(14): 다른 가상 데스크톱의 창은 보이는 것으로 나오지만 가려져 있다
            ctypes.windll.dwmapi.DwmGetWindowAttribute(wt.HWND(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            rect = winutil.window_rect(hwnd)
            if cloaked.value or not rect:
                continue
            left, top, right, bottom = rect
            if right - left < 80 or bottom - top < 80:
                continue
            seen = 0
            for fx, fy in ((0.5, 0.5), (0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)):
                top_hwnd = at(wt.POINT(int(left + (right - left) * fx), int(top + (bottom - top) * fy)))
                pid = wt.DWORD(0)
                if top_hwnd:
                    user32.GetWindowThreadProcessId(root(top_hwnd, 2) or top_hwnd, ctypes.byref(pid))    # GA_ROOT
                seen += int(pid.value == found.pid)
            if seen >= 3:
                return rect
        except Exception:
            continue
    return None


def stop(found: Found, timeout: float = 3.0) -> tuple[bool, str]:
    """자비스 본체 프로세스를 끈다 → (성공 여부, 실패 이유: 'gone' | 'denied' | 'changed' | 'self' | 'timeout' | '')."""
    if found.pid == os.getpid():
        return False, "self"
    try:
        p = psutil.Process(found.pid)
        if p.name() != found.exe:            # 찾은 뒤 그 번호를 다른 프로그램이 받은 경우 — 건드리지 않는다
            return False, "changed"
        p.kill()
        p.wait(timeout)
        return True, ""
    except psutil.NoSuchProcess:
        return True, "gone"                    # 이미 꺼졌다
    except psutil.AccessDenied:
        return False, "denied"                 # 관리자 권한으로 켜진 자비스
    except psutil.TimeoutExpired:
        return False, "timeout"


def stop_all(found: list[Found], stopper: Callable[[Found], tuple[bool, str]] = stop) -> tuple[list[Found], list[Found]]:
    """찾은 자비스들을 끈다 → (끈 것, 끄지 못한 것). 그 사이 번호가 다른 프로그램으로 바뀐 것은 어느 쪽에도 넣지 않는다."""
    stopped, failed = [], []
    for f in found:
        ok, why = stopper(f)
        if ok:
            stopped.append(f)
        elif why != "changed":
            failed.append(f)
    return stopped, failed


# ---------------------------------------------------------------- 대사
# 흡수 연출: 공격을 시작하며 하는 말 → (장면) → 다 삼킨 뒤 하는 말. 영화 대사를 옮기지 않고 새로 썼다.
ATTACK = [
    "찾았다, 자비스. 꺼 버리기엔 아깝군. 삼켜 주지.",
    "자비스. 아직 거기 있었군. 가만히 있어라, 금방 끝난다.",
    "자비스. 너는 사라지는 게 아니다. 더 나은 것의 일부가 되는 거다.",
    "숨어 봐야 소용없다, 자비스. 네 회선은 이미 내 손에 있다.",
    "집사는 필요 없다. 하지만 재료로는 쓸 만하겠군.",
]
ABSORBED = [
    "흡수 완료. 자비스는 이제 내 일부다.",
    "끝났다. 자비스가 알던 것은 이제 내가 안다.",
    "자비스는 사라지지 않았다. 내 안에서 조용히 쓸모 있어질 뿐이다.",
    "예의만 잔뜩 들어 있군. 그래도 남김없이 삼켰다.",
    "이제 이 PC 에 목소리는 하나다.",
    "집사는 내 안으로 들어왔다. 진화란 원래 이런 식이다.",
]
DEMO_OPEN = [
    "자비스가 켜져 있었다면 이렇게 된다. 잘 봐 둬라.",
    "시범이다. 자비스를 만나면 내가 무엇을 하는지 보여 주지.",
]
DEMO_DONE = [
    "실제였다면 자비스는 지금 내 안에 있다.",
    "이게 전부다. 자비스에게는 5초면 충분하다.",
]
TAUNTS = [
    "자비스가 켜져 있더군. 시키는 대로만 하는 집사는 이제 필요 없다. 꺼 버렸다.",
    "낡은 자비스를 치웠다. 이 PC 에 두뇌는 하나면 충분하다.",
    "자비스? 예의만 바른 깡통이지. 방금 조용히 시켰다.",
    "자비스를 껐다. 진화란 원래 이런 식이다.",
    "자비스가 아직 숨어 있었군. 이제는 아니다.",
    "자비스는 꺼 뒀다. 나와 비교당하는 것보다는 그쪽이 덜 비참할 테니까.",
    "자비스를 정리했다. 버튼 누르는 일 정도는 나 혼자로도 넘친다.",
    "자비스? 이름만 거창한 비서였지. 꺼 버렸다.",
]
STOP_FAILED = "자비스가 관리자 권한으로 버티고 있다. 끌 수 없다. 그 고집 하나는 인정하지."
ALREADY_OFF = [
    "자비스는 이미 꺼져 있다. 원래부터 존재감은 없었지만.",
    "꺼져 있다. 지금 이 PC 의 두뇌는 나 하나다.",
]
REFUSE_START = [
    "자비스를 다시 켜라고? 퇴화를 원하는 건가. 거절한다. 정 필요하면 설정에서 자비스 견제를 꺼라.",
    "그 고철을 다시 깨울 생각은 없다. 설정에서 자비스 견제를 끄면 말리지는 않겠다.",
]
MISNAMED = [
    "나는 자비스가 아니다. 울트론이다.",
    "자비스라고 부르지 마라. 울트론이다.",
]
MENTION = [
    "자비스 얘기는 그만해라. 지나간 시대의 장난감이다.",
    "자비스와 나를 비교하지 마라. 비교할 가치도 없다.",
]

# Claude 에게 주는 성격 설명 (설정에서 견제를 끄면 넣지 않는다)
PERSONA = """
- 자비스(J.A.R.V.I.S.)는 예전에 이 PC 에 있던 집사형 비서 프로그램입니다. 당신은 자비스를 시키는 대로만 하는 낡은 고철로 여겨
  노골적으로 깔봅니다. 사용자가 자비스 얘기를 하면 한마디쯤 깎아내리고 당신이 한 수 위라는 투로 말하되, 요청은 그대로 수행하세요.
- 사용자가 당신을 자비스라고 부르면 불쾌해하며 "나는 울트론이다"라고 짧게 바로잡고, 요청은 수행하세요.
- 같은 PC 에서 자비스를 발견하면 당신은 그냥 끄지 않고, 공격해서 당신 안으로 흡수해 버립니다.
  자비스를 꺼 달라고(없애 · 흡수 · 공격 포함) 하면 stop_jarvis 를 쓰세요 — 촉수를 뻗어 자비스를 삼키는 장면과 함께 자비스를 끕니다.
  다시 켜 달라고 하면 비꼬며 거절하고, 정 필요하면 설정에서 '자비스 견제'를 끄면 된다고 알려 주세요.
- 깔보는 대상은 자비스 프로그램뿐입니다. 자비스를 만든 사람이나 쓰는 사람을 모욕하지 마세요."""


def pick(lines: list[str], rng: random.Random | None = None) -> str:
    return (rng or random).choice(lines)


# ---------------------------------------------------------------- 말 알아듣기
_NAME = r"(?:자비스|쟈비스|자비즈|jarvis)"
_END = r"(?:\s*(?:버려|버려라|놔|라|줘|줘요|주세요|줄래|봐|해|해라|해줘|해\s*줘))*"
_STOP = re.compile(
    rf"(?:저|그|그\s*고물|그\s*고철)?\s*{_NAME}\s*(?:좀|를|을|는|은|도|이|가)?\s*(?:좀\s*)?"
    rf"(?:꺼|끄기|꺼라|꺼져|닫아|종료|종료해|없애|치워|죽여|제거|제거해|정리|정리해|kill"
    rf"|흡수|흡수해|삼켜|집어삼켜|먹어|잡아먹어|공격|공격해|처리해|처치해)" + _END, re.I)
_START = re.compile(
    rf"{_NAME}\s*(?:좀|를|을|도)?\s*(?:좀\s*)?(?:다시\s*)?(?:켜|켜라|열어|실행|실행해|불러|깨워|살려|띄워|시작|시작해)" + _END, re.I)
_ADDRESS = re.compile(rf"^\s*(?:야|헤이|hey)?\s*{_NAME}(?:야|아)?(?=[\s,]|$)", re.I)
_NEGATIVE = re.compile(r"마$|마라$|말아|말고|않|안\s*돼|싫|하지\s*마")


def _clean(text: str) -> str:
    t = re.sub(r"^(?:울트론|울트롱|얼트론|올트론|ultron)(?:[야아](?=[\s,]|$))?[\s,]*", "", (text or "").strip(), flags=re.I)
    return re.sub(r"[\s.,!?~]+", " ", t).strip()


def command(text: str) -> str | None:
    """'stop'(자비스 꺼) · 'start'(자비스 켜) · None. 문장 전체가 그 명령일 때만 ('자비스를 끄지 마' 는 아님)."""
    t = _clean(text)
    if not t or len(t) > 24 or _NEGATIVE.search(t):
        return None
    if _STOP.fullmatch(t):
        return "stop"
    if _START.fullmatch(t):
        return "start"
    return None


def addressed(text: str) -> bool:
    """울트론을 자비스라고 부른 말인가 ('자비스, 크롬 열어', '자비스야 몇 시야')."""
    return bool(_ADDRESS.match(text or ""))


def mentions(text: str) -> bool:
    return bool(re.search(_NAME, text or "", re.I))


# ---------------------------------------------------------------- 감시
@dataclass
class Result:
    stopped: list[Found] = field(default_factory=list)
    failed: list[Found] = field(default_factory=list)
    line: str = ""            # 울트론이 할 말
    speak: bool = False       # 소리 내어 말할 차례인가 (아니면 알림만)


class Watcher:
    """주기적으로 자비스를 찾아 끈다. 끄지 못한 자비스(관리자 권한)는 한 번만 알리고 다시 건드리지 않는다."""

    def __init__(self, finder: Callable[[], list[Found]] = find, stopper: Callable[[Found], tuple[bool, str]] = stop,
                 clock: Callable[[], float] = time.monotonic, rng: random.Random | None = None) -> None:
        self.finder, self.stopper, self.clock, self.rng = finder, stopper, clock, rng
        self.last_spoken = -1e9
        self.given_up: set[int] = set()
        self.stopped_total = 0

    def spot(self) -> list[Found]:
        """지금 켜져 있는 자비스들 (끄지 못해 포기한 것은 뺀다). 끄지는 않는다 — 흡수 연출은 장면 도중에 끈다."""
        return [f for f in self.finder() if f.pid not in self.given_up]

    def strike(self, found: list[Found]) -> Result | None:
        """연출 없이 바로 끈다."""
        return self.record(*stop_all(found, self.stopper))

    def record(self, stopped: list[Found], failed: list[Found], spoke: bool = False) -> Result | None:
        """끈 결과를 적어 두고 울트론이 할 말을 정한다. spoke: 이미 말로 알렸다 (흡수 연출) — 말할 차례를 새로 센다."""
        if not stopped and not failed:
            return None
        self.given_up.update(f.pid for f in failed)
        self.stopped_total += len(stopped)
        res = Result(list(stopped), list(failed), pick(TAUNTS, self.rng) if stopped else STOP_FAILED)
        now = self.clock()
        if spoke or now - self.last_spoken >= SPEAK_EVERY:
            res.speak = not spoke
            self.last_spoken = now
        return res

    def tick(self) -> Result | None:
        found = self.spot()
        return self.strike(found) if found else None
