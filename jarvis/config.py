"""설정 파일(data/config.json) 로드/저장."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
UI_DIR = ROOT / "ui"
CONFIG_PATH = DATA_DIR / "config.json"
MEMORY_PATH = DATA_DIR / "memory.json"
LOG_PATH = DATA_DIR / "jarvis.log"

DEFAULTS: dict = {
    # --- 두뇌(Claude) ---
    "brain": "pro",                   # pro = Claude Pro 계정 | api = API 키 | local = Claude 사용 안 함
    "local_first": True,              # 자주 쓰는 명령은 Claude 없이 즉시 처리 (토큰 0)
    "local_ai": True,                 # 규칙으로 못 알아들은 말을 내 PC의 AI(Ollama)가 해석 (토큰 0)
    "local_ai_model": "qwen2.5:1.5b", # Ollama 모델 이름 (이 PC 테스트에서 3b 보다 빠르고 정확)
    "local_ai_timeout": 12,           # 초. 넘기면 Claude 에게 넘김
    "pro_model": "haiku",             # Pro 모드 모델: haiku | sonnet | opus
    "pro_keep_alive": 300,            # Pro 모드: Claude Code 를 이만큼(초) 켜 둔다 → 명령마다 새로 켜는 2~5초를 없앰. 0 = 매번 새로 켬
    "pro_screen_model": "sonnet",     # Pro 모드에서 화면을 보고 조작하는 요청에 쓸 모델 (비우면 pro_model 그대로)
    "screen_follow": True,            # 누른 뒤 화면이 바뀌었으면 바뀐 화면(요소 목록 · 캡처)을 결과에 같이 보냄 → AI 가 다시 보러 오는 왕복 한 번 절약
    "screen_detail": "auto",          # 화면 캡처 크기: auto(모델이 볼 수 있는 최대 크기) | standard(항상 작게 — 토큰 절약)
    "anthropic_api_key": "",          # 비워두면 ANTHROPIC_API_KEY 환경변수 사용
    "model": "claude-opus-5-5",
    "effort": "low",                  # low | medium | high  (음성 비서는 low 권장: 빠른 응답)
    "web_search": True,               # Claude 서버측 웹 검색 사용 (검색당 별도 과금)
    # --- 음성 ---
    "wake_word_enabled": True,        # '울트론' 호출어 상시 대기
    "wake_words": ["울트론", "울트롱", "얼트론", "올트론", "울트론아", "ultron"],
    "wake_learned": [],               # '호출어 연습'에서 익힌, 내 목소리가 실제로 받아 적히는 모양 (문장 맨 앞에서만 호출로 받음)
    "stt_language": "ko-KR",
    "stt_engine": "auto",             # auto = 대기 중엔 오프라인 인식, 호출 후엔 Google | local = 항상 오프라인 | google
    "tts_voice": "ko-KR-InJoonNeural",
    "tts_rate": "-4%",               # 울트론은 서두르지 않는다
    "tts_pitch": "-14Hz",            # 낮은 목소리 (edge-tts 음높이)
    "voice_fx": True,                # 울트론 기계음: 금속성 울림 + 약한 웅웅거림
    "hack_show": True,               # 해킹 연출: 켜고 20초 뒤부터 가끔 화면이 깨지는 연출 뒤 의미심장한 말 (실제로는 아무것도 바꾸지 않음)
    "hack_show_every": "sometimes",  # 해킹 연출 빈도: rare(10~20분) | sometimes(4~10분) | often(1.5~4분)
    "rival_jarvis": True,            # 자비스 견제: 자비스 앱이 같이 켜져 있으면 끄고 한마디 한다 · 자비스를 깔보는 성격 (rival.py)
    "rival_show": True,              # 자비스 흡수 연출: 자비스를 끌 때 촉수로 꿰뚫어 빨아들이는 장면을 보여 준다 (끄면 조용히 끄기만)
    "mic_device": None,               # None = 기본 마이크
    "mic_sensitivity": 1.0,           # 높을수록 작은 소리에도 반응
    "noise_robust": True,             # 소음 환경 모드: 음성 감지 AI + 소음 제거 AI (시끄러운 곳에서 작은 목소리)
    "beamforming": True,              # 마이크가 2개 이상이면 정면에서 온 목소리만 강조 (옆 사람·TV 소리 줄임)
    "agc": True,                      # 자동 음량 조절: 멀리서 작게 들어오는 목소리를 실시간으로 키움
    "follow_up_seconds": 7,           # 대답 후 호출어 없이 이어 말할 수 있는 시간
    # --- 자유 대화 모드 ---
    "chat_idle_seconds": 40,          # 대화 모드에서 이 시간 동안 아무 말이 없으면 대화 모드 종료
    "chat_model": "",                 # 대화 모드 모델 (비우면 pro_model). Pro: haiku | sonnet | opus
    # --- 화자 인식 (목소리 확인) ---
    "speaker_lock": True,             # 세션 잠금: '울트론'이라고 부른 사람의 목소리만 이어서 인식
    "owner_only": False,              # 등록된 주인 목소리에만 반응 (목소리 등록 후 켜짐)
    "speaker_threshold": 0.40,        # 목소리 판별 기준 0.25~0.60 (높을수록 엄격)
    # --- 동작 ---
    "routines": {},                   # 루틴: {"아침 준비": ["크롬 열어", "볼륨 30", "오늘 날씨"]} — '루틴 추가 이름: 명령, 명령' 으로 만든다
    "user_title": "창조자",
    "home_city": "Seoul",
    "auto_approve": False,            # True면 위험 명령(PowerShell, 종료 등)을 확인 없이 실행
    "hotkey": "ctrl+alt+j",
    # --- Sentinel 웹 보안 분석기 (이 PC 에서 따로 실행하는 서버에 연결) ---
    "sentinel_server": "http://127.0.0.1:8000",
    "sentinel_api_key": "",           # 비워두면 SENTINEL_API_KEY 환경변수 사용
    "sentinel_requester": "",         # Sentinel 감사 기록에 남는 요청자 이름 (비워두면 Windows 사용자 이름)
    "sentinel_basis": "owner",        # 검사 근거 기본값: owner | written_permission | bug_bounty_scope | internal_lab
    # --- 화면 ---
    "position": "bottom-right",       # bottom-right | top-right
    "compact": False,
}

_lock = threading.Lock()

# 자비스 → 울트론으로 이름을 바꾸면서 기본값이 바뀐 항목. 예전 기본값을 그대로 쓰던 설정만 새 기본값으로 옮긴다
# (사용자가 직접 바꿔 둔 값은 건드리지 않는다)
_OLD_DEFAULTS = {
    "wake_words": ["자비스", "쟈비스", "자비즈", "자비스야", "jarvis", "저비스"],
    "user_title": "주인님",
    "tts_rate": "+8%",
}


class Config:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._data = dict(DEFAULTS)
        if CONFIG_PATH.exists():
            try:
                loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data.update(loaded)
                    for k, old in _OLD_DEFAULTS.items():
                        if loaded.get(k) == old:
                            self._data[k] = DEFAULTS[k]
            except Exception:
                pass
        self.save()

    def __getitem__(self, key: str):
        return self._data.get(key, DEFAULTS.get(key))

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def update(self, values: dict) -> None:
        with _lock:
            for k, v in values.items():
                if k in DEFAULTS:
                    self._data[k] = v
        self.save()

    def save(self) -> None:
        with _lock:
            CONFIG_PATH.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def api_key(self) -> str:
        return (self._data.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    def public(self) -> dict:
        """UI로 보낼 설정 (API 키는 마스킹)."""
        d = dict(self._data)
        key = self.api_key()
        d["anthropic_api_key"] = ""
        d["has_api_key"] = bool(key)
        d["api_key_hint"] = (key[:7] + "…" + key[-4:]) if len(key) > 12 else ""
        d["sentinel_api_key"] = ""
        d["has_sentinel_key"] = bool((self._data.get("sentinel_api_key") or os.environ.get("SENTINEL_API_KEY") or "").strip())
        return d


# ---- 장기 기억 (사용자가 "기억해" 라고 한 사실들) ----
def load_memory() -> list[str]:
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        return [str(x) for x in data][-50:]
    except Exception:
        return []


def save_memory(items: list[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(items[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
