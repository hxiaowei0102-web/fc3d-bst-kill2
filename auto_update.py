# -*- coding: utf-8 -*-
"""
福彩3D 新版百十个杀一码 — 云端全自动更新入口（GitHub Actions 定时运行）
=============================================
流程：多源降级抓取最新开奖 → 追加到CSV → 双窗口(200/300期)暴力穷举选最优公式
      → 回测 → 生成 static/index.html（部署到 GitHub Pages）
幂等设计：数据与公式均无变化时**不重写页面**（含时间戳），
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
    print("  福彩3D 百十个位各杀一码 · 云端全自动更新（双窗口200/300期）")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\n[1/4] 多源降级抓取 + 追加CSV")
    added = 0
    try:
        import fetch
        _, added = fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/4] 双窗口暴力穷举（200期 + 300期，各905万池，三位置独立选优）")
    import bruteforce
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

    if added == 0 and not formula_changed:
        print("\n[3/4] 数据与公式均无变化，跳过页面生成（零无效更新）")
    else:
        print("\n[3/4] 回测 + 生成网页")
        result = {
            'pool_size': pool_size,
            'data_info': {'n_issues': len(issues), 'first': issues[0], 'last': issues[-1]},
            'windows': windows,
        }
        with open(COMBO_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  已写入 {COMBO_JSON}（公式变化: {formula_changed}, 新增数据: {added}期）")
        os.makedirs('static', exist_ok=True)
        import gen_site
        gen_site.main(out_path=OUT_HTML)

    print("\n[4/4] 完成")
    print(f"  总耗时 {time.time()-t0:.1f} 秒")


if __name__ == '__main__':
    main()
