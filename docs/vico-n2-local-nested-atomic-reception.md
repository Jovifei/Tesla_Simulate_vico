# N2 Source/Renderer 嵌套恢复本地修复 · 2026-10-02

现有Source与Renderer虽然校验外层snapshot，子queue失效时仍会先改写baseline/live source。两项真实回归均RED：非法future queue后baseline scalars变化、后续PCM与twin不一致。

最小修复：既有restore主体保留为private applySnapshot；public restore先在同identity disposable实例上完整apply，全部子校验通过才apply到live。无递归公共restore调用；冻结s15/s17/s18类未修改。

两项回归GREEN，完整build/test通过；删除两个未接入、无引用的callback-only事务wrapper，保留真实恢复路径测试。新增profile/frame状态不会因失败snapshot隐式前进。

N2仍未objective/held-out评估或安装。校准、事件能量、真实参考导出/driver、预算锁与630-case回归继续由远端完成，此修复不等于声学资格。
