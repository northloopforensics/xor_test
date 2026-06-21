#!/usr/bin/env python3
"""
XOR Cipher Playground — Streamlit Web App
==========================================
Interactive demo of 64-bit keyed XOR encoding with TTL constraints.
Shows how XOR can bind an input string to a timestamp using a secret key.

Run:
    streamlit run xor_playground.py
"""

import csv
import hashlib
import hmac
import io
import json
import os
import sys
from datetime import date, datetime, timedelta

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xor_core import xor_encode, get_ttl_date, xor_validate

# ── Secrets (loaded from Streamlit secrets — never hardcoded in repo) ─────────
# Local dev:  .streamlit/secrets.toml  (gitignored)
# Production: Streamlit Community Cloud dashboard → App settings → Secrets
try:
    _KEY_PRESET_A: int = int(st.secrets["XOR_KEY_PRESET_A"], 16)
    _PHRASE_PRESET_B: str = st.secrets["XOR_PHRASE_PRESET_B"]
    _APP_PASSWORD: str = st.secrets["APP_PASSWORD"]
except KeyError as _e:
    st.error(
        f"Missing secret: **{_e}**. "
        "Add it to `.streamlit/secrets.toml` (local) or the Streamlit Cloud dashboard (production)."
    )
    st.stop()

_KEY_PRESET_B: int = int.from_bytes(
    hashlib.sha256(_PHRASE_PRESET_B.encode()).digest()[:8], "big"
)

_PRESETS: dict[str, dict] = {
    "Preset - A Seaweed": {
        "label": "Preset - A Seaweed",
        "secret": _KEY_PRESET_A,
        "hint": "Fixed 64-bit XOR key",
    },
    "Preset - B Vision": {
        "label": "Preset - B Vision",
        "secret": _KEY_PRESET_B,
        "hint": "Key derived via SHA-256 from a passphrase",
    },
}

# ── Auth ──────────────────────────────────────────────────────────────────────
def _check_password(pw: str) -> bool:
    """Constant-time password comparison to prevent timing attacks."""
    return hmac.compare_digest(
        hashlib.sha256(pw.encode()).hexdigest(),
        hashlib.sha256(_APP_PASSWORD.encode()).hexdigest(),
    )


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="XOR Cipher Playground",
    page_icon="⊕",
    layout="centered",
)

# ── Session state defaults ────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "authenticated": False,
    "encoding_log": [],        # list[dict] — history for this session
    "last_output": None,       # most recently encoded output
    "last_preset": None,       # preset label used at encode time
    "last_input": None,        # input string used at encode time
    "last_ttl": None,          # TTL string used at encode time
    "exp_date": date.today() + timedelta(days=365),
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Login gate ────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.title("⊕ XOR Cipher Playground")
    st.markdown("---")
    with st.form("login"):
        pw = st.text_input("Password", type="password", placeholder="Enter password")
        if st.form_submit_button("Login", use_container_width=True, type="primary"):
            if _check_password(pw):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()


# ═════════════════════════════════════════════════════════════════════════════
# Main App  (only reached after successful authentication)
# ═════════════════════════════════════════════════════════════════════════════
title_col, logout_col = st.columns([5, 1])
title_col.title("⊕ XOR Cipher Playground")
if logout_col.button("Logout"):
    st.session_state.authenticated = False
    st.rerun()

st.caption("64-bit keyed XOR encoding — input string × TTL timestamp")
st.markdown("---")

# ── Encode ────────────────────────────────────────────────────────────────────
st.subheader("Encode")

preset_key = st.selectbox("Key Preset", list(_PRESETS.keys()), index=1)
config = _PRESETS[preset_key]
st.caption(f"ℹ️ {config['hint']}")

input_str = st.text_input(
    "Input String",
    placeholder="Paste the input string here",
)

test_input = st.text_input(
    "Test / Compare String",
    placeholder="Optional — enter a second string to compare XOR output",
)
if test_input.strip():
    st.caption(
        f"XOR distance (bit diff): `{bin(int(hashlib.sha256(input_str.encode()).hexdigest()[:8], 16) ^ int(hashlib.sha256(test_input.encode()).hexdigest()[:8], 16)).count('1')}` bits differ"
    )

# TTL — quick-set buttons inside a collapsed expander
with st.expander("TTL offset shortcuts"):
    q_cols = st.columns(5)
    for col, (label, days) in zip(
        q_cols,
        [("+30d", 30), ("+90d", 90), ("+1y", 365), ("+2y", 730), ("+5y", 1825)],
    ):
        if col.button(label, use_container_width=True):
            st.session_state.exp_date = date.today() + timedelta(days=days)
            st.rerun()

exp_date: date = st.date_input(
    "TTL Date",
    value=st.session_state.exp_date,
)
# Sync manual edits back to session state
st.session_state.exp_date = exp_date

st.markdown("")

# ── Encode button ─────────────────────────────────────────────────────────────
if st.button("⚡  Encode", type="primary", use_container_width=True):
    input_clean = input_str.strip()
    if not input_clean:
        st.error("Please enter an input string.")
    else:
        ttl_dt = datetime.combine(exp_date, datetime.max.time().replace(microsecond=0))
        if ttl_dt < datetime.now():
            st.warning("⚠️ The TTL date is in the past — encoding anyway.")
        try:
            output = xor_encode(input_clean, ttl_dt, config["secret"])
            # Store result — preset config is looked up by label, secret never stored
            st.session_state.last_output = output
            st.session_state.last_preset = config["label"]
            st.session_state.last_input = input_clean
            st.session_state.last_ttl = exp_date.strftime("%Y-%m-%d")

            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "preset": config["label"],
                "input": input_clean,
                "ttl": exp_date.strftime("%Y-%m-%d"),
                "output": output,
                # secret is intentionally excluded from all exports/history
            }
            st.session_state.encoding_log.insert(0, record)
            st.success(
                f"Encoded with **{config['label']}** — TTL **{exp_date}**"
            )
        except Exception as exc:
            st.error(f"Encoding failed: {exc}")

# ── Result display ────────────────────────────────────────────────────────────
if st.session_state.last_output:
    st.markdown("---")
    st.subheader("Encoded Output")
    # st.code renders with a built-in copy button
    st.code(st.session_state.last_output, language=None)
    st.caption(
        f"Preset: **{st.session_state.last_preset}** · "
        f"TTL: **{st.session_state.last_ttl}**"
    )

    if st.button("✅  Decode & Verify"):
        # Resolve the secret by matching the stored preset label — key never leaves server
        matched = next(
            (c for c in _PRESETS.values() if c["label"] == st.session_state.last_preset),
            None,
        )
        if matched is None:
            st.error("Could not resolve preset for verification.")
        elif not st.session_state.last_input:
            st.error("No input string stored for verification.")
        else:
            is_valid = xor_validate(
                st.session_state.last_output,
                st.session_state.last_input,
                matched["secret"],
            )
            if is_valid:
                ttl_dt = get_ttl_date(st.session_state.last_output, matched["secret"])
                st.success(f"✅ VALID — TTL {ttl_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                st.error("❌ INVALID — Output does not match input string or TTL has elapsed.")

# ── Encoding Log ──────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Encoding Log")

if st.session_state.encoding_log:
    # Display table (secret key is intentionally excluded)
    display_rows = [
        {
            "Encoded At": r["timestamp"],
            "Preset": r["preset"],
            "Input": r["input"][:16] + "…" if len(r["input"]) > 16 else r["input"],
            "TTL": r["ttl"],
            "Output": r["output"],
        }
        for r in st.session_state.encoding_log
    ]
    st.dataframe(display_rows, use_container_width=True)

    _EXPORT_FIELDS = ["timestamp", "preset", "input", "ttl", "output"]
    safe_records = [{k: r[k] for k in _EXPORT_FIELDS} for r in st.session_state.encoding_log]
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV export
    csv_buf = io.StringIO()
    w = csv.DictWriter(csv_buf, fieldnames=_EXPORT_FIELDS)
    w.writeheader()
    w.writerows(safe_records)

    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])
    btn_col1.download_button(
        "Export CSV",
        data=csv_buf.getvalue(),
        file_name=f"xor_log_{timestamp_str}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    btn_col2.download_button(
        "Export JSON",
        data=json.dumps(safe_records, indent=2),
        file_name=f"xor_log_{timestamp_str}.json",
        mime="application/json",
        use_container_width=True,
    )
    if btn_col3.button("🗑️  Clear Log"):
        st.session_state.encoding_log = []
        st.session_state.last_output = None
        st.session_state.last_preset = None
        st.session_state.last_input = None
        st.session_state.last_ttl = None
        st.rerun()
else:
    st.caption("No encodings yet in this session.")
