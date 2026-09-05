# Reference / Human / Calibration Evidence Protocol

更新：2026-09-05
状态：`ACTIVE_AUTHORITY`

## 1. Reference record 最小字段

```text
vehicle_id
scenario
source_id / recording_session_id
audio_path + sha256
start_s / end_s
evidence_level
rights_status
microphone/recording metadata
speech_music_contamination
optional synchronized rpm/load/gear
```

## 2. Stage AD optimizer input

默认只使用项目 canonical `ReferenceCaseSet` / registry 中已治理的 BOUND case。Rejected/speech-contaminated 不进入。

公网 extractor 输出的片段：

```text
R3_PRIVATE_DIAGNOSTIC_ONLY
human A/B allowed when explicitly authorized
optimizer default = FORBIDDEN
R1/R2 promotion = FORBIDDEN without new evidence record
redistribution/product asset = FORBIDDEN by default
```

## 3. Closed-loop receipt

每轮至少记录：input config SHA、参数中心/范围、候选 overrides、hard gates、fixed `absolute_reference_distance`、candidate PCM receipt、audition manifest。跨轮停止只使用固定 reference ruler，不比较 changing-parent improvement 当作同一标尺。

## 4. Blind Human protocol

正式盲听：raw feedback → SHA → manifest verify → reveal → binding receipt。反馈前不得修改/覆盖官方 package。

Stage AD non-blind diagnostic package 必须另建目录，并标 `diagnostic only`。

## 5. Promotion protocol

```text
software verified
→ acoustic/reference evidence
→ Human accepted
→ Engineering Profile
→ product package
```

R1 是独立更高等级：没有 R1 不能称 OEM calibrated/Profile Freeze。
