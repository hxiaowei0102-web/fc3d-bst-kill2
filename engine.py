# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 数据引擎
=============================================
读取 CSV 为结构化列表，提供窗口切片（保证公式只访问历史、不偷看未来）。
列：issue,hundreds,tens,ones。
"""
import csv

CSV_PATH = 'data/fc3d-history.csv'


def load_data(csv_path=CSV_PATH):
    """读取 CSV，返回 (issues, hundreds, tens, ones)，乱序则排序修复"""
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
    if not issues:
        raise ValueError(
            f"CSV 无有效数据：{csv_path} 为空或表头/字段损坏（需列 issue,hundreds,tens,ones）。")
    if any(issues[i] >= issues[i + 1] for i in range(len(issues) - 1)):
        order = sorted(range(len(issues)), key=lambda i: int(issues[i]))
        issues = [issues[i] for i in order]
        hundreds = [hundreds[i] for i in order]
        tens = [tens[i] for i in order]
        ones = [ones[i] for i in order]
    return issues, hundreds, tens, ones


def get_next_issue(latest_issue, issues=None):
    """由最新期号推断下期期号（L1: 去掉跨年359硬编码）。

    福彩3D 一年实际期数不固定（约345~359期，春节/国庆休市会导致
    年末期号到不了359）。跨年条件改为「latest 已是数据中该年最后一期
    且该年并非当前进行中的年份」——即只有当年已完整结束(次年已出现
    期号)时才跳年，当年进行中(最后一年)一律顺序 +1。
    兼容历史: issues 传 None 时回退旧逻辑(359上限)。
    """
    year = int(latest_issue[:4])
    seq = int(latest_issue[4:]) + 1
    year_max = None
    last_year = None
    if issues:
        years = sorted({iss[:4] for iss in issues})
        last_year = years[-1] if years else None
        seqs = {int(iss[4:]) for iss in issues if iss.startswith(str(year))}
        if seqs:
            year_max = max(seqs)
    if year_max is not None and seq > year_max and str(year) != last_year:
        # 该年已完整结束(不是数据最后一年)且超出实际最大期号 → 跨到下一年
        year += 1
        seq = 1
    elif year_max is None and seq > 359:
        # 无历史数据时回退 359（旧行为，仅首次空库兜底）
        year += 1
        seq = 1
    return f"{year}{seq:03d}"


if __name__ == '__main__':
    issues, h, t, o = load_data()
    print(f"数据 {len(issues)} 期：{issues[0]} ~ {issues[-1]}")
    print(f"最新一期 {issues[-1]} = {h[-1]}{t[-1]}{o[-1]}")
    print(f"下期期号：{get_next_issue(issues[-1], issues)}")
