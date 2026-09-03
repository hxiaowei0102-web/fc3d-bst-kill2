# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 云端全自动更新入口（GitHub Actions 定时运行）
=============================================
流程：多源降级抓取最新开奖 → 追加到CSV → 双窗口(250/350期)暴力穷举选最优公式
      → 每日预测跟踪(回填昨日/记录今日) → 回测 → 生成 static/index.html
幂等设计：数据、公式、预测跟踪均无变化时**不重写页面**（含时间戳），
         workflow 的 git diff 检测不到任何变化即跳过提交与部署，零无效更新。
"""
import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

OUT_HTML = 'static/index.html'
COMBO_JSON = 'best_formula.json'
TRACK_PATH = 'data/predictions.jsonl'


def main():
    t0 = time.time()
    print("=" * 50)
    print("  福彩3D 百十个位各杀一码 · 云端全自动更新（双窗口250/450期 + 每日预测跟踪）")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\n[1/5] 多源降级抓取 + 追加CSV")
    added = 0
    try:
        import fetch
        _, added = fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/5] 双窗口暴力穷举（向量化 905万池，三位置独立选优）")
    import bruteforce_v2 as bruteforce   # v2 向量化：单窗口 137s→13s
    from engine import load_data
    issues, hh, tt, oo = load_data()
    windows = {}
    for w in bruteforce.WINDOWS:
        best, pool_size = bruteforce.search_best(hh, tt, oo, w, verbose=False)
        windows[str(w)] = {
            'combo': {pos: best[pos][0] for pos in ['h', 't', 'o']},
            'rates': {pos: round(best[pos][1] * 100, 2) for pos in ['h', 't', 'o']},
            'hits': {pos: best[pos][2] for pos in ['h', 't', 'o']},
        }
        print(f"  [{w}期] 百:{windows[str(w)]['combo']['h']}({windows[str(w)]['rates']['h']}%) "
              f"十:{windows[str(w)]['combo']['t']}({windows[str(w)]['rates']['t']}%) "
              f"个:{windows[str(w)]['combo']['o']}({windows[str(w)]['rates']['o']}%)")

    # 判断公式是否变化（对比旧 best_formula.json）
    old_combo = None
    try:
        with open(COMBO_JSON, 'r', encoding='utf-8') as f:
            old = json.load(f)
            old_combo = {w: old['windows'][w]['combo'] for w in old['windows']}
    except Exception:
        pass
    new_combo = {w: windows[w]['combo'] for w in windows}
    formula_changed = (old_combo != new_combo)

    print("\n[3/5] 每日预测跟踪（回填昨日 + 记录今日）")
    import tracking
    # 1) 回填：已记录的预测，若对应期已开奖，补真实开奖与命中
    issues_map = {iss: [b, s, g] for iss, b, s, g in zip(issues, hh, tt, oo)}
    filled = tracking.backfill(issues_map, TRACK_PATH)
    if filled:
        print(f"  ✓ 已回填 {filled} 期预测结果")
    # 2) 记录：下期预测落盘（同 issue+window 已存在则跳过，幂等）
    import backtest
    pred = backtest.predict_next('data/fc3d-history.csv', list(windows.values())[0]['combo'])
    recorded = 0
    for w, win in windows.items():
        p = backtest.predict_next('data/fc3d-history.csv', win['combo'])
        if tracking.record_prediction(pred['next_issue'], w, p['kh'], p['kt'], p['ko'], TRACK_PATH):
            recorded += 1
            print(f"  ✓ 已记录预测 {pred['next_issue']} [{w}期]: 百杀{p['kh']} 十杀{p['kt']} 个杀{p['ko']}")
        else:
            print(f"  - 预测 {pred['next_issue']} [{w}期] 已存在，跳过（幂等）")
    track_summary = tracking.summary(TRACK_PATH)

    # 页面是否需要重建：数据新增 / 公式变化 / 回填或新记录发生
    track_changed = (filled > 0 or recorded > 0)
    if added == 0 and not formula_changed and not track_changed:
        print("\n[4/5] 数据/公式/预测跟踪均无变化，跳过页面生成（零无效更新）")
    else:
        print("\n[4/5] 回测 + 生成网页")
        result = {
            'pool_size': pool_size,
            'data_info': {'n_issues': len(issues), 'first': issues[0], 'last': issues[-1]},
            'windows': windows,
        }
        with open(COMBO_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  已写入 {COMBO_JSON}（公式变化: {formula_changed}, 新增数据: {added}期, 跟踪: 回填{filled}/新记录{recorded}）")
        os.makedirs('static', exist_ok=True)
        import gen_site
        gen_site.main(out_path=OUT_HTML)

    print("\n[5/5] 完成")
    print(f"  预测跟踪: " + ", ".join(
        f"[{w}版] 已开奖{t['total']}期 命中{t['hits']}期={t['rate']}% 待开奖{t['pending']}期"
        for w, t in track_summary.items()))
    print(f"  总耗时 {time.time()-t0:.1f} 秒")


if __name__ == '__main__':
    main()
