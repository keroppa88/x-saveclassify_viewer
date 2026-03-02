/**
 * X (Twitter) ブックマーク URL 収集スクリプト
 *
 * 使い方:
 *   1. ブラウザで https://x.com/i/bookmarks を開く（ログイン済みであること）
 *   2. ブラウザの開発者ツール（F12）→ Console タブを開く
 *   3. このスクリプト全体をコピーしてコンソールに貼り付け、Enter を押す
 *   4. 自動スクロールが始まり、ブックマークのツイートURLを収集します
 *   5. 収集完了後、x_bookmark_url.csv が自動ダウンロードされます
 *
 * 設定:
 *   MAX_URLS     : 収集するURL数の上限（デフォルト200）
 *   SCROLL_DELAY : スクロール間隔ミリ秒（デフォルト2000）
 *   MAX_RETRIES  : 新しいツイートが見つからない場合のリトライ回数（デフォルト5）
 */

(async function collectBookmarks() {
  "use strict";

  const MAX_URLS = 200;
  const SCROLL_DELAY = 2000;
  const MAX_RETRIES = 5;

  const collectedUrls = new Set();
  let noNewCount = 0;

  function extractTweetUrls() {
    const links = document.querySelectorAll('a[href*="/status/"]');
    let newFound = 0;

    links.forEach(function (a) {
      const href = a.href;
      // ツイートURLのパターン: https://x.com/ユーザー名/status/数字
      const match = href.match(
        /https:\/\/(x\.com|twitter\.com)\/[^/]+\/status\/(\d+)/
      );
      if (match) {
        const normalizedUrl = "https://x.com/" + href.split("/")[3] + "/status/" + match[2];
        if (!collectedUrls.has(normalizedUrl)) {
          collectedUrls.add(normalizedUrl);
          newFound++;
        }
      }
    });

    return newFound;
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function downloadCsv(urls) {
    var csvContent = "url\n";
    urls.forEach(function (url) {
      csvContent += url + "\n";
    });

    var blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "x_bookmark_url.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }

  console.log("=== X ブックマーク URL 収集開始 ===");
  console.log("目標: " + MAX_URLS + " 件");

  // 初回の既存コンテンツを収集
  extractTweetUrls();
  console.log("初回収集: " + collectedUrls.size + " 件");

  // スクロールしながら収集
  while (collectedUrls.size < MAX_URLS && noNewCount < MAX_RETRIES) {
    window.scrollTo(0, document.body.scrollHeight);
    await sleep(SCROLL_DELAY);

    var newFound = extractTweetUrls();

    if (newFound > 0) {
      noNewCount = 0;
      console.log("収集中... " + collectedUrls.size + " / " + MAX_URLS + " 件");
    } else {
      noNewCount++;
      console.log(
        "新しいツイートが見つかりません (" + noNewCount + "/" + MAX_RETRIES + ")"
      );
    }
  }

  // 結果を配列に変換（上限適用）
  var urlArray = Array.from(collectedUrls).slice(0, MAX_URLS);

  console.log("=== 収集完了 ===");
  console.log("合計: " + urlArray.length + " 件のURLを収集しました");

  // CSVダウンロード
  downloadCsv(urlArray);
  console.log("x_bookmark_url.csv をダウンロードしました");

  // コンソールにも出力
  console.log("--- 収集URL一覧 ---");
  urlArray.forEach(function (url, i) {
    console.log((i + 1) + ": " + url);
  });

  return urlArray;
})();
