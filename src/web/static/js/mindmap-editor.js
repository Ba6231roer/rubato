class MindmapEditor {
    constructor(options = {}) {
        this.markmap = null;
        this.svg = null;
        this.converter = null;
        this.treeData = null;
        
        this.selectedNode = null;
        this.selectedNodePath = null;
        this.isEditing = false;
        this.editingNode = null;
        this.isProcessing = false;
        
        this.editorContainer = null;
        this.floatingEditor = null;
        
        this.onTreeChange = options.onTreeChange || null;
        this.onSelectionChange = options.onSelectionChange || null;
        
        this.lastClickTime = 0;
        this.lastClickTarget = null;
        
        this.init();
    }

    init() {
        this.converter = new MarkdownTreeConverter();
        this.createEditorContainer();
    }

    createEditorContainer() {
        this.editorContainer = document.createElement('div');
        this.editorContainer.className = 'mindmap-editor-container';
        this.editorContainer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 100;
        `;
        document.body.appendChild(this.editorContainer);
    }

    attach(svg, markmap) {
        this.svg = svg;
        this.markmap = markmap;
        
        this.treeData = this.markmap.state?.data || null;
        
        this.bindEvents();
    }

    bindEvents() {
        if (!this.svg) return;
        
        this._handleClick = this.handleClick.bind(this);
        this._handleKeyDown = this.handleKeyDown.bind(this);
        this._handleDocumentClick = this.handleDocumentClick.bind(this);
        
        this.svg.addEventListener('click', this._handleClick, true);
        this.svg.addEventListener('keydown', this._handleKeyDown);
        
        this.svg.setAttribute('tabindex', '0');
        this.svg.style.outline = 'none';
        this.svg.style.cursor = 'default';
        
        document.addEventListener('click', this._handleDocumentClick);
        
        document.addEventListener('keydown', (e) => {
            if (this.selectedNode && !this.isEditing) {
                if (document.activeElement === this.svg || 
                    this.svg.contains(document.activeElement)) {
                    this._handleKeyDown(e);
                }
            }
        });
    }

    handleClick(e) {
        const nodeGroup = e.target.closest('g.markmap-node');
        
        if (nodeGroup) {
            e.stopPropagation();
            
            const now = Date.now();
            const isDoubleClick = (now - this.lastClickTime < 300) && 
                                  (this.lastClickTarget === nodeGroup);
            
            console.log('[MindmapEditor] Click detected, isDoubleClick:', isDoubleClick, 'timeDiff:', now - this.lastClickTime);
            
            this.lastClickTime = now;
            this.lastClickTarget = nodeGroup;
            
            const nodeData = this.getNodeDataFromElement(nodeGroup);
            
            if (isDoubleClick && nodeData) {
                console.log('[MindmapEditor] Double click simulated on node:', nodeData.content?.substring(0, 50));
                this.startEditing(nodeData);
            } else if (nodeData) {
                const indexPath = this.getIndexPath(nodeData);
                this.selectNode(nodeData, indexPath);
                this.svg.focus();
                console.log('[MindmapEditor] Node selected:', nodeData.content?.substring(0, 50), 'IndexPath:', indexPath);
            }
        } else {
            this.deselectNode();
        }
    }
    
    getIndexPath(node) {
        if (!node || !this.treeData) return null;
        
        this.resyncTreeData();
        
        const path = node.state?.path;
        if (!path) return null;
        
        const parts = path.split('.').map(Number);
        if (parts.length < 1) return null;
        
        let current = this.treeData;
        const indexPath = [];
        
        for (let i = 1; i < parts.length; i++) {
            if (!current.children) return null;
            
            let foundIndex = -1;
            for (let j = 0; j < current.children.length; j++) {
                const childId = current.children[j].state?.id;
                if (childId === parts[i]) {
                    foundIndex = j;
                    break;
                }
            }
            
            if (foundIndex === -1) {
                console.warn('[MindmapEditor] Cannot find child with id:', parts[i]);
                return null;
            }
            
            indexPath.push(foundIndex);
            current = current.children[foundIndex];
        }
        
        return indexPath.length > 0 ? [0, ...indexPath] : [0];
    }

    handleKeyDown(e) {
        console.log('[MindmapEditor] Key pressed:', e.key, 'Selected node:', this.selectedNode?.content, 'Is editing:', this.isEditing);
        
        if (this.isEditing) {
            this.handleEditingKeyDown(e);
            return;
        }
        
        if (!this.selectedNode) {
            console.log('[MindmapEditor] No node selected, ignoring key');
            return;
        }
        
        console.log('[MindmapEditor] Processing key:', e.key);
        
        switch (e.key) {
            case 'Tab':
                e.preventDefault();
                e.stopPropagation();
                console.log('[MindmapEditor] Inserting child node');
                this.insertChildNode();
                break;
            case 'Enter':
                e.preventDefault();
                e.stopPropagation();
                console.log('[MindmapEditor] Inserting sibling node');
                this.insertSiblingNode();
                break;
            case 'Delete':
            case 'Backspace':
                e.preventDefault();
                e.stopPropagation();
                console.log('[MindmapEditor] Deleting node');
                this.deleteSelectedNode();
                break;
            case 'Escape':
                e.preventDefault();
                e.stopPropagation();
                console.log('[MindmapEditor] Deselecting node');
                this.deselectNode();
                break;
            case ' ':
                e.preventDefault();
                e.stopPropagation();
                console.log('[MindmapEditor] Toggling fold');
                this.toggleFold();
                break;
            case 'F2':
                e.preventDefault();
                e.stopPropagation();
                console.log('[MindmapEditor] Starting edit');
                this.startEditing(this.selectedNode);
                break;
        }
    }

    handleEditingKeyDown(e) {
        switch (e.key) {
            case 'Enter':
                if (!e.shiftKey) {
                    e.preventDefault();
                    this.finishEditing();
                }
                break;
            case 'Escape':
                e.preventDefault();
                this.cancelEditing();
                break;
        }
    }

    handleDocumentClick(e) {
        if (this.isEditing && this.floatingEditor) {
            if (!this.floatingEditor.contains(e.target)) {
                this.finishEditing();
            }
        }
    }

    getNodeDataFromElement(element) {
        if (!this.markmap || !this.markmap.state || !this.markmap.state.data) return null;
        
        const g = d3.select(element);
        const nodeData = g.datum();
        return nodeData;
    }

    selectNode(node, indexPath = null) {
        this.selectedNode = node;
        this.selectedNodePath = indexPath || node.state?.path || null;
        
        if (this.markmap) {
            this.markmap.setHighlight(node);
        }
        
        if (this.onSelectionChange) {
            this.onSelectionChange(node);
        }
    }

    deselectNode() {
        this.selectedNode = null;
        this.selectedNodePath = null;
        
        if (this.markmap) {
            this.markmap.setHighlight(null);
        }
        
        if (this.onSelectionChange) {
            this.onSelectionChange(null);
        }
    }

    setData(markdown) {
        this.treeData = this.converter.parse(markdown);
        return this.treeData;
    }

    getMarkdown() {
        if (!this.treeData) return '';
        return this.converter.build(this.treeData);
    }

    startEditing(node) {
        console.log('[MindmapEditor] startEditing called, node:', node?.content, 'isEditing:', this.isEditing);
        
        if (this.isEditing) {
            console.log('[MindmapEditor] Already editing, skipping');
            return;
        }
        
        this.isEditing = true;
        this.editingNode = node;
        
        const rect = node.state?.rect;
        if (!rect) {
            console.warn('[MindmapEditor] No rect found for node, state:', node.state);
            this.isEditing = false;
            this.editingNode = null;
            return;
        }
        
        console.log('[MindmapEditor] Starting edit for node, rect:', rect);
        
        const content = node.content || '';
        const plainContent = content.replace(/<[^>]*>/g, '');
        
        this.createFloatingEditor(plainContent, rect);
    }

    createFloatingEditor(content, rect) {
        if (this.floatingEditor) {
            this.removeFloatingEditor();
        }
        
        this.floatingEditor = document.createElement('div');
        this.floatingEditor.className = 'mindmap-floating-editor';
        this.floatingEditor.style.cssText = `
            position: absolute;
            pointer-events: auto;
            background: white;
            border: 2px solid #0097e6;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 16px;
            font-family: sans-serif;
            min-width: 100px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 1000;
        `;
        
        const input = document.createElement('input');
        input.type = 'text';
        input.value = content;
        input.style.cssText = `
            border: none;
            outline: none;
            font-size: inherit;
            font-family: inherit;
            width: 100%;
            min-width: 80px;
        `;
        
        input.addEventListener('input', () => {
            input.style.width = Math.max(80, input.value.length * 10) + 'px';
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.finishEditing();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.cancelEditing();
            }
        });
        
        this.floatingEditor.appendChild(input);
        this.editorContainer.appendChild(this.floatingEditor);
        
        const svgRect = this.svg.getBoundingClientRect();
        const transform = d3.zoomTransform(this.svg);
        
        const x = rect.x * transform.k + transform.x + svgRect.left;
        const y = rect.y * transform.k + transform.y + svgRect.top;
        
        this.floatingEditor.style.left = x + 'px';
        this.floatingEditor.style.top = y + 'px';
        
        console.log('[MindmapEditor] Floating editor positioned at:', x, y);
        
        input.focus();
        input.select();
    }

    removeFloatingEditor() {
        if (this.floatingEditor) {
            this.floatingEditor.remove();
            this.floatingEditor = null;
        }
    }

    finishEditing() {
        if (!this.isEditing || !this.editingNode) return;
        
        const input = this.floatingEditor?.querySelector('input');
        const newContent = input?.value?.trim() || this.editingNode.content;
        
        console.log('[MindmapEditor] Finishing edit, new content:', newContent);
        
        this.converter.updateNodeContent(this.editingNode, newContent);
        
        this.isEditing = false;
        this.editingNode = null;
        this.removeFloatingEditor();
        
        this.notifyTreeChange();
    }

    cancelEditing() {
        this.isEditing = false;
        this.editingNode = null;
        this.removeFloatingEditor();
    }

    insertChildNode() {
        if (!this.selectedNode) {
            console.warn('[MindmapEditor] No node selected');
            return;
        }
        
        if (this.isProcessing) {
            console.log('[MindmapEditor] Processing in progress, skipping');
            return;
        }
        
        this.isProcessing = true;
        console.log('[MindmapEditor] Adding child to node:', this.selectedNode.content?.substring(0, 30));
        
        const newNode = this.converter.addChildNode(this.selectedNode, '新节点');
        if (newNode) {
            const parentNode = this.selectedNode;
            this.notifyTreeChange();
            
            const trySelectNewNode = (retries = 0) => {
                setTimeout(() => {
                    this.resyncTreeData();
                    
                    if (parentNode && parentNode.children) {
                        const lastChild = parentNode.children[parentNode.children.length - 1];
                        if (lastChild && lastChild.state?.rect) {
                            console.log('[MindmapEditor] Found new child node with state:', lastChild.content?.substring(0, 30));
                            this.selectNode(lastChild);
                            this.isProcessing = false;
                            this.startEditing(lastChild);
                        } else if (retries < 3) {
                            console.log('[MindmapEditor] New child node not ready, retry', retries + 1);
                            trySelectNewNode(retries + 1);
                        } else {
                            console.warn('[MindmapEditor] Failed to find new child after retries');
                            this.isProcessing = false;
                        }
                    } else {
                        this.isProcessing = false;
                    }
                }, 100 + retries * 50);
            };
            
            trySelectNewNode();
        } else {
            this.isProcessing = false;
        }
    }

    insertSiblingNode() {
        if (!this.selectedNode || !this.treeData) {
            console.warn('[MindmapEditor] No node selected or no tree data');
            return;
        }
        
        if (this.isProcessing) {
            console.log('[MindmapEditor] Processing in progress, skipping');
            return;
        }
        
        if (this.selectedNode === this.treeData) {
            console.warn('[MindmapEditor] Cannot insert sibling to root');
            return;
        }
        
        const parentInfo = this.findParent(this.treeData, this.selectedNode);
        if (!parentInfo) {
            console.warn('[MindmapEditor] Parent not found');
            return;
        }
        
        this.isProcessing = true;
        console.log('[MindmapEditor] Adding sibling to parent:', parentInfo.parent.content?.substring(0, 30));
        
        const newNode = this.converter.addSiblingNode(this.selectedNode, parentInfo.parent, '新节点');
        if (newNode) {
            const siblingIndex = parentInfo.parent.children.indexOf(newNode);
            const parent = parentInfo.parent;
            
            this.notifyTreeChange();
            
            const trySelectNewNode = (retries = 0) => {
                setTimeout(() => {
                    this.resyncTreeData();
                    
                    if (parent.children && parent.children[siblingIndex]) {
                        const sibling = parent.children[siblingIndex];
                        if (sibling && sibling.state?.rect) {
                            console.log('[MindmapEditor] Found new sibling node with state:', sibling.content?.substring(0, 30));
                            this.selectNode(sibling);
                            this.isProcessing = false;
                            this.startEditing(sibling);
                        } else if (retries < 3) {
                            console.log('[MindmapEditor] New sibling node not ready, retry', retries + 1);
                            trySelectNewNode(retries + 1);
                        } else {
                            console.warn('[MindmapEditor] Failed to find new sibling after retries');
                            this.isProcessing = false;
                        }
                    } else {
                        this.isProcessing = false;
                    }
                }, 100 + retries * 50);
            };
            
            trySelectNewNode();
        } else {
            this.isProcessing = false;
        }
    }

    deleteSelectedNode() {
        if (!this.selectedNode || !this.treeData) {
            console.warn('[MindmapEditor] No node selected or no tree data');
            return;
        }
        
        if (this.selectedNode === this.treeData) {
            console.warn('[MindmapEditor] Cannot delete root node');
            return;
        }
        
        if (this.isProcessing) {
            console.log('[MindmapEditor] Processing in progress, skipping');
            return;
        }
        
        const indexPath = this.selectedNodePath;
        if (!indexPath || !Array.isArray(indexPath)) {
            console.warn('[MindmapEditor] No indexPath found for selected node');
            return;
        }
        
        if (indexPath.length < 2) {
            console.warn('[MindmapEditor] Cannot delete root node');
            return;
        }
        
        this.isProcessing = true;
        console.log('[MindmapEditor] Deleting node:', this.selectedNode.content?.substring(0, 30), 'IndexPath:', indexPath);
        
        const result = this.deleteNodeByIndexPath(this.treeData, indexPath);
        if (result) {
            console.log('[MindmapEditor] Node deleted successfully');
            
            const deletedNode = this.selectedNode;
            this.selectedNode = null;
            this.selectedNodePath = null;
            
            const markdown = this.getMarkdown();
            
            if (this.onTreeChange) {
                this.onTreeChange(markdown);
            }
            
            setTimeout(() => {
                this.isProcessing = false;
            }, 100);
        } else {
            console.warn('[MindmapEditor] Failed to delete node');
            this.isProcessing = false;
        }
    }
    
    deleteNodeByIndexPath(tree, indexPath) {
        if (!tree || !indexPath || indexPath.length < 2) {
            console.log('[MindmapEditor] deleteNodeByIndexPath: invalid params');
            return false;
        }
        
        let current = tree;
        
        for (let i = 1; i < indexPath.length - 1; i++) {
            const idx = indexPath[i];
            if (!current.children || idx < 0 || idx >= current.children.length) {
                console.log('[MindmapEditor] deleteNodeByIndexPath: invalid index', idx, 'at level', i);
                return false;
            }
            current = current.children[idx];
        }
        
        const lastIndex = indexPath[indexPath.length - 1];
        console.log('[MindmapEditor] deleteNodeByIndexPath: lastIndex:', lastIndex, 'children count:', current.children?.length);
        
        if (!current.children || lastIndex < 0 || lastIndex >= current.children.length) {
            console.log('[MindmapEditor] deleteNodeByIndexPath: cannot delete - invalid index');
            return false;
        }
        
        current.children.splice(lastIndex, 1);
        
        return true;
    }

    findParent(tree, target, parent = null) {
        if (tree === target) return { parent };
        
        if (tree.children) {
            for (const child of tree.children) {
                const result = this.findParent(child, target, tree);
                if (result) return result;
            }
        }
        
        return null;
    }

    toggleFold() {
        if (!this.selectedNode || !this.markmap) {
            console.warn('[MindmapEditor] No node selected or no markmap');
            return;
        }
        
        console.log('[MindmapEditor] Toggling fold for node:', this.selectedNode.content);
        this.markmap.toggleNode(this.selectedNode);
    }

    toggleFoldRecursive() {
        if (!this.selectedNode || !this.markmap) return;
        
        this.markmap.toggleNode(this.selectedNode, true);
    }

    expandAll() {
        if (!this.treeData) return;
        
        this.walkTree(this.treeData, (node) => {
            if (node.payload) {
                node.payload.fold = 0;
            } else {
                node.payload = { fold: 0 };
            }
        });
        
        this.notifyTreeChange();
    }

    collapseAll() {
        if (!this.treeData) return;
        
        this.walkTree(this.treeData, (node, depth) => {
            if (depth > 0) {
                if (node.payload) {
                    node.payload.fold = 1;
                } else {
                    node.payload = { fold: 1 };
                }
            }
        });
        
        this.notifyTreeChange();
    }

    walkTree(node, callback, depth = 0) {
        callback(node, depth);
        if (node.children) {
            for (const child of node.children) {
                this.walkTree(child, callback, depth + 1);
            }
        }
    }

    resyncTreeData() {
        if (this.markmap && this.markmap.state && this.markmap.state.data) {
            this.treeData = this.markmap.state.data;
            console.log('[MindmapEditor] Tree data resynced from markmap');
        }
    }

    notifyTreeChange() {
        console.log('[MindmapEditor] notifyTreeChange called, treeData:', this.treeData?.content);
        
        if (this.markmap && this.treeData) {
            console.log('[MindmapEditor] Setting markmap data');
            this.markmap.setData(this.treeData);
        }
        
        if (this.onTreeChange) {
            const markdown = this.getMarkdown();
            console.log('[MindmapEditor] Calling onTreeChange callback, markdown length:', markdown.length);
            this.onTreeChange(markdown);
        }
    }

    refresh() {
        if (this.markmap && this.treeData) {
            this.markmap.setData(this.treeData);
        }
    }

    destroy() {
        this.removeFloatingEditor();
        if (this.editorContainer) {
            this.editorContainer.remove();
        }
        document.removeEventListener('click', this._handleDocumentClick);
    }
}

window.MindmapEditor = MindmapEditor;
