import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.ultron.assistant",
  appName: "ULTRON",
  webDir: "dist",
  backgroundColor: "#0b0204",
  plugins: {
    // 화면 맨 위 · 아래(상태 표시줄 · 내비게이션 바) 높이를 --safe-area-inset-* CSS 변수로 넘겨받는다
    SystemBars: { insetsHandling: "css", initialViewportFitValueHint: "cover", style: "DARK" },
    LocalNotifications: { iconColor: "#ff2d3f" },
  },
};

export default config;
