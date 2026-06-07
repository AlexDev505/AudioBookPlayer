const libraryTitleTemplate = document.getElementById("library-title-template");
const libraryFavoritesTitleTemplate = document.getElementById(
  "library-favorites-title-template",
);
const bookCardTemplate = document.getElementById("book-card-template");
const filterBySecionItemTemplate = document.getElementById(
  "filter-by-section-item-template",
);
const LIBRARY_FETCH_LIMIT = 10;

var library_filters = {};

page("library-page").onOpen = function () {
  applyUrlParams();
  fillFilterBySections();
  library_filters.favorite = urlParams.get("favorite") == "1";
  library_filters.sort = urlParams.get("sort");
  library_filters.reverse = urlParams.get("reverse") == "1";
  library_filters.author = urlParams.get("author");
  library_filters.series = urlParams.get("series");
  library_filters.search_query = urlParams.get("search_query");
  if (library_filters.search_query)
    document.querySelector("#search-in-library-input-line input").value =
      library_filters.search_query;
  var base_text = library_filters.favorite
    ? libraryFavoritesTitleTemplate.innerHTML
    : libraryTitleTemplate.innerHTML;
  if (urlParams.get("author")) base_text += ` - ${urlParams.get("author")}`;
  else if (urlParams.get("series")) {
    base_text += ` - ${urlParams.get("series")}`;
    // pywebview.api
    //   .get_series_duration(urlParams.get("series"))
    //   .then((response) => {
    //     document.getElementById("library-title").innerHTML +=
    //       ` (${response.data})`;
    //   });
  }
  document.querySelector("#library-title").innerHTML = base_text;
  toggleReverseCheckbox();
  loadBooks();
};
page("library-page").onHide = function () {};
page("library-page").unLoad = function () {
  library_filters = {};
  books_count = 0;
  can_load_more = true;
  document.getElementById("library-container").innerHTML = "";
  document.getElementById("author-section").innerHTML = "";
  document.getElementById("series-section").innerHTML = "";
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
    el.querySelector(".remove").setAttribute("data-bid", book.bid);
    el.querySelector(".toggle-favorite").setAttribute("data-bid", book.bid);
    el.querySelector(".cover").src = book.cover;
    el.querySelector(".book-title").textContent = book.title;
    el.querySelector(".adding-date .content").textContent = book.adding_date;
    el.querySelector(".book-description").textContent = book.description;
    el.querySelector(".text-sources-count").textContent =
      book.text_sources_count ? book.text_sources_count : "";
    el.querySelector(".audio-sources-count").textContent =
      book.audio_sources_count ? book.audio_sources_count : "";
    el.querySelector(".author").textContent = book.author;
    el.querySelector(".series").textContent =
      `${book.series_name}${book.number_in_series ? ` (${book.number_in_series})` : ""}`;
    if (book.favorite)
      el.querySelector(".toggle-favorite").classList.add("active");
    loadCover(book);
    container.appendChild(el);
  }

  books_count += response.data.length;
  if (response.data.length < LIBRARY_FETCH_LIMIT) can_load_more = false;
}

function loadCover(book) {
  var img = new Image();
  img.src = book.cover;
  img.onload = function () {
    var el = document.querySelector(
      `#library-container .book-card[data-bid='${book.bid}'] .cover`,
    );
    if (!el) return;
    el.appendChild(img);
  };
  img.onerror = function () {
    // startPreviewFix(book);  TODO
    img.src = `/library/${book.local_preview}`;
    img.onerror = function () {
      document.querySelector(
        `.book-card[data-bid='${book.bid}'] .cover`,
      ).style = "background-image: url(static/images/book.svg)";
    };
  };
}

function openBookPage(card) {
  if (window.event.srcElement.classList.contains("icon-btn")) return;
  addUrlParams({ bid: card.dataset.bid });
  if (Page.last == page("book-page")) Page.last = null;
  if (!page("book-page").shown) page("book-page").open();
  else page("book-page").onOpen();
}

function applyFilters() {
  page("library-page").unLoad();
  page("library-page").onOpen();
}
function toggleFilterMenu() {
  filter_menu_opened = !document
    .getElementById("filter-menu")
    .classList.toggle("collapsed");
}
function toggleReverse() {
  if (urlParams.get("reverse")) urlParams.delete("reverse");
  else addUrlParams({ reverse: 1 });
  applyFilters();
}
function toggleReverseCheckbox() {
  document
    .getElementById("reverse-checkbox")
    .classList.toggle("checked", urlParams.get("reverse") !== null);
}
function filterByAuthor(event) {
  let value = event.target.dataset.value;
  if (urlParams.get("series")) {
    urlParams.delete("series");
    urlParams.delete("sort");
  }
  if (value == urlParams.get("author")) urlParams.delete("author");
  else addUrlParams({ author: value });
  applyFilters();
}
function filterBySeries(event) {
  let value = event.target.dataset.value;
  if (urlParams.get("author")) urlParams.delete("author");
  if (value == urlParams.get("series")) {
    urlParams.delete("series");
    urlParams.delete("sort");
  } else addUrlParams({ series: value, sort: "number_in_series" });
  applyFilters();
}
function selectFilterBy(value) {
  document
    .querySelector(`.filter-by-section-item[data-value="${value}"]`)
    .classList.add("checked");
}
lastSearch = 0;
async function searchBooksInLibrary() {
  var query = String(
    document.querySelector("#search-in-library-input-line input").value.trim(),
  );
  if (query.length == 0 && urlParams.get("search_query")) {
    urlParams.delete("search_query");
    applyFilters();
    return;
  }
  if (query.length < 3) return;
  if (Date.now() - lastSearch < 1000) await delay(1000);
  if (
    document
      .querySelector("#search-in-library-input-line input")
      .value.trim() != query
  )
    return;

  lastSearch = Date.now();
  addUrlParams({ search_query: query });
  applyFilters();
}
function fillFilterBySections() {
  pywebview.api.get_all_authors().then((response) => {
    fillFilterBySection(response.data, "author", filterByAuthor);
  });
  pywebview.api.get_all_series().then((response) => {
    fillFilterBySection(response.data, "series", filterBySeries);
  });
}
function fillFilterBySection(data, section, item_callback) {
  filter_by_section = document.getElementById(`${section}-section`);
  filter_by_section_btn = document.getElementById(`${section}-section-btn`);
  if (!data.length) {
    filter_by_section_btn.classList.add("disabled");
    return;
  }
  filter_by_section_btn.classList.remove("disabled");
  for (obj of data) {
    let el = filterBySecionItemTemplate.content.cloneNode(true);
    el.querySelector("div").setAttribute("data-value", obj);
    el.querySelector("div").innerText = obj;
    el.querySelector("div").onclick = item_callback;
    filter_by_section.appendChild(el);
  }
  if (urlParams.get(section)) selectFilterBy(urlParams.get(section));
}
