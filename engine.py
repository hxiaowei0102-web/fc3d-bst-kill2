# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀2码 — 公式引擎
=============================================
公式来源：D:/福彩3D资料/全史连错2_公式.txt（79 条固定公式）
  · 百位 23 条 / 十位 35 条 / 个位 21 条
  · 每条公式产出 1 个杀码（mod 10）
  · 变量字典与求值逻辑与「D:/杀2码/formula_sets.py」完全一致（已验证）

变量含义（均由「上期」三码 b=百位, s=十位, g=个位 计算）：
  b,s,g    = 上期百/十/个位
  b2/b3, s2/s3, g2/g3 = 各位的平方/立方 mod10
  S        = b+s+g（和值）          P  = mx-mn（跨度）
  mx,mn,md = 最大/最小/中位数
  d1=|b-s|, d2=|b-g|, d3=|s-g|
  bs/bg/sg/bsg = 两两乘积 / 三数乘积 mod10
  S2=S²%10, P2=P²%10
  sum2=(b+s)%10, sum3=(s+g)%10, sum4=(b+g)%10
  b^g / g^b / s^g = 幂 mod10（0^0 记为 1）
"""

import csv

# ============ 79 条固定公式（严格对应 formulas.txt） ============
FORMULAS = {
    'h': [
        'g+bsg+b^g+0',
        '1*g2+3*mn+5',
        '3*d1+3*g^b+2',
        'P+mx+g^b+2',
        'd1+bsg+sum4+8',
        '1*P+2*mx+5',
        '3*P+2*mn+5',
        'g+b2+bs+2',
        '2*d2+2*sum3+3',
        'b3+d3+S2+6',
        '3*g3+3*mx+0',
        's2+mx+g^b+7',
        's+d3+s^g+1',
        '1*S+1*md+3',
        'b+md+sum3+3',
        's+md+sum4+3',
        'g+md+sum2+3',
        '2*s3+2*P+6',
        'b+d1+bs+5',
        '3*b+1*s3+4',
        'b3+mx+sum4+8',
        'g2+bs+sum2+1',
        'b2+d2+bg+6',
    ],
    't': [
        '1*b+2*g2+9',
        '2*bsg+1*sum3+0',
        's+d3+sum3+4',
        '2*b2+3*S+7',
        'g+S+P2+5',
        'P2+sum3+sum4+5',
        'g3+S+bs+6',
        '1*b2+1*sum3+5',
        's+g+b2+5',
        '2*md+1*P2+5',
        '3*b2+1*b3+3',
        '1*md+2*bg+6',
        'P+bsg+P2+1',
        '2*g2+1*d3+9',
        '2*b3+1*bs+7',
        's+mx+P2+4',
        '1*g2+3*d3+3',
        's2+bs+bsg+3',
        's3+S+d3+1',
        '1*g+1*g^b+9',
        '1*md+3*d2+4',
        'd1+d2+sum2+2',
        'b2+d2+sum2+5',
        'b3+P2+sum3+5',
        '1*b3+3*s3+4',
        's2+g2+g^b+3',
        '2*b3+1*P+8',
        's3+bs+bsg+8',
        '1*sg+3*sum3+2',
        '3*g2+1*bs+9',
        'b2+mn+sum2+9',
        'md+d1+d2+6',
        '3*mn+2*md+1',
        'b3+bg+sg+6',
        'P+md+b^g+1',
    ],
    'o': [
        '1*g+1*mn+2',
        'mn+d1+sg+1',
        'b2+s2+b3+0',
        '1*s2+2*s3+2',
        'g+mx+d2+4',
        'g+d3+b^g+5',
        '3*mx+3*S2+2',
        'b+S2+g^b+7',
        'd3+P2+sum2+6',
        '1*bg+1*sg+2',
        '1*s3+3*mx+7',
        '2*P+3*mx+6',
        'b2+sg+S2+8',
        '1*bg+3*sum2+2',
        '3*bg+2*sum3+0',
        'b3+P+md+2',
        's3+d2+bsg+3',
        '1*s2+3*S2+2',
        '3*s+3*d2+8',
        's2+g2+P2+4',
        's2+P+bg+8',
    ],
}


def _terms_of(b, s, g):
    mx = max(b, s, g); mn = min(b, s, g); md = b + s + g - mx - mn
    S = b + s + g; P = mx - mn
    return {
        'b': b, 's': s, 'g': g,
        'b2': (b * b) % 10, 's2': (s * s) % 10, 'g2': (g * g) % 10,
        'b3': (b * b * b) % 10, 's3': (s * s * s) % 10, 'g3': (g * g * g) % 10,
        'S': S, 'P': P, 'mx': mx, 'mn': mn, 'md': md,
        'd1': abs(b - s), 'd2': abs(b - g), 'd3': abs(s - g),
        'bs': (b * s) % 10, 'bg': (b * g) % 10, 'sg': (s * g) % 10, 'bsg': (b * s * g) % 10,
        'S2': (S * S) % 10, 'P2': (P * P) % 10,
        'sum2': (b + s) % 10, 'sum3': (s + g) % 10, 'sum4': (b + g) % 10,
        'b^g': (1 if g == 0 else b ** g) % 10,
        'g^b': (1 if b == 0 else g ** b) % 10,
        's^g': (1 if g == 0 else s ** g) % 10,
    }


def eval_formula(b, s, g, formula):
    """计算单条公式的杀码（mod 10）"""
    t = _terms_of(b, s, g)
    total = 0
    for part in formula.split('+'):
        part = part.strip()
        if '*' in part:
            c, feat = part.split('*')
            total += int(c) * t[feat]
        elif part.isdigit():
            total += int(part)
        else:
            total += t[part]
    return total % 10


def load_data(csv_path):
    """读取 CSV，返回 (issues, hundreds, tens, ones)，校验严格升序"""
    issues, hundreds, tens, ones = [], [], [], []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                issues.append(row['issue'])
                hundreds.append(int(row['hundreds']))
                tens.append(int(row['tens']))
                ones.append(int(row['ones']))
            except (KeyError, ValueError):
                continue
    # 校验严格升序，乱序则排序修复
    if any(issues[i] >= issues[i + 1] for i in range(len(issues) - 1)):
        order = sorted(range(len(issues)), key=lambda i: int(issues[i]))
        issues = [issues[i] for i in order]
        hundreds = [hundreds[i] for i in order]
        tens = [tens[i] for i in order]
        ones = [ones[i] for i in order]
    return issues, hundreds, tens, ones


def get_next_issue(latest_issue):
    year = int(latest_issue[:4])
    seq = int(latest_issue[4:]) + 1
    if seq > 359:
        year += 1
        seq = 1
    return f"{year}{seq:03d}"


if __name__ == '__main__':
    issues, h, t, o = load_data('data/fc3d-history.csv')
    print(f"数据 {len(issues)} 期：{issues[0]} ~ {issues[-1]}")
    print(f"百位公式 {len(FORMULAS['h'])} 条 / 十位 {len(FORMULAS['t'])} 条 / 个位 {len(FORMULAS['o'])} 条，共 {sum(len(v) for v in FORMULAS.values())} 条")
    # 验证示例：上期 2026219 = 2,2,5
    b, s, g = 2, 2, 5
    print(f"示例：上期(b={b},s={s},g={g}) 百位公式 g+bsg+b^g+0 = {eval_formula(b,s,g,'g+bsg+b^g+0')}")
    print(f"下期期号：{get_next_issue(issues[-1])}")
