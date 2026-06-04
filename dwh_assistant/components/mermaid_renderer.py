import streamlit as st
import streamlit.components.v1 as components
import uuid
import json
from dwh_assistant.utils.parser import clean_mermaid_code, detect_truncation

def render_mermaid(code: str, height: int = 500, node_layers: dict = None):
    """Renders Mermaid.js code visually using a robust HTML/JS engine to guarantee graphic output."""
    from dwh_assistant.utils.parser import clean_mermaid_code, detect_truncation
    import streamlit.components.v1 as components
    import uuid
    import json
    
    print(f"\n[DWH LOG] render_mermaid invoked. Raw code length: {len(code) if code else 0}")
    if not code or code.strip() == "":
        print("[DWH LOG] No code provided to render_mermaid.")
        return
    
    # Detect truncation BEFORE healing so we capture the raw AI output signal
    if detect_truncation(code):
        st.warning(
            "**Diagram may be incomplete.** The AI response was likely cut off due to response "
            "size limits. The diagram below shows what could be rendered. To get a full diagram, "
            "try: reducing schema complexity, splitting into fewer tables, or regenerating."
        )
        print("[DWH LOG] Truncation detected in Mermaid output.")

    # Ensure pristine, valid syntax
    code = clean_mermaid_code(code)
    
    div_id = f"mermaid_{uuid.uuid4().hex}"
    
    # Define styles in a clean raw string to avoid escaping hell
    css_styles_template = r"""
        :root {
            --bg-color: #ffffff;
            --text-color: #0f172a;
            --border-color: #e2e8f0;
            --shadow-color: rgba(15, 23, 42, 0.08);
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
        }

        html, body {
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            overflow: hidden;
            width: 100%;
            height: 100%;
        }
        .mermaid-container {
            width: 100%;
            height: 100%;
            position: relative;
            overflow: auto;
            box-sizing: border-box;
            cursor: grab;
        }
        #zoom-wrapper {
            position: absolute;
            top: 0;
            left: 0;
            transform-origin: 0 0;
            transition: transform 0.05s ease-out;
            cursor: grab;
            display: inline-block;
        }
        #zoom-wrapper:active {
            cursor: grabbing;
        }
        pre.mermaid {
            margin: 0;
            padding: 0;
            background: transparent;
            overflow: visible;
        }
        .mermaid svg {
            max-width: none !important;
            background: transparent !important;
        }
        .mermaid .node rect, .mermaid .node circle, .mermaid .node ellipse, .mermaid .node polygon {
            stroke-width: 2px;
        }
        .mermaid .edgePath .path {
            stroke: var(--edge-color) !important;
            stroke-width: 2px !important;
            stroke-dasharray: none !important;
            transition: stroke 0.3s ease;
        }
        .mermaid .marker path {
            fill: var(--edge-color) !important;
            stroke: none !important;
            transition: fill 0.3s ease;
        }
        .mermaid .edgeLabel rect {
            fill: var(--bg-color) !important;
            rx: 6px;
            ry: 6px;
        }
        .mermaid .edgeLabel span {
            color: var(--text-color) !important;
            font-size: 13px !important;
            font-weight: 500 !important;
            background-color: var(--bg-color) !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
        }
        .mermaid .cluster rect {
            stroke-width: 2px !important;
            transition: all 0.3s ease;
        }
        .mermaid .cluster-label text, .mermaid .cluster span {
            font-weight: 700 !important;
            font-size: 14px !important;
            letter-spacing: 0.05em !important;
        }
        .controls-bar {
            position: absolute;
            bottom: 16px;
            right: 16px;
            display: flex;
            gap: 6px;
            z-index: 9999;
            background: rgba(15, 23, 42, 0.75);
            padding: 4px;
            border-radius: 8px;
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .controls-bar button {
            background: transparent;
            color: #f8fafc;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-family: 'Inter', sans-serif;
            font-size: 12px;
            font-weight: 600;
            transition: background 0.2s, color 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            min-width: 28px;
            height: 28px;
        }
        .controls-bar button:hover {
            background: rgba(255, 255, 255, 0.2);
            color: #ffffff;
        }
        .controls-bar button:active {
            background: rgba(255, 255, 255, 0.3);
        }
        .controls-divider {
            width: 1px;
            background: rgba(255, 255, 255, 0.15);
            align-self: stretch;
            margin: 2px 0;
        }
    """

    # Define JS in a raw string and insert variables using replace
    js_template = r"""
            const explicitNodeLayers = __NODE_LAYERS__;
            const rawMermaidCode = __RAW_MERMAID_CODE__;

            function parseMermaidLayers(code) {
                const nodeToLayer = {};
                if (!code) return nodeToLayer;
                
                const lines = code.split('\n');
                let currentLayer = null;
                
                const subgraphRegex = /subgraph\s+([a-zA-Z0-9_-]+)(?:\s*(?:\[\s*['"']?([^\]'"]+)['"']?\s*\]))?/i;
                const endRegex = /^\s*end\s*$/i;
                
                for (let line of lines) {
                    line = line.trim();
                    if (!line) continue;
                    
                    const subMatch = line.match(subgraphRegex);
                    if (subMatch) {
                        const subgraphId = subMatch[1].toLowerCase();
                        const subgraphLabel = subMatch[2] ? subMatch[2].toLowerCase() : '';
                        
                        let layerType = null;
                        const fullText = (subgraphId + ' ' + subgraphLabel).toLowerCase();
                        
                        // Ingestion / Source layer — including Lakehouse landing zone
                        if (fullText.includes('ingest') || fullText.includes('source') || fullText.includes('stage_ingest') || fullText.includes('extract') || fullText.includes('api') || fullText.includes('kafka') || fullText.includes('stream') || fullText.includes('s3') || fullText.includes('bucket') || fullText.includes('lake') || fullText.includes('file') || fullText.includes('landing') || fullText.includes('raw_zone')) {
                            layerType = 'ingest';
                        // Bronze / Raw Vault / Data Vault raw layer
                        } else if (fullText.includes('bronze') || fullText.includes('raw') || fullText.includes('transient') || fullText.includes('raw_vault') || fullText.includes('hub_') || fullText.includes('lnk_') || fullText.includes('sat_')) {
                            layerType = 'bronze';
                        // Silver / Conformed / Business Vault / Cleaned layer
                        } else if (fullText.includes('silver') || fullText.includes('clean') || fullText.includes('stage') || fullText.includes('staging') || fullText.includes('process') || fullText.includes('transform') || fullText.includes('enrich') || fullText.includes('dbt') || fullText.includes('conformed') || fullText.includes('business_vault') || fullText.includes('satellite') || fullText.includes('conform')) {
                            layerType = 'silver';
                        // Gold / Curated / Info Mart / Semantic / Dimensional layer
                        } else if (fullText.includes('gold') || fullText.includes('curated') || fullText.includes('mart') || fullText.includes('fact') || fullText.includes('dim_') || fullText.includes('fact_') || fullText.includes('semantic') || fullText.includes('serve') || fullText.includes('model') || fullText.includes('dimension') || fullText.includes('info_mart') || fullText.includes('enriched')) {
                            layerType = 'gold';
                        // Consumption / BI / Reporting layer
                        } else if (fullText.includes('consume') || fullText.includes('bi') || fullText.includes('report') || fullText.includes('dash') || fullText.includes('anal') || fullText.includes('viz') || fullText.includes('tableau') || fullText.includes('looker') || fullText.includes('powerbi') || fullText.includes('app') || fullText.includes('user') || fullText.includes('consumer')) {
                            layerType = 'consume';
                        // Governance / Security / RBAC layer
                        } else if (fullText.includes('govern') || fullText.includes('secur') || fullText.includes('audit') || fullText.includes('policy') || fullText.includes('rbac') || fullText.includes('iam') || fullText.includes('mask') || fullText.includes('encrypt') || fullText.includes('admin') || fullText.includes('role') || fullText.includes('access') || fullText.includes('grant') || fullText.includes('privilege') || fullText.includes('compliance') || fullText.includes('catalog')) {
                            layerType = 'govern';
                        } else {
                            layerType = subgraphId;
                        }
                        
                        if (layerType) {
                            currentLayer = layerType;
                        }
                        continue;
                    }
                    
                    if (line.match(endRegex)) {
                        currentLayer = null;
                        continue;
                    }
                    
                    if (currentLayer) {
                        const nodeMatch = line.match(/^\s*([a-zA-Z0-9_-]+)/);
                        if (nodeMatch) {
                            const nodeId = nodeMatch[1].toLowerCase();
                            const keywords = ['subgraph', 'end', 'classdef', 'style', 'class', 'click', 'linkstyle', 'direction'];
                            if (!keywords.includes(nodeId)) {
                                nodeToLayer[nodeId] = currentLayer;
                            }
                        }
                    }
                }
                return nodeToLayer;
            }

            const parsedSubgraphLayers = parseMermaidLayers(rawMermaidCode);

            const layerToTheme = {};
            let themeIdx = 0;
            function getThemeForLayer(layerName) {
                if (!layerName) return 'default';
                const name = layerName.toLowerCase();
                if (layerToTheme[name]) return layerToTheme[name];

                // Ingestion / Source / Landing Zone (Medallion, Lakehouse, Data Vault)
                if (name.includes('ingest') || name.includes('source') || name.includes('stage_ingest') || name.includes('extract') || name.includes('api') || name.includes('kafka') || name.includes('stream') || name.includes('s3') || name.includes('bucket') || name.includes('lake') || name.includes('blob') || name.includes('file') || name.includes('landing') || name.includes('raw_zone') || name === 'ingest') {
                    layerToTheme[name] = 'ingest';
                // Bronze / Raw Vault / Hub / Link / Satellite raw objects (Data Vault 2.0)
                } else if (name.includes('bronze') || name.includes('raw') || name.includes('transient') || name.includes('raw_vault') || name.startsWith('hub_') || name.startsWith('lnk_') || name.startsWith('sat_') || name === 'bronze') {
                    layerToTheme[name] = 'bronze';
                // Silver / Business Vault / Conformed / Cleaned (Medallion, Data Vault, Lakehouse)
                } else if (name.includes('silver') || name.includes('clean') || name.includes('stage') || name.includes('staging') || name.includes('transform') || name.includes('process') || name.includes('enrich') || name.includes('dbt') || name.includes('conformed') || name.includes('business_vault') || name.includes('satellite') || name.includes('conform') || name === 'silver') {
                    layerToTheme[name] = 'silver';
                // Gold / Info Mart / Semantic / Curated / Enriched / Dimensional (all architecture types)
                } else if (name.includes('gold') || name.includes('curated') || name.includes('mart') || name.includes('fact') || name.includes('dim_') || name.includes('fact_') || name.includes('semantic') || name.includes('serve') || name.includes('model') || name.includes('dimension') || name.includes('info_mart') || name.includes('enriched') || name === 'gold') {
                    layerToTheme[name] = 'gold';
                // Consumption / BI / Reporting / Analytics / Application layer
                } else if (name.includes('consume') || name.includes('bi') || name.includes('report') || name.includes('dashboard') || name.includes('anal') || name.includes('viz') || name.includes('tableau') || name.includes('looker') || name.includes('powerbi') || name.includes('app') || name.includes('user') || name.includes('consumer') || name === 'consume') {
                    layerToTheme[name] = 'consume';
                // Governance / Security / RBAC / Compliance / Catalog
                } else if (name.includes('govern') || name.includes('secur') || name.includes('audit') || name.includes('policy') || name.includes('rbac') || name.includes('iam') || name.includes('mask') || name.includes('encrypt') || name.includes('admin') || name.includes('role') || name.includes('access') || name.includes('grant') || name.includes('privilege') || name.includes('compliance') || name.includes('catalog') || name === 'govern') {
                    layerToTheme[name] = 'govern';
                } else {
                    const fallbackThemes = ['silver', 'gold', 'ingest', 'bronze', 'consume', 'govern'];
                    layerToTheme[name] = fallbackThemes[themeIdx % fallbackThemes.length];
                    themeIdx++;
                }
                return layerToTheme[name];
            }

            mermaid.initialize({
                startOnLoad: true,
                theme: 'base',
                securityLevel: 'loose',
                maxTextSize: 9000000,
                maxEdges: 100000,
                themeVariables: {
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
                },
                er: {
                    layoutDirection: 'TB',
                    minEntityWidth: 200,
                    minEntityHeight: 80
                },
                flowchart: {
                    htmlLabels: true,
                    curve: 'basis',
                    nodeSpacing: 50,
                    rankSpacing: 50
                }
            });

            // Wait for SVG AND its viewBox to be fully populated by Mermaid before doing anything.
            // Mermaid inserts the SVG element first, then populates viewBox asynchronously.
            // Firing too early results in zero dimensions → wrong fitToScreen scale.
            let initAttempts = 0;
            const MAX_INIT_ATTEMPTS = 120; // up to 6 seconds at 50ms intervals
            let lastVbW = -1;
            let stableCount = 0;
            const checkTimer = setInterval(() => {
                const svg = document.querySelector('.mermaid svg');
                if (!svg) { if (++initAttempts >= MAX_INIT_ATTEMPTS) clearInterval(checkTimer); return; }

                // Confirm viewBox is populated with real non-zero dimensions
                const vb = svg.getAttribute('viewBox');
                if (!vb) { if (++initAttempts >= MAX_INIT_ATTEMPTS) clearInterval(checkTimer); return; }
                const vbParts = vb.trim().split(/[ ,]+/);
                if (vbParts.length < 4) { if (++initAttempts >= MAX_INIT_ATTEMPTS) clearInterval(checkTimer); return; }
                const vbW = parseFloat(vbParts[2]);
                const vbH = parseFloat(vbParts[3]);
                if (!vbW || !vbH) { if (++initAttempts >= MAX_INIT_ATTEMPTS) clearInterval(checkTimer); return; }

                // Wait for layout stability (Dagre layout engine can adjust viewBox multiple times)
                if (vbW === lastVbW) {
                    stableCount++;
                } else {
                    stableCount = 0;
                    lastVbW = vbW;
                }

                if (stableCount >= 2) {
                    // SVG is fully rendered with stable real layout — safe to style and fit
                    clearInterval(checkTimer);
                    applyPremiumStyling(svg);
                    initPanZoom(svg);
                }
            }, 50);

            function applyPremiumStyling(svg) {
                try {
                    // Set SVG width and height to match its viewBox values with a safety buffer
                    let svgWidth = 0;
                    let svgHeight = 0;
                    const viewBoxAttr = svg.getAttribute('viewBox');
                    if (viewBoxAttr) {
                        const parts = viewBoxAttr.trim().split(/[ ,]+/);
                        if (parts.length === 4) {
                            let vx = parseFloat(parts[0]);
                            let vy = parseFloat(parts[1]);
                            let vw = parseFloat(parts[2]);
                            let vh = parseFloat(parts[3]);
                            
                            // Add 40px safety padding to right and bottom for font rendering discrepancies
                            vw += 40;
                            vh += 40;
                            svg.setAttribute('viewBox', `${vx} ${vy} ${vw} ${vh}`);
                            svgWidth = vw;
                            svgHeight = vh;
                        }
                    }
                    if (!svgWidth || !svgHeight) {
                        svgWidth = (parseFloat(svg.getAttribute('width')) || 0) + 40;
                        svgHeight = (parseFloat(svg.getAttribute('height')) || 0) + 40;
                    }
                    if (svgWidth && svgHeight) {
                        svg.style.setProperty('width', svgWidth + 'px', 'important');
                        svg.style.setProperty('height', svgHeight + 'px', 'important');
                    }

                    let defs = svg.querySelector('defs');
                    if (!defs) {
                        defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
                        svg.insertBefore(defs, svg.firstChild);
                    }
                    
                    const gradientsMarkup = `
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
                    
                    const parser = new DOMParser();
                    const doc = parser.parseFromString('<svg xmlns="http://www.w3.org/2000/svg">' + gradientsMarkup + '</svg>', "image/svg+xml");
                    const children = Array.from(doc.querySelector('svg').childNodes);
                    children.forEach(child => {
                        if (!defs.querySelector('#' + child.id)) {
                            defs.appendChild(child);
                        }
                    });

                    // 1. Style subgraphs (clusters) dynamically
                    const clusters = svg.querySelectorAll('.cluster');
                    clusters.forEach(cluster => {
                        let clusterId = '';
                        const idAttr = cluster.getAttribute('id');
                        if (idAttr) {
                            const match = idAttr.match(/^flowchart-([a-zA-Z0-9_-]+)-\d+$/) || idAttr.match(/^flowchart-([a-zA-Z0-9_-]+)$/);
                            if (match) {
                                clusterId = match[1];
                            } else {
                                clusterId = idAttr;
                            }
                        }
                        cluster.classList.forEach(cls => {
                            if (cls.startsWith('id-')) {
                                clusterId = cls.substring(3);
                            }
                        });

                        let clusterLabel = '';
                        const labelEl = cluster.querySelector('.cluster-label text, span, text');
                        if (labelEl) {
                            clusterLabel = labelEl.textContent.trim().toLowerCase();
                        }

                        const theme = getThemeForLayer(clusterLabel || clusterId);
                        const rect = cluster.querySelector('rect');
                        if (rect) {
                            rect.style.fill = `var(--${theme}-stop-1)`;
                            rect.style.stroke = `var(--${theme}-border)`;
                            rect.style.strokeWidth = '2px';
                            rect.style.strokeDasharray = '4,4';
                            rect.style.rx = '16px';
                            rect.style.ry = '16px';
                            rect.style.filter = 'url(#premium-shadow)';
                        }
                        const labels = cluster.querySelectorAll('.cluster-label text, span, text');
                        labels.forEach(lbl => {
                            lbl.style.fill = `var(--${theme}-text)`;
                            lbl.style.color = `var(--${theme}-text)`;
                            lbl.style.fontWeight = '600';
                        });
                    });

                    // 2. Enhance flowchart nodes
                    const nodes = svg.querySelectorAll('.node');
                    nodes.forEach(node => {
                        const label = node.querySelector('.label');
                        const text = label ? label.textContent.toLowerCase() : '';
                        
                        let nodeId = '';
                        node.classList.forEach(cls => {
                            if (cls.startsWith('id-')) {
                                nodeId = cls.substring(3);
                            }
                        });
                        if (!nodeId) {
                            const idAttr = node.getAttribute('id');
                            if (idAttr) {
                                const match = idAttr.match(/^flowchart-([a-zA-Z0-9_-]+)-\d+$/) || idAttr.match(/^flowchart-([a-zA-Z0-9_-]+)$/);
                                if (match) nodeId = match[1];
                                else nodeId = idAttr;
                            }
                        }

                        let type = 'default';
                        let matched = false;

                        if (explicitNodeLayers && Object.keys(explicitNodeLayers).length > 0) {
                            const lowNodeId = nodeId.toLowerCase();
                            const lowText = text.trim().toLowerCase().replace(/['"]/g, '');

                            // A. Exact nodeId match
                            if (explicitNodeLayers[lowNodeId]) {
                                type = getThemeForLayer(explicitNodeLayers[lowNodeId]);
                                matched = true;
                            }
                            // B. Exact label text match
                            if (!matched && lowText && explicitNodeLayers[lowText]) {
                                type = getThemeForLayer(explicitNodeLayers[lowText]);
                                matched = true;
                            }
                            // C. Underscore/space boundary matches
                            if (!matched && lowText) {
                                for (const [name, layer] of Object.entries(explicitNodeLayers)) {
                                    const lowName = name.toLowerCase();
                                    if (lowText === lowName || lowText.startsWith(lowName + '_') || lowText.endsWith('_' + lowName) || lowText.includes(' ' + lowName) || lowText.includes(lowName + ' ')) {
                                        type = getThemeForLayer(layer);
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                        }

                        if (!matched && parsedSubgraphLayers && Object.keys(parsedSubgraphLayers).length > 0) {
                            const lowNodeId = nodeId.toLowerCase();
                            if (parsedSubgraphLayers[lowNodeId]) {
                                type = getThemeForLayer(parsedSubgraphLayers[lowNodeId]);
                                matched = true;
                            }
                        }

                        if (!matched) {
                            type = getThemeForLayer(text || nodeId);
                        }

                        // Apply styles to shapes (path, rect, etc.)
                        const shapes = node.querySelectorAll('rect, circle, ellipse, polygon, path:not(.edgePath)');
                        shapes.forEach(shape => {
                            shape.style.fill = `url(#grad-${type})`;
                            shape.style.stroke = `var(--${type}-border)`;
                            shape.style.strokeWidth = '2px';
                            shape.style.filter = 'url(#premium-shadow)';
                            
                            if (shape.tagName.toLowerCase() === 'rect') {
                                shape.setAttribute('rx', '10');
                                shape.setAttribute('ry', '10');
                            }
                        });

                        if (label) {
                            const labelTexts = label.querySelectorAll('text, span, div, p');
                            const targetEls = labelTexts.length > 0 ? labelTexts : [label];
                            targetEls.forEach(el => {
                                el.style.color = `var(--${type}-text)`;
                                el.style.fill = `var(--${type}-text)`;
                                el.style.fontWeight = '600';
                                el.style.fontFamily = 'Inter, -apple-system, sans-serif';
                            });
                        }
                    });

                    // 3. Enhance ER Diagram Entities (Exact table name mapping)
                    const entityBoxes = svg.querySelectorAll('.entityBox');
                    entityBoxes.forEach(box => {
                        const parentG = box.parentElement;
                        let entityName = '';
                        const firstTextEl = parentG ? parentG.querySelector('text') : null;
                        if (firstTextEl) {
                            entityName = firstTextEl.textContent.trim().toLowerCase().replace(/['"]/g, '');
                        }
                        
                        let type = 'default';
                        let matched = false;

                        if (entityName && explicitNodeLayers && Object.keys(explicitNodeLayers).length > 0) {
                            if (explicitNodeLayers[entityName]) {
                                type = getThemeForLayer(explicitNodeLayers[entityName]);
                                matched = true;
                            }
                            if (!matched) {
                                for (const [name, layer] of Object.entries(explicitNodeLayers)) {
                                    const lowName = name.toLowerCase();
                                    if (entityName === lowName || entityName.startsWith(lowName + '_') || entityName.endsWith('_' + lowName)) {
                                        type = getThemeForLayer(layer);
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                        }

                        if (!matched && entityName) {
                            if (entityName.includes('fact_') || entityName.startsWith('fact')) type = 'gold';
                            else if (entityName.includes('dim_') || entityName.startsWith('dim')) type = 'silver';
                            else if (entityName.includes('bridge') || entityName.includes('map')) type = 'ingest';
                            else if (entityName.includes('raw_') || entityName.startsWith('raw') || entityName.startsWith('src_')) type = 'bronze';
                            else type = getThemeForLayer(entityName);
                        }

                        box.style.fill = 'var(--bg-color)';
                        box.style.stroke = `var(--${type}-border)`;
                        box.style.strokeWidth = '1.5px';
                        box.style.filter = 'url(#premium-shadow)';
                        box.setAttribute('rx', '10');
                        box.setAttribute('ry', '10');
                    });

                    const entityHeaders = svg.querySelectorAll('.entityHeader');
                    entityHeaders.forEach(header => {
                        const parentG = header.parentElement;
                        let entityName = '';
                        const firstTextEl = parentG ? parentG.querySelector('text') : null;
                        if (firstTextEl) {
                            entityName = firstTextEl.textContent.trim().toLowerCase().replace(/['"]/g, '');
                        }
                        
                        let type = 'default';
                        let matched = false;

                        if (entityName && explicitNodeLayers && Object.keys(explicitNodeLayers).length > 0) {
                            if (explicitNodeLayers[entityName]) {
                                type = getThemeForLayer(explicitNodeLayers[entityName]);
                                matched = true;
                            }
                            if (!matched) {
                                for (const [name, layer] of Object.entries(explicitNodeLayers)) {
                                    const lowName = name.toLowerCase();
                                    if (entityName === lowName || entityName.startsWith(lowName + '_') || entityName.endsWith('_' + lowName)) {
                                        type = getThemeForLayer(layer);
                                        matched = true;
                                        break;
                                    }
                                }
                            }
                        }

                        if (!matched && entityName) {
                            if (entityName.includes('fact_') || entityName.startsWith('fact')) type = 'gold';
                            else if (entityName.includes('dim_') || entityName.startsWith('dim')) type = 'silver';
                            else if (entityName.includes('bridge') || entityName.includes('map')) type = 'ingest';
                            else if (entityName.includes('raw_') || entityName.startsWith('raw') || entityName.startsWith('src_')) type = 'bronze';
                            else type = getThemeForLayer(entityName);
                        }

                        header.style.fill = `url(#grad-${type})`;
                        header.style.stroke = `var(--${type}-border)`;
                        header.style.strokeWidth = '1.5px';
                        header.setAttribute('rx', '10');
                        header.setAttribute('ry', '10');
                    });

                    const texts = svg.querySelectorAll('text');
                    texts.forEach(txt => {
                        txt.style.fontFamily = 'Inter, -apple-system, sans-serif';
                    });
                } catch (e) {
                    console.error("Premium styling error: ", e);
                }
            }

            let scale = 1.0;
            let pointX = 0;
            let pointY = 0;
            let start = { x: 0, y: 0 };
            let isDragging = false;
            let zoomWrapper = null;
            let container = null;

            function getElements() {
                if (!zoomWrapper) zoomWrapper = document.getElementById('zoom-wrapper');
                if (!container) container = document.querySelector('.mermaid-container');
                return { container, zoomWrapper };
            }

            function setTransform() {
                const els = getElements();
                if (els.zoomWrapper) {
                    els.zoomWrapper.style.transform = `translate(${pointX}px, ${pointY}px) scale(${scale})`;
                }
            }

            function initPanZoom(svg) {
                const els = getElements();
                if (!els.container) return;

                els.container.onmousedown = function (e) {
                    if (e.target.closest('.controls-bar')) return;
                    e.preventDefault();
                    start = { x: e.clientX - pointX, y: e.clientY - pointY };
                    isDragging = true;
                    els.container.style.cursor = 'grabbing';
                };

                els.container.onmouseup = function (e) {
                    isDragging = false;
                    els.container.style.cursor = 'grab';
                };

                els.container.onmouseleave = function (e) {
                    isDragging = false;
                    els.container.style.cursor = 'grab';
                };

                els.container.onmousemove = function (e) {
                    if (!isDragging) return;
                    e.preventDefault();
                    pointX = e.clientX - start.x;
                    pointY = e.clientY - start.y;
                    setTransform();
                };

                els.container.ondblclick = function (e) {
                    if (e.target.closest('.controls-bar')) return;
                    fitToScreen();
                };

                // Add mouse wheel listener for anchored zoom
                els.container.onwheel = function (e) {
                    e.preventDefault();
                    const rect = els.container.getBoundingClientRect();
                    const mouseX = e.clientX - rect.left;
                    const mouseY = e.clientY - rect.top;
                    
                    const zoomFactor = e.deltaY < 0 ? 1.15 : (1 / 1.15);
                    const newScale = Math.min(Math.max(scale * zoomFactor, 0.15), 4.0);
                    const actualFactor = newScale / scale;
                    
                    pointX = mouseX - (mouseX - pointX) * actualFactor;
                    pointY = mouseY - (mouseY - pointY) * actualFactor;
                    scale = newScale;
                    setTransform();
                };

                // checkTimer already verified viewBox dimensions are valid.
                // Small delay lets the browser repaint after applyPremiumStyling DOM changes.
                setTimeout(fitToScreen, 50);
            }

            function zoom(factor) {
                const els = getElements();
                if (!els.container) return;
                const rect = els.container.getBoundingClientRect();
                const cx = rect.width / 2;
                const cy = rect.height / 2;
                
                const newScale = Math.min(Math.max(scale * factor, 0.15), 4.0);
                const actualFactor = newScale / scale;
                
                pointX = cx - (cx - pointX) * actualFactor;
                pointY = cy - (cy - pointY) * actualFactor;
                scale = newScale;
                setTransform();
            }

            function zoomIn() {
                zoom(1.2);
            }

            function zoomOut() {
                zoom(1 / 1.2);
            }

            function resetZoom() {
                scale = 1.0;
                pointX = 0;
                pointY = 0;
                setTransform();
            }

            function fitToScreen() {
                const svg = document.querySelector('.mermaid svg');
                const els = getElements();
                if (!svg || !els.container) return;
                
                const containerRect = els.container.getBoundingClientRect();
                if (containerRect.width <= 0 || containerRect.height <= 0) {
                    // Container not sized yet, retry in 100ms
                    setTimeout(fitToScreen, 100);
                    return;
                }
                
                let svgWidth = 0;
                let svgHeight = 0;
                
                const viewBoxAttr = svg.getAttribute('viewBox');
                if (viewBoxAttr) {
                    const parts = viewBoxAttr.trim().split(/[ ,]+/);
                    if (parts.length === 4) {
                        svgWidth = parseFloat(parts[2]);
                        svgHeight = parseFloat(parts[3]);
                    }
                }
                
                if (!svgWidth || !svgHeight) {
                    try {
                        const bbox = svg.getBBox();
                        svgWidth = bbox.width;
                        svgHeight = bbox.height;
                    } catch (e) {
                        const rect = svg.getBoundingClientRect();
                        svgWidth = rect.width;
                        svgHeight = rect.height;
                    }
                }
                
                if (svgWidth <= 0 || svgHeight <= 0) {
                    // SVG elements not initialized yet, retry in 100ms
                    setTimeout(fitToScreen, 100);
                    return;
                }
                
                const scaleX = (containerRect.width - 40) / svgWidth;
                const scaleY = (containerRect.height - 40) / svgHeight;
                
                scale = Math.min(scaleX, scaleY, 1.0); // Maintain a clean optimal scale, never distorting or overzooming past 100%
                
                pointX = (containerRect.width - svgWidth * scale) / 2;
                pointY = (containerRect.height - svgHeight * scale) / 2;
                
                setTransform();
            }

            // Expose navigation functions to window for onclick handlers
            window.zoomIn = zoomIn;
            window.zoomOut = zoomOut;
            window.resetZoom = resetZoom;
            window.fitToScreen = fitToScreen;
    """

    # Do the raw template replacements
    css_styles = css_styles_template
    node_layers_json = json.dumps(node_layers or {})
    raw_mermaid_json = json.dumps(code)
    
    js_script = js_template.replace("__NODE_LAYERS__", node_layers_json).replace("__RAW_MERMAID_CODE__", raw_mermaid_json)
    
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
            {css_styles}
        </style>
    </head>
    <body>
        <div class="mermaid-container">
            <div id="zoom-wrapper">
                <pre class="mermaid" id="{div_id}">
{code}
                </pre>
            </div>
            <div class="controls-bar">
                <button onclick="zoomIn()" title="Zoom In">+</button>
                <button onclick="zoomOut()" title="Zoom Out">-</button>
                <div class="controls-divider"></div>
                <button onclick="fitToScreen()" title="Fit to Screen">Fit</button>
                <button onclick="resetZoom()" title="Reset Zoom">1:1</button>
            </div>
        </div>
        <script>
            {js_script}
        </script>
    </body>
    </html>
    """
    
    # Render using Streamlit's stable iframe component injection via data URL to avoid deprecation warnings
    import base64
    b64_html = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
    components.iframe(f"data:text/html;base64,{b64_html}", height=height, scrolling=True)

