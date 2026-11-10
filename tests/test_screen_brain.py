"""화면 작업용 모델 고르기 (brain.py) — Pro 모드에서 화면을 보고 조작하는 요청에만 더 정확한 모델을 쓴다."""
import threading

import pytest

import jarvis.brain as bm
from jarvis.config import DEFAULTS


class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k, DEFAULTS.get(k))

    def api_key(self):
        return ""


class Tools:
    def __init__(self):
        self.models = []

    def set_vision_model(self, model):
        self.models.append(model)

    def schemas(self):
        return []


def brain(**cfg):
    return bm.Brain(Cfg(cfg), Tools(), on_action=lambda *a: None, context_fn=lambda: "")


@pytest.mark.parametrize("text", [
    "이 페이지에서 로그인 버튼 눌러 줘", "화면에 뭐가 보여?", "여기 검색창에 고양이라고 입력해 줘", "이 글 요약해 줘",
    "설정 메뉴 어디 있어?", "아래로 스크롤해서 댓글 읽어 줘", "저거 클릭해", "이 사이트에서 장바구니 들어가 줘",
])
def test_screen_requests_use_the_screen_model(text):
    assert brain()._pro_model(text) == "sonnet"


@pytest.mark.parametrize("text", ["오늘 일정 정리해 줘", "피보나치 수열 설명해 줘", "내일 날씨 어때", "농담 하나 해 줘", ""])
def test_other_requests_keep_the_everyday_model(text):
    assert brain()._pro_model(text) == "haiku"


def test_screen_model_never_downgrades_and_can_be_turned_off():
    assert brain(pro_model="opus")._pro_model("이 버튼 눌러 줘") == "opus"                    # 평소 모델이 더 높으면 그대로
    assert brain(pro_model="sonnet")._pro_model("이 버튼 눌러 줘") == "sonnet"
    assert brain(pro_screen_model="")._pro_model("이 버튼 눌러 줘") == "haiku"                # 끈 경우
    assert brain(pro_screen_model="opus")._pro_model("이 버튼 눌러 줘") == "opus"
    assert brain(pro_screen_model="이상한값")._pro_model("이 버튼 눌러 줘") == "haiku"


def test_only_real_model_ids_reach_the_screen_tools():
    b = brain()
    for m in ("claude-sonnet-5-5", None, "", "haiku", "<synthetic>", 42, "claude-haiku-4-5-20251001"):
        b._vision_model(m)
    assert b.tools.models == ["claude-sonnet-5-5", "claude-haiku-4-5-20251001"]


class Runner:
    """Claude Code 실행을 흉내 낸다: (모델, 이어 갈 대화 번호) 를 기록하고 정해 둔 결과를 차례로 돌려준다."""

    def __init__(self, b, results):
        self.b, self.results, self.calls = b, list(results), []

    def __call__(self, exe, text, cancel, model):
        self.calls.append((model, self.b.session_id))
        ok, sid = self.results.pop(0)
        if sid:
            self.b.session_id = sid
        return ("답" if ok else None, "", not ok, 0 if ok else 1, "" if ok else "resume failed")


def wired(results):
    b = brain(pro_keep_alive=0)                     # 명령마다 Claude Code 를 새로 켜는 예전 방식
    b.claude_exe = lambda: "claude"
    b._build_system = lambda: "system"
    run = Runner(b, results)
    b._run_claude_code = run
    return b, run


def test_switching_models_retries_in_a_fresh_conversation_when_resume_fails():
    b, run = wired([(True, "s1"), (False, None), (True, "s2")])
    assert b._claude_code("오늘 일정 정리해 줘", threading.Event()) == "답"
    assert b._claude_code("이 화면에서 확인 버튼 눌러 줘", threading.Event()) == "답"
    # 평소 모델로 시작한 대화를 화면용 모델로 이어 가다 실패 → 새 대화로 한 번 더
    assert run.calls == [("haiku", None), ("sonnet", "s1"), ("sonnet", None)]
    assert b.session_id == "s2" and b._session_model == "sonnet"


def test_no_retry_when_the_model_did_not_change():
    b, run = wired([(True, "s1"), (False, None)])
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    reply = b._claude_code("그럼 내일은?", threading.Event())
    assert run.calls == [("haiku", None), ("haiku", "s1")]
    assert reply != "답" and b.session_id is None


def test_same_conversation_continues_when_switching_works():
    b, run = wired([(True, "s1"), (True, None), (True, None)])
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    b._claude_code("이 화면에서 확인 버튼 눌러 줘", threading.Event())
    b._claude_code("고마워 이제 됐어", threading.Event())
    assert run.calls == [("haiku", None), ("sonnet", "s1"), ("haiku", "s1")]


# ---------------------------------------------------------------- 켜 둔 Claude Code 로 명령 처리 (pro_keep_alive)
class FakeSession:
    """ClaudeSession 흉내: 질문 · 모델 전환 · 종료를 기록하고 정해 둔 답을 차례로 돌려준다."""
    made: list = []

    def __init__(self, args_fn, env_fn, cwd):
        self.args_fn, self.alive, self.session_id = args_fn, False, None
        self.asked, self.models, self.closed, self.warmed = [], [], [], 0
        self.answers = list(FakeSession.script)
        self.can_switch = True
        FakeSession.made.append(self)

    def warm(self):
        self.alive, self.warmed = True, self.warmed + 1

    def set_model(self, model):
        self.models.append(model)
        if not self.can_switch:
            self.alive = False
        return self.can_switch

    def ask(self, prompt, cancel, on_text=None, on_event=None, timeout=240):
        self.alive = True
        self.asked.append((prompt.splitlines()[-1], self.args_fn(self.session_id)))
        text, err = self.answers.pop(0) if self.answers else ("답", False)
        self.session_id = self.session_id or f"s{len(FakeSession.made)}"
        if on_event:
            on_event({"type": "system", "model": "claude-sonnet-5-5"})
        if on_text and not err:
            on_text(text)
        return (None if err else text), err, ("resume failed" if err else "")

    def close(self, forget=False):
        self.alive = False
        self.closed.append(forget)
        if forget:
            self.session_id = None

    def close_if_idle(self, seconds):
        return False


def live(monkeypatch, script=(), **cfg):
    FakeSession.made, FakeSession.script = [], list(script)
    monkeypatch.setattr(bm, "ClaudeSession", FakeSession)
    monkeypatch.setattr(bm.Brain, "_mcp_config", lambda self: "mcp.json")
    monkeypatch.setattr(bm.Brain, "_reap", lambda self: None)

    def drop(self):                              # 실제로는 다른 스레드에서 끈다 — 테스트에서는 바로
        sess, self.cmd_session = self.cmd_session, None
        if sess:
            sess.close(forget=True)

    monkeypatch.setattr(bm.Brain, "_drop_cmd_session", drop)
    b = brain(**cfg)
    b.claude_exe = lambda: "claude"
    b._build_system = lambda chat=False: "system"
    b.tool_server = object()
    return b


def model_of(args):
    return args[args.index("--model") + 1]


def test_commands_reuse_one_running_claude_code_and_stream_the_answer(monkeypatch):
    b = live(monkeypatch)
    heard = []
    assert b._claude_code("오늘 일정 정리해 줘", threading.Event(), heard.append) == "답"
    assert b._claude_code("그럼 내일은?", threading.Event(), heard.append) == "답"
    assert len(FakeSession.made) == 1                                   # 프로세스를 새로 켜지 않았다
    s = FakeSession.made[0]
    assert [q for q, _ in s.asked] == ["오늘 일정 정리해 줘", "그럼 내일은?"]
    assert heard == ["답", "답"]                                         # 답이 만들어지는 대로 넘어온다
    assert model_of(s.asked[0][1]) == "haiku" and "--resume" not in s.asked[0][1] and "stream-json" in s.asked[0][1]
    assert b.tools.models == ["claude-sonnet-5-5", "claude-sonnet-5-5"]   # 실제 모델 이름을 화면 도구에 알려 준다
    assert b.session_id == "s1" and b.turns == 2


def test_screen_request_switches_the_model_without_restarting(monkeypatch):
    b = live(monkeypatch)
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    b._claude_code("이 화면에서 확인 버튼 눌러 줘", threading.Event())
    b._claude_code("고마워 이제 됐어", threading.Event())
    s = FakeSession.made[0]
    assert len(FakeSession.made) == 1 and s.models == ["sonnet", "haiku"] and s.closed == []


def test_model_switch_falls_back_to_restart_and_then_to_a_fresh_conversation(monkeypatch):
    b = live(monkeypatch, script=[("답", False), ("", True)])
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    s = FakeSession.made[0]
    s.can_switch = False                         # 예전 Claude Code: 켜 둔 채로는 모델을 못 바꾼다 → 꺼졌다가 새 모델로 다시 켜진다
    assert b._claude_code("이 화면에서 확인 버튼 눌러 줘", threading.Event()) == "답"
    assert model_of(s.asked[1][1]) == "sonnet" and s.asked[1][1][-2:] == ["--resume", "s1"]
    assert len(FakeSession.made) == 2 and s.closed == [True]            # 이어 가기가 실패해 새 대화로 한 번 더
    assert "--resume" not in FakeSession.made[1].asked[0][1]


def test_old_conversation_starts_fresh_and_errors_drop_the_session(monkeypatch):
    b = live(monkeypatch, script=[("답", False), ("", True)])
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    b.last_turn = b._cmd_born = 0                # 10분 넘게 조용했다
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    assert len(FakeSession.made) == 2 and FakeSession.made[0].closed == [True]
    FakeSession.made[1].answers = [("", True)]
    reply = b._claude_code("그럼 내일은?", threading.Event())
    assert reply and reply != "답" and b.cmd_session is None and b.session_id is None


def test_cancel_forgets_the_conversation(monkeypatch):
    b = live(monkeypatch)
    cancel = threading.Event()
    cancel.set()
    assert b._claude_code("오늘 일정 정리해 줘", cancel) is None
    assert b.cmd_session is None and b.session_id is None


def test_prewarm_only_when_claude_was_used_recently(monkeypatch):
    import time as _t
    b = live(monkeypatch)
    assert not b.wants_prewarm()                 # 오늘 Claude 를 쓴 적이 없다 → 로컬 명령만 쓰는 사람에게는 켜지 않는다
    b.prewarm()
    assert FakeSession.made == []
    b._ai_used = _t.time()
    assert b.wants_prewarm()
    b.prewarm()
    assert len(FakeSession.made) == 1 and FakeSession.made[0].warmed == 1
    assert not b.wants_prewarm()                 # 이미 켜져 있다
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    assert len(FakeSession.made) == 1            # 미리 켜 둔 것을 그대로 쓴다
    b.chat_mode = True
    FakeSession.made[0].alive = False
    assert not b.wants_prewarm()                 # 대화 모드는 따로 켜 둔 세션을 쓴다


def test_keep_alive_zero_uses_a_new_process_per_command(monkeypatch):
    b = live(monkeypatch, pro_keep_alive=0)
    b._run_claude_code = lambda exe, text, cancel, model: ("예전 방식", "", False, 0, "")
    assert b._claude_code("오늘 일정 정리해 줘", threading.Event()) == "예전 방식"
    assert FakeSession.made == [] and not b.wants_prewarm()


def test_reset_and_shutdown_close_the_running_process(monkeypatch):
    b = live(monkeypatch)
    b._claude_code("오늘 일정 정리해 줘", threading.Event())
    s = FakeSession.made[0]
    b.shutdown()
    assert s.closed == [True] and b.cmd_session is None
