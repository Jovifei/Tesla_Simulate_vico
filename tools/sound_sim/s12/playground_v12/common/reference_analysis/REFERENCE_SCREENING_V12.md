# S12 v1.2 Eight-Vehicle Reference Screening Register

Status: `NOT_CALIBRATION_READY` (2026-07-30)

This register separates manufacturer identity evidence from candidate media.
Every candidate below is `R2` (listening-only) or `R3` (rejected); none is
an R1 calibration reference, no candidate has produced an acoustic target, and
no candidate may influence a synthetic tuning parameter.

R1 needs all of the following for the exact frozen vehicle baseline:

1. explicit year/market/trim identity;
2. explicit stock-exhaust confirmation;
3. exterior-rear recording perspective; and
4. a continuous RPM trace or at least three ordered, synchronized RPM anchors
   covering the analyzed clip.

| Vehicle | Identity evidence only | Candidate media | Status and missing R1 evidence |
| --- | --- | --- | --- |
| 2022 Challenger SRT Hellcat | [Dodge fact sheet](https://www.dodgegarage.com/news/article/press-room/2021/09/2022-dodge-challenger-challenger-srt-fact-sheet) | [AutoTopNL Charger candidate](https://www.youtube.com/watch?v=eyzGRhXp0do) | `R3`: title identifies a Charger rather than the frozen Challenger baseline. |
| 2007 Nissan GT-R R35 | [Nissan Heritage](https://www.nissan-global.com/EN/HERITAGE_COLLECTION/418_nissan_gt-r.html) | [stock-claimed acceleration / POV](https://www.youtube.com/watch?v=zRWKDKn8TTw); [R35 start/revs/acceleration](https://www.youtube.com/watch?v=7HhjgbIuVBQ) | `R2`: no verified 2007 trim, exterior-rear microphone position, or RPM anchors. |
| 2011-2014 C63 AMG W204 facelift | [Mercedes-Benz archive](https://mercedes-benz-publicarchive.com/marsClassic/en/instance/ko/C-63-AMG-2011---2014.xhtml?oid=189266534) | [stock-claimed throttle clip](https://www.youtube.com/watch?v=RcrwF3MEbDs); [W204 raw exhaust clips](https://www.youtube.com/watch?v=FGiWAWD4SsU) | `R2`: facelift/body/market, exterior-rear, and RPM evidence remain unverified. [Modified C63 counterexample](https://www.youtube.com/watch?v=KNOCYABG750) is `R3`. |
| 1993 Supra JZA80 RZ | [Toyota launch record](https://global.toyota/en/detail/7868203) | [full-stock-claimed external-mic acceleration](https://www.youtube.com/watch?v=nUugsfQ9PMA); [2JZ comparison](https://www.youtube.com/watch?v=L3zXs-om-LY) | `R2`: 1993 RZ identity, clean exterior-rear perspective, and RPM evidence remain unverified. [State-uncertain 1993 review](https://www.youtube.com/watch?v=2XuqyTP-o_g) is `R3`. |
| 1991 RX-7 FD | [Mazda history](https://www.mazda.com/en/about/history/1990-1999/) | [13B twin-turbo candidate](https://www.youtube.com/watch?v=Thh69Wc5uco) | `R2`: exact 1991 market/trim, stock exhaust, exterior-rear perspective, and RPM anchors are unverified. |
| Lexus LFA | [Toyota/Lexus launch record](https://global.toyota/en/detail/308263) | [exhaust-proximate acceleration/downshift candidate](https://www.youtube.com/watch?v=F0m6dvpK4m8); [full-acceleration candidate](https://www.youtube.com/watch?v=bpv7N8smafY) | `R2`: exact year/market, stock confirmation, and synchronized RPM evidence remain unverified. |
| Ferrari 458 Italia | [Ferrari model record](https://www.ferrari.com/en-EN/auto/458-italia) | [AutoTopNL acceleration candidate](https://www.youtube.com/watch?v=X0yiRilcKME) | `R2`: stock state, controlled exterior-rear position, and RPM anchors are unverified. |
| 2011 Aventador LP700-4 | [Lamborghini configuration record](https://www.lamborghini.com/en-en/news/end-of-an-era-with-the-last-lamborghini-aventador) | [iPE-versus-stock comparison](https://www.youtube.com/watch?v=Va166TfTP5A) | `R3` for stock calibration: the clip is an aftermarket-versus-stock comparison and has no verified 2011 vehicle identity or RPM anchors. |

## Cross-vehicle listening-only context

- Jovi supplied [Novitec Ferrari 812 GTS V12 POV](https://www.youtube.com/watch?v=1fzUnAUarNI) on 2026-07-30. Search metadata identifies a 812 GTS with an aftermarket Novitec exhaust and a driver-seat/near-cabin perspective. It is `R2` only: a different Ferrari model, non-stock exhaust, non-exterior-rear microphone position, and no synchronized RPM/load trace. It cannot calibrate the stock 458 profile or any frozen v1.2 vehicle; it may only inform later human audition vocabulary for a high-rev V12 character.

## Required next evidence

For each vehicle, a human reviewer must verify the candidate itself (not merely
its title) and record the exact clip interval, vehicle identity, stock proof,
microphone perspective, RPM trace/anchors, and permitted research use. Only
then may its original media be placed under the external raw-media root and
be represented by an R1 manifest. Copyrighted audio, decoded PCM, media cache,
and media hashes are intentionally not stored in this repository.
