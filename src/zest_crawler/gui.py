"""tkinter GUI for zest-crawler."""

import asyncio
import logging
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import ttk, filedialog, scrolledtext

from async_tkinter_loop import async_handler, async_mainloop

from zest_crawler.analyzer import GeoGebraAnalyzer
from zest_crawler.downloader import Downloader
from zest_crawler.models import GeoGebraResource
from zest_crawler.router import parse_url
from zest_crawler.storage import Storage

logger = logging.getLogger(__name__)


class App(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("GeoGebra 资源下载器")
        self.geometry("640x520")
        self.resizable(True, True)

        self._downloading = False
        self._cancel_requested = False
        self._build_ui()

    # ── UI Construction ──────────────────────────────────────

    def _build_ui(self) -> None:
        form = ttk.LabelFrame(self, text="下载设置", padding=10)
        form.pack(fill=tk.X, padx=10, pady=(10, 5))

        # Row 0: URL
        ttk.Label(form, text="资源地址:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.url_entry = ttk.Entry(form)
        self.url_entry.grid(row=0, column=1, sticky=tk.EW, padx=(5, 0), pady=3)
        form.columnconfigure(1, weight=1)

        # Row 1: Output directory
        ttk.Label(form, text="保存目录:").grid(row=1, column=0, sticky=tk.W, pady=3)
        out_frame = ttk.Frame(form)
        out_frame.grid(row=1, column=1, sticky=tk.EW, padx=(5, 0), pady=3)
        self.output_entry = ttk.Entry(out_frame)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.output_entry.insert(0, "./output")
        ttk.Button(out_frame, text="选择…", width=6,
                   command=self._choose_output_dir).pack(side=tk.RIGHT, padx=(5, 0))

        # Row 2: Proxy
        ttk.Label(form, text="代理地址:").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.proxy_entry = ttk.Entry(form)
        self.proxy_entry.grid(row=2, column=1, sticky=tk.EW, padx=(5, 0), pady=3)
        self.proxy_entry.insert(0, "http://127.0.0.1:62340")

        # Row 3: Concurrency + timeout + headless
        ttk.Label(form, text="并发数:").grid(row=3, column=0, sticky=tk.W, pady=3)
        opt_frame = ttk.Frame(form)
        opt_frame.grid(row=3, column=1, sticky=tk.W, padx=(5, 0), pady=3)
        self.concurrency_var = tk.IntVar(value=2)
        ttk.Spinbox(opt_frame, from_=1, to=5, width=4,
                    textvariable=self.concurrency_var).pack(side=tk.LEFT)
        ttk.Label(opt_frame, text="超时(秒):").pack(side=tk.LEFT, padx=(20, 0))
        self.timeout_var = tk.IntVar(value=60)
        ttk.Spinbox(opt_frame, from_=30, to=300, width=5, increment=10,
                    textvariable=self.timeout_var).pack(side=tk.LEFT, padx=(5, 0))
        self.headless_var = tk.IntVar(value=0)
        ttk.Checkbutton(opt_frame, text="显示浏览器窗口",
                        variable=self.headless_var).pack(side=tk.LEFT, padx=(20, 0))

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        self.start_btn = ttk.Button(btn_frame, text="开始下载",
                                    command=async_handler(self._on_start))
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.stop_btn = ttk.Button(btn_frame, text="停止",
                                   command=self._on_stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="清除日志",
                   command=self._clear_log).pack(side=tk.RIGHT)

        # Progress bar
        self.progress_bar = ttk.Progressbar(self, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=10, pady=(0, 5))
        self.progress_label = ttk.Label(self, text="就绪")
        self.progress_label.pack(anchor=tk.W, padx=10)

        # Log area
        self.log_text = scrolledtext.ScrolledText(
            self, height=12, state=tk.DISABLED, font=("Consolas", 9),
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

    # ── Helpers ───────────────────────────────────────────────

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def log(self, message: str) -> None:
        """Append a line to the log area."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        """Clear all log content."""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _set_downloading(self, active: bool) -> None:
        """Toggle UI state between downloading / idle."""
        self._downloading = active
        self._cancel_requested = False
        state = tk.DISABLED if active else tk.NORMAL
        self.start_btn.configure(state=state)
        self.url_entry.configure(state=state)
        self.output_entry.configure(state=state)
        self.proxy_entry.configure(state=state)
        self.stop_btn.configure(state=tk.NORMAL if active else tk.DISABLED)

    # ── Download Logic ────────────────────────────────────────

    async def _on_start(self) -> None:
        """Validate inputs, then run the download pipeline."""
        url = self.url_entry.get().strip()
        if not url:
            self.log("错误: 请输入资源地址")
            return

        try:
            parsed = parse_url(url)
        except ValueError as e:
            self.log(f"错误: {e}")
            return

        output_dir = self.output_entry.get().strip() or "./output"
        proxy = self.proxy_entry.get().strip() or None
        concurrency = self.concurrency_var.get()
        timeout = self.timeout_var.get() * 1000  # seconds -> milliseconds
        headless = self.headless_var.get() == 0  # unchecked = headless

        self._set_downloading(True)
        self.progress_bar["value"] = 0
        self.progress_label.configure(text="正在分析页面…")
        self.log(f"正在分析: {url}")

        try:
            # Step 1: Analyze
            analyzer = GeoGebraAnalyzer(headless=headless, proxy=proxy, timeout=timeout)
            resources = await analyzer.analyze(parsed)

            if not resources:
                self.log("未发现任何资源。")
                return

            self.log(f"发现 {len(resources)} 个资源")

            # Setup storage
            subdir = parsed.identifier
            storage = Storage(output_dir=Path(output_dir) / subdir)
            storage.ensure_dir()

            # Step 2: Download and save one by one
            self.progress_bar["maximum"] = len(resources)
            self.progress_label.configure(text=f"正在下载 0/{len(resources)}")

            downloader = Downloader(
                concurrency=concurrency,
                headless=headless,
                proxy=proxy,
                timeout=timeout,
            )

            now = datetime.now(timezone.utc).isoformat()
            success_count = 0
            material_ids = [r.material_id for r in resources]
            i = 0

            async for result in downloader.download_iter(material_ids):
                if self._cancel_requested:
                    self.log("已停止下载。")
                    break

                i += 1
                resource = resources[i - 1]

                if result.success and result.content:
                    filename = storage.make_filename(i, resource.title)
                    storage.save_file(filename, result.content)
                    resource.filename = filename
                    resource.download_time = now
                    success_count += 1
                    self.log(f"  [{i}/{len(resources)}] 已下载: {filename}")
                else:
                    self.log(
                        f"  [{i}/{len(resources)}] 失败: {resource.title}"
                        f" ({result.error})"
                    )

                self.progress_bar["value"] = i
                self.progress_label.configure(
                    text=f"正在下载 {i}/{len(resources)}"
                )

            # Step 3: Metadata
            storage.write_metadata(resources)
            self.log(
                f"\n完成! {success_count}/{len(resources)} 个文件已保存到"
                f" {storage.output_dir}"
            )
            self.progress_label.configure(
                text=f"完成 {success_count}/{len(resources)}"
            )

        except Exception as e:
            self.log(f"错误: {e}")
            logger.exception("Download failed")
        finally:
            self._set_downloading(False)

    def _on_stop(self) -> None:
        """Request cancellation of the current download."""
        self._cancel_requested = True
        self.log("正在停止…")

    def _on_start_sync_fallback(self) -> None:
        """Non-async validation only — used in tests without async loop."""
        url = self.url_entry.get().strip()
        if not url:
            self.log("错误: 请输入资源地址")
            return


def main() -> None:
    """Entry point for the GUI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    app = App()
    async_mainloop(app)


if __name__ == "__main__":
    main()
