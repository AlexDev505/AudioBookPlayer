var player = null;
var last_stop_flag_time = 0;

const volumeBtn = document.getElementById("volume-btn");
volumeBtn.onclick = function () {
  toggleVolumeSpeed("volume-input");
};
document.getElementById("speed-btn").onclick = function () {
  toggleVolumeSpeed("speed-input");
};

function setPlaybackBtnState(state) {
  let smallPlaybackBtn = document.querySelector("#player .playback-btn");
  smallPlaybackBtn.classList.remove("play");
  smallPlaybackBtn.classList.remove("pause");
  smallPlaybackBtn.classList.add(state);
  if (
    !opened_book ||
    !player.current_book ||
    player.current_book.bid != opened_book.bid
  )
    return;
  let bigPlaybackBtn = document.querySelector("#player-controls .playback-btn");
  bigPlaybackBtn.classList.remove("play");
  bigPlaybackBtn.classList.remove("pause");
  bigPlaybackBtn.classList.add(state);
}
function showListeningProgress(bid, percents) {
  let progress_text = document.querySelector(
    "template.book-progress[data-source='audio']",
  ).innerHTML;
  if (player.current_book && player.current_book.bid == bid)
    document.querySelector("#player .progress").innerHTML =
      `${percents}% ${progress_text}`;
  if (opened_book && opened_book.bid == bid)
    document.querySelector("#book-page .progress .content").innerHTML =
      `${percents}% ${progress_text}`;
}

document.addEventListener("DOMContentLoaded", (event) => {
  player = new window.Plyr("#audio-player", { storage: true, controls: [] });

  for (let scale of document.querySelectorAll('#player input[type="range"]')) {
    scale.oninput = scaleOninputDecorator(scale.oninput);
    scale.oninput();
  }

  player.on("pause", (event) => {
    setPlaybackBtnState("play");
  });
  player.on("play", (event) => {
    if (player.current_book.status != "in_progress") {
      pywebview.api.mark_audio_book_as_in_progress(player.current_source.sid);
      player.current_book.status = "in_progress";
      player.current_source.status = "in_progress";
    }
    setPlaybackBtnState("pause");
  });
  player.on("timeupdate", (event) => {
    if (!player.current_book) return;
    let progress_percent = Math.floor(
      (player.previous_chapters_duration + player.currentTime) /
        (player.total_duration / 100),
    );
    player.current_source.progress_percent = progress_percent;
    if (opened_book && player.current_book.bid == opened_book.bid) {
      showChapterPlaybackTime(
        player.currentTime / (player.duration / 100),
        Math.floor(player.currentTime),
      );
    }
    showListeningProgress(player.current_book.bid, progress_percent);
    if (Math.abs(player.currentTime - last_stop_flag_time) > 15) {
      player.current_source.progress.chapter_index =
        player.current_chapter_index;
      player.current_source.progress.time = Math.floor(player.currentTime);
      pywebview.api.set_listening_progress(
        player.current_source.sid,
        player.current_source.progress.chapter_index,
        player.current_source.progress.time,
      );
      last_stop_flag_time = player.currentTime;
    }
  });
  player.on("ended", (event) => {
    let next_chapter_index = player.current_chapter_index + 1;
    if (!player.current_source.chapters[next_chapter_index]) {
      pywebview.api.set_listening_progress(
        player.current_source.sid,
        player.current_chapter_index,
        Math.floor(player.duration),
      );
      player.current_book.status = "completed";
      player.current_source.status = "completed";
      player.current_source.progress_percent = "100";
      if (opened_book && player.current_book.bid == opened_book.bid)
        showBookState(player.current_book);
      return pywebview.api.mark_audio_book_as_completed(
        player.current_source.sid,
      );
    }
    _selectChapter(next_chapter_index);
    player.play();
  });
});

function initPlayer(book, source) {
  let playerEl = document.getElementById("player");
  playerEl.classList.remove("hidden");
  playerEl.querySelector(".playback-btn").style =
    `background-image: url('${source.cover}'), url('/library/${encodeURIComponent(book.dir_path + "\\" + source.local_cover)}');`;
  playerEl.querySelector(".book-title").innerHTML = book.title;
  showListeningProgress(book.bid, source.progress_percent);
  playerEl.querySelector(".book-info").dataset.bid = book.bid;
  player.current_book = book;
  player.current_source = source;
  let total_duration = 0;
  for (let chapter of source.chapters) {
    total_duration += chapter.end_time - chapter.start_time;
  }
  player.total_duration = total_duration;
  _selectChapter(source.progress.chapter_index);
  player.currentTime = source.progress.time;
  if (source.progress.time) {
    player.once("playing", (event) => {
      player.currentTime = source.progress.time;
    });
  }
}
function selectChapter(el) {
  let chapter_index = el.dataset.index;
  if (player.current_book.bid != opened_book.bid) return;
  if (player.current_chapter_index == chapter_index) return;
  _selectChapter(chapter_index);
}
function _selectChapter(chapter_index) {
  player.previous_chapters_duration = 0;
  for (let i of Array(Number(chapter_index)).keys()) {
    let chapter = player.current_source.chapters[i];
    player.previous_chapters_duration += chapter.end_time - chapter.start_time;
  }
  let playing = player.playing;
  _loadChapterSource(chapter_index);
  player.current_chapter_index = chapter_index;
  if (playing) player.play();
  if (opened_book && opened_book.bid == player.current_book.bid) {
    selectChapterEl(chapter_index);
  }
}
function _loadChapterSource(chapter_index) {
  let chapter = player.current_source.chapters[chapter_index];
  if (player.current_source.downloaded) {
    player.source = {
      type: "audio",
      title: "",
      sources: [
        {
          src: `/library/${encodeURIComponent(player.chapters.files[chapter.file_index])}`,
          type: "audio/mp3",
        },
      ],
    };
  } else {
    let fileType = "audio/mp3";
    try {
      const url = new URL(chapter.url);
      const pathname = url.pathname.toLowerCase();
      if (pathname.endsWith(".m3u8")) {
        fileType = "application/x-mpegURL";
      } else if (pathname.endsWith(".wav")) {
        fileType = "audio/wav";
      } else if (pathname.endsWith(".mp3")) {
        fileType = "audio/mp3";
      }
    } catch (e) {
      console.warn("Failed to parse URL for file type:", chapter.url);
    }

    player.source = {
      type: "audio",
      title: "",
      sources: [
        {
          src: chapter.url,
          type: fileType,
        },
      ],
    };
  }
  if (chapter.start_time !== 0) {
    player.once("playing", (event) => {
      player.currentTime = chapter.start_time;
    });
  }
}

function rewind() {
  if (!player.playing) return;
  if (player.current_book.bid != opened_book.bid) return;
  if (player.currentTime - 15 < 0 && player.current_chapter_index - 1 >= 0) {
    let t = player.currentTime;
    _selectChapter(player.current_chapter_index - 1);
    player.once("playing", (event) => {
      player.currentTime =
        player.current_source.chapters[player.current_chapter_index].end_time -
        player.current_source.chapters[player.current_chapter_index]
          .start_time -
        (15 - t);
    });
  } else player.rewind(15);
}
function forward() {
  if (!player.playing) return;
  if (player.current_book.bid != opened_book.bid) return;
  if (
    player.currentTime + 15 > player.duration &&
    player.current_chapter_index + 1 < player.current_source.chapters.length
  ) {
    let t = player.duration - player.currentTime;
    _selectChapter(player.current_chapter_index + 1);
    player.once("playing", (event) => {
      player.currentTime = 15 - t;
    });
  }
  player.forward(15);
}

function toggleVolumeSpeed(section) {
  if (section == "volume-input")
    document.getElementById("speed-input").classList.remove("showed");
  if (section == "speed-input")
    document.getElementById("volume-input").classList.remove("showed");
  let el = document.getElementById(section);
  if (el.classList.contains("showed")) el.classList.remove("showed");
  else el.classList.add("showed");
}
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
function clearPlayingBook() {
  if (!player.current_book) return;
  document.querySelector("#player").classList.add("hidden");
  player.stop();
  player.current_book = null;
}
function timeView(time) {
  return `${String(Math.floor(time / 60)).padStart(2, "0")}:${String(time % 60).padStart(2, "0")}`;
}
