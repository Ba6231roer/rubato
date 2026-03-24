class ConfigEditor {
    constructor() {
        this.currentConfig = null;
        this.editor = document.getElementById('configEditor');
        this.title = document.getElementById('configTitle');
        this.saveBtn = document.getElementById('saveConfigBtn');
        this.reloadBtn = document.getElementById('reloadConfigBtn');
        this.messageEl = document.getElementById('configMessage');
        
        this.init();
    }
    
    init() {
        this.saveBtn.addEventListener('click', () => this.save());
        this.reloadBtn.addEventListener('click', () => this.reload());
        
        this.editor.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = this.editor.selectionStart;
                const end = this.editor.selectionEnd;
                this.editor.value = this.editor.value.substring(0, start) + '  ' + this.editor.value.substring(end);
                this.editor.selectionStart = this.editor.selectionEnd = start + 2;
            }
        });
    }
    
    async load(configName) {
        this.currentConfig = configName;
        this.showMessage('加载中...', '');
        
        try {
            const data = await API.getConfig(configName);
            this.editor.value = data.content;
            this.title.textContent = this.getConfigTitle(configName);
            this.showMessage('', '');
        } catch (error) {
            this.showMessage(error.message, 'error');
        }
    }
    
    getConfigTitle(name) {
        const titles = {
            'model': '模型配置',
            'mcp': 'MCP配置',
            'prompt': '系统提示词配置',
            'skills': 'Skill配置'
        };
        return titles[name] || name;
    }
    
    async save() {
        if (!this.currentConfig) return;
        
        this.saveBtn.disabled = true;
        this.saveBtn.textContent = '保存中...';
        
        try {
            const result = await API.updateConfig(this.currentConfig, this.editor.value);
            
            if (result.success) {
                this.showMessage('配置已保存', 'success');
            } else {
                this.showMessage(result.message, 'error');
            }
        } catch (error) {
            this.showMessage(`保存失败: ${error.message}`, 'error');
        } finally {
            this.saveBtn.disabled = false;
            this.saveBtn.textContent = '保存';
        }
    }
    
    async reload() {
        if (this.currentConfig) {
            await this.load(this.currentConfig);
        }
    }
    
    showMessage(message, type) {
        this.messageEl.textContent = message;
        this.messageEl.className = `config-message ${type}`;
    }
}
