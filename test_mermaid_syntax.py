def test():
    height = 500
    div_id = "test_div"
    code = "graph TD\n  A --> B"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
        <style>
            :root {{
                --bg-color: #ffffff;
                --text-color: #0f172a;
                --border-color: #e2e8f0;
                --shadow-color: rgba(15, 23, 42, 0.04);
                --edge-color: #94a3b8;
                --cluster-bg: #f8fafc;
                --cluster-border: #e2e8f0;
                --cluster-text: #475569;

                /* Ingestion (Teal) */
                --ingest-stop-1: #f0fdfa;
                --ingest-stop-2: #ccfbf1;
                --ingest-border: #0d9488;
                --ingest-text: #0f766e;

                /* Bronze (Amber) */
                --bronze-stop-1: #fffbeb;
                --bronze-stop-2: #fef3c7;
                --bronze-border: #d97706;
                --bronze-text: #b45309;

                /* Silver (Blue) */
                --silver-stop-1: #eff6ff;
                --silver-stop-2: #dbeafe;
                --silver-border: #2563eb;
                --silver-text: #1d4ed8;

                /* Gold (Purple) */
                --gold-stop-1: #faf5ff;
                --gold-stop-2: #f3e8ff;
                --gold-border: #7c3aed;
                --gold-text: #6d28d9;

                /* Consumption (Rose) */
                --consume-stop-1: #fff1f2;
                --consume-stop-2: #ffe4e6;
                --consume-border: #e11d48;
                --consume-text: #be123c;

                /* Governance (Emerald) */
                --govern-stop-1: #f0fdf4;
                --govern-stop-2: #dcfce7;
                --govern-border: #16a34a;
                --govern-text: #15803d;

                /* Default (Slate/Gray) */
                --default-stop-1: #f8fafc;
                --default-stop-2: #f1f5f9;
                --default-border: #475569;
                --default-text: #334155;
            }}

            body {{
                margin: 0;
                padding: 25px;
                background-color: var(--bg-color);
                color: var(--text-color);
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: flex-start;
                min-height: {height - 40}px;
                transition: background-color 0.3s ease, color 0.3s ease;
            }}
            .mermaid-container {{
                width: 100%;
                display: flex;
                justify-content: center;
                overflow: auto;
                padding: 30px;
                box-sizing: border-box;
            }}
            /* Force rendered SVG diagrams to scale up significantly for maximum visual size */
            .mermaid svg {{
                max-width: none !important;
                width: auto !important;
                height: auto !important;
                zoom: 2.2; /* Significantly increase the visual size of diagram elements */
                background: transparent !important;
            }}
            .mermaid .node rect, .mermaid .node circle, .mermaid .node ellipse, .mermaid .node polygon {{
                stroke-width: 2px;
            }}
            .mermaid .edgePath .path {{
                stroke: var(--edge-color) !important;
                stroke-width: 2px !important;
                stroke-dasharray: none !important;
                transition: stroke 0.3s ease;
            }}
            .mermaid .marker path {{
                fill: var(--edge-color) !important;
                stroke: none !important;
                transition: fill 0.3s ease;
            }}
            .mermaid .edgeLabel rect {{
                fill: var(--bg-color) !important;
                rx: 6px;
                ry: 6px;
            }}
            .mermaid .edgeLabel span {{
                color: var(--text-color) !important;
                font-size: 13px !important;
                font-weight: 500 !important;
                background-color: var(--bg-color) !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
            }}
            .mermaid .cluster rect {{
                fill: var(--cluster-bg) !important;
                stroke: var(--cluster-border) !important;
                stroke-width: 1.5px !important;
                rx: 16px !important;
                ry: 16px !important;
                filter: drop-shadow(0 4px 8px var(--shadow-color)) !important;
                transition: all 0.3s ease;
            }}
            .mermaid .cluster-label text, .mermaid .cluster span {{
                fill: var(--cluster-text) !important;
                color: var(--cluster-text) !important;
                font-weight: 700 !important;
                font-size: 14px !important;
                letter-spacing: 0.05em !important;
                text-transform: uppercase !important;
            }}
        </style>
    </head>
    <body>
        <div class="mermaid-container">
            <pre class="mermaid" id="{div_id}">
{code}
            </pre>
        </div>
        <script>
            mermaid.initialize({{
                startOnLoad: true,
                theme: 'base',
                securityLevel: 'loose',
                themeVariables: {{
                    fontFamily: 'Inter, -apple-system, sans-serif',
                    fontSize: '18px',
                    primaryColor: '#F8FAFC',
                    primaryTextColor: '#0F172A',
                    primaryBorderColor: '#CBD5E1',
                    lineColor: '#64748B',
                    secondaryColor: '#F1F5F9',
                    tertiaryColor: '#E2E8F0',
                    entityBorder: '#CBD5E1',
                    entityBackground: '#F8FAFC',
                    attributeBackgroundColor: '#FFFFFF',
                    attributeLabelColor: '#0F172A',
                    relationshipLineColor: '#64748B'
                }},
                er: {{
                    layoutDirection: 'TB',
                    minEntityWidth: 200,
                    minEntityHeight: 80
                }},
                flowchart: {{
                    htmlLabels: true,
                    curve: 'basis',
                    nodeSpacing: 100,
                    rankSpacing: 100
                }}
            }});

            // Observe when SVG is generated and apply premium overrides
            const checkTimer = setInterval(() => {{
                const svg = document.querySelector('.mermaid svg');
                if (svg) {{
                    clearInterval(checkTimer);
                    applyPremiumStyling(svg);
                }}
            }}, 50);

            function applyPremiumStyling(svg) {{
                // Adjust container and body alignment based on overflow
                const container = document.querySelector('.mermaid-container');
                const svgRect = svg.getBoundingClientRect();
                if (svgRect.width > window.innerWidth - 60) {{
                    document.body.style.justifyContent = 'flex-start';
                    container.style.justifyContent = 'flex-start';
                }} else {{
                    document.body.style.justifyContent = 'center';
                    container.style.justifyContent = 'center';
                }}

                // 1. Inject linear gradients and filters into <defs>
                let defs = svg.querySelector('defs');
                if (!defs) {{
                    defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                    svg.insertBefore(defs, svg.firstChild);
                }
                
                defs.innerHTML += `
                    <filter id="premium-shadow" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="1" dy="3" stdDeviation="4" flood-color="var(--shadow-color)" flood-opacity="1" />
                    </filter>
                    <linearGradient id="grad-ingest" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="var(--ingest-stop-1)" />
                        <stop offset="100%" stop-color="var(--ingest-stop-2)" />
                    </linearGradient>
                    <linearGradient id="grad-bronze" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="var(--bronze-stop-1)" />
                        <stop offset="100%" stop-color="var(--bronze-stop-2)" />
                    </linearGradient>
                    <linearGradient id="grad-silver" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="var(--silver-stop-1)" />
                        <stop offset="100%" stop-color="var(--silver-stop-2)" />
                    </linearGradient>
                    <linearGradient id="grad-gold" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="var(--gold-stop-1)" />
                        <stop offset="100%" stop-color="var(--gold-stop-2)" />
                    </linearGradient>
                    <linearGradient id="grad-consume" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="var(--consume-stop-1)" />
                        <stop offset="100%" stop-color="var(--consume-stop-2)" />
                    </linearGradient>
                    <linearGradient id="grad-govern" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="var(--govern-stop-1)" />
                        <stop offset="100%" stop-color="var(--govern-stop-2)" />
                    </linearGradient>
                    <linearGradient id="grad-default" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="var(--default-stop-1)" />
                        <stop offset="100%" stop-color="var(--default-stop-2)" />
                    </linearGradient>
                `;

                // 2. Enhance flowchart nodes
                const nodes = svg.querySelectorAll('.node');
                nodes.forEach(node => {{
                    const label = node.querySelector('.label');
                    const text = label ? label.textContent.toLowerCase() : '';
                    
                    let type = 'default';
                    if (text.includes('source') || text.includes('ingest') || text.includes('extract') || text.includes('api') || text.includes('kafka') || text.includes('event') || text.includes('stream') || text.includes('crm') || text.includes('erp') || text.includes('s3') || text.includes('database') || text.includes('db')) {{
                        type = 'ingest';
                    }} else if (text.includes('bronze') || text.includes('raw') || text.includes('landing') || text.includes('transient')) {{
                        type = 'bronze';
                    }} else if (text.includes('silver') || text.includes('clean') || text.includes('stage') || text.includes('staging') || text.includes('transform') || text.includes('process') || text.includes('enrich') || text.includes('dbt')) {{
                        type = 'silver';
                    }} else if (text.includes('gold') || text.includes('curated') || text.includes('mart') || text.includes('fact') || text.includes('dim_') || text.includes('fact_') || text.includes('semantic') || text.includes('serve') || text.includes('model') || text.includes('dimension')) {{
                        type = 'gold';
                    }} else if (text.includes('bi') || text.includes('report') || text.includes('dashboard') || text.includes('consume') || text.includes('ml') || text.includes('ai') || text.includes('predict') || text.includes('analytics') || text.includes('user') || text.includes('viz') || text.includes('tableau') || text.includes('looker') || text.includes('powerbi')) {{
                        type = 'consume';
                    }} else if (text.includes('govern') || text.includes('secure') || text.includes('catalog') || text.includes('lineage') || text.includes('audit') || text.includes('mask') || text.includes('policy') || text.includes('access') || text.includes('rbac') || text.includes('iam') || text.includes('security')) {{
                        type = 'govern';
                    }}

                    // Apply styles to shapes
                    const shapes = node.querySelectorAll('rect, circle, ellipse, polygon, path:not(.edgePath)');
                    shapes.forEach(shape => {{
                        if (shape.tagName.toLowerCase() === 'path' && shape.getAttribute('d')) {{
                            return;
                        }}
                        shape.style.fill = `url(#grad-${{type}})`;
                        shape.style.stroke = `var(--${{type}}-border)`;
                        shape.style.strokeWidth = '2px';
                        shape.style.filter = 'url(#premium-shadow)';
                        
                        if (shape.tagName.toLowerCase() === 'rect') {{
                            shape.setAttribute('rx', '10');
                            shape.setAttribute('ry', '10');
                        }}
                    }});

                    // Enhance label typography and color
                    if (label) {{
                        const labelTexts = label.querySelectorAll('text, span, div, p');
                        if (labelTexts.length > 0) {{
                            labelTexts.forEach(el => {{
                                el.style.color = `var(--${{type}}-text)`;
                                el.style.fill = `var(--${{type}}-text)`;
                                el.style.fontWeight = '600';
                                el.style.fontFamily = 'Inter, -apple-system, sans-serif';
                            }});
                        }} else {{
                            label.style.color = `var(--${{type}}-text)`;
                            label.style.fill = `var(--${{type}}-text)`;
                            label.style.fontWeight = '600';
                            label.style.fontFamily = 'Inter, -apple-system, sans-serif';
                        }}
                    }}
                }});

                // 3. Enhance ER Diagram Entities
                const entityBoxes = svg.querySelectorAll('.entityBox');
                entityBoxes.forEach(box => {{
                    box.style.fill = 'var(--default-stop-1)';
                    box.style.stroke = 'var(--default-border)';
                    box.style.strokeWidth = '1.5px';
                    box.style.filter = 'url(#premium-shadow)';
                    box.setAttribute('rx', '10');
                    box.setAttribute('ry', '10');
                }});

                const entityHeaders = svg.querySelectorAll('.entityHeader');
                entityHeaders.forEach(header => {{
                    const parentG = header.parentElement;
                    const text = parentG ? parentG.textContent.toLowerCase() : '';
                    
                    let type = 'default';
                    if (text.includes('fact_')) {{
                        type = 'gold';
                    }} else if (text.includes('dim_')) {{
                        type = 'silver';
                    }} else if (text.includes('bridge') || text.includes('map')) {{
                        type = 'ingest';
                    }} else if (text.includes('raw_') || text.includes('src_')) {{
                        type = 'bronze';
                    }}

                    header.style.fill = `url(#grad-${{type}})`;
                    header.style.stroke = `var(--${{type}}-border)`;
                    header.style.strokeWidth = '1.5px';
                    header.setAttribute('rx', '10');
                    header.setAttribute('ry', '10');
                }});
            }}
        </script>
    </body>
    </html>
    """
    return html_content

print("HTML generation successful!")
