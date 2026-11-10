"""받아쓴 글자 다듬기 (hearing.py) — 호출어 찾기 · 인식기가 틀리게 적은 명령 바로잡기 · 한글 수.

여기 적힌 '뭉개진 받아쓰기'는 합성 목소리를 소음 · 주변 대화 · 먼 거리 조건으로 앱의 인식 과정에 넣어 실제로 나온 것들이다.
"""
import pytest

from jarvis import approval, hearing
from jarvis.config import DEFAULTS
from jarvis.local_router import LocalRouter, normalize

W = DEFAULTS["wake_words"]


# ---------------------------------------------------------------- 호출어
@pytest.mark.parametrize("text, rest", [
    ("울트론, 크롬 열어 줘.", "크롬 열어 줘"),
    ("울트론", ""),
    ("울트론아", ""),
    ("울트론아 몇 시야", "몇 시야"),
    ("울 트 론 크롬 열어", "크롬 열어"),
    ("크롬 열어 줘 울트론", "크롬 열어 줘"),
    ("야 울트론", ""),
    ("헤이 울트론, 크롬 닫아", "크롬 닫아"),
    # 예전에는 호출어를 뗀 뒤 양 끝의 '야 · 아' 글자까지 지웠다 → 아래 명령들이 망가졌다
    ("울트론, 아이유 노래 틀어 줘", "아이유 노래 틀어 줘"),
    ("울트론 야놀자 열어 줘", "야놀자 열어 줘"),
    ("울트론 볼륨 몇이야?", "볼륨 몇이야"),
    ("울트론 크롬 닫아", "크롬 닫아"),
    ("울트론 지금 몇 시야", "지금 몇 시야"),
])
def test_strip_wake_leaves_the_command_intact(text, rest):
    assert hearing.strip_wake(text, W) == rest


@pytest.mark.parametrize("text, rest", [
    # 첫 글자만 다르게 적힘 (소음 · 주변 대화 · 먼 거리에서 가장 흔한 모양)
    ("물트론 화면 좀 어둡게 해줘", "화면 좀 어둡게 해줘"),
    ("볼트론 크롬 열어줘", "크롬 열어줘"),
    ("골트론 메모장 열어", "메모장 열어"),
    ("꿀트론 소리 키워줘", "소리 키워줘"),
    ("놀트론 계산기 켜줘", "계산기 켜줘"),
    ("일트론 오늘 날씨 어때", "오늘 날씨 어때"),
    ("골트런을 크롬 열어", "크롬 열어"),
    ("물틀론 크롬 열어", "크롬 열어"),
    ("돌트론화면 밝기 올려", "화면 밝기 올려"),
    ("물트론5분 알려줘", "5분 알려줘"),
    ("물트론는 소리 키워", "소리 키워"),
    # 가운데 · 끝이 뭉개짐
    ("울트롱 크롬 열어줘", "크롬 열어줘"),
    ("울뜨론 크롬 열어 줘", "크롬 열어 줘"),
    ("울터론 메모장 열어", "메모장 열어"),
    ("울틀론 메모장 열어", "메모장 열어"),
    ("울투론 메모장 열어", "메모장 열어"),
    ("울트룸 계산기 켜", "계산기 켜"),
    ("울트롯 소리 키워", "소리 키워"),
    ("울트르론 컴퓨터 상태 어때", "컴퓨터 상태 어때"),
    ("울트러 크롬 열어줘", "크롬 열어줘"),
    ("울트로 크롬 열어줘", "크롬 열어줘"),
    ("울트로은 화면 밝기 올려", "화면 밝기 올려"),
    ("울트는 크롬 열어", "크롬 열어"),
    ("울트 크롬 열어", "크롬 열어"),
    ("울툰 다음 곡 틀어 줘", "다음 곡 틀어 줘"),
    ("울 트론 크롬 열어", "크롬 열어"),
    ("트론 크롬 열어 줘", "크롬 열어 줘"),
    ("ultron open chrome", "open chrome"),
    ("꿀트러", None),                      # 끝소리까지 빠진 것은 받지 않는다 (첫 글자가 '울' 일 때만)
])
def test_garbled_wake_word_is_still_a_call(text, rest):
    assert hearing.strip_wake(text, W) == rest
    if rest is not None:
        assert hearing.wake_at_start(text, W)


@pytest.mark.parametrize("text", [
    "크롬 열어 줘", "오늘 날씨 어때", "자비스 크롬 열어 줘", "버스 시간 알려 줘",
    # '울트라' 로 시작하는 말
    "울트라 마라톤 검색해 줘", "울트라북 추천해 줘", "울트로맨 틀어 줘", "울트라맨 틀어 줘",
    # 끝이 비슷한 다른 낱말
    "트로피 사진 보여 줘", "상을 트로피로 받았어", "트럭 사진 찾아 줘", "트롯 틀어 줘", "미스트롯 틀어 줘", "이 트롯 누구 노래야",
    "컨트롤 에이 눌러 줘", "레트로 게임 추천해 줘", "메트로 신문 열어 줘", "스트롱 제로 검색", "드론 영상 보여 줘", "일렉트론 설치해 줘",
    "오트밀 주문해 줘", "올트먼이 누구야",
    # 느슨한 모양은 문장 맨 앞에서만 받는다 — 띄어 적히거나 문장 가운데 있으면 호출이 아니다
    "서울 토론회 언제야", "겨울 트롤 영화 틀어 줘", "올 트로피", "나는 물트론 좋아", "그 볼트론 뭐야",
])
def test_similar_words_are_not_a_call(text):
    assert hearing.find_wake(text, W) is None


def test_wake_in_the_middle_only_counts_when_written_closely():
    assert hearing.strip_wake("아이언맨에 나오는 울트론을 만들 수 있을까", W) is not None     # 글자 그대로면 어디에 있든 찾는다
    assert not hearing.wake_at_start("아이언맨에 나오는 울트론을 만들 수 있을까", W)         # 맨 앞은 아니다 → 대화 중에는 호출로 보지 않음
    assert hearing.wake_at_start("야 울트론 크롬 열어", W)


def test_the_command_is_what_follows_the_wake_word():
    assert hearing.strip_wake("어 울트론 크롬 열어", W) == "크롬 열어"                      # 앞의 군말은 버린다
    assert hearing.strip_wake("대기업 울트론 화면 캡처해 줘", W) == "화면 캡처해 줘"         # 주변 사람 말이 앞에 섞여 적힌 경우
    assert hearing.strip_wake("크롬 열어 줘 울트론", W) == "크롬 열어 줘"                   # 뒤에 말이 없으면 앞의 말이 명령
    assert hearing.strip_wake("크롬 열어 줘 울트론 좀", W) == "크롬 열어 줘 좀"             # 뒤가 한 글자뿐이면 버리지 않는다


@pytest.mark.parametrize("text, rest", [
    ("먼저 고에 물트론 지금 시간 알려줘", "지금 시간 알려줘"),
    ("현대차 볼트론 3분 타이머 맞춰죠", "3분 타이머 맞춰죠"),
    ("오늘 볼트론 음소가 풀어줘", "음소가 풀어줘"),
    ("가지고 넘 물트론 네이버 들어가 줘", "네이버 들어가 줘"),
])
def test_crowded_room_accepts_a_garbled_wake_word_after_other_peoples_words(text, rest):
    # 주변 대화 상태에서는 발화 앞에 남의 말이 2초쯤 같이 잘려 들어와 호출어가 문장 가운데로 밀린다
    assert hearing.strip_wake(text, W, crowded=True) == rest
    assert hearing.strip_wake(text, W) is None                    # 평소에는 문장 맨 앞에서만 받는다


@pytest.mark.parametrize("text", [
    "스펙트럼 분석 결과 보여 줘", "일렉트론 앱 설치해 줘", "그 컨트롤 키 눌러 봐", "서울 토론회 언제야", "나는 레트로 게임이 좋아",
    "미스터트롯 틀어 줘", "오늘 저녁 뭐 먹지", "그거 울트라 와이드 모니터야",
])
def test_crowded_room_still_ignores_similar_words(text):
    assert hearing.find_wake(text, W, crowded=True) is None


def test_garbled_forms_belong_to_the_default_wake_word_only():
    custom = ["프라이데이"]
    assert hearing.strip_wake("프라이데이 크롬 열어", custom) == "크롬 열어"
    assert hearing.find_wake("물트론 크롬 열어", custom) is None
    assert hearing.find_wake("울트롱 크롬 열어", custom) is None
    assert hearing.find_wake("", W) is None and hearing.find_wake("울트론", []) is None


def test_exact_flag_tells_configured_word_from_garbled_form():
    assert hearing.find_wake("울트론 크롬 열어", W).exact
    assert not hearing.find_wake("물트론 크롬 열어", W).exact


# ---------------------------------------------------------------- 명령 문장 바로잡기
@pytest.mark.parametrize("heard, fixed", [
    ("유튜브 들어가죠", "유튜브 들어가 줘"),
    ("화면 잠가죠", "화면 잠가 줘"),
    ("네이버에서 맛집 검색해죠", "네이버에서 맛집 검색해 줘"),
    ("타이머 십분 맞춰죠", "타이머 십분 맞춰 줘"),
    ("크롬 열어져", "크롬 열어 줘"),
    ("다음 꼭 틀줘", "다음 곡 틀어 줘"),
    ("다음 꼭 틀 어 줘", "다음 곡 틀어 줘"),
    ("다음콕 틀어줘", "다음 곡 틀어줘"),
    ("크롬 열 어 줘", "크롬 열어 줘"),
    ("창 닫 아", "창 닫아"),
    ("파일 찾줘", "파일 찾아 줘"),
    ("화면 좀 어둡 게 해줘", "화면 좀 어둡게 해줘"),
    ("하면 밝기 50으로 해줘", "화면 밝기 50으로 해줘"),
    ("바탕화 보여줘", "바탕화면 보여줘"),
    ("바탕 하면 보여줘", "바탕화면 보여줘"),
    ("음소가 해줘", "음소거 해줘"),
    ("음속거 해줘", "음소거 해줘"),
    ("크린샷 찍어줘", "스크린샷 찍어줘"),
    ("다운로드드 폴더 열어줘", "다운로드 폴더 열어줘"),
    ("네이버 열죠", "네이버 열어 줘"),
    ("소리 키워져", "소리 키워 줘"),
    ("음소거 해져", "음소거 해 줘"),
    ("다음 꼭 틀 줘", "다음 곡 틀어 줘"),
    ("밝기묘이야", "밝기 몇이야"),
])
def test_repair_fixes_common_mistranscriptions(heard, fixed):
    assert hearing.repair(heard) == fixed


@pytest.mark.parametrize("text", [
    "오늘 날씨 좋죠", "맞죠", "그렇죠", "가시죠", "한번 보죠",        # 진짜 '-죠' 로 끝나는 말
    "물줘", "물 좀 줘",                                              # '물' 은 동사 줄기가 아니다
    "타이어 검색해 줘", "타이밍 알려 줘",                             # '타이머' 로 바꾸지 않는다
    "스크린샷을 찍어 줘", "다운로드한 파일 열어 줘",                  # 조사 · 어미가 붙은 말은 그대로
    "하면 된다", "다음 폭탄 영상 틀어 줘", "바탕화면으로", "크롬 열어 줘", "볼륨 30으로 해 줘",
    "우산 가져", "국민 체조", "가열죠", "물 줘",
])
def test_repair_leaves_ordinary_sentences_alone(text):
    assert hearing.repair(text) == text


# ---------------------------------------------------------------- 한글 수
@pytest.mark.parametrize("heard, fixed", [
    ("볼륨 삼십으로", "볼륨 30으로"),
    ("볼륨3십으로 해줘", "볼륨30으로 해줘"),
    ("화면 밝기5십으로", "화면 밝기50으로"),
    ("밝기 오십", "밝기 50"),
    ("볼륨 백으로", "볼륨 100으로"),
    ("십분 맞춰", "10분 맞춰"),
    ("오분 알려", "5분 알려"),
    ("타이머 십 분 맞춰", "타이머 10 분 맞춰"),
    ("이십오 분 타이머", "25 분 타이머"),
    ("2십5분", "25분"),
    ("삼 분 삼십 초", "3 분 30 초"),
    ("한 시간 뒤에 알려", "1시간 뒤에 알려"),
    ("두 시간 반 뒤에 알려", "2시간 30분 뒤에 알려"),
    ("볼륨 30으로", "볼륨 30으로"),
    ("5분 뒤에", "5분 뒤에"),
    ("십25분", "십25분"),
    ("크롬 열어", "크롬 열어"),
])
def test_digits(heard, fixed):
    assert hearing.digits(heard) == fixed


# ---------------------------------------------------------------- 명령 처리기까지 이어서
class Exec:
    def __init__(self):
        self.calls = []

    def __call__(self, name, args):
        self.calls.append((name, args))
        if name == "volume":
            return ("현재 볼륨 40%" if args.get("action") == "get" else "볼륨 50% → 40%", False)
        if name == "brightness":
            return ("밝기 50% → 30%", False)
        return ("ok", False)


def run(text):
    ex = Exec()
    reply = LocalRouter(ex, lambda: "창조자").try_handle(text, fallback=True)
    return reply, ex.calls


@pytest.mark.parametrize("heard, call", [
    ("볼륨 삼십으로 해 줘", ("volume", {"action": "set", "level": 30})),
    ("볼륨3십으로 해줘", ("volume", {"action": "set", "level": 30})),
    ("소리 오십 프로로 맞춰 줘", ("volume", {"action": "set", "level": 50})),
    ("화면 밝기5십으로 해줘", ("brightness", {"action": "set", "level": 50})),
    ("볼륨 몇 이야", ("volume", {"action": "get"})),
    ("타이머 십 분 맞춰 줘", ("set_timer", {"seconds": 600, "label": "타이머"})),
    ("오분 알려줘", ("set_timer", {"seconds": 300, "label": "타이머"})),
    ("한 시간 뒤에 알려 줘", ("set_timer", {"seconds": 3600, "label": "타이머"})),
    ("두 시간 반 뒤에 알려 줘", ("set_timer", {"seconds": 9000, "label": "타이머"})),
    ("뽀모도로 이십 분", ("set_timer", {"seconds": 1200, "label": "집중 시간 끝"})),
    ("유튜브 들어가죠", ("open_url", {"url": "https://www.youtube.com"})),
    ("다음 꼭 틀줘", ("media_control", {"action": "next"})),
    ("음소가 해줘", ("volume", {"action": "mute"})),
    ("화면 잠가죠", ("power", {"action": "lock"})),
    ("바탕화 보여줘", ("window_action", {"action": "show_desktop"})),
    ("좀 어둡게 해줘", ("brightness", {"action": "down", "level": 20})),
    ("많이 밝게 해 줘", ("brightness", {"action": "up", "level": 30})),
    ("하면 밝기 50으로 해줘", ("brightness", {"action": "set", "level": 50})),
    ("네이버 열죠", ("open_url", {"url": "https://www.naver.com"})),
    ("소리 키워져", ("volume", {"action": "up", "level": 10})),
    ("다음 꼭 틀 줘", ("media_control", {"action": "next"})),
    ("타이머십 분 맞춰죠", ("set_timer", {"seconds": 600, "label": "타이머"})),
    ("잠가 줘", ("power", {"action": "lock"})),
    ("화면 캡쳐 해줘", ("save_screenshot", {})),
    ("기터브 열어줘", ("open_url", {"url": "https://github.com"})),
    ("밝기묘이야", ("brightness", {"action": "get"})),
    # 같은 글자가 한 번 더 적힌 것 — 못 알아들었을 때만 줄여서 다시 본다
    ("볼륨 올려려줘", ("volume", {"action": "up", "level": 10})),
    ("음악악 멈춰져", ("media_control", {"action": "play_pause"})),
])
def test_misheard_commands_reach_the_right_tool(heard, call):
    reply, calls = run(heard)
    assert reply is not None and calls[0] == call


def test_doubled_syllables_are_only_collapsed_as_a_last_resort():
    _reply, calls = run("유튜브에서 코코 노래 틀어 줘")              # 원래 알아듣는 문장은 건드리지 않는다
    assert calls == [("play_youtube", {"query": "코코 노래"})]
    _reply, calls = run("구글에서 뽀뽀뽀 검색해 줘")
    assert calls == [("browser_search", {"query": "뽀뽀뽀", "site": "google"})]


def test_numbers_are_only_read_inside_level_and_timer_commands():
    _reply, calls = run("구글에서 십분 발휘 검색해 줘")            # 검색어 속의 '십분' 은 그대로
    assert calls == [("browser_search", {"query": "십분 발휘", "site": "google"})]
    _reply, calls = run("유튜브에서 오 분 명상 틀어 줘")
    assert calls == [("play_youtube", {"query": "오 분 명상"})]
    assert run("이 분 누구야") == (None, [])


def test_wake_prefix_in_typed_command_keeps_first_syllable():
    assert normalize("울트론 아이유 노래 틀어 줘") == "아이유 노래 틀어"
    assert normalize("울트론아 크롬 열어 줘") == "크롬 열어"
    assert normalize("울트론, 야놀자 열어") == "야놀자 열어"


def test_repair_does_not_turn_other_words_into_approval():
    assert approval.answer("실행해죠") is True              # '실행해 줘' 를 인식기가 다르게 적은 것
    assert approval.answer("네 해죠") is True
    assert approval.answer("그렇게 하죠") is None            # 승인 표현으로 보지 않는다 — 카드는 그대로
    assert approval.answer("취소해죠") is False
    assert approval.answer("잘 모르겠죠") is None


# ---------------------------------------------------------------- 호출어가 끝나는 시각
def test_wake_end_time_from_token_timestamps():
    tokens = ["울", "트", "론", " 줄", "여", "줘", "."]
    stamps = [0.72, 0.90, 1.08, 1.92, 2.04, 2.22, 2.94]
    assert hearing.wake_end_time(tokens, stamps, W) == pytest.approx(1.30)        # 뒤가 비어 있으면 마지막 글자 + 0.22초
    quick = ["울", "트", "론", " 크", "롬", " 열어", "줘"]
    assert hearing.wake_end_time(quick, [0.5, 0.7, 0.9, 1.05, 1.2, 1.5, 1.8], W) == pytest.approx(0.99)   # 바로 이어 말함
    garbled = ["물", "트", "론", " 크", "롬"]
    assert hearing.wake_end_time(garbled, [0.5, 0.7, 0.9, 1.4, 1.6], W) == pytest.approx(1.12)
    assert hearing.wake_end_time(["크", "롬", " 열어"], [0.5, 0.7, 0.9], W) is None             # 호출어 없음
    assert hearing.wake_end_time([" 크", "롬", " 열어", "줘", " 울", "트", "론"], [0.1, 0.2, 0.4, 0.6, 1.2, 1.4, 1.6], W) is None
    assert hearing.wake_end_time(tokens, stamps[:-1], W) is None                               # 시각 정보가 맞지 않음
    assert hearing.wake_end_time([], [], W) is None
