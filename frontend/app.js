// LegalClaw 前端逻辑: 与 Python 后端(window.pywebview.api)通信并渲染聊天。
(function () {
  const $ = (id) => document.getElementById(id);
  const messages = $("messages");
  const input = $("input");
  const btnSend = $("btn-send");
  const btnStop = $("btn-stop");
  const statusBar = $("status");

  let currentAssistant = null; // 当前流式助手气泡 {el, raw}
  let currentReasoning = null; // 当前流式思考面板 {el, body, raw}
  let busy = false;

  function clearEmptyHint() {
    const hint = messages.querySelector(".empty-hint");
    if (hint) hint.remove();
  }

  function scrollDown() {
    messages.scrollTop = messages.scrollHeight;
  }

  function addUser(text) {
    clearEmptyHint();
    const wrap = document.createElement("div");
    wrap.className = "msg user";
    wrap.innerHTML = `<div class="role">你</div><div class="bubble"></div>`;
    wrap.querySelector(".bubble").textContent = text;
    messages.appendChild(wrap);
    scrollDown();
  }

  function ensureAssistant() {
    if (currentAssistant) return currentAssistant;
    clearEmptyHint();
    const wrap = document.createElement("div");
    wrap.className = "msg assistant";
    wrap.innerHTML = `<div class="role">LegalClaw</div><div class="bubble"></div>`;
    messages.appendChild(wrap);
    currentAssistant = { el: wrap.querySelector(".bubble"), raw: "" };
    scrollDown();
    return currentAssistant;
  }

  function finalizeAssistant() {
    if (currentAssistant) {
      currentAssistant.el.innerHTML = window.renderMarkdown(currentAssistant.raw);
      currentAssistant = null;
      scrollDown();
    }
  }

  function ensureReasoning() {
    if (currentReasoning) return currentReasoning;
    clearEmptyHint();
    const wrap = document.createElement("div");
    wrap.className = "reasoning";
    wrap.innerHTML = `
      <div class="reasoning-head">
        <span class="reasoning-icon">✻</span>
        <span class="reasoning-title">思考中…</span>
      </div>
      <pre class="reasoning-body"></pre>`;
    wrap.querySelector(".reasoning-head").addEventListener("click", () =>
      wrap.classList.toggle("collapsed")
    );
    messages.appendChild(wrap);
    currentReasoning = { el: wrap, body: wrap.querySelector(".reasoning-body"), raw: "" };
    scrollDown();
    return currentReasoning;
  }

  function finalizeReasoning() {
    if (currentReasoning) {
      const count = currentReasoning.raw.length;
      currentReasoning.el.querySelector(".reasoning-title").textContent =
        count ? `已完成思考 (${count} 字)` : "思考中…";
      currentReasoning.el.classList.add("collapsed", "done");
      currentReasoning = null;
    }
  }

  function addToolCall(name, preview) {
    finalizeReasoning();
    finalizeAssistant();
    const el = document.createElement("div");
    el.className = "tool collapsed";
    el.dataset.name = name;
    el.innerHTML = `
      <div class="tool-head">
        <span class="tool-name">${window.escapeHtml(name)}</span>
        <span class="tool-preview">${window.escapeHtml(preview)}</span>
      </div>
      <pre class="tool-body"></pre>`;
    el.querySelector(".tool-head").addEventListener("click", () =>
      el.classList.toggle("collapsed")
    );
    messages.appendChild(el);
    scrollDown();
    return el;
  }

  function addToolResult(name, result) {
    // 找到最近一个同名、还没填结果的工具块
    const tools = messages.querySelectorAll(`.tool[data-name="${CSS.escape(name)}"]`);
    let target = null;
    for (let i = tools.length - 1; i >= 0; i--) {
      if (!tools[i].dataset.done) { target = tools[i]; break; }
    }
    if (name === "write_todos") {
      renderTodos(result);
    }
    if (!target) return;
    target.dataset.done = "1";
    target.querySelector(".tool-body").textContent = result;
    scrollDown();
  }

  function renderTodos(text) {
    const body = text.replace(/^任务清单已更新:\n?/, "");
    const el = document.createElement("div");
    el.className = "todos";
    el.innerHTML = `<div class="todos-title">任务清单</div><pre></pre>`;
    el.querySelector("pre").textContent = body;
    messages.appendChild(el);
    scrollDown();
  }

  function setStatus(msg, isErr) {
    if (!msg) {
      statusBar.classList.add("hidden");
      return;
    }
    statusBar.textContent = msg;
    statusBar.classList.toggle("err", !!isErr);
    statusBar.classList.remove("hidden");
  }

  function setBusy(b) {
    busy = b;
    btnSend.disabled = b;
    btnStop.classList.toggle("hidden", !b);
  }

  // 后端事件入口
  window.__clawEvent = function (evt) {
    switch (evt.type) {
      case "reasoning_delta": {
        const r = ensureReasoning();
        r.raw += evt.text;
        r.body.textContent = r.raw;
        scrollDown();
        break;
      }
      case "assistant_delta":
        finalizeReasoning();
        ensureAssistant().raw += evt.text;
        // 流式期间以纯文本预览, 结束再渲染 markdown
        currentAssistant.el.textContent = currentAssistant.raw;
        scrollDown();
        break;
      case "assistant_end":
        finalizeReasoning();
        finalizeAssistant();
        break;
      case "assistant_text": {
        finalizeReasoning();
        const a = ensureAssistant();
        a.raw = evt.text;
        finalizeAssistant();
        break;
      }
      case "tool_call":
        addToolCall(evt.name, evt.preview);
        break;
      case "tool_result":
        addToolResult(evt.name, evt.result);
        break;
      case "info":
        setStatus(evt.message, false);
        break;
      case "warning":
        setStatus(evt.message, false);
        break;
      case "error":
        setStatus(evt.message, true);
        break;
      case "approval_request":
        showApproval(evt);
        break;
      case "done":
        finalizeReasoning();
        finalizeAssistant();
        setBusy(false);
        setStatus("");
        break;
    }
  };

  // 发送
  function send() {
    const text = input.value.trim();
    if (!text || busy) return;
    addUser(text);
    input.value = "";
    autoResize();
    setBusy(true);
    setStatus("思考中…");
    window.pywebview.api.send_message(text);
  }

  btnSend.addEventListener("click", send);
  btnStop.addEventListener("click", () => {
    window.pywebview.api.stop();
    setStatus("正在停止…");
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }
  input.addEventListener("input", autoResize);

  // 清空
  $("btn-clear").addEventListener("click", () => {
    window.pywebview.api.clear();
    messages.innerHTML =
      '<div class="empty-hint"><h2>对话已清空</h2><p>输入新任务继续。</p></div>';
  });

  // 确认弹窗
  let approvalId = null;
  function showApproval(evt) {
    approvalId = evt.id;
    const overlay = $("approval-overlay");
    const modal = overlay.querySelector(".modal");
    $("approval-title").textContent = evt.dangerous ? "危险操作 — 需要确认" : "需要确认";
    $("approval-preview").textContent = evt.preview;
    modal.classList.toggle("danger", !!evt.dangerous);
    $("approval-all").classList.toggle("hidden", !!evt.dangerous);
    overlay.classList.remove("hidden");
  }
  function resolveApproval(answer) {
    $("approval-overlay").classList.add("hidden");
    window.pywebview.api.resolve_approval(approvalId, answer);
  }
  $("approval-yes").addEventListener("click", () => resolveApproval("y"));
  $("approval-no").addEventListener("click", () => resolveApproval("n"));
  $("approval-all").addEventListener("click", () => resolveApproval("a"));

  // 设置弹窗
  const settingsOverlay = $("settings-overlay");
  $("btn-settings").addEventListener("click", async () => {
    const cfg = await window.pywebview.api.get_config();
    $("cfg-model").value = cfg.model || "";
    $("cfg-base").value = cfg.api_base || "";
    $("cfg-key").value = "";
    $("cfg-auto").checked = !!cfg.auto_approve;
    $("cfg-key-hint").textContent = cfg.has_api_key
      ? "已保存密钥(留空则保持不变)"
      : "尚未设置密钥";
    settingsOverlay.classList.remove("hidden");
  });
  $("settings-cancel").addEventListener("click", () =>
    settingsOverlay.classList.add("hidden")
  );
  $("settings-save").addEventListener("click", async () => {
    const cfg = await window.pywebview.api.save_config(
      $("cfg-model").value.trim(),
      $("cfg-base").value.trim(),
      $("cfg-key").value,
      $("cfg-auto").checked
    );
    settingsOverlay.classList.add("hidden");
    refreshModelBadge(cfg.model);
  });

  function refreshModelBadge(model) {
    $("model-badge").textContent = model || "";
  }

  // 记忆管理弹窗
  const memoryOverlay = $("memory-overlay");
  const memoryList = $("memory-list");
  const sessionList = $("session-list");

  function debounce(fn, ms) {
    let timer = null;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }

  function renderMemoryEntries(entries) {
    if (!entries || !entries.length) {
      memoryList.innerHTML = '<div class="memory-empty">暂无记忆</div>';
      return;
    }
    memoryList.innerHTML = "";
    entries.forEach((entry) => {
      const row = document.createElement("div");
      row.className = "memory-item";
      const tagsHtml = entry.tags && entry.tags.length
        ? `<div class="memory-tags">${entry.tags.map((t) => "#" + window.escapeHtml(t)).join(" ")}</div>`
        : "";
      row.innerHTML = `
        <div class="memory-item-head">
          <span class="memory-scope ${entry.scope}">${entry.scope === "global" ? "全局" : "项目"}</span>
          <span class="memory-section">${window.escapeHtml(entry.section)}</span>
          <span class="memory-importance imp-${entry.importance}">${entry.importance}</span>
          ${entry.source === "auto" ? '<span class="memory-auto">自动提取</span>' : ""}
          <span class="memory-item-actions">
            <button class="mini-btn memory-edit-btn">编辑</button>
            <button class="mini-btn memory-delete-btn">删除</button>
          </span>
        </div>
        <div class="memory-content">${window.escapeHtml(entry.content)}</div>
        ${tagsHtml}
      `;
      row.querySelector(".memory-delete-btn").addEventListener("click", async () => {
        if (!confirm("确认删除这条记忆?")) return;
        await window.pywebview.api.delete_memory_entry(entry.id);
        reloadMemoryList();
      });
      row.querySelector(".memory-edit-btn").addEventListener("click", () =>
        startEditMemoryEntry(row, entry)
      );
      memoryList.appendChild(row);
    });
  }

  function startEditMemoryEntry(row, entry) {
    const contentEl = row.querySelector(".memory-content");
    contentEl.innerHTML = "";
    const textarea = document.createElement("textarea");
    textarea.className = "memory-edit-input";
    textarea.value = entry.content;
    const saveBtn = document.createElement("button");
    saveBtn.className = "mini-btn btn-primary";
    saveBtn.textContent = "保存";
    saveBtn.addEventListener("click", async () => {
      await window.pywebview.api.update_memory_entry(
        entry.id,
        textarea.value.trim(),
        "",
        [],
        ""
      );
      reloadMemoryList();
    });
    contentEl.appendChild(textarea);
    contentEl.appendChild(saveBtn);
    textarea.focus();
  }

  async function reloadMemoryList() {
    const query = $("memory-search").value.trim();
    const scope = $("memory-scope-filter").value;
    try {
      const entries = query
        ? await window.pywebview.api.search_memory(query, scope, 50)
        : await window.pywebview.api.list_memory(scope);
      renderMemoryEntries(entries);
    } catch (e) {
      memoryList.innerHTML = `<div class="memory-empty">加载失败: ${window.escapeHtml(String(e))}</div>`;
    }
  }

  $("memory-search").addEventListener("input", debounce(reloadMemoryList, 250));
  $("memory-scope-filter").addEventListener("change", reloadMemoryList);

  $("memory-add-btn").addEventListener("click", async () => {
    const content = $("memory-add-content").value.trim();
    if (!content) return;
    const section = $("memory-add-section").value.trim();
    const scope = $("memory-add-scope").value;
    const importance = $("memory-add-importance").value;
    await window.pywebview.api.add_memory_entry(content, section, [], importance, scope);
    $("memory-add-content").value = "";
    $("memory-add-section").value = "";
    reloadMemoryList();
  });

  async function renderSessions() {
    let sessions = [];
    try {
      sessions = await window.pywebview.api.list_sessions();
    } catch (e) {
      sessionList.innerHTML = `<div class="memory-empty">加载失败: ${window.escapeHtml(String(e))}</div>`;
      return;
    }
    if (!sessions.length) {
      sessionList.innerHTML = '<div class="memory-empty">暂无历史会话</div>';
      return;
    }
    sessionList.innerHTML = "";
    sessions.forEach((s) => {
      const row = document.createElement("div");
      row.className = "session-item";
      const ts = s.updated_at ? new Date(s.updated_at * 1000).toLocaleString() : "";
      row.innerHTML = `
        <div class="session-meta">
          <div class="session-time">${window.escapeHtml(ts)}</div>
          <div class="session-preview">${window.escapeHtml(s.preview || "(无预览)")}</div>
        </div>
        <button class="mini-btn btn-primary session-resume-btn">恢复</button>
      `;
      row.querySelector(".session-resume-btn").addEventListener("click", async () => {
        await window.pywebview.api.resume_session(s.id);
        memoryOverlay.classList.add("hidden");
        messages.innerHTML =
          '<div class="empty-hint"><h2>已恢复历史会话</h2><p>可以继续上次的对话。</p></div>';
        setStatus("已恢复历史会话");
      });
      sessionList.appendChild(row);
    });
  }

  function switchMemoryTab(tab) {
    $("memory-tab-entries").classList.toggle("active", tab === "entries");
    $("memory-tab-sessions").classList.toggle("active", tab === "sessions");
    $("memory-panel-entries").classList.toggle("hidden", tab !== "entries");
    $("memory-panel-sessions").classList.toggle("hidden", tab !== "sessions");
    if (tab === "sessions") renderSessions();
  }
  $("memory-tab-entries").addEventListener("click", () => switchMemoryTab("entries"));
  $("memory-tab-sessions").addEventListener("click", () => switchMemoryTab("sessions"));

  $("btn-memory").addEventListener("click", () => {
    memoryOverlay.classList.remove("hidden");
    switchMemoryTab("entries");
    reloadMemoryList();
  });
  $("memory-close").addEventListener("click", () => memoryOverlay.classList.add("hidden"));

  // 启动: 等待 pywebview 就绪
  window.addEventListener("pywebviewready", async () => {
    try {
      const info = await window.pywebview.api.app_info();
      $("version").textContent = "v" + info.version;
      const cfg = await window.pywebview.api.get_config();
      refreshModelBadge(cfg.model);
    } catch (e) {
      setStatus("初始化失败: " + e, true);
    }
  });

  autoResize();
})();
