import json
import uuid
import os
import time
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'data.json')

# Microsoft OAuth2 token endpoint
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def load_data():
    """从JSON文件加载数据（包含分组和账号）"""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            'groups': [
                {'id': 'default', 'name': '默认分组', 'accounts': []}
            ]
        }


def save_data(data):
    """保存数据到JSON文件"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_import_text(text):
    """解析导入文本，格式: email----password----client_id----refresh_token"""
    accounts = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split('----')
        if len(parts) >= 4:
            accounts.append({
                'id': str(uuid.uuid4()),
                'email': parts[0].strip(),
                'password': parts[1].strip(),
                'client_id': parts[2].strip(),
                'refresh_token': parts[3].strip(),
                'access_token': '',
                'status': '未验证',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    return accounts


def refresh_access_token(client_id, refresh_token):
    """使用refresh_token获取新的access_token"""
    data = {
        'grant_type': 'refresh_token',
        'client_id': client_id,
        'refresh_token': refresh_token,
        'scope': 'offline_access https://graph.microsoft.com/.default'
    }
    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=30)
        if resp.status_code == 200:
            token_data = resp.json()
            # 计算过期时间（提前5分钟视为过期，留缓冲）
            expires_in = token_data.get('expires_in', 3600)
            expires_at = int(time.time()) + expires_in - 300
            return {
                'success': True,
                'access_token': token_data.get('access_token', ''),
                'refresh_token': token_data.get('refresh_token', refresh_token),
                'expires_at': expires_at
            }
        else:
            error_info = resp.json().get('error_description', resp.text)
            return {'success': False, 'error': error_info}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fetch_emails(access_token, top=20):
    """使用Graph API获取邮件列表"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    params = {
        '$top': top,
        '$orderby': 'receivedDateTime desc',
        '$select': 'id,subject,from,receivedDateTime,bodyPreview,isRead,importance'
    }
    try:
        resp = requests.get(
            f'{GRAPH_API_BASE}/me/messages',
            headers=headers, params=params, timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            return {'success': True, 'messages': data.get('value', [])}
        else:
            error_info = resp.json().get('error', {}).get('message', resp.text)
            return {'success': False, 'error': error_info}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def fetch_email_detail(access_token, message_id):
    """获取单封邮件详情"""
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    try:
        resp = requests.get(
            f'{GRAPH_API_BASE}/me/messages/{message_id}',
            headers=headers, timeout=30
        )
        if resp.status_code == 200:
            return {'success': True, 'message': resp.json()}
        else:
            error_info = resp.json().get('error', {}).get('message', resp.text)
            return {'success': False, 'error': error_info}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def is_token_valid(account):
    """检查token是否有效（未过期）"""
    expires_at = account.get('token_expires_at', 0)
    return account.get('access_token') and int(time.time()) < expires_at


def ensure_access_token(account):
    """确保账号有有效的access_token，返回(access_token, need_refresh)"""
    if is_token_valid(account):
        return account['access_token'], False
    # token过期或不存在，返回None，由调用方决定是否刷新
    return None, True


def find_account(data, account_id):
    """在所有分组中查找账号"""
    for group in data['groups']:
        for acc in group['accounts']:
            if acc['id'] == account_id:
                return acc, group
    return None, None


def get_all_accounts(data):
    """获取所有账号（扁平列表）"""
    accounts = []
    for group in data['groups']:
        for acc in group['accounts']:
            acc_copy = acc.copy()
            acc_copy['group_id'] = group['id']
            acc_copy['group_name'] = group['name']
            accounts.append(acc_copy)
    return accounts


# ============ 路由 ============

@app.route('/')
def index():
    return render_template('index.html')


# ---- 分组管理 API ----

@app.route('/api/groups', methods=['GET'])
def get_groups():
    """获取所有分组（含账号）"""
    data = load_data()
    result = []
    for group in data['groups']:
        safe_accounts = []
        for acc in group['accounts']:
            safe_accounts.append({
                'id': acc['id'],
                'email': acc['email'],
                'client_id': acc['client_id'],
                'status': acc.get('status', '未验证'),
                'created_at': acc.get('created_at', '')
            })
        result.append({
            'id': group['id'],
            'name': group['name'],
            'accounts': safe_accounts
        })
    return jsonify({'success': True, 'groups': result})


@app.route('/api/groups', methods=['POST'])
def create_group():
    """创建新分组"""
    req = request.json
    name = req.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': '分组名称不能为空'}), 400

    data = load_data()
    new_group = {
        'id': str(uuid.uuid4()),
        'name': name,
        'accounts': []
    }
    data['groups'].append(new_group)
    save_data(data)
    return jsonify({'success': True, 'group': new_group})


@app.route('/api/groups/<group_id>', methods=['DELETE'])
def delete_group(group_id):
    """删除分组（账号移到默认分组）"""
    if group_id == 'default':
        return jsonify({'success': False, 'error': '不能删除默认分组'}), 400

    data = load_data()
    default_group = next((g for g in data['groups'] if g['id'] == 'default'), None)
    target_group = next((g for g in data['groups'] if g['id'] == group_id), None)

    if not target_group:
        return jsonify({'success': False, 'error': '分组不存在'}), 404

    # 把账号移到默认分组
    if default_group:
        default_group['accounts'].extend(target_group['accounts'])

    data['groups'] = [g for g in data['groups'] if g['id'] != group_id]
    save_data(data)
    return jsonify({'success': True, 'message': '分组已删除，账号已移至默认分组'})


@app.route('/api/groups/move', methods=['POST'])
def move_accounts():
    """移动账号到指定分组"""
    req = request.json
    account_ids = req.get('account_ids', [])
    target_group_id = req.get('target_group_id')

    if not account_ids:
        return jsonify({'success': False, 'error': '没有选择账号'}), 400

    data = load_data()
    target_group = next((g for g in data['groups'] if g['id'] == target_group_id), None)
    if not target_group:
        return jsonify({'success': False, 'error': '目标分组不存在'}), 404

    id_set = set(account_ids)
    moved_count = 0

    for group in data['groups']:
        remaining = []
        for acc in group['accounts']:
            if acc['id'] in id_set:
                target_group['accounts'].append(acc)
                moved_count += 1
            else:
                remaining.append(acc)
        group['accounts'] = remaining

    save_data(data)
    return jsonify({'success': True, 'message': f'已移动 {moved_count} 个账号'})


# ---- 账号管理 API ----

@app.route('/api/accounts/import', methods=['POST'])
def import_accounts():
    """导入账号"""
    req = request.json
    text = req.get('text', '')
    group_id = req.get('group_id', 'default')

    if not text:
        return jsonify({'success': False, 'error': '没有输入内容'}), 400

    new_accounts = parse_import_text(text)
    if not new_accounts:
        return jsonify({'success': False, 'error': '解析失败，请检查格式：email----password----client_id----refresh_token'}), 400

    data = load_data()
    target_group = next((g for g in data['groups'] if g['id'] == group_id), None)
    if not target_group:
        target_group = data['groups'][0]  # fallback to first group

    all_emails = {acc['email'] for group in data['groups'] for acc in group['accounts']}

    added = 0
    skipped = 0
    for acc in new_accounts:
        if acc['email'] not in all_emails:
            target_group['accounts'].append(acc)
            added += 1
        else:
            skipped += 1

    save_data(data)
    return jsonify({
        'success': True,
        'message': f'导入完成：新增 {added} 个，跳过 {skipped} 个重复账号',
        'added': added,
        'skipped': skipped
    })


@app.route('/api/accounts/<account_id>', methods=['DELETE'])
def delete_account(account_id):
    """删除单个账号"""
    data = load_data()
    for group in data['groups']:
        group['accounts'] = [acc for acc in group['accounts'] if acc['id'] != account_id]
    save_data(data)
    return jsonify({'success': True, 'message': '已删除'})


@app.route('/api/accounts/batch', methods=['DELETE'])
def batch_delete_accounts():
    """批量删除账号"""
    req = request.json
    ids = req.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'error': '没有选择账号'}), 400

    data = load_data()
    id_set = set(ids)
    for group in data['groups']:
        group['accounts'] = [acc for acc in group['accounts'] if acc['id'] not in id_set]
    save_data(data)
    return jsonify({'success': True, 'message': f'已删除 {len(ids)} 个账号'})


@app.route('/api/accounts/export', methods=['POST'])
def export_accounts():
    """导出账号密码"""
    req = request.json
    ids = req.get('ids', [])
    data = load_data()

    accounts = get_all_accounts(data)
    if ids:
        id_set = set(ids)
        accounts = [acc for acc in accounts if acc['id'] in id_set]

    lines = [f"{acc['email']}----{acc['password']}" for acc in accounts]
    return jsonify({'success': True, 'text': '\n'.join(lines)})


@app.route('/api/accounts/raw', methods=['POST'])
def export_raw():
    """导出原始数据"""
    req = request.json
    ids = req.get('ids', [])
    data = load_data()

    accounts = get_all_accounts(data)
    if ids:
        id_set = set(ids)
        accounts = [acc for acc in accounts if acc['id'] in id_set]

    lines = [f"{acc['email']}----{acc['password']}----{acc['client_id']}----{acc['refresh_token']}" for acc in accounts]
    return jsonify({'success': True, 'text': '\n'.join(lines)})


# ---- 邮件操作 API ----

@app.route('/api/accounts/<account_id>/refresh', methods=['POST'])
def refresh_account_token(account_id):
    """手动刷新指定账号的token"""
    data = load_data()
    account, group = find_account(data, account_id)

    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    refresh_result = refresh_access_token(account['client_id'], account['refresh_token'])
    if refresh_result['success']:
        account['access_token'] = refresh_result['access_token']
        account['refresh_token'] = refresh_result.get('refresh_token', account['refresh_token'])
        account['token_expires_at'] = refresh_result['expires_at']
        account['status'] = '有效'
        save_data(data)
        return jsonify({'success': True, 'message': 'Token已刷新'})
    else:
        account['status'] = '失效'
        save_data(data)
        return jsonify({'success': False, 'error': refresh_result['error']})


@app.route('/api/accounts/refresh-all', methods=['POST'])
def refresh_all_tokens():
    """批量刷新所有账号token（带延迟避免风控）"""
    data = load_data()
    import time as _time
    results = []

    for group in data['groups']:
        for acc in group['accounts']:
            # 只刷新过期的token
            if is_token_valid(acc):
                results.append({'email': acc['email'], 'status': '跳过（未过期）'})
                continue

            refresh_result = refresh_access_token(acc['client_id'], acc['refresh_token'])
            if refresh_result['success']:
                acc['access_token'] = refresh_result['access_token']
                acc['refresh_token'] = refresh_result.get('refresh_token', acc['refresh_token'])
                acc['token_expires_at'] = refresh_result['expires_at']
                acc['status'] = '有效'
                results.append({'email': acc['email'], 'status': '成功'})
            else:
                acc['status'] = '失效'
                results.append({'email': acc['email'], 'status': '失败'})

            _time.sleep(1)  # 每次刷新间隔1秒，避免风控

    save_data(data)
    return jsonify({'success': True, 'results': results})


@app.route('/api/emails/<account_id>', methods=['GET'])
def get_emails(account_id):
    """获取账号的邮件列表"""
    data = load_data()
    account, group = find_account(data, account_id)

    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    # 检查token是否有效
    access_token, need_refresh = ensure_access_token(account)

    if need_refresh:
        # token过期，自动刷新
        refresh_result = refresh_access_token(account['client_id'], account['refresh_token'])
        if refresh_result['success']:
            access_token = refresh_result['access_token']
            account['access_token'] = access_token
            account['refresh_token'] = refresh_result.get('refresh_token', account['refresh_token'])
            account['token_expires_at'] = refresh_result['expires_at']
            account['status'] = '有效'
            save_data(data)
        else:
            account['status'] = '失效'
            save_data(data)
            return jsonify({'success': False, 'error': f'Token刷新失败: {refresh_result["error"]}'})

    result = fetch_emails(access_token)
    if result.get('success'):
        return jsonify({'success': True, 'messages': result['messages'], 'email': account['email']})
    else:
        return jsonify({'success': False, 'error': result.get('error', '获取失败')})


@app.route('/api/emails/<account_id>/<message_id>', methods=['GET'])
def get_email_detail(account_id, message_id):
    """获取邮件详情"""
    data = load_data()
    account, group = find_account(data, account_id)

    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    # 检查token是否有效
    access_token, need_refresh = ensure_access_token(account)

    if need_refresh:
        refresh_result = refresh_access_token(account['client_id'], account['refresh_token'])
        if refresh_result['success']:
            access_token = refresh_result['access_token']
            account['access_token'] = access_token
            account['refresh_token'] = refresh_result.get('refresh_token', account['refresh_token'])
            account['token_expires_at'] = refresh_result['expires_at']
            account['status'] = '有效'
            save_data(data)
        else:
            return jsonify({'success': False, 'error': 'Token已过期，请刷新邮件列表'})

    result = fetch_email_detail(access_token, message_id)
    if result.get('success'):
        return jsonify({'success': True, 'message': result['message']})
    else:
        return jsonify({'success': False, 'error': result.get('error', '获取失败')})


@app.route('/api/emails/<account_id>/latest', methods=['GET'])
def get_latest_email(account_id):
    """获取最新一封邮件"""
    data = load_data()
    account, group = find_account(data, account_id)

    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    # 检查token是否有效
    access_token, need_refresh = ensure_access_token(account)

    if need_refresh:
        refresh_result = refresh_access_token(account['client_id'], account['refresh_token'])
        if refresh_result['success']:
            access_token = refresh_result['access_token']
            account['access_token'] = access_token
            account['refresh_token'] = refresh_result.get('refresh_token', account['refresh_token'])
            account['token_expires_at'] = refresh_result['expires_at']
            account['status'] = '有效'
            save_data(data)
        else:
            return jsonify({'success': False, 'error': 'Token刷新失败'})

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    params = {
        '$top': 1,
        '$orderby': 'receivedDateTime desc',
        '$select': 'id,subject,from,receivedDateTime,body,bodyPreview,isRead,importance,cc,bcc,toRecipients'
    }

    try:
        resp = requests.get(
            f'{GRAPH_API_BASE}/me/messages',
            headers=headers, params=params, timeout=30
        )
        if resp.status_code == 200:
            messages = resp.json().get('value', [])
            if messages:
                return jsonify({'success': True, 'message': messages[0], 'email': account['email']})
            else:
                return jsonify({'success': True, 'message': None, 'email': account['email'], 'info': '没有邮件'})
        else:
            return jsonify({'success': False, 'error': resp.text})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
