class App {
    constructor() {
        this.configEditor = new ConfigEditor();
        this.wsClient = null;
        this.currentView = 'chat';
        this.isStreaming = false;
        this.isCommandMode = false;
        this.knowledgeManager = null;
        this.testcaseManager = null;
        this.commands = [];
        this.toolbarSkills = [];
        this.toolbarSelectedSkills = new Set();
        this.loadedSkillNames = new Set();
        
        this.elements = {
            configNav: document.getElementById('configNav'),
            configView: document.getElementById('configView'),
            knowledgeView: document.getElementById('knowledgeView'),
            testcasesView: document.getElementById('testcasesView'),
            scenariosView: document.getElementById('scenariosView'),
            execsetsView: document.getElementById('execsetsView'),
            chatView: document.getElementById('chatView'),
            chatMessages: document.getElementById('chatMessages'),
            chatInput: document.getElementById('chatInput'),
            sendBtn: document.getElementById('sendBtn'),
            statusBar: document.getElementById('statusBar'),
            modelStatus: document.getElementById('modelStatus'),
            mcpStatus: document.getElementById('mcpStatus'),
            browserStatus: document.getElementById('browserStatus'),
            skillsList: document.getElementById('skillsList'),
            sidebar: document.querySelector('.sidebar'),
            sidebarToggle: document.getElementById('sidebarToggle'),
            sessionHistoryBtn: document.getElementById('session-history-btn'),
            sessionPanel: document.getElementById('session-panel'),
            sessionPanelClose: document.getElementById('session-panel-close'),
            sessionList: document.getElementById('session-list'),
            chatToolbar: document.getElementById('chatToolbar'),
            skillToolbarBtn: document.getElementById('skillToolbarBtn'),
            skillDropdown: document.getElementById('skillDropdown'),
            skillDropdownList: document.getElementById('skillDropdownList'),
            skillConfirmBtn: document.getElementById('skillConfirmBtn')
        };
        
        this.init();
    }
    
    init() {
        this.initNavigation();
        this.initChat();
        this.initWebSocket();
        this.initToolbar();
        this.initSidebarToggle();
        this.initSessionPanel();
        this.loadStatus();
        this.loadSkills();
        this.loadCommands();
        
        setInterval(() => this.loadStatus(), 30000);
    }
    
    initSidebarToggle() {
        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => {
                this.elements.sidebar.classList.toggle('collapsed');
                const icon = this.elements.sidebarToggle.querySelector('.toggle-icon');
                if (this.elements.sidebar.classList.contains('collapsed')) {
                    this.elements.sidebarToggle.title = '展开侧边栏';
                } else {
                    this.elements.sidebarToggle.title = '折叠侧边栏';
                }
            });
        }
    }
    
    initSessionPanel() {
        if (this.elements.sessionHistoryBtn) {
            this.elements.sessionHistoryBtn.addEventListener('click', () => this.toggleSessionPanel());
        }
        if (this.elements.sessionPanelClose) {
            this.elements.sessionPanelClose.addEventListener('click', () => this.toggleSessionPanel(false));
        }
    }
    
    toggleSessionPanel(show) {
        const panel = this.elements.sessionPanel;
        if (show === undefined) {
            show = panel.classList.contains('hidden');
        }
        if (show) {
            panel.classList.remove('hidden');
            this.loadSessionList();
        } else {
            panel.classList.add('hidden');
        }
    }
    
    async loadSessionList() {
        try {
            const sessions = await API.getSessions();
            this.elements.sessionList.innerHTML = '';
            if (!sessions || sessions.length === 0) {
                this.elements.sessionList.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:0.875rem;">暂无会话记录</div>';
                return;
            }
            sessions.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
            sessions.forEach(session => {
                const item = document.createElement('div');
                item.className = 'session-item';
                item.dataset.sessionId = session.session_id;
                const updateTime = session.updated_at ? new Date(session.updated_at).toLocaleString('zh-CN') : '--';
                const msgCount = session.message_count || 0;
                const desc = session.description || '';
                item.innerHTML = `
                    <div class="session-item-role">${this.escapeHtml(session.role || '未知')}</div>
                    <div class="session-item-meta">${updateTime} · ${msgCount}条消息</div>
                    ${desc ? `<div class="session-item-desc">${this.escapeHtml(desc)}</div>` : ''}
                `;
                item.addEventListener('click', () => this.loadSession(session.session_id));
                this.elements.sessionList.appendChild(item);
            });
        } catch (e) {
            this.elements.sessionList.innerHTML = '<div style="padding:16px;text-align:center;color:var(--error-color);font-size:0.875rem;">加载失败</div>';
        }
    }
    
    async loadSession(sessionId) {
        try {
            const detail = await API.getSession(sessionId);
            if (detail && detail.messages) {
                this.elements.chatMessages.innerHTML = '';
                this.renderSessionMessages(detail.messages);
                this.toggleSessionPanel(false);
                this.showView('chat');
                this.scrollToBottom();
            }
        } catch (e) {
            console.error('Failed to load session:', e);
        }
    }
    
    renderSessionMessages(messages) {
        messages.forEach(msg => {
            if (msg.role === 'user' || msg.type === 'human') {
                const msgEl = document.createElement('div');
                msgEl.className = 'message user';
                msgEl.innerHTML = `
                    <div class="message-header">用户</div>
                    <div class="message-content">${this.escapeHtml(msg.content || '')}</div>
                `;
                this.elements.chatMessages.appendChild(msgEl);
            } else if (msg.role === 'assistant' || msg.type === 'ai') {
                const msgEl = document.createElement('div');
                msgEl.className = 'message ai';
                const contentEl = document.createElement('div');
                contentEl.className = 'message-content';
                if (msg.content) {
                    contentEl.textContent = msg.content;
                }
                if (msg.tool_calls) {
                    msg.tool_calls.forEach(tc => {
                        const argsStr = JSON.stringify(tc.args, null, 2);
                        const argsSummary = this.getArgsSummary(tc.args);
                        const div = document.createElement('div');
                        div.className = 'tool-call collapsed';
                        div.dataset.toolCallId = tc.id;
                        div.innerHTML = `
                            <div class="tool-call-header" onclick="this.parentElement.classList.toggle('collapsed')">
                                <span class="tool-call-icon">▶</span>
                                <span class="tool-call-name">${this.escapeHtml(tc.name)}</span>
                                <span class="tool-call-args-summary">${this.escapeHtml(argsSummary)}</span>
                            </div>
                            <div class="tool-call-body">
                                <pre>${this.escapeHtml(argsStr)}</pre>
                            </div>
                        `;
                        contentEl.appendChild(div);
                    });
                }
                msgEl.innerHTML = `<div class="message-header">AI助手</div>`;
                msgEl.appendChild(contentEl);
                this.elements.chatMessages.appendChild(msgEl);
            } else if (msg.role === 'tool' || msg.type === 'tool') {
                const msgEl = document.createElement('div');
                msgEl.className = 'message ai';
                const resultContent = (msg.content || '').length > 500
                    ? (msg.content || '').substring(0, 500) + '...'
                    : (msg.content || '');
                msgEl.innerHTML = `
                    <div class="message-header">工具: ${this.escapeHtml(msg.name || msg.tool_name || 'tool')}</div>
                    <div class="message-content"><pre class="tool-result-content">${this.escapeHtml(resultContent)}</pre></div>
                `;
                this.elements.chatMessages.appendChild(msgEl);
            }
        });
    }
    
    initNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const config = item.dataset.config;
                const view = item.dataset.view;
                
                document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                
                if (config) {
                    this.showConfigView(config);
                } else if (view) {
                    this.showView(view);
                }
            });
        });
    }
    
    hideAllViews() {
        this.elements.configView.classList.add('hidden');
        this.elements.knowledgeView.classList.add('hidden');
        this.elements.testcasesView.classList.add('hidden');
        this.elements.scenariosView.classList.add('hidden');
        this.elements.execsetsView.classList.add('hidden');
        this.elements.chatView.classList.add('hidden');
    }
    
    showConfigView(configName) {
        this.currentView = 'config';
        this.hideAllViews();
        this.elements.configView.classList.remove('hidden');
        this.configEditor.load(configName);
    }
    
    showView(viewName) {
        this.currentView = viewName;
        this.hideAllViews();
        
        switch(viewName) {
            case 'knowledge':
                this.collapseSidebar();
                this.elements.knowledgeView.classList.remove('hidden');
                if (!this.knowledgeManager) {
                    this.knowledgeManager = new KnowledgeManager();
                }
                this.knowledgeManager.init();
                break;
            case 'testcases':
                this.collapseSidebar();
                this.elements.testcasesView.classList.remove('hidden');
                if (!this.testcaseManager) {
                    this.testcaseManager = new TestCaseManager();
                }
                this.testcaseManager.init();
                break;
            case 'scenarios':
                this.elements.scenariosView.classList.remove('hidden');
                break;
            case 'execsets':
                this.elements.execsetsView.classList.remove('hidden');
                break;
            case 'chat':
            default:
                this.elements.chatView.classList.remove('hidden');
                this.elements.chatInput.focus();
                break;
        }
    }
    
    collapseSidebar() {
        if (this.elements.sidebar && !this.elements.sidebar.classList.contains('collapsed')) {
            this.elements.sidebar.classList.add('collapsed');
            this.elements.sidebarToggle.title = '展开侧边栏';
        }
    }
    
    initToolbar() {
        if (this.elements.skillToolbarBtn) {
            this.elements.skillToolbarBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleSkillDropdown();
            });
        }
        if (this.elements.skillConfirmBtn) {
            this.elements.skillConfirmBtn.addEventListener('click', () => {
                this.loadSelectedSkills();
            });
        }
        document.addEventListener('click', (e) => {
            if (this.elements.skillDropdown && this.elements.skillDropdown.classList.contains('open')) {
                if (!this.elements.skillDropdown.contains(e.target) && !this.elements.skillToolbarBtn.contains(e.target)) {
                    this.closeSkillDropdown();
                }
            }
        });
    }
    
    toggleSkillDropdown() {
        if (!this.elements.skillDropdown) return;
        const isOpen = this.elements.skillDropdown.classList.contains('open');
        if (isOpen) {
            this.closeSkillDropdown();
        } else {
            this.openSkillDropdown();
        }
    }
    
    openSkillDropdown() {
        if (!this.elements.skillDropdown) return;
        this.renderSkillDropdownList();
        this.elements.skillDropdown.classList.add('open');
    }
    
    closeSkillDropdown() {
        if (!this.elements.skillDropdown) return;
        this.elements.skillDropdown.classList.remove('open');
    }
    
    async renderSkillDropdownList() {
        if (!this.elements.skillDropdownList) return;
        try {
            const skills = await API.getSkills();
            this.toolbarSkills = skills;
            this.elements.skillDropdownList.innerHTML = '';
            skills.forEach(skill => {
                const item = document.createElement('div');
                item.className = 'skill-dropdown-item';
                const isLoaded = this.loadedSkillNames.has(skill.name);
                const isChecked = this.toolbarSelectedSkills.has(skill.name);
                item.innerHTML = `
                    <input type="checkbox" data-skill-name="${this.escapeHtml(skill.name)}" ${isChecked ? 'checked' : ''}>
                    <div class="skill-dropdown-item-info">
                        <span class="skill-dropdown-item-name">${this.escapeHtml(skill.name)}</span>
                        <span class="skill-dropdown-item-desc">${this.escapeHtml(skill.description || '')}</span>
                    </div>
                    ${isLoaded ? '<span class="loaded-indicator">已加载</span>' : ''}
                `;
                const checkbox = item.querySelector('input[type="checkbox"]');
                checkbox.addEventListener('change', (e) => {
                    if (e.target.checked) {
                        this.toolbarSelectedSkills.add(skill.name);
                    } else {
                        this.toolbarSelectedSkills.delete(skill.name);
                    }
                    this.updateToolbarSelectedCount();
                });
                item.addEventListener('click', (e) => {
                    if (e.target !== checkbox) {
                        checkbox.checked = !checkbox.checked;
                        checkbox.dispatchEvent(new Event('change'));
                    }
                });
                this.elements.skillDropdownList.appendChild(item);
            });
        } catch (e) {
            this.elements.skillDropdownList.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-muted);font-size:0.8rem;">加载失败</div>';
        }
    }
    
    updateToolbarSelectedCount() {
        if (!this.elements.skillToolbarBtn) return;
        const countEl = this.elements.skillToolbarBtn.querySelector('.selected-count');
        if (this.toolbarSelectedSkills.size > 0) {
            if (countEl) {
                countEl.textContent = this.toolbarSelectedSkills.size;
            } else {
                const span = document.createElement('span');
                span.className = 'selected-count';
                span.textContent = this.toolbarSelectedSkills.size;
                this.elements.skillToolbarBtn.appendChild(span);
            }
        } else {
            if (countEl) {
                countEl.remove();
            }
        }
    }
    
    loadSelectedSkills() {
        if (this.toolbarSelectedSkills.size === 0) return;
        const names = Array.from(this.toolbarSelectedSkills);
        const command = `/skill load ${names.join(' ')}`;
        this.toolbarSelectedSkills.clear();
        this.updateToolbarSelectedCount();
        this.closeSkillDropdown();
        this.addUserMessage(command);
        this.isCommandMode = true;
        this.elements.sendBtn.disabled = true;
        this.wsClient.send('task', command);
    }
    
    initChat() {
        this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
        
        this.elements.chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }
    
    initWebSocket() {
        this.wsClient = new WebSocketClient(
            (data) => this.handleWSMessage(data),
            () => this.updateConnectionStatus(true),
            () => this.updateConnectionStatus(false)
        );
        this.wsClient.connect();
    }
    
    handleWSMessage(data) {
        if (this.currentView === 'knowledge' && this.knowledgeManager) {
            this.knowledgeManager.handleWSMessage(data);
            return;
        }
        
        if (this.currentView === 'testcases' && this.testcaseManager) {
            this.testcaseManager.handleWSMessage(data);
            return;
        }
        
        switch (data.type) {
            case 'connected':
                console.log('WS connected:', data.content);
                break;
            case 'command_result':
                this.handleCommandResult(data.content);
                break;
            case 'chunk':
                if (data.message) {
                    this.handleStructuredChunk(data.message);
                } else {
                    this.appendAIMessage(data.content);
                }
                break;
            case 'done':
                if (data.message) {
                    this.handleStructuredDone(data.message);
                } else {
                    this.finishAIMessage();
                }
                break;
            case 'error':
                this.showErrorMessage(data.content);
                this.finishAIMessage();
                break;
            case 'interrupted':
                this.finishAIMessage();
                const interruptMsg = document.createElement('div');
                interruptMsg.className = 'message ai';
                interruptMsg.innerHTML = `
                    <div class="message-header">系统</div>
                    <div class="message-content" style="color: var(--error-color);">任务已中断</div>
                `;
                this.elements.chatMessages.appendChild(interruptMsg);
                this.scrollToBottom();
                break;
        }
    }
    
    sendMessage() {
        if (this.isStreaming) {
            this.stopTask();
            return;
        }
        const content = this.elements.chatInput.value.trim();
        if (!content) return;
        
        this.addUserMessage(content);
        this.elements.chatInput.value = '';
        
        if (content.startsWith('/')) {
            this.isCommandMode = true;
            this.elements.sendBtn.disabled = true;
            this.wsClient.send('task', content);
        } else {
            this.isStreaming = true;
            this.elements.sendBtn.disabled = true;
            this.createAIMessage();
            this.wsClient.send('task', content);
        }
    }
    
    stopTask() {
        this.wsClient.send('stop', '');
    }
    
    addUserMessage(content) {
        const msgEl = document.createElement('div');
        msgEl.className = 'message user';
        msgEl.innerHTML = `
            <div class="message-header">用户</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        this.elements.chatMessages.appendChild(msgEl);
        this.scrollToBottom();
    }
    
    createAIMessage() {
        const msgEl = document.createElement('div');
        msgEl.className = 'message ai';
        msgEl.id = 'current-ai-message';
        msgEl.innerHTML = `
            <div class="message-header">AI助手</div>
            <div class="message-content streaming"></div>
        `;
        this.elements.chatMessages.appendChild(msgEl);
        this.scrollToBottom();
        this.elements.sendBtn.textContent = '停止';
        this.elements.sendBtn.disabled = false;
        this.elements.sendBtn.classList.remove('btn-primary');
        this.elements.sendBtn.classList.add('btn-danger');
    }
    
    appendAIMessage(content) {
        const msgEl = document.getElementById('current-ai-message');
        if (msgEl) {
            const contentEl = msgEl.querySelector('.message-content');
            contentEl.appendChild(document.createTextNode(content));
            this.scrollToBottom();
        }
    }
    
    handleStructuredChunk(msg) {
        if (msg.role === 'assistant') {
            if (msg.content) {
                this.appendAIMessage(msg.content);
            }
            if (msg.tool_calls) {
                this.appendToolCalls(msg.tool_calls);
            }
        } else if (msg.role === 'tool') {
            this.appendToolResult(msg);
        }
    }
    
    handleStructuredDone(msg) {
        if (msg.role === 'assistant' && msg.content) {
            const msgEl = document.getElementById('current-ai-message');
            if (msgEl) {
                const contentEl = msgEl.querySelector('.message-content');
                if (!contentEl.textContent) {
                    contentEl.textContent = msg.content;
                }
            }
        }
        this.finishAIMessage();
    }
    
    appendToolCalls(toolCalls) {
        const msgEl = document.getElementById('current-ai-message');
        if (!msgEl) return;
        const contentEl = msgEl.querySelector('.message-content');
        toolCalls.forEach(tc => {
            if (tc.name === 'spawn_agent') {
                this.appendSubAgentCall(contentEl, tc);
            } else {
                const argsStr = JSON.stringify(tc.args, null, 2);
                const argsSummary = this.getArgsSummary(tc.args);
                const div = document.createElement('div');
                div.className = 'tool-call collapsed';
                div.dataset.toolCallId = tc.id;
                div.innerHTML = `
                    <div class="tool-call-header" onclick="this.parentElement.classList.toggle('collapsed')">
                        <span class="tool-call-icon">▶</span>
                        <span class="tool-call-name">${this.escapeHtml(tc.name)}</span>
                        <span class="tool-call-args-summary">${this.escapeHtml(argsSummary)}</span>
                    </div>
                    <div class="tool-call-body">
                        <pre>${this.escapeHtml(argsStr)}</pre>
                    </div>
                `;
                contentEl.appendChild(div);
            }
        });
        this.scrollToBottom();
    }
    
    appendToolResult(msg) {
        const msgEl = document.getElementById('current-ai-message');
        if (!msgEl) return;
        const contentEl = msgEl.querySelector('.message-content');
        if (msg.name === 'spawn_agent') {
            this.appendSubAgentResult(contentEl, msg);
            return;
        }
        const toolCallEl = contentEl.querySelector(`.tool-call[data-tool-call-id="${msg.tool_call_id}"]`);
        const resultContent = msg.content.length > 500
            ? msg.content.substring(0, 500) + '...'
            : msg.content;
        const resultDiv = document.createElement('div');
        resultDiv.className = 'tool-result';
        resultDiv.dataset.toolCallId = msg.tool_call_id;
        resultDiv.innerHTML = `
            <div class="tool-result-header">结果: ${this.escapeHtml(msg.name)}</div>
            <pre class="tool-result-content">${this.escapeHtml(resultContent)}</pre>
        `;
        if (toolCallEl) {
            toolCallEl.after(resultDiv);
        } else {
            contentEl.appendChild(resultDiv);
        }
        this.scrollToBottom();
    }
    
    getArgsSummary(args) {
        if (!args || typeof args !== 'object') return '';
        const keys = Object.keys(args);
        if (keys.length === 0) return '';
        const first = keys[0];
        const val = args[first];
        const valStr = typeof val === 'string' ? val : JSON.stringify(val);
        const truncated = valStr.length > 30 ? valStr.substring(0, 30) + '...' : valStr;
        return `${first}: ${truncated}`;
    }
    
    appendSubAgentCall(contentEl, tc) {
        const agentName = tc.args && tc.args.agent_name ? tc.args.agent_name : 'unknown';
        const task = tc.args && tc.args.task ? tc.args.task : '';
        const taskSummary = task.length > 50 ? task.substring(0, 50) + '...' : task;
        const div = document.createElement('div');
        div.className = 'sub-agent-call collapsed';
        div.dataset.toolCallId = tc.id;
        div.dataset.agentName = agentName;
        div.innerHTML = `
            <div class="sub-agent-header" onclick="this.parentElement.classList.toggle('collapsed')">
                <span class="sub-agent-icon">▶</span>
                <span class="sub-agent-name">🤖 ${this.escapeHtml(agentName)}</span>
                <span class="sub-agent-task">${this.escapeHtml(taskSummary)}</span>
                <span class="sub-agent-status">执行中...</span>
            </div>
            <div class="sub-agent-body">
                <div class="sub-agent-messages"></div>
            </div>
        `;
        contentEl.appendChild(div);
    }
    
    appendSubAgentResult(contentEl, msg) {
        const subAgentEl = contentEl.querySelector(`.sub-agent-call[data-tool-call-id="${msg.tool_call_id}"]`);
        if (subAgentEl) {
            const statusEl = subAgentEl.querySelector('.sub-agent-status');
            statusEl.textContent = '已完成';
            statusEl.classList.add('completed');
            this.tryLoadSubAgentSession(subAgentEl, msg);
        } else {
            const resultDiv = document.createElement('div');
            resultDiv.className = 'tool-result';
            resultDiv.dataset.toolCallId = msg.tool_call_id;
            resultDiv.innerHTML = `
                <div class="tool-result-header">结果: spawn_agent</div>
                <pre class="tool-result-content">${this.escapeHtml(msg.content.length > 500 ? msg.content.substring(0, 500) + '...' : msg.content)}</pre>
            `;
            contentEl.appendChild(resultDiv);
        }
        this.scrollToBottom();
    }
    
    async tryLoadSubAgentSession(subAgentEl, msg) {
        const agentName = subAgentEl.dataset.agentName;
        const messagesEl = subAgentEl.querySelector('.sub-agent-messages');
        try {
            const sessionId = this.extractSessionId(msg.content);
            if (sessionId) {
                await this.loadSubAgentSessionById(sessionId, messagesEl);
                return;
            }
            const sessions = await API.getSessions();
            const matching = sessions
                .filter(s => s.role === agentName)
                .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
            if (matching.length > 0) {
                await this.loadSubAgentSessionById(matching[0].session_id, messagesEl);
                return;
            }
            messagesEl.innerHTML = '<div class="sub-msg system">会话详情暂不可用</div>';
        } catch (e) {
            messagesEl.innerHTML = '<div class="sub-msg system">内容加载失败</div>';
        }
    }
    
    extractSessionId(content) {
        const match = content.match(/\[session_id:([a-f0-9\-]{36})\]/i);
        return match ? match[1] : null;
    }
    
    async loadSubAgentSessionById(sessionId, messagesEl) {
        const detail = await API.getSession(sessionId);
        if (detail && detail.messages) {
            this.renderSubAgentMessages(messagesEl, detail.messages);
        } else {
            messagesEl.innerHTML = '<div class="sub-msg system">无消息内容</div>';
        }
    }
    
    renderSubAgentMessages(container, messages) {
        container.innerHTML = '';
        messages.forEach(msg => {
            const div = document.createElement('div');
            if (msg.type === 'human' || msg.role === 'user') {
                div.className = 'sub-msg user';
                div.textContent = msg.content || '';
            } else if (msg.type === 'ai' || msg.role === 'assistant') {
                div.className = 'sub-msg assistant';
                div.textContent = msg.content || '';
            } else if (msg.type === 'tool' || msg.role === 'tool') {
                div.className = 'sub-msg tool-call';
                div.textContent = '🔧 ' + (msg.name || msg.tool_name || 'tool');
            } else if (msg.type === 'system' || msg.role === 'system') {
                return;
            } else {
                div.className = 'sub-msg';
                div.textContent = msg.content || '';
            }
            container.appendChild(div);
        });
        if (!container.children.length) {
            container.innerHTML = '<div class="sub-msg system">无消息内容</div>';
        }
    }
    
    finishAIMessage() {
        const msgEl = document.getElementById('current-ai-message');
        if (msgEl) {
            msgEl.removeAttribute('id');
            const contentEl = msgEl.querySelector('.message-content');
            contentEl.classList.remove('streaming');
        }
        this.isStreaming = false;
        this.elements.sendBtn.disabled = false;
        this.elements.sendBtn.textContent = '发送';
        this.elements.sendBtn.classList.remove('btn-danger');
        this.elements.sendBtn.classList.add('btn-primary');
    }
    
    showErrorMessage(content) {
        const msgEl = document.getElementById('current-ai-message');
        if (msgEl) {
            const contentEl = msgEl.querySelector('.message-content');
            if (!contentEl.textContent) {
                contentEl.textContent = `错误: ${content}`;
            }
        }
    }
    
    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    async loadStatus() {
        try {
            const status = await API.getStatus();
            
            this.elements.modelStatus.textContent = `模型: ${status.model}`;
            
            if (status.mcp_enabled) {
                this.elements.mcpStatus.textContent = `MCP: 已连接`;
                this.elements.mcpStatus.className = 'status-item connected';
            } else {
                this.elements.mcpStatus.textContent = `MCP: 未启用`;
                this.elements.mcpStatus.className = 'status-item';
            }
            
            if (status.browser_alive !== null) {
                this.elements.browserStatus.textContent = `浏览器: ${status.browser_alive ? '运行中' : '已关闭'}`;
                this.elements.browserStatus.className = `status-item ${status.browser_alive ? 'connected' : 'disconnected'}`;
            } else {
                this.elements.browserStatus.textContent = '浏览器: --';
                this.elements.browserStatus.className = 'status-item';
            }
        } catch (error) {
            console.error('Failed to load status:', error);
        }
    }
    
    async loadSkills() {
        try {
            const skills = await API.getSkills();
            this.elements.skillsList.innerHTML = '';
            
            skills.forEach(skill => {
                const li = document.createElement('li');
                li.className = 'nav-item';
                li.innerHTML = `
                    <span class="nav-icon">📄</span>
                    <span class="nav-text">${skill.name}</span>
                `;
                li.title = skill.description;
                this.elements.skillsList.appendChild(li);
            });
            
            this.toolbarSkills = skills;
        } catch (error) {
            console.error('Failed to load skills:', error);
        }
    }
    
    updateConnectionStatus(connected) {
        console.log('WebSocket connection status:', connected);
    }
    
    async loadCommands() {
        try {
            this.commands = await API.getCommands();
            this.initCommandAutocomplete();
        } catch (error) {
            console.error('Failed to load commands:', error);
        }
    }
    
    initCommandAutocomplete() {
        if (!this.elements.chatInput) return;
        
        this.elements.chatInput.addEventListener('input', (e) => {
            const value = e.target.value;
            if (value.startsWith('/')) {
                this.showCommandSuggestions(value);
            } else {
                this.hideCommandSuggestions();
            }
        });
    }
    
    showCommandSuggestions(input) {
        const partial = input.slice(1).toLowerCase();
        const matches = this.commands.filter(cmd => 
            cmd.name.startsWith(partial) ||
            cmd.aliases.some(a => a.startsWith(partial))
        );
        
        if (matches.length === 0) {
            this.hideCommandSuggestions();
            return;
        }
        
        let suggestionsEl = document.getElementById('command-suggestions');
        if (!suggestionsEl) {
            suggestionsEl = document.createElement('div');
            suggestionsEl.id = 'command-suggestions';
            suggestionsEl.className = 'command-suggestions';
            this.elements.chatInput.parentNode.style.position = 'relative';
            this.elements.chatInput.parentNode.appendChild(suggestionsEl);
        }
        
        suggestionsEl.innerHTML = matches.map(cmd => `
            <div class="suggestion-item" data-command="/${cmd.name}">
                <span class="suggestion-cmd">/${cmd.name}</span>
                <span class="suggestion-desc">${cmd.description}</span>
            </div>
        `).join('');
        
        suggestionsEl.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                this.elements.chatInput.value = item.dataset.command + ' ';
                this.hideCommandSuggestions();
                this.elements.chatInput.focus();
            });
        });
    }
    
    hideCommandSuggestions() {
        const suggestionsEl = document.getElementById('command-suggestions');
        if (suggestionsEl) {
            suggestionsEl.remove();
        }
    }
    
    handleCommandResult(result) {
        if (this.isCommandMode) {
            const msgEl = document.createElement('div');
            msgEl.className = 'message ai';
            const contentEl = document.createElement('div');
            contentEl.className = 'message-content';
            if (result.data) {
                this.renderStructuredResult(contentEl, result);
            } else {
                contentEl.textContent = result.message;
            }
            msgEl.innerHTML = `<div class="message-header">系统</div>`;
            msgEl.appendChild(contentEl);
            this.elements.chatMessages.appendChild(msgEl);
            this.scrollToBottom();
            
            this.isCommandMode = false;
            this.elements.sendBtn.disabled = false;
        } else {
            const msgEl = document.getElementById('current-ai-message');
            if (msgEl) {
                const contentEl = msgEl.querySelector('.message-content');
                if (result.data) {
                    this.renderStructuredResult(contentEl, result);
                } else {
                    contentEl.textContent = result.message;
                }
                contentEl.classList.remove('streaming');
                msgEl.removeAttribute('id');
            }
            
            this.isStreaming = false;
            this.elements.sendBtn.disabled = false;
            this.elements.sendBtn.textContent = '发送';
            this.elements.sendBtn.classList.remove('btn-danger');
            this.elements.sendBtn.classList.add('btn-primary');
        }
    }
    
    renderStructuredResult(container, result) {
        if (result.data.roles) {
            container.innerHTML = this.renderRoleList(result.data.roles);
        } else if (result.data.role && result.data.skills) {
            container.innerHTML = this.renderRoleSwitch(result);
        } else if (result.data.role_info) {
            container.innerHTML = this.renderRoleInfo(result.data.role_info);
        } else if (result.data.loaded !== undefined) {
            container.innerHTML = this.renderSkillLoadResult(result.data);
        } else if (result.data.skills) {
            container.innerHTML = this.renderSkillList(result.data.skills);
        } else if (result.data.tools) {
            container.innerHTML = this.renderToolList(result.data.tools);
        } else if (result.data.history) {
            container.innerHTML = this.renderHistoryList(result.data.history);
        } else if (result.data.prompt !== undefined) {
            container.innerHTML = this.renderPrompt(result.data.prompt, result.data.truncated);
        } else if (result.data.model) {
            container.innerHTML = this.renderConfig(result.data);
        } else {
            container.innerHTML = `<div class="result-list"><pre>${this.escapeHtml(result.message)}</pre></div>`;
        }
    }
    
    renderRoleList(roles) {
        const items = roles.map(r =>
            `<li class="${r.is_current ? 'current' : ''}"><strong>${r.name}</strong>${r.is_current ? ' (当前)' : ''}: ${r.description}</li>`
        ).join('');
        return `<div class="result-list"><h4>可用角色</h4><ul>${items}</ul></div>`;
    }
    
    renderSkillList(skills) {
        const items = skills.map(s => {
            const name = s.name || s;
            const desc = s.description || '';
            const triggers = s.triggers && s.triggers.length ? `<br><small>触发词: ${s.triggers.join(', ')}</small>` : '';
            return `<li><strong>${name}</strong>: ${desc}${triggers}</li>`;
        }).join('');
        return `<div class="result-list"><h4>可用Skills</h4><ul>${items}</ul></div>`;
    }
    
    renderSkillLoadResult(data) {
        const parts = [];
        if (data.loaded && data.loaded.length > 0) {
            data.loaded.forEach(name => this.loadedSkillNames.add(name));
            parts.push(`<li style="color: var(--success-color);"><strong>已加载</strong>: ${data.loaded.join(', ')}</li>`);
        }
        if (data.already_loaded && data.already_loaded.length > 0) {
            parts.push(`<li style="color: var(--text-muted);"><strong>已加载过，跳过</strong>: ${data.already_loaded.join(', ')}</li>`);
        }
        if (data.not_found && data.not_found.length > 0) {
            parts.push(`<li style="color: var(--error-color);"><strong>未找到</strong>: ${data.not_found.join(', ')}</li>`);
        }
        return `<div class="result-list"><h4>Skill加载结果</h4><ul>${parts.join('')}</ul></div>`;
    }
    
    renderToolList(tools) {
        const items = tools.map(t =>
            `<li><strong>${t.name}</strong>: ${t.description}</li>`
        ).join('');
        return `<div class="result-list"><h4>可用工具</h4><ul>${items}</ul></div>`;
    }
    
    renderHistoryList(history) {
        const items = history.map(h =>
            `<li><span class="msg-type">${h.type}</span>: ${this.escapeHtml(h.content.substring(0, 100))}${h.content.length > 100 ? '...' : ''}</li>`
        ).join('');
        return `<div class="result-list"><h4>对话历史</h4><ul>${items}</ul></div>`;
    }

    renderRoleSwitch(result) {
        const msg = this.escapeHtml(result.message).replace(/\n/g, '<br>');
        const skills = result.data.skills;
        const skillItems = skills.map(s => {
            const name = s.name || s;
            const desc = s.description || '';
            return `<li><strong>${name}</strong>: ${desc}</li>`;
        }).join('');
        return `<div class="result-list"><div class="role-switch-msg">${msg}</div>${skills.length ? `<h4>Skills</h4><ul>${skillItems}</ul>` : ''}</div>`;
    }

    renderRoleInfo(info) {
        const model = info.model || {};
        const execution = info.execution || {};
        const tools = info.available_tools || [];
        const metadata = info.metadata || {};
        const metaItems = Object.entries(metadata).map(([k, v]) => `<li><strong>${k}</strong>: ${v}</li>`).join('');
        return `<div class="result-list"><h4>角色: ${info.name}</h4><p>${info.description}</p><h4>模型配置</h4><ul><li>继承默认配置: ${model.inherit ? '是' : '否'}</li><li>提供商: ${model.provider || '-'}</li><li>模型: ${model.name || '-'}</li><li>Temperature: ${model.temperature || '-'}</li><li>Max Tokens: ${model.max_tokens || '-'}</li></ul><h4>执行参数</h4><ul><li>最大上下文Token: ${execution.max_context_tokens || '-'}</li><li>超时时间: ${execution.timeout || '-'}秒</li><li>递归限制: ${execution.recursion_limit || '-'}</li></ul><h4>可用工具</h4><p>${tools.length ? tools.join(', ') : '全部'}</p>${metaItems ? `<h4>元数据</h4><ul>${metaItems}</ul>` : ''}</div>`;
    }

    renderPrompt(prompt, truncated) {
        const display = truncated ? this.escapeHtml(prompt.substring(0, 500)) + '...' : this.escapeHtml(prompt);
        return `<div class="result-list"><h4>系统提示词</h4><pre>${display}</pre></div>`;
    }

    renderConfig(data) {
        const model = data.model || {};
        const mcp = data.mcp_connected;
        return `<div class="result-list"><h4>当前配置</h4><ul><li>模型: ${model.provider || '-'}/${model.name || '-'}</li><li>Temperature: ${model.temperature || '-'}</li><li>Max Tokens: ${model.max_tokens || '-'}</li>${mcp !== null && mcp !== undefined ? `<li>MCP状态: ${mcp ? '已连接' : '未连接'}</li>` : ''}</ul></div>`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
