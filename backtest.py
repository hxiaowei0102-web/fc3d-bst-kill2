# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀2码 — 回测引擎（近200期）
严格滚动窗口：第 i 期预测仅用第 i-1 期数据，逐期真实预测记录。
"""
import json
from algorithms import make_algorithm
from engine import load_data, get_next_issue


def load_combo(path='best_combo.json'):
    with open(path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    return d['combo'], d.get('all6_rate')


def _compile(combo):
    return {pos: [make_algorithm(combo[pos][0]), make_algorithm(combo[pos][1])]
            for pos in ['h', 't', 'o']}


def _kills(fns, b, s, g):
    c1 = fns[0](b, s, g)
    c2 = fns[1](b, s, g)
    if c2 == c1:
        c2 = (c1 + 1) % 10
    return c1, c2


def run_backtest(csv_path, combo, n=200, full=False):
    issues, hh, tt, oo = load_data(csv_path)
    N = len(issues)
    if full:
        start = 1
        window_desc = f"全量{N-1}期"
    else:
        start = max(1, N - n)
        window_desc = f"最近{min(n, N-start)}期"

    fns = _compile(combo)
    results = []
    for i in range(start, N):
        pb, ps, pg = hh[i-1], tt[i-1], oo[i-1]
        ah, at, ao = hh[i], tt[i], oo[i]
        kh1, kh2 = _kills(fns['h'], pb, ps, pg)
        kt1, kt2 = _kills(fns['t'], pb, ps, pg)
        ko1, ko2 = _kills(fns['o'], pb, ps, pg)
        h_hit = (kh1 != ah and kh2 != ah)
        t_hit = (kt1 != at and kt2 != at)
        o_hit = (ko1 != ao and ko2 != ao)
        all_hit = h_hit and t_hit and o_hit
        results.append({
            'issue': issues[i], 'draw': [ah, at, ao], 'prev_draw': [pb, ps, pg],
            'kh': [kh1, kh2], 'kt': [kt1, kt2], 'ko': [ko1, ko2],
            'h_hit': h_hit, 't_hit': t_hit, 'o_hit': o_hit, 'all_hit': all_hit,
        })

    total = len(results)
    h_hits = sum(1 for r in results if r['h_hit'])
    t_hits = sum(1 for r in results if r['t_hit'])
    o_hits = sum(1 for r in results if r['o_hit'])
    all_hits = sum(1 for r in results if r['all_hit'])
    # 最大连错（未全中）
    mx_streak = cur = 0
    for r in results:
        if r['all_hit']:
            cur = 0
        else:
            cur += 1
            mx_streak = max(mx_streak, cur)
    summary = {
        'hundreds_hit_rate': round(h_hits/total*100, 2) if total else 0,
        'tens_hit_rate': round(t_hits/total*100, 2) if total else 0,
        'ones_hit_rate': round(o_hits/total*100, 2) if total else 0,
        'all_hit_rate': round(all_hits/total*100, 2) if total else 0,
        'total_periods': total, 'all_hits': all_hits,
        'max_streak': mx_streak, 'window': window_desc,
    }
    results.reverse()
    return {'results': results, 'summary': summary}


def predict_next(csv_path, combo):
    issues, hh, tt, oo = load_data(csv_path)
    latest = issues[-1]
    pb, ps, pg = hh[-1], tt[-1], oo[-1]
    fns = _compile(combo)
    kh1, kh2 = _kills(fns['h'], pb, ps, pg)
    kt1, kt2 = _kills(fns['t'], pb, ps, pg)
    ko1, ko2 = _kills(fns['o'], pb, ps, pg)
    return {
        'next_issue': get_next_issue(latest),
        'last_issue': latest,
        'last_draw': [pb, ps, pg],
        'kh': [kh1, kh2], 'kt': [kt1, kt2], 'ko': [ko1, ko2],
    }
