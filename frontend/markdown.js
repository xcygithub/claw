// 轻量 Markdown 渲染器(离线、无依赖)。覆盖常见语法, 满足聊天展示需要。
(function () {
  function escapeHtml(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function inline(text) {
    // 行内代码
    text = text.replace(/`([^`]+)`/g, (_, c) => `<code>${escapeHtml(c)}</code>`);
    // 粗体
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // 斜体
    text = text.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
    // 链接
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
    return text;
  }

  function render(md) {
    if (!md) return "";
    const lines = md.replace(/\r\n/g, "\n").split("\n");
    let html = "";
    let inCode = false;
    let codeBuf = [];
    let listType = null; // 'ul' | 'ol'
    let para = [];

    function flushPara() {
      if (para.length) {
        html += "<p>" + inline(escapeHtml(para.join(" "))) + "</p>";
        para = [];
      }
    }
    function closeList() {
      if (listType) {
        html += `</${listType}>`;
        listType = null;
      }
    }

    for (const raw of lines) {
      const line = raw;
      const fence = line.trim().startsWith("```");
      if (fence) {
        if (inCode) {
          html += "<pre><code>" + escapeHtml(codeBuf.join("\n")) + "</code></pre>";
          codeBuf = [];
          inCode = false;
        } else {
          flushPara();
          closeList();
          inCode = true;
        }
        continue;
      }
      if (inCode) {
        codeBuf.push(line);
        continue;
      }

      const h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) {
        flushPara();
        closeList();
        const level = h[1].length;
        html += `<h${level}>${inline(escapeHtml(h[2]))}</h${level}>`;
        continue;
      }

      const ol = line.match(/^\s*\d+\.\s+(.*)$/);
      const ul = line.match(/^\s*[-*]\s+(.*)$/);
      if (ol || ul) {
        flushPara();
        const t = ol ? "ol" : "ul";
        if (listType !== t) {
          closeList();
          listType = t;
          html += `<${t}>`;
        }
        html += "<li>" + inline(escapeHtml((ol || ul)[1])) + "</li>";
        continue;
      }

      if (line.trim() === "") {
        flushPara();
        closeList();
        continue;
      }

      para.push(line.trim());
    }

    if (inCode) html += "<pre><code>" + escapeHtml(codeBuf.join("\n")) + "</code></pre>";
    flushPara();
    closeList();
    return html;
  }

  window.renderMarkdown = render;
  window.escapeHtml = escapeHtml;
})();
