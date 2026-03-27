class Panel {
    constructor(options) {
        this.id = options.id;
        this.title = options.title || '';
        this.width = options.width || '25%';
        this.minWidth = options.minWidth || 200;
        this.collapsible = options.collapsible !== false;
        this.onCollapse = options.onCollapse || null;
        this.onExpand = options.onExpand || null;
        this.canCollapse = options.canCollapse || null;
        
        this.isCollapsed = false;
        this.container = null;
        this.headerEl = null;
        this.contentEl = null;
        this.collapseBtn = null;
        
        this.render();
    }
    
    render() {
        this.container = document.createElement('div');
        this.container.className = 'panel';
        this.container.id = this.id;
        this.container.style.width = this.width;
        this.container.style.minWidth = `${this.minWidth}px`;
        
        this.headerEl = document.createElement('div');
        this.headerEl.className = 'panel-header';
        
        const titleEl = document.createElement('h3');
        titleEl.className = 'panel-title';
        titleEl.textContent = this.title;
        
        this.headerEl.appendChild(titleEl);
        
        if (this.collapsible) {
            this.collapseBtn = document.createElement('button');
            this.collapseBtn.className = 'panel-collapse-btn';
            this.collapseBtn.innerHTML = '<span class="toggle-icon">«</span>';
            this.collapseBtn.title = '折叠面板';
            this.collapseBtn.addEventListener('click', () => this.collapse());
            this.headerEl.appendChild(this.collapseBtn);
        }
        
        this.contentEl = document.createElement('div');
        this.contentEl.className = 'panel-content';
        
        this.container.appendChild(this.headerEl);
        this.container.appendChild(this.contentEl);
    }
    
    setContent(element) {
        this.contentEl.innerHTML = '';
        if (typeof element === 'string') {
            this.contentEl.innerHTML = element;
        } else if (element instanceof HTMLElement) {
            this.contentEl.appendChild(element);
        }
    }
    
    appendContent(element) {
        if (typeof element === 'string') {
            this.contentEl.innerHTML += element;
        } else if (element instanceof HTMLElement) {
            this.contentEl.appendChild(element);
        }
    }
    
    addHeaderAction(button) {
        if (button instanceof HTMLElement) {
            button.className = button.className || 'panel-action-btn';
            this.headerEl.insertBefore(button, this.collapseBtn);
        }
    }
    
    collapse() {
        if (this.isCollapsed) return;
        
        if (this.canCollapse && !this.canCollapse()) {
            return;
        }
        
        this.isCollapsed = true;
        this.container.classList.add('collapsed');
        this.container.style.width = '0';
        this.container.style.minWidth = '0';
        
        if (this.onCollapse) {
            this.onCollapse(this.id);
        }
    }
    
    expand() {
        if (!this.isCollapsed) return;
        
        this.isCollapsed = false;
        this.container.classList.remove('collapsed');
        this.container.style.width = this.width;
        this.container.style.minWidth = `${this.minWidth}px`;
        
        if (this.onExpand) {
            this.onExpand(this.id);
        }
    }
    
    setWidth(width) {
        if (this.isCollapsed) return;
        this.width = width;
        this.container.style.width = width;
    }
    
    getWidth() {
        return this.container.offsetWidth;
    }
    
    destroy() {
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
    }
}

window.Panel = Panel;
