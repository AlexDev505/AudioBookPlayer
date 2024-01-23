filterMenu = document.getElementById("filter-menu")
function toggleFilterMenu() {
    if (filter_menu_opened)
        filterMenu.classList.add("collapsed")
    else
        filterMenu.classList.remove("collapsed")
    filter_menu_opened = !filter_menu_opened
}

function clearLibraryFilters() {
    urlParams.delete("sort")
    urlParams.delete("author")
    urlParams.delete("series")
    urlParams.delete("favorite")
    urlParams.delete("search_query")
}

function applyFilters() {
    clearLibrary()
    onOpenLibrary(page("library-page").el)
}

function toggleReverse() {
    if (urlParams.get("reverse")) urlParams.delete("reverse")
    else addUrlParams({"reverse": 1})
    applyFilters()
}
function toggleReverseCheckbox(value) {
    option = document.getElementById("reverse-checkbox")
    if (!value) option.classList.remove("checked")
    else option.classList.add("checked")
}

function filterByAuthor(value) {
    if (urlParams.get("series")) urlParams.delete("series")
    if (value == urlParams.get("author")) urlParams.delete("author")
    else addUrlParams({"author": value})
    applyFilters()
}
function filterBySeries(value) {
    if (urlParams.get("author")) urlParams.delete("author")
    if (value == urlParams.get("series")) urlParams.delete("series")
    else addUrlParams({"series": value})
    applyFilters()
}
function selectFilterBy(value) {
    document.querySelector(`.filter-by-section-item[data-value="${value}"]`).classList.add("checked")
}

lastSearch = 0
async function searchBooksInLibrary() {
    var query = String(document.querySelector("#search-in-library-input-line input").value.trim())
    if (query.length == 0 && urlParams.get("search_query")) {
        urlParams.delete("search_query")
        applyFilters()
        return
    }
    if (query.length < 3) return
    if (Date.now() - lastSearch < 1000)
        await delay(1000)
    if (document.querySelector("#search-in-library-input-line input").value.trim() != query)
        return

    lastSearch = Date.now()
    addUrlParams({"search_query": query})
    applyFilters()
}


is_authors_section_full = false
is_series_section_full = false
function fillFilterBySections() {
    pywebview.api.get_all_authors().then((response) => {
        filter_by_section = document.getElementById("authors-section")
        filter_by_section_btn = document.getElementById("authors-section-btn")
        if (!response.data.length) {
            is_authors_section_full = false
            filter_by_section_btn.classList.add("disabled")
            return
        }
        filter_by_section_btn.classList.remove("disabled")
        html = ""
        for (obj of response.data) {
            html = html + `<div class="filter-by-section-item" data-value="${obj}" onclick="filterByAuthor(this.dataset.value)">${obj}</div>`
        }
        filter_by_section.innerHTML = html
        if (urlParams.get("author")) selectFilterBy(urlParams.get("author"))
    })
    pywebview.api.get_all_series().then((response) => {
        filter_by_section = document.getElementById("series-section")
        filter_by_section_btn = document.getElementById("series-section-btn")
        if (!response.data.length) {
            is_series_section_full = false
            filter_by_section_btn.classList.add("disabled")
            return
        }
        filter_by_section_btn.classList.remove("disabled")
        html = ""
        for (obj of response.data) {
            html = html + `<div class="filter-by-section-item" data-value="${obj}" onclick="filterBySeries(this.dataset.value)">${obj}</div>`
        }
        filter_by_section.innerHTML = html
        if (urlParams.get("series")) selectFilterBy(urlParams.get("series"))
    })
}


class Section extends Page {
    constructor(el) {
        super(el)
        this.btn = document.getElementById(el.id + "-btn")
    }
    show() {
        super.show()
        this.btn.classList.add("active")
    }
    hide() {
        super.hide()
        this.btn.classList.remove("active")
    }
}

var books_in_sections = {}
var sections = {}
for (section_el of document.getElementsByClassName("books-section")) {
    section_ = new Section(section_el)
    sections[section_el.id] = section_
    section_.onShow = addBooks
    section_.onHide = onHideSection
    section_.hide()
}
function section(el_id) {return sections[el_id]}

function clearLibrary() {
    for ([_, container] of Object.entries(sections))
        container.el.innerHTML = ""
    books_in_sections = {}
    fetching_books = false
    can_get_next_books = true
}

function onOpenLibrary(el) {
    addUrlParams({"page": el.id})
    if (Section.current) Section.current.hide()
    section("all-books-section").show()
    fillFilterBySections()
    if (urlParams.get("favorite"))
        document.getElementById("library-title").innerHTML = "Библиотека: Избранное"
    else
        document.getElementById("library-title").innerHTML = "Библиотека"
    if (urlParams.get("reverse")) toggleReverseCheckbox(1)
    else toggleReverseCheckbox(0)
}

page("library-page").onHide = function() {
    clearLibraryFilters()
    clearLibrary()
}
page("library-page").onShow = onOpenLibrary

function onHideSection(el) {
    books_in_section = books_in_sections[el.id]
    document.getElementById("library-sections-container").scrollTop = 0
    fetching_books = false
    can_get_next_books = true
    if (books_in_section > 5) {
        books_in_sections[el.id] = 5
        while (el.children.length > 5)
            el.removeChild(el.lastChild)
    }
}
function addBooks(el) {
    var status = null
    if (el.id == "new-books-section") {status = "new"}
    else if (el.id == "in-progress-books-section") {status = "started"}
    else if (el.id == "listened-books-section") {status = "listened"}
    let books_in_section = books_in_sections[el.id]
    if (!books_in_sections.hasOwnProperty(el.id)) {
        books_in_section = 0
        books_in_sections[el.id] = 0
    }
    el.classList.add("loading")
    let sort = urlParams.get("sort")
    let reverse = urlParams.get("reverse")
    let author = urlParams.get("author")
    let series = urlParams.get("series")
    let favorite = urlParams.get("favorite")
    let search_query = urlParams.get("search_query")
    if (favorite != null)
        favorite = Boolean(Number(favorite))
    pywebview.api.get_library(
        10, books_in_section, sort, reverse, author, series, favorite, status, search_query
    ).then((response) => showBooks(response, status))
}

fetching_books = false
can_get_next_books = true
function onLibraryScrollEnd(el) {
    if (!can_get_next_books || fetching_books) return
    if (el.scrollHeight - el.offsetHeight - el.scrollTop < 100) {
        fetching_books = true
        addBooks(Section.current.el)
    }
}

function showBooks(response, status) {
    if (response.status != "ok") {console.log(response); return}

    if (status == null) {
        container = document.getElementById("all-books-section")
    } else if (status == "new") {
        container = document.getElementById("new-books-section")
    } else if (status == "started") {
        container = document.getElementById("in-progress-books-section")
    } else if (status == "listened") {
        container = document.getElementById("listened-books-section")
    }
    if (container.id != Section.current.el.id) return

    html = ""
    for (book of response.data) {
        html = html + `
          <div class="book-card" data-bid="${book.bid}", onclick="openBookPage(${book.bid})">
            <div class="book-preview" style="background-image: url(${book.preview})"></div>
            <div class="book-content">
              <div class="book-main-info-container">
                <div class="book-main-info">
                  <div class="book-title">${book.name}</div>
                  <div class="book-state">
                    <div class="book-listening-progress">${book.listening_progress} прослушано</div>
                    <div class="book-adding-date">Добавлена ${book.adding_date}</div>
                  </div>
                </div>
                <div class="book-actions">
                  <div class="icon-btn toggle-favorite-btn ${(book.favorite) ? 'active' : ''}" onclick="toggleFavorite(this, ${book.bid})"></div>
                  ${(book.downloaded) ? `<div class="icon-btn delete-btn" onclick="deleteBook(this, ${book.bid}, '${book.name}')"></div>` : `<div class="icon-btn download-btn ${(book.downloading) ? 'loading' : ''}" onclick="startDownloading(this, ${book.bid}, '${book.name}')"></div>`}
                  <div class="icon-btn remove-btn" onclick="removeBook(this, ${book.bid})"></div>
                </div>
              </div>
              <div class="book-description">${book.description}</div>
              <div class="book-additional-info">
                <div class="book-author">${book.author}</div>
                <div class="book-reader">${book.reader}</div>
                <div class="book-duration">${book.duration}</div>
                ${(book.series_name) ? `<div class="book-series">${book.series_name} (${book.number_in_series})</div>` : ''}
                <div class="book-driver">${book.driver}</div>
              </div>
            </div>
          </div>`
    }

    fetching_books = false
    if (response.data.length < 10) can_get_next_books = false
    books_in_sections[container.id] = books_in_sections[container.id] + response.data.length
    container.innerHTML = container.innerHTML + html
    container.classList.remove("loading")
}

function _toggleFavoriteActive(el) {
    if (el.classList.contains("active")) {
        el.classList.remove("active")
        return false
    } else {
        el.classList.add("active")
        return true
    }
}
function toggleFavorite(el, bid) {
    if (el.classList.contains("disabled")) return
    el.classList.add("disabled")
    let current_state = _toggleFavoriteActive(el)
    pywebview.api.toggle_favorite(bid).then(
        (response) => {
            el.classList.remove("disabled")
            if (response.status != "ok") {
                _toggleFavoriteActive(el)
                console.log(response)
                return
            }
            if (current_state != response.data)
                _toggleFavoriteActive(el)
        }
    )
}

function removeBook(el, bid) {
    if (el.classList.contains("loading")) return
    el.classList.add("loading")
    pywebview.api.remove_book(bid).then((resp) => {
        document.querySelector(`.book-card[data-bid='${bid}']`).remove()
    })
}

function deleteBook(el, bid, name) {
    if (el.classList.contains("loading")) return
    el.classList.add("loading")
    pywebview.api.delete_book(bid).then((resp) => {
        if (resp.status != "ok") {console.log(resp); return}
        deleteBtn = document.querySelector(`.book-card[data-bid='${bid}'] .delete-btn`)
        deleteBtn.classList.remove("delete-btn")
        deleteBtn.classList.add("download-btn")
        deleteBtn.onclick = function() {startDownloading(this, bid, name)}
    })
}

function openBookPage(bid) {
    if (window.event.srcElement.classList.contains("icon-btn")) return
    loadBookData(bid)
    addUrlParams({"bid": bid})
    page('book-page').show()
}
