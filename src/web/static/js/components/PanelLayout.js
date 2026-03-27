class PanelLayout {
    constructor(options) {
        this.container = options.container;
        this.panels = [];
        this.minPanelWidth = options.minPanelWidth || 200;
        this.resizeHandleWidth = 6;
        
        this.layoutEl = null;
        this.activeResize = null;
        
        this.render();
    }
    
    render() {
        this.layoutEl = document.createElement('div');
        this.layoutEl.className = 'panel-layout';
        
        this.container.appendChild(this.layoutEl);
    }
    
    addPanel(panelConfig) {
        const panel = new Panel({
            id: panelConfig.id,
            title: panelConfig.title,
            width: panelConfig.width || `${100 / (this.panels.length + 1)}%`,
            minWidth: panelConfig.minWidth || this.minPanelWidth,
            collapsible: panelConfig.collapsible !== false,
            onCollapse: (id) => this.handlePanelCollapse(id),
            onExpand: (id) => this.handlePanelExpand(id),
            canCollapse: () => this.getVisiblePanelCount() > 1
        });
        
        if (panelConfig.content) {
            panel.setContent(panelConfig.content);
        }
        
        this.panels.push(panel);
        this.layoutEl.appendChild(panel.container);
        
        this.rebuildLayout();
        
        return panel;
    }
    
    rebuildLayout() {
        const visiblePanels = this.getVisiblePanels();
        
        this.layoutEl.innerHTML = '';
        
        visiblePanels.forEach((panel, index) => {
            if (index > 0) {
                const handle = this.createResizeHandle(index - 1);
                this.layoutEl.appendChild(handle);
            }
            this.layoutEl.appendChild(panel.container);
        });
        
        this.updateExpandButtons();
    }
    
    createResizeHandle(visibleIndex) {
        const handle = document.createElement('div');
        handle.className = 'panel-resize-handle';
        handle.dataset.visibleIndex = visibleIndex;
        
        handle.addEventListener('mousedown', (e) => this.startResize(e, visibleIndex));
        
        return handle;
    }
    
    startResize(e, visibleIndex) {
        e.preventDefault();
        
        const visiblePanels = this.getVisiblePanels();
        const leftPanel = visiblePanels[visibleIndex];
        const rightPanel = visiblePanels[visibleIndex + 1];
        
        if (!leftPanel || !rightPanel) return;
        
        this.activeResize = {
            leftPanel,
            rightPanel,
            startX: e.clientX,
            startLeftWidth: leftPanel.getWidth(),
            startRightWidth: rightPanel.getWidth()
        };
        
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        
        document.addEventListener('mousemove', this.handleResize);
        document.addEventListener('mouseup', this.stopResize);
    }
    
    handleResize = (e) => {
        if (!this.activeResize) return;
        
        const { leftPanel, rightPanel, startX, startLeftWidth, startRightWidth } = this.activeResize;
        const deltaX = e.clientX - startX;
        
        const totalWidth = startLeftWidth + startRightWidth;
        let newLeftWidth = startLeftWidth + deltaX;
        let newRightWidth = startRightWidth - deltaX;
        
        if (newLeftWidth < leftPanel.minWidth) {
            newLeftWidth = leftPanel.minWidth;
            newRightWidth = totalWidth - newLeftWidth;
        }
        if (newRightWidth < rightPanel.minWidth) {
            newRightWidth = rightPanel.minWidth;
            newLeftWidth = totalWidth - newRightWidth;
        }
        
        const layoutWidth = this.layoutEl.offsetWidth;
        const visibleCount = this.getVisiblePanelCount();
        const handlesWidth = (visibleCount - 1) * this.resizeHandleWidth;
        const availableWidth = layoutWidth - handlesWidth;
        
        leftPanel.setWidth(`${(newLeftWidth / availableWidth) * 100}%`);
        rightPanel.setWidth(`${(newRightWidth / availableWidth) * 100}%`);
    }
    
    stopResize = () => {
        this.activeResize = null;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        
        document.removeEventListener('mousemove', this.handleResize);
        document.removeEventListener('mouseup', this.stopResize);
        
        this.dispatchEvent('resize');
    }
    
    handlePanelCollapse(panelId) {
        this.redistributeWidths();
        this.rebuildLayout();
        this.dispatchEvent('collapse', panelId);
    }
    
    handlePanelExpand(panelId) {
        this.redistributeWidths();
        this.rebuildLayout();
        this.dispatchEvent('expand', panelId);
    }
    
    redistributeWidths() {
        const visiblePanels = this.getVisiblePanels();
        if (visiblePanels.length === 0) return;
        
        const equalWidth = 100 / visiblePanels.length;
        visiblePanels.forEach(panel => {
            panel.setWidth(`${equalWidth}%`);
        });
    }
    
    updateExpandButtons() {
        this.clearExpandButtons();
        
        const visiblePanels = this.panels.filter(p => !p.isCollapsed);
        
        if (visiblePanels.length === this.panels.length) {
            return;
        }
        
        this.panels.forEach((panel, index) => {
            if (panel.isCollapsed) {
                const prevVisible = this.findPrevVisiblePanel(index);
                if (prevVisible) {
                    this.createExpandButton(prevVisible, panel);
                } else {
                    const nextVisible = this.findNextVisiblePanel(index);
                    if (nextVisible) {
                        this.createExpandButtonBefore(nextVisible, panel);
                    }
                }
            }
        });
    }
    
    findPrevVisiblePanel(index) {
        for (let i = index - 1; i >= 0; i--) {
            if (!this.panels[i].isCollapsed) {
                return this.panels[i];
            }
        }
        return null;
    }
    
    findNextVisiblePanel(index) {
        for (let i = index + 1; i < this.panels.length; i++) {
            if (!this.panels[i].isCollapsed) {
                return this.panels[i];
            }
        }
        return null;
    }
    
    createExpandButton(afterPanel, collapsedPanel) {
        const btn = document.createElement('button');
        btn.className = 'panel-expand-btn';
        btn.innerHTML = '<span class="toggle-icon">»</span>';
        btn.title = `展开${collapsedPanel.title}`;
        btn.addEventListener('click', () => collapsedPanel.expand());
        
        afterPanel.container.appendChild(btn);
        afterPanel._expandBtn = btn;
    }
    
    createExpandButtonBefore(beforePanel, collapsedPanel) {
        const btn = document.createElement('button');
        btn.className = 'panel-expand-btn panel-expand-btn-left';
        btn.innerHTML = '<span class="toggle-icon">«</span>';
        btn.title = `展开${collapsedPanel.title}`;
        btn.addEventListener('click', () => collapsedPanel.expand());
        
        beforePanel.container.appendChild(btn);
        beforePanel._expandBtn = btn;
    }
    
    clearExpandButtons() {
        this.panels.forEach(panel => {
            if (panel._expandBtn) {
                panel._expandBtn.remove();
                panel._expandBtn = null;
            }
        });
    }
    
    getVisiblePanelCount() {
        return this.panels.filter(p => !p.isCollapsed).length;
    }
    
    getVisiblePanels() {
        return this.panels.filter(p => !p.isCollapsed);
    }
    
    collapsePanel(panelId) {
        const panel = this.panels.find(p => p.id === panelId);
        if (panel && this.getVisiblePanelCount() > 1) {
            panel.collapse();
        }
    }
    
    expandPanel(panelId) {
        const panel = this.panels.find(p => p.id === panelId);
        if (panel) {
            panel.expand();
        }
    }
    
    togglePanel(panelId) {
        const panel = this.panels.find(p => p.id === panelId);
        if (panel) {
            if (panel.isCollapsed) {
                panel.expand();
            } else if (this.getVisiblePanelCount() > 1) {
                panel.collapse();
            }
        }
    }
    
    getPanel(panelId) {
        return this.panels.find(p => p.id === panelId);
    }
    
    dispatchEvent(name, detail) {
        const event = new CustomEvent(`panellayout:${name}`, { detail });
        this.container.dispatchEvent(event);
    }
    
    destroy() {
        this.panels.forEach(panel => panel.destroy());
        this.panels = [];
        
        if (this.layoutEl && this.layoutEl.parentNode) {
            this.layoutEl.parentNode.removeChild(this.layoutEl);
        }
    }
}

window.PanelLayout = PanelLayout;
