import streamlit as st
import streamlit.components.v1 as components
from dwh_assistant.utils.parser import clean_mermaid_code, detect_truncation

def render_mermaid(code: str, height: int = 500, node_layers: dict = None):
    """Renders Mermaid.js code natively using an HTML component for maximum reliability."""
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
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{
                startOnLoad: false,
                theme: 'default',
                securityLevel: 'loose'
            }});
            
            async function renderDiagram() {{
                const graphDefinition = document.getElementById('diagramCode').textContent;
                const container = document.getElementById('diagramContainer');
                try {{
                    const {{ svg }} = await mermaid.render('mermaid-svg', graphDefinition);
                    container.innerHTML = svg;
                    
                    // Initialize svg-pan-zoom
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
            }}
                width: 100%;
                height: 100%;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
        </style>
    </head>
    <body>
        <div id="diagramCode" style="display: none;">{code}</div>
        <div id="diagramContainer"></div>
    </body>
    </html>
    """
    
    components.html(html_code, height=height, scrolling=True)
