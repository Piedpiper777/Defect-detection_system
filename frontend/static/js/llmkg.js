document.addEventListener('DOMContentLoaded', function() {
    /* 问答交互 */
    const questionInput = document.getElementById('questionInput');
    const sendButton = document.getElementById('sendButton');
    const charCount = document.getElementById('charCount');
    const chatHistory = document.getElementById('chatHistory');
    const loadingIndicator = document.getElementById('loadingIndicator');

    if (!questionInput || !sendButton || !charCount || !chatHistory || !loadingIndicator) {
        return;
    }

    questionInput.addEventListener('input', function() {
        const length = this.value.length;
        charCount.textContent = length;
        sendButton.disabled = length === 0 || length > 1000;
    });

    sendButton.addEventListener('click', sendQuestion);
    questionInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendButton.disabled) sendQuestion();
        }
    });

    function sendQuestion() {
        const question = questionInput.value.trim();
        if (!question) return;

        addMessage(question, 'user');
        questionInput.value = '';
        charCount.textContent = '0';
        sendButton.disabled = true;

        loadingIndicator.style.display = 'flex';

        // 使用流式API
        fetch('/api/llm/llm_stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        }).then(async (res) => {
            if (!res.ok) {
                // 后端返回错误（非200），尝试读取json并提示
                const err = await res.json().catch(() => ({ error: '服务返回错误' }));
                loadingIndicator.style.display = 'none';
                sendButton.disabled = false;
                addMessage(err.error || '服务错误', 'bot');
                chatHistory.scrollTop = chatHistory.scrollHeight;
                return;
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder('utf-8');

            // 创建一个空的 bot 消息，并返回内容容器以便后续追加
            const botContent = addStreamingMessage('bot');

            let done = false;
            while (!done) {
                const { value, done: streamDone } = await reader.read();
                if (value) {
                    const chunk = decoder.decode(value, { stream: true });
                    // 追加文本
                    botContent.innerHTML += chunk.replace(/\n/g, '<br>');
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }
                done = streamDone;
            }

            loadingIndicator.style.display = 'none';
            sendButton.disabled = false;
        }).catch(err => {
            console.error(err);
            loadingIndicator.style.display = 'none';
            sendButton.disabled = false;
            addMessage('调用大模型失败，请检查网络或服务状态。', 'bot');
            chatHistory.scrollTop = chatHistory.scrollHeight;
        });
    }

    function addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = type === 'user' ? 'user-avatar' : 'bot-avatar';
        avatarDiv.innerHTML = type === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = `<p>${content.replace(/\n/g, '<br>')}</p>`;

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatHistory.appendChild(messageDiv);
        return contentDiv;
    }

    function addStreamingMessage(type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = type === 'user' ? 'user-avatar' : 'bot-avatar';
        avatarDiv.innerHTML = type === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = '';

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatHistory.appendChild(messageDiv);
        return contentDiv;
    }


    /* 图谱可视化 */
    let viz;
    const configElement = document.getElementById('neo4j-config');
    const neo4jConfig = configElement ? JSON.parse(configElement.textContent || '{}') : {};
    const config = {
        containerId: 'viz',
        neo4j: {
            serverUrl: neo4jConfig.serverUrl,
            serverUser: neo4jConfig.serverUser,
            serverPassword: neo4jConfig.serverPassword
        },
        visConfig: {
            nodes: {
                shape: 'circle',
                size: 48,
                scaling: { label: { enabled: false } },
                font: { size: 12, color: '#222' },
                borderWidth: 0.2
            },
            edges: {
                arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                font: { size: 12, align: 'middle' }
            },
            physics: {
                enabled: true,
                barnesHut: {
                    gravitationalConstant: -8000,
                    centralGravity: 0.3,
                    springLength: 95,
                    springConstant: 0.04,
                    damping: 0.09,
                    avoidOverlap: 0
                }
            },
            interaction: { hover: true, selectConnectedEdges: true, multiselect: true }
        },
        labels: {
            'DetectObject   ': { label: 'name' },
            'DefectType': { label: 'name' },
            'Cause': { label: 'name' },
            'Solution': { label: 'name' }
        },
        relationships: {
            [NeoVis.NEOVIS_DEFAULT_CONFIG]: {
                [NeoVis.NEOVIS_ADVANCED_CONFIG]: {
                    function: { label: (rel) => (rel?.raw?.type) || rel?.type || '' }
                }
            }
        },
        initialCypher: 'MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100'
    };

    function initViz() {
        try {
            viz = new NeoVis.default(config);
            viz.render();
            showStatus('可视化初始化成功', 'success');
        } catch (error) {
            showStatus('可视化初始化失败: ' + error.message, 'error');
            console.error(error);
        }
    }

    function showStatus(message, type) {
        const statusDiv = document.getElementById('statusMessage');
        if (!statusDiv) return;
        statusDiv.textContent = message;
        statusDiv.className = `status-message ${type}`;
        statusDiv.style.display = 'block';
        setTimeout(() => { statusDiv.style.display = 'none'; }, 2800);
    }

    function runCustomQuery() {
        const queryInput = document.getElementById('cypherQuery');
        const query = queryInput ? queryInput.value.trim() : '';
        if (!query) {
            showStatus('请输入查询语句', 'error');
            return;
        }

        try {
            if (viz) viz.clearNetwork();
            config.initialCypher = query;
            viz = new NeoVis.default(config);
            viz.render();
            showStatus('查询执行成功', 'success');
        } catch (error) {
            showStatus('查询执行失败: ' + error.message, 'error');
            console.error(error);
        }
    }

    function resetView() {
        if (viz && viz.network) {
            viz.network.fit();
            showStatus('视图已重置', 'success');
        }
    }

    function fitView() {
        if (viz && viz.network) {
            viz.network.fit({ animation: { duration: 900, easingFunction: 'easeInOutQuad' } });
            showStatus('视图已适应屏幕', 'success');
        }
    }

    const runQueryBtn = document.getElementById('runQuery');
    const resetViewBtn = document.getElementById('resetView');
    const fitViewBtn = document.getElementById('fitView');
    const cypherInput = document.getElementById('cypherQuery');

    if (runQueryBtn) runQueryBtn.addEventListener('click', runCustomQuery);
    if (resetViewBtn) resetViewBtn.addEventListener('click', resetView);
    if (fitViewBtn) fitViewBtn.addEventListener('click', fitView);
    if (cypherInput) {
        cypherInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') runCustomQuery();
        });
    }

    setTimeout(initViz, 800);
});
