# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 每日预测跟踪（真正的样本外记录）
==========================================================
核心思想：预测必须在开奖前落盘（杜绝事后编造），开奖后自动回填结果。
数据文件 data/predictions.jsonl，每行一条：

  {"issue":"2026230","window":"250","kh":3,"kt":5,"ko":5,
   "predicted_at":"2026-08-28 18:17","draw":"582",
   "filled_at":"2026-08-28 22:00","hit":true}

- 记录时机：云端 auto_update 每次运行时，把「下期预测」写入（已存在同 issue+window 则跳过，幂等）
- 回填时机：下次运行时，对已记录但未回填的预测，用最新开奖数据补 draw/filled_at/hit
- 命中判定：三位杀码均 ≠ 对应位开奖码（百杀≠百位 且 十杀≠十位 且 个杀≠个位）→ hit=true
- 页面展示：累计真实命中率 + 近30期明细（近期→远期，待开奖显示 ⏳）
"""
import json
import os

TRACK_PATH = 'data/predictions.jsonl'


def load_track(path=TRACK_PATH):
    """读取全部跟踪记录，按期号升序返回列表"""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def save_track(rows, path=TRACK_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        for r in sorted(rows, key=lambda x: (x['issue'], x.get('window', ''))):
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _now():
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')


def backfill(issues_map, path=TRACK_PATH):
    """回填：用最新开奖数据补全已记录但未回填的预测。返回回填条数。
    issues_map: {issue_str: [b,s,g]}，只含已开奖期"""
    rows = load_track(path)
    filled = 0
    for r in rows:
        if 'draw' in r and 'hit' in r:
            continue  # 已回填
        draw = issues_map.get(r['issue'])
        if draw is None:
            continue  # 还没开奖
        ah, at, ao = draw
        # 命中判定：三位杀码均 ≠ 对应位开奖码
        hit = (int(r['kh']) != ah) and (int(r['kt']) != at) and (int(r['ko']) != ao)
        r['draw'] = f'{ah}{at}{ao}'
        r['hit'] = bool(hit)
        r['filled_at'] = _now()
        filled += 1
    if filled:
        save_track(rows, path)
    return filled


def record_prediction(issue, window, kh, kt, ko, path=TRACK_PATH):
    """记录一期预测（开奖前落盘）。已存在同 issue+window 则跳过（幂等）。返回是否新增"""
    rows = load_track(path)
    existing = {(r['issue'], r.get('window', '')) for r in rows}
    if (issue, window) in existing:
        return False
    rows.append({
        'issue': issue,
        'window': window,
        'kh': int(kh), 'kt': int(kt), 'ko': int(ko),
        'predicted_at': _now(),
    })
    save_track(rows, path)
    return True


def summary(path=TRACK_PATH):
    """汇总：真实命中统计只算已回填；明细表含全部记录（待开奖也显示 ⏳）"""
    all_rows = load_track(path)
    rows = [r for r in all_rows if 'hit' in r]  # 命中率只算已回填
    hits = sum(1 for r in rows if r['hit'])
    mx = cur = 0
    for r in rows:
        if r['hit']:
            cur = 0
        else:
            cur += 1
            mx = max(mx, cur)
    recent = sorted(all_rows, key=lambda x: x['issue'], reverse=True)[:30]  # 近期→远期，含待开奖
    recent = [{
        'issue': r['issue'], 'window': r.get('window', ''),
        'kh': r.get('kh'), 'kt': r.get('kt'), 'ko': r.get('ko'),
        'draw': r.get('draw'), 'hit': r.get('hit'),
        'predicted_at': r.get('predicted_at', ''),
    } for r in recent]
    return {
        'total': len(rows), 'hits': hits,
        'rate': round(hits / len(rows) * 100, 2) if rows else 0.0,
        'max_streak': mx, 'recent': recent,
        'pending': len(all_rows) - len(rows),
    }
