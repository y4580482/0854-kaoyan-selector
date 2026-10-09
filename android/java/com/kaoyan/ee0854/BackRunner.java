package com.kaoyan.ee0854;

import android.app.Activity;
import android.widget.Toast;

/**
 * 回到 UI 线程执行的返回收尾动作。
 * 写成顶层类而不是匿名内部类：JDK 21+ 编译出的匿名内部类会让 d8 8.2 抛 NullPointerException。
 */
public class BackRunner implements Runnable {

    private final Activity act;
    private final boolean exit;

    public BackRunner(Activity a, boolean exit) {
        this.act = a;
        this.exit = exit;
    }

    @Override
    public void run() {
        Activity a = act;
        if (a == null || a.isFinishing()) return;
        if (exit) {
            a.finish();
        } else {
            Toast.makeText(a, "再按一次退出", Toast.LENGTH_SHORT).show();
        }
    }
}
