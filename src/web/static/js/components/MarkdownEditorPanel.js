class MarkdownEditorPanel {
    constructor(options) {
        this.container = options.container;
        this.placeholder = options.placeholder || '选择一个文件进行编辑...';
        this.onContentChange = options.onContentChange || null;
        this.onSave = options.onSave || null;
        
        this.currentContent = '';
        this.editorEl = null;
        this.saveBtn = null;
        this.updateTimeout = null;
        
        if (this.container) {
            this.render();
        } else {
            console.error('MarkdownEditorPanel: container is null or undefined');
        }
    }
    
    render() {
        const wrapper = document.createElement('div');
        wrapper.className = 'markdown-editor-wrapper';
        
        this.editorEl = document.createElement('textarea');
        this.editorEl.className = 'markdown-editor';
        this.editorEl.placeholder = this.placeholder;
        this.editorEl.spellcheck = false;
        
        this.editorEl.addEventListener('input', () => {
            this.currentContent = this.editorEl.value;
            
            if (this.updateTimeout) {
                clearTimeout(this.updateTimeout);
            }
            this.updateTimeout = setTimeout(() => {
                if (this.onContentChange) {
                    this.onContentChange(this.currentContent);
                }
            }, 300);
        });
        
        wrapper.appendChild(this.editorEl);
        this.container.appendChild(wrapper);
    }
    
    addSaveButton(headerEl) {
        if (!headerEl) return;
        this.saveBtn = document.createElement('button');
        this.saveBtn.className = 'btn btn-primary btn-sm';
        this.saveBtn.textContent = '保存';
        this.saveBtn.addEventListener('click', () => this.save());
        headerEl.appendChild(this.saveBtn);
    }
    
    setContent(content) {
        if (!this.editorEl) {
            console.error('MarkdownEditorPanel: editorEl is null, cannot setContent');
            return;
        }
        this.currentContent = content || '';
        this.editorEl.value = this.currentContent;
        
        if (this.onContentChange) {
            this.onContentChange(this.currentContent);
        }
    }
    
    getContent() {
        return this.currentContent;
    }
    
    async save() {
        if (!this.onSave) return;
        
        if (this.saveBtn) {
            this.saveBtn.disabled = true;
            this.saveBtn.textContent = '保存中...';
        }
        
        try {
            await this.onSave(this.currentContent);
            this.showMessage('保存成功', 'success');
        } catch (error) {
            this.showMessage(`保存失败: ${error.message}`, 'error');
        } finally {
            if (this.saveBtn) {
                this.saveBtn.disabled = false;
                this.saveBtn.textContent = '保存';
            }
        }
    }
    
    showMessage(message, type) {
        if (!this.container) return;
        let msgEl = this.container.querySelector('.save-message');
        if (!msgEl) {
            msgEl = document.createElement('span');
            msgEl.className = 'save-message';
            this.container.appendChild(msgEl);
        }
        msgEl.textContent = message;
        msgEl.className = `save-message ${type}`;
        
        setTimeout(() => {
            msgEl.textContent = '';
        }, 3000);
    }
    
    focus() {
        if (this.editorEl) {
            this.editorEl.focus();
        }
    }
    
    clear() {
        this.setContent('');
    }
}

window.MarkdownEditorPanel = MarkdownEditorPanel;
