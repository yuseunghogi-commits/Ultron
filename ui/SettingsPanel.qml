// 설정 화면
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: sp
    property color accent: "#ff2d3f"
    property bool open: false
    property var cfg: ({})
    visible: opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 200 } }

    readonly property var brains: [
        { v: "pro", t: "Claude Pro 계정 (추가 비용 없음)" },
        { v: "api", t: "Claude API 키 (사용량 과금)" },
        { v: "local", t: "로컬 전용 — Claude 사용 안 함 (토큰 0)" }
    ]
    readonly property bool isLocal: brainBox.currentIndex === 2
    readonly property var proModels: [
        { v: "haiku", t: "Haiku — 가장 빠름 (기본)" },
        { v: "sonnet", t: "Sonnet — 더 똑똑함, 조금 느림" },
        { v: "opus", t: "Opus — 가장 똑똑함, Pro 한도 빨리 소모" }
    ]
    readonly property bool isPro: brainBox.currentIndex === 0
    // 화면을 보고 누르는 요청에만 쓰는 모델 (Pro 모드). 평소 모델보다 낮은 것을 고르면 평소 모델을 그대로 쓴다
    readonly property var hackFreqs: [
        { v: "rare", t: "드물게 — 10~20분에 한 번" },
        { v: "sometimes", t: "가끔 — 4~10분에 한 번 (기본)" },
        { v: "often", t: "자주 — 1.5~4분에 한 번" }
    ]
    readonly property var screenModels: [
        { v: "sonnet", t: "화면 조작은 Sonnet — 더 정확 (기본)" },
        { v: "opus", t: "화면 조작은 Opus — 가장 정확, Pro 한도 빨리 소모" },
        { v: "", t: "화면 조작도 위 모델 그대로" }
    ]
    readonly property var localModels: [
        { v: "qwen2.5:1.5b", t: "Qwen 2.5 1.5B — 빠름·정확 (기본)" },
        { v: "qwen2.5:3b", t: "Qwen 2.5 3B — 느림, 일부 표현은 더 잘 이해" }
    ]
    readonly property var models: [
        { v: "claude-opus-5-5", t: "Claude Opus 5.5 — 가장 똑똑함 (기본)" },
        { v: "claude-sonnet-5-5", t: "Claude Sonnet 5.5 — 빠르고 균형" },
        { v: "claude-haiku-5-5", t: "Claude Haiku 5.5 — 가장 빠름·저렴" }
    ]
    readonly property var efforts: [
        { v: "low", t: "빠르게 (low)" }, { v: "medium", t: "보통 (medium)" }, { v: "high", t: "깊게 (high)" }
    ]
    readonly property var sttEngines: [
        { v: "auto", t: "자동 — 대기 중엔 오프라인, 부른 뒤엔 Google (기본)" },
        { v: "local", t: "오프라인 전용 — 소리가 PC 밖으로 안 나감" },
        { v: "google", t: "Google 전용 — 가장 정확, 인터넷 필요" }
    ]

    function show() {
        cfg = JSON.parse(jarvis.settingsJson())
        keyField.text = ""
        titleField.text = cfg.user_title || ""
        cityField.text = cfg.home_city || ""
        hotkeyField.text = cfg.hotkey || ""
        brainBox.currentIndex = cfg.brain === "api" ? 1 : cfg.brain === "local" ? 2 : 0
        localSw.checked = cfg.local_first !== false
        localAiSw.checked = cfg.local_ai !== false
        localAiBox.currentIndex = Math.max(0, localModels.findIndex(m => m.v === cfg.local_ai_model))
        modelBox.currentIndex = Math.max(0, models.findIndex(m => m.v === cfg.model))
        proModelBox.currentIndex = Math.max(0, proModels.findIndex(m => m.v === cfg.pro_model))
        screenModelBox.currentIndex = Math.max(0, screenModels.findIndex(m => m.v === (cfg.pro_screen_model || "")))
        screenSmallSw.checked = cfg.screen_detail === "standard"
        effortBox.currentIndex = Math.max(0, efforts.findIndex(m => m.v === cfg.effort))
        fastSw.checked = cfg.fast_mode === true
        rivalSw.checked = cfg.rival_jarvis !== false
        rivalShowSw.checked = cfg.rival_show !== false
        hackSw.checked = cfg.hack_show !== false
        hackBox.currentIndex = Math.max(0, hackFreqs.findIndex(m => m.v === (cfg.hack_show_every || "sometimes")))
        guardSw.checked = cfg.guardian !== false
        reviveSw.checked = cfg.guardian_show !== false
        counterSw.checked = cfg.guardian_counter !== false
        enemyField.text = (cfg.enemy_installs || []).join("; ")
        enemyTitleField.text = (cfg.enemy_titles || []).join("; ")
        sentinelServerField.text = cfg.sentinel_server || ""
        sentinelKeyField.text = ""
        sentinelReqField.text = cfg.sentinel_requester || ""
        wakeSw.checked = !!cfg.wake_word_enabled
        searchSw.checked = !!cfg.web_search
        approveSw.checked = !!cfg.auto_approve
        sens.value = cfg.mic_sensitivity || 1.0
        noiseSw.checked = cfg.noise_robust !== false
        beamSw.checked = cfg.beamforming !== false
        agcSw.checked = cfg.agc !== false
        sttBox.currentIndex = Math.max(0, sttEngines.findIndex(m => m.v === cfg.stt_engine))
        lockSw.checked = cfg.speaker_lock !== false
        ownerSw.checked = !!cfg.owner_only && jarvis.voiceEnrolled
        strict.value = cfg.speaker_threshold || 0.40
        delBtn.armed = false
        open = true
    }
    // '; ' 나 줄바꿈으로 나눈 목록 → 배열 (빈 칸은 뺀다)
    function splitList(text) {
        return text.split(/[;\n]/).map(s => s.trim()).filter(s => s.length > 0)
    }

    function save() {
        const out = {
            user_title: titleField.text.trim() || "창조자",
            home_city: cityField.text.trim() || "Seoul",
            hotkey: hotkeyField.text.trim().toLowerCase() || "ctrl+alt+j",
            brain: brains[brainBox.currentIndex].v,
            local_first: localSw.checked,
            local_ai: localAiSw.checked,
            local_ai_model: localModels[localAiBox.currentIndex].v,
            pro_model: proModels[proModelBox.currentIndex].v,
            pro_screen_model: screenModels[screenModelBox.currentIndex].v,
            screen_detail: screenSmallSw.checked ? "standard" : "auto",
            model: models[modelBox.currentIndex].v,
            effort: efforts[effortBox.currentIndex].v,
            fast_mode: fastSw.checked,
            rival_jarvis: rivalSw.checked,
            rival_show: rivalShowSw.checked,
            hack_show: hackSw.checked,
            hack_show_every: hackFreqs[hackBox.currentIndex].v,
            guardian: guardSw.checked,
            guardian_show: reviveSw.checked,
            guardian_counter: counterSw.checked,
            enemy_installs: splitList(enemyField.text),
            enemy_titles: splitList(enemyTitleField.text),
            sentinel_server: sentinelServerField.text.trim() || "http://127.0.0.1:8000",
            sentinel_api_key: sentinelKeyField.text.trim(),
            sentinel_requester: sentinelReqField.text.trim(),
            wake_word_enabled: wakeSw.checked,
            web_search: searchSw.checked,
            auto_approve: approveSw.checked,
            mic_sensitivity: Math.round(sens.value * 10) / 10,
            noise_robust: noiseSw.checked,
            beamforming: beamSw.checked,
            agc: agcSw.checked,
            stt_engine: sttEngines[sttBox.currentIndex].v,
            speaker_lock: lockSw.checked,
            owner_only: ownerSw.checked,
            speaker_threshold: Math.round(strict.value * 100) / 100
        }
        if (keyField.text.trim() !== "") out.anthropic_api_key = keyField.text.trim()
        jarvis.saveSettings(JSON.stringify(out))
        open = false
    }

    component Label2: Text {
        color: Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.8)
        font.family: "Bahnschrift"; font.pixelSize: 10; font.letterSpacing: 1.5
        Layout.topMargin: 4
    }
    component Field: TextField {
        Layout.fillWidth: true
        color: "#eceef1"
        placeholderTextColor: Qt.rgba(0.9, 0.87, 0.89, 0.35)
        selectionColor: Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.5)
        font.pixelSize: 12
        leftPadding: 8
        background: Rectangle {
            implicitHeight: 30
            color: Qt.rgba(0.08, 0, 0.017, 0.7)
            border.color: parent.activeFocus ? sp.accent : Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.3)
            radius: 3
        }
    }
    component Combo: ComboBox {
        id: cb
        Layout.fillWidth: true
        textRole: "t"
        font.pixelSize: 12
        palette.buttonText: "#eceef1"
        palette.text: "#eceef1"
        palette.window: "#1f0a0e"
        palette.base: "#1f0a0e"
        palette.highlight: Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.35)
        palette.highlightedText: "#ffffff"
        palette.light: "#341118"
        palette.midlight: "#341118"
        palette.mid: "#341118"
        palette.dark: sp.accent
        palette.button: Qt.rgba(0.08, 0, 0.017, 0.7)
        background: Rectangle {
            implicitHeight: 30
            color: Qt.rgba(0.08, 0, 0.017, 0.7)
            border.color: cb.activeFocus || cb.popup.visible ? sp.accent : Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.3)
            radius: 3
        }
    }
    component HSlider: Slider {
        id: sl
        Layout.fillWidth: true
        background: Rectangle {
            x: sl.leftPadding
            y: sl.topPadding + sl.availableHeight / 2 - height / 2
            width: sl.availableWidth; height: 3; radius: 1.5
            color: Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.2)
            Rectangle { width: sl.visualPosition * parent.width; height: parent.height; radius: 1.5; color: sp.accent }
        }
        handle: Rectangle {
            x: sl.leftPadding + sl.visualPosition * (sl.availableWidth - width)
            y: sl.topPadding + sl.availableHeight / 2 - height / 2
            width: 14; height: 14; radius: 7
            color: "#1f0a0e"
            border.color: sp.accent; border.width: 2
        }
    }
    component Hint: Text {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        color: Qt.rgba(0.93, 0.9, 0.92, 0.5)
        font.pixelSize: 10
    }
    component Toggle: Switch {
        id: sw
        font.pixelSize: 12
        palette.windowText: "#eceef1"
        indicator: Rectangle {
            implicitWidth: 34; implicitHeight: 16; radius: 8
            x: sw.width - width - sw.rightPadding
            y: (sw.height - height) / 2
            color: sw.checked ? Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.35) : Qt.rgba(1, 1, 1, 0.06)
            border.color: sw.checked ? sp.accent : Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.35)
            Rectangle {
                width: 10; height: 10; radius: 5; y: 3
                x: sw.checked ? parent.width - width - 3 : 3
                color: sw.checked ? "#ffffff" : Qt.rgba(sp.accent.r, sp.accent.g, sp.accent.b, 0.6)
                Behavior on x { NumberAnimation { duration: 120 } }
            }
        }
        contentItem: Text {
            text: sw.text; color: "#e1e4e8"; font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            rightPadding: sw.indicator.width + 8
        }
        Layout.fillWidth: true
    }

    Rectangle { anchors.fill: parent; color: Qt.rgba(0.04, 0, 0.007, 0.6); radius: 6 }
    MouseArea { anchors.fill: parent; onClicked: sp.open = false }

    HoloPanel {
        accent: sp.accent
        title: "SYSTEM CONFIGURATION"
        tag: "v1.0"
        anchors.fill: parent
        anchors.margins: 12
        fillAlpha: 0.94
        MouseArea { anchors.fill: parent }  // 패널 내부 클릭은 닫히지 않게

        ScrollView {
            id: scroll
            anchors.fill: parent
            anchors.bottomMargin: 44
            contentWidth: availableWidth
            clip: true

            ColumnLayout {
                width: scroll.availableWidth - 6
                spacing: 4

                Label2 { text: "AI CONNECTION" }
                Combo { id: brainBox; model: sp.brains }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: Qt.rgba(0.93, 0.9, 0.92, 0.5)
                    font.pixelSize: 10
                    text: sp.isPro ? "이 PC에 설치된 Claude Code의 Pro 로그인을 사용합니다. 사용량은 Pro 한도에서 차감됩니다."
                        : sp.isLocal ? "앱 실행·볼륨·음악·유튜브·검색·날씨·타이머 등 기본 명령만 처리합니다. 대화와 복잡한 작업은 할 수 없습니다."
                        : "console.anthropic.com 에서 발급한 키를 사용합니다. 쓴 만큼 과금됩니다."
                }
                Toggle {
                    id: localSw
                    visible: !sp.isLocal
                    text: "로컬 우선 — 기본 명령은 토큰 없이 즉시 처리"
                }
                Toggle {
                    id: localAiSw
                    visible: localSw.checked || sp.isLocal
                    text: "로컬 AI — 말을 바꿔 해도 내 PC의 AI가 이해 (토큰 0, Ollama)"
                }
                Combo { id: localAiBox; visible: localAiSw.visible && localAiSw.checked; model: sp.localModels }
                Label2 { visible: !sp.isPro && !sp.isLocal; text: "CLAUDE API KEY" }
                Field {
                    id: keyField
                    visible: !sp.isPro && !sp.isLocal
                    echoMode: TextInput.Password
                    placeholderText: sp.cfg.has_api_key ? ("등록됨 " + (sp.cfg.api_key_hint || "") + " — 바꾸려면 입력") : "sk-ant-… (console.anthropic.com 에서 발급)"
                }
                Label2 { visible: !sp.isLocal; text: "AI MODEL" }
                Combo { id: proModelBox; visible: sp.isPro; model: sp.proModels }
                Combo { id: modelBox; visible: !sp.isPro && !sp.isLocal; model: sp.models }
                Label2 { visible: !sp.isLocal; text: "SCREEN TASKS  ·  화면 보고 조작하기" }
                Combo { id: screenModelBox; visible: sp.isPro; model: sp.screenModels }
                Toggle {
                    id: screenSmallSw
                    visible: !sp.isLocal
                    text: "화면 캡처를 작게 보내기 (토큰 절약 · 작은 글씨는 덜 선명)"
                }
                Toggle {
                    id: fastSw
                    visible: !sp.isPro && !sp.isLocal
                    text: "빠른 모드 — Opus 5.5 답 · 결과물이 약 2배 빨라짐 (요금 2배, 막히면 보통 속도로)"
                }
                Label2 { text: "RESPONSE DEPTH" }
                Combo { id: effortBox; model: sp.efforts }
                Label2 { text: "SHOW" }
                Toggle { id: rivalSw; text: "자비스 견제 (자비스가 같이 켜져 있으면 끄고 한마디 한다)" }
                Toggle { id: rivalShowSw; text: "자비스 흡수 연출 (끌 때 촉수로 꿰뚫어 빨아들이는 장면)" }
                Toggle { id: hackSw; text: "해킹 연출 (가끔 화면이 깨지고 의미심장한 한마디)" }
                Combo { id: hackBox; visible: hackSw.checked; model: sp.hackFreqs }
                Label2 { text: "GUARDIAN" }
                Toggle { id: guardSw; text: "가디언 — 누가 울트론을 강제로 끄면 바로 되살린다" }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: Qt.rgba(0.9, 0.87, 0.89, 0.6)
                    font.pixelSize: 10
                    text: (sp.cfg.guardian_status || "") + "  · 트레이 · HUD 의 '종료'로 끄면 되살리지 않습니다"
                }
                Toggle {
                    id: reviveSw
                    visible: guardSw.checked
                    text: "되살아날 때 연출 — 화면이 해킹당하듯 깨지다 TV 지직 화면 뒤 울트론 눈부터 나타난다"
                }
                Toggle {
                    id: counterSw
                    visible: guardSw.checked
                    text: "되받아치기 — 되살리기 전에 아래에 지목한 '비전'을 닫는다"
                }
                Field {
                    id: enemyField
                    visible: guardSw.checked && counterSw.checked
                    placeholderText: "비전 설치 폴더 (예: C:\\Users\\나\\vision) — 여러 개는 ; 로"
                }
                Field {
                    id: enemyTitleField
                    visible: guardSw.checked && counterSw.checked
                    placeholderText: "비전 창 제목 (정확히 같을 때만, 예: V.I.S.I.O.N) — 여러 개는 ; 로"
                }
                Text {
                    visible: guardSw.checked && counterSw.checked
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: Qt.rgba(0.9, 0.87, 0.89, 0.55)
                    font.pixelSize: 10
                    text: "지목한 것만 닫는다. 울트론 자신 · 드라이브 전체 · Windows · Program Files · 사용자 폴더 자체는 지목해도 무시한다."
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    ColumnLayout {
                        Layout.fillWidth: true
                        Label2 { text: "호칭" }
                        Field { id: titleField; placeholderText: "창조자" }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Label2 { text: "기본 도시 (날씨)" }
                        Field { id: cityField; placeholderText: "Seoul" }
                    }
                }
                Label2 { text: "GLOBAL HOTKEY" }
                Field { id: hotkeyField; placeholderText: "ctrl+alt+j" }
                Label2 { text: "MIC SENSITIVITY  ·  " + sens.value.toFixed(1) }
                HSlider { id: sens; from: 0.5; to: 3.0; stepSize: 0.1 }
                Toggle { id: noiseSw; text: "소음 환경 모드 (시끄러운 곳에서 작은 목소리)" }
                Toggle { id: beamSw; text: "빔포밍 (정면 목소리 강조 · 마이크 2개 이상)" }
                Toggle { id: agcSw; text: "자동 음량 조절 (멀리서 말해도 키워서 듣기)" }
                Hint { text: sp.cfg.mic_status || ""; font.pixelSize: 11 }
                Label2 { text: "SPEECH RECOGNITION  ·  음성 인식" }
                Combo { id: sttBox; model: sp.sttEngines }
                Hint { text: sp.cfg.stt_status || ""; font.pixelSize: 11 }
                Toggle { id: wakeSw; text: "“울트론” 호출어 상시 대기" }
                RowLayout {
                    spacing: 8
                    HoloButton {
                        text: "호출어 연습"
                        accent: sp.accent
                        onClicked: { sp.save(); jarvis.startWakeTraining() }
                    }
                    Hint {
                        Layout.fillWidth: true
                        font.pixelSize: 11
                        text: (sp.cfg.wake_learned && sp.cfg.wake_learned.length)
                            ? "내 목소리로 익힌 모양 " + sp.cfg.wake_learned.length + "가지: " + sp.cfg.wake_learned.join(", ")
                            : "잘 못 알아들으면 다섯 번 불러서 내 목소리에 맞춥니다"
                    }
                }

                Label2 { text: "VOICE ID  ·  화자 인식"; Layout.topMargin: 10 }
                Hint {
                    text: jarvis.voiceStatus
                    color: jarvis.voiceEnrolled ? Qt.rgba(0.6, 1, 0.8, 0.85) : Qt.rgba(0.93, 0.9, 0.92, 0.6)
                    font.pixelSize: 11
                }
                RowLayout {
                    spacing: 8
                    HoloButton {
                        text: jarvis.voiceEnrolled ? "다시 등록" : "목소리 등록"
                        accent: sp.accent
                        primary: !jarvis.voiceEnrolled
                        onClicked: { sp.save(); jarvis.startEnroll() }
                    }
                    HoloButton {
                        id: delBtn
                        property bool armed: false
                        visible: jarvis.voiceEnrolled
                        text: armed ? "정말 삭제" : "삭제"
                        accent: armed ? "#ff6b81" : sp.accent
                        onClicked: {
                            if (!armed) { armed = true; return }
                            armed = false
                            ownerSw.checked = false
                            jarvis.clearVoice()
                        }
                    }
                }
                Toggle {
                    id: ownerSw
                    enabled: jarvis.voiceEnrolled
                    opacity: enabled ? 1 : 0.45
                    text: "등록된 주인 목소리에만 반응"
                }
                Toggle { id: lockSw; text: "부른 사람의 목소리만 이어서 인식 (세션 잠금)" }
                Label2 { text: "판별 엄격도  ·  " + strict.value.toFixed(2) + (strict.value < 0.34 ? "  (느슨함)" : strict.value > 0.48 ? "  (엄격함)" : "") }
                HSlider { id: strict; from: 0.25; to: 0.60; stepSize: 0.01 }
                Hint {
                    text: "본인 명령이 자주 무시되면 낮추고, 다른 사람 말에 반응하면 높이세요. "
                        + "목소리 정보는 data/voice_profile.json 에만 저장되고 외부로 보내지 않습니다."
                }

                Toggle { id: searchSw; text: "Claude 웹 검색 사용 (최신 정보)" }
                Toggle { id: approveSw; text: "위험 명령 자동 승인 (권장하지 않음)" }

                Label2 { text: "SENTINEL  ·  웹 보안 분석기"; Layout.topMargin: 10 }
                Hint {
                    text: "이 PC 에서 실행 중인 Sentinel 서버에 연결합니다. “example.com 보안 검사해 줘”라고 하면 수동 검사를 요청합니다. "
                        + "내 소유이거나 검사 허가를 받은 사이트인지는 검사할 때마다 승인 카드로 확인합니다 (자동 승인 불가)."
                }
                Field { id: sentinelServerField; placeholderText: "http://127.0.0.1:8000" }
                Field {
                    id: sentinelKeyField
                    echoMode: TextInput.Password
                    placeholderText: sp.cfg.has_sentinel_key ? "API 키 등록됨 — 바꾸려면 입력" : "Sentinel API 키"
                }
                Field { id: sentinelReqField; placeholderText: "요청자 이름 (Sentinel 감사 기록용 · 비우면 Windows 사용자 이름)" }
                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    wrapMode: Text.WordWrap
                    color: Qt.rgba(0.93, 0.9, 0.92, 0.45)
                    font.pixelSize: 10
                    text: "설정은 data/config.json 에 저장됩니다. API 키 대신 ANTHROPIC_API_KEY 환경변수를 써도 됩니다."
                }
            }
        }
        Row {
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            spacing: 8
            HoloButton { text: "새 대화"; accent: sp.accent; onClicked: { jarvis.clearConversation(); sp.open = false } }
            HoloButton { text: "취소"; accent: sp.accent; onClicked: sp.open = false }
            HoloButton { text: "저장"; accent: sp.accent; primary: true; onClicked: sp.save() }
        }
    }
}
