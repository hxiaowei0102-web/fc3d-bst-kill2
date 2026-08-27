# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 回测引擎（固定公式回看）
=============================================
固定3条公式（百/十/个各1条），应用到过去N期，逐期真实预测记录。
第 i 期预测仅用第 i-1 期及更早数据，不偷看未来。结果排序近期→远期。
"""
import json
from engine import load_data, get_next_issue
from formulas import make_predictor


def load_combo(path='best_formula.json', window=200):
    with open(path, 'r', encoding='utf-8') as f:
        d = json.load(f)
    return d['windows'][str(window)]['combo']


def _compile(combo):
    return {pos: make_predictor(combo[pos]) for pos in ['h', 't', 'o']}


def run_backtest(csv_path, combo, n=200):
    issues, hh, tt, oo = load_data(csv_path)
    N = len(issues)
    start = max(1, N - n)
    fns = _compile(combo)
    results = []
    for i in range(start, N):
        pb, ps, pg = hh[i-1], tt[i-1], oo[i-1]
        prev = (hh[i-2], tt[i-2], oo[i-2]) if i >= 2 else None
        ah, at, ao = hh[i], tt[i], oo[i]
        kh = fns['h'](pb, ps, pg, prev)
        kt = fns['t'](pb, ps, pg, prev)
        ko = fns['o'](pb, ps, pg, prev)
        h_hit = (kh != ah)
        t_hit = (kt != at)
        o_hit = (ko != ao)
        all_hit = h_hit and t_hit and o_hit
        results.append({
            'issue': issues[i], 'draw': [ah, at, ao], 'prev_draw': [pb, ps, pg],
            'kh': kh, 'kt': kt, 'ko': ko,
            'h_hit': h_hit, 't_hit': t_hit, 'o_hit': o_hit, 'all_hit': all_hit,
        })

    total = len(results)
    h_hits = sum(1 for r in results if r['h_hit'])
    t_hits = sum(1 for r in results if r['t_hit'])
    o_hits = sum(1 for r in results if r['o_hit'])
    all_hits = sum(1 for r in results if r['all_hit'])
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
        'max_streak': mx_streak, 'window': f"最近{total}期",
    }
    results.reverse()
    return {'results': results, 'summary': summary}


def predict_next(csv_path, combo):
    issues, hh, tt, oo = load_data(csv_path)
    latest = issues[-1]
    pb, ps, pg = hh[-1], tt[-1], oo[-1]
    fns = _compile(combo)
    prev = (hh[-2], tt[-2], oo[-2]) if len(issues) >= 2 else None
    return {
        'next_issue': get_next_issue(latest),
        'last_issue': latest,
        'last_draw': [pb, ps, pg],
        'kh': fns['h'](pb, ps, pg, prev),
        'kt': fns['t'](pb, ps, pg, prev),
        'ko': fns['o'](pb, ps, pg, prev),
    }
