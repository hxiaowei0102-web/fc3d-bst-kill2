# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀2码 — 云端全自动更新
=============================================
GitHub Actions 定时运行：多数据源降级抓取 → 期号校验 → 追加CSV → 双套回测 → 生成 predict.json
"""
import csv, json, os, sys, re as _re
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
CSV_PATH = 'data/fc3d-history.csv'
PREDICT_OUT = 'static/predict.json'
COMBO_PATH = 'best_sets.json'

# ============ 数据源（多源降级，均做期号合理性校验） ============
DATA_SOURCES = [
    {
        'name': 'huiniao',
        'type': 'json',
        'url': 'https://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page=1&limit=5',
        'parser': lambda data: [
            (item['code'], int(item['one']), int(item['two']), int(item['three']), item.get('next_code'))
            for item in data['data']['data']['list']
        ],
    },
    {
        'name': '17500',
        'type': 'txt17500',
        'url': 'http://www.17500.cn/getData/3d.TXT',  # 用 http（https 返回 nginx 报错页）
        'parser': None,
    },
    {
        'name': 'apihz',
        'type': 'json',
        'url': 'https://cn.apihz.cn/api/caipiao/fucai3d.php?id=88888888&key=88888888',
        'parser': lambda data: _parse_apihz(data),
    },
]


def _parse_apihz(data):
    if data.get('code') != 200:
        return []
    nums = str(data.get('number', '')).split('|')
    if len(nums) != 3:
        return []
    try:
        return [(data['qihao'], int(nums[0]), int(nums[1]), int(nums[2]), None)]
    except (KeyError, ValueError):
        return []


def _http_get(url):
    from urllib.request import urlopen, Request
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    # 默认 SSL 证书验证（灰鸟/apihz 证书正常，无需关闭验证）
    return urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')


def load_existing_rows():
    rows = {}
    out_of_order = False
    prev = None
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                iss = row['issue']
                try:
                    b, s, g = int(row['hundreds']), int(row['tens']), int(row['ones'])
                except (KeyError, ValueError):
                    continue
                rows[iss] = (b, s, g)
                if prev is not None and iss < prev:
                    out_of_order = True
                prev = iss
    except FileNotFoundError:
        pass
    return rows, out_of_order


def fetch_latest():
    rows, _ = load_existing_rows()
    local_last = max(rows.keys(), key=int) if rows else None
    if local_last:
        print(f"  本地最新期号: {local_last}")

    for src in DATA_SOURCES:
        try:
            raw = _http_get(src['url'])
            if src['type'] == 'json':
                data = json.loads(raw)
                draws = src['parser'](data)
            elif src['type'] == 'txt17500':
                draws = []
                lines = [l for l in raw.strip().split('\n') if l.strip()]
                for l in lines[-6:]:
                    parts = l.split()
                    if len(parts) >= 5 and _re.match(r'^20\d{5}$', parts[0]):
                        draws.append((parts[0], int(parts[2]), int(parts[3]), int(parts[4]), None))
            else:
                draws = []

            if not draws:
                print(f"  [{src['name']}] 无数据, 尝试下一个...")
                continue

            src_latest = max(int(d[0]) for d in draws)
            if local_last and src_latest <= int(local_last):
                print(f"  [{src['name']}] 期号{src_latest}<=本地{local_last}, 缓存/旧数据, 跳过")
                continue

            print(f"  [{src['name']}] ✓ 获取{len(draws)}条, 最新{max(d[0] for d in draws)}")
            return {src['name']: draws}
        except Exception as e:
            print(f"  [{src['name']}] ✗ {str(e)[:70]}")

    print("  ❌ 所有数据源均失败或无新数据")
    return {}


def append_to_csv(new_draws):
    rows, was_oos = load_existing_rows()
    added = 0
    for item in new_draws:
        issue = item[0]
        b, s, g = item[1], item[2], item[3]
        if not (isinstance(issue, str) and issue.startswith('20') and 7 <= len(issue) <= 8):
            continue
        if not all(isinstance(x, int) and 0 <= x <= 9 for x in [b, s, g]):
            continue
        if issue in rows:
            if rows[issue] != (b, s, g):
                print(f"  ⚠ 期号{issue}不一致 {rows[issue]} vs {(b,s,g)}，保留原值")
            continue
        rows[issue] = (b, s, g)
        added += 1
        print(f"  新增: {issue} = {b}{s}{g}")
    if added == 0 and not was_oos:
        return 0
    with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['issue', 'hundreds', 'tens', 'ones'])
        for iss in sorted(rows.keys()):
            b, s, g = rows[iss]
            w.writerow([iss, b, s, g])
    return added


def generate_outputs(next_code=None):
    import backtest
    from engine import load_data

    with open(COMBO_PATH, 'r', encoding='utf-8') as f:
        bs = json.load(f)

    issues, hh, tt, oo = load_data(CSV_PATH)
    latest = issues[-1]
    last_draw = ''.join(map(str, [hh[-1], tt[-1], oo[-1]]))

    if next_code and len(str(next_code)) >= 7:
        next_issue = str(next_code)
    else:
        from engine import get_next_issue
        next_issue = get_next_issue(latest)

    sets = {}
    for sid, s in bs['sets'].items():
        combo = s['combo']
        bt = backtest.run_backtest(CSV_PATH, combo, n=200)
        bt_full = backtest.run_backtest(CSV_PATH, combo, full=True)
        pred = backtest.predict_next(CSV_PATH, combo)
        sm = bt['summary']
        rows = [{
            'issue': r['issue'], 'draw': ''.join(map(str, r['draw'])),
            'kh': r['kh'], 'kt': r['kt'], 'ko': r['ko'],
            'hh': r['h_hit'], 'th': r['t_hit'], 'oh': r['o_hit'], 'ah': r['all_hit'],
        } for r in bt['results']]
        sets[str(sid)] = {
            'name': s['name'],
            'combo': combo,
            'kh': pred['kh'], 'kt': pred['kt'], 'ko': pred['ko'],
            's200': {'h': sm['hundreds_hit_rate'], 't': sm['tens_hit_rate'],
                     'o': sm['ones_hit_rate'], 'all': sm['all_hit_rate'],
                     'total': sm['total_periods']},
            'full_rate': bt_full['summary']['all_hit_rate'],
            'max_streak': sm['max_streak'],
            'rows': rows,
        }
        print(f"  {s['name']}: 近200全中{sm['all_hit_rate']}% (百{sm['hundreds_hit_rate']}% 十{sm['tens_hit_rate']}% 个{sm['ones_hit_rate']}%) | 连错{sm['max_streak']}期")

    out = {
        'next_issue': next_issue,
        'last_issue': latest,
        'last_draw': last_draw,
        'updated': datetime.now(BJT).strftime('%Y-%m-%d %H:%M'),
        'data_info': {'last': latest, 'n_issues': len(issues)},
        'sets': sets,
    }
    os.makedirs('static', exist_ok=True)
    with open(PREDICT_OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"  预测期号: {next_issue} | 上期 {latest}={last_draw}")


if __name__ == '__main__':
    print(f"=== 福彩3D 新版百十个杀2码 自动更新 ===")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n[1/3] 多源降级抓取...")
    fetched = fetch_latest()

    next_code = None
    if fetched:
        src_name, draws = list(fetched.items())[0]
        latest_draw = max(draws, key=lambda d: int(d[0]))
        if len(latest_draw) > 4 and latest_draw[4]:
            next_code = latest_draw[4]
            print(f"  下期期号(数据源): {next_code}")

        print("\n[2/3] 更新CSV...")
        added = append_to_csv(draws)
        print(f"  新增{added}期")
    else:
        print("  无新数据, 仅刷新预测")

    print("\n[3/3] 生成预测与回测...")
    generate_outputs(next_code=next_code)
    print("\n完成 ✓")
