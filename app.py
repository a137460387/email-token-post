import json
import uuid
import os
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

ACCOUNTS_FILE = os.path.join(os.path.dirname(__file__), 'accounts.json')

# Microsoft OAuth2 token endpoint
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


def load_accounts():
    """从JSON文件加载账号列表"""
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_accounts(accounts):
    """保存账号列表到JSON文件"""
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


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
            return {
                'success': True,
                'access_token': token_data.get('access_token', ''),
                'refresh_token': token_data.get('refresh_token', refresh_token)
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


# ============ 路由 ============

@app.route('/')
def index():
    return render_template('index.html')


# ---- 账号管理 API ----

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """获取所有账号"""
    accounts = load_accounts()
    # 不返回敏感字段给前端
    safe_accounts = []
    for acc in accounts:
        safe_accounts.append({
            'id': acc['id'],
            'email': acc['email'],
            'client_id': acc['client_id'],
            'status': acc.get('status', '未验证'),
            'created_at': acc.get('created_at', '')
        })
    return jsonify({'success': True, 'accounts': safe_accounts})


@app.route('/api/accounts/import', methods=['POST'])
def import_accounts():
    """导入账号"""
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'success': False, 'error': '没有输入内容'}), 400

    new_accounts = parse_import_text(text)
    if not new_accounts:
        return jsonify({'success': False, 'error': '解析失败，请检查格式：email----password----client_id----refresh_token'}), 400

    existing = load_accounts()
    existing_emails = {acc['email'] for acc in existing}

    added = 0
    skipped = 0
    for acc in new_accounts:
        if acc['email'] not in existing_emails:
            existing.append(acc)
            added += 1
        else:
            skipped += 1

    save_accounts(existing)
    return jsonify({
        'success': True,
        'message': f'导入完成：新增 {added} 个，跳过 {skipped} 个重复账号',
        'added': added,
        'skipped': skipped
    })


@app.route('/api/accounts/<account_id>', methods=['DELETE'])
def delete_account(account_id):
    """删除单个账号"""
    accounts = load_accounts()
    accounts = [acc for acc in accounts if acc['id'] != account_id]
    save_accounts(accounts)
    return jsonify({'success': True, 'message': '已删除'})


@app.route('/api/accounts/batch', methods=['DELETE'])
def batch_delete_accounts():
    """批量删除账号"""
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'error': '没有选择账号'}), 400

    accounts = load_accounts()
    id_set = set(ids)
    accounts = [acc for acc in accounts if acc['id'] not in id_set]
    save_accounts(accounts)
    return jsonify({'success': True, 'message': f'已删除 {len(ids)} 个账号'})


@app.route('/api/accounts/export', methods=['POST'])
def export_accounts():
    """导出账号密码"""
    data = request.json
    ids = data.get('ids', [])
    accounts = load_accounts()

    if ids:
        id_set = set(ids)
        accounts = [acc for acc in accounts if acc['id'] in id_set]

    lines = [f"{acc['email']}----{acc['password']}" for acc in accounts]
    return jsonify({'success': True, 'text': '\n'.join(lines)})


# ---- 邮件操作 API ----

@app.route('/api/emails/<account_id>', methods=['GET'])
def get_emails(account_id):
    """获取账号的邮件列表"""
    accounts = load_accounts()
    account = None
    for acc in accounts:
        if acc['id'] == account_id:
            account = acc
            break

    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    # 先尝试用现有的access_token
    access_token = account.get('access_token', '')
    result = None

    if access_token:
        result = fetch_emails(access_token)

    # 如果没有access_token或已失效，刷新token
    if not access_token or (result and not result.get('success')):
        refresh_result = refresh_access_token(account['client_id'], account['refresh_token'])
        if refresh_result['success']:
            access_token = refresh_result['access_token']
            # 更新存储的token
            for acc in accounts:
                if acc['id'] == account_id:
                    acc['access_token'] = access_token
                    acc['refresh_token'] = refresh_result.get('refresh_token', acc['refresh_token'])
                    acc['status'] = '有效'
                    break
            save_accounts(accounts)
            result = fetch_emails(access_token)
        else:
            # 更新状态为失效
            for acc in accounts:
                if acc['id'] == account_id:
                    acc['status'] = '失效'
                    break
            save_accounts(accounts)
            return jsonify({
                'success': False,
                'error': f'Token刷新失败: {refresh_result["error"]}'
            })

    if result and result.get('success'):
        return jsonify({'success': True, 'messages': result['messages'], 'email': account['email']})
    else:
        error_msg = result.get('error', '未知错误') if result else '请求失败'
        return jsonify({'success': False, 'error': error_msg})


@app.route('/api/emails/<account_id>/<message_id>', methods=['GET'])
def get_email_detail(account_id, message_id):
    """获取邮件详情"""
    accounts = load_accounts()
    account = None
    for acc in accounts:
        if acc['id'] == account_id:
            account = acc
            break

    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    access_token = account.get('access_token', '')
    if not access_token:
        return jsonify({'success': False, 'error': '请先刷新邮件列表以获取Token'}), 400

    result = fetch_email_detail(access_token, message_id)
    if result.get('success'):
        return jsonify({'success': True, 'message': result['message']})
    else:
        return jsonify({'success': False, 'error': result.get('error', '获取失败')})


@app.route('/api/emails/<account_id>/latest', methods=['GET'])
def get_latest_email(account_id):
    """获取最新一封邮件"""
    accounts = load_accounts()
    account = None
    for acc in accounts:
        if acc['id'] == account_id:
            account = acc
            break

    if not account:
        return jsonify({'success': False, 'error': '账号不存在'}), 404

    access_token = account.get('access_token', '')
    if not access_token:
        # 尝试刷新
        refresh_result = refresh_access_token(account['client_id'], account['refresh_token'])
        if refresh_result['success']:
            access_token = refresh_result['access_token']
            for acc in accounts:
                if acc['id'] == account_id:
                    acc['access_token'] = access_token
                    acc['refresh_token'] = refresh_result.get('refresh_token', acc['refresh_token'])
                    acc['status'] = '有效'
                    break
            save_accounts(accounts)
        else:
            return jsonify({'success': False, 'error': 'Token刷新失败'})

    # 获取最新1封邮件
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
