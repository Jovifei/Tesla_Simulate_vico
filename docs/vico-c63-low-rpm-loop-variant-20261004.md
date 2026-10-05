# C63 低转循环接缝版本化候选

状态：未发布、未安装的工程候选；声学数值基线 PR37 7bf34080。产品接入叠加在独立 SESSION_START 提交 3e76f0d702db85f4f82d048e2cdc474a11a6e73e 上，保留其日志修复。

## 范围和隔离

只增加 `live_loop_variants/c63_low_rpm_preroll_v1` 下的700/1400 RPM × .32/.92四个loop。2200及以上12个loop、4个事件文件、其他五车型、原 `s12_v10` 和 `s13_review_v1` 文件均不修改。原source、固定PTR、一个车型统一gain、齿比、原period17280/48000=0.36秒不改变。1400–2200插值边界含一层新、一层旧，已单独检查，不把覆盖范围说成所有转速。

`MatlabV6SoundBankEngine`的reference/cache/controller读取原bank。普通renderer才应用严格校验的四loop overlay；overlay不修改原bank对象或数组。S13准备直接加载原cache，AudioEngine的S13入口不先要求normal overlay成功；其采样率仍为S13固定48k。普通声库未就绪时不能启动普通声音；失败不会冒称候选已加载。S14/S15的数值声学代码不变。

`manifest.properties`为固定ASCII/LF合同，整个manifest SHA以及原manifest、新旧WAV SHA均检查；仅允许已审四坐标、48k、17280 samples、有限量和原峰预算。它不接受通用Properties转义、重复或未知键。普通bank版本在UI状态与本地记录profile身份中可见；它不是道路/物理输出的通过标记。

## 方法

原导出器head crossfade仍保留尾部，wrap会跳回尾8ms的起点。新离线方法取N+M的原始pre-loop：body=x[M:-M]，尾部使用末M与前滚M的cosine混合，输出body+cross为N样本。两接点连接原相邻样本；大部分主体相位和原周期保留。新旧DC均按明确float32口径记录，非有限DC/结果直接拒绝，gain后峰超限直接拒绝。

不是对已错误处理的bank二次修饰，不是全局低通、clip或逐loop等响归一化。旧source共振、高转相消与缺少真实coast素材属于其他问题。

## 数值证据

[机器可读证据](../review_packages/vico-input-loop-20261004/evidence.json)记录来源版本、失败候选和限定范围结果：55组/1404万frames，整体RMS变化0至+.1184dB，最大逐同窗谷退化.14923dB、干涉变化.12049dB，均在保持的.5dB工程保护范围内。1400–2200边界三load同窗退化.0904–.1205dB。

33个2200+恒定case完整PCM SHA不变；6,175,386个仅高RPM源参与的capture帧bitexact；4条drive的巡航段和旧6919RPM反例窗、8个事件邻域PCM不变。实际renderer最大preClipPeak .667629，hardClip/aboveContract/nonFinite均0。

这些是探索后保护检查，不冒充先验声学资格或人耳通过。原全域候选的高转反例和Supra峰失败保留，不用窄候选通过去抹除。

## 可复现命令

使用仓库现有SHA固定JVM依赖和NumPy环境，无新依赖安装：

```bash
python -m unittest discover -s vico_app/tools/python -p 'test_loop_preroll.py' -v
python -m unittest discover -s vico_app/tools/python -p 'test_live_loop_variant_wiring.py' -v
python vico_app/tools/python/generate_c63_live_loop_variant.py --repo . --output-dir /tmp/vico-low-rpm-new-output
# 输出目录必须事先不存在，且不能位于原bank内。
diff -qr /tmp/vico-low-rpm-new-output vico_app/Project/android/app/src/main/assets/live_loop_variants/c63_low_rpm_preroll_v1
python vico_app/tools/python/run_sensor_jvm_tests.py --deps "$PINNED_JVM_DEPS" --build-dir "$NEW_EMPTY_TEST_DIR"
# 55场景重放约生成230MiB；output目录须新建，variant可用reference或以下限定版本。
python review_packages/vico-input-loop-20261004/replay/run_replay.py --repo . --deps "$PINNED_JVM_DEPS" --output-dir /tmp/vico-low-rpm-replay --variant c63_low_rpm_preroll_v1
```

生成器直接调用原C63 source/各layer/frozen PTR，先要求四个旧loop逐sample重建一致，再生成新loop并要求最终manifest身份一致。仅构造namespace以避开无关导出器依赖；不替换DSP函数，不读取私有WAV。输出只写新目录，原bank不动。

Android真实编译、`LiveLoopVariantTest`、`LiveLoopReferenceIsolationTest`、lint和APK由精确提交CI验证；云端分离JVM/数据类抽取探针不能代替Android外壳验证。手机仍需main-compatible完整manifest、同签名保数据安装、静置DEMO同参数回放/日志、单独人耳反馈。未获得实际现场声音，不能断言已排除所有0.5–0.6秒点声。

经验与剩余任务见[问题经验记录](07-debugging/03-vico-input-and-loop-click-lessons-20261004.md)。
