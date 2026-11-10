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
    b = brain()
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
