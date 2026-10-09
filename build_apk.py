# -*- coding: utf-8 -*-
"""
纯命令行构建 APK（不用 Gradle / Android Studio）
流程：生成图标 -> aapt2 编译资源 -> javac -> d8 转 dex -> 打包 -> zipalign -> 签名
"""
import os, sys, shutil, subprocess, zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(BASE, "android")
SDK = r"E:\Android\sdk"
BT = os.path.join(SDK, "build-tools", "34.0.0")
PLAT = os.path.join(SDK, "platforms", "android-34")
ANDROID_JAR = os.path.join(PLAT, "android.jar")

BUILD = os.path.join(PROJ, "build")
KS = os.path.join(PROJ, "kaoyan.jks")
STORE_PASS = KEY_PASS = "ee0854"
ALIAS = "kaoyan"

# Windows 下这些是 .bat / .exe
AAPT2 = os.path.join(BT, "aapt2.exe")
ZIPALIGN = os.path.join(BT, "zipalign.exe")
# 直接调 jar，绕开 .bat（Windows 下 bat 需要 cmd.exe，易被安全策略拦截）
D8_JAR = os.path.join(BT, "lib", "d8.jar")
APKSIGNER_JAR = os.path.join(BT, "lib", "apksigner.jar")


def run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd)[:200])
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        print("❌ 失败:")
        print((r.stdout or "")[-2500:])
        print((r.stderr or "")[-2500:])
        sys.exit(1)
    return r.stdout


def java_home():
    r = subprocess.run(["java", "-XshowSettings:properties", "-version"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in (r.stderr or "").splitlines():
        if "java.home" in line:
            return line.split("=")[-1].strip()
    raise SystemExit("找不到 java.home")


# ---------------------------------------------------------------- 图标
def make_icons():
    from PIL import Image, ImageDraw, ImageFont
    sizes = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    fonts = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
             r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\Arial.ttf"]
    fpath = next((f for f in fonts if os.path.exists(f)), None)

    for dpi, size in sizes.items():
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # 蓝紫渐变背景（和网页主色一致）
        for y in range(size):
            t = y / max(size - 1, 1)
            r = int(47 + (107 - 47) * t)
            g = int(95 + (143 - 95) * t)
            b = int(224 + (251 - 224) * t)
            d.line([(0, y), (size, y)], fill=(r, g, b, 255))
        # 圆角遮罩
        mask = Image.new("L", (size, size), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
        img.putalpha(mask)

        txt = "0854"
        fs = int(size * 0.30)
        font = ImageFont.truetype(fpath, fs) if fpath else ImageFont.load_default()
        d2 = ImageDraw.Draw(img)
        bb = d2.textbbox((0, 0), txt, font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        d2.text(((size - w) / 2 - bb[0], (size - h) / 2 - bb[1] - size * 0.02),
                txt, font=font, fill=(255, 255, 255, 255))
        out = os.path.join(PROJ, "res", f"mipmap-{dpi}", "ic_launcher.png")
        img.save(out)
    print("✅ 图标已生成（5 个密度）")


# ---------------------------------------------------------------- 构建
def main():
    JH = java_home()
    env = dict(os.environ)
    env["JAVA_HOME"] = JH
    print("JAVA_HOME =", JH)

    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    for d in ("obj", "gen", "compiled", "out"):
        os.makedirs(os.path.join(BUILD, d), exist_ok=True)

    # 1. 图标 + assets
    make_icons()
    src_html = os.path.join(BASE, "index.html")
    assets = os.path.join(PROJ, "assets")
    os.makedirs(assets, exist_ok=True)
    shutil.copy(src_html, os.path.join(assets, "index.html"))
    print(f"✅ 已放入 assets/index.html（{os.path.getsize(src_html)//1024} KB）")

    # 2. aapt2 compile
    res_zip = os.path.join(BUILD, "compiled", "res.zip")
    run([AAPT2, "compile", "--dir", os.path.join(PROJ, "res"), "-o", res_zip])
    print("✅ 资源编译完成")

    # 3. aapt2 link
    gen = os.path.join(BUILD, "gen")
    apk_u = os.path.join(BUILD, "out", "unsigned.apk")
    run([AAPT2, "link",
         "-I", ANDROID_JAR,
         "--manifest", os.path.join(PROJ, "AndroidManifest.xml"),
         "-A", assets,
         "--java", gen,
         "--min-sdk-version", "24",
         "--target-sdk-version", "34",
         "--version-code", "5",
         "--version-name", "3.2",
         "-o", apk_u,
         res_zip])
    print("✅ 资源链接完成 ->", os.path.getsize(apk_u) // 1024, "KB")

    # 4. javac
    obj = os.path.join(BUILD, "obj")
    # 编译 java/ 下所有源文件；不编译 R.java（代码里不引用它，且其内部类会让 d8 8.2 崩溃）
    srcdir = os.path.join(PROJ, "java")
    sources = []
    for root, _, files in os.walk(srcdir):
        sources += [os.path.join(root, f) for f in files if f.endswith(".java")]
    javac = os.path.join(JH, "bin", "javac.exe")
    run([javac, "-source", "8", "-target", "8",
         "-bootclasspath", ANDROID_JAR,
         "-classpath", ANDROID_JAR,
         "-d", obj, "-nowarn", "-encoding", "UTF-8"] + sources, env=env)
    print("✅ Java 编译完成")

    # 5. d8 -> dex
    classes = []
    for root, _, files in os.walk(obj):
        classes += [os.path.join(root, f) for f in files if f.endswith(".class")]
    print("  待转 dex 的 class:", len(classes))
    java = os.path.join(JH, "bin", "java.exe")
    run([java, "-cp", D8_JAR, "com.android.tools.r8.D8",
         "--lib", ANDROID_JAR, "--min-api", "24",
         "--output", obj] + classes, env=env)
    dex = os.path.join(obj, "classes.dex")
    print("✅ dex 生成:", os.path.getsize(dex) // 1024, "KB")

    # 6. dex 打进 apk
    with zipfile.ZipFile(apk_u, "a", zipfile.ZIP_DEFLATED) as z:
        if "classes.dex" not in z.namelist():
            z.write(dex, "classes.dex")
    print("✅ classes.dex 已打包")

    # 7. zipalign
    apk_a = os.path.join(BUILD, "out", "aligned.apk")
    run([ZIPALIGN, "-f", "-p", "4", apk_u, apk_a])
    print("✅ 对齐完成")

    # 8. 签名
    if not os.path.exists(KS):
        keytool = os.path.join(JH, "bin", "keytool.exe")
        run([keytool, "-genkeypair", "-alias", ALIAS, "-keyalg", "RSA",
             "-keysize", "2048", "-validity", "10950",
             "-keystore", KS, "-storepass", STORE_PASS, "-keypass", KEY_PASS,
             "-dname", "CN=EE0854, OU=Kaoyan, O=EE0854, C=CN"], env=env)
        print("✅ 签名密钥已生成（30 年有效期）")

    apk_s = os.path.join(BASE, "考研择校通.apk")
    run([java, "-jar", APKSIGNER_JAR, "sign", "--ks", KS,
         "--ks-pass", f"pass:{STORE_PASS}", "--key-pass", f"pass:{KEY_PASS}",
         "--ks-key-alias", ALIAS, "--out", apk_s, apk_a], env=env)
    print("✅ 签名完成")

    # 9. 校验
    run([java, "-jar", APKSIGNER_JAR, "verify", apk_s], env=env)
    size = os.path.getsize(apk_s)
    print("\n" + "=" * 50)
    print(f"🎉 构建成功：{apk_s}")
    print(f"   大小：{size/1024/1024:.2f} MB")
    print(f"   包名：com.kaoyan.ee0854   最低支持 Android 7.0 (API 24)")
    print("=" * 50)


if __name__ == "__main__":
    main()
