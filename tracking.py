# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 每日预测实绩跟踪（真正的实盘记录）
============================================================
核心思想：过去的预测是「当时做出的决定」，开奖后只能回填结果、绝不能篡改。

data/predictions.csv（追加式日志）列：
  issue    被预测期号（开奖号验证该期）
  window   窗口（250 / 350）
  kh,kt,ko 当时预测的三位置杀码（公式变化后历史记录保持不变）
  fh,ft,fo 当时使用的三条公式名（保留快照，可追溯）
  r_h,r_t,r_o 回填后的单位置命中（1=杀中,0=杀错,空=未开奖）
  status   pending(等待开奖) / settled(已回填)
  updated  记录写入时间(北京)

流程（在 auto_update 中调用）：
  1. append_predictions(): 抓数据+穷举后，把「今天预测的下一期」追加进日志（status=pending）
  2. mark_settled(): 下次运行抓到新开奖后，把日志里已开奖的 pending 记录回填命中结果
"""
import csv
import os
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
LOG_PATH = 'data/predictions.csv'
FIELDS = ['issue', 'window', 'kh', 'kt', 'ko', 'fh', 'ft', 'fo',
          'draw', 'r_h', 'r_t', 'r_o', 'status', 'updated']


def _now():
    return datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')


def load_log(path=None):
    """返回 {(issue, window): row}，issue 为字符串"""
    path = path or LOG_PATH
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, 'r', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            key = (r['issue'], r['window'])
            rows[key] = r
    return rows


def append_predictions(entries, path=None):
    """追加当日预测。entries: [{issue, window, kh, kt, ko, fh, ft, fo}, ...]
    已存在同 (issue, window) 则跳过（防重复运行/防篡改历史）。"""
    path = path or LOG_PATH
    log = load_log(path)
    new_rows = []
    for e in entries:
        key = (e['issue'], e['window'])
        if key in log:
            continue
        row = {
            'issue': e['issue'], 'window': e['window'],
            'kh': e['kh'], 'kt': e['kt'], 'ko': e['ko'],
            'fh': e['fh'], 'ft': e['ft'], 'fo': e['fo'],
            'draw': '', 'r_h': '', 'r_t': '', 'r_o': '', 'status': 'pending',
            'updated': _now(),
        }
        log[key] = row
        new_rows.append(row)
    if new_rows:
        _write_log(log, path)
    return len(new_rows)


def mark_settled(issues, hh, tt, oo, path=None):
    """开奖数据推进后，回填所有已开奖的 pending 记录。返回本次回填条数。
    只有 status=pending 且该期号已出现在开奖数据中才会回填；历史预测永不修改。"""
    path = path or LOG_PATH
    draws = {iss: (h, t, o) for iss, h, t, o in zip(issues, hh, tt, oo)}
    log = load_log(path)
    settled = 0
    for key, row in log.items():
        if row['status'] == 'settled':
            continue
        draw = draws.get(row['issue'])
        if draw is None:
            continue
        ah, at, ao = draw
        row['draw'] = f'{ah}{at}{ao}'
        row['r_h'] = '1' if int(row['kh']) != ah else '0'
        row['r_t'] = '1' if int(row['kt']) != at else '0'
        row['r_o'] = '1' if int(row['ko']) != ao else '0'
        row['status'] = 'settled'
        settled += 1
    if settled:
        _write_log(log, path)
    return settled


def _write_log(log, path=None):
    path = path or LOG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for key in sorted(log.keys(), key=lambda k: (k[0], k[1])):
            row = log[key]
            w.writerow([row.get(c, '') for c in FIELDS])


def stats(log):
    """按窗口汇总实绩。返回 {window: {...}}，仅统计已回填(settled)记录。"""
    by_win = {}
    for (issue, w), row in log.items():
        if row['status'] != 'settled':
            continue
        by_win.setdefault(w, []).append(row)
    out = {}
    for w, rows in by_win.items():
        rows.sort(key=lambda r: r['issue'])
        n = len(rows)
        all_hit = sum(1 for r in rows if r['r_h'] == '1' and r['r_t'] == '1' and r['r_o'] == '1')
        # 当前连错 = 从最新一期往前数连续「未全中」期数
        cur_streak = 0
        for r in reversed(rows):
            if r['r_h'] == '1' and r['r_t'] == '1' and r['r_o'] == '1':
                break
            cur_streak += 1
        # 最大连错 = 历史上最长连续未全中
        max_streak = cur = 0
        for r in rows:
            if r['r_h'] == '1' and r['r_t'] == '1' and r['r_o'] == '1':
                cur = 0
            else:
                cur += 1
                max_streak = max(max_streak, cur)
        out[w] = {
            'total': n,
            'all_hit': all_hit,
            'rate': round(all_hit / n * 100, 2) if n else 0.0,
            'cur_streak': cur_streak,
            'max_streak': max_streak,
        }
    return out


def history(log, limit=60):
    """网页表格数据：按窗口分组，最新在前。返回 {window: [rows...]}"""
    by_win = {}
    for (issue, w), row in log.items():
        by_win.setdefault(w, []).append(row)
    out = {}
    for w, rows in by_win.items():
        rows.sort(key=lambda r: r['issue'], reverse=True)
        out[w] = rows[:limit]
    return out
