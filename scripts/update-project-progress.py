"""Generate both project views from the evidence ledger; --check detects drift."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'DONE', 'ACTIVE', 'PARTIAL', 'BLOCKED', 'FAILED', 'NOT_STARTED', 'PENDING_HUMAN', 'NOT_RUN'}


def validate(data, root=ROOT):
    phases = data['phases']
    ids = [p['id'] for p in phases]
    assert len(ids) == len(set(ids)), 'duplicate phase'
    assert data['current_phase'] in ids, 'unknown current phase'
    assert all(p['weight'] > 0 for p in phases) and sum(p['weight'] for p in phases) == 100, 'weights must sum to 100'
    seen = set()
    for phase in phases:
        assert phase['milestones'], 'empty phase'
        assert all(d in ids and d != phase['id'] for d in phase['dependencies']), 'invalid dependency'
        for milestone in phase['milestones']:
            assert milestone['id'] not in seen, 'duplicate milestone'
            seen.add(milestone['id'])
            assert milestone['status'] in STATUSES, 'invalid status'
            if milestone['status'] == 'DONE':
                assert milestone['evidence'], 'DONE requires evidence'
            for evidence in milestone['evidence']:
                path = (root / evidence).resolve()
                assert path.is_relative_to(root.resolve()) and path.is_file(), 'missing or external evidence: ' + evidence
    def visit(node, trail):
        assert node not in trail, 'dependency cycle'
        for dep in next(p for p in phases if p['id'] == node)['dependencies']:
            visit(dep, trail | {node})
    for node in ids:
        visit(node, set())


def percentage(phase):
    return 100 * sum(m['status'] == 'DONE' for m in phase['milestones']) / len(phase['milestones'])


def bar(value):
    count = int(value / 5)
    return '█' * count + '░' * (20 - count)


def render(data):
    phases = data['phases']
    total = sum(p['weight'] * percentage(p) / 100 for p in phases)
    header = f"更新：{data['updated_at']} · 主线：{data['current_phase']} · 工作包：{data['current_work_package']}\n\n"
    policy = ('本文件由 `scripts/update-project-progress.py` 从 `docs/project-ledger.json` 生成，不直接编辑。\n\n'
              '进度只计有证据的 DONE 里程碑；阶段内等权，再按阶段权重汇总。它不是工时、声音相似度或测试通过率。'
              '部分完成、失败、阻塞和待试听均不计完成；证据被推翻可回退。权重为规划口径，调整必须说明原因。\n\n')
    dashboard = '# 项目进度总览\n\n' + header + policy
    dashboard += f"工程里程碑进度：**{total:.1f}%** `{bar(total)}`。声音产品尚未完成。\n\n"
    dashboard += '| 大阶段 | 权重 | 完成里程碑 | 阶段进度 |\n|---|---:|---:|---:|\n'
    for p in phases:
        n = sum(m['status'] == 'DONE' for m in p['milestones'])
        dashboard += f"| {p['id']} {p['title']} | {p['weight']}% | {n}/{len(p['milestones'])} | {percentage(p):.1f}% |\n"
    dashboard += '\n## 当前阻塞与下一步\n\n' + '\n'.join('- ' + b for b in data['blockers']) + '\n\n'
    dashboard += next(p['next_action'] for p in phases if p['id'] == data['current_phase']) + '\n\n'
    dashboard += '## 六车型新连续算法资格（原声库不等于新算法交付）\n\n| 车型 | 实现 | 声学资格 | 新版手机交付 | 人耳 |\n|---|---|---|---|---|\n'
    for v in data['vehicles']:
        dashboard += '| ' + ' | '.join(v[k] for k in ['name', 'continuous', 'acoustic', 'device', 'human']) + ' |\n'
    roadmap = '# 项目总体路线图\n\n' + header + policy + data['scope'] + '\n\n'
    roadmap += ('远端 ChatGPT 负责规划与独立审核，本地 Codex 负责修改、命令、测试、产物与安装；Jovi负责具名试听与产品接受。'
                '阶段可并行准备，但依赖门未通过不能宣称下游最终资格。HY1 是 P2 内工作包，不另算大阶段。\n\n')
    for p in phases:
        roadmap += f"## {p['id']} {p['title']}（{p['weight']}%）\n\n{p['goal']}\n\n依赖：" + ('、'.join(p['dependencies']) or '无') + '\n\n实施步骤：\n\n'
        roadmap += '\n'.join(f'{i}. {s}' for i, s in enumerate(p['steps'], 1)) + '\n\n交付物：\n\n'
        roadmap += '\n'.join('- ' + s for s in p['deliverables']) + '\n\n退出门：\n\n'
        roadmap += '\n'.join('- ' + s for s in p['acceptance']) + '\n\n当前里程碑：\n\n'
        for m in p['milestones']:
            evidence = '；证据：' + '、'.join(f'[{e}](../{e})' for e in m['evidence']) if m['evidence'] else ''
            roadmap += f"- {m['id']} {m['title']}：{m['status']}{evidence}\n"
        roadmap += '\n下一步：' + p['next_action'] + '\n\n失败处理：保留失败证据，回到所属工作包修复并复测；不能跳过退出门或继承其他版本验收。\n\n'
    roadmap += '## 可选路线（不计主线进度）\n\n' + '\n'.join('- ' + s for s in data['optional_tracks']) + '\n\n'
    roadmap += ('## 每次项目更新的维护步骤\n\n'
                '1. 保存源码/配置/产物身份与实际测试、设备、远端审核或人耳记录。\n'
                '2. 修改唯一账本的日期、当前工作包、里程碑状态、证据、车型矩阵及阻塞。DONE 必须人工复核证据适用版本。\n'
                '3. 执行 `python scripts/update-project-progress.py` 生成两个视图。\n'
                '4. 执行 `python scripts/update-project-progress.py --check`；交付前检查不得遗漏。\n'
                '5. 同批交付代码、证据、账本和文档；不以定时刷新代替真实状态更新。\n\n'
                'Android 完成定义：P1–P8 全部退出门通过、六车接受记录齐全、发布材料完成。OEM认证不在范围；AI/iOS/小程序不阻塞本次主线。\n')
    return {'01-ARC-项目总体路线图.md': roadmap, '02-RPT-项目进度总览.md': dashboard}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    data = json.loads((ROOT / 'docs/project-ledger.json').read_text(encoding='utf-8'))
    validate(data)
    for name, content in render(data).items():
        path = ROOT / 'docs' / name
        if args.check:
            assert path.is_file() and path.read_text(encoding='utf-8') == content, 'stale view: ' + name
        else:
            path.write_text(content, encoding='utf-8')
    print('PASS: ledger and both views' + (' are current' if args.check else ' generated'))


if __name__ == '__main__':
    main()
