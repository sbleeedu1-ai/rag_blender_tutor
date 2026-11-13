"""설정 값 읽기 자체 시험(HISTORY [270], 기본 테스트 밖): Blender 5.2를 창 있게(화면 밖 자리에) 띄워 read_settings를 부르고 줄 수·시간을 낸다.

실행(프로젝트 폴더): .venv\\Scripts\\python addon\\settings_selftest.py
공장값 표가 '창 있는 Blender + 공장 설정 + 빈 사용자 폴더'로 만들어져(h12_view_run.py) 같은 조건으로 띄운다. 돈이 들지 않는다.
보는 것: ① 공장 장면 ② Blender에 딸린 Sculpting 템플릿 사본. 장면마다 늘 보내는 줄 수, 까닭별 칸 수, 분야별 줄 수,
가장 큰 분야 3개를 고를 때의 줄 수, 읽기 시간(3번). 공장 장면에서 '공장값과 다름'은 0에 가까워야 한다(규칙 13 시험과 같은 조건).
결과는 표준 출력과 임시 폴더의 JSON으로 낸다.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

if "bpy" not in sys.modules:  # 1) 보통 파이썬: 빈 사용자 폴더를 만들고 장면마다 Blender를 띄운다
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(PROJECT))
    from blender_tutor.paths import default_blender

    blender = default_blender()
    # Blender에 딸린 파일 자리: Windows는 실행 파일 옆 5.2/, Mac은 앱 묶음의 Contents/Resources/5.2/
    resources = Path(blender).parent.parent / "Resources" if sys.platform == "darwin" else Path(blender).parent
    template = resources / "5.2" / "scripts" / "startup" / "bl_app_templates_system" / "Sculpting" / "startup.blend"
    box = Path(tempfile.mkdtemp(prefix="settings_selftest_"))
    env = dict(os.environ)
    for name, folder in {"BLENDER_USER_CONFIG": "c", "BLENDER_USER_SCRIPTS": "s", "BLENDER_USER_DATAFILES": "d", "BLENDER_USER_EXTENSIONS": "e", "TEMP": "t", "TMP": "t", "TMPDIR": "t"}.items():
        (box / folder).mkdir(exist_ok=True)
        env[name] = str(box / folder)
    subprocess.run([blender, "-b", "--factory-startup", "--python-expr", "import bpy; bpy.ops.wm.save_userpref()"], env=env, cwd=str(box), capture_output=True, timeout=120, check=True)
    copy = box / "Sculpting_사본.blend"
    shutil.copy2(template, copy)
    failed = False
    for name, blend in (("공장", None), ("템플릿_Sculpting", copy)):
        out = box / f"{name}.json"
        command = [blender, "--no-window-focus", "--window-geometry", os.environ.get("STATE_WINDOW_X", "-1920"), "0", "1920", "1000", "--factory-startup"]
        if blend:
            command.append(str(blend))
        command += ["--python", __file__, "--", str(out), str(PROJECT / "state_tables")]
        started = time.monotonic()
        subprocess.run(command, env=dict(env, PYTHONUTF8="1"), cwd=str(box), timeout=600, capture_output=True)
        if not out.exists():
            print(f"{name}: 결과 없음(Blender {time.monotonic() - started:.0f}초)")
            failed = True
            continue
        result = json.loads(out.read_text(encoding="utf-8"))
        print(f"== {name} (Blender {time.monotonic() - started:.0f}초)")
        print(json.dumps({k: v for k, v in result.items() if k != "보기"}, ensure_ascii=False, indent=1))
    print(f"결과 폴더: {box}")
    sys.exit(1 if failed else 0)

# 2) Blender 안: 창이 뜬 뒤 읽는다
import importlib.util  # noqa: E402

import bpy  # noqa: E402

OUT, TABLES = Path(sys.argv[-2]), Path(sys.argv[-1])
spec = importlib.util.spec_from_file_location("settings_reader", HERE / "blender_tutor_addon" / "settings_reader.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def task():
    try:
        tables = reader.load_tables(TABLES)
        times, result = [], None
        for _ in range(3):
            started = time.perf_counter()
            result = reader.read_settings(bpy.context, tables)
            times.append(round((time.perf_counter() - started) * 1000))
        counts = dict(reader.LAST_COUNTS)
        fields = {code: len(lines) for code, lines in result["fields"].items()}
        top3 = sorted(fields, key=fields.get, reverse=True)[:3]
        union = dict.fromkeys(result["always"] + result["situation"] + result["computed"])
        for code in top3:
            union.update(dict.fromkeys(result["fields"][code]))
        target = bpy.context.view_layer.objects.active
        OUT.write_text(json.dumps({
            "활성": f"{target.name if target else None}/{target.mode if target else None}",
            "읽기 ms": times, "늘 보냄 줄": len(result["always"]), "1-a 초안 줄": len(result["situation"]), "2 초안 줄": len(result["computed"]),
            "까닭별 칸": counts, "분야 32종 있음": len(fields) == 32, "분야별 줄": fields,
            "가장 큰 분야 3개": top3, "그때 합친 줄": len(union),
            "보기": {"늘 보냄 앞 40줄": result["always"][:40], "MO 앞 10줄": result["fields"].get("MO", [])[:10]},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT.with_suffix(".lines.json")).write_text(json.dumps(result, ensure_ascii=False, indent=0), encoding="utf-8")
    except Exception:
        import traceback

        OUT.with_suffix(".오류.txt").write_text(traceback.format_exc(), encoding="utf-8")
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(task, first_interval=3.0)
