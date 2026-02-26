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
    page.querySelector("#player-downloading-required").style = "display: none";
    page.querySelector("#player-downloading").style = "display: none";
    page.querySelector(".toggle-favorite-btn").onclick = function () {
      toggleFavorite(this, resp.data.bid);
    };
    page.querySelector(".search-series").style = "display: none";
    page.querySelector(".open-book-dir").style = "display: none";
    page.querySelector(".open-in-browser").style = "display: none";
    page.querySelector("#player").classList.add("not-available");
    page.querySelector("#book-loading").style = "display: none;";
  });
}
