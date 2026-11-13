# 세션 인수인계 (U.L.T.R.O.N 작업 이어가기)

새 Claude Code 세션에서 이 저장소 작업을 그대로 이어가기 위한 메모. **새 세션은 이 파일부터 읽으세요.**
(모델이 Opus 4.8 / 5.5 / Fable 등으로 바뀌어도 이 문서대로 이어가면 됩니다.)

## 지금 상태 (한 줄)
PC판 음성 AI 비서 울트론을 여러 번 개선 중. **지금 진행 중인 일: 인피니티 울트론(각성판 엠블럼) 모습을 만들어 두었고(`jarvis/infinity.py`), 다듬은 뒤 "부활 연출" 끝에 이 모습으로 떠오르게 연결하는 것**이 다음 단계.

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

## 다음 할 일 (인피니티 울트론 연결)
1. `jarvis/infinity.py` 의 `paint(painter, t, reveal)` 가 인피니티 울트론을 440 단위(가운데 0,0)로 그린다 — `revive_view.draw_core` 와 같은 좌표계. 사용자가 모습을 더 손봐 달라고 할 수 있으니 **먼저 미리보기로 확인**받을 것 (아래 '미리보기' 참고).
2. 연결 지점: `jarvis/revive_view.py` 의 부활 연출. 코어가 다 나타난 뒤(`looks()` 의 `done`, `Assets.finished_core`, `paint()` 의 hold/shrink/handoff 단계)에 **일반 울트론 코어 대신 인피니티 코어**를 그리게 한다. 눈→코어 순서로 나타나는 `draw_core` 자리를 인피니티용으로 바꾸거나, "form" 단계부터 인피니티로 전환.
3. HUD 쪽도 바꿀지 사용자에게 물을 것: 되살아난 뒤 HUD(ui/Emblem.qml)도 인피니티로 둘지, 아니면 연출에서만 보여 주고 HUD 는 그대로일지. (QML Emblem 은 벡터로 따로 그려짐 — 인피니티를 QML 로도 그리려면 추가 작업.)
4. 설정 토글 `infinity_revive`(기본?) 추가 고려. 테스트(`tests/test_revive.py` 패턴)와 미리보기 영상 후 커밋·PR.

## 사용자 선호 / 이미 정해진 것
- 부활 연출: 해킹 화면 5초(점점 심해짐, 색 번짐)→ TV 지직 2초 → **눈부터 옅게→진하게** → 코어 → **화면 가운데에서 HUD 크기로 줄어 그 자리에 HUD 로 남음**. 싸우는 중(비전이 계속 끔)엔 연출 건너뛰고 1초 안에 복귀. 빛 민감: 넓은 면 밝기 급변 1초 3번 이하(30장/초로 시험).
- 가디언: 기본 켜짐. 강제로 꺼지면 1초 안에 되살림. 종료 메뉴로 끈 것은 안 살림. 되받아치기는 **지목한 비전 폴더에서 도는 것 전부(비전 본체 + 비전의 가디언)** 를 닫음(cwd 로도 판별). "관리자 권한으로 켜 줘" / 설정 "되살릴 때 관리자 권한으로" 로 일반 권한 비전이 못 끄게.
- 울트론은 **말하지 않음**(TTS 삭제). 대답은 화면 글자로만. 듣기(음성 인식)는 그대로.
- 인피니티 울트론은 영화 캐릭터를 베끼지 말고 **기존 엠블럼의 원본 업그레이드**로 (금빛 왕관·여섯 보석·흰 눈·∞).

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
- **베이스라인 실패 3개는 원래부터 이 환경 탓** (내 변경과 무관): `tests/test_stt_routing.py` 의 3개 (standby_wake_offline / active_offline_falls_back / auto_mode_retries). 그 외 전부 통과해야 함(현재 ~1075개).

## 미리보기(그림/영상) 만들어 사용자에게 보여주는 법
- offscreen 으로 QImage 를 numpy→PIL 로 저장. 패턴은 `scratchpad/inf/shot.py`, `scratchpad/revive/video_v2.py` 참고(스크립트는 세션 scratchpad 에 있어 새 세션엔 없음 — 다시 작성). `SendUserFile` 로 보냄. 연출 영상은 ffmpeg(설치돼 있음)로 프레임+wav 합쳐 mp4.
- 그림을 `Read` 로 직접 보고 품질을 확인한 뒤 사용자에게 보낼 것.

## 코드 지도 (가디언·연출 관련)
- `jarvis/guardian.py` — 울트론 지키는 별개 프로세스(되살리기·비전 닫기·관리자 권한 승격·독립 프로세스로 띄우기). 순수 로직(decide/is_enemy/same_process…)은 Linux 에서 시험 가능.
- `jarvis/revive.py` + `jarvis/revive_view.py` — 부활 연출(재료·시간표·사건 / 그리기). `draw_core` 가 울트론 코어를 그림.
- `jarvis/infinity.py` — 인피니티 울트론 모습(아직 미연결).
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
