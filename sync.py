# -*- coding: utf-8 -*-
"""
本地 ↔ 云端同步脚本（沙箱拦截 github.com:443，走 raw 下载 + API 上传）
================================================================
用法：
  python sync.py status   对比本地与云端（默认）
  python sync.py pull     以云端为基准，下载覆盖本地
  python sync.py push     以本地为基准，上传覆盖云端
"""
import base64, json, os, subprocess, sys, urllib.request, urllib.error

OWNER = 'hxiaowei0102-web'
REPO = 'fc3d-bst-kill2'
BRANCH = 'main'
RAW = f'https://raw.githubusercontent.com/{OWNER}/{REPO}/{BRANCH}/'
API = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/'

FILES = [
    '.github/workflows/update.yml',
    '.gitignore',
    'README.md',
    'auto_update.py',
    'backtest.py',
    'best_formula.json',
    'bruteforce.py',
    'bruteforce_v2.py',
    'data/fc3d-history.csv',
    'data/predictions.jsonl',
    'engine.py',
    'fetch.py',
    'formulas.py',
    'gen_site.py',
    'static/index.html',
    'sync.py',
    'tracking.py',
]


def get_token():
    r = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
    return r.stdout.strip()


def _api(method, url, payload=None, token=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'token ' + token,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
        'User-Agent': 'workbuddy',
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def cloud_get(path):
    # 用 gh api 走 Contents API（权威、稳定），绕开 raw.githubusercontent.com 间歇空响应
    r = subprocess.run(
        ['gh', 'api', f'repos/{OWNER}/{REPO}/contents/{path}', '--jq', '.content'],
        capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        try:
            return base64.b64decode(r.stdout.strip())
        except Exception:
            return None
    return None


def cloud_sha(path, token):
    status, body = _api('GET', API + path, token=token)
    if status == 200:
        return json.loads(body)['sha']
    return None


def cloud_put(path, content_b64, token, sha=None):
    payload = {'message': 'sync: ' + path, 'content': content_b64, 'branch': BRANCH}
    if sha:
        payload['sha'] = sha
    status, body = _api('PUT', API + path, payload, token)
    return status


def status(files=FILES):
    diff = 0
    for path in files:
        local = open(path, 'rb').read() if os.path.exists(path) else b''
        remote = cloud_get(path)
        if remote is None:
            print(f"  ✗ {path}: 云端不存在")
            diff += 1
        elif local == remote:
            print(f"  = {path}")
        else:
            print(f"  ≠ {path}: 本地{len(local)}B vs 云端{len(remote)}B")
            diff += 1
    print(f"\n差异文件 {diff} 个 / 共 {len(files)} 个")


def pull(files=FILES):
    for path in files:
        remote = cloud_get(path)
        if remote is None:
            print(f"  ✗ {path}: 云端不存在, 跳过")
            continue
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(remote)
        print(f"  ↓ {path} ({len(remote)}B)")


def push(files=FILES):
    token = get_token()
    if not token:
        print('未获取到 token'); sys.exit(1)
    for path in files:
        if not os.path.exists(path):
            print(f"  ✗ {path}: 本地不存在, 跳过"); continue
        with open(path, 'rb') as f:
            content_b64 = base64.b64encode(f.read()).decode()
        sha = cloud_sha(path, token)
        st = cloud_put(path, content_b64, token, sha)
        print(f"  {'✓' if st in (200, 201) else '✗('+str(st)+')'} {path}")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'status'
    targets = sys.argv[2:] if len(sys.argv) > 2 else None
    files = targets if targets else FILES
    print(f"=== 同步模式: {mode} ({OWNER}/{REPO}) {'文件:' + ','.join(files) if targets else '(全部)'} ===")
    if mode == 'status':
        status(files)
    elif mode == 'pull':
        pull(files)
    elif mode == 'push':
        push(files)
    else:
        print("用法: python sync.py [status|pull|push] [文件1 文件2 ...]")
