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
      `background-image: url('${resp.data.cover}'), url('/library/${resp.data.local_cover}');`;
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
    page.querySelector(".search-series").classList.add("hidden");
    page.querySelector(".open-book-dir").classList.add("hidden");
    page.querySelector(".open-in-browser").classList.add("hidden");
    page.querySelector("#player-controls").classList.add("hidden");
    page.querySelector("#sources").classList.remove("hidden");
    document
      .querySelector("#book-page-content .download")
      .classList.add("hidden");
    document
      .querySelector("#book-page-content .delete")
      .classList.add("hidden");

    showSources(resp.data);

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
      pywebview.api.mark_book_as_new(book.bid);
      book.status = "new";
      showBookState(book);
    };
  } else {
    el.classList.remove("completed");
    var actionText = document.querySelector(
      "template.book-mark-as-completed",
    ).innerHTML;
    el.onclick = () => {
      pywebview.api.mark_book_as_completed(book.bid);
      book.status = "completed";
      showBookState(book);
    };
  }
  el.innerHTML = actionText;
}
function showSources(book) {
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
    textSources.appendChild(card);
  }
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
    : source.total_pages;
  card.querySelector(".source-status").innerHTML = status;
  card.querySelector(".open-in-browser").onclick = () => {
    window.open(source.url, "_blank");
  };
  return card;
}

function selectAudioBook(sid) {
  pywebview.api.select_audio_source(sid);
  selected_source = opened_book.audio_sources.find(
    (source) => source.sid === sid,
  );
  showPlayer(selected_source);
}
function showPlayer(source) {
  document.querySelector("#player-controls").classList.remove("hidden");
  document.querySelector("#sources").classList.add("hidden");
  document.querySelector("#book-info .narrator").innerHTML = source.narrator;
  document.querySelector("#book-info .duration").innerHTML = source.duration;
  document.querySelector("#book-info .driver").innerHTML = source.domain;
  document
    .querySelector("#book-page-content .download")
    .classList.remove("hidden");
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
}

function showBookStateAction() {
  document.querySelector(".book-state-action").classList.toggle("showen");
}

function timeView(time) {
  return `${String(Math.floor(time / 60)).padStart(2, "0")}:${String(time % 60).padStart(2, "0")}`;
}

function bookChapterOnmousedown(event, el) {}
function bookChapterOnmousemove(event, el) {}
function bookChapterOnmouseup(event, el) {}
