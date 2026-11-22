#!/usr/bin/env python3
"""PicaComic 下载栈补丁：单图超时、等待超时、并发上限放宽。
在仓库根目录执行：python3 patch.py
"""
import io
import sys

def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()

def write(p, s):
    with io.open(p, 'w', encoding='utf-8') as f:
        f.write(s)

def sub(path, old, new, expect=None):
    s = read(path)
    n = s.count(old)
    if n == 0:
        print('[MISS]', path)
        return False
    if expect is not None and n != expect:
        print('[WARN] count=%d expect=%d %s' % (n, expect, path))
    s = s.replace(old, new)
    write(path, s)
    print('[OK] %s x%d' % (path, n))
    return True

ok = True

# 1) 并发档位加上 32 / 48（原来是 1/2/4/6/8/16）
ok &= sub(
    'lib/pages/settings/network_setting.dart',
    'final List<String> threadOptions = ["1", "2", "4", "6", "8", "16"];',
    'final List<String> threadOptions = ["1", "2", "4", "6", "8", "16", "24", "32", "48"];',
)

# 2) 单张图片流请求加 receiveTimeout，避免半死连接永久挂住
s = read('lib/foundation/image_manager.dart')
n = s.count('Options(responseType: ResponseType.stream)')
s = s.replace(
    'Options(responseType: ResponseType.stream)',
    'Options(responseType: ResponseType.stream, '
    'receiveTimeout: const Duration(seconds: 25))',
)
write('lib/foundation/image_manager.dart', s)
print('[OK] image_manager.dart stream options x%d' % n)
if n == 0:
    ok = False

# 3) 等待"最老那张"加 45s 上限，卡住就抛错走整本重试，而不是无限挂
ok &= sub(
    'lib/network/download_model.dart',
    '          await task.wait();\n          if (task.error != null) {',
    '          try {\n'
    '            await task.wait().timeout(const Duration(seconds: 45));\n'
    '          } catch (_) {\n'
    '            task.cancel();\n'
    '            _downloading.remove("$ep$index");\n'
    '            throw Exception("Image timeout: ep=$ep index=$index");\n'
    '          }\n'
    '          if (task.error != null) {',
)

# 4) 失败重试间隔缩短：2<<n（2/4/8/16s）→ 1/2/4/8s
ok &= sub(
    'lib/network/download_model.dart',
    'await Future.delayed(Duration(seconds: 2 << _retryTimes));',
    'await Future.delayed(Duration(seconds: 1 << _retryTimes));',
)

# 5) 依赖覆盖：liquid_glass_widgets 需要 meta>=1.17，而 Flutter SDK 自带的 flutter_test 锁在 1.16
s = read('pubspec.yaml')
if 'dependency_overrides' not in s:
    s = s.rstrip() + '\n\ndependency_overrides:\n  meta: ^1.17.0\n'
    write('pubspec.yaml', s)
    print('[OK] pubspec.yaml dependency_overrides meta')
else:
    print('[SKIP] pubspec.yaml already has dependency_overrides')

print('PATCH', 'OK' if ok else 'INCOMPLETE')
sys.exit(0 if ok else 1)