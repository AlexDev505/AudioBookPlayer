const player = new Plyr("#audio-player", {storage: true, controls: []})
opened_book = null
last_stop_flag_time = 0

page("book-page").onShow = function(el) {
    addUrlParams({"page": el.id})
    let bid = urlParams.get("bid")
    if (bid) loadBookData(bid)
}
page("book-page").onHide = function() {
    document.getElementById("book-loading").style = "display: block;"
    urlParams.delete("bid")
    opened_book = null
    if (!player.playing && player.current_book) {
        player.current_book = null
        player.current_item_index = null
        last_stop_flag_time = 0
    }
}

function loadBookData(bid) {
    pywebview.api.book_by_bid(bid, true).then((resp) => {
        opened_book = resp.data
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
            let playBtn = document.getElementById("toggle-playback-btn")
            playBtn.classList.remove("pause-button")
            playBtn.classList.add("play-button")
            document.getElementById("player-controls").style = "display: flex"
            document.getElementById("player").classList.remove("not-available")
            let html = ""
            let i = 0
            for (let item of resp.data.items) {
                html += `<div class="book-item" data-index="${i}"
                    onclick="selectItem(${i})"
                    onmousedown="bookItemOnmousedown(event, this)"
                    onmousemove="bookItemOnmousemove(event, this)"
                    onmouseup="bookItemOnmouseup(event, this)"
                    onmouseout="bookItemOnmouseup(event, this)">
                  <span class="title">${item.title}</span>
                  <span class="time"><span class="cur-time">00:00</span> / ${timeView(item.end_time - item.start_time)}</span>
                </div>`
                i++
            }
            document.getElementById("items-container").innerHTML = html

            document.getElementById("items-container").scrollTo(
                0, (document.querySelector(".book-item").clientHeight + 2) * (resp.data.stop_flag.item - 1)
            )
            let el = document.querySelector(`.book-item[data-index="${resp.data.stop_flag.item}"]`)
            el.classList.add("current")
            let duration = resp.data.items[resp.data.stop_flag.item].end_time - resp.data.items[resp.data.stop_flag.item].start_time
            el.style.setProperty('--current-item-percents',`${resp.data.stop_flag.time / (duration / 100)}%`)
            document.querySelector(".book-item.current .cur-time").innerText = timeView(Math.floor(resp.data.stop_flag.time))

            if (!player.current_book) initBook(resp.data)
            else {
                if (player.current_book.bid == opened_book.bid && player.playing) {
                    playBtn.classList.add("pause-button")
                    playBtn.classList.remove("play-button")
                }
            }
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

player.on("pause", (event) => {
    if (player.current_book.bid != opened_book.bid) return
    document.getElementById("toggle-playback-btn").classList.add("play-button")
    document.getElementById("toggle-playback-btn").classList.remove("pause-button")
})
player.on("play", (event) => {
    if (player.current_book.bid != opened_book.bid) return
    document.getElementById("toggle-playback-btn").classList.remove("play-button")
    document.getElementById("toggle-playback-btn").classList.add("pause-button")
})
player.on("timeupdate", (event) => {
    if (opened_book && player.current_book.bid == opened_book.bid) {
        let el = document.querySelector(".book-item.current")
        if (el.dataset.seeking) return
        el.style.setProperty('--current-item-percents', `${player.currentTime/ (player.duration / 100)}%`)
        document.querySelector(".book-item.current .cur-time").innerText = timeView(Math.floor(player.currentTime))
    }
    if (Math.abs(player.currentTime - last_stop_flag_time) > 15) {
        pywebview.api.set_stop_flag(player.current_book.bid, player.current_item_index, Math.floor(player.currentTime))
        last_stop_flag_time = player.currentTime
    }
})
player.on("ended", (event) => {
    let next_item = player.current_item_index + 1
    if (!player.current_book.files[next_item]) return
    _selectItem(next_item)
    player.play()
})

function initBook(book) {
    player.current_book = book
    _selectItem(book.stop_flag.item)
    if (book.stop_flag.time) {
        player.play()
        player.once("playing", (event) => {player.currentTime = book.stop_flag.time; player.pause()})
    }
}
function togglePlayback(btn) {
    if (player.current_book.bid != opened_book.bid) {
        initBook(opened_book)
        player.once("pause", (event) => {player.play()})
        return
    }
    player.togglePlay()
}
function rewind() {
    if (!player.playing) return
    if (player.current_book.bid != opened_book.bid) return
    if (player.currentTime - 15 < 0 && player.current_item_index - 1 >= 0) {
        let t = player.currentTime
        selectItem(player.current_item_index - 1)
        player.once("playing", (event) => {player.currentTime = (
            player.current_book.items[player.current_item_index].end_time
            - player.current_book.items[player.current_item_index].start_time - (15 - t)
        )})
    } else player.rewind(15)
}
function forward() {
    if (!player.playing) return
    if (player.current_book.bid != opened_book.bid) return
    if (
        player.currentTime + 15 > player.duration
        && player.current_item_index + 1 < player.current_book.files.length
    ) {
        let t = player.duration - player.currentTime
        selectItem(player.current_item_index + 1)
        player.once("playing", (event) => {player.currentTime = 15 - t})
    } player.forward(15)
}
function selectItem(item_index) {
    if (player.current_book.bid != opened_book.bid) return
    if (player.current_item_index == item_index) return
    _selectItem(item_index)
}
function _selectItem(item_index) {
    let playing = player.playing
    player.source = {type: "audio", title: "", sources: [{src: `/library/${player.current_book.files[item_index]}`, type: "audio/mp3"}]};
    player.current_item_index = item_index
    if (playing) player.play()
    if (player.current_book.bid == opened_book.bid) {
        let cur_item = document.querySelector(".book-item.current")
        let new_item = document.querySelector(`.book-item[data-index="${item_index}"]`)
        if (cur_item) cur_item.classList.remove("current")
        new_item.classList.add("current")
        if (player.current_item_index - 1 >= 0)
            document.getElementById("items-container").scrollTo(
                0, (document.querySelector(".book-item").clientHeight + 2) * (player.current_item_index - 1)
            )
    }
}
function bookItemOnmousedown(event, el) {
    if (player.current_book.bid != opened_book.bid) return
    if (!el.classList.contains("current")) return
    if (!player.playing) return
    el.dataset.seeking = "1"
    let percents = event.offsetX / (el.offsetWidth / 100)
    el.style.setProperty('--current-item-percents', `${percents}%`)
    document.querySelector(".book-item.current .cur-time").innerText = timeView(
        Math.floor(player.duration / 100 * percents)
    )
}
function bookItemOnmousemove(event, el) {
    if (!el.dataset.seeking) return
    let percents = event.offsetX / (el.offsetWidth / 100)
    el.style.setProperty('--current-item-percents', `${percents}%`)
    document.querySelector(".book-item.current .cur-time").innerText = timeView(
        Math.floor(player.duration / 100 * percents)
    )
}
function bookItemOnmouseup(event, el) {
    if (!el.dataset.seeking) return
    delete el.dataset.seeking
    if (event.type == "mouseout") return
    let percents = event.offsetX / (el.offsetWidth / 100)
    let time = player.duration / 100 * percents
    el.style.setProperty('--current-item-percents', `${percents}%`)
    document.querySelector(".book-item.current .cur-time").innerText = timeView(Math.floor(time))
    player.currentTime = time
}

function timeView(time) {
    return `${String(Math.floor(time/60)).padStart(2, '0')}:${String(time%60).padStart(2, '0')}`
}
