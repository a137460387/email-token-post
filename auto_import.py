"""自动提取阿奇索提货链接中的卡密账号并导入本地服务

用法:
    python auto_import.py https://alds.agiso.com/xxxxxxxx.aspx
    python auto_import.py qp3yx95llqgbxqwhfayewtudyinnty3w9c692e03959d4bc2b5c65d395aff6929 [--group GROUP_ID]

流程:
    1. 从链接中解析 token
    2. POST https://alds.agiso.com/api/Cpd/Detail 拉取卡密
    3. 解析 Data 里的 CardPwdArr，提取所有 c 字段（即 邮箱----密码----Client Id----令牌）
    4. 调用本地服务 /api/accounts/import 导入（自动去重）
"""
import re
import sys
import json
import urllib.request

TIQU_API = "https://alds.agiso.com/api/Cpd/Detail"
LOCAL_IMPORT_API = "http://127.0.0.1:17361/api/accounts/import"


def extract_token(url_or_token):
    """从完整链接（xxx/yyy.aspx）或裸 token 字符串中提取 token，失败抛 ValueError"""
    s = url_or_token.strip()
    if s.lower().endswith('.aspx'):
        s = s[:-5]
    s = s.rstrip('/').split('/')[-1].split('?')[0]
    if not re.fullmatch(r'[0-9a-zA-Z]{32,}', s):
        raise ValueError(f'无法从输入中解析 token: {url_or_token}')
    return s


def fetch_card_lines(token):
    """调用提货接口，返回 (卡密行列表, 标题)；失败抛 ValueError"""
    payload = json.dumps({'token': token}).encode('utf-8')
    req = urllib.request.Request(
        TIQU_API,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Origin': 'https://alds.agiso.com',
            'Referer': 'https://alds.agiso.com/tq/',
            'User-Agent': 'Mozilla/5.0',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode('utf-8'))

    if not result.get('IsSuccess'):
        raise ValueError(f"提货接口返回失败: {result.get('Error_Msg') or result}")

    groups = json.loads(result['Data'])
    lines = []
    title = groups[0].get('Title', '') if groups else ''
    for group in groups:
        for item in group.get('CardPwdArr') or []:
            c = (item.get('c') or '').strip()
            if c:
                lines.append(c)
    return lines, title


def import_lines(lines, group_id='default'):
    """调用本地导入接口"""
    payload = json.dumps({'text': '\n'.join(lines), 'group_id': group_id}).encode('utf-8')
    req = urllib.request.Request(
        LOCAL_IMPORT_API,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    try:
        token = extract_token(sys.argv[1])
        print(f'token: {token}')
        lines, title = fetch_card_lines(token)
    except ValueError as e:
        print(f'错误: {e}')
        sys.exit(1)

    group_id = 'default'
    if '--group' in sys.argv:
        group_id = sys.argv[sys.argv.index('--group') + 1]

    print(f'提取到 {len(lines)} 条卡密' + (f'（{title}）' if title else ''))

    result = import_lines(lines, group_id)
    print(json.dumps(result, ensure_ascii=False))
    if result.get('success'):
        print(f"完成: {result.get('message')}")


if __name__ == '__main__':
    main()
