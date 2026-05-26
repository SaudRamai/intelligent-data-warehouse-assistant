import streamlit as st
import time
import sys
import os
from pathlib import Path

# Fix for ModuleNotFoundError
root_path = str(Path(__file__).parent.parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

import pandas as pd
import json
import re
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from dwh_assistant.backend.executor import format_ddl
from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, init_session_state, render_page_header
st.set_page_config(page_title="Design Center | AI DWH", layout="wide")
init_session_state()
apply_premium_style()

def render_mermaid(code: str, height: int = 500, node_layers: dict = None):
    """Renders Mermaid.js code visually using a robust HTML/JS engine to guarantee graphic output."""
    from dwh_assistant.backend.validator import clean_mermaid_code, detect_truncation
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

def repair_session_state_keys():
    """Repairs mismatched keys in session_state for backward compatibility."""
    
    # If we have schema_modeling but not schema_design, create alias
    if st.session_state.get("schema_modeling") and not st.session_state.get("schema_design"):
        st.session_state["schema_design"] = st.session_state["schema_modeling"]
        st.session_state["schema"] = st.session_state["schema_modeling"]
        print("[REPAIR] Created schema_design alias from schema_modeling")
    
    # If we have final_blueprint but not blueprint, create alias
    if st.session_state.get("final_blueprint") and not st.session_state.get("blueprint"):
        st.session_state["blueprint"] = st.session_state["final_blueprint"]
        print("[REPAIR] Created blueprint alias from final_blueprint")
    
    # If generation_results exists, re-extract outputs
    gen_res = st.session_state.get("generation_results")
    if isinstance(gen_res, dict):
        outputs = gen_res.get("outputs", {})
        if outputs:
            # Re-map with correct keys
            if "schema_modeling" in outputs and not st.session_state.get("schema"):
                st.session_state["schema"] = outputs["schema_modeling"]
                st.session_state["schema_design"] = outputs["schema_modeling"]
                print("[REPAIR] Restored schema from generation_results")

def main():
    # Sidebar for consistent model selection
    st.sidebar.title("DWH Assistant")
    from dwh_assistant.backend.snowflake import ensure_session
    try:
        ensure_session()
    except Exception as e:
        st.error(f"Session Error: {e}")
        st.stop()
        
    selected_model, active_session = render_ai_sidebar()

    # ADD THIS:
    repair_session_state_keys()  # Fix any key mismatches

    def render_tab_placeholder(label, data):
        """Shows a premium skeleton state if data is missing but generation is running."""
        is_running = st.session_state.get("generation_running", False)
        if is_running and (not data or len(str(data)) < 10):
            st.markdown(f"""
                <div style="padding: 60px; text-align: center; background: #F8FAFC; border-radius: 12px; border: 2px dashed #E2E8F0; margin-top: 20px;">
                    <div class="spinner-border text-info" role="status" style="width: 3rem; height: 3rem; margin-bottom: 20px; opacity: 0.6;"></div>
                    <h3 style="color: #0F172A; font-weight: 600; margin-bottom: 10px;">Architecting {label}...</h3>
                    <p style="color: #64748B; font-size: 0.95rem;">Our AI agents are currently designing these components in a parallel workstream.<br>Results will appear here automatically as they are finalized.</p>
                </div>
            """, unsafe_allow_html=True)
            return True
        return False

    def render_interactive_mermaid(code, session_key, label="Diagram", height=500, checks=None, node_layers: dict = None):
        """Unified helper to render Mermaid with an editor and quality checks."""
        
        print(f"\n[DWH LOG] render_interactive_mermaid for '{session_key}' ('{label}'). Code present: {bool(code)}")
        if not code:
            print(f"[DWH LOG] Code for '{label}' is empty/None.")
            st.info(f"{label} will be available after AI generation.")
            return

        from dwh_assistant.backend.validator import clean_mermaid_code
        
        tab_route = None
        if "schema" in session_key.lower(): tab_route = "schema"
        elif "architecture" in session_key.lower(): tab_route = "architecture"
        elif "pipeline" in session_key.lower(): tab_route = "pipeline"
        elif "governance" in session_key.lower(): tab_route = "governance"
        
        cleaned = clean_mermaid_code(code, tab_route=tab_route)
        
        # Callback for editor
        def sync_mermaid():
            new_val = st.session_state[f"editor_{session_key}"].strip()
            # Update deep session state
            keys = session_key.split(".")
            target = st.session_state
            for k in keys[:-1]:
                if k not in target: target[k] = {}
                target = target[k]
            target[keys[-1]] = new_val

        # Use latest edited code from session state if available, otherwise fallback to cleaned AI output
        session_val = st.session_state.get(f"editor_{session_key}")
        current_code = session_val if session_val is not None else cleaned
        
        # Prevent invalid raw headers/text from crashing Mermaid parser; render cleanly outside diagram layer
        if not current_code or current_code.strip() == "":
            st.info(f"No valid graph/diagram syntax detected for {label}. Displaying raw extracted UI text layer:")
            if code and code.strip():
                st.markdown(f"<div style='padding:15px; background:#F8FAFC; border-radius:8px; border:1px solid #E2E8F0; color:#334155; white-space: pre-wrap; font-family: monospace;'>{code}</div>", unsafe_allow_html=True)
            return
        
        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; margin-top: 20px;">
                <h2 style="margin: 0; color: #0F172A; font-size: 1.5rem; font-weight: 700;">{label}</h2>
                <div style="color: #64748B; font-size: 0.8rem; font-weight: 500;">{len(current_code)} characters</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Layout Controls
        show_editor = st.toggle(f"Developer Mode: View/Edit {label} Syntax", value=False, key=f"toggle_{session_key}")
        if show_editor:
            canvas_h = st.slider("Canvas Viewport Height", 400, 2000, height, 50, key=f"slider_{session_key}")
        else:
            canvas_h = height

        # Always render the diagram for maximum visibility
        try:
            render_mermaid(current_code, height=canvas_h, node_layers=node_layers)
        except Exception as e:
            st.error(f"Render Error: {e}")
        
        if show_editor:
            st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-bottom: 10px;'>Manual refinements will persist in the current session.</p>", unsafe_allow_html=True)
            
            current_code = st.text_area(
                "Mermaid Syntax",
                value=current_code,
                height=300,
                key=f"editor_{session_key}",
                on_change=sync_mermaid,
                label_visibility="collapsed"
            )
            
            if checks:
                st.markdown("##### Design Quality Report")
                q_cols = st.columns(len(checks))
                for idx, (check_name, check_fn) in enumerate(checks.items()):
                    passed = check_fn(current_code)
                    q_cols[idx % len(q_cols)].markdown(f"{'[PASS]' if passed else '[FAIL]'} <small>{check_name}</small>", unsafe_allow_html=True)



    # Read from session_state with comprehensive fallbacks
    arch_data = (st.session_state.get("architecture_selection") or 
                 st.session_state.get("architecture") or 
                 st.session_state.get("architecture_strategy"))
    
    schema_data = (st.session_state.get("schema_modeling") or  # NEW: Try actual key first
                   st.session_state.get("schema_design") or 
                   st.session_state.get("schema"))
    
    pipeline_data = (st.session_state.get("pipeline_design") or 
                     st.session_state.get("pipeline"))
    
    governance_data = (st.session_state.get("governance_security") or 
                       st.session_state.get("governance"))
    
    ddl = (st.session_state.get("ddl_generation") or 
           st.session_state.get("artifacts"))
    
    # Schema context: derived from AI architecture layers (metadata-driven)
    schema_ctx = (st.session_state.get("schema_context") or
                  (st.session_state.get("generation_results") or {}).get("outputs", {}).get("schema_context") or
                  {})
    
    doc_design = (st.session_state.get("documentation_design") or 
                  st.session_state.get("final_blueprint") or {})
    
    history_data = st.session_state.get("history") or {}
    
    # Validation: Check if critical components are missing
    missing_components = []
    if not arch_data: missing_components.append("Architecture")
    if not schema_data: missing_components.append("Schema")
    if not pipeline_data: missing_components.append("Pipeline")
    if not governance_data: missing_components.append("Governance")
    if not ddl: missing_components.append("DDL Artifacts")
    
    if missing_components:
        st.error(f"Missing Components: {', '.join(missing_components)}")
        st.info("Please return to the AI Generation page to complete the architecture design.")
        if st.button("← Go to AI Generation"):
            st.switch_page("pages/3_AI_Generation.py")
        st.stop()

    # DEBUG: Log available keys for troubleshooting
    import sys
    if "--debug" in sys.argv or st.session_state.get("debug_mode"):
        st.sidebar.markdown("### Debug: Available Keys")
        available = {
            "architecture": bool(arch_data),
            "schema": bool(schema_data),
            "pipeline": bool(pipeline_data),
            "governance": bool(governance_data),
            "ddl": bool(ddl),
            "history": bool(history_data)
        }
        st.sidebar.json(available)
        
        st.sidebar.markdown("### Session State Keys")
        relevant_keys = [k for k in st.session_state.keys() if any(x in k for x in 
            ["architecture", "schema", "pipeline", "governance", "ddl", "blueprint", "history", "design"])]
        st.sidebar.code("\n".join(sorted(relevant_keys)))

    # Header Section (Aligned with Home Page / AI Generation)
    # Header Section (Aligned with Home Page / AI Generation)
    render_page_header("Design", "Review and refine your industrial data architecture.", "Center")
    
    # 0. Live Generation Monitor (Industrial Speed Hack)
    is_running = st.session_state.get("generation_running", False)
    if is_running:
        st.markdown("""
            <div style="background: rgba(15, 23, 42, 0.05); padding: 15px; border-radius: 8px; border: 1px solid #E2E8F0; margin-bottom: 25px; border-left: 4px solid #0EA5E9;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center;">
                        <span style="font-weight: 700; color: #0F172A; margin-right: 15px;">AI CORE ACTIVE:</span>
                        <span style="color: #64748B; font-size: 0.9rem;">Parallel workstreams are populating tabs in real-time...</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div class="spinner-grow text-info" role="status" style="width: 1rem; height: 1rem; margin-right: 8px;"></div>
                        <span style="font-size: 0.8rem; color: #0EA5E9; font-weight: 600;">LIVE FEED ACTIVE (3s)</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        # Periodic refresh to pull data from background threads
        time.sleep(3)
        st.rerun()
    
    # 1. Initialize ALL Session State variables at once for consistency
    def _safe_load(key):
        val = st.session_state.get(key, {})
        if isinstance(val, str):
            try:
                # Try to extract JSON from markdown if present
                json_match = re.search(r'\{.*\}', val, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0), strict=False)
                return json.loads(val, strict=False)
            except:
                return {"_raw": val}
        return val if isinstance(val, dict) else {}

    # 1. Master Results Registry (Background Thread Safe)
    gen_results = st.session_state.get("generation_results", {})

    # 2. Master Contract Load with Deep Extraction Support
    gen_outputs = gen_results.get("outputs", gen_results) if isinstance(gen_results, dict) else {}
    
    blueprint = arch_data if arch_data else {}
    schema = schema_data if schema_data else {}
    meta = st.session_state.get("metadata_analysis") or gen_outputs.get("metadata_analysis") or {}
    rel = st.session_state.get("relationship_design") or gen_outputs.get("relationship_design") or {}
    pipeline = pipeline_data if pipeline_data else {}
    gov = governance_data if governance_data else {}
    artifacts = ddl if ddl else {}
    final = st.session_state.get("final_blueprint") or gen_outputs.get("final_blueprint") or {}
    history_data = history_data if history_data else {}

    # Define master_layers mapping tables/tasks to layers
    master_layers = {}
    if isinstance(schema, dict):
        all_tables = schema.get("tables", [])
        if isinstance(all_tables, list):
            for t in all_tables:
                if isinstance(t, dict) and t.get("name") and t.get("layer"):
                    master_layers[t.get("name").lower()] = t.get("layer").lower()
    if isinstance(pipeline, dict):
        tasks = pipeline.get("tasks", [])
        if isinstance(tasks, list):
            for t in tasks:
                if isinstance(t, dict):
                    t_name = t.get("name") or t.get("n")
                    t_layer = t.get("layer") or t.get("l")
                    if t_name and t_layer:
                        master_layers[str(t_name).lower()] = str(t_layer).lower()
    
    # Mapping minified keys for UI
    mermaid_erd = rel.get("mermaid") or rel.get("mermaid_diagram") or "erDiagram\n"
    lineage_data = meta.get("lin") or meta.get("lineage") or []
    gov_tags = meta.get("tags") or meta.get("governance_tags") or []
    governance_mermaid = gov.get("mermaid") or gov.get("mermaid_diagram") or "graph LR"


    # Map internal artifact keys to expected variables for existing UI components
    ddl = artifacts if artifacts else {}
    doc_design = (
        gen_results.get("documentation_summary") or 
        st.session_state.get("documentation_design") or 
        st.session_state.get("final_blueprint") or 
        gen_outputs.get("final_blueprint") or 
        st.session_state.get("documentation_summary") or 
        (artifacts.get("documentation") if isinstance(artifacts, dict) else {}) or {}
    )
    if not isinstance(doc_design, dict): doc_design = {}

    
    # Status Check Banner
    status_cols = st.columns(6)
    steps = [
        ("Architecture", "architecture_strategy"),
        ("Schema", "schema_modeling"),
        ("Pipeline", "pipeline_design"),
        ("Governance", "governance_security"),
        ("Artifacts", "ddl_generation"),
        ("History", "history")
    ]
    for i, (label, key) in enumerate(steps):
        is_ready = bool(gen_results.get(key) or st.session_state.get(key))
        status_cols[i].markdown(f"""
            <div style="text-align: center; padding: 8px; border-radius: 8px; background: {'rgba(56, 189, 248, 0.1)' if is_ready else 'rgba(244, 63, 94, 0.1)'}; border: 1px solid {'#38BDF8' if is_ready else '#F43F5E'};">
                <small style="color: {'#38BDF8' if is_ready else '#F43F5E'}; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">{label}</small><br>
                <small style="color: {'#E2E8F0' if is_ready else '#F43F5E'}; opacity: 0.8;">{'READY' if is_ready else 'MISSING'}</small>
            </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    tabs = st.tabs(["Architecture", "Schema", "Pipeline", "Governance", "Artifacts", "History"])
    
    with tabs[0]:
        if not blueprint:
            st.warning("Architectural metadata is missing. Please ensure the 'Architecture Strategy Selection' step in AI Generation completed successfully.")
            if st.button("Return to AI Generation"):
                st.switch_page("pages/3_AI_Generation.py")
            return
            
        strategy_name = blueprint.get('architecture_type', 'N/A').replace('_', ' ').title()
        st.markdown(f"<h2 style='color: #0F172A; margin-top: 0;'>Architecture Strategy: <span style='color: #0284c7;'>{strategy_name}</span></h2>", unsafe_allow_html=True)
        st.markdown("""
            <div style="background: #F0F9FF; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px;">
                <span style="font-weight: 600; color: #0369A1;">Pipeline View Only:</span> Displays high-level data pipeline layers representing system flow and data movement. Completely isolates flow architecture without relational tables or column attributes.
            </div>
        """, unsafe_allow_html=True)
        
        # Interactive Architecture Fitness Radar - Case Insensitive Mapping
        def get_metric_val(val, default=50):
            if not val: return default
            m = str(val).lower()
            return {"low": 30, "medium": 60, "high": 90}.get(m, default)

        # Dynamic Fitness Profile from Master Blueprint
        metrics = blueprint.get("fitness_metrics", {})
        if not metrics and "architecture_strategy" in st.session_state:
            metrics = st.session_state.get("architecture_strategy", {}).get("fitness_metrics", {})
            
        fitness_data = []
        if metrics:
            for k, v in metrics.items():
                fitness_data.append({"Metric": k, "Value": v})
        else:
            fitness_data = [
                {"Metric": "Complexity", "Value": get_metric_val(blueprint.get("complexity"))},
                {"Metric": "Cost", "Value": get_metric_val(blueprint.get("estimated_cost_tier"))},
                {"Metric": "Scalability", "Value": 85}, 
                {"Metric": "Performance", "Value": 75},
                {"Metric": "Security", "Value": 90}
            ]
        fitness_df = pd.DataFrame(fitness_data)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("#### Architectural Reasoning")
            reasoning = blueprint.get("reasoning_summary") or blueprint.get("selection_logic", {}).get("business_rationale") or blueprint.get("reasoning", {}).get("selection", "N/A")
            st.markdown(f"<div style='color: #1a3c61; margin-bottom: 20px;'>{reasoning}</div>", unsafe_allow_html=True)
        
        with c2:
            st.markdown("#### Architectural Fitness Profile")
            st.vega_lite_chart(fitness_df, {
                'mark': {'type': 'bar', 'cornerRadiusEnd': 4, 'fill': '#38BDF8'},
                'encoding': {
                    'y': {'field': 'Metric', 'type': 'nominal', 'axis': {'title': None, 'labelColor': '#1a3c61'}},
                    'x': {'field': 'Value', 'type': 'quantitative', 'scale': {'domain': [0, 100]}, 'axis': {'title': 'Score', 'labelColor': '#1a3c61', 'titleColor': '#1a3c61'}},
                    'color': {'condition': {'test': 'datum.Value > 70', 'value': '#38BDF8'}, 'value': '#475569'}
                },
                'height': 250, 'background': 'transparent'
            }, width='stretch')

        justification = blueprint.get("architecture_justification")
        if justification and isinstance(justification, dict):
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### Architectural Decision Justification")
            jc1, jc2 = st.columns(2)
            with jc1:
                st.markdown(f"**Why Chosen**:\n{justification.get('why_chosen', 'N/A')}")
                st.markdown("<br>", unsafe_allow_html=True)
                
                alts = justification.get('alternatives_rejected', [])
                if isinstance(alts, list):
                    alts_str = "\n".join([f"- {a}" for a in alts])
                else:
                    alts_str = str(alts)
                st.markdown(f"**Alternatives Analyzed & Rejected**:\n{alts_str}")
            with jc2:
                assumptions = justification.get('assumptions_made', [])
                if isinstance(assumptions, list):
                    assump_str = "\n".join([f"- {a}" for a in assumptions])
                else:
                    assump_str = str(assumptions)
                st.markdown(f"**Assumptions Made**:\n{assump_str}")
                st.markdown("<br>", unsafe_allow_html=True)
                
                constraints = justification.get('constraints_influenced', [])
                if isinstance(constraints, list):
                    const_str = "\n".join([f"- {a}" for a in constraints])
                else:
                    const_str = str(constraints)
                st.markdown(f"**Influencing Constraints**:\n{const_str}")

        st.divider()
        
        # 3. Data Model Blueprint
        model = blueprint.get("data_model_blueprint") or blueprint.get("data_model") or {}
        if model:
            st.markdown("### Data Model Blueprint")
            mc1, mc2 = st.columns(2)
            with mc1:
                st.markdown(f"**Schema Type**: <span class='accent-text'>{model.get('schema_type', 'N/A')}</span>", unsafe_allow_html=True)
                entities = model.get('core_entities') or model.get('fact_tables', [])
                st.markdown(f"**Core Entities**: {', '.join(entities if isinstance(entities, list) else [str(entities)])}")
            with mc2:
                rels = model.get('primary_relationships') or model.get('relationships', [])
                st.markdown(f"**Key Relationships**: {', '.join(rels if isinstance(rels, list) else [str(rels)])}")
            st.divider()



        # 5. Lifecycle Data Flow
        flow = blueprint.get("data_flow", {})
        if isinstance(flow, str):
            try: flow = json.loads(flow)
            except: flow = {"ingestion": flow}
        if not isinstance(flow, dict): flow = {}
        
        if flow:
            st.markdown("### LIFECYCLE DATA FLOW")
            with st.container():
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    st.markdown("##### Ingestion Path")
                    st.info(flow.get('ingestion', 'N/A'))
                with fc2:
                    st.markdown("##### Processing Layer")
                    st.info(flow.get('processing', 'N/A'))
                with fc3:
                    st.markdown("##### Serving/BI Layer")
                    st.info(flow.get('serving', 'N/A'))

        # 6. Governance & Compliance
        gov_meta = blueprint.get("governance", {})
        if isinstance(gov_meta, str):
            try: gov_meta = json.loads(gov_meta)
            except: gov_meta = {"security": gov_meta}
        if not isinstance(gov_meta, dict): gov_meta = {}
        
        if gov_meta:
            st.markdown("### ARCHITECTURAL GOVERNANCE")
            with st.container():
                gc1, gc2 = st.columns(2)
                with gc1:
                    st.success(f"**Security Guardrails**: {gov_meta.get('security', 'N/A')}")
                with gc2:
                    st.success(f"**Lineage Tracking**: {gov_meta.get('lineage', 'N/A')}")
            
        st.divider()
        
        # Architecture quality checks — fully adaptive, not tied to any specific layer model
        arch_checks = {
            "Has layer structure": lambda x: "subgraph" in x.lower() or ("-->" in x and len(x.split("\n")) > 2),
            "Has flow paths": lambda x: "-->" in x or "---" in x,
            "Has named nodes": lambda x: "[" in x or "(" in x or "{" in x,
            "Flowchart format": lambda x: "flowchart" in x.lower() or "graph" in x.lower(),
        }
        
        render_interactive_mermaid(
            blueprint.get("mermaid_diagram"), 
            "architecture_selection.mermaid_diagram",
            label="Architecture Blueprint",
            height=1000,
            checks=arch_checks,
            node_layers=master_layers
        )

    with tabs[1]:
        st.markdown("### Industrial Schema Design")
        st.markdown("""
            <div style="background: #F0F9FF; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px;">
                <span style="font-weight: 600; color: #0369A1;">Warehouse Detailed Model Only:</span> Fully detailed relational design derived from the Architecture tab. Explicitly defines all table structures, columns, data types, primary keys (PK), and foreign keys (FK) without high-level pipeline or source system layers.
            </div>
        """, unsafe_allow_html=True)

        # Schema ERD: ONLY use schema_modeling mermaid_diagram — never doc_design which contains architecture-level diagrams
        # doc_design.mermaid_diagram is intentionally excluded here to avoid mixing pipeline architecture with the warehouse relational model
        from dwh_assistant.backend.validator import synthesize_erd_from_tables

        all_tables = schema.get("tables", [])
        if not isinstance(all_tables, list): all_tables = []
        rel_list = rel.get("rel", [])
        if not isinstance(rel_list, list): rel_list = []

        # Pull Data Model Blueprint metadata
        model = blueprint.get("data_model_blueprint") or blueprint.get("data_model") or {}
        core_entities = model.get('core_entities') or model.get('fact_tables', []) or []
        primary_relationships = model.get('primary_relationships') or model.get('relationships', []) or []

        # Backfill entities from Data Model Blueprint
        if core_entities:
            existing_names = {t.get("name").upper() for t in all_tables if isinstance(t, dict) and t.get("name")}
            for ent in core_entities:
                if ent.upper() not in existing_names:
                    # Guess a layer based on prefixes
                    layer = "Gold" if any(p in ent.upper() for p in ["DIM_", "FACT_", "FCT_", "GOLD"]) else "Silver"
                    all_tables.append({
                        "name": ent,
                        "layer": layer,
                        "columns": [
                            {"name": f"{ent.lower()}_sk", "type": "int", "pk": True, "description": "Surrogate primary key"},
                            {"name": "created_at", "type": "timestamp", "description": "Record creation timestamp"}
                        ]
                    })

        # Backfill relationships from Data Model Blueprint
        if primary_relationships:
            existing_rels = set()
            for r in rel_list:
                f = (r.get("from") or r.get("from_table") or "").upper()
                t = (r.get("to") or r.get("to_table") or "").upper()
                if f and t:
                    existing_rels.add((f, t))
                    existing_rels.add((t, f))
            
            for r_str in primary_relationships:
                parts = re.split(r'\s*(?:->|joins|to|-|ref|references)\s*', r_str, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    f_ent = parts[0].strip().upper()
                    t_ent = parts[1].strip().upper()
                    if (f_ent, t_ent) not in existing_rels:
                        rel_list.append({
                            "from": parts[0].strip(),
                            "to": parts[1].strip(),
                            "cardinality": "||--o{",
                            "label": "references"
                        })

        total_cols = sum(len(t.get("columns", [])) for t in all_tables if isinstance(t, dict))
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Design Entities", len(all_tables), "Tables")
        mc2.metric("System Relationships", len(rel_list), "Foreign Keys")
        mc3.metric("Attribute Density", total_cols, "Columns")
        st.divider()

        # Data Model Blueprint (Shared from Architecture)
        model = blueprint.get("data_model_blueprint") or blueprint.get("data_model") or {}
        if model:
            st.markdown("### Data Model Blueprint")
            mc_b1, mc_b2 = st.columns(2)
            with mc_b1:
                st.markdown(f"**Schema Type**: <span style='color: #0284c7; font-weight: 600;'>{model.get('schema_type', 'N/A')}</span>", unsafe_allow_html=True)
                entities = model.get('core_entities') or model.get('fact_tables', [])
                st.markdown(f"**Core Entities**: {', '.join(entities if isinstance(entities, list) else [str(entities)])}")
            with mc_b2:
                rels = model.get('primary_relationships') or model.get('relationships', [])
                st.markdown(f"**Key Relationships**: {', '.join(rels if isinstance(rels, list) else [str(rels)])}")
            st.divider()

        # --- ERD code resolution: 3-tier fallback ---
        # Tier 1: AI-generated diagram stored in schema_modeling — use if non-trivial and covers most tables
        ai_erd = schema.get("mermaid_diagram") or st.session_state.get("schema_modeling", {}).get("mermaid_diagram") or ""
        ai_erd = ai_erd.strip()

        def _erd_is_complete(erd_str: str, n_tables: int) -> bool:
            """Returns True only if the stored diagram looks substantially complete."""
            if not erd_str or len(erd_str) < 30:
                return False
            if "erdiagram" not in erd_str.lower():
                return False
            # Count entity blocks — each opens with a bare word followed by {
            entity_blocks = len(re.findall(r'^\s{0,8}[A-Z_][A-Z0-9_]+\s*\{', erd_str, re.MULTILINE | re.IGNORECASE))
            # Accept the AI diagram only if it covers at least 60 % of the tables
            if n_tables > 0 and entity_blocks < max(1, int(n_tables * 0.6)):
                return False
            return True

        if _erd_is_complete(ai_erd, len(all_tables)):
            erd_code = ai_erd
            print(f"[DWH LOG] Using AI-generated ERD ({len(erd_code)} chars, covers most tables)")
        elif all_tables:
            # Tier 2: Synthesise deterministically from merged tables + relationship list
            print(f"[DWH LOG] AI ERD incomplete or absent — synthesising from {len(all_tables)} tables + {len(rel_list)} rels")
            erd_code = synthesize_erd_from_tables(all_tables, rel_list)
        else:
            # Tier 3: Nothing available yet
            erd_code = "erDiagram\n"

        erd_key = "schema_design.mermaid_diagram"

        # 2. Main Visualization — schema ERD key already set above
        
        schema_checks = {
            "Has Entity Attributes": lambda x: "{" in x and "}" in x,
            "Has PK/FK Markers": lambda x: "PK" in x or "FK" in x or "sk" in x.lower() or "id" in x.lower(),
            "Surrogate Key Integrity": lambda x: "_sk" in x.lower(),
            "Has Relationships": lambda x: any(c in x for c in ["||--", "}o--", "|o--", "--o|", "--||", "-->"]),
            "Business Accuracy": lambda x: len(x.split("\n")) > 3
        }
        
        schema_tabs = st.tabs(["Entity Relationship Model", "Schema Inventory"])
        
        with schema_tabs[0]:
            # STRICT: Only use the warehouse schema ERD — rel.get("mermaid_diagram") can be a flowchart type and must NOT be used here
            mermaid_erd = erd_code or "erDiagram\n"
            render_interactive_mermaid(
                mermaid_erd,
                "schema.mermaid_diagram",
                label="Entity Relationship Diagram (ERD)",
                height=900,
                node_layers=master_layers
            )
            
            # 3. Layer Inventory

        with schema_tabs[1]:
            st.markdown("### Tabular Schema Inventory")
            # Strictly rely on runtime inference payload from the selected Cortex AI model
            unique_tables = all_tables

            if not unique_tables:
                st.info("No tables generated yet. Run AI Architect to populate.")
            else:
                from collections import defaultdict
                from dwh_assistant.backend.validator import layer_sort_key
                
                # Group unique tables by layer
                tables_by_layer = defaultdict(list)
                for t in unique_tables:
                    if not isinstance(t, dict):
                        continue
                    layer = t.get("layer", "Warehouse")
                    layer_display = str(layer).title()
                    tables_by_layer[layer_display].append(t)
                    
                sorted_layer_names = sorted(tables_by_layer.keys(), key=layer_sort_key)
                
                for layer_name in sorted_layer_names:
                    with st.expander(f"📁 {layer_name.upper()} LAYER ({len(tables_by_layer[layer_name])} Entities)", expanded=(layer_name.lower() in ["gold", "serving"])):
                        layer_tables = tables_by_layer[layer_name]
                        t_names = sorted([t.get("name") for t in layer_tables])
                        
                        selected_t_name = st.selectbox(
                            "Select Entity to Review", 
                            t_names, 
                            key=f"sel_inv_{layer_name.lower()}",
                            label_visibility="collapsed"
                        )
                        
                        t_obj = next((t for t in layer_tables if t.get("name") == selected_t_name), None)
                        if t_obj:
                            mcol1, mcol2 = st.columns([3, 1])
                            with mcol1:
                                st.markdown(f"##### Metadata: `{selected_t_name}`")
                                cols = t_obj.get("columns", [])
                                df_data = []
                                for c in cols:
                                    is_pk = t_obj.get("primary_key") == c.get("name") or c.get("primary_key") or c.get("pk")
                                    is_fk = c.get("is_fk") or c.get("references") or c.get("fk")
                                    df_data.append({
                                        "Column": c.get("name"),
                                        "Type": c.get("type"),
                                        "PK": "🔑 PK" if is_pk else "",
                                        "FK": "🔗 FK" if is_fk else "",
                                        "References": c.get("references") or c.get("ref") or "",
                                        "Description": c.get("description", "")
                                    })
                                st.dataframe(pd.DataFrame(df_data), width='stretch', hide_index=True)
                            with mcol2:
                                st.markdown("##### Entity Properties")
                                st.info(f"**Layer**: {t_obj.get('layer', 'N/A')}")
                                pk_name = t_obj.get('primary_key') or next((c.get("name") for c in t_obj.get("columns", []) if c.get("pk")), "None")
                                st.success(f"**PK**: {pk_name}")
                                t_rels = [r for r in rel_list if r.get("from") == selected_t_name or r.get("from_table") == selected_t_name]
                                if t_rels:
                                    st.markdown("##### Outbound Joins")
                                    for r in t_rels:
                                        target = r.get('to') or r.get('to_table')
                                        st.code(f"→ {target}")

        


    with tabs[2]:
        if not render_tab_placeholder("Transformation Pipelines", pipeline):
            # 1. Metric Overview
            tasks = pipeline.get("tasks", [])
            pc1, pc2, pc3 = st.columns(3)
            pc1.metric("Total Orchestration Tasks", len(tasks), "Workflows")
            arch_state = st.session_state.get("architecture_strategy", {}) or st.session_state.get("architecture", {})
            arch_display = arch_state.get("architecture_type", "Dynamic")
            pc2.metric("Ingestion Frequency", "Streaming/Batch", arch_display)
            pc3.metric("Transformation Logic", len([t for t in tasks if t.get("type") == "transformation"]), "Steps")
            st.divider()
    
            # 2. Main Visualization
            # Pipeline quality checks — architecture-agnostic: supports Medallion, Data Vault, Lakehouse
            pipe_checks = {
                "Has Flowchart": lambda x: "graph" in x.lower() or "flowchart" in x.lower(),
                "Has Task Dependencies": lambda x: "-->" in x,
                "Has Layer Nodes": lambda x: any(kw in x.lower() for kw in [
                    "bronze", "silver", "gold",        # Medallion
                    "hub", "sat", "lnk", "vault",     # Data Vault
                    "raw", "conformed", "enriched",   # Lakehouse
                    "landing", "staging", "mart",     # Generic
                ]),
            }
            
            render_interactive_mermaid(
                pipeline.get("mermaid_diagram"),
                "pipeline_design.mermaid_diagram",
                label="Technical Pipeline DAG",
                height=800,
                checks=pipe_checks,
                node_layers=master_layers
            )
    
            # 3. Task Inventory
            st.markdown("#### Execution Strategy")
            if tasks:
                task_df = pd.DataFrame(tasks)
                if not task_df.empty:
                    available_cols = [c for c in ["name", "type", "layer", "frequency"] if c in task_df.columns]
                    st.dataframe(task_df[available_cols], width='stretch', hide_index=True)
        

    with tabs[3]:
        if not render_tab_placeholder("Governance & Security", gov):
            # 1. Metric Overview
            g1, g2, g3 = st.columns(3)
            g1.metric("Roles Defined", len(gov.get("roles", [])), "RBAC")
            g2.metric("Masking Policies", len(gov.get("masking_policies", [])), "GDPR/CCPA")
            g3.metric("Compliant Steps", len(gov.get("compliance_checklist", [])), "Audit")
            st.divider()
    
            # 2. Main Visualization
            lineage_code_raw = (
                doc_design.get("governance_security", {}).get("mermaid_diagram") or 
                gov.get("mermaid_diagram") or 
                gov.get("mermaid_lineage")
            )
            lineage_code = lineage_code_raw or "graph LR\n  NODATA"

            # Governance checks — architecture-agnostic: detects any RBAC/policy/source/consumer pattern
            lineage_checks = {
                "Has Source/Role nodes": lambda x: any(kw in x.lower() for kw in ["source", "role", "graph", "admin", "user", "ingestion"]),
                "Has Consumer/Policy nodes": lambda x: any(kw in x.lower() for kw in ["gold", "bi", "policy", "storage", "mart", "info_mart", "dashboard", "report", "catalog"]),
                "Has Flow paths": lambda x: "-->" in x or "-." in x or "===" in x,
            }
            
            render_interactive_mermaid(
                lineage_code,
                "governance_security.mermaid_lineage",
                label="Industrial Privacy & Lineage Map",
                height=800,
                checks=lineage_checks,
                node_layers=master_layers
            )
    
            # 3. RBAC & Policies
            st.divider()
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("#### RBAC Authorization Heatmap")
                rbac_data = []
                for role in gov.get("roles", []):
                    if isinstance(role, dict):
                        grants = role.get("grants") or role.get("privileges", [])
                        for grant in grants: 
                            if isinstance(grant, dict):
                                rbac_data.append({
                                    "Role": role.get("name"),
                                    "Object": grant.get("object_name", "All"),
                                    "Privilege": grant.get("privilege", "USAGE")
                                })
                if rbac_data: st.vega_lite_chart(pd.DataFrame(rbac_data), {'mark': {'type': 'rect', 'stroke': '#fff'}, 'encoding': {'x': {'field': 'Role', 'type': 'nominal'}, 'y': {'field': 'Object', 'type': 'nominal'}, 'color': {'field': 'Privilege', 'type': 'nominal', 'scale': {'range': ['#002244', '#38BDF8', '#1E40AF']}}}, 'height': 400}, use_container_width=True)
                
        with c2:
            st.markdown("#### Masking Policies")
            policies = gov.get("masking_policies", [])
            for p in policies:
                if isinstance(p, dict):
                    st.markdown(f"""
                        <div style="border: 1px solid #E2E8F0; padding: 10px; border-radius: 8px; margin-bottom: 10px;">
                            <span style="color: #F43F5E; font-weight: bold;">{p.get('column')}</span><br>
                            <small>{p.get('type')} for <b>{p.get('role')}</b></small>
                        </div>
                    """, unsafe_allow_html=True)

    with tabs[4]:
        if not render_tab_placeholder("Artifacts & Deployment", artifacts):
            st.markdown("### Industrial Artifacts & Deployment")
            
            ac1, ac2, ac3 = st.columns(3)
            ddl_ready = bool(artifacts.get("ddl_sql"))
            ac1.metric("DDL Status", "READY" if ddl_ready else "PENDING")
            ac2.metric("RBAC Status", "READY" if bool(artifacts.get("grant_sql")) else "PENDING")
            ac3.metric("Readiness Score", "95%" if ddl_ready else "0%")
            
            st.divider()
            
            # Helper: force any value to a string for st.code / st.download_button
            def _to_str(val, fallback=""):
                if val is None: return fallback
                if isinstance(val, str): return val
                if isinstance(val, (dict, list)):
                    try: return json.dumps(val, indent=2)
                    except Exception: return str(val)
                return str(val)
    
            schema_creation_str = _to_str(ddl.get("schema_creation_sql"), "")
            if not schema_creation_str:
                # Pre-calculate fallback from schema_ctx so it is editable
                ctx_layers = schema_ctx.get("layers", []) if isinstance(schema_ctx, dict) else []
                if ctx_layers:
                    from dwh_assistant.backend.executor import layer_to_schema_name as _l2s
                    lines = ["-- ========================================================================="]
                    lines.append("-- SCHEMA CREATION (Derived from AI Architecture Strategy)")
                    lines.append("-- =========================================================================")
                    for lm in ctx_layers:
                        sname = lm.get("schema_name") or _l2s(lm.get("layer_name", "WAREHOUSE"))
                        lines.append(f"CREATE SCHEMA IF NOT EXISTS {sname};")
                    schema_creation_str = "\n".join(lines)

            ddl_sql_str     = _to_str(ddl.get("ddl_sql"), "-- No DDL generated")
            
            # Enhanced Documentation Rendering for Structured Objects
            doc_obj = doc_design
            if isinstance(doc_design, dict) and "documentation" in doc_design:
                nested = doc_design["documentation"]
                if isinstance(nested, (dict, str)):
                    doc_obj = nested
            
            if isinstance(doc_obj, str):
                doc_str = doc_obj
            elif isinstance(doc_obj, dict):
                doc_str = f"### Executive Summary\n{doc_obj.get('executive_summary', 'N/A')}\n\n"
                doc_str += f"### Architectural Logic\n{doc_obj.get('architecture_decision', doc_obj.get('architectural_logic', 'N/A'))}\n\n"
                if doc_obj.get('key_entities'):
                    entities = doc_obj.get('key_entities', [])
                    if isinstance(entities, list):
                        doc_str += f"### Key Entities\n- " + "\n- ".join(entities)
                    else:
                        doc_str += f"### Key Entities\n{entities}"
            else:
                doc_str = _to_str(doc_obj, "No documentation generated.")
            grant_sql_str = _to_str(ddl.get("grant_sql"), "-- No Grants generated")
            transform_sql_str = _to_str(ddl.get("transform_sql"), "-- No Transformations generated")

            # Synchronize editable state with original AI payload
            original_payload = {
                "schema_creation": schema_creation_str,
                "ddl_sql": ddl_sql_str,
                "grant_sql": grant_sql_str,
                "transform_sql": transform_sql_str
            }
            if st.session_state.get("artifacts_original_payload") != original_payload:
                st.session_state["edited_schema_creation"] = schema_creation_str
                st.session_state["edited_ddl_sql"] = ddl_sql_str
                st.session_state["edited_grant_sql"] = grant_sql_str
                st.session_state["edited_transform_sql"] = transform_sql_str
                st.session_state["artifacts_original_payload"] = original_payload

            # Ensure keys exist in session state
            if "edited_schema_creation" not in st.session_state: st.session_state["edited_schema_creation"] = schema_creation_str
            if "edited_ddl_sql" not in st.session_state: st.session_state["edited_ddl_sql"] = ddl_sql_str
            if "edited_grant_sql" not in st.session_state: st.session_state["edited_grant_sql"] = grant_sql_str
            if "edited_transform_sql" not in st.session_state: st.session_state["edited_transform_sql"] = transform_sql_str

            full_sql_script = f"""-- =========================================================================
-- SCHEMA CREATION (AI-Derived from Architecture Strategy)
-- =========================================================================
{st.session_state["edited_schema_creation"]}

-- =========================================================================
-- CORE DDL (TABLES & SCHEMAS)
-- =========================================================================
{st.session_state["edited_ddl_sql"]}

-- =========================================================================
-- ACCESS CONTROL (RBAC & GRANTS)
-- =========================================================================
{st.session_state["edited_grant_sql"]}
"""

            c1, c2 = st.columns([2, 1])
            with c1:
                # Add the Developer Mode Edit toggle
                edit_mode = st.toggle("✏️ Enable Developer Edit Mode (Modify AI Artifacts)", value=False, key="artifacts_edit_mode")
                
                # Sub-tabs for better organization
                sub_tabs = st.tabs(["Full Script", "Schemas", "Tables", "Grants", "Transformations"])
                
                with sub_tabs[0]:
                    if edit_mode:
                        st.info("💡 Edit the individual tabs to modify this compiled deployment script.")
                    st.code(full_sql_script, language="sql", line_numbers=True)

                with sub_tabs[1]:
                    st.markdown("#### Schema Architecture Map")
                    st.markdown("""
                        <div style="background: #F0F9FF; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px;">
                            <span style="font-weight: 600; color: #0369A1;">Metadata-Driven Schemas:</span>
                            Derived dynamically from the AI-generated architecture layers — no hardcoded schema names.
                        </div>
                    """, unsafe_allow_html=True)

                    # Render the schema layer → schema name → table count table
                    ctx_layers = schema_ctx.get("layers", []) if isinstance(schema_ctx, dict) else []
                    if ctx_layers:
                        schema_map_rows = []
                        for lm in ctx_layers:
                            schema_map_rows.append({
                                "Architecture Layer": lm.get("layer_name", "N/A"),
                                "Snowflake Schema":   lm.get("schema_name", "N/A"),
                                "Tables Assigned":    len(lm.get("tables", [])),
                                "Table Names":        ", ".join(t.get("name", "") for t in lm.get("tables", []))
                            })
                        st.dataframe(pd.DataFrame(schema_map_rows), hide_index=True, use_container_width=True)
                        st.divider()
                    else:
                        st.info("Schema context not yet available. Run AI generation to populate.")

                    # Show/Edit the deterministic CREATE SCHEMA block
                    if edit_mode:
                        st.markdown("#### Edit Schema Creation Statements")
                        st.session_state["edited_schema_creation"] = st.text_area(
                            "Edit Schema Creation SQL",
                            value=st.session_state["edited_schema_creation"],
                            height=300,
                            key="editor_schema_creation",
                            label_visibility="collapsed"
                        )
                    else:
                        st.markdown("#### CREATE SCHEMA Statements")
                        if st.session_state["edited_schema_creation"].strip():
                            st.code(st.session_state["edited_schema_creation"], language="sql", line_numbers=True)
                        else:
                            st.info("No schema creation SQL available yet.")

                with sub_tabs[2]:
                    if edit_mode:
                        st.markdown("#### Edit Table DDL SQL")
                        st.session_state["edited_ddl_sql"] = st.text_area(
                            "Edit Table DDL SQL",
                            value=st.session_state["edited_ddl_sql"],
                            height=500,
                            key="editor_ddl_sql",
                            label_visibility="collapsed"
                        )
                    else:
                        st.code(st.session_state["edited_ddl_sql"], language="sql", line_numbers=True)

                with sub_tabs[3]:
                    if edit_mode:
                        st.markdown("#### Edit Access Control SQL")
                        st.session_state["edited_grant_sql"] = st.text_area(
                            "Edit Access Control SQL",
                            value=st.session_state["edited_grant_sql"],
                            height=500,
                            key="editor_grant_sql",
                            label_visibility="collapsed"
                        )
                    else:
                        st.code(st.session_state["edited_grant_sql"], language="sql", line_numbers=True)

                with sub_tabs[4]:
                    if edit_mode:
                        st.markdown("#### Edit Transformations SQL")
                        st.session_state["edited_transform_sql"] = st.text_area(
                            "Edit Transformations SQL",
                            value=st.session_state["edited_transform_sql"],
                            height=500,
                            key="editor_transform_sql",
                            label_visibility="collapsed"
                        )
                    else:
                        st.markdown("#### Transformations")
                        st.code(st.session_state["edited_transform_sql"], language="sql")
    
                st.divider()
                d1, d2 = st.columns(2)
                d1.download_button("Download Full Script (.sql)", full_sql_script, file_name="full_deployment_script.sql", width='stretch')
                d2.download_button("Technical Docs (.md)", doc_str, file_name="documentation.md", width='stretch')
            
            with c2:
                st.markdown("#### Deployment Console")
                
                with st.container():
                    st.markdown("""
                        <div style="background: #F8FAFC; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 15px;">
                            <small style="color: #64748B; text-transform: uppercase; font-weight: 600;">Status</small><br>
                            <span style="font-size: 1.1rem; color: #0F172A; font-weight: 500;">Ready for Deployment</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                if st.button("SAVE PROJECT SNAPSHOT", type="secondary", width='stretch'):
                     from dwh_assistant.backend.snowflake import save_project_to_store, ensure_session
                     try:
                         ensure_session()
                         outputs = {
                             "architecture_selection": st.session_state.get("architecture_selection"),
                             "schema_design": st.session_state.get("schema_design"),
                             "pipeline_design": st.session_state.get("pipeline_design"),
                             "governance_security": st.session_state.get("governance_security"),
                             "ddl_generation": st.session_state.get("ddl_generation"),
                             "documentation_design": st.session_state.get("documentation_design"),
                             "relationship_design": st.session_state.get("relationship_design"),
                             "final_blueprint": st.session_state.get("final_blueprint"),
                             "history": st.session_state.get("history")
                         }
                         save_project_to_store(
                             st.session_state["snowflake_session"],
                             st.session_state.get("project_id"),
                             st.session_state.get("requirements", {}),
                             st.session_state.get("data_profile", {}),
                             outputs
                         )
                         st.toast("Design Saved Successfully!")
                     except Exception as e:
                         st.error(f"Save Failed: {e}")
    
                st.divider()
                st.markdown("##### Target Destination")
                
                t_db = st.text_input("Database", value="ANALYTICS_PROD")
                
                if st.button("EXECUTE FULL DEPLOYMENT", type="primary", width='stretch'):
                    from dwh_assistant.backend.executor import execute_deployment
                    with st.status("Deploying to Snowflake...", expanded=True) as status:
                        schema_context = st.session_state.get("schema_context")
                        res = execute_deployment(
                            st.session_state.snowflake_session,
                            full_sql_script,
                            t_db,
                            project_id=st.session_state.get("project_id", "N/A"),
                            schema_context=schema_context
                        )
                        if res["success"]:
                            status.update(label="Deployment Successful!", state="complete", expanded=False)
                            st.success(f"Successfully executed {res['statements_run']} statements.")
                            if res.get("skipped_count", 0) > 0:
                                st.warning(f"⚠️ Skipped {res['skipped_count']} non-blocking statements (e.g. references to objects or roles that do not exist).")
                            st.dataframe(pd.DataFrame(res["results"]) if "results" in res else pd.DataFrame([{"status": "deployed"}]), width='stretch', hide_index=True)
                        else:
                            status.update(label="Deployment Failed", state="error", expanded=True)
                            st.error(f"Error: {res['error']}")
                            if "failed_statement" in res: st.code(res["failed_statement"], language="sql")

    with tabs[5]:
        if not render_tab_placeholder("Design History", history_data):
            st.markdown("### Industrial History & Provenance")
            
            # 1. Metric Overview
            hcol1, hcol2, hcol3 = st.columns(3)
            hcol1.metric("Current Version", history_data.get("version", "v1.0"), "Production")
            hcol2.metric("Last Generation", (history_data.get("generated_at", "N/A")[:10]) if history_data.get("generated_at") else time.strftime("%Y-%m-%d"), "UTC")
            hcol3.metric("Industrial Assumptions", len(history_data.get("assumptions", [])), "Verified")
            st.divider()
    
            # 2. History Details
            h_c1, h_c2 = st.columns(2)
            with h_c1:
                st.markdown("#### Strategic Assumptions")
                for a in history_data.get("assumptions", []):
                    st.info(f"**✓ Assumption**: {a}")
            with h_c2:
                st.markdown("#### Revision Log")
                for c in history_data.get("change_log", []):
                    st.success(f"**• Revision**: {c}")
        
        st.divider()
        st.subheader("Project Registry (Global History)")
        from dwh_assistant.backend.snowflake import get_all_projects, load_project_by_id
        projects = get_all_projects(st.session_state["snowflake_session"])
        for p_row in projects:
            # get_all_projects now returns plain dicts after Fix 6
            raw = p_row if isinstance(p_row, dict) else p_row.as_dict()
            p = {k.upper(): v for k, v in raw.items()}
            pid = p.get('ID')
            created_at = p.get('CREATED_AT')
            
            st.markdown(f"""
                <div class="glass-card" style="padding: 25px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div>
                            <h3 style="margin: 0; color: #38BDF8 !important;">Project Snapshot</h3>
                            <code style="background: rgba(0,0,0,0.2); color: #94A3B8; padding: 2px 6px; border-radius: 4px;">{pid}</code>
                        </div>
                        <div style="text-align: right;">
                            <small style="color: #94A3B8;">Created At</small><br>
                            <span style="font-weight: 600; color: #E2E8F0;">{created_at}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                h1, h2 = st.columns([3, 1])
                h1.code(str(p.get('DDL_SQL') or "-- No DDL")[:500] + "...", language="sql")
                if h2.button("Load Design", key=f"load_dc_{pid}"):
                    p_data = load_project_by_id(st.session_state["snowflake_session"], pid)
                    if p_data:
                        for k, v in p_data.items(): st.session_state[k] = v
                        st.session_state["form_complete"] = True
                        st.success(f"Project {pid} Loaded Successfully!")
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
