"""가디언 — 울트론을 지키는 감시 프로그램. 운영체제 없이 '언제 다시 켜고, 무엇을 닫는가'의 판단만 본다.

지켜야 하는 것: 사용자가 직접 끈 것은 되살리지 않는다, 강제로 꺼지면 다시 켠다, 너무 자주 죽으면 잠깐 쉰다,
같은 번호를 다른 프로그램이 받아도 속지 않는다, 가디언은 하나만 돈다,
'비전'은 사용자가 지목한 것(설치 폴더 · 창 제목)만 — 울트론 자신과 평범한 프로그램은 절대 닫지 않는다.
"""
import json
import os
import types

import pytest

from jarvis import guardian
from jarvis.guardian import (Guard, Paths, acquire_lock, decide, is_enemy, is_within, release_lock, same_process,
                             script_dir, too_broad)


# ---------------------------------------------------------------- 무엇을 할까
def test_decide_respects_user_quit_and_restarts_on_a_kill():
    assert decide(quit_flag=True, dead=True) == "quit"              # 사용자가 직접 껐다
    assert decide(quit_flag=False, dead=False) == "wait"            # 멀쩡하다
    assert decide(quit_flag=False, dead=True) == "restart"          # 누가 껐다 → 되살린다


def test_same_process_is_not_fooled_by_a_reused_number():
    assert same_process(1000.0, 1000.0)                             # 그 번호 · 그 시각 — 울트론 그대로
    assert same_process(1000.4, 1000.0)                             # 시각의 소수점 차이는 같은 것
    assert not same_process(None, 1000.0)                           # 그 번호의 프로그램이 없다 → 죽었다
    assert not same_process(5000.0, 1000.0)                         # 같은 번호를 다른 프로그램이 받았다 → 죽었다
    assert same_process(1000.0, None)                               # 예전 형식의 기록 — 번호만으로 본다


# ---------------------------------------------------------------- '비전' 고르기 (오인 방지)
def test_is_within_folder():
    assert is_within(r"C:\Vision\app\main.py", r"C:\Vision")
    assert is_within(r"c:\vision\APP\x.exe", r"C:\Vision")          # 대소문자 무시
    assert not is_within(r"C:\VisionX\main.py", r"C:\Vision")       # 이름만 비슷한 옆 폴더는 아니다
    assert not is_within(r"C:\Other\main.py", r"C:\Vision")
    assert is_within("C:/Vision/app/main.py", r"C:\Vision")         # / 로 적어도 같다
    assert not is_within(r"C:\Vision\..\Other\x.exe", r"C:\Vision")  # '..' 로 빠져나가면 아니다


def test_too_broad_folders_are_never_treated_as_vision():
    for broad in ("C:\\", "C:", r"C:\Windows", r"C:\Program Files", r"c:\program files (x86)",
                  r"C:\ProgramData", r"C:\Users", r"C:\Users\me", "D:\\"):
        assert too_broad(broad), broad
    for ok in (r"C:\Vision", r"C:\Users\me\vision", r"D:\Games\Vision", r"C:\Program Files\Vision"):
        assert not too_broad(ok), ok
    # 너무 넓은 폴더를 지목해도 그 안의 평범한 프로그램을 '비전'으로 보지 않는다
    assert not is_enemy("", r"C:\Windows\notepad.exe", [r"C:\Windows"], [], r"C:\Users\me\ultron")
    assert not is_enemy("", r"C:\Users\me\chrome\chrome.exe", [r"C:\Users\me"], [], r"C:\Users\me\ultron")


def test_is_enemy_only_matches_what_the_user_designated():
    own = r"C:\Users\me\ultron"
    installs = [r"C:\Users\me\vision"]
    titles = ["V.I.S.I.O.N"]
    assert is_enemy("", r"C:\Users\me\vision\main.py", installs, titles, own)              # 지목한 폴더
    assert is_enemy("V.I.S.I.O.N", r"C:\Python\pythonw.exe", installs, titles, own)        # 지목한 제목
    # 울트론 자신은 — 제목이 우연히 같아도 — 절대 고르지 않는다
    assert not is_enemy("V.I.S.I.O.N", r"C:\Users\me\ultron\main.py", installs, titles, own)
    assert not is_enemy("V.I.S.I.O.N 2", r"C:\x\y.exe", installs, titles, own)   # 제목은 정확히 같을 때만
    assert not is_enemy("메모장", r"C:\Windows\notepad.exe", installs, titles, own)      # 평범한 프로그램
    assert not is_enemy("무엇이든", r"C:\x\y.exe", [], [], own)                          # 지목한 게 없으면 아무것도
    # 울트론 폴더를 품은 폴더를 지목하면 그 안의 다른 프로그램까지 닫히므로 무시한다
    assert not is_enemy("", r"C:\Users\me\projects\game\game.exe", [r"C:\Users\me\projects"], [],
                        r"C:\Users\me\projects\ultron")
    assert not guardian.usable_install(r"C:\Users\me\ultron\sub", own)                 # 울트론 폴더 안
    assert guardian.usable_install(r"C:\Users\me\vision", own)


def test_script_dir_finds_where_a_python_program_lives():
    # 비전도 pythonw.exe 로 돌기 쉽다 — 실행 파일 위치(파이썬 설치 폴더)가 아니라 스크립트 폴더로 본다
    assert script_dir([r"C:\Python\pythonw.exe", r"C:\Users\me\vision\main.py"]) == r"C:\Users\me\vision"
    assert script_dir([r"C:\Python\python.exe", "-X", "utf8", r"D:\v\run.pyw"]) == r"D:\v"
    assert script_dir([r"C:\Python\python.exe", "-m", "jarvis.guardian"]) == ""             # 스크립트가 없다
    assert script_dir([r"C:\Program Files\Chrome\chrome.exe"]) == "" and script_dir([]) == ""


# ---------------------------------------------------------------- 한 번 확인 (step)
@pytest.fixture
def guard(tmp_path, monkeypatch):
    info = {"pid": 4242, "created": 1000.0, "root": str(tmp_path / "ultron"), "relaunch": ["py", "main.py"]}
    (tmp_path / "guardian.json").write_text(json.dumps(info), encoding="utf-8")
    g = Guard(tmp_path, load_cfg=lambda: dict(g.cfg))
    g.cfg = {"guardian": True, "guardian_counter": True,
             "enemy_installs": [str(tmp_path / "vision")], "enemy_titles": []}
    g.created, g.counted, g.launched = 1000.0, [], []               # 울트론이 켜진 시각 (None = 꺼졌다)
    g.shutdown = False
    monkeypatch.setattr(guardian, "created_at", lambda pid: g.created)
    monkeypatch.setattr(guardian, "shutting_down", lambda: g.shutdown)
    monkeypatch.setattr(Guard, "counter", lambda self, cfg, root: g.counted.append(root) or ["vision"])
    monkeypatch.setattr(Guard, "relaunch", lambda self, info, closed=None: g.launched.append((info, closed)))
    return g


def test_step_waits_while_ultron_is_alive(guard):
    assert guard.step(now=100) == "wait" and guard.launched == []


def test_step_does_nothing_when_the_user_quit(guard):
    guard.created = None
    Paths(guard.data_dir).quit.write_text("1", encoding="utf-8")
    assert guard.step(now=100) == "quit" and guard.launched == []    # 되살리지 않는다


def test_step_closes_the_enemy_then_relaunches_when_ultron_is_killed(guard):
    guard.created = None
    assert guard.step(now=100) == "restart"
    assert guard.counted == [str(guard.data_dir / "ultron")]
    assert len(guard.launched) == 1 and guard.launched[0][1] == ["vision"]   # 무엇을 닫았는지 되살린 울트론에 알린다
    assert guard.revived == 1 and guard.awaiting == (4242, 1000.0, 100 + guardian.START_TIMEOUT)


def test_step_does_not_revive_while_the_pc_is_shutting_down(guard):
    guard.created, guard.shutdown = None, True                      # Windows 가 프로그램을 차례로 끄는 중
    assert guard.step(now=100) == "quit" and guard.launched == [] and guard.counted == []


def test_step_treats_a_reused_number_as_dead(guard):
    guard.created = 9999.0                                          # 같은 번호를 다른 프로그램이 받았다
    assert guard.step(now=100) == "restart"


def test_step_skips_the_counter_when_it_is_off(guard):
    guard.created = None
    guard.cfg["guardian_counter"] = False
    guard.step(now=100)
    assert guard.counted == [] and guard.launched[0][1] == []        # 비전은 그냥 두고 울트론만 되살린다


def test_step_is_idle_when_the_guardian_setting_is_off(guard):
    guard.cfg["guardian"] = False
    guard.created = None
    assert guard.step(now=100) == "off" and guard.launched == []


def _register(guard, pid, created):
    """다시 켜진 울트론이 '나 떴다'를 남긴다 (main.py 의 guardian.register 흉내)."""
    info = {"pid": pid, "created": created, "root": str(guard.data_dir / "ultron"), "relaunch": ["py", "main.py"]}
    (guard.data_dir / "guardian.json").write_text(json.dumps(info), encoding="utf-8")


def test_step_revives_every_single_time_with_no_rest(guard, monkeypatch):
    alive = {4242: 1000.0}                                          # 살아 있는 울트론들: 번호 → 켜진 시각
    monkeypatch.setattr(guardian, "created_at", lambda pid: alive.get(pid))
    now = 100.0
    for n in range(1, 21):                                          # 20번 연달아 꺼도
        alive.clear()                                               # 비전이 울트론을 껐다
        assert guard.step(now) == "restart"
        assert len(guard.launched) == n                             # 매번 되살린다 — 쉬지 않는다
        new_pid = 5000 + n                                          # 되살아난 울트론이 곧바로 등록한다
        alive[new_pid] = now + 1
        _register(guard, new_pid, now + 1)
        now += 3
        assert guard.step(now) == "wait"                            # 새 울트론을 지키는 중
        now += 3
    assert guard.revived == 20


def test_step_never_launches_twice_while_the_new_ultron_is_still_starting(guard):
    guard.created = None                                            # 꺼졌다
    assert guard.step(now=100) == "restart"
    for t in (103, 106, 110, 120, 129):                             # 새 울트론이 아직 등록 전 — 또 켜면 울트론이 두 개가 된다
        assert guard.step(now=t) == "wait"
    assert len(guard.launched) == 1
    assert guard.step(now=100 + guardian.START_TIMEOUT + 1) == "restart"    # 30초가 지나도 안 떴다 — 다시 켠다
    assert len(guard.launched) == 2
    Paths(guard.data_dir).quit.write_text("1", encoding="utf-8")
    assert guard.step(now=140) == "quit"                            # 기다리는 중이어도 사용자가 끄면 끝낸다


# ---------------------------------------------------------------- 되살릴 때의 명령 · 비전 닫기
def test_relaunch_tells_the_new_ultron_it_was_revived(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(guardian, "launch_detached", lambda cmd, cwd=None: calls.append((cmd, cwd)))
    g = Guard(tmp_path, load_cfg=dict)
    g.relaunch({"relaunch": ["pythonw", "main.py"], "root": str(tmp_path)}, ["vision"])
    g.relaunch({"relaunch": ["pythonw", "main.py"], "root": str(tmp_path)})
    assert calls[0] == (["pythonw", "main.py", "--revived", "--closed", "vision"], str(tmp_path))
    assert calls[1][0] == ["pythonw", "main.py", "--revived"]       # 가디언의 자식이 아닌 독립 프로세스로 띄운다
    g.relaunch({})                                                   # 다시 켜는 법을 모르면 아무것도 하지 않는다
    assert len(calls) == 2


def test_launch_detached_goes_through_a_short_lived_bridge(tmp_path, monkeypatch):
    """작업 관리자에서 울트론을 '작업 끝내기' 하면 그 자식 프로세스까지 끝난다 — 가디언 · 되살린 울트론은 누구의 자식도 아니어야 한다."""
    calls = []
    monkeypatch.setattr(guardian.sys, "platform", "win32")
    monkeypatch.setattr(guardian.subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))
    guardian.launch_detached(["pythonw", "main.py", "--revived"], str(tmp_path))
    args, kw = calls[0]
    assert args[1] == "-c" and args[3] == str(tmp_path) and args[4:] == ["pythonw", "main.py", "--revived"]
    assert kw["creationflags"] & guardian.BREAKAWAY and kw["creationflags"] & guardian.NO_WINDOW
    calls.clear()

    def refuse_breakaway(args, **kw):                                # 작업 객체가 빠져나가기를 막으면 그냥 띄운다
        if kw["creationflags"] & guardian.BREAKAWAY:
            raise OSError(5, "Access is denied")
        calls.append((args, kw))
    monkeypatch.setattr(guardian.subprocess, "Popen", refuse_breakaway)
    guardian.launch_detached(["x"], None)
    assert len(calls) == 1 and not calls[0][1]["creationflags"] & guardian.BREAKAWAY
    assert "start_new_session" in guardian._BRIDGE and "0x01000000" in guardian._BRIDGE   # 다리도 같은 방법으로


def test_bridge_really_starts_an_orphan_process(tmp_path):
    """(실제로) 다리를 거쳐 띄운 프로세스는 띄운 쪽의 자식이 아니다."""
    import subprocess
    import sys
    import time
    import psutil
    out = tmp_path / "ppid.txt"
    code = f"import os; open(r'{out}', 'w').write(str(os.getppid()))"
    guardian.launch_detached([sys.executable, "-c", code], str(tmp_path))
    for _ in range(50):
        if out.exists() and out.read_text():
            break
        time.sleep(0.1)
    assert out.read_text() and int(out.read_text()) != os.getpid()
    assert int(out.read_text()) not in [c.pid for c in psutil.Process().children(recursive=True) if c.status() != "zombie"]


def test_counter_closes_only_designated_programs(tmp_path, monkeypatch):
    killed = []

    class Proc:
        def __init__(self, pid, exe, cmdline):
            self.pid, self.info = pid, {"pid": pid, "exe": exe, "cmdline": cmdline}

        def kill(self):
            killed.append(self.pid)

        def wait(self, t):
            pass

    procs = [Proc(1, r"C:\Python\pythonw.exe", [r"C:\Python\pythonw.exe", r"C:\Users\me\ultron\main.py"]),   # 울트론
             Proc(2, r"C:\Python\pythonw.exe", [r"C:\Python\pythonw.exe", r"C:\Users\me\vision\main.py"]),   # 비전
             Proc(3, r"C:\Windows\notepad.exe", [r"C:\Windows\notepad.exe"]),                               # 메모장
             Proc(4, r"C:\Users\me\vision\v.exe", [r"C:\Users\me\vision\v.exe"])]                         # 비전 (exe)
    monkeypatch.setitem(__import__("sys").modules, "psutil", types.SimpleNamespace(process_iter=lambda attrs: procs))
    g = Guard(tmp_path, load_cfg=dict)
    cfg = {"enemy_installs": [r"C:\Users\me\vision"], "enemy_titles": []}
    closed = g.counter(cfg, r"C:\Users\me\ultron")
    assert killed == [2, 4] and closed == ["vision", "v.exe"]          # 울트론 · 메모장은 건드리지 않는다
    killed.clear()
    assert g.counter({"enemy_installs": [], "enemy_titles": []}, r"C:\Users\me\ultron") == [] and killed == []


# ---------------------------------------------------------------- 가디언은 하나만
def test_only_one_guardian_holds_the_lock(tmp_path, monkeypatch):
    p = Paths(tmp_path)
    alive = {111}
    monkeypatch.setattr(guardian, "is_guardian", lambda pid: pid in alive)
    assert acquire_lock(p, me=111)
    assert not acquire_lock(p, me=222)                               # 111 이 살아서 지키고 있다
    alive.clear()                                                    # 111 이 사라졌다 (버려진 잠금)
    assert acquire_lock(p, me=222) and p.lock.read_text() == "222"
    release_lock(p, me=111)                                          # 남의 잠금은 풀지 않는다
    assert p.lock.exists()
    release_lock(p, me=222)
    assert not p.lock.exists()


def test_an_empty_lock_means_another_guardian_is_starting(tmp_path, monkeypatch):
    p = Paths(tmp_path)
    monkeypatch.setattr(guardian, "is_guardian", lambda pid: False)
    p.lock.write_text("", encoding="utf-8")                          # 다른 가디언이 막 자리를 잡는 중
    assert not acquire_lock(p, me=5)
    old = p.lock.stat().st_mtime - 60
    os.utime(p.lock, (old, old))                                     # 그런데 오래됐다 → 버려진 것
    assert acquire_lock(p, me=5)


# ---------------------------------------------------------------- 울트론 ↔ 가디언 파일
def test_register_clears_a_stale_quit_flag_and_records_who_to_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(guardian, "created_at", lambda pid: 1234.5)
    p = Paths(tmp_path)
    guardian.mark_quit(tmp_path)
    assert p.quit.exists()
    guardian.register(tmp_path, tmp_path / "ultron")                 # 새로 켜졌다
    assert not p.quit.exists()                                       # 지난번 '직접 껐음' 표시를 지운다
    info = guardian.read_info(p)
    assert info["pid"] == os.getpid() and info["created"] == 1234.5
    assert info["relaunch"][-1].endswith("main.py") and info["root"].endswith("ultron")


def test_spawn_is_skipped_when_a_guardian_already_runs(tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(guardian.sys, "platform", "win32")
    monkeypatch.setattr(guardian, "launch_detached", lambda cmd, cwd=None: launched.append((cmd, cwd)))
    monkeypatch.setattr(guardian, "running", lambda d: True)
    assert guardian.spawn(tmp_path) is False and launched == []
    monkeypatch.setattr(guardian, "running", lambda d: False)
    assert guardian.spawn(tmp_path) is True and len(launched) == 1
    assert launched[0][0][1:] == ["-m", "jarvis.guardian"] and launched[0][1] == str(tmp_path.parent)   # 울트론의 자식이 아니게


def test_guardian_checks_every_second():
    assert guardian.POLL <= 1.0                                       # 꺼진 지 1초 안에 알아챈다
