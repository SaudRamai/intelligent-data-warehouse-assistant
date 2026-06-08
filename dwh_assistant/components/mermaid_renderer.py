import streamlit as st
import streamlit.components.v1 as components
from dwh_assistant.utils.parser import clean_mermaid_code, detect_truncation

import os

@st.cache_data
def get_js_libraries():
    base_dir = os.path.dirname(__file__)
    mermaid_path = os.path.join(base_dir, 'static', 'mermaid.min.js')
    pan_zoom_path = os.path.join(base_dir, 'static', 'svg-pan-zoom.min.js')
    
    with open(mermaid_path, 'r', encoding='utf-8') as f:
        mermaid_js = f.read()
        
    with open(pan_zoom_path, 'r', encoding='utf-8') as f:
        pan_zoom_js = f.read()
        
    return mermaid_js, pan_zoom_js

def render_mermaid(code: str, height: int = 500, node_layers: dict = None):
    """Renders Mermaid.js code natively using an HTML component with offline JS for maximum reliability."""
    print(f"\n[DWH LOG] render_mermaid invoked. Raw code length: {len(code) if code else 0}")
    
    if not code or code.strip() == "":
        print("[DWH LOG] No code provided to render_mermaid.")
        return
    
    if detect_truncation(code):
        st.warning(
            "**Diagram may be incomplete.** The AI response was likely cut off due to response "
            "size limits. The diagram below shows what could be rendered. To get a full diagram, "
            "try: reducing schema complexity, splitting into fewer tables, or regenerating."
        )
        print("[DWH LOG] Truncation detected in Mermaid output.")

    code = clean_mermaid_code(code)
    
    try:
        mermaid_js, pan_zoom_js = get_js_libraries()
    except Exception as e:
        st.error(f"Failed to load local JS libraries: {e}")
        return
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script>{pan_zoom_js}</script>
        <script>{mermaid_js}</script>
        <script>
            mermaid.initialize({{
                startOnLoad: false,
                theme: 'default',
                securityLevel: 'loose'
            }});
            
            function renderDiagram() {{
                const graphDefinition = document.getElementById('diagramCode').textContent;
                const container = document.getElementById('diagramContainer');
                try {{
                    mermaid.mermaidAPI.render('mermaid-svg', graphDefinition, function(svgCode) {{
                        container.innerHTML = svgCode;
                        
                        // Update download link
                        const downloadBtn = document.getElementById('downloadBtn');
                        const encodedData = encodeURIComponent(svgCode);
                        downloadBtn.href = "data:image/svg+xml;charset=utf-8," + encodedData;
                        
                        const svgElement = container.querySelector('svg');
                        if(svgElement) {{
                            svgElement.style.width = '100%';
                            svgElement.style.height = '100%';
                            svgElement.style.maxWidth = 'none';
                            svgElement.style.maxHeight = 'none';
                            svgPanZoom(svgElement, {{
                                zoomEnabled: true,
                                controlIconsEnabled: true,
                                fit: true,
                                center: true,
                                minZoom: 0.1,
                                maxZoom: 10
                            }});
                        }}
                    }});
                }} catch (e) {{
                    container.innerHTML = `<div style="color: red; padding: 20px;">Mermaid syntax error:<br><pre>${{e.message}}</pre></div>`;
                }}
            }}
            
            function initWhenVisible() {{
                const container = document.getElementById('diagramContainer');
                if (container.offsetWidth > 0 && container.offsetHeight > 0) {{
                    renderDiagram();
                }} else {{
                    const observer = new ResizeObserver((entries) => {{
                        for (let entry of entries) {{
                            if (entry.contentRect.width > 0) {{
                                observer.disconnect();
                                renderDiagram();
                                break;
                            }}
                        }}
                    }});
                    observer.observe(document.body);
                }}
            }}
            
            document.addEventListener("DOMContentLoaded", initWhenVisible);
        </script>
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: transparent;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                height: 100vh;
                overflow: hidden;
                position: relative;
            }}
            #diagramContainer {{
                width: 100%;
                height: 100%;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .download-btn {{
                position: absolute;
                top: 15px;
                right: 15px;
                z-index: 1000;
                padding: 8px 16px;
                background-color: #0EA5E9;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-family: inherit;
                font-weight: 600;
                font-size: 13px;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                transition: background-color 0.2s, transform 0.1s;
                text-decoration: none;
                display: inline-block;
            }}
            .download-btn:hover {{
                background-color: #0284C7;
                transform: translateY(-1px);
                text-decoration: none;
                color: white;
            }}
            .download-btn:active {{
                transform: translateY(1px);
            }}
        </style>
    </head>
    <body>
        <a id="downloadBtn" class="download-btn" download="diagram.svg" href="#">Download SVG</a>
        <div id="diagramCode" style="display: none;">{code}</div>
        <div id="diagramContainer"></div>
    </body>
    </html>
    """
    
    components.html(html_code, height=height, scrolling=True)
