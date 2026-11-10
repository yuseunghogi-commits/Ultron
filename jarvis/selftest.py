"""자가 점검 — 실제 Windows PC 에서만 확인할 수 있는 부분(화면 캡처 · 좌표 · UI 자동화 · 오프라인 인식)을 한 번에 돌려 본다.

    python -m jarvis.selftest          (울트론을 끈 상태에서 실행해도 된다)

시작하면 5초를 센다. 그동안 점검에 쓸 창(크롬 · 메모장 등)을 눌러 앞에 띄워 두면 그 창을 읽어 본다.
아무것도 누르거나 입력하지 않는다 — 마우스 위치만 잠깐 옮겼다가 되돌린다.
결과는 화면에 나오고 data/selftest.txt 에도 저장된다. 그 파일 내용을 그대로 알려 주면 문제를 찾을 수 있다.
"""
from __future__ import annotations

import ctypes
import sys
import time
import traceback

LINES: list[str] = []


def say(text: str) -> None:
    LINES.append(text)
    print(text, flush=True)


def check(name: str, fn) -> object:
    """점검 하나: 성공하면 결과 요약을, 실패하면 오류를 적는다. 하나가 실패해도 다음 점검은 계속한다."""
    try:
        out = fn()
        say(f"[통과] {name}: {out}")
        return out
    except Exception as e:
        say(f"[실패] {name}: {type(e).__name__}: {e}")
        LINES.append("        " + traceback.format_exc().strip().splitlines()[-3].strip())
        return None


def main() -> int:
    if sys.platform != "win32":
        print("Windows 에서만 실행할 수 있습니다.")
        return 1
    try:   # 울트론 앱(Qt)과 같은 좌표 기준으로 맞춘다: 모니터별 배율 인식
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    from PIL import ImageGrab

    from . import uia, vision, winutil
    from .config import DATA_DIR

    user32 = ctypes.windll.user32
    say(f"울트론 자가 점검 — {time.strftime('%Y-%m-%d %H:%M')} · Python {sys.version.split()[0]}")
    say("5초 뒤에 지금 앞에 있는 창을 점검합니다. 점검할 창(크롬 등)을 눌러 두세요…")
    time.sleep(5)
    hwnd = user32.GetForegroundWindow()
    say(f"점검할 창: {winutil.window_title(hwnd)!r}")

    # ---- 화면 영역 · 캡처 ----
    primary = check("주 모니터 영역", lambda: winutil.monitor_rect(0))
    mon = check("이 창이 있는 모니터 영역", lambda: winutil.monitor_rect(hwnd))
    win = check("창 영역", lambda: winutil.window_rect(hwnd))
    say(f"       모니터 개수 {user32.GetSystemMetrics(80)} · 가상 화면 "
        f"({user32.GetSystemMetrics(76)}, {user32.GetSystemMetrics(77)}) {user32.GetSystemMetrics(78)}x{user32.GetSystemMetrics(79)}"
        f" · 이 창의 배율 {getattr(user32, 'GetDpiForWindow', lambda h: 0)(hwnd) / 96:.2f}")

    def grab():
        img = ImageGrab.grab(bbox=mon, all_screens=True)
        want = (mon[2] - mon[0], mon[3] - mon[1])
        if img.size != want:
            raise RuntimeError(f"캡처 크기 {img.size} 가 모니터 크기 {want} 와 다릅니다 (배율 문제 — 좌표가 어긋날 수 있음)")
        return f"{img.size[0]}x{img.size[1]} · 표준 등급으로 보낼 크기 {vision.send_size(*img.size, 'standard')} · 고해상도 {vision.send_size(*img.size, 'high')}"

    if mon:
        check("모니터 캡처", grab)

    def cursor():
        pt = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        back = (pt.x, pt.y)
        x, y = (mon[0] + mon[2]) // 2 + 37, (mon[1] + mon[3]) // 2 + 23
        uia.move_to(x, y)
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetCursorPos(*back)
        if abs(pt.x - x) > 1 or abs(pt.y - y) > 1:
            raise RuntimeError(f"({x}, {y}) 로 옮겼는데 ({pt.x}, {pt.y}) 에 있습니다 (좌표 기준이 다름)")
        return f"({x}, {y}) 로 옮기고 되돌림"

    if mon:
        import ctypes.wintypes  # noqa: F401
        check("마우스 좌표", cursor)

    def changes():
        a = vision.small_gray(ImageGrab.grab(bbox=mon, all_screens=True))
        time.sleep(0.4)
        b = vision.small_gray(ImageGrab.grab(bbox=mon, all_screens=True))
        return f"0.4초 사이 달라진 비율 {vision.changed_fraction(a, b):.4f} (동영상이 없으면 0 에 가까워야 함)"

    if mon:
        check("화면 변화 감지", changes)

    # ---- UI 자동화 ----
    screen = uia.Screen()

    def read():
        screen.read(hwnd)
        if not screen.items:
            raise RuntimeError("누를 수 있는 요소를 하나도 읽지 못했습니다")
        return f"요소 {len(screen.items)}개 · 예: " + " / ".join(it.line() for it in screen.items[:4])

    check("창 요소 읽기 (read_ui)", read)
    check("창 글자 읽기 (read_screen_text)", lambda: (lambda t: f"{len(t)}자 · 첫 줄: {t.splitlines()[1][:60] if len(t.splitlines()) > 1 else t[:60]!r}")(screen.read_text(hwnd)))

    def at():
        it = next(i for i in screen.items if i.name and i.rect[2] - i.rect[0] > 20)
        x, y = (it.rect[0] + it.rect[2]) // 2, (it.rect[1] + it.rect[3]) // 2
        name, kind = uia.element_at(x, y)
        if not name:
            raise RuntimeError(f"'{it.name}' 의 가운데 ({x}, {y}) 에서 요소 이름을 얻지 못했습니다")
        return f"({x}, {y}) → '{name}' {kind} (목록의 이름: '{it.name}')"

    if screen.items:
        check("좌표에 있는 요소 확인", at)

    def marks():
        img = ImageGrab.grab(bbox=mon, all_screens=True)
        size = vision.send_size(*img.size, "standard")
        view = vision.make_view(mon, size)
        picked = vision.pick_marks([(it.n, it.rect) for it in screen.items], view)
        vision.annotate(img.resize(size), picked).save(DATA_DIR / "selftest_marks.png")
        return f"번호 상자 {len(picked)}개 → data/selftest_marks.png (상자가 실제 버튼 위에 그려졌는지 눈으로 확인)"

    if mon and screen.items:
        check("번호 상자 그리기", marks)
    check("화면 밖 요소 찾기", lambda: f"{len(screen.find_hidden(hwnd, 'a'))}개 (이름에 'a' 가 든 것 — 웹 페이지가 길면 0 보다 큼)")
    check("창이 클릭을 막는지 확인", lambda: f"이 창 가운데: {winutil.blocks_clicks(hwnd, (win[0] + win[2]) // 2, (win[1] + win[3]) // 2) if win else '창 영역 없음'}")

    # ---- 오프라인 음성 인식 ----
    def stt():
        import numpy as np

        from .local_stt import LocalSTT, _present
        if not _present():
            return "모델이 아직 없음 (앱을 한 번 실행하면 내려받습니다) — 건너뜀"
        s = LocalSTT()
        s._load()
        if not s.ready:
            raise RuntimeError(s.error)
        s.recognize((np.random.default_rng(0).standard_normal(16000) * 300).astype(np.int16))
        return f"준비됨 · 한 번 인식 {s.last_ms}ms · 글 조각 시각 정보 {'있음' if isinstance(s.last, tuple) else '없음'}"

    check("오프라인 인식 모델", stt)

    failed = sum(1 for line in LINES if line.startswith("[실패]"))
    say(f"끝 — 실패 {failed}건. 이 내용이 {DATA_DIR / 'selftest.txt'} 에 저장됐습니다.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "selftest.txt").write_text("\n".join(LINES), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
