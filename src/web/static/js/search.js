const searchResultItemTemplate = document.getElementById(
  "search-result-item-template",
);

page("search-page").onShow = function (el) {
  q = urlParams.get("search");
  if (q) {
    document.querySelector("#search-input-line input").value = q;
    searchBooks();
  }
};
page("search-page").onHide = function () {
  urlParams.delete("search");
};
page("search-page").unLoad = function () {
  document.getElementById("search-results-container").innerHTML = "";
  document.querySelector("#search-input-line input").value = "";
  document.getElementById("search-results-container").classList.remove("shown");
};

function hideSearchAnimation() {
  document
    .querySelector("#search-input-line .search-btn")
    .classList.remove("loading");
}
function showSearchAnimation() {
  document
    .querySelector("#search-input-line .search-btn")
    .classList.add("loading");
}

lastSearch = 0;
async function searchBooks() {
  var query = String(
    document.querySelector("#search-input-line input").value.trim(),
  );
  if (query.length < 3) return;

  showSearchAnimation();
  if (Date.now() - lastSearch < 1000) await delay(1000);
  if (document.querySelector("#search-input-line input").value.trim() != query)
    return;

  lastSearch = Date.now();
  addUrlParams({ search: query });

  pywebview.api.search_books(query).then(onSearchCompleted);
}

function onSearchCompleted(resp, clear = true) {
  if (document.querySelector("#search-input-line input").value == "") return;
  searching = false;
  if (resp.status != "ok") return showError(resp.message);
  resp = resp.data;
  var books = {};
  var items = [];
  container = document.getElementById("search-results-container");
  for (let book of resp) {
    var el = document.querySelector(
      `.search-result-item[data-hash="${book.hash}"]`,
    );
    var exists = el !== null;
    if (!exists) {
      el = document.importNode(searchResultItemTemplate.content, true);
      el.querySelector(".search-result-item").dataset.hash = book.hash;
      el.querySelector(".item-cover").style.backgroundImage =
        `url(${book.cover})`;
      el.querySelector(".item-title").textContent = book.title;
      el.querySelector(".item-author").textContent = book.author;
      el.querySelector(".item-series-name").textContent =
        `${book.series_name}${book.number_in_series ? ` (${book.number_in_series})` : ""}`;
    }
    if (exists && book.updated) {
      el.querySelector(".add-book-btn").classList.remove("added");
      container.removeChild(el);
    }
    if (!exists || book.updated) {
      books[book.hash] = book.urls;
      el.querySelector(".item-narrators").textContent =
        book.narrators.join(" | ");
      el.querySelector(".item-publications").textContent =
        book.publications.join(" | ");
      el.querySelector(".item-durations").textContent =
        book.durations.join(" | ");
      items.push(el);
    }
  }
  if (clear) {
    container.innerHTML = "";
    container.scrollTop = 0;
    searching = false;
    can_search_next = true;
  }
  for (let item of items) {
    container.appendChild(item);
  }
  if (!container.classList.contains("shown")) container.classList.add("shown");
  hideSearchAnimation();
  if (resp.length == 0) {
    can_search_next = false;
    return;
  }
  pywebview.api
    .check_is_sources_exists(books)
    .then(onCheckIsBooksExistsCompleted);
  container = document.getElementById("search-results-container");
  if (
    container.scrollHeight - container.offsetHeight - container.scrollTop ==
    0
  )
    onSearchResultContainerScroll();
}

function onCheckIsBooksExistsCompleted(resp) {
  for (let hash of resp.data) {
    let item = document.querySelector(
      `.search-result-item[data-hash="${hash}"]`,
    );
    if (item) item.querySelector(".add-book-btn").classList.add("added");
  }
}

searching = false;
can_search_next = true;
function onSearchResultContainerScroll() {
  if (!can_search_next || searching) return;
  let container = document.getElementById("search-results-container");
  if (
    container.scrollHeight - container.offsetHeight - container.scrollTop <
    100
  ) {
    searching = true;
    showSearchAnimation();
    pywebview.api
      .search_books(
        document.querySelector("#search-input-line input").value.trim(),
      )
      .then((resp) => {
        onSearchCompleted(resp, false);
      });
  }
}
