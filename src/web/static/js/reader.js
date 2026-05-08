page("reader-page").onOpen = () => {
  if (!current_text_book) return openLibraryPage();
};
const unLoad = () => {
  document.querySelector("#toc-view").innerHTML = "";
  let el = document.querySelector("foliate-view");
  if (el) el.remove();
  current_text_book = null;
};

var current_text_book = null;
async function _readBook(source) {
  if (current_text_book && current_text_book.sid !== source.sid) unLoad();
  else if (current_text_book && current_text_book.sid === source.sid)
    return page("reader-page").open();
  current_text_book = source;
  document.querySelector("#book-loading").classList.remove("hidden");
  const response = await fetch(
    `/text_book_content/${encodeURIComponent(encodeURIComponent(source.file_url))}`,
  );
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  const blob = await response.blob();
  const type =
    response.headers.get("content-type") || "application/octet-stream";
  const contentDisposition = response.headers.get("Content-Disposition");
  let filename = "downloaded_file"; // Default name
  if (contentDisposition && contentDisposition.indexOf("attachment") !== -1) {
    const matches = /filename="?([^"]+)"?/.exec(contentDisposition);
    if (matches && matches[1]) {
      filename = matches[1];
    }
  }
  const file = new File([blob], filename, { type: type });
  let container = new DataTransfer();
  container.items.add(file);
  document.querySelector("#file-input").files = container.files;
  document.querySelector("#file-input").onchange();
  page("reader-page").open();
  pywebview.api.mark_as_in_progress(source.sid);
}

var last_progress_update = 0;
var actual_cfi = null;
var last_cfi = null;
async function saveProgress(cfi, percent) {
  actual_cfi = cfi;
  if (Date.now() - last_progress_update < 1000) await delay(1000);
  if (cfi !== actual_cfi) return;
  if (cfi === last_cfi) return;

  last_cfi = cfi;
  last_progress_update = Date.now();
  pywebview.api.set_reading_progress(current_text_book.sid, cfi, percent);
  current_text_book.progress = cfi;
  current_text_book.progress_percent = percent;
}
