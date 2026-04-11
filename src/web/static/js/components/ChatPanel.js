class ChatPanel {
    constructor(options) {
        this.container = options.container;
        this.onSend = options.onSend || null;
        this.placeholder = options.placeholder || '输入任务描述...';
        
        this.messages = [];
        this.isStreaming = false;
        this.isCommandMode = false;
        this.currentAIMessage = null;
        
        this.messagesEl = null;
        this.inputEl = null;
        this.sendBtn = null;
        
        this.render();
    }
    
    render() {
        const wrapper = document.createElement('div');
        wrapper.className = 'chat-panel-wrapper';
        
        this.messagesEl = document.createElement('div');
        this.messagesEl.className = 'chat-messages';
        
        this.showWelcome();
        
        const inputArea = document.createElement('div');
        inputArea.className = 'chat-input-area';
        
        this.inputEl = document.createElement('textarea');
        this.inputEl.className = 'chat-input';
        this.inputEl.placeholder = this.placeholder;
        this.inputEl.rows = 3;
        
        this.sendBtn = document.createElement('button');
        this.sendBtn.className = 'btn btn-primary send-btn';
        this.sendBtn.textContent = '发送';
        
        this.inputEl.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.send();
            }
        });
        
        this.sendBtn.addEventListener('click', () => this.send());
        
        inputArea.appendChild(this.inputEl);
        inputArea.appendChild(this.sendBtn);
        
        wrapper.appendChild(this.messagesEl);
        wrapper.appendChild(inputArea);
        
        this.container.appendChild(wrapper);
    }
    
    showWelcome() {
        this.messagesEl.innerHTML = `
            <div class="welcome-message">
                <h2>任务输入</h2>
                <p>在下方输入您的任务描述</p>
            </div>
        `;
    }
    
    send() {
        if (this.isStreaming) {
            this.stopTask();
            return;
        }
        const content = this.inputEl.value.trim();
        if (!content) return;
        
        this.addUserMessage(content);
        this.inputEl.value = '';
        
        if (this.onSend) {
            if (content.startsWith('/')) {
                this.isCommandMode = true;
                this.sendBtn.disabled = true;
                this.onSend(content);
            } else {
                this.isStreaming = true;
                this.sendBtn.disabled = true;
                this.createAIMessage();
                this.onSend(content);
            }
        }
    }
    
    stopTask() {
        if (window.app && window.app.wsClient) {
            window.app.wsClient.send('stop', '');
        }
    }
    
    addUserMessage(content) {
        const msgEl = document.createElement('div');
        msgEl.className = 'message user';
        msgEl.innerHTML = `
            <div class="message-header">用户</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        this.messagesEl.appendChild(msgEl);
        this.messages.push({ type: 'user', content });
        this.scrollToBottom();
    }
    
    createAIMessage() {
        const msgEl = document.createElement('div');
        msgEl.className = 'message ai';
        msgEl.id = this.generateAIMessageId();
        msgEl.innerHTML = `
            <div class="message-header">AI助手</div>
            <div class="message-content streaming"></div>
        `;
        this.messagesEl.appendChild(msgEl);
        this.currentAIMessage = msgEl;
        this.scrollToBottom();
        this.sendBtn.textContent = '停止';
        this.sendBtn.classList.remove('btn-primary');
        this.sendBtn.classList.add('btn-danger');
    }
    
    appendAIMessage(content) {
        if (!this.currentAIMessage) return;
        
        const contentEl = this.currentAIMessage.querySelector('.message-content');
        if (contentEl) {
            contentEl.textContent += content;
            this.scrollToBottom();
        }
    }
    
    finishAIMessage() {
        if (this.currentAIMessage) {
            const contentEl = this.currentAIMessage.querySelector('.message-content');
            if (contentEl) {
                const content = contentEl.textContent;
                this.messages.push({ type: 'ai', content });
            }
            this.currentAIMessage.removeAttribute('id');
            this.currentAIMessage = null;
        }
        
        this.isStreaming = false;
        this.sendBtn.disabled = false;
        this.sendBtn.textContent = '发送';
        this.sendBtn.classList.remove('btn-danger');
        this.sendBtn.classList.add('btn-primary');
    }
    
    addCommandResult(content, isHtml) {
        const msgEl = document.createElement('div');
        msgEl.className = 'message ai';
        const contentEl = document.createElement('div');
        contentEl.className = 'message-content';
        if (isHtml) {
            contentEl.innerHTML = content;
        } else {
            contentEl.textContent = content;
        }
        msgEl.innerHTML = `<div class="message-header">系统</div>`;
        msgEl.appendChild(contentEl);
        this.messagesEl.appendChild(msgEl);
        this.messages.push({ type: 'ai', content });
        this.scrollToBottom();
        this.isCommandMode = false;
        this.sendBtn.disabled = false;
    }

    showErrorMessage(content) {
        if (this.currentAIMessage) {
            const contentEl = this.currentAIMessage.querySelector('.message-content');
            if (contentEl && !contentEl.textContent) {
                contentEl.textContent = `错误: ${content}`;
            }
        }
    }
    
    addMessage(content, type = 'user') {
        if (type === 'user') {
            this.addUserMessage(content);
        } else if (type === 'ai') {
            this.createAIMessage();
            this.appendAIMessage(content);
            this.finishAIMessage();
        }
    }
    
    clearMessages() {
        this.messages = [];
        this.currentAIMessage = null;
        this.showWelcome();
    }
    
    setStreaming(isStreaming) {
        this.isStreaming = isStreaming;
        this.sendBtn.disabled = isStreaming;
        
        if (!isStreaming && this.currentAIMessage) {
            this.finishAIMessage();
        }
    }
    
    scrollToBottom() {
        this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }
    
    focus() {
        this.inputEl.focus();
    }
    
    generateAIMessageId() {
        return `ai-msg-${Date.now()}`;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

window.ChatPanel = ChatPanel;
