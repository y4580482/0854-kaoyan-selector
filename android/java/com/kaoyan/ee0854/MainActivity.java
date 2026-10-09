package com.kaoyan.ee0854;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;

/**
 * 0854 电子信息择校速查表 —— 离线 WebView 壳
 * 全部数据内联在 assets/index.html 中，无需联网。
 */
public class MainActivity extends Activity {

    private WebView web;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);          // 表格筛选/排序依赖 JS
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);            // 适配手机屏幕
        s.setSupportZoom(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setTextZoom(100);
        s.setMediaPlaybackRequiresUserGesture(false);

        web.setWebViewClient(new MyWebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        web.addJavascriptInterface(new BackBridge(this), "AndroidBack");   // 网页回调：请求退出/提示

        web.loadUrl("file:///android_asset/index.html");
        setContentView(web);
    }

    static long lastBackMs = 0;

    /**
     * 返回统一入口：先交给网页处理。
     * 网页有上一级（学校页/专业页）就退一级；没有上一级时走「再按一次退出」，
     * 避免从屏幕边缘侧滑时被系统当成 Activity 返回、直接退出 App。
     */
    @Override
    public void onBackPressed() {
        if (web == null) {
            finish();
            return;
        }
        web.evaluateJavascript(
            "(function(){var h=false;try{h=!!window.__androidBack()}catch(e){}" +
            "try{AndroidBack.onBackResult(h?'true':'false')}catch(e){}return h})()", null);
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (web != null) web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
