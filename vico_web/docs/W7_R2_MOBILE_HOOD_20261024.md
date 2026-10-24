# W7 R2 — Compact 390px inner-hood repair (2026-10-24)

## Fixed identity and scope

- Repo: \`Jovifei/Tesla_Simulate_vico\`, existing PR39, branch \`codex-web-vico-lab-20261015\`, base \`codex-remote-stage-20261011-integration\`. **Not main.**
- Repaired from \`0c3620476bcc905e98ddf4e984c9400eca7ee82c\`, after native Windows Chrome/Edge reception. The published site remains on the prior \`0822de48\` release; this remote stage does not deploy.
- Only \`vico_web/src/factory-display.js\` and targeted test/receipt files changed relative to this repair baseline. No changes to production \`app/session/core/worklet/appearance\`, six banks, gain, Android or server.
- Real Chrome/Edge old receipt location: \`reports/vico-w7-0c362047/MOBILE-HOOD-RED.md\`, \`chrome-w7/receipt.json\`, \`edge-w7/receipt.json\` in Tesla_speed workspace. Original screenshots remain there. These local files are **not** part of the remote code branch.

## Preserved RED

- On \`0c362047\`, Chrome & Edge each had **12/12** mobile 390×844 auto-vehicle/theme snapshots with bottom metadata outside the inner hood. In Chromium, baseline hood bottom 615.2306px and load label bottom 619.1256px (≈3.895px intrusion), with similar Edge result.
- Regression added in commit \`53523ed25f17ae1386d9d7f2427a43a84d4840c8\`; strict 390px W7 hood assertion added in \`c94ac8adb9b489e872af06f3919af827db60d340\`.
- [GitHub RED CI 40057995369](https://github.com/Jovifei/Tesla_Simulate_vico/actions/runs/40057995369): actual Node **87 tests, 86 PASS, 1 FAIL, 0 SKIP**, with failure \`c63_w204_v6 load labels touch hood: 393,393,393\`. No failed assertion removed or threshold lowered.

## Narrow GREEN source change

- \`factory-display.js\` makes \`load(x,y,width,labelOffset=28)\` backward compatible; **noncompact default remains 28**, preserving all desktop SVG geometry.
- Compact \`load(23,365,150)\` becomes \`load(23,359,150,22)\`. This raises the bar by 6 SVG units and the labels by 12, without intersecting the gear unit above.
- Compact redline label moves \`redline(262,389)\` to \`redline(262,381)\`, aligning text on the same lower row, preserving actual car redline and units. Complete RPM segments, full scales, displayed speed/gear, GPS unknown and stop remain untouched.
- W7 test now asserts \`belowHood\` at **every size including 390×844**, no special exemption. For 390 it also checks a **minimum 8px gap** between percent and REDLINE labels; all other stop, 64/44px, collisions, bank/runId and real-Worklet requirements remain.

## Measured evidence and limits

- On the actual frozen HTML/CSS with modified renderer, sandbox Chromium \`page.set_content\` static-layout reproduction: for **all 6 automatic profiles × 2 themes at 390×844**, inner hood bottom 615.23px, load/redline caption bottoms 608.39px, ~6.84px inside; percent right 171.10px, REDLINE left 188.44px, ~17.34px gap, with no collisions. Meter/gear unit and load bar no longer intersect.
- Strict **1320/1320** sandbox Chromium layout cases across six cars plus five display presets, themes, layouts, 1440×900/1280×720/1280×600/1024×600/1010×1270/390×844, and five injected value conditions: **0 failures**. This is **offline display injection only, not a real AudioWorklet/browser navigation qualification**.
- [Green CI 40058106029](https://github.com/Jovifei/Tesla_Simulate_vico/actions/runs/40058106029) at \`e8778701b29352f640cb56d787105c13ab33ad07\`: **87/87 PASS, 0 FAIL, 0 SKIP**; Python browser test syntax checked; actual six-bank build \`testOnly=false\`, 126 hashed files. Archive verified 126/126 hashes; 118 original frozen bank/core/appearance items unchanged.
- The final PR-head's CI may have a new run ID due to this receipt-only commit; inspect its completed result rather than assuming inheritance.
- Native Windows Chrome/Edge W7/geometry/motion/factory/lifecycle and final public-domain changes are **NOT_RUN** for the new SHA until local Codex independently reaccepts it. Physical Tesla, device IMU, road GPS, speakers/Bluetooth, acoustics and human audition remain NOT_RUN/NOT_EVALUATED.

## Local reacceptance stop gate

From final exact GitHub SHA in a new isolated worktree, build a **new empty real-six-bank** dist and validate all SHA. Run Node and native Chrome/Edge \`browser_w7_instruments.py\` (strict mobile bottom+gap; 56 screenshots), \`browser_atelier_review.py\` (1345 geometry), \`browser_motion_review.py\` (injected IMU with real Worklet), \`browser_factory_review.py\` (6 real cars+5 presets/112 screenshots), \`browser_smoke.py\`, and \`browser_lifecycle.py\` (33 each). Read screenshots for C63 minimal and Supra cyber mobile first, and confirm no stop obstruction. New SHA must have 0 failure and 0 skip; old 0c's green browser receipts do not qualify the new build. Keep 0822 public release and rollback, do not auto-deploy.

This package is a **completed remote source repair and CI handoff**, not a device/human/public release approval.
