import os
import sys
import time
import shutil
import subprocess


def main():
    if len(sys.argv) < 3:
        return

    old_exe = sys.argv[1]
    new_exe = sys.argv[2]

    # 等待旧程序退出，使旧 EXE 可以被替换
    while True:
        try:
            with open(old_exe, "r+b"):
                break
        except (PermissionError, OSError):
            time.sleep(1)

    # 新版本 EXE 使用自己的版本号文件名
    new_exe_final = os.path.join(
        os.path.dirname(old_exe),
        os.path.basename(new_exe)
    )

    # 删除旧版本 EXE
    try:
        os.remove(old_exe)
    except Exception:
        pass

    # 将新版本 EXE 移动到程序目录
    shutil.move(new_exe, new_exe_final)

    # 启动新版本 EXE
    subprocess.Popen([new_exe_final])


if __name__ == "__main__":
    main()