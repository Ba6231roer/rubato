class App {
    constructor() {
        this.configEditor = new ConfigEditor();
        this.wsClient = null;
        this.currentView = 'chat';
        this.workspaceManager = null;
        this.chatPanel = null;
        this.chatInitialized = false;
        this.commands = [];

        this.elements = {
            configNav: document.getElementById('configNav'),
            configView: document.getElementById('configView'),
            workspaceView: document.getElementById('workspaceView'),
            scenariosView: document.getElementById('scenariosView'),
            execsetsView: document.getElementById('execsetsView'),
            chatView: document.getElementById('chatView'),
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
            sessionList: document.getElementById('session-list')
        };

        this.init();
    }

    init() {
        this.initNavigation();
        this.initWebSocket();
        this.initSidebarToggle();
        this.initSessionPanel();
        this.loadStatus();
        this.loadSkills();
        this.loadCommands();
        this.showView('chat');

        setInterval(() => this.loadStatus(), 30000);
    }

    initSidebarToggle() {
        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => {
                this.elements.sidebar.classList.toggle('collapsed');
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
                if (this.currentView === 'chat' && this.chatPanel) {
                    this.chatPanel.clearMessages();
                    this.renderSessionMessagesToChatPanel(detail.messages);
                }
                this.toggleSessionPanel(false);
                this.showView('chat');
            }
        } catch (e) {
            console.error('Failed to load session:', e);
        }
    }

    renderSessionMessagesToChatPanel(messages) {
        messages.forEach(msg => {
            if (msg.role === 'user' || msg.type === 'human') {
                this.chatPanel.addMessage(msg.content || '', 'user');
            } else if (msg.role === 'assistant' || msg.type === 'ai') {
                let content = msg.content || '';
                if (msg.tool_calls) {
                    msg.tool_calls.forEach(tc => {
                        content += `\n🔧 ${tc.name}`;
                    });
                }
                this.chatPanel.addMessage(content, 'ai');
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
        this.elements.workspaceView.classList.add('hidden');
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
            case 'workspace':
                this.collapseSidebar();
                this.elements.workspaceView.classList.remove('hidden');
                if (!this.workspaceManager) {
                    this.workspaceManager = new WorkspaceManager();
                }
                this.workspaceManager.init();
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
                if (!this.chatPanel) {
                    this.chatPanel = new ChatPanel({
                        container: this.elements.chatView,
                        placeholder: '输入任务描述...',
                        onSend: (content) => this.handleChatSend(content)
                    });
                }
                this.chatPanel.focus();
                break;
        }
    }

    collapseSidebar() {
        if (this.elements.sidebar && !this.elements.sidebar.classList.contains('collapsed')) {
            this.elements.sidebar.classList.add('collapsed');
            this.elements.sidebarToggle.title = '展开侧边栏';
        }
    }

    handleChatSend(content) {
        if (window.app && window.app.wsClient) {
            window.app.wsClient.send('task', content);
        }
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
        if (this.currentView === 'workspace' && this.workspaceManager) {
            this.workspaceManager.handleWSMessage(data);
            return;
        }

        if (this.currentView === 'chat' && this.chatPanel) {
            this.handleChatWSMessage(data);
            return;
        }
    }

    handleChatWSMessage(data) {
        switch (data.type) {
            case 'command_result':
                if (this.chatPanel.isCommandMode) {
                    const result = data.content;
                    const message = result.message || '';
                    this.chatPanel.addCommandResult(message, false);
                }
                break;
            case 'chunk':
                if (data.message) {
                    this.handleChatStructuredChunk(data.message);
                } else {
                    this.chatPanel.appendAIMessage(data.content);
                }
                break;
            case 'done':
                if (data.message) {
                    this.handleChatStructuredDone(data.message);
                } else {
                    this.chatPanel.finishAIMessage();
                }
                break;
            case 'error':
                this.chatPanel.showErrorMessage(data.content);
                this.chatPanel.finishAIMessage();
                break;
            case 'interrupted':
                this.chatPanel.finishAIMessage();
                break;
            case 'context_compressed':
                if (data.content) {
                    this.chatPanel.addCompressionNotice(data.content);
                }
                break;
            case 'user_message_resolved':
                if (data.content) {
                    this.chatPanel.updateLastUserMessage(data.content);
                }
                break;
        }
    }

    handleChatStructuredChunk(msg) {
        if (msg.role === 'assistant') {
            if (msg.content) {
                this.chatPanel.appendAIMessage(msg.content);
            }
            if (msg.tool_calls) {
                this.chatPanel.appendToolCalls(msg.tool_calls);
            }
        } else if (msg.role === 'tool') {
            this.chatPanel.appendToolResult(msg);
        }
    }

    handleChatStructuredDone(msg) {
        this.chatPanel.finishAIMessage();
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
        } catch (error) {
            console.error('Failed to load commands:', error);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
