var player = null;

document.addEventListener("DOMContentLoaded", (event) => {
  player = new window.Plyr("#audio-player", { storage: true, controls: [] });
  for (let scale of document.querySelectorAll('input[type="range"]')) {
    scale.oninput = scaleOninputDecorator(scale.oninput);
    scale.oninput();
  }
  player.on("pause", (event) => {
    let smallPlaybackControl = smallPlayer.querySelector(
      ".small-playback-control",
    );
    smallPlaybackControl.classList.add("play");
    smallPlaybackControl.classList.remove("pause");
    if (opened_book && player.current_book.bid != opened_book.bid) return;
    let bigPlaybackControl = document.getElementById("toggle-playback-btn");
    bigPlaybackControl.classList.add("play-button");
    bigPlaybackControl.classList.remove("pause-button");
  });
  player.on("play", (event) => {
    if (player.current_book.status != "started") {
      pywebview.api.mark_as_started(player.current_book.bid);
      player.current_book.status = "started";
    }
    let smallPlaybackControl = smallPlayer.querySelector(
      ".small-playback-control",
    );
    smallPlaybackControl.classList.remove("play");
    smallPlaybackControl.classList.add("pause");
    if (opened_book && player.current_book.bid != opened_book.bid) return;
    let bigPlaybackControl = document.getElementById("toggle-playback-btn");
    bigPlaybackControl.classList.remove("play-button");
    bigPlaybackControl.classList.add("pause-button");
  });
  player.on("timeupdate", (event) => {
    let listening_progress = Math.floor(
      (player.previous_items_duration + player.currentTime) /
        (player.total_duration / 100),
    );
    player.current_book.listening_progress = listening_progress;
    if (opened_book && player.current_book.bid == opened_book.bid) {
      let el = document.querySelector(".book-item.current");
      if (el.dataset.seeking) return;
      el.style.setProperty(
        "--current-item-percents",
        `${player.currentTime / (player.duration / 100)}%`,
      );
      document.querySelector(".book-item.current .cur-time").innerText =
        timeView(Math.floor(player.currentTime));
      document.querySelector(".book-listening-progress").innerText =
        `${listening_progress}% {{ gettext("book.listening_progress") }}`;
    }
    smallPlayer.querySelector(".listening-progres").innerText =
      `${listening_progress}% {{ gettext("book.listening_progress") }}`;
    if (Math.abs(player.currentTime - last_stop_flag_time) > 15) {
      pywebview.api.set_stop_flag(
        player.current_book.bid,
        player.current_item_index,
        Math.floor(player.currentTime),
      );
      last_stop_flag_time = player.currentTime;
    }
  });
  player.on("ended", (event) => {
    let next_item = player.current_item_index + 1;
    if (!player.current_book.files[next_item]) {
      pywebview.api.set_stop_flag(
        player.current_book.bid,
        player.current_item_index,
        Math.floor(player.duration),
      );
      player.current_book.status = "finished";
      initBookListeningProgress(player.current_book);
      return pywebview.api.mark_as_finished(player.current_book.bid);
    }
    _selectItem(next_item);
    player.play();
  });
});

function setVolume(value) {
  player.volume = value / 100;
  volumeBtn.classList.remove("muted");
  volumeBtn.classList.remove("low");
  volumeBtn.classList.remove("medium");
  if (value == 0) volumeBtn.classList.add("muted");
  else if (value <= 33) volumeBtn.classList.add("low");
  else if (value <= 66) volumeBtn.classList.add("medium");
}
function setSpeed(value) {
  player.speed = Number(value);
}
