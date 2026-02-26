const libraryTitleTemplate = document.getElementById("library-title-template");
const libraryFavoritesTitleTemplate = document.getElementById(
  "library-favorites-title-template",
);
const bookCardTemplate = document.getElementById("book-card-template");
const LIBRARY_FETCH_LIMIT = 10;

var library_filters = {};

page("library-page").onOpen = function () {
  library_filters.favorite = urlParams.get("favorite") == "1";
  var base_text = library_filters.favorite
    ? libraryFavoritesTitleTemplate.innerHTML
    : libraryTitleTemplate.innerHTML;
  document.querySelector("#library-title").innerHTML = base_text;
  loadBooks();
};
page("library-page").onHide = function () {};
page("library-page").unLoad = function () {
  library_filters = {};
  document.getElementById("library-container").innerHTML = "";
};

var books_count = 0;
var fetching_books = false;
var can_load_more = true;
function loadBooks() {
  fetching_books = true;
  let limit = LIBRARY_FETCH_LIMIT;
  let favorite = library_filters.favorite;
  document.getElementById("library-container").classList.add("loading");
  pywebview.api
    .get_library(
      (limit = limit),
      (offset = books_count),
      (sort = library_filters.sort || "adding_date"),
      (reverse = library_filters.reverse || false),
      (author = library_filters.author),
      (series = library_filters.series),
      (favorite = favorite),
      (status = library_filters.status),
      (search_query = library_filters.search_query),
    )
    .then((response) => showBooks(response));
}
function onLibraryScrollEnd(el) {
  if (!can_load_more || fetching_books) return;
  if (el.scrollHeight - el.offsetHeight - el.scrollTop < 100) loadBooks();
}
function showBooks(response) {
  fetching_books = false;
  let container = document.getElementById("library-container");
  container.classList.remove("loading");

  if (response.status != "ok") return showError(response.message);

  console.log(response.data);
  for (let book of response.data) {
    let el = bookCardTemplate.content.cloneNode(true);
    el.querySelector(".book-card").setAttribute("data-bid", book.bid);
    el.querySelector(".book-cover").src = book.cover;
    el.querySelector(".book-title").textContent = book.title;
    el.querySelector(".book-adding-date").textContent = book.adding_date;
    el.querySelector(".book-description").textContent = book.description;
    el.querySelector(".book-author").textContent = book.author;
    el.querySelector(".book-series").textContent =
      `${book.series_name}${book.number_in_series ? ` (${book.number_in_series})` : ""}`;
    if (book.favorite)
      el.querySelector(".toggle-favorite-btn").classList.add("active");
    if (book.downloaded) {
      el.querySelector(".download-btn").remove();
    } else {
      el.querySelector(".delete-btn").remove();
      if (book.downloading)
        el.querySelector(".download-btn").classList.add("loading");
    }
    loadPreview(book);
    container.appendChild(el);
  }

  books_count += response.data.length;
  if (response.data.length < LIBRARY_FETCH_LIMIT) can_load_more = false;
}

function loadPreview(book) {
  var img = new Image();
  img.src = book.cover;
  img.onload = function () {
    var el = document.querySelector(
      `#library-container .book-card[data-bid='${book.bid}'] .book-cover`,
    );
    if (!el) return;
    el.appendChild(img);
  };
  img.onerror = function () {
    // startPreviewFix(book);  TODO
    img.src = `/library/${book.local_preview}`;
    img.onerror = function () {
      document.querySelector(
        `.book-card[data-bid='${book.bid}'] .book-cover`,
      ).style = "background-image: url(static/images/book.svg)";
    };
  };
}
