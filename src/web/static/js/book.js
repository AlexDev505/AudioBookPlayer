const sourceCardTemplate = document.querySelector("#source-card-template");
var opened_book = null;

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
  pywebview.api.book_by_bid(parseInt(bid), true).then((resp) => {
    if (resp.status != "ok") {
      return showError(resp.message);
    }
    opened_book = resp.data;
    let page = document.querySelector("#book-page-content");
    page.querySelector(".book-title").innerHTML = resp.data.title;
    page.querySelector(".book-adding-date .content").innerHTML =
      resp.data.adding_date;
    showBookState(resp.data);
    page.querySelector(".book-preview").style =
      `background-image: url('${resp.data.cover}'), url('/library/${resp.data.local_cover}');`;
    page.querySelector(".book-author").innerHTML = resp.data.author;
    if (resp.data.series_name) {
      page.querySelector(".book-series").innerHTML =
        `${resp.data.series_name} (${resp.data.number_in_series})`;
      page.querySelector(".book-series").style = "display: flex";
    } else page.querySelector(".book-series").style = "display: none";
    page.querySelector(".book-description").innerHTML = resp.data.description;
    page.querySelector("#player-controls").style = "display: none";
    page.querySelector(".toggle-favorite-btn").onclick = function () {
      toggleFavorite(this, resp.data.bid);
    };
    page.querySelector(".search-series").style = "display: none";
    page.querySelector(".open-book-dir").style = "display: none";
    page.querySelector(".open-in-browser").style = "display: none";
    page.querySelector("#player").classList.add("not-available");

    showSources(resp.data);

    page.querySelector("#book-loading").style = "display: none;";
  });
}
function showBookState(book) {
  let status = document.querySelector(
    `template.book-status[data-status="${book.status}"]`,
  ).innerHTML;
  document.querySelector("#book-page-content .book-status").innerHTML = status;
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

function showBookStateAction() {
  document.querySelector(".book-state-action").classList.toggle("showen");
}
