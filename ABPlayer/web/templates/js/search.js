page("search-page").onHide = function() {
    document.getElementById("search-results-container").innerHTML = ""
    document.querySelector("#search-input-line input").value = ""
    document.getElementById("search-results-container").classList.remove("shown")
    urlParams.delete("search")
}
page("search-page").onShow = function(el) {
    addUrlParams({"page": el.id})
    q = urlParams.get("search")
    if (q) {
        document.querySelector("#search-input-line input").value = q
        searchBooks()
    }
}

function loadAvailableDrivers(resp) {
    container = document.getElementById("drivers-container")
    if (required_drivers.length == 0) required_drivers = resp.data
    _required_drivers = required_drivers.slice(0, required_drivers.length)
    required_drivers = []
    for (driver of resp.data) {
        if (_required_drivers.includes(driver)) required_drivers.push(driver)
        container.innerHTML = container.innerHTML + `
          <div class="driver-option checkbox ${(_required_drivers.includes(driver)) ? 'checked' : ''}" data-driver="${driver}" onclick="toggleDriver('${driver}')">${driver}</div>
        `
    }
}
function toggleDriver(driver) {
    option = document.querySelector(`.driver-option[data-driver='${driver}']`)
    if (required_drivers.length == 1 & required_drivers.includes(driver)) return
    if (required_drivers.includes(driver)) {
        required_drivers = required_drivers.filter(v => v !== driver)
    } else required_drivers.push(driver)
    option.classList.toggle("checked")
    if (document.querySelector("#search-input-line input").value.trim()) searchBooks()
}
function toggleDriverOptions() {
    container = document.getElementById("drivers-container")
    if (container.classList.contains("shown")) container.classList.remove("shown")
    else container.classList.add("shown")
}

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
    addUrlParams({"search": query})

    pywebview.api.search_books(query, required_drivers=required_drivers).then(onSearchCompleted)
}

function searchBookSeries(url, series_name) {
    document.querySelector("#search-input-line input").value = series_name
    page('search-page').show()
    showSearchAnimation()
    pywebview.api.search_book_series(url).then((resp) => {
        onSearchCompleted(resp)
        can_search_next = false
    })
}

function hideSearchAnimation() {
    document.querySelector("#search-input-line .search-btn").classList.remove("loading")
}
function showSearchAnimation() {
    document.querySelector("#search-input-line .search-btn").classList.add("loading")
}

searching = false
can_search_next = true
function onSearchResultContainerScroll() {
    if (!can_search_next || searching) return
    container = document.getElementById("search-results-container")
    if (container.scrollHeight - container.offsetHeight - container.scrollTop < 100) {
        searching = true
        showSearchAnimation()
        pywebview.api.search_books(
            document.querySelector("#search-input-line input").value.trim()
        ).then((resp) => {onSearchCompleted(resp, false)})
    }
}

function onSearchCompleted(resp, clear=true) {
    if (!page("search-page").shown) return
    searching = false
    if (resp.status != "ok") {showError(resp.message); return}
    resp = resp.data
    html = ""
    urls = []
    for (book of resp) {
        urls.push(book.url)
        html = html + `<div class="search-result-item" data-url="${book.url}">
          <div class="search-result-item-card">
            <div class="item-cover" style="background-image: url(${book.preview})"></div>
            <div>
              <div class="item-title">${book.name}</div>
              <div class="item-info">
                <div class="item-author">${book.author}</div>
                <div class="item-reader">${book.reader}</div>
                <div class="item-duration">${book.duration}</div>
                <div class="item-series-name">${book.series_name} ${(book.number_in_series)? ` (${book.number_in_series})` : ''}</div>
                <div class="item-driver">${book.driver}</div>
              </div>
            </div>
          </div>
          <div class="icon-btn add-book-btn" onclick="addBook(this)"><span>{{ gettext("book.add_to_library") }}</span></div>
        </div>`
    }
    if (!resp.length && clear) html = '<div id="no-search-result">{{ gettext("search.empty") }}</div>'
    container = document.getElementById("search-results-container")
    if (!container.classList.contains("shown")) container.classList.add("shown")
    if (clear) {
        container.innerHTML = html
        container.scrollTop = 0
        searching = false
        can_search_next = true
    } else {
        container.innerHTML = container.innerHTML + html
        if (resp.length == 0)
            can_search_next = false
    }
    pywebview.api.check_is_books_exists(urls).then(onCheckIsBooksExistsCompleted)
    hideSearchAnimation()
    container = document.getElementById("search-results-container")
    if (container.scrollHeight - container.offsetHeight - container.scrollTop == 0) onSearchResultContainerScroll()
}

function onCheckIsBooksExistsCompleted(resp) {
    for (url of resp.data) {
        item = document.querySelector(`.search-result-item[data-url="${url}"]`)
        if (item)
            item.querySelector(".add-book-btn").classList.add("added")
    }
}

function addBook(el) {
    if (el.classList.contains("added") || el.classList.contains("loading")) return
    el.classList.add("loading")
    pywebview.api.add_book_to_library(el.parentElement.dataset.url).then(
        (response) => {
            el.classList.remove("loading")
            if (response.status != "ok") {
                showError(response.message)
            } else
                el.classList.add("added")
        }
    )
}
