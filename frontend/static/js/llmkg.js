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
    const memoryUpdateBtn = document.getElementById('memoryUpdateBtn');
    const memoryUpdateModal = document.getElementById('memoryUpdateModal');
    const memoryModalOverlay = document.getElementById('memoryModalOverlay');
    const closeMemoryModal = document.getElementById('closeMemoryModal');
    const memoryUpdateControls = document.getElementById('memoryUpdateControls');
    const memoryUpdateConfirmSelectionBtn = document.getElementById('memoryUpdateConfirmSelectionBtn');
    const memoryUpdateCancelSelectionBtn = document.getElementById('memoryUpdateCancelSelectionBtn');
    const memoryUpdateConfirmBtn = document.getElementById('memoryUpdateConfirmBtn');
    const memoryUpdateCancelBtn = document.getElementById('memoryUpdateCancelBtn');
    const memoryUpdateCloseBtn = document.getElementById('memoryUpdateCloseBtn');
    const memoryProcessingState = document.getElementById('memoryProcessingState');
    const memoryResultState = document.getElementById('memoryResultState');
    const memoryUpdateResultState = document.getElementById('memoryUpdateResultState');
    const memorySummaryContent = document.getElementById('memorySummaryContent');
    const memoryRelationshipType = document.getElementById('memoryRelationshipType');
    const memoryUpdateMessage = document.getElementById('memoryUpdateMessage');
    const selectedCount = document.getElementById('selectedCount');

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
            conversationMessages.forEach((msg, index) => {
                if (msg.role === 'user' || msg.role === 'assistant') {
                    addMessageToHistory(msg.content, msg.role === 'user' ? 'user' : 'bot', index);
                }
            });
        }
        
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    // 记忆更新相关状态
    let isMemoryUpdateMode = false;
    let selectedMessageIndices = new Set();
    let currentMemoryId = null;
    
    // HTML转义函数
    function escapeHtml(text) {
        if (typeof text !== 'string') {
            text = String(text);
        }
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // 添加消息到历史（不添加到messages数组）
    function addMessageToHistory(content, type, index = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        if (index !== null) {
            messageDiv.dataset.messageIndex = index;
        }

        const avatarDiv = document.createElement('div');
        avatarDiv.className = type === 'user' ? 'user-avatar' : 'bot-avatar';
        avatarDiv.innerHTML = type === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        // 安全地转义HTML
        const escapedContent = escapeHtml(content).replace(/\n/g, '<br>');
        contentDiv.innerHTML = `<p>${escapedContent}</p>`;

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatHistory.appendChild(messageDiv);
        
        // 如果处于记忆更新模式，添加勾选功能
        if (isMemoryUpdateMode && index !== null) {
            messageDiv.classList.add('selectable');
            messageDiv.addEventListener('click', () => toggleMessageSelection(index, messageDiv));
        }
        
        return messageDiv;
    }
    
    // 切换消息选择状态
    function toggleMessageSelection(index, messageDiv) {
        if (selectedMessageIndices.has(index)) {
            selectedMessageIndices.delete(index);
            messageDiv.classList.remove('selected');
        } else {
            selectedMessageIndices.add(index);
            messageDiv.classList.add('selected');
        }
        updateSelectedCount();
    }
    
    // 更新选中数量显示
    function updateSelectedCount() {
        if (selectedCount) {
            selectedCount.textContent = selectedMessageIndices.size;
        }
    }
    
    // 进入记忆更新模式
    function enterMemoryUpdateMode() {
        isMemoryUpdateMode = true;
        selectedMessageIndices.clear();
        updateSelectedCount();
        
        // 为所有消息添加勾选功能
        const messages = chatHistory.querySelectorAll('.message');
        messages.forEach((msgDiv, idx) => {
            const msgIndex = parseInt(msgDiv.dataset.messageIndex);
            if (!isNaN(msgIndex)) {
                msgDiv.classList.add('selectable');
                msgDiv.addEventListener('click', () => toggleMessageSelection(msgIndex, msgDiv));
            }
        });
        
        // 显示控制按钮
        if (memoryUpdateControls) {
            memoryUpdateControls.style.display = 'block';
        }
        
        // 禁用记忆更新按钮
        if (memoryUpdateBtn) {
            memoryUpdateBtn.disabled = true;
        }
    }
    
    // 退出记忆更新模式
    function exitMemoryUpdateMode() {
        isMemoryUpdateMode = false;
        selectedMessageIndices.clear();
        
        // 移除所有消息的勾选功能
        const messages = chatHistory.querySelectorAll('.message.selectable');
        messages.forEach(msgDiv => {
            msgDiv.classList.remove('selectable', 'selected');
        });
        
        // 隐藏控制按钮
        if (memoryUpdateControls) {
            memoryUpdateControls.style.display = 'none';
        }
        
        // 启用记忆更新按钮
        if (memoryUpdateBtn) {
            memoryUpdateBtn.disabled = false;
        }
    }
    
    // 提交选中的消息进行总结
    async function submitMemoryUpdate() {
        if (selectedMessageIndices.size === 0) {
            alert('请至少选择一条消息');
            return;
        }
        
        // 获取选中的消息
        const selectedMessages = [];
        selectedMessageIndices.forEach(index => {
            if (conversationMessages[index]) {
                selectedMessages.push(conversationMessages[index]);
            }
        });
        
        if (selectedMessages.length === 0) {
            alert('选中的消息无效');
            return;
        }
        
        // 显示处理中弹窗
        showMemoryModal('processing');
        
        try {
            // 调用后端API进行总结
            const res = await fetch('/api/llm/memory/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: selectedMessages })
            });
            
            const data = await res.json();
            
            if (data.success) {
                currentMemoryId = data.memory_id;
                // 显示结果
                showMemoryModal('result', data.memory);
            } else {
                alert('总结失败: ' + (data.error || '未知错误'));
                closeMemoryModalFunc();
            }
        } catch (e) {
            console.error('提交记忆更新失败:', e);
            alert('提交失败，请重试');
            closeMemoryModalFunc();
        }
        
        // 退出记忆更新模式
        exitMemoryUpdateMode();
    }
    
    // 确认更新记忆到知识库
    async function confirmMemoryUpdate() {
        if (!currentMemoryId) {
            alert('记忆ID不存在');
            return;
        }
        
        // 显示处理中状态
        showMemoryModal('processing');
        
        try {
            const res = await fetch('/api/llm/memory/update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ memory_id: currentMemoryId })
            });
            
            const data = await res.json();
            
            if (data.success) {
                // 在弹窗中显示更新结果
                showMemoryModal('updateResult', data);
            } else {
                alert('更新失败: ' + (data.error || '未知错误'));
                showMemoryModal('result', data.memory || null);
            }
        } catch (e) {
            console.error('更新记忆失败:', e);
            alert('更新失败，请重试');
            showMemoryModal('result', null);
        }
    }
    
    // 显示记忆弹窗
    function showMemoryModal(state, memoryData = null) {
        if (!memoryUpdateModal) return;
        
        memoryUpdateModal.setAttribute('aria-hidden', 'false');
        
        // 隐藏所有状态
        if (memoryProcessingState) memoryProcessingState.style.display = 'none';
        if (memoryResultState) memoryResultState.style.display = 'none';
        if (memoryUpdateResultState) memoryUpdateResultState.style.display = 'none';
        
        if (state === 'processing') {
            if (memoryProcessingState) memoryProcessingState.style.display = 'block';
        } else if (state === 'result') {
            if (memoryResultState) memoryResultState.style.display = 'block';
            
            if (memoryData && memorySummaryContent) {
                memorySummaryContent.textContent = memoryData.summary || '无内容';
            }
        } else if (state === 'updateResult') {
            if (memoryUpdateResultState) memoryUpdateResultState.style.display = 'block';
            
            // 显示关系类型
            if (memoryData && memoryRelationshipType) {
                const relationship = memoryData.relationship || 'unknown';
                const relationshipText = {
                    'high_similarity': '高度相似',
                    'extension': '补充扩展',
                    'difference': '存在差异'
                }[relationship] || relationship;
                memoryRelationshipType.textContent = relationshipText;
                memoryRelationshipType.className = 'result-value relationship-' + relationship;
            }
            
            // 显示处理结果消息
            if (memoryData && memoryUpdateMessage) {
                memoryUpdateMessage.textContent = memoryData.message || '处理完成';
            }
        }
    }
    
    // 关闭记忆弹窗
    function closeMemoryModalFunc() {
        if (!memoryUpdateModal) return;
        memoryUpdateModal.setAttribute('aria-hidden', 'true');
        currentMemoryId = null;
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
    
    // 记忆更新相关事件监听
    if (memoryUpdateBtn) {
        memoryUpdateBtn.addEventListener('click', () => {
            if (conversationMessages.length === 0) {
                alert('当前对话中没有消息');
                return;
            }
            enterMemoryUpdateMode();
        });
    }
    
    if (memoryUpdateConfirmSelectionBtn) {
        memoryUpdateConfirmSelectionBtn.addEventListener('click', submitMemoryUpdate);
    }
    
    if (memoryUpdateCancelSelectionBtn) {
        memoryUpdateCancelSelectionBtn.addEventListener('click', exitMemoryUpdateMode);
    }
    
    if (memoryUpdateConfirmBtn) {
        memoryUpdateConfirmBtn.addEventListener('click', confirmMemoryUpdate);
    }
    
    if (memoryUpdateCancelBtn) {
        memoryUpdateCancelBtn.addEventListener('click', closeMemoryModalFunc);
    }
    
    if (memoryUpdateCloseBtn) {
        memoryUpdateCloseBtn.addEventListener('click', closeMemoryModalFunc);
    }
    
    if (closeMemoryModal) {
        closeMemoryModal.addEventListener('click', closeMemoryModalFunc);
    }
    
    if (memoryModalOverlay) {
        memoryModalOverlay.addEventListener('click', closeMemoryModalFunc);
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
            
            console.log('[DEBUG] 发送请求到 /api/llm/llm_answer');
            console.log('[DEBUG] 对话历史长度:', conversationMessages.length);
            
            const res = await fetch('/api/llm/llm_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question: question,
                    messages: conversationMessages  // 发送对话历史
                })
            });

            console.log('[DEBUG] 收到响应，状态:', res.status, res.statusText);
            console.log('[DEBUG] 响应头 Content-Type:', res.headers.get('Content-Type'));
            console.log('[DEBUG] 响应是否有body:', !!res.body);

            if (!res.ok) {
                const err = await res.json().catch(() => ({ error: '服务错误' }));
                console.error('[ERROR] 响应错误:', err);
                loadingIndicator.style.display = 'none';
                sendButton.disabled = false;
                addMessage('请求失败: ' + (err.error || res.statusText || '服务错误'), 'bot');
                return;
            }
            
            if (!res.body) {
                console.error('[ERROR] 响应body为空');
                loadingIndicator.style.display = 'none';
                sendButton.disabled = false;
                addMessage('响应body为空，请检查后端服务', 'bot');
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
            
            console.log('[DEBUG] 创建流式消息容器:', !!botContent);
            
            if (!botContent) {
                console.error('[ERROR] 无法创建流式消息容器');
                loadingIndicator.style.display = 'none';
                sendButton.disabled = false;
                addMessage('无法创建消息容器', 'bot');
                return;
            }

            let assistantReply = '';  // 收集完整的assistant回复
            let done = false;
            let hasReceivedData = false;
            let chunkCount = 0;
            let lastChunkTime = Date.now();
            
            // 设置超时（5分钟）
            const timeoutId = setTimeout(() => {
                if (!done) {
                    console.error('[ERROR] 流式响应超时（5分钟），强制结束');
                    console.error('[ERROR] 已接收chunk数量:', chunkCount);
                    console.error('[ERROR] 已接收数据长度:', assistantReply.length);
                    console.error('[ERROR] 最后chunk时间:', new Date(lastChunkTime).toISOString());
                    done = true;
                    try {
                        reader.cancel();
                    } catch (e) {
                        console.error('[ERROR] 取消reader失败:', e);
                    }
                    if (!hasReceivedData) {
                        addMessage('流式响应超时，未收到任何数据。请检查后端服务或网络连接。', 'bot');
                    }
                }
            }, 5 * 60 * 1000);
            
            // 设置心跳检测（30秒无数据则警告）
            const heartbeatId = setInterval(() => {
                const timeSinceLastChunk = Date.now() - lastChunkTime;
                if (!done && timeSinceLastChunk > 30000 && hasReceivedData) {
                    console.warn('[WARN] 30秒未收到新数据，但流式响应仍在进行中...');
                    console.warn('[WARN] 已接收数据:', assistantReply.substring(0, 100) + '...');
                }
            }, 10000);
            
            try {
                console.log('[DEBUG] 开始读取流式响应');
                while (!done) {
                    const readStartTime = Date.now();
                    let readResult;
                    try {
                        readResult = await reader.read();
                    } catch (readErr) {
                        console.error('[ERROR] reader.read() 抛出异常:', readErr);
                        throw readErr;
                    }
                    
                    const { value, done: streamDone } = readResult;
                    
                    if (value) {
                        hasReceivedData = true;
                        chunkCount++;
                        lastChunkTime = Date.now();
                        const chunk = decoder.decode(value, { stream: true });
                        assistantReply += chunk;  // 累积完整回复
                        
                        console.log(`[DEBUG] 收到chunk #${chunkCount}, 长度: ${chunk.length}, 总长度: ${assistantReply.length}`);
                        
                        // 确保内容被正确追加（使用安全的HTML转义）
                        if (botContent) {
                            // 转义HTML特殊字符，然后替换换行符
                            const escapedChunk = escapeHtml(chunk).replace(/\n/g, '<br>');
                            botContent.innerHTML += escapedChunk;
                            chatHistory.scrollTop = chatHistory.scrollHeight;
                        } else {
                            console.error('[ERROR] botContent 不存在，无法追加内容');
                        }
                    } else {
                        console.log('[DEBUG] 收到空chunk');
                    }
                    
                    done = streamDone;
                    
                    if (done) {
                        console.log('[DEBUG] 流式响应结束，共接收', chunkCount, '个chunk，总长度:', assistantReply.length);
                    }
                }
                
                // 清除超时和心跳
                clearTimeout(timeoutId);
                clearInterval(heartbeatId);
            } catch (readError) {
                console.error('[ERROR] 流式读取异常:', readError);
                console.error('[ERROR] 错误堆栈:', readError.stack);
                console.error('[ERROR] 已接收chunk数量:', chunkCount);
                console.error('[ERROR] 已接收数据长度:', assistantReply.length);
                console.error('[ERROR] 是否收到过数据:', hasReceivedData);
                
                clearTimeout(timeoutId);
                clearInterval(heartbeatId);
                
                if (!hasReceivedData && botContent && botContent.parentElement) {
                    botContent.parentElement.remove();
                }
                if (assistantReply.trim()) {
                    // 如果已经有部分内容，保留它
                    console.log('[INFO] 流式读取中断，但已收到部分内容，保留已接收内容');
                } else {
                    const errorMsg = `流式响应读取失败: ${readError.message || readError.toString()}`;
                    console.error('[ERROR]', errorMsg);
                    addMessage(errorMsg, 'bot');
                }
            } finally {
                // 清除超时和心跳
                clearTimeout(timeoutId);
                clearInterval(heartbeatId);
                
                console.log('[DEBUG] 清理资源，loadingIndicator将被隐藏');
                
                // 确保资源被释放
                try {
                    if (reader) {
                        reader.releaseLock();
                        console.log('[DEBUG] reader锁已释放');
                    }
                } catch (e) {
                    console.error('[ERROR] 释放reader锁失败:', e);
                }
                
                // 确保loadingIndicator被隐藏
                loadingIndicator.style.display = 'none';
                sendButton.disabled = false;
                console.log('[DEBUG] loadingIndicator已隐藏，sendButton已启用');
            }

            // 将assistant回复添加到对话历史
            if (assistantReply.trim()) {
                conversationMessages.push({"role": "assistant", "content": assistantReply.trim()});
                
                // 更新流式消息的索引（因为此时消息已经被push到conversationMessages）
                if (botContent && botContent.parentElement) {
                    const messageDiv = botContent.parentElement;
                    const correctIndex = conversationMessages.length - 1;
                    messageDiv.dataset.messageIndex = correctIndex;
                }
                
                // 保存到后端
                if (currentConversationId) {
                    await saveCurrentSessionMessages();
                    // 重新加载会话列表以更新标题（如果自动生成了）
                    await renderConversationsList();
                    updateConversationTitle();
                }
            } else {
                // 如果没有内容，移除空消息
                if (botContent && botContent.parentElement) {
                    botContent.parentElement.remove();
                }
            }
        } catch (err) {
            console.error('[ERROR] sendQuestion 异常:', err);
            console.error('[ERROR] 错误类型:', err.constructor.name);
            console.error('[ERROR] 错误消息:', err.message);
            console.error('[ERROR] 错误堆栈:', err.stack);
            
            loadingIndicator.style.display = 'none';
            sendButton.disabled = false;
            
            let errorMessage = '调用大模型失败';
            if (err.message) {
                errorMessage += ': ' + err.message;
            } else if (err.toString) {
                errorMessage += ': ' + err.toString();
            }
            errorMessage += '。请检查网络或服务状态。';
            
            addMessage(errorMessage, 'bot');
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
                .map(line => `<p>${escapeHtml(line).replace(/\n/g, '<br>')}</p>`)
                .join('');
            retrievalContent.innerHTML = html;
        } else {
            retrievalContent.innerHTML = '<p class="muted">未检索到相关信息，将基于通用知识回答。</p>';
        }
    }

    function addMessage(content, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        // 添加消息索引
        const currentIndex = conversationMessages.length;
        messageDiv.dataset.messageIndex = currentIndex;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = type === 'user' ? 'user-avatar' : 'bot-avatar';
        avatarDiv.innerHTML = type === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        // 安全地转义HTML
        const escapedContent = escapeHtml(content).replace(/\n/g, '<br>');
        contentDiv.innerHTML = `<p>${escapedContent}</p>`;

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatHistory.appendChild(messageDiv);
        
        // 如果处于记忆更新模式，添加勾选功能
        if (isMemoryUpdateMode) {
            messageDiv.classList.add('selectable');
            messageDiv.addEventListener('click', () => toggleMessageSelection(currentIndex, messageDiv));
        }
        
        return contentDiv;
    }

    function addStreamingMessage(type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        // 添加消息索引（注意：对于流式消息，此时消息还未添加到conversationMessages，所以索引会是当前长度）
        const currentIndex = conversationMessages.length;
        messageDiv.dataset.messageIndex = currentIndex;

        const avatarDiv = document.createElement('div');
        avatarDiv.className = type === 'user' ? 'user-avatar' : 'bot-avatar';
        avatarDiv.innerHTML = type === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        // 流式消息初始为空，内容会逐步追加
        contentDiv.innerHTML = '';

        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        chatHistory.appendChild(messageDiv);
        
        // 确保消息被添加到DOM后再返回
        chatHistory.scrollTop = chatHistory.scrollHeight;
        
        // 如果处于记忆更新模式，添加勾选功能
        if (isMemoryUpdateMode) {
            messageDiv.classList.add('selectable');
            messageDiv.addEventListener('click', () => toggleMessageSelection(currentIndex, messageDiv));
        }
        
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
