class App {
    constructor() {
        this.configEditor = new ConfigEditor();
        this.wsClient = null;
        this.currentView = 'chat';
        this.isStreaming = false;
        this.knowledgeManager = null;
        this.testcaseManager = null;
        this.commands = [];
        
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
            sidebarToggle: document.getElementById('sidebarToggle')
        };
        
        this.init();
    }
    
    init() {
        this.initNavigation();
        this.initChat();
        this.initWebSocket();
        this.initSidebarToggle();
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
                this.appendAIMessage(data.content);
                break;
            case 'done':
                this.finishAIMessage();
                break;
            case 'error':
                this.showErrorMessage(data.content);
                this.finishAIMessage();
                break;
        }
    }
    
    sendMessage() {
        const content = this.elements.chatInput.value.trim();
        if (!content || this.isStreaming) return;
        
        this.addUserMessage(content);
        this.elements.chatInput.value = '';
        this.isStreaming = true;
        this.elements.sendBtn.disabled = true;
        
        this.createAIMessage();
        this.wsClient.send('task', content);
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
    }
    
    appendAIMessage(content) {
        const msgEl = document.getElementById('current-ai-message');
        if (msgEl) {
            const contentEl = msgEl.querySelector('.message-content');
            contentEl.textContent += content;
            this.scrollToBottom();
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
    }
    
    renderStructuredResult(container, result) {
        if (result.data.roles) {
            container.innerHTML = this.renderRoleList(result.data.roles);
        } else if (result.data.skills) {
            container.innerHTML = this.renderSkillList(result.data.skills);
        } else if (result.data.tools) {
            container.innerHTML = this.renderToolList(result.data.tools);
        } else if (result.data.history) {
            container.innerHTML = this.renderHistoryList(result.data.history);
        } else {
            container.innerHTML = `<pre>${this.escapeHtml(result.message)}</pre>`;
        }
    }
    
    renderRoleList(roles) {
        return `
            <div class="result-list">
                <h4>可用角色</h4>
                <ul>
                    ${roles.map(r => `
                        <li class="${r.is_current ? 'current' : ''}">
                            <strong>${r.name}</strong>${r.is_current ? ' (当前)' : ''}: ${r.description}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }
    
    renderSkillList(skills) {
        return `
            <div class="result-list">
                <h4>可用Skills</h4>
                <ul>
                    ${skills.map(s => `
                        <li>
                            <strong>${s.name}</strong>: ${s.description}
                            ${s.triggers && s.triggers.length ? `<br><small>触发词: ${s.triggers.join(', ')}</small>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }
    
    renderToolList(tools) {
        return `
            <div class="result-list">
                <h4>可用工具</h4>
                <ul>
                    ${tools.map(t => `
                        <li><strong>${t.name}</strong>: ${t.description}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }
    
    renderHistoryList(history) {
        return `
            <div class="result-list">
                <h4>对话历史</h4>
                <ul>
                    ${history.map(h => `
                        <li>
                            <span class="msg-type">${h.type}</span>: 
                            ${this.escapeHtml(h.content.substring(0, 100))}${h.content.length > 100 ? '...' : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
