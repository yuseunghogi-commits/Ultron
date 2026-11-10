// U.L.T.R.O.N 코어 엠블럼 — 붉게 빛나는 두 눈 + 톱니 링 + 육각 꺾쇠 (배경 없음, 전부 벡터)
//
//   육각 꺾쇠     r211 꼭짓점마다 꺾쇠 — 천천히 흔들림
//   톱니 링       r184~196, 톱니 60개 — 천천히 돌고, 생각 중엔 빨라짐
//   눈금 링       r160~174, 72개 — 빛이 훑고 지나가고, 말할 때 바깥으로 늘어남
//   칼날 띠       r124~151, 비스듬한 칼날 6개 — 생각 중엔 빠르게 회전
//   강철 호       r116, 반대로 회전
//   안쪽 링       r107 밝은 링 + 어두운 원판 + 삼각 무늬
//   두 눈         안쪽으로 치켜 내려간 빛나는 눈 — 들을 땐 크게 뜨고, 생각할 땐 가늘게, 가끔 깜빡임
//   워드마크      ULTRON
//
// 좌표는 440 단위 정사각형(중심 220,220) 기준이고 u 로 크기를 맞춘다.
// 모든 움직임은 매 프레임 지수 감쇠로 목표값을 따라가므로 상태가 바뀌어도 툭 끊기지 않는다.
import QtQuick
import QtQuick.Shapes
import QtQuick.Effects

Item {
    id: e
    property color accent: "#ff2d3f"
    property real level: 0             // 0..1 (마이크/음성)
    property string mode: "standby"    // boot | standby | listening | thinking | speaking | offline
    property real size: 214
    property bool voiceBars: false     // 워드마크 아래 음성 파형 (전체 모드)
    width: size; height: size

    readonly property real u: size / 440
    readonly property real cx: width / 2
    readonly property real cy: height / 2

    // ---------------- 상태별 목표값 ----------------
    readonly property real speedTarget: mode === "thinking" ? 4.5 : mode === "listening" ? 1.6
                                      : mode === "speaking" ? 1.4 : mode === "offline" ? 0.25 : 1.0
    readonly property real energyTarget: mode === "thinking" ? 1.0 : mode === "listening" ? 0.85
                                       : mode === "speaking" ? 0.7 : mode === "boot" ? 0.5 : mode === "offline" ? 0.3 : 0.2
    readonly property real tintTarget: (mode === "thinking" || mode === "offline") ? 0.8 : 0.0
    readonly property real eyeTarget: mode === "listening" ? 1.25 : mode === "thinking" ? 0.6
                                    : mode === "offline" ? 0.4 : mode === "boot" ? 0.8 : 1.0
    readonly property real glowTarget: mode === "offline" ? 0.3 : mode === "standby" ? 0.86 : 1.0

    // ---------------- 매 프레임 갱신되는 값 ----------------
    property real t: 0
    property real spd: 1
    property real energy: 0.2
    property real tint: 0
    property real amp: 0
    property real listenAmt: 0
    property real thinkAmt: 0
    property real eyeOpen: 1
    property real eyeGlow: 0.86
    property real aSaw: 0
    property real aTicks: 0
    property real aBand: 0
    property real aSteel: 0
    property real aCore: 0
    property real aOrbit: 0
    property real scanA: 0
    property real blink: 1             // 1 = 뜬 눈, 깜빡일 때 잠깐 0 근처
    readonly property real breath: 0.5 + 0.5 * Math.sin(t * 1.15)
    readonly property real sway: 2.0 * Math.sin(t * 0.23) + 1.0 * Math.sin(t * 0.11 + 1.3)

    FrameAnimation {
        running: e.visible
        onTriggered: {
            const dt = Math.min(frameTime, 0.05)
            const f = k => 1 - Math.exp(-dt * k)
            e.t += dt
            e.spd += (e.speedTarget - e.spd) * f(1.6)
            e.energy += (e.energyTarget - e.energy) * f(2.4)
            e.tint += (e.tintTarget - e.tint) * f(3)
            e.listenAmt += ((e.mode === "listening" ? 1 : 0) - e.listenAmt) * f(3.5)
            e.thinkAmt += ((e.mode === "thinking" ? 1 : 0) - e.thinkAmt) * f(3.5)
            const target = Math.min(1, e.mode === "standby" ? e.level * 0.5 : e.level)
            e.amp += (target - e.amp) * f(target > e.amp ? 20 : 4.5)   // 빠르게 오르고 천천히 가라앉음
            e.eyeOpen += (e.eyeTarget - e.eyeOpen) * f(6)
            e.eyeGlow += (Math.min(1.2, e.glowTarget + 0.4 * e.amp) - e.eyeGlow) * f(9)
            e.aSaw += dt * (3 * e.spd + 40 * e.thinkAmt)
            e.aTicks -= dt * 2 * e.spd
            e.aBand += dt * (6 * e.spd + 150 * e.thinkAmt)
            e.aSteel -= dt * (10 + 80 * e.thinkAmt)
            e.aCore += dt * 5 * e.spd
            e.aOrbit += dt * (50 + 130 * e.thinkAmt)
            e.scanA += dt * (40 + 150 * e.listenAmt + 90 * e.thinkAmt)
        }
    }

    // 가끔 깜빡임 (대기 · 말하는 중에만)
    Timer {
        interval: 4200; repeat: true
        running: e.visible && e.mode !== "offline"
        onTriggered: {
            interval = 3500 + Math.random() * 5500
            if (e.mode === "standby" || e.mode === "speaking") blinkAnim.restart()
        }
    }
    SequentialAnimation {
        id: blinkAnim
        NumberAnimation { target: e; property: "blink"; to: 0.06; duration: 70; easing.type: Easing.InQuad }
        NumberAnimation { target: e; property: "blink"; to: 1; duration: 140; easing.type: Easing.OutQuad }
    }

    // 등장 연출: 요소마다 시차를 두고 그려진다 (마지막에 눈이 켜짐)
    property real intro: 0
    NumberAnimation on intro { id: introAnim; from: 0; to: 1; duration: 1900 }
    onVisibleChanged: if (visible) introAnim.restart()
    function clamp01(x) { return Math.max(0, Math.min(1, x)) }
    function ease(x) { x = clamp01(x); return 1 - Math.pow(1 - x, 3) }
    function stage(a, b) { return ease((intro - a) / (b - a)) }

    // ---------------- 색 ----------------
    function rgba(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }
    function tinted(base, k) { return Qt.tint(base, Qt.rgba(e.accent.r, e.accent.g, e.accent.b, k)) }
    readonly property color ringCol: tinted("#ff4b55", tint)
    readonly property color ringHot: Qt.lighter(ringCol, 1.1 + 0.25 * amp)
    readonly property color bandCol: tinted("#c8141f", tint * 0.85)
    readonly property color steel: "#c3cad3"
    readonly property color eyeHot: Qt.tint("#fff4f0", Qt.rgba(e.accent.r, e.accent.g, e.accent.b, 0.22))

    // ---------------- 도우미 ----------------
    function s(v) { return v * e.u }                    // 440 단위 → 화면
    function lw(v) { return Math.max(1, v * e.u) }       // 선 굵기 (최소 1px)
    function pt(deg, rad) { const a = deg * Math.PI / 180; return Qt.point(e.cx + Math.cos(a) * e.s(rad), e.cy + Math.sin(a) * e.s(rad)) }
    function mix(a, b, k) { return Qt.point(a.x + (b.x - a.x) * k, a.y + (b.y - a.y) * k) }

    // 톱니: 안쪽 → 바깥(4.5° 뒤) → 다음 안쪽 (톱날처럼 한쪽으로 기운 이)
    readonly property var sawPts: {
        const out = []
        for (let k = 0; k <= 60; k++) {
            out.push(e.pt(k * 6, 184))
            if (k < 60) out.push(e.pt(k * 6 + 4.5, 196))
        }
        return out
    }
    // 육각형 꼭짓점 (위쪽이 뾰족)
    readonly property var hexPts: [0, 1, 2, 3, 4, 5].map(i => e.pt(-90 + i * 60, 211))

    // =====================================================================
    // 0) 은은한 그림자 + 후광 (밝은 배경화면에서도 읽히도록)
    // =====================================================================
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        opacity: e.stage(0.0, 0.5)
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: e.cx; centerY: e.cy; centerRadius: e.size * 0.5
                focalX: e.cx; focalY: e.cy
                GradientStop { position: 0.0; color: Qt.rgba(0.07, 0.0, 0.01, 0.45) }
                GradientStop { position: 0.80; color: Qt.rgba(0.07, 0.0, 0.01, 0.22) }
                GradientStop { position: 1.0; color: Qt.rgba(0.07, 0.0, 0.01, 0.0) }
            }
            PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.size * 0.5; radiusY: e.size * 0.5; startAngle: 0; sweepAngle: 360 }
        }
    }
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        opacity: e.stage(0.2, 0.9) * (0.35 + 0.35 * e.energy + 0.45 * e.amp + 0.12 * e.breath)
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: e.cx; centerY: e.cy; centerRadius: e.size * 0.5
                focalX: e.cx; focalY: e.cy
                GradientStop { position: 0.0; color: e.rgba(e.accent, 0.0) }
                GradientStop { position: 0.62; color: e.rgba(e.accent, 0.10) }
                GradientStop { position: 0.89; color: e.rgba(e.accent, 0.22) }
                GradientStop { position: 1.0; color: e.rgba(e.accent, 0.0) }
            }
            PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.size * 0.5; radiusY: e.size * 0.5; startAngle: 0; sweepAngle: 360 }
        }
    }

    // =====================================================================
    // 1) 안쪽 어두운 원판 + 삼각 무늬
    // =====================================================================
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        opacity: e.stage(0.05, 0.5)
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: e.cx; centerY: e.cy; centerRadius: e.s(105)
                focalX: e.cx; focalY: e.cy - e.s(30)
                GradientStop { position: 0.0; color: Qt.rgba(0.18, 0.03, 0.05, 0.96) }
                GradientStop { position: 0.85; color: Qt.rgba(0.07, 0.01, 0.02, 0.96) }
                GradientStop { position: 1.0; color: e.rgba(e.ringCol, 0.35) }
            }
            PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(105); radiusY: e.s(105); startAngle: 0; sweepAngle: 360 }
        }
    }
    Item {   // 원판 무늬 (희미하게, 천천히 회전)
        anchors.fill: parent
        opacity: e.stage(0.3, 0.9) * (0.75 + 0.25 * e.energy)
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            rotation: e.aCore
            ShapePath {
                strokeColor: e.rgba(e.ringCol, 0.22); strokeWidth: e.lw(1.2); fillColor: "transparent"
                strokeStyle: ShapePath.DashLine; dashPattern: [3, 2.5]
                PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(94); radiusY: e.s(94); startAngle: 0; sweepAngle: 360 }
            }
            ShapePath {   // 아래로 향한 큰 삼각형
                strokeColor: e.rgba(e.ringCol, 0.15); strokeWidth: e.lw(1.2); fillColor: "transparent"
                joinStyle: ShapePath.MiterJoin
                PathPolyline { path: [e.pt(90, 88), e.pt(210, 88), e.pt(330, 88), e.pt(90, 88)] }
            }
        }
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            rotation: -e.aCore * 0.6
            ShapePath {   // 위로 향한 작은 삼각형
                strokeColor: e.rgba(e.ringCol, 0.11); strokeWidth: e.lw(1); fillColor: "transparent"
                joinStyle: ShapePath.MiterJoin
                PathPolyline { path: [e.pt(270, 66), e.pt(30, 66), e.pt(150, 66), e.pt(270, 66)] }
            }
        }
        Shape {   // 가로 주사선
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: e.rgba(e.ringCol, 0.09); strokeWidth: 1; fillColor: "transparent"
                PathMove { x: e.cx - e.s(100); y: e.cy + e.s(8) }
                PathLine { x: e.cx + e.s(100); y: e.cy + e.s(8) }
                PathMove { x: e.cx - e.s(84); y: e.cy + e.s(56) }
                PathLine { x: e.cx + e.s(84); y: e.cy + e.s(56) }
            }
        }
    }

    // =====================================================================
    // 2) 링 묶음 (발광)
    // =====================================================================
    Item {
        id: rings
        anchors.fill: parent
        layer.enabled: true
        layer.smooth: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: e.accent
            shadowBlur: 0.6
            blurMax: 22
            shadowOpacity: Math.min(1, 0.72 + 0.2 * e.energy + 0.3 * e.amp + 0.1 * e.breath)
            shadowHorizontalOffset: 0
            shadowVerticalOffset: 0
        }

        // ---------- 육각 꺾쇠 (돌지 않고 천천히 흔들림) ----------
        Item {
            anchors.fill: parent
            rotation: e.sway
            Repeater {
                model: 6
                Shape {
                    id: hc
                    required property int index
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    readonly property real p: e.stage(0.05 + index * 0.04, 0.4 + index * 0.04)
                    readonly property point v: e.hexPts[index]
                    readonly property point prev: e.hexPts[(index + 5) % 6]
                    readonly property point next: e.hexPts[(index + 1) % 6]
                    ShapePath {
                        strokeColor: e.ringHot; strokeWidth: e.s(4.5); fillColor: "transparent"
                        capStyle: ShapePath.FlatCap; joinStyle: ShapePath.MiterJoin
                        PathPolyline { path: [e.mix(hc.v, hc.prev, 0.16 * hc.p), hc.v, e.mix(hc.v, hc.next, 0.16 * hc.p)] }
                    }
                    ShapePath {   // 꼭짓점 안쪽의 작은 쐐기
                        strokeColor: "transparent"; fillColor: e.rgba(e.ringCol, 0.8 * hc.p)
                        PathPolyline { path: [e.mix(hc.v, Qt.point(e.cx, e.cy), 0.035), e.mix(e.mix(hc.v, hc.prev, 0.05), Qt.point(e.cx, e.cy), 0.075),
                                              e.mix(e.mix(hc.v, hc.next, 0.05), Qt.point(e.cx, e.cy), 0.075), e.mix(hc.v, Qt.point(e.cx, e.cy), 0.035)] }
                    }
                }
            }
        }

        // ---------- 톱니 링 ----------
        Shape {
            id: saw
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            rotation: e.aSaw
            readonly property real p: e.stage(0.0, 0.55)
            ShapePath {
                strokeColor: e.ringHot; strokeWidth: e.lw(2); fillColor: "transparent"
                joinStyle: ShapePath.MiterJoin
                PathPolyline { path: e.sawPts.slice(0, Math.max(2, Math.ceil(e.sawPts.length * saw.p))) }
            }
            ShapePath {   // 톱니 뿌리 쪽 가는 링
                strokeColor: e.rgba(e.ringCol, 0.45 * saw.p); strokeWidth: e.lw(1.2); fillColor: "transparent"
                PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(180); radiusY: e.s(180); startAngle: 0; sweepAngle: 360 }
            }
        }

        // ---------- 눈금 링 (빛이 훑고 지나감 · 말하면 늘어남) ----------
        Item {
            anchors.fill: parent
            rotation: e.aTicks
            Repeater {
                model: 72
                Rectangle {
                    required property int index
                    readonly property real ang: index * 5
                    readonly property real inner: e.s(160)
                    readonly property real d: ((ang + e.aTicks - e.scanA) % 360 + 360) % 360
                    readonly property real wave: Math.pow(0.5 + 0.5 * Math.cos(d * Math.PI / 180), 10)
                    readonly property real n: 0.5 + 0.5 * Math.sin(e.t * (5 + index % 4) + index * 2.1)
                    width: e.lw(index % 6 === 0 ? 3 : 1.6)
                    height: e.s(index % 6 === 0 ? 14 : 9) + e.amp * (0.35 + 0.65 * n) * e.s(14)
                    antialiasing: true
                    x: e.cx - width / 2
                    y: e.cy - inner - height
                    color: index % 6 === 0 ? e.ringHot : e.ringCol
                    opacity: e.stage(0.12 + index * 0.005, 0.3 + index * 0.005)
                             * Math.min(1, 0.55 + wave * (0.25 + 0.4 * e.energy) + 0.35 * e.amp)
                    transform: Rotation { origin.x: width / 2; origin.y: inner + height; angle: ang }
                }
            }
        }

        // ---------- 칼날 띠 (비스듬한 칼날 6개) ----------
        Item {
            anchors.fill: parent
            rotation: e.aBand
            Repeater {
                model: 6
                Shape {
                    id: blade
                    required property int index
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    readonly property real a0: index * 60
                    readonly property var pts: {
                        const out = []
                        for (let i = 0; i <= 8; i++) out.push(e.pt(blade.a0 + 40 * i / 8, 124))          // 안쪽 가장자리
                        for (let i = 8; i >= 0; i--) out.push(e.pt(blade.a0 + 11 + 40 * i / 8, 151))     // 바깥 가장자리 (앞으로 기울어짐)
                        out.push(out[0])
                        return out
                    }
                    readonly property real lead: Math.pow(0.5 + 0.5 * Math.cos((blade.a0 + 20 + e.aBand - 270) * Math.PI / 180), 6)
                    opacity: e.stage(0.22 + index * 0.05, 0.45 + index * 0.05)
                             * Math.min(1, 0.62 + 0.18 * e.energy + 0.2 * e.amp + 0.25 * lead)
                    ShapePath {
                        strokeColor: e.rgba(Qt.lighter(e.bandCol, 1.7), 0.85); strokeWidth: e.lw(1.2)
                        joinStyle: ShapePath.MiterJoin
                        fillGradient: RadialGradient {
                            centerX: e.cx; centerY: e.cy; centerRadius: e.s(152)
                            focalX: e.cx; focalY: e.cy
                            GradientStop { position: 0.80; color: e.rgba(e.bandCol, 0.5) }
                            GradientStop { position: 1.0; color: e.rgba(Qt.lighter(e.bandCol, 1.5), 0.95) }
                        }
                        PathPolyline { path: blade.pts }
                    }
                }
            }
        }

        // ---------- 강철 호 (반대로 회전) ----------
        Shape {
            id: steelArc
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            rotation: e.aSteel
            readonly property real p: e.stage(0.4, 0.85)
            opacity: Math.min(1, p * 1.5)
            ShapePath {
                strokeColor: e.steel; strokeWidth: e.lw(2.6); fillColor: "transparent"; capStyle: ShapePath.FlatCap
                PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(116); radiusY: e.s(116); startAngle: 200; sweepAngle: 52 * steelArc.p }
                PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(116); radiusY: e.s(116); startAngle: 20; sweepAngle: 52 * steelArc.p }
            }
            ShapePath {
                strokeColor: e.rgba(e.steel, 0.5); strokeWidth: e.s(5); fillColor: "transparent"; capStyle: ShapePath.FlatCap
                strokeStyle: ShapePath.DashLine; dashPattern: [0.25, 0.6]
                PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(116); radiusY: e.s(116); startAngle: 262; sweepAngle: 40 * steelArc.p }
                PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(116); radiusY: e.s(116); startAngle: 82; sweepAngle: 40 * steelArc.p }
            }
        }

        // ---------- 안쪽 밝은 링 ----------
        Shape {
            id: innerRing
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            readonly property real p: e.stage(0.08, 0.55)
            ShapePath {
                strokeColor: e.ringHot; strokeWidth: e.s(5) * (1 + 0.25 * e.amp); fillColor: "transparent"; capStyle: ShapePath.FlatCap
                PathAngleArc { centerX: e.cx; centerY: e.cy; radiusX: e.s(107); radiusY: e.s(107); startAngle: 270; sweepAngle: 360 * innerRing.p }
            }
        }

        // ---------- 생각 중: 칼날 위를 도는 빛 ----------
        Item {
            anchors.fill: parent
            visible: e.thinkAmt > 0.01
            opacity: e.thinkAmt
            rotation: e.aOrbit
            Repeater {
                model: 3
                Rectangle {
                    required property int index
                    width: e.s(9); height: width; rotation: 45
                    color: "#ffd9d0"
                    x: e.cx + Math.cos(index * 2.0944) * e.s(137.5) - width / 2
                    y: e.cy + Math.sin(index * 2.0944) * e.s(137.5) - height / 2
                }
            }
        }

        // ---------- 듣는 중: 바깥으로 퍼지는 파동 ----------
        Repeater {
            model: 2
            Shape {
                id: rip
                required property int index
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                visible: e.listenAmt > 0.01
                readonly property real p: (e.t * 0.6 + index * 0.5) % 1
                opacity: e.listenAmt * Math.sin(p * Math.PI) * 0.7
                ShapePath {
                    strokeColor: e.accent; strokeWidth: e.lw(1.6); fillColor: "transparent"
                    PathAngleArc {
                        centerX: e.cx; centerY: e.cy
                        radiusX: e.s(107 + 108 * rip.p); radiusY: e.s(107 + 108 * rip.p)
                        startAngle: 0; sweepAngle: 360
                    }
                }
            }
        }
    }

    // =====================================================================
    // 3) 두 눈 — 안쪽 끝이 아래로 내려간 날카로운 눈 (강하게 발광)
    // =====================================================================
    Item {
        id: eyes
        anchors.fill: parent
        opacity: e.stage(0.5, 0.95)
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true; shadowColor: e.accent
            shadowBlur: 0.8; blurMax: 24
            shadowOpacity: Math.min(1, 0.55 + 0.45 * e.eyeGlow)
            shadowHorizontalOffset: 0; shadowVerticalOffset: 0
        }
        Repeater {
            model: 2
            Shape {
                id: eye
                required property int index
                readonly property int sx: index === 0 ? -1 : 1
                // 눈 모양 (오른쪽 눈 기준, 중심에서의 거리). 왼쪽 눈은 좌우를 뒤집는다
                readonly property var outline: [[78, -54], [44, -47], [14, -31], [20, -17], [48, -29], [75, -41], [78, -54]]
                readonly property var pts: eye.outline.map(q => Qt.point(e.cx + eye.sx * e.s(q[0]), e.cy + e.s(q[1])))
                // 생각 중에는 양쪽 눈이 번갈아 깜빡이듯 연산
                readonly property real flick: e.thinkAmt * 0.35 * Math.sin(e.t * 9 + eye.index * Math.PI)
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                opacity: Math.max(0.15, Math.min(1, e.eyeGlow + flick))
                transform: Scale { origin.x: e.cx; origin.y: e.cy - e.s(35); yScale: Math.max(0.06, e.eyeOpen * e.blink) }
                ShapePath {
                    strokeColor: e.rgba(e.accent, 0.95); strokeWidth: e.lw(2.2)
                    joinStyle: ShapePath.MiterJoin
                    fillGradient: LinearGradient {
                        x1: e.cx; y1: e.cy - e.s(54); x2: e.cx; y2: e.cy - e.s(17)
                        GradientStop { position: 0.0; color: e.eyeHot }
                        GradientStop { position: 0.55; color: Qt.lighter(e.accent, 1.25) }
                        GradientStop { position: 1.0; color: e.accent }
                    }
                    PathPolyline { path: eye.pts }
                }
            }
        }
    }

    // =====================================================================
    // 4) 워드마크 ULTRON (금속 질감 + 발광)
    // =====================================================================
    Item {
        id: wm
        readonly property real p: e.stage(0.55, 1.0)
        readonly property real px: Math.max(9, e.s(30))
        anchors.centerIn: parent
        anchors.verticalCenterOffset: e.s(30) - (e.voiceBars ? 4 : 0)
        width: wmText.implicitWidth; height: wmText.implicitHeight
        opacity: p
        transform: Scale {
            origin.x: wm.width / 2; origin.y: wm.height / 2
            xScale: e.s(168) / Math.max(1, wm.width) * (0.94 + 0.06 * wm.p)
            yScale: 0.94 + 0.06 * wm.p
        }
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true; shadowColor: e.accent
            shadowBlur: 0.6; blurMax: 14
            shadowOpacity: Math.min(1, 0.45 + 0.35 * e.amp + 0.12 * e.breath)
            shadowHorizontalOffset: 0; shadowVerticalOffset: 0
        }
        Text {
            id: wmText
            text: "ULTRON"
            font.family: "Bahnschrift"; font.weight: Font.Bold; font.pixelSize: wm.px
            font.letterSpacing: wm.px * 0.32
            color: "#ffffff"
        }
        Item {   // 글자 아래쪽 절반은 차가운 강철색 — 금속 반사 느낌
            readonly property real split: wmText.baselineOffset - wmText.font.pixelSize * 0.34
            y: split
            width: wmText.width; height: wmText.height - split
            clip: true
            Text {
                y: -parent.split
                text: wmText.text
                font: wmText.font
                color: "#a3abb6"
            }
        }
    }

    // 음성 파형 (전체 모드)
    Row {
        visible: e.voiceBars
        anchors.horizontalCenter: parent.horizontalCenter
        y: e.cy + e.s(62)
        height: 14
        spacing: 2.5
        opacity: e.stage(0.7, 1.0)
        Repeater {
            model: 13
            Rectangle {
                required property int index
                readonly property real prof: Math.exp(-Math.pow((index - 6) / 3.6, 2))
                readonly property real n: 0.5 + 0.5 * Math.sin(e.t * (6 + index % 5) + index * 1.7)
                readonly property real idle: 0.12 + 0.08 * Math.sin(e.t * 2.0 + index * 0.6)
                width: 2.5; radius: 0
                height: Math.max(2, 14 * Math.min(1, idle + e.amp * prof * (0.4 + 0.6 * n) * 1.5))
                anchors.verticalCenter: parent.verticalCenter
                color: index === 6 ? "#ffffff" : e.ringCol
                opacity: 0.5 + 0.5 * prof
            }
        }
    }
}
