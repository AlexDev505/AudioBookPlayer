page("book-page").onShow = function(el) {
    addUrlParams({"page": el.id})
    bid = urlParams.get("bid")
    if (bid) loadBookData(bid)
}
page("book-page").onHide = function() {
    document.getElementById("book-loading").style = "display: block;"
}


function loadBookData(bid) {
    pywebview.api.book_by_bid(bid).then((resp) => {
        if (resp.status != "ok") {console.log(resp); return}
        document.querySelector("#book-page-content .book-title").innerHTML = resp.data.name
        document.querySelector("#book-page-content .book-listening-progress").innerHTML = `${resp.data.listening_progress} прослушано`
        document.querySelector("#book-page-content .book-adding-date").innerHTML = `Добавлена ${resp.data.adding_date}`
        document.querySelector("#book-page-content .book-preview").style = `background-image: url(${resp.data.preview})`
        document.querySelector("#book-page-content .book-author").innerHTML = resp.data.author
        document.querySelector("#book-page-content .book-reader").innerHTML = resp.data.reader
        document.querySelector("#book-page-content .book-duration").innerHTML = resp.data.duration
        if (resp.data.series_name) {
            document.querySelector("#book-page-content .book-series").innerHTML = `${resp.data.series_name} (${resp.data.number_in_series})`
            document.querySelector("#book-page-content .book-series").style = "display: flex"
        } else document.querySelector("#book-page-content .book-series").style = "display: none"
        document.querySelector("#book-page-content .book-driver").innerHTML = resp.data.driver
        document.querySelector("#book-page-content .book-description").innerHTML = resp.data.description
        document.getElementById("book-loading").style = "display: none;"
    })
}
