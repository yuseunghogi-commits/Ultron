"""U.L.T.R.O.N 실행 진입점.

    python main.py              # 일반 실행
    python main.py --no-mic     # 마이크 없이 (텍스트 입력만)
    python main.py --no-greet   # 시작 인사 생략
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# 고해상도 화면에서 선명하게
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QSG_RHI_BACKEND", "d3d11")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from jarvis.config import DATA_DIR, LOG_PATH, ROOT, load_config

INSTANCE_KEY = "ultron-hud-" + os.environ.get("USERNAME", "user")


def setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")]
    if sys.stderr:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def already_running() -> bool:
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="U.L.T.R.O.N")
    parser.add_argument("--no-mic", action="store_true", help="마이크 사용 안 함")
    parser.add_argument("--no-greet", action="store_true", help="시작 인사 생략")
    parser.add_argument("--shot", metavar="PNG", help="(개발용) N초 후 HUD 화면을 PNG로 저장하고 종료")
    parser.add_argument("--shot-delay", type=float, default=4.0)
    parser.add_argument("--demo", action="store_true", help="(개발용) 상태 데모")
    parser.add_argument("--revived", action="store_true", help=argparse.SUPPRESS)   # 가디언이 되살려 준 울트론
    parser.add_argument("--fast", action="store_true", help=argparse.SUPPRESS)      # 공격받는 중 — 긴 연출을 건너뛴다
    parser.add_argument("--closed", default="", help=argparse.SUPPRESS)            # 가디언이 닫은 '비전'
    args = parser.parse_args()

    setup_logging()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("ULTRON")
    app.setQuitOnLastWindowClosed(False)

    if not args.shot and already_running():
        print("U.L.T.R.O.N 이 이미 실행 중입니다.")
        return 0

    # 가디언(울트론을 지키는 감시 프로그램)에게 '지금 이 울트론을 지켜라'를 가장 먼저 알린다.
    # 화면 · 모델을 다 불러온 뒤에 알리면, 그 사이 가디언이 아직 꺼져 있는 줄 알고 울트론을 한 번 더 켤 수 있다.
    if not (args.shot or args.demo) and sys.platform == "win32":
        try:
            if load_config().get("guardian"):
                from jarvis import guardian
                guardian.register(DATA_DIR, ROOT)
        except Exception as e:
            logging.getLogger("main").warning("가디언 등록 실패: %s", e)

    from jarvis.app import Jarvis
    core = Jarvis(app, args)

    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_KEY)
    server.listen(INSTANCE_KEY)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), core.show_external()))

    if args.demo or args.shot:
        from jarvis.demo import run_demo
        run_demo(core, args)

    code = app.exec()
    # QML 화면을 먼저 정리해야 종료 시 'jarvis is null' 경고가 나지 않는다
    import shiboken6
    core.win.hide()
    if core.overlay is not None:
        core.overlay.hide()
    shiboken6.delete(core.engine)
    return code


if __name__ == "__main__":
    sys.exit(main())
