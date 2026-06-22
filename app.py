from __future__ import annotations
from pathlib import Path

import pandas as pd
import json
import re

import math
import time

from concurrent.futures import ThreadPoolExecutor

import streamlit as st
# ============================================================
# REGRESSION LOCK v1.9.29 — JS HTML RUNNER WITHOUT COMPONENTS.HTML
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# v1.9.27 ghost fix needs JavaScript execution.
# components.html works but prints noisy Streamlit deprecation logs.
#
# Use st.html(..., unsafe_allow_javascript=True) instead.
# This wrapper accepts old height/width kwargs so existing calls stay simple.
#
# Required tests:
# 1. No repeated terminal warnings about st.components.v1.html.
# 2. First upload screen: upload block visible.
# 3. Processing screen: ghost hero/uploader elements hidden.
# 4. Back → upload screen: upload block visible again.
# ============================================================
# === COSTERLY_HTML_JS_RUNNER_V1_9_29_START ===
def costerly_html_js_runner_v1_9_29(html_source: str, **_ignored_kwargs):
    st.html(
        html_source,
        unsafe_allow_javascript=True,
    )
# === COSTERLY_HTML_JS_RUNNER_V1_9_29_END ===

from agents.detection_agent import run_detection_agent
from db.supabase_client import get_supabase_client
from db.repositories import (
    fetch_company_data,
    fetch_estimate_driver_quantities,
    fetch_rfq_detected_objects,
    fetch_rfq_run,
    upsert_rfq_detection_result,
)
from engine.routing import select_routes
from engine.estimate_engine import calculate_work_hours
from styles import apply_css
from styles import apply_custom_upload_block_css_v1_9
import os
import textwrap


st.set_page_config(
    page_title="costerly.ai",
    page_icon="/Users/qb/rfq-estimate-app/assets/brand/costelry_mark_cherry.svg",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_css()
apply_custom_upload_block_css_v1_9()


def get_company_id() -> str:
    return st.secrets.get("COMPANY_ID", "001")

def get_detection_agent_mode() -> str:
    return str(st.secrets.get("DETECTION_AGENT_MODE", "mock")).strip().lower()


def init_state():
    if "screen" not in st.session_state:
        st.session_state.screen = "upload"

    if "current_run_id" not in st.session_state:
        st.session_state.current_run_id = None

    if "uploaded_file_name" not in st.session_state:
        st.session_state.uploaded_file_name = None

    if "uploaded_file_bytes" not in st.session_state:
        st.session_state.uploaded_file_bytes = None


def go_to(screen: str):
    st.session_state.screen = screen
    st.rerun()


@st.cache_data(show_spinner=False)
def load_company_data_cached(company_id: str):
    client = get_supabase_client()
    return fetch_company_data(client, company_id)


# -----------------------------------------------------------------------------
# Product flow
# -----------------------------------------------------------------------------


# COMMON_POST_UPLOAD_LAYOUT_V1
def apply_post_upload_layout_css() -> None:
    st.markdown(
        """
<style>
:root {
    --post-upload-width: min(960px, calc(100vw - 56px));
    --post-upload-top: 88px;
}

html,
body,
.stApp,
div[data-testid="stAppViewContainer"],
section.main {
    background: #F1EFEF !important;
}

/* Canonical layout for all screens after Upload. */
.block-container {
    width: var(--post-upload-width) !important;
    max-width: none !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-top: var(--post-upload-top) !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    padding-bottom: 72px !important;
    background: #F1EFEF !important;
}

/* Upload screen remains its own centered exception. */
.stApp:has(.upload-screen-active) .block-container {
    width: 100% !important;
    max-width: none !important;
    padding: 0 !important;
}

.post-upload-title {
    font-family: var(--mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace) !important;
    color: #8049C6 !important;
    font-size: 40px !important;
    line-height: 1.1 !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em !important;
    margin: 0 0 var(--s5) 0 !important;
    padding: 0 !important;
}

.post-upload-subtitle {
    color: var(--ink-500, rgba(0, 0, 0, 0.52)) !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
    margin: calc(-1 * var(--s3, 16px)) 0 var(--s5, 32px) 0 !important;
    max-width: 760px !important;
}

.custom-progress-track {
    width: 100%;
    height: 12px;
    border-radius: 999px;
    background: #D85A5A;
    overflow: hidden;
}

.custom-progress-fill {
    height: 100%;
    min-width: 0;
    border-radius: 999px;
    background: #8049C6;
    transition: width 140ms linear;
}

.custom-progress-fill.is-running {
    background: linear-gradient(
        90deg,
        #8049C6 0%,
        #9A65DF 52%,
        #8049C6 100%
    );
}

/* White object-card substrate for File Review and later pages. */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border: 1px solid rgba(42, 31, 44, 0.14) !important;
    border-radius: 16px !important;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.055) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border-radius: 16px !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_post_upload_header(title: str, subtitle: str | None = None) -> None:
    apply_post_upload_layout_css()

    st.markdown(
        f"<h1 class='post-upload-title'>{title}</h1>",
        unsafe_allow_html=True,
    )

    if subtitle:
        st.markdown(
            f"<div class='post-upload-subtitle'>{subtitle}</div>",
            unsafe_allow_html=True,
        )



def detect_uploaded_file_type(file_name: str) -> str:
    """Return a simple file type label for uploaded RFQ packages."""
    suffix = Path(file_name).suffix.lower().lstrip(".")

    if suffix == "pdf":
        return "pdf"
    if suffix in {"xlsx", "xls", "csv"}:
        return "spreadsheet"
    if suffix in {"png", "jpg", "jpeg"}:
        return "image"
    if suffix in {"dwg", "dxf"}:
        return "cad"

    return suffix or "unknown"


# First screen: minimal RFQ package upload.
# === COSTERLY_CUSTOM_UPLOAD_DRAGOVER_JS_V1_9_START ===
def install_custom_upload_dragover_js_v1_9():
    costerly_html_js_runner_v1_9_29(
        """
<script>
(() => {
  const parentDoc = window.parent.document;
  const markerId = "COSTERLY_CUSTOM_UPLOAD_DRAGOVER_JS_V1_9_2";

  const oldMarkers = [
    "COSTERLY_CUSTOM_UPLOAD_DRAGOVER_JS_V1_9",
    "COSTERLY_CUSTOM_UPLOAD_DRAGOVER_JS_V1_9_1",
    "COSTERLY_CUSTOM_UPLOAD_DRAGOVER_JS_V1_9_2"
  ];

  for (const id of oldMarkers) {
    const old = parentDoc.getElementById(id);
    if (old) old.remove();
  }

  const script = parentDoc.createElement("script");
  script.id = markerId;

  script.textContent = `
(() => {
  const DROPZONE_SELECTOR = 'section[data-testid="stFileUploaderDropzone"]';
  const DRAG_CLASS = 'costerly-upload-dragover';

  let clearTimer = null;

  function getDropzones() {
    return Array.from(document.querySelectorAll(DROPZONE_SELECTOR));
  }

  function hasFiles(event) {
    const dt = event.dataTransfer;
    if (!dt) return true;

    const types = Array.from(dt.types || []);
    return types.includes('Files') || types.includes('application/x-moz-file');
  }

  function setDragover(on) {
    const zones = getDropzones();

    zones.forEach((dz) => {
      dz.classList.toggle(DRAG_CLASS, Boolean(on));
    });

    document.documentElement.classList.toggle('costerly-file-is-dragging', Boolean(on));
    document.body.classList.toggle('costerly-file-is-dragging', Boolean(on));
  }

  function clearDragover() {
    window.clearTimeout(clearTimer);
    setDragover(false);
  }

  function forceDragover(event) {
    if (!hasFiles(event)) return;

    event.preventDefault();
    window.clearTimeout(clearTimer);
    setDragover(true);
  }

  document.addEventListener('dragenter', forceDragover, true);

  document.addEventListener('dragover', forceDragover, true);

  document.addEventListener(
    'dragleave',
    () => {
      window.clearTimeout(clearTimer);
      clearTimer = window.setTimeout(() => {
        setDragover(false);
      }, 140);
    },
    true
  );

  document.addEventListener('drop', clearDragover, true);
  document.addEventListener('dragend', clearDragover, true);
  window.addEventListener('blur', clearDragover, true);
})();
  `;

  parentDoc.head.appendChild(script);
})();
</script>
        """,
        height=0,
        width=0,
    )
# === COSTERLY_CUSTOM_UPLOAD_DRAGOVER_JS_V1_9_END ===

# ============================================================
# REGRESSION LOCK v1.9.21 — UPLOAD SCREEN CLEARS PROCESSING GHOST GUARD
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# This runs only on the upload screen.
# It removes only v1.9.21 processing-hide classes.
# It must NOT hide anything.
#
# Required tests:
# - first upload screen: upload block visible
# - upload file -> processing: upload ghosts hidden
# - Back -> upload screen: upload block visible again
# ============================================================

# ============================================================
# REGRESSION LOCK v1.9.24 — UPLOAD SCREEN CLEARS PROCESSING GHOST STATE
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# This helper runs ONLY on the upload screen.
# It must never hide the uploader.
# It only removes v1.9.24 processing marker/classes so Back → Upload
# keeps the upload rectangle visible.
#
# Required tests:
# 1. First upload screen: upload block visible.
# 2. Upload file → processing: upload ghosts hidden.
# 3. Back → upload screen: upload block visible again.
# ============================================================

# ============================================================
# REGRESSION LOCK v1.9.25 — UPLOAD SCREEN CLEARS PROCESSING GHOST STATE
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# Runs only on upload screen.
# It must never hide the uploader.
# It clears only v1.9.25 processing state/classes, so Back → Upload
# keeps the upload rectangle visible.
#
# Required tests:
# 1. First upload screen: upload block visible.
# 2. Upload file → processing: upload ghosts hidden.
# 3. Back → upload screen: upload block visible again.
# ============================================================

# ============================================================
# REGRESSION LOCK v1.9.27 — UPLOAD / PROCESSING GHOST GUARD
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# Required tests:
# 1. First upload screen: upload block visible.
# 2. Upload file → processing: upload-screen ghost elements hidden.
# 3. Back → upload screen: upload block visible again.
#
# Important:
# - No permanent inline display:none on uploader.
# - Hiding works only while body/html has processing class v1.9.27.
# - Upload screen always clears processing class and hidden markers.
# ============================================================

# === COSTERLY_UPLOAD_CLEAR_PROCESSING_GHOST_STATE_V1_9_27_START ===
def install_upload_clear_processing_ghost_state_v1_9_27():
    costerly_html_js_runner_v1_9_29(
        """
<script>
(() => {
  const parentDoc = window.parent.document;
  const scriptId = "COSTERLY_UPLOAD_CLEAR_PROCESSING_GHOST_STATE_V1_9_27";

  const old = parentDoc.getElementById(scriptId);
  if (old) old.remove();

  const script = parentDoc.createElement("script");
  script.id = scriptId;

  script.textContent = `
(() => {
  const PROCESSING_CLASS = 'costerly-processing-active-v1-9-27';
  const HIDDEN_CLASS = 'costerly-processing-ghost-hidden-v1-9-27';
  const MARKER_ID = 'costerly-processing-screen-active-v1-9-27';

  function clearProcessingGhostState() {
    document.documentElement.classList.remove(PROCESSING_CLASS);
    document.body.classList.remove(PROCESSING_CLASS);

    document
      .querySelectorAll('.' + HIDDEN_CLASS + ', [data-costerly-processing-ghost-hidden-v1-9-27]')
      .forEach((el) => {
        el.classList.remove(HIDDEN_CLASS);
        el.removeAttribute('data-costerly-processing-ghost-hidden-v1-9-27');
      });

    const marker = document.getElementById(MARKER_ID);
    if (marker) marker.remove();

    if (
      window.__costerlyProcessingGhostGuardV1927 &&
      typeof window.__costerlyProcessingGhostGuardV1927.clear === 'function'
    ) {
      window.__costerlyProcessingGhostGuardV1927.clear();
    }
  }

  clearProcessingGhostState();
  window.setTimeout(clearProcessingGhostState, 50);
  window.setTimeout(clearProcessingGhostState, 150);
  window.setTimeout(clearProcessingGhostState, 500);
})();
  `;

  parentDoc.head.appendChild(script);
})();
</script>
        """,
        height=0,
        width=0,
    )
# === COSTERLY_UPLOAD_CLEAR_PROCESSING_GHOST_STATE_V1_9_27_END ===


# === COSTERLY_PROCESSING_GHOST_GUARD_V1_9_27_START ===
def install_processing_ghost_guard_v1_9_27():
    st.markdown(
        '<div id="costerly-processing-screen-active-v1-9-27" style="display:none"></div>',
        unsafe_allow_html=True,
    )

    costerly_html_js_runner_v1_9_29(
        """
<script>
(() => {
  const parentDoc = window.parent.document;

  const styleId = "COSTERLY_PROCESSING_GHOST_GUARD_V1_9_27_STYLE";
  const scriptId = "COSTERLY_PROCESSING_GHOST_GUARD_V1_9_27_SCRIPT";

  const oldStyle = parentDoc.getElementById(styleId);
  if (oldStyle) oldStyle.remove();

  const style = parentDoc.createElement("style");
  style.id = styleId;

  style.textContent = `
    body.costerly-processing-active-v1-9-27 .costerly-processing-ghost-hidden-v1-9-27,
    html.costerly-processing-active-v1-9-27 .costerly-processing-ghost-hidden-v1-9-27 {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      height: 0 !important;
      min-height: 0 !important;
      max-height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      overflow: hidden !important;
    }

    body.costerly-processing-active-v1-9-27 div[data-testid="stFileUploader"],
    body.costerly-processing-active-v1-9-27 section[data-testid="stFileUploaderDropzone"],
    html.costerly-processing-active-v1-9-27 div[data-testid="stFileUploader"],
    html.costerly-processing-active-v1-9-27 section[data-testid="stFileUploaderDropzone"] {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      height: 0 !important;
      min-height: 0 !important;
      max-height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      overflow: hidden !important;
    }
  `;

  parentDoc.head.appendChild(style);

  const oldScript = parentDoc.getElementById(scriptId);
  if (oldScript) oldScript.remove();

  const script = parentDoc.createElement("script");
  script.id = scriptId;

  script.textContent = `
(() => {
  const MARKER_ID = 'costerly-processing-screen-active-v1-9-27';
  const PROCESSING_CLASS = 'costerly-processing-active-v1-9-27';
  const HIDDEN_CLASS = 'costerly-processing-ghost-hidden-v1-9-27';

  const GHOST_TEXTS = [
    'AI estimating',
    'Quote request to proposal',
    'In minutes, not days',
    'Drop or upload'
  ];

  function norm(s) {
    return (s || '').replace(/\\s+/g, ' ').trim();
  }

  function isProcessing() {
    return Boolean(document.getElementById(MARKER_ID));
  }

  function clear() {
    document.documentElement.classList.remove(PROCESSING_CLASS);
    document.body.classList.remove(PROCESSING_CLASS);

    document
      .querySelectorAll('.' + HIDDEN_CLASS + ', [data-costerly-processing-ghost-hidden-v1-9-27]')
      .forEach((el) => {
        el.classList.remove(HIDDEN_CLASS);
        el.removeAttribute('data-costerly-processing-ghost-hidden-v1-9-27');
      });
  }

  function markHidden(el) {
    if (!el) return;

    el.classList.add(HIDDEN_CLASS);
    el.setAttribute('data-costerly-processing-ghost-hidden-v1-9-27', 'true');
  }

  function containerForTextNode(node) {
    const el = node && node.parentElement;
    if (!el) return null;

    const stElement = el.closest('div[data-testid="stElementContainer"]');
    if (stElement) return stElement;

    const md = el.closest('div[data-testid="stMarkdownContainer"]');
    if (md) return md.closest('div[data-testid="stElementContainer"]') || md;

    return el;
  }

  function markTextGhosts() {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          const text = norm(node.nodeValue);
          if (!text) return NodeFilter.FILTER_REJECT;

          for (const ghost of GHOST_TEXTS) {
            if (text === ghost || text.includes(ghost)) {
              return NodeFilter.FILTER_ACCEPT;
            }
          }

          return NodeFilter.FILTER_REJECT;
        }
      }
    );

    const nodes = [];
    let node;

    while ((node = walker.nextNode())) {
      nodes.push(node);
    }

    nodes.forEach((node) => markHidden(containerForTextNode(node)));
  }

  function markUploadWidgets() {
    document
      .querySelectorAll('div[data-testid="stFileUploader"], section[data-testid="stFileUploaderDropzone"]')
      .forEach((el) => {
        markHidden(el.closest('div[data-testid="stElementContainer"]') || el);
      });
  }

  function apply() {
    if (!isProcessing()) {
      clear();
      return;
    }

    document.documentElement.classList.add(PROCESSING_CLASS);
    document.body.classList.add(PROCESSING_CLASS);

    markTextGhosts();
    markUploadWidgets();
  }

  apply();
  window.setTimeout(apply, 50);
  window.setTimeout(apply, 150);
  window.setTimeout(apply, 500);
  window.setTimeout(apply, 1000);

  window.__costerlyProcessingGhostGuardV1927 = {
    apply,
    clear
  };
})();
  `;

  parentDoc.head.appendChild(script);
})();
</script>
        """,
        height=0,
        width=0,
    )
# === COSTERLY_PROCESSING_GHOST_GUARD_V1_9_27_END ===

def render_upload_screen(company_id=None):
    install_upload_clear_processing_ghost_state_v1_9_27()
    st.markdown(
        """
        <style>
        .stApp:has(.upload-screen-active) .block-container {
            height: 100vh !important;
            max-height: 100vh !important;
            padding: 0 !important;
            overflow: hidden !important;
        }

        .stApp:has(.upload-screen-active) .block-container > div {
            height: 100vh !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-items: center !important;
            transform: translateY(-40px) !important;
        }

        html, body {
            height: 100% !important;
            overflow: hidden !important;
        }

        .stApp,
        div[data-testid="stAppViewContainer"],
        section.main {
            height: 100vh !important;
            max-height: 100vh !important;
            overflow: hidden !important;
        }

        .block-container {
            height: 100vh !important;
            max-height: 100vh !important;
            padding-top: 0 !important;
            padding-bottom: 0 !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
            overflow: hidden !important;
        }

        .landing-title {
            text-align: center;
            font-size: 64px;
            line-height: 1.05;
            font-weight: 800;
            letter-spacing: -2px;
            margin: 150px 0 72px 0;
            color: var(--orange);
        }

        div[data-testid="stFileUploader"] {
            flex: 0 0 auto !important;
        }
        </style>

        <div class="upload-screen-active" style="display:none"></div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <!-- HERO_ARCHIVO_FONT_LINKS_V1 -->
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Archivo+Black&display=swap" rel="stylesheet">

        <style>
            @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&display=swap');

            .landing-hero-v2 {
                width: 100%;
                max-width: 1040px;
                margin: -20px auto 28px auto;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
            }

            .landing-hero-line-1-v2,
            .landing-hero-line-2-v2 {
                font-family: "Archivo Black", "Arial Black", "Helvetica Neue", Arial, sans-serif;
                font-weight: 400;
                font-synthesis: none;
                letter-spacing: -0.045em;
                text-align: center;
                -webkit-font-smoothing: antialiased;
                text-rendering: geometricPrecision;
            }

            .landing-hero-line-1-v2 {
                color: #3B2E48;
                font-size: 46px;
                line-height: 1.18;
                margin-top: 14px;
                margin-bottom: 36px;
            }

            .landing-hero-line-2-v2 {
                color: #3B2E48;
                font-size: 46px;
                line-height: 1.18;
                margin-bottom: 36px;
            }

        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="landing-hero-v2">', unsafe_allow_html=True)
    st.image("assets/brand/costelry_logo_full.svg", width=323)

    st.markdown(
        """
        <div class="landing-hero-line-1-v2">
            AI estimating<br>
            Quote request to proposal<br>
            In minutes, not days
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)

    install_custom_upload_dragover_js_v1_9()


    uploaded_file = st.file_uploader(
        "📎 Drop or upload",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()

        st.session_state.uploaded_file = uploaded_file
        st.session_state.uploaded_filename = uploaded_file.name
        st.session_state.uploaded_file_size = uploaded_file.size
        st.session_state.uploaded_file_type = detect_uploaded_file_type(uploaded_file.name)
        st.session_state.uploaded_file_bytes = file_bytes


        for key in [
            "processing_completed",
            "processing_error",
            "detection_result",
            "current_run_id",
        ]:
            st.session_state.pop(key, None)

        st.session_state.screen = "processing"
        st.rerun()









# ============================================================
# REGRESSION LOCK v1.9.21 — PROCESSING SCREEN GHOST GUARD
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# Previous solved bug:
# Processing screen showed dimmed remnants of the upload screen:
# - AI estimating
# - Quote request to proposal
# - In minutes, not days
# - Drop or upload / upload rectangle
#
# Previous regression:
# A hard JS guard removed those ghosts but also kept hiding the
# uploader after Back.
#
# v1.9.21 rule:
# Hide ghosts ONLY while this processing marker exists:
# #costerly-processing-screen-active-v1-9-21
#
# When the marker is absent, all v1.9.21 hiding is cleared.
# ============================================================

# ============================================================
# REGRESSION LOCK v1.9.24 — PROCESSING SCREEN GHOST GUARD
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# Processing screen must NOT show upload-screen remnants:
# - AI estimating
# - Quote request to proposal
# - In minutes, not days
# - Drop or upload / upload rectangle
#
# This version is deliberately scoped:
# - It hides ghosts only while body has:
#   .costerly-processing-active-v1-9-24
# - Upload screen removes that body class.
# - Hidden markers alone do nothing without the processing body class.
#
# This prevents the old regression where a hard guard kept hiding
# the uploader after Back.
# ============================================================

# ============================================================
# REGRESSION LOCK v1.9.25 — PROCESSING SCREEN GHOST GUARD
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# Processing screen must NOT show upload-screen remnants:
# - AI estimating
# - Quote request to proposal
# - In minutes, not days
# - Drop or upload / upload rectangle
#
# Scoped rule:
# - hiding works only while body/html has .costerly-processing-active-v1-9-25
# - upload screen removes that class
# - no permanent inline display:none is applied to uploader
# ============================================================
def render_processing_screen(company_id: str | None = None):
    # Same layout system as File Review / Objects / Object Detail.
    # No fixed overlay. No separate coordinate system.
    install_processing_ghost_guard_v1_9_27()
    if st.session_state.get("processing_completed"):
        render_file_review_screen(company_id)
        return

    render_post_upload_header(
        "Reading your RFQ package",
        "AI Detection is analyzing the uploaded file and detecting estimate-scope objects.",
    )

    progress_slot = st.empty()

    def render_progress(progress_value: float) -> None:
        value = max(0.0, min(1.0, float(progress_value)))
        width = round(value * 100, 1)

        progress_slot.markdown(
            f"<div class='custom-progress-track'>"
            f"<div class='custom-progress-fill is-running' style='width:{width}%;'></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    try:
        render_progress(0.04)

        file_name = st.session_state.get("uploaded_filename")
        file_bytes = st.session_state.get("uploaded_file_bytes")

        if not file_name:
            st.session_state.screen = "upload"
            st.rerun()

        if not file_bytes:
            uploaded_file = st.session_state.get("uploaded_file")
            if uploaded_file is not None:
                file_bytes = uploaded_file.getvalue()
                st.session_state.uploaded_file_bytes = file_bytes

        if not file_bytes:
            st.session_state.screen = "upload"
            st.rerun()

        active_company_id = company_id or st.secrets.get("COMPANY_ID", "001")

        # Fast local preparation zone.
        render_progress(0.12)

        # Soft-progress zone during the black-box Claude call.
        # Only the agent call runs in the background thread.
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                run_detection_agent,
                file_name=file_name,
                company_id=active_company_id,
                file_bytes=file_bytes,
            )

            while not future.done():
                elapsed = time.time() - start_time

                # Smoothly approaches 88%, but never reaches completion before Claude returns.
                soft_value = 0.12 + 0.76 * (1 - math.exp(-elapsed / 18))
                soft_value = min(soft_value, 0.88)

                render_progress(soft_value)
                time.sleep(0.15)

            detection_result = future.result()

        # Real post-processing zone.
        render_progress(0.90)

        if not isinstance(detection_result, dict):
            raise RuntimeError("Detection agent returned an invalid result.")

        rfq_run = detection_result.get("rfq_run") or {}
        run_id = rfq_run.get("run_id")

        if not run_id:
            raise RuntimeError("Detection result does not contain rfq_run.run_id.")

        st.session_state.detection_result = detection_result
        st.session_state.current_run_id = run_id

        render_progress(0.94)

        client = get_supabase_client()
        upsert_rfq_detection_result(client, detection_result)

        render_progress(1.0)

        st.session_state.processing_completed = True

        time.sleep(0.25)
        st.rerun()

    except Exception as exc:
        st.session_state.processing_error = str(exc)
        st.error(str(exc))

        if st.button("Back to upload"):
            st.session_state.screen = "upload"
            st.rerun()
def _is_empty_value(value) -> bool:
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except Exception:
        pass

    text = str(value).strip()
    return text == "" or text.lower() in {"none", "unknown", "nan", "null", "-"}


def split_text_to_points(value) -> list[str]:
    if _is_empty_value(value):
        return []

    text = str(value).strip()

    text = text.replace("•", "\n")
    text = text.replace("; ", "\n")
    text = text.replace(";", "\n")

    raw_parts = []
    for line in text.splitlines():
        line = line.strip(" \t-•")
        if not line:
            continue

        parts = re.split(r"(?<=[.!?])\s+(?=[A-ZА-Яא-ת0-9])", line)
        raw_parts.extend(parts)

    points = []
    for part in raw_parts:
        part = part.strip(" \t-•.;")
        if part and part.lower() not in {"none", "unknown"}:
            points.append(part)

    return points


def render_bullets(value, empty_text: str = "No major missing information detected.") -> None:
    points = split_text_to_points(value)

    if not points:
        st.caption(empty_text)
        return

    for point in points:
        st.markdown(f"- {point}")


def format_confidence(value) -> str:
    if _is_empty_value(value):
        return "—"

    try:
        return f"{float(value):.0f}%"
    except Exception:
        return str(value)


def format_quantity(row) -> str:
    quantity = row.get("quantity", 1)
    quantity_confidence = row.get("quantity_confidence", 0)

    try:
        q = float(quantity)
        q_text = str(int(q)) if q.is_integer() else str(round(q, 2))
    except Exception:
        q_text = str(quantity)

    try:
        qc = float(quantity_confidence)
    except Exception:
        qc = 0

    return f"{q_text}?" if qc < 70 else q_text


def _parse_dimensions(value) -> dict:
    if isinstance(value, dict):
        return value

    if _is_empty_value(value):
        return {}

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}

    return {}


def _dimension_part(label: str, value) -> str:
    try:
        number = float(value)
        if number <= 0:
            return f"{label} ?"
        if number.is_integer():
            return f"{label} {int(number)}"
        return f"{label} {round(number, 1)}"
    except Exception:
        return f"{label} ?"


def format_dimensions(value) -> str:
    dimensions = _parse_dimensions(value)

    width = dimensions.get("width", 0)
    depth = dimensions.get("depth", 0)
    height = dimensions.get("height", 0)
    unit = dimensions.get("unit", "mm")

    if _is_empty_value(unit):
        unit = "mm"

    return (
        f"{_dimension_part('W', width)} × "
        f"{_dimension_part('D', depth)} × "
        f"{_dimension_part('H', height)} {unit}"
    )


def render_file_review_screen(company_id: str):
    render_post_upload_header("File Review")

    client = get_supabase_client()
    run_id = st.session_state.get("current_run_id") or "RA-N01_run_001"

    run_df = fetch_rfq_run(client, run_id)
    objects_df = fetch_rfq_detected_objects(client, run_id)

    if run_df.empty:
        st.warning("No RFQ run found. Run detection first.")
        if st.button("Back to upload"):
            go_to("upload")
        return

    run = run_df.iloc[0].to_dict()

    col1, col2, col3 = st.columns(3)
    col1.metric("Project", run.get("project_name", "—"))
    col2.metric("Pages", run.get("pages_detected", 0))
    col3.metric("File quality", run.get("file_quality_label", "—"))

    st.divider()

    st.subheader("Missing information")
    render_bullets(
        run.get("missing_information", "none"),
        empty_text="No major missing information detected.",
    )

    with st.expander("Technical metadata", expanded=False):
        metadata_rows = [
            ("Project name", run.get("project_name", "—")),
            ("File name", run.get("file_name", "—")),
            ("Source type", run.get("source_type", "—")),
            ("Design partner", run.get("client_or_design_partner", "—")),
            ("Author", run.get("author", "—")),
            ("Document date", run.get("document_date", "—")),
            ("Language", run.get("language", "—")),
            ("File quality confidence", format_confidence(run.get("file_quality_confidence", 0))),
            ("Run ID", run.get("run_id", "—")),
            ("Status", run.get("status", "—")),
        ]

        st.dataframe(
            pd.DataFrame(metadata_rows, columns=["Field", "Value"]),
            width="stretch",
            hide_index=True,
        )

    st.divider()

    st.subheader("Detected objects")

    if objects_df.empty:
        st.warning("No objects detected.")
    else:
        for _, row in objects_df.iterrows():
            with st.container(border=True):
                top_left, top_mid, top_right = st.columns([5, 1, 1])

                top_left.subheader(row.get("object_name", "Unknown object"))
                top_mid.metric("Qty", format_quantity(row))
                top_right.metric("Confidence", format_confidence(row.get("confidence", 0)))

                dim_col, mat_col = st.columns([2, 3])

                with dim_col:
                    st.caption("Dimensions")
                    st.write(format_dimensions(row.get("dimensions_json", {})))

                with mat_col:
                    st.caption("Materials")
                    materials = row.get("detected_materials", "unknown")
                    st.write("—" if _is_empty_value(materials) else materials)

                notes = row.get("notes", "none")
                if not _is_empty_value(notes):
                    st.caption("Notes")
                    render_bullets(notes, empty_text="—")

    col_back, col_next = st.columns(2)

    if col_back.button("Back to upload"):
        go_to("upload")

    if col_next.button("Continue to objects", type="primary"):
        go_to("objects")

def render_objects_screen(company_id: str):
    st.title("Detected Objects")

    client = get_supabase_client()
    run_id = st.session_state.get("current_run_id") or "RA-N01_run_001"

    objects_df = fetch_rfq_detected_objects(client, run_id)

    if objects_df.empty:
        st.warning("No detected objects found.")
        if st.button("Back to File Review"):
            go_to("file_review")
        return

    for _, row in objects_df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])

            col1.subheader(row.get("object_name", "Unknown object"))
            col1.caption(row.get("notes", ""))

            col2.metric("Qty", row.get("quantity", 1))
            col3.metric("Confidence", f"{row.get('confidence', 0)}%")

            st.write(f"**Materials:** {row.get('detected_materials', 'none')}")
            st.write(f"**Evidence pages:** {row.get('evidence_pages', 'none')}")
            st.write(f"**Dimensions:** {row.get('dimensions_json', {})}")

    col_back, col_next = st.columns(2)

    if col_back.button("Back to File Review"):
        go_to("file_review")

    if col_next.button("Continue to route preview", type="primary"):
        go_to("dev_dashboard")


# -----------------------------------------------------------------------------
# Dev dashboard
# -----------------------------------------------------------------------------

def render_connection_check():
    st.header("1. Supabase connection")

    try:
        client = get_supabase_client()
        st.success("Supabase client initialized.")
        return client
    except Exception as exc:
        st.error(str(exc))
        st.info("Add SUPABASE_URL and SUPABASE_ANON_KEY to Streamlit secrets.")
        st.stop()


def render_data_overview(company_id: str):
    st.header("2. Company data")

    data = load_company_data_cached(company_id)

    counts = pd.DataFrame(
        [
            {"table": name, "rows": len(df)}
            for name, df in data.items()
        ]
    )

    st.dataframe(counts, use_container_width=True, hide_index=True)

    with st.expander("Preview works"):
        st.dataframe(data["works"], use_container_width=True, height=420)

    with st.expander("Preview company machines"):
        st.dataframe(data["company_machines"], use_container_width=True, height=360)

    return data


def render_detection_agent_dev(company_id: str):
    st.header("3. Detection Agent")

    st.caption(
        "Mock Detection Agent v1: parses RFQ metadata, file quality and detected objects."
    )

    file_name = st.text_input(
        "RFQ file name",
        value="RA-N01_20260216.pdf",
        key="detection_file_name_dev",
    )

    dev_uploaded_file = st.file_uploader(
        "Optional PDF for real Anthropic detection",
        type=["pdf"],
        key="detection_file_dev_upload",
    )

    client = get_supabase_client()

    if st.button("Run Detection Agent", type="primary"):
        if dev_uploaded_file is not None:
            detection_result = run_detection_agent(
                file_name=dev_uploaded_file.name,
                company_id=company_id,
                file_bytes=dev_uploaded_file.getvalue(),
            )
        else:
            detection_result = run_detection_agent(
                file_name=file_name,
                company_id=company_id,
                file_bytes=None,
            )

        upsert_rfq_detection_result(client, detection_result)

        st.session_state["current_run_id"] = detection_result["rfq_run"]["run_id"]
        st.success(f"Detection result saved: {detection_result['rfq_run']['run_id']}")

    run_id = st.session_state.get("current_run_id", "RA-N01_run_001")

    run_df = fetch_rfq_run(client, run_id)
    objects_df = fetch_rfq_detected_objects(client, run_id)

    if run_df.empty:
        st.info("No RFQ run saved yet. Run the Detection Agent first.")
        return

    run = run_df.iloc[0].to_dict()

    col1, col2, col3 = st.columns(3)
    col1.metric("Project", run.get("project_name", "—"))
    col2.metric("File quality", run.get("file_quality_label", "—"))
    col3.metric("Confidence", f"{run.get('file_quality_confidence', 0)}%")

    with st.expander("RFQ run metadata", expanded=True):
        st.dataframe(run_df, use_container_width=True, hide_index=True)

    st.subheader("Detected objects")

    if objects_df.empty:
        st.warning("No detected objects found for this run.")
        return

    visible_cols = [
        "object_id",
        "object_name",
        "quantity",
        "quantity_explicit",
        "quantity_confidence",
        "confidence",
        "evidence_pages",
        "detected_materials",
        "dimensions_json",
        "notes",
    ]

    existing_cols = [col for col in visible_cols if col in objects_df.columns]

    st.dataframe(
        objects_df[existing_cols],
        use_container_width=True,
        hide_index=True,
        height=260,
    )


def render_route_preview(data: dict[str, pd.DataFrame]):
    st.header("4. Route selection preview")

    works = data.get("works", pd.DataFrame())
    company_machines = data.get("company_machines", pd.DataFrame())

    if works.empty:
        st.warning("No rows loaded from works. Check Supabase data import or RLS policies.")
        return pd.DataFrame()

    if company_machines.empty:
        st.warning("No rows loaded from company_machines. Check Supabase data import or RLS policies.")
        return pd.DataFrame()

    selected_routes = select_routes(works, company_machines)

    if selected_routes.empty:
        st.warning("No routes selected.")
        return selected_routes

    st.caption(
        "One selected route per work_family_code based on active company machines and route_priority."
    )

    columns_to_show = [
        "work_category",
        "work_family_code",
        "route_name",
        "execution_method",
        "machine_type",
        "service_code",
        "driver_code",
        "hours_per_unit",
    ]

    existing_columns = [
        col for col in columns_to_show
        if col in selected_routes.columns
    ]

    st.dataframe(
        selected_routes[existing_columns],
        use_container_width=True,
        height=420,
    )

    return selected_routes


def render_estimate_test(company_id: str, selected_routes: pd.DataFrame):
    st.header("5. Estimate driver quantities test")

    if selected_routes.empty:
        st.info("No selected routes available.")
        return

    estimate_id = st.text_input("estimate_id", value="RA-N01_run_001")
    object_id = st.text_input("object_id", value="01_kitchen")

    client = get_supabase_client()

    if st.button("Load driver quantities and calculate hours", type="primary"):
        quantities = fetch_estimate_driver_quantities(
            client=client,
            company_id=company_id,
            estimate_id=estimate_id,
            object_id=object_id,
        )

        if quantities.empty:
            st.warning("No rows found in estimate_driver_quantities for this estimate/object.")
            st.info("This is expected until the AI/takeoff layer writes driver quantities.")
            return

        st.subheader("Driver quantities")
        st.dataframe(quantities, use_container_width=True, hide_index=True)

        hours_df = calculate_work_hours(selected_routes, quantities)

        st.subheader("Calculated work hours")
        st.dataframe(hours_df, use_container_width=True, hide_index=True, height=480)

        st.metric("Total adjusted hours", round(hours_df["adjusted_hours"].sum(), 2))


def render_dev_dashboard(company_id: str):
    st.title("RFQ Estimate App")
    st.caption("Developer dashboard. Supabase-backed backend checks.")

    render_connection_check()

    if st.button("Refresh Supabase data"):
        load_company_data_cached.clear()
        st.rerun()

    data = render_data_overview(company_id)
    render_detection_agent_dev(company_id)
    selected_routes = render_route_preview(data)
    render_estimate_test(company_id, selected_routes)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    init_state()

    company_id = get_company_id()

    show_dev_nav = os.getenv("SHOW_DEV_NAV", "false").lower() in {"1", "true", "yes", "on"}

    if show_dev_nav:
        with st.sidebar:
            st.write("Navigation")
            st.caption(f"company_id: {company_id}")

            if st.button("Upload flow"):
                go_to("upload")

            if st.button("Dev dashboard"):
                go_to("dev_dashboard")

            if st.session_state.get("current_run_id"):
                st.caption(f"run_id: {st.session_state.current_run_id}")

    screen = st.session_state.screen

    if screen == "upload":
        render_upload_screen(company_id)
    elif screen == "processing":
        render_processing_screen(company_id)
    elif screen == "file_review":
        render_file_review_screen(company_id)
    elif screen == "objects":
        render_objects_screen(company_id)
    elif screen == "dev_dashboard":
        render_dev_dashboard(company_id)
    else:
        render_upload_screen(company_id)


if __name__ == "__main__":
    main()

