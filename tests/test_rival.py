"""자비스 견제 (rival.py) — 자비스 앱만 정확히 찾아 끄고, 울트론 자신이나 다른 프로그램은 건드리지 않는다."""
import os
import random
import threading

import psutil
import pytest

import jarvis.brain as bm
from jarvis import rival
from jarvis.config import DEFAULTS


# ---------------------------------------------------------------- 찾기
@pytest.mark.parametrize("title, proc, yes", [
    ("J.A.R.V.I.S", "pythonw.exe", True),
    ("J.A.R.V.I.S ACTIVE", "python.exe", True),
    ("J.A.R.V.I.S CHAT", "pythonw.exe", True),
    ("J.A.R.V.I.S", "jarvis.exe", True),                  # 실행 파일로 묶어 둔 자비스
    ("J.A.R.V.I.S", "Python.EXE", True),
    ("J.A.R.V.I.S", "chrome.exe", False),                 # 같은 제목의 웹 페이지 · 문서
    ("J.A.R.V.I.S - Chrome", "chrome.exe", False),
    ("J.A.R.V.I.S.txt - 메모장", "notepad.exe", False),
    ("U.L.T.R.O.N", "pythonw.exe", False),                # 울트론 자신
    ("jarvis", "python.exe", False),
    ("J.A.R.V.I.S 소개 영상", "python.exe", False),
    ("", "pythonw.exe", False),
])
def test_is_jarvis_needs_the_exact_window_title_and_a_python_owner(title, proc, yes):
    assert rival.is_jarvis(title, proc) is yes


def test_find_skips_ultron_itself_and_lists_each_process_once():
    wins = [("J.A.R.V.I.S", 100), ("J.A.R.V.I.S ACTIVE", 100), ("J.A.R.V.I.S CHAT", 100),
            ("J.A.R.V.I.S", 200),                     # 울트론 자신의 번호 (울트론 코드 폴더 이름도 jarvis)
            ("J.A.R.V.I.S", 300),                     # 크롬 탭
            ("U.L.T.R.O.N", 400), ("J.A.R.V.I.S", 0)]
    names = {100: "pythonw.exe", 200: "pythonw.exe", 300: "chrome.exe", 400: "pythonw.exe"}
    found = rival.find(own_pid=200, windows=lambda: wins, proc_name=names.get)
    assert found == [rival.Found(100, "J.A.R.V.I.S", "pythonw.exe")]
    assert rival.find(own_pid=1, windows=lambda: [], proc_name=names.get) == []

    def broken():
        raise OSError("창 목록을 읽을 수 없음")

    assert rival.find(own_pid=1, windows=broken, proc_name=names.get) == []


# ---------------------------------------------------------------- 끄기
class FakeProc:
    procs: dict = {}

    def __init__(self, pid):
        if pid not in FakeProc.procs:
            raise psutil.NoSuchProcess(pid)
        self.pid, self.info = pid, FakeProc.procs[pid]

    def name(self):
        return self.info["name"]

    def kill(self):
        if self.info.get("denied"):
            raise psutil.AccessDenied(self.pid)
        self.info["killed"] = True

    def wait(self, timeout=None):
        return 0


@pytest.fixture
def procs(monkeypatch):
    FakeProc.procs = {}
    monkeypatch.setattr(rival.psutil, "Process", FakeProc)
    return FakeProc.procs


def test_stop_kills_only_the_found_process(procs):
    procs[100] = {"name": "pythonw.exe"}
    assert rival.stop(rival.Found(100, "J.A.R.V.I.S", "pythonw.exe")) == (True, "")
    assert procs[100]["killed"]


def test_stop_refuses_itself_a_reused_number_and_reports_denied(procs):
    procs[os.getpid()] = {"name": "pythonw.exe"}
    assert rival.stop(rival.Found(os.getpid(), "J.A.R.V.I.S", "pythonw.exe")) == (False, "self")
    assert "killed" not in procs[os.getpid()]
    procs[100] = {"name": "chrome.exe"}                       # 찾은 뒤 그 번호를 다른 프로그램이 받았다
    assert rival.stop(rival.Found(100, "J.A.R.V.I.S", "pythonw.exe")) == (False, "changed")
    assert "killed" not in procs[100]
    procs[200] = {"name": "pythonw.exe", "denied": True}      # 관리자 권한으로 켜진 자비스
    assert rival.stop(rival.Found(200, "J.A.R.V.I.S", "pythonw.exe")) == (False, "denied")
    assert rival.stop(rival.Found(300, "J.A.R.V.I.S", "pythonw.exe")) == (True, "gone")   # 이미 꺼짐


# ---------------------------------------------------------------- 감시 (5초마다)
class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_watcher_stops_jarvis_speaks_rarely_and_gives_up_on_denied():
    alive = {100: True}
    clock = Clock()
    stops = []

    def finder():
        return [rival.Found(pid, "J.A.R.V.I.S", "pythonw.exe") for pid, on in alive.items() if on]

    def stopper(f):
        stops.append(f.pid)
        if f.pid == 300:
            return False, "denied"
        alive[f.pid] = False
        return True, ""

    w = rival.Watcher(finder, stopper, clock, random.Random(1))
    first = w.tick()
    assert [f.pid for f in first.stopped] == [100] and first.speak and first.line in rival.TAUNTS
    alive[200] = True                                        # 자비스가 바로 다시 켜졌다
    clock.t += 60
    again = w.tick()
    assert again.stopped and not again.speak                 # 끄기는 하지만 말은 10분에 한 번만
    assert w.tick() is None                                  # 이제 켜져 있는 자비스가 없다
    alive[300] = True
    clock.t += rival.SPEAK_EVERY
    denied = w.tick()
    assert denied.failed and not denied.stopped and denied.line == rival.STOP_FAILED and denied.speak
    n = len(stops)
    assert w.tick() is None and len(stops) == n              # 못 끈 자비스는 다시 건드리지 않는다
    assert w.stopped_total == 2


# ---------------------------------------------------------------- 말 알아듣기
@pytest.mark.parametrize("text, cmd", [
    ("자비스 꺼", "stop"), ("자비스 꺼 줘", "stop"), ("울트론, 자비스 좀 꺼 줘.", "stop"), ("자비스 종료해", "stop"),
    ("자비스를 없애 줘", "stop"), ("그 고물 자비스 꺼 버려", "stop"), ("jarvis 꺼", "stop"),
    ("자비스 켜 줘", "start"), ("자비스 다시 켜 줘", "start"), ("자비스 실행해", "start"), ("자비스 불러 줘", "start"),
    ("자비스를 끄지 마", None), ("자비스 끄지 말고 둬", None), ("자비스 켜지 마", None),
    ("자비스 어때", None), ("자비스가 더 낫지 않아?", None), ("자비스 끄는 법 알려 줘", None),
    ("크롬 꺼", None), ("울트론 꺼", None), ("", None),
])
def test_command(text, cmd):
    assert rival.command(text) == cmd


def test_addressed_and_mentions():
    assert rival.addressed("자비스, 크롬 열어") and rival.addressed("자비스야 몇 시야") and rival.addressed("야 자비스 볼륨 올려")
    assert not rival.addressed("자비스가 뭐야") and not rival.addressed("크롬 열어") and not rival.addressed("자비스트 검색")
    assert rival.mentions("요즘 자비스는 어때") and not rival.mentions("크롬 열어")


# ---------------------------------------------------------------- 두뇌에 연결
class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k, DEFAULTS.get(k))

    def api_key(self):
        return ""

    def update(self, values):
        dict.update(self, values)


class Tools:
    def __init__(self, jarvis_running=True):
        self.ran = []
        self.jarvis_running = jarvis_running

    def schemas(self):
        return []

    def label(self, name, args):
        return name

    def run(self, name, args):
        self.ran.append(name)
        if name == "stop_jarvis":
            return rival.TAUNTS[0] if self.jarvis_running else rival.ALREADY_OFF[0]
        return "ok"

    def _find_app(self, name, min_score=38):
        return ("Chrome", "id") if name == "크롬" else None

    def _match_windows(self, name):
        return []


def brain(**cfg):
    cfg.setdefault("brain", "local")
    cfg.setdefault("local_ai", False)
    return bm.Brain(Cfg(cfg), Tools(), on_action=lambda *a: None, context_fn=lambda: "")


def test_stop_command_runs_the_tool_and_answers_with_a_taunt():
    b = brain()
    assert b.handle("자비스 꺼 줘", threading.Event()) == rival.TAUNTS[0]
    assert b.tools.ran == ["stop_jarvis"]
    b.tools.jarvis_running = False
    assert b.handle("자비스 꺼", threading.Event()) == rival.ALREADY_OFF[0]
    b = brain(rival_jarvis=False)                            # 견제를 꺼도 직접 시키면 끈다
    b.handle("자비스 꺼 줘", threading.Event())
    assert b.tools.ran == ["stop_jarvis"]


def test_start_command_is_refused_only_while_rivalry_is_on():
    b = brain()
    assert b.handle("자비스 켜 줘", threading.Event()) in rival.REFUSE_START and b.tools.ran == []
    b = brain(rival_jarvis=False)
    assert b.handle("자비스 켜 줘", threading.Event()) not in rival.REFUSE_START


def test_being_called_jarvis_gets_corrected_but_the_command_still_runs():
    b = brain()
    reply = b.handle("자비스, 크롬 열어", threading.Event())
    assert any(reply.startswith(m) for m in rival.MISNAMED) and "크롬" in reply and b.tools.ran == ["open_app"]
    b = brain(rival_jarvis=False)
    reply = b.handle("자비스, 크롬 열어", threading.Event())
    assert not any(reply.startswith(m) for m in rival.MISNAMED) and b.tools.ran == ["open_app"]
    assert not any(brain().handle("크롬 열어", threading.Event()).startswith(m) for m in rival.MISNAMED)


def test_local_only_mode_mocks_jarvis_talk():
    assert brain().handle("자비스는 요즘 뭐 해", threading.Event()) in rival.MENTION
    assert brain(rival_jarvis=False).handle("자비스는 요즘 뭐 해", threading.Event()) not in rival.MENTION


def test_persona_goes_into_the_prompts_only_when_enabled():
    on, off = brain(), brain(rival_jarvis=False)
    for chat in (False, True):
        assert "자비스를 시키는 대로만 하는 낡은 고철" in on._build_system(chat=chat)
        assert "stop_jarvis" not in off._build_system(chat=chat) and "고철" not in off._build_system(chat=chat)
    assert "자비스를 만든 사람이나 쓰는 사람을 모욕하지 마세요" in on._build_system()
    assert on.recognizes("자비스 꺼 줘")


def test_stop_really_ends_a_running_process():
    """실제 프로세스를 하나 띄워서 끈다 (psutil 이 실제로 동작하는지)."""
    import subprocess
    import sys
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        name = psutil.Process(child.pid).name()
        assert rival.stop(rival.Found(child.pid, "J.A.R.V.I.S", name), timeout=5) == (True, "")
        assert child.wait(timeout=5) is not None
    finally:
        if child.poll() is None:
            child.kill()
