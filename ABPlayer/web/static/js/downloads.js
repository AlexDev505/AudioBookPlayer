page("downloads-page").onShow = function(el) {
    addUrlParams({"page": el.id})
}
page("downloads-page").onHide = function() {}

function showDownloads(response) {
    for (download_process of response.data) {
        createDownloadingCard(download_process[0], download_process[1])
        setDownloadingStatus(download_process[0], download_process[2])
        if (download_process[3])
            initTotalSize(download_process[0], download_process[3])
    }
}
function startDownloading(button, bid, title) {
    if (button) {
        if (button.classList.contains("loading")) return
        button.classList.add("loading")
    }
    pywebview.api.download_book(bid).then((response) => {
        if (response.status != "ok") {
            console.log(response)
            removeDownloadingCard(response.extra.bid)
            return
        } else {
            if (response.data.bid)
                setDownloadingStatus(response.data.bid, "waiting")
        }
    })
    createDownloadingCard(bid, title)
}

function createDownloadingCard(bid, title) {
    container = document.getElementById("downloads-container")
    html = `
    <div class="download-card" data-bid="${bid}">
      <div>
        <div class="book-title">${title}</div>
        <div class="status">инициализация...</div>
        <div class="progress-info">
          <div class="percents"></div>
          <div class="data-size"></div>
        </div>
      </div>
      <div>
        <div class="icon-btn cancel-btn" onclick="terminateDownloading(${bid})"></div>
      </div>
      <div class="progress-bar"></div>
    </div>`
    container.innerHTML = container.innerHTML + html
}
function setDownloadingStatus(bid, status) {
    status_el = document.querySelector(`.download-card[data-bid='${bid}'] .status`)
    status_el.style = ((status == "downloading") ? "display: none" : "")
    if (status == "finished") document.querySelector(`.download-card[data-bid='${bid}']`).dataset["finished"] = "1"

    if (status == "waiting") status_el.innerHTML = "ожидание..."
    else if (status == "preparing") status_el.innerHTML = "подготовка..."
    else if (status == "downloading") status_el.innerHTML = "скачивание..."
    else if (status == "finishing") status_el.innerHTML = "завершение..."
    else if (status == "finished") status_el.innerHTML = "скачивание завершено"
    else if (status == "terminating") status_el.innerHTML = "остановка..."
    else if (status == "terminated") removeDownloadingCard(bid)
}
function initTotalSize(bid, total_size) {
    data_size = document.querySelector(`.download-card[data-bid='${bid}'] .data-size`)
    data_size.dataset["total_size"] = total_size
}
function downloadingCallback(bid, percents, size) {
    percents_el = document.querySelector(`.download-card[data-bid='${bid}'] .percents`)
    data_size_el = document.querySelector(`.download-card[data-bid='${bid}'] .data-size`)
    pb_el = document.querySelector(`.download-card[data-bid='${bid}'] .progress-bar`)
    percents_el.innerHTML = `${percents}%`
    data_size_el.innerHTML = `${size} / ${data_size_el.dataset['total_size']}`
    pb_el.style.width = `${percents}%`
}
function terminateDownloading(bid) {
    if (document.querySelector(`.download-card[data-bid='${bid}']`).dataset["finished"])
        removeDownloadingCard(bid)
    else {
        document.querySelector(`.download-card[data-bid='${bid}'] .cancel-btn`).classList.add("loading")
        pywebview.api.terminate_downloading(bid)
    }
}

function removeDownloadingCard(bid) {
    document.querySelector(`.download-card[data-bid='${bid}']`).remove()
}

function endLoading(bid) {
    if (document.querySelector(`.book-card[data-bid='${bid}']`)) applyFilters()
}

