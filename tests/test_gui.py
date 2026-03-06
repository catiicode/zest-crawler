import tkinter as tk

import pytest

from zest_crawler.gui import App, main


def test_gui_module_imports():
    assert callable(main)
    assert issubclass(App, tk.Tk)


def test_app_full():
    """Test widget creation, defaults, logging, and validation in a single Tk session."""
    app = App()
    try:
        # Widgets exist
        assert hasattr(app, "url_entry")
        assert hasattr(app, "output_entry")
        assert hasattr(app, "proxy_entry")
        assert hasattr(app, "progress_bar")
        assert hasattr(app, "log_text")
        assert hasattr(app, "start_btn")
        assert hasattr(app, "stop_btn")

        # Default values
        assert app.output_entry.get() == "./output"
        assert app.concurrency_var.get() == 2
        assert app.headless_var.get() == 0

        # Log appends messages
        app.log("line 1")
        app.log("line 2")
        log_content = app.log_text.get("1.0", tk.END)
        assert "line 1" in log_content
        assert "line 2" in log_content

        # Empty URL validation
        app.url_entry.delete(0, tk.END)
        app._on_start_sync_fallback()
        log_content = app.log_text.get("1.0", tk.END)
        assert "请输入" in log_content
    finally:
        app.destroy()
