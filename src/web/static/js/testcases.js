class TestCaseManager {
    constructor() {
        this.currentFile = null;
        this.panelLayout = null;
        this.directoryTree = null;
        this.markdownEditor = null;
        this.mindmapPanel = null;
        this.chatPanel = null;
        this.initialized = false;
        
        this.container = document.getElementById('testcasesView');
    }
    
    init() {
        if (this.initialized) return;
        this.initialized = true;
        
        this.createLayout();
        this.initComponents();
    }
    
    createLayout() {
        this.container.innerHTML = '';
        
        this.panelLayout = new PanelLayout({
            container: this.container,
            minPanelWidth: 200
        });
        
        const treePanel = this.panelLayout.addPanel({
            id: 'testcases-tree-panel',
            title: '测试案例目录',
            width: '11.1%',
            minWidth: 200
        });
        
        const editorPanel = this.panelLayout.addPanel({
            id: 'testcases-editor-panel',
            title: 'Markdown编辑',
            width: '11.1%',
            minWidth: 200
        });
        
        const mindmapPanel = this.panelLayout.addPanel({
            id: 'testcases-mindmap-panel',
            title: '思维导图',
            width: '44.4%',
            minWidth: 200
        });
        
        const chatPanel = this.panelLayout.addPanel({
            id: 'testcases-chat-panel',
            title: '任务输入',
            width: '33.3%',
            minWidth: 200
        });
        
        this.treePanel = treePanel;
        this.editorPanel = editorPanel;
        this.mindmapPanelContainer = mindmapPanel;
        this.chatPanelContainer = chatPanel;
    }
    
    initComponents() {
        this.directoryTree = new DirectoryTree({
            container: this.treePanel.contentEl,
            title: '测试案例目录',
            loadTreeFn: () => API.getTestCaseTree(),
            onFileSelect: (path) => this.selectFile(path)
        });
        
        this.markdownEditor = new MarkdownEditorPanel({
            container: this.editorPanel.contentEl,
            placeholder: '选择一个.md文件进行编辑...',
            onContentChange: (content) => this.handleContentChange(content),
            onSave: (content) => this.saveFile(content)
        });
        
        this.markdownEditor.addSaveButton(this.editorPanel.headerEl);
        
        this.mindmapPanel = new MindmapPanel({
            container: this.mindmapPanelContainer.contentEl,
            onContentChange: (content) => this.handleMindmapChange(content)
        });
        
        this.chatPanel = new ChatPanel({
            container: this.chatPanelContainer.contentEl,
            placeholder: '输入任务描述...',
            onSend: (content) => this.handleTaskSend(content)
        });
    }
    
    async selectFile(path) {
        this.currentFile = path;
        
        try {
            const data = await API.getTestCaseFile(path);
            this.markdownEditor.setContent(data.content);
            this.mindmapPanel.setContent(data.content);
        } catch (error) {
            console.error('Failed to load file:', error);
            this.markdownEditor.setContent(`# 加载文件失败\n\n${error.message}`);
        }
    }
    
    handleContentChange(content) {
        this.mindmapPanel.setContent(content);
    }
    
    handleMindmapChange(content) {
        this.markdownEditor.setContent(content);
    }
    
    async saveFile(content) {
        if (!this.currentFile) {
            throw new Error('请先选择一个文件');
        }
        
        const result = await API.updateTestCaseFile(this.currentFile, content);
        if (!result.success) {
            throw new Error(result.message || '保存失败');
        }
        
        return result;
    }
    
    handleTaskSend(content) {
        if (window.app && window.app.wsClient) {
            window.app.wsClient.send('task', content);
        } else {
            console.warn('WebSocket not available');
            this.chatPanel.addMessage('WebSocket连接不可用，请刷新页面', 'ai');
        }
    }
    
    handleWSMessage(data) {
        switch (data.type) {
            case 'command_result':
                if (this.chatPanel.isCommandMode) {
                    const result = data.content;
                    const message = result.message || '';
                    this.chatPanel.addCommandResult(message, false);
                }
                break;
            case 'chunk':
                this.chatPanel.appendAIMessage(data.content);
                break;
            case 'done':
                this.chatPanel.finishAIMessage();
                break;
            case 'error':
                this.chatPanel.showErrorMessage(data.content);
                this.chatPanel.finishAIMessage();
                break;
            case 'interrupted':
                this.chatPanel.finishAIMessage();
                break;
        }
    }
    
    refresh() {
        if (this.directoryTree) {
            this.directoryTree.refresh();
        }
    }
}

window.TestCaseManager = TestCaseManager;
