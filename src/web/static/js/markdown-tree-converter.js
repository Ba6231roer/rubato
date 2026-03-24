class MarkdownTreeConverter {
    constructor() {
        this.transformer = null;
        this.initTransformer();
    }

    initTransformer() {
        if (window.markmap && window.markmap.Transformer) {
            this.transformer = new window.markmap.Transformer();
        }
    }

    parse(markdown) {
        if (!this.transformer) {
            this.initTransformer();
        }
        if (!this.transformer) {
            throw new Error('markmap-lib Transformer not available');
        }
        const result = this.transformer.transform(markdown);
        return result.root;
    }

    build(tree) {
        if (!tree) return '';
        let markdown = '';
        
        if (tree.content) {
            markdown += `# ${this.escapeContent(tree.content)}\n`;
        }
        
        if (tree.children && tree.children.length > 0) {
            for (const child of tree.children) {
                markdown += this.buildNode(child, 2);
            }
        }
        
        return markdown;
    }

    buildNode(node, depth) {
        let markdown = '';
        const prefix = '#'.repeat(depth);
        
        markdown += `\n${prefix} ${this.escapeContent(node.content)}\n`;
        
        if (node.children && node.children.length > 0) {
            for (const child of node.children) {
                markdown += this.buildListItem(child, 0);
            }
        }
        
        return markdown;
    }

    buildListItem(node, indent) {
        let markdown = '';
        const spaces = '  '.repeat(indent);
        
        markdown += `${spaces}- ${this.escapeContent(node.content)}\n`;
        
        if (node.children && node.children.length > 0) {
            for (const child of node.children) {
                markdown += this.buildListItem(child, indent + 1);
            }
        }
        
        return markdown;
    }

    escapeContent(content) {
        if (!content) return '';
        return content
            .replace(/\\/g, '\\\\')
            .replace(/\n/g, ' ');
    }

    cloneTree(tree) {
        if (!tree) return null;
        return JSON.parse(JSON.stringify(tree));
    }

    findNodeByPath(tree, path) {
        if (!path) return null;
        const parts = path.split('.').map(Number);
        let current = tree;
        
        for (let i = 0; i < parts.length; i++) {
            if (i === 0) {
                if (parts[i] !== current.state?.id) return null;
            } else {
                if (!current.children) return null;
                const childIndex = parts[i] - 1;
                if (childIndex < 0 || childIndex >= current.children.length) return null;
                current = current.children[childIndex];
            }
        }
        
        return current;
    }

    findParentNode(tree, targetNode) {
        if (!tree || !targetNode) return null;
        
        const findParent = (node, parent, target) => {
            if (node === target) return parent;
            if (node.children) {
                for (const child of node.children) {
                    const result = findParent(child, node, target);
                    if (result !== null) return { parent: node, index: node.children.indexOf(child) };
                }
            }
            return null;
        };
        
        const result = findParent(tree, null, targetNode);
        return result;
    }

    addChildNode(parentNode, content = '新节点') {
        if (!parentNode) return null;
        if (!parentNode.children) {
            parentNode.children = [];
        }
        const newNode = {
            content: content,
            children: []
        };
        parentNode.children.push(newNode);
        return newNode;
    }

    addSiblingNode(node, parent, content = '新节点') {
        if (!parent || !node) return null;
        if (!parent.children) {
            parent.children = [];
        }
        const index = parent.children.indexOf(node);
        if (index === -1) return null;
        
        const newNode = {
            content: content,
            children: []
        };
        parent.children.splice(index + 1, 0, newNode);
        return newNode;
    }

    deleteNode(node, parent) {
        if (!parent || !node || !parent.children) return false;
        const index = parent.children.indexOf(node);
        if (index === -1) return false;
        parent.children.splice(index, 1);
        if (parent.children.length === 0) {
            delete parent.children;
        }
        return true;
    }

    updateNodeContent(node, newContent) {
        if (!node) return false;
        node.content = newContent;
        return true;
    }

    getRootNode(tree) {
        return tree;
    }

    getNodeDepth(node, tree) {
        if (!node || !tree) return -1;
        
        const findDepth = (current, target, depth) => {
            if (current === target) return depth;
            if (current.children) {
                for (const child of current.children) {
                    const result = findDepth(child, target, depth + 1);
                    if (result !== -1) return result;
                }
            }
            return -1;
        };
        
        return findDepth(tree, node, 0);
    }
}

window.MarkdownTreeConverter = MarkdownTreeConverter;
