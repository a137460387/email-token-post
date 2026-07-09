// ============ 全局状态 ============
let groups = [];
let currentGroupId = 'default';
let selectedAccountId = null;
let selectedAccountIds = new Set();
let currentEmails = [];
let currentAbortController = null; // 用于取消竞态请求
let toastTimer = null; // Toast定时器

// ============ 工具函数 ============

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    // 清除之前的定时器，防止覆盖
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        toast.className = 'toast';
        toastTimer = null;
    }, 3000);
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(Math.abs(diff) / (1000 * 60 * 60 * 24));

    if (diff < 0) return '刚刚'; // 未来时间
    if (days === 0) {
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
        return '昨天';
    } else if (days < 7) {
        return `${days}天前`;
    } else {
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 简易HTML净化器（移除script/event handler等危险标签和属性）
function sanitizeHtml(html) {
    if (!html) return '';
    // 创建临时DOM
    const doc = new DOMParser().parseFromString(html, 'text/html');
    // 移除所有script标签
    doc.querySelectorAll('script').forEach(el => el.remove());
    // 移除所有带有事件处理器的元素属性
    doc.querySelectorAll('*').forEach(el => {
        for (const attr of Array.from(el.attributes)) {
            if (attr.name.startsWith('on') || attr.value.includes('javascript:')) {
                el.removeAttribute(attr.name);
            }
        }
    });
    return doc.body.innerHTML;
}

function openModal(id) {
    document.getElementById(id).classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}

function getCurrentGroup() {
    return groups.find(g => g.id === currentGroupId);
}

function getCurrentAccounts() {
    const group = getCurrentGroup();
    return group ? group.accounts : [];
}

// ============ API 调用 ============

async function apiRequest(url, options = {}) {
    try {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        return await resp.json();
    } catch (e) {
        throw e;
    }
}

async function fetchGroups() {
    try {
        const data = await apiRequest('/api/groups');
        if (data.success) {
            groups = data.groups || [];
            renderGroupList();
            renderAccountList();
            updateGroupSelects();
            // 更新当前分组名称
            const group = getCurrentGroup();
            if (group) {
                document.getElementById('currentGroupName').textContent = group.name;
            }
        }
    } catch (e) {
        showToast('获取分组失败', 'error');
    }
}

async function createGroup(name) {
    try {
        const data = await apiRequest('/api/groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (data.success) {
            showToast('分组已创建', 'success');
            fetchGroups();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('创建失败', 'error');
    }
}

async function deleteGroup(groupId) {
    if (!confirm('确定删除此分组？分组内的账号将移到默认分组。')) return;
    try {
        const data = await apiRequest(`/api/groups/${groupId}`, { method: 'DELETE' });
        if (data.success) {
            showToast(data.message, 'success');
            if (currentGroupId === groupId) {
                currentGroupId = 'default';
            }
            fetchGroups();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

async function importAccounts(text, groupId) {
    try {
        const data = await apiRequest('/api/accounts/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, group_id: groupId })
        });
        if (data.success) {
            showToast(data.message, 'success');
            fetchGroups();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('导入失败', 'error');
    }
}

async function deleteAccount(id) {
    if (!confirm('确定删除这个账号？')) return;
    try {
        const data = await apiRequest(`/api/accounts/${id}`, { method: 'DELETE' });
        if (data.success) {
            showToast('已删除', 'success');
            if (selectedAccountId === id) {
                selectedAccountId = null;
                showEmptyEmailView();
            }
            fetchGroups();
        } else {
            showToast(data.error || '删除失败', 'error');
        }
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

async function batchDeleteAccounts() {
    const ids = Array.from(selectedAccountIds);
    if (ids.length === 0) {
        showToast('请先勾选要删除的账号', 'error');
        return;
    }
    if (!confirm(`确定删除选中的 ${ids.length} 个账号？`)) return;

    try {
        const data = await apiRequest('/api/accounts/batch', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        if (data.success) {
            showToast(data.message, 'success');
            selectedAccountIds.clear();
            if (ids.includes(selectedAccountId)) {
                selectedAccountId = null;
                showEmptyEmailView();
            }
            fetchGroups();
        }
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

async function moveAccounts(targetGroupId) {
    const ids = Array.from(selectedAccountIds);
    if (ids.length === 0) {
        showToast('请先勾选要移动的账号', 'error');
        return;
    }

    try {
        const data = await apiRequest('/api/groups/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_ids: ids, target_group_id: targetGroupId })
        });
        if (data.success) {
            showToast(data.message, 'success');
            selectedAccountIds.clear();
            closeModal('moveModal');
            fetchGroups();
        } else {
            showToast(data.error, 'error');
        }
    } catch (e) {
        showToast('移动失败', 'error');
    }
}

async function exportAccounts(type) {
    const ids = Array.from(selectedAccountIds);
    const endpoint = type === 'raw' ? '/api/accounts/raw' : '/api/accounts/export';
    const title = type === 'raw' ? '原数据' : '导出账密';

    try {
        const data = await apiRequest(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        });
        if (data.success) {
            document.getElementById('exportText').value = data.text;
            document.getElementById('exportModalTitle').textContent = title;
            openModal('exportModal');
        }
    } catch (e) {
        showToast('导出失败', 'error');
    }
}

// 取消之前的请求
function cancelPendingRequests() {
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }
}

async function fetchEmails(accountId, email) {
    // 取消之前的请求，防止竞态
    cancelPendingRequests();
    currentAbortController = new AbortController();

    const emailList = document.getElementById('emailList');
    emailList.innerHTML = '<div class="loading">正在加载邮件</div>';

    try {
        const resp = await fetch(`/api/emails/${accountId}`, {
            signal: currentAbortController.signal
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        // 检查当前选中的账号是否仍然是请求时的账号
        if (selectedAccountId !== accountId) return;

        if (data.success) {
            // 保留本地已读状态（防止刷新后丢失）
            const readSet = new Set(
                currentEmails.filter(m => m.isRead).map(m => m.id)
            );
            // 合并：服务器数据 + 本地已读状态
            currentEmails = data.messages.map(msg => ({
                ...msg,
                isRead: msg.isRead || readSet.has(msg.id)
            }));
            renderEmailList(currentEmails, data.email);
        } else {
            emailList.innerHTML = `<div class="empty-state">加载失败：${escapeHtml(data.error)}</div>`;
            showToast(data.error, 'error');
        }
    } catch (e) {
        if (e.name === 'AbortError') return; // 被取消的请求，忽略
        emailList.innerHTML = '<div class="empty-state">网络错误</div>';
        showToast('获取邮件失败', 'error');
    }
}

async function fetchLatestEmail(accountId) {
    cancelPendingRequests();
    currentAbortController = new AbortController();

    const emailList = document.getElementById('emailList');
    emailList.innerHTML = '<div class="loading">正在获取最新邮件</div>';

    try {
        const resp = await fetch(`/api/emails/${accountId}/latest`, {
            signal: currentAbortController.signal
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (selectedAccountId !== accountId) return;

        if (data.success) {
            if (data.message) {
                showEmailDetail(data.message);
            } else {
                emailList.innerHTML = '<div class="empty-state">没有邮件</div>';
            }
        } else {
            emailList.innerHTML = `<div class="empty-state">获取失败：${escapeHtml(data.error)}</div>`;
            showToast(data.error, 'error');
        }
    } catch (e) {
        if (e.name === 'AbortError') return;
        emailList.innerHTML = '<div class="empty-state">网络错误</div>';
        showToast('获取最新邮件失败', 'error');
    }
}

async function fetchEmailDetail(accountId, messageId) {
    const detailDiv = document.getElementById('emailDetail');
    detailDiv.innerHTML = '<div class="loading">正在加载邮件内容</div>';

    try {
        const resp = await fetch(`/api/emails/${accountId}/${messageId}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        if (selectedAccountId !== accountId) return;

        if (data.success) {
            renderEmailDetail(data.message);
        } else {
            detailDiv.innerHTML = `<div class="empty-state">加载失败：${escapeHtml(data.error)}</div>`;
        }
    } catch (e) {
        if (e.name === 'AbortError') return;
        detailDiv.innerHTML = '<div class="empty-state">网络错误</div>';
    }
}

// ============ 渲染函数 ============

function renderGroupList() {
    const list = document.getElementById('groupList');

    list.innerHTML = groups.map(group => {
        const isActive = group.id === currentGroupId;
        const count = group.accounts.length;
        const isDefault = group.id === 'default';

        return `
            <div class="group-item ${isActive ? 'active' : ''}" data-id="${group.id}" onclick="selectGroup('${group.id}')">
                <span class="group-icon">${isDefault ? '📁' : '📂'}</span>
                <span class="group-name">${escapeHtml(group.name)}</span>
                <span class="group-count">${count}</span>
                ${!isDefault ? `<button class="group-delete" onclick="event.stopPropagation(); deleteGroup('${group.id}')" title="删除分组">×</button>` : ''}
            </div>
        `;
    }).join('');
}

function selectGroup(groupId) {
    currentGroupId = groupId;
    selectedAccountIds.clear();
    selectedAccountId = null;

    const group = getCurrentGroup();
    document.getElementById('currentGroupName').textContent = group ? group.name : '';

    renderGroupList();
    renderAccountList();
    showEmptyEmailView();
}

function updateGroupSelects() {
    const options = groups.map(g => `<option value="${g.id}">${escapeHtml(g.name)}</option>`).join('');

    document.getElementById('importGroupSelect').innerHTML = options;
    document.getElementById('moveGroupSelect').innerHTML = options;
}

function renderAccountList() {
    const allAccounts = getCurrentAccounts();
    const searchKeyword = document.getElementById('accountSearchInput').value.trim().toLowerCase();

    // 根据搜索关键词过滤账号
    const accounts = searchKeyword
        ? allAccounts.filter(acc => acc.email.toLowerCase().includes(searchKeyword))
        : allAccounts;

    const list = document.getElementById('accountList');
    const countEl = document.getElementById('accountCount');
    countEl.textContent = `${accounts.length}`;

    if (accounts.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无账号</div>';
        return;
    }

    list.innerHTML = accounts.map(acc => {
        const isActive = acc.id === selectedAccountId;
        const isChecked = selectedAccountIds.has(acc.id);
        let statusClass = 'status-unknown';
        let statusText = '未验证';
        if (acc.status === '有效') {
            statusClass = 'status-valid';
            statusText = '有效';
        } else if (acc.status === '失效') {
            statusClass = 'status-invalid';
            statusText = '失效';
        }

        return `
            <div class="account-item ${isActive ? 'active' : ''}" data-id="${acc.id}">
                <input type="checkbox" ${isChecked ? 'checked' : ''} data-id="${acc.id}" class="account-checkbox">
                <div class="account-info" onclick="selectAccount('${acc.id}')">
                    <div class="account-email-row">
                        <span class="account-email">${escapeHtml(acc.email)}</span>
                        <button class="btn-action" onclick="event.stopPropagation(); copyAccount('${acc.id}')" title="复制账号">📋</button>
                        <button class="btn-action btn-action-danger" onclick="event.stopPropagation(); deleteAccount('${acc.id}')" title="删除账号">🗑</button>
                    </div>
                    <span class="account-status ${statusClass}">${statusText}</span>
                </div>
            </div>
        `;
    }).join('');

    // 绑定checkbox事件
    list.querySelectorAll('.account-checkbox').forEach(cb => {
        cb.addEventListener('change', (e) => {
            e.stopPropagation();
            const id = cb.dataset.id;
            if (cb.checked) {
                selectedAccountIds.add(id);
            } else {
                selectedAccountIds.delete(id);
            }
        });
    });
}

function selectAccount(id) {
    selectedAccountId = id;
    const accounts = getCurrentAccounts();
    const account = accounts.find(a => a.id === id);

    // 更新UI选中状态
    document.querySelectorAll('.account-item').forEach(item => {
        item.classList.toggle('active', item.dataset.id === id);
    });

    // 显示邮件操作按钮
    document.getElementById('btnRefreshEmails').style.display = '';
    document.getElementById('btnLatestEmail').style.display = '';
    document.getElementById('emailListTitle').textContent = `邮件 - ${account ? account.email : ''}`;

    // 显示邮件列表视图
    showEmailListView();

    // 加载邮件
    fetchEmails(id, account ? account.email : '');
}

function showEmptyEmailView() {
    document.getElementById('emailListTitle').textContent = '邮件列表';
    document.getElementById('btnRefreshEmails').style.display = 'none';
    document.getElementById('btnLatestEmail').style.display = 'none';
    document.getElementById('emailList').innerHTML = '<div class="empty-state">选择账号查看邮件</div>';
    showEmailListView();
}

function showEmailListView() {
    document.getElementById('emailListView').style.display = 'flex';
    document.getElementById('emailDetailView').style.display = 'none';
}

function showEmailDetailView() {
    document.getElementById('emailListView').style.display = 'none';
    document.getElementById('emailDetailView').style.display = 'flex';
}

function renderEmailList(messages, email) {
    const list = document.getElementById('emailList');

    if (!messages || messages.length === 0) {
        list.innerHTML = '<div class="empty-state">暂无邮件</div>';
        return;
    }

    list.innerHTML = messages.map(msg => {
        const fromName = msg.from?.emailAddress?.name || msg.from?.emailAddress?.address || '未知发件人';
        const fromAddr = msg.from?.emailAddress?.address || '';
        const isUnread = !msg.isRead;

        return `
            <div class="email-item ${isUnread ? 'unread' : ''}" data-id="${msg.id}" onclick="openEmail('${msg.id}')">
                <div class="email-subject">${escapeHtml(msg.subject || '(无主题)')}</div>
                <div class="email-from">${escapeHtml(fromName)} &lt;${escapeHtml(fromAddr)}&gt;</div>
                <div class="email-preview">${escapeHtml(msg.bodyPreview || '')}</div>
                <div class="email-time">${formatDate(msg.receivedDateTime)}</div>
            </div>
        `;
    }).join('');
}

function openEmail(messageId) {
    if (!selectedAccountId) return;
    showEmailDetailView();
    fetchEmailDetail(selectedAccountId, messageId);

    // 标记邮件为已读
    markEmailAsRead(selectedAccountId, messageId);
}

async function copyAccount(accountId) {
    try {
        const accounts = getCurrentAccounts();
        const account = accounts.find(a => a.id === accountId);
        if (account) {
            await navigator.clipboard.writeText(account.email);
            showToast('已复制邮箱', 'success');
        }
    } catch (e) {
        showToast('复制失败', 'error');
    }
}

async function markEmailAsRead(accountId, messageId) {
    try {
        await fetch(`/api/emails/${accountId}/${messageId}/read`, { method: 'POST' });

        // 更新本地邮件列表中的isRead状态
        const emailItem = currentEmails.find(m => m.id === messageId);
        if (emailItem) {
            emailItem.isRead = true;
        }

        // 更新UI：移除未读样式
        const emailEl = document.querySelector(`.email-item[data-id="${messageId}"]`);
        if (emailEl) {
            emailEl.classList.remove('unread');
        }
    } catch (e) {
        // 静默失败，不影响用户体验
    }
}

function showEmailDetail(msg) {
    showEmailDetailView();
    renderEmailDetail(msg);
}

function renderEmailDetail(msg) {
    const detail = document.getElementById('emailDetail');
    const subject = msg.subject || '(无主题)';
    const fromName = msg.from?.emailAddress?.name || '';
    const fromAddr = msg.from?.emailAddress?.address || '';
    const toAddrs = (msg.toRecipients || []).map(r => r.emailAddress?.address || '').join(', ');
    const ccAddrs = (msg.cc || msg.ccRecipients || []).map(r => r.emailAddress?.address || '').join(', ');
    const date = msg.receivedDateTime ? new Date(msg.receivedDateTime).toLocaleString('zh-CN') : '';

    // 更新详情标题
    document.getElementById('emailDetailTitle').textContent = subject;

    let bodyHtml = '';
    if (msg.body?.content) {
        if (msg.body.contentType === 'html') {
            // 净化HTML防止XSS
            bodyHtml = sanitizeHtml(msg.body.content);
        } else {
            bodyHtml = `<pre style="white-space:pre-wrap;word-break:break-all;">${escapeHtml(msg.body.content)}</pre>`;
        }
    } else {
        bodyHtml = `<pre style="white-space:pre-wrap;word-break:break-all;">${escapeHtml(msg.bodyPreview || '无内容')}</pre>`;
    }

    detail.innerHTML = `
        <div class="email-detail-header">
            <div class="email-detail-subject">${escapeHtml(subject)}</div>
            <div class="email-detail-meta">
                <p><strong>发件人：</strong>${escapeHtml(fromName)} &lt;${escapeHtml(fromAddr)}&gt;</p>
                ${toAddrs ? `<p><strong>收件人：</strong>${escapeHtml(toAddrs)}</p>` : ''}
                ${ccAddrs ? `<p><strong>抄送：</strong>${escapeHtml(ccAddrs)}</p>` : ''}
                <p><strong>时间：</strong>${date}</p>
            </div>
        </div>
        <div class="email-detail-body">${bodyHtml}</div>
    `;
}

// ============ 事件绑定 ============

document.addEventListener('DOMContentLoaded', () => {
    // 初始加载
    fetchGroups();

    // 导入按钮
    document.getElementById('btnImport').addEventListener('click', () => {
        document.getElementById('importText').value = '';
        document.getElementById('importFile').value = '';
        document.getElementById('importGroupSelect').value = currentGroupId;
        openModal('importModal');
    });

    // 文件上传
    document.getElementById('importFile').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (ev) => {
                document.getElementById('importText').value = ev.target.result;
            };
            reader.readAsText(file);
        }
    });

    // 搜索账号
    document.getElementById('accountSearchInput').addEventListener('input', () => {
        renderAccountList();
    });

    // 确认导入
    document.getElementById('btnConfirmImport').addEventListener('click', async () => {
        const text = document.getElementById('importText').value.trim();
        const groupId = document.getElementById('importGroupSelect').value;
        if (!text) {
            showToast('请输入或上传账号数据', 'error');
            return;
        }
        await importAccounts(text, groupId);
        closeModal('importModal');
    });

    // 新建分组
    document.getElementById('btnNewGroup').addEventListener('click', () => {
        document.getElementById('newGroupName').value = '';
        openModal('newGroupModal');
    });

    document.getElementById('btnConfirmNewGroup').addEventListener('click', async () => {
        const name = document.getElementById('newGroupName').value.trim();
        if (!name) {
            showToast('请输入分组名称', 'error');
            return;
        }
        await createGroup(name);
        closeModal('newGroupModal');
    });

    // 全选（基于搜索过滤后的列表）
    document.getElementById('btnSelectAll').addEventListener('click', () => {
        const allAccounts = getCurrentAccounts();
        const searchKeyword = document.getElementById('accountSearchInput').value.trim().toLowerCase();
        const filteredAccounts = searchKeyword
            ? allAccounts.filter(acc => acc.email.toLowerCase().includes(searchKeyword))
            : allAccounts;

        // 检查是否全部已选中
        const allSelected = filteredAccounts.every(a => selectedAccountIds.has(a.id));
        if (allSelected) {
            // 取消选中过滤后的账号
            filteredAccounts.forEach(a => selectedAccountIds.delete(a.id));
        } else {
            // 选中过滤后的账号
            filteredAccounts.forEach(a => selectedAccountIds.add(a.id));
        }
        renderAccountList();
    });

    // 移动分组
    document.getElementById('btnMoveGroup').addEventListener('click', () => {
        const ids = Array.from(selectedAccountIds);
        if (ids.length === 0) {
            showToast('请先勾选要移动的账号', 'error');
            return;
        }
        document.getElementById('moveCount').textContent = ids.length;
        document.getElementById('moveGroupSelect').value = currentGroupId;
        openModal('moveModal');
    });

    document.getElementById('btnConfirmMove').addEventListener('click', () => {
        const targetGroupId = document.getElementById('moveGroupSelect').value;
        moveAccounts(targetGroupId);
    });

    // 删除勾选
    document.getElementById('btnDeleteSelected').addEventListener('click', batchDeleteAccounts);

    // 导出账密
    document.getElementById('btnExport').addEventListener('click', () => exportAccounts('export'));

    // 原数据
    document.getElementById('btnRawData').addEventListener('click', () => exportAccounts('raw'));

    // 复制导出内容
    document.getElementById('btnCopyExport').addEventListener('click', () => {
        const text = document.getElementById('exportText').value;
        navigator.clipboard.writeText(text).then(() => {
            showToast('已复制到剪贴板', 'success');
        }).catch(() => {
            const ta = document.getElementById('exportText');
            ta.select();
            document.execCommand('copy');
            showToast('已复制到剪贴板', 'success');
        });
    });

    // 刷新邮件
    document.getElementById('btnRefreshEmails').addEventListener('click', () => {
        if (selectedAccountId) {
            const accounts = getCurrentAccounts();
            const account = accounts.find(a => a.id === selectedAccountId);
            fetchEmails(selectedAccountId, account ? account.email : '');
        }
    });

    // 最新邮件
    document.getElementById('btnLatestEmail').addEventListener('click', () => {
        if (selectedAccountId) fetchLatestEmail(selectedAccountId);
    });

    // 返回列表
    document.getElementById('btnBackToList').addEventListener('click', () => {
        cancelPendingRequests();
        showEmailListView();
        // 如果邮件列表是loading状态，恢复显示
        const emailList = document.getElementById('emailList');
        if (emailList.querySelector('.loading')) {
            if (currentEmails.length > 0) {
                const account = getCurrentAccounts().find(a => a.id === selectedAccountId);
                renderEmailList(currentEmails, account ? account.email : '');
            } else {
                emailList.innerHTML = '<div class="empty-state">暂无邮件</div>';
            }
        }
    });

    // 点击弹窗外部关闭
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('show');
            }
        });
    });

    // Escape键关闭弹窗
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.show').forEach(m => m.classList.remove('show'));
        }
    });
});
