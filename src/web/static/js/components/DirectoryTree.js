class DirectoryTree {
    constructor(options) {
        this.container = options.container;
        this.title = options.title || '目录';
        this.loadTreeFn = options.loadTreeFn;
        this.onFileSelect = options.onFileSelect;
        this.onFolderToggle = options.onFolderToggle || null;
        
        this.tree = [];
        this.currentFile = null;
        this.treeEl = null;
        
        this.render();
    }
    
    render() {
        const wrapper = document.createElement('div');
        wrapper.className = 'directory-tree-wrapper';
        
        this.treeEl = document.createElement('div');
        this.treeEl.className = 'directory-tree';
        
        wrapper.appendChild(this.treeEl);
        this.container.appendChild(wrapper);
        
        this.loadTree();
    }
    
    async loadTree() {
        if (!this.loadTreeFn) return;
        
        try {
            this.tree = await this.loadTreeFn();
            this.renderTree();
        } catch (error) {
            console.error('Failed to load tree:', error);
            this.treeEl.innerHTML = '<div class="tree-error">加载目录失败</div>';
        }
    }
    
    renderTree() {
        if (!this.tree || this.tree.length === 0) {
            this.treeEl.innerHTML = '<div class="tree-empty">暂无内容</div>';
            return;
        }
        this.treeEl.innerHTML = this.renderTreeNodes(this.tree);
        this.bindEvents();
    }
    
    renderTreeNodes(nodes) {
        let html = '';
        for (const node of nodes) {
            if (node.type === 'folder') {
                html += `
                    <div class="tree-node" data-path="${this.escapeAttr(node.path)}" data-type="folder">
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
                    <div class="tree-item file" data-path="${this.escapeAttr(node.path)}" data-type="file">
                        <span class="tree-icon">📄</span>
                        <span class="tree-text">${this.escapeHtml(node.name)}</span>
                    </div>
                `;
            }
        }
        return html;
    }
    
    bindEvents() {
        this.treeEl.addEventListener('click', (e) => {
            const folderItem = e.target.closest('.tree-item.folder');
            const fileItem = e.target.closest('.tree-item.file');
            
            if (folderItem) {
                this.toggleFolder(folderItem.parentElement);
            } else if (fileItem) {
                this.selectFile(fileItem);
            }
        });
    }
    
    toggleFolder(folderNode) {
        const children = folderNode.querySelector('.tree-children');
        const icon = folderNode.querySelector('.tree-icon');
        if (children) {
            const isHidden = children.style.display === 'none';
            children.style.display = isHidden ? 'block' : 'none';
            icon.textContent = isHidden ? '📂' : '📁';
            
            if (this.onFolderToggle) {
                this.onFolderToggle(folderNode.dataset.path, isHidden);
            }
        }
    }
    
    selectFile(fileItem) {
        this.treeEl.querySelectorAll('.tree-item.file').forEach(item => {
            item.classList.remove('active');
        });
        fileItem.classList.add('active');
        
        const path = fileItem.dataset.path;
        this.currentFile = path;
        
        if (this.onFileSelect) {
            this.onFileSelect(path);
        }
    }
    
    getCurrentFile() {
        return this.currentFile;
    }
    
    refresh() {
        this.loadTree();
    }
    
    clear() {
        this.tree = [];
        this.currentFile = null;
        this.treeEl.innerHTML = '<div class="tree-empty">暂无内容</div>';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    escapeAttr(text) {
        return text.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
}

window.DirectoryTree = DirectoryTree;
