# 조사 결과: 도우미 창을 더 매끈하게 만들 UI 도구

근거: `docs/adr/0001-채팅은-Blender-위-도우미-창으로.md`, 시제품 `prototype/01-addon-roundtrip` 브랜치의 `run_overlay.py` · 조사일 2026-10-20 · 1차 출처(공식 문서, PyPI, 소스 저장소, 공식 이슈 트래커)만 사용, 측정은 강의실 PC(i7-4770, GTX 950, Windows 11 25H2 빌드 26200, Python 3.12)에서 직접 함

## 요약

1. **바라는 모양(반투명 유리 창, 둥근 카드, 알약 입력칸, 부드러운 움직임)에 가장 가까운 것은 PySide6(Qt) + QML이다.** 테두리 없는 창, 둥근 카드, 애니메이션, 한글 조합 글자 칸 안 표시가 모두 됐고, 창 번호(HWND)도 바로 얻는다. 대신 설치 용량이 약 219MB로 크고, 도우미 창 코드는 새로 써야 한다(Windows 처리 코드는 그대로 쓴다).
2. **"진짜 배경 블러"에는 큰 함정이 있다.** Windows 11의 공식 방법(Acrylic, `DWMWA_SYSTEMBACKDROP_TYPE`)은 **창이 비활성일 때 단색으로 바뀐다**. 도우미 창은 Blender를 쓰는 동안 늘 비활성이므로 대부분의 시간에 회색 판으로 보인다(직접 찍어 확인). 비활성일 때도 흐림이 남는 것은 **문서가 없는 Windows 내부 함수**뿐이다. 그래서 "흐린 유리"는 ① 문서 없는 함수로 진짜 블러, ② 블러 없이 어두운 반투명 판으로 흉내, 둘 중에서 골라야 한다.
3. **한글 입력기(IME)는 후보마다 차이가 컸다.** tkinter·CustomTkinter는 한글은 되지만 조합 중 글자가 칸 안이 아니라 커서 옆 작은 Windows 상자에 뜬다. Qt(위젯·QML)와 웹 화면(pywebview)은 조합 글자가 칸 안에 바로 보인다. **Dear PyGui는 "안녕하세요"가 `??????????`로 들어가 탈락**, **Flet(Flutter)은 Windows에서 한글 음절이 빠지는 버그가 아직 열려 있어 탈락**이다.
4. **F10에서 입력 가능 0.1초는 모든 후보가 넉넉하다.** 숨겨 둔 창을 앞으로 꺼내는 데 강의실 PC에서 11-87ms였다. 다만 첫 실행 시간과 메모리는 차이가 크다(tkinter 0.12초·33MB, Qt 0.28-0.77초·60MB, pywebview 1.4-2.1초·본체 99MB + 웹 엔진 프로세스 6개).
5. **추천 순위: ① PySide6 + QML, ② pywebview(HTML/CSS), ③ CustomTkinter(지금 코드 유지, 모양 목표는 일부만).** 작업 표시줄·Alt+Tab에서 빼고 트레이 아이콘만 두는 구성은 Qt가 내장 기능(`Qt.Tool`, `QSystemTrayIcon`)으로 바로 되고, tkinter는 도구 창은 저절로 되지만 트레이에 3년째 릴리스 없는 pystray가 필요하며, pywebview는 둘 다 내장 기능이 없다. Windows 11이 새 트레이 아이콘을 숨김 영역(^)에 넣는 것은 프로그램이 바꿀 수 없다(사용자만 바꿈).

## 먼저: 지금 시제품 구조와 바꿀 범위

시제품 `run_overlay.py`(약 230줄)는 세 덩어리다.

| 덩어리 | 하는 일 | 도구를 바꾸면 |
|---|---|---|
| 창·위젯(약 40줄) | tkinter 창, 대화 칸(`Text`), 입력칸(`Entry`), 글 붙이기 | **새로 씀** |
| Windows 처리(약 90줄) | `ctypes`(파이썬에서 Windows 함수를 부르는 도구)로 `SetWindowPos`, `SetForegroundWindow`, `ShowWindow`, Blender 최소화 감지 | **그대로 씀**. 창 번호(HWND, Windows가 창마다 붙이는 번호)만 얻으면 됨 |
| 신호 받기(약 20줄) | 애드온이 보낸 F10 신호를 HTTP로 받아 줄(queue)에 넣음 | **그대로 씀**. 줄에서 꺼내는 부분만 도구에 맞게 |

즉 어떤 도구로 가든 "Blender가 앞일 때만 맨 위"와 "Blender 최소화 시 숨김"은 HWND만 있으면 지금 코드 그대로 된다.

## 이번에 직접 해 본 것

모두 저장소 밖 임시 폴더에서 했고 커밋하지 않았다. 비용 드는 호출은 없다.

- **설치·용량:** 가상 환경에 각 후보를 pip로 설치하고 폴더 크기를 셈.
- **속도·메모리:** 후보마다 같은 시나리오를 3번씩 돌림. "프로세스 시작 → 숨긴 창 준비 완료", "다른 스레드에서 F10 신호 → 창이 보이고 앞으로 옴", HWND 얻기, 메모리(RSS, 프로세스가 차지한 실제 메모리).
- **한글 입력:** 창을 띄우고 입력칸에 초점을 준 뒤 한글 모드로 바꾸고 `dkssudgktpdy`(= 안녕하세요) + Space를 키보드 신호로 보냄. 조합 중에 창 그림을 찍고, 끝에 칸의 값을 읽음.
  - 깨끗하게 끝난 것은 tkinter(`'안녕하세요 '`, 정답)와 Dear PyGui(`'?????????? '`, 오답) 두 번이다.
  - 다른 후보는 시험 중 사용자가 VS Code에서 작업하면서 초점이 바뀌어 중간에 멈췄고, 사용자 입력이 섞여 **값은 믿지 않는다**. 대신 그 전에 찍힌 "조합 중 그림"으로 조합 글자가 칸 안에 보이는지만 판정했다. 사용자 작업을 방해하므로 자동 입력 시험은 거기서 그만뒀다.
- **유리 창 모양:** 포커스를 빼앗지 않게 비활성으로 띄우고 그림을 찍음(= Blender를 쓰는 동안 실제 모습).
- **테두리 없는 창·트레이:** 창 성질(작업 표시줄·Alt+Tab에 나오는지, 최소화되는지)을 Windows 함수로 읽고, 트레이 아이콘이 만들어지는지 봄. 트레이 클릭은 손으로 해야 해서 하지 않았다.

### 측정 결과(강의실 PC, 3회)

| 후보 | 첫 실행 → 숨긴 창 준비 | F10 신호 → 창 보임 | 메모리 | 설치 용량(대략) |
|---|---|---|---|---|
| tkinter(파이썬 기본) | 121-548ms(첫 회만 느림) | 22-27ms | 32-33MB | 0(파이썬에 포함, Tcl/Tk 약 9MB) |
| CustomTkinter 6.0.0 | 315-537ms | 28-39ms | 43-44MB | 3MB(+darkdetect) |
| ttkbootstrap 2.2.3 | 362-450ms | 16-28ms | 47-49MB | 4MB + Pillow 16MB |
| sv-ttk 2.6.1 | 232-324ms | 11-34ms | 33-36MB | 1MB 미만 |
| PySide6 6.12.0(위젯) | 279-773ms | 16-54ms | 60-62MB | 약 219MB(PySide6-Essentials 215MB + shiboken6 4MB) |
| pywebview 6.2.1 | 1,379-2,087ms | 57-87ms | 본체 99MB + 웹 엔진 자식 프로세스 6개(합 약 305MB, 공유 메모리 중복 포함이라 실제보다 크게 나옴) | 5MB(+pythonnet). 웹 엔진은 Windows 11에 들어 있는 WebView2 런타임 사용 |
| Dear PyGui 2.3.1 | 286-299ms | 22-33ms | 56-59MB | 7MB |
| Flet 1.0.4 | 측정 안 함 | 측정 안 함 | 측정 안 함 | 파이썬 쪽 1MB 미만, 화면 프로그램은 따로 받음(확인 필요) |

- 표의 "창 보임"은 창이 화면에 나타난 시간이다. 몇 번은 "앞으로 오기"가 실패했는데, Windows가 뒤에 있는 프로그램이 스스로 앞으로 나오는 것을 막기 때문이다. 실제 앱에서는 Blender 애드온이 `AllowSetForegroundWindow`로 허락해 주므로(시제품에서 확인) 도구 탓이 아니다.
- 모든 후보가 0.1초 목표 안이다. 첫 실행이 느린 것(pywebview 약 1.4-2초)은 Blender를 켤 때 미리 띄워 두므로 사용자가 느끼는 F10 속도와는 관계없다.

## 후보별 상세

### A-1. tkinter 그대로(비교 기준)

- **한글:** 된다. 자동 시험에서 `안녕하세요 `가 정확히 들어갔다. 다만 조합 중 글자는 칸 안이 아니라 **커서 옆 작은 Windows 기본 상자**에 작게 뜬다. Tk 소스가 완성된 글자(`GCS_RESULTSTR`)만 받고, 조합 중 글자는 Windows 기본 조합 창을 커서 위치에 놓는 방식이기 때문이다. 출처: [Tk 8.6 `win/tkWinX.c`의 `HandleIMEComposition`, `ImmSetCompositionWindow`](https://github.com/tcltk/tk/blob/core-8-6-branch/win/tkWinX.c)
- **HWND:** `int(root.wm_frame(), 16)`로 얻는다(시제품에서 이미 사용).
- **스트리밍·줄바꿈·링크:** `Text`에 `insert("end", 글자)`로 이어 붙이기, `wrap="word"`로 자동 줄바꿈, `tag_bind`로 글 일부에 클릭 동작을 붙여 링크를 연다. 출처: [Tk text 위젯 설명서](https://www.tcl-lang.org/man/tcl8.6/TkCmd/text.htm)
- **유리 창:** 안 된다. Tk는 픽셀마다 투명도를 줄 수 없어 둥근 창 모서리, 반투명 카드가 안 되고, 창 전체 투명도(`-alpha`)는 글자까지 흐려진다.
- **테두리 없는 창:** `overrideredirect(True)`로 테두리를 없애면 Windows가 이 창을 **도구 창(WS_EX_TOOLWINDOW)**으로 만든다. 직접 확인한 결과 작업 표시줄 아이콘과 Alt+Tab에서 사라진다. 이번에 정한 구성(작업 표시줄 없이 트레이만)에는 오히려 맞다. 최소화(`iconify()`)는 `can't iconify "." : override-redirect flag is set` 오류가 나지만, `_` 버튼을 두지 않기로 했으므로 문제가 아니다. 트레이 아이콘은 내장 기능이 없어 pystray가 필요하다. 도구 창 성질 출처: [Microsoft, Extended Window Styles](https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles)
- **라이선스·유지:** 파이썬 기본 포함. 이 PC의 Python 3.12는 Tk 8.6.15.

### A-2. CustomTkinter(tkinter 겉모습 바꾸기)

- **무엇:** tkinter 위젯을 둥근 모서리·어두운 테마로 다시 그려 주는 꾸밈 도구.
- **한글:** tkinter와 같다. `CTkEntry`는 안에 `tkinter.Entry`를, `CTkTextbox`는 `tkinter.Text`를 그대로 쓴다. 출처: [ctk_entry.py](https://github.com/TomSchimansky/CustomTkinter/blob/master/customtkinter/windows/widgets/ctk_entry.py), [ctk_textbox.py](https://github.com/TomSchimansky/CustomTkinter/blob/master/customtkinter/windows/widgets/ctk_textbox.py). 그래서 조합 글자 표시도 tkinter처럼 작은 상자다. 이 저장소 이슈에서 한글·IME 관련 보고는 찾지 못했다.
- **모양:** 창 **안의** 카드·알약 입력칸(`corner_radius`)·어두운 테마는 쉽게 된다. 창 자체의 블러, 둥근 창 모서리, 부드러운 애니메이션은 tkinter 한계를 그대로 물려받는다.
- **지금 코드 재사용:** 가장 많다. `tk.Text` → `CTkTextbox`, `tk.Entry` → `CTkEntry` 정도로 바꾸면 된다.
- **라이선스·유지:** 최신 6.0.0(PyPI 2026-06-24). 저장소의 LICENSE 파일은 MIT인데 PyPI 정보에는 "CC0"으로 적혀 있어 서로 다르다(둘 다 공개 저장소에 문제없는 자유 라이선스). Python 3.7+. 출처: [PyPI](https://pypi.org/project/customtkinter/), [저장소](https://github.com/TomSchimansky/CustomTkinter)

### A-3. ttkbootstrap, sv-ttk(Sun Valley)

- **무엇:** tkinter의 `ttk` 위젯에 테마를 씌우는 도구. sv-ttk는 Windows 11 느낌의 테마.
- **한글·HWND·스트리밍:** tkinter와 같다(같은 Tk 위젯 위의 테마일 뿐).
- **모양:** 위젯 색·모양만 바뀐다. 둥근 카드, 블러, 애니메이션은 CustomTkinter보다도 적다. 대화 칸(`Text`)은 ttk 위젯이 아니라 테마가 덜 먹는다.
- **유지:** ttkbootstrap 2.2.3(2026-09-12), MIT, Python 3.10+. sv-ttk 2.6.1(2025-06-08, 1년 넘게 새 릴리스 없음), MIT, Python 3.9+. 출처: [ttkbootstrap PyPI](https://pypi.org/project/ttkbootstrap/), [sv-ttk PyPI](https://pypi.org/project/sv-ttk/), [sv-ttk 저장소](https://github.com/rdbende/Sun-Valley-ttk-theme)
- **판단:** 바라는 모양과 거리가 멀어 추천에서 뺐다.

### A-4. pywinstyles(tkinter에 Windows 유리 효과 입히기)

- tkinter 창에 Acrylic·Mica 등을 입혀 주는 작은 도구. 소스를 보면 문서 없는 Windows 함수 `SetWindowCompositionAttribute`와 문서 없는 속성 번호(1029)를 쓴다. 마지막 릴리스 1.8이 2024-04-22라 2년 넘게 멈춰 있다. 출처: [PyPI](https://pypi.org/project/pywinstyles/)
- 직접 입혀 보니 비활성 상태에서는 **회색 단색**이었고 제목 표시줄도 그대로였다(아래 "유리 창 시험" 참고). tkinter에서 진짜 유리 창을 만드는 길로는 부족하다.

### B-1. PySide6(Qt) — 위젯 방식과 QML 방식

- **무엇:** Qt(오래된 C++ 화면 도구)의 공식 파이썬 판. 위젯 방식(전통적인 칸·버튼)과 QML 방식(애니메이션에 강한 선언형 화면 언어)이 한 꾸러미(`PySide6-Essentials`)에 다 들어 있다.
- **한글:** 위젯(`QLineEdit`)과 QML(`TextField`) 모두 **조합 중 글자가 칸 안에 바로 보였다**(위젯은 반전 표시). 자동 시험의 최종 값은 사용자 입력이 섞여 판정하지 못했다(확인 필요). Qt 공식 이슈 트래커에서 찾은 Windows 한국어 IME 관련 보고:
  - [QTBUG-145234](https://qt-project.atlassian.net/browse/QTBUG-145234): 한국어 지역 설정 Windows에서 한글이 네모로 보임 → **6.12.0에서 고침**(최신 PySide6가 6.12.0).
  - [QTBUG-58300](https://qt-project.atlassian.net/browse/QTBUG-58300): 조합 중 Ctrl 단축키를 누르면 조합 글자가 사라짐(Qt 5 시절 보고).
  - [QTBUG-107650](https://qt-project.atlassian.net/browse/QTBUG-107650): 한국어 IME 이모지 창으로 넣은 이모지가 사라짐.
  - [QTBUG-50451](https://qt-project.atlassian.net/browse/QTBUG-50451): 이미 쓴 글자를 다시 한자로 바꾸는 기능이 안 됨("Won't Do"로 닫힘).
  - 일반 한글 입력이 깨진다는 열린 보고는 찾지 못했다.
- **HWND:** `int(widget.winId())`. 숨긴 채로도 얻었다.
- **F10 속도:** 창 보임 16-54ms, 첫 실행 0.28-0.77초, 메모리 약 60MB(위젯 기준. QML은 측정 안 함, 확인 필요).
- **스트리밍·줄바꿈·링크:** 위젯은 `QTextBrowser`에 글을 이어 붙이고, `openExternalLinks`를 켜면 링크 클릭 시 브라우저가 열린다. 출처: [QTextBrowser](https://doc.qt.io/qt-6/qtextbrowser.html). QML은 `Text`/`TextEdit`의 자동 줄바꿈과 `onLinkActivated`로 같은 일을 한다.
- **유리 창·모양:** 테두리 없는 창(`FramelessWindowHint`) + 투명 배경(`WA_TranslucentBackground`) 위에 둥근 카드, 알약 입력칸, 흰 굵은 답 글씨, 회색 작은 질문 글씨를 직접 그려 봤고 잘 나왔다. 애니메이션은 QML이 가장 쉽다(그래픽 카드로 그림). 블러는 아래 "유리 창 시험" 참고.
- **테두리 없는 창·트레이:** `Qt.Tool`을 함께 주면 작업 표시줄·Alt+Tab에서 빠지는 도구 창이 되고, 트레이 아이콘은 내장 `QSystemTrayIcon`으로 바로 만들어졌다(직접 확인). 가장자리 끌어 크기 조절과 창 끌어 옮기기는 Qt가 Windows 기본 동작을 불러 주는 `startSystemResize()`/`startSystemMove()`가 있다. 출처: [QWindow 설명서](https://doc.qt.io/qt-6/qwindow.html)
- **라이선스:** LGPL-3.0 / GPL-2.0 / GPL-3.0 중 선택. pip로 받은 PySide6를 그대로 쓰는 공개 저장소라면 LGPL 조건(라이브러리를 고치면 그 부분 공개, 사용자가 라이브러리를 바꿀 수 있게 둠)을 지키기 쉽다. 출처: [Qt for Python 라이선스](https://doc.qt.io/qtforpython-6/licenses.html)
- **유지:** 6.12.0(2026-10-08), Python 3.10-3.15. 출처: [PyPI](https://pypi.org/project/PySide6/)
- **비슷한 것:** PyQt6는 GPL만이라 공개 저장소에서도 이 프로젝트 전체가 GPL이 돼야 한다. PySide6가 낫다.

### B-2. pywebview(HTML/CSS 화면)

- **무엇:** 파이썬 창 안에 Windows 내장 웹 엔진(WebView2, Edge와 같은 엔진)을 띄워 화면을 HTML/CSS로 만드는 도구.
- **한글:** 조합 중 글자가 칸 안에 바로 보였다(Edge와 같은 방식). 공식 이슈 트래커의 관련 보고:
  - [WebView2Feedback #5475](https://github.com/MicrosoftEdge/WebView2Feedback/issues/5475): 한글 조합 중에 입력칸 밖을 클릭하면 WebView2가 멈추며 꺼짐(.NET MAUI 앱 보고). 고쳐졌다는 말 없이 보고자가 2026-10-08에 닫음.
  - [WebView2Feedback #5675](https://github.com/MicrosoftEdge/WebView2Feedback/issues/5675): 창 크기를 바꾼 뒤 한글 조합 창이 화면 왼쪽 위로 튐(열림).
  - 우리 앱에서 이 두 문제가 나는지는 확인하지 못했다(확인 필요).
- **HWND:** `int(window.native.Handle.ToInt64())`로 얻었다. `window.native`는 Windows에서 WinForms 창이다. 출처: [pywebview API](https://pywebview.flowrl.com/api/)
- **F10 속도:** 창 보임 57-87ms로 후보 중 가장 느리지만 목표 안. 첫 실행 1.4-2.1초, 메모리가 가장 크다.
- **스트리밍·줄바꿈·링크:** `evaluate_js`로 글을 이어 붙이면 되고, 줄바꿈은 CSS가 알아서 한다(한국어는 `word-break: keep-all`로 단어 중간 끊김 방지). 링크는 기본 설정 `OPEN_EXTERNAL_LINKS_IN_BROWSER = True`로 브라우저에서 열린다(설치된 소스 `webview/__init__.py`에서 확인).
- **유리 창·모양:** 둥근 카드·알약 입력칸·애니메이션은 CSS로 가장 쉽게 만든다. 그러나 **창 뒤(바탕화면·Blender)를 비치게 하는 투명 창은 공식 문서에 "Windows에서는 지원하지 않음"**이라고 적혀 있다. 소스에는 WebView2 배경을 투명으로 두는 코드가 있어 문서와 다르다(확인 필요). CSS의 `backdrop-filter` 블러는 페이지 안 내용만 흐리게 한다.
- **테두리 없는 창·트레이:** `frameless=True`로 테두리를 없애도 작업 표시줄 아이콘이 남는다. 작업 표시줄에서 빼는 옵션은 없고, WinForms 창의 `ShowInTaskbar = False`로 빠졌지만 그때 HWND가 새로 바뀐다(직접 확인). 트레이 기능도 없다. 끌어 옮기기는 `easy_drag`나 `pywebview-drag-region` 표시로 된다. 다만 테두리 없는 창은 WinForms의 "테두리 없음" 모드라 **가장자리 끌어 크기 조절이 안 된다**(창 성질에 크기 조절 테두리 없음 확인). 직접 만든 손잡이 + `window.resize()`로 만들어야 한다.
- **라이선스·유지:** BSD-3-Clause, 6.2.1(2026-04-15), 저장소는 2026-10-19까지 활발. Windows에서는 pythonnet(MIT, Python 3.11-3.15)이 필요. 출처: [PyPI](https://pypi.org/project/pywebview/), [저장소](https://github.com/r0x0r/pywebview)

### B-3. Flet(Flutter 화면) — 탈락

- **한글:** Flet이 쓰는 Flutter의 Windows 판에 한글 버그가 열려 있다. [flutter #189491](https://github.com/flutter/flutter/issues/189491)(2026-07 보고, 열림): 빨리 치면 "동해물과"가 "동물과"가 되는 음절 빠짐. [flutter #191196](https://github.com/flutter/flutter/issues/191196)(열림): 조합 중에 다른 칸으로 가면 조합 글자가 새 칸으로 샘. 초보자가 질문을 빨리 치는 도구에서 글자가 빠지는 것은 치명적이다.
- **HWND:** 창 속성 문서에 창 번호를 얻는 방법이 없다(`always_on_top`, `to_front`, `skip_task_bar`, `frameless`, `start_dragging`, `start_resizing`은 있음). 화면이 파이썬과 다른 프로그램에서 돌아 창 제목으로 찾아야 한다. 출처: [Flet Window 문서](https://flet.dev/docs/types/window/)
- **유리 창:** `bgcolor`를 투명으로 하면 창 뒤가 비치지만 블러는 없다(문서 기준).
- **라이선스·유지:** Apache-2.0, 1.0.4(2026-10-08), 활발.
- 설치·측정은 하지 않았다.

### B-4. Dear PyGui — 탈락

- **한글:** **안 된다.** 맑은 고딕 글꼴을 넣고 자동 시험을 했더니 `안녕하세요 `가 `?????????? `(물음표 10개 + 공백)로 들어갔다. 한 음절이 물음표 2개씩이라, 한글이 Windows 옛 문자 방식으로 바뀌며 깨지는 것으로 보인다. 같은 증상 보고: [Dear ImGui #471 "InputText show '???' when use IME"](https://github.com/ocornut/imgui/issues/471). Dear PyGui 저장소의 한국어 이슈 [#689](https://github.com/hoffstadt/DearPyGui/issues/689)는 "글꼴을 넣으라"는 답으로 닫혔지만, 글꼴을 넣어도 위처럼 깨졌다. Windows 기본 입력기에서 입력이 느리다는 [#1571](https://github.com/hoffstadt/DearPyGui/issues/1571)도 있다.
- **그 밖:** 링크 위젯이 없고, 화면 구성이 게임 개발 도구식이라 유리 창 모양과 거리가 멀다. MIT, 2.3.1(2026-05-01).

## 유리 창 시험(배경 블러가 진짜 되는가)

바라는 모양: 뒤가 흐리게 비치는 반투명 유리 창, 둥근 모서리, 테두리 없음, 어두운 바탕에 큰 흰 굵은 답 글씨와 작은 회색 질문 글씨, 반투명 둥근 카드, 아래 알약 모양 입력칸, 부드러운 애니메이션. (특정 회사 이름·로고·아이콘은 쓰지 않고 스타일만 참고한다.)

### Windows가 주는 방법 두 가지

- **공식 방법:** `DwmSetWindowAttribute`에 `DWMWA_SYSTEMBACKDROP_TYPE`을 주면 창 뒤에 Mica(바탕화면 색만 은은히 비침) 또는 Acrylic(뒤 창들이 흐리게 비침, `DWMSBT_TRANSIENTWINDOW`)을 깔아 준다. **Windows 11 빌드 22621 이상만** 된다. 출처: [DWM_SYSTEMBACKDROP_TYPE](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type)
  - Microsoft 문서는 **창이 비활성이면 배경 Acrylic·Mica가 단색으로 바뀐다**고 적고 있다. 투명 효과 설정을 끄거나, 배터리 절약 모드이거나, 성능 낮은 PC에서도 단색이 된다. 또 "Acrylic은 그래픽 카드를 많이 쓴다"고 한다. 출처: [Acrylic](https://learn.microsoft.com/en-us/windows/apps/design/style/acrylic), [Mica](https://learn.microsoft.com/en-us/windows/apps/design/style/mica)
- **문서 없는 방법:** `SetWindowCompositionAttribute` + `ACCENT_ENABLE_ACRYLICBLURBEHIND`. Microsoft 공식 문서가 없는 내부 함수라 Windows 업데이트로 언제든 바뀔 수 있다. pywinstyles 등 여러 꾸밈 도구가 이 함수를 쓴다.

### 직접 찍은 결과(강의실 PC, 창을 비활성으로 띄움 = Blender를 쓰는 동안의 모습)

| 방식 | 결과 |
|---|---|
| tkinter + pywinstyles "acrylic" | 회색 단색 판. 뒤가 비치지 않음. 제목 표시줄 그대로 |
| tkinter + 공식 Acrylic | 위와 똑같이 회색 단색 |
| Qt + 블러 없이 반투명 판만 그림(흉내) | 둥근 모서리·카드·알약 입력칸 다 나옴. 뒤 VS Code 글자가 **또렷이** 비쳐 읽기 방해 → 판을 더 어둡게(불투명도 높게) 해야 함 |
| Qt + 공식 Acrylic | 회색 단색 판(비활성이라). 카드·글자는 잘 보임 |
| Qt + 문서 없는 Acrylic | 어두운 바탕에 뒤가 **흐릿하게 번진 듯한 얼룩**이 보임 → 비활성에서도 블러가 남는 것으로 보임(정밀 대조는 안 함, 확인 필요) |

- 활성 상태(F10으로 불러 글을 칠 때)의 모습은 사용자 작업을 방해하지 않으려고 찍지 않았다(확인 필요). 문서대로라면 공식 Acrylic도 활성일 때는 흐림이 보인다. 그러면 **F10을 누를 때만 유리가 되고 Blender로 돌아가면 회색이 되는** 깜빡임이 생긴다.
- **성능:** 블러는 Windows 화면 합성기(DWM)가 그래픽 카드로 하므로 우리 프로그램의 F10 속도와는 거의 관계없다. 위 측정은 모두 GTX 950에서 했고 0.1초 안이었다. 블러·애니메이션을 켠 채로 F10 속도와 Blender 화면 속도를 함께 잰 것은 아니다(확인 필요).
- **IME 조합 글자:** Qt·웹 화면은 조합 글자를 칸 안에 우리 글자색으로 그리므로 유리 위에서도 잘 보인다. tkinter는 Windows 기본 흰 상자가 따로 떠서 어두운 유리 디자인과 어울리지 않는다.
- **Windows 10:** 공식 방법은 안 된다. 문서 없는 방법만 된다. Windows 10은 2025-10-14에 지원이 끝났으므로 ADR의 전제(Windows 11)를 유지하는 것이 낫다.

**결론:** 유리 느낌을 늘 유지하려면 ① 문서 없는 함수로 진짜 블러(위험: 업데이트로 깨질 수 있음), ② 블러 없이 "아주 어두운 반투명 판"으로 흉내(위험 없음, 뒤가 덜 비침) 중 하나다. **②로 시작하고 ①은 켜고 끌 수 있는 선택 기능으로 두기**를 권한다. 둘 다 Qt·QML이 가장 잘 받친다.

## 테두리 없는 창, `X` 버튼, 트레이 아이콘

정해진 것:

- Windows 제목 표시줄을 없애고 대화 영역과 입력칸만 보인다. 오른쪽 위에 단색 작은 `X` 하나만 둔다(숨기기, 프로그램은 안 꺼짐). 평소에는 흐리거나 마우스를 올렸을 때만 보인다.
- 도우미 창은 **작업 표시줄과 Alt+Tab에 나오지 않는다**(도구 창, `WS_EX_TOOLWINDOW`). 대신 **시스템 트레이**(시계 옆 알림 영역)에 아이콘을 둔다.
- 트레이 아이콘 왼쪽 클릭 = 보이기(이미 보이면 앞으로 부름, 숨기지 않음). 오른쪽 클릭 메뉴 = "보이기", "끝내기". 끝낸 뒤 F10을 누르면 애드온이 도우미를 다시 켠다.

도구 창 성질 출처: "도구 창은 작업 표시줄에도, Alt+Tab 목록에도 나오지 않는다." [Microsoft, Extended Window Styles](https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles)

| 확인 항목 | tkinter / CustomTkinter | PySide6(Qt, QML) | pywebview |
|---|---|---|---|
| 테두리 없애기 | `overrideredirect(True)` | `FramelessWindowHint` | `frameless=True` |
| 작업 표시줄·Alt+Tab에서 빼기 | **저절로 됨**. `overrideredirect`만으로 도구 창이 됨(직접 확인) | `Qt.Tool`을 함께 주면 도구 창이 됨(직접 확인) | 내장 기능 없음. `window.native`(WinForms 창)의 `ShowInTaskbar = False`로 작업 표시줄에서 빠짐(직접 확인). **이때 창 번호(HWND)가 새로 바뀌므로** 그 뒤에 다시 읽어야 함. Alt+Tab에서도 빠지는지는 확인 필요 |
| 트레이 아이콘 | 내장 없음. **pystray**(별도 라이브러리) 필요. 만들어지는 것 확인 | **내장** `QSystemTrayIcon`. 만들어지는 것 확인 | 내장 없음. pythonnet으로 WinForms `NotifyIcon`을 직접 쓰거나 pystray(확인 필요) |
| 트레이와 화면 도구가 함께 도는지 | pystray는 Windows에서 다른 스레드에서 돌려도 되고, 다른 도구와 함께 쓸 때는 `run_detached()`를 쓰라고 한다. 메뉴 클릭은 pystray 쪽 스레드에서 오므로 tkinter 스레드로 넘겨야 함(지금 코드의 줄(queue) 방식 그대로) | 같은 이벤트 루프 안. 클릭은 `activated` 신호(왼쪽 클릭 = `Trigger`), 메뉴는 `setContextMenu` | WinForms `NotifyIcon`은 같은 WinForms 스레드에서 돎(확인 필요) |
| `X` 숨기기 → F10·트레이로 다시 | 됨(지금 코드의 `ShowWindow(SW_HIDE)`) | 됨(`hide()`) | 됨(`hide()`/`show()`) |
| 가장자리 끌어 크기 조절 | 직접 만들어야 함(마우스 위치로 창 크기 계산) | `startSystemResize()`로 Windows 기본 동작 | 직접 만들어야 함(`window.resize()`) |
| 창 끌어 옮기기 | 직접 만들어야 함(쉬움) | `startSystemMove()` | `easy_drag` / 끌기 영역 표시 |
| 둥근 모서리·그림자 | 창 모서리 둥글게는 확인 필요(DWM 요청은 "힌트"일 뿐) | 창을 투명하게 하고 둥근 판을 직접 그림. 이때는 Windows 둥근 모서리·그림자를 못 받으므로 그림자도 직접 그림 | Windows 둥근 모서리는 확인 필요, 안쪽 모양은 CSS |
| 마우스 올렸을 때만 `X` 보이기 | `<Enter>`/`<Leave>` 이벤트로 됨(서서히 나타나는 효과는 거칢) | 쉬움(QML `HoverHandler` + 투명도 애니메이션) | 가장 쉬움(CSS `:hover` + `transition`) |

- 출처: [pystray 사용법](https://pystray.readthedocs.io/en/latest/usage.html)("Windows만 대상이면 `run()`을 메인 스레드가 아닌 곳에서 불러도 안전", 다른 도구와 함께면 `run_detached()`, Windows에서 기본 메뉴 항목은 왼쪽 클릭으로 실행), [QSystemTrayIcon](https://doc.qt.io/qt-6/qsystemtrayicon.html). pystray는 LGPL-3.0이고 마지막 릴리스가 0.19.5(2023-09-17)로 3년 넘게 멈춰 있다. 출처: [PyPI](https://pypi.org/project/pystray/)
- Qt로 트레이 앱을 만들 때는 창을 숨겨도 프로그램이 꺼지지 않게 `setQuitOnLastWindowClosed(False)`를 둔다(시험 코드에서 사용).
- 둥근 모서리 출처: Microsoft는 "픽셀마다 투명도를 쓰는 창(per-pixel alpha)이나 창 영역(region)을 쓰는 창은 둥근 모서리를 받을 수 없다"고 한다. 출처: [Apply rounded corners](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners). Qt 투명 창이 바로 이 경우다(창 성질에서 layered 확인).

### Windows 11이 새 트레이 아이콘을 숨김 영역(^)에 넣는 것

- **프로그램이 바꿀 수 없다.** Microsoft 문서: 새 알림 영역 아이콘은 기본으로 넘침 영역(숨김 영역)에 들어가고, **"아이콘을 넘침 영역에서 알림 영역으로 올릴 수 있는 것은 사용자뿐"**이다(시스템이 1분 미만 잠깐 보여 주는 경우만 예외). 문서는 사용자가 어떤 아이콘을 볼지 최종 결정해야 한다고 적는다. 출처: [Notifications and the Notification Area](https://learn.microsoft.com/en-us/windows/win32/shell/notification-area)
- 그래서 설치 안내에 "작업 표시줄 설정에서 도우미 아이콘을 켜 두세요" 한 줄이 필요하다. 트레이를 못 찾아도 F10으로 부를 수 있으므로 막히지는 않는다.

### 작업 표시줄에서 빼도 F10 부르기·한글이 되는가

- **F10 부르기:** `SetForegroundWindow`의 제한 조건(앞 프로그램이거나, 앞 프로그램이 `AllowSetForegroundWindow`로 허락했거나, 마지막 입력을 받았거나 등)에는 작업 표시줄 아이콘 유무가 없다. 출처: [SetForegroundWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setforegroundwindow). 지금처럼 Blender 애드온이 허락해 주는 방식은 도구 창에서도 같게 동작할 것으로 본다. **실제 F10 왕복은 도구 창으로 시험하지 않았다(확인 필요).**
- **한글:** 입력기는 창마다 붙는 입력 문맥으로 동작하고 작업 표시줄과는 관계없다. tkinter 한글 시험은 일반 창으로 했고, 도구 창으로는 하지 않았다(확인 필요).

### 트레이를 누르는 순간 앞 프로그램이 탐색기로 바뀌는 문제

- 트레이를 클릭하면 그 순간 앞 프로그램은 Windows 탐색기(작업 표시줄)가 된다. 지금 시제품의 `follow_blender`는 0.1초마다 앞 프로그램을 보고 "Blender나 도우미 자신이면 맨 위, 아니면 그 프로그램 뒤로, Blender가 최소화돼 있으면 숨김"으로 정한다. 그래서 클릭과 보이기 사이 0.1초 안에 도우미가 **탐색기 뒤로 한 번 내려갈 수 있다**. 바로 이어서 트레이 처리 코드가 창을 보이고 앞으로 부르면, 다음 확인 때 앞 프로그램이 "도우미 자신"이 되어 맨 위로 돌아온다.
- **도우미 자신이 앞이면 보이는 상태를 유지하는 처리는 이미 지금 코드에 있다**(앞 프로그램의 프로세스 번호가 도우미 자신이면 "맨 위"). 이 규칙은 HWND·프로세스 번호만 쓰므로 Qt·tkinter·pywebview 모두 같게 옮길 수 있다. 트레이 메뉴(Qt `QMenu`, pystray 메뉴)도 도우미 프로세스 안의 창이라 "자신"으로 잡힌다.
- 덧붙일 것 두 가지(도구와 관계없음):
  1. 앞 프로그램이 작업 표시줄·트레이(탐색기의 작업 표시줄 창)일 때는 "그대로 둠"으로 처리하면 내려갔다 올라오는 깜빡임이 없어진다.
  2. 트레이 클릭 뒤 도우미가 정말 앞으로 오는지(`SetForegroundWindow` 허락 여부)는 위 조건 중 "마지막 입력을 받은 프로세스"에 기대게 되는데, 클릭 입력은 탐색기가 받으므로 **보장되지 않는다**. 앞으로 못 오면 창은 보이되 입력칸에 초점이 없을 수 있다(확인 필요). Qt는 `activateWindow()`, 그 밖은 지금 코드의 `SetForegroundWindow`로 시도한다.
- Blender가 최소화된 상태에서 트레이로 도우미를 불렀다가 다른 곳을 누르면 지금 규칙상 다시 숨는다. 이것이 원하는 동작인지 정해야 한다.

## 조건별 비교 표

된다 / 안 된다 / 확인 필요. 근거는 위 상세 절의 링크와 직접 시험. PySide6 열의 속도·메모리 숫자는 위젯 판으로 잰 것이다(QML 판은 확인 필요).

| 조건 | tkinter | CustomTkinter | ttkbootstrap · sv-ttk | PySide6 + QML | pywebview | Flet | Dear PyGui |
|---|---|---|---|---|---|---|---|
| 1. 기본 한국어 IME로 한글 | 된다(시험 통과) | 된다(같은 Tk 칸) | 된다(같은 Tk 칸) | 된다(조합 표시 확인, 최종 값은 확인 필요) | 된다(조합 표시 확인, WebView2 한글 버그 보고 2건) | **안 된다**(열린 음절 빠짐 버그) | **안 된다**(`??????????`) |
| 1-1. 조합 중 글자를 칸 안에 표시 | 아니오(작은 별도 상자) | 아니오 | 아니오 | 예 | 예 | 확인 필요 | 아니오 |
| 2. F10 → 창 보임(목표 100ms) | 22-27ms | 28-39ms | 11-34ms | 16-54ms | 57-87ms | 확인 필요 | 22-33ms |
| 2-1. 첫 실행 / 메모리 / 용량 | 0.12초 / 33MB / 0 | 0.3-0.5초 / 44MB / 3MB | 0.2-0.45초 / 33-49MB / 1-20MB | 0.3-0.8초 / 60MB / 약 219MB | 1.4-2.1초 / 99MB + 웹 엔진 / 5MB | 확인 필요 | 0.3초 / 57MB / 7MB |
| 3. HWND 얻어 "Blender 앞일 때만 맨 위" | 된다(지금 코드) | 된다 | 된다 | 된다(`winId`) | 된다(`native.Handle`) | 확인 필요(창 제목으로 찾아야 함) | 된다(창 제목으로 찾음) |
| 4. 스트리밍·자동 줄바꿈·링크 클릭 | 된다 | 된다 | 된다 | 된다 | 된다 | 된다(문서 기준) | 링크 위젯 없음 |
| 5. 라이선스 | 파이썬 기본 | MIT(PyPI 표기는 CC0) | MIT / MIT | LGPL-3.0 등 | BSD-3 | Apache-2.0 | MIT |
| 5-1. Python 3.11+ · 최근 릴리스 | 된다 · 파이썬과 함께 | 된다 · 2026-06-24 | 된다 · 2026-09-12 / 2025-06-08 | 된다 · 2026-10-08 | 된다 · 2026-04-15 | 된다 · 2026-10-08 | 된다 · 2026-05-01 |
| 6. 유리 모양(반투명 유리, 둥근 카드, 알약 입력칸, 애니메이션) | 안 된다 | 일부(창 안 카드·알약 입력칸만) | 안 된다 | **된다**(진짜 블러는 문서 없는 함수로만 비활성 유지) | 모양은 가장 쉬움, 창 뒤 비침은 문서상 안 됨 | 일부(블러 없음) | 안 된다 |
| 7. 테두리 없는 창 + `X` 숨기기 + 가장자리 크기 조절 | 된다(크기 조절은 직접 만듦) | 같음 | 같음 | 된다(`startSystemResize`) | 된다(크기 조절은 직접 만듦) | 확인 필요 | 확인 필요 |
| 8. 작업 표시줄·Alt+Tab에서 빼기 + 트레이 아이콘 | 된다(도구 창 저절로) + pystray 필요 | 같음 | 같음 | 된다(둘 다 내장) | 우회로 됨(HWND 바뀜) + 트레이는 WinForms 직접 또는 pystray(확인 필요) | 확인 필요 | 확인 필요 |
| 9. Windows 11 트레이 숨김 영역에서 꺼내기 | 못 함(사용자만) | 못 함 | 못 함 | 못 함 | 못 함 | 못 함 | 못 함 |

## 추천 후보 3개

### 1순위: PySide6 + QML

- **이유:** 바라는 유리 모양(둥근 카드, 알약 입력칸, 흰 굵은 답·회색 질문, 부드러운 등장·글자 애니메이션)을 모두 만들 수 있는 유일한 후보다. 한글 조합 글자가 칸 안에 보이고, HWND를 바로 얻어 지금 Windows 처리 코드를 그대로 쓴다. 작업 표시줄·Alt+Tab에서 빼기(`Qt.Tool`)와 트레이 아이콘(`QSystemTrayIcon`)이 모두 내장이라 별도 라이브러리가 없고, 테두리 없는 창에서도 Windows 기본 크기 조절·옮기기가 된다. F10 속도 16-54ms.
- **위험:**
  - 진짜 배경 블러는 문서 없는 Windows 함수로만 비활성 상태에서 유지된다. 처음에는 "어두운 반투명 판"으로 시작하길 권한다.
  - 설치 용량 약 219MB, 첫 실행 0.3-0.8초(미리 띄우므로 F10에는 영향 없음).
  - QML이라는 새 화면 언어를 익혀야 한다. QML 판의 속도·메모리, 최종 한글 값, 도구 창에서의 F10 왕복, 트레이 클릭 뒤 앞으로 오기는 아직 직접 확인하지 못했다.
  - LGPL: PySide6를 고치지 않고 pip로 받아 쓰면 문제없다.
- **지금 코드에서 바꿀 양:** 창·위젯 약 40줄을 QML 파일 하나(약 100-150줄 예상) + 파이썬 연결 코드로 새로 쓴다. Windows 처리 약 90줄과 신호 받기 약 20줄은 그대로 쓰고, 줄(queue)에서 꺼내는 부분만 Qt 신호로 바꾼다. `X`용 "사용자가 내림" 표시, 트레이(약 20줄), 앞 프로그램이 작업 표시줄일 때 "그대로 둠" 규칙은 새로 넣는다.

### 2순위: pywebview(HTML/CSS)

- **이유:** 모양 만들기는 가장 쉽다(CSS로 둥근 카드·알약·애니메이션·마우스 올림 효과). 한글 조합 글자도 칸 안에 보이고, HWND도 얻는다. 테두리 없는 창에서 `minimize`·`hide`가 된다.
- **위험:**
  - 창 뒤를 비치게 하는 투명 창은 공식 문서상 Windows에서 지원하지 않는다. 그러면 유리 느낌은 창 안 디자인으로만 낸다.
  - 메모리가 가장 크고(본체 99MB + 웹 엔진 프로세스 6개), 첫 실행 1.4-2.1초, F10 창 보임 57-87ms로 목표에 가장 가깝다.
  - WebView2 한글 보고 2건(조합 중 초점 이동 시 꺼짐, 크기 바꾼 뒤 조합 창 위치 튐)을 우리 앱에서 확인해야 한다.
  - 테두리 없는 창은 가장자리 크기 조절을 직접 만들어야 한다.
  - 작업 표시줄에서 빼기·트레이 아이콘이 내장 기능에 없다. WinForms 속성(`ShowInTaskbar`, `NotifyIcon`)을 pythonnet으로 직접 만져야 하고, 그때 HWND가 바뀌는 점을 챙겨야 한다.
- **지금 코드에서 바꿀 양:** 창·위젯 약 40줄을 HTML/CSS/JS 한 파일(약 150-200줄 예상) + 파이썬 연결 코드로 새로 쓴다. Windows 처리·신호 받기는 그대로 쓴다. 스트리밍은 파이썬에서 `evaluate_js`로 글을 넘긴다.

### 3순위: CustomTkinter(지금 tkinter 유지)

- **이유:** 가장 적게 바꾸고, 가장 가볍고(첫 실행 0.3-0.5초, 44MB, 3MB), 한글 입력은 시제품에서 이미 검증된 Tk 칸을 그대로 쓴다. 창 안의 어두운 테마, 둥근 카드, 알약 입력칸은 된다.
- **위험:**
  - 바라는 모양 중 반투명 유리, 둥근 창 모서리, 부드러운 애니메이션은 안 된다. "투박함"이 일부만 풀린다.
  - 조합 중 글자가 Windows 기본 흰 상자에 따로 뜬다.
  - 트레이 아이콘에 pystray가 필요한데 마지막 릴리스가 2023-09로 멈춰 있고(LGPL-3.0), 메뉴 클릭을 tkinter 스레드로 넘기는 코드가 필요하다. 테두리 없는 창의 크기 조절은 직접 만들어야 한다.
- **지금 코드에서 바꿀 양:** 가장 적다. `tk.Text`·`tk.Entry`를 `CTkTextbox`·`CTkEntry`로 바꾸고 색·글꼴을 정하는 정도(약 20-40줄). 테두리 없는 창(`overrideredirect` 한 줄, 그러면 작업 표시줄에서도 저절로 빠짐), pystray 트레이(약 20-30줄), 크기 조절 손잡이(약 20줄)가 더 든다.

**뺀 후보:** Flet(Flutter Windows 한글 음절 빠짐 버그 열림), Dear PyGui(한글이 `?`로 깨짐), ttkbootstrap·sv-ttk(모양 목표와 거리가 멂, sv-ttk는 1년 넘게 릴리스 없음), PyQt6(GPL만).

## 확인 못 한 것

- **Qt·QML·pywebview·CustomTkinter의 한글 최종 값:** 자동 시험 중 사용자 작업과 겹쳐 값이 섞였다. 조합 중 표시만 확인했다. 사용자가 각 시험 창에서 직접 "동해물과 백두산이" 같은 문장을 빨리 쳐 보는 확인이 필요하다.
- **활성 상태의 유리 모양:** 포커스를 빼앗지 않으려고 비활성 모습만 찍었다.
- **문서 없는 Acrylic 블러가 정말 비활성에서도 유지되는지:** 그림으로 보기에는 그렇지만, 뒤에 대비가 큰 그림을 두고 정밀하게 대조하지는 않았다.
- **트레이 클릭 뒤 도우미가 앞으로 오고 입력칸에 초점이 가는지, 그 순간 탐색기가 앞이 되어 생기는 깜빡임:** 손으로 눌러 봐야 한다.
- **도구 창(작업 표시줄에서 뺀 창)에서 F10 왕복과 한글 입력:** 일반 창으로만 시험했다.
- **pywebview `ShowInTaskbar = False` 뒤 Alt+Tab에서도 빠지는지, WinForms `NotifyIcon` 트레이:** 시험하지 않았다.
- **QML 판의 첫 실행 시간·메모리, 블러·애니메이션을 켠 상태의 F10 속도와 Blender 화면 속도:** 측정은 Qt 위젯 판으로만 했다.
- **pywebview 투명 창:** 문서는 "Windows 미지원", 소스에는 투명 배경 코드가 있다. 실제로 시험하지 않았다.
- **Flet:** 설치·측정하지 않았다(한글 버그로 먼저 뺌).
- **tkinter 테두리 없는 창의 둥근 모서리:** 시험하지 않았다.
- **WebView2 한글 버그 2건이 pywebview에서 재현되는지:** 시험하지 않았다.

## 재현 방법(이번 조사에서 한 일)

- 가상 환경: `python -m venv %TEMP%\uiv` 뒤 `pip install customtkinter ttkbootstrap sv-ttk PySide6-Essentials pywebview dearpygui pywinstyles pystray psutil`. 처음에 긴 경로 폴더에 설치하다가 Windows 경로 길이 제한(260자)에 걸려 짧은 경로로 옮겼다.
- 패키지 정보: PyPI JSON(`https://pypi.org/pypi/<이름>/json`)에서 최신 버전·날짜·라이선스·지원 파이썬을 읽었다. 저장소 활성도는 `gh api repos/<저장소>`로 봤다.
- 이슈 검색: GitHub는 `gh search issues`, Qt는 Qt 이슈 트래커(qt-project.atlassian.net) 검색 API를 썼다.
- 측정·시험 스크립트(속도, 한글 입력, 유리 창, 테두리 없는 창)는 저장소 밖 임시 폴더에만 두었고 커밋하지 않았다. 유료 API는 쓰지 않았다.
