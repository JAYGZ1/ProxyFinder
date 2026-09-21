\# ProxyFinder



\*\*ProxyFinder\*\* 是一款基于 Python + Tkinter 开发的代理查找与检测工具。



用于获取公开代理列表，并对代理的连通性、响应速度、出口 IP、国家/地区等信息进行检测，同时提供 Residential / 住宅代理候选检测功能。



\## ✨ 功能



\* 获取公开代理列表

\* 批量检测代理可用性

\* HTTP / HTTPS / SOCKS 等代理检测

\* 测试代理响应速度

\* 获取代理出口 IP

\* 查询出口 IP 国家/地区

\* Residential / 住宅代理候选检测

\* 过滤部分数据中心 / 托管网络候选

\* 测试选中的代理

\* 导出检测结果为 TXT

\* 检查 GitHub 最新版本

\* 支持程序自动更新



\## 🖥️ 界面



程序提供两个主要检测结果区域：



\### ① 公共代理检测结果



用于显示从公开代理列表获取并检测后的代理。



\### ② Residential / 住宅代理出口识别结果



用于检测 Residential / 住宅代理候选，并尝试识别其出口 IP 和网络信息。



\## 🚀 使用方法



1\. 启动 `LswProxyFinder_v1.0.1.exe`

2\. 点击 \*\*获取代理\*\*

3\. 等待代理列表获取完成

4\. 点击 \*\*开始检测\*\*

5\. 查看检测结果

6\. 可以使用 \*\*测试选中\*\* 对指定代理进行再次测试

7\. 可以使用 \*\*导出 TXT\*\* 保存检测结果



\## 📦 下载



最新正式版本：



\*\*v1.0.1\*\*



程序文件：



`LswProxyFinder\_v1.0.1.exe`



请前往 GitHub Releases 下载最新版本。



\[下载 v1.0.1](https://github.com/JAYGZ1/ProxyFinder/releases/tag/v1.0.1)



\## 🔄 自动更新



程序支持检查 GitHub Releases 中的最新版本。



当发现新版本时，程序可以下载新的版本并自动完成更新。



程序的更新检查不要求用户安装 GitHub CLI，也不要求用户登录 GitHub。



\## ⚠️ 注意事项



代理的可用性、速度和出口位置可能随时间发生变化。



检测结果仅代表检测时的网络状态，不保证代理能够长期保持可用。



部分代理可能存在：



\* 连接速度较慢

\* 网络不稳定

\* 出口 IP 与代理服务器 IP 不一致

\* 无法访问特定网站

\* 对 HTTPS 或特定目标存在限制



请根据实际使用场景自行判断检测结果。



\## 🔐 隐私



本项目不会在代码中内置开发者个人局域网地址或个人代理服务器。



代理检测过程中使用的代理地址来自程序获取的代理列表，并用于连接测试目标。



\## 🛠️ 技术栈



\* Python 3

\* Tkinter

\* Requests

\* ThreadPoolExecutor

\* PyInstaller



\## 📁 项目结构



```text

ProxyFinder/

├── main.py

├── updater.py

├── LswProxyFinder\_v1.0.spec

├── a1.ico

├── a1.png

├── LICENSE

└── README.md

```



\## 📄 License



This project is licensed under the \*\*MIT License\*\*.



See \[LICENSE](LICENSE) for details.



\---



\*\*ProxyFinder\*\*

GitHub: https://github.com/JAYGZ1/ProxyFinder



