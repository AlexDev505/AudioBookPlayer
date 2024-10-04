page("book-page").onShow = function(el) {
    addUrlParams({"page": el.id})
    bid = urlParams.get("bid")
    if (bid) loadBookData(bid)
}
page("book-page").onHide = function() {
    document.getElementById("book-loading").style = "display: block;"
    urlParams.delete("bid")
}


function loadBookData(bid) {
    pywebview.api.book_by_bid(bid, true).then((resp) => {
        if (resp.status != "ok") {showError(resp.message); return}
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
        document.getElementById("player-controls").style = "display: none"
        document.getElementById("player-downloading-required").style = "display: none"
        document.getElementById("player-downloading").style = "display: none"
        if (resp.data.downloaded) {
            document.getElementById("player-controls").style = "display: flex"
            document.getElementById("player").classList.remove("not-available")
            html = ""
            for (item of resp.data.items) {
                html += `<div class="book-item">
                  <span class="title">${item.title}</span>
                  <span class="time">00:00 / ${timeView(item.end_time - item.start_time)}</span>
                </div>`
            }
            document.getElementById("items-container").innerHTML = html
        } else {
            document.getElementById("player").classList.add("not-available")
            if (resp.data.downloading) document.getElementById("player-downloading").style = "display: block"
            else {
                document.getElementById("player-downloading-required").style = "display: block"
                document.getElementById("download-book-btn").onclick = function() {
                    startDownloading(this, resp.data.bid, resp.data.name)
                    document.getElementById("player-downloading-required").style = "display: none"
                    document.getElementById("player-downloading").style = "display: block"
                }
            }
        }
        document.getElementById("book-loading").style = "display: none;"
    })
}

function timeView(time) {
    return `${String(Math.floor(time/60)).padStart(2, '0')}:${String(time%60).padStart(2, '0')}`
}
