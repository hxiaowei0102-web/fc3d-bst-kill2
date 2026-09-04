# -*- coding: utf-8 -*-
"""
bruteforce_v2.py — 向量化版暴力穷举（905万池：单+双+三特征）
=========================================================
与 bruteforce.py 完全等价的选优逻辑，穷举内核数学重组（同 grid_scan_v2 思路）：
  1. out = (Σ c·F + const) % 10；杀错 ⟺ (Σ c·F)%10 ≡ (target − const)%10
  2. 固定特征组：base = (Σ c·F)%10 一次向量化算出 (NC, W)
  3. d = (base − target)%10 → 行偏移扁平 bincount (NC, 10)，10 个常数项全展开
  4. 循环量：905万公式 → 单236 + 双1711 + 三32509 特征组（系数行向量化）
tie-break 与逐条版一致：命中数 → 公式短 → 字典序。
"""
import json

import numpy as np

from engine import load_data
from formulas import NF, COEFFS, TRIPLE_COEFFS, feat_list, formula_name

CSV = 'data/fc3d-history.csv'
WINDOWS = (450,)   # 单窗口 450期 — 2026-09-04 老板要求删350只留450

# ---------- 模块级向量化常量 ----------
# 双特征系数序：c1 外层、c2 内层（同 iter_specs）
_PC1 = np.array([c for c in COEFFS for _ in COEFFS], dtype=np.int64)
_PC2 = np.array([c for _ in COEFFS for c in COEFFS], dtype=np.int64)
_NP = len(COEFFS) ** 2                                          # 16
# 三特征系数序：c1 外层、c3 内层（同 iter_specs triple）
_TC1 = np.array([c1 for c1 in TRIPLE_COEFFS for _2 in TRIPLE_COEFFS for _3 in TRIPLE_COEFFS], dtype=np.int64)
_TC2 = np.array([c2 for _1 in TRIPLE_COEFFS for c2 in TRIPLE_COEFFS for _3 in TRIPLE_COEFFS], dtype=np.int64)
_TC3 = np.array([c3 for _1 in TRIPLE_COEFFS for _2 in TRIPLE_COEFFS for c3 in TRIPLE_COEFFS], dtype=np.int64)
_NT = len(TRIPLE_COEFFS) ** 3                                   # 27
_REV = np.array([(10 - k) % 10 for k in range(10)], dtype=np.int64)
_ROWP = (np.arange(_NP) * 10)[:, None]
_ROWT = (np.arange(_NT) * 10)[:, None]
_PAIRS = [(i, j) for i in range(NF) for j in range(i + 1, NF)]
_TRIPLES = [(i, j, k) for i in range(NF) for j in range(i + 1, NF) for k in range(j + 1, NF)]


def _update_best(best, pkey, cand_hits, name):
    b_hits, b_name = best[pkey]
    if cand_hits > b_hits or (len(name), name) < (len(b_name), b_name):
        best[pkey] = (cand_hits, name)


def search_best(hh, tt, oo, window, verbose=True, include_triple=False):
    """在最新 window 期上向量化穷举公式池，返回三位置最优 {pos: (name, rate, hits)}
    include_triple=False(默认): 只用单+双池(27.6万) —— 2026-09-03 实测样本外 80% > 全池73.3%
                                 且快30倍；三特征属过拟合，生产默认关闭。
    include_triple=True: 单+双+三全池(905万)，保留能力备用。"""
    N = len(hh)
    if N < window + 1:
        raise ValueError(
            f"数据量不足：仅 {N} 期，至少需要 {window+1} 期（{window}期被预测 + 1期上期）。")
    start = N - window
    if verbose:
        print(f"  穷举窗口: 第 {start+1}..{N} 条数据，共 {window} 期"
              f"({'单+双池27.6万' if not include_triple else '全池905万'})")

    rows = [
        feat_list(
            hh[start + k - 1], tt[start + k - 1], oo[start + k - 1],
            prev=(hh[start + k - 2], tt[start + k - 2], oo[start + k - 2]) if start + k - 2 >= 0 else None
        )
        for k in range(window)
    ]
    F = np.array(rows, dtype=np.int64)
    fcols = [F[:, k] for k in range(NF)]
    ah = np.asarray(hh[start:start + window], dtype=np.int64)
    at = np.asarray(tt[start:start + window], dtype=np.int64)
    ao = np.asarray(oo[start:start + window], dtype=np.int64)
    TARGETS = (('h', ah), ('t', at), ('o', ao))
    W = window

    best = {'h': (-1, ''), 't': (-1, ''), 'o': (-1, '')}

    # ---------- 单特征（NF × 4 系数） ----------
    for idx in range(NF):
        a = fcols[idx]
        for c in COEFFS:
            base = (c * a) % 10
            for pkey, Tp in TARGETS:
                d = (base - Tp) % 10
                cnt = np.bincount(d, minlength=10)
                mn = int(cnt.min())
                cand = W - mn
                if cand < best[pkey][0]:
                    continue
                cbest = int(_REV[np.where(cnt == mn)[0]].min())
                _update_best(best, pkey, cand, formula_name(((c, idx),), cbest))

    # ---------- 双特征（1711 对 × 16 系数） ----------
    for i, j in _PAIRS:
        a = fcols[i]
        b = fcols[j]
        base16 = (_PC1[:, None] * a[None, :] + _PC2[:, None] * b[None, :]) % 10
        for pkey, Tp in TARGETS:
            d = (base16 - Tp[None, :]) % 10
            hist = np.bincount((d + _ROWP).ravel(), minlength=_NP * 10).reshape(_NP, 10)
            mn_all = hist.min(axis=1)
            cbest_all = np.where(hist == mn_all[:, None], _REV[None, :], 10).min(axis=1)
            cand_all = W - mn_all
            for r in np.nonzero(cand_all >= best[pkey][0])[0]:
                cand = int(cand_all[r])
                _update_best(best, pkey, cand,
                             formula_name(((int(_PC1[r]), i), (int(_PC2[r]), j)), int(cbest_all[r])))

    # ---------- 三特征（32509 组 × 27 系数，默认关：过拟合+慢） ----------
    if include_triple:
        for i, j, k in _TRIPLES:
            a = fcols[i]
            b = fcols[j]
            c = fcols[k]
            base27 = (_TC1[:, None] * a[None, :] + _TC2[:, None] * b[None, :] + _TC3[:, None] * c[None, :]) % 10
            for pkey, Tp in TARGETS:
                d = (base27 - Tp[None, :]) % 10
                hist = np.bincount((d + _ROWT).ravel(), minlength=_NT * 10).reshape(_NT, 10)
                mn_all = hist.min(axis=1)
                cbest_all = np.where(hist == mn_all[:, None], _REV[None, :], 10).min(axis=1)
                cand_all = W - mn_all
                for r in np.nonzero(cand_all >= best[pkey][0])[0]:
                    cand = int(cand_all[r])
                    _update_best(best, pkey, cand,
                                 formula_name(((int(_TC1[r]), i), (int(_TC2[r]), j), (int(_TC3[r]), k)),
                                              int(cbest_all[r])))

    out = {}
    for pos in ['h', 't', 'o']:
        hits, name = best[pos]
        out[pos] = (name, hits / W, hits)
        if verbose:
            print(f"  {pos} 最优: {name}  命中 {hits}/{W} = {hits/W*100:.2f}%")
    total = 9053550 if include_triple else 276120
    return out, total   # (out, total) 与 bruteforce.py 接口一致


def main():
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    print(f"数据 {N} 期：{issues[0]} ~ {issues[-1]}")

    windows = {}
    pool_size = 0
    for w in WINDOWS:
        print(f"\n===== 窗口 {w} 期 =====")
        best, ps = search_best(hh, tt, oo, w)
        pool_size = ps
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
