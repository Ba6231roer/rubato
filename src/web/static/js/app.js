class App {
    constructor() {
        this.configEditor = new ConfigEditor();
        this.wsClient = null;
        this.currentView = 'chat';
        this.isStreaming = false;
        
        this.elements = {
            configNav: document.getElementById('configNav'),
            configView: document.getElementById('configView'),
            sysconfigView: document.getElementById('sysconfigView'),
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
            skillsList: document.getElementById('skillsList')
        };
        
        this.init();
    }
    
    init() {
        this.initNavigation();
        this.initChat();
        this.initWebSocket();
        this.loadStatus();
        this.loadSkills();
        
        setInterval(() => this.loadStatus(), 30000);
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
        this.elements.sysconfigView.classList.add('hidden');
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
            case 'sysconfig':
                this.elements.sysconfigView.classList.remove('hidden');
                break;
            case 'testcases':
                this.elements.testcasesView.classList.remove('hidden');
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
        switch (data.type) {
            case 'connected':
                console.log('WS connected:', data.content);
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
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
