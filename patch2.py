#!/usr/bin/env python3
"""共存版补丁：改 applicationId，可与原版/主版同时安装。
在仓库根目录、且 patch.py 已执行之后运行：python3 patch2.py
思路：applicationId 换新包名，Kotlin/Java 类仍留在原包（manifest 写全名），
MethodChannel 名一律不动（Dart 侧硬编码同名）。
"""
import io
import sys

def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()

def write(p, s):
    with io.open(p, 'w', encoding='utf-8') as f:
        f.write(s)

def sub(path, old, new, label):
    s = read(path)
    if old not in s:
        print('[MISS2]', label, path)
        return False
    if new in s:
        print('[SKIP2]', label)
        return True
    write(path, s.replace(old, new))
    print('[OK2]', label, path)
    return True

ok = True
APPID_OLD = 'applicationId "com.github.pacalini.pica_comic"'
APPID_NEW = 'applicationId "com.github.pacalini.pica_comic.lx"'

ok &= sub('android/app/build.gradle', APPID_OLD, APPID_NEW, 'applicationId')

MAN = 'android/app/src/main/AndroidManifest.xml'
ok &= sub(MAN, 'android:name=".MainActivity"',
          'android:name="com.github.pacalini.pica_comic.MainActivity"', 'manifest MainActivity')
ok &= sub(MAN, 'android:name=".DownloadForegroundService"',
          'android:name="com.github.pacalini.pica_comic.DownloadForegroundService"', 'manifest service')
ok &= sub(MAN, 'android:name=".HistoryWidgetReceiver"',
          'android:name="com.github.pacalini.pica_comic.HistoryWidgetReceiver"', 'manifest receiver')
ok &= sub(MAN, 'android:label="Pica Comic"', 'android:label="Pica Comic LX"', 'manifest label')

# 跳系统设置页的 package: 串要指向新包名（MethodChannel 名不含 "package:"，不会误伤）
ok &= sub('android/app/src/main/kotlin/com/github/pacalini/pica_comic/MainActivity.kt',
          'package:com.github.pacalini.pica_comic"',
          'package:com.github.pacalini.pica_comic.lx"', 'settings package uri')

print('PATCH2', 'OK' if ok else 'INCOMPLETE')
sys.exit(0 if ok else 1)