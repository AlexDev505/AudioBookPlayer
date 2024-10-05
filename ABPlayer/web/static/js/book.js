page("book-page").onShow = function(el) {
    addUrlParams({"page": el.id})
    bid = urlParams.get("bid")
    if (bid) loadBookData(bid)
}
page("book-page").onHide = function() {
    document.getElementById("book-loading").style = "display: block;"
    urlParams.delete("bid")
}

const player = new Plyr("#audio-player", {storage: true, controls: []})
last_stop_flag_time = 0


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
            player.current_book = resp.data
            document.getElementById("player-controls").style = "display: flex"
            document.getElementById("player").classList.remove("not-available")
            html = ""
            i = 0
            for (item of resp.data.items) {
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
            selectItem(resp.data.stop_flag.item)
            if (resp.data.stop_flag.time) {
                player.play()
                player.once("playing", (event) => {player.currentTime = resp.data.stop_flag.time; player.pause()})
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
    document.getElementById("toggle-playback-btn").classList.add("play-button")
    document.getElementById("toggle-playback-btn").classList.remove("pause-button")
})
player.on("play", (event) => {
    document.getElementById("toggle-playback-btn").classList.remove("play-button")
    document.getElementById("toggle-playback-btn").classList.add("pause-button")
})
player.on("timeupdate", (event) => {
    el = document.querySelector(".book-item.current")
    if (el.dataset.seeking) return
    el.style.setProperty('--current-item-percents', `${player.currentTime/ (player.duration / 100)}%`)
    document.querySelector(".book-item.current .cur-time").innerText = timeView(Math.floor(player.currentTime))
    if (Math.abs(player.currentTime - last_stop_flag_time) > 15) {
        pywebview.api.set_stop_flag(player.current_book.bid, player.current_item_index, Math.floor(player.currentTime))
        last_stop_flag_time = player.currentTime
    }
})
player.on("ended", (event) => {
    next_item = player.current_item_index + 1
    if (!player.current_book.files[next_item]) return
    selectItem(next_item)
    player.play()
})

function togglePlayback(btn) {
    player.togglePlay()
}
function rewind() {
    if (!player.playing) return
    if (player.currentTime - 15 < 0 && player.current_item_index - 1 >= 0) {
        t = player.currentTime
        selectItem(player.current_item_index - 1)
        player.once("playing", (event) => {player.currentTime = player.current_book.items[0].end_time - player.current_book.items[0].start_time - (15 - t)})
    } else player.rewind(15)
}
function forward() {
    if (!player.playing) return
    if (
        player.currentTime + 15 > player.duration
        && player.current_item_index + 1 < player.current_book.files.length
    ) {
        t = player.duration - player.currentTime
        selectItem(player.current_item_index + 1)
        player.once("playing", (event) => {player.currentTime = 15 - t})
    } player.forward(15)
}
function selectItem(item_index) {
    cur_item = document.querySelector(".book-item.current")
    new_item = document.querySelector(`.book-item[data-index="${item_index}"]`)
    if (cur_item) {
        if (player.current_item_index == item_index) return
        cur_item.classList.remove("current")
    }
    new_item.classList.add("current")
    playing = player.playing
    player.source = {type: "audio", title: "", sources: [{src: `/library/${player.current_book.files[item_index]}`, type: "audio/mp3"}]};
    player.current_item_index = item_index
    if (playing) player.play()
}
function bookItemOnmousedown(event, el) {
    if (!el.classList.contains("current")) return
    if (!player.playing) return
    el.dataset.seeking = "1"
    percents = event.offsetX / (el.offsetWidth / 100)
    el.style.setProperty('--current-item-percents', `${percents}%`)
    document.querySelector(".book-item.current .cur-time").innerText = timeView(
        Math.floor(player.duration / 100 * percents)
    )
}
function bookItemOnmousemove(event, el) {
    if (!el.dataset.seeking) return
    percents = event.offsetX / (el.offsetWidth / 100)
    el.style.setProperty('--current-item-percents', `${percents}%`)
    document.querySelector(".book-item.current .cur-time").innerText = timeView(
        Math.floor(player.duration / 100 * percents)
    )
}
function bookItemOnmouseup(event, el) {
    if (!el.dataset.seeking) return
    delete el.dataset.seeking
    if (event.type == "mouseout") return
    percents = event.offsetX / (el.offsetWidth / 100)
    time = player.duration / 100 * percents
    el.style.setProperty('--current-item-percents', `${percents}%`)
    document.querySelector(".book-item.current .cur-time").innerText = timeView(Math.floor(time))
    player.currentTime = time
}

function timeView(time) {
    return `${String(Math.floor(time/60)).padStart(2, '0')}:${String(time%60).padStart(2, '0')}`
}
