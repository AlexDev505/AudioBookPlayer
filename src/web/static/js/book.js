const sourceCardTemplate = document.querySelector("#source-card-template");
const chapterTemplate = document.querySelector("#chapter-template");
var opened_book = null;
var selected_source = null;

page("book-page").onOpen = function () {
  let bid = urlParams.get("bid");
  if (bid) loadBookData(bid);
};
page("book-page").unLoad = function () {
  opened_book = null;
  urlParams.delete("bid");
};
page("book-page").onHide = function () {};

function loadBookData(bid) {
  document.querySelector("#book-loading").classList.remove("hidden");
  pywebview.api.book_by_bid(parseInt(bid), true).then((resp) => {
    if (resp.status != "ok") {
      return showError(resp.message);
    }
    opened_book = resp.data;
    let page = document.querySelector("#book-page-content");
    page.querySelector(".book-title").innerHTML = resp.data.title;
    page.querySelector(".adding-date .content").innerHTML =
      resp.data.adding_date;
    showBookState(resp.data);
    page.querySelector(".book-cover").style =
      `background-image: url('${resp.data.cover}'), url('/library/${encodeURIComponent(resp.data.local_cover)}');`;
    page.querySelector(".author").innerHTML = resp.data.author;
    if (resp.data.series_name) {
      page.querySelector(".series").innerHTML =
        `${resp.data.series_name} (${resp.data.number_in_series})`;
      page.querySelector(".series").classList.remove("hidden");
    } else page.querySelector(".series").classList.add("hidden");
    page.querySelector(".book-description").innerHTML = resp.data.description;
    page.querySelector(".toggle-favorite").onclick = function () {
      toggleFavorite(this, resp.data.bid);
    };
    page.querySelector("#book-page .progress").classList.add("hidden");
    page.querySelector(".search-series").classList.add("hidden");
    page.querySelector(".open-in-browser").classList.add("hidden");
    page.querySelector("#player-controls").classList.add("hidden");
    page.querySelector("#sources").classList.add("hidden");
    page.querySelector("#text-source-loading").classList.add("hidden");
    document.querySelector("#book-page .download").classList.add("hidden");
    document.querySelector("#book-page .delete").classList.add("hidden");
    document.querySelector("#read-btn").classList.remove("loading");

    var selected_audio_book = opened_book.audio_sources.find(
      (source) => source.selected === true,
    );
    var selected_text_book = opened_book.text_sources.find(
      (source) => source.selected === true,
    );
    if (player.current_book && player.current_book.bid == resp.data.bid)
      selected_audio_book = player.current_source;
    if (selected_text_book && downloads.includes(selected_text_book.sid)) {
      document.querySelector("#text-source-loading").classList.remove("hidden");
      document.querySelector("#read-btn").classList.add("loading");
    } else if (selected_audio_book) {
      selected_source = selected_audio_book;
      showPlayer(selected_source);
      if (
        player.current_book &&
        player.current_book.bid == resp.data.bid &&
        player.playing
      )
        setPlaybackBtnState("pause");
    } else _showSources(resp.data);

    if (resp.data.audio_sources_count == 1 && !selected_audio_book) {
      selectAudioBook(resp.data.audio_sources[0].sid);
    }

    document
      .querySelector("#book-page #read-btn")
      .classList.toggle("hidden", !resp.data.text_sources_count);
    document
      .querySelector("#book-page #show-sources-btn")
      .classList.toggle(
        "hidden",
        resp.data.audio_sources_count <= 1 && resp.data.text_sources_count <= 1,
      );

    page.querySelector("#book-loading").classList.add("hidden");
  });
}
function showBookState(book) {
  let status = document.querySelector(
    `template.book-status[data-status="${book.status}"]`,
  ).innerHTML;
  document.querySelector("#book-page-content .status").innerHTML = status;
  let el = document.querySelector("#book-page-content .book-state-action");
  if (book.status == "completed") {
    el.classList.add("completed");
    var actionText = document.querySelector(
      "template.book-mark-as-new",
    ).innerHTML;
    el.onclick = () => {
      pywebview.api.mark_as_new(selected_source.sid);
      book.status = "new";
      showBookState(book);
    };
  } else {
    el.classList.remove("completed");
    var actionText = document.querySelector(
      "template.book-mark-as-completed",
    ).innerHTML;
    el.onclick = () => {
      pywebview.api.mark_as_completed(selected_source.sid);
      book.status = "completed";
      showBookState(book);
    };
  }
  el.innerHTML = actionText;
}
function showSources() {
  if (player.current_book && player.current_book.bid == opened_book.bid) {
    clearPlayingBook();
  }
  _showSources(opened_book);
  document.querySelector("#player-controls").classList.add("hidden");
}
function _showSources(book) {
  let audioSources = document.querySelector(
    "#audio-sources .sources-container",
  );
  let textSources = document.querySelector("#text-sources .sources-container");
  audioSources.innerHTML = "";
  textSources.innerHTML = "";
  for (let source of book.audio_sources) {
    let card = createSourceCard(source);
    card.querySelector(".source-card").onclick = () => {
      selectAudioBook(source.sid);
    };
    audioSources.appendChild(card);
  }
  for (let source of book.text_sources) {
    let card = createSourceCard(source);
    card.querySelector(".source-card").onclick = () => {
      selectTextBook(source.sid);
    };
    textSources.appendChild(card);
  }
  document.querySelector("#sources").classList.remove("hidden");
}
function createSourceCard(source) {
  let status = document.querySelector(
    `template.book-status[data-status="${source.status}"]`,
  ).innerHTML;
  let card = sourceCardTemplate.content.cloneNode(true);
  card.querySelector(".source-card").setAttribute("data-sid", source.sid);
  card.querySelector(".source-title").innerHTML = source.narrator
    ? source.narrator
    : source.publication;
  card.querySelector(".source-domain").innerHTML = source.domain;
  card.querySelector(".source-duration").innerHTML = source.duration
    ? source.duration
    : "";
  card.querySelector(".source-status").innerHTML = status;
  card.querySelector(".open-in-browser").onclick = (event) => {
    window.open(source.url, "_blank");
    event.stopPropagation();
  };
  return card;
}

function selectAudioBook(sid) {
  pywebview.api.select_source(sid);
  selected_source = opened_book.audio_sources.find(
    (source) => source.sid === sid,
  );
  selected_source.selected = true;
  showPlayer(selected_source);
}
function showPlayer(source) {
  document.querySelector("#player-controls").classList.remove("hidden");
  document
    .querySelector("#player-controls .playback-btn")
    .classList.remove("pause");
  document
    .querySelector("#player-controls .playback-btn")
    .classList.add("play");
  document.querySelector("#sources").classList.add("hidden");
  document.querySelector("#book-info .narrator").innerHTML = source.narrator;
  document.querySelector("#book-info .duration").innerHTML = source.duration;
  document.querySelector("#book-info .driver").innerHTML = source.domain;
  showListeningProgress(opened_book.bid, source.progress_percent);
  document.querySelector("#book-main .book-cover").style =
    `background-image: url('${source.cover}'), url('/library/${encodeURIComponent(source.local_cover)}');`;
  let openInBrowserBtn = document.querySelector(
    "#book-page-content .open-in-browser",
  );
  openInBrowserBtn.classList.remove("hidden");
  openInBrowserBtn.dataset.url = source.url;
  if (source.downloaded) {
    var btn = document.querySelector("#book-page-content .delete");
    btn.onclick = (event) => {
      deleteSourceFiles(event.target, source.sid);
    };
  } else {
    var btn = document.querySelector("#book-page-content .download");
    btn.onclick = (event) => {
      startDownloadingAudioBook(
        event.target,
        source.sid,
        `${opened_book.title} - ${source.narrator}`,
      );
    };
    btn.classList.toggle("loading", downloads.includes(source.sid));
  }
  btn.classList.remove("hidden");
  var container = document.querySelector(
    "#player-controls #chapters-container",
  );
  container.innerHTML = "";
  var i = 0;
  for (let chapter of source.chapters) {
    let el = chapterTemplate.content.cloneNode(true);
    el.querySelector(".chapter").setAttribute("data-index", i++);
    el.querySelector(".title").innerHTML = chapter.title;
    el.querySelector(".total-time").innerHTML = timeView(
      chapter.end_time - chapter.start_time,
    );
    container.appendChild(el);
  }
  container.scrollTo(0, 0);
  selectChapterEl(source.progress.chapter_index);
  let duration =
    source.chapters[source.progress.chapter_index].end_time -
    source.chapters[source.progress.chapter_index].start_time;
  showChapterPlaybackTime(
    source.progress.time / (duration / 100),
    Math.floor(source.progress.time),
  );
}
function selectChapterEl(chapter_index) {
  let cur_chapter = document.querySelector("#player-controls .chapter.current");
  let new_chapter = document.querySelector(
    `#player-controls .chapter[data-index="${chapter_index}"]`,
  );
  if (cur_chapter) cur_chapter.classList.remove("current");
  new_chapter.classList.add("current");
  if (chapter_index >= 1) {
    document
      .querySelector(
        `#player-controls .chapter[data-index="${chapter_index - 1}"]`,
      )
      .scrollIntoView();
  }
}
function showChapterPlaybackTime(percents, time) {
  let el = document.querySelector("#book-page .chapter.current");
  if (el.dataset.seeking) return;
  el.style.setProperty("--current-item-percents", `${percents}%`);
  document.querySelector("#book-page .chapter.current .cur-time").innerText =
    timeView(time);
}

function showBookStateAction() {
  document.querySelector(".book-state-action").classList.toggle("showen");
}

function togglePlayback() {
  if (
    !player.current_source ||
    (selected_source && player.current_source.sid != selected_source.sid)
  ) {
    initPlayer(opened_book, selected_source);
    return player.play();
  }
  player.togglePlay();
}
function bookChapterOnmousedown(event, el) {
  if (player.current_book.bid != opened_book.bid) return;
  if (!el.classList.contains("current")) return;
  if (!player.playing) return;
  el.dataset.seeking = "1";
  let percents = event.offsetX / (el.offsetWidth / 100);
  el.style.setProperty("--current-item-percents", `${percents}%`);
  document.querySelector(".chapter.current .cur-time").innerText = timeView(
    Math.floor((player.duration / 100) * percents),
  );
}
function bookChapterOnmousemove(event, el) {
  if (!el.dataset.seeking) return;
  let percents = event.offsetX / (el.offsetWidth / 100);
  el.style.setProperty("--current-item-percents", `${percents}%`);
  document.querySelector(".chapter.current .cur-time").innerText = timeView(
    Math.floor((player.duration / 100) * percents),
  );
}
function bookChapterOnmouseup(event, el) {
  if (!el.dataset.seeking) return;
  delete el.dataset.seeking;
  if (event.type == "mouseout") return;
  let percents = event.offsetX / (el.offsetWidth / 100);
  let time = (player.duration / 100) * percents;
  el.style.setProperty("--current-item-percents", `${percents}%`);
  document.querySelector(".chapter.current .cur-time").innerText = timeView(
    Math.floor(time),
  );
  player.currentTime = time;
}

function readBook() {
  if (player.current_book && player.current_book.bid == opened_book.bid) {
    clearPlayingBook();
  }
  var selected_text_source = opened_book.text_sources.find(
    (source) => source.selected === true,
  );
  if (opened_book.text_sources_count == 1)
    return selectTextBook(opened_book.text_sources[0].sid);
  if (!selected_text_source) return showSources();
  if (!checkIsTextBookDownloaded(selected_text_source)) return;
  _readBook(selected_text_source);
}
function selectTextBook(sid) {
  pywebview.api.select_source(sid);
  var selected_text_source = opened_book.text_sources.find(
    (source) => source.sid === sid,
  );
  selected_text_source.selected = true;
  if (!checkIsTextBookDownloaded(selected_text_source)) return;
  _readBook(selected_text_source);
}
function checkIsTextBookDownloaded(source) {
  if (source.downloaded) return true;
  document.querySelector("#player-controls").classList.add("hidden");
  document.querySelector("#sources").classList.add("hidden");
  document.querySelector("#text-source-loading").classList.remove("hidden");
  startDownloadingTextBook(
    document.querySelector("#read-btn"),
    source.sid,
    `${opened_book.title} - ${source.publication}`,
  );
  return false;
}

function deleteSourceFiles(btn, sid) {
  btn.classList.add("loading");
  pywebview.api.delete_source_files(sid).then((resp) => {
    if (resp.status != "ok") return showError(resp.message);
    if (opened_book && selected_source.sid == sid)
      loadBookData(opened_book.bid);
  });
}
function removeBook(btn) {
  let bid = Number(btn.dataset.bid);
  pywebview.api.remove_book(bid).then((resp) => {
    if (resp.status != "ok") return showError(resp.message);
  });
  document.querySelector(`.book-card[data-bid='${bid}']`).remove();
}
function openBookDir() {
  pywebview.api.open_book_dir(opened_book.bid).then((resp) => {
    if (resp.status != "ok") return showError(resp.message);
  });
}
