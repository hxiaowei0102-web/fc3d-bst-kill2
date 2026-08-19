# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀2码 — 算法库（可评估）
=============================================
统一封装三类算法，供回测/预测/网页调用：
  1. 决策树（参考 D:/百十个）：kill_h / kill_t / kill_o
  2. 固定公式（79条，全史连错2_公式.txt）：eval_formula
  3. 线性公式（暴力穷举生成）：如 "1*s+3*md+3"

make_algorithm(name) -> 返回 (b,s,g)->int 的可调用函数。
"""
from engine import eval_formula

FEAT_NAMES = [
    'b', 's', 'g',
    'b2', 's2', 'g2',
    'b3', 's3', 'g3',
    'S', 'S10', 'P', 'mx', 'mn', 'md',
    'd1', 'd2', 'd3',
    'bs', 'bg', 'sg', 'bsg',
    'S2', 'P2',
    'sum2', 'sum3', 'sum4',
    'bp', 'gp', 'sp',
    'bo', 'so', 'go', 'So',
]
_IDX = {n: i for i, n in enumerate(FEAT_NAMES)}


def feat_list(b, s, g):
    mx = max(b, s, g); mn = min(b, s, g); md = b + s + g - mx - mn
    S = b + s + g; P = mx - mn
    return [
        b, s, g,
        b*b % 10, s*s % 10, g*g % 10,
        b*b*b % 10, s*s*s % 10, g*g*g % 10,
        S, S % 10, P, mx, mn, md,
        abs(b-s), abs(b-g), abs(s-g),
        b*s % 10, b*g % 10, s*g % 10, b*s*g % 10,
        S*S % 10, P*P % 10,
        (b+s) % 10, (s+g) % 10, (b+g) % 10,
        (1 if g == 0 else b**g) % 10, (1 if b == 0 else g**b) % 10, (1 if g == 0 else s**g) % 10,
        b % 2, s % 2, g % 2, S % 2,
    ]


# ================= 决策树 =================
def kill_h(b, s, g):
    sp = max(b, s, g) - min(b, s, g)
    if b % 2 == 0 and s % 2 == 0 and g % 2 == 0: return (b+s+g+1) % 10
    if b % 2 == 1 and s % 2 == 1 and g % 2 == 1: return (b+s+g+2) % 10
    if b == s: return (3*max(b, s, g)) % 10
    if b == g: return (sp+1) % 10
    if s == g: return (b+s+g+8) % 10
    if sp == 4: return (b+s+g+2) % 10
    if sp >= 6: return (b*g-s) % 10
    if (b+s+g) % 2 == 1: return (b*b+s+g*g) % 10
    if b < g: return (b+s+g+2) % 10
    if b+s+g <= 12: return (sp+3) % 10
    return (b+s+g+1) % 10


def kill_t(b, s, g):
    if (b+s+g) % 2 == 1:
        if (b*b+s*s) % 10 == 0: return (b+s+g+2) % 10
        return (b*b+s*s+g) % 10
    if max(b, s, g) - min(b, s, g) >= 6:
        if b >= s and b >= g: return ((b+s)*g) % 10
        return (3*max(b, s, g)) % 10
    return (g*g+b) % 10


def kill_o(b, s, g):
    sp = max(b, s, g) - min(b, s, g)
    if b % 2 == 1 and s % 2 == 1 and g % 2 == 1: return (b+s+g+3) % 10
    if b == s: return (b+s+g+6) % 10
    if b == g: return (b+s+g+2) % 10
    if s == g: return (b+s+g+1) % 10
    if sp == 4: return (b*b+s*s+g) % 10
    if sp == 2: return (s*g+b) % 10
    if g == max(b, s, g): return (s*g+b) % 10
    if b > g: return (s*g) % 10
    if b+s+g >= 15: return (b*s+s*g) % 10
    if (b+s+g) % 2 == 0: return (s*g+b) % 10
    if (b+s+g) % 2 == 1: return (g*g*s) % 10
    return (s*g-b) % 10


# ================= 线性公式解析 =================
def parse_linear(name):
    terms = []
    const = 0
    for part in name.split('+'):
        part = part.strip()
        if '*' in part:
            c_str, feat = part.split('*', 1)
            terms.append((int(c_str), _IDX[feat]))
        elif part.isdigit():
            const += int(part)
        else:
            terms.append((1, _IDX[part]))
    return terms, const


# ================= 统一工厂 =================
def make_algorithm(name):
    if name.startswith('决策树_百'):
        return kill_h
    if name.startswith('决策树_十'):
        return kill_t
    if name.startswith('决策树_个'):
        return kill_o
    if name.startswith('公式['):
        f = name.split(':', 1)[1]
        return lambda b, s, g, f=f: eval_formula(b, s, g, f)
    # 线性公式
    terms, const = parse_linear(name)
    def fn(b, s, g, terms=terms, const=const):
        fv = feat_list(b, s, g)
        v = const
        for c, idx in terms:
            v += c * fv[idx]
        return v % 10
    return fn


def get_kill2(name1, name2, b, s, g):
    """按两个算法名算 2 个杀码（碰撞时第二个 +1 兜底）"""
    f1 = make_algorithm(name1)
    f2 = make_algorithm(name2)
    c1 = f1(b, s, g)
    c2 = f2(b, s, g)
    if c2 == c1:
        c2 = (c1 + 1) % 10
    return c1, c2
