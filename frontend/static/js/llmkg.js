document.addEventListener('DOMContentLoaded', function() {
    /* 问答交互 */
    const questionInput = document.getElementById('questionInput');
    const sendButton = document.getElementById('sendButton');
    const charCount = document.getElementById('charCount');
    const chatHistory = document.getElementById('chatHistory');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const retrievalContent = document.getElementById('retrievalContent');
    const conversationsList = document.getElementById('conversationsList');
    const newConversationBtn = document.getElementById('newConversationBtn');
    const renameConversationBtn = document.getElementById('renameConversationBtn');
    const deleteConversationBtn = document.getElementById('deleteConversationBtn');
    const conversationTitle = document.getElementById('conversationTitle');

    if (!questionInput || !sendButton || !charCount || !chatHistory || !loadingIndicator) {
        return;
    }

    // 会话管理（使用后端API）
    let conversations = [];
    let currentConversationId = null;

    // 从后端加载会话列表
    async function loadConversations() {
        try {
            const res = await fetch('/api/llm/sessions');
            const data = await res.json();
            if (data.success) {
                conversations = data.sessions || [];
            } else {
                console.error('加载会话失败:', data.error);
                conversations = [];
            }
        } catch (e) {
            console.error('加载会话失败:', e);
            conversations = [];
        }
    }

    // 创建新会话
    async function createConversation(title = null) {
        try {
            const res = await fetch('/api/llm/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: title })
            });
            const data = await res.json();
            if (data.success) {
                const conversation = data.session;
                conversations.unshift(conversation); // 添加到开头
                await renderConversationsList();
                await switchConversation(conversation.id);
                return conversation;
            } else {
                console.error('创建会话失败:', data.error);
                return null;
            }
        } catch (e) {
            console.error('创建会话失败:', e);
            return null;
        }
    }

    // 删除会话
    async function deleteConversation(id) {
        if (confirm('确定要删除这个对话吗？')) {
            try {
                const res = await fetch(`/api/llm/sessions/${id}`, {
                    method: 'DELETE'
                });
                const data = await res.json();
                if (data.success) {
                    conversations = conversations.filter(c => c.id !== id);
                    if (currentConversationId === id) {
                        if (conversations.length > 0) {
                            await switchConversation(conversations[0].id);
                        } else {
                            await createConversation();
                        }
                    } else {
                        await renderConversationsList();
                    }
                } else {
                    alert('删除失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                console.error('删除会话失败:', e);
                alert('删除失败，请重试');
            }
        }
    }

    // 重命名会话
    async function renameConversation(id) {
        const conversation = conversations.find(c => c.id === id);
        if (!conversation) return;
        
        const newTitle = prompt('请输入新的对话标题:', conversation.title);
        if (newTitle && newTitle.trim()) {
            try {
                const res = await fetch(`/api/llm/sessions/${id}/title`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: newTitle.trim() })
                });
                const data = await res.json();
                if (data.success) {
                    conversation.title = newTitle.trim();
                    await renderConversationsList();
                    if (currentConversationId === id) {
                        updateConversationTitle();
                    }
                } else {
                    alert('重命名失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                console.error('重命名会话失败:', e);
                alert('重命名失败，请重试');
            }
        }
    }

    // 切换会话
    async function switchConversation(id) {
        const conversation = conversations.find(c => c.id === id);
        if (!conversation) return;

        // 保存当前会话的消息到后端
        if (currentConversationId && conversationMessages.length > 0) {
            await saveCurrentSessionMessages();
        }

        // 从后端加载新会话的消息
        try {
            const res = await fetch(`/api/llm/sessions/${id}`);
            const data = await res.json();
            if (data.success) {
                currentConversationId = id;
                conversationMessages = data.messages || [];
                
                // 更新会话信息
                const idx = conversations.findIndex(c => c.id === id);
                if (idx >= 0) {
                    conversations[idx] = data.session;
                }
            } else {
                console.error('加载会话失败:', data.error);
                conversationMessages = [];
            }
        } catch (e) {
            console.error('加载会话失败:', e);
            conversationMessages = [];
        }
        
        // 清空检索面板
        if (retrievalContent) {
            retrievalContent.innerHTML = '<p class="muted">暂无检索结果，若为空将基于通用知识回答。</p>';
        }
        
        // 更新UI
        await renderConversationsList();
        renderChatHistory();
        updateConversationTitle();
    }

    // 保存当前会话的消息到后端
    async function saveCurrentSessionMessages() {
        if (!currentConversationId || conversationMessages.length === 0) {
            return;
        }
        
        try {
            const res = await fetch(`/api/llm/sessions/${currentConversationId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: conversationMessages })
            });
            const data = await res.json();
            if (!data.success) {
                console.error('保存会话消息失败:', data.error);
            }
        } catch (e) {
            console.error('保存会话消息失败:', e);
        }
    }

    // 渲染会话列表
    async function renderConversationsList() {
        if (!conversationsList) return;
        
        // 重新加载会话列表以确保最新
        await loadConversations();
        
        conversationsList.innerHTML = '';
        conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conversation-item' + (conv.id === currentConversationId ? ' active' : '');
            item.innerHTML = `
                <span class="conversation-item-title" title="${conv.title}">${conv.title}</span>
                <div class="conversation-item-actions">
                    <button onclick="event.stopPropagation(); renameConversationById('${conv.id}')" title="重命名">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="event.stopPropagation(); deleteConversationById('${conv.id}')" title="删除">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `;
            item.addEventListener('click', () => switchConversation(conv.id));
            conversationsList.appendChild(item);
        });
    }

    // 更新对话标题
    function updateConversationTitle() {
        if (!conversationTitle) return;
        const conversation = conversations.find(c => c.id === currentConversationId);
        if (conversation) {
            conversationTitle.innerHTML = `<i class="fas fa-comments" style="margin-right:8px;color:#2F80ED;"></i>${conversation.title}`;
        }
    }

    // 渲染聊天历史
    function renderChatHistory() {
        if (!chatHistory) return;
        
        chatHistory.innerHTML = '';
        
        if (conversationMessages.length === 0) {
            // 显示欢迎消息
            const welcomeDiv = document.createElement('div');
            welcomeDiv.className = 'welcome-message';
            welcomeDiv.innerHTML = `
                <div class="bot-avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <p>您好！这里可以提问缺陷检测相关的问题，同时在右侧查看图谱上下文。</p>
                    <p>输入问题并发送，我会基于知识库给出回答。</p>
                </div>
            `;
            chatHistory.appendChild(welcomeDiv);
        } else {
            // 渲染历史消息
            conversationMessages.forEach(msg => {
                if (msg.role === 'user' || msg.role === 'assistant') {
                    addMessageToHistory(msg.content, msg.role === 'user' ? 'user' : 'bot');
                }
            });
        }
        
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // 添加消息到历史（不添加到messages数组）
    function addMessageToHistory(content, type) {
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
    }

    // 全局函数供HTML调用
    window.renameConversationById = function(id) {
        renameConversation(id);
    };

    window.deleteConversationById = function(id) {
        deleteConversation(id);
    };

    // 事件监听
    if (newConversationBtn) {
        newConversationBtn.addEventListener('click', () => createConversation());
    }

    if (renameConversationBtn) {
        renameConversationBtn.addEventListener('click', () => {
            if (currentConversationId) {
                renameConversation(currentConversationId);
            }
        });
    }

    if (deleteConversationBtn) {
        deleteConversationBtn.addEventListener('click', () => {
            if (currentConversationId) {
                deleteConversation(currentConversationId);
            }
        });
    }

    // 维护对话历史（messages数组），按照OpenAI格式
    let conversationMessages = [];

    // 初始化
    (async function init() {
        await loadConversations();
        if (conversations.length === 0) {
            await createConversation();
        } else {
            await switchConversation(conversations[0].id);
        }
    })();

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

    async function sendQuestion() {
        const question = questionInput.value.trim();
        if (!question) return;

        addMessage(question, 'user');
        
        // 将用户消息添加到对话历史
        conversationMessages.push({"role": "user", "content": question});
        
        questionInput.value = '';
        charCount.textContent = '0';
        sendButton.disabled = true;

        loadingIndicator.style.display = 'flex';

        try {
            // kick off an async retrieval call so user sees documents quickly
            fetchRetrievalDocs(question, 6).catch(err => console.warn('检索失败', err));
            const res = await fetch('/api/llm/llm_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question: question,
                    messages: conversationMessages  // 发送对话历史
                })
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({ error: '服务错误' }));
                loadingIndicator.style.display = 'none';
                sendButton.disabled = false;
                addMessage(err.error || '服务错误', 'bot');
                return;
            }

            // 展示检索信息（从响应头获取）
            updateRetrievalPanel(res);

            // 若后端返回了生成的 Cypher（Base64），在右侧同步执行
            const cypherB64 = res.headers.get('X-Cypher-B64');
            if (cypherB64) {
                try {
                    const bytes = Uint8Array.from(atob(cypherB64), c => c.charCodeAt(0));
                    const decoded = new TextDecoder('utf-8').decode(bytes);
                    const queryInput = document.getElementById('cypherQuery');
                    if (queryInput) queryInput.value = decoded;
                    if (decoded) {
                        if (viz) viz.clearNetwork();
                        config.initialCypher = decoded;
                        viz = new NeoVis.default(config);
                        viz.render();
                        showStatus('已用生成语句更新图谱', 'success');
                    }
                } catch (err) {
                    console.error('解码或渲染生成语句失败', err);
                    showStatus('图谱更新失败: ' + err.message, 'error');
                }
            }

            const reader = res.body.getReader();
            const decoder = new TextDecoder('utf-8');
            const botContent = addStreamingMessage('bot');

            let assistantReply = '';  // 收集完整的assistant回复
            let done = false;
            while (!done) {
                const { value, done: streamDone } = await reader.read();
                if (value) {
                    const chunk = decoder.decode(value, { stream: true });
                    assistantReply += chunk;  // 累积完整回复
                    botContent.innerHTML += chunk.replace(/\n/g, '<br>');
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }
                done = streamDone;
            }

            // 将assistant回复添加到对话历史
            if (assistantReply.trim()) {
                conversationMessages.push({"role": "assistant", "content": assistantReply.trim()});
                
                // 保存到后端
                if (currentConversationId) {
                    await saveCurrentSessionMessages();
                    // 重新加载会话列表以更新标题（如果自动生成了）
                    await renderConversationsList();
                    updateConversationTitle();
                }
            }

            loadingIndicator.style.display = 'none';
            sendButton.disabled = false;
        } catch (err) {
            console.error(err);
            loadingIndicator.style.display = 'none';
            sendButton.disabled = false;
            addMessage('调用大模型失败，请检查网络或服务状态。', 'bot');
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    }

    // Fetch vector retrieval results and render into the retrieval panel
    async function fetchRetrievalDocs(query, k=5) {
        if (!retrievalContent) return;
        retrievalContent.innerHTML = '<p class="muted">检索中…</p>';
        try {
            const res = await fetch(`/api/kg/textdb/vector_search?q=${encodeURIComponent(query)}&k=${k}`);
            if (!res.ok) {
                retrievalContent.innerHTML = `<p class="muted">检索失败: ${res.status}</p>`;
                return;
            }
            const data = await res.json();
            if (!data.success) {
                retrievalContent.innerHTML = `<p class="muted">检索失败: ${data.error || '未知错误'}</p>`;
                return;
            }
            renderRetrieval(data.results || []);
            // also try to get a cypher to update the graph quickly
            try {
                const cres = await fetch('/api/llm/gen_cypher', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: query, max_rows: 50 })
                });
                if (cres.ok) {
                    const cdata = await cres.json();
                    if (cdata.success && cdata.viz) {
                        // update the cypher query input and render viz
                        const queryInput = document.getElementById('cypherQuery');
                        if (queryInput) queryInput.value = cdata.viz;
                        try {
                            if (viz) viz.clearNetwork();
                            config.initialCypher = cdata.viz;
                            viz = new NeoVis.default(config);
                            viz.render();
                            showStatus('已用检索生成的语句更新图谱', 'success');
                        } catch (err) {
                            console.error('渲染检索生成语句失败', err);
                        }
                    }
                }
            } catch (e) {
                console.warn('gen_cypher failed', e);
            }
        } catch (e) {
            console.error(e);
            retrievalContent.innerHTML = '<p class="muted">检索异常</p>';
        }
    }

    function _createRetrievalCard(it) {
        const card = document.createElement('div');
        card.className = 'retrieval-card';
        const meta = document.createElement('div');
        meta.className = 'meta';
        const sc = (it.score || (it.item && it.item.score) || 0);
        const scText = (typeof sc === 'number' && sc.toFixed) ? sc.toFixed(3) : sc;
        meta.innerHTML = `<div><strong>#${it.item?.id ?? ''}</strong></div><div>score: ${scText}</div>`;
        const body = document.createElement('div');
        body.className = 'body';
        const snippet = document.createElement('div');
        snippet.className = 'snippet';
        const text = it.item?.text ?? '';
        snippet.textContent = text.length > 220 ? (text.slice(0,220) + '…') : text;
        const full = document.createElement('div');
        full.className = 'fulltext';
        full.textContent = text;
        const actions = document.createElement('div');
        actions.className = 'actions';
        const btnCopy = document.createElement('button');
        btnCopy.textContent = '复制ID';
        btnCopy.addEventListener('click', () => {
            const id = it.item?.id ?? '';
            if (navigator.clipboard) navigator.clipboard.writeText(String(id));
            showStatus('已复制 id: ' + id, 'success');
        });
        const btnOpen = document.createElement('button');
        btnOpen.textContent = '在文本库中查看';
        btnOpen.addEventListener('click', () => {
            const filter = document.getElementById('textDbFilter');
            if (filter) { filter.value = String(it.item?.id ?? ''); filter.dispatchEvent(new Event('input')); }
            showStatus('已跳转到文本库并筛选', 'success');
        });
        actions.appendChild(btnCopy);
        actions.appendChild(btnOpen);

        body.appendChild(snippet);
        body.appendChild(full);
        body.appendChild(actions);

        card.appendChild(meta);
        card.appendChild(body);
        return card;
    }

    function renderRetrieval(items) {
        if (!retrievalContent) return;
        if (!items || !items.length) {
            retrievalContent.innerHTML = '<p class="muted">未检索到相关信息，将基于通用知识回答。</p>';
            return;
        }

        // Compact: show only up to two summary cards in the small container
        retrievalContent.innerHTML = '';
        const preview = items.slice(0, 2);
        preview.forEach(it => {
            const card = _createRetrievalCard(it);
            retrievalContent.appendChild(card);
        });

        // Show header "查看全部" button when there are more items
        const headerBtn = document.getElementById('openRetrievalModalHeader');
        if (headerBtn) {
            if (items.length > 2) {
                headerBtn.style.display = 'inline-block';
                headerBtn.textContent = `查看全部 (${items.length})`;
                headerBtn.onclick = () => openRetrievalModal(items);
            } else {
                headerBtn.style.display = 'none';
                headerBtn.onclick = null;
            }
        }

        // ensure compact class applied when items present
        if (items && items.length > 0) retrievalContent.classList.add('compact');
        else retrievalContent.classList.remove('compact');

        // populate modal body as well
        const modalBody = document.getElementById('retrievalModalBody');
        if (modalBody) {
            modalBody.innerHTML = '';
            items.forEach(it => {
                const card = _createRetrievalCard(it);
                modalBody.appendChild(card);
            });
        }
    }

    function openRetrievalModal(items) {
        const modal = document.getElementById('retrievalModal');
        const modalBody = document.getElementById('retrievalModalBody');
        if (!modal || !modalBody) return;
        // modalBody already populated in renderRetrieval, but ensure
        if (items) {
            modalBody.innerHTML = '';
            items.forEach(it => modalBody.appendChild(_createRetrievalCard(it)));
        }
        modal.setAttribute('aria-hidden', 'false');
    }

    function closeRetrievalModal() {
        const modal = document.getElementById('retrievalModal');
        if (!modal) return;
        modal.setAttribute('aria-hidden', 'true');
    }

    // retrieval panel reference (header button handled in renderRetrieval)
    const retrievalPanel = document.querySelector('.retrieval-panel');

    // modal controls
    const closeRetrievalModalBtn = document.getElementById('closeRetrievalModal');
    const retrievalModalOverlay = document.getElementById('retrievalModalOverlay');
    if (closeRetrievalModalBtn) closeRetrievalModalBtn.addEventListener('click', closeRetrievalModal);
    if (retrievalModalOverlay) retrievalModalOverlay.addEventListener('click', closeRetrievalModal);

    function updateRetrievalPanel(res) {
        if (!retrievalContent) return;
        // If we've already rendered retrieval cards client-side (from vector_search),
        // don't overwrite them with the server-sent rag text header which may be less structured.
        if (retrievalContent.querySelector('.retrieval-card') || retrievalContent.classList.contains('compact')) {
            return;
        }

        let ragText = '';
        try {
            const ragB64 = res.headers.get('X-RAG-TEXT-B64');
            if (ragB64) {
                const bytes = Uint8Array.from(atob(ragB64), c => c.charCodeAt(0));
                ragText = new TextDecoder('utf-8').decode(bytes);
            }
        } catch (e) {
            console.warn('解析检索结果失败', e);
        }

        if (ragText && ragText.trim().length > 0) {
            const html = ragText
                .split('\n')
                .map(line => line.trim())
                .filter(line => line.length > 0)
                .map(line => `<p>${line.replace(/\n/g, '<br>')}</p>`)
                .join('');
            retrievalContent.innerHTML = html;
        } else {
            retrievalContent.innerHTML = '<p class="muted">未检索到相关信息，将基于通用知识回答。</p>';
        }
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
    const refreshSchemaBtn = document.getElementById('refreshSchema');
    const cypherInput = document.getElementById('cypherQuery');

    if (runQueryBtn) runQueryBtn.addEventListener('click', runCustomQuery);
    if (resetViewBtn) resetViewBtn.addEventListener('click', resetView);
    if (fitViewBtn) fitViewBtn.addEventListener('click', fitView);
    if (refreshSchemaBtn) {
        refreshSchemaBtn.addEventListener('click', async () => {
            try {
                const res = await fetch('/api/kg/schema/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
                const data = await res.json();
                if (data.success) {
                    showStatus('Schema 已从 CSV 更新', 'success');
                } else {
                    showStatus('Schema 更新失败: ' + (data.error || '未知错误'), 'error');
                }
            } catch (e) {
                console.error(e);
                showStatus('Schema 更新异常', 'error');
            }
        });
    }
    if (cypherInput) {
        cypherInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') runCustomQuery();
        });
    }

    // load viz and text DB after a short delay
    setTimeout(() => {
        initViz();
        loadTextDb();
    }, 800);

    // Text DB: fetch and render
    async function loadTextDb(limit = 50, offset = 0, q = '') {
        const cont = document.getElementById('textDb');
        if (!cont) return;
        cont.innerHTML = '<p class="muted">正在加载…</p>';
        try {
            const url = `/api/kg/textdb?limit=${limit}&offset=${offset}` + (q ? `&q=${encodeURIComponent(q)}` : '');
            const res = await fetch(url);
            if (!res.ok) {
                cont.innerHTML = `<p class="muted">加载失败: ${res.status}</p>`;
                return;
            }
            const data = await res.json();
            if (!data.success) {
                cont.innerHTML = `<p class="muted">加载失败: ${data.error || '未知错误'}</p>`;
                return;
            }
            renderTextDb(data.items || []);
            const header = document.querySelector('.text-db-panel .panel-header h3');
            if (header) {
                const countSpan = header.querySelector('.count');
                if (countSpan) countSpan.remove();
                const span = document.createElement('span');
                span.className = 'count';
                span.style.fontWeight = '400';
                span.style.fontSize = '13px';
                span.style.color = 'var(--muted)';
                span.style.marginLeft = '8px';
                span.textContent = `(${data.items ? data.items.length : 0}/${data.count || 0})`;
                header.appendChild(span);
            }
        } catch (e) {
            console.error(e);
            cont.innerHTML = `<p class="muted">加载异常</p>`;
        }
    }

    // debounce helper
    function debounce(fn, wait) {
        let t;
        return function(...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        }
    }

    const refreshTextDbBtn = document.getElementById('refreshTextDb');
    if (refreshTextDbBtn) {
        refreshTextDbBtn.addEventListener('click', () => loadTextDb());
    }

    const textDbFilter = document.getElementById('textDbFilter');
    if (textDbFilter) {
        const debounced = debounce(() => loadTextDb(50,0,textDbFilter.value.trim()), 300);
        textDbFilter.addEventListener('input', debounced);
        // allow Enter to force immediate search
        textDbFilter.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') loadTextDb(50,0,textDbFilter.value.trim());
        });
    }

    function renderTextDb(items) {
        const cont = document.getElementById('textDb');
        if (!cont) return;
        if (!items || !items.length) {
            cont.innerHTML = '<p class="muted">没有数据</p>';
            return;
        }
        cont.innerHTML = '';
        items.forEach(it => {
            const el = document.createElement('div');
            el.className = 'text-db-item';
            const idSpan = document.createElement('span');
            idSpan.className = 'id';
            idSpan.textContent = `#${it.id}`;
            const txtSpan = document.createElement('span');
            txtSpan.className = 'txt';
            txtSpan.textContent = it.text || '';
            el.appendChild(idSpan);
            el.appendChild(txtSpan);
            el.addEventListener('click', () => {
                // show full text in status area for quick inspection
                showStatus(it.text || '(无内容)', 'success');
            });
            cont.appendChild(el);
        });
    }

});
