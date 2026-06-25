// LegalClaw 前端逻辑: 与 Python 后端(window.pywebview.api)通信并渲染聊天。
(function () {
  const $ = (id) => document.getElementById(id);
  const messages = $("messages");
  const input = $("input");
  const btnSend = $("btn-send");
  const btnStop = $("btn-stop");
  const statusBar = $("status");

  let currentAssistant = null; // 当前流式助手气泡 {el, raw}
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

  function addToolCall(name, preview) {
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
      case "assistant_delta":
        ensureAssistant().raw += evt.text;
        // 流式期间以纯文本预览, 结束再渲染 markdown
        currentAssistant.el.textContent = currentAssistant.raw;
        scrollDown();
        break;
      case "assistant_end":
        finalizeAssistant();
        break;
      case "assistant_text": {
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
