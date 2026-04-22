class WorkspaceManager {
    constructor() {
        this.currentFile = null;
        this.currentFileType = null;
        this.panelLayout = null;
        this.directoryTree = null;
        this.fileEditor = null;
        this.mindmapPanel = null;
        this.chatPanel = null;
        this.initialized = false;

        this.container = document.getElementById('workspaceView');
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
            id: 'workspace-tree-panel',
            title: '工作目录',
            width: '11.1%',
            minWidth: 200
        });

        const editorPanel = this.panelLayout.addPanel({
            id: 'workspace-editor-panel',
            title: '文件编辑',
            width: '11.1%',
            minWidth: 200
        });

        const mindmapPanel = this.panelLayout.addPanel({
            id: 'workspace-mindmap-panel',
            title: '思维导图',
            width: '44.4%',
            minWidth: 200
        });

        const chatPanel = this.panelLayout.addPanel({
            id: 'workspace-chat-panel',
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
            title: '工作目录',
            loadTreeFn: () => API.getWorkspaceTree(),
            onFileSelect: (path) => this.selectFile(path)
        });

        this.fileEditor = new MarkdownEditorPanel({
            container: this.editorPanel.contentEl,
            placeholder: '选择一个文件进行编辑...',
            onContentChange: (content) => this.handleContentChange(content),
            onSave: (content) => this.saveFile(content)
        });

        this.fileEditor.addSaveButton(this.editorPanel.headerEl);

        this.mindmapPanel = new MindmapPanel({
            container: this.mindmapPanelContainer.contentEl,
            onContentChange: (content) => this.handleMindmapChange(content)
        });

        this.chatPanel = new ChatPanel({
            container: this.chatPanelContainer.contentEl,
            placeholder: '输入任务描述...',
            onSend: (content) => this.handleTaskSend(content)
        });

        this.chatPanel.selectRole('test-case-generator');
    }

    async selectFile(path) {
        this.currentFile = path;

        try {
            const data = await API.getWorkspaceFile(path);
            this.currentFileType = data.file_type || 'text';

            if (data.editable) {
                this.fileEditor.setContent(data.content || '');
                this.fileEditor.enableEditing();
            } else {
                this.fileEditor.setContent('');
                this.fileEditor.disableEditing(path);
            }

            if (this.currentFileType === 'text' && path.toLowerCase().endsWith('.md')) {
                this.mindmapPanel.setContent(data.content || '');
            } else {
                this.mindmapPanel.clearMindmap();
                this.mindmapPanel.mindmapEl.innerHTML = '<div class="mindmap-placeholder">选择Markdown文件查看思维导图</div>';
            }
        } catch (error) {
            console.error('Failed to load file:', error);
            this.fileEditor.setContent(`# 加载文件失败\n\n${error.message}`);
        }
    }

    handleContentChange(content) {
        if (this.currentFile && this.currentFile.toLowerCase().endsWith('.md')) {
            this.mindmapPanel.setContent(content);
        }
    }

    handleMindmapChange(content) {
        this.fileEditor.setContent(content);
    }

    async saveFile(content) {
        if (!this.currentFile) {
            throw new Error('请先选择一个文件');
        }

        const result = await API.updateWorkspaceFile(this.currentFile, content);
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
            case 'context_compressed':
                this.chatPanel.addCompressionNotice(data.content);
                break;
            case 'chunk':
                if (data.message) {
                    this.handleStructuredChunk(data.message);
                } else {
                    this.chatPanel.appendAIMessage(data.content);
                }
                break;
            case 'done':
                if (data.message) {
                    this.handleStructuredDone(data.message);
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
        }
    }

    handleStructuredChunk(msg) {
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

    handleStructuredDone(msg) {
        this.chatPanel.finishAIMessage();
    }

    refresh() {
        if (this.directoryTree) {
            this.directoryTree.refresh();
        }
    }
}

window.WorkspaceManager = WorkspaceManager;
