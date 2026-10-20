# -*- coding: utf-8 -*-
"""
Gradio 聊天机器人 —— DeepSeek 风格界面
=======================================
环境:  Python 3.10+, gradio 5.x / 6.x (新版 API)

运行:  ./launch.sh          (或: pip install -r requirements.txt && python app.py)
然后浏览器打开终端里打印的 URL。

界面:
  - 左侧栏: 品牌 / 新建对话 / 历史对话 / 设置入口
  - 主区域: 对话页 (气泡聊天 + 底部输入条) 与 设置页 (与 config.json 一一对应)
  - 头像、气泡、输入条、配色均按 chat.deepseek.com 风格定制 (纯 CSS, 见 CSS 常量)

配置说明:
  - config.json 保存所有配置项, 设置页保存即写回该文件。
  - llm.enabled 关闭时用内置规则回答 (无需 Key); 开启并填好 base_url/api_key/model 走真实大模型。
  - ui.theme / ui.server_port 在下次启动时生效。
"""

import json
import os

import gradio as gr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(BASE_DIR, "history.json")
AVATAR_USER = os.path.join(BASE_DIR, "assets", "avatar_user.svg")
AVATAR_AI = os.path.join(BASE_DIR, "assets", "avatar_ai.svg")

import config as config_mod
from config import CONFIG_PATH, get_config
from config import load_config, read_config, reload_config, save_config

try:
    import openai as _openai
except ImportError:
    _openai = None

THEMES = ["Soft", "Default", "Monochrome", "Glass", "Ocean", "Cyberpunk"]


# ===================== 聊天核心 =====================
def _rule_reply(message):
    """内置规则回答 (不需要任何 Key)。"""
    msg = (message or "").strip()
    rules = [
        (("你好", "您好", "hi", "hello"), "你好呀! 我是你的智能助手 👋 有什么可以帮你?"),
        (("名字", "你是谁"), "我是智能助手, 一个用 Gradio 搭出来的聊天机器人。😄"),
        (("天气",), "我没有联网查天气的能力, 建议看看手机上的天气 App 😅"),
        (("会什么", "功能"), "去左侧「设置」里填好大模型信息并启用, 我就能像真正的 AI 一样回答你了。"),
        (("bye", "再见", "拜拜"), "再见~ 随时回来找我聊天! 👋"),
    ]
    lower = msg.lower()
    for keywords, reply in rules:
        if any(k.lower() in lower for k in keywords):
            return reply
    return (f"我听到你说:「{msg}」。目前是规则模式(未启用大模型)。\n"
            "到左侧「设置」勾选启用、填好 base_url / api_key / model 并保存, 我就接入大模型了。")


def _llm_reply(message, history, cfg):
    """用 OpenAI 兼容接口调大模型 (设置页启用后生效)。"""
    llm = cfg["llm"]
    if _openai is None:
        return "⚠️ 未安装 openai 包, 请执行: pip install openai\n(也可在设置页关闭「启用大模型」继续用规则模式)"
    if not llm.get("api_key"):
        return "⚠️ 已启用大模型但没填 API Key。请到左侧「设置」里填写并保存。"

    try:
        client = _openai.OpenAI(base_url=llm["base_url"], api_key=llm["api_key"])
        messages = [{"role": "system", "content": llm["system_prompt"]}]
        messages += [{"role": m["role"], "content": m["content"]} for m in (history or [])]
        messages.append({"role": "user", "content": message})

        resp = client.chat.completions.create(
            model=llm["model"],
            messages=messages,
            temperature=float(llm["temperature"]),
            max_tokens=int(llm["max_tokens"]),
        )
        return resp.choices[0].message.content or "(空回复)"
    except Exception as exc:  # 网络/鉴权/限流等一律给出友好提示
        return f"⚠️ 调用大模型失败: {exc}\n请检查设置里的 base_url / api_key / model 是否正确。"


def bot_reply(message, history):
    """对外入口: 按当前配置决定走规则还是大模型。"""
    cfg = get_config()
    if cfg["llm"]["enabled"]:
        return _llm_reply(message, history, cfg)
    return _rule_reply(message)


def _text(content):
    """gradio 6 的 Chatbot 会把 content 规范成「分段列表」,
    统一还原成纯文本, 保证 LLM 与历史记录里都是字符串。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                parts.append(p.get("text") or p.get("content") or "")
            else:
                parts.append(str(p))
        return "\n".join(parts)
    return str(content)


# ===================== 聊天记录持久化 =====================
def _load_history():
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                items = json.load(f)
                return items if isinstance(items, list) else []
        except Exception:
            return []
    return []


def _save_history(items):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _chat_title(messages):
    for m in (messages or []):
        if m.get("role") == "user" and m.get("content"):
            return _text(m["content"]).replace("\n", " ")[:20]
    return "新对话"


def _history_titles():
    return [h["title"] for h in _load_history()]


# ===================== 样式 (DeepSeek 风格) =====================
CSS = """
:root{
  --ds-accent:#4d6bfe; --ds-accent-hover:#3b59ec; --ds-accent-soft:#eef1ff;
  --ds-bg:#f5f6f8; --ds-chat-bg:#ffffff;
  --ds-text:#1f2329; --ds-text-2:#8a8f99; --ds-border:#ececf0; --ds-sidebar-bg:#fafbfd;
}
html,body{background:var(--ds-bg);}
.gradio-container{
  max-width:100% !important; margin:0 !important; padding:0 !important;
  background:var(--ds-bg); color:var(--ds-text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
}
.footer{display:none !important;}

/* 去掉 gradio 默认的居中留白 / 内边距, 让应用铺满视口 */
.main{max-width:none !important; margin:0 !important; padding:0 !important;}
.wrap{padding:0 !important;}

/* ---------- 主体布局 ---------- */
.ds-root{height:100vh; display:flex;}
.ds-sidebar{
  width:252px; min-width:252px; height:100vh;
  background:var(--ds-sidebar-bg); border-right:1px solid var(--ds-border);
  padding:20px 14px 14px; overflow-y:auto;
  display:flex; flex-direction:column;
}
.ds-area{flex:1 1 auto; min-width:0;}

/* ---------- 侧栏 ---------- */
.ds-brand{display:flex; align-items:center; gap:11px; padding:2px 6px 14px;}
.ds-brand .logo{
  width:36px; height:36px; border-radius:10px; flex:0 0 auto;
  background:linear-gradient(135deg,#7c93ff,#4d6bfe);
  display:flex; align-items:center; justify-content:center; color:#fff; font-size:19px;
}
.ds-brand .name{font-size:16px; font-weight:600; color:var(--ds-text);}
.ds-brand .sub{font-size:11px; color:var(--ds-text-2); margin-top:1px;}

.ds-newchat{
  width:100% !important; border-radius:10px !important;
  background:#fff !important; border:1px solid var(--ds-border) !important;
  color:var(--ds-text) !important; font-weight:500 !important;
  padding:9px 12px !important; margin:0 !important; box-shadow:none !important;
  justify-content:flex-start !important; display:flex; align-items:center; gap:6px;
}
.ds-newchat:hover{background:var(--ds-accent-soft)!important; border-color:#c9d3ff !important; color:var(--ds-accent)!important;}

.ds-side-title{font-size:12px; color:var(--ds-text-2); margin:18px 6px 8px !important; letter-spacing:.3px;}
.ds-scroll{margin-top:2px;}
.ds-sidebar .btn-group{display:flex; gap:8px; margin-top:8px;}
.ds-sidebar .btn-group button{
  flex:1 !important; border-radius:8px !important; border:1px solid var(--ds-border) !important;
  background:#fff !important; color:var(--ds-text-2) !important;
  font-size:12px !important; padding:6px 0 !important; box-shadow:none !important;
}
.ds-sidebar .btn-group button:hover{color:var(--ds-accent)!important; border-color:#c9d3ff!important;}

.ds-sidebar-bottom{margin-top:auto; padding-top:16px;}
.ds-status-line{font-size:12px; color:var(--ds-text-2); display:flex; align-items:center; gap:6px; padding:4px 6px;}
.online-dot{width:8px; height:8px; border-radius:50%; background:#34c759; display:inline-block;}
.ds-settings{
  width:100% !important; border-radius:10px !important; border:1px solid var(--ds-border) !important;
  background:#fff !important; color:var(--ds-text) !important;
  padding:8px 12px !important; margin-top:10px !important; box-shadow:none !important;
  justify-content:flex-start !important; display:flex; align-items:center; gap:6px;
}.ds-settings:hover{background:var(--ds-accent-soft)!important; color:var(--ds-accent)!important; border-color:#c9d3ff!important;}

/* ---------- 聊天页 ---------- */
.ds-page-chat{
  height:100vh; display:flex; flex-direction:column;
  background:var(--ds-chat-bg);
}
.ds-topbar{
  flex:0 0 auto; padding:10px 20px; border-bottom:1px solid var(--ds-border);
  display:flex; align-items:center; justify-content:center;
}
.ds-model-pill{
  font-size:13px; color:var(--ds-text-2); background:#fff;
  border:1px solid var(--ds-border); border-radius:999px; padding:5px 14px;
  display:inline-flex; align-items:center; gap:7px;
}
/* gradio 6 的 Chatbot 消息结构: .message.user/.bot > .message-content > span.md */
#ds-chatbot{
  flex:1 1 auto; min-height:0; padding:0;
  height:calc(100vh - 186px) !important; min-height:240px !important;
  border:none !important; box-shadow:none !important; background:transparent !important;
}
#ds-chatbot .chatbot{
  flex:1 1 auto;
  border:none !important; background:transparent !important; box-shadow:none !important;
  margin:0 !important; height:100% !important;
}
#ds-chatbot .message{margin:0 !important; padding:0 0 14px !important;}
#ds-chatbot .message .md{font-size:15px !important; line-height:1.7 !important;}
#ds-chatbot .md p{margin:0 0 6px !important;}
#ds-chatbot .md p:last-child{margin:0 !important;}
/* 用户消息: 右侧蓝色气泡 */
#ds-chatbot .message.user{justify-content:flex-end !important;}
#ds-chatbot .message.user .message-content{
  display:flex; justify-content:flex-end; margin-left:auto; max-width:80%;
}
#ds-chatbot .message.user .md{
  background:var(--ds-accent) !important; color:#fff !important;
  border-radius:18px 18px 4px 18px !important;
  padding:9px 14px !important; font-size:15px !important; line-height:1.6 !important;
}
/* 助手消息: 左侧常规文本 */
#ds-chatbot .message.bot{justify-content:flex-start !important;}
#ds-chatbot .message.bot .message-content{max-width:92%;}
#ds-chatbot .message.bot .md{color:var(--ds-text) !important; padding:2px 0 !important;}
#ds-chatbot .avatar-container{width:30px; height:30px; flex:0 0 auto; align-self:flex-start; margin:2px 10px 0 0;}
#ds-chatbot .avatar-container img{width:30px; height:30px; border-radius:9px;}

/* ---------- 输入条 ---------- */
.ds-composer{
  flex:0 0 auto; margin:0 24px 6px !important;
  display:flex !important; align-items:flex-end !important; gap:8px !important;
  background:#f4f5f8 !important; border:1px solid #e9eaef !important;
  border-radius:22px !important; padding:8px 8px 8px 18px !important;
  box-shadow:0 1px 2px rgba(0,0,0,.04) !important;
}
.ds-composer .block{box-shadow:none !important; border:none !important; background:transparent !important; margin:0 !important;}
.ds-input textarea{
  border:none !important; box-shadow:none !important; background:transparent !important;
  font-size:15px !important; color:var(--ds-text) !important; padding:6px 2px !important;
  min-height:22px !important; line-height:1.5 !important; resize:none !important;
}
.ds-input textarea:focus{box-shadow:none !important; border:none !important;}
.ds-input .wrap{border:none !important; box-shadow:none !important; background:transparent !important;}
.ds-send{
  width:38px !important; height:38px !important; min-width:38px !important; padding:0 !important;
  border-radius:50% !important; background:var(--ds-accent) !important; color:#fff !important;
  font-size:18px !important; border:none !important; box-shadow:none !important;
  display:flex; align-items:center; justify-content:center; flex:0 0 auto !important;
}
.ds-send:hover{background:var(--ds-accent-hover) !important;}
.ds-send:disabled{background:#aab4f8 !important;}

.ds-hint{flex:0 0 auto; text-align:center; font-size:11px; color:#aaadb8; padding-bottom:12px;}

/* ---------- 设置页 ---------- */
.ds-page-config{height:100vh; overflow-y:auto; background:var(--ds-chat-bg);}
.ds-config-inner{max-width:880px; margin:0 auto; padding:24px 32px 48px;}
.ds-config-inner h1{font-size:20px; font-weight:600; margin:6px 0 4px;}
.ds-config-inner .desc{color:var(--ds-text-2); font-size:13px; margin-bottom:14px;}
.ds-back{
  border-radius:999px !important; border:1px solid var(--ds-border) !important;
  background:#fff !important; color:var(--ds-text) !important; box-shadow:none !important;
  padding:6px 14px !important; font-size:13px !important; width:fit-content !important;
}
.ds-back:hover{border-color:#c9d3ff !important; color:var(--ds-accent) !important;}
.ds-form-card{
  background:#f9fafc; border:1px solid var(--ds-border); border-radius:16px;
  padding:20px 22px; margin-bottom:18px;
}
.ds-form-card h3{font-size:13px; color:var(--ds-text-2); margin:0 0 14px; font-weight:600; letter-spacing:.3px;}
.ds-status-box textarea{font-size:12px !important;}
"""


# ===================== 界面 =====================
def build_blocks():
    with gr.Blocks(title="智能助手 · Gradio Chat") as demo:
        with gr.Row(elem_classes="ds-root", equal_height=False):
            # ---------- 左侧栏 ----------
            with gr.Column(elem_classes="ds-sidebar", scale=0, min_width=252):
                gr.HTML(
                    '<div class="ds-brand">'
                    '<div class="logo">✨</div>'
                    '<div><div class="name">智能助手</div><div class="sub">Gradio Chat</div></div>'
                    "</div>"
                )
                new_chat_btn = gr.Button("＋ 新建对话", elem_classes="ds-newchat")
                gr.Markdown("历史对话", elem_classes="ds-side-title")
                history_dd = gr.Dropdown(
                    label="", choices=_history_titles(), value=None,
                    interactive=True, elem_classes="ds-scroll",
                    info="选择一条历史对话载入",
                )
                with gr.Row(elem_classes="btn-group"):
                    clear_hist_btn = gr.Button("清空历史", size="sm")

                with gr.Column(elem_classes="ds-sidebar-bottom"):
                    gr.HTML(
                        '<div class="ds-status-line"><span class="online-dot"></span>在线</div>'
                    )
                    settings_btn = gr.Button("⚙️ 设置", elem_classes="ds-settings")

            # ---------- 主区域 ----------
            with gr.Column(elem_classes="ds-area", scale=1):
                # ---- 页面 1: 对话 ----
                with gr.Column(visible=True, elem_classes="ds-page-chat") as chat_page:
                    with gr.Row(elem_classes="ds-topbar"):
                        gr.HTML('<span class="ds-model-pill"><span class="online-dot"></span>模型: 按配置</span>')

                    chatbot = gr.Chatbot(
                        elem_id="ds-chatbot",
                        placeholder="开始和智能助手对话…",
                        avatar_images=[AVATAR_USER, AVATAR_AI],
                        show_label=False,
                        container=False,
                        layout="bubble",
                    )

                    with gr.Row(elem_classes="ds-composer"):
                        textbox = gr.Textbox(
                            placeholder="输入消息… (Enter 发送 / Shift+Enter 换行)",
                            show_label=False,
                            elem_classes="ds-input",
                            scale=10,
                            max_lines=6,
                            autofocus=True,
                        )
                        send_btn = gr.Button("↑", elem_classes="ds-send", scale=0)
                    gr.Markdown("AI 生成的内容仅供参考", elem_classes="ds-hint")

                # ---- 页面 2: 设置 (与 config.json 一一对应) ----
                with gr.Column(visible=False, elem_classes="ds-page-config") as config_page:
                    with gr.Column(elem_classes="ds-config-inner"):
                        with gr.Row(elem_classes="ds-back"):
                            back_btn = gr.Button("← 返回对话")
                        gr.HTML(
                            "<h1>⚙️ 设置</h1>"
                            f'<div class="desc">配置项与 <code>{CONFIG_PATH}</code> 一一对应，'
                            "保存即写回文件；也可直接编辑文件后点「重载配置」。</div>"
                        )
                        with gr.Column(elem_classes="ds-form-card"):
                            gr.HTML("<h3>🤖 大模型 (LLM)</h3>")
                            llm_enabled = gr.Checkbox(label="启用大模型 (llm.enabled)", value=False)
                            with gr.Row():
                                llm_base_url = gr.Textbox(
                                    label="接口地址 Base URL (llm.base_url)",
                                    placeholder="https://api.deepseek.com/v1",
                                )
                                llm_model = gr.Textbox(label="模型名 (llm.model)", placeholder="deepseek-chat")
                            llm_api_key = gr.Textbox(
                                label="API Key (llm.api_key)", type="password",
                                placeholder="sk-xxxxxxxxxxxx",
                            )
                            with gr.Row():
                                llm_temp = gr.Slider(
                                    label="温度 (llm.temperature)", minimum=0, maximum=2,
                                    step=0.1, value=0.7,
                                )
                                llm_max_tokens = gr.Slider(
                                    label="最大 Tokens (llm.max_tokens)", minimum=64, maximum=8192,
                                    step=64, value=1024,
                                )
                            llm_system_prompt = gr.Textbox(
                                label="系统提示词 (llm.system_prompt)", lines=3,
                                placeholder="你是一个乐于助人的智能助手…",
                            )
                        with gr.Column(elem_classes="ds-form-card"):
                            gr.HTML("<h3>🎨 界面 (UI)</h3>")
                            with gr.Row():
                                ui_theme = gr.Dropdown(
                                    label="主题 (ui.theme)", choices=THEMES, value=THEMES[0],
                                )
                                ui_port = gr.Number(label="启动端口 (ui.server_port)", value=7860, precision=0)
                        with gr.Row():
                            save_btn = gr.Button("💾 保存配置", variant="primary")
                            reload_btn = gr.Button("🔄 重载配置")
                        status = gr.Textbox(label="状态", interactive=False, lines=3, elem_classes="ds-status-box")

        # ===================== 事件 =====================
        # --- 页面切换 ---
        def show_config():
            return gr.update(visible=False), gr.update(visible=True)

        def show_chat():
            return gr.update(visible=True), gr.update(visible=False)

        settings_btn.click(show_config, outputs=[chat_page, config_page])
        back_btn.click(show_chat, outputs=[chat_page, config_page])

        # --- 聊天 ---
        def respond(message, history):
            # 先把 gradio 规范化过的历史统一成纯字符串, 再交给 bot_reply
            history = [{"role": m["role"], "content": _text(m.get("content"))}
                       for m in (history or [])]
            reply = bot_reply(message, history)
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            return "", history

        send_btn.click(respond, inputs=[textbox, chatbot], outputs=[textbox, chatbot])
        textbox.submit(respond, inputs=[textbox, chatbot], outputs=[textbox, chatbot])

        # --- 历史对话 ---
        def new_chat(history):
            hist = _load_history()
            msgs = list(history or [])
            if msgs:
                hist.insert(0, {"title": _chat_title(msgs), "messages": msgs})
                _save_history(hist)
            return "", [], gr.update(choices=_history_titles(), value=None)

        def open_history(title):
            for h in _load_history():
                if h["title"] == title:
                    return list(h["messages"])
            return []

        def clear_history():
            _save_history([])
            return gr.update(choices=[], value=None)

        new_chat_btn.click(new_chat, inputs=[chatbot], outputs=[textbox, chatbot, history_dd])
        history_dd.change(open_history, inputs=[history_dd], outputs=[chatbot])
        clear_hist_btn.click(clear_history, outputs=[history_dd])

        # --- 配置 ---
        def _to_list(cfg):
            """把配置按固定顺序铺平成表单值列表。"""
            llm, ui = cfg["llm"], cfg["ui"]
            theme = ui["theme"] if ui["theme"] in THEMES else THEMES[0]
            return [
                bool(llm["enabled"]), llm["base_url"], llm["api_key"], llm["model"],
                float(llm["temperature"]), int(llm["max_tokens"]), llm["system_prompt"],
                theme, int(ui["server_port"]),
            ]

        def do_save(enabled, base_url, api_key, model, temperature,
                    max_tokens, system_prompt, theme, port):
            # 以磁盘上的最新配置为基准合并, 避免覆盖其它字段 (如手改的文件值)
            cfg = read_config()
            cfg["llm"].update(
                enabled=bool(enabled), base_url=base_url.strip(), api_key=(api_key or "").strip(),
                model=model.strip(), temperature=float(temperature),
                max_tokens=int(max_tokens), system_prompt=system_prompt,
            )
            cfg["ui"].update(theme=theme, server_port=int(port))
            try:
                path = save_config(cfg)
                reload_config()  # 让运行期配置立即同步
                return f"✅ 已保存到 {path}\nllm.enabled={cfg['llm']['enabled']}, model={cfg['llm']['model']}"
            except Exception as exc:
                return f"❌ 保存失败: {exc}"

        def do_reload():
            cfg = load_config()
            # gradio 要求返回值个数 == 输出组件个数, 必须平铺成 10 个值
            return [*_to_list(cfg), "🔄 已从配置文件重新加载."]

        save_btn.click(
            do_save,
            inputs=[llm_enabled, llm_base_url, llm_api_key, llm_model,
                    llm_temp, llm_max_tokens, llm_system_prompt, ui_theme, ui_port],
            outputs=status,
        )
        reload_btn.click(
            do_reload,
            outputs=[llm_enabled, llm_base_url, llm_api_key, llm_model,
                     llm_temp, llm_max_tokens, llm_system_prompt, ui_theme,
                     ui_port, status],
        )
        # 页面加载时把表单填成当前配置文件里的值 (与文件一一对应)
        demo.load(
            do_reload,
            outputs=[llm_enabled, llm_base_url, llm_api_key, llm_model,
                     llm_temp, llm_max_tokens, llm_system_prompt, ui_theme,
                     ui_port, status],
        )

    return demo


# ===================== 入口 =====================
def main():
    cfg = load_config()

    # 从配置文件里的端口开始找空闲端口 (被占用时自动顺延)
    import socket
    start = int(cfg["ui"].get("server_port", 7860))
    port = start
    for candidate in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", candidate))
                port = candidate
                break
            except OSError:
                continue

    theme_name = cfg["ui"].get("theme", "Soft")
    theme = getattr(gr.themes, theme_name, gr.themes.Soft)()

    print(f"💬 打开浏览器访问: http://127.0.0.1:{port}")
    print(f"📄 配置已从 {CONFIG_PATH} 载入: "
          f"model={cfg['llm']['model']}, theme={cfg['ui'].get('theme')}, "
          f"enabled={cfg['llm']['enabled']} (侧栏「设置」在线修改后保存即生效)")

    demo = build_blocks()
    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=port,
        theme=theme,
        css=CSS,       # 自定义样式 (DeepSeek 风格)
        share=False,   # 需要外网临时访问时改成 share=True
    )


if __name__ == "__main__":
    main()
