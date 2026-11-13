# 세션 인수인계 (U.L.T.R.O.N 작업 이어가기)

새 Claude Code 세션에서 이 저장소 작업을 그대로 이어가기 위한 메모. **새 세션은 이 파일부터 읽으세요.**
(모델이 Opus 4.8 / 5.5 / Fable 등으로 바뀌어도 이 문서대로 이어가면 됩니다.)

## 지금 상태 (한 줄)
PC판 음성 AI 비서 울트론을 여러 번 개선 중. **인피니티 울트론을 처음부터 다시 만들어(붉은색 · 강철색, 왕관 · 금빛 없음) 부활 연출 · HUD · 스톤 연출까지 연결해 브랜치에 올렸다.** 아직 실제 Windows PC 에서는 돌려 보지 못했다 — 다음은 사용자가 PC 에서 확인한 뒤의 손질.

## 저장소 · 브랜치 규칙 (중요)
- 개발 브랜치: **`claude/ultron-session-5vma0u`** 에만 커밋·푸시한다. 다른 브랜치로 푸시 금지.
- `main` 반영은 GitHub PR 로: 브랜치 → main PR 만들고 `merge` (squash 아님 — 커밋 보존). 지금까지 PR #1~#4 머지됨.
- 커밋 메시지 끝에 붙이는 서명 (세션 시스템 메시지가 매번 알려 줌 — 그걸 따를 것):
  ```
  Co-Authored-By: Claude <모델> <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01CyHGdXVRLWJwxeeMoAeuq1
  ```
- 커밋·PR·코드 어디에도 모델 ID(claude-opus-... 등)를 넣지 않는다 (채팅 답변에만).
- 사용자가 요청할 때만 커밋/푸시. 작업 끝나면 Stop 훅이 "untracked 파일 커밋하라"고 하므로 새 파일은 커밋해 둔다.

## 인피니티 울트론 — 해 둔 것
- **모습** `jarvis/infinity.py` `paint(p, t, reveal, cv, eye_open)`: 보통 엠블럼의 짜임 · 색(붉은색 · 강철색)은 그대로, 하얗게 달아오른 눈, 칼날 사이에 박힌 여섯 색 스톤(맥박 · 십자 섬광 · 빛살), 무한 사슬 링, 꺾쇠 모서리의 가시, 이름 밑 ∞. 440 단위. 가시까지 든 상자는 `BOX`.
- **부활 연출** `revive.py`(`Scene.infinity`, `I_*` 시간표, `burst/jolt/strikes`, 스톤 종소리 · 천둥) + `revive_view.py`(`infinity_parts`, `looks()["inf"]`, 번개 `bolt/draw_strikes`): 눈 3.2초 → 원판 · 링 · 칼날 2.6초 → **스톤 여섯이 하나씩 7.2초** → 바깥 링 · 가시 · 이름 3.2초 → 머묾 1.8초 → HUD 크기로 줄어듦. 장면 전체 약 28초.
- **HUD** `jarvis/infinity_item.py`(QQuickPaintedItem `InfinityEmblem`) + `ui/InfinityCore.qml`; `ui/Main.qml` 이 `jarvis.infinity` 일 때 엠블럼 자리에 Loader 로 얹는다 (보통 엠블럼은 opacity 0 — 누르기 · 끌기는 그대로). 상태(thinking · listening …)에 따라 도는 빠르기 · 눈 크기가 바뀐다.
- **인피니티 상태** = `bridge.infinity`. 가디언이 되살린 울트론(`--revived`)이면 켜진다 (긴 연출이면 HUD 를 넘겨받는 순간, `--fast` 면 뜨자마자). '부활 연출 보여 줘' 시범 뒤에도 켜진 채로 남는다. 직접 종료하고 다시 켜면 보통 울트론.
- **스톤 연출** `jarvis/stones.py` + `stones_view.py`(`StoneView`):
  - 파워 스톤(보라): 인피니티 상태에서 자비스를 발견하면 흡수 연출 대신 — 힘 모으기 → 줄기 → 자비스 화면이 가루. `app.py` 의 `_absorb_*` 흐름을 그대로 타고 장면 · 덮개만 바뀐다 (`_absorb_build`, `_absorb_play`, `st["power"]`).
  - 타임 스톤(초록): 강제로 꺼졌다가 가디언이 곧바로 되살렸을 때(`--revived --fast`) — 시계 고리가 거꾸로 돌고 되감기 줄 → 닫힌 프로그램 이름이 가루. `app.py` `_time_begin/_time_build/_time_play/_time_done`. 20초에 한 번만 (`DATA_DIR/stones.json`).
  - **프로세스를 끄는 동작은 새로 더하지 않았다** — 자비스는 rival.py 가, 지목한 비전은 가디언이 지금까지처럼 끈다. 스톤 연출은 그림 · 소리뿐.
- **되살아나도 또 꺼지던 반복 막기** (사용자 제보: 비전/자비스가 되살린 울트론을 또 끔): 가디언이 되살리기 전에 지목한 비전에 더해 **자비스도** 닫는다 (`Guard.counter_jarvis`, 되받아치기 + 자비스 견제가 켜졌을 때). 되살아난 인피니티 울트론은 자비스를 뜨자마자 · 1초마다 확인하고, 바쁘면 기다리지 않고 끈다. 파워 스톤 장면은 실제 자비스를 줄기가 닿기 전, 그림이 창을 가리자마자(`stones.KILL`) 끈다.
  - 그래도 지목하지 않은 프로그램이 끄면 막을 수 없다 → 사용자가 설정에 비전 폴더 · 창 제목을 적어야 한다. 가장 확실한 것은 '되살릴 때 관리자 권한으로' (일반 권한 프로그램은 Windows 가 못 끄게 막는다).
- **가디언을 못 끄게** (자비스가 가디언을 먼저 끄는 문제): 가디언이 하나가 아니라 **둘**이 돈다 (`guardian.SLOTS`). 서로를 지켜서(각자 `guard_peers`로 빈 자리를 다시 띄움), 적이 하나를 꺼도 1초 안에 다시 뜬다. 울트론·가디언 셋을 같은 순간에 모두 꺼야 영영 끌 수 있다. 자리별 잠금은 `guardian.lock`·`guardian1.lock`(`Paths.lock_at`, `acquire_slot`). 울트론도 `_guardian_tick`에서 `spawn`으로 빈 자리를 채운다.
- **가디언 늘 켜짐**: 설정에서 끄는 토글을 없앴다. `config._migrate`가 `guardian`을 늘 True로 강제한다(파일에 False로 남아 있어도). 끄는 건 트레이·HUD의 '종료'뿐(`mark_quit`). `guardian_show`·`infinity`·`guardian_admin`·`guardian_counter` 하위 토글은 그대로 보인다.
- **'되살릴 때 관리자 권한으로'(`guardian_admin`) 기본 켜짐** (사용자 요청). 예전 설정 파일에도 한 번만 켜짐으로 옮김(`_MIGRATIONS['guardian_admin_default_on']`) — 그 뒤에 사용자가 끄면 꺼진 채로 남는다.
- 설정 `infinity`(기본 켜짐, 설정 화면 가디언 칸의 '인피니티 울트론' 토글). 끄면 전부 예전 그대로.
- 시험 `tests/test_infinity.py`. 전체 1096개 통과 (아래 베이스라인 3개만 실패).

## 다음 할 일
1. **사용자가 PC 에서 확인** — 여기(Linux)서는 offscreen 그림 · QML 읽기까지만 봤다. 볼 것: HUD 가 인피니티 모습으로 바뀌는가, 부활 연출 끝에 덮개와 HUD 가 딱 겹치는가, 글꼴(Bahnschrift)로 본 이름, 속도.
2. **속도**: 1080p 에서 다 나타난 인피니티 코어 한 장이 이 컨테이너 기준 약 20ms (보통 코어 8ms). 느리면 `infinity._stamp` 로 그려 두는 층을 늘릴 것 (칼날 띠 · 꺾쇠 · 보석 빛무리).
3. 사용자가 손봐 달라고 할 수 있는 것: 모습 · 번쩍임 세기 · 스톤 등장 시간 · 대사(`stones.POWER_* / TIME_DONE`).
4. 지목한 비전이 '살아 있는 울트론 앞에 나타났을 때' 파워 스톤으로 닫는 것은 **하지 않았다** (지금은 비전이 울트론을 끈 뒤 가디언이 닫고 → 타임 스톤). 사용자가 원하면 그때 논의.
5. 다 확인되면 브랜치 → main PR.

## 사용자 선호 / 이미 정해진 것
- 부활 연출: 해킹 화면 5초(점점 심해짐, 색 번짐)→ TV 지직 2초 → **눈부터 옅게→진하게** → 코어 → **화면 가운데에서 HUD 크기로 줄어 그 자리에 HUD 로 남음**. 싸우는 중(비전이 계속 끔)엔 연출 건너뛰고 1초 안에 복귀. 빛 민감: 넓은 면 밝기 급변 1초 3번 이하(30장/초로 시험).
- 가디언: 기본 켜짐. 강제로 꺼지면 1초 안에 되살림. 종료 메뉴로 끈 것은 안 살림. 되받아치기는 **지목한 비전 폴더에서 도는 것 전부(비전 본체 + 비전의 가디언)** 를 닫음(cwd 로도 판별). "관리자 권한으로 켜 줘" / 설정 "되살릴 때 관리자 권한으로" 로 일반 권한 비전이 못 끄게.
- 울트론은 **말하지 않음**(TTS 삭제). 대답은 화면 글자로만. 듣기(음성 인식)는 그대로.
- 인피니티 울트론은 영화 캐릭터를 베끼지 말고 **기존 엠블럼의 원본 업그레이드**로. **왕관 · 노란(금)색은 싫다고 했다** — 붉은색 · 강철색에 여섯 스톤만 색.
- **과격한 연출 좋다고 했다**: 보는 사람 가운데 광과민성이 있는 사람이 없으니 1초에 3번 넘게 깜빡여도 된다, 그 규칙만 지키면 밋밋하다. → 인피니티 부활 · 스톤 장면은 번쩍임 · 흔들림 · 번개를 넣었고 그 규칙을 시험하지 않는다. (해킹 · 흡수 · 보통 부활은 예전 그대로 규칙을 지킨다 — 바꿔 달라고 하면 그때.)

## 테스트 돌리는 법 (이 환경은 Windows 가 아니라 Linux 라 흉내 필요)
- 파이썬 venv 를 새로 만들고 아래를 설치 (Qt offscreen 용 apt 도): 
  `pytest numpy Pillow psutil anthropic httpx PySide6-Essentials PySide6-Addons python-pptx python-docx XlsxWriter openpyxl sherpa-onnx comtypes` / apt: `libegl1 libgl1 libxkbcommon0 libpulse0`.
- **Windows 전용 모듈 흉내**: 아래 내용을 `tests/conftest.py` 로 **임시** 복사하고 테스트 후 **반드시 삭제**(커밋 금지):
  ```python
  import ctypes, sys, types
  from unittest.mock import MagicMock
  ctypes.windll = MagicMock(); ctypes.WinDLL = MagicMock(); ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
  import ctypes.wintypes
  for m in ["win32api","win32con","win32gui","win32process","win32clipboard","pywintypes","comtypes","comtypes.client",
            "pycaw","pycaw.pycaw","sounddevice","speech_recognition","edge_tts","sherpa_onnx","win32com","win32com.client"]:
      sys.modules.setdefault(m, MagicMock())
  ```
- 실행: `QT_QPA_PLATFORM=offscreen <venv>/bin/python -m pytest -q`
- **베이스라인 실패 3개는 원래부터 이 환경 탓** (내 변경과 무관): `tests/test_stt_routing.py` 의 3개 (standby_wake_offline / active_offline_falls_back / auto_mode_retries). 그 외 전부 통과해야 함(현재 1102개).

## 미리보기(그림/영상) 만들어 사용자에게 보여주는 법
- offscreen 으로 QImage 를 numpy→PIL 로 저장. 패턴은 `scratchpad/inf/shot.py`, `scratchpad/revive/video_v2.py` 참고(스크립트는 세션 scratchpad 에 있어 새 세션엔 없음 — 다시 작성). `SendUserFile` 로 보냄. 연출 영상은 ffmpeg(설치돼 있음)로 프레임+wav 합쳐 mp4.
- 그림을 `Read` 로 직접 보고 품질을 확인한 뒤 사용자에게 보낼 것.

## 코드 지도 (가디언·연출 관련)
- `jarvis/guardian.py` — 울트론 지키는 별개 프로세스(되살리기·비전 닫기·관리자 권한 승격·독립 프로세스로 띄우기). 순수 로직(decide/is_enemy/same_process…)은 Linux 에서 시험 가능.
- `jarvis/revive.py` + `jarvis/revive_view.py` — 부활 연출(재료·시간표·사건 / 그리기). `draw_core` 가 울트론 코어를 그림.
- `jarvis/infinity.py` · `infinity_item.py` · `stones.py` · `stones_view.py` · `ui/InfinityCore.qml` — 인피니티 울트론 (위 '해 둔 것').
- `jarvis/app.py` — 오케스트레이터. `_revive_begin/_on_revive/_revive_handoff/_revive_done`, `_relaunch_admin`, `guardian_status`, 설정 저장(`save_settings`), 트레이.
- `jarvis/brain.py` — 명령 라우팅. `_hud_command` 안에 REVIVE_SHOW/REVIVE_TEST/ADMIN_ON 등. `on_hud(action)` → app `_on_hud`.
- `jarvis/config.py` — DEFAULTS(guardian, guardian_show, guardian_admin, enemy_installs/titles 등) + `_migrate`(설정 한 번만 옮기기) + `load_config`(가디언이 Qt 없이 읽는 용).
- 설정 화면: `ui/SettingsPanel.qml`, HUD: `ui/Main.qml` · `ui/Emblem.qml` · `ui/ActiveMode.qml`.

## 주의 (제약)
- **줄 끝 유지**: 일부 파일은 CRLF(`tools.py` `uia.py` `local_router.py` `brain.py`? README 등), 일부는 LF. 편집할 때 그 파일의 줄 끝을 그대로 둘 것. (scratchpad 의 `ed.py` 헬퍼가 CRLF/LF 보존. 없으면 다시 작성.)
- 사용자 이메일 등 개인정보를 외부로 보내지 않음. API 키를 채팅에 붙여 달라고 하지 않음.
- 사용자의 미리캔버스 캔버스는 고치지 않음(예전 대화 맥락).
- 가디언/부활/비전 관련은 **사용자 본인 PC·본인 앱 방어** 맥락. 비전 자동 사냥 같은 공격적 동작은 사용자가 '지목한 것'에 한정.

## 사용자가 PC 에서 할 일 (현재까지)
- PC 울트론 폴더에서 `git checkout main && git pull`(이 브랜치는 PR 로 main 에 머지됨). 단, 인피니티 울트론은 아직 브랜치에만 있고 연결 안 됨.
- 예전 `data/tts_cache` 폴더는 지워도 됨(이제 안 씀). `requirements.txt` 에서 `edge-tts` 빠짐.
