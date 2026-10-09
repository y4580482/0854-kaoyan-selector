package com.kaoyan.ee0854;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;

/**
 * 系统返回（返回键 / Android 系统侧滑返回）的结果回调，由网页调用。
 *
 * 两个刻意的设计：
 * 1) 不实现任何泛型接口 —— JDK 21+ 编译出的泛型 bridge 方法会让 d8 8.2 抛 NullPointerException，
 *    所以这里用 JavascriptInterface 代替 evaluateJavascript 的 ValueCallback<String>。
 * 2) 不写匿名内部类 —— JDK 21+ 的匿名内部类同样会让 d8 8.2 崩溃，所以 UI 线程任务用顶层类 BackRunner。
 *
 * handled=true  -> App 内部已回退一级，什么都不做。
 * handled=false -> 已退到顶层，走「再按一次退出」，避免误触直接退出 App。
 */
public class BackBridge {

    private final Activity act;
    private final Handler ui = new Handler(Looper.getMainLooper());

    public BackBridge(Activity a) {
        this.act = a;
    }

    @JavascriptInterface
    public void onBackResult(String handled) {
        if ("true".equals(handled)) return;

        Activity a = act;
        if (a == null || a.isFinishing()) return;

        long now = System.currentTimeMillis();
        boolean exit;
        if (now - MainActivity.lastBackMs < 2000) {
            MainActivity.lastBackMs = 0;
            exit = true;
        } else {
            MainActivity.lastBackMs = now;
            exit = false;
        }
        ui.post(new BackRunner(a, exit));
    }
}
