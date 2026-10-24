# Vico R4 · Original factory-inspired display stage

Target: Jovifei/Tesla_Simulate_vico PR39 only, parent `10d619e24b502936016a152d8743d7e204b22519`.

## Real reference grounding (visual inspiration, not cloned OEM art)

- Mercedes C-Class / C63 W204: 2010 Mercedes US C-Class owner manual shows left combination gauge, **central speedometer** and **right tachometer**. https://www.mbusa.com/mbrace/vcm/MB/DigitalAssets/pdfmb/ownersmanual/2010_c.pdf
- BMW M traditional cluster: official BMW Group 2020 X3 M materials describe **classic circular instruments, white illumination, red needles and digital speed**. https://www.press.bmwgroup.com/usa/article/detail/T0291875EN_US/the-first-ever-2020-bmw-x3-m-and-bmw-x4-m
- Audi Virtual Cockpit (2014): official tech portal describes **two modes**, classic larger circular gauges versus small side instruments around central content. https://www.audi-technology-portal.de/en/electrics-electronics/controls/new-control-and-display-concepts
- VW Golf GTI Digital Cockpit (2024): official newsroom describes **central round rev counter and prominent digital speed** in the GTI profile. https://www.volkswagen-newsroom.com/en/the-new-golf-gti-and-golf-gti-clubsport-18404/the-gti-interior-with-completely-new-infotainment-system-18407
- Honda S2000 original cluster: Honda News describes **semicircular 100-rpm tach segments with digital speed below**; this is the digital bar layout inspiration. https://hondanews.com/en-US/releases/release-40de5c8eb2551628d3183c004c34c871-honda-s2000-interior

Preference evidence is **anecdotal**, not a poll: r/cars (Jan 2025), r/Audi (Apr 2024) and S2KI enthusiasts discuss analog readability versus well-integrated digital clusters. These self-selected discussions cannot establish majority preferences. https://www.reddit.com/r/cars/comments/1ie5uhw/ , https://www.reddit.com/r/Audi/comments/1cdyna3/ and https://www.s2ki.com/forums/s2000-talk-1/gauge-cluster-love-237567/ . Therefore Vico offers multiple layouts rather than asserting a universal winner.

## Product architecture

- **Sound identity** is only the selected six-bank catalog entry (unchanged IDs and hashes). BMW, Audi, VW, Honda are **display-only selections**; they never create or rename sound banks.
- `vico-web-display-style-v1`: `auto` / `mercedes` / `bmw` / `audi` / `vw` / `honda`, localStorage best-effort. `auto` preserves six independent original layout ideas: C63/mercedes, Hellcat/muscle, 458/maranello, LFA/precision, R35/technical, Supra/heritage. Existing `vico-web-cluster-v1` (车型仪表 vs 数字) and two color themes remain independent.
- One live DOM stage: SVG `viewBox=0 0 1200 340`, all ticks, needles, large speed/RPM/gear and load under the same coordinate system. No standalone visual clock, startup sweep, substitute PCM or fake fuel/temperature/boost values. Physical tick marks use actual display value intervals, red sectors use the selected **real catalog `redlineRpm`**, and graph saturates without altering numeric model stats.
- `src/factory-display.js` renders only. Existing `src/cockpit.js` delegates prepare/update to it when available, retaining old math path for old unit fixtures; **single AudioSession and original app owner** remain untouched. App's existing `speed/rpm/gear/load/redline-rpm/rpm-arc` IDs remain unique. Hidden legacy `rpm-arc` is deliberately present to preserve compatibility with the existing app event writer; R4 needle values remain independently driven by the actual stats.
- User may choose style during playback. Change does not call start, stop, network or GPS. On invalid/stop the stage clears current values, unloads active bar and blanks needle demand; historic run diagnostics stay scoped to their actual bank.

## Visual collision regression

Local native review reproduced the initial overlap and stopped GPS regression (35 failed display checks at1896438). The integrated correction repositions readouts and their unit labels, removes opaque value plates, and retains every physical major scale numeral rather than culling labels. Honda shows all0–10 labels above its bar; stopped unauthorized GPS stays unknown through style and layout changes. Status metadata occupies a dedicated header and invalid input hides live needle demand. Native regression covers both themes, touring/digital and three critical viewports with explicit injected-display-only scope; actual six-bank Worklet evidence is separate.

## Honest verification and local handoff

Remote sandbox cannot navigate localhost (`ERR_BLOCKED_BY_ADMINISTRATOR`), so any local `page.set_content` screenshots are **offline visual geometry samples**, not browser AudioWorklet evidence. No policy was weakened. Independent CI runs Node and six-bank assembly, but Windows local Codex must fetch the **exact Git SHA** into the existing isolated worktree, rebuild from fixed source commit, verify protected 118 files against parent, and run full actual Chrome/Edge smoke, lifecycle, `browser_cockpit_review.py`, `browser_vehicle_instruments.py` and the new `browser_factory_review.py`. No skips/empty outputs PASS. Verify 1440×900 / 1280×720 / 1280×600 / 1024×600 / **1010×1270** / 390×844 for major-value size and stop hit-test. Only then versioned public publish with retained rollback; check shared host disk capacity before uploading. Do not touch main/Android/owner WAV, existing Nginx/DNS or original audio sources.

Physical Tesla screen/audio, Bluetooth, road GPS and human audition remain `NOT_RUN` / `NOT_EVALUATED`. OEM look-alike fidelity and sound equivalence are **not claimed**.
