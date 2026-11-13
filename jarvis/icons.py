"""아이콘 — 카드뉴스 · 포스터에 넣는 그림 기호 (구글 Material Icons Round, Apache 2.0 — assets/icons).

글자만 있는 카드는 밋밋하다. 카드마다 내용에 맞는 아이콘을 하나씩 넣는다:
  · Claude 가 이름을 고르면 그것을 쓴다 (예: 'bedtime', 'smartphone', 'school' — Material Icons 의 이름 2,200개).
  · 이름이 없거나 모르는 이름이면 카드의 글(한국어)에서 낱말로 고른다 (예: '수면' → bedtime, '스마트폰' → smartphone).
  · 그래도 없으면 카드 종류에 맞는 기본 아이콘.
아이콘 글꼴은 글자처럼 그린다 (색 · 크기를 자유롭게, 가장자리가 매끄럽다). 이 파일은 고르기 · 그리기만 한다.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "assets" / "icons" / "MaterialIconsRound-Regular.ttf"
CODES = ROOT / "assets" / "icons" / "codepoints.json"

# 한국어 낱말 → 아이콘. 위에서부터 먼저 맞는 것을 쓴다 (구체적인 것을 위에).
# 한 글자 낱말은 앞에 다른 한글이 붙지 않을 때만 — '집중력'의 '집', '방법'의 '법', '검색'의 '색'을 잘못 잡지 않게.
_W = r"(?<![가-힣])"
KEYWORDS: list[tuple[str, str]] = [
    (r"수면|" + _W + r"잠(?![깐시])|잠자|숙면|불면|졸음|밤샘|취침", "bedtime"),
    (r"스마트폰|휴대폰|핸드폰|" + _W + r"폰(?!트)|모바일|" + _W + r"앱(?![가-힣])|sns|인스타|유튜브|틱톡", "smartphone"),
    (r"블루\s*라이트|화면|모니터|컴퓨터|노트북|(?<![a-z])pc(?![a-z])", "computer"),
    (r"카페인|커피|에너지\s*음료", "local_cafe"),
    (r"강연|강의|특강|연설|발표회|세미나|토크\s*콘서트", "record_voice_over"),
    (r"신청|참가\s*방법|접수|등록|지원\s*방법|가입", "how_to_reg"),
    (r"공부|학습|성적|" + _W + r"시험|수업|학교|교과|숙제|과제", "school"),
    (_W + r"책(?!임|상)|독서|도서|읽기|교과서", "menu_book"),
    (r"인공\s*지능|(?<![a-z])ai(?![a-z])|로봇|챗봇|자동화", "smart_toy"),
    (r"코딩|프로그래밍|소프트웨어|알고리즘", "code"),
    (r"데이터|통계|그래프|조사\s*결과|비율|퍼센트|%", "insights"),
    (r"\d\s*원|만\s*원|" + _W + r"돈(?![가-힣])|돈을|돈이|비용|가격|요금|용돈|경제|저축|소비|지출|예산|세금", "payments"),
    (r"쇼핑|구매|주문|장바구니|할인", "shopping_cart"),
    (r"건강|질병|면역|감기|병원|의사|치료|진료|약국|복용|처방", "health_and_safety"),
    (r"심장|사랑|마음|감사|응원|좋아요|기부|나눔|봉사", "favorite"),
    (r"우울|스트레스|불안|짜증|화를|걱정|고민|외로", "sentiment_dissatisfied"),
    (r"행복|웃음|기쁨|즐거|만족|힐링", "sentiment_very_satisfied"),
    (r"운동(?!장)|스트레칭|헬스|달리기|걷기|체육(?!관)|근육|요가", "fitness_center"),
    (r"식사|음식|" + _W + r"밥|급식|요리|영양|채소|과일|식단", "restaurant"),
    (r"물\s*마시|수분|" + _W + r"물을|생수|음수", "water_drop"),
    (r"분리\s*배출|재활용|쓰레기|플라스틱|일회용|폐기", "recycling"),
    (r"친환경|에코|생태|지속\s*가능", "eco"),
    (r"환경|지구|기후|탄소|온난화|온실가스", "public"),
    (_W + r"숲|나무|식물|" + _W + r"꽃|정원|녹지|" + _W + r"자연(?!스)", "park"),
    (r"에너지|전기|전력|절전|배터리|충전", "bolt"),
    (r"날씨|햇빛|태양|여름|더위|폭염", "wb_sunny"),
    (_W + r"비가|장마|우산|홍수|폭우|빗물", "umbrella"),
    (r"겨울|추위|한파|폭설|눈사람", "ac_unit"),
    (r"안전|보안|보호|예방|지키", "shield"),
    (r"위험|주의|경고|금지|조심|사고", "warning"),
    (r"화재|소방|산불", "local_fire_department"),
    (r"시간|\d\s*분|일찍|늦게|습관|매일|루틴", "schedule"),
    (r"날짜|일정|기간|마감|월\s*\d|\d+\s*월|요일|캘린더", "event"),
    (r"장소|위치|어디|주소|체육관|강당|운동장|교실|본관", "place"),
    (r"전화|연락|문의|상담", "call"),
    (r"메일|이메일|편지|우편", "mail"),
    (r"친구|사람들|" + _W + r"사람|" + _W + r"팀(?![가-힣])|함께|모두|가족|부모|이웃|공동체|학급", "groups"),
    (_W + r"아이(?!디어|폰|패드|콘|템)|어린이|유아|청소년|10대", "child_care"),
    (r"노인|어르신|고령", "elderly"),
    (r"말하기|대화|소통|토론|의견|질문", "forum"),
    (r"아이디어|생각|창의|발상|해결|방법|는\s*법(?![가-힣])|" + _W + r"팁|꿀팁|비법", "lightbulb"),
    (r"목표|도전|성공|성취|" + _W + r"꿈", "flag"),
    (r"수상|우승|1등|대회|경품|선물|시상|상품|상장", "emoji_events"),
    (r"음악|노래|공연|콘서트|밴드", "music_note"),
    (r"영화|영상|동영상|촬영|사진|카메라", "photo_camera"),
    (r"그림|미술|디자인|" + _W + r"색(?:깔|칠)?(?![가-힣])|색깔|색칠|그리기", "palette"),
    (r"과학|실험|연구|화학|물리|생물", "science"),
    (r"우주|행성|로켓|천문|별자리", "rocket_launch"),
    (r"여행|비행기|해외|관광|휴가", "flight"),
    (r"교통|버스|지하철|자동차|운전|도로", "directions_bus"),
    (r"자전거", "directions_bike"),
    (r"동물|반려|강아지|고양이|애완", "pets"),
    (r"뉴스|소식|공지|안내", "campaign"),
    ("(?<!는\\s)" + _W + r"법(?!칙)|법률|법원|헌법|규칙|제도|정책|권리|투표|선거", "gavel"),
    (r"세계|국제|글로벌|외국|나라", "language"),
    (r"우리\s*집|" + _W + r"집(?:에|이|은|을|안|밖)|주거|가정|침실", "home"),
    (r"직업|취업|회사|업무|직장|진로|일자리|출근", "work"),
    (r"개선|증가|성장|늘어|상승", "trending_up"),
    (r"감소|줄어|하락|떨어", "trending_down"),
    (r"확인|체크|완료|해야\s*할|실천|점검", "task_alt"),
    (r"효과\s*없|오해|거짓|가짜|잘못", "cancel"),
]

# 카드 종류별 기본 아이콘 (글에서 고르지 못했을 때)
DEFAULTS = {"cover": "auto_awesome", "point": "tips_and_updates", "list": "checklist", "stat": "insights",
            "steps": "route", "compare": "compare_arrows", "quote": "format_quote", "closing": "favorite",
            "poster": "campaign", "section": "label_important"}


@lru_cache(maxsize=1)
def codes() -> dict[str, int]:
    """아이콘 이름 → 글자 번호 (없으면 빈 사전 — 아이콘 없이 그린다)."""
    try:
        return json.loads(CODES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def available() -> bool:
    return FONT.exists() and bool(codes())


def normalize(name: str | None) -> str:
    """'Bed Time', 'bed-time' 같은 표기도 받아 준다."""
    return re.sub(r"[\s\-]+", "_", str(name or "").strip().lower())


def resolve(name: str | None) -> str | None:
    """아는 아이콘 이름이면 그 이름 ('Bed Time' → 'bedtime', 'Local Cafe' → 'local_cafe'), 모르면 None."""
    n = normalize(name)
    if not n:
        return None
    for cand in (n, n.replace("_", "")):
        if cand in codes():
            return cand
    return None


def known(name: str | None) -> bool:
    return resolve(name) is not None


def candidates(*texts: str) -> list[str]:
    """글에 맞는 아이콘들 — 앞의 글(제목)을 먼저, 같은 글 안에서는 먼저 나온 낱말부터."""
    out: list[str] = []
    for t in texts:
        blob = str(t or "").lower()
        if not blob.strip():
            continue
        hits = []
        for pattern, name in KEYWORDS:
            m = re.search(pattern, blob)
            if m and name in codes():
                hits.append((m.start(), name))
        for _, name in sorted(hits, key=lambda h: h[0]):
            if name not in out:
                out.append(name)
    return out


def from_text(*texts: str) -> str | None:
    """글에서 아이콘을 고른다 (맞는 낱말이 없으면 None)."""
    found = candidates(*texts)
    return found[0] if found else None


def pick(name: str | None, *texts: str, kind: str = "point", avoid=()) -> str | None:
    """쓸 아이콘 이름: 준 이름(알면) → 글에서 고른 것(avoid — 이미 쓴 것 — 은 되도록 피한다) → 카드 종류의 기본.
    아이콘 글꼴이 없으면 None."""
    if not available():
        return None
    if known(name):
        return resolve(name)
    found = candidates(*texts)
    fresh = [n for n in found if n not in avoid]
    if fresh:
        return fresh[0]
    default = DEFAULTS.get(kind, "auto_awesome")
    if default not in avoid or not found:
        return default
    return found[0]


@lru_cache(maxsize=64)
def font(size: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONT), int(size))


def draw(d, name: str | None, center: tuple[float, float], size: float, fill) -> bool:
    """아이콘 하나를 가운데 맞춰 그린다 (size = 아이콘 한 변의 픽셀). 그렸으면 True."""
    cp = codes().get(resolve(name) or "") if name else None
    if cp is None or not FONT.exists():
        return False
    d.text(center, chr(cp), font=font(round(size)), fill=fill, anchor="mm")
    return True
