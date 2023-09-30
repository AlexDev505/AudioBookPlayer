filterMenu = document.getElementById("filter-menu")
var filter_menu_opened = true
function toggleFilterMenu() {
    if (filter_menu_opened)
        filterMenu.classList.add("collapsed")
    else
        filterMenu.classList.remove("collapsed")
    filter_menu_opened = !filter_menu_opened
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

page("library-page").onHide = function(el) {
}
page("library-page").onShow = function(el) {
    addUrlParams({"page": el.id})
    sort = urlParams.get("sort")
    author = urlParams.get("author")
    series = urlParams.get("series")
    favorite = urlParams.get("favorite")
    section("all-books-section").show()
}

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
    pywebview.api.get_library(
        10, books_in_section, sort, author, series, favorite, status
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
    console.log(container.id, Section.current.el.id)
    if (container.id != Section.current.el.id) return

    html = ""
    for (book of response.data) {
        html = html + `
          <div class="book-card">
            <div class="book-preview" style="background-image: url(${book.preview})"></div>
            <div class="book-content">
              <div class="book-main-info-container">
                <div class="book-main-info">
                  <div class="book-title">${book.name}</div>
                  <div class="book-state">
                    <div class="book-listening-progress">${book.listening_progress}% listened</div>
                    <div class="book-adding-date">Добавлена ${book.adding_date}</div>
                  </div>
                </div>
                <div class="book-actions">
                  <div class="icon-btn toggle-favorite-btn ${(book.favorite) ? 'active' : ''}"></div>
                  ${(book.downloaded) ? '<div class="icon-btn delete-btn"></div>' : '<div class="icon-btn download-btn"></div>'}
                </div>
              </div>
              <div class="book-description">${book.description}</div>
              <div class="book-additional-info">
                <div class="book-author">${book.author}</div>
                <div class="book-reader">${book.reader}</div>
                <div class="book-duration">${book.duration}</div>
                <div class="book-series">${book.series_name} (${book.number_in_series})</div>
                <div class="book-driver">${book.driver}</div>
              </div>
            </div>
          </div>`
    }

    fetching_books = false
    if (!html && !container.innerHTML) {container.classList.add("empty")}
    else {container.classList.remove("empty")}
    if (response.data.length < 10) can_get_next_books = false
    books_in_sections[container.id] = books_in_sections[container.id] + response.data.length
    container.innerHTML = container.innerHTML + html
    container.classList.remove("loading")
}
