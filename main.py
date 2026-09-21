import os
import sys
import tempfile
import queue
import subprocess
import socket
import threading

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_VERSION = "1.0.0"


PROXY_LIST_URL = (
    "https://cdn.jsdelivr.net/gh/proxyscrape/"
    "free-proxy-list@main/proxies/all/data.json"
)

TEST_URLS = [
    "https://www.google.com/generate_204",
    "https://www.cloudflare.com/cdn-cgi/trace",
    "https://example.com/",
]

EXIT_IP_URL = "https://api.ipify.org?format=json"
RESIDENTIAL_PROXY_URL = (
    "https://raw.githubusercontent.com/"
    "stormsia/proxy-list/main/web/public/proxies.json"
)

RESIDENTIAL_DC_KEYWORDS = [
    "digitalocean",
    "amazon",
    "aws",
    "hosting",
    "ovh",
    "hetzner",
    "linode",
    "vultr",
    "contabo",
    "datacamp",
    "cloudflare",
    "google",
    "microsoft",
    "azure",
    "server",
    "datacenter",
    "data center",
    "colocation",
]

GEO_URL = "https://ipwho.is/{ip}"

MAX_WORKERS = 50

TCP_TIMEOUT = 3
PROXY_TIMEOUT = 6
EXIT_TIMEOUT = 8
GEO_TIMEOUT = 6


class ProxyCheckerApp:

    def __init__(self, root):
        self.root = root

        self.root.title(f"代理查找检测工具 v{APP_VERSION}")
        if getattr(sys, "frozen", False):
            icon_path = os.path.join(
                sys._MEIPASS,
                "a1.ico"
            )
        else:
            icon_path = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)
                ),
                "a1.ico"
            )

        try:
            self.root.iconbitmap(icon_path)
        except tk.TclError:
            pass
        self.root.geometry("1250x820")
        self.root.minsize(1050, 700)

        self.proxy_list = []

        self.public_results = []
        self.exit_results = []

        self.result_queue = queue.Queue()

        self.stop_event = threading.Event()

        self.fetch_thread = None
        self.test_thread = None

        self.total_count = 0
        self.checked_count = 0
        self.working_count = 0
        self.residential_finished = False
        self.public_finished = False

        self.build_ui()

        self.root.after(
            100,
            self.process_queue
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

    # ==========================================================
    # UI
    # ==========================================================

    def build_ui(self):

        # ------------------------------------------------------
        # 顶部状态
        # ------------------------------------------------------

        top_frame = ttk.Frame(self.root)

        top_frame.pack(
            fill="x",
            padx=10,
            pady=(10, 5)
        )

        self.total_label = ttk.Label(
            top_frame,
            text="代理总数：0"
        )

        self.total_label.pack(
            side="left",
            padx=10
        )

        self.checked_label = ttk.Label(
            top_frame,
            text="已检测：0"
        )

        self.checked_label.pack(
            side="left",
            padx=10
        )

        self.working_label = ttk.Label(
            top_frame,
            text="可用代理：0"
        )

        self.working_label.pack(
            side="left",
            padx=10
        )

        self.status_label = ttk.Label(
            top_frame,
            text="状态：准备就绪"
        )

        self.status_label.pack(
            side="left",
            padx=10
        )

        # ------------------------------------------------------
        # 进度条
        # ------------------------------------------------------

        progress_frame = ttk.Frame(self.root)

        progress_frame.pack(
            fill="x",
            padx=20,
            pady=(3, 8)
        )

        self.progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            value=0
        )

        self.progress.pack(
            side="left",
            fill="x",
            expand=True
        )

        self.progress_label = ttk.Label(
            progress_frame,
            text="0.0%"
        )

        self.progress_label.pack(
            side="left",
            padx=(10, 0)
        )

        # ------------------------------------------------------
        # 按钮
        # ------------------------------------------------------

        button_frame = ttk.Frame(self.root)

        button_frame.pack(
            fill="x",
            padx=10,
            pady=5
        )

        self.fetch_button = ttk.Button(
            button_frame,
            text="获取代理",
            command=self.fetch_proxies
        )

        self.fetch_button.pack(
            side="left",
            padx=5
        )

        self.start_button = ttk.Button(
            button_frame,
            text="开始检测",
            command=self.start_test
        )

        self.start_button.pack(
            side="left",
            padx=5
        )

        self.stop_button = ttk.Button(
            button_frame,
            text="停止检测",
            command=self.stop_test
        )

        self.stop_button.pack(
            side="left",
            padx=5
        )

        self.selected_button = ttk.Button(
            button_frame,
            text="测试选中",
            command=self.test_selected
        )

        self.selected_button.pack(
            side="left",
            padx=5
        )

        self.export_button = ttk.Button(
            button_frame,
            text="导出 TXT",
            command=self.export_txt
        )

        self.export_button.pack(
            side="left",
            padx=5
        )

        self.clear_button = ttk.Button(
            button_frame,
            text="清空结果",
            command=self.clear_results
        )

        self.clear_button.pack(
            side="left",
            padx=5
        )

        self.update_button = ttk.Button(
            button_frame,
            text="检查更新",
            command=self.check_update
        )

        self.update_button.pack(
            side="left",
            padx=5
        )

        # ======================================================
        # ① 公共代理检测结果
        # ======================================================

        title1 = ttk.Label(
            self.root,
            text="① 公共代理检测结果",
            font=("Microsoft YaHei UI", 11, "bold")
        )

        title1.pack(
            anchor="w",
            padx=10,
            pady=(10, 4)
        )

        table1_frame = ttk.Frame(self.root)

        table1_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 8)
        )

        columns1 = (
            "protocol",
            "ip",
            "port",
            "country",
            "tcp_delay",
            "proxy_delay",
            "result"
        )

        self.public_tree = ttk.Treeview(
            table1_frame,
            columns=columns1,
            show="headings",
            selectmode="extended"
        )

        self.public_tree.heading(
            "protocol",
            text="协议"
        )

        self.public_tree.heading(
            "ip",
            text="IP地址"
        )

        self.public_tree.heading(
            "port",
            text="端口"
        )

        self.public_tree.heading(
            "country",
            text="IP所在国家"
        )

        self.public_tree.heading(
            "tcp_delay",
            text="TCP延迟"
        )

        self.public_tree.heading(
            "proxy_delay",
            text="代理延迟"
        )

        self.public_tree.heading(
            "result",
            text="测试结果"
        )

        self.public_tree.column(
            "protocol",
            width=80,
            anchor="center"
        )

        self.public_tree.column(
            "ip",
            width=160,
            anchor="center"
        )

        self.public_tree.column(
            "port",
            width=80,
            anchor="center"
        )

        self.public_tree.column(
            "country",
            width=130,
            anchor="center"
        )

        self.public_tree.column(
            "tcp_delay",
            width=100,
            anchor="center"
        )

        self.public_tree.column(
            "proxy_delay",
            width=100,
            anchor="center"
        )

        self.public_tree.column(
            "result",
            width=120,
            anchor="center"
        )

        scrollbar1 = ttk.Scrollbar(
            table1_frame,
            orient="vertical",
            command=self.public_tree.yview
        )

        self.public_tree.configure(
            yscrollcommand=scrollbar1.set
        )

        self.public_tree.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar1.pack(
            side="right",
            fill="y"
        )

        # ------------------------------------------------------
        # ①右键菜单
        # ------------------------------------------------------

        self.public_menu = tk.Menu(
            self.root,
            tearoff=False
        )

        self.public_menu.add_command(
            label="复制 IP",
            command=self.copy_selected_ip
        )

        self.public_menu.add_command(
            label="复制 IP:端口",
            command=self.copy_selected_ip_port
        )

        self.public_menu.add_command(
            label="复制端口",
            command=self.copy_selected_port
        )

        self.public_menu.add_separator()

        self.public_menu.add_command(
            label="复制整行",
            command=self.copy_selected_row
        )

        self.public_tree.bind(
            "<Button-3>",
            self.show_public_menu
        )

        self.public_tree.bind(
            "<Control-c>",
            self.copy_selected_row
        )

        self.public_tree.bind(
            "<<TreeviewSelect>>",
            self.update_selection_label
        )

        # ======================================================
        # ② 国外出口识别结果
        # ======================================================

        title2 = ttk.Label(
            self.root,
            text="② Residential / 住宅代理出口识别结果",
            font=("Microsoft YaHei UI", 11, "bold")
        )

        title2.pack(
            anchor="w",
            padx=10,
            pady=(5, 4)
        )

        table2_frame = ttk.Frame(self.root)

        table2_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 5)
        )

        columns2 = (
            "protocol",
            "proxy_ip",
            "proxy_port",
            "exit_ip",
            "country",
            "city",
            "delay"
        )

        self.exit_tree = ttk.Treeview(
            table2_frame,
            columns=columns2,
            show="headings",
            selectmode="extended"
        )

        self.exit_tree.heading(
            "protocol",
            text="协议"
        )

        self.exit_tree.heading(
            "proxy_ip",
            text="代理IP"
        )

        self.exit_tree.heading(
            "proxy_port",
            text="端口"
        )

        self.exit_tree.heading(
            "exit_ip",
            text="出口IP"
        )

        self.exit_tree.heading(
            "country",
            text="国家"
        )

        self.exit_tree.heading(
            "city",
            text="城市"
        )

        self.exit_tree.heading(
            "delay",
            text="延迟"
        )

        self.exit_tree.column(
            "protocol",
            width=80,
            anchor="center"
        )

        self.exit_tree.column(
            "proxy_ip",
            width=160,
            anchor="center"
        )

        self.exit_tree.column(
            "proxy_port",
            width=80,
            anchor="center"
        )

        self.exit_tree.column(
            "exit_ip",
            width=160,
            anchor="center"
        )

        self.exit_tree.column(
            "country",
            width=120,
            anchor="center"
        )

        self.exit_tree.column(
            "city",
            width=120,
            anchor="center"
        )

        self.exit_tree.column(
            "delay",
            width=100,
            anchor="center"
        )

        scrollbar2 = ttk.Scrollbar(
            table2_frame,
            orient="vertical",
            command=self.exit_tree.yview
        )

        self.exit_tree.configure(
            yscrollcommand=scrollbar2.set
        )

        self.exit_tree.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar2.pack(
            side="right",
            fill="y"
        )

        # ------------------------------------------------------
        # ②右键菜单
        # ------------------------------------------------------

        self.exit_menu = tk.Menu(
            self.root,
            tearoff=False
        )

        self.exit_menu.add_command(
            label="复制代理IP",
            command=self.copy_exit_proxy_ip
        )

        self.exit_menu.add_command(
            label="复制代理IP:端口",
            command=self.copy_exit_proxy_ip_port
        )

        self.exit_menu.add_command(
            label="复制出口IP",
            command=self.copy_exit_ip
        )

        self.exit_menu.add_separator()

        self.exit_menu.add_command(
            label="复制整行",
            command=self.copy_exit_row
        )

        self.exit_tree.bind(
            "<Button-3>",
            self.show_exit_menu
        )

        self.exit_tree.bind(
            "<Control-c>",
            self.copy_exit_row
        )

        # ------------------------------------------------------
        # 底部
        # ------------------------------------------------------

        bottom_frame = ttk.Frame(self.root)

        bottom_frame.pack(
            fill="x",
            padx=10,
            pady=(0, 8)
        )

        self.selection_label = ttk.Label(
            bottom_frame,
            text="当前选择：0 个"
        )

        self.selection_label.pack(
            side="left"
        )

    # ==========================================================
    # 状态
    # ==========================================================

    def set_status(
        self,
        text
    ):

        self.result_queue.put(
            (
                "status",
                text
            )
        )

    # ==========================================================
    # 获取代理
    # ==========================================================

    def get_latest_release(self):
        try:
            response = requests.get(
                "https://api.github.com/repos/JAYGZ1/ProxyFinder/releases/latest",
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

            print("GitHub 最新版本：", data.get("tag_name"))
            print("Release 名称：", data.get("name"))
            print("附件数量：", len(data.get("assets", [])))

            return data

        except Exception as e:
            print(f"获取 GitHub Release 失败：{e}")
            return None

    def download_update(self, download_url, output_path):
        try:

            with requests.get(
                    download_url,
                    stream=True,
                    timeout=30
            ) as response:

                response.raise_for_status()

                total_size = int(
                    response.headers.get("Content-Length", 0)
                )

                downloaded_size = 0

                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(
                            chunk_size=1024 * 64
                    ):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            if total_size > 0:
                                percent = (
                                        downloaded_size
                                        / total_size
                                        * 100
                                )

                                self.root.after(
                                    0,
                                    self.update_download_progress,
                                    percent,
                                    downloaded_size,
                                    total_size
                                )

            return True

        except Exception as e:
            print(f"下载更新失败：{e}")
            return False

    def update_download_progress(
            self,
            percent,
            downloaded_size,
            total_size
    ):
        downloaded_mb = downloaded_size / 1024 / 1024
        total_mb = total_size / 1024 / 1024

        self.progress["value"] = percent
        self.progress_label.config(
            text=f"{percent:.1f}%"
        )
        self.status_label.config(
            text=(
                f"状态：正在下载更新 "
                f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB"
            )
        )

    def check_update(self):
        release = self.get_latest_release()

        if not release:
            messagebox.showerror(
                "检查更新失败",
                "无法获取 GitHub 最新版本。\n\n"
                "请确认网络连接和 GitHub 登录状态。"
            )
            return

        latest_version = release.get("tag_name", "").lstrip("v")

        if not latest_version:
            messagebox.showerror(
                "检查更新失败",
                "无法获取最新版本号。"
            )
            return

        if latest_version == APP_VERSION:
            messagebox.showinfo(
                "检查更新",
                f"当前版本：v{APP_VERSION}\n\n"
                "已经是最新版本。"
            )
        else:
            assets = release.get("assets", [])

            exe_asset = None

            for asset in assets:
                if asset.get("name", "").lower().endswith(".exe"):
                    exe_asset = asset
                    break

            if not exe_asset:
                messagebox.showerror(
                    "检查更新失败",
                    "最新版本没有找到 EXE 更新文件。"
                )
                return

            download_url = exe_asset.get("browser_download_url", "")

            answer = messagebox.askyesno(
                "发现新版本",
                f"当前版本：v{APP_VERSION}\n"
                f"最新版本：v{latest_version}\n\n"
                f"更新文件：{exe_asset.get('name')}\n\n"
                "是否立即下载更新？"
            )

            if not answer:
                return

            output_path = os.path.join(
                tempfile.gettempdir(),
                exe_asset.get("name", "update.exe")
            )

            print("准备下载更新：", exe_asset.get("name"))
            print("下载地址：", download_url)
            print("保存位置：", output_path)

            success = self.download_update(
                download_url,
                output_path
            )

            if success:
                self.root.after(
                    0,
                    self.update_download_progress,
                    100,
                    1,
                    1
                )

                self.status_label.config(
                    text="状态：更新下载完成，正在安装..."
                )

                self.root.update_idletasks()

                current_exe = sys.executable

                updater_script = os.path.join(
                    tempfile.gettempdir(),
                    "LswProxyFinder_updater.exe"
                )

                if not os.path.exists(updater_script):
                    updater_data = getattr(sys, "_MEIPASS", os.path.dirname(current_exe))
                    bundled_updater = os.path.join(
                        updater_data,
                        "updater.exe"
                    )

                    with open(bundled_updater, "rb") as src:
                        with open(updater_script, "wb") as dst:
                            dst.write(src.read())

                subprocess.Popen([
                    updater_script,
                    current_exe,
                    output_path
                ])

                self.root.destroy()
                return

            else:
                messagebox.showerror(
                    "下载失败",
                    "更新文件下载失败。\n\n"
                    "请查看终端中的错误信息。"
                )

    def fetch_residential_proxies(self):
        try:
            response = requests.get(
                RESIDENTIAL_PROXY_URL,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            residential_proxies = []

            for item in data:
                asn = item.get("asn") or {}

                asn_org = (
                    asn.get(
                        "autonomous_system_organization",
                        ""
                    )
                    or ""
                ).lower()

                # 按照 Stormsia 官方 Residential 页面规则筛选
                if any(
                    keyword in asn_org
                    for keyword in RESIDENTIAL_DC_KEYWORDS
                ):
                    continue

                residential_proxies.append(
                    {
                        "protocol": item.get(
                            "protocol",
                            ""
                        ),
                        "ip": item.get(
                            "host",
                            ""
                        ),
                        "port": item.get(
                            "port",
                            ""
                        ),
                        "exit_ip": item.get(
                            "exit_ip",
                            ""
                        ),
                        "country": (
                            item.get(
                                "geolocation"
                            ) or {}
                        ).get(
                            "country",
                            ""
                        ),
                        "city": (
                            item.get(
                                "geolocation"
                            ) or {}
                        ).get(
                            "city",
                            ""
                        ),
                        "asn": asn.get(
                            "autonomous_system_number",
                            ""
                        ),
                        "isp": asn.get(
                            "autonomous_system_organization",
                            ""
                        )
                    }
                )

            print(
                "Stormsia Residential 候选数量：",
                len(residential_proxies)
            )

            print(
                "Stormsia Residential 第一个：",
                residential_proxies[0] if residential_proxies else None
            )

            return residential_proxies

        except Exception as e:
            print(
                f"获取 Stormsia Residential 数据失败：{e}"
            )
            return []

    def fetch_proxies(self):

        if (
            self.fetch_thread
            and
            self.fetch_thread.is_alive()
        ):
            return

        self.set_status(
            "获取代理中"
        )

        self.fetch_button.config(
            state="disabled"
        )

        self.fetch_thread = threading.Thread(
            target=self.fetch_worker,
            daemon=True
        )

        self.fetch_thread.start()

    def fetch_worker(self):

        try:

            response = requests.get(
                PROXY_LIST_URL,
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list):

                raise ValueError(
                    "代理列表格式错误"
                )

            proxies = []

            for item in data:

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                protocol = str(
                    item.get(
                        "protocol",
                        ""
                    )
                ).strip().lower()

                ip = str(
                    item.get(
                        "ip",
                        ""
                    )
                ).strip()

                port = str(
                    item.get(
                        "port",
                        ""
                    )
                ).strip()

                if (
                    not protocol
                    or
                    not ip
                    or
                    not port
                ):
                    continue

                try:

                    port_number = int(
                        port
                    )

                    if not (
                        1
                        <=
                        port_number
                        <=
                        65535
                    ):
                        continue

                except ValueError:

                    continue

                proxies.append({
                    "protocol": protocol,
                    "ip": ip,
                    "port": port
                })

            self.result_queue.put(
                (
                    "fetch_done",
                    proxies
                )
            )

        except Exception as e:

            self.result_queue.put(
                (
                    "fetch_error",
                    str(e)
                )
            )

    # ==========================================================
    # 开始检测
    # ==========================================================

    def start_test(self):

        if not self.proxy_list:

            messagebox.showwarning(
                "提示",
                "请先点击“获取代理”。"
            )

            return

        if (
            self.test_thread
            and
            self.test_thread.is_alive()
        ):
            return

        self.stop_event.clear()

        self.checked_count = 0
        self.working_count = 0

        self.residential_finished = False
        self.public_finished = False

        self.public_results.clear()
        self.exit_results.clear()

        self.clear_tree(
            self.public_tree
        )

        self.clear_tree(
            self.exit_tree
        )

        # 重置进度条

        self.progress["value"] = 0

        self.progress_label.config(
            text="0.0%"
        )

        self.update_stats()

        self.set_status(
            "检测中"
        )

        self.start_button.config(
            state="disabled"
        )

        self.test_thread = threading.Thread(
            target=self.test_all_worker,
            daemon=True
        )

        self.test_thread.start()

        self.residential_thread = threading.Thread(
            target=self.residential_worker,
            daemon=True
        )

        self.residential_thread.start()


    def check_residential_tcp(self, proxy):
        protocol = proxy.get("protocol", "")
        proxy_ip = proxy.get("ip", "")
        proxy_port = proxy.get("port", "")

        start = time.perf_counter()

        try:
            sock = socket.create_connection(
                (
                    proxy_ip,
                    int(proxy_port)
                ),
                timeout=TCP_TIMEOUT
            )

            sock.close()

            tcp_delay = (
                time.perf_counter()
                -
                start
            ) * 1000

            return tcp_delay

        except Exception:
            return None

    def check_residential_proxy(self, proxy):
        protocol = proxy.get("protocol", "")
        proxy_ip = proxy.get("ip", "")
        proxy_port = proxy.get("port", "")

        proxy_url = (
            f"{protocol}://"
            f"{proxy_ip}:"
            f"{proxy_port}"
        )

        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }

        test_urls = [
            "https://www.google.com/generate_204",
            "https://www.cloudflare.com/cdn-cgi/trace"
        ]

        start = time.perf_counter()

        try:
            for url in test_urls:
                response = requests.get(
                    url,
                    proxies=proxies,
                    timeout=PROXY_TIMEOUT
                )

                if response.status_code >= 400:
                    return None

            delay = (
                time.perf_counter()
                -
                start
            ) * 1000

            return delay

        except Exception:
            return None

    def residential_worker(self):
        try:
            if self.stop_event.is_set():
                return

            residential_proxies = self.fetch_residential_proxies()

            if self.stop_event.is_set():
                return

            print(
                "准备检测 Residential 候选：",
                len(residential_proxies)
            )

            success_count = 0
            tcp_success_count = 0

            def worker(proxy):
                tcp_delay = self.check_residential_tcp(proxy)

                if tcp_delay is None:
                    return None

                proxy_delay = self.check_residential_proxy(proxy)

                if proxy_delay is None:
                    return None

                return proxy, tcp_delay, proxy_delay

            with ThreadPoolExecutor(
                    max_workers=MAX_WORKERS
            ) as executor:

                futures = [
                    executor.submit(worker, proxy)
                    for proxy in residential_proxies
                ]

                for future in as_completed(futures):

                    if self.stop_event.is_set():
                        break

                    try:
                        result = future.result()

                        if result is None:
                            continue

                        proxy, tcp_delay, proxy_delay = result

                        tcp_success_count += 1
                        success_count += 1

                        country = proxy.get("country") or {}

                        if isinstance(country, dict):
                            country = (
                                country.get("names", {})
                                .get("zh-CN", "")
                            )

                        city = proxy.get("city") or {}

                        if isinstance(city, dict):
                            city = (
                                city.get("names", {})
                                .get("zh-CN", "")
                            )

                        result_data = {
                            "protocol": proxy.get(
                                "protocol",
                                ""
                            ),
                            "proxy_ip": proxy.get(
                                "ip",
                                ""
                            ),
                            "proxy_port": proxy.get(
                                "port",
                                ""
                            ),
                            "exit_ip": proxy.get(
                                "exit_ip",
                                ""
                            ),
                            "country": country,
                            "city": city,
                            "delay": proxy_delay
                        }

                        self.result_queue.put(
                            (
                                "exit_result",
                                result_data
                            )
                        )

                        print(
                            "Residential 检测成功：",
                            proxy.get(
                                "protocol",
                                ""
                            ).upper(),
                            proxy.get(
                                "ip",
                                ""
                            ),
                            proxy.get(
                                "port",
                                ""
                            ),
                            f"{proxy_delay:.0f} ms"
                        )

                    except Exception as e:
                        print(
                            "Residential 单个检测异常：",
                            e
                        )

            print(
                "Residential TCP 成功数量：",
                tcp_success_count
            )

            print(
                "Residential 检测完成，成功数量：",
                success_count
            )

        except Exception as e:
            print(
                "Residential 检测线程异常：",
                e
            )

        finally:
            self.residential_finished = True

            self.result_queue.put(
                (
                    "residential_finished",
                    None
                )
            )

    def stop_test(self):

        self.stop_event.set()

        self.set_status(
            "已停止"
        )

    # ==========================================================
    # 全部代理检测
    # ==========================================================

    def test_all_worker(self):

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            futures = []

            for proxy in self.proxy_list:

                if self.stop_event.is_set():
                    break

                futures.append(
                    executor.submit(
                        self.check_proxy,
                        proxy
                    )
                )

            for future in as_completed(
                futures
            ):

                if self.stop_event.is_set():
                    break

                try:

                    result = future.result()

                    self.result_queue.put(
                        (
                            "proxy_result",
                            result
                        )
                    )

                except Exception:

                    self.result_queue.put(
                        (
                            "proxy_result",
                            None
                        )
                    )

        self.result_queue.put(
            (
                "test_finished",
                None
            )
        )

    # ==========================================================
    # ① 检测代理
    # ==========================================================

    def check_proxy(
        self,
        proxy
    ):

        protocol = proxy["protocol"]

        ip = proxy["ip"]

        port = proxy["port"]

        # ------------------------------------------------------
        # TCP检测
        # ------------------------------------------------------

        tcp_start = time.perf_counter()

        try:

            sock = socket.create_connection(
                (
                    ip,
                    int(port)
                ),
                timeout=TCP_TIMEOUT
            )

            sock.close()

            tcp_delay = (
                time.perf_counter()
                -
                tcp_start
            ) * 1000

        except Exception:

            return {
                "success": False,
                "protocol": protocol,
                "ip": ip,
                "port": port,
                "tcp_delay": None,
                "proxy_delay": None,
                "country": "",
                "status": "TCP失败"
            }

        # ------------------------------------------------------
        # 代理检测
        # ------------------------------------------------------

        proxy_url = (
            f"{protocol}://"
            f"{ip}:"
            f"{port}"
        )

        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }

        for test_url in TEST_URLS:

            if self.stop_event.is_set():

                return {
                    "success": False,
                    "protocol": protocol,
                    "ip": ip,
                    "port": port,
                    "tcp_delay": tcp_delay,
                    "proxy_delay": None,
                    "country": "",
                    "status": "已停止"
                }

            # 每个测试地址重新计时

            proxy_start = time.perf_counter()

            try:

                response = requests.get(
                    test_url,
                    proxies=proxies,
                    timeout=PROXY_TIMEOUT,
                    allow_redirects=True
                )

                if response.status_code < 500:

                    proxy_delay = (
                        time.perf_counter()
                        -
                        proxy_start
                    ) * 1000

                    country = (
                        self.get_geo_country(
                            ip
                        )
                    )

                    return {
                        "success": True,
                        "protocol": protocol,
                        "ip": ip,
                        "port": port,
                        "tcp_delay": tcp_delay,
                        "proxy_delay": proxy_delay,
                        "country": country,
                        "status": "可用"
                    }

            except Exception:

                continue

        return {
            "success": False,
            "protocol": protocol,
            "ip": ip,
            "port": port,
            "tcp_delay": tcp_delay,
            "proxy_delay": None,
            "country": "",
            "status": "代理失败"
        }

    # ==========================================================
    # ② 出口IP识别
    # ==========================================================

    def identify_exit(
        self,
        proxy_result
    ):

        protocol = proxy_result[
            "protocol"
        ]

        proxy_ip = proxy_result[
            "ip"
        ]

        proxy_port = proxy_result[
            "port"
        ]

        proxy_url = (
            f"{protocol}://"
            f"{proxy_ip}:"
            f"{proxy_port}"
        )

        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }

        start = time.perf_counter()

        try:

            response = requests.get(
                EXIT_IP_URL,
                proxies=proxies,
                timeout=EXIT_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            exit_ip = str(
                data.get(
                    "ip",
                    ""
                )
            ).strip()

            if not exit_ip:
                return None

            delay = (
                time.perf_counter()
                -
                start
            ) * 1000

            geo = self.get_geo(
                exit_ip
            )

            return {
                "protocol": protocol,
                "proxy_ip": proxy_ip,
                "proxy_port": proxy_port,
                "exit_ip": exit_ip,
                "country": geo.get(
                    "country",
                    ""
                ),
                "city": geo.get(
                    "city",
                    ""
                ),
                "delay": delay
            }

        except Exception:

            return None

    def exit_worker(
        self,
        proxy_result
    ):

        if self.stop_event.is_set():
            return

        result = self.identify_exit(
            proxy_result
        )

        if (
            result is not None
            and
            not self.stop_event.is_set()
        ):

            self.result_queue.put(
                (
                    "exit_result",
                    result
                )
            )

    # ==========================================================
    # IP地理位置
    # ==========================================================

    def get_geo_country(
        self,
        ip
    ):

        try:

            geo = self.get_geo(
                ip
            )

            return geo.get(
                "country",
                ""
            )

        except Exception:

            return ""

    def get_geo(
        self,
        ip
    ):

        try:

            response = requests.get(
                GEO_URL.format(
                    ip=ip
                ),
                timeout=GEO_TIMEOUT
            )

            response.raise_for_status()

            data = response.json()

            if not data.get(
                "success",
                True
            ):
                return {}

            return data

        except Exception:

            return {}

    # ==========================================================
    # 测试选中
    # ==========================================================

    def test_selected(self):

        selected = (
            self.public_tree.selection()
        )

        if not selected:

            messagebox.showwarning(
                "提示",
                "请先选择代理。"
            )

            return

        selected_proxies = []

        for item_id in selected:

            values = self.public_tree.item(
                item_id,
                "values"
            )

            if len(values) < 3:
                continue

            selected_proxies.append({
                "protocol": values[0].lower(),
                "ip": values[1],
                "port": values[2]
            })

        if not selected_proxies:
            return

        self.stop_event.clear()

        threading.Thread(
            target=self.test_selected_worker,
            args=(selected_proxies,),
            daemon=True
        ).start()

        self.set_status(
            "检测选中代理中"
        )

    def test_selected_worker(
        self,
        selected_proxies
    ):

        worker_count = min(
            MAX_WORKERS,
            len(selected_proxies)
        )

        with ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:

            futures = []

            for proxy in selected_proxies:

                if self.stop_event.is_set():
                    break

                futures.append(
                    executor.submit(
                        self.check_proxy,
                        proxy
                    )
                )

            for future in as_completed(
                futures
            ):

                if self.stop_event.is_set():
                    break

                try:

                    result = future.result()

                    self.result_queue.put(
                        (
                            "selected_proxy_result",
                            result
                        )
                    )

                except Exception:

                    pass

    # ==========================================================
    # 消息队列
    # ==========================================================

    def process_queue(self):

        try:

            while True:

                message_type, data = (
                    self.result_queue.get_nowait()
                )

                # ----------------------------------------------
                # 状态
                # ----------------------------------------------

                if message_type == "status":

                    self.status_label.config(
                        text=f"状态：{data}"
                    )

                # ----------------------------------------------
                # 获取完成
                # ----------------------------------------------

                elif message_type == "fetch_done":

                    self.proxy_list = data

                    self.total_count = (
                        len(
                            self.proxy_list
                        )
                    )

                    self.checked_count = 0

                    self.working_count = 0

                    self.progress["value"] = 0

                    self.progress_label.config(
                        text="0.0%"
                    )

                    self.update_stats()

                    self.status_label.config(
                        text="状态：获取完成"
                    )

                    self.fetch_button.config(
                        state="normal"
                    )

                # ----------------------------------------------
                # 获取失败
                # ----------------------------------------------

                elif message_type == "fetch_error":

                    self.status_label.config(
                        text="状态：获取失败"
                    )

                    self.fetch_button.config(
                        state="normal"
                    )

                    messagebox.showerror(
                        "获取代理失败",
                        data
                    )

                # ----------------------------------------------
                # ①结果
                # ----------------------------------------------

                elif message_type == "proxy_result":

                    self.handle_proxy_result(
                        data
                    )

                # ----------------------------------------------
                # ②结果
                # ----------------------------------------------

                elif message_type == "exit_result":

                    self.add_exit_result(
                        data
                    )

                # ----------------------------------------------
                # 测试选中
                # ----------------------------------------------

                elif message_type == "selected_proxy_result":

                    self.handle_selected_result(
                        data
                    )

                # ----------------------------------------------
                # 全部检测完成
                # ----------------------------------------------

                elif message_type == "test_finished":
                    self.public_finished = True

                    if self.stop_event.is_set():
                        self.start_button.config(state="normal")
                        self.status_label.config(text="状态：已停止")

                    elif self.residential_finished:
                        self.start_button.config(state="normal")
                        self.progress["value"] = 100
                        self.progress_label.config(text="100.0%")
                        self.status_label.config(text="状态：检测完成")

                    else:
                        self.status_label.config(
                            text="状态：①检测完成，②检测中"
                        )

                elif message_type == "residential_finished":
                    if self.stop_event.is_set():
                        self.start_button.config(state="normal")
                        self.status_label.config(text="状态：已停止")

                    elif self.public_finished:
                        self.start_button.config(state="normal")
                        self.progress["value"] = 100
                        self.progress_label.config(text="100.0%")
                        self.status_label.config(text="状态：检测完成")

                    else:
                        self.status_label.config(
                            text="状态：①检测中，②检测完成"
                        )

        except queue.Empty:

            pass

        self.root.after(
            100,
            self.process_queue
        )

    # ==========================================================
    # 处理①结果
    # ==========================================================

    def handle_proxy_result(
        self,
        result
    ):

        # 每完成一个代理检测，
        # 无论成功还是失败，都算“已检测”

        self.checked_count += 1

        # ------------------------------------------------------
        # 更新进度条
        # ------------------------------------------------------

        if self.total_count > 0:

            percent = (
                self.checked_count
                /
                self.total_count
                *
                100
            )

            self.progress["value"] = percent

            self.progress_label.config(
                text=f"{percent:.1f}%"
            )

        # ------------------------------------------------------
        # 失败：
        # 不显示
        # 不进入②
        # ------------------------------------------------------

        if (
            result is None
            or
            not result.get(
                "success",
                False
            )
        ):

            self.update_stats()

            return

        # ------------------------------------------------------
        # 成功
        # ------------------------------------------------------

        self.public_results.append(
            result
        )

        self.add_public_result(
            result
        )

        self.working_count += 1

        self.update_stats()

        # ------------------------------------------------------
        # ①成功后立即进入②
        # ------------------------------------------------------

#        threading.Thread(
#            target=self.exit_worker,
#            args=(result,),
#            daemon=True
#        ).start()

    # ==========================================================
    # 处理测试选中结果
    # ==========================================================

    def handle_selected_result(
        self,
        result
    ):

        # ------------------------------------------------------
        # 失败直接丢弃
        # ------------------------------------------------------

        if (
            result is None
            or
            not result.get(
                "success",
                False
            )
        ):

            return

        # ------------------------------------------------------
        # 成功
        # ------------------------------------------------------

        self.public_results.append(
            result
        )

        self.add_public_result(
            result
        )

        self.working_count += 1

        self.update_stats()

        # ------------------------------------------------------
        # 立即进入②
        # ------------------------------------------------------

#        threading.Thread(
#            target=self.exit_worker,
#            args=(result,),
#            daemon=True
#        ).start()

    # ==========================================================
    # ①添加结果
    #
    # 失败不显示
    # 成功后按照代理延迟动态排序
    # ==========================================================

    def add_public_result(
        self,
        result
    ):

        if result is None:
            return

        if not result.get(
            "success",
            False
        ):
            return

        protocol = result.get(
            "protocol",
            ""
        )

        ip = result.get(
            "ip",
            ""
        )

        port = result.get(
            "port",
            ""
        )

        country = result.get(
            "country",
            ""
        )

        tcp_delay = result.get(
            "tcp_delay"
        )

        proxy_delay = result.get(
            "proxy_delay"
        )

        status = result.get(
            "status",
            ""
        )

        if tcp_delay is not None:

            tcp_text = (
                f"{tcp_delay:.0f} ms"
            )

        else:

            tcp_text = "-"

        if proxy_delay is not None:

            proxy_text = (
                f"{proxy_delay:.0f} ms"
            )

        else:

            proxy_text = "-"

        self.public_tree.insert(
            "",
            "end",
            values=(
                protocol.upper(),
                ip,
                port,
                country,
                tcp_text,
                proxy_text,
                status
            )
        )

        # 动态排序
        self.sort_public_tree()

    # ==========================================================
    # ①动态排序
    # ==========================================================

    def sort_public_tree(self):

        items = self.public_tree.get_children()

        sortable = []

        for item_id in items:

            values = self.public_tree.item(
                item_id,
                "values"
            )

            if len(values) < 6:
                continue

            delay_text = str(
                values[5]
            ).strip()

            try:

                delay = float(
                    delay_text.replace(
                        "ms",
                        ""
                    ).strip()
                )

            except ValueError:

                delay = float("inf")

            sortable.append(
                (
                    delay,
                    item_id
                )
            )

        sortable.sort(
            key=lambda x: x[0]
        )

        for index, (_, item_id) in enumerate(
            sortable
        ):

            self.public_tree.move(
                item_id,
                "",
                index
            )

    # ==========================================================
    # ②添加结果
    #
    # 失败不显示
    # 成功后按照出口延迟动态排序
    # ==========================================================

    def add_exit_result(
        self,
        result
    ):

        if result is None:
            return

        self.exit_results.append(
            result
        )

        delay = result.get(
            "delay",
            0
        )

        self.exit_tree.insert(
            "",
            "end",
            values=(
                result.get(
                    "protocol",
                    ""
                ).upper(),

                result.get(
                    "proxy_ip",
                    ""
                ),

                result.get(
                    "proxy_port",
                    ""
                ),

                result.get(
                    "exit_ip",
                    ""
                ),

                result.get(
                    "country",
                    ""
                ),

                result.get(
                    "city",
                    ""
                ),

                f"{delay:.0f} ms"
            )
        )

        # 动态排序
        self.sort_exit_tree()

    # ==========================================================
    # ②动态排序
    # ==========================================================

    def sort_exit_tree(self):

        items = self.exit_tree.get_children()

        sortable = []

        for item_id in items:

            values = self.exit_tree.item(
                item_id,
                "values"
            )

            if len(values) < 7:
                continue

            delay_text = str(
                values[6]
            ).strip()

            try:

                delay = float(
                    delay_text.replace(
                        "ms",
                        ""
                    ).strip()
                )

            except ValueError:

                delay = float("inf")

            sortable.append(
                (
                    delay,
                    item_id
                )
            )

        sortable.sort(
            key=lambda x: x[0]
        )

        for index, (_, item_id) in enumerate(
            sortable
        ):

            self.exit_tree.move(
                item_id,
                "",
                index
            )

    # ==========================================================
    # 统计
    # ==========================================================

    def update_stats(self):

        self.total_label.config(
            text=(
                f"代理总数："
                f"{self.total_count}"
            )
        )

        self.checked_label.config(
            text=(
                f"已检测："
                f"{self.checked_count}"
            )
        )

        self.working_label.config(
            text=(
                f"可用代理："
                f"{self.working_count}"
            )
        )

    # ==========================================================
    # 清空Treeview
    # ==========================================================

    def clear_tree(
        self,
        tree
    ):

        for item in tree.get_children():

            tree.delete(
                item
            )

    # ==========================================================
    # 清空结果
    # ==========================================================

    def clear_results(self):

        self.clear_tree(
            self.public_tree
        )

        self.clear_tree(
            self.exit_tree
        )

        self.public_results.clear()

        self.exit_results.clear()

        self.checked_count = 0

        self.working_count = 0

        self.progress["value"] = 0

        self.progress_label.config(
            text="0.0%"
        )

        self.update_stats()

        self.status_label.config(
            text="状态：准备就绪"
        )

        self.selection_label.config(
            text="当前选择：0 个"
        )

    # ==========================================================
    # 当前选择
    # ==========================================================

    def update_selection_label(
        self,
        event=None
    ):

        count = len(
            self.public_tree.selection()
        )

        self.selection_label.config(
            text=(
                f"当前选择："
                f"{count} 个"
            )
        )

    # ==========================================================
    # ①右键菜单
    # ==========================================================

    def show_public_menu(
        self,
        event
    ):

        row_id = self.public_tree.identify_row(
            event.y
        )

        if row_id:

            if (
                row_id
                not in
                self.public_tree.selection()
            ):

                self.public_tree.selection_set(
                    row_id
                )

            self.public_menu.post(
                event.x_root,
                event.y_root
            )

    # ==========================================================
    # 复制① IP
    # ==========================================================

    def copy_selected_ip(self):

        rows = self.public_tree.selection()

        if not rows:
            return

        values = self.public_tree.item(
            rows[0],
            "values"
        )

        if len(values) >= 2:

            self.copy_text(
                values[1]
            )

    # ==========================================================
    # 复制① IP:端口
    # ==========================================================

    def copy_selected_ip_port(self):

        rows = self.public_tree.selection()

        if not rows:
            return

        values = self.public_tree.item(
            rows[0],
            "values"
        )

        if len(values) >= 3:

            self.copy_text(
                f"{values[1]}:{values[2]}"
            )

    # ==========================================================
    # 复制①端口
    # ==========================================================

    def copy_selected_port(self):

        rows = self.public_tree.selection()

        if not rows:
            return

        values = self.public_tree.item(
            rows[0],
            "values"
        )

        if len(values) >= 3:

            self.copy_text(
                values[2]
            )

    # ==========================================================
    # 复制①整行
    # ==========================================================

    def copy_selected_row(
        self,
        event=None
    ):

        rows = self.public_tree.selection()

        if not rows:
            return "break"

        lines = []

        for row in rows:

            values = self.public_tree.item(
                row,
                "values"
            )

            lines.append(
                "\t".join(
                    str(v)
                    for v in values
                )
            )

        self.copy_text(
            "\n".join(lines)
        )

        return "break"

    # ==========================================================
    # ②右键菜单
    # ==========================================================

    def show_exit_menu(
        self,
        event
    ):

        row_id = self.exit_tree.identify_row(
            event.y
        )

        if row_id:

            if (
                row_id
                not in
                self.exit_tree.selection()
            ):

                self.exit_tree.selection_set(
                    row_id
                )

            self.exit_menu.post(
                event.x_root,
                event.y_root
            )

    # ==========================================================
    # 复制②代理IP
    # ==========================================================

    def copy_exit_proxy_ip(self):

        rows = self.exit_tree.selection()

        if not rows:
            return

        values = self.exit_tree.item(
            rows[0],
            "values"
        )

        if len(values) >= 2:

            self.copy_text(
                values[1]
            )

    # ==========================================================
    # 复制②代理IP:端口
    # ==========================================================

    def copy_exit_proxy_ip_port(self):

        rows = self.exit_tree.selection()

        if not rows:
            return

        values = self.exit_tree.item(
            rows[0],
            "values"
        )

        if len(values) >= 3:

            self.copy_text(
                f"{values[1]}:{values[2]}"
            )

    # ==========================================================
    # 复制②出口IP
    # ==========================================================

    def copy_exit_ip(self):

        rows = self.exit_tree.selection()

        if not rows:
            return

        values = self.exit_tree.item(
            rows[0],
            "values"
        )

        if len(values) >= 4:

            self.copy_text(
                values[3]
            )

    # ==========================================================
    # 复制②整行
    # ==========================================================

    def copy_exit_row(
        self,
        event=None
    ):

        rows = self.exit_tree.selection()

        if not rows:
            return "break"

        lines = []

        for row in rows:

            values = self.exit_tree.item(
                row,
                "values"
            )

            lines.append(
                "\t".join(
                    str(v)
                    for v in values
                )
            )

        self.copy_text(
            "\n".join(lines)
        )

        return "break"

    # ==========================================================
    # 复制文本
    # ==========================================================

    def copy_text(
        self,
        text
    ):

        self.root.clipboard_clear()

        self.root.clipboard_append(
            text
        )

        self.root.update()

    # ==========================================================
    # 导出TXT
    # ==========================================================

    def export_txt(self):

        if (
            not self.public_tree.get_children()
            and
            not self.exit_tree.get_children()
        ):

            messagebox.showwarning(
                "提示",
                "目前没有检测结果。"
            )

            return

        filename = filedialog.asksaveasfilename(
            title="导出检测结果",
            defaultextension=".txt",
            filetypes=[
                ("TXT文件", "*.txt")
            ]
        )

        if not filename:
            return

        try:

            with open(
                filename,
                "w",
                encoding="utf-8"
            ) as f:

                # ----------------------------------------------
                # ①
                # ----------------------------------------------

                f.write(
                    "① 公共代理检测结果\n"
                )

                f.write(
                    "=" * 100
                    +
                    "\n"
                )

                f.write(
                    "协议\tIP地址\t端口\t"
                    "IP所在国家\tTCP延迟\t"
                    "代理延迟\t测试结果\n"
                )

                for row in (
                    self.public_tree.get_children()
                ):

                    values = (
                        self.public_tree.item(
                            row,
                            "values"
                        )
                    )

                    f.write(
                        "\t".join(
                            str(v)
                            for v in values
                        )
                        +
                        "\n"
                    )

                # ----------------------------------------------
                # ②
                # ----------------------------------------------

                f.write(
                    "\n\n"
                )

                f.write(
                    "② 国外出口识别结果\n"
                )

                f.write(
                    "=" * 100
                    +
                    "\n"
                )

                f.write(
                    "协议\t代理IP\t端口\t"
                    "出口IP\t国家\t城市\t延迟\n"
                )

                for row in (
                    self.exit_tree.get_children()
                ):

                    values = (
                        self.exit_tree.item(
                            row,
                            "values"
                        )
                    )

                    f.write(
                        "\t".join(
                            str(v)
                            for v in values
                        )
                        +
                        "\n"
                    )

            messagebox.showinfo(
                "导出完成",
                "检测结果已经导出。"
            )

        except Exception as e:

            messagebox.showerror(
                "导出失败",
                str(e)
            )

    # ==========================================================
    # 关闭
    # ==========================================================

    def on_close(self):

        self.stop_event.set()

        self.root.destroy()


# ==============================================================
# 主程序
# ==============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = ProxyCheckerApp(
        root
    )

    root.mainloop()