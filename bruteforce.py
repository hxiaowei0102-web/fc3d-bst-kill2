# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀2码 — 暴力穷举（近200期，多套）
=============================================
目标：只参考近200期数据，从超大算法池中暴力穷举出多套「杀6码最优组合」。
  · 每个位置必须杀2码（2个不同码，碰撞时 +1 兜底）
  · 指标 = 近200期 6杀全中率
  · 套与套之间算法不重复（穷举时排除已用算法）

算法池 = 3个决策树 + 79条固定公式 + 海量线性公式
"""
import json
from engine import load_data, FORMULAS as FILE_FORMULAS, eval_formula
from algorithms import kill_h, kill_t, kill_o, feat_list, FEAT_NAMES

CSV = 'data/fc3d-history.csv'
WINDOW = 200
TOP_K = 600       # 位置对搜索：每位置取单码命中率 top-K
JOINT_N = 80      # 联合搜索：每位置取 top-N 对
HT_KEEP = 2000    # 联合搜索 h×t 粗筛保留数

issues, hh, tt, oo = load_data(CSV)
N = len(issues)
start = N - WINDOW
feats = [feat_list(hh[k-1], tt[k-1], oo[k-1]) for k in range(start, N)]
actual = [(hh[k], tt[k], oo[k]) for k in range(start, N)]


def build_pool():
    pool = []  # (name, [200 outputs])
    for nm, fn in [('决策树_百', kill_h), ('决策树_十', kill_t), ('决策树_个', kill_o)]:
        out = [fn(hh[start+k-1], tt[start+k-1], oo[start+k-1]) for k in range(WINDOW)]
        pool.append((nm, out))
    for pos in ['h', 't', 'o']:
        for f in FILE_FORMULAS[pos]:
            out = [eval_formula(hh[start+k-1], tt[start+k-1], oo[start+k-1], f) for k in range(WINDOW)]
            pool.append((f'公式[{pos}]:{f}', out))

    nf = len(FEAT_NAMES)
    linear = []
    for idx in range(nf):
        for c in (1, 2, 3):
            for const in range(10):
                linear.append((((c, idx),), const))
    for i in range(nf):
        for j in range(i+1, nf):
            for c1 in (1, 2, 3):
                for c2 in (1, 2, 3):
                    for const in range(10):
                        linear.append((((c1, i), (c2, j)), const))
    print(f"  线性公式数(去重前): {len(linear)}")

    seen = set()
    for terms, const in linear:
        out = []
        for k in range(WINDOW):
            v = const
            for c, idx in terms:
                v += c * feats[k][idx]
            out.append(v % 10)
        packed = 0
        for k, v in enumerate(out):
            packed |= v << (4*k)
        if packed in seen:
            continue
        seen.add(packed)
        name = '+'.join(f'{c}*{FEAT_NAMES[idx]}' for c, idx in terms) + f'+{const}'
        pool.append((name, out))
    return pool


def single_acc(out, pi):
    hit = 0
    for k in range(WINDOW):
        if out[k] != actual[k][pi]:
            hit += 1
    return hit / WINDOW


def pair_hit(o1, o2, pi):
    hit = 0
    for k in range(WINDOW):
        c1 = o1[k]; c2 = o2[k]
        if c2 == c1:
            c2 = (c1 + 1) % 10
        if c1 != actual[k][pi] and c2 != actual[k][pi]:
            hit += 1
    return hit / WINDOW


def joint_6kill(h_pair, t_pair, o_pair):
    hit = 0
    for k in range(WINDOW):
        ok = True
        for (o1, o2), pi in [(h_pair, 0), (t_pair, 1), (o_pair, 2)]:
            c1 = o1[k]; c2 = o2[k]
            if c2 == c1:
                c2 = (c1 + 1) % 10
            if not (c1 != actual[k][pi] and c2 != actual[k][pi]):
                ok = False
                break
        if ok:
            hit += 1
    return hit / WINDOW


def search_combo(pool, exclude_names):
    """排除 exclude_names 后，暴力穷举最优 6杀组合，返回 (combo_dict, all6_rate)"""
    avail = [i for i in range(len(pool)) if pool[i][0] not in exclude_names]
    POS = [('h', 0), ('t', 1), ('o', 2)]
    best_pairs = {}
    for pos, pi in POS:
        ranked = sorted(avail, key=lambda i: -single_acc(pool[i][1], pi))
        top = ranked[:TOP_K]
        pairs = []
        for a in range(len(top)):
            for b in range(a+1, len(top)):
                r = pair_hit(pool[top[a]][1], pool[top[b]][1], pi)
                pairs.append((r, top[a], top[b]))
        pairs.sort(key=lambda x: -x[0])
        best_pairs[pos] = pairs

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
        h_pair = (pool[ah][1], pool[bh][1])
        t_pair = (pool[at][1], pool[bt][1])
        for ro, ao, bo in cand['o']:
            r = joint_6kill(h_pair, t_pair, (pool[ao][1], pool[bo][1]))
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
    print("构建算法池...")
    pool = build_pool()
    print(f"算法池(去重后): {len(pool)} 个")

    sets = {}
    used = set()
    for sid in (1,):  # 仅保留系统1（系统2已彻底删除）
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
