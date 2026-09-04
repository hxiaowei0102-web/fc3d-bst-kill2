# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 暴力穷举（双窗口：最新200期 / 最新300期）
=============================================
公式池：59特征 × 单/双/三特征线性组合 ≈ 905万规格。
numpy 向量化计算窗口输出，流式更新三位置最优（不存池、不去重、内存O(1)）。
并列裁决：命中率 → 公式更短 → 字典序。
输出 best_formula.json 含两套：windows["200"] 与 windows["300"]。
"""
import json
import numpy as np
from engine import load_data
from formulas import feat_list, iter_specs, formula_name

CSV = 'data/fc3d-history.csv'
WINDOWS = (450,)   # 单窗口 450期 — 2026-09-04 老板要求删350只留450


def search_best(hh, tt, oo, window, verbose=True):
    """在最新 window 期上穷举 905万公式池，返回三位置最优 {pos: (name, rate, hits)}"""
    N = len(hh)
    if N < window + 1:
        raise ValueError(
            f"数据量不足：仅 {N} 期，至少需要 {window+1} 期（{window}期被预测 + 1期上期）。")
    start = N - window
    if verbose:
        print(f"  穷举窗口: 第 {start+1}..{N} 条数据，共 {window} 期")

    # 特征矩阵 (window, NF)
    rows = [
        feat_list(
            hh[start + k - 1], tt[start + k - 1], oo[start + k - 1],
            prev=(hh[start + k - 2], tt[start + k - 2], oo[start + k - 2]) if start + k - 2 >= 0 else None
        )
        for k in range(window)
    ]
    F = np.array(rows, dtype=np.int64)
    ah = np.array(hh[start:start + window], dtype=np.int64)
    at = np.array(tt[start:start + window], dtype=np.int64)
    ao = np.array(oo[start:start + window], dtype=np.int64)

    # 流式维护三位置最优 (hits, name)
    best = {'h': (-1, ''), 't': (-1, ''), 'o': (-1, '')}
    total = 0
    for terms, const in iter_specs():
        cols = np.array([idx for _, idx in terms], dtype=np.int64)
        coeffs = np.array([c for c, _ in terms], dtype=np.int64)
        out = (F[:, cols] * coeffs).sum(axis=1) + const
        out %= 10
        hh_hits = int((out != ah).sum())
        tt_hits = int((out != at).sum())
        oo_hits = int((out != ao).sum())
        for pos, hits in (('h', hh_hits), ('t', tt_hits), ('o', oo_hits)):
            b_hits, b_name = best[pos]
            if hits >= b_hits:
                name = formula_name(terms, const)
                if hits > b_hits or (len(name), name) < (len(b_name), b_name):
                    best[pos] = (hits, name)
        total += 1

    if verbose:
        print(f"  遍历公式规格: {total:,} 条")
    out = {}
    for pos in ['h', 't', 'o']:
        hits, name = best[pos]
        out[pos] = (name, hits / window, hits)
        if verbose:
            print(f"  {pos} 最优: {name}  命中 {hits}/{window} = {hits/window*100:.2f}%")
    return out, total


def main():
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    print(f"数据 {N} 期：{issues[0]} ~ {issues[-1]}")

    windows = {}
    pool_size = 0
    for w in WINDOWS:
        print(f"\n===== 窗口 {w} 期 =====")
        best, pool_size = search_best(hh, tt, oo, w)
        windows[str(w)] = {
            'combo': {pos: best[pos][0] for pos in ['h', 't', 'o']},
            'rates': {pos: round(best[pos][1] * 100, 2) for pos in ['h', 't', 'o']},
            'hits': {pos: best[pos][2] for pos in ['h', 't', 'o']},
        }

    result = {
        'pool_size': pool_size,
        'data_info': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'windows': windows,
    }
    with open('best_formula.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("\n已写入 best_formula.json（双窗口）")
    for w in WINDOWS:
        c = windows[str(w)]['combo']
        r = windows[str(w)]['rates']
        print(f"  [{w}期] 百:{c['h']}({r['h']}%) 十:{c['t']}({r['t']}%) 个:{c['o']}({r['o']}%)")


if __name__ == '__main__':
    main()
