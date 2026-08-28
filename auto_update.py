# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 云端全自动更新入口（GitHub Actions 定时运行）
=============================================
流程：多源降级抓取最新开奖 → 追加到CSV → 回填每日预测实绩 → 双窗口(250/350期)暴力穷举选最优公式
      → 写入当日预测 → 回测 → 生成 static/index.html（部署到 GitHub Pages）
幂等设计：数据、公式、实绩均无变化时**不重写页面**（含时间戳），
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


def main():
    t0 = time.time()
    print("=" * 50)
    print("  福彩3D 百十个位各杀一码 · 云端全自动更新（双窗口250/350期 + 每日实绩跟踪）")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\n[1/5] 多源降级抓取 + 追加CSV")
    added = 0
    try:
        import fetch
        _, added = fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/5] 回填每日预测实绩（已开奖的 pending → settled）")
    import tracking
    from engine import load_data
    issues, hh, tt, oo = load_data()
    settled = tracking.mark_settled(issues, hh, tt, oo)
    print(f"  本次回填 {settled} 条实绩")

    print("\n[3/5] 双窗口暴力穷举（250期 + 350期，各905万池，三位置独立选优）")
    import bruteforce
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

    print("\n[4/5] 写入当日预测（实绩日志，历史记录不可篡改）")
    import backtest
    next_issue = backtest.predict_next('data/fc3d-history.csv', list(windows.values())[0]['combo'])['next_issue']
    entries = []
    for w, win in windows.items():
        entries.append({
            'issue': next_issue, 'window': w,
            'kh': win['combo']['h'], 'kt': win['combo']['t'], 'ko': win['combo']['o'],
            'fh': win['combo']['h'], 'ft': win['combo']['t'], 'fo': win['combo']['o'],
        })
    appended = tracking.append_predictions(entries)
    print(f"  新增预测记录 {appended} 条（预测期号 {next_issue}）")

    # 实绩有任何变化（新增预测/回填结果）都需要重新生成页面
    track_changed = (appended > 0 or settled > 0)

    if added == 0 and not formula_changed and not track_changed:
        print("\n[5/5] 数据/公式/实绩均无变化，跳过页面生成（零无效更新）")
    else:
        print("\n[5/5] 回测 + 生成网页")
        result = {
            'pool_size': pool_size,
            'data_info': {'n_issues': len(issues), 'first': issues[0], 'last': issues[-1]},
            'windows': windows,
        }
        with open(COMBO_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  已写入 {COMBO_JSON}（公式变化: {formula_changed}, 新增数据: {added}期, 实绩: 回填{settled}/新增{appended}）")
        os.makedirs('static', exist_ok=True)
        import gen_site
        gen_site.main(out_path=OUT_HTML)

    print(f"\n  总耗时 {time.time()-t0:.1f} 秒")


if __name__ == '__main__':
    main()
