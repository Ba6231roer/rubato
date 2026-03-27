class MindmapPanel {
    constructor(options) {
        this.container = options.container;
        this.onContentChange = options.onContentChange || null;
        
        this.markmap = null;
        this.mindmapEditor = null;
        this.svg = null;
        this.currentContent = '';
        this.syncSource = null;
        
        this.toolbarId = `mindmap-toolbar-${Date.now()}`;
        
        this.render();
    }
    
    render() {
        const wrapper = document.createElement('div');
        wrapper.className = 'mindmap-panel-wrapper';
        
        this.mindmapEl = document.createElement('div');
        this.mindmapEl.className = 'mindmap-content';
        
        wrapper.appendChild(this.mindmapEl);
        this.container.appendChild(wrapper);
        
        this.addToolbar();
    }
    
    addToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'mindmap-toolbar';
        
        const expandBtn = document.createElement('button');
        expandBtn.className = 'mindmap-toolbar-btn';
        expandBtn.textContent = '展开全部';
        expandBtn.title = '全部展开';
        expandBtn.addEventListener('click', () => {
            if (this.mindmapEditor) {
                this.mindmapEditor.expandAll();
            }
        });
        
        const collapseBtn = document.createElement('button');
        collapseBtn.className = 'mindmap-toolbar-btn';
        collapseBtn.textContent = '折叠全部';
        collapseBtn.title = '全部折叠';
        collapseBtn.addEventListener('click', () => {
            if (this.mindmapEditor) {
                this.mindmapEditor.collapseAll();
            }
        });
        
        toolbar.appendChild(expandBtn);
        toolbar.appendChild(collapseBtn);
        
        this.container.style.position = 'relative';
        this.container.insertBefore(toolbar, this.container.firstChild);
    }
    
    setContent(content) {
        if (this.syncSource === 'mindmap') {
            return;
        }
        
        this.currentContent = content || '';
        
        if (!this.currentContent.trim()) {
            this.clearMindmap();
            this.mindmapEl.innerHTML = '<div class="mindmap-placeholder">输入Markdown内容查看思维导图</div>';
            return;
        }
        
        try {
            const { Transformer, Markmap } = window.markmap;
            
            if (Transformer && Markmap) {
                const transformer = new Transformer();
                const { root } = transformer.transform(this.currentContent);
                
                if (this.markmap) {
                    this.markmap.setData(root);
                    this.markmap.fit();
                } else {
                    this.clearMindmap();
                    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                    this.svg.setAttribute('class', 'markmap');
                    this.svg.style.width = '100%';
                    this.svg.style.height = '100%';
                    this.mindmapEl.appendChild(this.svg);
                    this.markmap = Markmap.create(this.svg, null, root);
                    
                    this.initMindmapEditor();
                }
                
                if (this.mindmapEditor && this.mindmapEditor.treeData) {
                    const freshTree = this.mindmapEditor.converter.parse(this.currentContent);
                    this.mindmapEditor.treeData = freshTree;
                }
            } else {
                console.error('Markmap libraries not loaded');
                this.clearMindmap();
                this.mindmapEl.innerHTML = '<div class="mindmap-placeholder">思维导图库加载失败，请刷新页面</div>';
            }
        } catch (error) {
            console.error('Markmap render error:', error);
            this.clearMindmap();
            this.mindmapEl.innerHTML = `<div class="mindmap-placeholder">渲染失败: ${error.message}</div>`;
        }
    }
    
    initMindmapEditor() {
        if (!window.MindmapEditor) {
            console.warn('MindmapEditor not loaded');
            return;
        }
        
        this.mindmapEditor = new MindmapEditor({
            onTreeChange: (markdown) => {
                this.syncSource = 'mindmap';
                this.currentContent = markdown;
                if (this.onContentChange) {
                    this.onContentChange(markdown);
                }
                this.syncSource = null;
            },
            onSelectionChange: (node) => {
            }
        });
        
        this.mindmapEditor.attach(this.svg, this.markmap);
    }
    
    clearMindmap() {
        if (this.mindmapEditor) {
            try {
                this.mindmapEditor.destroy();
            } catch (e) {
            }
            this.mindmapEditor = null;
        }
        if (this.markmap) {
            try {
                this.markmap.destroy();
            } catch (e) {
            }
            this.markmap = null;
        }
        this.mindmapEl.innerHTML = '';
    }
    
    getContent() {
        return this.currentContent;
    }
    
    fit() {
        if (this.markmap) {
            this.markmap.fit();
        }
    }
    
    destroy() {
        this.clearMindmap();
    }
}

window.MindmapPanel = MindmapPanel;
