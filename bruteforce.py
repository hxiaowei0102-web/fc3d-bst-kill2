# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀2码 — 暴力穷举 v2（近200期，公式池扩展版）
=============================================================
目标：只参考近200期数据，从超大算法池中暴力穷举最优「杀6码组合」。
  · 每个位置必须杀2码（2个不同码，碰撞时 +1 兜底）
  · 指标 = 近200期 6杀全中率

v2 算法池（相比 v1 的 47892 个大幅扩展）：
  1. 3 个决策树 + 79 条固定公式
  2. 线性公式：单项 + 二项 + 三项（62 特征，系数 1-3，常数 0-9）
     · 单项: 62×3×10 = 1860
     · 二项: C(62,2)×9×10 = 170,370
     · 三项: C(62,3)×4变体×10 = 1,512,800（变体: 111/112/122/123）
  3. numpy 向量化批量生成输出 + uint64 位图加速对搜索/联合搜索
"""
import json
import numpy as np
from engine import load_data, FORMULAS as FILE_FORMULAS, eval_formula
from algorithms import kill_h, kill_t, kill_o, feat_list, FEAT_NAMES

CSV = 'data/fc3d-history.csv'
WINDOW = 200
TOP_K = 2000       # 位置对搜索：每位置取单码命中率 top-K
JOINT_N = 150      # 联合搜索：每位置取 top-N 对
HT_KEEP = 20000    # 联合搜索 h×t 粗筛保留数
MIN_RATE = 0.90    # 单码命中率下限过滤（近200期 ≥90%）

issues, hh, tt, oo = load_data(CSV)
N = len(issues)
start = N - WINDOW
actual = np.array([(hh[k], tt[k], oo[k]) for k in range(start, N)], dtype=np.int16)
NF = len(FEAT_NAMES)

# 特征矩阵 (WINDOW, NF)
F = np.array([feat_list(hh[k-1], tt[k-1], oo[k-1]) for k in range(start, N)], dtype=np.int16)

# ============ 候选生成（numpy 向量化） ============
def gen_candidate_specs():
    specs = []  # (name, terms, const)  terms=[(c, idx), ...]
    # 单项
    for i in range(NF):
        for c in (1, 2, 3):
            for const in range(10):
                specs.append((f'{c}*{FEAT_NAMES[i]}+{const}', ((c, i),), const))
    # 二项
    for i in range(NF):
        for j in range(i+1, NF):
            for c1 in (1, 2, 3):
                for c2 in (1, 2, 3):
                    for const in range(10):
                        specs.append((f'{c1}*{FEAT_NAMES[i]}+{c2}*{FEAT_NAMES[j]}+{const}',
                                      ((c1, i), (c2, j)), const))
    # 三项（4 种系数变体）
    variants = [(1, 1, 1), (1, 1, 2), (1, 2, 2), (1, 2, 3)]
    for i in range(NF):
        for j in range(i+1, NF):
            for k in range(j+1, NF):
                for (c1, c2, c3) in variants:
                    for const in range(10):
                        specs.append((f'{c1}*{FEAT_NAMES[i]}+{c2}*{FEAT_NAMES[j]}+{c3}*{FEAT_NAMES[k]}+{const}',
                                      ((c1, i), (c2, j), (c3, k)), const))
    return specs


def pack_miss(out_arr, pi):
    """out_arr: (W,) int 输出；返回 miss 位图（bit k=1 表示第k期杀错/未杀中）"""
    miss = (out_arr == actual[:, pi])
    words = []
    for w in range(0, WINDOW, 64):
        v = 0
        for b in range(w, min(w+64, WINDOW)):
            if miss[b]:
                v |= 1 << (b - w)
        words.append(v)
    return tuple(words)


def eval_spec_block(terms_list, consts, block):
    """批量计算输出矩阵 (block, WINDOW)。单项/二项统一 padding 到 3 项（系数0补齐）"""
    m = len(block)
    padded = []
    for terms in terms_list:
        p = [(c, idx) for c, idx in terms]
        while len(p) < 3:
            p.append((0, 0))
        padded.append(p)
    idx_arr = np.array([[idx for _, idx in p] for p in padded], dtype=np.int64)   # (m, 3)
    coef_arr = np.array([[c for c, _ in p] for p in padded], dtype=np.int16)      # (m, 3)
    const_arr = np.array(consts, dtype=np.int16)[:, None]
    cols = F[:, idx_arr]                    # (WINDOW, m, 3)
    cols = np.transpose(cols, (1, 0, 2))    # (m, WINDOW, 3)
    out = (cols * coef_arr[:, None, :]).sum(axis=2) + const_arr   # (m, WINDOW)
    return out % 10


def build_pool():
    import os, pickle
    CACHE = 'pool_cache.pkl'
    if os.path.exists(CACHE):
        print(f"  加载缓存池 {CACHE}...")
        with open(CACHE, 'rb') as f:
            return pickle.load(f)

    print("生成候选规格...")
    specs = gen_candidate_specs()
    print(f"  候选总数(去重前): {len(specs)}")

    # 决策树 + 固定公式（直接算）
    pool = []
    for nm, fn in [('决策树_百', kill_h), ('决策树_十', kill_t), ('决策树_个', kill_o)]:
        out = [fn(hh[start+k-1], tt[start+k-1], oo[start+k-1]) for k in range(WINDOW)]
        pool.append((nm, np.array(out, dtype=np.int16)))
    for pos in ['h', 't', 'o']:
        for f in FILE_FORMULAS[pos]:
            out = [eval_formula(hh[start+k-1], tt[start+k-1], oo[start+k-1], f) for k in range(WINDOW)]
            pool.append((f'公式[{pos}]:{f}', np.array(out, dtype=np.int16)))

    # 线性公式分块批量生成 + 单码命中率过滤 + 去重
    seen = set()
    block = 20000
    n_spec = len(specs)
    for b0 in range(0, n_spec, block):
        b1 = min(b0 + block, n_spec)
        names = [specs[i][0] for i in range(b0, b1)]
        terms_list = [specs[i][1] for i in range(b0, b1)]
        consts = [specs[i][2] for i in range(b0, b1)]
        outs = eval_spec_block(terms_list, consts, range(b1 - b0))  # (m, WINDOW)
        for t in range(b1 - b0):
            # 去重：用输出序列打包
            packed = 0
            for k in range(WINDOW):
                packed |= int(outs[t, k]) << (4 * k)
            if packed in seen:
                continue
            # 单码命中率（三位置取最高，用于粗筛）
            r = max((outs[t] != actual[:, pi]).mean() for pi in range(3))
            if r < MIN_RATE:
                continue
            seen.add(packed)
            pool.append((names[t], outs[t].copy()))
        if (b1 % 100000) < block:
            print(f"  已处理 {b1}/{n_spec} 候选, 池内 {len(pool)} 个")
    print(f"  线性公式保留: {len(pool) - 3 - 79} 个（去重+过滤后）")
    import pickle
    with open('pool_cache.pkl', 'wb') as f:
        pickle.dump(pool, f, protocol=4)
    print(f"  池已缓存到 pool_cache.pkl")
    return pool


# ============ 位图辅助 ============
# miss 位图: bit=1 表示该期杀错(公式输出==开奖)。pack 按 64 位一组。
WORD_MASK = (1 << 64) - 1
_MASKS = [WORD_MASK] * (WINDOW // 64)
if WINDOW % 64:
    _MASKS.append((1 << (WINDOW % 64)) - 1)


def miss_bits(out_arr, pi):
    """返回 miss 位图元组（bit=1 表示该期杀错）"""
    return pack_miss(out_arr, pi)


def pair_rate(m1, m2):
    """两个公式联合命中率（两者都杀对才算中）。~ 无限取反后用掩码截断再计数"""
    hit = 0
    for wa, wb, mk in zip(m1, m2, _MASKS):
        hit += ((~(wa | wb)) & mk).bit_count()
    return hit / WINDOW


def joint_6kill(hp, tp, op):
    hit = 0
    for wha, whb, wta, wtb, woa, wob, mk in zip(hp[0], hp[1], tp[0], tp[1], op[0], op[1], _MASKS):
        merged = wha | whb | wta | wtb | woa | wob
        hit += ((~merged) & mk).bit_count()
    return hit / WINDOW


def search_combo(pool, exclude_names):
    """排除 exclude_names 后，穷举最优 6杀组合。
    关键：pair 搜索用「含碰撞兜底」的精确命中率（与 backtest 引擎一致），
    并排除碰撞率≥50% 的假杀2码对（两公式输出几乎相同）。
    """
    avail = [i for i in range(len(pool)) if pool[i][0] not in exclude_names]
    POS = [('h', 0), ('t', 1), ('o', 2)]
    miss_maps = {}
    for i in avail:
        miss_maps[i] = {pi: miss_bits(pool[i][1], pi) for pi in range(3)}

    # 每位置：单码 top-K → 精确 pair 搜索（含碰撞兜底 + 排除碰撞率≥50%假杀2码）
    from itertools import combinations
    best_pairs = {}
    for pos, pi in POS:
        ranked = sorted(avail, key=lambda i: sum(w.bit_count() for w in miss_maps[i][pi]))
        top = ranked[:TOP_K]
        TO = np.stack([pool[i][1] for i in top])          # (K, WINDOW)
        K = TO.shape[0]
        a_pi = actual[:, pi]
        all_pairs = list(combinations(range(K), 2))
        total = len(all_pairs)
        pairs = []
        BLK = 8000
        for b0 in range(0, total, BLK):
            b1 = min(b0 + BLK, total)
            seg = all_pairs[b0:b1]
            ia = np.array([p[0] for p in seg], dtype=np.int64)
            ja = np.array([p[1] for p in seg], dtype=np.int64)
            c1 = TO[ia]                       # (B, WINDOW)
            c2 = TO[ja]
            coll = (c1 == c2)
            coll_rate = coll.mean(axis=1)               # 碰撞率
            c2f = np.where(coll, (c1 + 1) % 10, c2)     # 碰撞时 +1 兜底
            hitn = ((c1 != a_pi) & (c2f != a_pi)).sum(axis=1)
            for q in range(len(ia)):
                if coll_rate[q] < 0.5:                  # 排除假杀2码对
                    pairs.append((hitn[q] / WINDOW, top[ia[q]], top[ja[q]]))
        pairs.sort(key=lambda x: -x[0])
        best_pairs[pos] = pairs[:JOINT_N]
        print(f"  [{pos}] 单码top-K {K} 个, 精确最优对 {pairs[0][0]*100:.2f}%")

    cand = {p: best_pairs[p][:JOINT_N] for p in ['h', 't', 'o']}
    ht = []
    for rh, ah, bh in cand['h']:
        for rt, at, bt in cand['t']:
            ht.append((rh + rt, ah, bh, at, bt))
    ht.sort(key=lambda x: -x[0])
    ht = ht[:HT_KEEP]

    best_rate = -1
    best_idx = None
    for sh, ah, bh, at, bt in ht:
        hp = (miss_maps[ah][0], miss_maps[bh][0])
        tp = (miss_maps[at][1], miss_maps[bt][1])
        for ro, ao, bo in cand['o']:
            r = joint_6kill(hp, tp, (miss_maps[ao][2], miss_maps[bo][2]))
            if r > best_rate:
                best_rate = r
                best_idx = (ah, bh, at, bt, ao, bo)

    ah, bh, at, bt, ao, bo = best_idx
    combo = {
        'h': [pool[ah][0], pool[bh][0]],
        't': [pool[at][0], pool[bt][0]],
        'o': [pool[ao][0], pool[bo][0]],
    }
    return combo, best_rate


def main():
    print("构建算法池 v2（62特征 × 单项/二项/三项）...")
    pool = build_pool()
    print(f"算法池(去重+过滤后): {len(pool)} 个")

    sets = {}
    used = set()
    for sid in (1,):  # 仅系统1
        print(f"\n===== 搜索 系统{sid}（排除 {len(used)} 个已用算法）=====")
        combo, rate = search_combo(pool, used)
        used.update(combo['h'] + combo['t'] + combo['o'])
        sets[str(sid)] = {'name': f'系统{sid}', 'combo': combo, 'all6_rate': round(rate*100, 2)}
        print(f"  系统{sid} 近200期 6杀全中: {rate*100:.2f}%")
        print(f"    百位: {combo['h'][0]} + {combo['h'][1]}")
        print(f"    十位: {combo['t'][0]} + {combo['t'][1]}")
        print(f"    个位: {combo['o'][0]} + {combo['o'][1]}")

    result = {
        'window': WINDOW,
        'data_info': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'pool_size': len(pool),
        'sets': sets,
    }
    with open('best_sets.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n已写入 best_sets.json")


if __name__ == '__main__':
    main()
