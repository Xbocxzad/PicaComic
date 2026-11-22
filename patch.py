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

# 0-T) hitomi 图床按 IP 限流：请求发起间隔 ≥130ms（16 线程时约 7.7 req/s）
# 实测 16 线程 ≈22 req/s 会直接被 503 + "Your IP address has been banned"
if not sub(
    'lib/foundation/image_manager.dart',
    '  int ehgtLoading = 0;',
    '  int ehgtLoading = 0;\n'
    '\n'
    '  /// hitomi 图床对同 IP 请求速率极敏感，这里做全局节流\n'
    '  static DateTime _lastHitomiReq = DateTime(2000);\n'
    '  static Future<void> _hitomiThrottle() async {\n'
    '    final ms = DateTime.now().difference(_lastHitomiReq).inMilliseconds;\n'
    '    if (ms < 130) {\n'
    '      await Future.delayed(Duration(milliseconds: 130 - ms));\n'
    '    }\n'
    '    _lastHitomiReq = DateTime.now();\n'
    '  }',
):
    ok = False

# 0-A) hitomi 图片请求改用 ImageManager 的共享 dio（连接复用）
# 原来每张图都 new 一个 Dio，等于每张图新建 TCP+TLS（实测 3.7s/次握手）
_A_OLD = '''      var dio = logDio();
      dio.options.headers = {
        "User-Agent": webUA,
        "Referer": "https://hitomi.la/reader/$galleryId.html"
      };

      var res = await dio.get<ResponseBody>(url,
          options: Options(responseType: ResponseType.stream));'''

_A_NEW = '''      await _hitomiThrottle();
      var res = await dio.get<ResponseBody>(url,
          options: Options(
              responseType: ResponseType.stream,
              receiveTimeout: const Duration(seconds: 25),
              headers: {
                "User-Agent": webUA,
                "Referer": "https://hitomi.la/reader/$galleryId.html"
              }));'''

if not sub('lib/foundation/image_manager.dart', _A_OLD, _A_NEW):
    ok = False

# 0-B) gg.js 缓存 100ms → 10 分钟（原来几乎每张图都要重新拉一次 gg.js）
if not sub(
    'lib/network/hitomi_network/image.dart',
    '- cacheTime!.millisecondsSinceEpoch < 100){',
    '- cacheTime!.millisecondsSinceEpoch < 600000){',
):
    ok = False


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
    s = s.rstrip() + '\n\ndependency_overrides:\n  meta: ^1.17.0\n  synchronized: 3.3.0\n'
    write('pubspec.yaml', s)
    print('[OK] pubspec.yaml dependency_overrides meta')
else:
    print('[SKIP] pubspec.yaml already has dependency_overrides')

print('PATCH', 'OK' if ok else 'INCOMPLETE')
sys.exit(0 if ok else 1)