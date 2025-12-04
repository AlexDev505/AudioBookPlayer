const smallPlayer = document.getElementById("small-player");
opened_book = null;
last_stop_flag_time = 0;

page("book-page").onShow = function (el) {
  addUrlParams({ page: el.id });
  let bid = urlParams.get("bid");
  if (bid) loadBookData(bid);
};
page("book-page").onHide = function () {
  document.getElementById("book-loading").style = "display: block;";
  urlParams.delete("bid");
  opened_book = null;
};

function loadBookData(bid) {
  pywebview.api.book_by_bid(bid, true).then((resp) => {
    if (resp.status != "ok") {
      showError(resp.message);
      return;
    }
    opened_book = resp.data;
    document.querySelector("#book-page-content .book-title").innerHTML =
      resp.data.name;
    document.querySelector("#book-page-content .book-adding-date").innerHTML =
      `{{ gettext("book.added") }} ${resp.data.adding_date}`;
    initBookListeningProgress(resp.data);
    document.querySelector("#book-page-content .book-preview").style =
      `background-image: url('${resp.data.preview}'), url('/library/${resp.data.local_preview}');`;
    document.querySelector("#book-page-content .book-author").innerHTML =
      resp.data.author;
    document.querySelector("#book-page-content .book-reader").innerHTML =
      resp.data.reader;
    document.querySelector("#book-page-content .book-duration").innerHTML =
      resp.data.duration;
    if (resp.data.series_name) {
      document.querySelector("#book-page-content .book-series").innerHTML =
        `${resp.data.series_name} (${resp.data.number_in_series})`;
      document.querySelector("#book-page-content .book-series").style =
        "display: flex";
    } else
      document.querySelector("#book-page-content .book-series").style =
        "display: none";
    document.querySelector("#book-page-content .book-driver").innerHTML =
      resp.data.driver;
    document.querySelector("#book-page-content .book-description").innerHTML =
      resp.data.description;
    document.getElementById("player-controls").style = "display: none";
    document.getElementById("player-downloading-required").style =
      "display: none";
    document.getElementById("player-downloading").style = "display: none";
    document.querySelector("#book-page-content .toggle-favorite-btn").onclick =
      function () {
        toggleFavorite(this, resp.data.bid);
      };
    document.querySelector("#book-page-content .open-in-browser").dataset.url =
      resp.data.url;
    if (!resp.data.driver)
      document.querySelector("#book-page-content .open-in-browser").style =
        "display: none";
    else
      document.querySelector("#book-page-content .open-in-browser").style = "";

    if (resp.data.series_name && resp.data.driver) {
      document.querySelector("#book-page-content .search-series").style = "";
      document.querySelector("#book-page-content .search-series").onclick =
        function () {
          searchBookSeries(resp.data.url, resp.data.series_name);
        };
    } else
      document.querySelector("#book-page-content .search-series").style =
        "display: none";
    if (resp.data.downloaded) {
      document.querySelector("#book-page-content .open-book-dir").style = "";
      document.querySelector("#book-page-content .open-book-dir").onclick =
        function () {
          pywebview.api.open_book_dir(resp.data.bid).then((response) => {
            if (response.status != "ok") showError(response.message);
          });
        };
      let playBtn = document.getElementById("toggle-playback-btn");
      playBtn.classList.remove("pause-button");
      playBtn.classList.add("play-button");
      document.getElementById("player-controls").style = "display: flex";
      document.getElementById("player").classList.remove("not-available");
      let html = "";
      let i = 0;
      for (let item of resp.data.items) {
        html += `<div class="book-item" data-index="${i}"
                    onclick="selectItem(${i})"
                    onmousedown="bookItemOnmousedown(event, this)"
                    onmousemove="bookItemOnmousemove(event, this)"
                    onmouseup="bookItemOnmouseup(event, this)"
                    onmouseout="bookItemOnmouseup(event, this)">
                  <span class="title">${item.title}</span>
                  <span class="time"><span class="cur-time">00:00</span> / ${timeView(item.end_time - item.start_time)}</span>
                </div>`;
        i++;
      }
      document.getElementById("items-container").innerHTML = html;

      document
        .getElementById("items-container")
        .scrollTo(
          0,
          (document.querySelector(".book-item").clientHeight + 2) *
            (resp.data.stop_flag.item - 1),
        );
      let el = document.querySelector(
        `.book-item[data-index="${resp.data.stop_flag.item}"]`,
      );
      el.classList.add("current");
      let duration =
        resp.data.items[resp.data.stop_flag.item].end_time -
        resp.data.items[resp.data.stop_flag.item].start_time;
      el.style.setProperty(
        "--current-item-percents",
        `${resp.data.stop_flag.time / (duration / 100)}%`,
      );
      document.querySelector(".book-item.current .cur-time").innerText =
        timeView(Math.floor(resp.data.stop_flag.time));

      if (!player.current_book) initBook(resp.data);
      else {
        if (player.current_book.bid == opened_book.bid && player.playing) {
          playBtn.classList.add("pause-button");
          playBtn.classList.remove("play-button");
        }
      }
    } else {
      document.querySelector("#book-page-content .open-book-dir").style =
        "display: none";
      document.getElementById("player").classList.add("not-available");
      if (resp.data.downloading)
        document.getElementById("player-downloading").style = "display: block";
      else {
        document.getElementById("player-downloading-required").style =
          "display: block";
        document.getElementById("download-book-btn").onclick = function () {
          startDownloading(this, resp.data.bid, resp.data.name);
          document.getElementById("player-downloading-required").style =
            "display: none";
          document.getElementById("player-downloading").style =
            "display: block";
        };
      }
    }
    document.getElementById("book-loading").style = "display: none;";
  });
}

document.addEventListener("DOMContentLoaded", (event) => {
  player = new window.Plyr("#audio-player", { storage: true, controls: [] });
  for (let scale of document.querySelectorAll('input[type="range"]')) {
    scale.oninput = scaleOninputDecorator(scale.oninput);
    scale.oninput();
  }
  player.on("pause", (event) => {
    let smallPlaybackControl = smallPlayer.querySelector(
      ".small-playback-control",
    );
    smallPlaybackControl.classList.add("play");
    smallPlaybackControl.classList.remove("pause");
    if (opened_book && player.current_book.bid != opened_book.bid) return;
    let bigPlaybackControl = document.getElementById("toggle-playback-btn");
    bigPlaybackControl.classList.add("play-button");
    bigPlaybackControl.classList.remove("pause-button");
  });
  player.on("play", (event) => {
    if (player.current_book.status != "started") {
      pywebview.api.mark_as_started(player.current_book.bid);
      player.current_book.status = "started";
    }
    let smallPlaybackControl = smallPlayer.querySelector(
      ".small-playback-control",
    );
    smallPlaybackControl.classList.remove("play");
    smallPlaybackControl.classList.add("pause");
    if (opened_book && player.current_book.bid != opened_book.bid) return;
    let bigPlaybackControl = document.getElementById("toggle-playback-btn");
    bigPlaybackControl.classList.remove("play-button");
    bigPlaybackControl.classList.add("pause-button");
  });
  player.on("timeupdate", (event) => {
    let listening_progress = Math.floor(
      (player.previous_items_duration + player.currentTime) /
        (player.total_duration / 100),
    );
    player.current_book.listening_progress = listening_progress;
    if (opened_book && player.current_book.bid == opened_book.bid) {
      let el = document.querySelector(".book-item.current");
      if (el.dataset.seeking) return;
      el.style.setProperty(
        "--current-item-percents",
        `${player.currentTime / (player.duration / 100)}%`,
      );
      document.querySelector(".book-item.current .cur-time").innerText =
        timeView(Math.floor(player.currentTime));
      document.querySelector(".book-listening-progress").innerText =
        `${listening_progress}% {{ gettext("book.listening_progress") }}`;
    }
    smallPlayer.querySelector(".listening-progres").innerText =
      `${listening_progress}% {{ gettext("book.listening_progress") }}`;
    if (Math.abs(player.currentTime - last_stop_flag_time) > 15) {
      pywebview.api.set_stop_flag(
        player.current_book.bid,
        player.current_item_index,
        Math.floor(player.currentTime),
      );
      last_stop_flag_time = player.currentTime;
    }
  });
  player.on("ended", (event) => {
    let next_item = player.current_item_index + 1;
    if (!player.current_book.files[next_item]) {
      pywebview.api.set_stop_flag(
        player.current_book.bid,
        player.current_item_index,
        Math.floor(player.duration),
      );
      player.current_book.status = "finished";
      initBookListeningProgress(player.current_book);
      return pywebview.api.mark_as_finished(player.current_book.bid);
    }
    _selectItem(next_item);
    player.play();
  });
});

function initBook(book) {
  smallPlayer.classList.add("visible");
  smallPlayer.querySelector(".small-playback-control").style =
    `background-image: url('${book.preview}'), url('/library/${book.local_preview}');`;
  smallPlayer.querySelector(".book-title").innerText = `${book.name}`;
  smallPlayer.querySelector(".listening-progres").innerText =
    `${book.listening_progress}% {{ gettext("book.listening_progress") }}`;
  smallPlayer.querySelector(".book-info").onclick = function () {
    if (opened_book && opened_book.bid == player.current_book.bid) return;
    openBookPage(player.current_book.bid);
  };
  player.current_book = book;
  let total_duration = 0;
  for (let item of book.items)
    total_duration += item.end_time - item.start_time;
  player.total_duration = total_duration;
  _selectItem(book.stop_flag.item);
  if (book.stop_flag.time) {
    player.play();
    player.once("playing", (event) => {
      player.currentTime = book.stop_flag.time;
      player.pause();
    });
  }
}
function togglePlayback() {
  if (opened_book && player.current_book.bid != opened_book.bid) {
    initBook(opened_book);
    player.once("pause", (event) => {
      togglePlayback();
    });
    return;
  }
  player.togglePlay();
}
function rewind() {
  if (!player.playing) return;
  if (player.current_book.bid != opened_book.bid) return;
  if (player.currentTime - 15 < 0 && player.current_item_index - 1 >= 0) {
    let t = player.currentTime;
    selectItem(player.current_item_index - 1);
    player.once("playing", (event) => {
      player.currentTime =
        player.current_book.items[player.current_item_index].end_time -
        player.current_book.items[player.current_item_index].start_time -
        (15 - t);
    });
  } else player.rewind(15);
}
function forward() {
  if (!player.playing) return;
  if (player.current_book.bid != opened_book.bid) return;
  if (
    player.currentTime + 15 > player.duration &&
    player.current_item_index + 1 < player.current_book.files.length
  ) {
    let t = player.duration - player.currentTime;
    selectItem(player.current_item_index + 1);
    player.once("playing", (event) => {
      player.currentTime = 15 - t;
    });
  }
  player.forward(15);
}
function selectItem(item_index) {
  if (player.current_book.bid != opened_book.bid) return;
  if (player.current_item_index == item_index) return;
  _selectItem(item_index);
}
function _selectItem(item_index) {
  let previous_items_duration = 0;
  for (let i of Array(item_index).keys()) {
    item = player.current_book.items[i];
    previous_items_duration += item.end_time - item.start_time;
  }
  player.previous_items_duration = previous_items_duration;
  let playing = player.playing;
  player.source = {
    type: "audio",
    title: "",
    sources: [
      {
        src: `/library/${player.current_book.files[item_index]}`,
        type: "audio/mp3",
      },
    ],
  };
  player.current_item_index = item_index;
  if (playing) player.play();
  if (opened_book && player.current_book.bid == opened_book.bid) {
    let cur_item = document.querySelector(".book-item.current");
    let new_item = document.querySelector(
      `.book-item[data-index="${item_index}"]`,
    );
    if (cur_item) cur_item.classList.remove("current");
    new_item.classList.add("current");
    if (player.current_item_index - 1 >= 0)
      document
        .getElementById("items-container")
        .scrollTo(
          0,
          (document.querySelector(".book-item").clientHeight + 2) *
            (player.current_item_index - 1),
        );
  }
}
function bookItemOnmousedown(event, el) {
  if (player.current_book.bid != opened_book.bid) return;
  if (!el.classList.contains("current")) return;
  if (!player.playing) return;
  el.dataset.seeking = "1";
  let percents = event.offsetX / (el.offsetWidth / 100);
  el.style.setProperty("--current-item-percents", `${percents}%`);
  document.querySelector(".book-item.current .cur-time").innerText = timeView(
    Math.floor((player.duration / 100) * percents),
  );
}
function bookItemOnmousemove(event, el) {
  if (!el.dataset.seeking) return;
  let percents = event.offsetX / (el.offsetWidth / 100);
  el.style.setProperty("--current-item-percents", `${percents}%`);
  document.querySelector(".book-item.current .cur-time").innerText = timeView(
    Math.floor((player.duration / 100) * percents),
  );
}
function bookItemOnmouseup(event, el) {
  if (!el.dataset.seeking) return;
  delete el.dataset.seeking;
  if (event.type == "mouseout") return;
  let percents = event.offsetX / (el.offsetWidth / 100);
  let time = (player.duration / 100) * percents;
  el.style.setProperty("--current-item-percents", `${percents}%`);
  document.querySelector(".book-item.current .cur-time").innerText = timeView(
    Math.floor(time),
  );
  player.currentTime = time;
}

function timeView(time) {
  return `${String(Math.floor(time / 60)).padStart(2, "0")}:${String(time % 60).padStart(2, "0")}`;
}

function loadLastListenedBook() {
  if (last_listened_book_bid) {
    pywebview.api.book_by_bid(last_listened_book_bid, true).then((resp) => {
      if (resp.status != "ok") {
        showError(resp.message);
        return;
      }
      if (resp.data.downloaded) initBook(resp.data);
    });
  }
}
function clearPlayingBook() {
  if (!player.current_book) return;
  smallPlayer.classList.remove("visible");
  player.stop();
  player.current_book = null;
}

function startPreviewFix(book) {
  pywebview.api.fix_preview(book.bid);
}

function initBookListeningProgress(book) {
  document.querySelector(
    "#book-page-content .book-listening-progress",
  ).innerHTML =
    `${book.listening_progress} {{ gettext("book.listening_progress")}}`;
  let el = document.querySelector(
    "#book-page-content .book-listening-progress-action",
  );
  if (book.status == "finished") {
    el.classList.add("finished");
    el.innerText = "{{ gettext('book.mark_as_new') }}";
    el.onclick = () => {
      pywebview.api.mark_as_new(book.bid);
      book.listening_progress = "0%";
      book.status = "new";
      initBookListeningProgress(book);
    };
  } else {
    el.classList.remove("finished");
    el.innerText = "{{ gettext('book.mark_as_finished') }}";
    el.onclick = () => {
      pywebview.api.mark_as_finished(book.bid);
      book.listening_progress = "100%";
      book.status = "finished";
      initBookListeningProgress(book);
    };
  }
}
function showListeningProgressAction() {
  document
    .querySelector(".book-listening-progress-action")
    .classList.toggle("showen");
}
function mark(bid, status) {}
