const downloadCardTemplate = document.querySelector("#download-card-template");
var downloads = [];

function showDownloads(resp) {
  for (let [sid, title] of resp.data) {
    downloads.push(sid);
    createDownloadingCard(sid, title);
  }
}

const start_downloading_callback = (sid, resp) => {
  if (resp.status != "ok") {
    button.classList.remove("loading");
    showError(resp.message);
    removeDownloadingCard(sid);
  } else {
    initStatus(sid, "waiting", 0);
    downloads.push(sid);
  }
};
function startDownloadingAudioBook(button, sid, title) {
  if (button) {
    if (button.classList.contains("loading")) return;
    button.classList.add("loading");
  }
  createDownloadingCard(sid, title);
  pywebview.api
    .download_audio_book(sid, title)
    .then((resp) => start_downloading_callback(sid, resp));
}
function startDownloadingTextBook(button, sid, title) {
  if (button) {
    if (button.classList.contains("loading")) return;
    button.classList.add("loading");
  }
  createDownloadingCard(sid, title);
  pywebview.api
    .download_text_book(sid, title)
    .then((resp) => start_downloading_callback(sid, resp));
}

function createDownloadingCard(sid, title) {
  container = document.getElementById("downloads-container");
  var card = downloadCardTemplate.content.cloneNode(true);
  card.querySelector(".download-card").setAttribute("data-sid", sid);
  card.querySelector(".book-title").innerText = title;
  card.querySelector(".cancel-btn").onclick = () => {
    terminateDownloading(sid);
  };
  container.appendChild(card);
}
function initStatus(sid, status, total_count) {
  if (status == "terminated") return removeDownloadingCard(sid);
  var card = document.querySelector(`.download-card[data-sid='${sid}']`);
  card.dataset["status"] = status;
  var status_el = document.querySelector(
    `.download-card[data-sid='${sid}'] .status`,
  );
  status_el.style = status == "downloading" ? "display: none" : "";
  if (status == "finished") card.dataset["finished"] = "1";
  document.querySelector(
    `.download-card[data-sid='${sid}'] .data-size`,
  ).dataset["total_count"] = total_count;
  var status_text = document.querySelector(
    `template.downloading-status[data-status='${status}']`,
  ).innerHTML;
  status_el.innerHTML = status_text;
  if (status == "finished") donwnloadingEnded(sid);
}
function downloadingCallback(sid, done_size, done_count, total_count) {
  var percents = (done_count / total_count) * 100;
  document.querySelector(
    `.download-card[data-sid='${sid}'] .percents`,
  ).innerText = `${percents.toFixed(2)}%`;
  var size_el = document.querySelector(
    `.download-card[data-sid='${sid}'] .data-size`,
  );
  size_el.innerText = `${done_size} / ${size_el.dataset["total_count"]}`;
  document.querySelector(
    `.download-card[data-sid='${sid}'] .progress-bar`,
  ).style.width = `${percents}%`;
}
function terminateDownloading(sid) {
  if (
    document.querySelector(`.download-card[data-sid='${sid}']`).dataset[
      "finished"
    ]
  )
    removeDownloadingCard(sid);
  else {
    downloads = downloads.filter((s) => s !== sid);
    document
      .querySelector(`.download-card[data-sid='${sid}'] .cancel-btn`)
      .classList.add("loading");
    pywebview.api.terminate_download(sid).then((_) => {
      if (
        document.querySelector(`.download-card[data-sid='${sid}']`).dataset[
          "status"
        ] == "waiting"
      )
        removeDownloadingCard(sid);
    });
  }
}
function removeDownloadingCard(sid) {
  document.querySelector(`.download-card[data-sid='${sid}']`).remove();
}
function donwnloadingEnded(sid) {
  downloads = downloads.filter((s) => s !== sid);
  title = document.querySelector(
    `.download-card[data-sid='${sid}'] .book-title`,
  );
  if (title) {
    var notification = document
      .getElementById("downloading-finished-notification")
      .content.cloneNode(true);
    notification.querySelector(".book-title").innerHTML = title.innerHTML;
    createNotification(notification, 60, true);
  }
  if (sid.includes("AudioBook")) {
    if (opened_book && selected_source && selected_source.sid == sid)
      loadBookData(opened_book.bid);
  } else {
    if (opened_book) {
      var selected_text_source = opened_book.text_sources.find(
        (source) => source.selected === true,
      );
      if (selected_text_source && selected_text_source.sid == sid) {
        pywebview.api.book_by_bid(opened_book.bid, true).then((resp) => {
          console.log(resp);
          _readBook(
            resp.data.text_sources.find((source) => source.selected === true),
          );
        });
      }
    }
  }
}
