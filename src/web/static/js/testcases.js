class TestCaseManager {
    constructor() {
        this.currentFile = null;
        this.tree = [];
        this.markmap = null;
        this.mindmapEditor = null;
        this.updateTimeout = null;
        this.syncSource = null;
        
        this.elements = {
            tree: document.getElementById('testcasesTree'),
            editor: document.getElementById('testcasesEditor'),
            mindmap: document.getElementById('testcasesMindmap'),
            saveBtn: document.getElementById('saveTestcaseBtn'),
            sidebar: document.getElementById('testcasesSidebar'),
            sidebarToggle: document.getElementById('testcasesSidebarToggle'),
            sidebarExpand: document.getElementById('testcasesSidebarExpand'),
            editorPanel: document.getElementById('testcasesEditorPanel'),
            mindmapPanel: document.getElementById('testcasesMindmapPanel'),
            resizeHandle: document.getElementById('testcasesResizeHandle')
        };
        
        this.init();
    }
    
    init() {
        this.loadTree();
        this.initEditor();
        this.initSaveButton();
        this.initSidebarToggle();
        this.initResizeHandle();
        this.initMindmapToolbar();
    }
    
    async loadTree() {
        try {
            this.tree = await API.getTestCaseTree();
            this.renderTree();
        } catch (error) {
            console.error('Failed to load test case tree:', error);
            this.elements.tree.innerHTML = '<div class="tree-error">加载目录失败</div>';
        }
    }
    
    renderTree() {
        if (!this.tree || this.tree.length === 0) {
            this.elements.tree.innerHTML = '<div class="tree-empty">暂无测试案例</div>';
            return;
        }
        this.elements.tree.innerHTML = this.renderTreeNodes(this.tree);
    }
    
    renderTreeNodes(nodes) {
        let html = '';
        for (const node of nodes) {
            if (node.type === 'folder') {
                html += `
                    <div class="tree-node" data-path="${node.path}" data-type="folder">
                        <div class="tree-item folder">
                            <span class="tree-icon">📁</span>
                            <span class="tree-text">${this.escapeHtml(node.name)}</span>
                        </div>
                        <div class="tree-children" style="display: none;">
                            ${node.children ? this.renderTreeNodes(node.children) : ''}
                        </div>
                    </div>
                `;
            } else {
                html += `
                    <div class="tree-item file" data-path="${node.path}" data-type="file">
                        <span class="tree-icon">📄</span>
                        <span class="tree-text">${this.escapeHtml(node.name)}</span>
                    </div>
                `;
            }
        }
        return html;
    }
    
    initEditor() {
        this.elements.tree.addEventListener('click', (e) => {
            const folderItem = e.target.closest('.tree-item.folder');
            const fileItem = e.target.closest('.tree-item.file');
            
            if (folderItem) {
                this.toggleFolder(folderItem.parentElement);
            } else if (fileItem) {
                this.selectFile(fileItem);
            }
        });
        
        this.elements.editor.addEventListener('input', () => {
            if (this.updateTimeout) {
                clearTimeout(this.updateTimeout);
            }
            this.updateTimeout = setTimeout(() => {
                this.updateMindmap();
            }, 300);
        });
    }
    
    toggleFolder(folderNode) {
        const children = folderNode.querySelector('.tree-children');
        const icon = folderNode.querySelector('.tree-icon');
        if (children) {
            const isHidden = children.style.display === 'none';
            children.style.display = isHidden ? 'block' : 'none';
            icon.textContent = isHidden ? '📂' : '📁';
        }
    }
    
    async selectFile(fileItem) {
        document.querySelectorAll('#testcasesTree .tree-item.file').forEach(item => {
            item.classList.remove('active');
        });
        fileItem.classList.add('active');
        
        const path = fileItem.dataset.path;
        this.currentFile = path;
        
        try {
            const data = await API.getTestCaseFile(path);
            this.elements.editor.value = data.content;
            this.updateMindmap();
        } catch (error) {
            console.error('Failed to load file:', error);
            this.elements.editor.value = `# 加载文件失败\n\n${error.message}`;
        }
    }
    
    updateMindmap() {
        if (this.syncSource === 'mindmap') {
            return;
        }
        
        const content = this.elements.editor.value;
        if (!content.trim()) {
            this.clearMindmap();
            this.elements.mindmap.innerHTML = '<div class="mindmap-placeholder">输入Markdown内容查看思维导图</div>';
            return;
        }
        
        try {
            const { Transformer, Markmap } = window.markmap;
            
            if (Transformer && Markmap) {
                const transformer = new Transformer();
                const { root } = transformer.transform(content);
                
                if (this.markmap) {
                    this.markmap.setData(root);
                    this.markmap.fit();
                } else {
                    this.clearMindmap();
                    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                    svg.setAttribute('class', 'markmap');
                    svg.style.width = '100%';
                    svg.style.height = '100%';
                    this.elements.mindmap.appendChild(svg);
                    this.markmap = Markmap.create(svg, null, root);
                    
                    this.initMindmapEditor(svg);
                }
                
                if (this.mindmapEditor && this.mindmapEditor.treeData) {
                    const freshTree = this.mindmapEditor.converter.parse(content);
                    this.mindmapEditor.treeData = freshTree;
                }
            } else {
                console.error('Markmap libraries not loaded:', {
                    markmap: !!window.markmap,
                    keys: window.markmap ? Object.keys(window.markmap) : []
                });
                this.clearMindmap();
                this.elements.mindmap.innerHTML = '<div class="mindmap-placeholder">思维导图库加载失败，请刷新页面</div>';
            }
        } catch (error) {
            console.error('Markmap render error:', error);
            this.clearMindmap();
            this.elements.mindmap.innerHTML = `<div class="mindmap-placeholder">渲染失败: ${error.message}</div>`;
        }
    }
    
    initMindmapEditor(svg) {
        if (!window.MindmapEditor) {
            console.warn('MindmapEditor not loaded');
            return;
        }
        
        this.mindmapEditor = new MindmapEditor({
            onTreeChange: (markdown) => {
                console.log('[TestCaseManager] onTreeChange callback received');
                this.syncSource = 'mindmap';
                this.elements.editor.value = markdown;
                this.syncSource = null;
            },
            onSelectionChange: (node) => {
            }
        });
        
        this.mindmapEditor.attach(svg, this.markmap);
        console.log('[TestCaseManager] MindmapEditor attached, treeData:', this.mindmapEditor.treeData?.content);
    }
    
    clearMindmap() {
        if (this.mindmapEditor) {
            this.mindmapEditor.destroy();
            this.mindmapEditor = null;
        }
        if (this.markmap) {
            try {
                this.markmap.destroy();
            } catch (e) {
            }
            this.markmap = null;
        }
        this.elements.mindmap.innerHTML = '';
    }
    
    initMindmapToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'mindmap-toolbar';
        toolbar.innerHTML = `
            <button class="mindmap-toolbar-btn" id="expandAllBtn" title="全部展开">展开全部</button>
            <button class="mindmap-toolbar-btn" id="collapseAllBtn" title="全部折叠">折叠全部</button>
        `;
        
        this.elements.mindmapPanel.style.position = 'relative';
        this.elements.mindmapPanel.insertBefore(toolbar, this.elements.mindmapPanel.firstChild);
        
        document.getElementById('expandAllBtn').addEventListener('click', () => {
            if (this.mindmapEditor) {
                this.mindmapEditor.expandAll();
            }
        });
        
        document.getElementById('collapseAllBtn').addEventListener('click', () => {
            if (this.mindmapEditor) {
                this.mindmapEditor.collapseAll();
            }
        });
    }
    
    initSaveButton() {
        this.elements.saveBtn.addEventListener('click', () => this.saveFile());
    }
    
    async saveFile() {
        if (!this.currentFile) {
            alert('请先选择一个文件');
            return;
        }
        
        const content = this.elements.editor.value;
        this.elements.saveBtn.disabled = true;
        this.elements.saveBtn.textContent = '保存中...';
        
        try {
            const result = await API.updateTestCaseFile(this.currentFile, content);
            if (result.success) {
                this.showMessage('保存成功', 'success');
            } else {
                this.showMessage(result.message, 'error');
            }
        } catch (error) {
            this.showMessage(`保存失败: ${error.message}`, 'error');
        } finally {
            this.elements.saveBtn.disabled = false;
            this.elements.saveBtn.textContent = '保存';
        }
    }
    
    showMessage(message, type) {
        const header = this.elements.saveBtn.parentElement;
        let msgEl = header.querySelector('.save-message');
        if (!msgEl) {
            msgEl = document.createElement('span');
            msgEl.className = 'save-message';
            header.appendChild(msgEl);
        }
        msgEl.textContent = message;
        msgEl.className = `save-message ${type}`;
        
        setTimeout(() => {
            msgEl.textContent = '';
        }, 3000);
    }
    
    initSidebarToggle() {
        if (this.elements.sidebarToggle) {
            this.elements.sidebarToggle.addEventListener('click', () => {
                this.elements.sidebar.classList.add('collapsed');
            });
        }
        
        if (this.elements.sidebarExpand) {
            this.elements.sidebarExpand.addEventListener('click', () => {
                this.elements.sidebar.classList.remove('collapsed');
            });
        }
    }
    
    initResizeHandle() {
        if (!this.elements.resizeHandle) return;
        
        let isResizing = false;
        let startX = 0;
        let startEditorWidth = 0;
        
        this.elements.resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startEditorWidth = this.elements.editorPanel.offsetWidth;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;
            
            const deltaX = e.clientX - startX;
            const containerWidth = this.elements.editorPanel.parentElement.offsetWidth - 30;
            const newEditorWidth = startEditorWidth + deltaX;
            const minWidth = 200;
            const maxWidth = containerWidth - 200;
            
            if (newEditorWidth >= minWidth && newEditorWidth <= maxWidth) {
                const editorPercent = (newEditorWidth / containerWidth) * 100;
                this.elements.editorPanel.style.width = `${editorPercent}%`;
                this.elements.mindmapPanel.style.width = `${100 - editorPercent}%`;
            }
        });
        
        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                if (this.markmap) {
                    this.markmap.fit();
                }
            }
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.testcaseManager = new TestCaseManager();
});
