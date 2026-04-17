class ChatPanel {
    constructor(options) {
        this.container = options.container;
        this.onSend = options.onSend || null;
        this.placeholder = options.placeholder || '输入任务描述...';
        
        this.messages = [];
        this.isStreaming = false;
        this.isCommandMode = false;
        this.currentAIMessage = null;
        this.toolbarSkills = [];
        this.toolbarSelectedSkills = new Set();
        this.loadedSkillNames = new Set();
        
        this.messagesEl = null;
        this.inputEl = null;
        this.sendBtn = null;
        this.toolbarEl = null;
        this.skillDropdownEl = null;
        this.skillDropdownListEl = null;
        
        this.render();
    }
    
    render() {
        const wrapper = document.createElement('div');
        wrapper.className = 'chat-panel-wrapper';
        
        this.messagesEl = document.createElement('div');
        this.messagesEl.className = 'chat-messages';
        
        this.showWelcome();
        
        this.toolbarEl = document.createElement('div');
        this.toolbarEl.className = 'chat-toolbar';
        
        const skillBtn = document.createElement('button');
        skillBtn.className = 'toolbar-btn skill-btn';
        skillBtn.title = '选择Skill';
        skillBtn.innerHTML = '<span class="toolbar-btn-icon">⚡</span><span class="toolbar-btn-text">Skill</span>';
        skillBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleSkillDropdown();
        });
        
        this.skillDropdownEl = document.createElement('div');
        this.skillDropdownEl.className = 'skill-dropdown';
        
        const dropdownHeader = document.createElement('div');
        dropdownHeader.className = 'skill-dropdown-header';
        dropdownHeader.innerHTML = '<span>选择要加载的Skill</span>';
        
        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'skill-dropdown-confirm-btn';
        confirmBtn.textContent = '加载选中';
        confirmBtn.addEventListener('click', () => this.loadSelectedSkills());
        dropdownHeader.appendChild(confirmBtn);
        
        this.skillDropdownListEl = document.createElement('div');
        this.skillDropdownListEl.className = 'skill-dropdown-list';
        
        this.skillDropdownEl.appendChild(dropdownHeader);
        this.skillDropdownEl.appendChild(this.skillDropdownListEl);
        this.toolbarEl.appendChild(skillBtn);
        this.toolbarEl.appendChild(this.skillDropdownEl);
        
        document.addEventListener('click', (e) => {
            if (this.skillDropdownEl && this.skillDropdownEl.classList.contains('open')) {
                if (!this.skillDropdownEl.contains(e.target) && !skillBtn.contains(e.target)) {
                    this.closeSkillDropdown();
                }
            }
        });
        
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
        wrapper.appendChild(this.toolbarEl);
        wrapper.appendChild(inputArea);
        
        this.container.appendChild(wrapper);
    }
    
    toggleSkillDropdown() {
        if (!this.skillDropdownEl) return;
        if (this.skillDropdownEl.classList.contains('open')) {
            this.closeSkillDropdown();
        } else {
            this.openSkillDropdown();
        }
    }
    
    openSkillDropdown() {
        if (!this.skillDropdownEl) return;
        this.renderSkillDropdownList();
        this.skillDropdownEl.classList.add('open');
    }
    
    closeSkillDropdown() {
        if (!this.skillDropdownEl) return;
        this.skillDropdownEl.classList.remove('open');
    }
    
    async renderSkillDropdownList() {
        if (!this.skillDropdownListEl) return;
        try {
            const skills = await API.getSkills();
            this.toolbarSkills = skills;
            this.skillDropdownListEl.innerHTML = '';
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
                this.skillDropdownListEl.appendChild(item);
            });
        } catch (e) {
            this.skillDropdownListEl.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-muted);font-size:0.8rem;">加载失败</div>';
        }
    }
    
    updateToolbarSelectedCount() {
        const skillBtn = this.toolbarEl ? this.toolbarEl.querySelector('.skill-btn') : null;
        if (!skillBtn) return;
        const countEl = skillBtn.querySelector('.selected-count');
        if (this.toolbarSelectedSkills.size > 0) {
            if (countEl) {
                countEl.textContent = this.toolbarSelectedSkills.size;
            } else {
                const span = document.createElement('span');
                span.className = 'selected-count';
                span.textContent = this.toolbarSelectedSkills.size;
                skillBtn.appendChild(span);
            }
        } else {
            if (countEl) countEl.remove();
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
        this.sendBtn.disabled = true;
        if (this.onSend) {
            this.onSend(command);
        }
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
        this.sendBtn.disabled = false;
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
