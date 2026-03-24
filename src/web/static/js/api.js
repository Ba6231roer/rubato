const API = {
    baseUrl: window.location.origin,
    
    async getConfigs() {
        const response = await fetch(`${this.baseUrl}/api/configs`);
        return response.json();
    },
    
    async getConfig(name) {
        const response = await fetch(`${this.baseUrl}/api/configs/${name}`);
        if (!response.ok) {
            throw new Error(`获取配置失败: ${response.statusText}`);
        }
        return response.json();
    },
    
    async updateConfig(name, content) {
        const response = await fetch(`${this.baseUrl}/api/configs/${name}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content })
        });
        return response.json();
    },
    
    async getStatus() {
        const response = await fetch(`${this.baseUrl}/api/status`);
        return response.json();
    },
    
    async getSkills() {
        const response = await fetch(`${this.baseUrl}/api/skills`);
        return response.json();
    },
    
    async getTools() {
        const response = await fetch(`${this.baseUrl}/api/tools`);
        return response.json();
    },
    
    async getTestCaseTree() {
        const response = await fetch(`${this.baseUrl}/api/testcases/tree`);
        return response.json();
    },
    
    async getTestCaseFile(path) {
        const response = await fetch(`${this.baseUrl}/api/testcases/file?path=${encodeURIComponent(path)}`);
        if (!response.ok) {
            throw new Error(`获取文件失败: ${response.statusText}`);
        }
        return response.json();
    },
    
    async updateTestCaseFile(path, content) {
        const response = await fetch(`${this.baseUrl}/api/testcases/file`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path, content })
        });
        return response.json();
    },
    
    async getKnowledgeTree() {
        const response = await fetch(`${this.baseUrl}/api/knowledge/tree`);
        return response.json();
    },
    
    async getKnowledgeFile(path) {
        const response = await fetch(`${this.baseUrl}/api/knowledge/file?path=${encodeURIComponent(path)}`);
        if (!response.ok) {
            throw new Error(`获取文件失败: ${response.statusText}`);
        }
        return response.json();
    },
    
    async updateKnowledgeFile(path, content) {
        const response = await fetch(`${this.baseUrl}/api/knowledge/file`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path, content })
        });
        return response.json();
    }
};

class WebSocketClient {
    constructor(onMessage, onConnect, onDisconnect) {
        this.ws = null;
        this.onMessage = onMessage;
        this.onConnect = onConnect;
        this.onDisconnect = onDisconnect;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }
    
    connect() {
        const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            if (this.onConnect) this.onConnect();
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (this.onMessage) this.onMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            if (this.onDisconnect) this.onDisconnect();
            this.attemptReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
            setTimeout(() => this.connect(), 2000 * this.reconnectAttempts);
        }
    }
    
    send(type, content) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, content }));
        } else {
            console.error('WebSocket is not connected');
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}
