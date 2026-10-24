# Vehicle instruments R3 — design and verification contract

Jovi requested vehicle-specific instrument character after c443e08. Original 音浪 ChatGPT returned a read-only PLAN (11m05s), confirmed Tesla_speed and the real six-car catalog; no remote parallel writes.

## Design / implementation plan

- Actual catalog IDs select immutable display profiles in cockpit.js. C63 center-speed triple housing; Hellcat equal deep twin dials; 458 center yellow mechanical tach and digital speed; LFA precision single digital tach arc and central gear; R35 offset large tach, small left speed and right rectangular information; Supra amber center-tach three-pod hierarchy.
- Original design, not factory reproduction. BMW was an example of instrument identity; no BMW bank/model/logo added. Speed scales 280/320/340 are display choices, not original car performance claims; model ceiling and input are unchanged.
- Shared unique speed/rpm/gear/load nodes retain real Worklet telemetry. Only cockpit owns graphical normalization; app continues numeric/owner/control duties. Engine core/session/worklet/appearance and all banks untouched.
- Major/minor ticks use integer physical intervals; exact catalog redline is separate from display maximum. Full mechanical needles/hubs except the LFA digital ring. SVG faces and needles share coordinates to avoid mobile ellipse/misalignment.
- Keep existing touring storage identifier for backward compatibility, but label it 车型仪表 and automatically choose geometry by ID; digital remains an explicit alternative. No new route/audio/GPS access in display component.

## Verification

- RED: old code failed new ID mapping and real marks/redzone tests. Separate RED exposed an invisible red sector at exact integer-thousand redlines. Raw receipts retained outside Git under E:/Tesla_speed/reports/vico-web-0cb610e8/r3-*.tap.
- GREEN precommit: Node62/62, zero failures/skips. Real six-bank preview (dirty, catalog parent c443e08, explicitly NOT final release) Chrome6 models x2 themes x4 viewports48 screenshots and real Worklet continuity passed. Manual screenshot inspection found and corrected mobile decorative face misalignment and low-height Ferrari speed footer crowding.
- Final acceptance must rebuild from clean committed SHA; verify manifest/protected118 hashes; run Chrome and Edge vehicle matrix, existing cockpit and lifecycle regression. Native/browser software proof is distinct from physical Tesla/human audition.
- Scope: vico_web only. No main merge, force-push, Android, original WAV/gain, fitting/MATLAB/ADB. Public release reuses existing own-domain versioned static deployment with retained rollback.

## Read-only references

Original ChatGPT plan cites official Lexus LFA single-dial design: https://media.lexus.co.uk/lexus-lfa/ . Reference describes layout inspiration; no external images or assets copied.

Final SHA-bound receipts and deployment status are reported outside source in R3-VEHICLE-INSTRUMENTS.md. This source document records the design and precommit evidence only.
