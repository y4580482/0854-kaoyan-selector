package com.kaoyan.ee0854;

import android.content.Intent;
import android.net.Uri;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * 独立顶层类（不用匿名内部类）：
 * JDK 21+ 编译出的匿名内部类会带 d8 8.2 无法解析的属性，导致 NullPointerException。
 */
public class MyWebViewClient extends WebViewClient {

    @Override
    public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
        String url = request != null ? request.getUrl().toString() : null;
        // 页面里的原始来源链接交给系统浏览器，其余留在 App 内
        if (url != null && (url.startsWith("http://") || url.startsWith("https://"))) {
            view.getContext().startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            return true;
        }
        return super.shouldOverrideUrlLoading(view, request);
    }
}
