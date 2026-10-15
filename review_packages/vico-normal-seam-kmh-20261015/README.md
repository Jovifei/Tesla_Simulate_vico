# Normal seam softening and km/h, 2026-10-15

Normal playback uses `NORMAL_CANONICAL_SEAM_V1`: fixed H=8source-sample raised-cosine corrections at the original loop's last-sample and wrapped-zero slope junctions. The original modulo clock and interpolation weights remain; there is no random grain or permanent phase offset. Original WAV, gain, events and the default S13 renderer remain frozen. Unsupported short loops are diagnosed and left canonical. The normal renderer algorithm is logged separately from bank identity.

Android upgrades use a new native `display_unit` authority. Missing/invalid legacy preferences display km/h; existing user data and legacy values remain. Future explicit mph/kmh changes persist through the same bridge across all four screens. Internal vehicle speed units remain km/h.

Local evidence is imported by Codex /root from the actual cd1bab58 reception tree, not hosted CI. See `review_packages/vico-normal-seam-kmh-20261015/verification.json`: realbank48/48RMS/peak,12REAL-synthetic40s and6actualDEMO80s cases pass, originalS13 six30s references bitexact; Android512total483PASS29SKIP0FAIL/lint/APKPASS, Python155PASS2Windows-symlinkSKIP, JS31PASS, source-extractednativeunitJVM4PASS. Runtime/instrumented phone and human qualification remain pending.

This is **SEAM_ONLY**. C63 3000/6232RPM seam d2max falls about74–86%, but 910RPM .553846s slow texture remains (absolute1.6–2.1Hz power ratios.999963/.999987, not25% improvement). Some local junction windows/HF have negative controls despite lower globald2max; allrecords retained. No full half-second periodicity or all-cars acoustic fix is claimed. Earlier random/shared-cycle diagnostic variants failed the originalRMS guard and are not enabled.

Local APK SHA256 `b620ef8a38b23724396de32cf5a433cb24f3e12cfc5d40a3c1c25222bf707d36`, AndroidDebug certificate `9ab144e824abf26a5941819abb06831288c36a8bfe622657e3dc9d88281fc774`, packagecom.vico.simulator/versionCode1/versionName1.0. Jovi audition packet is outsideGit at E:/Tesla_speed/review_packages/periodicity-seam-kmh-20261015. No install/clear/uninstall/mainmerge performed.

The complete REA public website analysis was actually read/hashverified in the same ChatGPT chat. Website regrain/long fades motivated diagnostic work; final minimal slope correction was planned there and implemented locally. No website code/audio copied, login-only driving behavior unverified, no MATLAB or source-fitting budget used. Future slow-texture work needs its own evidence and must preserve the current failed-target record.
