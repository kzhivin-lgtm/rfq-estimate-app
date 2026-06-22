from __future__ import annotations
from pathlib import Path

import pandas as pd
import json
import re

import math
import time

from concurrent.futures import ThreadPoolExecutor

import streamlit as st
from streamlit.components.v1 import html as costerly_component_html_v1_9_34
# ============================================================
# REGRESSION LOCK v1.9.34 — COMPONENT HTML JS RUNNER FOR PROD
#
# DO NOT REMOVE WITHOUT MANUAL TESTING.
#
# Restores iframe-based JS execution for production.
# v1.9.29 st.html runner removed warning logs but did not reliably
# run the DOM guards in fresh prod sessions:
# - dragover lilac plus did not appear
# - processing ghost elements were visible again
#
# Required tests:
# 1. First upload screen: upload block visible.
# 2. Drag file over upload block: lilac state + white plus visible.
# 3. Upload file → processing: ghost hero/uploader elements hidden.
# 4. Back → upload screen: upload block visible again.
# ============================================================
# === COSTERLY_COMPONENT_HTML_JS_RUNNER_V1_9_34_START ===
def costerly_component_html_js_runner_v1_9_34(html_source: str, **kwargs):
    costerly_component_html_v1_9_34(
        html_source,
        height=kwargs.get("height", 0),
        width=kwargs.get("width", 0),
    )
# === COSTERLY_COMPONENT_HTML_JS_RUNNER_V1_9_34_END ===
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
    costerly_component_html_js_runner_v1_9_34(
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
# === COSTERLY_UPLOAD_EARLY_PROCESSING_SCREEN_SHELL_V1_11_1_START ===
def install_upload_early_processing_screen_shell_v1_11_1() -> None:
    """
    v1.11.1: immediately show a processing-screen-looking frontend shell after file drop/change.

    UX:
    - drop/change -> immediately show Processing file screen
    - progress bar stays at first stage while Streamlit receives the file
    - real backend processing screen takes over after Python receives uploaded_file

    Regression lock:
    - Client-side only.
    - Does not change st.session_state.screen.
    - Does not start backend processing.
    - Real processing starts only when Streamlit gives Python uploaded_file.
    - Keep v1.9.27/v1.9.34 guards untouched.
    """
    costerly_component_html_js_runner_v1_9_34(
        """
<script>
(function () {
    const VERSION = "v1.11.1";
    const SHELL_ID = "costerly-upload-early-processing-shell-v1-11-1";
    const STYLE_ID = "costerly-upload-early-processing-shell-style-v1-11-1";
    const INSTALLED_FLAG = "__costerlyUploadEarlyProcessingShellV1111Installed";
    const TIMEOUT_KEY = "__costerlyUploadEarlyProcessingShellTimeoutV1111";
    const WATCHER_KEY = "__costerlyUploadEarlyProcessingShellWatcherV1111";

    const parentWindow = window.parent || window;
    const doc = parentWindow.document;

    if (!doc || !doc.body) {
        return;
    }

    if (doc[INSTALLED_FLAG]) {
        return;
    }

    doc[INSTALLED_FLAG] = true;

    function installStyle() {
        if (doc.getElementById(STYLE_ID)) {
            return;
        }

        const style = doc.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            html.costerly-upload-early-processing-shell-active-v1-11-1,
            body.costerly-upload-early-processing-shell-active-v1-11-1 {
                overflow: hidden !important;
            }

            #${SHELL_ID} {
                position: fixed;
                inset: 0;
                z-index: 2147483000;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #F1EFEF;
                color: #2A1F2C;
                font-family: var(--font, Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
            }

            #${SHELL_ID} .costerly-early-processing-wrap-v1-11-1 {
                width: min(760px, calc(100vw - 44px));
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
            }

            #${SHELL_ID} .costerly-early-processing-logo-v1-11-1 {
                width: 82px;
                height: 82px;
                border-radius: 999px;
                border: 2px solid rgba(128, 73, 198, 0.28);
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 30px;
                position: relative;
            }

            #${SHELL_ID} .costerly-early-processing-logo-v1-11-1::before {
                content: "";
                width: 52px;
                height: 52px;
                border-radius: 999px;
                border: 4px solid rgba(128, 73, 198, 0.20);
                border-top-color: #8049C6;
                animation: costerlyEarlyProcessingSpinV1111 0.95s linear infinite;
                box-sizing: border-box;
            }

            #${SHELL_ID} .costerly-early-processing-title-v1-11-1 {
                font-size: 40px;
                line-height: 1.08;
                font-weight: 760;
                letter-spacing: -0.05em;
                color: #2A1F2C;
                margin: 0 0 14px 0;
            }

            #${SHELL_ID} .costerly-early-processing-subtitle-v1-11-1 {
                font-size: 17px;
                line-height: 1.45;
                color: rgba(42, 31, 44, 0.66);
                margin: 0 0 34px 0;
                max-width: 560px;
            }

            #${SHELL_ID} .costerly-early-processing-progress-track-v1-11-1 {
                width: min(520px, 100%);
                height: 10px;
                border-radius: 999px;
                background: rgba(42, 31, 44, 0.10);
                overflow: hidden;
                margin: 0 auto 16px auto;
            }

            #${SHELL_ID} .costerly-early-processing-progress-fill-v1-11-1 {
                height: 100%;
                width: 6%;
                border-radius: 999px;
                background: #8049C6;
                transition: width 200ms ease;
            }

            #${SHELL_ID} .costerly-early-processing-step-v1-11-1 {
                font-size: 15px;
                line-height: 1.35;
                color: rgba(42, 31, 44, 0.70);
                margin: 0;
            }

            #${SHELL_ID} .costerly-early-processing-timeout-v1-11-1 {
                display: none;
                margin-top: 26px;
                font-size: 14px;
                line-height: 1.45;
                color: rgba(42, 31, 44, 0.62);
            }

            #${SHELL_ID}[data-slow="true"] .costerly-early-processing-timeout-v1-11-1 {
                display: block;
            }

            #${SHELL_ID} .costerly-early-processing-cancel-v1-11-1 {
                margin-top: 14px;
                border: 1px solid rgba(42, 31, 44, 0.18);
                background: #FFFFFF;
                color: #2A1F2C;
                border-radius: 999px;
                padding: 9px 16px;
                font-size: 13px;
                cursor: pointer;
            }

            @keyframes costerlyEarlyProcessingSpinV1111 {
                to {
                    transform: rotate(360deg);
                }
            }

            @media (max-width: 760px) {
                #${SHELL_ID} .costerly-early-processing-title-v1-11-1 {
                    font-size: 32px;
                }

                #${SHELL_ID} .costerly-early-processing-subtitle-v1-11-1 {
                    font-size: 16px;
                }
            }
        `;
        doc.head.appendChild(style);
    }

    function realProcessingIsActive() {
        return Boolean(
            doc.getElementById("costerly-processing-screen-active-v1-9-27") ||
            doc.body.classList.contains("costerly-processing-active-v1-9-27") ||
            doc.documentElement.classList.contains("costerly-processing-active-v1-9-27")
        );
    }

    function removeShell() {
        const shell = doc.getElementById(SHELL_ID);

        if (shell) {
            shell.remove();
        }

        doc.documentElement.classList.remove("costerly-upload-early-processing-shell-active-v1-11-1");
        doc.body.classList.remove("costerly-upload-early-processing-shell-active-v1-11-1");

        if (parentWindow[TIMEOUT_KEY]) {
            parentWindow.clearTimeout(parentWindow[TIMEOUT_KEY]);
            parentWindow[TIMEOUT_KEY] = null;
        }
    }

    function startRealProcessingWatcher() {
        if (parentWindow[WATCHER_KEY]) {
            return;
        }

        parentWindow[WATCHER_KEY] = parentWindow.setInterval(function () {
            if (realProcessingIsActive()) {
                removeShell();
                parentWindow.clearInterval(parentWindow[WATCHER_KEY]);
                parentWindow[WATCHER_KEY] = null;
            }
        }, 120);
    }

    function showShell(source) {
        if (realProcessingIsActive()) {
            return;
        }

        installStyle();

        let shell = doc.getElementById(SHELL_ID);

        if (!shell) {
            shell = doc.createElement("div");
            shell.id = SHELL_ID;
            shell.setAttribute("data-source", source || "unknown");
            shell.innerHTML = `
                <div class="costerly-early-processing-wrap-v1-11-1">
                    <div class="costerly-early-processing-logo-v1-11-1" aria-hidden="true"></div>

                    <h1 class="costerly-early-processing-title-v1-11-1">Processing file</h1>

                    <p class="costerly-early-processing-subtitle-v1-11-1">
                        We’re analyzing your RFQ package and preparing the detected objects.
                    </p>

                    <div class="costerly-early-processing-progress-track-v1-11-1">
                        <div class="costerly-early-processing-progress-fill-v1-11-1"></div>
                    </div>

                    <p class="costerly-early-processing-step-v1-11-1">
                        Receiving file
                    </p>

                    <div class="costerly-early-processing-timeout-v1-11-1">
                        Upload is taking longer than expected.
                        <br />
                        <button class="costerly-early-processing-cancel-v1-11-1" type="button">
                            Return to upload
                        </button>
                    </div>
                </div>
            `;

            doc.body.appendChild(shell);

            const cancel = shell.querySelector(".costerly-early-processing-cancel-v1-11-1");
            if (cancel) {
                cancel.addEventListener("click", removeShell);
            }
        }

        shell.dataset.source = source || "unknown";
        shell.dataset.slow = "false";

        doc.documentElement.classList.add("costerly-upload-early-processing-shell-active-v1-11-1");
        doc.body.classList.add("costerly-upload-early-processing-shell-active-v1-11-1");

        if (parentWindow[TIMEOUT_KEY]) {
            parentWindow.clearTimeout(parentWindow[TIMEOUT_KEY]);
        }

        parentWindow[TIMEOUT_KEY] = parentWindow.setTimeout(function () {
            const activeShell = doc.getElementById(SHELL_ID);
            if (activeShell && !realProcessingIsActive()) {
                activeShell.dataset.slow = "true";
            }
        }, 25000);

        startRealProcessingWatcher();
    }

    function bindFileInputs() {
        const inputs = Array.from(doc.querySelectorAll('input[type="file"]'));

        inputs.forEach(function (input) {
            if (input.dataset.costerlyUploadEarlyProcessingShellV1111Bound === "true") {
                return;
            }

            input.dataset.costerlyUploadEarlyProcessingShellV1111Bound = "true";

            input.addEventListener("change", function () {
                if (input.files && input.files.length > 0) {
                    showShell("input-change");
                }
            }, true);
        });
    }

    doc.addEventListener("drop", function (event) {
        try {
            if (
                event.dataTransfer &&
                event.dataTransfer.files &&
                event.dataTransfer.files.length > 0
            ) {
                parentWindow.setTimeout(function () {
                    showShell("drop");
                }, 0);
            }
        } catch (err) {
            // Keep upload behavior intact even if shell detection fails.
        }
    }, true);

    doc.addEventListener("change", function (event) {
        const target = event.target;

        if (
            target &&
            target.matches &&
            target.matches('input[type="file"]') &&
            target.files &&
            target.files.length > 0
        ) {
            showShell("document-change");
        }
    }, true);

    const observer = new MutationObserver(function () {
        bindFileInputs();

        if (realProcessingIsActive()) {
            removeShell();
        }
    });

    observer.observe(doc.body, {
        childList: true,
        subtree: true
    });

    bindFileInputs();
    startRealProcessingWatcher();

    console.debug("[Costerly] Upload early processing screen shell installed", VERSION);
})();
</script>
        """,
        height=0,
        width=0,
    )
# === COSTERLY_UPLOAD_EARLY_PROCESSING_SCREEN_SHELL_V1_11_1_END ===

# === COSTERLY_UPLOAD_LEGACY_PREPARING_REWRITER_V1_11_2_START ===
def install_upload_legacy_preparing_rewriter_v1_11_2() -> None:
    """
    v1.11.2: rewrite/remove legacy v1.11.0 Preparing shell if it appears.

    Why:
    Existing browser tabs can keep old anonymous JS listeners from v1.11.0.
    We cannot directly remove those listeners, but we can immediately rewrite
    their DOM after they create the old shell.

    Regression lock:
    - Client-side only.
    - Does not change st.session_state.screen.
    - Does not start backend processing.
    - Does not touch v1.9.27/v1.9.34 guards.
    """
    costerly_component_html_js_runner_v1_9_34(
        """
<script>
(function () {
    const VERSION = "v1.11.2";
    const LEGACY_SHELL_ID = "costerly-upload-processing-shell-v1-11-0";
    const STYLE_ID = "costerly-upload-legacy-preparing-rewriter-style-v1-11-2";
    const INSTALLED_FLAG = "__costerlyUploadLegacyPreparingRewriterV1112Installed";

    const parentWindow = window.parent || window;
    const doc = parentWindow.document;

    if (!doc || !doc.body) {
        return;
    }

    function installStyle() {
        if (doc.getElementById(STYLE_ID)) {
            return;
        }

        const style = doc.createElement("style");
        style.id = STYLE_ID;
        style.textContent = `
            #${LEGACY_SHELL_ID} {
                background: #F1EFEF !important;
            }

            #${LEGACY_SHELL_ID} .costerly-upload-processing-card-v1-11-0 {
                width: min(760px, calc(100vw - 44px)) !important;
                min-height: 0 !important;
                background: transparent !important;
                border: 0 !important;
                box-shadow: none !important;
                padding: 0 !important;
            }

            #${LEGACY_SHELL_ID} .costerly-upload-processing-title-v1-11-0 {
                font-size: 40px !important;
                line-height: 1.08 !important;
                font-weight: 760 !important;
                letter-spacing: -0.05em !important;
                color: #2A1F2C !important;
                margin: 0 0 14px 0 !important;
            }

            #${LEGACY_SHELL_ID} .costerly-upload-processing-subtitle-v1-11-0 {
                font-size: 17px !important;
                line-height: 1.45 !important;
                color: rgba(42, 31, 44, 0.66) !important;
                margin: 0 0 34px 0 !important;
                max-width: 560px !important;
            }

            #${LEGACY_SHELL_ID} .costerly-legacy-progress-track-v1-11-2 {
                width: min(520px, 100%);
                height: 10px;
                border-radius: 999px;
                background: rgba(42, 31, 44, 0.10);
                overflow: hidden;
                margin: 0 auto 16px auto;
            }

            #${LEGACY_SHELL_ID} .costerly-legacy-progress-fill-v1-11-2 {
                height: 100%;
                width: 6%;
                border-radius: 999px;
                background: #8049C6;
            }

            #${LEGACY_SHELL_ID} .costerly-legacy-step-v1-11-2 {
                font-size: 15px;
                line-height: 1.35;
                color: rgba(42, 31, 44, 0.70);
                margin: 0;
            }
        `;

        doc.head.appendChild(style);
    }

    function rewriteLegacyShell() {
        installStyle();

        const shell = doc.getElementById(LEGACY_SHELL_ID);
        if (!shell) {
            return false;
        }

        shell.dataset.rewrittenByV1112 = "true";

        const title = shell.querySelector(".costerly-upload-processing-title-v1-11-0");
        if (title) {
            title.textContent = "Processing file";
        }

        const subtitle = shell.querySelector(".costerly-upload-processing-subtitle-v1-11-0");
        if (subtitle) {
            subtitle.textContent = "We’re analyzing your RFQ package and preparing the detected objects.";
        }

        const card = shell.querySelector(".costerly-upload-processing-card-v1-11-0");
        if (card && !card.querySelector(".costerly-legacy-progress-track-v1-11-2")) {
            const progress = doc.createElement("div");
            progress.className = "costerly-legacy-progress-track-v1-11-2";
            progress.innerHTML = '<div class="costerly-legacy-progress-fill-v1-11-2"></div>';

            const step = doc.createElement("p");
            step.className = "costerly-legacy-step-v1-11-2";
            step.textContent = "Receiving file";

            const timeout = card.querySelector(".costerly-upload-processing-timeout-v1-11-0");
            if (timeout) {
                card.insertBefore(progress, timeout);
                card.insertBefore(step, timeout);
            } else {
                card.appendChild(progress);
                card.appendChild(step);
            }
        }

        return true;
    }

    if (!doc[INSTALLED_FLAG]) {
        doc[INSTALLED_FLAG] = true;

        const observer = new MutationObserver(function () {
            rewriteLegacyShell();
        });

        observer.observe(doc.body, {
            childList: true,
            subtree: true,
            characterData: true
        });

        parentWindow.setInterval(rewriteLegacyShell, 120);
    }

    rewriteLegacyShell();

    console.debug("[Costerly] Legacy Preparing shell rewriter installed", VERSION);
})();
</script>
        """,
        height=0,
        width=0,
    )
# === COSTERLY_UPLOAD_LEGACY_PREPARING_REWRITER_V1_11_2_END ===

def install_upload_clear_processing_ghost_state_v1_9_27():
    costerly_component_html_js_runner_v1_9_34(
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

    costerly_component_html_js_runner_v1_9_34(
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
    install_upload_early_processing_screen_shell_v1_11_1()
    install_upload_legacy_preparing_rewriter_v1_11_2()


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


# === COSTERLY_FILE_REVIEW_CARD_LAYOUT_V1_9_36_START ===
def _html_escape_v1_9_36(value) -> str:
    from html import escape

    if _is_empty_value(value):
        return "—"

    return escape(str(value).strip())


def _display_value_v1_9_36(value, fallback: str = "—") -> str:
    if _is_empty_value(value):
        return fallback

    return str(value).strip()


def _file_stem_v1_9_36(file_name) -> str:
    if _is_empty_value(file_name):
        return ""

    try:
        return Path(str(file_name)).stem.strip()
    except Exception:
        return str(file_name).strip()


def _file_review_project_name_v1_9_36(run: dict, objects_df: pd.DataFrame) -> str:
    for key in ["project_name", "project_title", "rfq_name"]:
        value = _display_value_v1_9_36(run.get(key), "")
        if value:
            return value

    if objects_df is not None and not objects_df.empty and "object_name" in objects_df.columns:
        value = _display_value_v1_9_36(objects_df.iloc[0].get("object_name"), "")
        if value:
            return value

    for key in ["file_name", "uploaded_filename"]:
        value = _file_stem_v1_9_36(run.get(key))
        if value:
            return value

    value = _file_stem_v1_9_36(st.session_state.get("uploaded_filename"))
    if value:
        return value

    return "Untitled project"


def _file_review_partner_v1_9_36(run: dict) -> str:
    # Prefer architect / bureau / design-side fields when present.
    # Fall back to direct client fields. This is UI-only; no prompt/schema change yet.
    partner_keys = [
        "architecture_bureau",
        "architectural_bureau",
        "architect_bureau",
        "architect_name",
        "designer_name",
        "design_partner",
        "client_or_design_partner",
        "client_name",
        "customer_name",
        "author",
    ]

    for key in partner_keys:
        value = _display_value_v1_9_36(run.get(key), "")
        if value:
            return value

    return "Not detected"


def _compact_missing_information_html_v1_9_36(value) -> str:
    points = split_text_to_points(value)

    if not points:
        return (
            "<div class='file-review-empty-v1-9-36'>"
            "No major missing information detected."
            "</div>"
        )

    items = "".join(
        f"<li>{_html_escape_v1_9_36(point)}</li>"
        for point in points
    )

    return f"<ul class='file-review-missing-list-v1-9-36'>{items}</ul>"


def _metadata_table_html_v1_9_36(rows: list[tuple[str, object]]) -> str:
    body = "".join(
        "<tr>"
        f"<td>{_html_escape_v1_9_36(label)}</td>"
        f"<td>{_html_escape_v1_9_36(value)}</td>"
        "</tr>"
        for label, value in rows
    )

    return f"<table class='file-review-metadata-table-v1-9-36'>{body}</table>"


# === COSTERLY_FILE_REVIEW_V1_10_4_START ===
def apply_file_review_v1_10_4_css() -> None:
    """Apply File Review-specific typography and compact metadata styles."""
    st.markdown(
        """
<style>
/* ============================================================
   COSTERLY_FILE_REVIEW_V1_10_4

   Scope:
   - File Review white review card.
   - Top summary fields.
   - Missing information block.
   - Compact technical metadata.
   ============================================================ */

.file-review-card-v1-10-4 {
    width: 100%;
    background: #FFFFFF;
    border: 1px solid rgba(42, 31, 44, 0.14);
    border-radius: 16px;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.055);
    padding: 32px 34px 26px 34px;
    box-sizing: border-box;
    color: #2A1F2C;
}

.file-review-summary-grid-v1-10-4 {
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    column-gap: 28px;
    row-gap: 14px;
    align-items: baseline;
}

.file-review-label-v1-10-4 {
    font-size: 18px;
    line-height: 1.25;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: rgba(42, 31, 44, 0.54);
}

.file-review-value-v1-10-4 {
    font-size: 18px;
    line-height: 1.28;
    font-weight: 700;
    letter-spacing: -0.015em;
    color: #2A1F2C;
}

.file-review-divider-v1-10-4 {
    height: 1px;
    background: rgba(42, 31, 44, 0.14);
    margin: 24px 0 20px 0;
}

.file-review-section-title-v1-10-4 {
    font-size: 18px;
    line-height: 1.25;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: rgba(42, 31, 44, 0.58);
    margin: 0 0 10px 0;
}

.file-review-missing-list-v1-10-4 {
    margin: 0 0 0 22px;
    padding: 0;
    color: #2A1F2C;
}

.file-review-missing-list-v1-10-4 li {
    font-size: 16px;
    line-height: 1.42;
    margin: 3px 0;
    padding-left: 2px;
}

.file-review-muted-v1-10-4 {
    font-size: 16px;
    line-height: 1.42;
    color: rgba(42, 31, 44, 0.58);
}

.file-review-meta-details-v1-10-4 {
    margin-top: 0;
}

.file-review-meta-summary-v1-10-4 {
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 0;
    padding: 0;
    user-select: none;
}

.file-review-meta-summary-v1-10-4::-webkit-details-marker {
    display: none;
}

.file-review-meta-summary-v1-10-4::before {
    content: "▾";
    font-size: 28px;
    line-height: 1;
    color: rgba(42, 31, 44, 0.60);
    transform: translateY(-1px);
}

.file-review-meta-details-v1-10-4:not([open]) .file-review-meta-summary-v1-10-4::before {
    content: "▸";
}

.file-review-meta-title-v1-10-4 {
    font-size: 18px;
    line-height: 1.25;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: rgba(42, 31, 44, 0.58);
}

.file-review-meta-table-v1-10-4 {
    margin-top: 12px;
    border-top: 1px solid rgba(42, 31, 44, 0.10);
}

.file-review-meta-row-v1-10-4 {
    display: grid;
    grid-template-columns: 190px minmax(0, 1fr);
    column-gap: 14px;
    min-height: 27px;
    padding: 5px 0;
    border-bottom: 1px solid rgba(42, 31, 44, 0.08);
    align-items: center;
}

.file-review-meta-key-v1-10-4 {
    font-size: 14px;
    line-height: 1.2;
    color: rgba(42, 31, 44, 0.52);
}

.file-review-meta-value-v1-10-4 {
    font-size: 14px;
    line-height: 1.2;
    color: #2A1F2C;
    font-weight: 500;
    overflow-wrap: anywhere;
}


.file-review-detected-title-v1-10-4 {
    font-family: var(--mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace) !important;
    color: #8049C6 !important;
    font-size: 40px !important;
    line-height: 1.1 !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em !important;
    margin: 48px 0 24px 0 !important;
    padding: 0 !important;
}

.file-review-object-card-v1-10-4 {
    width: 100%;
    background: #FFFFFF;
    border: 1px solid rgba(42, 31, 44, 0.14);
    border-radius: 16px;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.055);
    padding: 28px 34px 26px 34px;
    box-sizing: border-box;
    color: #2A1F2C;
    margin: 0 0 20px 0;
}

.file-review-object-top-v1-10-4 {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 110px 130px;
    column-gap: 34px;
    align-items: start;
    margin-bottom: 28px;
}

.file-review-object-name-v1-10-4 {
    font-size: 28px;
    line-height: 1.18;
    font-weight: 800;
    letter-spacing: -0.035em;
    color: #17131C;
}

.file-review-object-metric-label-v1-10-4 {
    font-size: 13px;
    line-height: 1.2;
    color: rgba(42, 31, 44, 0.62);
    margin-bottom: 6px;
}

.file-review-object-metric-value-v1-10-4 {
    font-size: 34px;
    line-height: 1;
    font-weight: 500;
    color: #111111;
}

.file-review-object-grid-v1-10-4 {
    display: grid;
    grid-template-columns: 1fr 1.45fr;
    column-gap: 44px;
    row-gap: 20px;
    margin-bottom: 18px;
}

.file-review-object-field-label-v1-10-4 {
    font-size: 14px;
    line-height: 1.2;
    color: rgba(42, 31, 44, 0.52);
    margin-bottom: 12px;
}

.file-review-object-field-value-v1-10-4 {
    font-size: 16px;
    line-height: 1.42;
    color: #2A1F2C;
}

.file-review-object-notes-title-v1-10-4 {
    font-size: 14px;
    line-height: 1.2;
    color: rgba(42, 31, 44, 0.52);
    margin: 18px 0 10px 0;
}

.file-review-object-notes-list-v1-10-4 {
    margin: 0 0 0 22px;
    padding: 0;
    color: #2A1F2C;
}

.file-review-object-notes-list-v1-10-4 li {
    font-size: 16px;
    line-height: 1.45;
    margin: 8px 0;
}

@media (max-width: 760px) {
    .file-review-card-v1-10-4 {
        padding: 26px 22px 24px 22px;
    }

    .file-review-summary-grid-v1-10-4,
    .file-review-meta-row-v1-10-4 {
        grid-template-columns: 1fr;
        row-gap: 4px;
    }

    .file-review-value-v1-10-4 {
        font-size: 17px;
    }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _file_review_html_escape_v1_10_4(value) -> str:
    """Return a safe text representation for File Review HTML rendering."""
    import html as _html

    if _is_empty_value(value):
        return "—"

    return _html.escape(str(value))


def _file_review_missing_html_v1_10_4(value) -> str:
    """Render missing information as compact HTML bullets."""
    import html as _html

    points = split_text_to_points(value)

    if not points:
        return "<div class='file-review-muted-v1-10-4'>No major missing information detected.</div>"

    items = "".join(
        f"<li>{_html.escape(str(point))}</li>"
        for point in points
    )

    return f"<ul class='file-review-missing-list-v1-10-4'>{items}</ul>"


def _file_review_metadata_rows_html_v1_10_4(rows: list[tuple[str, object]]) -> str:
    """Render compact technical metadata rows without Streamlit dataframe spacing."""
    row_html = []

    for key, value in rows:
        row_html.append(
            "<div class='file-review-meta-row-v1-10-4'>"
            f"<div class='file-review-meta-key-v1-10-4'>{_file_review_html_escape_v1_10_4(key)}</div>"
            f"<div class='file-review-meta-value-v1-10-4'>{_file_review_html_escape_v1_10_4(value)}</div>"
            "</div>"
        )

    return "".join(row_html)


def render_file_review_card_v1_10_4(run: dict) -> None:
    """Render the top File Review card: summary, missing info and compact metadata."""
    project_name = run.get("project_name", "—")
    partner = run.get("client_or_design_partner", "Not detected")
    file_quality = run.get("file_quality_label", "—")

    metadata_rows = [
        ("Project name", run.get("project_name", "—")),
        ("Partner", run.get("client_or_design_partner", "Not detected")),
        ("File name", run.get("file_name", "—")),
        ("Pages detected", run.get("pages_detected", 0)),
        ("Source type", run.get("source_type", "—")),
        ("Author", run.get("author", "—")),
        ("Document date", run.get("document_date", "—")),
        ("Language", run.get("language", "—")),
        ("File quality confidence", format_confidence(run.get("file_quality_confidence", 0))),
        ("Run ID", run.get("run_id", "—")),
        ("Status", run.get("status", "—")),
    ]

    missing_html = _file_review_missing_html_v1_10_4(
        run.get("missing_information", "none")
    )

    metadata_html = _file_review_metadata_rows_html_v1_10_4(metadata_rows)

    st.html(
        f"""
<div class="file-review-card-v1-10-4">
    <div class="file-review-summary-grid-v1-10-4">
        <div class="file-review-label-v1-10-4">Project name:</div>
        <div class="file-review-value-v1-10-4">{_file_review_html_escape_v1_10_4(project_name)}</div>

        <div class="file-review-label-v1-10-4">Partner:</div>
        <div class="file-review-value-v1-10-4">{_file_review_html_escape_v1_10_4(partner)}</div>

        <div class="file-review-label-v1-10-4">File quality:</div>
        <div class="file-review-value-v1-10-4">{_file_review_html_escape_v1_10_4(file_quality)}</div>
    </div>

    <div class="file-review-divider-v1-10-4"></div>

    <div class="file-review-section-title-v1-10-4">Missing information:</div>
    {missing_html}

    <div class="file-review-divider-v1-10-4"></div>

    <details class="file-review-meta-details-v1-10-4">
        <summary class="file-review-meta-summary-v1-10-4">
            <span class="file-review-meta-title-v1-10-4">Technical metadata:</span>
        </summary>

        <div class="file-review-meta-table-v1-10-4">
            {metadata_html}
        </div>
    </details>
</div>
        """
    )
def _file_review_notes_html_v1_10_4(value) -> str:
    """Render detected-object notes as compact HTML bullets."""
    import html as _html

    points = split_text_to_points(value)

    if not points:
        return ""

    items = "".join(
        f"<li>{_html.escape(str(point))}</li>"
        for point in points
    )

    return (
        "<div class='file-review-object-notes-title-v1-10-4'>Notes</div>"
        f"<ul class='file-review-object-notes-list-v1-10-4'>{items}</ul>"
    )


def render_detected_object_card_v1_10_4(row) -> None:
    """Render one detected object as a white card aligned with File Review styling."""
    object_name = row.get("object_name", "Unknown object")
    quantity = format_quantity(row)
    confidence = format_confidence(row.get("confidence", 0))
    dimensions = format_dimensions(row.get("dimensions_json", {}))

    materials = row.get("detected_materials", "unknown")
    materials_text = "—" if _is_empty_value(materials) else materials

    notes_html = _file_review_notes_html_v1_10_4(row.get("notes", "none"))

    st.html(
        f"""
<div class="file-review-object-card-v1-10-4">
    <div class="file-review-object-top-v1-10-4">
        <div class="file-review-object-name-v1-10-4">{_file_review_html_escape_v1_10_4(object_name)}</div>

        <div>
            <div class="file-review-object-metric-label-v1-10-4">Qty</div>
            <div class="file-review-object-metric-value-v1-10-4">{_file_review_html_escape_v1_10_4(quantity)}</div>
        </div>

        <div>
            <div class="file-review-object-metric-label-v1-10-4">Confidence</div>
            <div class="file-review-object-metric-value-v1-10-4">{_file_review_html_escape_v1_10_4(confidence)}</div>
        </div>
    </div>

    <div class="file-review-object-grid-v1-10-4">
        <div>
            <div class="file-review-object-field-label-v1-10-4">Dimensions</div>
            <div class="file-review-object-field-value-v1-10-4">{_file_review_html_escape_v1_10_4(dimensions)}</div>
        </div>

        <div>
            <div class="file-review-object-field-label-v1-10-4">Materials</div>
            <div class="file-review-object-field-value-v1-10-4">{_file_review_html_escape_v1_10_4(materials_text)}</div>
        </div>
    </div>

    {notes_html}
</div>
        """
    )
# === COSTERLY_FILE_REVIEW_V1_10_4_END ===

def render_file_review_screen(company_id: str):
    render_post_upload_header("File Review")
    apply_file_review_v1_10_4_css()

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

    render_file_review_card_v1_10_4(run)

    st.html("<h1 class='file-review-detected-title-v1-10-4'>Detected objects</h1>")

    if objects_df.empty:
        st.warning("No objects detected.")
    else:
        for _, row in objects_df.iterrows():
            render_detected_object_card_v1_10_4(row)

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

# === COSTERLY_PROD_VERSION_MARKER_V1_9_35_START ===
def render_prod_version_marker_v1_9_35():
    st.markdown(
        """
        <div style="
            position: fixed;
            right: 10px;
            bottom: 8px;
            z-index: 999999;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 10px;
            line-height: 1;
            color: rgba(0,0,0,0.45);
            background: rgba(255,255,255,0.75);
            border: 1px solid rgba(0,0,0,0.10);
            border-radius: 999px;
            padding: 5px 7px;
            pointer-events: none;
        ">
            v1.9.35 / commit a7105eb
        </div>
        """,
        unsafe_allow_html=True,
    )
# === COSTERLY_PROD_VERSION_MARKER_V1_9_35_END ===

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

