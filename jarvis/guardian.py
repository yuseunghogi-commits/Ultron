"""가디언 — 울트론을 지키는 작은 감시 프로그램 (울트론과 따로 도는 별개 프로세스).

왜 따로 도는가: 누가 울트론을 강제로 끄면 울트론 안에서는 아무 코드도 돌지 못한다 (그 순간 사라지므로).
그래서 밖에서 지켜보다가, 울트론이 꺼지면 다시 켜 주는 역할을 울트론 바깥의 이 프로그램이 한다.
반대로 울트론도 5초마다 가디언이 살아 있는지 보고, 없으면 다시 띄운다 — 서로가 서로를 지킨다.

하는 일 (설정 'guardian' 이 켜졌을 때만, Windows 전용):
  · 울트론이 살아 있는지 3초마다 본다. 프로세스 번호만 보지 않고 '그 번호의 프로그램이 켜진 시각'까지 맞춰 본다
    (울트론이 꺼진 뒤 같은 번호를 다른 프로그램이 받아도 속지 않는다. 절전에서 깨어나도 오작동하지 않는다).
  · 사용자가 직접 끈 것(종료 메뉴)이면 그냥 둔다 — 울트론이 꺼지기 전에 'quit' 표시를 남긴다.
  · 그게 아니라 누가 강제로 껐으면 → 울트론을 다시 켠다. 몇 번을 꺼도 매번 다시 켠다 (쉬지 않는다).
  · '되받아치기'(guardian_counter)가 켜져 있으면, 다시 켜기 전에 '비전'을 닫는다.

'비전'을 어떻게 고르는가 — 엉뚱한 프로그램을 닫는 일이 없도록, 사용자가 지목한 것만:
  · 설정에 적어 둔 폴더(enemy_installs)에서 실행된 프로그램, 또는
  · 설정에 적어 둔 창 제목(enemy_titles)과 정확히 같은 창을 띄운 프로그램.
  울트론 자신(이 설치 폴더)은 어떤 경우에도 고르지 않는다. 드라이브 전체 · Windows · Program Files · 사용자 폴더 자체처럼
  너무 넓은 폴더는 지목해도 무시한다 (그 안의 평범한 프로그램까지 닫히므로).
  ('누가 나를 껐는가'를 운영체제에 물어 확실히 알아내는 방법은 일반 프로그램에는 없다 — 그래서 미리 지목한 것만 닫는다.)
"""
from __future__ import annotations

import json
import logging
import ntpath
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger("jarvis.guardian")

POLL = 1.0                 # 몇 초마다 살아 있는지 보는가 (프로세스 번호 하나를 보는 일이라 1초마다 봐도 부담이 없다)
REGISTER_WAIT = 10.0       # 다시 켠 울트론이 '나 떴다'(등록)를 알릴 때까지 기다리는 최대 시간. 그 안에 또 켜지 않되,
                           # 이 안에 등록이 없으면 (뜨다 말고 또 꺼졌다) 다시 켠다 — 예전엔 30초를 기다려 빈틈이 컸다
REVIVE_QUIET = 30.0        # 되살린 지 이 안에 또 꺼지면 (공격받는 중) 긴 연출 없이 바로 돌아온다 (연출 끝나기 전에 또 꺼지는 반복 방지)
                           # (아직 뜨는 중인 울트론을 죽은 줄 알고 한 번 더 켜면 울트론이 두 개가 된다). 넘으면 다시 켠다.
LOCK_STALE = 10.0          # 내용이 빈 잠금 파일이 이보다 오래되면 버려진 것으로 본다
GUARDIAN_MODULE = "jarvis.guardian"


# ---------------------------------------------------------------- 순수 판단 (운영체제와 무관 · 테스트하기 쉽게)
def decide(quit_flag: bool, dead: bool) -> str:
    """지금 무엇을 할까: 'quit'(사용자가 껐으니 가디언도 끝낸다) · 'wait'(살아 있다) · 'restart'(다시 켠다).
    몇 번째로 꺼졌든 상관없이 매번 다시 켠다."""
    if quit_flag:
        return "quit"
    return "restart" if dead else "wait"


def same_process(found_created: float | None, recorded_created: float | None) -> bool:
    """그 번호의 프로그램이 울트론이 남긴 것과 같은 때 켜졌는가 (번호를 다른 프로그램이 다시 받은 경우를 가린다)."""
    if found_created is None:
        return False                            # 그 번호의 프로그램이 없다
    if not recorded_created:
        return True                             # 예전 형식의 기록 — 번호만으로 본다
    return abs(found_created - recorded_created) < 1.0


def _norm(path: str) -> str:
    """Windows 경로로 정리: 소문자 · 구분 기호는 \\ · '..' 풀기. (가디언은 Windows 에서만 돌므로 늘 Windows 규칙으로 본다.)"""
    return ntpath.normcase(ntpath.normpath(path or ""))


def is_within(path: str, root: str) -> bool:
    """path 가 root 폴더 안(또는 그 자체)인가. 대소문자 · 구분 기호 차이를 무시한다 (Windows)."""
    try:
        p, r = _norm(path), _norm(root)
    except (TypeError, ValueError):
        return False
    if not p or not r or p == ".":
        return False
    return p == r or p.startswith(r.rstrip("\\") + "\\")


_SYSTEM_TOP = {"windows", "program files", "program files (x86)", "programdata", "users"}


def too_broad(root: str) -> bool:
    """'비전 폴더'로 지목하기엔 너무 넓은가 — 드라이브 전체 · Windows · Program Files · 사용자 폴더 자체.
    이런 곳을 지목하면 그 안의 평범한 프로그램까지 '비전'으로 닫혀 버리므로 무시한다 (오인 방지)."""
    parts = [x for x in _norm(root).split("\\") if x]
    if len(parts) <= 1:
        return True                             # 'C:\' 처럼 드라이브 전체
    if len(parts) == 2 and parts[1] in _SYSTEM_TOP:
        return True                             # 'C:\Windows' · 'C:\Program Files' · 'C:\Users'
    return len(parts) == 3 and parts[1] == "users"   # 'C:\Users\나' — 사용자 폴더 전체


def usable_install(inst: str, own_root: str) -> bool:
    """지목한 '비전 폴더'를 쓸 수 있는가 — 너무 넓거나, 울트론 폴더를 품고 있거나(그 안의 다른 프로그램까지 닫힌다),
    울트론 폴더 안이면(울트론 자신은 고르지 않으므로 아무 뜻이 없다) 쓰지 않는다."""
    if not inst or too_broad(inst):
        return False
    return not (own_root and (is_within(own_root, inst) or is_within(inst, own_root)))


def is_enemy(title: str, exe_path: str, enemy_installs: list[str], enemy_titles: list[str], own_root: str) -> bool:
    """이 프로그램이 사용자가 지목한 '비전'인가. 울트론 자신의 설치 폴더에서 돈다면 절대 아니다 (오인 방지)."""
    if own_root and exe_path and is_within(exe_path, own_root):
        return False
    t = (title or "").strip()
    if t and any(t == (e or "").strip() for e in enemy_titles if e):
        return True
    return bool(exe_path and any(usable_install(inst, own_root) and is_within(exe_path, inst) for inst in enemy_installs))


def script_dir(cmdline: list[str]) -> str:
    """파이썬 프로그램이면 실행한 스크립트(main.py)가 있는 폴더. 비전도 울트론처럼 pythonw.exe 로 돌기 쉬워서,
    실행 파일(pythonw.exe) 위치만 보면 어느 폴더의 프로그램인지 알 수 없다 — 스크립트 위치로 본다."""
    for arg in (cmdline or [])[1:]:
        if arg and not arg.startswith("-") and arg.lower().endswith((".py", ".pyw")):
            return ntpath.dirname(arg)
    return ""


# ---------------------------------------------------------------- 파일 (울트론 ↔ 가디언이 주고받는 표시)
@dataclass
class Paths:
    data: Path

    @property
    def info(self) -> Path:
        return self.data / "guardian.json"      # 울트론이 남기는 정보: 번호 · 켜진 시각 · 설치 폴더 · 다시 켜는 명령

    @property
    def quit(self) -> Path:
        return self.data / "guardian.quit"      # 사용자가 울트론을 직접 껐다는 표시

    @property
    def lock(self) -> Path:
        return self.data / "guardian.lock"      # 지금 도는 가디언의 번호 (가디언이 여러 개 뜨지 않게)


def read_info(p: Paths) -> dict:
    try:
        d = json.loads(p.info.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- 프로세스 (psutil — 테스트에서는 바꿔 끼운다)
def created_at(pid: int) -> float | None:
    """그 번호의 프로그램이 켜진 시각 (없으면 None)."""
    if not pid:
        return None
    try:
        import psutil
        p = psutil.Process(pid)
        if p.status() == psutil.STATUS_ZOMBIE:
            return None
        return p.create_time()
    except Exception:
        return None


def shutting_down() -> bool:
    """PC 가 꺼지거나 로그아웃하는 중인가 — 그때는 Windows 가 프로그램을 차례로 끄는 것이니 되살리지 않는다."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.GetSystemMetrics(0x2000))     # SM_SHUTTINGDOWN
    except Exception:
        return False


def is_guardian(pid: int) -> bool:
    """그 번호의 프로그램이 가디언인가 (명령줄에 jarvis.guardian 이 들어 있다)."""
    if not pid:
        return False
    try:
        import psutil
        return GUARDIAN_MODULE in " ".join(psutil.Process(pid).cmdline())
    except Exception:
        return False


def _lock_pid(p: Paths) -> int | None:
    try:
        text = p.lock.read_text(encoding="utf-8").strip()
        return int(text) if text else None
    except (OSError, ValueError):
        return None


def running(data_dir: Path) -> bool:
    """가디언이 지금 돌고 있는가."""
    pid = _lock_pid(Paths(Path(data_dir)))
    return bool(pid) and is_guardian(pid)


def acquire_lock(p: Paths, me: int | None = None) -> bool:
    """가디언 자리 차지하기 → 차지했으면 True. 다른 가디언이 이미 돌면 False (이 가디언은 그냥 끝낸다)."""
    me = me or os.getpid()
    for _ in range(2):
        try:
            fd = os.open(p.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder = _lock_pid(p)
            if holder and holder != me and is_guardian(holder):
                return False                    # 다른 가디언이 이미 지킨다
            if holder is None:
                try:
                    if time.time() - p.lock.stat().st_mtime < LOCK_STALE:
                        return False            # 다른 가디언이 막 자리 잡는 중
                except OSError:
                    pass
            try:
                p.lock.unlink()                 # 버려진 잠금 (그 가디언은 이미 없다)
            except OSError:
                pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(me))
        return True
    return False


def release_lock(p: Paths, me: int | None = None) -> None:
    if _lock_pid(p) == (me or os.getpid()):
        try:
            p.lock.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- 따로 띄우기 (프로세스 트리에서 떼어 낸다)
# 작업 관리자에서 울트론을 '작업 끝내기' 하면 울트론이 띄운 자식 프로세스(프로세스 트리)까지 함께 끝난다 — 가디언을 울트론의
# 자식으로 띄우면 울트론과 함께 죽어서 아무도 되살리지 못한다. 그래서 잠깐 뜨고 바로 끝나는 '다리' 파이썬을 거쳐 띄운다:
# 다리가 끝나면 띄운 프로세스는 누구의 자식도 아니게 된다. (작업 객체(Job)에 묶여 있으면 거기서도 빠져나온다 — 안 되면 그냥)
DETACHED, NEW_GROUP, BREAKAWAY, NO_WINDOW = 0x00000008, 0x00000200, 0x01000000, 0x08000000
_BRIDGE = ("import subprocess,sys\n"
           "cwd = sys.argv[1] or None\n"
           "if sys.platform != 'win32':\n"
           "    subprocess.Popen(sys.argv[2:], cwd=cwd, start_new_session=True, close_fds=True)\n"
           "else:\n"
           "    for f in (0x00000008|0x00000200|0x01000000, 0x00000008|0x00000200):\n"
           "        try:\n"
           "            subprocess.Popen(sys.argv[2:], cwd=cwd, creationflags=f, close_fds=True)\n"
           "            break\n"
           "        except OSError:\n"
           "            pass\n")


def _python(windowless: bool = True) -> str:
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    return str(pyw) if windowless and pyw.exists() else sys.executable


def launch_detached(cmd: list[str], cwd: str | None = None) -> None:
    """cmd 를 이 프로세스와 엮이지 않은 독립 프로세스로 띄운다 (다리 파이썬을 거쳐서 — 위 설명)."""
    args = [_python(), "-c", _BRIDGE, cwd or "", *cmd]
    if sys.platform != "win32":
        subprocess.Popen(args, cwd=cwd or None, start_new_session=True, close_fds=True)
        return
    for flags in (NO_WINDOW | BREAKAWAY, NO_WINDOW):
        try:
            subprocess.Popen(args, cwd=cwd or None, creationflags=flags, close_fds=True)
            return
        except OSError:
            continue
    raise OSError("독립 프로세스를 띄우지 못했습니다")


# ---------------------------------------------------------------- 울트론 쪽에서 쓰는 함수 (main.py · app.py 가 부른다)
def relaunch_cmd(root: Path) -> list[str]:
    """울트론을 다시 켜는 명령 — 창 없는 pythonw 로 (없으면 지금 파이썬으로)."""
    return [_python(), str(Path(root) / "main.py")]


def register(data_dir: Path, root: Path) -> None:
    """'지금 이 울트론을 지켜라' — 켜지자마자(main.py 맨 앞) 부른다. 늦게 알리면 가디언이 아직 죽은 줄 알고
    울트론을 한 번 더 켜 버릴 수 있다."""
    write_info(data_dir, os.getpid(), str(root), relaunch_cmd(root))


def write_info(data_dir: Path, pid: int, own_root: str, relaunch: list[str]) -> None:
    """울트론이 켜질 때: 가디언이 알아야 할 정보를 남긴다."""
    p = Paths(Path(data_dir))
    p.data.mkdir(parents=True, exist_ok=True)
    try:
        p.quit.unlink()                         # 지난번에 남은 '직접 껐음' 표시를 지운다 (이번엔 새로 켜졌으니)
    except OSError:
        pass
    info = {"pid": pid, "created": created_at(pid), "root": own_root, "relaunch": relaunch}
    tmp = p.info.with_suffix(".tmp")
    tmp.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p.info)                     # 가디언이 반쯤 쓴 파일을 읽지 않게


def mark_quit(data_dir: Path) -> None:
    """사용자가 울트론을 직접 껐다 — 가디언이 되살리지 않도록 표시를 남긴다."""
    p = Paths(Path(data_dir))
    try:
        p.data.mkdir(parents=True, exist_ok=True)
        p.quit.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def spawn(data_dir: Path) -> bool:
    """가디언을 따로 띄운다 (이미 돌고 있으면 띄우지 않는다) → 띄웠으면 True."""
    if sys.platform != "win32" or running(data_dir):
        return False
    try:
        launch_detached([_python(), "-m", GUARDIAN_MODULE], str(Path(data_dir).parent))   # 울트론의 자식이 되지 않게
        return True
    except Exception as e:
        log.warning("가디언을 띄우지 못했습니다: %s", e)
        return False


# ---------------------------------------------------------------- 가디언 본체 (별개 프로세스로 돈다)
@dataclass
class Guard:
    data_dir: Path
    load_cfg: Callable[[], dict]                # 설정을 매번 새로 읽는다 — 켜고 끄기 · 비전 지목이 바로 반영되게
    paths: Paths = field(init=False)
    awaiting: tuple | None = None               # 방금 다시 켰다: ((죽은 번호, 켜진 시각), 기다림이 끝나는 시각)
    revived: int = 0                            # 지금까지 되살린 횟수 (기록용)
    last_revive: float | None = None            # 마지막으로 되살린 때 (초) — 곧바로 또 꺼지면 '공격받는 중'으로 본다

    def __post_init__(self) -> None:
        self.paths = Paths(Path(self.data_dir))

    def enemies(self, cfg: dict, own_root: str) -> list:
        """지금 돌고 있는 프로그램 중 사용자가 지목한 '비전'들 → [(프로세스, 이름표)]."""
        import psutil
        installs = [str(x) for x in (cfg.get("enemy_installs") or []) if x]
        titles = [str(x) for x in (cfg.get("enemy_titles") or []) if x]
        if not installs and not titles:
            return []
        by_title = _title_owners(titles) if titles else {}
        out = []
        for proc in psutil.process_iter(["pid", "exe", "cmdline"]):
            try:
                if proc.pid == os.getpid():
                    continue
                exe = proc.info.get("exe") or ""
                folder = script_dir(proc.info.get("cmdline") or [])
                title = by_title.get(proc.pid, "")
                # 파이썬 프로그램은 스크립트 폴더로, 그 밖의 프로그램은 실행 파일 위치로 본다
                where = ntpath.join(folder, "main.py") if folder else exe
                if is_enemy(title, where, installs, titles, own_root):
                    label = title or (ntpath.basename(folder.rstrip("\\")) if folder else ntpath.basename(exe)) or "비전"
                    out.append((proc, label))
            except Exception:
                continue
        return out

    def counter(self, cfg: dict, own_root: str) -> list[str]:
        """비전을 닫는다 → 닫은 프로그램 이름들. (되받아치기가 켜졌을 때만 부른다.)"""
        closed = []
        for proc, label in self.enemies(cfg, own_root):
            try:
                proc.kill()
                proc.wait(3)
                if label not in closed:
                    closed.append(label)
                log.info("비전을 닫음 (pid %d, %s)", proc.pid, label)
            except Exception as e:
                log.warning("비전을 닫지 못함 (pid %d): %s — 관리자 권한으로 켜졌을 수 있음", proc.pid, e)
        return closed

    def relaunch(self, info: dict, closed: list[str] | None = None, fast: bool = False) -> None:
        cmd = list(info.get("relaunch") or [])
        if not cmd:
            return
        cmd.append("--revived")                 # 되살아난 울트론은 평소 인사 대신 '되살아났다'를 띄운다
        if fast:
            cmd.append("--fast")                # 공격받는 중 — 긴 연출을 건너뛰고 바로 돌아온다
        if closed:
            cmd += ["--closed", ", ".join(closed)[:120]]
        try:
            launch_detached(cmd, info.get("root") or None)      # 가디언의 자식이 되지 않게 (함께 끝나지 않게)
            log.info("울트론을 다시 켰습니다")
        except Exception as e:
            log.warning("울트론을 다시 켜지 못했습니다: %s", e)

    def step(self, now: float) -> str:
        """한 번 확인하고 그 결과를 돌려준다 (테스트하기 쉽게 반복문과 분리)."""
        cfg = self.load_cfg() or {}
        if not cfg.get("guardian"):
            return "off"
        quit_flag = self.paths.quit.exists()
        if quit_flag:
            return "quit"                       # 사용자가 직접 껐다 — 무엇을 기다리던 중이든 가디언도 끝낸다
        info = read_info(self.paths)
        pid = int(info.get("pid") or 0)
        created = info.get("created")
        if self.awaiting:
            dead_key, until = self.awaiting
            if (pid, created) != dead_key:
                self.awaiting = None            # 새 울트론이 등록했다 — 아래에서 그 번호를 지킨다
            elif now < until:
                return "wait"                   # 다시 켠 울트론이 아직 뜨는 중 (아직 등록 전) — 잠깐 더 기다린다
            else:
                self.awaiting = None            # 기다렸는데 등록이 없다 (뜨다 말고 또 꺼졌다) — 아래에서 다시 켠다
        alive = same_process(created_at(pid), created)
        action = decide(quit_flag, not alive)
        if action == "restart" and shutting_down():
            log.info("PC 가 꺼지는 중 — 되살리지 않고 가디언도 끝냅니다")
            return "quit"
        if action == "restart":
            fast = self.last_revive is not None and now - self.last_revive < REVIVE_QUIET
            log.warning("울트론이 강제로 꺼졌습니다 (pid %d)%s", pid, " — 공격받는 중, 바로 되살림" if fast else "")
            closed = self.counter(cfg, info.get("root") or "") if cfg.get("guardian_counter") else []
            self.relaunch(info, closed, fast=fast)
            self.revived += 1
            self.last_revive = now
            self.awaiting = ((pid, created), now + REGISTER_WAIT)
            log.info("되살림 %d번째%s", self.revived, " (빠르게)" if fast else "")
        return action

    def run(self) -> None:
        if not acquire_lock(self.paths):
            log.info("다른 가디언이 이미 지키고 있습니다")
            return
        log.info("가디언 시작 — 울트론을 지킵니다")
        try:
            while True:
                try:
                    action = self.step(time.time())
                except Exception:
                    log.exception("가디언 확인 중 오류")
                    action = "wait"
                if action == "quit":
                    log.info("울트론이 정상 종료됨 — 가디언도 끝냅니다")
                    return
                if action == "off":
                    log.info("설정에서 가디언을 껐습니다")
                    return
                time.sleep(POLL)                # 다시 켠 직후에도 3초마다 본다 — 또 꺼지면 바로 알아챈다
        finally:
            release_lock(self.paths)


def _title_owners(titles: list[str]) -> dict[int, str]:
    """창 제목이 titles 중 하나와 정확히 같은 창의 (프로세스 번호 → 제목). Windows 전용."""
    want = {(t or "").strip() for t in titles if t}
    if not want or sys.platform != "win32":
        return {}
    import ctypes
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    found: dict[int, str] = {}

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def each(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if 0 < n < 80:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.strip() in want:
                pid = wt.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                found[int(pid.value)] = buf.value.strip()
        return True

    user32.EnumWindows(each, 0)
    return found


def run() -> int:
    from logging.handlers import RotatingFileHandler

    from .config import DATA_DIR, load_config
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[RotatingFileHandler(DATA_DIR / "guardian.log", maxBytes=300_000, backupCount=1,
                                                      encoding="utf-8")])
    Guard(DATA_DIR, load_config).run()
    return 0


if __name__ == "__main__":
    sys.exit(run())
