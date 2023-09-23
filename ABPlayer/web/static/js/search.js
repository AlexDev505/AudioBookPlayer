search_offset = 0
lastSearch = 0
async function searchBooks() {
    var query = String(document.querySelector("#search-input-line input").value.trim())
    if (query.length < 3) return

    showSearchAnimation()
    if (Date.now() - lastSearch < 1000)
        await delay(1000)
    if (document.querySelector("#search-input-line input").value.trim() != query)
        return

    lastSearch = Date.now()

    pywebview.api.search_books(query, limit=20).then(onSearchCompleted)
}

function hideSearchAnimation() {
    document.querySelector("#search-input-line button").classList.remove("loading")
}
function showSearchAnimation() {
    document.querySelector("#search-input-line button").classList.add("loading")
}

searching = false
can_get_next = true
function onSearchResultContainerScroll() {
    if (!can_get_next || searching) return
    container = document.getElementById("search-results-container")
    if (container.scrollHeight - container.offsetHeight - container.scrollTop < 100) {
        searching = true
        showSearchAnimation()
        pywebview.api.search_books(
            document.querySelector("#search-input-line input").value.trim(),
            limit=10,
            offset=search_offset
        ).then((resp) => {onSearchCompleted(resp, false)})
    }
}

function onSearchCompleted(resp, clear=true) {
    searching = false
    html = ""
    for (book of resp) {
        html = html + `<div class="search-result-item">
          <div class="search-result-item-card">
            <div class="item-cover" style="background-image: url(${book.preview})"></div>
            <div>
              <div class="item-title">${book.name}</div>
              <div class="item-info">
                <div class="item-author">${book.author}</div>
                <div class="item-reader">${book.reader}</div>
                <div class="item-duration">${book.duration}</div>
                ${(book.series_name) ? `<div class="item-series-name">${book.series_name}</div>`: ""}
                <div class="item-driver">${book.driver}</div>
              </div>
            </div>
          </div>
          <div class="icon-btn add-book-btn"><span>в библиотеку</span></div>
        </div>`
    }
    if (!resp.length && clear) html = '<div id="no-search-result">Ничего не найдено</div>'
    container = document.getElementById("search-results-container")
    if (!container.classList.contains("shown")) container.classList.add("shown")
    if (clear) {
        container.innerHTML = html
        container.scrollTop = 0
        search_offset = resp.length
        searching = false
        can_get_next = true
    } else {
        container.innerHTML = container.innerHTML + html
        search_offset += resp.length
        if (resp.length < 10)
            can_get_next = false
    }
    hideSearchAnimation()
}
