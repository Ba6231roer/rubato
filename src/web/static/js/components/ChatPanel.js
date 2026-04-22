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
        this.currentRoleName = null;
        this.fileReferences = [];
        
        this.messagesEl = null;
        this.inputEl = null;
        this.sendBtn = null;
        this.toolbarEl = null;
        this.skillDropdownEl = null;
        this.skillDropdownListEl = null;
        this.roleDropdownEl = null;
        this.roleDropdownListEl = null;
        this.fileRefsEl = null;
        
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
        
        const roleBtn = document.createElement('button');
        roleBtn.className = 'toolbar-btn role-btn';
        roleBtn.title = '选择角色';
        roleBtn.innerHTML = '<span class="toolbar-btn-icon">🎭</span><span class="toolbar-btn-text">Role</span>';
        roleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleRoleDropdown();
        });
        
        this.roleDropdownEl = document.createElement('div');
        this.roleDropdownEl.className = 'role-dropdown';
        
        const roleDropdownHeader = document.createElement('div');
        roleDropdownHeader.className = 'role-dropdown-header';
        roleDropdownHeader.innerHTML = '<span>选择角色</span>';
        
        this.roleDropdownListEl = document.createElement('div');
        this.roleDropdownListEl.className = 'role-dropdown-list';
        
        this.roleDropdownEl.appendChild(roleDropdownHeader);
        this.roleDropdownEl.appendChild(this.roleDropdownListEl);
        
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
        this.toolbarEl.appendChild(roleBtn);
        this.toolbarEl.appendChild(this.roleDropdownEl);
        this.toolbarEl.appendChild(skillBtn);
        this.toolbarEl.appendChild(this.skillDropdownEl);
        
        document.addEventListener('click', (e) => {
            if (this.roleDropdownEl && this.roleDropdownEl.classList.contains('open')) {
                if (!this.roleDropdownEl.contains(e.target) && !roleBtn.contains(e.target)) {
                    this.closeRoleDropdown();
                }
            }
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
            if (e.key === 'Backspace' && this.inputEl.selectionStart === 0 && this.inputEl.selectionEnd === 0) {
                if (this.removeLastFileReference()) {
                    e.preventDefault();
                    return;
                }
            }
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.send();
            }
        });
        
        this.inputEl.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.inputEl.classList.add('drag-over');
        });
        
        this.inputEl.addEventListener('dragleave', (e) => {
            e.preventDefault();
            this.inputEl.classList.remove('drag-over');
        });
        
        this.inputEl.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.inputEl.classList.remove('drag-over');
            this.handleFileDrop(e);
        });
        
        this.sendBtn.addEventListener('click', () => this.send());
        
        inputArea.appendChild(this.inputEl);
        inputArea.appendChild(this.sendBtn);
        
        wrapper.appendChild(this.messagesEl);
        wrapper.appendChild(this.toolbarEl);
        
        this.fileRefsEl = document.createElement('div');
        this.fileRefsEl.className = 'file-refs-container';
        wrapper.appendChild(this.fileRefsEl);
        
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
        this.closeRoleDropdown();
        this.renderSkillDropdownList();
        this.skillDropdownEl.classList.add('open');
    }
    
    closeSkillDropdown() {
        if (!this.skillDropdownEl) return;
        this.skillDropdownEl.classList.remove('open');
    }
    
    toggleRoleDropdown() {
        if (!this.roleDropdownEl) return;
        if (this.roleDropdownEl.classList.contains('open')) {
            this.closeRoleDropdown();
        } else {
            this.openRoleDropdown();
        }
    }
    
    openRoleDropdown() {
        if (!this.roleDropdownEl) return;
        this.closeSkillDropdown();
        this.renderRoleDropdownList();
        this.roleDropdownEl.classList.add('open');
    }
    
    closeRoleDropdown() {
        if (!this.roleDropdownEl) return;
        this.roleDropdownEl.classList.remove('open');
    }
    
    async renderRoleDropdownList() {
        if (!this.roleDropdownListEl) return;
        try {
            const roles = await API.getRoles();
            this.roleDropdownListEl.innerHTML = '';
            roles.forEach(role => {
                const item = document.createElement('div');
                item.className = 'role-dropdown-item';
                if (role.is_current) {
                    item.classList.add('current');
                }
                item.innerHTML = `
                    <div class="role-dropdown-item-info">
                        <span class="role-dropdown-item-name">${this.escapeHtml(role.name)}</span>
                        <span class="role-dropdown-item-desc">${this.escapeHtml(role.description || '')}</span>
                    </div>
                    ${role.is_current ? '<span class="current-indicator">当前</span>' : ''}
                `;
                item.addEventListener('click', () => this.selectRole(role.name));
                this.roleDropdownListEl.appendChild(item);
            });
        } catch (e) {
            this.roleDropdownListEl.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-muted);font-size:0.8rem;">加载失败</div>';
        }
    }
    
    selectRole(name) {
        this.closeRoleDropdown();
        this.currentRoleName = name;
        this.addUserMessage('/role ' + name);
        this.isCommandMode = true;
        this.sendBtn.disabled = true;
        if (this.onSend) {
            this.onSend('/role ' + name);
        }
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
        if (!content && this.fileReferences.length === 0) return;
        
        let fullContent = content;
        if (this.fileReferences.length > 0) {
            const fileRefs = this.fileReferences.map(ref => `@${ref.path}`).join(' ');
            fullContent = fileRefs + (content ? ' ' + content : '');
        }
        
        this.addUserMessage(fullContent);
        this.inputEl.value = '';
        this.fileReferences = [];
        this.renderFileReferences();
        
        if (this.onSend) {
            if (fullContent.startsWith('/')) {
                this.isCommandMode = true;
                this.sendBtn.disabled = true;
                this.onSend(fullContent);
            } else {
                this.isStreaming = true;
                this.sendBtn.disabled = true;
                this.createAIMessage();
                this.onSend(fullContent);
            }
        }
    }
    
    _normalizeFilePath(filePath) {
        let normalized = filePath.replace(/\\/g, '/');
        if (!normalized.startsWith('workspace/')) {
            normalized = 'workspace/' + normalized;
        }
        return normalized;
    }

    handleFileDrop(e) {
        const rawPath = e.dataTransfer.getData('text/plain');
        if (!rawPath) return;
        
        const filePath = this._normalizeFilePath(rawPath);
        const fileName = filePath.split('/').pop();
        if (this.fileReferences.some(ref => ref.path === filePath)) return;
        
        this.fileReferences.push({ path: filePath, name: fileName });
        this.renderFileReferences();
    }
    
    addFileReference(rawPath) {
        const filePath = this._normalizeFilePath(rawPath);
        const fileName = filePath.split('/').pop();
        if (this.fileReferences.some(ref => ref.path === filePath)) return;
        this.fileReferences.push({ path: filePath, name: fileName });
        this.renderFileReferences();
    }
    
    renderFileReferences() {
        if (!this.fileRefsEl) return;
        this.fileRefsEl.innerHTML = '';
        this.fileReferences.forEach((ref, index) => {
            const chip = document.createElement('span');
            chip.className = 'file-ref-chip';
            chip.textContent = ref.name;
            chip.dataset.index = index;
            chip.title = ref.path;
            chip.addEventListener('click', () => {
                this.fileReferences.splice(index, 1);
                this.renderFileReferences();
            });
            this.fileRefsEl.appendChild(chip);
        });
    }
    
    removeLastFileReference() {
        if (this.fileReferences.length > 0 && this.inputEl.selectionStart === 0) {
            this.fileReferences.pop();
            this.renderFileReferences();
            return true;
        }
        return false;
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
            contentEl.appendChild(document.createTextNode(content));
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
    
    appendToolCalls(toolCalls) {
        if (!this.currentAIMessage) return;
        const contentEl = this.currentAIMessage.querySelector('.message-content');
        if (!contentEl) return;
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
        if (!this.currentAIMessage) return;
        const contentEl = this.currentAIMessage.querySelector('.message-content');
        if (!contentEl) return;
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
                .filter(s => s.role === agentName && s.parent_session_id)
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
        const match = content.match(/session[_\-]?id[:\s]*([a-f0-9\-]{8,})/i);
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

    updateLastUserMessage(content) {
        const userMessages = this.messagesEl.querySelectorAll('.message.user');
        if (userMessages.length === 0) return;
        const lastUserMsg = userMessages[userMessages.length - 1];
        const contentEl = lastUserMsg.querySelector('.message-content');
        if (contentEl) {
            contentEl.textContent = content;
        }
        const lastMsg = this.messages.filter(m => m.type === 'user').pop();
        if (lastMsg) {
            lastMsg.content = content;
        }
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
    
    addCompressionNotice(data) {
        const msgEl = document.createElement('div');
        msgEl.className = 'message system';
        const originalCount = data.original_count || '?';
        const compressedCount = data.compressed_count || '?';
        msgEl.innerHTML = `
            <div class="message-header">系统</div>
            <div class="message-content compression-notice">⚠️ 上下文已压缩（压缩前${originalCount}条消息 → 压缩后${compressedCount}条消息）</div>
        `;
        this.messagesEl.appendChild(msgEl);
        this.messages.push({ type: 'system', content: '上下文已压缩' });
        this.scrollToBottom();
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
